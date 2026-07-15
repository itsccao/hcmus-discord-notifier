import logging
import discord

from discord.ext import commands
from util.color import Color

logger = logging.getLogger(__name__)


class Logging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
    await bot.add_cog(Logging(bot))