from typing import Annotated, TypedDict
import operator
import asyncio

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from app.graph import AgentState, PlannerAgent, HumanNode

# 1. 定义状态 (State)
# ==========================================
class KyberState(TypedDict):
    # messages 列表，使用 operator.add 确保每次更新是追加而不是覆盖
    messages: Annotated[list[BaseMessage], operator.add]
# ==========================================
# 2. 定义服务类 (Service)
# ==========================================
class AgentService:
    def __init__(self):
        # 使用内存来存储 Checkpoint，适合开发测试
        # 生产环境中可以换成 SqliteSaver 或 RedisSaver
        self.planner = PlannerAgent()
        self.human = HumanNode()
        self.checkpointer = MemorySaver()
        self._build_graph()



    def _build_graph(self):
        """构建 LangGraph 状态图"""
        workflow = StateGraph(AgentState)

        # 添加节点
        workflow.add_node("planner", self.planner.run)
        # 添加一个专门用于“挂起/等待”的虚拟节点
        workflow.add_node("human", self.human.run)


        # 设置入口
        workflow.set_entry_point("planner")

        # 设置条件边：Planner 执行完后，该去哪？
        # workflow.add_conditional_edges(
        #     "planner",
        #     self._check_plan_completion,
        #     {
        #         "continue": "human",  # 去往 human 节点等待输入
        #         "next": END  # 讨论完毕，结束
        #     }
        # )
        workflow.add_edge("planner", "human")
        workflow.add_conditional_edges(
            "human",
            self._check_plan_completion,
            {
                "continue": "planner",  # 去往 human 节点等待输入
                "next": "master"
            }
        )



        # 用户输入完毕后，流转回 Planner 继续思考
        workflow.add_edge("human", "planner")

        # 编译图，并设置在 "human" 节点之前强制中断
        self.graph = workflow.compile(
            checkpointer=self.checkpointer,
            interrupt_before=["human"]
        )

    # ==========================================
    # 3. 节点逻辑 (Nodes)
    # ==========================================
    async def _planner_node(self, state: KyberState):
        """Planner Agent 核心逻辑 (这里使用 Mock 模拟 LLM)"""
        await asyncio.sleep(1)  # 模拟大模型思考延迟

        messages = state["messages"]
        user_msg = messages[-1].content

        # --- Mock 逻辑开始 ---
        # 假设只要用户输入包含 "确认"，我们就结束需求收集
        if "确认" in user_msg:
            doc_content = "# 需求文档\n用户需求已确认生成。"
            # 这里后续可以调用写文件的 Tool
            return {"messages": [AIMessage(content=f"太棒了！需求收集完毕。正在为您生成文档：\n{doc_content}")]}

        # 否则，继续追问
        reply = f"我已收到您的想法：'{user_msg}'。请问这个项目需要包含前端界面吗？（输入'确认'结束讨论）"
        return {"messages": [AIMessage(content=reply)]}
        # --- Mock 逻辑结束 ---

    async def _human_node(self, state: AgentState):
        """
        这是一个被动的节点，实际不执行任何操作。
        它的存在只是为了让 LangGraph 有个地方可以 Interrupt。
        """

        pass

    def _check_plan_completion(self, state: AgentState) -> str:
        if state["status"] == "plan_completed":
            return "next"
        return "continue"

    def _should_continue(self, state: KyberState) -> str:
        """路由函数：判断是继续追问，还是结束"""
        last_msg = state["messages"][-1]
        # 如果最后一条消息是 AI 发的，且包含“生成文档”，说明聊完了
        if isinstance(last_msg, AIMessage) and "需求收集完毕" in last_msg.content:
            return "finish"
        return "ask_user"

    # ==========================================
    # 4. 供 API 调用的生成器入口 (核心流式交互)
    # ==========================================
    async def run_graph(self, session_id: str, user_input: str):
        # 1. 动态生成该 session 专属的工作路径
        # 例如：每个会话的数据保存在 ./workspaces/session-xxx/ 下
        user_workspace = f"./workspaces/{session_id}"

        # 确保文件夹存在
        import os
        os.makedirs(user_workspace, exist_ok=True)

        # 2. 将 workspace_dir 塞进 configurable 配置字典中
        config = {
            "configurable": {
                "thread_id": session_id,  # 留给 checkpointer 存档用
                "workspace_dir": user_workspace  # 留给 Tools 工具库用
            }
        }

        # 获取当前图的状态
        state = self.graph.get_state(config)

        # 判断当前是否处于被中断的状态（即等待在 human 节点）
        if state.next and "human" in state.next:
            # 1. 恢复执行：将用户的最新回复作为 human 节点的输出强行塞入状态
            self.graph.update_state(
                config,
                {"messages": [HumanMessage(content=user_input)]},
                as_node="human"
            )
            input_data = None  # 因为已经手动更新了状态，直接告诉图继续跑
        else:
            # 2. 全新对话
            input_data = {"messages": [HumanMessage(content=user_input)]}

        # 启动异步流式生成
        async for event in self.graph.astream(input_data, config, stream_mode="updates"):
            for node_name, node_data in event.items():

                # 推送系统日志
                yield {"type": "log", "content": f"[{node_name}] 节点执行完毕"}

                # 如果节点产生了新的消息，提取并推送给前端
                if "messages" in node_data and node_data["messages"]:
                    last_msg = node_data["messages"][-1]
                    if isinstance(last_msg, AIMessage):
                        yield {"type": "assistant", "content": last_msg.content}

        # 一轮执行结束后，检查是否停在了中断点
        new_state = self.graph.get_state(config)
        if new_state.next and "human" in new_state.next:
            yield {"type": "interrupt", "content": "等待用户回复..."}