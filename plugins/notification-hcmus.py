import discord
import aiohttp
import asyncio
import feedparser
import logging
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin
from discord.ext import commands, tasks

from util.config import load_notification_channels
from util.state import load_state, save_state
from util.http import create_persistent_session

logger = logging.getLogger(__name__)

_STATE_KEY = "hcmus"
_UTC7 = timezone(timedelta(hours=7))
_TIMEOUT = aiohttp.ClientTimeout(total=30)


class Hcmus(commands.Cog):
    """Scrapes multiple HCMUS pages and notifies on new posts."""

    def __init__(self, bot):
        self.bot = bot
        self.seen_links: dict[str, str] = {}  # {source_key: last_link}
        self.state_loaded = False
        # One persistent session for the lifetime of this Cog; avoids
        # creating a new TCPConnector on every HTTP call (prevents RAM growth).
        self._session = create_persistent_session(_TIMEOUT)
        self.check_new_post.start()

    async def cog_unload(self):  # type: ignore
        self.check_new_post.cancel()
        # Close the shared session so the connector is released cleanly.
        if not self._session.closed:
            await self._session.close()

    # --- State persistence ---

    async def _load_seen(self) -> None:
        state = await load_state(_STATE_KEY)
        self.seen_links = state.get("seen_links", {})
        self.state_loaded = True

    async def _save_seen(self) -> None:
        await save_state(_STATE_KEY, {
            "seen_links": self.seen_links,
            "last_check": datetime.now(_UTC7).isoformat(),
        })

    # --- HTTP helper with retries ---

    async def _fetch_html(self, url: str, retries: int = 2) -> str | None:
        """GET a URL and return its HTML text, with retries on failure."""
        last_error = None
        for attempt in range(retries + 1):
            try:
                async with self._session.get(url) as resp:
                    resp.raise_for_status()
                    return await resp.text()
            except (aiohttp.ClientError, OSError) as e:
                last_error = e
                if attempt < retries:
                    await asyncio.sleep(2 * (attempt + 1))  # backoff: 2s, 4s
                    continue
        logger.error(f"HTTP error for {url} after {retries + 1} attempts: {last_error}")
        return None

    # --- Scrapers (all async) ---

    async def _fetch_hcmus_common(self, url: str) -> tuple[str, str] | None:
        """Scrape an HCMUS WordPress page for the latest post."""
        html = await self._fetch_html(url)
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")
        a_tags = soup.select("a.vc_gitem-link.vc-zone-link")
        if not a_tags:
            return None
        a = a_tags[0]
        title = a.get("title") or a.text.strip()
        href = a.get("href")
        return (title, href) if href else None

    async def fetch_hcmus_main(self) -> tuple[str, str] | None:
        return await self._fetch_hcmus_common(
            "https://hcmus.edu.vn/thong-tin-danh-cho-nguoi-hoc/"
        )

    async def fetch_student_affairs(self) -> tuple[str, str] | None:
        return await self._fetch_hcmus_common(
            "https://hcmus.edu.vn/phong-cong-tac-sinh-vien/"
        )

    async def fetch_exam_schedule(self) -> tuple[str, str] | None:
        """Fetch exam schedule via RSS feed."""
        rss_url = "https://ktdbcl.hcmus.edu.vn/index.php/cong-tac-kh-o-thi/l-ch-thi-h-c-ky?format=feed&type=rss"
        last_error = None
        for attempt in range(3):
            try:
                async with self._session.get(rss_url) as resp:
                    resp.raise_for_status()
                    body = await resp.read()
                    feed = feedparser.parse(body)
                    if feed.entries:
                        entry = feed.entries[0]
                        title = getattr(entry, "title", "").strip()
                        link = getattr(entry, "link", "")
                        if title and link:
                            return (title, link)
                    return None
            except (aiohttp.ClientError, OSError) as e:
                last_error = e
                if attempt < 2:
                    await asyncio.sleep(2 * (attempt + 1))
                    continue
        logger.error(f"HTTP error for exam-schedule RSS after 3 attempts: {last_error}")
        return None

    async def fetch_fit_news(self) -> tuple[str, str] | None:
        html = await self._fetch_html("https://www.fit.hcmus.edu.vn/tin-tuc")
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")
        links = soup.select("div.col-lg-9 a") or soup.select("a[href*='/tin-tuc/']")
        base = "https://www.fit.hcmus.edu.vn/"
        for a in links:
            title = a.text.strip()
            href = a.get("href", "")
            if not title:
                continue
            # Use urljoin so absolute URLs from other domains are not mangled
            href = urljoin(base, href)
            return (title, href)
        return None

    def _get_fetcher(self, key: str):
        """Map source key to its fetcher coroutine. Returns None for unknown keys."""
        return {
            "hcmus/root": self.fetch_hcmus_main,
            "hcmus/student-affairs": self.fetch_student_affairs,
            "hcmus/exam-schedule": self.fetch_exam_schedule,
            "hcmus/fit-news": self.fetch_fit_news,
        }.get(key)

    # --- Main loop ---

    @tasks.loop(minutes=10)
    async def check_new_post(self):
        try:
            if not self.state_loaded:
                await self._load_seen()

            logger.info("Fetching sys@hcmus...")
            channels = load_notification_channels("feeds")
            source_keys = ["hcmus/root", "hcmus/exam-schedule", "hcmus/fit-news", "hcmus/student-affairs"]

            # First time ever — seed links, don't spam
            if not self.seen_links:
                for key in source_keys:
                    fetcher = self._get_fetcher(key)
                    if not fetcher:
                        continue
                    post = await fetcher()
                    if post:
                        self.seen_links[key] = post[1]
                await self._save_seen()
                logger.info(f"sys@hcmus: seeded {len(self.seen_links)} links (first run).")
                return

            # Check each source for new posts
            for key in source_keys:
                fetcher = self._get_fetcher(key)
                if not fetcher:
                    logger.warning(f"No fetcher registered for source key: {key}")
                    continue
                post = await fetcher()
                if not post:
                    continue

                title, link = post
                if self.seen_links.get(key) == link:
                    continue  # Same as last time

                self.seen_links[key] = link

                if channels:
                    for channel_id in channels:
                        channel = self.bot.get_channel(channel_id)
                        if not channel:
                            continue
                        embed = discord.Embed(
                            title=f"📰 | {title}",
                            url=link,
                            color=discord.Colour.blue(),
                            timestamp=datetime.now(_UTC7),
                        )
                        embed.set_footer(text=key)
                        try:
                            await channel.send(embed=embed)
                        except discord.Forbidden:
                            logger.warning(
                                f"No send permission in channel {channel_id}, skipping."
                            )
                        except discord.HTTPException as e:
                            logger.error(f"Failed to send embed to channel {channel_id}: {e}")
                        else:
                            logger.info(f"NEW POST! {key}: {title}")

            await self._save_seen()

        except Exception as e:
            logger.error(f"ERROR checking sys@hcmus: {e}")

    @check_new_post.before_loop
    async def before_check_new_post(self):
        await self.bot.wait_until_ready()

    # --- Manual check command ---

    @commands.hybrid_command(
        name="check-hcmus-root",
        description="Danh sách các thông báo mới của trường ĐH KHTN",
    )
    async def check_hcmus(self, ctx: commands.Context):
        await ctx.defer()
        source_keys = ["hcmus/root", "hcmus/exam-schedule", "hcmus/fit-news", "hcmus/student-affairs"]

        embed = discord.Embed(
            title="Latest HCMUS posts",
            color=discord.Colour.blue(),
            timestamp=datetime.now(_UTC7),
        )
        found = 0
        for key in source_keys:
            fetcher = self._get_fetcher(key)
            if not fetcher:
                logger.warning(f"No fetcher registered for source key: {key}")
                continue
            post = await fetcher()
            if not post:
                continue
            title, link = post
            self.seen_links[key] = link
            embed.add_field(name=key, value=f"[{title}]({link})", inline=False)
            found += 1

        if not found:
            embed.description = "No posts found."

        await self._save_seen()
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Hcmus(bot))