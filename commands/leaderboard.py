# commands/leaderboard.py

from discord.ext import commands
from typing import Optional
from helper_scripts.data_functions import get_tracked_bots
from helper_scripts.helper_functions import send_leaderboard

class LeaderboardCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        @bot.command(name="leaderboard", aliases=["lb", "top"])
        async def leaderboard_command(
            ctx: commands.Context, top_x: Optional[str] = None, mode: Optional[str] = None
        ):
            """Zeigt Leaderboard, optional Top x: "!leaderboard x (alias: lb, top)" """

            if top_x and top_x.lower() == "help":
                await ctx.send(
                    f"## Nutzung von `{ctx.prefix}leaderboard`"
                    f"\n-# (aliases: {ctx.prefix}lb, {ctx.prefix}top)"
                    "\n"
                    "\n`!top [top_x] [force_text] [no_tracked]`"
                    "\n- `[top_x]       ` → zeige nur die top [top_x] Einträge des Leaderboards"
                    '\n- `["text"]      ` → erzwingt Textformat statt Bilder'
                    '\n- `["no_tracked"]` → sendet keine tracked Bots'
                    "\n-# ℹ️ Syntax: `<param>` = erforderlicher parameter, `[param]` = optionaler parameter"
                )
                return

            # Determine guild ID (or use author ID for DM)
            guild_id = ctx.guild.id if ctx.guild else ctx.author.id

            # top filter
            top_x_int = 0  # default 0 (all)
            if top_x:
                try:
                    top_x_int = int(top_x)
                    if top_x_int < 0:
                        top_x_int = 0
                except ValueError:
                    # ignore if top_x is "text" or other mode
                    if top_x.lower() != "text":
                        await ctx.send("❌ Ungültige Zahl. Bitte gib eine ganze Zahl ein.")
                        return

            # Decide if we force text mode
            force_text = mode and mode.lower() == "text"
            if top_x and top_x.lower() == "text":
                force_text = True
                top_x_int = None

            # Get tracked bots for this guild/DM
            tracked_bots = get_tracked_bots(guild_id=guild_id)

            # Call the updated send_leaderboard
            await send_leaderboard(
                channel=ctx.channel,
                tracked_bots=tracked_bots,
                top_x=top_x_int,
                force_text=force_text,
                as_thread=True,
            )

async def setup(bot):
    await bot.add_cog(LeaderboardCommand(bot))