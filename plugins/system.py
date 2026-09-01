import gc
import re
import time
import asyncio
import discord
import os

from dotenv import load_dotenv
from discord.ext import commands
from datetime import datetime
from util.config import (
    add_allowed_server,
    remove_allowed_server,
    load_allowed_servers,
    set_server_config,
    get_server_config,
)

load_dotenv()
BOT_NAME = os.getenv("BOT_NAME", "Delta")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))


class System(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- General commands ---

    @commands.hybrid_command(description="📊 RAM usage của bot.")
    @commands.is_owner()
    async def memstats(self, ctx: commands.Context):
        """Show RSS vs Python heap, and force a GC cycle."""
        collected = gc.collect()

        try:
            import psutil
            proc = psutil.Process()
            rss_mb = proc.memory_info().rss / 1024 / 1024
            rss_line = f"{rss_mb:.1f} MB"
        except ImportError:
            rss_line = "*(psutil not installed)*"

        import tracemalloc
        if not tracemalloc.is_tracing():
            heap_line = "*(start bot with PYTHONTRACEMALLOC=1 to enable heap tracking)*"
        else:
            current, peak = tracemalloc.get_traced_memory()
            heap_line = f"current: {current/1024/1024:.1f} MB | peak: {peak/1024/1024:.1f} MB"

        embed = discord.Embed(title="📊 Memory Stats", color=discord.Colour.blurple())
        embed.add_field(name="RSS (OS view)", value=rss_line, inline=False)
        embed.add_field(name="Python heap (tracemalloc)", value=heap_line, inline=False)
        embed.add_field(name="GC objects collected", value=str(collected), inline=False)
        embed.add_field(
            name="discord.py caches",
            value=(
                f"Guilds: {len(self.bot.guilds)}\n"
                f"Cached messages: {len(self.bot._connection._messages or [])}\n"
                f"Cached members: {sum(len(g.members) for g in self.bot.guilds)}"
            ),
            inline=False,
        )
        embed.set_footer(text="RSS includes Python allocator headroom — may be higher than actual heap.")
        await ctx.send(embed=embed, ephemeral=True)

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
                "`check-rss` — Xem bài đăng mới nhất từ các RSS feed"
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
                "`server-list` — Danh sách server đang hoạt động\n"
                "`server-leave` — Buộc bot rời server\n"
                "`server-allow` — Thêm server vào danh sách cho phép\n"
                "`server-deny` — Xóa server khỏi danh sách cho phép\n"
                "`start` — Thiết lập kênh thông báo và role ping"
            ),
            inline=False,
        )

        await ctx.send(embed=embed)

    # --- Server management (owner only) ---

    @commands.hybrid_command(name="server-list", description=f"Danh sách các server có {BOT_NAME}.")
    @commands.is_owner()
    async def server_list(self, ctx: commands.Context):
        guilds = self.bot.guilds
        if not guilds:
            await ctx.send("Bot is not in any guilds.", ephemeral=True)
            return

        allowed = load_allowed_servers()
        embed = discord.Embed(
            title=f"Joined Server Count: {len(guilds)}",
            color=discord.Colour.green(),
        )
        display_guilds = guilds[:25]
        for guild in display_guilds:
            status = "✅" if guild.id in allowed else "❌"
            cfg = get_server_config(guild.id)
            channel_str = f"<#{cfg['channel_id']}>" if cfg and cfg.get("channel_id") else "Chưa setup"
            role_str = f"<@&{cfg['role_id']}>" if cfg and cfg.get("role_id") else "None"
            embed.add_field(
                name=f"{status} {guild.name}",
                value=f"ID: `{guild.id}`\nMembers: {guild.member_count}\nChannel: {channel_str}\nRole: {role_str}",
                inline=True,
            )
        if len(guilds) > 25:
            embed.set_footer(text=f"Showing 25 of {len(guilds)} servers.")
        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(name="server-leave", description=f"Buộc {BOT_NAME} rời server.")
    @commands.is_owner()
    async def server_leave(self, ctx: commands.Context, guild_id: int):
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

    # --- Setup Notification Command (owner only) ---

    @commands.hybrid_command(
        name="start",
        description="Thiết lập kênh gửi thông báo và role ping cho server này.",
    )
    @commands.is_owner()
    async def start_setup(self, ctx: commands.Context):
        """Interactive setup for notification channel and ping role."""
        if not ctx.guild:
            await ctx.send("❌ Lệnh này chỉ có thể chạy bên trong một server (guild).", ephemeral=True)
            return

        target_channel = ctx.channel
        if not isinstance(target_channel, discord.TextChannel):
            await ctx.send("❌ Kênh này không phải là TextChannel hợp lệ.", ephemeral=True)
            return

        # Check permissions in the target channel
        bot_member = ctx.guild.me or await ctx.guild.fetch_member(self.bot.user.id)
        perms = target_channel.permissions_for(bot_member)
        if not (perms.send_messages and perms.embed_links):
            await ctx.send(
                f"❌ Bot không có đủ quyền (`Send Messages`, `Embed Links`) trong kênh {target_channel.mention}. Vui lòng cấp quyền và thử lại.",
                ephemeral=True,
            )
            return

        prompt_text = (
            f"🔔 **Thiết lập thông báo cho server {ctx.guild.name}**\n"
            f"• Kênh nhận thông báo: {target_channel.mention} (`{target_channel.id}`)\n\n"
            f"👉 **Vui lòng reply (trả lời) tin nhắn này** với **Role ID** (hoặc mention `@Role`) để ping khi có thông báo mới.\n"
            f"*(Nếu không muốn ping role nào, hãy reply `none` hoặc `skip`)*\n"
            f"⏱️ *Thời gian chờ phản hồi: 60 giây.*"
        )

        if ctx.interaction:
            await ctx.interaction.response.send_message(prompt_text)
            prompt_msg = await ctx.interaction.original_response()
        else:
            prompt_msg = await ctx.send(prompt_text)

        prompt_msg_id = prompt_msg.id

        def check_reply(m: discord.Message) -> bool:
            if m.author.id != ctx.author.id or m.channel.id != target_channel.id:
                return False
            if m.reference and m.reference.message_id == prompt_msg_id:
                return True
            return False

        try:
            reply_msg = await self.bot.wait_for("message", check=check_reply, timeout=60.0)
        except asyncio.TimeoutError:
            await ctx.send("⌛ Đã hết thời gian chờ phản hồi. Quá trình thiết lập bị hủy (cấu hình cũ được giữ nguyên).")
            return

        reply_text = reply_msg.content.strip()
        selected_role_id = None
        role_display = "Không ping role"

        if reply_text.lower() not in ["none", "skip", "k", "khong", "không", "0", "no", "n"]:
            match = re.search(r"\d+", reply_text)
            if not match:
                await reply_msg.reply("❌ Không tìm thấy Role ID hợp lệ. Quá trình thiết lập bị hủy.")
                return

            role_id = int(match.group(0))
            role = ctx.guild.get_role(role_id)
            if not role:
                await reply_msg.reply(f"❌ Không tìm thấy Role với ID `{role_id}` trong server này. Quá trình thiết lập bị hủy.")
                return

            selected_role_id = role.id
            role_display = f"{role.mention} (`{role.id}`)"

        # Save configuration
        set_server_config(ctx.guild.id, target_channel.id, selected_role_id)

        embed = discord.Embed(
            title="✅ Thiết lập thông báo thành công!",
            description=(
                f"• **Server**: **{ctx.guild.name}** (`{ctx.guild.id}`)\n"
                f"• **Kênh thông báo**: {target_channel.mention} (`{target_channel.id}`)\n"
                f"• **Role ping**: {role_display}"
            ),
            color=discord.Colour.green(),
            timestamp=datetime.now(),
        )
        await reply_msg.reply(embed=embed)


async def setup(bot):
    await bot.add_cog(System(bot))