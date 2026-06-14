# /商店 /购买 /使用 /背包 指令详细流程

## /商店 (shop) 概述

查看金币商店和钻石商店的商品列表，以及当前持有的金币和钻石。纯文本回复。

## /商店 调用链路

```
用户发送 "/商店"
    │
    ▼
handler.py :: handle_message()
    │  parse_command("/商店") → cmd="商店", arg=""
    │  get_handler("商店") → EconomyMixin.shop_menu  (装饰器注册)
    │
    ▼
game/economy.py :: EconomyMixin.shop_menu(user_id, user_name, arg, group_id)
    │
    ├─ 1. self.dm.get_pet(user_id)
    │     └─ data/pet_store.py → 无宠物 → 返回 "你还没有宠物"
    │
    ├─ 2. self.dm.get_gold(user_id)
    │     └─ data/economy.py → Redis GET qqbot:gold:{user_id}
    │
    ├─ 3. self.dm.get_diamond(user_id)
    │     └─ data/economy.py → Redis GET qqbot:diamond:{user_id}
    │
    └─ 4. 遍历 SHOP_ITEMS / DIAMOND_ITEMS 构建商品列表文本
          └─ 静态配置来自 game/shop_config.py
```

## /购买 (buy) 概述

购买金币或钻石商品，支持别名（如"经验药水小"→ potion_s）。纯文本回复。

## /购买 调用链路

```
用户发送 "/购买 经验药水小 3"
    │
    ▼
handler.py :: handle_message()
    │  parse_command("/购买 经验药水小 3") → cmd="购买", arg="经验药水小 3"
    │  get_handler("购买") → EconomyMixin.shop_buy  (装饰器注册)
    │
    ▼
game/economy.py :: EconomyMixin.shop_buy(user_id, user_name, arg, group_id)
    │
    ├─ 1. self.dm.get_pet(user_id)
    │     └─ 无宠物 → 返回 "你还没有宠物"
    │
    ├─ 2. 解析参数
    │     ├─ parts = arg.split() → ["经验药水小", "3"]
    │     ├─ item_name = "经验药水小"
    │     └─ qty = 3（默认 1）
    │
    ├─ 3. item_id = resolve_item_id(item_name)
    │     └─ game/shop_config.py :: resolve_item_id()
    │        └─ 查表 ITEM_ALIASES → "potion_s"
    │        └─ 未找到 → 返回 "商品不存在"
    │
    ├─ 4. [金币商品] item_id in SHOP_ITEMS
    │     ├─ total_cost = gold_price × qty
    │     ├─ bought = self.dm.get_shop_buy_count(user_id, item_id)
    │     │   └─ data/economy.py → Redis GET qqbot:shop_buy:{user_id}:{item}:{date}
    │     ├─ bought + qty > daily_limit → 返回 "限购已达上限"
    │     ├─ self.dm.use_gold(user_id, total_cost)
    │     │   └─ data/economy.py → Redis DECRBY qqbot:gold:{user_id}
    │     │   └─ 余额不足 → 返回 "金币不足"
    │     ├─ self.dm.add_item(user_id, item_id, qty)
    │     │   └─ data/economy.py → Redis INCRBY qqbot:item:{user_id}:{item_id}
    │     └─ self.dm.incr_shop_buy(user_id, item_id, qty)
    │         └─ data/economy.py → Redis INCRBY + EXPIRE 24h
    │
    └─ 5. [钻石商品] item_id in DIAMOND_ITEMS
          ├─ 逻辑同上，使用 use_diamond / add_diamond
          └─ 限购 key 前缀 "d_" 区分金币/钻石限购
```

## /使用 (use) 概述

使用消耗品（经验药水、行动力药水），发放对应效果。纯文本回复。

## /使用 调用链路

