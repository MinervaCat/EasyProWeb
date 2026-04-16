

# app/utils/file_utils.py
import os
import json
from pathlib import Path

import aiofiles
from typing import Any, Dict, Optional

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
