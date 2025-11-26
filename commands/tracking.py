from discord.ext import commands
from typing import Optional, List, Dict # <-- ADDED List and Dict
from helper_scripts.data_functions import get_tracked_bots, set_tracked_bots
from helper_scripts.helper_functions import get_leaderboard_json
from discord import Embed # <-- ADDED Embed

class TrackingCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # MARK: !track
    @commands.command(name="track", aliases=["t"])
    async def track_command(
        self, # <-- ADDED SELF
        ctx: commands.Context,
        action: Optional[str] = None,
        *,
        arg: Optional[str] = None,
    ):
        """Manage tracked bots: list/add/remove"""
        guild_id = ctx.guild.id if ctx.guild else ctx.author.id
        tracked_bots: List[Dict] = get_tracked_bots(guild_id=guild_id)

        # Determine if this is a DM or a server
        location_type = (
            f"DM: {ctx.author.name}"
            if ctx.guild is None
            else f"Server: {ctx.guild.name}"
        )
        embed_color = 0xB1CCDB

        # MARK: > list
        if action == "list":
            if not tracked_bots:
                embed = Embed( # <-- Embed is now imported
                    title=f"Tracked Bots in {location_type}",
                    description="📭 Keine Bots werden aktuell getrackt.",
                    color=embed_color,
                )
                await ctx.send(embed=embed)
                return

            embed = Embed(title=f"Tracked Bots in {location_type}", color=embed_color) # <-- Embed is now imported

            for idx, info in enumerate(tracked_bots, start=1):
                embed.add_field(
                    name=f"{idx}. {info['emoji']} {info['name']}",
                    value=f"Autor: {info['author']}",
                    inline=False,
                )

            await ctx.send(embed=embed)
            return

        # MARK: > add
        elif action == "add":
            if not arg:
                await ctx.send(
                    "Bitte gib den Namen des Bots an, z.B. `!track add ZitronenBot` oder mehrere durch Kommas getrennt."
                )
                return

            # Check if get_leaderboard_json is async and needs await
            # Assuming it is, as per helper_functions snippet (not fully shown, but common discord.py pattern)
            leaderboard_json, _ = get_leaderboard_json() 
            if "error" in leaderboard_json[0]:
                await ctx.send(leaderboard_json[0]["error"])
                return

            bot_names = [name.strip() for name in arg.split(",") if name.strip()]
            added_bots = []
            already_tracked = []
            not_found_bots = []
            limit_reached_bots = []
            multi_index_needed = {}
            MAX_TRACKED_BOTS = 25
            not_found_counter = 1

            for bot_name in bot_names:
                if len(tracked_bots) >= MAX_TRACKED_BOTS:
                    limit_reached_bots.append(
                        f"{not_found_counter}. ❌ {bot_name} (Limit erreicht)"
                    )
                    not_found_counter += 1
                    continue

                # Prüfen, ob Index angegeben wurde
                parts = bot_name.rsplit(" ", 1)
                base_name, index = (
                    (parts[0], int(parts[1]) - 1)
                    if len(parts) == 2 and parts[1].isdigit()
                    else (bot_name, None)
                )

                # Matching: zuerst exakt, dann contains
                matching_bots = [
                    b
                    for b in leaderboard_json
                    if b.get("Bot", "").lower() == base_name.lower()
                ]

                if not matching_bots:
                    # dann direkt not_found
                    not_found_bots.append(f"{not_found_counter}. ❓ {bot_name}")
                    not_found_counter += 1
                    continue

                # wenn mehrere, dann in multi_index_needed speichern
                if len(matching_bots) > 1 and index is None:
                    multi_index_needed[bot_name] = matching_bots
                    continue

                # Index anwenden, aber nur innerhalb dieser Liste
                index = 0 if index is None else min(index, len(matching_bots) - 1)
                bot_info = matching_bots[index]

                bot_dict = {
                    "name": bot_info.get("Bot"),
                    "emoji": bot_info.get("Col1", ""),
                    "author": bot_info.get("Autor / Team", ""),
                }

                if bot_dict in tracked_bots:
                    already_tracked.append(bot_dict)
                    continue

                tracked_bots.append(bot_dict)
                added_bots.append(bot_dict)

            set_tracked_bots(guild_id=guild_id, tracked=tracked_bots)

            embed = Embed(title="Bots zum Tracken Hinzufügen", color=0x00FF00) # <-- Embed is now imported

            # Field 1: Successfully added bots
            if added_bots:
                lines = [
                    f"{i+1}. {b['emoji']} {b['name']} (Autor: {b['author']})"
                    for i, b in enumerate(added_bots)
                ]
                embed.add_field(
                    name="✅ **__Zugefügte Bots__**",
                    value="\n".join(lines),
                    inline=False,
                )

            # Field 2: Bots needing index selection
            for bot_name, matches in multi_index_needed.items():
                lines = [
                    f"{i+1}. {b.get('Col1','')} {b.get('Bot','')} ({b.get('Autor / Team','')})"
                    for i, b in enumerate(matches)
                ]
                embed.add_field(
                    name=f"⚠️ **__Mehrere Bots gefunden für `{bot_name}`, bitte Index angeben__**",
                    value="\n".join(lines),
                    inline=False,
                )

            # Field 3: Already tracked bots
            if already_tracked:
                lines = [
                    f"{i+1}. {b['emoji']} {b['name']} (Autor: {b['author']})"
                    for i, b in enumerate(already_tracked)
                ]
                embed.add_field(
                    name="⚠️ **__Bereits getrackte Bots__**",
                    value="\n".join(lines),
                    inline=False,
                )

            # Field 4: Not found
            if not_found_bots:
                embed.add_field(
                    name="⚠️ **__Nicht gefunden__**",
                    value="\n".join(not_found_bots),
                    inline=False,
                )

            # Field 5: Limit reached
            if limit_reached_bots:
                embed.add_field(
                    name=f"⚠️ **__Limit erreicht__** ({len(tracked_bots)}/{MAX_TRACKED_BOTS} Bots getrackt)",
                    value="\n".join(limit_reached_bots),
                    inline=False,
                )

            await ctx.send(embed=embed)
            return

        # MARK: > remove
        elif action == "remove":
            if not arg:
                await ctx.send(
                    "Bitte gib den Index des zu entfernenden Bots an, z.B. `!track remove 2` oder mehrere durch Kommas getrennt."
                )
                return

            indices = []
            not_found = []

            # Parse comma-separated values and ranges
            for part in arg.split(","):
                part = part.strip()
                if not part:
                    continue

                # --- Check for ranges: 5-8 or 13..15 ---
                if "-" in part or ".." in part:
                    splitter = "-" if "-" in part else ".."
                    try:
                        start_str, end_str = part.split(splitter)
                        start = int(start_str.strip())
                        end = int(end_str.strip())

                        for n in range(start, end + 1):
                            idx = n - 1
                            if 0 <= idx < len(tracked_bots):
                                indices.append(idx)
                            else:
                                not_found.append(str(n))
                    except ValueError:
                        not_found.append(part)
                    continue

                # --- Single number ---
                try:
                    idx = int(part) - 1
                    if 0 <= idx < len(tracked_bots):
                        indices.append(idx)
                    else:
                        not_found.append(part)
                except ValueError:
                    not_found.append(part)

            # Remove duplicates from indices
            indices = sorted(set(indices), reverse=True)

            removed_bots = []
            removed_info = []  # store (original_index, bot_dict)
            for idx in indices:
                bot = tracked_bots.pop(idx)
                removed_bots.append(bot)
                removed_info.append((idx + 1, bot))  # save 1-based index

            set_tracked_bots(guild_id=guild_id, tracked=tracked_bots)

            # Build embed
            embed = Embed(title="Bots zum Tracken entfernen", color=0xFF0000) # <-- Embed is now imported

            if removed_info:
                for idx, bot_info in removed_info:
                    embed.add_field(
                        name=f"{idx}. {bot_info['emoji']} {bot_info['name']}",
                        value=f"Autor: {bot_info['author']}",
                        inline=False,
                    )

            # Remove duplicates + sort not found
            if not_found:
                clean_nf = sorted(
                    set(not_found), key=lambda x: int(x) if x.isdigit() else x
                )
                embed.add_field(
                    name="⚠️ Ungültige Indizes",
                    value="\n".join(clean_nf),
                    inline=False,
                )

            await ctx.send(embed=embed)

        else:
            await ctx.send(
                f"## Nutzung von `{ctx.prefix}track`"
                f"\n-# (aliases: {ctx.prefix}t)"
                "\n"
                "\n- `add <Botname>      ` → fügt Bot zu zum tracking mit namen `<Botname>`"
                "\n- `remove <list index>` → entfernt bot vom tracking mit index `<list index>`"
                "\n- `list               ` → Zeigt alle tracked Bots"
                "\n-# ℹ️ Syntax: `<param>` = erforderlicher parameter, `[param]` = optionaler parameter"
            )
            return

async def setup(bot):
    await bot.add_cog(TrackingCommand(bot))