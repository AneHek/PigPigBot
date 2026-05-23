"""
test_data_manager.py - DataManager 数据持久化测试用例

使用内存模拟 Redis，验证所有数据操作的正确性，重点覆盖：
- 宠物创建/读取/更新/删除
- 经验增加与升级逻辑（之前经验丢失 bug 的回归测试）
- 冷却与排行榜
- 属性衰减
"""

import json
import time
import unittest
import sys
from unittest.mock import patch, MagicMock


# ══════════════════════════════════════════════════════════════════════
# Mock Redis — 在导入 DataManager 之前打补丁
# ══════════════════════════════════════════════════════════════════════

class InMemoryRedis:
    """内存 Redis 模拟，验证数据持久化行为"""

    _store: dict[str, str] = {}
    _hashes: dict[str, dict[str, str]] = {}
    _zsets: dict[str, dict[str, float]] = {}

    @classmethod
    def reset(cls):
        cls._store = {}
        cls._hashes = {}
        cls._zsets = {}

    def __init__(self, *args, **kwargs):
        pass

    def ping(self):
        return True

    # ── String ──
    def set(self, key: str, value: str, *args, **kwargs):
        self._store[key] = value

    def get(self, key: str):
        return self._store.get(key)

    def exists(self, key: str):
        return 1 if key in self._store else 0

    def delete(self, *keys: str):
        count = 0
        for k in keys:
            if k in self._store:
                del self._store[k]
                count += 1
            # 同时删除 hash / zset 数据
            if k in self._hashes:
                del self._hashes[k]
                count += 1
            if k in self._zsets:
                del self._zsets[k]
                count += 1
        return count

    # ── Hash ──
    def hget(self, name: str, key: str):
        return self._hashes.get(name, {}).get(key)

    def hset(self, name: str, key: str = None, value: str = None, mapping: dict = None):
        if name not in self._hashes:
            self._hashes[name] = {}
        if mapping:
            self._hashes[name].update(mapping)
        elif key is not None:
            self._hashes[name][key] = value
        return 1

    # ── Sorted Set ──
    def zadd(self, name: str, mapping: dict):
        if name not in self._zsets:
            self._zsets[name] = {}
        self._zsets[name].update(mapping)
        return len(mapping)

    def zrevrange(self, name: str, start: int, end: int):
        if name not in self._zsets:
            return []
        sorted_items = sorted(self._zsets[name].items(), key=lambda x: x[1], reverse=True)
        return [item[0] for item in sorted_items[start:end + 1]]

    def zrem(self, name: str, *values: str):
        if name not in self._zsets:
            return 0
        count = 0
        for v in values:
            if v in self._zsets[name]:
                del self._zsets[name][v]
                count += 1
        return count

    # ── Scan ──
    def scan_iter(self, match: str = None):
        prefix = match.replace("*", "") if match else ""
        for key in self._store:
            if key.startswith(prefix):
                yield key


# ── 构造 Mock 配置 ──
MOCK_CONFIG = {
    "redis": {"host": "localhost", "port": 6379, "password": "", "db": 0},
    "image": {"dir": "data/images"},
    "game": {
        "decay_interval": 10,
        "pet_types": [
            {
                "id": "cat", "name": "猫咪", "emoji": "🐱",
                "desc": "优雅的小猫咪",
                "base_stats": {"satiety": 70, "mood": 70, "health": 80, "energy": 60},
            },
        ],
        "exp": {"feed": 10, "play": 15, "work": 20, "train": 25},
    },
}


# ── 在导入被测模块前替换 Redis 和 config ──
# 用 InMemoryRedis 替换 redis.Redis
_redis_patch = patch("redis.Redis", InMemoryRedis)
_redis_patch.start()

# 强行替换 src.data_manager 模块中的 config（普通 dict 无法 patch get）
import src.data_manager as dm_module
dm_module.config = MOCK_CONFIG
dm_module._redis_client = InMemoryRedis()

# 替换全局 data_manager 实例
from src.data_manager import DataManager, Pet, data_manager, KEY_LEADERBOARD


