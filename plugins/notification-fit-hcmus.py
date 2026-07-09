import discord
import aiohttp
import asyncio
import feedparser
import logging
from datetime import datetime, timezone, timedelta
from discord.ext import commands, tasks

from util.config import load_notification_channels
from util.state import load_state, save_state
from util.http import create_session

logger = logging.getLogger(__name__)

_STATE_KEY = "fit-hcmus"
_MAX_SEEN = 50
_UTC7 = timezone(timedelta(hours=7))
_TIMEOUT = aiohttp.ClientTimeout(total=30)


class FitHcmus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.name = "fit@hcmus"
        self.feed_url = "https://www.fit.hcmus.edu.vn/vn/feed.aspx"
        self.seen_links: set[str] = set()
        self.state_loaded = False
        self.check_feed.start()

    def cog_unload(self):  # type: ignore
        self.check_feed.cancel()

    async def _load_seen(self) -> None:
        """Load previously seen links from disk."""
        state = await load_state(_STATE_KEY)
        self.seen_links = set(state.get("seen_links", []))
        self.state_loaded = True

    async def _save_seen(self) -> None:
        """Persist seen links to disk (capped at _MAX_SEEN most recent)."""
        recent = list(self.seen_links)[-_MAX_SEEN:]
        await save_state(_STATE_KEY, {
            "seen_links": recent,
            "last_check": datetime.now(_UTC7).isoformat(),
        })

    async def _fetch_feed(self, retries: int = 2) -> feedparser.FeedParserDict:
        """Fetch and parse the RSS feed with retries and backoff."""
        last_error = None
        for attempt in range(retries + 1):
            try:
                async with create_session(_TIMEOUT) as session:
                    async with session.get(self.feed_url) as resp:
                        resp.raise_for_status()
                        body = await resp.read()
                        return feedparser.parse(body)
            except (aiohttp.ClientError, OSError) as e:
                last_error = e
                if attempt < retries:
                    await asyncio.sleep(2 * (attempt + 1))  # backoff: 2s, 4s
                    continue
        raise last_error if last_error else RuntimeError("Unknown feed fetch error")

    @tasks.loop(minutes=10)
    async def check_feed(self):
        try:
            # Load state on first run
            if not self.state_loaded:
                await self._load_seen()

            logger.info(f"Fetching {self.name}...")
            feed = await self._fetch_feed()
            channels = load_notification_channels("feeds")

            if not feed.entries:
                logger.warning(f"No posts found for {self.name}.")
                return

            latest = feed.entries[:10]

            # First time ever (no state file existed) — seed links, don't spam
            if not self.seen_links:
                self.seen_links = {entry.link for entry in latest if hasattr(entry, "link")}
                await self._save_seen()
                logger.info(f"{self.name}: seeded {len(self.seen_links)} links (first run).")
                return

            # Find new posts (entries whose link we haven't seen)
            new_posts = [
                entry for entry in latest
                if hasattr(entry, "link") and entry.link not in self.seen_links
            ]

            if new_posts and channels:
                logger.info(f"Found {len(new_posts)} new post(s) for {self.name}")
                for channel_id in channels:
                    channel = self.bot.get_channel(channel_id)
                    if not channel:
                        continue
                    for post in reversed(new_posts):
                        embed = discord.Embed(
                            title=f"📰 | {post.title}",
                            url=post.link,
                            color=discord.Colour.blue(),
                            timestamp=datetime(
                                *post.published_parsed[:6], tzinfo=_UTC7,
                            ) if hasattr(post, "published_parsed") and post.published_parsed
                            else datetime.now(_UTC7),
                        )
                        embed.set_footer(text=self.name)
                        await channel.send(embed=embed)
                        logger.info(f"NEW POST: {post.title}")

            # Update seen links
            for entry in latest:
                if hasattr(entry, "link"):
                    self.seen_links.add(entry.link)
            await self._save_seen()

        except Exception as e:
            logger.error(f"ERROR checking {self.name}: {e}")

    @check_feed.before_loop
    async def before_check_feed(self):
        await self.bot.wait_until_ready()

    @commands.hybrid_command(
        name="check-hcmus-fit",
        description="Danh sách các thông báo mới của fit@hcmus.",
    )
    async def check_fit_hcmus(self, ctx: commands.Context):
        await ctx.defer()
        try:
            feed = await self._fetch_feed()
        except Exception as error:
            logger.error(f"ERROR checking {self.name} manually: {error}")
            await ctx.send(
                "Could not reach FIT HCMUS feed right now (connection reset/timeout). "
                "Please try again in a moment."
            )
            return

        if not feed.entries:
            await ctx.send("No posts found.")
            return

        latest = feed.entries[:5]
        embed = discord.Embed(
            title="Latest FIT HCMUS posts",
            color=discord.Colour.blue(),
            timestamp=datetime.now(_UTC7),
        )
        lines = []
        for i, post in enumerate(latest, start=1):
            title = getattr(post, "title", "Untitled")
            link = getattr(post, "link", None)
            lines.append(f"{i}. [{title}]({link})" if link else f"{i}. {title}")

        embed.description = "\n".join(lines) or "No posts found."
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(FitHcmus(bot))