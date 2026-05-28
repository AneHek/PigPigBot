"""
test_screenshot_flow.py — 截图优化流程测试覆盖。

覆盖：
- UUID 场景隔离（generate_screenshot_uuid 含 scene 参数）
- html_to_image 页面复用（page 参数传入/不传入）
- _generate_screenshot 缓存命中、信号量、页面池
- _pre_generate_screenshot 后台预生成
- render_pet_html base64_image 参数
"""
import sys
import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

sys.modules['redis'] = MagicMock()
sys.modules['playwright'] = MagicMock()
sys.modules['playwright.async_api'] = MagicMock()


class TestUUIDSceneIsolation(unittest.TestCase):
    """generate_screenshot_uuid 含 scene 参数的确定性 UUID 生成。"""

    def test_same_inputs_same_uuid(self):
        """相同 user_id + last_update + scene → 相同 UUID"""
        from src.image_lifecycle import generate_screenshot_uuid
        u1 = generate_screenshot_uuid("user1", 1000.0, "adopt")
        u2 = generate_screenshot_uuid("user1", 1000.0, "adopt")
        self.assertEqual(u1, u2)

    def test_different_scene_different_uuid(self):
        """相同 user_id + last_update，不同 scene → 不同 UUID"""
        from src.image_lifecycle import generate_screenshot_uuid
        u_adopt = generate_screenshot_uuid("user1", 1000.0, "adopt")
        u_stats = generate_screenshot_uuid("user1", 1000.0, "stats")
        u_evolve = generate_screenshot_uuid("user1", 1000.0, "evolve")
        u_training = generate_screenshot_uuid("user1", 1000.0, "training")
        uuids = {u_adopt, u_stats, u_evolve, u_training}
        self.assertEqual(len(uuids), 4, "4 个不同 scene 应产生 4 个不同 UUID")

    def test_different_last_update_different_uuid(self):
        """不同 last_update → 不同 UUID"""
        from src.image_lifecycle import generate_screenshot_uuid
        u1 = generate_screenshot_uuid("user1", 1000.0, "stats")
        u2 = generate_screenshot_uuid("user1", 2000.0, "stats")
        self.assertNotEqual(u1, u2)

    def test_empty_scene_backward_compatible(self):
        """scene 为空字符串时仍可正常工作"""
        from src.image_lifecycle import generate_screenshot_uuid
        u = generate_screenshot_uuid("user1", 1000.0, "")
        self.assertIsNotNone(u)
        self.assertGreater(len(u), 0)

    def test_uuid_format(self):
        """UUID 格式为 xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"""
        from src.image_lifecycle import generate_screenshot_uuid
        u = generate_screenshot_uuid("user1", 1000.0, "adopt")
        parts = u.split("-")
        self.assertEqual(len(parts), 5)


class TestRenderPetHtmlBase64(unittest.TestCase):
    """render_pet_html 的 base64_image 参数。"""

    def _make_pet(self):
        from src.data_manager import Pet
        return Pet(
            owner_id="test", owner_name="test",
            name="测试猪", species_id="P001",
            evolution_stage=0, battle_type="attack", level=10, exp=500,
            iv_hp=15, iv_atk=15, iv_def=15, iv_spd=15, iv_crit=15, iv_eva=15,
            hp=520, atk=65, def_=18, spd=0.58,
            crit=8, crit_dmg=1.5, eva=4, lifesteal=0.05,
        )

    def test_base64_image_used_in_src(self):
        """传入 base64_image 时，img src 使用 data URI"""
        from src.image_gen import render_pet_html
        pet = self._make_pet()
        b64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg=="
        html = render_pet_html(pet, "stats", "http://example.com/img.png",
                               base64_image=b64)
        self.assertIn(b64, html)
        self.assertNotIn("http://example.com/img.png", html)

    def test_no_base64_falls_back_to_url(self):
        """不传 base64_image 时，使用 image_url 或 file:// 路径"""
        from src.image_gen import render_pet_html
        pet = self._make_pet()
        html = render_pet_html(pet, "stats", "http://example.com/img.png")
        self.assertIn("http://example.com/img.png", html)

    def test_base64_empty_string_falls_back(self):
        """base64_image 为空字符串时回退到 URL"""
        from src.image_gen import render_pet_html
        pet = self._make_pet()
        html = render_pet_html(pet, "stats", "http://example.com/img.png",
                               base64_image="")
        self.assertIn("http://example.com/img.png", html)


