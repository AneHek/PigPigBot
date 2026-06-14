# /副本 /副本重置 指令详细流程

## /副本 (dungeon) 概述

副本系统入口命令，根据参数数量分发到不同子功能：
- 无参数 → 副本总览菜单
- 单参数（章节号）→ 章节关卡列表
- 双参数（章节号 + 关卡号）→ 挑战关卡

挑战关卡返回**两次消息**（list[str, str]）：战斗开始提示 + 战斗结果。

## /副本 调用链路

```
用户发送 "/副本 4 1"
    │
    ▼
handler.py :: handle_message()
    │  parse_command("/副本 4 1") → cmd="副本", arg="4 1"
    │  get_handler("副本") → DungeonMixin.dungeon  (装饰器注册)
    │
    ▼
game/dungeon.py :: DungeonMixin.dungeon(user_id, user_name, arg, group_id)
    │
    ├─ 1. self.dm.get_pet(user_id)
    │     └─ data/pet_store.py → 无宠物 → 返回 "你还没有宠物"
    │
    ├─ 2. 参数分发
    │     ├─ arg 为空 → self._dungeon_menu(user_id, pet)
    │     ├─ arg 为单数字 → self._dungeon_chapter(user_id, pet, ch)
    │     └─ arg 为 "数字 关卡" → self._dungeon_fight(user_id, pet, ch, stage_str)
    │
    └─ [挑战关卡] self._dungeon_fight(user_id, pet, ch, stage_str)
        │
        ├─ 3. 章节/关卡校验
        │     ├─ ch not in CHAPTERS → 返回 "章节不存在"
        │     ├─ stage_id = get_stage_id(stage_str)
        │     │   └─ game/dungeon_config.py → 查表 STAGES
        │     │   └─ 无效 → 返回 "关卡不存在"
        │     └─ is_chapter_unlocked(first_set, ch)
        │         └─ game/dungeon_config.py → 检查前一章是否全通关
        │         └─ 未解锁 → 返回 "第 N 章尚未解锁"
        │
        ├─ 4. 隐藏关卡特殊校验
        │     ├─ stage_id == "hide" && ch != 7 → 返回 "隐藏关卡仅在第 7 章可用"
        │     └─ stage_id == "hide" && "7-boss" not in first_set → 返回 "需要先通关 BOSS 关"
        │
        ├─ 5. 每日次数检查
        │     ├─ count = self.dm.get_dungeon_count(user_id, ch, stage_id)
        │     │   └─ data/dungeon_store.py → Redis GET qqbot:dungeon:{user_id}:{ch}:{stage}:{date}
        │     └─ count >= daily_limit → 返回 "该关卡今日次数已用完"
        │
        ├─ 6. 训练状态检查
        │     └─ pet.training → 返回 "训练中无法挑战副本"
        │
        ├─ 7. 扣减行动力
        │     └─ self.dm.use_energy(user_id, 5)
        │         └─ data/energy.py → 不足 → 返回 "行动力不足"
        │
        ├─ 8. 生成怪物属性
        │     ├─ level = random.randint(level_range[0], level_range[1])
        │     ├─ monster_species = f"P{random.choice(1..25):03d}"
        │     ├─ monster_stage = min(2, ch // 3)
        │     ├─ monster_stats = calc_stats(monster_species, monster_stage, level, ivs)
        │     │   └─ pet/stats.py → 属性公式计算
        │     ├─ monster_dict = {owner_id: "monster", name, species_id, ...}
        │     └─ [Ch≥2] get_enemy_passives(ch, stage_id) → 注入 passive_slots/passive_levels
        │         └─ game/dungeon_config.py → ENEMY_PASSIVES 查表
        │
        ├─ 8b. 注入玩家被动
        │     ├─ passive_slots = self.dm.get_passive_slots(user_id)
        │     │   └─ data/passive_store.py → Redis HGETALL qqbot:passive:{user_id}:slots
        │     ├─ [有装备] pet_dict["passive_slots"] = passive_slots
        │     └─ [有装备] pet_dict["passive_levels"] = {sid: get_passive_level(user_id, sid)}
        │
        ├─ 9. 执行战斗
        │     ├─ start_msg = "⚔️ 挑战 {chapter_name} {ch}-{stage_id} ..."
        │     └─ result = battle_engine.run(pet_dict, monster_dict)
        │         └─ battle/engine.py → 120 秒实时战斗模拟（含被动加成，无额外时间限制）
        │
        └─ 10. 胜利结算
              │
              ├─ is_first = "{ch}-{stage_id}" not in first_set
              │   └─ first_set = self.dm.get_dungeon_first_set(user_id)
              │       └─ data/dungeon_store.py → Redis SMEMBERS qqbot:dungeon:first:{user_id}
              │
              ├─ 经验发放
              │   ├─ exp_mult = stage_info["exp_mult"] × (first_mult if is_first else 1)
              │   ├─ exp = level × exp_mult
              │   └─ self.dm.add_exp(user_id, exp)
              │
              ├─ 材料发放
              │   ├─ stone = random.randint(mat["stone"][0], mat["stone"][1])
              │   ├─ rare = random.randint(mat["rare"][0], mat["rare"][1])
              │   ├─ gold = level × mat["gold_mult"]
              │   ├─ self.dm.add_gold(user_id, gold)
              │   ├─ self.dm.add_item(user_id, "stone", stone)
              │   └─ self.dm.add_item(user_id, "rare_shard", rare)
              │
              ├─ 次数递增 + 首通标记
              │   ├─ self.dm.incr_dungeon_count(user_id, ch, stage_id)
              │   │   └─ data/dungeon_store.py → Redis INCR + EXPIRE 24h
              │   └─ [首通] self.dm.mark_dungeon_first(user_id, ch, stage_id)
              │       └─ data/dungeon_store.py → Redis SADD qqbot:dungeon:first:{user_id}
              │
              ├─ 章节首通奖励检查
              │   ├─ updated_first = self.dm.get_dungeon_first_set(user_id)
              │   ├─ all(f"{ch}-{s}" in updated_first for s in all_stages)
              │   └─ 全部首通 → 发放 CHAPTER_FIRST_REWARDS[ch]
              │       ├─ self.dm.add_item(user_id, "stone", reward["stone"])
              │       ├─ self.dm.add_item(user_id, "rare_shard", reward["rare"])
              │       ├─ self.dm.add_item(user_id, "legend_shard", reward["legend"])
              │       └─ self.dm.add_gold(user_id, reward["gold"])
              │
              └─ 返回 [start_msg, result_msg]
                  └─ bot.py 收到 list → 分两次发送，间隔 1s
```

