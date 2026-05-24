# QQ 宠物战斗机器人

基于 QQ 开放平台官方 API (v2) 的宠物战斗养成机器人，**Webhook 模式**，处理群聊 @ 消息和私聊消息。25 种宠物、三阶进化、IV 个体值、实时自动战斗系统。

## 功能特性

- 🐷 **25 种宠物** - 随机领养一只独一无二的猪猪伙伴，含个体值差异
- ⚔️ **PvP 战斗** - 实时自动战斗引擎，技能轮换、状态效果、类型克制
- 🧬 **IV 个体值** - 6 维 IV（HP/ATK/DEF/SPD/CRIT/EVA），决定宠物品质（S~E）
- 📈 **三阶进化** - Lv29 一阶进化、Lv59 二阶进化，每阶段解锁新技能
- 🏋️ **挂机训练** - 最少训练 10 分钟获得经验，时间越长经验越多
- 🏆 **排行榜** - 全服宠物等级排行
- 🔒 **Token 管理** - 自动获取和后台刷新 QQ API access_token，存入 Redis
- 🔘 **内嵌键盘** - 支持可配置行列的按钮列表消息

## 快速开始

### 1. 获取机器人凭证

前往 [QQ 开放平台](https://q.qq.com) 创建机器人应用，获取 AppID 和 AppSecret。

### 2. 修改配置

#### 敏感凭证（bot_config.yaml，已加入 .gitignore）

```yaml
bot:
  app_id: "YOUR_APP_ID"
  secret: "YOUR_APP_SECRET"
  sandbox: true  # 首次测试建议开启沙箱模式
```

#### 公共配置（config.yaml）

```yaml
webhook:
  host: "127.0.0.1"          # 监听地址
  port: 8080                 # 监听端口
  path: "/qqbot/webhook"     # 回调路径
  force_https: false         # false=HTTP（配合 nginx/ngrok），true=本地 HTTPS

image:
  dir: "data/images"
  route: "/static/images"

redis:
  host: "localhost"
  port: 6379
  password: ""
  db: 0

game:
  battle:
    tick_interval: 0.1
    max_duration: 60
  training:
    min_lock_minutes: 10
    exp_per_level_per_minute: 50
```

### 3. 启动 Redis

```bash
# Docker
docker run -d -p 6379:6379 redis:latest

# 或直接启动
redis-server
```

### 4. 配置回调地址

在 QQ 开放平台机器人管理后台配置 Webhook 回调地址。本地调试推荐使用 ngrok 等内网穿透工具：

```
ngrok http 8080
```

将 ngrok 提供的 HTTPS 地址 + `/qqbot/webhook` 填入 QQ 开放平台回调地址。

### 5. 安装依赖

```bash
pip install -r requirements.txt
```

### 6. 启动机器人

```bash
python main.py
```

### 7. 运行测试

```bash
python -m unittest discover -s test -v
```

测试无需 Redis —— 已通过 mock 方式隔离。

## 命令列表

| 命令 | 说明 |
|------|------|
| `/领养` | 随机领养一只猪猪宠物 |
| `/属性` | 查看宠物详细属性（含 IV 详情和进化提示） |
| `/战斗 @某人` | 与对方宠物进行 PvP 战斗 |
| `/进化` | 进化宠物（需 Lv29 或 Lv59） |
| `/训练` | 开始挂机训练（最少 10 分钟） |
| `/休息` | 结束训练领取经验 |
| `/改名 <名字>` | 给宠物改名（1-8 字符） |
| `/遗弃` | 遗弃当前宠物 |
| `/排行` | 查看全局排行榜 TOP10 |
| `/帮助` | 查看帮助菜单 |

所有命令均支持英文别名：`/adopt` `/status` `/stats` `/battle` `/evolve` `/train` `/rest` `/rename` `/abandon` `/top` `/help`

## 战斗系统

### 类型克制

攻击型(attack) → 防御型(defense) → 速度型(speed) → 攻击型(attack)，克制方 15% 伤害加成，被克方 10% 减伤。

### IV 品质

| 品质 | IV 总和 |
|------|---------|
| S（传说） | ≥ 151 |
| A（卓越） | ≥ 121 |
| B（优秀） | ≥ 91 |
| C（不错） | ≥ 61 |
| D（一般） | ≥ 31 |
| E（普通） | < 31 |

### 进化门槛

- 一阶 → 二阶：达到 Lv29，使用 `/进化`
- 二阶 → 三阶：达到 Lv59，使用 `/进化`
- 进化后重置经验、解锁新技能，属性追溯重算

## 项目结构

```
QQBot/
├── main.py              # 入口文件
├── config.yaml          # 公共配置文件
├── bot_config.yaml      # 敏感凭证（.gitignore）
├── requirements.txt     # 依赖列表
├── CODEBUDDY.md         # AI 开发指南
├── data/images/         # 本地图片目录
├── docs/                # 设计文档
├── src/
│   ├── bot.py           # Webhook 服务 + API 调用
│   ├── config.py        # 配置加载
│   ├── token_manager.py # Token 管理（Redis + 后台刷新）
│   ├── data_manager.py  # Redis 数据持久化
│   ├── handler.py       # 命令路由
│   ├── pet_game.py      # 游戏核心逻辑
│   ├── pet_config.py    # 25 种宠物 + 技能数据
│   ├── pet_stats.py     # IV 生成 + 属性计算
│   ├── battle.py        # 实时自动战斗引擎
│   └── msg_templates.py # Markdown/按钮消息模板
└── test/
    ├── test_battle.py
    ├── test_data_manager.py
    ├── test_pet_stats.py
    └── test_signature.py
```

## 技术栈

- **Python 3.10+**
- **aiohttp** - HTTP 服务器 + 异步 API 调用
- **Redis** - 高性能数据存储（宠物、排行榜、Token）
- **PyNaCl** - Ed25519 签名验证
- **PyYAML** - 配置文件解析
- **Cryptography** - 自签名证书生成
- **QQ 开放平台 API v2** - Webhook 模式
