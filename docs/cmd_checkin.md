# /签到 /行动力 指令详细流程

## /签到 (checkin) 概述

每日签到，获取金币、钻石和道具奖励。7 天一个签到周期，断签重置为第 1 天。纯文本回复。

## /签到 调用链路

```
用户发送 "/签到"
    │
    ▼
handler.py :: handle_message()
    │  parse_command("/签到") → cmd="签到", arg=""
    │  get_handler("签到") → EconomyMixin.checkin  (装饰器注册)
    │
    ▼
game/economy.py :: EconomyMixin.checkin(user_id, user_name, arg, group_id)
    │
    ├─ 1. self.dm.get_pet(user_id)
    │     └─ data/pet_store.py → 无宠物 → 返回 "你还没有宠物"
    │
    ├─ 2. self.dm.is_checked_in_today(user_id)
    │     └─ data/checkin.py → Redis EXISTS qqbot:checkin:{user_id}:{date}
    │     └─ 已签到 → 返回 "今日已签到！当前连续签到 N 天"
    │
    ├─ 3. streak = self.dm.do_checkin(user_id)
    │     └─ data/checkin.py :: CheckinMixin.do_checkin()
    │        ├─ Redis GET qqbot:checkin:{user_id}:last_date
    │        │   └─ 判断与今日是否连续（diff == 1 → INCR streak，diff > 1 → SET streak=1）
    │        ├─ Redis SET qqbot:checkin:{user_id}:{date} "1" (TTL 24h)
    │        └─ Redis SET qqbot:checkin:{user_id}:last_date {today}
    │
    ├─ 4. day_in_cycle = ((streak - 1) % 7) + 1
    │     └─ 查表 CHECKIN_REWARDS[day_in_cycle] 获取当日奖励配置
    │
    ├─ 5. 发放奖励
    │     ├─ gold = reward["gold"]（固定值，不随等级变化）
    │     │   └─ self.dm.add_gold(user_id, gold)
    │     │       └─ data/economy.py → Redis INCRBY qqbot:gold:{user_id}
    │     ├─ diamond = reward["diamond"]（每日固定发放）
    │     │   └─ self.dm.add_diamond(user_id, diamond)
    │     │       └─ data/economy.py → Redis INCRBY qqbot:diamond:{user_id}
    │     └─ [可选] self.dm.add_item(user_id, item_id, qty)
    │         └─ data/economy.py → Redis INCRBY qqbot:item:{user_id}:{item_id}
    │
    └─ 6. 构建回复文本
          ├─ 签到天数 + 金币/钻石/物品明细
          ├─ 明日预告（day_in_cycle + 1）
          └─ 第 7 天预告（day_in_cycle < 7 时追加）
```

## /行动力 (energy) 概述

查看当前行动力状态、回复机制和消耗明细。纯文本回复。

## /行动力 调用链路

```
用户发送 "/行动力"
    │
    ▼
handler.py :: handle_message()
    │  parse_command("/行动力") → cmd="行动力", arg=""
    │  get_handler("行动力") → EconomyMixin.energy_status  (装饰器注册)
    │
    ▼
game/economy.py :: EconomyMixin.energy_status(user_id, user_name, arg, group_id)
    │
    ├─ 1. self.dm.get_pet(user_id)
    │     └─ 无宠物 → 返回 "你还没有宠物"
    │
    ├─ 2. energy = self.dm.get_energy(user_id)
    │     └─ data/energy.py :: EnergyMixin.get_energy()
    │        ├─ Redis HGETALL qqbot:energy:{user_id}
    │        │   └─ 首次访问 → 初始化 {value: 100, last_update: now}
    │        ├─ 计算自然回复：elapsed // 180 → regen 点数
    │        │   └─ value = min(100, value + regen)
    │        └─ 返回 {value: int, last_update: float}
    │
    └─ 3. 构建回复文本
          ├─ 当前行动力 / 100
          ├─ 回复机制说明
          ├─ 消耗明细列表
          └─ [行动力 < 100] 计算下次回复倒计时
              └─ next_regen_in = 180 - (elapsed % 180)
```

## 涉及函数清单

| 函数 | 文件 | 作用 |
|------|------|------|
| `get_pet()` | data/pet_store.py | 检查宠物是否存在 |
| `is_checked_in_today()` | data/checkin.py | 检查今日是否已签到 |
| `do_checkin()` | data/checkin.py | 执行签到：判断连续天数、写入签到标记 |
| `get_streak()` | data/checkin.py | 获取连续签到天数 |
| `add_gold()` | data/economy.py | 增加金币 |
| `add_diamond()` | data/economy.py | 增加钻石 |
| `add_item()` | data/economy.py | 增加物品 |
| `get_energy()` | data/energy.py | 获取行动力（含自然回复计算） |
