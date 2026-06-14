from src.game.commands import command
from src.game.boss_config import (
    BOSSES, BOSS_ATTACK_CD, BOSS_ENERGY_COST, BOSS_BATTLE_DURATION,
    EXP_REWARDS, get_active_boss,
)
from src.battle import battle_engine
from src.pet.stats import calc_stats


class BossMixin:

    @command("boss")
    def boss(self, user_id: str, user_name: str = "", arg: str = "", group_id: str = "") -> str | list[str]:
        parts = arg.split()

        if not parts or not parts[0]:
            return self._boss_status(group_id)

        sub = parts[0].lower()
        if sub in ("攻击", "attack"):
            return self._boss_attack(user_id, group_id)
        elif sub in ("排行", "rank"):
            return self._boss_rank(group_id)
        elif sub in ("奖励", "claim"):
            return self._boss_claim(user_id, group_id)

        return self._boss_status(group_id)

    def _boss_status(self, group_id: str) -> str:
        active = get_active_boss()
        if not active:
            lines = ["🐲 当前没有活跃的世界 Boss", "", "📌 Boss 出现时间表："]
            for boss_id, info in BOSSES.items():
                if info.get("weekly"):
                    lines.append(f"  {info['name']} — 每周日 21:00 (Lv.{info['min_level']}+)")
                else:
                    times = ", ".join(f"{h:02d}:{m:02d}" for h, m in info["schedule"])
                    lines.append(f"  {info['name']} — 每日 {times} (Lv.{info['min_level']}+)")
            return "\n".join(lines)

        boss_id, info = active
        hp = self.dm.get_boss_hp(boss_id)
        if hp == 0:
            hp = info["hp"]

        rank = self.dm.get_boss_rank(boss_id, 3)
        participants = self.dm.get_boss_rank_count(boss_id)

        lines = [
            f"🐲 世界 Boss：{info['name']}",
            f"   ❤️ HP：{hp:,} / {info['hp']:,}",
            f"   👥 参与人数：{participants}",
        ]

        if rank:
            lines.append("")
            lines.append("🏆 伤害排行 Top 3：")
            for i, (uid, dmg) in enumerate(rank):
                medals = ["🥇", "🥈", "🥉"]
                lines.append(f"   {medals[i]} {uid}: {dmg:,.0f}")

        lines.append("")
        lines.append("📌 /boss 攻击 — 参与战斗（20 行动力，10s CD）")
        lines.append("📌 /boss 排行 — 查看伤害排行")
        lines.append("📌 /boss 奖励 — 领取奖励")

        return "\n".join(lines)

    def _boss_attack(self, user_id: str, group_id: str) -> str | list[str]:
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"

        if pet.training:
            return "❌ 训练中无法攻击 Boss"

        active = get_active_boss()
        if not active:
            return "❌ 当前没有活跃的世界 Boss"

        boss_id, info = active

        cd_key = f"boss_attack_{boss_id}"
        cd_remaining = self.dm.get_cooldown(user_id, cd_key)
        if cd_remaining > 0:
            return f"⏳ 攻击冷却中，剩 {cd_remaining:.0f} 秒"

        if not self.dm.use_energy(user_id, BOSS_ENERGY_COST):
            energy = self.dm.get_energy(user_id)
            return f"❌ 行动力不足（当前 {energy['value']}/{BOSS_ENERGY_COST}）"

        if pet.level < info["min_level"]:
            return f"⚠️ 推荐等级 Lv.{info['min_level']}+，你的宠物为 Lv.{pet.level}"

        hp = self.dm.get_boss_hp(boss_id)
        if hp == 0:
            self.dm.set_boss_hp(boss_id, info["hp"])
            hp = info["hp"]

        if hp <= 0:
            return "🎉 Boss 已被击杀！使用 /boss 奖励 领取奖励"

        from src.pet.config import PET_SPECIES
        monster_stats = calc_stats(info["species_id"], info["stage"], info["min_level"],
                                   {"iv_hp": 15, "iv_atk": 15, "iv_def": 15, "iv_spd": 15, "iv_crit": 15, "iv_eva": 15})

        monster_dict = {
            "owner_id": "boss",
            "name": info["name"],
            "species_id": info["species_id"],
            "evolution_stage": info["stage"],
            "battle_type": PET_SPECIES[info["species_id"]]["battle_type"],
            "level": info["min_level"],
            "hp": min(hp, monster_stats["hp"]),
            **monster_stats,
        }

        start_msg = f"⚔️ 你对 {info['name']} 发起了攻击！\n战斗进行中..."

        self.dm.set_cooldown(user_id, cd_key, BOSS_ATTACK_CD)

        result = battle_engine.run(pet.to_dict(), monster_dict, max_duration=BOSS_BATTLE_DURATION)

        total_damage = sum(ev.damage for ev in result.events if ev.source == pet.name and ev.type in ("attack", "damage"))

        self.dm.add_boss_damage(boss_id, user_id, total_damage)
        new_hp = self.dm.decr_boss_hp(boss_id, total_damage)

        rank = self.dm.get_boss_rank(boss_id)
        user_rank = next((i + 1 for i, (uid, _) in enumerate(rank) if uid == user_id), len(rank))
        total_participants = len(rank)

        energy = self.dm.get_energy(user_id)

        lines = [
            f"🎯 本次伤害：{total_damage:,.0f}",
            f"🔻 剩余 HP：{new_hp:,} / {info['hp']:,}",
            f"📊 你的累计伤害排名：第 {user_rank} / {total_participants} 人",
            f"🔋 行动力：{energy['value']}/100",
        ]

        if new_hp <= 0:
            self.dm.set_boss_last_kill(boss_id, user_id)
            lines.append(f"\n🎉 {info['name']} 已被击杀！")
            lines.append("📌 使用 /boss 奖励 领取奖励")

        return [start_msg, "\n".join(lines)]

    def _boss_rank(self, group_id: str) -> str:
        active = get_active_boss()
        if not active:
            return "❌ 当前没有活跃的世界 Boss"

        boss_id, info = active
        rank = self.dm.get_boss_rank(boss_id, 20)

        if not rank:
            return f"🐲 {info['name']} 伤害排行\n\n暂无参与者"

        lines = [f"🐲 {info['name']} 伤害排行 Top 20", ""]
        for i, (uid, dmg) in enumerate(rank):
            medal = "🥇🥈🥉"[i] if i < 3 else f"{i+1}."
            lines.append(f"  {medal} {uid}: {dmg:,.0f}")

        return "\n".join(lines)

    def _boss_claim(self, user_id: str, group_id: str) -> str:
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"

        active = get_active_boss()
        if not active:
            return "❌ 当前没有活跃的世界 Boss"

        boss_id, info = active

        if self.dm.is_boss_claimed(boss_id, user_id):
            return "❌ 你已经领取过本次 Boss 奖励了"

        damage = self.dm.get_boss_damage(boss_id, user_id)
        if damage <= 0:
            return "❌ 你未参与本次 Boss 战斗"

        rank = self.dm.get_boss_rank(boss_id)
        user_rank = next((i + 1 for i, (uid, _) in enumerate(rank) if uid == user_id), 0)
        total = len(rank)

        if user_rank == 0:
            return "❌ 排名异常"

        if user_rank == 1:
            exp_mult = EXP_REWARDS["top1"]
        elif user_rank <= 3:
            exp_mult = EXP_REWARDS["top2_3"]
        elif user_rank <= 10:
            exp_mult = EXP_REWARDS["top4_10"]
        elif user_rank <= total * 0.3:
            exp_mult = EXP_REWARDS["top11_30pct"]
        elif user_rank <= total * 0.6:
            exp_mult = EXP_REWARDS["top30_60pct"]
        else:
            exp_mult = EXP_REWARDS["top60_100pct"]

        exp = pet.level * exp_mult
        self.dm.add_exp(user_id, exp)
        self.dm.mark_boss_claimed(boss_id, user_id)

        lines = [
            f"🎁 Boss 奖励领取成功！",
            f"   🏆 排名：第 {user_rank} / {total} 人",
            f"   ⭐ 经验 +{exp:,}",
        ]

        return "\n".join(lines)