class TestDataManagerBase(unittest.TestCase):
    """测试基类：每次测试前后清空内存 Redis"""

    @classmethod
    def setUpClass(cls):
        cls.dm = DataManager()

    def setUp(self):
        InMemoryRedis.reset()


# ══════════════════════════════════════════════════════════════════════
# 1. 宠物创建 & 基本 CRUD
# ══════════════════════════════════════════════════════════════════════

class TestPetCreation(TestDataManagerBase):
    """测试宠物创建、查询、删除"""

    def test_create_pet_and_retrieve(self):
        """创建宠物后应能从 Redis 正确读取"""
        pet_config = {
            "emoji": "🐱", "name": "小猫咪",
            "base_stats": {"satiety": 70, "mood": 70, "health": 80, "energy": 60},
        }
        pet = self.dm.create_pet("user001", "张三", "cat", pet_config)

        self.assertEqual(pet.owner_id, "user001")
        self.assertEqual(pet.owner_name, "张三")
        self.assertEqual(pet.name, "小猫咪")
        self.assertEqual(pet.pet_type, "cat")
        self.assertEqual(pet.emoji, "🐱")
        self.assertEqual(pet.level, 1)
        self.assertEqual(pet.exp, 0)
        self.assertEqual(pet.satiety, 70)
        self.assertEqual(pet.mood, 70)
        self.assertEqual(pet.health, 80)
        self.assertEqual(pet.energy, 60)
        self.assertEqual(pet.coins, 100)

        retrieved = self.dm.get_pet("user001")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.owner_id, "user001")
        self.assertEqual(retrieved.level, 1)
        self.assertEqual(retrieved.exp, 0)

    def test_has_pet(self):
        """has_pet 应正确反映宠物是否存在"""
        self.assertFalse(self.dm.has_pet("user001"))
        cfg = {"emoji": "🐶", "name": "小狗", "base_stats": {"satiety": 60, "mood": 80, "health": 75, "energy": 80}}
        self.dm.create_pet("user001", "张三", "dog", cfg)
        self.assertTrue(self.dm.has_pet("user001"))
        self.assertFalse(self.dm.has_pet("user002"))

    def test_delete_pet(self):
        """删除宠物后所有相关数据应被清除"""
        cfg = {"emoji": "🐱", "name": "猫咪", "base_stats": {"satiety": 70, "mood": 70, "health": 80, "energy": 60}}
        pet = self.dm.create_pet("user001", "张三", "cat", cfg)
        self.dm.set_cooldown("user001", "feed", 30)
        self.dm.update_leaderboard(pet)

        self.assertTrue(self.dm.has_pet("user001"))
        result = self.dm.delete_pet("user001")
        self.assertTrue(result)
        self.assertFalse(self.dm.has_pet("user001"))
        self.assertIsNone(self.dm.get_pet("user001"))
        self.assertFalse(self.dm.delete_pet("user999"))


# ══════════════════════════════════════════════════════════════════════
# 2. 属性更新
# ══════════════════════════════════════════════════════════════════════

class TestPetUpdate(TestDataManagerBase):
    """测试 update_pet 属性修改"""

    def setUp(self):
        super().setUp()
        cfg = {"emoji": "🐱", "name": "猫咪", "base_stats": {"satiety": 70, "mood": 70, "health": 80, "energy": 60}}
        self.dm.create_pet("user001", "张三", "cat", cfg)

    def test_update_single_attribute(self):
        """更新单个属性后应持久化到 Redis"""
        pet = self.dm.update_pet("user001", satiety=95)
        self.assertEqual(pet.satiety, 95)
        pet2 = self.dm.get_pet("user001")
        self.assertEqual(pet2.satiety, 95)

    def test_update_multiple_attributes(self):
        """同时更新多个属性"""
        pet = self.dm.update_pet("user001", satiety=80, mood=50, coins=200)
        self.assertEqual(pet.satiety, 80)
        self.assertEqual(pet.mood, 50)
        self.assertEqual(pet.coins, 200)
        pet2 = self.dm.get_pet("user001")
        self.assertEqual(pet2.satiety, 80)
        self.assertEqual(pet2.mood, 50)
        self.assertEqual(pet2.coins, 200)

    def test_update_clamps_attributes_to_range(self):
        """属性值应被限制在 0-100"""
        pet = self.dm.update_pet("user001", satiety=150, mood=-10, health=200, energy=-50)
        self.assertEqual(pet.satiety, 100)
        self.assertEqual(pet.mood, 0)
        self.assertEqual(pet.health, 100)
        self.assertEqual(pet.energy, 0)

    def test_update_nonexistent_pet(self):
        """更新不存在的宠物应返回 None"""
        self.assertIsNone(self.dm.update_pet("user999", satiety=50))


