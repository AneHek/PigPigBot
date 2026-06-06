# /训练 (train) 指令详细流程

## 概述

开始挂机训练，记录训练开始时间。最少训练 10 分钟后才能通过 `/休息` 领取经验。返回文本+按钮消息（不再使用 Markdown 模板/截图）。

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
    └─ 5. build_button_list_msg(content, rows)
          ├─ content: "💪 开始训练！\n🕓  预计获得{exp}经验(10分钟)。\n⚠  训练时间越长经验越多\n🗨  休息指令可用时间：{HH:MM}"
          │           （HH:MM = 当前时间 + 10 分钟）
          ├─ rows: [结束训练] / [属性详情] 按钮
          └─ 返回 dict (msg_type=0, content, keyboard)
```

## 涉及函数清单

| 函数 | 文件 | 作用 |
|------|------|------|
| `get_pet()` | data_manager.py | 获取宠物数据 |
| `start_training()` | data_manager.py | 设置训练状态、记录开始时间 |
| `calc_training_exp()` | pet_stats.py | 计算训练经验公式 |
| `build_button_list_msg()` | msg_templates.py | 构建文本+按钮消息（代替 Markdown 模板） |
