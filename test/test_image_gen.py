"""
test_image_gen.py — 测试 image_gen HTML渲染 和 image_lifecycle 生命周期函数。
使用 mock playwright 避免真实浏览器依赖，使用 mock asyncio 测试延迟删除。
"""
import sys
import unittest
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

sys.modules['redis'] = MagicMock()
sys.modules['playwright'] = MagicMock()
sys.modules['playwright.async_api'] = MagicMock()


class TestImageGen(unittest.TestCase):
    """Test HTML template rendering."""

    @classmethod
    def setUpClass(cls):
        """绕过模块级 playwright import 检查：先 mock 再导入。"""
        pass

    def _make_pet(self, species_id="P001", evo=0, name="测试猪",
                  level=10, exp=500):
        """创建测试用 Pet 对象"""
        from src.data.models import Pet
        return Pet(
            owner_id="test_user",
            owner_name="测试用户",
            name=name,
            species_id=species_id,
            evolution_stage=evo,
            battle_type="attack",
            level=level,
            exp=exp,
            iv_hp=15, iv_atk=15, iv_def=15, iv_spd=15, iv_crit=15, iv_eva=15,
            hp=520, atk=65, def_=18, spd=0.58,
            crit=8, crit_dmg=1.5, eva=4, lifesteal=0.05,
        )

    def test_render_pet_html_status(self):
        """render_pet_html 包含宠物名和属性"""
        from src.screenshot.render import render_pet_html
        pet = self._make_pet()
        html = render_pet_html(pet, "http://example.com/img.png")
        self.assertIn("测试猪", html)
        self.assertIn('<img class="pet-img"', html)
        self.assertIn("520", html)  # HP
        self.assertIn("65", html)   # ATK

    def test_render_pet_html_stats(self):
        """render_pet_html 包含IV进度条"""
        from src.screenshot.render import render_pet_html
        pet = self._make_pet()
        html = render_pet_html(pet, "http://example.com/img.png")
        self.assertIn("iv-fill", html)

    def test_render_pet_html_adopt(self):
        """render_pet_html 不含改名提示（已移到tip）"""
        from src.screenshot.render import render_pet_html
        pet = self._make_pet()
        html = render_pet_html(pet, "http://example.com/img.png")
        self.assertIn("测试猪", html)
        self.assertNotIn("/改名", html)

    def test_render_pet_html_evolve(self):
        """render_pet_html 含属性变化预览（old_pet）"""
        from src.screenshot.render import render_pet_html
        pet = self._make_pet(evo=1, level=30)
        old = self._make_pet(evo=0, level=29, name="旧猪")
        old.hp, old.atk, old.def_, old.spd = 400, 50, 14, 0.50
        html = render_pet_html(pet, "http://example.com/img.png",
                               old_pet=old)
        self.assertIn("二阶", html)
        self.assertIn("→", html)

    def test_render_pet_html_skill_section(self):
        """render_pet_html 包含技能信息区域"""
        from src.screenshot.render import render_pet_html
        pet = self._make_pet()
        html = render_pet_html(pet, "http://example.com/img.png")
        self.assertIn("skill-section", html)
        self.assertIn("技能按阶段", html)

    def test_html_content_validity(self):
        """HTML 以 <!DOCTYPE html> 开头"""
        from src.screenshot.render import render_pet_html
        pet = self._make_pet()
        html = render_pet_html(pet, "http://example.com/img.png")
        self.assertTrue(html.strip().startswith("<!DOCTYPE html>"))


class TestImageLifecycle(unittest.IsolatedAsyncioTestCase):
    """Test image lifecycle functions."""

    async def test_schedule_deletion_deletes_file(self):
        """延迟删除在指定时间后删除文件"""
        from src.screenshot.lifecycle import schedule_deletion

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = Path(f.name)
        try:
            path.write_text("test")
            # 使用短延迟
            await schedule_deletion(path, 0)
            await asyncio.sleep(0.2)  # 给任务时间
            self.assertFalse(path.exists())
        finally:
            if path.exists():
                path.unlink()

    async def test_schedule_deletion_missing_file_no_error(self):
        """删除不存在的文件不抛出异常"""
        from src.screenshot.lifecycle import schedule_deletion
        path = Path("/tmp/nonexistent_xyz123.png")
        await schedule_deletion(path, 0)
        # 不应抛出异常

    def test_cleanup_orphan_files(self):
        """cleanup_orphan_files 清理目录下所有文件"""
        from src.screenshot.lifecycle import cleanup_orphan_files
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            (d / "a.png").write_text("a")
            (d / "b.png").write_text("b")
            count = cleanup_orphan_files(d)
            self.assertEqual(count, 2)
            self.assertFalse((d / "a.png").exists())

    def test_cleanup_orphan_empty_dir(self):
        """清理空目录返回0"""
        from src.screenshot.lifecycle import cleanup_orphan_files
        with tempfile.TemporaryDirectory() as tmpdir:
            count = cleanup_orphan_files(Path(tmpdir))
            self.assertEqual(count, 0)


