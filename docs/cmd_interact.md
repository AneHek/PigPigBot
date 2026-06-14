# /喂食 /抚摸 /玩耍 /鼓励 /群训练 /亲密 指令详细流程

## /喂食 /抚摸 /玩耍 /鼓励 概述

群内互动命令，参数为游戏用户 ID。对目标宠物执行互动动作，发放经验、亲密度和群贡献点。双方各有冷却时间。纯文本回复。

## 互动调用链路（以 /喂食 为例）

```
用户发送 "/喂食 123"
    │
    ▼
handler.py :: handle_message()
    │  parse_command("/喂食 123") → cmd="喂食", arg="123"
    │  get_handler("喂食") → InteractMixin.feed  (装饰器注册)
    │
    ▼
game/interact.py :: InteractMixin.feed(user_id, user_name, arg, group_id)
    │
    └─ self._do_interact(user_id, "喂食", arg)
        │
        ├─ 1. self.dm.get_pet(user_id)
        │     └─ data/pet_store.py → 无宠物 → 返回 "你还没有宠物"
        │
        ├─ 2. target_id = self._resolve_target(arg)
        │     ├─ arg.isdigit() → target_game_uid = int(arg)
        │     └─ self.dm.get_user_by_game_uid(target_game_uid)
        │         └─ data/group.py → Redis GET qqbot:game_uid:{game_uid}
        │         └─ 未找到 → 返回 "请输入正确的游戏用户 ID"
        │
        ├─ 3. 校验
        │     ├─ target_id == user_id → 返回 "不能对自己使用互动"
        │     └─ self.dm.get_pet(target_id) → 对方无宠物 → 返回 "对方还没有宠物"
        │
        ├─ 4. cfg = INTERACT_CONFIG["喂食"]
        │     └─ {self_cd: 7200, target_cd: 3600, exp_mult: 30, intimacy: 1, contribution: 2}
        │
        ├─ 5. 发起方冷却检查
        │     ├─ cd_key = "interact_喂食"
        │     ├─ self.dm.get_cooldown(user_id, cd_key)
        │     │   └─ data/pet_store.py → Redis HGET qqbot:cooldown:{user_id} {cd_key}
        │     └─ cd_remaining > 0 → 返回 "喂食冷却中，剩 N 分钟"
        │
        ├─ 6. 目标方冷却检查
        │     ├─ target_cd_key = "interacted_喂食_{user_id}"
        │     ├─ self.dm.get_cooldown(target_id, target_cd_key)
        │     └─ cd_remaining > 0 → 返回 "对方喂食冷却中，剩 N 分钟"
        │
        ├─ 7. 设置冷却
        │     ├─ self.dm.set_cooldown(user_id, cd_key, 7200)
        │     │   └─ data/pet_store.py → Redis HSET qqbot:cooldown:{user_id} {cd_key} {timestamp}
        │     └─ self.dm.set_cooldown(target_id, target_cd_key, 3600)
        │
        ├─ 8. 发放经验
        │     ├─ exp = pet.level × 30
        │     └─ self.dm.add_exp(user_id, exp)
        │         └─ data/pet_store.py → update_pet() → 升级循环
        │
        ├─ 9. 增加亲密度（双向）
        │     └─ self.dm.add_intimacy(user_id, target_id, 1)
        │         └─ data/social.py :: SocialMixin.add_intimacy()
        │            ├─ Redis HINCRBY qqbot:intimacy:{user_id} {target_id} 1
        │            └─ Redis HINCRBY qqbot:intimacy:{target_id} {user_id} 1
        │
        ├─ 10. 增加群贡献点（双方）
        │     ├─ self.dm.add_contribution(user_id, 2)
        │     │   └─ data/social.py → Redis SET qqbot:contribution:{user_id}
        │     └─ self.dm.add_contribution(target_id, 2)
        │
        └─ 11. 构建回复文本
              ├─ 经验 +{exp}
              ├─ 亲密度 {new_intimacy}（{label}）
              │   └─ _intimacy_label() 判断等级变化（陌生→点头→熟识→信赖→挚友）
              └─ 群贡献点 +{contribution}（双方各得）
```

## /群训练 (grouptrain) 调用链路

```
用户发送 "/群训练"
    │
    ▼
handler.py :: handle_message()
    │  parse_command("/群训练") → cmd="群训练", arg=""
    │  get_handler("群训练") → InteractMixin.group_train  (装饰器注册)
    │
    ▼
game/interact.py :: InteractMixin.group_train(user_id, user_name, arg, group_id)
    │
    ├─ 1. self.dm.get_pet(user_id)
    │     └─ 无宠物 → 返回 "你还没有宠物"
    │
    ├─ 2. group_id 为空 → 返回 "群训练只能在群聊中使用"
    │
    ├─ 3. 冷却检查
    │     ├─ cd_key = "group_train"
    │     ├─ self.dm.get_cooldown(user_id, cd_key)
    │     └─ cd_remaining > 0 → 返回 "群训练冷却中，剩 N 分钟"
    │
    ├─ 4. self.dm.use_energy(user_id, 20)
    │     └─ data/energy.py → 行动力不足 → 返回 "行动力不足"
    │
    ├─ 5. self.dm.set_cooldown(user_id, "group_train", 21600)
    │
    ├─ 6. 发放奖励
    │     ├─ exp = pet.level × 80
    │     ├─ self.dm.add_exp(user_id, exp)
    │     └─ self.dm.add_contribution(user_id, 3)
    │
    └─ 7. 构建回复文本
          ├─ 经验 +{exp}
          ├─ 群贡献点 +3
          └─ 行动力 -20
```

## /亲密 (intimacy) 调用链路

```
用户发送 "/亲密"
    │
    ▼
handler.py :: handle_message()
    │  parse_command("/亲密") → cmd="亲密", arg=""
    │  get_handler("亲密") → InteractMixin.intimacy_list  (装饰器注册)
    │
    ▼
game/interact.py :: InteractMixin.intimacy_list(user_id, user_name, arg, group_id)
    │
    ├─ 1. self.dm.get_pet(user_id)
    │     └─ 无宠物 → 返回 "你还没有宠物"
    │
    ├─ 2. all_intimacy = self.dm.get_all_intimacy(user_id)
    │     └─ data/social.py → Redis HGETALL qqbot:intimacy:{user_id}
    │     └─ 空 → 返回 "还没有亲密度记录"
    │
    └─ 3. 构建回复文本
          ├─ 按亲密度降序排列
          ├─ 取 Top 10
          ├─ 每行：{name} — {value} ({label})
          │   └─ self.dm.get_pet(target_id) 获取对方昵称
          │   └─ _intimacy_label(value) 判断等级
          └─ 底部追加亲密度等级说明
```

## 涉及函数清单

| 函数 | 文件 | 作用 |
|------|------|------|
| `get_pet()` | data/pet_store.py | 检查宠物是否存在 |
| `get_user_by_game_uid()` | data/group.py | 游戏 ID → QQ ID 反查 |
| `get_cooldown()` | data/pet_store.py | 获取冷却剩余时间 |
| `set_cooldown()` | data/pet_store.py | 设置冷却时间戳 |
| `add_exp()` | data/pet_store.py | 增加经验并处理升级 |
| `add_intimacy()` | data/social.py | 双向增加亲密度 |
| `get_all_intimacy()` | data/social.py | 获取用户所有亲密度记录 |
| `add_contribution()` | data/social.py | 增加群贡献点（软上限 100000） |
| `use_energy()` | data/energy.py | 扣减行动力 |
