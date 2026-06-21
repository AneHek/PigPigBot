# gameplay.md — 副本敌方被动设计稿

## 一、设计原则

1. **副本 1（萌新猪舍）**：敌方**无被动**，新手友好。
2. **副本 2~7**：敌方根据章节等级区间递增被动数量与等级。
3. **BOSS 关**比普通关多 1 个被动或更高等级。
4. **隐藏关（仅第 7 章）**：拥有最高等级被动配置。
5. 所有敌方被动均从 `PASSIVE_SKILLS`（28 种）中选取，复用玩家被动体系。

## 二、被动数量梯度

| 章节 | 等级区间 | 普通关被动数 | BOSS 关被动数 | 隐藏关被动数 |
|------|----------|-------------|-------------|-------------|
| 1 | 1-14 | 0 | 0 | — |
| 2 | 15-29 | 1~2 | 2 | — |
| 3 | 30-44 | 1~2 | 3 | — |
| 4 | 45-59 | 2~3 | 3 | — |
| 5 | 60-74 | 2~3 | 4 | — |
| 6 | 75-89 | 3~4 | 4 | — |
| 7 | 90-100 | 4 | 4 | 4（高等级） |

## 三、各章节详细配置

### 第 2 章：翠玉猪林（Lv.15-29）

| 关卡 | 被动技能 | 等级 | 效果说明 |
|------|---------|------|---------|
| 2-1 杂兵关 | 坚韧体魄(PS_D01) | Lv.2 | HP +4% |
| 2-2 连续关 | 坚韧体魄(PS_D01) | Lv.2 | HP +4% |
| 2-3 陷阱关 | 坚韧体魄(PS_D01) + 蛮力印记(PS_A01) | Lv.3 + Lv.2 | HP +5%, ATK +4.2% |
| 2-BOSS | 坚韧体魄(PS_D01) + 蛮力印记(PS_A01) | Lv.3 + Lv.3 | HP +5%, ATK +5.4% |

### 第 3 章：进化之塔（Lv.30-44）

| 关卡 | 被动技能 | 等级 | 效果说明 |
|------|---------|------|---------|
| 3-1 杂兵关 | 蛮力印记(PS_A01) | Lv.3 | ATK +5.4% |
| 3-2 连续关 | 蛮力印记(PS_A01) + 敏捷步伐(PS_S01) | Lv.3 + Lv.2 | ATK +5.4%, SPD +2.6% |
| 3-3 陷阱关 | 蛮力印记(PS_A01) + 铁壁(PS_D02) | Lv.3 + Lv.3 | ATK +5.4%, DEF +5% |
| 3-BOSS | 蛮力印记(PS_A01) + 铁壁(PS_D02) + 敏捷步伐(PS_S01) | Lv.4 + Lv.3 + Lv.3 | ATK +6.6%, DEF +5%, SPD +3.2% |

### 第 4 章：深渊之底（Lv.45-59）

| 关卡 | 被动技能 | 等级 | 效果说明 |
|------|---------|------|---------|
| 4-1 杂兵关 | 暴击精通(PS_A03) + 减伤护体(PS_D04) | Lv.3 + Lv.2 | CRIT_DMG +8.6%, DMG_REDUCE +2.6% |
| 4-2 连续关 | 暴击精通(PS_A03) + 减伤护体(PS_D04) | Lv.3 + Lv.3 | CRIT_DMG +8.6%, DMG_REDUCE +3.2% |
| 4-3 陷阱关 | 暴击精通(PS_A03) + 减伤护体(PS_D04) + 吸血本能(PS_X01) | Lv.4 + Lv.3 + Lv.2 | CRIT_DMG +10.4%, DMG_REDUCE +3.2%, LIFESTEAL +1.4% |
| 4-BOSS | 暴击精通(PS_A03) + 减伤护体(PS_D04) + 吸血本能(PS_X01) | Lv.5 + Lv.4 + Lv.3 | CRIT_DMG +12.2%, DMG_REDUCE +3.8%, LIFESTEAL +1.8% |

### 第 5 章：星空之巅（Lv.60-74）

| 关卡 | 被动技能 | 等级 | 效果说明 |
|------|---------|------|---------|
| 5-1 杂兵关 | 破甲之力(PS_A04) + 格挡本能(PS_D05) | Lv.3 + Lv.3 | DEF_PEN +5%, BLOCK +10.8% |
| 5-2 连续关 | 破甲之力(PS_A04) + 格挡本能(PS_D05) + 先手优势(PS_S04) | Lv.4 + Lv.3 + Lv.2 | DEF_PEN +6%, BLOCK +10.8%, OPENING_SPD +8.6% |
| 5-3 陷阱关 | 破甲之力(PS_A04) + 格挡本能(PS_D05) + 先手优势(PS_S04) | Lv.4 + Lv.4 + Lv.3 | DEF_PEN +6%, BLOCK +12.2%, OPENING_SPD +10.4% |
| 5-BOSS | 破甲之力(PS_A04) + 格挡本能(PS_D05) + 先手优势(PS_S04) + 致命一击(PS_A07) | Lv.5 + Lv.5 + Lv.4 + Lv.3 | DEF_PEN +7%, BLOCK +13.6%, OPENING_SPD +12.2%, CRIT_BONUS +5% |

### 第 6 章：仙猪秘境（Lv.75-89）

