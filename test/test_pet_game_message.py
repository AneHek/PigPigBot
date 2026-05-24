"""
test_pet_game_message.py — 验证宠物消息返回 dict 结构含 msg_type/keyboard。

由于 pet_game 方法现在需要 bot 引用和 Playwright browser，
测试通过 mock bot 来验证消息结构。
"""
import sys
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

sys.modules['redis'] = MagicMock()
sys.modules['playwright'] = MagicMock()
sys.modules['playwright.async_api'] = MagicMock()


class TestPetGameMessageStructure(unittest.IsolatedAsyncioTestCase):
    """验证 pet_game 方法返回 dict 结构。"""

    async def _make_game(self):
        """创建带 mock bot 的 PetGame 实例"""
        from src.data_manager import DataManager
        from src.pet_game import PetGame
        from pathlib import Path

        # mock bot with browser
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_browser.new_page.return_value = mock_page
        mock_page.evaluate.return_value = 600

        mock_bot = MagicMock()
        mock_bot._playwright_browser = mock_browser

        dm = DataManager()
        dm.has_pet = MagicMock(return_value=False)
        dm.create_pet = MagicMock()
        dm.update_leaderboard = MagicMock()

        # mock create_pet 返回有效 Pet
        from src.data_manager import Pet
        test_pet = Pet(
            owner_id="test_user", owner_name="test",
            name="五行猪混混", species_id="P001",
            evolution_stage=0, battle_type="attack", level=1, exp=0,
            iv_hp=15, iv_atk=15, iv_def=15, iv_spd=15, iv_crit=15, iv_eva=15,
            hp=520, atk=65, def_=18, spd=0.58,
            crit=8, crit_dmg=1.5, eva=4, lifesteal=0.05,
        )
        dm.create_pet.return_value = test_pet

        # mock data_manager.get_pet 返回 test_pet
        dm.get_pet = MagicMock(return_value=test_pet)

        game = PetGame(dm, mock_bot)
        return game

    async def test_adopt_returns_dict_with_keyboard(self):
        """领养消息返回 dict 含 msg_type=2 和 keyboard"""
        game = await self._make_game()
        result = await game.adopt("user1", "测试用户")
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("msg_type"), 2)
        self.assertIn("markdown", result)
        self.assertIn("keyboard", result)

    async def test_stats_detail_returns_dict(self):
        """属性详情返回 dict"""
        game = await self._make_game()
        result = await game.stats_detail("user1")
        self.assertIsInstance(result, dict)
        self.assertIn("markdown", result)
        self.assertIn("keyboard", result)

    async def test_evolve(self):
        """测试evolve需要mock evolve_pet"""
        game = await self._make_game()
        result = await game.evolve("user1")
        # evolution_stage==0 and level==1 < 29 → 返回错误文本
        self.assertIsInstance(result, str)
        self.assertIn("Lv.29", result)

    async def test_evolve_success_returns_dict(self):
        """进化成功后应返回 dict"""
        game = await self._make_game()
        from src.data_manager import Pet
        test_pet = Pet(
            owner_id="test_user", owner_name="test",
            name="五行猪混混", species_id="P001",
            evolution_stage=0, battle_type="attack", level=30, exp=0,
            iv_hp=15, iv_atk=15, iv_def=15, iv_spd=15, iv_crit=15, iv_eva=15,
            hp=520, atk=65, def_=18, spd=0.58,
            crit=8, crit_dmg=1.5, eva=4, lifesteal=0.05,
        )
        game.dm.get_pet.return_value = test_pet

        evolved_pet = Pet(
            owner_id="test_user", owner_name="test",
            name="黑白猪煞", species_id="P001",
            evolution_stage=1, battle_type="attack", level=30, exp=0,
            iv_hp=15, iv_atk=15, iv_def=15, iv_spd=15, iv_crit=15, iv_eva=15,
            hp=520, atk=65, def_=18, spd=0.58,
            crit=8, crit_dmg=1.6, eva=4, lifesteal=0.08,
        )
        game.dm.evolve_pet = MagicMock(return_value=evolved_pet)

        result = await game.evolve("user1")
        self.assertIsInstance(result, dict)
        self.assertIn("markdown", result)

    async def test_start_training_returns_dict(self):
        """开始训练返回 dict"""
        game = await self._make_game()
        game.dm.start_training = MagicMock()
        from src.data_manager import Pet
        test_pet = Pet(
            owner_id="test_user", owner_name="test",
            name="五行猪混混", species_id="P001",
            evolution_stage=0, battle_type="attack", level=1, exp=0,
            iv_hp=15, iv_atk=15, iv_def=15, iv_spd=15, iv_crit=15, iv_eva=15,
            hp=520, atk=65, def_=18, spd=0.58,
            crit=8, crit_dmg=1.5, eva=4, lifesteal=0.05,
            training=True, training_start=0,
        )
        game.dm.start_training.return_value = test_pet

        result = await game.start_training("user1")
        self.assertIsInstance(result, dict)
        self.assertIn("markdown", result)

    async def test_no_pet_returns_string(self):
        """无宠物时返回文本错误消息"""
        game = await self._make_game()
        game.dm.get_pet.return_value = None
        result = await game.stats_detail("user1")
        self.assertIsInstance(result, str)
        self.assertIn("没有宠物", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
