# /战斗 (battle) 指令详细流程

## 概述

PvP 战斗，通过游戏用户ID指定对手。战斗指令会返回**两次消息**：

1. **第一次**（msg_seq=1）：立即返回"战斗开始，结果生成中..."
2. **第二次**（msg_seq=2）：间隔至少 1 秒后返回战斗结果报告

双方宠物进入实时自动战斗引擎（0.1s tick），技能轮换、状态效果、类型克制，最长 60 秒。战斗结束后双方获得经验。

## 消息发送流程

```
bot.py :: handle_group_at / handle_c2c
    │
    ├─ reply = await handle_message(...)
    │
    ├─ 检测 reply 类型：
    │   ├─ isinstance(reply, list) → 多消息模式（战斗）
    │   │   ├─ 第 1 条: send_group_reply(msg_seq=1)
    │   │   ├─ await asyncio.sleep(1)
    │   │   └─ 第 2 条: send_group_reply(msg_seq=2)
    │   │
    │   └─ 其他类型 → 单消息模式（普通命令）
    │       └─ send_group_reply(reply)
    │
    └─ _build_msg_payload(reply, msg_id, msg_seq)
        └─ msg_seq > 0 时添加 "msg_seq" 字段到 POST 载荷
```

## 调用链路

```
用户发送 "/战斗 123"  (123 为对方的游戏用户ID)
    │
    ▼
handler.py :: handle_message()
    │  parse_command("/战斗 123") → cmd="战斗", arg="123"
    │  _resolve_battle_target():
    │    ├─ arg.isdigit() → target_game_uid = 123
    │    └─ data_manager.get_user_by_game_uid(123)
    │       └─ Redis GET qqbot:game_uid:123 → 对方 QQ user_id
    │  handlers["战斗"] → game.battle_pvp(user_id, target_qq_id)
    │
    ▼
pet_game.py :: PetGame.battle_pvp(challenger_id, target_id)  [async]
    │
    ├─ 1. 基础校验
    │     ├─ target_id 为 None → 返回 str "请提供对方的游戏用户ID"
    │     ├─ challenger_id == target_id → 返回 str "不能挑战自己"
    │     ├─ self.dm.get_pet(challenger_id) → 无宠物 → 返回 str 错误
    │     ├─ pet_a.training → 返回 str "训练中无法战斗"
    │     ├─ self.dm.get_pet(target_id) → 对方无宠物 → 返回 str 错误
    │     └─ pet_b.training → 返回 str "对方训练中"
    │
    ├─ 2. 构建开始消息
    │     └─ start_msg = "⚔️ {pet_a.species_name}「{pet_a.name}」 VS ..."
    │
    ├─ 3. battle_engine.run(pet_a.to_dict(), pet_b.to_dict())
    │     └─ battle.py :: BattleEngine.run()
    │        ├─ _create_battle_pet() × 2
    │        ├─ _type_advantage() → 克制环
    │        └─ 主循环 (elapsed < 60s, DT=0.1s)
    │              ├─ 控制状态检查
    │              ├─ 状态效果 tick (DoT/HoT)
    │              ├─ _process_pet(a) → 技能轮换 + 普攻
    │              ├─ _process_pet(b) → 技能轮换 + 普攻
    │              └─ 死亡检查 → 任一方 HP<=0 则跳出
    │
    ├─ 4. 经验发放
    │     ├─ 胜方: exp = 50 * pet_a.level
    │     ├─ 败方: exp = 20 * pet_a.level
    │     └─ self.dm.update_leaderboard() × 2
    │
    ├─ 5. 构建结果消息
    │     └─ result_msg = format_battle_report(result)
    │
    └─ 6. 返回 [start_msg, result_msg]
          └─ bot.py 收到 list → 分两次发送，间隔 1s
              ├─ 第 1 次 POST: {content: start_msg, msg_seq: 1}
              ├─ sleep(1)
              └─ 第 2 次 POST: {content: result_msg, msg_seq: 2}
```

## 返回值类型

| 场景 | 返回类型 | 说明 |
|------|----------|------|
| 校验失败 | `str` | 单条错误消息，bot 直接发送 |
| 战斗成功 | `list[str, str]` | 两条消息，bot 分次发送（msg_seq=1,2，间隔 1s） |

## 涉及函数清单

| 函数 | 文件 | 作用 |
|------|------|------|
| `get_user_by_game_uid()` | data_manager.py | 通过游戏用户ID反查QQ用户ID |
| `get_pet()` | data_manager.py | 获取双方宠物数据 |
| `battle_pvp()` | pet_game.py | 异步战斗：返回 [开始消息, 结果消息] |
| `BattleEngine.run()` | battle.py | 运行完整战斗模拟 |
| `_create_battle_pet()` | battle.py | 从 Pet dict 创建战斗快照 |
| `_type_advantage()` | battle.py | 计算类型克制系数 |
| `_process_pet()` | battle.py | 处理单个宠物每 tick 的行动 |
| `_execute_skill()` | battle.py | 执行技能 |
| `_resolve_effect()` | battle.py | 解析技能效果（15+ 种类型） |
| `_execute_attack()` | battle.py | 执行普攻 |
| `_calc_damage()` | battle.py | 9 步伤害管线 |
| `_tick_statuses()` | battle.py | 处理 DoT/HoT tick |
| `_decay_statuses()` | battle.py | 状态持续时间衰减 |
| `_is_controlled()` | battle.py | 控制状态检查 |
| `add_exp()` | data_manager.py | 战斗后发放经验 |
| `update_leaderboard()` | data_manager.py | 刷新排行榜 |
| `format_battle_report()` | battle.py | 格式化战斗报告文本 |
| `_build_msg_payload()` | bot.py | 构建消息载荷（支持 msg_seq） |
| `handle_group_at()` | bot.py | 检测 list 回复，分次发送+延迟 |
