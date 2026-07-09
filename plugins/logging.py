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

    @commands.Cog.listener()
    async def on_ready(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"Successfully Logged As {self.bot.user}")

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
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"You're on cooldown! Try again in **{round(error.retry_after, 2)}** second(s).",
                ephemeral=True,
            )
            return

        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Missing argument.")
            return

        logger.exception(f"Command error: {error}")
        embed = discord.Embed(
            description="",
            color=discord.Colour.red(),
        )
        await ctx.send(embed=embed)

    def emit(self, record):
        self.queue.put_nowait(record)

    def close(self):
        pass


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