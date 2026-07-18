"""
Shared aiohttp utilities for the bot.

Provides a DNS resolver and a pre-configured connector factory
so all HTTP requests (bot gateway + plugins) resolve DNS consistently.
"""

import asyncio
import socket
import aiohttp


class LoopSafeResolver(aiohttp.abc.AbstractResolver):
    """DNS resolver that uses the running event loop instead of creating a new one."""

    async def resolve(self, host, port=0, family=socket.AF_UNSPEC):
        infos = await asyncio.get_running_loop().getaddrinfo(
            host, port,
            type=socket.SOCK_STREAM,
            family=family,
            proto=socket.IPPROTO_TCP,
        )
        return [
            {
                "hostname": host,
                "host": addr[4][0],
                "port": addr[4][1],
                "family": addr[0],
                "proto": addr[2],
                "flags": 0,
            }
            for addr in infos
        ]

    async def close(self):
        pass


def create_connector() -> aiohttp.TCPConnector:
    """Create a TCPConnector with the LoopSafeResolver."""
    return aiohttp.TCPConnector(resolver=LoopSafeResolver())


def create_session(timeout: aiohttp.ClientTimeout | None = None) -> aiohttp.ClientSession:
    """Create an aiohttp session with LoopSafeResolver and optional timeout.

    NOTE: Prefer reusing a long-lived session (created once per Cog and closed
    in cog_unload) instead of calling this repeatedly, to avoid TCPConnector
    accumulation and the associated RAM growth.
    """
    return aiohttp.ClientSession(
        connector=create_connector(),
        timeout=timeout or aiohttp.ClientTimeout(total=30),
        headers={"User-Agent": "Mozilla/5.0"},
    )


def create_persistent_session(timeout: aiohttp.ClientTimeout | None = None) -> aiohttp.ClientSession:
    """Create a long-lived aiohttp session intended to be reused across requests.

    The caller is responsible for closing it (e.g. in cog_unload).
    Uses connector_owner=True so closing the session also closes the connector.
    """
    return aiohttp.ClientSession(
        connector=create_connector(),
        connector_owner=True,
        timeout=timeout or aiohttp.ClientTimeout(total=30),
        headers={"User-Agent": "Mozilla/5.0"},
    )
