import operator
from typing import List, Optional, Annotated, TypedDict

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field


class Milestone(BaseModel):
    id: str = Field(..., description="唯一id，如 'M1', 'M2'")
    title: str = Field(..., description="里程碑简短名称")
    description: str = Field(..., description="详细描述该阶段需要完成的功能和逻辑")
    required_files: List[str] = Field(..., description="需要完成的文件")
    # 核心修改：改为 List[str]
    dependencies: List[str] = Field(
        default=[],
        description="依赖的里程碑ID列表，例如 ['M1']"
    )
    # 确保这个字段是必填的
    verification_criteria: str = Field(..., description="具体的验收标准")


class MilestoneList(BaseModel):
    project_name: str = Field(description="项目名称，英文单词，用于创建项目文件夹")
    milestones: List[Milestone] = Field(description="按顺序排列的里程碑任务列表")


class ClarificationQuestion(BaseModel):
    question: str = Field(..., description="向用户提出的具体澄清问题")
    reason: str = Field(..., description="为什么要问这个问题（例如：影响技术选型/数据库设计）")
    category: str = Field(..., description="问题类别，如：并发量、支付流程、技术栈、业务规则")


class AnalysisResult(BaseModel):
    # 1. 设置为可选，并给默认值 None。如果还没聊完，大模型不传也不会报错了。
    summary: Optional[str] = Field(default=None, description="需求总结，如果还在追问阶段请留空或不传。")

    # 2. 直接接受字符串列表，大模型最喜欢也最擅长这种扁平结构。
    questions: List[str] = Field(default_factory=list, description="需要向用户追问的问题列表。")

    is_complete: bool = Field(description="标识是否已经收集到足够的信息可以开始写文档了。")


class SubTask(BaseModel):
    instruction: str = Field(
        description="详细的任务指令。应包含：1.要实现的逻辑 2.架构要求 3.API定义。请使用专业技术术语。"
    )

    target_files: List[str] = Field(
        description="允许修改的目标文件列表（写权限）。"
    )

    context_files: List[str] = Field(
        default_factory=list,
        description="仅供参考的上下文文件列表，如接口定义、常量或已完成的模块（只读权限）。"
    )

    test_file_name: str = Field(
        description="指定的测试脚本路径，必须在该文件中编写测试逻辑。例如：'tests/m1_logic.test.js'"
    )

    test_command: str = Field(
        description="运行测试的具体 Shell 命令。例如：'node tests/m1_logic.test.js'"
    )

    success_criteria: str = Field(
        description="明确的任务完成判定标准。例如：'所有单元测试通过'。"
    )

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]
    # 已确认的需求点 (Key-Value 对)
    confirmed_requirements: dict
    # 待澄清的问题列表
    pending_questions: List[str]
    #
    status: str
    """新版task"""
    # tasks: List[Task]  # 所有的任务列表保存在这里
    current_task_id: int

    sub_task: SubTask
    task_summary: str
    tool_content: str
    tool_call_id: str

    project_status: str
    # history: Annotated[List[AIMessage], merge_lists]
    # """工作区状态 - 包含项目文件和进度"""
    # milestone_index: int
    # # milestone_list: Annotated[List[SubTask], merge_lists]
    # # Planner 输出
    # task_list: List[str]
    # current_task_index: int
    # task_nums: int
    # file_structure: Annotated[list[FileSpec], update_file_structure]
    #
    # # Coder 输出
    # implemented_files: Annotated[list[FileSpec], merge_lists]
    # current_file_index: int
    #
    # # Tester 输出
    # test_results: Annotated[list[TestResult], merge_lists]
    #
    # # Reviewer 输出
    # review_result: Optional[CodeReviewResult]
    # iterations: int
    #
    # # 流程控制
    # next_step: Optional[str]
    # error_message: Optional[str]
    # final_output: Optional[str]