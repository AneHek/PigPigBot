"""
handler.py - 消息处理与命令路由模块

处理函数可返回：
- str:  纯文本回复
- dict: 模板消息（markdown / 按钮列表等），由 bot 层序列化发送
"""
from __future__ import annotations

import re
from typing import Union

from src.pet_game import game

# 回复类型：纯文本字符串 或 结构化消息字典
Reply = Union[str, dict]


def parse_command(content: str) -> tuple[str, str]:
    """
    解析用户消息，提取命令和参数
    返回 (command, arg)
    """
    content = content.strip()
    # 去除 @ 提及前缀
    content = re.sub(r'<@!\d+>', '', content).strip()
    content = re.sub(r'@\S+', '', content).strip()

    # 匹配 /命令 参数 格式
    match = re.match(r'^[/／]([\u4e00-\u9fa5a-zA-Z]+)\s*(.*)', content)
    if match:
        cmd = match.group(1)
        arg = match.group(2).strip()
        return cmd, arg
    return "", ""


def handle_message(user_id: str, user_name: str, content: str) -> Reply:
    """
    处理用户消息，路由到对应命令处理器
    返回纯文本或结构化消息（模板消息 / 按钮列表等）
    """
    cmd, arg = parse_command(content)

    if not cmd:
        return ""

    # 命令路由表
    handlers: dict[str, callable] = {
        "领养": lambda: game.adopt(user_id, user_name, arg),
        "状态": lambda: game.status(user_id),
        "喂食": lambda: game.feed(user_id),
        "玩耍": lambda: game.play(user_id),
        "休息": lambda: game.rest(user_id),
        "治疗": lambda: game.heal(user_id),
        "打工": lambda: game.work(user_id),
        "训练": lambda: game.train(user_id),
        "遗弃": lambda: game.abandon(user_id),
        "改名": lambda: game.rename(user_id, arg),
        "排行": lambda: game.top(),
        "帮助": lambda: game.help(),
        "菜单": lambda: game.help(),
        "help": lambda: game.help(),
        "adopt": lambda: game.adopt(user_id, user_name, arg),
        "status": lambda: game.status(user_id),
        "feed": lambda: game.feed(user_id),
        "play": lambda: game.play(user_id),
        "rest": lambda: game.rest(user_id),
        "heal": lambda: game.heal(user_id),
        "work": lambda: game.work(user_id),
        "train": lambda: game.train(user_id),
        "top": lambda: game.top(),
        "rename": lambda: game.rename(user_id, arg),
        "abandon": lambda: game.abandon(user_id),
    }

    if cmd in handlers:
        return handlers[cmd]()

    # 未知命令提示
    return (
        f"❓ 未知命令「{cmd}」，发送「/帮助」查看所有可用命令。"
    )
