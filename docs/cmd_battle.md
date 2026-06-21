# /战斗 (battle) 指令详细流程

## 概述

PvP 战斗，通过游戏用户ID指定对手。战斗指令会返回**两次消息**：

1. **第一次**（msg_seq=1）：立即返回"战斗开始，结果生成中..."
2. **第二次**（msg_seq=2）：间隔至少 1 秒后返回战斗结果报告

双方宠物进入实时自动战斗引擎（0.1s tick），技能轮换、状态效果、类型克制，最长 120 秒。战斗结束后双方获得经验。

## 消息发送流程

```
core/bot.py :: handle_group_at / handle_c2c
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
    └─ core/api.py :: _build_msg_payload(reply, msg_id, msg_seq)
        └─ msg_seq > 0 时添加 "msg_seq" 字段到 POST 载荷
```

## 调用链路

```
用户发送 "/战斗 123"  (123 为对方的游戏用户ID)
    │
    ▼
handler.py :: handle_message()
    │  parse_command("/战斗 123") → cmd="战斗", arg="123"
    │  get_handler("战斗") → PvPMixin.battle_pvp  (装饰器注册)
    │
    ▼
game/pvp.py :: PvPMixin.battle_pvp(user_id, user_name, arg, group_id)
    │
    ├─ 1. 解析目标
    │     ├─ arg.isdigit() → target_game_uid = int(arg)
    │     └─ self.dm.get_user_by_game_uid(target_game_uid)
    │        └─ data/group.py → Redis GET qqbot:game_uid:{game_uid} → 对方 QQ user_id
    │
    ├─ 2. 基础校验
    │     ├─ target_id 为 None → 返回 str "请提供对方的游戏用户ID"
    │     ├─ challenger_id == target_id → 返回 str "不能挑战自己"
    │     ├─ self.dm.get_pet(challenger_id) → 无宠物 → 返回 str 错误
    │     ├─ pet_a.training → 返回 str "训练中无法战斗"
    │     ├─ self.dm.get_pet(target_id) → 对方无宠物 → 返回 str 错误
    │     └─ pet_b.training → 返回 str "对方训练中"
    │
    ├─ 3. 构建开始消息
    │     └─ start_msg = "⚔️ {pet_a.species_name}「{pet_a.name}」 VS ..."
    │
    ├─ 4. 构建战斗数据（含被动注入）
    │     ├─ self._build_battle_dict(challenger_id, pet_a)
    │     │   └─ game/base.py :: PetGameBase._build_battle_dict()
    │     │       ├─ self.dm.get_passive_slots(user_id) → 被动槽位
    │     │       ├─ self.dm.get_passive_level(user_id, sid) → 各技能等级
    │     │       └─ pet.with_passives(slots, levels) → 合并到 dict
    │     └─ self._build_battle_dict(target_id, pet_b) → 同上
    │
    ├─ 5. battle_engine.run(pet_a_dict, pet_b_dict)
    │     └─ battle/engine.py :: BattleEngine.run()
    │        ├─ _create_battle_pet() × 2
    │        │   └─ 初始化技能冷却：所有技能初始 CD = skill.cd（全部进入冷却）
    │        ├─ _apply_passive_skills() × 2
    │        │   └─ 读取 passive_slots/passive_levels → 叠加属性加成
    │        ├─ _type_advantage() → 克制环
    │        └─ 主循环 (elapsed < 60s, DT=0.1s)
    │              ├─ 控制状态检查
    │              ├─ 状态效果 tick (DoT/HoT)
    │              ├─ _process_pet(a) → 技能轮换 + 普攻
    │              │   └─ 技能轮换逻辑：
    │              │       1. 检查当前技能（skill_index）冷却是否结束
    │              │       2. 若 CD <= 0，执行当前技能
    │              │       3. 设置下一个技能的冷却时间
    │              │       4. 移动到下一个技能（skill_index + 1）
    │              │       5. 循环：0→1→2→0→1→2→...
    │              ├─ _process_pet(b) → 技能轮换 + 普攻
    │              └─ 死亡检查 → 任一方 HP<=0 则跳出
    │
    ├─ 6. 经验发放
    │     ├─ 胜方: exp = 50 * pet_a.level
    │     ├─ 败方: exp = 20 * pet_a.level
    │     └─ self.dm.update_leaderboard() × 2
    │
    ├─ 7. 构建结果消息
    │     └─ result_msg = format_battle_report(result)
    │         └─ battle/report.py
    │
    └─ 8. 返回 [start_msg, result_msg]
          └─ core/bot.py 收到 list → 分两次发送，间隔 1s
              ├─ 第 1 次 POST: {content: start_msg, msg_seq: 1}
              ├─ sleep(1)
              └─ 第 2 次 POST: {content: result_msg, msg_seq: 2}
```