class TestImageGeneration(unittest.IsolatedAsyncioTestCase):
    """验证 html_to_image 实际写出文件到磁盘（mock playwright，写真实文件）。
    此测试确认生成流程端到端正常，不涉及删除。"""

    async def test_html_to_image_creates_file(self):
        """html_to_image 应在指定路径创建PNG文件"""
        from src.screenshot.render import html_to_image

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "test_output.png"

            mock_page = AsyncMock()
            mock_page.evaluate.return_value = 500

            async def _fake_screenshot(path, full_page=False):
                Path(path).write_bytes(b"\x89PNG\r\n\x1a\nfake_png_data")

            mock_page.screenshot = _fake_screenshot
            mock_page.set_viewport_size = AsyncMock()
            mock_page.set_content = AsyncMock()
            mock_page.close = AsyncMock()

            mock_browser = AsyncMock()
            mock_browser.new_page.return_value = mock_page

            await html_to_image(mock_browser, "<html></html>", output)

            self.assertTrue(output.exists(), "截图文件应被创建")
            self.assertGreater(output.stat().st_size, 0, "文件不应为空")

    async def test_html_to_image_output_path_respected(self):
        """截图输出路径正确，文件名包含 ext"""
        from src.screenshot.render import html_to_image

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "my_screenshot.png"

            mock_page = AsyncMock()
            mock_page.evaluate.return_value = 400

            captured_path = None

            async def _fake_screenshot(path, full_page=False):
                nonlocal captured_path
                captured_path = str(path)
                Path(path).write_bytes(b"\x89PNG\r\n\x1a\nok")

            mock_page.screenshot = _fake_screenshot
            mock_page.set_viewport_size = AsyncMock()
            mock_page.set_content = AsyncMock()
            mock_page.close = AsyncMock()

            mock_browser = AsyncMock()
            mock_browser.new_page.return_value = mock_page

            await html_to_image(mock_browser, "<html></html>", output)

            self.assertIsNotNone(captured_path)
            self.assertTrue(str(captured_path).endswith(".png"))
            self.assertTrue(output.exists())


