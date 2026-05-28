# /训练 (train) 指令详细流程

## 概述

开始挂机训练，记录训练开始时间。最少训练 10 分钟后才能通过 `/休息` 领取经验。返回截图+按钮消息。

## 调用链路

```
用户发送 "/训练"
    │
    ▼
handler.py :: handle_message()
    │  parse_command("/训练") → cmd="训练", arg=""
    │  handlers["训练"] → game.start_training(user_id)
    │
    ▼
pet_game.py :: PetGame.start_training(user_id)
    │
    ├─ 1. self.dm.get_pet(user_id)
    │     └─ 无宠物 → 返回错误
    │
    ├─ 2. 训练状态检查
    │     └─ pet.training == True → 返回 "正在训练中" + 已训练时长
    │
    ├─ 3. self.dm.start_training(user_id)
    │     └─ data_manager.py :: DataManager.start_training()
    │        ├─ get_pet() → 获取 Pet
    │        ├─ pet.training = True
    │        ├─ pet.training_start = time.time()
    │        ├─ pet.last_update = time.time()
    │        └─ Redis SET qqbot:pet:{user_id}
    │
    ├─ 4. calc_training_exp(pet.level, 10)
    │     └─ pet_stats.py :: calc_training_exp()
    │        └─ 公式: 50 * level * minutes
    │        └─ 计算 10 分钟预计获得经验
    │
    └─ 5. await self._build_pet_message(result, title, tip, rows)
          └─ title: "💪 {species_name}({game_uid}) 开始训练"
          └─ 调用 _generate_screenshot(result) 生成通用截图
          └─ 截图流程 → 详见 screenshot_flow.md
          └─ 返回 dict (msg_type=2, markdown, keyboard)
```

## 涉及函数清单

| 函数 | 文件 | 作用 |
|------|------|------|
| `get_pet()` | data_manager.py | 获取宠物数据 |
| `start_training()` | data_manager.py | 设置训练状态、记录开始时间 |
| `calc_training_exp()` | pet_stats.py | 计算训练经验公式 |
| `_generate_screenshot()` | pet_game.py | 截图核心：缓存/渲染/截图/并发控制 |
| `_build_pet_message()` | pet_game.py | 调用截图核心 + 构建消息 |
