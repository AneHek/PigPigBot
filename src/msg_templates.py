"""
msg_templates.py - QQ 机器人消息模板封装

提供两种回复模板：
1. Markdown 模板 - 基于 QQ 官方模板 ID 的消息
2. 按钮列表模板 - 可配置行列的键盘按钮消息
"""

from typing import Optional

# ──────────────────────────────────────────────
# Markdown 模板
# ──────────────────────────────────────────────

# QQ 官方 Markdown 模板 ID
MARKDOWN_TEMPLATE_ID = "102708504_1742576617"


def build_markdown_msg(
    title: str,
    image: str = "",
    tip: str = "",
    template_id: Optional[str] = None,
) -> dict:
    """构建 Markdown 模板消息

    Args:
        title: 标题文本
        image: 图片链接（可为空字符串）
        tip: 图片下方文本文本（可为空字符串）
        template_id: 模板 ID，默认使用内置模板

    Returns:
        可直接用于消息 API 的结构化消息字典
    """
    tid = template_id or MARKDOWN_TEMPLATE_ID
    return {
        "msg_type": 2,  # Markdown 消息类型
        "markdown": {
            "custom_template_id": tid,
            "params": [
                {"key": "title", "values": [title]},
                {"key": "image", "values": [image]},
                {"key": "tip", "values": [tip]},
            ],
        },
    }


# ──────────────────────────────────────────────
# 按钮列表模板
# ──────────────────────────────────────────────


def build_button_list(
    rows: list[list[dict]],
    keyboard_id: Optional[str] = None,
) -> dict:
    """构建按钮列表消息（内嵌键盘）

    每一行是一个按钮列表，用户可以自由配置行数、列数、
    按钮文本和对应指令。

    Args:
        rows: 二维按钮列表，格式：
              [
                  [
                      {"text": "喂食", "command": "/喂食"},
                      {"text": "状态", "command": "/状态"},
                  ],
                  [
                      {"text": "帮助", "command": "/帮助"},
                  ],
              ]
        keyboard_id: 可选，键盘标识符

    Returns:
        可直接用于消息 API 的结构化消息字典（msg_type=2, 含 keyboard）

    按钮默认行为：
        - permission.type = 2（所有人可调用）
        - action.type  = 2（at 机器人并发送指令）
        - action.enter = True（点击后自动发送）
        - action.reply = True（引用当前消息）
    """
    button_rows = []
    for row_buttons in rows:
        buttons = []
        for btn_data in row_buttons:
            text = btn_data.get("text", "")
            command = btn_data.get("command", "")
            btn_id = btn_data.get("id", command.lstrip("/"))

            buttons.append({
                "id": btn_id,
                "render_data": {
                    "label": text,
                    "visited_label": text,
                },
                "action": {
                    "type": 2,  # at 机器人并发送指令
                    "permission": {
                        "type": 2,  # 所有人可调用
                    },
                    "data": command,
                    "enter": True,
                },
            })
        button_rows.append({"buttons": buttons})

    keyboard_content = {"rows": button_rows}
    keyboard_payload = {"content": keyboard_content}
    if keyboard_id:
        keyboard_payload["id"] = keyboard_id

    return {
        "keyboard": keyboard_payload,
    }


def build_button_list_msg(
    content: str,
    rows: list[list[dict]],
    keyboard_id: Optional[str] = None,
) -> dict:
    """构建带文本内容的按钮列表消息

    Args:
        content: 消息正文文本
        rows: 二维按钮列表，同 build_button_list
        keyboard_id: 可选，键盘标识符

    Returns:
        完整消息字典，可直接用于消息 API
    """
    msg = {
        "content": content,
        "msg_type": 0,  # 文本消息 + 内嵌键盘
    }
    msg.update(build_button_list(rows, keyboard_id))
    return msg


def build_simple_button_row(
    buttons: list[tuple[str, str]],
) -> list[dict]:
    """快捷构建一行按钮

    Args:
        buttons: [(文本, 指令), ...]，例如 [("喂食", "/喂食"), ("状态", "/状态")]

    Returns:
        单行按钮字典列表
    """
    return [{"text": t, "command": c} for t, c in buttons]


def build_auto_grid(
    buttons: list[tuple[str, str]],
    cols: int = 2,
) -> list[list[dict]]:
    """自动将按钮列表按指定列数排列成网格

    Args:
        buttons: [(文本, 指令), ...]
        cols: 每行按钮数量

    Returns:
        可用于 build_button_list / build_button_list_msg 的 rows 数据
    """
    rows = []
    for i in range(0, len(buttons), cols):
        row = [
            {"text": t, "command": c}
            for t, c in buttons[i : i + cols]
        ]
        rows.append(row)
    return rows
