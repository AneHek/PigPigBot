"""
pet_game.py - Battle pet game logic.

Commands: adopt, stats_detail, abandon, rename, top, help,
          battle_pvp, evolve, train, rest
"""
from __future__ import annotations

import logging
import random
import time
from pathlib import Path

from src.data_manager import DataManager, Pet, data_manager

logger = logging.getLogger("QQBot")
from src.pet_config import PET_SPECIES, Skill, SkillEffect, get_pet_image_url, get_pet_image_local_path
from src.pet_stats import (generate_ivs, generate_quality, QUALITY_INDEX_TO_LABEL,
                           calc_stats, calc_training_exp,
                           format_battle_stats, format_iv_detail, quality_label)
from src.battle import battle_engine, format_battle_report
from src.config import config


class PetGame:
    """Battle pet game."""

    def __init__(self, dm: DataManager, bot=None):
        self.dm = dm
        self.bot = bot

    # ── Screenshot helper ──

    async def _build_pet_message(self, pet: Pet, scene: str,
                                  title: str, tip: str,
                                  rows: list[list[dict]],
                                  old_pet: Pet = None) -> dict:
        """生成截图并构建 Markdown+按钮 消息dict。

        基于 pet.last_update 生成确定性 UUID 作为截图名，数据未变则复用已有截图。

        Args:
            pet: 宠物数据
            scene: 场景 (adopt/stats/evolve/training)
            title: Markdown模板标题
            tip: Markdown模板tip文本
            rows: 按钮行列表
            old_pet: 进化前的旧宠物（仅 evolve 使用，显示属性变化预览）

        Returns:
            完整消息dict（含markdown段和keyboard段）
        """
        from src.image_gen import render_pet_html, html_to_image
        from src.image_lifecycle import generate_screenshot_uuid
        from src.msg_templates import build_markdown_with_buttons

        callback_domain = config["webhook"].get("callback_domain", "")
        pig_source = config["image"].get("pig_source", "cropped_pigs1")
        image_url = get_pet_image_url(pet.species_id, pet.evolution_stage,
                                      pig_source, callback_domain)

        # 本地绝对路径（用于Playwright渲染宠物图片）
        base_dir = config["image"].get("pet_image_base_dir", "")
        if base_dir and not Path(base_dir).is_absolute():
            base_dir = str(Path(__file__).parent.parent / base_dir)
        local_image_path = get_pet_image_local_path(
            pet.species_id, pet.evolution_stage, base_dir) if base_dir else ""

        # 截图目录
        screenshots_dir = Path(config["image"].get("screenshots_dir", "data/images/screenshots"))
        if not screenshots_dir.is_absolute():
            screenshots_dir = Path(__file__).parent.parent / screenshots_dir
        screenshots_dir.mkdir(parents=True, exist_ok=True)

        user_id = pet.owner_id

        # 基于 last_update 生成确定性 UUID，数据不变则 UUID 不变
        screenshot_uuid = generate_screenshot_uuid(user_id, pet.last_update)
        filename = f"{screenshot_uuid}.png"
        output_path = screenshots_dir / filename

        # 检查是否与记录一致且文件存在 → 直接复用
        recorded_uuid = self.dm.get_screenshot_uuid(user_id)
        if recorded_uuid == screenshot_uuid and output_path.exists():
            screenshot_url = f"{callback_domain}/static/images/screenshots/{filename}"
            return build_markdown_with_buttons(title, screenshot_url, tip, rows)

        # ── 需要重新生成：先删除旧截图 ──
        if recorded_uuid:
            old_path = screenshots_dir / f"{recorded_uuid}.png"
            if old_path.exists():
                old_path.unlink()
                logger.debug(f"已删除旧截图: {old_path.name}")

        # ── 生成新截图 ──
        if self.bot and hasattr(self.bot, '_playwright_browser') and self.bot._playwright_browser:
            html = render_pet_html(pet, scene, image_url, local_image_path,
                                   old_pet=old_pet)
            await html_to_image(self.bot._playwright_browser, html, output_path)
            self.dm.set_screenshot_uuid(user_id, screenshot_uuid)
            screenshot_url = f"{callback_domain}/static/images/screenshots/{filename}"
        else:
            # 截图不可用时用原图代替
            screenshot_url = image_url

        return build_markdown_with_buttons(title, screenshot_url, tip, rows)

    # ── Adopt ──

    async def adopt(self, user_id: str, user_name: str, _arg: str = "") -> str | dict:
        """领养随机宠物 P001~P026，生成截图+按钮消息。"""
        if self.dm.has_pet(user_id):
            pet = self.dm.get_pet(user_id)
            return (f"❌ 你已经有一只 {pet.species_name}「{pet.name}」了！\n"
                    f"使用「/遗弃」先放生当前宠物才能领养新的哦~")

        species_num = random.randint(1, 26)
        species_id = f"P{species_num:03d}"
        species = PET_SPECIES[species_id]
        pet_name = species["names"][0]

        quality_index = generate_quality()
        ivs = generate_ivs(quality_index)
        q_rating = QUALITY_INDEX_TO_LABEL[quality_index]

        stats = calc_stats(species_id, 0, 1, ivs)
        battle_type = species["battle_type"]

        pet = self.dm.create_pet(user_id, user_name, species_id, pet_name,
                                 battle_type, ivs, stats)
        self.dm.update_leaderboard(pet)

        type_names = {"attack": "攻击型", "defense": "防御型", "speed": "速度型"}
        btype_cn = type_names.get(battle_type, battle_type)

        title = f"🎉 {pet_name} 成为了你的伙伴！"
        tip = (f"品质：{q_rating}({quality_label(q_rating)})  |  类型：{btype_cn}  |  "
               f"可使用「/改名」给宠物取一个喜欢的名字哦~")
        rows = [
            [{"text": "🧬 属性详情", "command": "/属性"},
             {"text": "⚔️ 战斗", "command": "/战斗"}],
            [{"text": "💪 训练", "command": "/训练"}],
        ]
        return await self._build_pet_message(pet, "adopt", title, tip, rows)

    # ── Stats Detail ──

    async def stats_detail(self, user_id: str) -> str | dict:
        """查看属性详情含IV，生成截图+按钮消息。"""
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"

        self.dm.update_leaderboard(pet)

        # 进化门槛警告
        gate_info = ""
        if pet.evolution_stage == 0 and pet.level >= 29:
            gate_info = " | ⚠️ 已达29级上限，需要进化"
        elif pet.evolution_stage == 1 and pet.level >= 59:
            gate_info = " | ⚠️ 已达59级上限，需要进化"

        title = f"{pet.species_name} · Lv.{pet.level} 属性详情"
        tip = (f"{pet.name} | 品质:{pet.quality}({quality_label(pet.quality)})"
               f" | IV总和:{pet.iv_sum}/186 | EXP:{pet.exp}/{pet.max_exp}{gate_info}")
        rows = [
            [{"text": "🔮 进化", "command": "/进化"},
             {"text": "💪 训练", "command": "/训练"}],
            [{"text": "⚔️ 战斗", "command": "/战斗"}],
        ]
        return await self._build_pet_message(pet, "stats", title, tip, rows)

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

    async def evolve(self, user_id: str) -> str | dict:
        """进化宠物，生成截图+按钮消息。"""
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"

        if pet.evolution_stage >= 2:
            return "❌ 已经是三阶形态，无法再进化了！"

        gate = 29 if pet.evolution_stage == 0 else 59
        if pet.level < gate:
            return f"❌ 需要达到 Lv.{gate} 才能进化！（当前 Lv.{pet.level}）"

        old_name = pet.species_name
        # 保存进化前数据用于属性变化预览
        import copy
        old_pet = copy.deepcopy(pet)
        result = self.dm.evolve_pet(user_id)
        if result is None:
            return "❌ 进化失败，请稍后再试。"

        new_name = result.species_name
        self.dm.update_leaderboard(result)

        stage_names = ["一阶", "二阶", "三阶"]
        title = f"🎊 {old_name} → {new_name}"
        tip = f"新形态：{stage_names[result.evolution_stage]}进化 | Lv.{result.level}"
        rows = [
            [{"text": "🧬 属性详情", "command": "/属性"},
             {"text": "💪 训练", "command": "/训练"}],
        ]
        return await self._build_pet_message(result, "evolve", title, tip, rows,
                                             old_pet=old_pet)

    # ── Training ──

    async def start_training(self, user_id: str) -> str | dict:
        """开始训练，生成截图+按钮消息（展示当前状态）。"""
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
        title = f"💪 {pet.species_name} 开始训练"
        tip = f"最少10分钟 | 预计{exp_10min}经验 | 训练越长经验越多"
        rows = [
            [{"text": "🛌 结束训练", "command": "/休息"}],
            [{"text": "🧬 属性详情", "command": "/属性"}],
        ]
        return await self._build_pet_message(result, "training", title, tip, rows)

    async def end_training(self, user_id: str) -> str | dict:
        """结束训练，生成截图+按钮消息。"""
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

        level_info = ""
        if result.level > pet.level:
            level_info = f" | 🎉 Lv.{pet.level}→Lv.{result.level}"

        gate_info = ""
        if result.evolution_stage == 0 and result.level >= 29:
            gate_info = " ⚠️ 可进化"
        elif result.evolution_stage == 1 and result.level >= 59:
            gate_info = " ⚠️ 可进化"

        title = f"🛌 {result.species_name} 训练结束"
        tip = f"训练{minutes}分钟 | 获得{exp_gained}经验{level_info}{gate_info}"
        rows = [
            [{"text": "🧬 属性详情", "command": "/属性"},
             {"text": "💪 再训练", "command": "/训练"}],
        ]
        return await self._build_pet_message(result, "training", title, tip, rows)

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
            "━━━━━━━━━━━━━\n"
            "📋 基础命令：\n"
            "  /领养        - 随机领养一只猪猪宠物\n"
            "  /属性        - 查看宠物属性详情(含IV)\n"
            "  /遗弃        - 遗弃当前宠物\n"
            "  /改名 <名>   - 给宠物改名\n"
            "  /帮助        - 显示本帮助\n\n"
            "⚔️ 战斗与成长：\n"
            "  /战斗 @某人  - 进行PK\n"
            "  /进化        - 进化宠物(Lv29/Lv59)\n"
            "  /训练        - 开始训练(10分钟以上)\n"
            "  /休息        - 结束训练领取经验\n\n"
            "🏆 /排行 - 查看排行榜\n\n"
            "💡 提示：\n\t训练是获取经验的主要方式\n\t战斗可以获得额外经验奖励！"
        )


# Global instance
game = PetGame(data_manager)