class TestFileDeletion(unittest.TestCase):
    """验证文件实际删除功能（不依赖 asyncio / 延迟调度，直接测试删除行为）。"""

    def test_file_deletion_confirmed(self):
        """创建文件 → 确认存在 → 删除 → 确认不存在"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "to_delete.png"
            path.write_bytes(b"test data")

            self.assertTrue(path.exists(), "删除前文件应存在")

            path.unlink()

            self.assertFalse(path.exists(), "删除后文件应不存在")

    def test_cleanup_orphan_deletes_all(self):
        """cleanup_orphan_files 清理目录下多个文件"""
        from src.screenshot.lifecycle import cleanup_orphan_files
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            files = [d / f"snap_{i}.png" for i in range(5)]
            for f in files:
                f.write_bytes(b"data")

            count = cleanup_orphan_files(d)
            self.assertEqual(count, 5, "应清理5个文件")
            for f in files:
                self.assertFalse(f.exists(), f"{f.name} 应被删除")

    def test_cleanup_orphan_handles_permission_error(self):
        """清理时单个文件失败不影响其他文件（模拟权限错误）"""
        from src.screenshot.lifecycle import cleanup_orphan_files
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            (d / "a.png").write_text("a")
            (d / "b.png").write_text("b")
            (d / "c.png").write_text("c")

            # 用 patch 让 b.png 的 unlink 失败
            import builtins
            original_unlink = Path.unlink
            fail_count = [0]

            def _fail_unlink(self_path):
                if self_path.name == "b.png":
                    fail_count[0] += 1
                    raise PermissionError("模拟权限错误")
                return original_unlink(self_path)

            with patch.object(Path, "unlink", _fail_unlink):
                count = cleanup_orphan_files(d)

            # a 和 c 被删除，b 因权限错误跳过 → count=2
            self.assertEqual(count, 2, "应删除2个（b因权限跳过）")
            self.assertFalse((d / "a.png").exists())
            self.assertTrue((d / "b.png").exists(), "b因权限错误应保留")
            self.assertFalse((d / "c.png").exists())
            self.assertEqual(fail_count[0], 1, "b应触发一次权限错误")


class TestRealImageGeneration(unittest.IsolatedAsyncioTestCase):
    """真实端到端测试：生成 HTML 和 PNG 截图到 screenshots 目录。

    此测试用于：1) 验证路径和生成流程端到端可用；
    2) 手动查看 HTML/PNG 效果进行样式调优。

    需要真实 Playwright 环境，否则自动跳过。
    """

    _PLAYWRIGHT_AVAILABLE = None  # None=未检测, True=可用, False=不可用

    @classmethod
    def setUpClass(cls):
        """检测 Playwright 是否可用（绕过文件顶部 mock）。"""
        for mod in ["playwright", "playwright.async_api"]:
            sys.modules.pop(mod, None)
        try:
            from playwright.async_api import async_playwright as _apw
            cls._PLAYWRIGHT_AVAILABLE = True
        except ImportError:
            cls._PLAYWRIGHT_AVAILABLE = False
        # 恢复 mock（其他测试类依赖 mock）
        sys.modules["playwright"] = MagicMock()
        sys.modules["playwright.async_api"] = MagicMock()

    async def asyncSetUp(self):
        if not self._PLAYWRIGHT_AVAILABLE:
            self.skipTest("Playwright 未安装，跳过真实截图测试")

        # 确保截图目录存在
        screenshots_dir = Path(__file__).parent.parent / "data" / "images" / "screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.screenshots_dir = screenshots_dir

        # 清除所有 playwright 相关 mock（_impl 等子模块也需清除，否则 import 失败）
        to_pop = [k for k in list(sys.modules.keys())
                  if k == "playwright" or k.startswith("playwright.")]
        for mod in to_pop:
            sys.modules.pop(mod, None)

        from playwright.async_api import async_playwright

        # 启动真实 browser
        self._pw_instance = await async_playwright().start()
        self.browser = await self._pw_instance.chromium.launch(headless=True)

    async def asyncTearDown(self):
        if hasattr(self, "browser"):
            await self.browser.close()
        if hasattr(self, "_pw_instance"):
            await self._pw_instance.stop()
        # 恢复 mock 保持其他测试类兼容
        sys.modules["playwright"] = MagicMock()
        sys.modules["playwright.async_api"] = MagicMock()

    def _make_pet(self, species_id="P001", evo=0, name="五行猪混混",
                  level=10, exp=500):
        """创建测试用 Pet 对象"""
        from src.data.models import Pet
        return Pet(
            owner_id="test_user",
            owner_name="测试用户",
            name=name,
            species_id=species_id,
            evolution_stage=evo,
            battle_type="attack",
            level=level,
            exp=exp,
            iv_hp=20, iv_atk=25, iv_def=15, iv_spd=18, iv_crit=22, iv_eva=10,
            hp=720, atk=85, def_=22, spd=0.65,
            crit=10, crit_dmg=1.5, eva=5, lifesteal=0.05,
        )

    # ── 真实截图测试：S/A/B/C 四品质 × 各场景 ──

    async def _gen_and_verify(self, pet, scene: str, image_url: str,
                               old_pet=None, tag: str = ""):
        """公用：渲染HTML→写出HTML文件→截图PNG→验证两个文件都存在"""
        import base64
        from src.screenshot.render import render_pet_html, html_to_image

        suffix = f"_{tag}" if tag else ""
        base_name = f"test_{scene}{suffix}"
        html_path = self.screenshots_dir / f"{base_name}.html"
        png_path = self.screenshots_dir / f"{base_name}.png"

        local_image_path = ""
        marker = "/static/images/"
        idx = image_url.find(marker)
        if idx != -1:
            relative = image_url[idx + len(marker):]
            local = Path(__file__).parent.parent / "data" / "images" / relative
            if local.exists():
                local_image_path = str(local.resolve())

        base64_image = ""
        if local_image_path and Path(local_image_path).exists():
            img_bytes = Path(local_image_path).read_bytes()
            b64 = base64.b64encode(img_bytes).decode("ascii")
            base64_image = f"data:image/png;base64,{b64}"

        html = render_pet_html(pet, image_url, local_image_path,
                               old_pet=old_pet, base64_image=base64_image)
        html_path.write_text(html, encoding="utf-8")
        self.assertTrue(html_path.exists(), f"HTML 文件应被创建: {html_path}")
        self.assertGreater(html_path.stat().st_size, 100)

        await html_to_image(self.browser, html, png_path)
        self.assertTrue(png_path.exists(), f"PNG 文件应被创建: {png_path}")
        self.assertGreater(png_path.stat().st_size, 100)
        return png_path

    def _make_quality_pet(self, quality_index: int, species_id: str,
                          evo: int, level: int, exp: int, name: str):
        """用 calc_stats 生成正确属性的宠物"""
        from src.data.models import Pet
        from src.pet.stats import calc_stats, generate_ivs

        ivs = generate_ivs(quality_index)
        stats = calc_stats(species_id, evo, level, ivs)
        return Pet(
            owner_id="test_user", owner_name="测试用户",
            name=name, species_id=species_id, evolution_stage=evo,
            battle_type="attack" if "P005" not in species_id else "defense",
            level=level, exp=exp,
            iv_hp=ivs["iv_hp"], iv_atk=ivs["iv_atk"], iv_def=ivs["iv_def"],
            iv_spd=ivs["iv_spd"], iv_crit=ivs["iv_crit"], iv_eva=ivs["iv_eva"],
            hp=stats["hp"], atk=stats["atk"], def_=stats["def_"],
            spd=stats["spd"], crit=stats["crit"], crit_dmg=stats["crit_dmg"],
            eva=stats["eva"], lifesteal=stats["lifesteal"],
        )

    # ── S品质 — P001 混沌猪 三阶 ──
    async def test_real_S_evolve(self):
        """S品质 P001 进化：二阶→三阶，含箭头预览"""
        from src.data.models import Pet
        from src.pet.stats import calc_stats, generate_ivs
        species_id = "P001"
        image_url = "/static/images/cropped_pigs2/P001_2.png"

        ivs = generate_ivs(5)  # S quality
        old_stats = calc_stats(species_id, 1, 59, ivs)
        new_stats = calc_stats(species_id, 2, 60, ivs)

        old_pet = Pet(owner_id="t", owner_name="t", name="黑白猪煞",
                      species_id=species_id, evolution_stage=1, battle_type="attack",
                      level=59, exp=4000,
                      iv_hp=ivs["iv_hp"], iv_atk=ivs["iv_atk"], iv_def=ivs["iv_def"],
                      iv_spd=ivs["iv_spd"], iv_crit=ivs["iv_crit"], iv_eva=ivs["iv_eva"],
                      hp=old_stats["hp"], atk=old_stats["atk"], def_=old_stats["def_"],
                      spd=old_stats["spd"], crit=old_stats["crit"],
                      crit_dmg=old_stats["crit_dmg"], eva=old_stats["eva"],
                      lifesteal=old_stats["lifesteal"])
        new_pet = Pet(owner_id="t", owner_name="t", name="混沌猪",
                      species_id=species_id, evolution_stage=2, battle_type="attack",
                      level=60, exp=5000,
                      iv_hp=ivs["iv_hp"], iv_atk=ivs["iv_atk"], iv_def=ivs["iv_def"],
                      iv_spd=ivs["iv_spd"], iv_crit=ivs["iv_crit"], iv_eva=ivs["iv_eva"],
                      hp=new_stats["hp"], atk=new_stats["atk"], def_=new_stats["def_"],
                      spd=new_stats["spd"], crit=new_stats["crit"],
                      crit_dmg=new_stats["crit_dmg"], eva=new_stats["eva"],
                      lifesteal=new_stats["lifesteal"])
        await self._gen_and_verify(new_pet, "evolve", image_url,
                                   old_pet=old_pet, tag="S")

    # ── A品质 — P008 骷髅猪 stats 场景 ──
    async def test_real_A_stats(self):
        """A品质 P008 属性详情"""
        species_id = "P008"
        evo = 1
        image_url = f"/static/images/cropped_pigs2/{species_id}_{evo}.png"

        pet = self._make_quality_pet(4, species_id, evo, 42, 3000, "骷髅猪士")
        await self._gen_and_verify(pet, "stats", image_url, tag="A")

    # ── B品质 — P015 训练中 ──
    async def test_real_B_training(self):
        """B品质 P015 训练场景"""
        import time
        species_id = "P015"
        evo = 1
        image_url = f"/static/images/cropped_pigs2/{species_id}_{evo}.png"

        pet = self._make_quality_pet(3, species_id, evo, 35, 2000, "表情猪王")
        pet.training = True
        pet.training_start = time.time() - 1200  # 已训练20分钟
        await self._gen_and_verify(pet, "training", image_url, tag="B")

    # ── C品质 — P020 领养场景 ──
    async def test_real_C_adopt(self):
        """C品质 P020 领养"""
        species_id = "P020"
        evo = 0
        image_url = f"/static/images/cropped_pigs2/{species_id}_{evo}.png"

        pet = self._make_quality_pet(2, species_id, evo, 1, 0, "泡泡猪")
        await self._gen_and_verify(pet, "adopt", image_url, tag="C")

    # ── 帮助菜单截图 ──
    async def test_real_help_menu(self):
        """帮助菜单 HTML → data/images/help.png"""
        from src.screenshot.render import html_to_image

        html_path = Path(__file__).parent.parent / "help_menu.html"
        self.assertTrue(html_path.exists(), f"help_menu.html 应存在: {html_path}")

        html_str = html_path.read_text(encoding="utf-8")
        output_path = Path(__file__).parent.parent / "data" / "images" / "help.png"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        await html_to_image(self.browser, html_str, output_path, padding=0)
        self.assertTrue(output_path.exists(), f"help.png 应被创建: {output_path}")
        self.assertGreater(output_path.stat().st_size, 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)
