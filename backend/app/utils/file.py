

# app/utils/file_utils.py
import os
import json
from pathlib import Path

import aiofiles
from typing import Any, Dict, Optional

import asyncio


async def read_json(file_path: str) -> Dict[str, Any]:
    """
    异步读取 JSON 文件并返回字典。
    如果文件不存在或格式错误，会抛出相应的异常。
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"未找到 JSON 文件: {file_path}")

    async with aiofiles.open(file_path, mode='r', encoding='utf-8') as f:
        content = await f.read()
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 格式错误: {file_path} - {str(e)}")

async def write_json(file_path: str, data: Any, indent: int = 4) -> None:
    """
    将数据异步写入为 JSON 文件。
    自动处理目录创建并确保中文不被转义。
    """
    # 确保目标文件夹存在
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # 在写入前先序列化，避免在文件打开期间占用过多时间
    # ensure_ascii=False 确保中文在文件中以汉字形式保存，方便阅读
    content = json.dumps(data, indent=indent, ensure_ascii=False)

    async with aiofiles.open(file_path, mode='w', encoding='utf-8') as f:
        await f.write(content)

async def read_file_content(file_path: str) -> str:
    """系统级底层函数：读取文件内容"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    async with aiofiles.open(file_path, mode='r', encoding='utf-8') as f:
        return await f.read()

async def write_file_content(file_path: str, content: Any):
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")


async def get_env_info() -> str:
    # 异步读取 JSON
    project_plan = await read_json("project_plan.json")
    project_name = project_plan.get("project_name", ".")

    # 异步调用 get_file_tree
    file_tree = await get_file_tree(project_name)

    return f"cwd:{project_name}\ncurrent_file_tree:{file_tree}"


async def get_file_tree(root_dir: str, max_depth: int = 5) -> str:
    """
    异步扫描目录并返回类似 tree 命令的字符串表示
    """
    tree_lines = [root_dir]
    ignore_dirs = {'.git', '__pycache__', 'node_modules', '.venv', 'dist', 'build'}
    ignore_exts = {'.pyc', '.pyo', '.so', '.dll'}

    async def scan(current_path, prefix="", depth=0):
        if depth > max_depth:
            return

        try:
            # os.listdir 是阻塞 I/O，放入线程池中执行
            entries = await asyncio.to_thread(os.listdir, current_path)
            entries.sort()
        except PermissionError:
            return

        # 过滤隐藏文件
        entries = [e for e in entries if not (e.startswith('.') and e not in ['.gitignore'])]

        for i, entry in enumerate(entries):
            full_path = os.path.join(current_path, entry)
            is_last = (i == len(entries) - 1)
            connector = "└── " if is_last else "├── "

            # os.path.isdir 也是阻塞操作
            is_dir = await asyncio.to_thread(os.path.isdir, full_path)

            if is_dir:
                if entry in ignore_dirs:
                    continue
                tree_lines.append(f"{prefix}{connector}{entry}/")
                await scan(full_path, prefix + ("    " if is_last else "│   "), depth + 1)
            else:
                _, ext = os.path.splitext(entry)
                if ext in ignore_exts:
                    continue
                tree_lines.append(f"{prefix}{connector}{entry}")

    await scan(root_dir)
    return "\n".join(tree_lines) if tree_lines else "(空目录)"
