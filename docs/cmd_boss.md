# /boss 指令详细流程

## 概述

世界 Boss 系统入口命令，根据子命令分发到不同功能：
- 无参数 → Boss 状态（当前活跃 Boss、HP、排行）
- `攻击` → 参与战斗（返回两次消息：开始提示 + 战斗结果）
- `排行` → 伤害排行 Top 20
- `奖励` → 领取奖励

## /boss 调用链路

```
用户发送 "/boss 攻击"
    │
    ▼
handler.py :: handle_message()
    │  parse_command("/boss 攻击") → cmd="boss", arg="攻击"
    │  get_handler("boss") → BossMixin.boss  (装饰器注册)
    │
    ▼
game/boss.py :: BossMixin.boss(user_id, user_name, arg, group_id)
    │
    ├─ 参数分发
    │   ├─ arg 为空 → self._boss_status(group_id)
    │   ├─ arg == "攻击" → self._boss_attack(user_id, group_id)
    │   ├─ arg == "排行" → self._boss_rank(group_id)
    │   └─ arg == "奖励" → self._boss_claim(user_id, group_id)
    │
    └─ [攻击] self._boss_attack(user_id, group_id)
        │
        ├─ 1. self.dm.get_pet(user_id)
        │     └─ data/pet_store.py → 无宠物 → 返回 "你还没有宠物"
        │
        ├─ 2. 训练状态检查
        │     └─ pet.training → 返回 "训练中无法攻击 Boss"
        │
        ├─ 3. active = get_active_boss()
        │     └─ game/boss_config.py → 根据当前时间判断活跃 Boss
        │     └─ 无活跃 Boss → 返回 "当前没有活跃的世界 Boss"
        │
        ├─ 4. 冷却检查
        │     ├─ cd_key = "boss_attack_{boss_id}"
        │     ├─ self.dm.get_cooldown(user_id, cd_key)
        │     │   └─ data/pet_store.py → Redis HGET qqbot:cooldown:{user_id}
        │     └─ cd_remaining > 0 → 返回 "攻击冷却中，剩 N 秒"
        │
        ├─ 5. 扣减行动力
        │     └─ self.dm.use_energy(user_id, 20)
        │         └─ data/energy.py → 不足 → 返回 "行动力不足"
        │
        ├─ 6. 等级检查（仅警告，不拦截）
        │     └─ pet.level < min_level → 返回 "推荐等级 Lv.N+"
        │
        ├─ 7. 初始化 Boss HP
        │     ├─ hp = self.dm.get_boss_hp(boss_id)
        │     │   └─ data/boss_store.py → Redis GET qqbot:boss:{boss_id}:{date}:hp
        │     └─ hp == 0 → self.dm.set_boss_hp(boss_id, info["hp"])
        │
        ├─ 8. 生成 Boss 属性
        │     ├─ monster_stats = calc_stats(species_id, stage, min_level, ivs)
        │     │   └─ pet/stats.py → 属性公式计算
        │     └─ monster_dict = {owner_id: "boss", name, hp: min(hp, max_hp), ...}
        │
        ├─ 9. 设置冷却 + 执行战斗
        │     ├─ self.dm.set_cooldown(user_id, cd_key, 10)
        │     └─ result = battle_engine.run(pet.to_dict(), monster_dict, max_duration=30)
        │         └─ battle/engine.py → 30 秒实时战斗模拟
        │
        ├─ 10. 伤害统计
        │     ├─ total_damage = sum(ev.damage for ev in result.events if ev.source == pet.name)
        │     ├─ self.dm.add_boss_damage(boss_id, user_id, total_damage)
        │     │   └─ data/boss_store.py → Redis ZINCRBY qqbot:boss:{boss_id}:{date}:dmg
        │     └─ new_hp = self.dm.decr_boss_hp(boss_id, total_damage)
        │         └─ data/boss_store.py → Redis DECRBY qqbot:boss:{boss_id}:{date}:hp
        │
        ├─ 11. 排名计算
        │     ├─ rank = self.dm.get_boss_rank(boss_id)
        │     │   └─ data/boss_store.py → Redis ZREVRANGE qqbot:boss:{boss_id}:{date}:dmg
        │     └─ user_rank = next((i+1 for i, (uid, _) in enumerate(rank) if uid == user_id))
        │
        └─ 12. 构建回复
              ├─ start_msg = "⚔️ 你对 {boss_name} 发起了攻击！"
              ├─ result_msg = 本次伤害 + 剩余 HP + 排名 + 行动力
              └─ [Boss 被击杀] self.dm.set_boss_last_kill(boss_id, user_id)
                  └─ 追加 "Boss 已被击杀！"
              └─ 返回 [start_msg, result_msg]
```

