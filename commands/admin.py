# commands/admin.py

from discord.ext import commands
from discord import TextChannel
from typing import Optional

# Assuming this path is correct for your helper script
from helper_scripts.asset_access import send_embed_all_emojis

class AdminCommands(commands.Cog):
    """Commands accessible only to bot administrators or for managing scheduled posts."""
    
    def __init__(self, bot, admins, channels_to_post, scheduled_channels, save_channels_func):
        self.bot = bot
        self.admins = admins
        self.channels_to_post = channels_to_post
        self.scheduled_channels = scheduled_channels
        self.save_channels = save_channels_func

    # --- Commands are now Cog methods using self.attributes ---

    # MARK: !ping
    @commands.command(name="ping", aliases=["p"])
    async def ping_command(self, ctx: commands.Context):
        """Responds with bot latency."""
        latency_ms = round(self.bot.latency * 1000)
        await ctx.send(f"🏓 Pong! {latency_ms}ms")

    # The old @commands.command(name="stopbot", aliases=["stop"]) is removed,
    # as the 'stop' functionality is now correctly implemented under !bot stop.

    # MARK: !schedule
    @commands.command(name="schedule", aliases=["s"])
    async def schedule_command(self, ctx: commands.Context, action: str = ""):
        """Start, stop oder list scheduled leaderboard posts (Uses class attributes)."""
        valid_actions = ["start", "stop", "list"]

        # Wenn keine Aktion angegeben oder ungültig
        if not action or action.lower() not in valid_actions:
            await ctx.send(
                f"## Nutzung von `{ctx.prefix}schedule`"
                f"\n-# (aliases: {ctx.prefix}s)"
                "\n"
                "\n- `start` → Scheduler für diesen Channel aktivieren"
                "\n- `stop ` → Scheduler für diesen Channel deaktivieren"
                "\n- `list ` → Zeigt alle registrierten Channels (Admins only)"
                "\n-# ℹ️ Syntax: `<param>` = erforderlicher parameter, `[param]` = optionaler parameter"
            )
            return

        action = action.lower()
        channel_id = ctx.channel.id
        channel = ctx.channel
        guild = ctx.guild

        if guild is None or not isinstance(channel, TextChannel):
            await ctx.send(
                "❌ Dieser Befehl kann nur in Server-Textkanälen verwendet werden."
            )
            return

        # START
        if action == "start":
            if channel_id in self.channels_to_post:
                await ctx.send("ℹ️ Dieser Channel bekommt das Leaderboard bereits.")
            else:
                self.channels_to_post.add(channel_id)
                self.scheduled_channels[str(channel_id)] = f"{guild.name}#{channel.name}"
                self.save_channels()
                await ctx.send(
                    "✅ Dieser Channel wird jetzt täglich um 03:00 CET das Leaderboard erhalten."
                )

        # STOP
        elif action == "stop":
            if channel_id in self.channels_to_post:
                self.channels_to_post.remove(channel_id)
                self.scheduled_channels.pop(str(channel_id), None)
                self.save_channels()
                await ctx.send(
                    "✅ Dieser Channel erhält das Leaderboard ab jetzt nicht mehr."
                )
            else:
                await ctx.send(
                    "ℹ️ Dieser Channel war nicht für das Leaderboard registriert."
                )

        # LIST (Admins only)
        elif action == "list":
            if ctx.author.id not in self.admins:
                await ctx.send(
                    "🚫 Du hast keine Admin-Rechte, um diese Liste anzusehen."
                )
                return

            if not self.scheduled_channels:
                await ctx.send("📭 Es sind aktuell keine Channels registriert.")
            else:
                lines = []
                for ch_id, full_name in self.scheduled_channels.items():
                    if "#" in full_name:
                        server, channel_name = full_name.split("#", 1)
                    else:
                        server, channel_name = full_name, "Unbekannt"
                    lines.append(
                        f"**Server:** `{server.strip()}` -> **Channel:** `#{channel_name.strip()}`"
                    )
                msg = "\n".join(lines)
                await ctx.send(f"📋 **Aktuell registrierte Channels:**\n\n{msg}")

        else:
            await ctx.send(
                "❌ Ungültiger Parameter. Nutze `start`, `stop` oder `list`."
            )

    # MARK: !bot
    @commands.command(name="bot")
    async def manage_bot_command(self, ctx: commands.Context, subcommand: Optional[str] = None): # FIX 1: Added self
        """
        Verwalte Bot-spezifische Aktionen: emojitest, stop
        """
        if subcommand is None:
            # Hilfe ausgeben, wenn kein Unterbefehl angegeben
            await ctx.send(
                f"## Nutzung von `{ctx.prefix}bot`"
                "\n- `emojitest` → sendet alle Emojis zum Testen"
                "\n- `stop`      → fährt den Bot herunter (Admins only)"
                "\n-# ℹ️ Syntax: `<param>` = erforderlicher Parameter, `[param]` = optionaler Parameter"
            )
            return

        subcommand = subcommand.lower()

        if subcommand == "emojitest":
            # Note: send_embed_all_emojis is likely an async function
            await send_embed_all_emojis(ctx)

        elif subcommand == "stop":
            if ctx.author.id not in self.admins: # FIX 2: Used self.admins instead of unbound ADMINS
                await ctx.send(
                    "🚫 Du hast keine Berechtigung, diesen Befehl zu nutzen."
                )
                return

            print(
                f"[BOT STOP] {ctx.author} ({ctx.author.id}) hat den Bot heruntergefahren."
            )
            await ctx.send("⏹️ Bot wird heruntergefahren...")
            await self.bot.close() # FIX 3: Used self.bot instead of unbound bot

        else:
            # Fallback-Hilfe für unbekannte Unterbefehle
            await ctx.send(
                f"Unbekannter Unterbefehl `{subcommand}`.\n"
                f"Verfügbare Unterbefehle: `emojitest`, `stop`"
            )

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))