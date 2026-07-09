"""
Bot configuration manager.

Handles reading/writing JSON config files in the data/ directory:
- allowed_servers.json  — guilds the bot is permitted to operate in
- notification_channels.json — channels grouped by notification type

Uses atomic writes (temp + rename) for crash safety.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_UTC7 = timezone(timedelta(hours=7))


# ---------------------------------------------------------------------------
# Generic JSON helpers
# ---------------------------------------------------------------------------

def _read_json(filename: str) -> dict:
    """Read a JSON file from data/. Returns empty dict on missing/corrupt."""
    path = _DATA_DIR / filename
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_json(filename: str, data: dict) -> None:
    """Atomically write a JSON file to data/."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = _DATA_DIR / filename
    tmp = path.with_suffix(".tmp")
    data["last_updated"] = datetime.now(_UTC7).isoformat()
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


# ---------------------------------------------------------------------------
# Allowed servers
# ---------------------------------------------------------------------------

_SERVERS_FILE = "allowed_servers.json"


def load_allowed_servers() -> list[int]:
    """Return list of allowed guild IDs. Empty list = no restriction."""
    data = _read_json(_SERVERS_FILE)
    return [int(gid) for gid in data.get("servers", {}).keys()]


def add_allowed_server(guild_id: int) -> bool:
    """Add a guild to the allow-list. Returns False if already present."""
    data = _read_json(_SERVERS_FILE)
    servers = data.get("servers", {})
    guild_id_str = str(guild_id)
    if guild_id_str in servers:
        return False
    servers[guild_id_str] = True
    data["servers"] = servers
    _write_json(_SERVERS_FILE, data)
    return True


def remove_allowed_server(guild_id: int) -> bool:
    """Remove a guild from the allow-list. Returns False if not found."""
    data = _read_json(_SERVERS_FILE)
    servers = data.get("servers", {})
    guild_id_str = str(guild_id)
    if guild_id_str not in servers:
        return False
    del servers[guild_id_str]
    data["servers"] = servers
    _write_json(_SERVERS_FILE, data)
    return True


def is_server_allowed(guild_id: int) -> bool:
    """Check if a guild is allowed. Returns True if allow-list is empty."""
    servers = load_allowed_servers()
    return not servers or guild_id in servers


# ---------------------------------------------------------------------------
# Notification channels
# ---------------------------------------------------------------------------

_CHANNELS_FILE = "allowed_notify_channels.json"


def load_notification_channels(group: str = "feeds") -> list[int]:
    """Load channel IDs for a notification group."""
    data = _read_json(_CHANNELS_FILE)
    channels = data.get(group, {})
    if not isinstance(channels, dict):
        return []
    return [int(cid) for cid in channels.keys()]


def add_notification_channel(group: str, channel_id: int) -> bool:
    """Add a channel to a notification group. Returns False if already present."""
    data = _read_json(_CHANNELS_FILE)
    channels = data.get(group, {})
    channel_id_str = str(channel_id)
    if channel_id_str in channels:
        return False
    channels[channel_id_str] = True
    data[group] = channels
    _write_json(_CHANNELS_FILE, data)
    return True


def remove_notification_channel(group: str, channel_id: int) -> bool:
    """Remove a channel from a notification group. Returns False if not found."""
    data = _read_json(_CHANNELS_FILE)
    channels = data.get(group, {})
    channel_id_str = str(channel_id)
    if channel_id_str not in channels:
        return False
    del channels[channel_id_str]
    data[group] = channels
    _write_json(_CHANNELS_FILE, data)
    return True


def list_notification_groups() -> dict[str, list[int]]:
    """Return all notification groups and their channels."""
    data = _read_json(_CHANNELS_FILE)
    return {
        k: [int(cid) for cid in v.keys()]
        for k, v in data.items()
        if k != "last_updated" and isinstance(v, dict)
    }
