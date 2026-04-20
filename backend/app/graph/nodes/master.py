from typing import List

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage
import os
from datetime import datetime
import json
from app.tools import get_master_tool
from app.graph.state.state import AgentState, SubTask, MilestoneList
from app.graph.prompts import MASTER_SYSTEM_PROMPT, MASTER_CREATE_MILESTONE
from app.utils import read_json, write_json, get_env_info, read_file_async, save_file_async, path_exists_async, makedirs_async
from langchain_core.messages import message_to_dict
from langchain_core.runnables import RunnableConfig

class MasterAgent:
    def __init__(self, model: str = "gpt-4o-mini"):
        self.llm = ChatOpenAI(
            model="qwen3.6-flash",  # 这里填写通义千问的模型名
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",  # 关键：指定阿里云兼容端点
            temperature=0.2,
        )
        tools = get_master_tool()
        self.llm_with_tools = self.llm.bind_tools(tools)
        self.tool_map = {t.name: t for t in tools}
        self.max_steps = 5

    async def run(self, state: AgentState, config: RunnableConfig) -> AgentState:
        print(f"💻 Master: 正在分配任务... ")
        prompt = ChatPromptTemplate.from_messages([
            ("system", MASTER_SYSTEM_PROMPT),
            ("human", """
            # Context
            - Project Plan: {project_plan}
            - Project Milestones: {milestones}
            - Your Working Directory:
            {current_env_info}
            """),
            MessagesPlaceholder(variable_name="chat_history"),
        ])

        workspace_dir = config.get("configurable", {}).get("workspace_dir", "./workspace")

        # 2. 显式拼接后传给 util
        plan_path = f"{workspace_dir}/project_plan.md"
        project_plan = await read_file_async(plan_path)
        milestone_path = f"{workspace_dir}/milestones.json"
        if not await path_exists_async(milestone_path):
            await self._create_milestone(project_plan, config)
        milestones = await read_json(milestone_path)
        print(type(milestones))
        print(milestones)
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
                    project_plan=project_plan,
                    milestones=milestones,
                    current_env_info=await get_env_info(config),
                    chat_history=chat_history,
                )

                response = await self.llm_with_tools.ainvoke(messages)
                print(response)
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
                        await write_json(milestone_path, milestones)
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


    async def _create_milestone(self, project_plan, config):
        prompt = ChatPromptTemplate.from_messages([
            ("system", MASTER_CREATE_MILESTONE),
            ("human", """
                # Input Context
                项目规划：{project_plan}
                """),
        ])
        chain = prompt | self.llm.with_structured_output(MilestoneList)
        try:
            # 变化 1: 你的文件工具如果支持异步，也需要 await
            # requirement_document = await self.file_tools.read_file("PRD.md")
            # if not requirement_document:
            #     print("can't read PRD.md")

            # 变化 2: LangChain 的执行方法必须从 invoke 改为 ainvoke
            milestones = await chain.ainvoke({"project_plan": project_plan})

            workspace_dir = config.get("configurable", {}).get("workspace_dir", "./workspace")
            # print(milestones)
            # 2. 显式拼接后传给 util
            milestone_path = f"{workspace_dir}/milestones.json"
            # 变化 3: 文件写入也要 await

            json_string = milestones.model_dump_json(indent=2)
            await makedirs_async(f"{workspace_dir}/{milestones.project_name}")
            # 直接保存字符串
            await save_file_async(milestone_path, json_string)
            # state["milestone_index"] = 0

            # 同理，如果后续有 structured_output 的逻辑：
            # chain2 = self._get_prompt2() | self.llm.with_structured_output(TaskList)
            # result2 = await chain2.ainvoke({"project_plan": project_plan})
            # state["task_list"] = result2.task_list
            # state["current_task_index"] = 0

        except Exception as e:
            print(f"❌ 生成项目里程碑时出现错误: {e}")

