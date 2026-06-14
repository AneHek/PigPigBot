"""
passive.py — 被动技能命令。

/被动技能          查看已装备的被动技能
/被动技能 背包      查看拥有的技能书
/被动技能 装备 <名> <槽位>  装备技能书到指定槽位
/被动技能 升级 <名>  消耗同名书升级
/被动技能 重置 <槽位>  卸下技能（5钻石/次）
"""
from src.game.commands import command
from src.game.passive_config import (
    PASSIVE_SKILLS, UPGRADE_COSTS, MAX_PASSIVE_LEVEL,
    PASSIVE_SLOTS, RESET_COST,
)

CATEGORY_ICON = {"attack": "⚔️", "defense": "🛡️", "speed": "💨", "special": "✨"}


def _resolve_skill_name(name: str) -> str | None:
    for sid, info in PASSIVE_SKILLS.items():
        if info["name"] == name or sid == name:
            return sid
    return None


class PassiveMixin:

    @command("被动", "passive")
    def passive_cmd(self, user_id: str, user_name: str = "", arg: str = "", group_id: str = "") -> str:
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"

        parts = arg.split()

        if not parts:
            return self._passive_list(user_id, pet)

        sub = parts[0]
        if sub == "背包":
            return self._passive_bag(user_id)
        elif sub == "装备" and len(parts) >= 3:
            return self._passive_equip(user_id, parts[1], parts[2])
        elif sub == "升级" and len(parts) >= 2:
            return self._passive_upgrade(user_id, parts[1])
        elif sub == "重置" and len(parts) >= 2:
            return self._passive_reset(user_id, parts[1])
        else:
            return ("📖 被动指令：\n"
                    "  /被动          查看已装备\n"
                    "  /被动 背包      查看技能书\n"
                    "  /被动 装备 <名> <槽位>\n"
                    "  /被动 升级 <名>\n"
                    "  /被动 重置 <槽位>")

    def _passive_list(self, user_id: str, pet) -> str:
        slots = self.dm.get_passive_slots(user_id)
        lines = [f"📖 被动技能（{pet.name} Lv.{pet.level}）", ""]

        for i in range(1, PASSIVE_SLOTS + 1):
            skill_id = slots.get(str(i))
            if skill_id and skill_id in PASSIVE_SKILLS:
                info = PASSIVE_SKILLS[skill_id]
                level = self.dm.get_passive_level(user_id, skill_id)
                pct = info["pct_per_level"][level - 1] if level > 0 else 0
                icon = CATEGORY_ICON.get(info["category"], "❓")
                lines.append(f"  槽位 {i} {icon} {info['name']} Lv.{level}    {info['stat']} +{pct}%")
            else:
                lines.append(f"  槽位 {i}    （空）")

        lines.append("")
        lines.append("📌 输入「/被动 背包」查看拥有的技能书")
        lines.append("📌 输入「/被动 升级 蛮力印记」消耗同名书升级")
        return "\n".join(lines)

    def _passive_bag(self, user_id: str) -> str:
        bags = self.dm.get_all_passive_bags(user_id)
        slots = self.dm.get_passive_slots(user_id)
        equipped_ids = set(slots.values())

        if not bags:
            return "📦 被动技能书背包空空如也~\n📌 挑战副本可获得技能书"

        lines = ["📦 被动技能书背包", ""]
        for skill_id, count in sorted(bags.items()):
            if skill_id not in PASSIVE_SKILLS:
                continue
            info = PASSIVE_SKILLS[skill_id]
            icon = CATEGORY_ICON.get(info["category"], "❓")
            equipped = "（已装备" if skill_id in equipped_ids else "（未装备"
            level = self.dm.get_passive_level(user_id, skill_id)
            if level > 0:
                equipped += f" Lv.{level}"
            equipped += "）"
            lines.append(f"  {icon} {info['name']}    ×{count}{equipped}")

        lines.append("")
        lines.append("📌 输入「/被动 装备 坚韧体魄 4」装备到槽位 4")
        lines.append("📌 输入「/被动 升级 蛮力印记」消耗同名书升级")
        return "\n".join(lines)

    def _passive_equip(self, user_id: str, name: str, slot_str: str) -> str:
        if not slot_str.isdigit():
            return "❌ 槽位号必须为 1~4 的数字"
        slot = int(slot_str)
        if slot < 1 or slot > PASSIVE_SLOTS:
            return f"❌ 槽位号必须为 1~{PASSIVE_SLOTS}"

        skill_id = _resolve_skill_name(name)
        if not skill_id:
            return "❌ 技能不存在，输入「/被动 背包」查看拥有的技能"

        bag_count = self.dm.get_passive_bag(user_id, skill_id)
        level = self.dm.get_passive_level(user_id, skill_id)
        if level == 0 and bag_count < 1:
            return "❌ 你没有该技能书，挑战副本可获得"

        slots = self.dm.get_passive_slots(user_id)
        for s, sid in slots.items():
            if sid == skill_id and int(s) != slot:
                return f"❌ 该技能已装备在槽位 {s}，不可重复装备"

        if level == 0:
            self.dm.use_passive_bag(user_id, skill_id, 1)
            self.dm.set_passive_level(user_id, skill_id, 1)

        self.dm.set_passive_slot(user_id, slot, skill_id)
        info = PASSIVE_SKILLS[skill_id]
        pct = info["pct_per_level"][0]
        return f"✅ {info['name']} 已装备到槽位 {slot}（Lv.1，{info['stat']} +{pct}%）"

    def _passive_upgrade(self, user_id: str, name: str) -> str:
        skill_id = _resolve_skill_name(name)
        if not skill_id:
            return "❌ 技能不存在，输入「/被动 背包」查看拥有的技能"

        level = self.dm.get_passive_level(user_id, skill_id)
        if level == 0:
            return "❌ 你还没有该技能，先装备或获取技能书"
        if level >= MAX_PASSIVE_LEVEL:
            return f"❌ {PASSIVE_SKILLS[skill_id]['name']} 已满级（Lv.{MAX_PASSIVE_LEVEL}）"

        cost = UPGRADE_COSTS[level]
        bag_count = self.dm.get_passive_bag(user_id, skill_id)
        if bag_count < cost:
            return f"❌ 需要 {cost} 本同名技能书（当前 ×{bag_count}），挑战副本获取更多"

        self.dm.use_passive_bag(user_id, skill_id, cost)
        new_level = level + 1
        self.dm.set_passive_level(user_id, skill_id, new_level)

        info = PASSIVE_SKILLS[skill_id]
        old_pct = info["pct_per_level"][level - 1]
        new_pct = info["pct_per_level"][new_level - 1]
        remaining = self.dm.get_passive_bag(user_id, skill_id)

        return (f"✅ {info['name']} 升级成功！\n"
                f"   Lv.{level} → Lv.{new_level}\n"
                f"   {info['stat']} +{old_pct}% → +{new_pct}%\n"
                f"   消耗：{info['name']} ×{cost}（剩余 ×{remaining}）")

    def _passive_reset(self, user_id: str, slot_str: str) -> str:
        if not slot_str.isdigit():
            return "❌ 槽位号必须为 1~4 的数字"
        slot = int(slot_str)
        if slot < 1 or slot > PASSIVE_SLOTS:
            return f"❌ 槽位号必须为 1~{PASSIVE_SLOTS}"

        slots = self.dm.get_passive_slots(user_id)
        skill_id = slots.get(str(slot))
        if not skill_id:
            return f"❌ 槽位 {slot} 为空，无需重置"

        if self.dm.is_passive_reset_today(user_id, slot):
            return "❌ 该槽位今日已重置过，明日 0:00 后可再次重置"

        if not self.dm.use_diamond(user_id, RESET_COST):
            current = self.dm.get_diamond(user_id)
            return f"❌ 钻石不足（当前 {current}/{RESET_COST}），每日签到可获得钻石"

        self.dm.clear_passive_slot(user_id, slot)
        self.dm.add_passive_bag(user_id, skill_id, 1)
        self.dm.mark_passive_reset(user_id, slot)

        info = PASSIVE_SKILLS.get(skill_id, {"name": skill_id})
        return f"✅ 槽位 {slot} 已重置！{info['name']} 已卸下（退还 Lv.1 技能书 ×1），花费 {RESET_COST} 钻石"