# ══════════════════════════════════════════════════════════════════════
# 3. 经验增加 & 升级（核心：原 bug 回归测试）
# ══════════════════════════════════════════════════════════════════════

class TestExpAndLevelUp(TestDataManagerBase):
    """测试经验增加与升级逻辑"""

    def setUp(self):
        super().setUp()
        cfg = {"emoji": "🐱", "name": "猫咪", "base_stats": {"satiety": 70, "mood": 70, "health": 80, "energy": 60}}
        self.dm.create_pet("user001", "张三", "cat", cfg)

    # ── 经验持久化（回归 BUG-001）──
    def test_add_exp_persists_to_redis(self):
        """add_exp 后经验必须持久化到 Redis"""
        self.dm.add_exp("user001", 30)
        pet = self.dm.get_pet("user001")
        self.assertEqual(pet.exp, 30, "经验应持久化（修复前此断言会失败：exp 未存储）")

    def test_add_exp_multiple_times_accumulates(self):
        """多次 add_exp 应累积"""
        self.dm.add_exp("user001", 10)
        self.dm.add_exp("user001", 15)
        self.dm.add_exp("user001", 20)
        pet = self.dm.get_pet("user001")
        self.assertEqual(pet.exp, 45)

    def test_add_exp_to_nonexistent_pet(self):
        """不存在的宠物返回 None"""
        self.assertIsNone(self.dm.add_exp("user999", 100))

    # ── 升级触发 ──
    def test_single_level_up(self):
        """足够经验触发一次升级"""
        pet = self.dm.add_exp("user001", 120)
        self.assertEqual(pet.level, 2)
        self.assertEqual(pet.exp, 20)
        self.assertEqual(pet.max_exp, 200)

        pet2 = self.dm.get_pet("user001")
        self.assertEqual(pet2.level, 2)
        self.assertEqual(pet2.exp, 20)

    def test_no_level_up_when_exp_insufficient(self):
        """经验不满不升级"""
        pet = self.dm.add_exp("user001", 99)
        self.assertEqual(pet.level, 1)
        self.assertEqual(pet.exp, 99)

    def test_exact_exp_for_level_up(self):
        """刚好满经验升级"""
        pet = self.dm.add_exp("user001", 100)
        self.assertEqual(pet.level, 2)
        self.assertEqual(pet.exp, 0)

    def test_chain_level_up(self):
        """大量经验连升多级"""
        # Lv.1→100, Lv.2→200, Lv.3→300 共需 600 升到 Lv.4
        pet = self.dm.add_exp("user001", 600)
        self.assertEqual(pet.level, 4)
        self.assertEqual(pet.exp, 0)

    def test_chain_level_up_with_overflow(self):
        """连升多级后溢出经验保留"""
        # 650: 100→Lv2(剩550), 200→Lv3(剩350), 300→Lv4(剩50)
        pet = self.dm.add_exp("user001", 650)
        self.assertEqual(pet.level, 4)
        self.assertEqual(pet.exp, 50)

    def test_level_up_bonus_stats(self):
        """升级后四属性各 +20"""
        self.dm.update_pet("user001", satiety=50, mood=50, health=50, energy=50)
        pet = self.dm.add_exp("user001", 100)
        self.assertEqual(pet.level, 2)
        self.assertEqual(pet.satiety, 70)
        self.assertEqual(pet.mood, 70)
        self.assertEqual(pet.health, 70)
        self.assertEqual(pet.energy, 70)

    def test_level_up_bonus_at_cap(self):
        """升级奖励不超过 100"""
        self.dm.update_pet("user001", satiety=95, mood=95, health=95, energy=95)
        pet = self.dm.add_exp("user001", 100)
        self.assertEqual(pet.level, 2)
        self.assertEqual(pet.satiety, 100)
        self.assertEqual(pet.mood, 100)
        self.assertEqual(pet.health, 100)
        self.assertEqual(pet.energy, 100)

    def test_massive_exp(self):
        """海量经验冲击高级别"""
        pet = self.dm.add_exp("user001", 100000)
        self.assertGreaterEqual(pet.level, 44)
        self.assertLess(pet.exp, pet.max_exp)


