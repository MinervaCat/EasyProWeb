from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from typing import List
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage
import os
from datetime import datetime
import json
from app.tools import get_master_tool
from app.graph.state.state import AgentState, SubTask
from app.graph.prompts import MASTER_SYSTEM_PROMPT
from app.utils import read_json, write_json, get_env_info
from langchain_core.messages import message_to_dict
class MasterAgent:
    def __init__(self, model: str = "gpt-4o-mini"):
        self.llm = ChatOpenAI(
            model="glm-4.7",  # 这里填写通义千问的模型名
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",  # 关键：指定阿里云兼容端点
            temperature=0.2,
        )
        tools = get_master_tool()
        self.llm_with_tools = self.llm.bind_tools(tools)
        self.tool_map = {t.name: t for t in tools}
        self.max_steps = 5

    async def run(self, state: AgentState) -> AgentState:
        print(f"💻 Master: 正在分配任务... ")
        prompt = ChatPromptTemplate.from_messages([
            ("system", MASTER_SYSTEM_PROMPT),
            ("human", """
            # Context
            - Project Summary: {project_summary}
            - Project Milestones: {milestones}
            - Your Working Directory:
            {current_env_info}
            """),
            MessagesPlaceholder(variable_name="chat_history"),
        ])
        project_plan = await read_json("project_plan.json")
        milestones = await read_json("milestones.json")
        current_step = 0

        chat_history = []

        if "task_summary" in state:
            chat_history.append(AIMessage(
                content=state.get("tool_content"),
                tool_call_id=state.get("tool_call_id"),
            ))
            chat_history.append(ToolMessage(
                content=state.get("task_summary"),
                tool_call_id=state.get("tool_call_id"),
            ))
        while current_step < self.max_steps:
            current_step += 1
            # current_file_tree = get_file_tree(project_plan.get("project_name"))
            try:
                # 生成代码
                messages = prompt.format_messages(
                    project_summary=project_plan.get("summary"),
                    milestones=milestones,
                    current_env_info=get_env_info(),
                    chat_history=chat_history,
                )
                response = await self.llm_with_tools.ainvoke(messages)

                # 1. 准备要保存的数据
                log_data = {
                    "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
                    "input_messages": [message_to_dict(m) for m in messages],
                    "output_response": message_to_dict(response)
                }
                # 创建 logs 文件夹
                os.makedirs("logs", exist_ok=True)
                filename = f"logs/chat.json"

                with open(filename, "a", encoding="utf-8") as f:
                     f.write(json.dumps(log_data, ensure_ascii=False) + "\n")
                # response_list.append(response.model_dump())
                if response.tool_calls:
                    if len(response.tool_calls) > 1:
                        print("tool_calls数量大于1")
                    # chat_history.append(AIMessage(content=response.content))
                    tc = response.tool_calls[0]
                    chat_history.append(AIMessage(
                        content=response.content,
                        tool_call_name=tc['name'],
                        tool_call_id=tc['id'],
                    ))
                    if tc['name'] not in self.tool_map:
                        print(f"❌ 错误：找不到名为 '{tc['name']}' 的工具。")
                        break
                    elif tc['name'] == 'delegate_task':
                        task = SubTask(
                            instruction=tc['args'].get("instruction", ""),
                            target_files=tc['args'].get("target_files", []),
                            context_files=tc['args'].get("context_files", []),
                            test_file_name=tc['args'].get("test_file_name", ""),
                            test_command=tc['args'].get("test_command", ""),
                            success_criteria=tc['args'].get("success_criteria", ""),
                        )
                        state["tool_content"] = response.content
                        state["tool_call_id"] = tc['id']
                        state["sub_task"] = task
                        break
                    elif tc['name'] == 'finish_milestone':
                        milestone_id = tc['args'].get("milestone_id", "")
                        for milestone in milestones:
                            if milestone["id"] == milestone_id:
                                milestone["status"] = "completed"
                                milestone["summary"] = state.get("task_summary", "")
                                break
                        print(milestone_id + "已完成")
                        write_json("milestones.json", milestones)
                        chat_history.append(ToolMessage(
                            content=f"里程碑{milestone_id}已完成，请开始实施下个里程碑",
                            tool_call_id=tc['id'],
                        ))

                    elif tc['name'] == 'finish_project':
                        state["project_status"] = "finished"
                        print("项目结束")
                        break
                    else:
                        tool_result = await self.tool_map[tc['name']].ainvoke(tc["args"])
                        chat_history.append(ToolMessage(
                            content=tool_result,
                            tool_call_id=tc['id'],
                        ))
                        print("继续调用工具")
                else:
                    print("No tool calls")
                    break

            except Exception as e:
                print(f"❌ Master 错误: {e}")
                # state.error_message = f"Coding failed: {str(e)}"

        return state


