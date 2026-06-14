import time

from src.game.commands import command

PURCHASABLE_TITLES = {
    "群聊之星": {"cost": 500},
    "社交达人": {"cost": 2000},
    "猪群领袖": {"cost": 10000},
}


class TitleMixin:

    @command("称号", "title")
    def title_cmd(self, user_id: str, user_name: str = "", arg: str = "", group_id: str = "") -> str:
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"

        parts = arg.split()

        if not parts:
            return self._title_list(user_id)

        sub = parts[0]
        if sub == "装备" and len(parts) >= 2:
            title_name = " ".join(parts[1:])
            return self._title_equip(user_id, title_name)
        elif sub == "卸下":
            return self._title_unequip(user_id)
        elif sub == "购买" and len(parts) >= 2:
            title_name = " ".join(parts[1:])
            return self._title_buy(user_id, title_name)

        return self._title_list(user_id)

    def _title_list(self, user_id: str) -> str:
        titles = self.dm.get_titles(user_id)
        equipped = self.dm.get_equipped_title(user_id)

        if not titles:
            lines = ["🏅 已拥有称号", "", "暂无称号"]
            lines.append("")
            lines.append("📌 可购买称号：")
            for name, info in PURCHASABLE_TITLES.items():
                lines.append(f"  {name} — {info['cost']} 群贡献点")
            lines.append(f"\n📌 输入「/称号 购买 群聊之星」购买称号")
            return "\n".join(lines)

        now = time.time()
        lines = ["🏅 已拥有称号", ""]
        for title in sorted(titles):
            expire_ts = self.dm.get_title_expire(user_id, title)
            if expire_ts > 0 and now > expire_ts:
                continue
            mark = " ← 已装备" if title == equipped else ""
            if expire_ts > 0:
                remaining = int((expire_ts - now) / 86400)
                lines.append(f"  ⏳ {title}（剩 {remaining} 天）{mark}")
            else:
                lines.append(f"  ⭐ {title}（永久）{mark}")

        lines.append("")
        lines.append("📌 输入「/称号 装备 <称号名>」切换装备称号")
        lines.append("📌 输入「/称号 卸下」卸下当前称号")

        return "\n".join(lines)

    def _title_equip(self, user_id: str, title_name: str) -> str:
        if not self.dm.has_title(user_id, title_name):
            return "❌ 称号不存在，发送 /称号 查看已拥有称号"

        expire_ts = self.dm.get_title_expire(user_id, title_name)
        if expire_ts > 0 and time.time() > expire_ts:
            self.dm.remove_title(user_id, title_name)
            return "❌ 该称号已过期"

        self.dm.equip_title(user_id, title_name)
        return f"✅ 已装备称号「{title_name}」"

    def _title_unequip(self, user_id: str) -> str:
        equipped = self.dm.get_equipped_title(user_id)
        if not equipped:
            return "❌ 当前没有装备称号"

        self.dm.unequip_title(user_id)
        return f"✅ 已卸下称号「{equipped}」"

    def _title_buy(self, user_id: str, title_name: str) -> str:
        if title_name not in PURCHASABLE_TITLES:
            return "❌ 称号不存在，可购买称号：群聊之星 / 社交达人 / 猪群领袖"

        if self.dm.has_title(user_id, title_name):
            return f"❌ 你已经拥有称号「{title_name}」了"

        cost = PURCHASABLE_TITLES[title_name]["cost"]
        if not self.dm.use_contribution(user_id, cost):
            current = self.dm.get_contribution(user_id)
            return f"❌ 群贡献点不足（当前 {current}/{cost}），互动和 Boss 攻击可获得贡献点"

        self.dm.add_title(user_id, title_name)
        return f"✅ 购买称号「{title_name}」成功！花费 {cost} 群贡献点"
