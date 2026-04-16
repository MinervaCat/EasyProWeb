# app/tools/file_ops.py
import os
from langchain_core.tools import tool
from langchain_core.runnables.config import RunnableConfig
from app.utils.file import read_file_content

@tool
async def read_file(file_path: str, config: RunnableConfig) -> str:
    """
    读取工作区中指定文件的内容。
    参数 file_path: 相对于工作区的相对路径，例如 "PRD.md"
    """
    # 1. 从 config 中动态提取当前用户的专属工作路径
    # 如果没传，给一个默认的防崩溃路径
    workspace_dir = config.get("configurable", {}).get(
        "workspace_dir",
        "./workspace/default"
    )

    # 2. 安全校验 (限制在当前用户的专属目录下)
    safe_path = os.path.abspath(os.path.join(workspace_dir, file_path))
    if not safe_path.startswith(os.path.abspath(workspace_dir)):
        return "❌ 权限拒绝：只能读取您自己工作区目录下的文件。"

    # 3. 调用底层执行
    try:
        return await read_file_content(safe_path)
    except FileNotFoundError:
        return f"❌ 错误：未找到文件 {file_path}。"
    except Exception as e:
        return f"❌ 读取发生未知错误：{str(e)}"