# ══════════════════════════════════════════════════════════════════════
# 4. 冷却系统
# ══════════════════════════════════════════════════════════════════════

class TestCooldown(TestDataManagerBase):
    """测试冷却设置与查询"""

    def setUp(self):
        super().setUp()
        cfg = {"emoji": "🐱", "name": "猫咪", "base_stats": {"satiety": 70, "mood": 70, "health": 80, "energy": 60}}
        self.dm.create_pet("user001", "张三", "cat", cfg)

    def test_no_cooldown_initially(self):
        self.assertEqual(self.dm.get_cooldown("user001", "feed"), 0.0)

    def test_set_and_check_cooldown(self):
        self.dm.set_cooldown("user001", "feed", 30)
        cd = self.dm.get_cooldown("user001", "feed")
        self.assertGreater(cd, 0)
        self.assertLess(cd, 30)

    def test_expired_cooldown(self):
        self.dm.set_cooldown("user001", "feed", -10)
        self.assertEqual(self.dm.get_cooldown("user001", "feed"), 0.0)

    def test_multiple_actions_independent(self):
        self.dm.set_cooldown("user001", "feed", 30)
        self.dm.set_cooldown("user001", "play", 45)
        self.assertGreater(self.dm.get_cooldown("user001", "feed"), 0)
        self.assertGreater(self.dm.get_cooldown("user001", "play"), 0)
        self.assertEqual(self.dm.get_cooldown("user001", "rest"), 0.0)

    def test_cooldown_cleared_on_delete(self):
        self.dm.set_cooldown("user001", "feed", 30)
        self.dm.delete_pet("user001")
        self.assertEqual(self.dm.get_cooldown("user001", "feed"), 0.0)


# ══════════════════════════════════════════════════════════════════════
# 5. 排行榜
# ══════════════════════════════════════════════════════════════════════

class TestLeaderboard(TestDataManagerBase):
    """测试排行榜增删查"""

    def setUp(self):
        super().setUp()
        cfg = {"emoji": "🐱", "name": "猫", "base_stats": {"satiety": 70, "mood": 70, "health": 80, "energy": 60}}
        self.dm.create_pet("user001", "张三", "cat", cfg)
        self.dm.create_pet("user002", "李四", "cat", cfg)

    def test_empty_leaderboard(self):
        self.assertEqual(self.dm.get_leaderboard(10), [])

    def test_leaderboard_sorting(self):
        self.dm.add_exp("user001", 350)  # → Lv.3, exp=50
        self.dm.add_exp("user002", 120)  # → Lv.2, exp=20
        pet1 = self.dm.get_pet("user001")
        pet2 = self.dm.get_pet("user002")
        self.dm.update_leaderboard(pet1)
        self.dm.update_leaderboard(pet2)

        board = self.dm.get_leaderboard(10)
        self.assertEqual(len(board), 2)
        self.assertEqual(board[0]["owner_id"], "user001")
        self.assertEqual(board[0]["level"], 3)
        self.assertEqual(board[1]["owner_id"], "user002")
        self.assertEqual(board[1]["level"], 2)

    def test_leaderboard_details(self):
        pet = self.dm.get_pet("user001")
        self.dm.update_leaderboard(pet)
        entry = self.dm.get_leaderboard(10)[0]
        self.assertEqual(entry["owner_id"], "user001")
        self.assertEqual(entry["owner_name"], "张三")
        self.assertEqual(entry["pet_name"], "猫")
        self.assertEqual(entry["emoji"], "🐱")
        self.assertIn("level", entry)
        self.assertIn("exp", entry)
        self.assertIn("coins", entry)

    def test_top_n_limit(self):
        pet = self.dm.get_pet("user001")
        self.dm.update_leaderboard(pet)
        self.assertEqual(len(self.dm.get_leaderboard(1)), 1)


