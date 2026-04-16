from anyio import Path
from langchain_core.tools import tool  # 假设你使用的是 langchain 的 tool 装饰器


@tool
async def read_file(path: str) -> str:
    """
    异步读取文件内容。

    Args:
        path: 文件路径（相对于当前工作目录）
    Returns:
        文件内容，如果文件不存在返回错误信息
    """
    try:
        file_path = Path(path)
        if not await file_path.exists():
            return f"Error: File '{path}' does not exist"
        if not await file_path.is_file():
            return f"Error: '{path}' is not a file"

        # anyio 的 Path 对象提供异步读取
        return await file_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file: {str(e)}"


@tool
async def write_file(path: str, content: str) -> str:
    """
    异步写入文件内容。如果目录不存在会自动创建。
    Args:
        path: 文件路径
        content: 文件内容
    Returns:
        操作结果信息
    """
    try:
        file_path = Path(path)
        # 创建父目录，mkdir 是异步的
        await file_path.parent.mkdir(parents=True, exist_ok=True)
        # 写入内容
        await file_path.write_text(content, encoding="utf-8")
        return f"Successfully wrote to '{path}'"
    except Exception as e:
        return f"Error writing file: {str(e)}"


@tool
async def edit_file(path: str, old_string: str, new_string: str) -> str:
    """
    异步编辑文件内容，将 old_string 替换为 new_string。

    Args:
        path: 文件路径
        old_string: 要替换的旧内容
        new_string: 新内容

    Returns:
        操作结果信息
    """
    try:
        file_path = Path(path)
        if not await file_path.exists():
            return f"Error: File '{path}' does not exist"
        if not await file_path.is_file():
            return f"Error: '{path}' is not a file"

        content = await file_path.read_text(encoding="utf-8")
        count = content.count(old_string)

        if count == 0:
            return f"Error: The specified old_string was not found in '{path}'"

        if count > 1:
            return f"Error: Found {count} occurrences of the old_string in '{path}'. Please provide a more unique context to avoid ambiguous replacement."

        new_content = content.replace(old_string, new_string, 1)
        await file_path.write_text(new_content, encoding="utf-8")

        return f"Successfully edited '{path}'"
    except Exception as e:
        return f"Error editing file: {str(e)}"