## /boss 排行 调用链路

```
用户发送 "/boss 排行"
    │
    ▼
game/boss.py :: BossMixin._boss_rank(group_id)
    │
    ├─ 1. active = get_active_boss()
    │     └─ 无活跃 Boss → 返回 "当前没有活跃的世界 Boss"
    │
    ├─ 2. rank = self.dm.get_boss_rank(boss_id, 20)
    │     └─ data/boss_store.py → Redis ZREVRANGE ... WITHSCORES
    │
    └─ 3. 构建排行文本
          ├─ 空 → "暂无参与者"
          └─ 遍历 → 🥇🥈🥉 + 数字序号 + 伤害值
```

## /boss 奖励 调用链路

```
用户发送 "/boss 奖励"
    │
    ▼
game/boss.py :: BossMixin._boss_claim(user_id, group_id)
    │
    ├─ 1. self.dm.get_pet(user_id)
    │     └─ 无宠物 → 返回 "你还没有宠物"
    │
    ├─ 2. active = get_active_boss()
    │     └─ 无活跃 Boss → 返回 "当前没有活跃的世界 Boss"
    │
    ├─ 3. self.dm.is_boss_claimed(boss_id, user_id)
    │     └─ data/boss_store.py → Redis SISMEMBER qqbot:boss:{boss_id}:{date}:claimed
    │     └─ 已领取 → 返回 "你已经领取过本次 Boss 奖励了"
    │
    ├─ 4. damage = self.dm.get_boss_damage(boss_id, user_id)
    │     └─ data/boss_store.py → Redis ZSCORE qqbot:boss:{boss_id}:{date}:dmg
    │     └─ damage <= 0 → 返回 "你未参与本次 Boss 战斗"
    │
    ├─ 5. 排名计算 + 经验倍率
    │     ├─ rank = self.dm.get_boss_rank(boss_id)
    │     ├─ user_rank = next((i+1 for i, (uid, _) in enumerate(rank) if uid == user_id))
    │     └─ 查表 EXP_REWARDS → exp_mult
    │         ├─ Top 1 → 5000
    │         ├─ Top 2~3 → 3000
    │         ├─ Top 4~10 → 1500
    │         ├─ Top 11~30% → 600
    │         ├─ Top 30~60% → 300
    │         └─ Top 60~100% → 100
    │
    ├─ 6. 发放经验
    │     ├─ exp = pet.level × exp_mult
    │     └─ self.dm.add_exp(user_id, exp)
    │
    └─ 7. self.dm.mark_boss_claimed(boss_id, user_id)
          └─ data/boss_store.py → Redis SADD qqbot:boss:{boss_id}:{date}:claimed
```

## 涉及函数清单

| 函数 | 文件 | 作用 |
|------|------|------|
| `get_pet()` | data/pet_store.py | 检查宠物是否存在 |
| `get_cooldown()` | data/pet_store.py | 获取冷却剩余时间 |
| `set_cooldown()` | data/pet_store.py | 设置冷却时间戳 |
| `use_energy()` | data/energy.py | 扣减行动力 |
| `get_energy()` | data/energy.py | 获取当前行动力 |
| `get_boss_hp()` | data/boss_store.py | 获取 Boss 当前 HP |
| `set_boss_hp()` | data/boss_store.py | 设置 Boss HP |
| `decr_boss_hp()` | data/boss_store.py | 扣减 Boss HP |
| `add_boss_damage()` | data/boss_store.py | 累加玩家伤害 |
| `get_boss_damage()` | data/boss_store.py | 获取玩家累计伤害 |
| `get_boss_rank()` | data/boss_store.py | 获取伤害排行 |
| `get_boss_rank_count()` | data/boss_store.py | 获取参与人数 |
| `is_boss_claimed()` | data/boss_store.py | 检查是否已领奖 |
| `mark_boss_claimed()` | data/boss_store.py | 标记已领奖 |
| `set_boss_last_kill()` | data/boss_store.py | 记录最后一击 |
| `add_exp()` | data/pet_store.py | 增加经验并处理升级 |
| `calc_stats()` | pet/stats.py | 生成 Boss 属性 |
| `BattleEngine.run()` | battle/engine.py | 运行 30 秒战斗模拟 |
| `get_active_boss()` | game/boss_config.py | 根据时间判断活跃 Boss |
