# helper_scripts/bot_commands.py
# Standard library imports

import os 
import re 
import json 
import datetime 
import time # <<< NEU: Für die 1-Sekunden-Pause beim Geocoding
from typing import Optional, List, Dict
from pathlib import Path
import urllib.request

# Third-party imports

import contextily as cx 
import discord
from discord.ext import commands
from discord import TextChannel
import requests 
import pandas as pd 
from bs4 import BeautifulSoup 
import matplotlib 
matplotlib.use("Agg") 
import matplotlib.pyplot as plt 
import folium 
from geopy.geocoders import Nominatim 

# Own modules
# Diese Imports müssen natürlich in deinem Projekt existieren:
from helper_scripts.helper_functions import get_leaderboard_json
from helper_scripts.data_functions import get_tracked_bots, set_tracked_bots

# ----------------------------------------------------------------------
# MARK: Configuration & Constants
# ----------------------------------------------------------------------

URL = "https://hiddengems.gymnasiumsteglitz.de/scrims"
DATA_ROOT = Path("data")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
GEO_CACHE_FILE = DATA_ROOT / "geo_cache.json" 
DATA_ROOT.mkdir(exist_ok=True)

LANG_MAP = {
    'python': 'Python', 'cpp': 'C++', 'c': 'C', 'csharp': 'C#',
    'ts': 'TypeScript', 'ruby': 'Ruby', 'java': 'Java', 'js': 'JavaScript', 'go': 'Go'
}

# Stelle sicher, dass der Daten-Root-Ordner existiert
DATA_ROOT.mkdir(exist_ok=True)

# ----------------------------------------------------------------------
# MARK: Core Helper Functions (Scraping, Plotting, Geocoding, Mapping)
# ----------------------------------------------------------------------

def parse_float(text: str):
    if not text: return None
    t = text.strip().replace('%', '').replace(',', '.')
    try:
        m = re.search(r'(-?\d+(.\d+)?)', t)
        if m: return float(m.group(1))
    except: pass
    return None

