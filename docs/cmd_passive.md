# /被动 指令详细流程

## /被动 (passive) 概述

查看、装备、升级、重置被动技能。被动技能通过副本掉落获得，装备到 4 个槽位中，
在战斗中自动生效（属性加成/战斗特效）。消耗同名技能书可升级，最高 10 级。纯文本回复。

## /被动 调用链路

```
用户发送 "/被动"
    │
    ▼
handler.py :: handle_message()
    │  parse_command("/被动") → cmd="被动", arg=""
    │  get_handler("被动") → PassiveMixin.passive_cmd  (装饰器注册)
    │
    ▼
game/passive.py :: PassiveMixin.passive_cmd(user_id, user_name, arg, group_id)
    │
    ├─ 1. self.dm.get_pet(user_id)
    │     └─ 无宠物 → 返回 "你还没有宠物"
    │
    ├─ 2. 解析子命令
    │     ├─ 无参数 → _passive_list()
    │     ├─ "背包" → _passive_bag()
    │     ├─ "装备 <名> <槽>" → _passive_equip()
    │     ├─ "升级 <名>" → _passive_upgrade()
    │     ├─ "重置 <槽>" → _passive_reset()
    │     └─ 其他 → 返回帮助文本
    │
    ├─ 3a. _passive_list()
    │     ├─ self.dm.get_passive_slots(user_id)
    │     │   └─ data/passive_store.py → Redis HGETALL qqbot:passive:{user_id}:slots
    │     ├─ 遍历 4 个槽位，查询每个技能的等级和效果百分比
    │     └─ 构建回复文本
    │
    ├─ 3b. _passive_bag()
    │     ├─ self.dm.get_all_passive_bags(user_id)
    │     │   └─ data/passive_store.py → Redis KEYS qqbot:passive:{user_id}:bag:*
    │     └─ 列出所有技能书及数量
    │
    ├─ 3c. _passive_equip(name, slot)
    │     ├─ 解析技能名 → skill_id
    │     ├─ 检查背包中是否有该技能书
    │     ├─ 检查是否已在其他槽位装备
    │     ├─ self.dm.use_passive_bag() 消耗 1 本
    │     ├─ self.dm.set_passive_level() 设为 Lv.1
    │     └─ self.dm.set_passive_slot() 装备到槽位
    │
    ├─ 3d. _passive_upgrade(name)
    │     ├─ 查询当前等级和升级所需同名书数量
    │     ├─ self.dm.use_passive_bag() 消耗对应数量
    │     └─ self.dm.set_passive_level() 等级 +1
    │
    └─ 3e. _passive_reset(slot)
          ├─ 检查该槽位是否有技能
          ├─ 检查今日是否已重置
          ├─ self.dm.use_diamond() 消耗 5 钻石
          ├─ self.dm.clear_passive_slot() 卸下技能
          ├─ self.dm.add_passive_bag() 退还 1 本 Lv.1 技能书
          └─ self.dm.mark_passive_reset() 标记今日已重置
```

## 被动技能战斗接入

```
battle/engine.py :: BattleEngine.run()
    │
    ├─ _create_battle_pet() 创建 BattlePet
    ├─ _apply_passive_skills() 叠加被动技能属性加成
    │   ├─ 读取 pet_dict["passive_slots"] 和 pet_dict["passive_levels"]
    │   ├─ 查询 PASSIVE_SKILLS 配置表获取百分比值
    │   └─ 按 stat 类型叠加到对应属性（ATK/HP/DEF/SPD/CRIT/EVA 等）
    └─ 进入正常战斗循环
```

## 副本掉落被动技能书

```
game/dungeon.py :: _dungeon_fight()
    │
    ├─ 战斗胜利后
    ├─ 查询 CHAPTER_DROP_POOL[ch] 获取该章节掉落池
    ├─ 按 STAGE_DROP_RATE[stage_id] 概率判定是否掉落
    ├─ 首通额外按 STAGE_FIRST_BONUS_RATE[stage_id] 概率判定
    └─ self.dm.add_passive_bag() 发放技能书
```

## 涉及函数清单

| 函数 | 文件 | 作用 |
|------|------|------|
| `passive_cmd()` | game/passive.py | 被动技能命令入口 |
| `get_passive_slots()` | data/passive_store.py | 获取 4 个槽位装备 |
| `get_passive_level()` | data/passive_store.py | 获取技能等级 |
| `get_all_passive_bags()` | data/passive_store.py | 获取所有技能书库存 |
| `set_passive_slot()` | data/passive_store.py | 装备技能到槽位 |
| `clear_passive_slot()` | data/passive_store.py | 卸下槽位技能 |
| `add_passive_bag()` | data/passive_store.py | 增加技能书 |
| `use_passive_bag()` | data/passive_store.py | 消耗技能书 |
| `_apply_passive_skills()` | battle/engine.py | 战斗中叠加被动属性 |