# ══════════════════════════════════════════════════════════════════════
# 6. 属性衰减
# ══════════════════════════════════════════════════════════════════════

class TestDecay(TestDataManagerBase):
    """测试自然衰减"""

    def setUp(self):
        super().setUp()
        cfg = {"emoji": "🐱", "name": "猫咪", "base_stats": {"satiety": 70, "mood": 70, "health": 80, "energy": 60}}
        self.dm.create_pet("user001", "张三", "cat", cfg)

    def _set_last_update(self, user_id: str, timestamp: float):
        """直接修改 Redis 中 pet 的 last_update（绕过 update_pet 的自动覆盖）"""
        import src.data_manager as dm_mod
        pet = self.dm.get_pet(user_id)
        pet.last_update = timestamp
        dm_mod._redis_client.set(
            self.dm._pet_key(user_id),
            json.dumps(pet.to_dict(), ensure_ascii=False),
        )

    def test_no_decay_immediately(self):
        pet = self.dm.apply_decay("user001", {"interval": 10})
        self.assertEqual(pet.satiety, 70)
        self.assertEqual(pet.mood, 70)

    def test_decay_after_time(self):
        self._set_last_update("user001", time.time() - 3600)  # 60 分钟前
        pet = self.dm.apply_decay("user001", {"interval": 10})
        # 6 间隔: 饱食-18, 心情-12, 健康-3, 体力+6
        self.assertEqual(pet.satiety, 52)
        self.assertEqual(pet.mood, 58)
        self.assertEqual(pet.health, 77)
        self.assertEqual(pet.energy, 66)

    def test_decay_capped_at_10_intervals(self):
        self._set_last_update("user001", time.time() - 72000)
        pet = self.dm.apply_decay("user001", {"interval": 10})
        # 最多10间隔: 饱食-30, 心情-20, 健康-5, 体力+10
        self.assertEqual(pet.satiety, 40)
        self.assertEqual(pet.mood, 50)
        self.assertEqual(pet.health, 75)
        self.assertEqual(pet.energy, 70)

    def test_decay_floor_at_zero(self):
        self.dm.update_pet("user001", satiety=5, mood=5, health=2)
        self._set_last_update("user001", time.time() - 72000)
        pet = self.dm.apply_decay("user001", {"interval": 10})
        self.assertEqual(pet.satiety, 0)
        self.assertEqual(pet.mood, 0)
        self.assertEqual(pet.health, 0)

    def test_energy_recovery_ceiling(self):
        self.dm.update_pet("user001", energy=95)
        self._set_last_update("user001", time.time() - 3600)
        pet = self.dm.apply_decay("user001", {"interval": 10})
        self.assertEqual(pet.energy, 100)


# ══════════════════════════════════════════════════════════════════════
# 7. 改名
# ══════════════════════════════════════════════════════════════════════

class TestRename(TestDataManagerBase):
    """测试宠物改名"""

    def setUp(self):
        super().setUp()
        cfg = {"emoji": "🐱", "name": "猫咪", "base_stats": {"satiety": 70, "mood": 70, "health": 80, "energy": 60}}
        self.dm.create_pet("user001", "张三", "cat", cfg)

    def test_rename_persists(self):
        pet = self.dm.rename_pet("user001", "小花")
        self.assertEqual(pet.name, "小花")
        self.assertEqual(self.dm.get_pet("user001").name, "小花")

    def test_rename_nonexistent(self):
        self.assertIsNone(self.dm.rename_pet("user999", "不存在"))


# ══════════════════════════════════════════════════════════════════════
# 8. Pet 数据模型
# ══════════════════════════════════════════════════════════════════════

