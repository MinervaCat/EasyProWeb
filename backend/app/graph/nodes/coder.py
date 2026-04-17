"""
Coder Agent - 负责编写具体代码
"""
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, ToolMessage
from src.tools.file_tools import FileTools
from langchain_openai import ChatOpenAI
from src.utils.read_json import read_json
from src.utils.utils import get_file_tree, write_json, get_env_info
from src.prompt import DECOMPOSER_SYSTEM_PROMPT, CODER_SYSTEM_PROMPT3, CODER_SYSTEM_PROMPT
from src.state import AgentState, TaskPlan
from langchain_core.tools import tool
import json
from app.tools import get_coder_tool
from langchain_core.messages import message_to_dict
import os
import uuid
import subprocess
from datetime import datetime


class CoderAgent:
    """
    Coder 职责：
    1. 根据任务和文件规范编写代码
    2. 调用文件读写工具实现功能
    3. 确保代码质量和正确性
    """

    def __init__(self, model: str = "gpt-4o-mini"):
        self.llm = ChatOpenAI(
            model="MiniMax-M2.5",  # 这里填写通义千问的模型名
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",  # 关键：指定阿里云兼容端点
            temperature=0.2,
        )
        tools = get_coder_tool()
        self.llm_with_tools = self.llm.bind_tools(tools)
        self.tool_map = {t.name: t for t in tools}
        self.max_steps = 25

    async def run(self, state: AgentState) -> AgentState:

        task = state.get("sub_task")
        print(f"💻 Coder: 正在编写代码... (任务： {task.instruction})")
        prompt = ChatPromptTemplate.from_messages([
            ("system", CODER_SYSTEM_PROMPT3),
            ("human", """
                ### NEW TASK ASSIGNED ###
                I have a coding task for you. Please strictly adhere to the following contract:

                **Instruction**: {instruction}

                **Target Files (Write Access)**: {target_files}

                **Context Files (Read Only)**: {context_files}

                **Testing Contract**:
                - **Test File**: {test_file_name}
                - **Test Command**: {test_command}

                **Success Criteria**: {success_criteria}

                **Current Working Directory**: {working_directory}

                Please begin your ReAct loop now.
                    """),
            MessagesPlaceholder(variable_name="agent_scratchpad"),  # ReAct 思考路径
        ])
        current_step = 0
        agent_scratchpad = []

        # 1. 定义一个唯一的 ID
        initial_call_id = f"call_{uuid.uuid4().hex}"

        # 2. 模拟第一步：Agent 的“思考”和“调用”
        initial_thought_and_call = AIMessage(
            content="Thought: I need to check the current directory structure to ensure I am using the correct paths for implementation and testing.",
            tool_calls=[{
                "name": "execute_command",
                "args": {"command": "dir"},  # Windows 环境建议用 dir
                "id": initial_call_id
            }]
        )

        # 3. 模拟工具返回的结果（Observation）
        initial_tool_result = ToolMessage(
            content=self.tool_map['execute_command'].ainvoke("dir"),
            tool_call_id=initial_call_id,
            tool_call_name="execute_command",
        )
        # 4. 在任务开始前初始化 scratchpad
        agent_scratchpad = [initial_thought_and_call, initial_tool_result]
        project_plan = await read_json("project_plan.json")
        current_file_tree = await get_file_tree(project_plan.get("project_name"))

        while current_step < self.max_steps:
            current_step += 1

            # try:
            # 生成代码
            messages = prompt.format_messages(
                instruction=task.instruction,
                target_files=task.target_files,
                context_files=task.context_files,
                test_file_name=task.test_file_name,
                test_command=task.test_command,
                success_criteria=task.success_criteria,
                working_directory=await get_env_info(),
                agent_scratchpad=manage_scratchpad(agent_scratchpad),
            )
            response = await self.llm_with_tools.ainvoke(messages)
            # 1. 准备要保存的数据
            log_data = {
                "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
                "input_messages": message_to_dict(messages[-1]),
                "output_response": message_to_dict(response)
            }
            # 创建 logs 文件夹
            os.makedirs("logs", exist_ok=True)
            filename = f"logs/chat.json"

            with open(filename, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_data, ensure_ascii=False) + "\n")
            if response.tool_calls:
                agent_scratchpad.append(response)
                for tc in response.tool_calls:
                    print(tc)
                    if tc['name'] not in self.tool_map:
                        print(f"❌ 错误：找不到名为 '{tc['name']}' 的工具。")
                        break
                    elif tc['name'] == 'finish_task':
                        summary = tc['args'].get("summary")
                        print(summary)
                        state['task_summary'] = summary
                        return state
                    else:
                        tool_result = await self.tool_map[tc['name']].ainvoke(tc["args"])
                    agent_scratchpad.append(ToolMessage(
                        content=tool_result,
                        tool_call_id=tc['id'],
                        tool_call_name=tc['name'],
                    ))
            else:
                print("No tool calls")
                break

            # except Exception as e:
            #     print(f"❌ Coder 错误: {e}")
            # state.error_message = f"Coding failed: {str(e)}"

        return state


    def _clean_code(self, code: str) -> str:
        """清理代码内容"""
        # 移除 markdown 代码块标记
        lines = code.split('\n')
        cleaned = []
        in_code_block = False

        for line in lines:
            if line.strip().startswith('```'):
                in_code_block = not in_code_block
                continue
            cleaned.append(line)

        return '\n'.join(cleaned).strip()




