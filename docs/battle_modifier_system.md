# 统一战斗修饰符系统（Battle Modifier System）

## 一、设计目标

解决"霰弹式修改"问题：当新增属性加成来源（装备、药剂、Buff 等）时，**战斗引擎层零修改**，只需在游戏层增加一个收集方法。

### 对比：重构前 vs 重构后

| 新增系统 | 重构前需改文件 | 重构后需改文件 |
|---------|--------------|--------------|
| 装备系统 | `models.py` + `base.py` + `engine.py` (3 处) | `base.py` (1 处) |
| 属性药剂 | `models.py` + `base.py` + `engine.py` (3 处) | `base.py` (1 处) |
| Buff 系统 | `models.py` + `base.py` + `engine.py` (3 处) | `base.py` (1 处) |

## 二、架构总览

```
┌─────────────────────────────────────────────────────────────┐
│  游戏层 (game/base.py)                                       │
│                                                             │
│  _build_battle_dict(user_id, pet)                            │
│    ├─ pet.to_dict()                                         │
│    ├─ _collect_passive_modifiers(user_id)  ← 被动技能       │
│    ├─ _collect_equipment_modifiers(user_id) ← 装备 (未来)   │
│    ├─ _collect_potion_modifiers(user_id)    ← 药剂 (未来)   │
│    └─ d["modifiers"] = [...]                                │
└──────────────────────────┬──────────────────────────────────┘
                           │ pet_dict（含 modifiers 列表）
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  引擎层 (battle/engine.py)                                   │
│                                                             │
│  BattleEngine.run(pet_a_dict, pet_b_dict)                   │
│    ├─ _create_battle_pet(dict) → BattlePet                  │
│    ├─ _collect_battle_modifiers(dict) → modifiers[]         │
│    └─ _apply_modifiers(bp, modifiers) → 属性加成            │
│                                                             │
│  ★ 引擎层不关心修饰符来源，只处理统一格式                      │
└─────────────────────────────────────────────────────────────┘
```

## 三、修饰符格式规范

每个修饰符是一个 dict，包含 3 个字段：

```python
{"stat": str, "value": float, "type": "pct" | "flat"}
```

| 字段 | 说明 | 示例 |
|------|------|------|
| `stat` | 目标属性名 | `"atk"`, `"hp"`, `"def"`, `"spd"`, `"crit"`, `"crit_dmg"`, `"eva"`, `"lifesteal"` |
| `value` | 数值 | `7.8`（百分比）或 `0.1`（比率） |
| `type` | 应用方式 | `"pct"` = 乘法叠加，`"flat"` = 加法叠加 |

### type 详解

**`"pct"`（百分比乘法）**：`属性值 *= (1 + value / 100)`

适用于：atk, hp, def, spd 等基础属性的百分比加成。

```
ATK=100 + 10% pct → 100 × 1.10 = 110
ATK=100 + 10% pct + 5% pct → 100 × 1.10 × 1.05 = 115.5（乘法叠加）
```

**`"flat"`（加法）**：`属性值 += value`

适用于：crit, eva（百分比加法）以及 crit_dmg, lifesteal（比率加法）。

```
CRIT=5 + 3 flat → 5 + 3 = 8%
CRIT_DMG=1.5 + 0.1 flat → 1.5 + 0.1 = 1.6（即 160%）
LIFESTEAL=0.05 + 0.02 flat → 0.05 + 0.02 = 0.07（即 7%）
```

### 各属性的推荐 type

| 属性 | 存储格式 | 推荐 type | value 含义 |
|------|---------|----------|-----------|
| `atk` | 绝对值 | `pct` | 百分比（10 = +10%） |
| `hp` | 绝对值 | `pct` | 百分比（10 = +10%） |
| `def` | 绝对值 | `pct` | 百分比（10 = +10%） |
| `spd` | 绝对值 | `pct` | 百分比（10 = +10%） |
| `crit` | 百分比（5 = 5%） | `flat` | 百分比（3 = +3%） |
| `crit_dmg` | 比率（1.5 = 150%） | `flat` | 比率（0.1 = +10%） |
| `eva` | 百分比（5 = 5%） | `flat` | 百分比（3 = +3%） |
| `lifesteal` | 比率（0.05 = 5%） | `flat` | 比率（0.02 = +2%） |