## 返回值类型

| 场景 | 返回类型 | 说明 |
|------|----------|------|
| 校验失败 | `str` | 单条错误消息，bot 直接发送 |
| 战斗成功 | `list[str, str]` | 两条消息，bot 分次发送（msg_seq=1,2，间隔 1s） |

## 技能轮换机制

战斗中的技能使用遵循严格的轮换规则：

### 初始化
- 战斗开始时，所有技能立即进入冷却状态
- `skill_cds[i] = skill.cd`（每个技能的冷却时间等于其定义的 CD）

### 轮换流程
```
时间轴 →
├─ t=0.0s: 所有技能冷却中，仅使用普攻
├─ t=skill[0].cd: 技能0冷却结束 → 释放技能0 → 技能1进入冷却
├─ t=skill[0].cd + skill[1].cd: 技能1冷却结束 → 释放技能1 → 技能2进入冷却
├─ t=... + skill[2].cd: 技能2冷却结束 → 释放技能2 → 技能0进入冷却
└─ 循环：0→1→2→0→1→2→...
```

### 关键规则
1. **顺序释放**：技能按索引顺序释放（0, 1, 2, 0, 1, 2...）
2. **冷却传递**：释放技能 i 后，技能 (i+1) 进入冷却
3. **普攻填充**：技能冷却期间使用普攻
4. **控制影响**：被控制（眩晕/沉默）时跳过技能释放，但冷却继续倒计时

### 示例（3 技能宠物，CD 分别为 4s, 5s, 6s）
```
0.0s  - 普攻（所有技能冷却中）
4.0s  - 释放技能0（CD=4s）→ 技能1开始冷却
9.0s  - 释放技能1（CD=5s）→ 技能2开始冷却
15.0s - 释放技能2（CD=6s）→ 技能0开始冷却
19.0s - 释放技能0（CD=4s）→ 技能1开始冷却
24.0s - 释放技能1（CD=5s）→ 技能2开始冷却
...
```

## 涉及函数清单

| 函数 | 文件 | 作用 |
|------|------|------|
| `get_user_by_game_uid()` | data/group.py | 通过游戏用户ID反查QQ用户ID |
| `get_pet()` | data/pet_store.py | 获取双方宠物数据 |
| `battle_pvp()` | game/pvp.py | 异步战斗：返回 [开始消息, 结果消息] |
| `_build_battle_dict()` | game/base.py | 构建战斗用 dict（修饰符收集管线） |
| `_collect_passive_modifiers()` | game/base.py | 被动技能 → 修饰符列表 |
| `get_passive_slots()` | data/passive_store.py | 获取玩家已装备被动槽位 |
| `get_passive_level()` | data/passive_store.py | 获取被动技能等级 |
| `BattleEngine.run()` | battle/engine.py | 运行完整战斗模拟 |
| `_create_battle_pet()` | battle/engine.py | 从 Pet dict 创建战斗快照 |
| `_collect_battle_modifiers()` | battle/engine.py | 从 dict 提取修饰符列表 |
| `_apply_modifiers()` | battle/engine.py | 通用属性加成应用（来源无关） |
| `_type_advantage()` | battle/engine.py | 计算类型克制系数 |
| `_process_pet()` | battle/engine.py | 处理单个宠物每 tick 的行动 |
| `_execute_skill()` | battle/engine.py | 执行技能 |
| `_resolve_effect()` | battle/engine.py | 解析技能效果（15+ 种类型） |
| `_execute_attack()` | battle/engine.py | 执行普攻 |
| `_calc_damage()` | battle/engine.py | 9 步伤害管线 |
| `_tick_statuses()` | battle/engine.py | 处理 DoT/HoT tick |
| `_decay_statuses()` | battle/engine.py | 状态持续时间衰减 |
| `_is_controlled()` | battle/engine.py | 控制状态检查 |
| `add_exp()` | data/pet_store.py | 战斗后发放经验 |
| `update_leaderboard()` | data/leaderboard.py | 刷新排行榜 |
| `format_battle_report()` | battle/report.py | 格式化战斗报告文本 |
| `_build_msg_payload()` | core/api.py | 构建消息载荷（支持 msg_seq） |
| `handle_group_at()` | core/bot.py | 检测 list 回复，分次发送+延迟 |
