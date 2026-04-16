"""
Planner Agent - 负责需求分析和任务拆解
"""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from app.graph.prompts import PLANNER_CONFIRM_REQUIREMENT, PLANNER_CREATE_PLAN
from app.graph.state.state import AgentState, AnalysisResult

from app.utils.file import write_json


class PlannerAgent:
    """
    Planner 职责：
    1. 理解用户需求
    2. 拆解为可执行的任务列表
    3. 设计文件结构和接口定义
    """

    def __init__(self, model: str = None):
        self.llm = ChatOpenAI(
            model="qwen3-vl-32b-thinking",  # 这里填写通义千问的模型名
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",  # 关键：指定阿里云兼容端点
            temperature=0.3,
        )
        self.parser = JsonOutputParser()

    async def run(self, state: AgentState, config: RunnableConfig) -> AgentState:
        """执行规划，通过 interrupt 循环等待用户澄清需求"""

        print("🔍 PM: 正在分析需求...")
        prompt = ChatPromptTemplate.from_messages([
            ("system", PLANNER_CONFIRM_REQUIREMENT),
            MessagesPlaceholder(variable_name="chat_messages"),  # ReAct 思考路径
        ])
        chain = prompt | self.llm.with_structured_output(AnalysisResult)

        # latest_message = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
        # chat_history_str = "\n".join([f"{msg.type}: {msg.content}" for msg in messages[:-1]])
        chat_messages = state["messages"]
        result = await chain.ainvoke({
            "confirmed_requirements": str(state.get("confirmed_requirements", {})),
            "chat_messages": chat_messages,
        })
        print(result)
        # if result.summary:
        #     state["confirmed_requirements"] = result.summary

        if result.is_complete:
            await self._generate_plan(result.summary, config)
            return {"status": "plan_completed"}

        else:
            # 需要继续提问：先展示问题，再通过 interrupt 等待用户输入
            questions_text = "\n".join([f"- {q}" for q in result.questions])
            response_text = (
                f"📋 **需求分析总结**: {result.summary}\n\n"
                f"❓ **为了制定合理的规划，我需要您澄清以下几点**:\n{questions_text}"
            )

            # messages.append(ai_msg)
            # 挂起节点，将问题文本呈现给外部调用方，等待用户回答
            # user_response = interrupt(response_text)
            # human_msg = HumanMessage(content=user_response)
            # state["messages"].append(human_msg)

            return {
                "messages": [AIMessage(content=response_text)],
                "status": "plan_running"
            }


    async def _generate_plan(self, requirement: str, config: RunnableConfig):
        """执行规划"""
        print("生成项目规划...")
        prompt = ChatPromptTemplate.from_messages([
            ("system", PLANNER_CREATE_PLAN),
            ("human", "请根据用户需求制定实施计划。用户需求：{requirement}")
        ])
        chain = prompt | self.llm
        try:
            # 变化 1: 你的文件工具如果支持异步，也需要 await
            # requirement_document = await self.file_tools.read_file("PRD.md")
            # if not requirement_document:
            #     print("can't read PRD.md")

            # 变化 2: LangChain 的执行方法必须从 invoke 改为 ainvoke
            result = await chain.ainvoke({"requirement": requirement})

            print(result.content)
            workspace_dir = config.get("configurable", {}).get("workspace_dir", "./workspace")

            # 2. 显式拼接后传给 util
            plan_path = f"{workspace_dir}/project_plan.json"
            # 变化 3: 文件写入也要 await
            await write_json(plan_path, result.content)

            # state["milestone_index"] = 0

            # 同理，如果后续有 structured_output 的逻辑：
            # chain2 = self._get_prompt2() | self.llm.with_structured_output(TaskList)
            # result2 = await chain2.ainvoke({"project_plan": project_plan})
            # state["task_list"] = result2.task_list
            # state["current_task_index"] = 0

        except Exception as e:
            print(f"❌ 生成项目规划时出现错误: {e}")



