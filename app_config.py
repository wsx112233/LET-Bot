from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CONFIG_PATH = DATA_DIR / "config.json"
_LAST_GOOD_FILE_CONFIG: dict[str, str] = {}

CONFIG_KEYS = [
    "AI_PROVIDER",
    "AI_API_KEY",
    "AI_BASE_URL",
    "AI_MODEL",
    "AI_MODEL_FALLBACKS",
    "AI_TIMEOUT",
    "AI_MAX_RETRIES",
    "AI_CONTENT_LIMIT",
    "SCAN_INTERVAL_MIN",
    "SCAN_INTERVAL_MAX",
    "BLOCKED_SLEEP_SECONDS",
    "TG_BOT_TOKEN",
    "TG_CHAT_ID",
    "TG_PARSE_MODE",
    "TG_DISABLE_WEB_PREVIEW",
    "TZ",
]

DEFAULTS = {
    "AI_PROVIDER": "SiliconFlow",
    "AI_BASE_URL": "https://api.siliconflow.cn/v1",
    "AI_MODEL": "Qwen/Qwen2.5-7B-Instruct",
    "AI_MODEL_FALLBACKS": "Qwen/Qwen3-8B",
    "AI_TIMEOUT": "45",
    "AI_MAX_RETRIES": "0",
    "AI_CONTENT_LIMIT": "8000",
    "SCAN_INTERVAL_MIN": "90",
    "SCAN_INTERVAL_MAX": "180",
    "BLOCKED_SLEEP_SECONDS": "1800",
    "TG_PARSE_MODE": "MarkdownV2",
    "TG_DISABLE_WEB_PREVIEW": "true",
    "TZ": "UTC",
}

SECRET_KEYS = {"AI_API_KEY", "TG_BOT_TOKEN"}
INT_LIMITS = {
    "AI_TIMEOUT": (5, 180),
    "AI_MAX_RETRIES": (0, 3),
    "AI_CONTENT_LIMIT": (1000, 20000),
    "SCAN_INTERVAL_MIN": (30, 86400),
    "SCAN_INTERVAL_MAX": (30, 86400),
    "BLOCKED_SLEEP_SECONDS": (60, 86400),
}
BOOL_KEYS = {"TG_DISABLE_WEB_PREVIEW"}


def _normalize_bool(value: str) -> str:
    return "true" if value.lower() in {"1", "true", "yes", "on"} else "false"


def _normalize_int(key: str, value: str) -> str:
    minimum, maximum = INT_LIMITS[key]
    try:
        parsed = int(value)
    except ValueError:
        parsed = int(DEFAULTS.get(key, minimum))
    return str(max(minimum, min(parsed, maximum)))


def _normalize_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return DEFAULTS["AI_BASE_URL"]
    return value.rstrip("/")


def normalize_config_value(key: str, value: str) -> str:
    value = str(value or "").strip()
    if key in INT_LIMITS:
        return _normalize_int(key, value)
    if key in BOOL_KEYS:
        return _normalize_bool(value)
    if key == "AI_BASE_URL":
        return _normalize_url(value)
    if key == "TG_PARSE_MODE":
        return value if value in {"MarkdownV2", "HTML", ""} else DEFAULTS["TG_PARSE_MODE"]
    return value[:500]


def _read_file_config() -> dict[str, str]:
    global _LAST_GOOD_FILE_CONFIG
    if not CONFIG_PATH.exists():
        return {}
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(_LAST_GOOD_FILE_CONFIG)
    parsed = {
        key: normalize_config_value(key, str(value))
        for key, value in data.items()
        if key in CONFIG_KEYS and value is not None
    }
    _LAST_GOOD_FILE_CONFIG = dict(parsed)
    return parsed


def load_config(mask_secrets: bool = False) -> dict[str, str]:
    file_config = _read_file_config()
    config: dict[str, str] = {}
    for key in CONFIG_KEYS:
        value = file_config.get(key)
        if value is None:
            value = os.getenv(key)
        if value is None and key == "AI_API_KEY":
            value = os.getenv("SILICON_API_KEY")
        if value is None:
            value = DEFAULTS.get(key, "")
        config[key] = str(value)

    if mask_secrets:
        for key in SECRET_KEYS:
            if config.get(key):
                config[key] = "********"
    return config


def save_config(updates: dict[str, object]) -> dict[str, str]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    current = _read_file_config()
    env_config = load_config(mask_secrets=False)

    for key, raw_value in updates.items():
        if key not in CONFIG_KEYS:
            continue
        value = str(raw_value or "").strip()
        if key in SECRET_KEYS and value in {"", "********"}:
            if key in current:
                continue
            value = env_config.get(key, "")
        current[key] = normalize_config_value(key, value)

    tmp_path = CONFIG_PATH.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        tmp_path.chmod(0o600)
    except OSError:
        pass
    tmp_path.replace(CONFIG_PATH)
    try:
        CONFIG_PATH.chmod(0o600)
    except OSError:
        pass
    return load_config(mask_secrets=True)


def get_config_value(key: str, default: str = "") -> str:
    return load_config(mask_secrets=False).get(key, default)


def get_int(key: str, default: int) -> int:
    try:
        return int(get_config_value(key, str(default)))
    except ValueError:
        return default


def get_float(key: str, default: float) -> float:
    try:
        return float(get_config_value(key, str(default)))
    except ValueError:
        return default