class TestHtmlToImagePageReuse(unittest.IsolatedAsyncioTestCase):
    """html_to_image 页面复用逻辑。"""

    async def test_no_page_creates_and_closes(self):
        """不传 page 时新建页面并在 finally 中关闭"""
        from src.image_gen import html_to_image

        mock_page = AsyncMock()
        mock_page.evaluate.return_value = 500

        async def _fake_screenshot(path, full_page=False):
            Path(path).write_bytes(b"\x89PNG\r\n\x1a\nfake")

        mock_page.screenshot = _fake_screenshot
        mock_page.set_viewport_size = AsyncMock()
        mock_page.set_content = AsyncMock()
        mock_page.close = AsyncMock()

        mock_browser = AsyncMock()
        mock_browser.new_page.return_value = mock_page

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "out.png"
            await html_to_image(mock_browser, "<html></html>", output)

        mock_browser.new_page.assert_awaited_once()
        mock_page.close.assert_awaited_once()

    async def test_with_page_reuses_no_close(self):
        """传入 page 时复用页面，不新建也不关闭"""
        from src.image_gen import html_to_image

        mock_page = AsyncMock()
        mock_page.evaluate.return_value = 500

        async def _fake_screenshot(path, full_page=False):
            Path(path).write_bytes(b"\x89PNG\r\n\x1a\nfake")

        mock_page.screenshot = AsyncMock(side_effect=_fake_screenshot)
        mock_page.set_viewport_size = AsyncMock()
        mock_page.set_content = AsyncMock()
        mock_page.close = AsyncMock()

        mock_browser = AsyncMock()

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "out.png"
            await html_to_image(mock_browser, "<html></html>", output,
                                page=mock_page)

        mock_browser.new_page.assert_not_awaited()
        mock_page.close.assert_not_awaited()
        mock_page.set_content.assert_awaited_once()
        mock_page.screenshot.assert_awaited_once()

    async def test_page_set_content_called(self):
        """html_to_image 使用 set_content 而非 goto"""
        from src.image_gen import html_to_image

        mock_page = AsyncMock()
        mock_page.evaluate.return_value = 500

        async def _fake_screenshot(path, full_page=False):
            Path(path).write_bytes(b"\x89PNG\r\n\x1a\nfake")

        mock_page.screenshot = _fake_screenshot
        mock_page.set_viewport_size = AsyncMock()
        mock_page.set_content = AsyncMock()
        mock_page.close = AsyncMock()

        mock_browser = AsyncMock()
        mock_browser.new_page.return_value = mock_page

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "out.png"
            await html_to_image(mock_browser, "<html>test</html>", output)

        mock_page.set_content.assert_awaited_once()
        call_args = mock_page.set_content.call_args
        self.assertIn("<html>test</html>", call_args[0][0])


