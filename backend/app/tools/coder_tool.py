import os
import subprocess

import locale
from anyio import Path
from langchain_core.tools import tool  # 假设你使用的是 langchain 的 tool 装饰器


def get_coder_tool():
    return [read_file, write_file, edit_file, execute_command]

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


@tool
def execute_command(command: str):
    """
    Use this tool to execute tests or run code.
    Input should be a shell command like 'node tests/logic.test.js'.
    The tool returns the full console output.
    If the output shows '❌ FAILED', you MUST analyze the error and fix your code.
    """
    # 调用上面定义的函数
    return safe_execute_command(command)

def safe_execute_command(command: str, timeout: int = 15):
    # 1. 危险指令拦截
    forbidden_words = ["rm ", "format", "sudo", "chmod", "mv /"]
    if any(word in command.lower() for word in forbidden_words):
        return "❌ SECURITY ERROR: This command is not allowed for safety reasons."

    try:
        # 2. 执行命令（注意：这里不使用 text=True 和 encoding）
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,  # 捕获原始字节流
            timeout=timeout,
            cwd=os.getcwd()
        )

        # 3. 智能解码逻辑
        def smart_decode(data: bytes) -> str:
            if not data:
                return ""
            # 尝试顺序：UTF-8 -> 系统默认编码(Windows通常是GBK) -> 容错替换
            for enc in ['utf-8', locale.getpreferredencoding(), 'gbk']:
                try:
                    return data.decode(enc)
                except UnicodeDecodeError:
                    continue
            return data.decode('utf-8', errors='replace')

        stdout_str = smart_decode(result.stdout)
        stderr_str = smart_decode(result.stderr)

        # 4. 构造反馈
        if result.returncode == 0:
            # 某些命令（如 dir）成功但输出在 stdout
            return f"✅ SUCCESS:\n{stdout_str}"
        else:
            # 失败时同时返回标准输出和错误输出，方便 Agent 诊断
            return (f"❌ FAILED (Exit Code {result.returncode}):\n"
                    f"STDOUT: {stdout_str}\n"
                    f"STDERR: {stderr_str}")

    except subprocess.TimeoutExpired:
        return f"❌ ERROR: Command timed out after {timeout} seconds. Potential infinite loop."
    except Exception as e:
        return f"❌ SYSTEM ERROR while executing: {str(e)}"

@tool
def finish_task(summary: str):
    """
    完成任务后调用
    Args:
        summary: 简洁的任务完成说明
    """
    pass