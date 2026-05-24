# CODEBUDDY.md This file provides guidance to CodeBuddy when working with code in this repository.

## 常用命令

```bash
# 安装依赖
pip install -r requirements.txt

# 启动机器人（需先配置 bot_config.yaml 和 Redis）
python main.py

# 运行全部测试
python -m unittest discover -s test -v

# 运行单个测试文件
python -m unittest test.test_battle -v

# 运行单个测试类
python -m unittest test.test_battle.TestBattleEngine -v

# 运行单个测试方法
python -m unittest test.test_battle.TestBattleEngine.test_battle_ends_with_winner -v
```

注意：测试不依赖真实 Redis——`test_battle.py` 和 `test_pet_stats.py` 在导入时 mock 掉 redis 模块，`test_data_manager.py` 使用自实现的 `InMemoryRedis`。

## 架构总览

本项目是一个 QQ 开放平台宠物战斗养成机器人，采用 **Webhook (HTTPS)** 模式，通过 aiohttp 提供 HTTP 服务接收 QQ 平台事件推送，异步调用 QQ 开放 API 回复消息。核心业务是 25 种宠物的三阶进化、IV 属性、实时自动战斗系统。

### 数据流

```
QQ 平台 → POST /qqbot/webhook → QQBot.webhook_handler()
  ├── op=13 → URL 验证（Ed25519 签名）
  └── op=0  → 事件分发
       ├── GROUP_AT_MESSAGE_CREATE → handle_group_at()
       └── C2C_MESSAGE_CREATE → handle_c2c()
            ↓
       handler.handle_message() → 命令解析 + 路由
            ↓
       pet_game.PetGame → 业务逻辑
            ↓
       data_manager.DataManager → Redis 读写
            ↓
       QQBot.send_*_reply() → POST QQ 开放 API
```

### 模块职责

**入口 & 配置层**

- `main.py`：入口，检查配置、初始化 `QQBot`、启动事件循环。Windows 下显式设置 `WindowsSelectorEventLoopPolicy`。
- `config.py`：加载 `config.yaml`（公共配置：webhook 端口、Redis、图片路径、游戏参数）和 `bot_config.yaml`（敏感凭证：app_id、secret），合并到全局 `config` dict。
- `config.yaml`：公共配置，包含 `webhook`、`image`、`redis`、`game` 四个 section。`webhook.force_https` 控制本地是否启用 HTTPS；设为 false 时走纯 HTTP，依赖 nginx/ngrok 反向代理提供 HTTPS。
- `bot_config.yaml`：敏感凭证，被 `.gitignore` 忽略。包含 `bot.app_id`、`bot.secret`、`bot.sandbox`。

**网络 & 事件层**

- `bot.py::QQBot`：核心类，管理 aiohttp web 服务器 + API 客户端。
  - `webhook_handler()`：统一处理 POST 请求。op=13 做 Ed25519 URL 验证（用 secret 派生 32 字节种子生成签名密钥）；op=0 按事件类型分发。
  - `_build_ssl_context()`：根据 `force_https` 决定是否加载证书，无证书时自动生成自签名证书。
  - 消息回复通过 `_build_msg_payload()` 统一构建载荷，支持纯文本（str）和结构化消息（dict，含 msg_type、keyboard 等字段）。
  - 图片静态文件通过 aiohttp `add_static` 挂载到 `/static/images` 路由。
- `token_manager.py::TokenManager`：后台 asyncio task 管理 QQ 开放平台 access_token。启动时从 QQ API 获取 token 存入 Redis，定期检查剩余有效期（阈值 30 分钟）并自动刷新。bot.py 通过 `token_manager.get_token()` 读取 token 用于 API 调用。

**业务逻辑层**

- `handler.py`：命令解析和路由。`parse_command()` 剥除 `@!` mention 前缀后提取命令名和参数；`handle_message()` 将命令路由到 `pet_game.PetGame` 对应方法。无命令但有 @mention 时自动触发 PvP 战斗。支持中英文双语命令（如 `/领养` 与 `/adopt`）。
- `pet_game.py::PetGame`：游戏业务逻辑。所有方法返回字符串回复（部分内部调用 `format_battle_stats` / `format_battle_report` 格式化）。关键业务：领养（随机 25 种之一，生成 IV 和属性）、进化（Lv29/Lv59 门槛）、训练（挂机 10+n 分钟）、PvP 战斗（调用 `battle_engine.run()`）、排行榜（Redis zset）。

**数据层**

