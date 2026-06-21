import asyncio
import logging
from pathlib import Path

from src.data.models import Pet
from src.config import config

logger = logging.getLogger("QQBot")


class PetGameBase:

    def __init__(self, dm, bot=None):
        self.dm = dm
        self.bot = bot

    def _build_battle_dict(self, user_id: str, pet: Pet) -> dict:
        d = pet.to_dict()
        modifiers = []
        modifiers.extend(self._collect_passive_modifiers(user_id))
        if modifiers:
            d["modifiers"] = modifiers
        return d

    def _collect_passive_modifiers(self, user_id: str) -> list[dict]:
        from src.game.passive_config import PASSIVE_SKILLS
        modifiers = []
        slots = self.dm.get_passive_slots(user_id)
        for slot, skill_id in slots.items():
            if skill_id not in PASSIVE_SKILLS:
                continue
            info = PASSIVE_SKILLS[skill_id]
            level = self.dm.get_passive_level(user_id, skill_id)
            if level <= 0 or level > len(info["pct_per_level"]):
                continue
            pct = info["pct_per_level"][level - 1]
            stat = info["stat"]
            if stat in ("crit_dmg", "lifesteal"):
                modifiers.append({"stat": stat, "value": pct / 100, "type": "flat"})
            else:
                modifiers.append({"stat": stat, "value": pct, "type": "pct"})
        return modifiers

    async def _generate_screenshot(self, pet: Pet,
                                    old_pet: Pet = None) -> str | None:
        import base64
        from src.screenshot.render import render_pet_html, html_to_image
        from src.screenshot.lifecycle import generate_screenshot_uuid, schedule_deletion

        scene = "evolve" if old_pet is not None else ""

        callback_domain = config["webhook"].get("callback_domain", "")
        pig_source = config["image"].get("pig_source", "cropped_pigs1")
        from src.pet.config import get_pet_image_url, get_pet_image_local_path
        image_url = get_pet_image_url(pet.species_id, pet.evolution_stage,
                                      pig_source, callback_domain)

        base_dir = config["image"].get("pet_image_base_dir", "")
        if base_dir and not Path(base_dir).is_absolute():
            base_dir = str(Path(__file__).parent.parent.parent / base_dir)
        local_image_path = get_pet_image_local_path(
            pet.species_id, pet.evolution_stage, base_dir) if base_dir else ""

        screenshots_dir = Path(config["image"].get("screenshots_dir", "data/images/screenshots"))
        if not screenshots_dir.is_absolute():
            screenshots_dir = Path(__file__).parent.parent.parent / screenshots_dir
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
        try:
            await self._generate_screenshot(pet, old_pet)
        except Exception as e:
            logger.debug(f"预生成截图失败: {e}")

    async def _build_pet_message(self, pet: Pet,
                                  title: str, tip: str,
                                  rows: list[list[dict]],
                                  old_pet: Pet = None) -> dict:
        from src.msg_templates import build_markdown_with_buttons
        from src.pet.config import get_pet_image_url

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
