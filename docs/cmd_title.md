# /称号 指令详细流程

## 概述

称号系统入口命令，根据子命令分发到不同功能：
- 无参数 → 查看已拥有称号列表
- `装备 <称号名>` → 装备指定称号
- `卸下` → 卸下当前装备称号
- `购买 <称号名>` → 使用群贡献点购买称号

纯文本回复。

## /称号 调用链路

```
用户发送 "/称号 装备 进化大师"
    │
    ▼
handler.py :: handle_message()
    │  parse_command("/称号 装备 进化大师") → cmd="称号", arg="装备 进化大师"
    │  get_handler("称号") → TitleMixin.title_cmd  (装饰器注册)
    │
    ▼
game/title.py :: TitleMixin.title_cmd(user_id, user_name, arg, group_id)
    │
    ├─ 1. self.dm.get_pet(user_id)
    │     └─ data/pet_store.py → 无宠物 → 返回 "你还没有宠物"
    │
    ├─ 2. 参数分发
    │     ├─ arg 为空 → self._title_list(user_id)
    │     ├─ arg 以 "装备" 开头 → self._title_equip(user_id, title_name)
    │     ├─ arg == "卸下" → self._title_unequip(user_id)
    │     └─ arg 以 "购买" 开头 → self._title_buy(user_id, title_name)
    │
    └─ [装备] self._title_equip(user_id, "进化大师")
        │
        ├─ 3. self.dm.has_title(user_id, "进化大师")
        │     └─ data/social.py → Redis SISMEMBER qqbot:title:{user_id}
        │     └─ 未拥有 → 返回 "称号不存在"
        │
        ├─ 4. 过期检查
        │     ├─ expire_ts = self.dm.get_title_expire(user_id, "进化大师")
        │     │   └─ data/social.py → Redis GET qqbot:title:{user_id}:expire:{title}
        │     └─ expire_ts > 0 && now > expire_ts
        │         ├─ self.dm.remove_title(user_id, "进化大师")
        │         └─ 返回 "该称号已过期"
        │
        └─ 5. self.dm.equip_title(user_id, "进化大师")
              └─ data/social.py → Redis SET qqbot:title:{user_id}:equipped
```

## /称号（查看列表）调用链路

```
用户发送 "/称号"
    │
    ▼
game/title.py :: TitleMixin._title_list(user_id)
    │
    ├─ 1. titles = self.dm.get_titles(user_id)
    │     └─ data/social.py → Redis SMEMBERS qqbot:title:{user_id}
    │
    ├─ 2. equipped = self.dm.get_equipped_title(user_id)
    │     └─ data/social.py → Redis GET qqbot:title:{user_id}:equipped
    │
    ├─ 3. [空列表] 返回可购买称号列表
    │     └─ 遍历 PURCHASABLE_TITLES → 名称 + 群贡献点价格
    │
    └─ 4. [非空] 构建称号列表
          ├─ 遍历 titles（按名称排序）
          ├─ 过期检查：expire_ts > 0 && now > expire_ts → 跳过
          ├─ 装备标记：title == equipped → " ← 已装备"
          ├─ 有效期显示：
          │   ├─ expire_ts > 0 → "⏳ {title}（剩 N 天）"
          │   └─ expire_ts == 0 → "⭐ {title}（永久）"
          └─ 底部追加操作提示
```

## /称号 购买 调用链路

```
用户发送 "/称号 购买 群聊之星"
    │
    ▼
game/title.py :: TitleMixin._title_buy(user_id, "群聊之星")
    │
    ├─ 1. 校验称号是否可购买
    │     └─ "群聊之星" not in PURCHASABLE_TITLES → 返回 "称号不存在"
    │
    ├─ 2. self.dm.has_title(user_id, "群聊之星")
    │     └─ 已拥有 → 返回 "你已经拥有称号"
    │
    ├─ 3. cost = PURCHASABLE_TITLES["群聊之星"]["cost"]  # 500
    │
    ├─ 4. self.dm.use_contribution(user_id, 500)
    │     └─ data/social.py :: SocialMixin.use_contribution()
    │         ├─ current = self.get_contribution(user_id)
    │         │   └─ Redis GET qqbot:contribution:{user_id}
    │         └─ current < 500 → 返回 "群贡献点不足"
    │
    └─ 5. self.dm.add_title(user_id, "群聊之星")
          └─ data/social.py → Redis SADD qqbot:title:{user_id}
```

## /称号 卸下 调用链路

```
用户发送 "/称号 卸下"
    │
    ▼
game/title.py :: TitleMixin._title_unequip(user_id)
    │
    ├─ 1. equipped = self.dm.get_equipped_title(user_id)
    │     └─ 无装备 → 返回 "当前没有装备称号"
    │
    └─ 2. self.dm.unequip_title(user_id)
          └─ data/social.py → Redis DEL qqbot:title:{user_id}:equipped
```

## 涉及函数清单

| 函数 | 文件 | 作用 |
|------|------|------|
| `get_pet()` | data/pet_store.py | 检查宠物是否存在 |
| `get_titles()` | data/social.py | 获取用户所有称号 |
| `has_title()` | data/social.py | 检查是否拥有指定称号 |
| `add_title()` | data/social.py | 添加称号 |
| `remove_title()` | data/social.py | 移除称号 |
| `equip_title()` | data/social.py | 装备称号 |
| `unequip_title()` | data/social.py | 卸下称号 |
| `get_equipped_title()` | data/social.py | 获取当前装备称号 |
| `get_title_expire()` | data/social.py | 获取称号过期时间戳 |
| `get_contribution()` | data/social.py | 获取群贡献点余额 |
| `use_contribution()` | data/social.py | 扣减群贡献点 |
