"""
pet_game.py - Battle pet game logic.

Commands: adopt, status, abandon, rename, top, help,
          battle_pvp, evolve, train, rest, stats_detail
"""
from __future__ import annotations

import random
import time

from src.data_manager import DataManager, Pet, data_manager
from src.pet_config import PET_SPECIES, Skill, SkillEffect
from src.pet_stats import (generate_ivs, calc_stats, calc_training_exp,
                           format_battle_stats, format_iv_detail, quality_label)
from src.battle import battle_engine, format_battle_report


class PetGame:
    """Battle pet game."""

    def __init__(self, dm: DataManager):
        self.dm = dm

    # ── Adopt ──

    def adopt(self, user_id: str, user_name: str, _arg: str = "") -> str:
        """Randomly adopt a pet from 25 species."""
        if self.dm.has_pet(user_id):
            pet = self.dm.get_pet(user_id)
            return (f"❌ 你已经有一只 {pet.species_name}「{pet.name}」了！\n"
                    f"使用「/遗弃」先放生当前宠物才能领养新的哦~")

        # Random species
        species_id = random.choice(list(PET_SPECIES.keys()))
        species = PET_SPECIES[species_id]
        pet_name = species["names"][0]  # Stage 0 name

        # Generate IVs
        ivs = generate_ivs()

        # Calculate stats
        stats = calc_stats(species_id, 0, 1, ivs)
        battle_type = species["battle_type"]
        q = sum(ivs.values())
        q_rating = "S" if q >= 151 else "A" if q >= 121 else "B" if q >= 91 else "C" if q >= 61 else "D" if q >= 31 else "E"

        pet = self.dm.create_pet(user_id, user_name, species_id, pet_name,
                                 battle_type, ivs, stats)
        self.dm.update_leaderboard(pet)

        type_names = {"attack": "攻击型", "defense": "防御型", "speed": "速度型"}
        btype_cn = type_names.get(battle_type, battle_type)

        return (
            f"🎉 领养成功！\n"
            f"🐷 一只{pet_name}成为了你的伙伴！\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⭐ 品质：{q_rating}({quality_label(q_rating)})  |  类型：{btype_cn}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📛 名字：{pet_name}（可使用 /改名 修改）\n"
            f"使用「/状态」查看宠物详情  |  「/帮助」查看所有命令"
        )

    # ── Status ──

    def status(self, user_id: str) -> str:
        """Show pet battle status."""
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"

        self.dm.update_leaderboard(pet)

        # Gate info
        gate_info = ""
        if pet.evolution_stage == 0 and pet.level >= 29:
            gate_info = "\n⚠️ 已达 29 级上限，需要「/进化」才能继续升级！"
        elif pet.evolution_stage == 1 and pet.level >= 59:
            gate_info = "\n⚠️ 已达 59 级上限，需要「/进化」才能继续升级！"

        return format_battle_stats(pet) + gate_info

    # ── Stats Detail ──

    def stats_detail(self, user_id: str) -> str:
        """Show detailed stats including IVs."""
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"
        return format_battle_stats(pet) + "\n\n" + format_iv_detail(pet)

    # ── Abandon ──

    def abandon(self, user_id: str) -> str:
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"
        name = pet.name
        self.dm.delete_pet(user_id)
        return (f"😢 你含泪放生了 {pet.species_name}「{name}」...\n"
                f"使用「/领养」可以重新领养一只新的伙伴。")

    # ── Rename ──

    def rename(self, user_id: str, new_name: str) -> str:
        if not new_name or len(new_name) > 8:
            return "❌ 名字长度需在 1-8 个字符之间！"
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"
        old = pet.name
        self.dm.rename_pet(user_id, new_name)
        return f"✅ 改名成功！「{old}」→「{new_name}」"

    # ── Evolve ──

    def evolve(self, user_id: str) -> str:
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"

        if pet.evolution_stage >= 2:
            return "❌ 已经是三阶形态，无法再进化了！"

        gate = 29 if pet.evolution_stage == 0 else 59
        if pet.level < gate:
            return f"❌ 需要达到 Lv.{gate} 才能进化！（当前 Lv.{pet.level}）"

        old_name = pet.species_name
        result = self.dm.evolve_pet(user_id)
        if result is None:
            return "❌ 进化失败，请稍后再试。"

        new_name = result.species_name
        self.dm.update_leaderboard(result)

        stage_names = ["一阶", "二阶", "三阶"]
        return (
            f"🎊 进化成功！\n"
            f"🐷 {old_name} → {new_name}\n"
            f"⭐ 新形态：{stage_names[result.evolution_stage]}进化\n"
            f"📊 解锁新技能！属性已追溯重算\n"
            f"使用「/状态」查看新形态的详细属性"
        )

    # ── Training ──

    def start_training(self, user_id: str) -> str:
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"

        if pet.training:
            elapsed = int((time.time() - pet.training_start) / 60)
            return (f"⏳ 宠物正在训练中！（已训练 {elapsed} 分钟）\n"
                    f"需要至少训练 10 分钟后使用「/休息」结束训练。")

        result = self.dm.start_training(user_id)
        if result is None:
            return "❌ 开始训练失败。"

        exp_10min = calc_training_exp(pet.level, 10)
        return (
            f"💪 {pet.species_name}「{pet.name}」开始训练！\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⏱ 训练中... 最少训练 10 分钟\n"
            f"📊 预计 10 分钟后获得 {exp_10min} 经验\n"
            f"📊 训练时间越长，经验越多！\n"
            f"🔒 训练期间无法进行其他操作\n"
            f"💡 记得 10 分钟后使用「/休息」结束训练领取经验！"
        )

    def end_training(self, user_id: str) -> str:
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"

        if not pet.training:
            return "❌ 宠物不在训练中！使用「/训练」开始训练。"

        result, exp_gained = self.dm.end_training(user_id)
        if exp_gained == -1:
            elapsed = int((time.time() - pet.training_start) / 60)
            remaining = 10 - elapsed
            return f"⏳ 还需要训练 {remaining} 分钟才能休息！\n已训练 {elapsed} 分钟，至少需要 10 分钟。"

        if result is None:
            return "❌ 结束训练失败。"

        minutes = int((time.time() - pet.training_start) / 60)
        self.dm.update_leaderboard(result)

        # Check if level up occurred
        level_info = ""
        if result.level > pet.level:
            level_info = f"\n🎉 升级了！Lv.{pet.level} → Lv.{result.level}"

        # Check evolution gate
        gate_info = ""
        if result.evolution_stage == 0 and result.level >= 29:
            gate_info = "\n⚠️ 已达 29 级上限，需要「/进化」才能继续升级！"
        elif result.evolution_stage == 1 and result.level >= 59:
            gate_info = "\n⚠️ 已达 59 级上限，需要「/进化」才能继续升级！"

        return (
            f"🛌 {result.species_name}「{result.name}」训练结束！\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⏱ 训练时长：{minutes} 分钟\n"
            f"✨ 获得经验：{exp_gained}\n"
            f"📊 当前经验：{result.exp}/{result.max_exp}"
            f"{level_info}{gate_info}"
        )

    # ── PvP Battle ──

    def battle_pvp(self, challenger_id: str, target_id: str) -> str:
        """PvP battle between two users."""
        if challenger_id == target_id:
            return "❌ 不能挑战自己哦！"

        pet_a = self.dm.get_pet(challenger_id)
        if pet_a is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"

        if pet_a.training:
            return "❌ 你的宠物正在训练中，无法战斗！使用「/休息」结束训练。"

        pet_b = self.dm.get_pet(target_id)
        if pet_b is None:
            return "❌ 对方还没有宠物！"

        if pet_b.training:
            return "❌ 对方的宠物正在训练中，暂时无法挑战！"

        # Run battle
        result = battle_engine.run(pet_a.to_dict(), pet_b.to_dict())

        # Grant EXP to both sides
        exp_winner = 50 * pet_a.level if result.winner else 0
        exp_loser = 20 * pet_a.level

        if result.winner == challenger_id:
            self.dm.add_exp(challenger_id, exp_winner)
            self.dm.add_exp(target_id, exp_loser)
            self.dm.update_leaderboard(self.dm.get_pet(challenger_id))
            self.dm.update_leaderboard(self.dm.get_pet(target_id))
        elif result.winner == target_id:
            self.dm.add_exp(target_id, exp_winner)
            self.dm.add_exp(challenger_id, exp_loser)
            self.dm.update_leaderboard(self.dm.get_pet(target_id))
            self.dm.update_leaderboard(self.dm.get_pet(challenger_id))

        return format_battle_report(result)

    # ── Leaderboard ──

    def top(self) -> str:
        board = self.dm.get_leaderboard(10)
        if not board:
            return "📊 排行榜还是空的，快来领养宠物吧！"

        medals = ["🥇", "🥈", "🥉"]
        lines = ["🏆 宠物排行榜 TOP10"]
        lines.append("━━━━━━━━━━━━━━━━━━")
        for i, entry in enumerate(board):
            medal = medals[i] if i < 3 else f"{i+1}."
            stage_names = ["一阶", "二阶", "三阶"]
            stage = stage_names[entry["evolution_stage"]] if entry["evolution_stage"] < 3 else "三阶"
            lines.append(
                f"{medal} {entry['species_name']}「{entry['pet_name']}」"
                f"(Lv.{entry['level']} {stage})"
                f" - {entry['owner_name']}"
            )
        return "\n".join(lines)

    # ── Help ──

    def help(self) -> str:
        return (
            "🐷 宠物战斗机器人 - 帮助菜单\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📋 基础命令：\n"
            "  /领养        - 随机领养一只猪猪宠物\n"
            "  /状态        - 查看宠物属性\n"
            "  /属性        - 查看详细属性(含IV)\n"
            "  /遗弃        - 遗弃当前宠物\n"
            "  /改名 <名>   - 给宠物改名\n"
            "  /帮助        - 显示本帮助\n\n"
            "⚔️ 战斗与成长：\n"
            "  /战斗 @某人  - 与对方宠物进行战斗\n"
            "  /进化        - 进化宠物(Lv29/Lv59)\n"
            "  /训练        - 开始训练(10分钟)\n"
            "  /休息        - 结束训练领取经验\n\n"
            "🏆 /排行 - 查看排行榜\n\n"
            "💡 提示：训练是获取经验的主要方式，\n"
            "   战斗可以获得额外经验奖励！"
        )


# Global instance
game = PetGame(data_manager)
