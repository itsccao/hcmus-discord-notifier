import discord
import logging
import os
import sys

from dotenv import load_dotenv
from discord.ext import commands
from pathlib import Path
from util.color import Color
from util.config import is_server_allowed
from util.http import create_connector
from util.errors import bot_error_handler

# Strip ANSI color codes when stdout is not a TTY (e.g. redirected to a file
# in container environments), otherwise the escape sequences appear as garbage.
if sys.stdout.isatty():
    _log_fmt = (
        f"{Color.DATETIME}{{asctime}} {Color.RESET}{Color.BOLD}| "
        f"{Color.LEVELNAME}{{levelname}} {Color.RESET}{Color.BOLD}| "
        f"{Color.NAME}{{name}}: {Color.MESSAGE}{{message}}"
    )
else:
    _log_fmt = "{asctime} | {levelname} | {name}: {message}"

logging.basicConfig(
    format=_log_fmt,
    style="{",
    datefmt="%d-%m-%Y | %H:%M:%S",
    level=logging.INFO,
)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_NAME = os.getenv("BOT_NAME", "Delta")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing in .env")


class DeltaBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents, help_command=None)

    async def setup_hook(self) -> None:
        # Register the app command error handler before loading plugins
        self.tree.on_error = bot_error_handler
        await self._load_plugins()
        await self._sync_commands()

    async def _load_plugins(self) -> None:
        plugins_dir = Path("plugins")
        if not plugins_dir.is_dir():
            logging.warning("Plugins directory not found")
            return

        for file in sorted(plugins_dir.glob("*.py")):
            if file.name.startswith("__"):
                continue
            ext = f"plugins.{file.stem}"
            try:
                await self.load_extension(ext)
                logging.info(f"Loaded {Color.LEVELNAME}{ext.upper()}")
            except Exception as e:
                logging.error(
                    f"Failed to load {Color.LEVELNAME}{ext.upper()}"
                    f"{Color.RESET}: {Color.ERROR}{e}"
                )

    async def _sync_commands(self) -> None:
        try:
            synced = await self.tree.sync()
            logging.info(f"Synced {len(synced)} application (slash) command(s)")
        except Exception as e:
            logging.error(f"Failed to sync commands: {e}")

    async def login(self, token: str) -> None:
        self.http.connector = create_connector()
        await super().login(token)

    async def on_ready(self):
        logging.info(f"Logged in as {self.user}")
        await self._enforce_bot_name()

    async def _enforce_bot_name(self):
        for guild in self.guilds:
            try:
                if guild.me.nick != BOT_NAME:
                    await guild.me.edit(nick=BOT_NAME)
                    logging.info(f"Updated nickname in {guild.name} -> {BOT_NAME}")
            except discord.Forbidden:
                logging.warning(f"Missing permission to change nickname in {guild.name}")
            except Exception as e:
                logging.error(f"Failed to update nickname in {guild.name}: {e}")

    async def on_message(self, message: discord.Message):
        if message.author == self.user:
            return

        # Block messages from non-allowed servers (DMs always pass)
        if message.guild and not is_server_allowed(message.guild.id):
            return

        # Log every message
        if isinstance(message.channel, discord.DMChannel):
            logging.log(100, f"DM - {message.author}: {message.content}")
        else:
            logging.log(
                100,
                f"{Color.GUILD}{message.guild} {Color.RESET}> "
                f"{Color.CHANNEL}{message.channel} {Color.RESET}> "
                f"{Color.AUTHOR}{message.author}{Color.RESET}: "
                f"{Color.MESSAGE}{message.content}",
            )

        if message.content.startswith(f"hello {BOT_NAME}"):
            await message.channel.send(
                f"Hello from the other side of the screen, {message.author}!"
            )

        # Only allow Owner to use commands through Direct Message
        if not isinstance(message.channel, discord.DMChannel) or message.author.id == OWNER_ID:
            await self.process_commands(message)

    async def on_command_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.CommandNotFound):
            return
        logging.error(
            f"{Color.COMMAND}ERROR {Color.RESET}at "
            f'{Color.ERROR}"{ctx.command}"{Color.RESET}: '
            f"{Color.MESSAGE}{error}"
        )


if __name__ == "__main__":
    DeltaBot().run(BOT_TOKEN)