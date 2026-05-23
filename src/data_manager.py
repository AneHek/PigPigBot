"""
data_manager.py - 数据持久化管理模块
使用 Redis 存储用户数据
"""
import json
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict

import redis

from src.config import config

# Redis 连接配置
_redis_cfg = config["redis"]
_redis_client = redis.Redis(
    host=_redis_cfg["host"],
    port=_redis_cfg["port"],
    password=_redis_cfg["password"] or None,
    db=_redis_cfg.get("db", 0),
    decode_responses=True,
)

# Redis Key 前缀
KEY_PET = "qqbot:pet:{user_id}"
KEY_COOLDOWN = "qqbot:cooldown:{user_id}"
KEY_LEADERBOARD = "qqbot:leaderboard"

# 确保本地图片目录存在
_IMAGE_DIR = Path(__file__).parent.parent / config["image"]["dir"]
_IMAGE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Pet:
    """宠物数据模型"""
    owner_id: str                 # 主人 QQ 号
    owner_name: str               # 主人昵称
    name: str                     # 宠物名字
    pet_type: str                 # 宠物类型 ID
    emoji: str                    # 宠物表情
    level: int = 1                # 等级
    exp: int = 0                  # 当前经验
    satiety: int = 70             # 饱食度 (0-100)
    mood: int = 70                # 心情 (0-100)
    health: int = 80              # 健康 (0-100)
    energy: int = 60              # 体力 (0-100)
    coins: int = 100              # 金币
    create_time: float = field(default_factory=time.time)
    last_update: float = field(default_factory=time.time)
    total_feed: int = 0           # 累计喂食
    total_play: int = 0           # 累计玩耍
    total_work: int = 0           # 累计打工
    total_train: int = 0          # 累计训练

    @property
    def max_exp(self) -> int:
        """当前等级升级所需经验"""
        return 100 * self.level

    @property
    def level_name(self) -> str:
        """等级称号"""
        titles = [
            (1, "🥚 宠物蛋"),
            (3, "🌟 幼年期"),
            (5, "⭐ 成长期"),
            (10, "💫 成熟期"),
            (20, "🔥 完全体"),
            (35, "👑 究极体"),
            (50, "🌌 传说级"),
            (80, "✨ 神话级"),
            (100, "💎 至尊级"),
        ]
        for lv, title in reversed(titles):
            if self.level >= lv:
                return title
        return "🥚 宠物蛋"

    @property
    def is_dead(self) -> bool:
        """宠物是否死亡（饱食度和健康度都为 0）"""
        return self.health <= 0 or self.satiety <= 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Pet":
        return cls(**data)


