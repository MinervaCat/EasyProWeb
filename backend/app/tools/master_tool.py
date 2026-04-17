from langchain_core.tools import tool
from app.graph.state.state import SubTask
from typing import List

def get_master_tool():
    return [delegate_task, finish_project, finish_milestone]

@tool(args_schema=SubTask)
def delegate_task(instruction: str, target_files: List[str], context_files: List[str], test_file_name: str, test_command: str, success_criteria: str):
    """
    将具体的编程任务委派给具备文件操作和执行能力的 Code Agent。
    """
    pass

@tool
def finish_project(summary: str):
    """
    完成项目后调用
    Args:
        summary: 项目最终交付说明
    """
    pass

@tool
def finish_milestone(milestone_id: str):
    """
    完成一个milestone时调用
    Args:
        milestone_id: milestone的id
    """
    pass