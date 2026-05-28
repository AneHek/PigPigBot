"""
handler.py - Message handler and command routing.
"""
from __future__ import annotations

import re
from typing import Union

from src.pet_game import game
from src.data_manager import data_manager

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


async def handle_message(user_id: str, user_name: str, content: str,
                         group_id: str = "") -> Reply:
    """异步路由用户消息到对应处理器。"""
    import inspect

    raw_cmd, arg = parse_command(content)

    if not raw_cmd:
        return ""

    cmd = raw_cmd.lower()

    def _resolve_battle_target() -> str | None:
        """从参数解析游戏用户ID并反查QQ用户ID"""
        if not arg or not arg.isdigit():
            return None
        target_game_uid = int(arg)
        return data_manager.get_user_by_game_uid(target_game_uid)

    # ── 命令路由表 ──
    handlers = {
        "领养": lambda: game.adopt(user_id, user_name, arg),
        "属性": lambda: game.stats_detail(user_id),
        "遗弃": lambda: game.abandon(user_id),
        "改名": lambda: game.rename(user_id, arg),
        "排行": lambda: game.top(),
        "帮助": lambda: game.help(),
        "菜单": lambda: game.help(),
        "进化": lambda: game.evolve(user_id),
        "训练": lambda: game.start_training(user_id),
        "休息": lambda: game.end_training(user_id),
        "注册": lambda: game.register(user_id),
        "战斗": lambda: game.battle_pvp(user_id, _resolve_battle_target()) if _resolve_battle_target() else "❌ 请提供对方的游戏用户ID！\n例如：/战斗 123",
        "adopt": lambda: game.adopt(user_id, user_name, arg),
        "stats": lambda: game.stats_detail(user_id),
        "abandon": lambda: game.abandon(user_id),
        "rename": lambda: game.rename(user_id, arg),
        "top": lambda: game.top(),
        "help": lambda: game.help(),
        "evolve": lambda: game.evolve(user_id),
        "train": lambda: game.start_training(user_id),
        "rest": lambda: game.end_training(user_id),
        "register": lambda: game.register(user_id),
        "battle": lambda: game.battle_pvp(user_id, _resolve_battle_target()) if _resolve_battle_target() else "❌ 请提供对方的游戏用户ID！\n例如：/战斗 123",
    }

    if cmd in handlers:
        try:
            result = handlers[cmd]()
            if inspect.iscoroutine(result):
                result = await result
            return result
        except Exception as e:
            return f"❌ 命令执行出错：{e}"

    return f"❓ 未知命令「{raw_cmd}」，发送「/帮助」查看所有可用命令。"
