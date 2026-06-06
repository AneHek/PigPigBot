# /休息 (rest) 指令详细流程

## 概述

结束训练并领取经验。至少训练 10 分钟才能领取，经验公式为 `50 * level * minutes`。可能触发升级。返回截图+按钮消息。

## 调用链路

```
用户发送 "/休息"
    │
    ▼
handler.py :: handle_message()
    │  parse_command("/休息") → cmd="休息", arg=""
    │  handlers["休息"] → game.end_training(user_id)
    │
    ▼
pet_game.py :: PetGame.end_training(user_id)
    │
    ├─ 1. self.dm.get_pet(user_id)
    │     └─ 无宠物 → 返回错误
    │
    ├─ 2. 训练状态检查
    │     └─ pet.training == False → 返回 "宠物不在训练中"
    │
    ├─ 3. self.dm.end_training(user_id)
    │     └─ data_manager.py :: DataManager.end_training()
    │        ├─ get_pet() → 获取 Pet
    │        ├─ 计算 elapsed = time.time() - pet.training_start
    │        ├─ minutes = int(elapsed / 60)
    │        ├─ minutes < 10 → 返回 (None, -1) 表示时间不足
    │        ├─ exp_gained = 50 * pet.level * minutes
    │        ├─ pet.training = False
    │        ├─ pet.training_start = 0.0
    │        ├─ pet.last_update = time.time()
    │        ├─ Redis SET qqbot:pet:{user_id}
    │        ├─ self.add_exp(user_id, exp_gained)
    │        │   └─ update_pet(user_id, exp=pet.exp + exp_gained)
    │        │      └─ 升级循环：
    │        │         ├─ 进化门槛检查 (stage 0→29, stage 1→59)
    │        │         ├─ exp >= max_exp → exp -= max_exp, level += 1
    │        │         └─ 升级后 calc_stats() 重算属性
    │        └─ 返回 (updated_pet, exp_gained)
    │
    ├─ 4. exp_gained == -1 → 返回 "还需要训练 X 分钟"
    │
    ├─ 5. self.dm.update_leaderboard(result)
    │     └─ 刷新排行榜
    │
    ├─ 6. 构建回复信息
    │     ├─ title: "🛌 {species_name}({game_uid}) 训练结束"
    │     ├─ tip: "训练{minutes}分钟 | Lv.{old_level}->Lv.{new_level}  |  战力：{cp}"
    │     │       （cp = calc_cp(result) 计算综合战力）
    │     └─ 检测升级: result.level > pet.level → 标题中展示等级变化
    │     └─ 检测可进化: level 达到门槛 → 标题中追加 "可进化" 警告
    │
    ├─ 7. msg = await self._build_pet_message(result, title, tip, rows)
    │     └─ title: "🛌 {species_name}({game_uid}) 训练结束"
    │     └─ 调用 _generate_screenshot(result) 生成通用截图
    │     └─ 截图流程 → 详见 screenshot_flow.md
    │
    └─ 8. asyncio.create_task(self._pre_generate_screenshot(result))
          └─ 后台预生成通用截图（fire-and-forget）
          └─ 用户后续点击 /属性 时直接命中缓存，0ms 截图延迟
          └─ 返回 msg
```

## 涉及函数清单

| 函数 | 文件 | 作用 |
|------|------|------|
| `get_pet()` | data_manager.py | 获取宠物数据 |
| `end_training()` | data_manager.py | 结束训练、计算经验、发放经验 |
| `add_exp()` | data_manager.py | 增加经验并处理升级 |
| `update_pet()` | data_manager.py | 更新属性、升级循环、进化门槛 |
| `calc_stats()` | pet_stats.py | 升级后重算战斗属性 |
| `update_leaderboard()` | data_manager.py | 刷新排行榜 |
| `_generate_screenshot()` | pet_game.py | 截图核心：缓存/渲染/截图/并发控制 |
| `_pre_generate_screenshot()` | pet_game.py | 后台预生成通用截图 |
| `_build_pet_message()` | pet_game.py | 调用截图核心 + 构建消息 |
