# 浏览器截图流程详细记录

## 概述

截图系统使用 Playwright (headless Chromium/Edge) 将宠物信息渲染为 HTML 卡片，再截图为 PNG 文件，通过静态文件服务提供给 QQ 消息展示。系统实现了确定性 UUID 缓存、页面预热池、并发控制和后台预生成机制。

## 架构组件

| 组件 | 文件 | 职责 |
|------|------|------|
| 截图核心 | pet_game.py `_generate_screenshot()` | 缓存判断、渲染、截图、并发控制、页面池调度 |
| 后台预生成 | pet_game.py `_pre_generate_screenshot()` | 数据变更后 fire-and-forget 预生成下一场景截图 |
| 消息组装 | pet_game.py `_build_pet_message()` | 调用截图核心 + 构建 Markdown+按钮消息 |
| HTML 渲染 | image_gen.py `render_pet_html()` | 宠物数据 → HTML 卡片（支持 base64 内联图片） |
| 截图引擎 | image_gen.py `html_to_image()` | Playwright set_content → PNG（支持复用预热页面） |
| UUID 缓存 | image_lifecycle.py `generate_screenshot_uuid()` | 基于 user_id + last_update + scene 的确定性 UUID |
| 生命周期管理 | image_lifecycle.py | 延迟删除、启动清理、每日兜底清理 |
| 消息模板 | msg_templates.py `build_markdown_with_buttons()` | 截图 URL + Markdown + 按钮 |
| 并发控制 | bot.py `_screenshot_semaphore` | asyncio.Semaphore 限制同时截图数 |
| 页面预热池 | bot.py `_page_pool` | 启动时预创建 N 个 Playwright page 复用 |
| 静态文件服务 | bot.py aiohttp 路由 | `/static/images/` 提供图片访问 |

## 完整流程

### 阶段 1：截图调度

```
pet_game.py :: _build_pet_message(pet, title, tip, rows, old_pet=None)
    │
    ├─ 1. 获取配置（callback_domain / pig_source / screenshots_dir）
    │
    ├─ 2. 计算宠物图片路径
    │     ├─ get_pet_image_url() → HTTP URL
    │     └─ get_pet_image_local_path() → 本地绝对路径
    │
    ├─ 3. 调用 _generate_screenshot(pet, old_pet)
    │     └─ 返回 filename 或 None
    │
    └─ 4. 组装消息
          ├─ filename 存在 → screenshot_url = domain/static/images/screenshots/{filename}
          ├─ filename 为 None → 回退到原始宠物图片 URL
          └─ build_markdown_with_buttons(title, screenshot_url, tip, rows)
```

### 阶段 2：截图核心（_generate_screenshot）

```
pet_game.py :: _generate_screenshot(pet, old_pet=None)
    │
    ├─ 0. 确定 scene
    │     └─ scene = "evolve" if old_pet is not None else ""
    │
    ├─ 1. 生成确定性 UUID
    │     └─ generate_screenshot_uuid(user_id, pet.last_update, scene)
    │        └─ seed = f"{user_id}:{last_update}:{scene}"
    │        └─ 非进化场景 scene="" → 所有非进化指令共用同一 UUID
    │        └─ 进化场景 scene="evolve" → 独立 UUID（含属性变化预览）
    │
    ├─ 2. 缓存命中检查
    │     ├─ recorded_uuid = dm.get_screenshot_uuid(user_id)
    │     │   └─ Redis GET qqbot:screenshot:{user_id}
    │     ├─ 条件：recorded_uuid == screenshot_uuid 且 文件存在
    │     └─ 命中 → 直接返回 filename（跳过截图生成）
    │
    ├─ 3. 旧截图延迟删除（fire-and-forget，不阻塞）
    │     └─ schedule_deletion(old_path, delay_seconds=60)
    │
    ├─ 4. 检查 Playwright 可用性
    │     └─ bot._playwright_browser 不存在 → 返回 None
    │
    ├─ 5. 图片 base64 内联
    │     ├─ Path(local_image_path).read_bytes()
    │     ├─ base64.b64encode() → data:image/png;base64,...
    │     └─ 配合 set_content 免临时文件
    │
    ├─ 6. 渲染 HTML
    │     └─ render_pet_html(pet, scene, image_url, local_image_path,
    │                         old_pet=old_pet, base64_image=base64_image)
    │
    ├─ 7. 获取预热页面
    │     ├─ 从 bot._page_pool 弹出一个预热页面
    │     └─ 池为空 → page = None（html_to_image 内新建）
    │
    ├─ 8. 并发控制
    │     ├─ await bot._screenshot_semaphore.acquire()
    │     └─ 等待直到有空闲槽位
    │
    ├─ 9. 截图生成
    │     └─ html_to_image(browser, html, output_path, page=page)
    │        ├─ page.set_content(html, wait_until="load")
    │        ├─ body_height = page.evaluate("document.body.scrollHeight")
    │        ├─ page.set_viewport_size({"width": 380, "height": body_height + 8})
    │        ├─ page.screenshot(path=output_path, full_page=True)
    │        └─ [预热页面不关闭，归还池中]
    │
    ├─ 10. 释放并发槽位
    │     ├─ semaphore.release()
    │     └─ 页面归还 bot._page_pool
    │
    └─ 11. UUID 记录异步写入（fire-and-forget，不阻塞返回）
          └─ asyncio.create_task(_record_uuid)
             └─ dm.set_screenshot_uuid(user_id, screenshot_uuid)
```

