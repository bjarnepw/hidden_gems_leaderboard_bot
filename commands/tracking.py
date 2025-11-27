# commands/tracking.py

# Standard library imports
from typing import List, Optional, Dict
import re
import datetime

# Third-party imports
import discord
from discord.ext import commands, tasks
from discord import TextChannel

# Own modules
# Stellen Sie sicher, dass diese Imports korrekt sind, basierend auf Ihrer Projektstruktur
from helper_scripts.helper_functions import get_leaderboard_json
from helper_scripts.data_functions import get_tracked_bots, set_tracked_bots, load_polls, save_polls


class TrackingCommand(commands.Cog):

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
                embed = discord.Embed( 
                    title=f"Tracked Bots in {location_type}",
                    description="📭 Keine Bots werden aktuell getrackt.",
                    color=embed_color,
                )
                await ctx.send(embed=embed)
                return

            embed = discord.Embed(title=f"Tracked Bots in {location_type}", color=embed_color) # <-- Embed is now imported

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

            embed = discord.Embed(title="Bots zum Tracken Hinzufügen", color=0x00FF00) # <-- Embed is now imported

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
            embed = discord.Embed(title="Bots zum Tracken entfernen", color=0xFF0000) # <-- Embed is now imported

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

    """
    Commands and tasks for managing the bot tracking polls, including the 
    background worker to check for ended polls.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Lade die Poll-Daten beim Start und speichere sie als Klassen-Attribut
        self.poll_data: dict = load_polls()
        
        # Starte die Hintergrundaufgabe
        self.poll_watcher_task.start()

    def cog_unload(self):
        """Wird aufgerufen, wenn der Cog entladen wird. Stoppt die Hintergrundaufgabe."""
        self.poll_watcher_task.cancel()
        
    # MARK: - Background Task
    @tasks.loop(seconds=5)
    async def poll_watcher_task(self):
        """Überwacht laufende Discord-Abstimmungen und verarbeitet die Ergebnisse nach Ablauf."""
        
        # Lade die Poll-Daten neu, um den neuesten Stand zu erhalten
        self.poll_data = load_polls()
        finished_polls = []

        for message_id, data in self.poll_data.copy().items(): # Iteriere über eine Kopie, da wir das Original ändern
            channel_id = data["channel_id"]
            # Verwende self.bot
            channel = self.bot.get_channel(channel_id)

            if channel is None:
                finished_polls.append(message_id)
                continue

            guild_id = channel.guild.id if channel.guild else None
            tracked_bots = get_tracked_bots(guild_id=guild_id)
            try:
                # Verwende self.bot zum Holen der Nachricht
                msg = await channel.fetch_message(int(message_id))
            except:
                finished_polls.append(message_id)
                continue

            if msg.poll is None:
                finished_polls.append(message_id)
                continue

            poll = msg.poll
            if poll.is_finalised:
                # Poll beendet: Daten entfernen und Ergebnis verarbeiten
                self.poll_data.pop(message_id, None)

                save_polls(self.poll_data)
                
                
                # Sicherer Zugriff auf die Zähler (Ja/Nein sind Index 1 und 2)
                ja_answer = poll.get_answer(1)
                nein_answer = poll.get_answer(2)
                
                # Use asynchronous list comprehension to gather all voters and get the count
                ja_voters = [v async for v in ja_answer.voters()] if ja_answer else []
                nein_voters = [v async for v in nein_answer.voters()] if nein_answer else []

                ja = len(ja_voters)
                nein = len(nein_voters)

                match = re.search(r"Bot '(.+?)' \((.+?)\)", poll.question)
                if match:
                    actionedbot_name = match.group(1)
                    actionedbot_author = match.group(2)
                else:
                    actionedbot_name = None
                    actionedbot_author = None
                    
                leaderboard_json, _ = get_leaderboard_json()
                actionedbot_info = None
                
                for bot_entry in leaderboard_json:
                    if actionedbot_name and actionedbot_author and (
                        bot_entry.get("Bot", "").lower() == actionedbot_name.lower() and
                        bot_entry.get("Autor / Team", "").lower() == actionedbot_author.lower()
                    ):
                        actionedbot_info = bot_entry
                        break

                if not actionedbot_info:
                    await channel.send(f"❌ Bot '{actionedbot_name}' ({actionedbot_author}) nicht in Leaderboard gefunden.")
                    continue 
                    
                # Bestimme, ob es eine 'add' oder 'remove' Abstimmung war
                mode = "remove" if "entfernt" in poll.question else "add"
                    
                if mode == "add":
                    if ja > nein:
                        await channel.send(f"Der Bot {actionedbot_name} ({actionedbot_author}) wurde nach dem Voting nun zu den Getrackten Bots Hinzugefügt!")
                        
                        leaderboard_json, _ = get_leaderboard_json()
                        if "error" in leaderboard_json[0]:
                            await channel.send(leaderboard_json[0]["error"])
                            continue

                        bot_names = [actionedbot_info] 
                        added_bots = []
                        MAX_TRACKED_BOTS = 25

                        for bot_name_dict in bot_names:
                            bot_info = bot_name_dict 
                            
                            bot_dict = {
                                "name": bot_info.get("Bot"),
                                "emoji": bot_info.get("Col1", ""),
                                "author": bot_info.get("Autor / Team", ""),
                            }
                            
                            if len(tracked_bots) >= MAX_TRACKED_BOTS:
                                continue

                            if bot_dict in tracked_bots:
                                continue

                            tracked_bots.append(bot_dict)
                            added_bots.append(bot_dict)
                            
                        if added_bots:
                            set_tracked_bots(guild_id=guild_id, tracked=tracked_bots)
                            
                    else:
                        await channel.send(f"Der Bot {actionedbot_name} ({actionedbot_author}) wurde nach dem Voting nicht zu den Getrackten Bots Hinzugefügt!")
                
                else: # mode == "remove"
                    if ja > nein:
                        await channel.send(f"Der Bot {actionedbot_name} ({actionedbot_author}) wurde nach dem Voting nun von den Getrackten Bots Entfernt!")
                        
                        removed = None
                        for i, b in enumerate(tracked_bots):
                            if b["name"].lower() == actionedbot_name.lower() and b["author"].lower() == actionedbot_author.lower():
                                removed = tracked_bots.pop(i)
                                break
                                
                        if removed:
                            set_tracked_bots(guild_id=guild_id, tracked=tracked_bots)
                            await channel.send(f"✅ Bot '{actionedbot_name} ({actionedbot_author})' wurde entfernt!")
                        else:
                            await channel.send(f"❌ Bot '{actionedbot_name} ({actionedbot_author})' nicht in der Tracking-Liste gefunden!")
                        
                    else:
                        await channel.send(f"Der Bot {actionedbot_name} ({actionedbot_author}) wurde nach dem Voting nicht von den Getrackten Bots Entfernt!")

        # Entferne Polls, deren Channel/Nachricht nicht mehr erreichbar waren
        for message_id in finished_polls:
            if message_id in self.poll_data:
                del self.poll_data[message_id]
                
        if self.poll_data:
            save_polls(self.poll_data)
            
    @poll_watcher_task.before_loop
    async def before_poll_watcher_task(self):
        # Warte, bis der Bot bereit ist, bevor die Task gestartet wird
        await self.bot.wait_until_ready()

    # MARK: - Commands
    @commands.command(name="polltrack")
    async def polltrack_command(self, ctx: commands.Context, mode: str = None, *, botname: str = None):
        """Erstellt eine Abstimmung, um einen Bot zum Tracking hinzuzufügen oder zu entfernen."""
        
        # Lade Poll-Daten neu, um den aktuellsten Stand zu haben, falls eine andere Instanz sie geändert hat
        self.poll_data = load_polls()

        if mode not in ["add", "remove"]:
            await ctx.send("Nutze: `!polltrack add <Botname>` oder `!polltrack remove <Botname>`")
            return

        if not botname:
            await ctx.send("Bitte einen Botnamen angeben.")
            return

        # Überprüfe auf laufende Abstimmungen für diesen Botnamen
        for existing_poll in self.poll_data.values():
            if existing_poll.get("bot_name", "").lower() == botname.lower():
                await ctx.send(f"❌ Für den Bot `{botname}` läuft bereits eine Abstimmung!")
                return

        leaderboard_json, _ = get_leaderboard_json()
        if not leaderboard_json or ("error" in leaderboard_json[0] if leaderboard_json else False):
            await ctx.send(leaderboard_json[0]["error"] if leaderboard_json else "❌ Leaderboard-Daten konnten nicht geladen werden.")
            return

        # Logik zum Parsen des Botnamens und optionalen Index (z.B. "Botname 1")
        parts = botname.rsplit(" ", 1)
        base_name, index = (
            (parts[0], int(parts[1]) - 1)
            if len(parts) == 2 and parts[1].isdigit()
            else (botname, None)
        )

        matching_bots = [
            b
            for b in leaderboard_json
            if b.get("Bot", "").lower() == base_name.lower()
        ]

        if not matching_bots:
            await ctx.send(f"❌ Bot `{botname}` wurde nicht im Leaderboard gefunden!")
            return

        # Handle den Fall, dass mehrere Bots gefunden werden
        if len(matching_bots) > 1 and index is None:
            msg = ["⚠️ Mehrere Bots gefunden — bitte nutze einen Index:"]
            for i, b in enumerate(matching_bots, start=1):
                msg.append(f"{i}. {b.get('Col1', '')} {b.get('Bot', '')} ({b.get('Autor / Team', '')})")

            await ctx.send("\n".join(msg))
            return

        # Wähle den Bot aus
        index = 0 if index is None else min(index, len(matching_bots) - 1)
        bot_info = matching_bots[index]
        resolved_name = bot_info.get("Bot")
        resolved_author = bot_info.get("Autor / Team", "Unbekannt")

        # Erstelle die Frage
        if mode == "add":
            question = f"Soll der Bot '{resolved_name}' ({resolved_author}) zu den getrackten Bots hinzugefügt werden?"
        else:
            question = f"Soll der Bot '{resolved_name}' ({resolved_author}) von den getrackten Bots entfernt werden?"

        # Setze die Ablaufzeit auf 1 Stunde
        now = datetime.datetime.now(datetime.timezone.utc)
        expiry_time = now + datetime.timedelta(hours=1) 
        
        # Erstelle die Abstimmung
        # Poll senden
        poll = discord.Poll(
            question=question,
            duration=datetime.timedelta(hours=1),
            multiple=False,
        ).add_answer(
            text="Ja",
            emoji="✅"
        ).add_answer(
            text="Nein",
            emoji="❌"
        )

        # Sende die Abstimmung
        msg = await ctx.send(poll=poll)

        # Speichere die Poll-Informationen
        self.poll_data[str(msg.id)] = {
            "channel_id": ctx.channel.id,
            "bot_name": resolved_name,
            "bot_author": resolved_author
        }

        save_polls(self.poll_data)
        await ctx.send("🗳️ Abstimmung wurde erstellt und endet in 1 Stunde!")