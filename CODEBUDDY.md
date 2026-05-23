# CODEBUDDY.md

This file provides guidance to CodeBuddy Code when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the bot
python main.py

# Run all tests (no real Redis required - tests use InMemoryRedis mock)
python -m unittest discover test -v

# Run a single test file
python -m unittest test.test_data_manager -v
python -m unittest test.test_signature -v

# Run a specific test class or method
python -m unittest test.test_data_manager.TestExpAndLevelUp -v
python -m unittest test.test_data_manager.TestExpAndLevelUp.test_add_exp_persists_to_redis -v
```

## Architecture

This is a QQ bot (pet-raising game) built on the QQ Open Platform API v2, using **Webhook mode** (aiohttp HTTPS server receives push events, no persistent connection needed).

### Request Flow

```
QQ Platform → webhook POST → main.py → QQBot.webhook_handler()
  ├─ op=13 → URL verification (Ed25519 signature)
  └─ op=0  → event dispatch
       ├─ GROUP_AT_MESSAGE_CREATE → handle_group_at() → send_group_reply()
       └─ C2C_MESSAGE_CREATE      → handle_c2c()      → send_c2c_reply()
```

### Source File Roles

| File | Role |
|------|------|
| `main.py` | Entry point: config validation, QQBot lifecycle, Windows asyncio policy |
| `src/bot.py` | `QQBot` class: aiohttp web server, webhook handling, Ed25519 signature verification, QQ API HTTP calls, message sending |
| `src/handler.py` | Parses commands from message text (strips @mentions, extracts `/command arg`), routes to `PetGame` methods via a dict of lambdas. Supports both Chinese and English command aliases. |
| `src/pet_game.py` | `PetGame` class: all game logic — adopt, feed, play, rest, heal, work, train, rename, abandon, status (with decay application), leaderboard, help. Uses cooldowns and stat requirements. Exports a global `game` singleton. |
| `src/data_manager.py` | `DataManager` class: Redis CRUD for `Pet` dataclass. Handles cooldowns (hash), leaderboard (sorted set), and natural attribute decay (time-based). Exports a global `data_manager` singleton. Uses synchronous `redis` (not `redis.asyncio`). |
| `src/token_manager.py` | `TokenManager` class: fetches QQ API access token via HTTP, stores in Redis with expiry tracking, runs background async refresh loop. Exports a global `token_manager` singleton. Uses `redis.asyncio`. |
| `src/config.py` | Loads `config.yaml` (public, committed) and `bot_config.yaml` (credentials, gitignored), merges them into a single `config` dict. |
| `src/msg_templates.py` | Builders for QQ platform structured messages: Markdown templates (`msg_type=2`) and inline keyboard buttons (`msg_type=0 + keyboard`). |

### Configuration

Two YAML files, merged by `src/config.py`:
- **`config.yaml`** (committed): webhook settings, Redis connection, image paths, game config (pet types, exp values, decay interval)
- **`bot_config.yaml`** (gitignored): `bot.app_id`, `bot.token`, `bot.secret`, `bot.sandbox`

Access config anywhere via `from src.config import config`.

### Data Model

`Pet` is a `@dataclass` with four 0-100 attributes: `satiety`, `mood`, `health`, `energy`. Death occurs when `health <= 0 or satiety <= 0`. Leveling uses `max_exp = 100 * level`; on level-up, remaining exp carries over and all four stats get +20.

### Redis Key Schema

```
qqbot:pet:{user_id}          → JSON-serialized Pet (String)
qqbot:cooldown:{user_id}     → action→expiry_timestamp (Hash)
qqbot:leaderboard            → user_id→score (Sorted Set, score = level + exp/1000)
qqbot:leaderboard:detail     → user_id→JSON detail (Hash)
qqbot:access_token           → QQ API access token (String, with TTL)
qqbot:access_token_expires_at → expiry timestamp (String, with TTL)
```

### Message Reply Types

Handler functions can return:
- `str` → sent as plain text (`msg_type=0`)
- `dict` → sent as structured message (supports `msg_type`, `keyboard`, `markdown` fields)

Currently the game only returns strings; templates from `msg_templates.py` are available but not wired into the game logic.

### Testing

Tests live in `test/` and use `unittest`. The data manager tests mock Redis with an `InMemoryRedis` class — no real Redis needed. Patch order is critical: `redis.Redis` is patched *before* importing `DataManager` (see `test_data_manager.py` line 130-136). The signature test verifies Ed25519 derivation matches the Go reference implementation from QQ platform docs.

### Key Dependencies

- `aiohttp` — async HTTP server + API client
- `redis` (sync) — `src/data_manager.py` and `src/token_manager.py` (async variant)
- `pynacl` (via `nacl`) — Ed25519 signing for webhook URL verification
- `cryptography` — self-signed SSL cert generation (optional)
- `PyYAML` — config file parsing
