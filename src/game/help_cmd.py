from src.game.commands import command
from src.config import config
from src.msg_templates import build_markdown_with_buttons


class HelpMixin:

    @command("帮助", "help", "菜单")
    def help(self, user_id: str = "", user_name: str = "", arg: str = "", group_id: str = "") -> dict:
        callback_domain = config["webhook"].get("callback_domain", "")
        image_url = f"{callback_domain}/static/images/help.png"

        rows = [
            [
                {"text": "🐷 领养", "command": "/领养"},
                {"text": "📊 属性", "command": "/属性"},
                {"text": "🏋 训练", "command": "/训练"},
            ],
            [
                {"text": "🏰 副本", "command": "/副本"},
                {"text": "🐲 Boss", "command": "/boss"},
                {"text": "📅 签到", "command": "/签到"},
            ],
            [
                {"text": "🎒 背包", "command": "/背包"},
                {"text": "🏆 排行", "command": "/排行"},
                {"text": "📖 被动", "command": "/被动"},
            ],
            [
                {"text": "🏅 称号", "command": "/称号"},
                {"text": "🎉 活动", "command": "/活动"},
            ],
        ]

        tip = "💡 训练是获取经验的主要方式丨💡 副本和Boss提供进化材料丨💡 互动可建立亲密度获得加成"

        return build_markdown_with_buttons(
            title="🐷 帮助菜单",
            image=image_url,
            tip=tip,
            rows=rows,
        )