def scrape_data():
    """Scrapes data from the website and returns a Pandas DataFrame."""
    headers = {"User-Agent": USER_AGENT}
    try:
        resp = requests.get(URL, headers=headers, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        return {"error": f"Webseite konnte nicht abgerufen werden: {e}"}
        
    soup = BeautifulSoup(resp.text, 'html.parser')

    target_table = None
    tables = soup.find_all('table')
    for tbl in tables:
        headers_text = [th.get_text(strip=True) for th in tbl.find_all('th')]
        if "Bot" in headers_text and "Score" in headers_text:
            target_table = tbl
            break

    if not target_table:
        return {"error": "Keine Leaderboard-Tabelle auf der Webseite gefunden."}

    rows = []
    tbody = target_table.find('tbody') or target_table
    for tr in tbody.find_all('tr'):
        if 'spacer' in (tr.get('class') or []): continue
        tds = tr.find_all('td')
        
        if len(tds) < 10: continue 

        def txt(i): return tds[i].get_text(strip=True) if i < len(tds) else ""

        rank_raw = txt(0)
        rank = int(re.sub(r'\D', '', rank_raw)) if re.search(r'\d', rank_raw) else None
        
        try: score = int(re.sub(r'[^\d\-]', '', txt(3)))
        except: score = 0
        
        gu_pct = parse_float(txt(4))
        cf_pct = parse_float(txt(5))
        fc_pct = parse_float(txt(6))
        
        author = txt(7)
        city = txt(8)
        
        lang = "Unknown"
        if len(tds) > 9:
            img = tds[9].find('img')
            if img and img.get('src'):
                src_base = os.path.basename(img.get('src').split('?')[0])
                m = re.match(r'([a-z0-9_\-]+)-logo', src_base, flags=re.I)
                if m:
                    key = m.group(1).lower()
                    lang = LANG_MAP.get(key, key.capitalize())

        rows.append({
            "rank": rank,
            "bot": txt(2),
            "score": score,
            "gu_pct": gu_pct,
            "cf_pct": cf_pct,
            "fc_pct": fc_pct,
            "author": author,
            "city": city,
            "language": lang
        })

    return pd.DataFrame(rows)

def generate_plots_images(df, folder):
    """Generiert die Plots und speichert sie im angegebenen Ordner."""
    folder.mkdir(parents=True, exist_ok=True)
    
    metrics_to_plot = [
        ("Score Distribution", 'score', '#f59e0b', 'Higher', 'score_hist.png'),
        ("Gem Utilization (GU)", 'gu_pct', '#3b82f6', 'Higher', 'gu_pct_hist.png'),
        ("Chaos Factor (CF)", 'cf_pct', '#ef4444', 'Lower', 'cf_pct_hist.png'),
        ("Floor Coverage (FC)", 'fc_pct', '#10b981', 'Higher', 'fc_pct_hist.png'),
    ]

    # Histogramme
    for name, col, color, better, file_name in metrics_to_plot:
        fig, ax = plt.subplots(figsize=(6, 4))
        if col in df.columns:
            data = pd.to_numeric(df[col], errors='coerce').dropna()
            if not data.empty:
                ax.hist(data, bins=15, color=color, alpha=0.7)
                ax.set_xlabel(name.split('(')[0].strip())
                ax.set_ylabel("Count")
            else:
                ax.text(0.5, 0.5, f"No data for {name}", 
                       horizontalalignment='center', verticalalignment='center',
                       transform=ax.transAxes, fontsize=12)
        else:
            ax.text(0.5, 0.5, f"Column '{col}' not found", 
                   horizontalalignment='center', verticalalignment='center',
                   transform=ax.transAxes, fontsize=12)
                   
        ax.set_title(f"{name} ({better} is Better)")
        fig.tight_layout()
        fig.savefig(folder / file_name)
        plt.close(fig)
        
    # Language bar chart
    fig, ax = plt.subplots(figsize=(6, 4))
    if 'language' in df.columns:
        df['language'].value_counts().plot(kind='bar', ax=ax, color="#3b82f6")
        ax.set_title("Bots per Language")
        ax.set_xlabel("Language")
    else:
        ax.text(0.5, 0.5, "No language data", 
               horizontalalignment='center', verticalalignment='center',
               transform=ax.transAxes, fontsize=12)
        ax.set_title("Bots per Language")
    fig.tight_layout()
    fig.savefig(folder / "lang_bar.png")
    plt.close(fig)

    # City bar chart
    fig, ax = plt.subplots(figsize=(6, 4))
    if 'city' in df.columns:
        city_counts = df['city'].value_counts()
        if not city_counts.empty:
            city_counts.head(15).plot(kind='bar', ax=ax, color="#10b981")
            ax.set_title("Top 15 Cities")
            ax.set_xlabel("City")
        else:
            ax.text(0.5, 0.5, "No city data", 
                   horizontalalignment='center', verticalalignment='center',
                   transform=ax.transAxes, fontsize=12)
            ax.set_title("Top 15 Cities")
    else:
        ax.text(0.5, 0.5, "No city data", 
               horizontalalignment='center', verticalalignment='center',
               transform=ax.transAxes, fontsize=12)
        ax.set_title("Top 15 Cities")
    fig.tight_layout()
    fig.savefig(folder / "city_bar.png")
    plt.close(fig)
    
    return folder


# ----------------------------------------------------------------------
# MARK: Geocoding & Map Functions
# ----------------------------------------------------------------------

def load_geo_cache():
    """Lädt den Geocoding Cache, behandelt leere oder fehlende Dateien."""
    if GEO_CACHE_FILE.exists():
        try:
            content = GEO_CACHE_FILE.read_text(encoding='utf-8').strip()
            if content:
                # Stelle sicher, dass der Inhalt nicht leer ist, um JSONDecodeError (Errno 22) zu vermeiden
                return json.loads(content)
            else:
                return {} # Leere Datei ist ein leerer Cache
        except Exception as e:
            # Protokolliere den Fehler und gib leeren Cache zurück
            print(f"Fehler beim Laden des Geocaching-Caches: {e}. Verwende leeren Cache.")
            return {}
    return {}

def save_geo_cache(cache):
    """Speichert den Geocoding Cache."""
    GEO_CACHE_FILE.write_text(json.dumps(cache, indent=2), encoding='utf-8')

COLOR_PALETTE = [
    '#e60049', '#0bb4ff', '#50e991', '#e6d800', '#9b19f5', 
    '#ffa300', '#dc0ab4', '#b3d4ff', '#00bfa0', '#ff0000'
]

def get_city_color(city_count, max_count):
    if max_count == 0: return COLOR_PALETTE[0]
    index = int((city_count / max_count) * (len(COLOR_PALETTE) - 1))
    return COLOR_PALETTE[index]

def get_coordinates(city_name, cache):
    """Ruft Koordinaten ab und nutzt Caching, inklusive 1s Pause."""
    clean_city = city_name.strip()
    if not clean_city: return None
    
    # Cache Hit
    if clean_city in cache: return cache[clean_city]

    # Geocoding durchführen
    try:
        # Verwende einen längeren Timeout, um ReadTimeoutError zu vermeiden
        geolocator = Nominatim(user_agent="scrims_analyzer_bot", timeout=5) 
        
        location = geolocator.geocode(f"{clean_city}, Germany")
        if not location: 
            location = geolocator.geocode(clean_city)
        
        if location:
            coords = [location.latitude, location.longitude]
            # Cache speichern
            cache[clean_city] = coords
            save_geo_cache(cache)
            time.sleep(1.2) # WARTE 1.2 SEKUNDE (etwas mehr als die obligatorische 1s)
            return coords
    except Exception as e:
        # Hier protokollieren wir den Fehler, um zu sehen, ob es immer noch Timeouts gibt
        print(f"Geocoding error for {clean_city}: {e}")
    return None

def generate_interactive_map(df, folder_path, as_html=False):
    """
    Generiert die Folium-Karte (HTML) oder einen Matplotlib-Scatter-Plot (PNG) mit Basiskarte.
    Gibt den Pfad zur gespeicherten Datei zurück.
    """
    if df is None or 'city' not in df.columns or df['city'].empty:
        return {"error": "Keine Stadt-Daten für die Kartengenerierung verfügbar."}

    geo_cache = load_geo_cache()
    
    city_counts = df['city'].dropna().value_counts()
    cities_to_map = city_counts.index.tolist()
    max_count = city_counts.max()
    mapped_coords = []

    for city in cities_to_map:
        coords = get_coordinates(city, geo_cache) 
        if coords:
            mapped_coords.append({
                'city': city,
                'coords': coords,
                'count': city_counts[city]
            })

    if not mapped_coords:
        return {"error": "Es konnten keine Koordinaten für die Städte gefunden werden."}

    # Karte erstellen (Mittelpunkt: Durchschnitt der gefundenen Koordinaten)
    avg_lat = sum(c['coords'][0] for c in mapped_coords) / len(mapped_coords)
    avg_lon = sum(c['coords'][1] for c in mapped_coords) / len(mapped_coords)
    
    if as_html:
        # Interaktive HTML-Karte mit Folium (UNVERÄNDERT)
        m = folium.Map(location=[avg_lat, avg_lon], zoom_start=6)
        
        for data in mapped_coords:
            lat, lon = data['coords']
            city_count = data['count']
            
            radius = 5 + (city_count / max_count) * 15 if max_count > 0 else 5
            color = get_city_color(city_count, max_count)

            folium.CircleMarker(
                location=[lat, lon], 
                radius=radius, 
                popup=f"{data['city']} ({city_count} bots)", 
                color=color, 
                fill=True, 
                fill_color=color,
                fill_opacity=0.7
            ).add_to(m)

        map_path = folder_path / "map.html"
        m.save(str(map_path))
        return map_path
    
    else:
        # Statisches PNG-Bild mit Matplotlib und contextily (GEÄNDERT)
        map_path = folder_path / "map.png"
        fig, ax = plt.subplots(figsize=(7, 7))
        
        # Extrahieren der Koordinaten
        lons = [c['coords'][1] for c in mapped_coords]
        lats = [c['coords'][0] for c in mapped_coords]
        sizes = [50 + (c['count'] / max_count) * 150 for c in mapped_coords]
        colors = [get_city_color(c['count'], max_count) for c in mapped_coords]

        # Scatter-Plot der Punkte
        ax.scatter(lons, lats, 
                   s=sizes, 
                   color=colors, 
                   alpha=0.7, 
                   zorder=2) # zorder=2, damit die Punkte über der Basiskarte liegen

        ax.set_title(f"Bot Locations (Static View)")
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")

        # Basiskarte hinzufügen mit contextily
        # cx.add_basemap erwartet Daten im Web Mercator (EPSG:3857) Projektion.
        # Unsere Längen- und Breitengrade sind in WGS84 (EPSG:4326).
        # Contextily übernimmt die Projektionstransformation automatisch, 
        # wenn wir ihm die Achsen übergeben.
        # Wir müssen jedoch die Achsen auf die Bounding Box der Daten setzen.
        
        # Bounding Box für die Basiskarte bestimmen
        min_lon, max_lon = min(lons) - 0.5, max(lons) + 0.5
        min_lat, max_lat = min(lats) - 0.5, max(lats) + 0.5
        
        ax.set_xlim(min_lon, max_lon)
        ax.set_ylim(min_lat, max_lat)
        
        try:
            # Hier fügen wir die Basiskarte hinzu
            cx.add_basemap(ax, 
                           crs='EPSG:4326', 
                           source=cx.providers.OpenStreetMap.Mapnik,
                           zoom=10) 
        except Exception as e:
            # GEÄNDERT: Nur noch protokollieren, KEIN await ctx.send() mehr hier
            print(f"Fehler beim Hinzufügen der Basiskarte: {e}. Karte wird ohne Basiskarte gespeichert.")
            # Wir geben einen Fehlercode zurück, den der Aufrufer (das Command) behandeln kann
            base_map_error = True

        fig.tight_layout()
        fig.savefig(map_path)
        plt.close(fig)
        return map_path

async def scrape_and_generate_plots(ctx: commands.Context) -> Path | dict:
    """Führt Scraping durch, speichert Daten und generiert Plots."""
    
    # 1. Prüfen, ob Daten von heute bereits existieren
    today = datetime.date.today().isoformat()
    folder = DATA_ROOT / f"scrims_out_{today}"
    data_path = folder / "data.csv"
    
    # 3600 Sekunden = 1 Stunde. Reduziere die Abfragefrequenz.
    if data_path.exists() and (datetime.datetime.now() - datetime.datetime.fromtimestamp(data_path.stat().st_mtime)).total_seconds() < 3600:
        await ctx.send(f"ℹ️ Verwende aktuelle Daten vom **{today}** (zuletzt aktualisiert in der letzten Stunde).")
        return folder

    # 2. Scraping durchführen
    await ctx.send("🌐 Starte Scraping der Webseite... dies kann einen Moment dauern.")
    
    df_result = scrape_data()
    
    if isinstance(df_result, dict) and "error" in df_result:
        await ctx.send(f"❌ Scraping-Fehler: {df_result['error']}")
        return df_result

    df = df_result

    # 3. Speichern und Plots generieren
    await ctx.send("📈 Daten empfangen. Generiere Diagramme...")
    
    folder.mkdir(parents=True, exist_ok=True)
    df.to_csv(data_path, index=False)
    
    generate_plots_images(df, folder)
    
    await ctx.send(f"✅ Daten ({len(df)} Bots) und Diagramme für heute erfolgreich gespeichert.")
    return folder

# ----------------------------------------------------------------------
# MARK: Discord Commands
# ----------------------------------------------------------------------

def register_commands(
    bot: commands.Bot,
    ADMINS: set,
    channels_to_post: set,
    scheduled_channels: dict,
    save_channels,
    send_leaderboard,
):
    # MARK: !leaderboard / top
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
                "\n- `[top_x]      ` → zeige nur die top [top_x] Einträge des Leaderboards"
                '\n- `["text"]      ` → erzwingt Textformat statt Bilder'
                '\n- `["no_tracked"]` → sendet keine tracked Bots'
                "\n-# ℹ️ Syntax: `<param>` = erforderlicher parameter, `[param]` = optionaler parameter"
            )
            return

        guild_id = ctx.guild.id if ctx.guild else ctx.author.id

        top_x_int = 0 
        if top_x:
            try:
                top_x_int = int(top_x)
                if top_x_int < 0:
                    top_x_int = 0
            except ValueError:
                if top_x.lower() != "text":
                    await ctx.send("❌ Ungültige Zahl. Bitte gib eine ganze Zahl ein.")
                    return

        force_text = mode and mode.lower() == "text"
        if top_x and top_x.lower() == "text":
            force_text = True
            top_x_int = None

        tracked_bots = get_tracked_bots(guild_id=guild_id)

        await send_leaderboard(
            channel=ctx.channel,
            tracked_bots=tracked_bots,
            top_x=top_x_int,
            force_text=force_text,
            as_thread=False,
        )

    # ------------------------------------------------------------------

    # MARK: !schedule
    @bot.command(name="schedule", aliases=["s"])
    async def schedule_command(ctx: commands.Context, action: str = ""):
        """Start, stop oder list scheduled leaderboard posts"""
        valid_actions = ["start", "stop", "list"]

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
            if channel_id in channels_to_post:
                await ctx.send("ℹ️ Dieser Channel bekommt das Leaderboard bereits.")
            else:
                channels_to_post.add(channel_id)
                scheduled_channels[str(channel_id)] = f"{guild.name}#{channel.name}"
                save_channels()
                await ctx.send(
                    "✅ Dieser Channel wird jetzt täglich um 03:00 CET das Leaderboard erhalten."
                )

        # STOP
        elif action == "stop":
            if channel_id in channels_to_post:
                channels_to_post.remove(channel_id)
                scheduled_channels.pop(str(channel_id), None)
                save_channels()
                await ctx.send(
                    "✅ Dieser Channel erhält das Leaderboard ab jetzt nicht mehr."
                )
            else:
                await ctx.send(
                    "ℹ️ Dieser Channel war nicht für das Leaderboard registriert."
                )

        # LIST (Admins only)
        elif action == "list":
            if ctx.author.id not in ADMINS:
                await ctx.send(
                    "🚫 Du hast keine Admin-Rechte, um diese Liste anzusehen."
                )
                return

            if not scheduled_channels:
                await ctx.send("📭 Es sind aktuell keine Channels registriert.")
            else:
                lines = []
                for ch_id, full_name in scheduled_channels.items():
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

    # ------------------------------------------------------------------

    # MARK: !stopbot
    @bot.command(name="stopbot", aliases=["stop"])
    async def stop_bot_command(ctx: commands.Context):
        """Stoppt den Bot (Admins only)"""
        if ctx.author.id not in ADMINS:
            await ctx.send("🚫 Du hast keine Berechtigung, diesen Befehl zu nutzen.")
            return

        await ctx.send("⏹️ Bot wird heruntergefahren...")
        await bot.close()

    # ------------------------------------------------------------------

    # MARK: !ping
    @bot.command(name="ping", aliases=["p"])
    async def ping_command(ctx: commands.Context):
        """Responds with bot latency."""
        latency_ms = round(ctx.bot.latency * 1000)
        await ctx.send(f"🏓 Pong! {latency_ms}ms")

    # ------------------------------------------------------------------

    # MARK: !track
    @bot.command(name="track", aliases=["t"])
    async def track_command(
        ctx: commands.Context,
        action: Optional[str] = None,
        *,
        arg: Optional[str] = None,
    ):
        """Manage tracked bots: list/add/remove"""
        guild_id = ctx.guild.id if ctx.guild else ctx.author.id
        tracked_bots: List[Dict] = get_tracked_bots(guild_id=guild_id)

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

            embed = discord.Embed(
                title=f"Tracked Bots in {location_type}", color=embed_color
            )

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

                parts = bot_name.rsplit(" ", 1)
                base_name, index = (
                    (parts[0], int(parts[1]) - 1)
                    if len(parts) == 2 and parts[1].isdigit()
                    else (bot_name, None)
                )

                matching_bots = [
                    b
                    for b in leaderboard_json
                    if b.get("Bot", "").lower() == base_name.lower()
                ]

                if not matching_bots:
                    not_found_bots.append(f"{not_found_counter}. ❓ {bot_name}")
                    not_found_counter += 1
                    continue

                if len(matching_bots) > 1 and index is None:
                    multi_index_needed[bot_name] = matching_bots
                    continue

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

            embed = discord.Embed(title="Bots zum Tracken Hinzufügen", color=0x00FF00)

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

            if not_found_bots:
                embed.add_field(
                    name="⚠️ **__Nicht gefunden__**",
                    value="\n".join(not_found_bots),
                    inline=False,
                )

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

            for part in arg.split(","):
                part = part.strip()
                if not part:
                    continue

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

                try:
                    idx = int(part) - 1
                    if 0 <= idx < len(tracked_bots):
                        indices.append(idx)
                    else:
                        not_found.append(part)
                except ValueError:
                    not_found.append(part)

            indices = sorted(set(indices), reverse=True)

            removed_bots = []
            removed_info = []
            for idx in indices:
                bot = tracked_bots.pop(idx)
                removed_bots.append(bot)
                removed_info.append((idx + 1, bot))

            set_tracked_bots(guild_id=guild_id, tracked=tracked_bots)

            embed = discord.Embed(title="Bots zum Tracken entfernen", color=0xFF0000)

            if removed_info:
                for idx, bot_info in removed_info:
                    embed.add_field(
                        name=f"{idx}. {bot_info['emoji']} {bot_info['name']}",
                        value=f"Autor: {bot_info['author']}",
                        inline=False,
                    )

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
                "\n- `add <Botname>      ` → fügt Bot zu zum tracking mit namen `<Botname>`"
                "\n- `remove <list index>` → entfernt bot vom tracking mit index `<list index>`"
                "\n- `list             ` → Zeigt alle tracked Bots"
                "\n-# ℹ️ Syntax: `<param>` = erforderlicher parameter, `[param]` = optionaler parameter"
            )
            return

    # ------------------------------------------------------------------

    # MARK: !stats
    @bot.command(name="stats", aliases=["st"])
    async def stats_command(
        ctx: commands.Context, plot_name: Optional[str] = None, style: Optional[str] = None
    ):
        """Zeigt verschiedene Statistiken als Diagramm an.
        Nutzung: !stats <diagramm> [stil]
        """

        available_plots = {
            "score": "Score Distribution",
            "gu": "Gem Utilization (GU)",
            "cf": "Chaos Factor (CF)",
            "fc": "Floor Coverage (FC)",
            "lang": "Bots per Language",
            "city": "Top 15 Cities",
        }

        if not plot_name or plot_name.lower() in ["help", "h"]:
            help_msg = (
                f"## Nutzung von `{ctx.prefix}stats <diagramm> [stil]`\n"
                f"-# (aliases: {ctx.prefix}st)\n"
                "\n"
                "**Verfügbare Diagramme (`<diagramm>`):**\n"
            )
            for key, name in available_plots.items():
                help_msg += f"- `{key.ljust(5)}` → {name}\n"

            help_msg += (
                "\n"
                "**Verfügbare Stile (`[stil]`):**\n"
                "- `text`    → Sende die Rohdaten (noch nicht implementiert)\n"
                "- `default` → Sende das Diagramm als Bild (Standard)\n"
                "\n"
                "ℹ️ Syntax: `<param>` = erforderlicher parameter, `[param]` = optionaler parameter"
            )
            await ctx.send(help_msg)
            return

        plot_name = plot_name.lower()
        style = style.lower() if style else "default"

        # Führe Scraping und Plot-Generierung aus oder verwende aktuelle Daten
        folder_result = await scrape_and_generate_plots(ctx)
        
        if isinstance(folder_result, dict) and "error" in folder_result:
            return 

        folder_path = folder_result

        # Suche nach dem Diagrammnamen
        plot_key = None
        for key in available_plots:
            if plot_name == key or plot_name == key.replace('_', ''):
                plot_key = key
                break

        if not plot_key:
            await ctx.send(f"❌ Ungültiger Diagramm-Name: `{plot_name}`. Nutze `!stats help`.")
            return

        # Dateiname für das Diagramm bestimmen
        if plot_key in ["lang", "city"]:
            file_name = f"{plot_key}_bar.png"
        elif plot_key in ["score", "gu", "cf", "fc"]:
            plot_col = {
                "score": "score", 
                "gu": "gu_pct", 
                "cf": "cf_pct", 
                "fc": "fc_pct"
            }.get(plot_key)
            file_name = f"{plot_col}_hist.png"
        else:
            await ctx.send(f"Interner Fehler bei der Plot-Zuordnung für {plot_key}.")
            return

        plot_path = folder_path / file_name

        # Diagramm senden
        if not plot_path.exists():
            await ctx.send(f"⚠️ Diagramm-Datei **{file_name}** wurde nicht im Datenverzeichnis gefunden. Ein Plot-Generierungsfehler ist aufgetreten.")
            return

        if style == "text":
            await ctx.send(
                f"❌ Der Stil `text` für {available_plots[plot_key]} ist noch nicht implementiert."
            )
            return
        
        # Standard: Bild senden
        try:
            await ctx.send(
                f"📊 **{available_plots[plot_key]}** (Daten vom {folder_path.name.replace('scrims_out_', '')})",
                file=discord.File(plot_path),
            )
        except Exception as e:
            await ctx.send(f"❌ Fehler beim Senden des Diagramms: {e}")
            
    # ------------------------------------------------------------------

    # MARK: !maps
    @bot.command(name="maps", aliases=["map"])
    async def maps_command(ctx: commands.Context, output_type: Optional[str] = None):
        """Generiert eine interaktive Karte der Bot-Standorte (als Bild oder HTML)."""
        
        output_type = output_type.lower() if output_type else "image"
        
        # 1. Daten sicherstellen (Scraping oder Cache-Hit)
        await ctx.send("🌐 Starte die Generierung der Standort-Karte. Dies kann beim ersten Mal etwas dauern (wegen Geocoding)!")
        folder_result = await scrape_and_generate_plots(ctx)
        
        if isinstance(folder_result, dict) and "error" in folder_result:
            return 

        folder_path = folder_result
        data_path = folder_path / "data.csv"
        
        if not data_path.exists():
            await ctx.send("❌ Fehler: Konnte keine CSV-Daten für die Kartenerstellung finden.")
            return

        try:
            df = pd.read_csv(data_path)
            
            # 2. Map generieren: HTML oder Bild
            send_as_html = output_type == "html"
            
            # generate_interactive_map nutzt Caching und generiert PNG (Matplotlib) oder HTML (Folium)
            map_path_or_error = generate_interactive_map(df, folder_path, as_html=send_as_html)
            
            if isinstance(map_path_or_error, dict) and "error" in map_path_or_error:
                await ctx.send(f"❌ Fehler bei der Kartengenerierung: {map_path_or_error['error']}")
                return

            map_path = map_path_or_error
            
            # 3. Datei senden
            data_date = folder_path.name.replace('scrims_out_', '')
            
            if send_as_html:
                await ctx.send(
                    f"✅ Interaktive Karte generiert! Lade die **`map.html`** herunter und öffne sie in deinem Webbrowser, um Zoom und Bewegung zu nutzen. (Daten vom {data_date})",
                    file=discord.File(map_path, filename="map.html")
                )
            else:
                await ctx.send(
                    f"🌍 **Statische Karte der Bot-Standorte** (Daten vom {data_date}). Nutze `!maps html` für die interaktive Version.",
                    file=discord.File(map_path) # Sendet das generierte PNG
                )

        except Exception as e:
            await ctx.send(f"❌ Unerwarteter Fehler bei der Kartengenerierung: {e}")
            
    # ------------------------------------------------------------------