## /副本重置 (dungeonreset) 调用链路

```
用户发送 "/副本重置 3"
    │
    ▼
handler.py :: handle_message()
    │  parse_command("/副本重置 3") → cmd="副本重置", arg="3"
    │  get_handler("副本重置") → DungeonMixin.dungeon_reset  (装饰器注册)
    │
    ▼
game/dungeon.py :: DungeonMixin.dungeon_reset(user_id, user_name, arg, group_id)
    │
    ├─ 1. self.dm.get_pet(user_id)
    │     └─ 无宠物 → 返回 "你还没有宠物"
    │
    ├─ 2. 参数校验
    │     ├─ arg 非数字 → 返回 "请指定章节号"
    │     └─ ch not in CHAPTERS → 返回 "章节不存在"
    │
    ├─ 3. self.dm.is_dungeon_reset_today(user_id, ch)
    │     └─ data/dungeon_store.py → Redis EXISTS qqbot:dungeon_reset:{user_id}:{ch}:{date}
    │     └─ 已重置 → 返回 "该章节今日已重置过"
    │
    ├─ 4. self.dm.use_diamond(user_id, 10)
    │     └─ data/economy.py → 钻石不足 → 返回 "钻石不足"
    │
    ├─ 5. self.dm.reset_dungeon_counts(user_id, ch)
    │     └─ data/dungeon_store.py → Redis SCAN + DEL qqbot:dungeon:{user_id}:{ch}:*:{date}
    │
    └─ 6. self.dm.mark_dungeon_reset(user_id, ch)
          └─ data/dungeon_store.py → Redis SET + EXPIRE 24h
```

## 涉及函数清单

| 函数 | 文件 | 作用 |
|------|------|------|
| `get_pet()` | data/pet_store.py | 检查宠物是否存在 |
| `get_dungeon_first_set()` | data/dungeon_store.py | 获取用户所有首通标记 |
| `get_dungeon_count()` | data/dungeon_store.py | 获取关卡今日已用次数 |
| `incr_dungeon_count()` | data/dungeon_store.py | 递增关卡今日次数 |
| `mark_dungeon_first()` | data/dungeon_store.py | 标记关卡首通 |
| `is_dungeon_reset_today()` | data/dungeon_store.py | 检查章节今日是否已重置 |
| `reset_dungeon_counts()` | data/dungeon_store.py | 清除章节所有关卡今日次数 |
| `mark_dungeon_reset()` | data/dungeon_store.py | 标记章节今日已重置 |
| `use_energy()` | data/energy.py | 扣减行动力 |
| `use_diamond()` | data/economy.py | 扣减钻石 |
| `add_exp()` | data/pet_store.py | 增加经验并处理升级 |
| `add_gold()` | data/economy.py | 增加金币 |
| `add_item()` | data/economy.py | 增加物品 |
| `calc_stats()` | pet/stats.py | 生成怪物属性 |
| `BattleEngine.run()` | battle/engine.py | 运行 30 秒战斗模拟 |
| `is_chapter_unlocked()` | game/dungeon_config.py | 判断章节是否解锁 |
| `get_stage_id()` | game/dungeon_config.py | 关卡字符串 → stage_id |
| `get_enemy_passives()` | game/dungeon_config.py | 获取敌方被动配置（Ch1 无，Ch2+ 有） |
| `get_passive_slots()` | data/passive_store.py | 获取玩家已装备被动槽位 |
| `get_passive_level()` | data/passive_store.py | 获取被动技能等级 |
