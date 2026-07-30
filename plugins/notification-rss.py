"""
notification-rss.py
-------------------
Theo dõi nhiều RSS feed / WordPress REST API và gửi thông báo Discord khi có
bài đăng mới.

Để thêm hoặc bỏ feed, chỉ cần chỉnh sửa danh sách RSS_FEEDS bên dưới.
Mỗi entry là một dict với các key:
    key   – khóa duy nhất để lưu state (không được trùng)
    name  – tên hiển thị trong thông báo Discord
    url   – URL của feed
    type  – "rss" (feedparser) | "wp_json" (WordPress REST API v2 JSON)
"""

import discord
import aiohttp
import asyncio
import feedparser
import calendar
import logging
from datetime import datetime, timezone, timedelta
from discord.ext import commands, tasks

from util.config import load_notification_channels
from util.state import load_state, save_state
from util.http import create_persistent_session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ★  Cấu hình feed — chỉ cần sửa ở đây để thêm/xoá nguồn  ★
# ---------------------------------------------------------------------------
RSS_FEEDS: list[dict] = [
    {
        "key": "rss/hcmus-nguoi-hoc",
        "name": "Thông tin người học",
        "url": "https://hcmus.edu.vn/wp-json/wp/v2/posts?categories=3&per_page=10",
        "type": "wp_json",
    },
    {
        "key": "rss/fit-hcmus",
        "name": "fit@hcmus",
        "url": "https://www.fit.hcmus.edu.vn/vn/feed.aspx",
        "type": "rss",
    },
    {
        "key": "rss/ktdbcl-lich-thi",
        "name": "Phòng Khảo thí & Đảm bảo chất lượng - Lịch thi",
        "url": "https://ktdbcl.hcmus.edu.vn/index.php/cong-tac-kh-o-thi/l-ch-thi-h-c-ky?format=feed&type=rss",
        "type": "rss",
    },
    {
        "key": "rss/ktdbcl-thong-bao",
        "name": "Phòng Khảo thí & Đảm bảo chất lượng - Thông báo",
        "url": "https://ktdbcl.hcmus.edu.vn/index.php/thong-bao?format=feed&type=rss",
        "type": "rss",
    },
]
# ---------------------------------------------------------------------------

_STATE_KEY = "rss-feeds"
_MAX_SEEN = 50          # số link tối đa giữ lại per feed
_UTC7 = timezone(timedelta(hours=7))
_TIMEOUT = aiohttp.ClientTimeout(total=30)


def _fmt_time(dt: datetime | None) -> str:
    """Format a datetime to HH:MM AM/PM dd/mm/yyyy UTC+7."""
    if dt is None:
        return "Không rõ"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt_vn = dt.astimezone(_UTC7)
    return dt_vn.strftime("%I:%M %p %d/%m/%Y")


def _parse_rss_datetime(entry) -> datetime | None:
    """Extract datetime from a feedparser entry.

    NOTE: Vietnamese RSS servers (FIT, KTDBCL, ...) write local time (UTC+7)
    in the pubDate field but label it as 'GMT'. We attach _UTC7 directly
    to avoid double-converting (+7 h on top of an already-local timestamp).
    """
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                # Build a naive datetime from the struct then attach UTC+7
                # (do NOT use calendar.timegm which treats the struct as UTC)
                naive = datetime(*t[:6])
                return naive.replace(tzinfo=_UTC7)
            except Exception:
                continue
    return None


