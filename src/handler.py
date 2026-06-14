"""
handler.py - Message handler and command routing.
"""
from __future__ import annotations

import inspect
import re
from typing import Union

from src.game import game
from src.game.commands import get_handler

Reply = Union[str, dict]


def parse_command(content: str) -> tuple[str, str]:
    content = content.strip()
    content = re.sub(r'<@!\d+>', '', content).strip()
    content = re.sub(r'@\S+', '', content).strip()

    match = re.match(r'^[/／]([\u4e00-\u9fa5a-zA-Z]+)\s*(.*)', content)
    if match:
        return match.group(1), match.group(2).strip()
    return "", ""


def extract_mention(content: str) -> str | None:
    m = re.search(r'<@!(\d+)>', content)
    if m:
        return m.group(1)
    m = re.search(r'<@(\d+)>', content)
    if m:
        return m.group(1)
    m = re.search(r'@(\d+)', content)
    if m:
        return m.group(1)
    return None


async def handle_message(user_id: str, user_name: str, content: str,
                         group_id: str = "") -> Reply:
    raw_cmd, arg = parse_command(content)

    if not raw_cmd:
        return ""

    cmd = raw_cmd.lower()

    handler = get_handler(cmd)
    if handler is None:
        return f"❓ 未知命令「{raw_cmd}」，发送「/帮助」查看所有可用命令。"

    try:
        result = handler(game, user_id, user_name, arg, group_id)
        if inspect.iscoroutine(result):
            result = await result
        if isinstance(result, str) and result:
            result = "\n" + result
        return result
    except Exception as e:
        return f"\n❌ 命令执行出错：{e}"
