# /遗弃 (abandon) 指令详细流程

## 概述

遗弃当前宠物，从 Redis 中删除宠物数据、冷却时间和排行榜记录。纯文本回复，无截图。

## 调用链路

```
用户发送 "/遗弃"
    │
    ▼
handler.py :: handle_message()
    │  parse_command("/遗弃") → cmd="遗弃", arg=""
    │  get_handler("遗弃") → ManageMixin.abandon  (装饰器注册)
    │
    ▼
game/manage.py :: ManageMixin.abandon(user_id, user_name, arg, group_id)
    │
    ├─ 1. self.dm.get_pet(user_id)
    │     └─ data/pet_store.py → 无宠物 → 返回 "你还没有宠物"
    │
    ├─ 2. 记录 pet.name 用于回复文本
    │
    └─ 3. self.dm.delete_pet(user_id)
          └─ data/pet_store.py :: PetStoreMixin.delete_pet()
             ├─ Redis EXISTS qqbot:pet:{user_id}
             ├─ Redis DEL qqbot:pet:{user_id}
             ├─ Redis DEL qqbot:cooldown:{user_id}
             └─ Redis ZREM qqbot:leaderboard {user_id}
```

## 涉及函数清单

| 函数 | 文件 | 作用 |
|------|------|------|
| `get_pet()` | data/pet_store.py | 检查宠物是否存在 |
| `delete_pet()` | data/pet_store.py | 删除宠物+冷却+排行榜数据 |
