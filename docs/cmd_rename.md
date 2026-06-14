# /改名 (rename) 指令详细流程

## 概述

给宠物改名（1-8 字符），更新 Redis 中的宠物名称和改名计数。纯文本回复，无截图。

## 调用链路

```
用户发送 "/改名 新名字"
    │
    ▼
handler.py :: handle_message()
    │  parse_command("/改名 新名字") → cmd="改名", arg="新名字"
    │  get_handler("改名") → ManageMixin.rename  (装饰器注册)
    │
    ▼
game/manage.py :: ManageMixin.rename(user_id, user_name, arg, group_id)
    │
    ├─ 1. 参数校验
    │     └─ arg 为空 或 len > 8 → 返回错误提示
    │
    ├─ 2. self.dm.get_pet(user_id)
    │     └─ data/pet_store.py → 无宠物 → 返回 "你还没有宠物"
    │
    ├─ 3. 记录旧名 old = pet.name
    │
    └─ 4. self.dm.rename_pet(user_id, new_name)
          └─ data/pet_store.py :: PetStoreMixin.rename_pet()
             ├─ get_pet() → 获取 Pet 对象
             ├─ pet.name = new_name
             ├─ pet.rename_count += 1
             └─ Redis SET qqbot:pet:{user_id} → JSON 序列化
```

## 涉及函数清单

| 函数 | 文件 | 作用 |
|------|------|------|
| `get_pet()` | data/pet_store.py | 获取宠物数据 |
| `rename_pet()` | data/pet_store.py | 更新宠物名称并保存 |