def manage_scratchpad(messages, max_content_len=300):
    if not messages:
        return []

    processed_messages = []
    # 建立 ID 到 工具名的映射表
    id_to_tool = {}

    # 第一遍扫描：记录所有 tool_call_id 对应的工具名称
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                id_to_tool[tc['id']] = tc['name']

    # 第二遍扫描：进行定向压缩
    for i, msg in enumerate(messages):
        new_msg = msg

        # 1. 处理 AIMessage (write_file 的参数压缩)
        if isinstance(msg, AIMessage) and msg.tool_calls:
            # 注意：AIMessage 是不可变对象，修改参数需要重建
            new_tool_calls = []
            for tc in msg.tool_calls:
                new_tc = tc.copy()
                if tc['name'] == 'write_file':
                    args = new_tc['args']
                    if 'content' in args and len(args['content']) > max_content_len:
                        args['content'] = f"{args['content'][:100]}... [Content omitted]"
                new_tool_calls.append(new_tc)
            # 重建消息对象，保持原有 content 不变
            new_msg = AIMessage(content=msg.content, tool_calls=new_tool_calls)

        # 2. 处理 ToolMessage (定向结果压缩)
        elif isinstance(msg, ToolMessage):
            tool_name = id_to_tool.get(msg.tool_call_id, "")

            # --- 核心逻辑：只压缩 read_file 的结果 ---
            # run_test_command (dir/ls) 的结果我们选择保留，除非它真的长得离谱（比如 > 2000字）
            if tool_name == 'read_file' and len(msg.content) > max_content_len and i < len(messages) - 3:
                new_msg = ToolMessage(
                    content=f"✅ [File content omitted. Total {len(msg.content)} chars. Read again if needed.]",
                    tool_call_id=msg.tool_call_id
                )

            # --- 可选：对 run_test_command 的报错进行有选择的压缩 ---
            elif tool_name == 'run_test_command' and i < len(messages) - 2 and len(msg.content) > 1000:
                # 如果是测试成功且很长的日志，可以压缩；
                # 但如果是 'dir' 的结果，建议给一个极大的阈值（比如 2000），防止地图丢失
                # if "Directory of" not in msg.content and len(msg.content) > 3000:
                #     if i < len(messages) - 1:
                new_msg = ToolMessage(
                    content=f"✅ [Long test log omitted. Total {len(msg.content)} chars.]",
                    tool_call_id=msg.tool_call_id
                )

        processed_messages.append(new_msg)

    return processed_messages
