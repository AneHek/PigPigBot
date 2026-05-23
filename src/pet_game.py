"""
pet_game.py - 宠物养成游戏核心逻辑
"""
import time
from src.data_manager import DataManager, Pet
from src.config import config

game_config = config["game"]
# 冷却时间配置（秒）
COOLDOWNS = {
    "feed": 30,      # 喂食 30 秒冷却
    "play": 45,      # 玩耍 45 秒冷却
    "rest": 60,      # 休息 60 秒冷却
    "heal": 90,      # 治疗 90 秒冷却
    "work": 120,     # 打工 2 分钟冷却
    "train": 180,    # 训练 3 分钟冷却
}


def format_pet_status(pet: Pet) -> str:
    """格式化宠物状态信息"""
    hp_bar = _progress_bar(pet.health)
    full_bar = _progress_bar(pet.satiety)
    mood_bar = _progress_bar(pet.mood)
    energy_bar = _progress_bar(pet.energy)
    exp_bar = _progress_bar(pet.exp, pet.max_exp, 10)

    return (
        f"{pet.emoji} 【{pet.name}】 {pet.level_name} (Lv.{pet.level})\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"❤️ 健康：{hp_bar} {pet.health}/100\n"
        f"🍖 饱食：{full_bar} {pet.satiety}/100\n"
        f"😊 心情：{mood_bar} {pet.mood}/100\n"
        f"⚡ 体力：{energy_bar} {pet.energy}/100\n"
        f"✨ 经验：{exp_bar} {pet.exp}/{pet.max_exp}\n"
        f"💰 金币：{pet.coins}\n"
        f"🎯 统计：喂食{pet.total_feed}次 | 玩耍{pet.total_play}次 | 打工{pet.total_work}次 | 训练{pet.total_train}次"
    )


def _progress_bar(current: int, maximum: int = 100, length: int = 10) -> str:
    """生成进度条"""
    ratio = max(0, min(1, current / maximum if maximum > 0 else 0))
    filled = int(ratio * length)
    empty = length - filled
    color = "🟩" if ratio > 0.5 else ("🟨" if ratio > 0.2 else "🟥")
    return f"{color * filled}{'⬛' * empty}"