class TestPetModel(unittest.TestCase):
    """测试 Pet 数据类的属性和方法"""

    def test_max_exp_formula(self):
        pet = Pet(owner_id="u1", owner_name="t", name="t", pet_type="cat", emoji="🐱")
        self.assertEqual(pet.max_exp, 100)
        pet.level = 5
        self.assertEqual(pet.max_exp, 500)
        pet.level = 10
        self.assertEqual(pet.max_exp, 1000)

    def test_level_name_titles(self):
        pet = Pet(owner_id="u1", owner_name="t", name="t", pet_type="cat", emoji="🐱")
        cases = [
            (1, "🥚 宠物蛋"), (2, "🥚 宠物蛋"),
            (3, "🌟 幼年期"), (4, "🌟 幼年期"),
            (5, "⭐ 成长期"), (9, "⭐ 成长期"),
            (10, "💫 成熟期"), (19, "💫 成熟期"),
            (20, "🔥 完全体"), (34, "🔥 完全体"),
            (35, "👑 究极体"), (49, "👑 究极体"),
            (50, "🌌 传说级"), (79, "🌌 传说级"),
            (80, "✨ 神话级"), (99, "✨ 神话级"),
            (100, "💎 至尊级"),
        ]
        for level, expected in cases:
            pet.level = level
            self.assertEqual(pet.level_name, expected, f"Lv.{level}")

    def test_is_dead(self):
        pet = Pet(owner_id="u1", owner_name="t", name="t", pet_type="cat", emoji="🐱")
        pet.health, pet.satiety = 0, 50
        self.assertTrue(pet.is_dead)
        pet.health, pet.satiety = 50, 0
        self.assertTrue(pet.is_dead)
        pet.health, pet.satiety = 50, 50
        self.assertFalse(pet.is_dead)

    def test_to_dict_from_dict_roundtrip(self):
        pet = Pet(owner_id="user001", owner_name="张三", name="小猫咪",
                  pet_type="cat", emoji="🐱", level=5, exp=120)
        d = pet.to_dict()
        pet2 = Pet.from_dict(d)
        self.assertEqual(pet2.owner_id, "user001")
        self.assertEqual(pet2.name, "小猫咪")
        self.assertEqual(pet2.level, 5)
        self.assertEqual(pet2.exp, 120)


# ══════════════════════════════════════════════════════════════════════
# 9. 获取全部宠物 & update_pet 集成测试
# ══════════════════════════════════════════════════════════════════════

class TestIntegration(TestDataManagerBase):
    """集成测试"""

    def setUp(self):
        super().setUp()
        cfg = {"emoji": "🐱", "name": "猫咪", "base_stats": {"satiety": 70, "mood": 70, "health": 80, "energy": 60}}
        self.dm.create_pet("user001", "张三", "cat", cfg)

    def test_get_all_pets(self):
        cfg = {"emoji": "🐱", "name": "猫", "base_stats": {"satiety": 70, "mood": 70, "health": 80, "energy": 60}}
        self.dm.create_pet("u2", "B", "cat", cfg)
        self.dm.create_pet("u3", "C", "cat", cfg)
        pets = self.dm.get_all_pets()
        self.assertEqual(len(pets), 3)
        self.assertEqual({p.owner_id for p in pets}, {"user001", "u2", "u3"})

    def test_update_exp_and_attrs_together(self):
        """同时传 exp 和其他属性，升级和属性都生效"""
        current = self.dm.get_pet("user001")
        pet = self.dm.update_pet(
            "user001",
            satiety=current.satiety + 25,
            coins=current.coins - 5,
            total_feed=current.total_feed + 1,
            exp=current.exp + 120,
        )
        self.assertEqual(pet.level, 2)
        self.assertEqual(pet.exp, 20)
        self.assertEqual(pet.satiety, 100)  # 70+25=95, 升级+20→100
        self.assertEqual(pet.coins, 95)
        self.assertEqual(pet.total_feed, 1)

        pet2 = self.dm.get_pet("user001")
        self.assertEqual(pet2.level, 2)
        self.assertEqual(pet2.exp, 20)

    def test_upgrade_preserves_modified_attrs(self):
        """升级不覆盖非升级奖励属性（如 coins）"""
        current = self.dm.get_pet("user001")
        pet = self.dm.update_pet("user001", coins=200, exp=current.exp + 350)
        self.assertEqual(pet.level, 3)     # Lv.1→2(100)→3(200), 剩余 50
        self.assertEqual(pet.exp, 50)
        self.assertEqual(pet.coins, 200)   # 不被升级覆盖


if __name__ == "__main__":
    unittest.main(verbosity=2)