class TestGenerateScreenshot(unittest.IsolatedAsyncioTestCase):
    """_generate_screenshot 核心流程测试。"""

    def _make_pet(self):
        from src.data_manager import Pet
        return Pet(
            owner_id="user1", owner_name="test",
            name="测试猪", species_id="P001",
            evolution_stage=0, battle_type="attack", level=1, exp=0,
            iv_hp=15, iv_atk=15, iv_def=15, iv_spd=15, iv_crit=15, iv_eva=15,
            hp=520, atk=65, def_=18, spd=0.58,
            crit=8, crit_dmg=1.5, eva=4, lifesteal=0.05,
        )

    def _make_game(self, dm_overrides=None):
        from src.pet_game import PetGame
        from src.data_manager import DataManager

        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_page.evaluate.return_value = 600

        async def _fake_screenshot(path, full_page=False):
            Path(path).write_bytes(b"\x89PNG\r\n\x1a\nfake_png")

        mock_page.screenshot = _fake_screenshot
        mock_page.set_viewport_size = AsyncMock()
        mock_page.set_content = AsyncMock()
        mock_page.close = AsyncMock()
        mock_browser.new_page.return_value = mock_page

        mock_bot = MagicMock()
        mock_bot._playwright_browser = mock_browser
        mock_bot._screenshot_semaphore = asyncio.Semaphore(2)
        mock_bot._page_pool = [mock_page]

        dm = MagicMock(spec=DataManager)
        dm.get_screenshot_uuid = MagicMock(return_value=None)
        dm.set_screenshot_uuid = MagicMock()

        if dm_overrides:
            for k, v in dm_overrides.items():
                setattr(dm, k, v)

        game = PetGame(dm, mock_bot)
        return game

    async def test_cache_hit_returns_filename(self):
        """缓存命中时直接返回文件名，不生成截图"""
        from src.image_lifecycle import generate_screenshot_uuid

        pet = self._make_pet()
        expected_uuid = generate_screenshot_uuid("user1", pet.last_update, "")

        with tempfile.TemporaryDirectory() as tmpdir:
            screenshots_dir = Path(tmpdir)
            fake_file = screenshots_dir / f"{expected_uuid}.png"
            fake_file.write_bytes(b"fake")

            with patch("src.pet_game.config", {
                "webhook": {"callback_domain": "https://test.com"},
                "image": {
                    "pig_source": "cropped_pigs2",
                    "screenshots_dir": str(screenshots_dir),
                    "pet_image_base_dir": "",
                },
            }):
                game = self._make_game({
                    "get_screenshot_uuid": MagicMock(return_value=expected_uuid),
                })
                result = await game._generate_screenshot(pet)

        self.assertEqual(result, f"{expected_uuid}.png")

    async def test_no_playwright_returns_none(self):
        """Playwright 不可用时返回 None"""
        pet = self._make_pet()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.pet_game.config", {
                "webhook": {"callback_domain": "https://test.com"},
                "image": {
                    "pig_source": "cropped_pigs2",
                    "screenshots_dir": str(Path(tmpdir)),
                    "pet_image_base_dir": "",
                },
            }):
                game = self._make_game()
                game.bot._playwright_browser = None
                result = await game._generate_screenshot(pet)

        self.assertIsNone(result)

    async def test_semaphore_acquired_and_released(self):
        """截图过程中信号量被正确 acquire 和 release"""
        pet = self._make_pet()
        sem = asyncio.Semaphore(2)

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.pet_game.config", {
                "webhook": {"callback_domain": "https://test.com"},
                "image": {
                    "pig_source": "cropped_pigs2",
                    "screenshots_dir": str(Path(tmpdir)),
                    "pet_image_base_dir": "",
                },
            }):
                game = self._make_game()
                game.bot._screenshot_semaphore = sem
                initial_value = sem._value

                await game._generate_screenshot(pet)

                self.assertEqual(sem._value, initial_value,
                                 "信号量应在截图后释放回初始值")

    async def test_page_pool_pop_and_return(self):
        """页面从池中取出并在截图后归还"""
        pet = self._make_pet()
        mock_page = AsyncMock()
        mock_page.evaluate.return_value = 600

        async def _fake_screenshot(path, full_page=False):
            Path(path).write_bytes(b"\x89PNG\r\n\x1a\nfake")

        mock_page.screenshot = _fake_screenshot
        mock_page.set_viewport_size = AsyncMock()
        mock_page.set_content = AsyncMock()
        mock_page.close = AsyncMock()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.pet_game.config", {
                "webhook": {"callback_domain": "https://test.com"},
                "image": {
                    "pig_source": "cropped_pigs2",
                    "screenshots_dir": str(Path(tmpdir)),
                    "pet_image_base_dir": "",
                },
            }):
                game = self._make_game()
                game.bot._page_pool = [mock_page]

                await game._generate_screenshot(pet)

                self.assertEqual(len(game.bot._page_pool), 1,
                                 "页面应归还到池中")
                self.assertIs(game.bot._page_pool[0], mock_page,
                              "归还的应是同一个页面对象")

    async def test_page_pool_empty_creates_new(self):
        """页面池为空时新建页面，用后关闭"""
        pet = self._make_pet()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.pet_game.config", {
                "webhook": {"callback_domain": "https://test.com"},
                "image": {
                    "pig_source": "cropped_pigs2",
                    "screenshots_dir": str(Path(tmpdir)),
                    "pet_image_base_dir": "",
                },
            }):
                game = self._make_game()
                game.bot._page_pool = []

                result = await game._generate_screenshot(pet)

                self.assertIsNotNone(result)
                self.assertEqual(len(game.bot._page_pool), 0,
                                 "新建的页面不应归还到空池中")

    async def test_old_screenshot_scheduled_deletion(self):
        """旧截图通过 schedule_deletion 延迟删除"""
        pet = self._make_pet()
        old_uuid = "old-uuid-1234"

        with tempfile.TemporaryDirectory() as tmpdir:
            screenshots_dir = Path(tmpdir)
            old_file = screenshots_dir / f"{old_uuid}.png"
            old_file.write_bytes(b"old_screenshot")

            with patch("src.pet_game.config", {
                "webhook": {"callback_domain": "https://test.com"},
                "image": {
                    "pig_source": "cropped_pigs2",
                    "screenshots_dir": str(screenshots_dir),
                    "pet_image_base_dir": "",
                },
            }):
                game = self._make_game({
                    "get_screenshot_uuid": MagicMock(return_value=old_uuid),
                })

                with patch("src.image_lifecycle.schedule_deletion") as mock_schedule:
                    await game._generate_screenshot(pet)
                    mock_schedule.assert_called_once()
                    call_args = mock_schedule.call_args
                    self.assertIn(old_file, call_args[0])