def _parse_wp_datetime(date_str: str | None) -> datetime | None:
    """Parse WordPress REST API date string (ISO 8601)."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except ValueError:
        return None


class RssFeedNotifier(commands.Cog):
    """Polls multiple RSS/JSON feeds and notifies Discord channels on new posts."""

    def __init__(self, bot):
        self.bot = bot
        # {feed_key: [link, ...]}  — list preserves insertion order
        self.seen: dict[str, list[str]] = {}
        self.state_loaded = False
        self._session = create_persistent_session(_TIMEOUT)
        self.check_feeds.start()

    async def cog_unload(self):  # type: ignore
        self.check_feeds.cancel()
        if not self._session.closed:
            await self._session.close()

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    async def _load_seen(self) -> None:
        state = await load_state(_STATE_KEY)
        self.seen = state.get("seen", {})
        for key in list(self.seen.keys()):
            if not isinstance(self.seen[key], list):
                self.seen[key] = [self.seen[key]] if self.seen[key] else []
        self.state_loaded = True
        logger.info(f"[rss] State loaded — tracking {len(self.seen)} feed(s).")

    async def _save_seen(self) -> None:
        # Giớ hạn an toàn: list mỏi feed chỉ phát triển bằng cách append link mới
        # từ feed (có số item cố định), nên không cần cắt. _MAX_SEEN là lưới an toàn
        # dự phòng nếu có bug khiến list phồng to bất thường.
        safe = {k: v[-_MAX_SEEN:] for k, v in self.seen.items()}
        await save_state(_STATE_KEY, {
            "seen": safe,
            "last_check": datetime.now(_UTC7).isoformat(),
        })

    # ------------------------------------------------------------------
    # Fetchers
    # ------------------------------------------------------------------

    async def _fetch_bytes(self, url: str, retries: int = 2) -> bytes | None:
        last_error = None
        for attempt in range(retries + 1):
            try:
                async with self._session.get(url) as resp:
                    resp.raise_for_status()
                    return await resp.read()
            except (aiohttp.ClientError, OSError) as e:
                last_error = e
                if attempt < retries:
                    await asyncio.sleep(2 * (attempt + 1))
        logger.error(f"[rss] HTTP error for {url} after {retries + 1} attempt(s): {last_error}")
        return None

    async def _fetch_json(self, url: str, retries: int = 2):
        last_error = None
        for attempt in range(retries + 1):
            try:
                async with self._session.get(url) as resp:
                    resp.raise_for_status()
                    return await resp.json(content_type=None)
            except (aiohttp.ClientError, OSError) as e:
                last_error = e
                if attempt < retries:
                    await asyncio.sleep(2 * (attempt + 1))
        logger.error(f"[rss] JSON HTTP error for {url} after {retries + 1} attempt(s): {last_error}")
        return None

    async def _get_entries(self, feed_cfg: dict) -> list[dict]:
        """
        Return a list of normalised entries: {title, link, dt}.
        Newest-first order is preserved as returned by the source.
        """
        feed_type = feed_cfg["type"]
        url = feed_cfg["url"]
        entries = []

        if feed_type == "wp_json":
            data = await self._fetch_json(url)
            if not isinstance(data, list):
                return []
            for post in data:
                title = post.get("title", {}).get("rendered", "").strip() or "Thông báo mới"
                link = post.get("link", "")
                date_gmt = post.get("date_gmt")
                date_local = post.get("date")
                # Prefer date_gmt (pure UTC); fall back to date (site local)
                if date_gmt and not date_gmt.endswith("Z"):
                    date_gmt = date_gmt + "Z"
                dt = _parse_wp_datetime(date_gmt) or _parse_wp_datetime(date_local)
                if link:
                    entries.append({"title": title, "link": link, "dt": dt})

        elif feed_type == "rss":
            body = await self._fetch_bytes(url)
            if not body:
                return []
            feed = feedparser.parse(body)
            for entry in feed.entries:
                title = getattr(entry, "title", "").strip() or "Thông báo mới"
                link = getattr(entry, "link", "")
                dt = _parse_rss_datetime(entry)
                if link:
                    entries.append({"title": title, "link": link, "dt": dt})

        else:
            logger.warning(f"[rss] Unknown feed type '{feed_type}' for {feed_cfg['key']}")

        return entries

    # ------------------------------------------------------------------
    # Main polling loop
    # ------------------------------------------------------------------

    @tasks.loop(minutes=10)
    async def check_feeds(self):
        try:
            if not self.state_loaded:
                await self._load_seen()

            logger.info("[rss] Checking all feeds...")
            channels = load_notification_channels("feeds")

            first_run = not self.seen  # True when state file is brand-new

            total_new = 0
            for feed_cfg in RSS_FEEDS:
                key = feed_cfg["key"]
                name = feed_cfg["name"]

                entries = await self._get_entries(feed_cfg)
                if not entries:
                    logger.warning(f"[rss] No entries found for '{name}'.")
                    continue

                # Chỉ xét _MAX_SEEN bài mới nhất (feed trả về newest-first).
                # Đảm bảo window so sánh không vượt quá số link đã lưu trong state.
                entries = entries[:_MAX_SEEN]

                seen_for_feed: list[str] = self.seen.get(key, [])

                if first_run or not seen_for_feed:
                    # Seed — record what exists, don't notify
                    self.seen[key] = [e["link"] for e in entries]
                    logger.info(f"[rss] '{name}': seeded {len(entries)} link(s) (first run).")
                    continue

                # Entries whose link we have not seen yet
                new_entries = [e for e in entries if e["link"] not in seen_for_feed]

                if new_entries:
                    logger.info(f"[rss] '{name}': {len(new_entries)} new post(s).")
                    total_new += len(new_entries)
                    if channels:
                        for channel_id in channels:
                            channel = self.bot.get_channel(channel_id)
                            if not channel:
                                continue
                            # Send oldest-first so Discord feed reads top-to-bottom
                            for entry in reversed(new_entries):
                                embed = self._build_embed(entry, name)
                                try:
                                    await channel.send(embed=embed)
                                except discord.Forbidden:
                                    logger.warning(
                                        f"[rss] No send permission in channel {channel_id}."
                                    )
                                except discord.HTTPException as e:
                                    logger.error(
                                        f"[rss] Failed to send to channel {channel_id}: {e}"
                                    )
                                else:
                                    logger.info(f"[rss] Sent: [{name}] {entry['title']}")

                    # Append new links to seen list
                    for entry in new_entries:
                        if entry["link"] not in self.seen.get(key, []):
                            self.seen.setdefault(key, []).append(entry["link"])
                else:
                    logger.info(f"[rss] '{name}': no new posts.")

            await self._save_seen()

            if total_new:
                logger.info(f"[rss] Done — {total_new} new post(s) sent across all feeds.")
            else:
                logger.info("[rss] Done — no new posts across all feeds.")

        except Exception as e:
            logger.error(f"[rss] Unexpected error in check_feeds: {e}", exc_info=True)

    @check_feeds.before_loop
    async def before_check_feeds(self):
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------------
    # Message builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_embed(entry: dict, feed_name: str) -> discord.Embed:
        """
        Tạo embed Discord:
            📰 | <title>  (clickable → link)
            Lúc: HH:MM AM/PM dd/mm/yyyy
            Thuộc: <tên rss>  (footer)
        """
        title = entry["title"]
        link = entry["link"]
        time_str = _fmt_time(entry.get("dt"))
        embed = discord.Embed(
            title=f"📰 | {title}",
            url=link,
            description=f"Lúc: {time_str}\nThuộc: {feed_name}",
            color=discord.Colour.blurple(),
            timestamp=datetime.now(_UTC7),
        )
        return embed

    # ------------------------------------------------------------------
    # Manual check slash command
    # ------------------------------------------------------------------

    @commands.hybrid_command(
        name="check-rss",
        description="Xem bài đăng mới nhất từ các RSS feed đang theo dõi.",
    )
    async def check_rss(self, ctx: commands.Context):
        await ctx.defer()

        lines = []
        for feed_cfg in RSS_FEEDS:
            name = feed_cfg["name"]
            entries = await self._get_entries(feed_cfg)
            if not entries:
                lines.append(f"**{name}**: *(không lấy được dữ liệu)*")
                continue
            e = entries[0]
            time_str = _fmt_time(e.get("dt"))
            lines.append(
                f"**{name}**\n"
                f"└ [{e['title']}](<{e['link']}>)  ·  {time_str}"
            )

        embed = discord.Embed(
            title="📡 RSS Feeds — bài đăng mới nhất",
            description="\n\n".join(lines) or "Không có dữ liệu.",
            color=discord.Colour.blurple(),
            timestamp=datetime.now(_UTC7),
        )
        embed.set_footer(text="Cập nhật mỗi 10 phút")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(RssFeedNotifier(bot))
