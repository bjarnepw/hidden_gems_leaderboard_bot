# helper_scripts/data_functions.py

# Standard library imports
import json
from typing import List, Dict

# Third-party imports
# None

# Own modules
from helper_scripts.globals import LOCAL_DATA_PATH_DIR


BOT_DATA_FILE = LOCAL_DATA_PATH_DIR / "bot_data.json"


# MARK: Bot Data
def load_bot_data() -> dict:
    """Load the entire bot_data.json file."""
    if not BOT_DATA_FILE.exists():
        return {}
    with open(BOT_DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_bot_data(data: dict):
    """Save a full dict back into bot_data.json."""
    with open(BOT_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# MARK: Guild Data
def get_guild_data(guild_id: int) -> dict:
    """Return the data for a specific guild ID, creating it if missing."""
    data = load_bot_data()
    guilds = data.setdefault("guild_data", {})

    guild_id_str = str(guild_id)

    # Create empty structure if missing, including the new voting list
    if guild_id_str not in guilds:
        guilds[guild_id_str] = {
            "tracked_bots": [], 
            "scheduled_channels": [],
            # NEW: Field for voting tracking
            "tracked_voting_bots": [] 
        }
        save_bot_data(data)

    return guilds[guild_id_str]


# MARK: Tracked Bots
def _get_tracking_key(mode: str) -> str:
    """Returns the key for the tracked list based on mode, defaults to 'tracked_bots'."""
    if mode.lower() == "voting":
        return "tracked_voting_bots"
    # Default key for existing functionality
    return "tracked_bots" 

def get_tracked_bots(guild_id: int, mode: str = "leaderboard") -> list[dict]:
    """Return the list of tracked bots for a specific guild ID and tracking mode.
    Mode can be 'leaderboard' (default) or 'voting'."""
    guild_data = get_guild_data(guild_id)
    return guild_data.get(_get_tracking_key(mode), [])

def set_tracked_bots(guild_id: int, tracked: list[dict], mode: str = "leaderboard"):
    """Write the updated tracked bots list back into bot_data.json for a specific mode.
    Mode can be 'leaderboard' (default) or 'voting'."""
    data = load_bot_data()
    guilds = data.setdefault("guild_data", {})
    
    guild_id_str = str(guild_id)
    
    # Ensure the guild entry exists (call get_guild_data to initialize if not)
    # This also ensures the guild data dictionary is present in 'data' before assignment
    guilds[guild_id_str] = get_guild_data(guild_id)

    guilds[guild_id_str][_get_tracking_key(mode)] = tracked
    save_bot_data(data)



# MARK: Poll Data Management
def get_polls_path():
    return LOCAL_DATA_PATH_DIR / "active_polls.json"

def load_polls() -> dict:
    """Loads active polls from JSON."""
    path = get_polls_path()
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def save_polls(data: dict):
    """Saves active polls to JSON."""
    path = get_polls_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)