| 关卡 | 被动技能 | 等级 | 效果说明 |
|------|---------|------|---------|
| 6-1 杂兵关 | 技能增幅(PS_A05) + 不屈意志(PS_D06) + 闪避反击(PS_S05) | Lv.4 + Lv.3 + Lv.3 | SKILL_DMG +7.6%, LAST_STAND +10.4%, DODGE_CTR +20.8% |
| 6-2 连续关 | 技能增幅(PS_A05) + 不屈意志(PS_D06) + 闪避反击(PS_S05) | Lv.4 + Lv.4 + Lv.3 | SKILL_DMG +7.6%, LAST_STAND +12.2%, DODGE_CTR +20.8% |
| 6-3 陷阱关 | 技能增幅(PS_A05) + 不屈意志(PS_D06) + 闪避反击(PS_S05) + 净化之体(PS_X04) | Lv.5 + Lv.4 + Lv.4 + Lv.3 | SKILL_DMG +8.8%, LAST_STAND +12.2%, DODGE_CTR +24.4%, DEBUFF_R +10.4% |
| 6-BOSS | 技能增幅(PS_A05) + 不屈意志(PS_D06) + 闪避反击(PS_S05) + 净化之体(PS_X04) | Lv.6 + Lv.5 + Lv.5 + Lv.4 | SKILL_DMG +10%, LAST_STAND +14%, DODGE_CTR +28%, DEBUFF_R +12.2% |

### 第 7 章：宇宙之心（Lv.90-100）

| 关卡 | 被动技能 | 等级 | 效果说明 |
|------|---------|------|---------|
| 7-1 杂兵关 | 致命一击(PS_A07) + 反刺甲(PS_D07) + 时间扭曲(PS_S06) + 混沌共鸣(PS_X06) | Lv.5 + Lv.4 + Lv.4 + Lv.3 | CRIT_BONUS +7%, THORNS +6%, SPD_FLAT +0.06, SKILL_NO_CD +13.6% |
| 7-2 连续关 | 致命一击(PS_A07) + 反刺甲(PS_D07) + 时间扭曲(PS_S06) + 混沌共鸣(PS_X06) | Lv.5 + Lv.5 + Lv.4 + Lv.3 | CRIT_BONUS +7%, THORNS +7%, SPD_FLAT +0.06, SKILL_NO_CD +13.6% |
| 7-3 陷阱关 | 战意沸腾(PS_A08) + 最后防线(PS_D08) + 时间扭曲(PS_S06) + 混沌共鸣(PS_X06) | Lv.5 + Lv.5 + Lv.5 + Lv.4 | RAGE_ATK +2.6%, REVIVE_HP +14%, SPD_FLAT +0.07, SKILL_NO_CD +15.4% |
| 7-BOSS | 战意沸腾(PS_A08) + 最后防线(PS_D08) + 时间扭曲(PS_S06) + 混沌共鸣(PS_X06) | Lv.7 + Lv.6 + Lv.6 + Lv.5 | RAGE_ATK +3.3%, REVIVE_HP +15.5%, SPD_FLAT +0.09, SKILL_NO_CD +17.2% |
| 7-HIDE | 战意沸腾(PS_A08) + 最后防线(PS_D08) + 时间扭曲(PS_S06) + 混沌共鸣(PS_X06) | Lv.8 + Lv.7 + Lv.7 + Lv.6 | RAGE_ATK +3.6%, REVIVE_HP +17%, SPD_FLAT +0.10, SKILL_NO_CD +19% |

## 四、配置存储

敌方被动配置存储在 `src/game/dungeon_config.py` 的 `ENEMY_PASSIVES` 字典中。

结构：
```python
ENEMY_PASSIVES = {
    chapter: {
        stage_id: {
            "passive_slots": {"1": "PS_XXX", "2": "PS_YYY", ...},
            "passive_levels": {"PS_XXX": level, "PS_YYY": level, ...},
        }
    }
}
```

通过 `get_enemy_passives(chapter, stage_id)` 函数获取，返回空字典表示无被动（第 1 章）。

## 五、战斗集成

所有战斗场景通过**统一修饰符系统**构建玩家战斗数据。详见 [battle_modifier_system.md](battle_modifier_system.md)。

| 场景 | 调用位置 | 说明 |
|------|---------|------|
| PvP 战斗 | `game/pvp.py` | 双方均调用 `_build_battle_dict()` |
| 世界 Boss | `game/boss.py` | 玩家调用 `_build_battle_dict()`，Boss 无修饰符 |
| 副本战斗 | `game/dungeon.py` | 玩家调用 `_build_battle_dict()`，敌方被动由 `get_enemy_passives()` 注入 |

`_build_battle_dict()` 通过 `_collect_passive_modifiers()` 将被动技能转换为统一修饰符列表，引擎层 `_apply_modifiers()` 统一应用。

未来新增属性来源（装备、药剂等），只需在 `game/base.py` 增加一个 `_collect_xxx_modifiers()` 方法并注册到管线，**引擎层零修改**，所有战斗入口自动兼容。

## 六、战斗时长规则

| 场景 | 最大时长 | 说明 |
|------|---------|------|
| 副本战斗 | 120 秒（引擎默认） | 不设额外上限，确保战斗完整进行至一方阵亡 |
| 世界 Boss | 30 秒（`BOSS_BATTLE_DURATION`） | 限时输出，鼓励玩家提升 DPS |
| PvP 战斗 | 120 秒（引擎默认） | 不设额外上限，确保完整对决 |

**设计理由**：副本是 PvE 内容，玩家应能完整体验战斗过程并击败敌人；世界 Boss 是限时 DPS 竞赛，需要时间压力来区分玩家实力。
