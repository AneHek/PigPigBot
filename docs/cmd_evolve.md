# /进化 (evolve) 指令详细流程

## 概述

进化宠物（一阶→二阶需 Lv29，二阶→三阶需 Lv59），保留多余经验继续升级、解锁新技能、重算属性。若宠物名等于旧种族名则自动更新为新种族名。返回截图+按钮消息，含属性变化预览。

## 调用链路

```
用户发送 "/进化"
    │
    ▼
handler.py :: handle_message()
    │  parse_command("/进化") → cmd="进化", arg=""
    │  get_handler("进化") → EvolveMixin.evolve  (装饰器注册)
    │
    ▼
game/evolve.py :: EvolveMixin.evolve(user_id, user_name, arg, group_id)
    │
    ├─ 1. self.dm.get_pet(user_id)
    │     └─ data/pet_store.py → 无宠物 → 返回错误
    │
    ├─ 2. 进化条件校验
    │     ├─ evolution_stage >= 2 → "已是三阶，无法再进化"
    │     ├─ stage=0 且 level < 29 → "需要达到 Lv.29"
    │     └─ stage=1 且 level < 59 → "需要达到 Lv.59"
    │
    ├─ 3. copy.deepcopy(pet) → old_pet
    │     └─ 保存进化前数据用于属性变化预览
    │
    ├─ 4. self.dm.evolve_pet(user_id)
    │     └─ data/pet_store.py :: PetStoreMixin.evolve_pet()
    │        ├─ 校验 stage < 2 且 level >= gate
    │        ├─ 记录 old_species_name = pet.species_name
    │        ├─ pet.evolution_stage += 1
    │        ├─ pet.level += 1
    │        ├─ pet.last_update = time.time()
    │        ├─ 若 pet.name == old_species_name → pet.name = pet.species_name（自动改名）
    │        ├─ 升级循环（保留多余经验）：
    │        │   while pet.exp >= pet.max_exp:
    │        │     ├─ 进化门槛检查 (stage 0→29, stage 1→59)
    │        │     ├─ pet.exp -= pet.max_exp
    │        │     └─ pet.level += 1
    │        ├─ calc_stats(species_id, new_stage, new_level, ivs)
    │        │   └─ pet/stats.py :: calc_stats()
    │        │      └─ E = EVOLUTION_COEFFICIENTS[new_stage] (1.10/1.21)
    │        │      └─ 属性全面提升
    │        ├─ 更新 pet 的 hp/atk/def_/spd/crit/crit_dmg/eva/lifesteal
    │        └─ Redis SET qqbot:pet:{user_id}
    │
    ├─ 5. self.dm.update_leaderboard(result)
    │     └─ data/leaderboard.py → 刷新排行榜
    │
    ├─ 6. msg = await self._build_pet_message(result, title, tip, rows, old_pet=old_pet)
    │     └─ game/base.py → 调用 _generate_screenshot(result, old_pet) 生成进化截图（含属性变化预览）
    │     └─ old_pet 参数使截图显示 "旧值→新值" 属性变化
    │     └─ 截图流程 → 详见 screenshot_flow.md
    │
    └─ 7. asyncio.create_task(self._pre_generate_screenshot(result))
          └─ 后台预生成通用截图（fire-and-forget）
          └─ 用户后续点击 /属性 时直接命中缓存，0ms 截图延迟
          └─ 返回 msg
```

## 进化机制说明

### 经验保留与连续升级

进化前累积的多余经验不再清零，而是继续参与升级循环：

```
进化前: Lv29, exp=15000 (max_exp=9800)
进化后: stage+1, level=30, exp=15000
  → 15000 >= 10500 (Lv30 max_exp) → exp=4500, level=31
  → 4500 < 11200 (Lv31 max_exp) → 停止
最终: Lv31, exp=4500
```

### 自动改名

若宠物名等于进化前的种族名（即用户未自定义改名），进化后自动更新为新种族名：

```
进化前: name="五行猪混混", species_name="五行猪混混" (P001 一阶)
进化后: name="黑白猪煞", species_name="黑白猪煞" (P001 二阶)

进化前: name="我的小猪", species_name="五行猪混混" (用户已改名)
进化后: name="我的小猪", species_name="黑白猪煞" (保留用户自定义名)
```

## 涉及函数清单

| 函数 | 文件 | 作用 |
|------|------|------|
| `get_pet()` | data/pet_store.py | 获取宠物数据 |
| `evolve_pet()` | data/pet_store.py | 执行进化：升阶、升级、保留经验继续升级、自动改名、重算属性 |
| `calc_stats()` | pet/stats.py | 进化后重算战斗属性（含进化系数） |
| `update_leaderboard()` | data/leaderboard.py | 刷新排行榜 |
| `_generate_screenshot()` | game/base.py | 截图核心：缓存/渲染/截图/并发控制 |
| `_pre_generate_screenshot()` | game/base.py | 后台预生成通用截图 |
| `_build_pet_message()` | game/base.py | 调用截图核心 + 构建消息（含属性变化预览） |