### 阶段 3：后台预生成

```
数据变更指令返回消息后，后台预生成通用截图（非进化场景共用）：

  adopt()        → 生成通用截图 → create_task(_pre_generate_screenshot(pet))
  evolve()       → 生成进化截图(old_pet) → create_task(_pre_generate_screenshot(result))
  end_training() → 生成通用截图 → create_task(_pre_generate_screenshot(result))

预生成流程：
  _pre_generate_screenshot(pet, old_pet=None)
    └─ try: await _generate_screenshot(pet, old_pet)
       except: logger.debug("预生成截图失败")

效果：
  用户后续点击 /属性 → stats_detail() → _generate_screenshot(pet)
    → 缓存命中 → 直接返回，0ms 截图延迟
```

### 阶段 4：截图生命周期管理

```
┌─────────────────────────────────────────────────────────────┐
│  截图清理机制（三层保障）                                      │
│                                                             │
│  1. 延迟清理（_generate_screenshot 内）                       │
│     └─ schedule_deletion(old_path, 60s) fire-and-forget     │
│     └─ 生成新截图前将旧截图标记 60s 后删除                     │
│                                                             │
│  2. 启动清理（bot.py :: start()）                            │
│     └─ cleanup_orphan_files(screenshots_dir)                │
│     └─ 删除截图目录下所有文件（清理上次运行的孤儿文件）        │
│                                                             │
│  3. 每日兜底清理（image_lifecycle.py :: daily_cleanup_loop） │
│     └─ 后台协程，计算到下一个 0 点的秒数休眠                  │
│     └─ 到达 0 点后调用 cleanup_orphan_files() 全量清理       │
└─────────────────────────────────────────────────────────────┘
```

## 截图缓存机制

```
数据变更事件 (领养/进化/训练/休息/改名)
    │
    ├─ pet.last_update = time.time()  ← data_manager 中更新
    │
    ├─ generate_screenshot_uuid(user_id, last_update, scene)
    │   ├─ 非进化场景: scene="" → uuid5(DNS, "{user_id}:{last_update}:")
    │   └─ 进化场景: scene="evolve" → uuid5(DNS, "{user_id}:{last_update}:evolve")
    │   └─ last_update 变化 → UUID 变化 → 缓存未命中 → 重新截图
    │
    └─ 缓存判断逻辑:
        recorded = Redis GET qqbot:screenshot:{user_id}
        if recorded == current_uuid AND file_exists:
            → 复用 (跳过截图)
        else:
            → 延迟删除旧文件 → 生成新截图 → 异步更新 Redis 记录
```

## Playwright 启动与页面预热

```
bot.py :: start()
    │
    ├─ 检测 Playwright 是否安装
    │   └─ try: from playwright.async_api import async_playwright
    │   └─ 失败 → _playwright_available = False
    │
    ├─ 启动 Playwright
    │   └─ self._playwright = await async_playwright().start()
    │
    ├─ 启动浏览器（优先 chromium）
    │   ├─ try: chromium.launch(headless=True)
    │   └─ except → chromium.launch(channel="msedge", headless=True)
    │   └─ 均失败 → _playwright_browser = None，截图功能不可用
    │
    ├─ 预热页面池
    │   ├─ 读取 screenshot_concurrency 配置（默认 2）
    │   ├─ 循环创建 N 个 page(viewport=380×800)
    │   ├─ 存入 self._page_pool 列表
    │   └─ 截图时从池中取出，用后归还（不关闭）
    │
    └─ 关闭时
        ├─ 逐个关闭 _page_pool 中的页面
        ├─ browser.close()
        └─ playwright.stop()
```

## 并发控制与内存分析

### 2GB 内存并发分析

```
总内存:                          2048 MB
──────────────────────────────────────────
OS + 基础服务:                   ~300 MB
Redis:                           ~50 MB
Python + aiohttp:                ~100 MB
Chromium headless (基础):        ~200 MB
远程控制预留 (SSH/RDP):          ~300 MB
──────────────────────────────────────────
可用于截图页面:                  ~1098 MB

每个 Playwright 页面开销:
  页面上下文:                    ~30-50 MB
  DOM 渲染 (380px 卡片):         ~10-20 MB
 截图缓冲区:                    ~5-10 MB
  base64 图片数据:               ~1-3 MB
  ──────────────────────────────
  单页面总计:                    ~50-80 MB

安全并发数: 2 (峰值 ~160MB，余量充足)
激进并发数: 3 (峰值 ~240MB，余量偏紧)
危险并发数: 4+ (可能触发 OOM)
```