class TestPreGenerateScreenshot(unittest.IsolatedAsyncioTestCase):
    """_pre_generate_screenshot 后台预生成测试。"""

    def _make_pet(self):
        from src.data_manager import Pet
        return Pet(
            owner_id="user1", owner_name="test",
            name="测试猪", species_id="P001",
            evolution_stage=0, battle_type="attack", level=1, exp=0,
            iv_hp=15, iv_atk=15, iv_def=15, iv_spd=15, iv_crit=15, iv_eva=15,
            hp=520, atk=65, def_=18, spd=0.58,
            crit=8, crit_dmg=1.5, eva=4, lifesteal=0.05,
        )

    async def test_pre_generate_calls_generate_screenshot(self):
        """_pre_generate_screenshot 调用 _generate_screenshot"""
        from src.pet_game import PetGame

        pet = self._make_pet()
        game = PetGame(MagicMock(), MagicMock())
        game._generate_screenshot = AsyncMock(return_value="test.png")

        await game._pre_generate_screenshot(pet)

        game._generate_screenshot.assert_awaited_once_with(pet, None)

    async def test_pre_generate_swallows_exceptions(self):
        """_pre_generate_screenshot 吞掉异常不抛出"""
        from src.pet_game import PetGame

        pet = self._make_pet()
        game = PetGame(MagicMock(), MagicMock())
        game._generate_screenshot = AsyncMock(side_effect=RuntimeError("test error"))

        await game._pre_generate_screenshot(pet)

    async def test_pre_generate_with_old_pet(self):
        """_pre_generate_screenshot 传递 old_pet 参数"""
        from src.pet_game import PetGame

        pet = self._make_pet()
        old_pet = self._make_pet()
        old_pet.name = "旧猪"

        game = PetGame(MagicMock(), MagicMock())
        game._generate_screenshot = AsyncMock(return_value="test.png")

        await game._pre_generate_screenshot(pet, old_pet=old_pet)

        game._generate_screenshot.assert_awaited_once_with(pet, old_pet)


class TestBuildPetMessage(unittest.IsolatedAsyncioTestCase):
    """_build_pet_message 消息组装测试。"""

    def _make_pet(self):
        from src.data_manager import Pet
        return Pet(
            owner_id="user1", owner_name="test",
            name="测试猪", species_id="P001",
            evolution_stage=0, battle_type="attack", level=1, exp=0,
            iv_hp=15, iv_atk=15, iv_def=15, iv_spd=15, iv_crit=15, iv_eva=15,
            hp=520, atk=65, def_=18, spd=0.58,
            crit=8, crit_dmg=1.5, eva=4, lifesteal=0.05,
        )

    async def test_screenshot_url_in_message(self):
        """截图成功时消息中包含截图 URL"""
        from src.pet_game import PetGame

        pet = self._make_pet()
        game = PetGame(MagicMock(), MagicMock())
        game._generate_screenshot = AsyncMock(return_value="abc-123.png")

        with patch("src.pet_game.config", {
            "webhook": {"callback_domain": "https://test.com"},
            "image": {"pig_source": "cropped_pigs2"},
        }):
            msg = await game._build_pet_message(
                pet, "标题", "提示",
                [[{"text": "按钮", "command": "/cmd"}]])

        self.assertIn("https://test.com/static/images/screenshots/abc-123.png",
                       str(msg))

    async def test_fallback_to_image_url(self):
        """截图失败时回退到原始宠物图片 URL"""
        from src.pet_game import PetGame

        pet = self._make_pet()
        game = PetGame(MagicMock(), MagicMock())
        game._generate_screenshot = AsyncMock(return_value=None)

        with patch("src.pet_game.config", {
            "webhook": {"callback_domain": "https://test.com"},
            "image": {"pig_source": "cropped_pigs2"},
        }):
            msg = await game._build_pet_message(
                pet, "标题", "提示", [])

        self.assertNotIn("screenshots", str(msg))

    async def test_message_has_keyboard(self):
        """消息包含 keyboard 字段"""
        from src.pet_game import PetGame

        pet = self._make_pet()
        game = PetGame(MagicMock(), MagicMock())
        game._generate_screenshot = AsyncMock(return_value="test.png")

        with patch("src.pet_game.config", {
            "webhook": {"callback_domain": "https://test.com"},
            "image": {"pig_source": "cropped_pigs2"},
        }):
            msg = await game._build_pet_message(
                pet, "标题", "提示",
                [[{"text": "按钮", "command": "/cmd"}]])

        self.assertIn("keyboard", msg)


if __name__ == "__main__":
    unittest.main(verbosity=2)
