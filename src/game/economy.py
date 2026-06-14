from src.game.commands import command
from src.game.shop_config import SHOP_ITEMS, DIAMOND_ITEMS, USE_ITEMS, resolve_item_id

CHECKIN_REWARDS = {
    1: {"gold": 1000, "diamond": 5, "item": None},
    2: {"gold": 1000, "diamond": 5, "item": ("potion_s", 1)},
    3: {"gold": 1500, "diamond": 5, "item": None},
    4: {"gold": 1500, "diamond": 5, "item": ("energy_potion", 1)},
    5: {"gold": 2000, "diamond": 5, "item": None},
    6: {"gold": 2000, "diamond": 10, "item": ("potion_m", 1)},
    7: {"gold": 5000, "diamond": 15, "item": ("potion_l", 1)},
}


class EconomyMixin:

    @command("签到", "checkin")
    def checkin(self, user_id: str, user_name: str = "", arg: str = "", group_id: str = "") -> str:
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"

        if self.dm.is_checked_in_today(user_id):
            streak = self.dm.get_streak(user_id)
            return f"📅 今日已签到！当前连续签到 {streak} 天"

        streak = self.dm.do_checkin(user_id)
        if streak == -1:
            return "📅 今日已签到！"

        day_in_cycle = ((streak - 1) % 7) + 1
        reward = CHECKIN_REWARDS[day_in_cycle]

        gold = reward["gold"]
        diamond = reward["diamond"]

        self.dm.add_gold(user_id, gold)
        self.dm.add_diamond(user_id, diamond)

        lines = [
            f"📅 签到成功！连续签到第 {streak} 天",
            "",
            f"   💰 金币 +{gold:,}",
            f"   💎 钻石 ×{diamond}",
        ]

        if reward.get("item"):
            item_id, qty = reward["item"]
            self.dm.add_item(user_id, item_id, qty)
            item_names = {
                "potion_s": "经验药水(小)",
                "potion_m": "经验药水(中)",
                "potion_l": "经验药水(大)",
                "energy_potion": "行动力药水",
            }
            lines.append(f"   🧪 {item_names.get(item_id, item_id)} ×{qty}")

        next_day = (day_in_cycle % 7) + 1
        next_reward = CHECKIN_REWARDS[next_day]
        lines.append("")
        lines.append(f"📌 明天签到可获得：金币 {next_reward['gold']:,} + 钻石 ×{next_reward['diamond']}")

        if day_in_cycle < 7:
            day7_reward = CHECKIN_REWARDS[7]
            lines.append(f"📌 第 7 天签到可获得：金币 {day7_reward['gold']:,} + 钻石 ×{day7_reward['diamond']} + 经验药水(大) ×1")

        return "\n".join(lines)

    @command("行动力", "energy")
    def energy_status(self, user_id: str, user_name: str = "", arg: str = "", group_id: str = "") -> str:
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"

        energy = self.dm.get_energy(user_id)
        current = energy["value"]

        lines = [
            f"🔋 行动力：{current}/100",
            "",
            "📌 自然回复：1 点 / 3 分钟（满速 5 小时回满）",
            "📌 每日 0:00 自动 +50",
            "",
            "消耗明细：",
            "  副本 1 关 = 5 行动力",
            "  Boss 1 击 = 20 行动力",
            "  群训练 1 次 = 20 行动力",
        ]

        if current < 100:
            import time
            last_update = energy["last_update"]
            elapsed = time.time() - last_update
            next_regen_in = 180 - (elapsed % 180)
            minutes = int(next_regen_in / 60)
            seconds = int(next_regen_in % 60)
            lines.append(f"\n⏱ 下次回复：约 {minutes}分{seconds}秒")

        return "\n".join(lines)

    @command("商店", "shop")
    def shop_menu(self, user_id: str, user_name: str = "", arg: str = "", group_id: str = "") -> str:
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"

        gold = self.dm.get_gold(user_id)
        diamond = self.dm.get_diamond(user_id)

        lines = [
            "🏪 商店",
            "",
            "━━ 金币商店 ━━",
        ]
        for item_id, info in SHOP_ITEMS.items():
            lines.append(f"  {info['name']}    {info['gold_price']:,} 金币    限购 {info['daily_limit']}/日")

        lines.append("")
        lines.append("━━ 钻石商店 ━━")
        for item_id, info in DIAMOND_ITEMS.items():
            lines.append(f"  {info['name']}    {info['diamond_price']} 钻石      限购 {info['daily_limit']}/日")

        lines.append("")
        lines.append(f"💰 你的金币：{gold:,}    💎 你的钻石：{diamond}")
        lines.append("📌 输入「/购买 经验药水小 3」购买 3 个经验药水(小)")

        return "\n".join(lines)

    @command("购买", "buy")
    def shop_buy(self, user_id: str, user_name: str = "", arg: str = "", group_id: str = "") -> str:
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"

        if not arg:
            return "❌ 请指定商品名！发送 /商店 查看商品列表"

        parts = arg.split()
        item_name = parts[0]
        qty = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1

        item_id = resolve_item_id(item_name)
        if not item_id:
            return "❌ 商品不存在，发送 /商店 查看商品列表"

        if item_id in SHOP_ITEMS:
            info = SHOP_ITEMS[item_id]
            total_cost = info["gold_price"] * qty
            bought = self.dm.get_shop_buy_count(user_id, item_id)
            if bought + qty > info["daily_limit"]:
                return f"❌ 该商品今日限购已达上限（{bought}/{info['daily_limit']}），明日 0:00 重置"
            if not self.dm.use_gold(user_id, total_cost):
                current = self.dm.get_gold(user_id)
                return f"❌ 金币不足（当前 {current:,}/{total_cost:,}），副本和签到可获得金币"
            self.dm.add_item(user_id, item_id, qty)
            self.dm.incr_shop_buy(user_id, item_id, qty)
            return f"✅ 购买成功！{info['name']} ×{qty}，花费 {total_cost:,} 金币"

        elif item_id in DIAMOND_ITEMS:
            info = DIAMOND_ITEMS[item_id]
            total_cost = info["diamond_price"] * qty
            bought = self.dm.get_shop_buy_count(user_id, f"d_{item_id}")
            if bought + qty > info["daily_limit"]:
                return f"❌ 该商品今日限购已达上限（{bought}/{info['daily_limit']}），明日 0:00 重置"
            if not self.dm.use_diamond(user_id, total_cost):
                current = self.dm.get_diamond(user_id)
                return f"❌ 钻石不足（当前 {current}/{total_cost}），每日签到可获得钻石"
            self.dm.add_item(user_id, item_id, qty)
            self.dm.incr_shop_buy(user_id, f"d_{item_id}", qty)
            return f"✅ 购买成功！{info['name']} ×{qty}，花费 {total_cost} 钻石"

        return "❌ 商品不存在，发送 /商店 查看商品列表"

    @command("使用", "use")
    def use_item_cmd(self, user_id: str, user_name: str = "", arg: str = "", group_id: str = "") -> str:
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"

        if not arg:
            return "❌ 请指定物品名！发送 /背包 查看持有物品"

        parts = arg.split()
        item_name = parts[0]
        qty = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1

        item_id = resolve_item_id(item_name)
        if not item_id or item_id not in USE_ITEMS:
            return "❌ 你没有该物品，发送 /背包 查看持有物品"

        info = USE_ITEMS[item_id]
        current_count = self.dm.get_use_item_count(user_id, item_id)
        if current_count + qty > info["daily_limit"]:
            return f"❌ 该物品今日使用次数已达上限（{current_count}/{info['daily_limit']}），明日 0:00 重置"

        if not self.dm.use_item(user_id, item_id, qty):
            return f"❌ 你没有该物品，发送 /背包 查看持有物品"

        self.dm.incr_use_item(user_id, item_id, qty)

        if info.get("exp"):
            total_exp = info["exp"] * qty
            self.dm.add_exp(user_id, total_exp)
            return f"✅ 使用了 {info['name']} ×{qty}，获得 {total_exp:,} 经验！"
        elif info.get("energy"):
            total_energy = info["energy"] * qty
            new_energy = self.dm.add_energy(user_id, total_energy)
            return f"✅ 使用了 {info['name']} ×{qty}，行动力 +{total_energy}（当前 {new_energy}）"

        return f"✅ 使用了 {info['name']} ×{qty}"

    @command("背包", "bag")
    def bag_list(self, user_id: str, user_name: str = "", arg: str = "", group_id: str = "") -> str:
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"

        items = self.dm.get_all_items(user_id)
        if not items:
            return "🎒 背包空空如也~\n📌 副本、签到和商店可获得物品"

        item_names = {}
        for item_id, info in USE_ITEMS.items():
            item_names[item_id] = info["name"]

        lines = ["🎒 背包", ""]
        for item_id, count in sorted(items.items()):
            name = item_names.get(item_id, item_id)
            lines.append(f"  {name}  ×{count}")

        lines.append("")
        lines.append("📌 输入「/使用 经验药水小 2」使用 2 个经验药水(小)")

        return "\n".join(lines)
