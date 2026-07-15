import asyncio
import logging
import discord
import os

from dotenv import load_dotenv
from discord.ext import commands
from util.color import Color

load_dotenv()
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

root_logger = logging.getLogger()
logger = logging.getLogger(__name__)


class Logging(commands.Cog, logging.Handler):
    def __init__(self, bot, owner_id):
        logging.Handler.__init__(self)
        self.bot = bot
        self.owner_id = owner_id
        self.queue = asyncio.Queue()
        self._task: asyncio.Task | None = None

    def emit(self, record: logging.LogRecord) -> None:
        """Forward log records to the bot owner via Discord DM."""
        try:
            msg = self.format(record)
        except Exception:
            self.handleError(record)
            return

        try:
            loop = self.bot.loop
            if loop.is_running():
                loop.call_soon_threadsafe(self.queue.put_nowait, msg)
        except Exception:
            self.handleError(record)

    async def _dispatch_loop(self) -> None:
        """Consume the queue and DM each message to the owner."""
        await self.bot.wait_until_ready()
        while True:
            msg = await self.queue.get()
            try:
                # Fetch owner each iteration so a transient failure doesn't
                # kill the entire task permanently.
                owner = await self.bot.fetch_user(self.owner_id)
                # Discord messages have a 2000-char limit; truncate if needed
                await owner.send(f"```ansi\n{msg[:1990]}\n```")
            except (discord.NotFound, discord.Forbidden, discord.HTTPException) as e:
                # Use print() to avoid feeding a new record back into this
                # same handler, which would cause a recursive logging loop.
                print(f"[Logging] Failed to DM log record to owner: {e}", flush=True)
            finally:
                self.queue.task_done()

    async def cog_unload(self) -> None:
        """Clean up: cancel the dispatch task and remove the handler."""
        if self._task and not self._task.done():
            self._task.cancel()
        root_logger.removeHandler(self)

    @commands.Cog.listener()
    async def on_ready(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"Successfully Logged As {self.bot.user}")
        # Start the background task that forwards queued log records to the owner
        if self._task is None or self._task.done():
            self._task = asyncio.ensure_future(self._dispatch_loop())

    @commands.Cog.listener()
    async def on_command(self, ctx):
        if isinstance(ctx.channel, discord.DMChannel):
            logging.info(
                f"{Color.COMMAND}COMMAND USED {Color.RESET}- DM - "
                f"{ctx.author}: {ctx.command}"
            )
        else:
            logging.info(
                f"{Color.COMMAND}COMMAND USED {Color.RESET}- "
                f"{Color.GUILD}{ctx.guild}{Color.RESET} > "
                f"{Color.CHANNEL}{ctx.channel}{Color.RESET} > "
                f"{Color.AUTHOR}{ctx.author}{Color.RESET}: "
                f"{Color.MESSAGE}{ctx.command}"
            )

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, commands.CommandOnCooldown):
            try:
                await ctx.send(
                    f"You're on cooldown! Try again in **{round(error.retry_after, 2)}** second(s).",
                    ephemeral=True,
                )
            except discord.HTTPException as e:
                logger.error(f"Failed to send cooldown message: {e}")
            return

        if isinstance(error, commands.MissingRequiredArgument):
            try:
                await ctx.send("❌ Missing argument.", ephemeral=True)
            except discord.HTTPException as e:
                logger.error(f"Failed to send missing argument message: {e}")
            return

        logger.exception(f"Command error in {ctx.command}: {error}")

        embed = discord.Embed(
            title="⚠️ An Error Occurred",
            description=f"```{error}```",
            color=discord.Colour.red(),
        )

        try:
            if ctx.interaction and ctx.interaction.response.is_done():
                await ctx.interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await ctx.send(embed=embed)
        except discord.HTTPException as e:
            logger.error(f"Failed to send error embed to Discord: {e}")


async def setup(bot):
    if not OWNER_ID:
        logger.warning("Skipping logging cog — OWNER_ID not provided.")
        return

    logging_cog = Logging(bot, OWNER_ID)
    logging_cog.setLevel(logging.WARNING)
    logging_cog.setFormatter(logging.Formatter(
        fmt=(
            f"{Color.DATETIME}{{asctime}} {Color.RESET}{Color.BOLD}| "
            f"{Color.LEVELNAME}{{levelname}} {Color.RESET}{Color.BOLD}| "
            f"{Color.NAME}{{name}}: {Color.MESSAGE}{{message}}"
        ),
        style="{",
        datefmt="%d-%m-%Y | %H:%M:%S",
    ))
    root_logger.addHandler(logging_cog)
    await bot.add_cog(logging_cog)


async def teardown(bot):
    """Remove the handler when the extension is unloaded."""
    root_logger.removeHandler(next(
        (h for h in root_logger.handlers if isinstance(h, Logging)), None
    ))