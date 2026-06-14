import random

from src.game.commands import command
from src.game.dungeon_config import (
    CHAPTERS, STAGES, STAGE_MATERIALS, CHAPTER_FIRST_REWARDS,
    ENERGY_COST, RESET_COST, get_stage_id, is_chapter_unlocked,
    get_enemy_passives,
)
from src.game.passive_config import (
    CHAPTER_DROP_POOL, STAGE_DROP_RATE, STAGE_FIRST_BONUS_RATE,
)
from src.battle import battle_engine
from src.pet.stats import calc_stats


class DungeonMixin:

    @command("副本", "dungeon")
    def dungeon(self, user_id: str, user_name: str = "", arg: str = "", group_id: str = "") -> str | list[str]:
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"

        parts = arg.split()

        if not parts or not parts[0]:
            return self._dungeon_menu(user_id, pet)

        if parts[0].isdigit() and len(parts) == 1:
            ch = int(parts[0])
            return self._dungeon_chapter(user_id, pet, ch)

        if len(parts) >= 2 and parts[0].isdigit():
            ch = int(parts[0])
            stage_str = parts[1].lower()
            return self._dungeon_fight(user_id, pet, ch, stage_str)

        return self._dungeon_menu(user_id, pet)

    def _dungeon_menu(self, user_id: str, pet) -> str:
        first_set = self.dm.get_dungeon_first_set(user_id)

        lines = [f"🏰 副本总览（你的等级：Lv.{pet.level}）", ""]

        for ch, info in CHAPTERS.items():
            unlocked = is_chapter_unlocked(first_set, ch)
            if not unlocked:
                lines.append(f"⚪ {info['name']} (Lv.{info['level_range'][0]}-{info['level_range'][1]})       — 未解锁")
                continue

            all_stages = ["1", "2", "3", "boss"]
            if ch == 7:
                all_stages.append("hide")

            all_cleared = all(f"{ch}-{s}" in first_set for s in all_stages)
            if all_cleared:
                lines.append(f"🟢 {info['name']} (Lv.{info['level_range'][0]}-{info['level_range'][1]})       — 已首通")
            else:
                counts = []
                for s in all_stages:
                    count = self.dm.get_dungeon_count(user_id, ch, s)
                    limit = STAGES[s]["daily_limit"]
                    stage_name = STAGES[s]["name"][:2]
                    counts.append(f"{stage_name} {count}/{limit}")
                lines.append(f"🟡 {info['name']} (Lv.{info['level_range'][0]}-{info['level_range'][1]})       — {' '.join(counts)}")

        lines.append("")
        lines.append("📌 输入「/副本 4」查看 4 章关卡")
        lines.append("📌 输入「/副本 4 1」挑战 4-1")

        return "\n".join(lines)

    def _dungeon_chapter(self, user_id: str, pet, ch: int) -> str:
        if ch not in CHAPTERS:
            return "❌ 章节不存在，有效范围 1~7"

        first_set = self.dm.get_dungeon_first_set(user_id)
        if not is_chapter_unlocked(first_set, ch):
            return f"❌ 第 {ch} 章尚未解锁，请先通关第 {ch-1} 章全部关卡"

        info = CHAPTERS[ch]
        lines = [f"🏰 第 {ch} 章：{info['name']} (Lv.{info['level_range'][0]}-{info['level_range'][1]})", ""]

        all_stages = ["1", "2", "3", "boss"]
        if ch == 7:
            all_stages.append("hide")

        for s in all_stages:
            stage_info = STAGES[s]
            count = self.dm.get_dungeon_count(user_id, ch, s)
            limit = stage_info["daily_limit"]
            first = f"{ch}-{s}" in first_set
            first_mark = " ✅" if first else ""
            lines.append(f"  {ch}-{s} {stage_info['name']}    {count}/{limit} 次{first_mark}")

        lines.append("")
        lines.append(f"📌 输入「/副本 {ch} 1」挑战杂兵关")
        lines.append(f"📌 输入「/副本 {ch} boss」挑战 BOSS")

        return "\n".join(lines)

    def _dungeon_fight(self, user_id: str, pet, ch: int, stage_str: str) -> str | list[str]:
        if ch not in CHAPTERS:
            return "❌ 章节不存在，有效范围 1~7"

        stage_id = get_stage_id(stage_str)
        if not stage_id:
            return "❌ 关卡不存在，有效值：1/2/3/boss/hide"

        first_set = self.dm.get_dungeon_first_set(user_id)
        if not is_chapter_unlocked(first_set, ch):
            return f"❌ 第 {ch} 章尚未解锁"

        if stage_id == "hide" and ch != 7:
            return "❌ 隐藏关卡仅在第 7 章可用"

        if stage_id == "hide" and f"{ch}-boss" not in first_set:
            return "❌ 隐藏关卡需要先通关 BOSS 关"

        stage_info = STAGES[stage_id]
        count = self.dm.get_dungeon_count(user_id, ch, stage_id)
        if count >= stage_info["daily_limit"]:
            return f"❌ 该关卡今日次数已用完（{count}/{stage_info['daily_limit']}），明日 0:00 重置"

        if pet.training:
            return "❌ 训练中无法挑战副本"

        if not self.dm.use_energy(user_id, ENERGY_COST):
            energy = self.dm.get_energy(user_id)
            return f"❌ 行动力不足（当前 {energy['value']}/{ENERGY_COST}），回复时间约 {ENERGY_COST * 3} 分钟"

        ch_info = CHAPTERS[ch]
        level = random.randint(ch_info["level_range"][0], ch_info["level_range"][1])

        species_ids = list(range(1, 26))
        monster_species = f"P{random.choice(species_ids):03d}"
        monster_stage = min(2, ch // 3)
        monster_ivs = {"iv_hp": 15, "iv_atk": 15, "iv_def": 15, "iv_spd": 15, "iv_crit": 15, "iv_eva": 15}
        monster_stats = calc_stats(monster_species, monster_stage, level, monster_ivs)

        from src.pet.config import PET_SPECIES
        monster_name = PET_SPECIES[monster_species]["names"][monster_stage]

        monster_dict = {
            "owner_id": "monster",
            "name": monster_name,
            "species_id": monster_species,
            "evolution_stage": monster_stage,
            "battle_type": PET_SPECIES[monster_species]["battle_type"],
            "level": level,
            **monster_stats,
        }

        enemy_passives = get_enemy_passives(ch, stage_id)
        if enemy_passives:
            monster_dict.update(enemy_passives)

        pet_dict = pet.to_dict()
        passive_slots = self.dm.get_passive_slots(user_id)
        if passive_slots:
            pet_dict["passive_slots"] = passive_slots
            pet_dict["passive_levels"] = {
                sid: self.dm.get_passive_level(user_id, sid)
                for sid in passive_slots.values()
            }

        start_msg = f"⚔️ 挑战 {ch_info['name']} {ch}-{stage_id} {stage_info['name']}\n对手：{monster_name} Lv.{level}\n战斗开始..."

        result = battle_engine.run(pet_dict, monster_dict)

        if result.winner == user_id:
            is_first = f"{ch}-{stage_id}" not in first_set
            exp_mult = stage_info["exp_mult"] * (stage_info["first_mult"] if is_first else 1)
            exp = level * exp_mult

            mat = STAGE_MATERIALS[stage_id]
            stone = random.randint(mat["stone"][0], mat["stone"][1])
            rare = random.randint(mat["rare"][0], mat["rare"][1])
            gold = level * mat["gold_mult"]

            self.dm.add_exp(user_id, exp)
            self.dm.add_gold(user_id, gold)
            if stone > 0:
                self.dm.add_item(user_id, "stone", stone)
            if rare > 0:
                self.dm.add_item(user_id, "rare_shard", rare)

            self.dm.incr_dungeon_count(user_id, ch, stage_id)
            if is_first:
                self.dm.mark_dungeon_first(user_id, ch, stage_id)

            passive_book = None
            if ch in CHAPTER_DROP_POOL:
                pool = CHAPTER_DROP_POOL[ch]
                base_rate = STAGE_DROP_RATE.get(stage_id, 0.08)
                if random.random() < base_rate:
                    passive_book = random.choice(pool)
                    self.dm.add_passive_bag(user_id, passive_book, 1)
                if is_first:
                    bonus_rate = STAGE_FIRST_BONUS_RATE.get(stage_id, 0.10)
                    if random.random() < bonus_rate:
                        bonus_book = random.choice(pool)
                        self.dm.add_passive_bag(user_id, bonus_book, 1)
                        if passive_book is None:
                            passive_book = bonus_book

            result_lines = [
                f"🏆 胜利！",
                f"   ⭐ 经验 +{exp:,}" + (" (首通加成)" if is_first else ""),
                f"   💰 金币 +{gold:,}",
            ]
            if stone > 0:
                result_lines.append(f"   💎 进化石 ×{stone}")
            if rare > 0:
                result_lines.append(f"   ✨ 稀有碎片 ×{rare}")
            if passive_book:
                from src.game.passive_config import PASSIVE_SKILLS
                book_info = PASSIVE_SKILLS.get(passive_book, {})
                result_lines.append(f"   📖 {book_info.get('name', passive_book)} ×1")

            all_stages = ["1", "2", "3", "boss"]
            if ch == 7:
                all_stages.append("hide")
            updated_first = self.dm.get_dungeon_first_set(user_id)
            if all(f"{ch}-{s}" in updated_first for s in all_stages):
                reward = CHAPTER_FIRST_REWARDS[ch]
                self.dm.add_item(user_id, "stone", reward["stone"])
                if reward["rare"] > 0:
                    self.dm.add_item(user_id, "rare_shard", reward["rare"])
                if reward["legend"] > 0:
                    self.dm.add_item(user_id, "legend_shard", reward["legend"])
                self.dm.add_gold(user_id, reward["gold"])
                result_lines.append(f"\n🎊 第 {ch} 章首通奖励！")
                result_lines.append(f"   💎 进化石 ×{reward['stone']}")
                if reward["rare"] > 0:
                    result_lines.append(f"   ✨ 稀有碎片 ×{reward['rare']}")
                if reward["legend"] > 0:
                    result_lines.append(f"   🌟 传说碎片 ×{reward['legend']}")
                result_lines.append(f"   💰 金币 +{reward['gold']:,}")

            return [start_msg, "\n".join(result_lines)]
        else:
            return [start_msg, "💀 战败！提升等级和属性后再来挑战吧~"]

    @command("副本重置", "dungeonreset")
    def dungeon_reset(self, user_id: str, user_name: str = "", arg: str = "", group_id: str = "") -> str:
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"

        if not arg or not arg.isdigit():
            return "❌ 请指定章节号！例如：/副本重置 3"

        ch = int(arg)
        if ch not in CHAPTERS:
            return "❌ 章节不存在，有效范围 1~7"

        if self.dm.is_dungeon_reset_today(user_id, ch):
            return "❌ 该章节今日已重置过，明日 0:00 后可再次重置"

        if not self.dm.use_diamond(user_id, RESET_COST):
            current = self.dm.get_diamond(user_id)
            return f"❌ 钻石不足（当前 {current}/{RESET_COST}），每日签到可获得钻石"

        self.dm.reset_dungeon_counts(user_id, ch)
        self.dm.mark_dungeon_reset(user_id, ch)

        return f"✅ 第 {ch} 章今日次数已重置！花费 {RESET_COST} 钻石"
