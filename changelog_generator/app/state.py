"""Persistent state management with atomic writes."""

import json
import logging
import os
import tempfile
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

STATE_DIR = "/addon_configs/changelog_generator"
STATE_FILE = os.path.join(STATE_DIR, "state.json")

DEFAULT_STATE = {
    "last_run_commit": None,
    "last_run_time": None,
    "history": [],
}


def _ensure_dir():
    os.makedirs(STATE_DIR, exist_ok=True)


def load_state() -> dict:
    """Load state from disk. Returns default state on any error."""
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Validate structure
        if not isinstance(data, dict):
            raise ValueError("State is not a dict")
        data.setdefault("last_run_commit", None)
        data.setdefault("last_run_time", None)
        data.setdefault("history", [])
        return data
    except FileNotFoundError:
        logger.info("No state file found, starting fresh")
        return dict(DEFAULT_STATE)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Corrupt state file, resetting: %s", e)
        return dict(DEFAULT_STATE)


def save_state(state: dict):
    """Atomic write: write to temp file then rename."""
    _ensure_dir()
    try:
        fd, tmp_path = tempfile.mkstemp(dir=STATE_DIR, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, STATE_FILE)
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except Exception as e:
        logger.error("Failed to save state: %s", e)
        raise


def update_state_after_run(
    head_commit: str,
    changelog: str,
    metadata: dict,
    history_count: int,
):
    """Update state after successful changelog generation."""
    state = load_state()
    state["last_run_commit"] = head_commit
    state["last_run_time"] = datetime.now(timezone.utc).isoformat()

    entry = {
        "generated_at": metadata["generated_at"],
        "head_commit": head_commit,
        "commit_count": metadata["commit_count"],
        "changelog": changelog,
        "tokens_used": metadata.get("tokens_used", 0),
    }
    state["history"].insert(0, entry)
    state["history"] = state["history"][:history_count]

    save_state(state)


def seconds_since_last_run(state: dict) -> float | None:
    """Return seconds since last run, or None if never run."""
    last = state.get("last_run_time")
    if not last:
        return None
    try:
        last_dt = datetime.fromisoformat(last)
        now = datetime.now(timezone.utc)
        return (now - last_dt).total_seconds()
    except (ValueError, TypeError):
        return None
