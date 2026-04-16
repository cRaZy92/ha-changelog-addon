"""Safe options reader for addon configuration."""

import json
import logging
import os

logger = logging.getLogger(__name__)

OPTIONS_PATH = "/data/options.json"
DEFAULT_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "default_system_prompt.md")

DEFAULTS = {
    "openai_model": "gpt-4o-mini",
    "system_prompt": "",
    "max_diff_chars": 100000,
    "excluded_paths": ["custom_components/"],
    "cooldown_seconds": 60,
    "history_count": 20,
}


class Config:
    """Holds validated addon configuration."""

    def __init__(self, data: dict):
        self.openai_api_key: str = data.get("openai_api_key", "")
        self.openai_model: str = data.get("openai_model") or DEFAULTS["openai_model"]
        self.max_diff_chars: int = _clamp(
            int(data.get("max_diff_chars") or DEFAULTS["max_diff_chars"]), 10000, 500000
        )
        self.excluded_paths: list[str] = data.get("excluded_paths") or DEFAULTS["excluded_paths"]
        self.cooldown_seconds: int = _clamp(
            int(data.get("cooldown_seconds") or DEFAULTS["cooldown_seconds"]), 10, 600
        )
        self.history_count: int = _clamp(
            int(data.get("history_count") or DEFAULTS["history_count"]), 1, 100
        )

        # System prompt: use provided or load default
        custom_prompt = (data.get("system_prompt") or "").strip()
        if custom_prompt:
            self.system_prompt = custom_prompt
        else:
            self.system_prompt = _load_default_prompt()


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def _load_default_prompt() -> str:
    try:
        with open(DEFAULT_PROMPT_PATH, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        logger.warning("Default system prompt not found at %s", DEFAULT_PROMPT_PATH)
        return "You are a helpful assistant that generates changelogs from git diffs."


def load_config() -> Config:
    """Load and validate addon options. Re-reads file each call so option changes take effect."""
    try:
        with open(OPTIONS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.error("Options file not found at %s, using defaults", OPTIONS_PATH)
        data = {}
    except json.JSONDecodeError:
        logger.error("Options file is corrupt, using defaults")
        data = {}

    config = Config(data)

    if not config.openai_api_key:
        logger.warning("OpenAI API key is not set")

    return config


def save_options(updates: dict):
    """Merge updates into options file and write back."""
    try:
        with open(OPTIONS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}

    data.update(updates)

    import tempfile
    fd, tmp_path = tempfile.mkstemp(
        dir=os.path.dirname(OPTIONS_PATH) or ".", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, OPTIONS_PATH)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def mask_api_key(key: str) -> str:
    """Mask API key for safe logging. Never log full key."""
    if not key or len(key) < 8:
        return "***"
    return f"{key[:3]}...{key[-4:]}"
