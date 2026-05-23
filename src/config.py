"""
config.py - 配置加载模块

从 config.yaml 加载公共配置，从 bot_config.yaml 加载机器人敏感凭证
"""
import yaml
from pathlib import Path

_CONFIG_DIR = Path(__file__).parent.parent


def _load_yaml(filename: str) -> dict:
    """加载单个 YAML 文件"""
    config_path = _CONFIG_DIR / filename
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# 加载公共配置
config: dict = _load_yaml("config.yaml")

# 加载敏感凭证配置并合并到 config["bot"]
_bot_config: dict = _load_yaml("bot_config.yaml")
config["bot"] = _bot_config.get("bot", {})
