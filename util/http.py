"""
Shared aiohttp utilities for the bot.

Provides a DNS resolver and a pre-configured connector factory
so all HTTP requests (bot gateway + plugins) resolve DNS consistently
and use standard browser headers to avoid WAF/Cloudflare blocks.
"""

import asyncio
import socket
import aiohttp

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
}


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
    """Create an aiohttp session with LoopSafeResolver and standard headers."""
    return aiohttp.ClientSession(
        connector=create_connector(),
        timeout=timeout or aiohttp.ClientTimeout(total=30),
        headers=DEFAULT_HEADERS,
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
        headers=DEFAULT_HEADERS,
    )
