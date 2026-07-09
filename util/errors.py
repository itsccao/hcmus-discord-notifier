import discord
import logging
import asyncio

from discord.ext import commands

logger = logging.getLogger(__name__)


async def bot_error_handler(interaction, exception):
    if getattr(exception, "handled", False):
        return

    if isinstance(exception, commands.NotOwner):
        embed = discord.Embed(description="Owner Only!", color=discord.Colour.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await asyncio.sleep(5)
        await interaction.delete_original_response()
    else:
        logger.exception(
            "Ignoring exception in command %s: ", interaction.command,
            exc_info=(type(exception), exception, exception.__traceback__),
        )