class PetGame:
    """宠物养成游戏类"""

    def __init__(self, dm: DataManager):
        self.dm = dm

    def adopt(self, user_id: str, user_name: str, pet_type_id: str) -> str | None:
        """领养宠物，返回格式化消息或 None（失败）"""
        if self.dm.has_pet(user_id):
            pet = self.dm.get_pet(user_id)
            return f"❌ 你已经有一只 {pet.emoji}{pet.name} 了！\n使用「/遗弃」先放生当前宠物才能领养新的哦~"

        pet_configs = game_config["pet_types"]
        matched = None
        # 支持通过 ID 或名称匹配
        for pt in pet_configs:
            if pt["id"] == pet_type_id or pt["name"] == pet_type_id:
                matched = pt
                break

        if matched is None:
            available = "、".join(f"{p['emoji']}{p['name']}({p['id']})" for p in pet_configs)
            return f"❌ 没有找到这种宠物！\n可领养的宠物有：\n{available}\n\n使用「/领养 种类」来选择你的伙伴吧！"

        pet = self.dm.create_pet(user_id, user_name, matched["id"], matched)
        self.dm.update_leaderboard(pet)

        return (
            f"🎉 领养成功！\n"
            f"{matched['emoji']} 一只可爱的{matched['name']}成为了你的伙伴！\n"
            f"「{matched['desc']}」\n\n"
            f"📛 名字：{matched['name']}（可使用 /改名 修改）\n"
            f"使用「/状态」查看宠物详情  |  「/帮助」查看所有命令"
        )

    def abandon(self, user_id: str) -> str:
        """遗弃宠物"""
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物呢！使用「/领养 种类」来领养一只吧~"
        self.dm.delete_pet(user_id)
        return (
            f"😢 你含泪放生了 {pet.emoji}{pet.name}...\n"
            f"它回头看了你最后一眼，消失在了远方。\n"
            f"使用「/领养 种类」可以重新领养一只新的伙伴。"
        )

    def status(self, user_id: str) -> str:
        """查看宠物状态"""
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养 种类」来领养一只吧~"

        # 先应用衰减
        self.dm.apply_decay(user_id, {
            "interval": game_config["decay_interval"]
        })

        # 重新获取更新后的宠物
        pet = self.dm.get_pet(user_id)
        if pet.is_dead:
            self.dm.delete_pet(user_id)
            return (
                f"💀 你的宠物 {pet.emoji}{pet.name} 因为疏于照顾已经离你而去了...\n"
                f"请好好反思，然后使用「/领养 种类」重新开始吧！"
            )

        self.dm.update_leaderboard(pet)
        return format_pet_status(pet)

    def feed(self, user_id: str) -> str:
        """喂食"""
        cd = self.dm.get_cooldown(user_id, "feed")
        if cd > 0:
            return f"⏳ 喂食冷却中，请等待 {int(cd)} 秒后再试"

        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养 种类」来领养一只吧~"
        if pet.is_dead:
            return "💀 你的宠物已经...请重新领养吧"

        if pet.coins < 5:
            return "❌ 金币不足！喂食需要 5 金币，试试「/打工」赚点金币吧！"

        pet = self.dm.update_pet(user_id,
            satiety=pet.satiety + 25,
            coins=pet.coins - 5,
            total_feed=pet.total_feed + 1,
        )
        pet = self.dm.add_exp(user_id, game_config["exp"]["feed"])
        self.dm.set_cooldown(user_id, "feed", COOLDOWNS["feed"])
        self.dm.update_leaderboard(pet)

        foods = ["🍖 肉肉", "🐟 小鱼干", "🍎 水果", "🥕 胡萝卜", "🍰 蛋糕", "🍗 鸡腿"]
        import random
        food = random.choice(foods)
        return (
            f"🍽️ 你给 {pet.emoji}{pet.name} 喂了{food}！\n"
            f"饱食度 +25 | 金币 -5\n"
            f"✨ 经验 +{game_config['exp']['feed']}"
        )

    def play(self, user_id: str) -> str:
        """玩耍"""
        cd = self.dm.get_cooldown(user_id, "play")
        if cd > 0:
            return f"⏳ 玩耍冷却中，请等待 {int(cd)} 秒后再试"

        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养 种类」来领养一只吧~"
        if pet.is_dead:
            return "💀 你的宠物已经...请重新领养吧"

        if pet.energy < 10:
            return "❌ 宠物体力不足！让它「/休息」一下吧~"

        pet = self.dm.update_pet(user_id,
            mood=pet.mood + 20,
            energy=pet.energy - 10,
            total_play=pet.total_play + 1,
        )
        pet = self.dm.add_exp(user_id, game_config["exp"]["play"])
        self.dm.set_cooldown(user_id, "play", COOLDOWNS["play"])
        self.dm.update_leaderboard(pet)

        import random
        games = ["⚽ 扔飞盘", "🎾 玩球球", "🪀 玩悠悠球", "🧶 玩毛线团", "🐾 捉迷藏", "🫧 追泡泡"]
        game = random.choice(games)
        return (
            f"🎮 你和 {pet.emoji}{pet.name} 一起{game}！\n"
            f"心情 +20 | 体力 -10\n"
            f"✨ 经验 +{game_config['exp']['play']}"
        )

    def rest(self, user_id: str) -> str:
        """休息"""
        cd = self.dm.get_cooldown(user_id, "rest")
        if cd > 0:
            return f"⏳ 休息冷却中，请等待 {int(cd)} 秒后再试"

        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养 种类」来领养一只吧~"
        if pet.is_dead:
            return "💀 你的宠物已经...请重新领养吧"

        pet = self.dm.update_pet(user_id,
            energy=pet.energy + 35,
            mood=pet.mood + 5,
        )
        self.dm.set_cooldown(user_id, "rest", COOLDOWNS["rest"])
        self.dm.update_leaderboard(pet)

        return (
            f"😴 {pet.emoji}{pet.name} 美美地睡了一觉！\n"
            f"体力 +35 | 心情 +5\n"
            f"💤 Zzz..."
        )

    def heal(self, user_id: str) -> str:
        """治疗"""
        cd = self.dm.get_cooldown(user_id, "heal")
        if cd > 0:
            return f"⏳ 治疗冷却中，请等待 {int(cd)} 秒后再试"

        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养 种类」来领养一只吧~"
        if pet.is_dead:
            return "💀 你的宠物已经...请重新领养吧"

        if pet.coins < 15:
            return "❌ 金币不足！治疗需要 15 金币，试试「/打工」赚点金币吧！"

        pet = self.dm.update_pet(user_id,
            health=pet.health + 35,
            coins=pet.coins - 15,
        )
        self.dm.set_cooldown(user_id, "heal", COOLDOWNS["heal"])
        self.dm.update_leaderboard(pet)

        return (
            f"🏥 你带 {pet.emoji}{pet.name} 去了宠物医院！\n"
            f"健康 +35 | 金币 -15\n"
            f"💊 打了针，吃了药，活力满满！"
        )

    def work(self, user_id: str) -> str:
        """打工"""
        cd = self.dm.get_cooldown(user_id, "work")
        if cd > 0:
            return f"⏳ 打工冷却中，请等待 {int(cd)} 秒后再试"

        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养 种类」来领养一只吧~"
        if pet.is_dead:
            return "💀 你的宠物已经...请重新领养吧"

        if pet.energy < 15:
            return "❌ 宠物体力不足！让它「/休息」一下吧~"

        if pet.mood < 10:
            return "❌ 宠物心情太差了！先「/玩耍」哄哄它吧~"

        import random
        earn = random.randint(20, 40)
        pet = self.dm.update_pet(user_id,
            coins=pet.coins + earn,
            energy=pet.energy - 15,
            mood=pet.mood - 10,
            total_work=pet.total_work + 1,
        )
        pet = self.dm.add_exp(user_id, game_config["exp"]["work"])
        self.dm.set_cooldown(user_id, "work", COOLDOWNS["work"])
        self.dm.update_leaderboard(pet)

        jobs = [
            "📦 帮快递站分拣包裹",
            "🌾 帮农场收庄稼",
            "🎵 在街头表演才艺",
            "📚 帮图书馆整理书籍",
            "🍰 在蛋糕店做学徒",
            "🏪 在便利店看店",
        ]
        job = random.choice(jobs)
        return (
            f"💼 {pet.emoji}{pet.name} {job}！\n"
            f"💰 金币 +{earn} | 体力 -15 | 心情 -10\n"
            f"✨ 经验 +{game_config['exp']['work']}"
        )

    def train(self, user_id: str) -> str:
        """训练"""
        cd = self.dm.get_cooldown(user_id, "train")
        if cd > 0:
            return f"⏳ 训练冷却中，请等待 {int(cd)} 秒后再试"

        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养 种类」来领养一只吧~"
        if pet.is_dead:
            return "💀 你的宠物已经...请重新领养吧"

        if pet.energy < 20:
            return "❌ 宠物体力不足！让它「/休息」一下吧~"

        if pet.satiety < 15:
            return "❌ 宠物太饿了！先「/喂食」喂饱它吧~"

        import random
        bonus_exp = random.randint(20, 35)
        pet = self.dm.update_pet(user_id,
            energy=pet.energy - 20,
            satiety=pet.satiety - 15,
            total_train=pet.total_train + 1,
        )
        pet = self.dm.add_exp(user_id, game_config["exp"]["train"] + bonus_exp)
        self.dm.set_cooldown(user_id, "train", COOLDOWNS["train"])
        self.dm.update_leaderboard(pet)

        trainings = [
            "🏋️ 力量训练",
            "🏃 耐力跑步",
            "🧘 冥想修炼",
            "🎯 敏捷训练",
            "📖 智慧学习",
            "🥋 格斗练习",
        ]
        t = random.choice(trainings)
        return (
            f"💪 你带 {pet.emoji}{pet.name} 进行了{t}！\n"
            f"体力 -20 | 饱食 -15 | 经验 +{game_config['exp']['train'] + bonus_exp}\n"
            f"✨ 额外获得 {bonus_exp} 经验奖励！"
        )

    def rename(self, user_id: str, new_name: str) -> str:
        """重命名宠物"""
        if not new_name or len(new_name) > 10:
            return "❌ 名字长度需在 1-10 个字符之间！"
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养 种类」来领养一只吧~"
        if pet.coins < 30:
            return "❌ 改名需要 30 金币哦！快去「/打工」赚金币吧~"
        old_name = pet.name
        self.dm.update_pet(user_id, coins=pet.coins - 30)
        self.dm.rename_pet(user_id, new_name)
        return (
            f"✅ 改名成功！\n"
            f"{pet.emoji} 「{old_name}」→「{new_name}」\n"
            f"💰 花费 30 金币"
        )

    def top(self) -> str:
        """排行榜"""
        board = self.dm.get_leaderboard(10)
        if not board:
            return "📊 排行榜还是空的，快来领养宠物吧！"

        medals = ["🥇", "🥈", "🥉"]
        lines = ["🏆 宠物排行榜 TOP10"]
        lines.append("━━━━━━━━━━━━━━━━━━")
        for i, entry in enumerate(board):
            medal = medals[i] if i < 3 else f"{i+1}."
            lines.append(
                f"{medal} {entry['emoji']}{entry['pet_name']} "
                f"(Lv.{entry['level']} | 💰{entry['coins']})"
                f" - {entry['owner_name']}"
            )
        return "\n".join(lines)

    def help(self) -> str:
        """帮助信息"""
        return (
            "🐾 宠物养成机器人 - 帮助菜单\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📋 基础命令：\n"
            "  /领养 <种类> - 领养一只宠物\n"
            "  /状态        - 查看宠物状态\n"
            "  /遗弃        - 遗弃当前宠物\n"
            "  /改名 <名>   - 给宠物改名(30💰)\n"
            "  /帮助        - 显示本帮助\n\n"
            "🎯 互动命令：\n"
            "  /喂食  - 喂食宠物 (5💰)\n"
            "  /玩耍  - 和宠物玩耍 (需体力≥10)\n"
            "  /休息  - 让宠物睡觉\n"
            "  /治疗  - 治疗宠物 (15💰)\n"
            "  /打工  - 打工赚金币 (需体力≥15, 心情≥10)\n"
            "  /训练  - 训练宠物 (需体力≥20, 饱食≥15)\n\n"
            "🏆 /排行 - 查看排行榜\n\n"
            "💡 提示：记得经常照顾你的宠物，不然它会生病的！\n"
            f"每隔{game_config['decay_interval']}分钟，属性会自然衰减哦~"
        )


# 全局游戏实例
game = PetGame(dm=None)  # 延迟初始化，由 main.py 注入

from src.data_manager import data_manager
game.dm = data_manager