> 注：`atk`/`hp`/`def`/`spd` 也可用 `flat` 做绝对值加成（如装备 "+50 ATK"），引擎均支持。

## 四、核心组件详解

### 4.1 引擎层：`_apply_modifiers()`

位于 `battle/engine.py`，是**唯一**的属性加成应用逻辑。

```python
def _apply_modifiers(self, bp: BattlePet, modifiers: list[dict]):
    for mod in modifiers:
        stat = mod["stat"]
        value = mod["value"]
        mod_type = mod.get("type", "pct")

        if stat == "atk":
            if mod_type == "pct": bp.atk *= (1 + value / 100)
            else: bp.atk += value
        elif stat == "hp":
            bonus = bp.max_hp * value / 100 if mod_type == "pct" else value
            bp.max_hp += bonus; bp.hp += bonus
        elif stat == "def":
            if mod_type == "pct": bp.def_ *= (1 + value / 100)
            else: bp.def_ += value
        elif stat == "spd":
            if mod_type == "pct": bp.spd *= (1 + value / 100)
            else: bp.spd += value
            bp.attack_interval = 1.0 / max(bp.spd, 0.1)
        elif stat == "crit":    bp.crit += value
        elif stat == "crit_dmg": bp.crit_dmg += value
        elif stat == "eva":     bp.eva += value
        elif stat == "lifesteal": bp.lifesteal += value
```

**关键特性**：
- 来源无关：不关心修饰符来自被动、装备还是药剂
- 顺序应用：多个修饰符按列表顺序依次叠加
- 安全默认：`type` 缺省为 `"pct"`

### 4.2 引擎层：`_collect_battle_modifiers()`

从 pet_dict 中提取修饰符列表：

```python
def _collect_battle_modifiers(self, pet_dict: dict) -> list[dict]:
    return pet_dict.get("modifiers", [])
```

### 4.3 游戏层：`_build_battle_dict()`

位于 `game/base.py`，负责收集所有来源的修饰符并注入 pet dict：

```python
def _build_battle_dict(self, user_id: str, pet: Pet) -> dict:
    d = pet.to_dict()
    modifiers = []
    modifiers.extend(self._collect_passive_modifiers(user_id))
    # 未来扩展点：
    # modifiers.extend(self._collect_equipment_modifiers(user_id))
    # modifiers.extend(self._collect_potion_modifiers(user_id))
    if modifiers:
        d["modifiers"] = modifiers
    return d
```

### 4.4 游戏层：`_collect_passive_modifiers()`

被动技能收集器（已有实现）：

```python
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
```

### 4.5 战斗调用链

所有战斗场景（PvP / Boss / 副本）统一调用：

```
pvp.py      → self._build_battle_dict(challenger_id, pet_a)
boss.py     → self._build_battle_dict(user_id, pet)
dungeon.py  → self._build_battle_dict(user_id, pet)
```

敌方被动（副本怪物）仍通过 `dungeon_config.get_enemy_passives()` 直接注入 `monster_dict`，由引擎统一处理。

## 五、扩展指南：添加新属性来源

### 示例：添加装备系统

**只需 2 步，引擎零修改：**

#### 步骤 1：创建装备数据层和配置

```python
# src/game/equipment_config.py（新建）
EQUIPMENT = {
    "iron_sword": {"name": "铁剑", "stat": "atk", "value": 10, "type": "flat"},
    "steel_armor": {"name": "钢甲", "stat": "def", "value": 15, "type": "pct"},
    "swift_boots": {"name": "疾风靴", "stat": "spd", "value": 8, "type": "pct"},
    "crit_ring": {"name": "暴击戒指", "stat": "crit", "value": 5, "type": "flat"},
}

# src/data/equipment_store.py（新建）
# Redis 持久化：qqbot:equipment:{user_id}:slots → Hash
# 类似 passive_store.py 的结构
```

#### 步骤 2：在 `game/base.py` 添加收集方法