### 配置方式

```yaml
# config.yaml
image:
  screenshot_concurrency: 2  # 2GB 内存建议 2，4GB+ 可设 3-4
```

### 信号量机制

```
bot._screenshot_semaphore = asyncio.Semaphore(screenshot_concurrency)

_generate_screenshot() 内:
  await semaphore.acquire()   ← 等待空闲槽位
  try:
      html_to_image(...)      ← 截图
  finally:
      semaphore.release()     ← 释放槽位
      page_pool.append(page)  ← 归还页面

预生成任务与前台截图共享同一信号量，前台任务优先（先获取信号量）。
```

## 性能指标

| 场景 | 耗时 | 说明 |
|------|------|------|
| 首次截图 | ~170ms | set_content + screenshot，复用预热页面 |
| 缓存命中 | ~5ms | Redis GET + file exists |
| 预生成命中 | ~0ms | 后台已生成，直接命中缓存 |

## HTML 卡片视觉结构

```
┌──────────────────────────────────┐
│  [宠物图]  宠物名字              [品质]  │  ← header (渐变蓝背景)
│            类型·阶段·Lv.X        菱形    │
├──────────────────────────────────┤
│  📊 战斗属性                            │  ← section
│  ❤️ 生命  520    ████████░░  IV:25     │
│  ⚔️ 攻击  65     ██████░░░░  IV:20     │
│  🛡️ 防御  18     ████░░░░░░  IV:12     │
│  ⚡ 速度  0.58   ███████░░░  IV:22     │
│  💥 暴击  8.0%   █████░░░░░  IV:16     │
│  👻 闪避  4.0%   ███░░░░░░░  IV:10     │
│  🔪 暴伤  150%                          │
│  🩸 吸血  5%                            │
├──────────────────────────────────┤
│  ✨ 经验        1200/6000 (20%)         │  ← EXP 条
│  ████████░░░░░░░░░░░░                    │
├──────────────────────────────────┤
│  技能名    │  一阶段（4s）               │  ← 技能信息（左右布局）
│  技能按阶段 │  随机造成50~70点伤害        │
│  轮流使用   │  ↓                         │
│            │  二阶段（5s）               │
│            │  两段60点伤害               │
├──────────────────────────────────┤
│           猪猪养成                       │  ← footer
└──────────────────────────────────┘
```

### 截图共享策略

- **非进化场景**（领养/属性/训练/休息）：共用同一张截图（UUID scene=""）
- **进化场景**：独立截图（UUID scene="evolve"），额外包含旧→新属性变化预览

## 涉及函数清单

| 函数 | 文件 | 作用 |
|------|------|------|
| `_generate_screenshot()` | pet_game.py | 截图核心：缓存判断、渲染、截图、并发控制 |
| `_pre_generate_screenshot()` | pet_game.py | 后台预生成截图（fire-and-forget） |
| `_build_pet_message()` | pet_game.py | 消息组装：调用 _generate_screenshot + 构建消息 |
| `render_pet_html()` | image_gen.py | 宠物数据 → HTML 卡片（含技能信息区域） |
| `_skill_section_html()` | image_gen.py | 技能信息区域 HTML（左右布局+↓箭头） |
| `html_to_image()` | image_gen.py | Playwright set_content → PNG（支持复用预热页面） |
| `_resolve_image_src()` | image_gen.py | 解析图片 src（file:// 或 http，base64 时不使用） |
| `_stat_row()` | image_gen.py | 单行属性 HTML（含 IV 进度条） |
| `_iv_bar_html()` | image_gen.py | IV 进度条 HTML |
| `_quality_diamond_html()` | image_gen.py | 品质菱形色块 HTML |
| `_exp_bar()` | image_gen.py | 经验条 HTML |
| `generate_screenshot_uuid()` | image_lifecycle.py | 确定性 UUID 生成（非进化 scene=""，进化 scene="evolve"） |
| `cleanup_orphan_files()` | image_lifecycle.py | 同步清理目录所有文件 |
| `daily_cleanup_loop()` | image_lifecycle.py | 每日 0 点兜底清理协程 |
| `schedule_deletion()` | image_lifecycle.py | 异步延迟删除文件（fire-and-forget） |
| `get_screenshot_uuid()` | data_manager.py | Redis 读取截图 UUID 记录 |
| `set_screenshot_uuid()` | data_manager.py | Redis 保存截图 UUID 记录 |
| `build_markdown_with_buttons()` | msg_templates.py | 组合截图 URL + Markdown + 按钮 |
| `get_pet_image_url()` | pet_config.py | 计算宠物形象图 URL |
| `get_pet_image_local_path()` | pet_config.py | 计算本地图片绝对路径 |