- `data_manager.py`：Redis 数据持久化。全局 `data_manager` 单例。关键 Redis key：
  - `qqbot:pet:{user_id}`：宠物 JSON 序列化存储
  - `qqbot:cooldown:{user_id}`：冷却 hash（action → 到期时间戳）
  - `qqbot:leaderboard`：zset（user_id → score=level+exp/1000）
  - `qqbot:leaderboard:detail`：hash（user_id → 详情 JSON）
  - `qqbot:access_token` / `qqbot:access_token_expires_at`：TokenManager 管理
  
- `Pet` dataclass：包含 owner 信息、物种 ID、进化阶段、6 项 IV（hp/atk/def/spd/crit/eva）、计算属性（hp/atk/def_/spd/crit/crit_dmg/eva/lifesteal）、训练状态。`update_pet()` 内含升级循环和进化门槛逻辑（stage 0 锁 Lv29，stage 1 锁 Lv59）。升级时自动调用 `calc_stats()` 重算属性。`delete_pet()` 级联删除冷却和排行榜。

**战斗系统**

- `battle.py`：实时 tick-based 自动战斗引擎。核心类 `BattleEngine.run()` 以 0.1s 为 tick、最长 60s 运行，每 tick 处理状态效果轮转、dot/hot 结算、技能 CD 和自动普攻。关键机制：
  - **类型克制**：attack > defense > speed > attack（优势 15% 加成，劣势 10% 惩罚）
  - **9 步伤害管线**：类型加成 → 暴击判定 → 闪避判定 → 护盾吸收 → 防御减伤（公式 `1 - def/(def+1000)`）→ 反伤 → 吸血
  - **控制优先级**：stun/freeze(100) > imprison/float(80) > fear(60) > silence(40) > disarm(20) > taunt/confuse(10)
  - 技能通过 `SkillEffect` 数据驱动执行，支持 damage、dot、hot、heal、debuff、buff、control、shield、reflect、true_damage、crit_guaranteed、purify、interrupt、confuse、auto_skill 共 15 种效果类型
  - `format_battle_report()`：输出战斗结果和最后 10 个事件日志

- `pet_config.py`：26 种宠物（P001~P026）的完整数据定义。新增 P025 粉红猪系（占位），原 P025 仙猪萌系后移为 P026。包含 `get_pet_image_url()` 图片映射函数，公式 `pig_index = 77 - ((num-1)*3 + stage)`。
  
- `pet_stats.py`：属性计算模块。IV 生成通过二项分布 Binomial(5,0.5) 先决定品质档位（E~S），再在档位IV总和范围内生成6项IV。`QUALITY_RANGES` 和 `QUALITY_INDEX_TO_LABEL` 统一品质判定。IV 修正系数 `f = 0.75 + (IV/31) × 0.5`；最终属性公式 `base_init × f + per_level × f × E × (level - 1)`。

**消息模板层**

- `msg_templates.py`：封装 QQ 官方 Markdown 模板和按钮列表。`build_markdown_msg()` 使用自定义 template_id；`build_button_list_msg()` 支持自由行列布局；`build_markdown_with_buttons()` 组合 markdown+keyboard 为完整消息 dict。

**图片服务层**

- `image_gen.py`：HTML 渲染和 Playwright 截图。`render_pet_html()` 支持5种场景(adopt/status/stats/evolve/training)的宠物信息HTML模板，含宠物形象 `<img>` 标签。`html_to_image()` 通过 headless chromium/msedge 截图输出PNG。
- `image_lifecycle.py`：截图生命周期管理。`schedule_deletion()` 异步延迟60秒删除文件；`cleanup_orphan_files()` 启动时清理 screenshots 目录孤儿文件。
- 图片映射：`get_pet_image_url()` 将 species_id+stage 映射到 `cropped_pigs1/2` 目录的 `pig_0~pig_77.png`，倒序对应 pig.md 表格中78个名字。

### 配置双文件设计

敏感凭证（app_id、secret）存储在 `bot_config.yaml`，公共配置（端口、Redis、游戏参数）存储在 `config.yaml`，两者在 `config.py` 中合并。`bot_config.yaml` 通过 `.gitignore` 排除，防止意外提交。

### Redis 依赖

所有持久化依赖 Redis，包括宠物数据、排行榜、冷却时间、access_token。测试中 mock 掉 redis 模块以实现无 Redis 环境的单元测试。

### 新增战斗系统经验奖励

PvP 战斗胜者获得 `50 × 胜者等级` 经验，败者获得 `20 × 挑战者等级` 经验，双方均更新排行榜。
