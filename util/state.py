"""
Persistent JSON state manager for bot plugins.

Provides atomic read/write of plugin state to a shared JSON file.
Uses asyncio.to_thread to prevent blocking the asyncio event loop / Discord gateway heartbeat.
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
    """Atomically write state: write to .tmp then replace, with fallback."""
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _STATE_FILE.with_suffix(".tmp")
    content = json.dumps(data, indent=2, ensure_ascii=False)
    tmp.write_text(content, encoding="utf-8")
    try:
        tmp.replace(_STATE_FILE)
    except OSError:
        # Fallback if atomic replace fails across filesystems / overlay mounts
        _STATE_FILE.write_text(content, encoding="utf-8")
        try:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
        except OSError:
            pass


async def load_state(key: str) -> dict:
    """Load the state dict for a specific plugin key asynchronously."""
    async with _lock:
        all_state = await asyncio.to_thread(_read_all)
        return all_state.get(key, {})


async def save_state(key: str, data: dict) -> None:
    """Save the state dict for a specific plugin key asynchronously."""
    async with _lock:
        all_state = await asyncio.to_thread(_read_all)
        all_state[key] = data
        await asyncio.to_thread(_write_all, all_state)
