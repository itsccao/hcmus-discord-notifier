"""
Bot configuration manager.

Handles reading/writing JSON config file in the data/ directory:
- data.json — allowed servers, configured notification channels, and ping roles.

Uses atomic writes (temp + rename) for crash safety.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_DATA_FILE = "data.json"
_UTC7 = timezone(timedelta(hours=7))


# ---------------------------------------------------------------------------
# Generic JSON helpers
# ---------------------------------------------------------------------------

def _read_data() -> dict:
    """Read data.json. Returns empty dict structure on missing/corrupt."""
    path = _DATA_DIR / _DATA_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"servers": {}}
        if "servers" not in data or not isinstance(data["servers"], dict):
            data["servers"] = {}
        return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {"servers": {}}


def _write_data(data: dict) -> None:
    """Atomically write data.json."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = _DATA_DIR / _DATA_FILE
    tmp = path.with_suffix(".tmp")
    data["last_updated"] = datetime.now(_UTC7).isoformat()
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


# ---------------------------------------------------------------------------
# Server and Channel Configuration
# ---------------------------------------------------------------------------

def load_allowed_servers() -> list[int]:
    """Return list of allowed guild IDs."""
    data = _read_data()
    return [int(gid) for gid in data.get("servers", {}).keys()]


def is_server_allowed(guild_id: int) -> bool:
    """Check if a guild is in the allowed servers list."""
    servers = load_allowed_servers()
    return guild_id in servers


def add_allowed_server(guild_id: int, channel_id: int | None = None, role_id: int | None = None) -> bool:
    """Add a guild to the allow-list. Returns False if already present."""
    data = _read_data()
    servers = data.setdefault("servers", {})
    guild_id_str = str(guild_id)
    if guild_id_str in servers:
        return False
    servers[guild_id_str] = {
        "channel_id": channel_id,
        "role_id": role_id,
    }
    _write_data(data)
    return True


def remove_allowed_server(guild_id: int) -> bool:
    """Remove a guild from the allow-list. Returns False if not found."""
    data = _read_data()
    servers = data.setdefault("servers", {})
    guild_id_str = str(guild_id)
    if guild_id_str not in servers:
        return False
    del servers[guild_id_str]
    _write_data(data)
    return True


def set_server_config(guild_id: int, channel_id: int, role_id: int | None = None) -> None:
    """Set or overwrite notification channel and ping role for a server."""
    data = _read_data()
    servers = data.setdefault("servers", {})
    servers[str(guild_id)] = {
        "channel_id": channel_id,
        "role_id": role_id,
    }
    _write_data(data)


def get_server_config(guild_id: int) -> dict | None:
    """Get the configuration for a specific server."""
    data = _read_data()
    return data.get("servers", {}).get(str(guild_id))


def get_all_notify_targets() -> list[dict]:
    """
    Return all configured notification targets.
    Each item is a dict: {'guild_id': int, 'channel_id': int, 'role_id': int | None}
    """
    data = _read_data()
    targets = []
    for gid_str, cfg in data.get("servers", {}).items():
        if isinstance(cfg, dict) and cfg.get("channel_id"):
            targets.append({
                "guild_id": int(gid_str),
                "channel_id": int(cfg["channel_id"]),
                "role_id": int(cfg["role_id"]) if cfg.get("role_id") else None,
            })
    return targets
