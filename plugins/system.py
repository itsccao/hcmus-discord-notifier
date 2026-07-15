import time
import discord
import os

from dotenv import load_dotenv
from discord.ext import commands
from datetime import datetime
from util.config import (
    add_allowed_server, remove_allowed_server, load_allowed_servers,
    add_notification_channel, remove_notification_channel, list_notification_groups,
)

load_dotenv()
BOT_NAME = os.getenv("BOT_NAME", "Delta")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))


class System(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- General commands ---

    @commands.hybrid_command(description="🏓")
    async def ping(self, ctx: commands.Context):
        gateway_ms = int(self.bot.latency * 1000)
        content = "Pong! :ping_pong:"

        if ctx.interaction:
            start = time.perf_counter()
            await ctx.send(content)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            full = f"{content}\nREST API latency: {elapsed_ms}ms \nGateway API latency: {gateway_ms}ms"
            await ctx.interaction.edit_original_response(content=full)
        else:
            start = time.perf_counter()
            msg = await ctx.send(content)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            full = f"{content}\nREST API latency: {elapsed_ms}ms \nGateway API latency: {gateway_ms}ms"
            await msg.edit(content=full)

    @commands.hybrid_command(description="Gửi feedback cho tôi.")
    async def feedback(self, ctx: commands.Context, *, msg: str):
        if not OWNER_ID:
            await ctx.send("Feedback is not configured.", ephemeral=True)
            return
        owner = await self.bot.fetch_user(OWNER_ID)
        guild_info = f"**{ctx.guild.name}** - `{ctx.guild.id}`" if ctx.guild else "Direct Message"
        text = (
            f"Feedback received at {datetime.now().strftime('**%H:%M:%S**, on **%A**, **%d/%m/%Y**.')}\n"
            f"User: **{ctx.author}** - `{ctx.author.id}`.\n"
            f"Server: {guild_info}.\n"
            f"Content:\n{msg}"
        )
        await owner.send(text)
        await ctx.send("Your feedback has been sent!", ephemeral=True)

    @commands.hybrid_command(description=f"Các thông tin về {BOT_NAME}.")
    async def about(self, ctx: commands.Context):
        embed = discord.Embed(
            description="Discord Bot để không bỏ lỡ các thông báo mới nhất của trường và khoa.",
            color=discord.Colour.green(),
        )
        embed.set_author(
            name=BOT_NAME,
            icon_url="https://cdn.discordapp.com/avatars/1006462067093540935/3ce43e8fe00fa4421a8cc56c5e2d628b.webp?size=1024",
        )
        embed.add_field(name="Danh sách các lệnh", value="`!help`", inline=False)
        embed.add_field(name="Discord", value="**`chrysovella`**", inline=False)
        embed.add_field(name="Website", value="[itsccao.github.io](https://itsccao.github.io)", inline=False)
        embed.add_field(name="Source Code", value="[itsccao/hcmus-discord-notifier](https://github.com/itsccao/hcmus-discord-notifier)", inline=False)
        embed.add_field(name="Làm sao để thêm bot vào server?", value="Nhắn tin cho tôi qua Discord.")
        await ctx.send(embed=embed)

    @commands.hybrid_command(description="Danh sách các câu lệnh.")
    async def help(self, ctx: commands.Context):
        embed = discord.Embed(description="**Prefix**: `!`", color=discord.Colour.green())
        embed.set_author(
            name=BOT_NAME,
            icon_url="https://cdn.discordapp.com/avatars/1006462067093540935/3ce43e8fe00fa4421a8cc56c5e2d628b.webp?size=1024",
        )

        embed.add_field(name="", value="", inline=False)
        embed.add_field(
            name="📢 Thông báo",
            value=(
                "`check-hcmus-root` — Thông báo mới của ĐH KHTN\n"
                "`check-hcmus-fit` — Thông báo mới của FIT HCMUS"
            ),
            inline=False,
        )

        embed.add_field(name="", value="", inline=False)
        embed.add_field(
            name="🛠️ Hệ thống",
            value=(
                "`help` — Danh sách các câu lệnh\n"
                "`about` — Thông tin về bot\n"
                "`ping` — Kiểm tra độ trễ\n"
                "`feedback` — Gửi feedback cho tác giả"
            ),
            inline=False,
        )

        embed.add_field(name="", value="", inline=False)
        embed.add_field(
            name="🔒 Admins Only",
            value=(
                "`guild-list` — Danh sách server đang hoạt động\n"
                "`guild-leave` — Buộc bot rời server\n"
                "`server-allow` — Thêm server vào danh sách cho phép\n"
                "`server-deny` — Xóa server khỏi danh sách cho phép\n"
                "`server-list` — Xem danh sách server được phép\n"
                "`channel-add` — Thêm channel vào nhóm thông báo\n"
                "`channel-remove` — Xóa channel khỏi nhóm thông báo\n"
                "`channel-list` — Xem tất cả channel thông báo"
            ),
            inline=False,
        )

        await ctx.send(embed=embed)

    # --- Guild management (owner only) ---

    @commands.hybrid_command(name="guild-list", description=f"Danh sách các server có {BOT_NAME}.")
    @commands.is_owner()
    async def guildlist(self, ctx: commands.Context):
        guilds = self.bot.guilds
        if not guilds:
            await ctx.send("Bot is not in any guilds.")
            return

        allowed = load_allowed_servers()
        embed = discord.Embed(
            title=f"Joined Server Count: {len(guilds)}",
            color=discord.Colour.green(),
        )
        # Discord embeds have a hard limit of 25 fields
        display_guilds = guilds[:25]
        for guild in display_guilds:
            status = "✅" if not allowed or guild.id in allowed else "❌"
            embed.add_field(
                name=f"{status} {guild.name}",
                value=f"ID: `{guild.id}`\nMembers: {guild.member_count}",
                inline=True,
            )
        if len(guilds) > 25:
            embed.set_footer(text=f"Showing 25 of {len(guilds)} servers.")
        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(name="guild-leave", description=f"Buộc {BOT_NAME} rời server.")
    @commands.is_owner()
    async def guildleave(self, ctx: commands.Context, guild_id: int):
        guild = self.bot.get_guild(guild_id)
        if not guild:
            await ctx.send(f"Guild with ID `{guild_id}` not found.", ephemeral=True)
            return

        name = guild.name
        try:
            await guild.leave()
            await ctx.send(f"Successfully left guild: **{name}** - `{guild_id}`", ephemeral=True)
        except Exception as e:
            await ctx.send(f"Failed to leave guild: {e}", ephemeral=True)

    # --- Server allow-list (owner only) ---

    @commands.hybrid_command(
        name="server-allow",
        description="Thêm server vào danh sách cho phép.",
    )
    @commands.is_owner()
    async def server_allow(self, ctx: commands.Context, guild_id: int = 0):
        """Add a server to the allow-list. Defaults to current server if no ID given."""
        target_id = guild_id or (ctx.guild.id if ctx.guild else 0)
        if not target_id:
            await ctx.send("❌ Please provide a guild ID or run this in a server.", ephemeral=True)
            return

        guild = self.bot.get_guild(target_id)
        name = guild.name if guild else f"Unknown ({target_id})"

        if add_allowed_server(target_id):
            await ctx.send(f"✅ Server **{name}** (`{target_id}`) has been allowed.", ephemeral=True)
        else:
            await ctx.send(f"ℹ️ Server **{name}** (`{target_id}`) is already allowed.", ephemeral=True)

    @commands.hybrid_command(
        name="server-deny",
        description="Xóa server khỏi danh sách cho phép.",
    )
    @commands.is_owner()
    async def server_deny(self, ctx: commands.Context, guild_id: int = 0):
        """Remove a server from the allow-list. Defaults to current server if no ID given."""
        target_id = guild_id or (ctx.guild.id if ctx.guild else 0)
        if not target_id:
            await ctx.send("❌ Please provide a guild ID or run this in a server.", ephemeral=True)
            return

        guild = self.bot.get_guild(target_id)
        name = guild.name if guild else f"Unknown ({target_id})"

        if remove_allowed_server(target_id):
            await ctx.send(f"✅ Server **{name}** (`{target_id}`) has been removed.", ephemeral=True)
        else:
            await ctx.send(f"ℹ️ Server **{name}** (`{target_id}`) was not in the allow-list.", ephemeral=True)

    @commands.hybrid_command(
        name="server-list",
        description="Danh sách server được cho phép.",
    )
    @commands.is_owner()
    async def server_list(self, ctx: commands.Context):
        """Show all allowed servers."""
        servers = load_allowed_servers()
        if not servers:
            await ctx.send("ℹ️ Allow-list is empty — bot works in **all** servers.", ephemeral=True)
            return

        lines = []
        for gid in servers:
            guild = self.bot.get_guild(gid)
            name = guild.name if guild else "Unknown"
            lines.append(f"• **{name}** — `{gid}`")

        embed = discord.Embed(
            title=f"Allowed Servers ({len(servers)})",
            description="\n".join(lines),
            color=discord.Colour.green(),
        )
        await ctx.send(embed=embed, ephemeral=True)

    # --- Notification channel management (owner only) ---

    @commands.hybrid_command(
        name="channel-add",
        description="Thêm channel vào nhóm thông báo.",
    )
    @commands.is_owner()
    async def channel_add(self, ctx: commands.Context, group: str, channel: discord.TextChannel = None):  # type: ignore
        """Add a channel to a notification group. Defaults to current channel."""
        target = channel or ctx.channel
        if not target:
            await ctx.send("❌ Could not determine target channel.", ephemeral=True)
            return
        if add_notification_channel(group, target.id):
            await ctx.send(
                f"✅ {target.mention} has been added to notification group `{group}`.",
                ephemeral=True,
            )
        else:
            await ctx.send(
                f"ℹ️ {target.mention} is already in group `{group}`.",
                ephemeral=True,
            )

    @commands.hybrid_command(
        name="channel-remove",
        description="Xóa channel khỏi nhóm thông báo.",
    )
    @commands.is_owner()
    async def channel_remove(self, ctx: commands.Context, group: str, channel: discord.TextChannel = None):  # type: ignore
        """Remove a channel from a notification group. Defaults to current channel."""
        target = channel or ctx.channel
        if not target:
            await ctx.send("❌ Could not determine target channel.", ephemeral=True)
            return
        if remove_notification_channel(group, target.id):
            await ctx.send(
                f"✅ {target.mention} has been removed from group `{group}`.",
                ephemeral=True,
            )
        else:
            await ctx.send(
                f"ℹ️ {target.mention} was not in group `{group}`.",
                ephemeral=True,
            )

    @commands.hybrid_command(
        name="channel-list",
        description="Danh sách channel trong các nhóm thông báo.",
    )
    @commands.is_owner()
    async def channel_list(self, ctx: commands.Context):
        """Show all notification channels grouped by type."""
        groups = list_notification_groups()
        if not groups:
            await ctx.send("ℹ️ No notification channels configured.", ephemeral=True)
            return

        embed = discord.Embed(
            title="Notification Channels",
            color=discord.Colour.green(),
        )
        for group_name, channel_ids in groups.items():
            mentions = []
            for cid in channel_ids:
                ch = self.bot.get_channel(cid)
                mentions.append(ch.mention if ch else f"`{cid}`")
            embed.add_field(
                name=f"📢 {group_name}",
                value="\n".join(mentions) or "None",
                inline=False,
            )
        await ctx.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(System(bot))