"""
handler.py - Message handler and command routing.
"""
from __future__ import annotations

import re
from typing import Union

from src.pet_game import game

Reply = Union[str, dict]


def parse_command(content: str) -> tuple[str, str]:
    """Parse user message, extract command and argument."""
    content = content.strip()
    content = re.sub(r'<@!\d+>', '', content).strip()
    content = re.sub(r'@\S+', '', content).strip()

    match = re.match(r'^[/／]([\u4e00-\u9fa5a-zA-Z]+)\s*(.*)', content)
    if match:
        return match.group(1), match.group(2).strip()
    return "", ""


def extract_mention(content: str) -> str | None:
    """Extract mentioned user ID from message content.
    Supports: <@!12345>, <@12345>, @12345
    """
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


def handle_message(user_id: str, user_name: str, content: str) -> Reply:
    """Route user message to the appropriate handler."""
    # Check for @mention PvP (battle triggered by mentioning someone with pet)
    mentioned_id = extract_mention(content)
    raw_cmd, arg = parse_command(content)

    # If no slash command but has @mention, treat as battle
    if not raw_cmd and mentioned_id and mentioned_id != user_id:
        return game.battle_pvp(user_id, mentioned_id)

    if not raw_cmd:
        return ""

    cmd = raw_cmd.lower()

    # ── Command routing ──
    handlers = {
        # Chinese
        "领养": lambda: game.adopt(user_id, user_name, arg),
        "状态": lambda: game.status(user_id),
        "属性": lambda: game.stats_detail(user_id),
        "遗弃": lambda: game.abandon(user_id),
        "改名": lambda: game.rename(user_id, arg),
        "排行": lambda: game.top(),
        "帮助": lambda: game.help(),
        "菜单": lambda: game.help(),
        "进化": lambda: game.evolve(user_id),
        "训练": lambda: game.start_training(user_id),
        "休息": lambda: game.end_training(user_id),
        "战斗": lambda: game.battle_pvp(user_id, mentioned_id) if mentioned_id else "❌ 请 @一个人 来发起战斗！\n例如：/战斗 @某人",
        # English
        "adopt": lambda: game.adopt(user_id, user_name, arg),
        "status": lambda: game.status(user_id),
        "stats": lambda: game.stats_detail(user_id),
        "abandon": lambda: game.abandon(user_id),
        "rename": lambda: game.rename(user_id, arg),
        "top": lambda: game.top(),
        "help": lambda: game.help(),
        "evolve": lambda: game.evolve(user_id),
        "train": lambda: game.start_training(user_id),
        "rest": lambda: game.end_training(user_id),
        "battle": lambda: game.battle_pvp(user_id, mentioned_id) if mentioned_id else "❌ 请 @一个人 来发起战斗！\n例如：/战斗 @某人",
    }

    if cmd in handlers:
        try:
            return handlers[cmd]()
        except Exception as e:
            return f"❌ 命令执行出错：{e}"

    return f"❓ 未知命令「{raw_cmd}」，发送「/帮助」查看所有可用命令。"