```
用户发送 "/使用 经验药水小 2"
    │
    ▼
handler.py :: handle_message()
    │  parse_command("/使用 经验药水小 2") → cmd="使用", arg="经验药水小 2"
    │  get_handler("使用") → EconomyMixin.use_item_cmd  (装饰器注册)
    │
    ▼
game/economy.py :: EconomyMixin.use_item_cmd(user_id, user_name, arg, group_id)
    │
    ├─ 1. self.dm.get_pet(user_id)
    │     └─ 无宠物 → 返回 "你还没有宠物"
    │
    ├─ 2. 解析参数 + resolve_item_id()
    │     └─ 同 /购买 流程
    │
    ├─ 3. 每日使用次数检查
    │     ├─ current_count = self.dm.get_use_item_count(user_id, item_id)
    │     │   └─ data/economy.py → Redis GET qqbot:use_item:{user_id}:{item}:{date}
    │     └─ current_count + qty > daily_limit → 返回 "使用次数已达上限"
    │
    ├─ 4. self.dm.use_item(user_id, item_id, qty)
    │     └─ data/economy.py → Redis DECRBY qqbot:item:{user_id}:{item_id}
    │     └─ 数量不足 → 返回 "你没有该物品"
    │
    ├─ 5. self.dm.incr_use_item(user_id, item_id, qty)
    │     └─ data/economy.py → Redis INCRBY + EXPIRE 24h
    │
    └─ 6. 发放效果
          ├─ [经验药水] self.dm.add_exp(user_id, exp × qty)
          │   └─ data/pet_store.py → update_pet() → 升级循环
          └─ [行动力药水] self.dm.add_energy(user_id, energy × qty)
              └─ data/energy.py → Redis HSET qqbot:energy:{user_id}
```

## /背包 (bag) 概述

列出当前持有的所有物品及数量。纯文本回复。

## /背包 调用链路

```
用户发送 "/背包"
    │
    ▼
handler.py :: handle_message()
    │  parse_command("/背包") → cmd="背包", arg=""
    │  get_handler("背包") → EconomyMixin.bag_list  (装饰器注册)
    │
    ▼
game/economy.py :: EconomyMixin.bag_list(user_id, user_name, arg, group_id)
    │
    ├─ 1. self.dm.get_pet(user_id)
    │     └─ 无宠物 → 返回 "你还没有宠物"
    │
    ├─ 2. items = self.dm.get_all_items(user_id)
    │     └─ data/economy.py :: EconomyMixin.get_all_items()
    │        └─ Redis SCAN qqbot:item:{user_id}:* → 遍历所有物品 key
    │        └─ 过滤 count > 0 的物品
    │
    └─ 3. 构建回复文本
          ├─ 空背包 → "背包空空如也~"
          └─ 遍历 items → 查 USE_ITEMS 映射中文名 → 逐行输出
```

## 涉及函数清单

| 函数 | 文件 | 作用 |
|------|------|------|
| `get_pet()` | data/pet_store.py | 检查宠物是否存在 |
| `get_gold()` | data/economy.py | 获取金币余额 |
| `get_diamond()` | data/economy.py | 获取钻石余额 |
| `use_gold()` | data/economy.py | 扣除金币（余额不足返回 False） |
| `use_diamond()` | data/economy.py | 扣除钻石 |
| `add_item()` | data/economy.py | 增加物品数量 |
| `use_item()` | data/economy.py | 扣减物品数量 |
| `get_all_items()` | data/economy.py | 扫描用户所有物品 |
| `get_shop_buy_count()` | data/economy.py | 获取今日已购数量 |
| `incr_shop_buy()` | data/economy.py | 递增今日已购计数 |
| `get_use_item_count()` | data/economy.py | 获取今日已用数量 |
| `incr_use_item()` | data/economy.py | 递增今日已用计数 |
| `add_exp()` | data/pet_store.py | 增加经验并处理升级 |
| `add_energy()` | data/energy.py | 增加行动力 |
| `resolve_item_id()` | game/shop_config.py | 物品名/别名 → item_id |