class DataManager:
    """数据管理器：Redis 读写宠物数据

    注意：Redis 连接检查由 main.py 启动时统一完成，
    此处不做模块级阻塞，避免导入链在 logging 初始化前崩溃。
    """

    def __init__(self):
        self._connected = False
        try:
            _redis_client.ping()
            self._connected = True
        except Exception:
            pass  # 由 main.py 预检 + 实际调用时自然报错

    # ── 宠物数据操作 ──

    def _pet_key(self, user_id: str) -> str:
        return KEY_PET.format(user_id=user_id)

    def _cooldown_key(self, user_id: str) -> str:
        return KEY_COOLDOWN.format(user_id=user_id)

    def has_pet(self, user_id: str) -> bool:
        return _redis_client.exists(self._pet_key(user_id)) > 0

    def get_pet(self, user_id: str) -> Optional[Pet]:
        data = _redis_client.get(self._pet_key(user_id))
        if data is None:
            return None
        return Pet.from_dict(json.loads(data))

    def create_pet(self, user_id: str, user_name: str, pet_type_id: str,
                   pet_config: dict) -> Pet:
        """创建新宠物"""
        emoji = pet_config["emoji"]
        base = pet_config["base_stats"]
        pet = Pet(
            owner_id=user_id,
            owner_name=user_name,
            name=pet_config["name"],
            pet_type=pet_type_id,
            emoji=emoji,
            satiety=base["satiety"],
            mood=base["mood"],
            health=base["health"],
            energy=base["energy"],
        )
        _redis_client.set(self._pet_key(user_id), json.dumps(pet.to_dict(), ensure_ascii=False))
        return pet

    def delete_pet(self, user_id: str) -> bool:
        """遗弃宠物"""
        key = self._pet_key(user_id)
        if _redis_client.exists(key):
            _redis_client.delete(key)
            # 同时删除冷却数据和排行榜数据
            _redis_client.delete(self._cooldown_key(user_id))
            _redis_client.zrem(KEY_LEADERBOARD, user_id)
            return True
        return False

    def update_pet(self, user_id: str, **kwargs) -> Optional[Pet]:
        """更新宠物属性并自动保存"""
        pet = self.get_pet(user_id)
        if pet is None:
            return None
        for k, v in kwargs.items():
            if hasattr(pet, k):
                setattr(pet, k, v)
        pet.last_update = time.time()
        # 限制属性范围
        for attr in ["satiety", "mood", "health", "energy"]:
            val = getattr(pet, attr, 50)
            setattr(pet, attr, max(0, min(100, val)))

        # 检查升级
        while pet.exp >= pet.max_exp:
            pet.exp -= pet.max_exp
            pet.level += 1
            pet.satiety = min(100, pet.satiety + 20)
            pet.mood = min(100, pet.mood + 20)
            pet.health = min(100, pet.health + 20)
            pet.energy = min(100, pet.energy + 20)

        _redis_client.set(self._pet_key(user_id), json.dumps(pet.to_dict(), ensure_ascii=False))
        return pet

    def add_exp(self, user_id: str, amount: int) -> Optional[Pet]:
        """增加经验"""
        pet = self.get_pet(user_id)
        if pet is None:
            return None
        return self.update_pet(user_id, exp=pet.exp + amount)

    # ── 冷却操作 ──

    def get_cooldown(self, user_id: str, action: str) -> float:
        """获取冷却剩余秒数，0 表示可用"""
        raw = _redis_client.hget(self._cooldown_key(user_id), action)
        if raw is None:
            return 0.0
        cd = float(raw)
        return max(0.0, cd - time.time())

    def set_cooldown(self, user_id: str, action: str, seconds: int):
        """设置冷却时间"""
        _redis_client.hset(
            self._cooldown_key(user_id),
            action,
            time.time() + seconds,
        )

    # ── 排行榜操作 ──

    def update_leaderboard(self, pet: Pet):
        """更新排行榜（Redis Sorted Set，按 level+exp/1000 复合分排序）"""
        score = pet.level + pet.exp / 1000.0
        _redis_client.zadd(KEY_LEADERBOARD, {pet.owner_id: score})
        # 在 Hash 中存储排行榜用户详情
        detail = {
            "owner_id": pet.owner_id,
            "owner_name": pet.owner_name,
            "pet_name": pet.name,
            "emoji": pet.emoji,
            "level": str(pet.level),
            "exp": str(pet.exp),
            "coins": str(pet.coins),
        }
        _redis_client.hset(f"{KEY_LEADERBOARD}:detail", pet.owner_id,
                           json.dumps(detail, ensure_ascii=False))

    def get_leaderboard(self, top_n: int = 10) -> list[dict]:
        """获取排行榜前 N 名"""
        top_users = _redis_client.zrevrange(KEY_LEADERBOARD, 0, top_n - 1)
        results = []
        for uid in top_users:
            raw = _redis_client.hget(f"{KEY_LEADERBOARD}:detail", uid)
            if raw:
                entry = json.loads(raw)
                entry["level"] = int(entry["level"])
                entry["exp"] = int(entry["exp"])
                entry["coins"] = int(entry["coins"])
                results.append(entry)
        return results

    # ── 衰减操作 ──

    def apply_decay(self, user_id: str, decay_config: dict) -> Optional[Pet]:
        """应用自然衰减"""
        pet = self.get_pet(user_id)
        if pet is None:
            return None
        elapsed = time.time() - pet.last_update
        intervals = elapsed / (decay_config["interval"] * 60)
        if intervals < 1:
            return pet
        intervals = min(intervals, 10)  # 最多衰减 10 次
        decay_satiety = int(intervals * 3)
        decay_mood = int(intervals * 2)
        decay_health = int(intervals * 0.5)
        decay_energy = -int(intervals * 1)  # 自然恢复体力

        pet.satiety = max(0, pet.satiety - decay_satiety)
        pet.mood = max(0, pet.mood - decay_mood)
        pet.health = max(0, pet.health - decay_health)
        pet.energy = min(100, pet.energy - decay_energy)
        pet.last_update = time.time()

        _redis_client.set(self._pet_key(user_id), json.dumps(pet.to_dict(), ensure_ascii=False))
        return pet

    # ── 其他操作 ──

    def get_all_pets(self) -> list[Pet]:
        """获取所有宠物（扫描 Redis keys）"""
        pets = []
        for key in _redis_client.scan_iter(match="qqbot:pet:*"):
            data = _redis_client.get(key)
            if data:
                pets.append(Pet.from_dict(json.loads(data)))
        return pets

    def rename_pet(self, user_id: str, new_name: str) -> Optional[Pet]:
        """重命名宠物"""
        pet = self.get_pet(user_id)
        if pet is None:
            return None
        pet.name = new_name
        _redis_client.set(self._pet_key(user_id), json.dumps(pet.to_dict(), ensure_ascii=False))
        return pet


# 全局单例
data_manager = DataManager()