```python
# game/base.py — 新增一个方法 + 修改一行

def _build_battle_dict(self, user_id: str, pet: Pet) -> dict:
    d = pet.to_dict()
    modifiers = []
    modifiers.extend(self._collect_passive_modifiers(user_id))
    modifiers.extend(self._collect_equipment_modifiers(user_id))  # ← 新增一行
    if modifiers:
        d["modifiers"] = modifiers
    return d

def _collect_equipment_modifiers(self, user_id: str) -> list[dict]:
    from src.game.equipment_config import EQUIPMENT
    modifiers = []
    slots = self.dm.get_equipment_slots(user_id)
    for slot, item_id in slots.items():
        if item_id not in EQUIPMENT:
            continue
        info = EQUIPMENT[item_id]
        modifiers.append({
            "stat": info["stat"],
            "value": info["value"],
            "type": info["type"],
        })
    return modifiers
```

**完成。** 所有战斗场景（PvP / Boss / 副本）自动生效。

### 示例：添加属性药剂

```python
# game/base.py — 同样只需新增一个方法 + 一行调用

def _collect_potion_modifiers(self, user_id: str) -> list[dict]:
    active_buffs = self.dm.get_active_potion_buffs(user_id)
    modifiers = []
    for buff in active_buffs:
        modifiers.append({
            "stat": buff["stat"],
            "value": buff["value"],
            "type": buff.get("type", "pct"),
        })
    return modifiers
```

### 扩展检查清单

添加新属性来源时，确认以下事项：

| 检查项 | 说明 |
|--------|------|
| 新建配置文件 | 定义物品/效果的属性加成数据 |
| 新建数据层 | Redis 持久化（如需要） |
| 新建收集方法 | `_collect_xxx_modifiers()` in `game/base.py` |
| 注册到管线 | 在 `_build_battle_dict()` 中加一行 `extend` |
| 引擎层 | **无需修改** |
| Pet 模型 | **无需修改** |
| 战斗命令 | **无需修改**（pvp/boss/dungeon 不变） |

## 六、兼容性保障

### 旧数据兼容

| 机制 | 说明 |
|------|------|
| `Pet.from_dict()` | 过滤未知键 + dataclass 默认值，旧数据自动兼容新字段 |
| `modifiers` 缺省 | `pet_dict.get("modifiers", [])` → 无修饰符时返回空列表 |
| `type` 缺省 | `mod.get("type", "pct")` → 未指定时默认百分比乘法 |

### 新参数扩展兼容

| 场景 | 影响范围 |
|------|---------|
| 新增属性来源（装备/药剂/Buff） | 只改 `game/base.py` |
| 新增属性类型（如 `block_rate`） | 改 `engine.py` 的 `_apply_modifiers` + 对应收集方法 |
| 新增修饰符 type（如 `multiply`） | 改 `engine.py` 的 `_apply_modifiers` |

### 数学等价性

重构后的 `_apply_modifiers` 与原 `_apply_passive_skills` 数学等价：

| 属性 | 原逻辑 | 新逻辑 | 结果 |
|------|--------|--------|------|
| atk +7.8% | `atk *= 1.078` | `pct=7.8 → atk *= 1.078` | 等价 |
| hp +5% | `hp += max_hp * 0.05` | `pct=5 → bonus = max_hp * 0.05` | 等价 |
| crit_dmg +10% | `crit_dmg += 0.1` | `flat=0.1 → crit_dmg += 0.1` | 等价 |
| lifesteal +2% | `lifesteal += 0.02` | `flat=0.02 → lifesteal += 0.02` | 等价 |

## 七、文件清单

| 文件 | 职责 |
|------|------|
| `battle/engine.py` | `_collect_battle_modifiers()` + `_apply_modifiers()` |
| `game/base.py` | `_build_battle_dict()` + `_collect_passive_modifiers()` |
| `game/passive_config.py` | 被动技能配置表（`PASSIVE_SKILLS`） |
| `data/passive_store.py` | 被动技能数据持久化 |
| `game/pvp.py` | PvP 战斗入口（调用 `_build_battle_dict`） |
| `game/boss.py` | Boss 战斗入口（调用 `_build_battle_dict`） |
| `game/dungeon.py` | 副本战斗入口（调用 `_build_battle_dict`） |
| `test/test_passive.py` | 修饰符系统测试（`TestApplyModifiers` 等） |
