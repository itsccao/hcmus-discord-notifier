"""
Persistent JSON state manager for bot plugins.

Provides atomic read/write of plugin state to a shared JSON file.
Uses temp-file + os.replace for crash-safe writes.
"""

import json
import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_STATE_DIR = Path(__file__).resolve().parent.parent / "data"
_STATE_FILE = _STATE_DIR / "notification_state.json"
_lock = asyncio.Lock()


def _read_all() -> dict:
    """Read the entire state file. Returns empty dict if missing/corrupt."""
    try:
        return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_all(data: dict) -> None:
    """Atomically write state: write to .tmp then rename."""
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(_STATE_FILE)


async def load_state(key: str) -> dict:
    """Load the state dict for a specific plugin key."""
    async with _lock:
        return _read_all().get(key, {})


async def save_state(key: str, data: dict) -> None:
    """Save the state dict for a specific plugin key."""
    async with _lock:
        all_state = _read_all()
        all_state[key] = data
        _write_all(all_state)
