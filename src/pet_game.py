"""
pet_game.py - Battle pet game logic.

Commands: adopt, stats_detail, abandon, rename, top, help,
          battle_pvp, evolve, train, rest
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from pathlib import Path

from src.data_manager import DataManager, Pet, data_manager

logger = logging.getLogger("QQBot")
from src.pet_config import PET_SPECIES, Skill, SkillEffect, get_pet_image_url, get_pet_image_local_path
from src.pet_stats import (generate_ivs, generate_quality, QUALITY_INDEX_TO_LABEL,
                           calc_stats, calc_training_exp, calc_cp,
                           format_battle_stats, format_iv_detail, quality_label)
from src.battle import battle_engine, format_battle_report
from src.config import config


class PetGame:
    """Battle pet game."""

    def __init__(self, dm: DataManager, bot=None):
        self.dm = dm
        self.bot = bot

    # ── Screenshot helper ──

    async def _generate_screenshot(self, pet: Pet,
                                    old_pet: Pet = None) -> str | None:
        """生成截图文件，受信号量并发限制。

        非进化场景共用同一张截图（scene=""），进化场景使用 scene="evolve" 以包含属性变化预览。

        Args:
            pet: 宠物数据
            old_pet: 进化前旧宠物（仅 evolve 使用）

        Returns:
            截图文件名（如 uuid.png），截图不可用时返回 None
        """
        import asyncio
        import base64
        from src.image_gen import render_pet_html, html_to_image
        from src.image_lifecycle import generate_screenshot_uuid, schedule_deletion

        scene = "evolve" if old_pet is not None else ""

        callback_domain = config["webhook"].get("callback_domain", "")
        pig_source = config["image"].get("pig_source", "cropped_pigs1")
        image_url = get_pet_image_url(pet.species_id, pet.evolution_stage,
                                      pig_source, callback_domain)

        base_dir = config["image"].get("pet_image_base_dir", "")
        if base_dir and not Path(base_dir).is_absolute():
            base_dir = str(Path(__file__).parent.parent / base_dir)
        local_image_path = get_pet_image_local_path(
            pet.species_id, pet.evolution_stage, base_dir) if base_dir else ""

        screenshots_dir = Path(config["image"].get("screenshots_dir", "data/images/screenshots"))
        if not screenshots_dir.is_absolute():
            screenshots_dir = Path(__file__).parent.parent / screenshots_dir
        screenshots_dir.mkdir(parents=True, exist_ok=True)

        user_id = pet.owner_id
        screenshot_uuid = generate_screenshot_uuid(user_id, pet.last_update, scene)
        filename = f"{screenshot_uuid}.png"
        output_path = screenshots_dir / filename

        logger.info(f"[截图] 生成请求: user={user_id}, scene='{scene}', "
                   f"uuid={screenshot_uuid}, last_update={pet.last_update}")

        recorded_uuid = self.dm.get_screenshot_uuid(user_id, scene)
        logger.info(f"[截图] 缓存检查: recorded_uuid={recorded_uuid}, "
                   f"current_uuid={screenshot_uuid}, file_exists={output_path.exists()}")
        
        if recorded_uuid == screenshot_uuid and output_path.exists():
            logger.info(f"[截图] 缓存命中: 返回 {filename}")
            return filename

        if recorded_uuid:
            old_path = screenshots_dir / f"{recorded_uuid}.png"
            if old_path.exists():
                logger.info(f"[截图] 延迟删除旧截图: {recorded_uuid}.png")
                schedule_deletion(old_path, delay_seconds=60)

        if not (self.bot and hasattr(self.bot, '_playwright_browser')
                and self.bot._playwright_browser):
            logger.warning("[截图] Playwright 不可用，返回 None")
            return None

        base64_image = ""
        if local_image_path and Path(local_image_path).exists():
            img_bytes = Path(local_image_path).read_bytes()
            b64 = base64.b64encode(img_bytes).decode("ascii")
            base64_image = f"data:image/png;base64,{b64}"
            logger.info(f"[截图] 使用 base64 内联图片: {local_image_path}")

        html = render_pet_html(pet, image_url, local_image_path,
                               old_pet=old_pet, base64_image=base64_image)

        browser = self.bot._playwright_browser
        page = None
        if hasattr(self.bot, '_page_pool') and self.bot._page_pool:
            try:
                page = self.bot._page_pool.pop()
                logger.info(f"[截图] 从预热池获取页面，剩余 {len(self.bot._page_pool)} 个")
            except IndexError:
                page = None
                logger.info("[截图] 预热池为空，将新建页面")

        sem = getattr(self.bot, '_screenshot_semaphore', None)
        if sem:
            await sem.acquire()
            logger.info("[截图] 获取信号量成功")
        try:
            await html_to_image(browser, html, output_path, page=page)
            logger.info(f"[截图] 截图生成成功: {filename}")
        finally:
            if sem:
                sem.release()
            if page is not None:
                self.bot._page_pool.append(page)

        dm = self.dm
        async def _record_uuid():
            try:
                dm.set_screenshot_uuid(user_id, screenshot_uuid, scene)
                logger.info(f"[截图] UUID 记录成功: user={user_id}, scene='{scene}', uuid={screenshot_uuid}")
            except Exception as e:
                logger.error(f"[截图] UUID 记录失败: {e}")
        asyncio.create_task(_record_uuid())

        return filename

    async def _pre_generate_screenshot(self, pet: Pet,
                                        old_pet: Pet = None) -> None:
        """后台预生成截图（fire-and-forget），加速后续查看。"""
        try:
            await self._generate_screenshot(pet, old_pet)
        except Exception as e:
            logger.debug(f"预生成截图失败: {e}")

    async def _build_pet_message(self, pet: Pet,
                                  title: str, tip: str,
                                  rows: list[list[dict]],
                                  old_pet: Pet = None) -> dict:
        """生成截图并构建 Markdown+按钮 消息dict。

        非进化场景共用同一张截图，进化场景额外包含属性变化预览。

        Args:
            pet: 宠物数据
            title: Markdown模板标题
            tip: Markdown模板tip文本
            rows: 按钮行列表
            old_pet: 进化前的旧宠物（仅 evolve 使用，显示属性变化预览）

        Returns:
            完整消息dict（含markdown段和keyboard段）
        """
        from src.msg_templates import build_markdown_with_buttons

        callback_domain = config["webhook"].get("callback_domain", "")
        pig_source = config["image"].get("pig_source", "cropped_pigs1")
        image_url = get_pet_image_url(pet.species_id, pet.evolution_stage,
                                      pig_source, callback_domain)

        filename = await self._generate_screenshot(pet, old_pet)

        if filename:
            screenshot_url = f"{callback_domain}/static/images/screenshots/{filename}"
            logger.info(f"[消息] 使用截图 URL: {screenshot_url}")
        else:
            screenshot_url = image_url
            logger.warning(f"[消息] 截图失败，回退到原始图片 URL: {screenshot_url}")

        msg = build_markdown_with_buttons(title, screenshot_url, tip, rows)
        logger.info(f"[消息] 构建完成: title='{title}', image_url='{screenshot_url}'")
        return msg

    # ── Adopt ──

    async def adopt(self, user_id: str, user_name: str, _arg: str = "") -> str | dict:
        """领养随机宠物 P001~P026，生成截图+按钮消息。首次领养自动分配游戏用户ID。"""
        if self.dm.has_pet(user_id):
            pet = self.dm.get_pet(user_id)
            return (f"❌ 你已经有一只 {pet.species_name}「{pet.name}」了！\n"
                    f"使用「/遗弃」先放生当前宠物才能领养新的哦~")

        game_uid = self.dm.get_user_game_uid(user_id)
        if game_uid == 0:
            game_uid = self.dm.assign_game_uid(user_id)

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
        pet.game_uid = game_uid
        self.dm.update_pet(user_id, game_uid=game_uid)
        self.dm.update_leaderboard(pet)

        type_names = {"attack": "攻击型", "defense": "防御型", "speed": "速度型"}
        btype_cn = type_names.get(battle_type, battle_type)

        title = f"🎉 {pet_name} 成为了你的伙伴！"
        cp = calc_cp(pet)
        tip = (f"品质：{q_rating}({quality_label(q_rating)})  |  类型：{btype_cn}  |  "
               f"游戏ID：{game_uid}  |  战力：{cp}  |  可使用「/改名」给宠物取一个喜欢的名字哦~")
        rows = [
            [{"text": "🧬 属性详情", "command": "/属性"},
             {"text": "⚔️ 战斗", "command": "/战斗"}],
            [{"text": "💪 训练", "command": "/训练"}],
        ]
        msg = await self._build_pet_message(pet, title, tip, rows)
        asyncio.create_task(self._pre_generate_screenshot(pet))
        return msg

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

        title = f"{pet.species_name}({pet.game_uid}) 属性详情"
        cp = calc_cp(pet)
        tip = f"品质：{pet.quality}  |  战力：{cp}  |  IV总和:{pet.iv_sum}/186"
        rows = [
            [{"text": "🔮 进化", "command": "/进化"},
             {"text": "💪 训练", "command": "/训练"}],
            [{"text": "⚔️ 战斗", "command": "/战斗"}],
        ]
        return await self._build_pet_message(pet, title, tip, rows)

    # ── Abandon ──

    def abandon(self, user_id: str) -> str:
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"
        name = pet.name
        self.dm.delete_pet(user_id)
        return (f"😢 你含泪放生了 {pet.species_name}「{name}」...\n"
                f"使用「/领养」可以重新领养一只新的伙伴。")

    # ── Register ──

    def register(self, user_id: str) -> str:
        """为已有宠物但无游戏用户ID的旧用户分配游戏用户ID。"""
        pet = self.dm.get_pet(user_id)
        if pet is None:
            return "❌ 你还没有宠物！使用「/领养」来领养一只猪吧~"

        existing_uid = self.dm.get_user_game_uid(user_id)
        if existing_uid > 0:
            return f"✅ 你已经注册过了！你的游戏用户ID是：{existing_uid}"

        game_uid = self.dm.assign_game_uid(user_id)
        self.dm.update_pet(user_id, game_uid=game_uid)
        return f"✅ 注册成功！你的游戏用户ID是：{game_uid}\n其他人可以通过「/战斗 {game_uid}」来挑战你！"

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
        msg = await self._build_pet_message(result, title, tip, rows,
                                            old_pet=old_pet)
        asyncio.create_task(self._pre_generate_screenshot(result))
        return msg

    # ── Training ──

    async def start_training(self, user_id: str) -> str | dict:
        """开始训练，返回文本+按钮消息。"""
        from datetime import datetime, timedelta
        from src.msg_templates import build_button_list_msg

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
        rest_time = datetime.now() + timedelta(minutes=10)
        time_str = rest_time.strftime("%H:%M")
        content = f"💪 开始训练！\n🕓  预计获得{exp_10min}经验(10分钟)。\n⚠  训练时间越长经验越多\n🗨  休息指令可用时间：{time_str}"
        rows = [
            [{"text": "🛌 结束训练", "command": "/休息"}],
            [{"text": "🧬 属性详情", "command": "/属性"}],
        ]
        return build_button_list_msg(content, rows)

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

        title = f"🛌 {result.species_name}({result.game_uid}) 训练结束"
        # tip: {原有等级}->{现有等级}|{战力}
        old_level = pet.level
        new_level = result.level
        cp = calc_cp(result)
        tip = f"训练{minutes}分钟 | Lv.{old_level}->Lv.{new_level}  |  战力：{cp}"
        rows = [
            [{"text": "🧬 属性详情", "command": "/属性"},
             {"text": "💪 再训练", "command": "/训练"}],
        ]
        msg = await self._build_pet_message(result, title, tip, rows)
        asyncio.create_task(self._pre_generate_screenshot(result))
        return msg

    # ── PvP Battle ──

    async def battle_pvp(self, challenger_id: str, target_id: str | None) -> str | list[str]:
        """PvP battle between two users.

        返回 list[str, str] 表示两次消息（开始提示 + 战斗结果），
        返回 str 表示单次错误消息。
        """
        if not target_id:
            return "❌ 请提供对方的游戏用户ID！\n例如：/战斗 123"

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

        start_msg = f"⚔️ {pet_a.species_name}「{pet_a.name}」 VS {pet_b.species_name}「{pet_b.name}」\n战斗开始，结果生成中..."

        result = battle_engine.run(pet_a.to_dict(), pet_b.to_dict())

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

        result_msg = format_battle_report(result)

        return [start_msg, result_msg]

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
            "  /战斗 <游戏ID> - 进行PK(输入对方游戏用户ID)\n"
            "  /进化        - 进化宠物(Lv29/Lv59)\n"
            "  /训练        - 开始训练(10分钟以上)\n"
            "  /休息        - 结束训练领取经验\n\n"
            "🏆 /排行 - 查看排行榜\n\n"
            "💡 提示：\n\t训练是获取经验的主要方式\n\t战斗可以获得额外经验奖励！"
        )


# Global instance
game = PetGame(data_manager)
