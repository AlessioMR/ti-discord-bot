import discord
from discord import app_commands
import gspread
from google.oauth2.service_account import Credentials
from collections import Counter
import os
import json
import re

# =========================================================
# 🔐 DISCORD TOKEN
# =========================================================
TOKEN = os.getenv("DISCORD_TOKEN")

# =========================================================
# 📊 GOOGLE SHEETS SETUP
# =========================================================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

creds_json = json.loads(os.getenv("GOOGLE_CREDENTIALS"))

creds = Credentials.from_service_account_info(
    creds_json,
    scopes=SCOPES
)

gc = gspread.authorize(creds)

# =========================================================
# 📄 SHEET ID
# =========================================================
SHEET_ID = "16QIygRCKOKSRWwsbWzcbG_zNEtLlBxVIokmy-xyqTxs"

spreadsheet = gc.open_by_key(SHEET_ID)
sheet = spreadsheet.sheet1

# =========================================================
# 🤖 DISCORD SETUP
# =========================================================
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

statistics = app_commands.Group(
    name="statistics",
    description="Twilight Imperium Statistiken"
)

tree.add_command(statistics)

# =========================================================
# 🧠 HELPERS
# =========================================================
def normalize_name(name: str):
    return name.strip().lower()

def parse_players(entry: str):
    if not entry:
        return []
    return [p.strip() for p in str(entry).split(",") if p.strip()]

def parse_game_players(raw: str):
    """
    Robust parser for:
    1. Chris (Faction, 10)
    """
    if not raw:
        return []

    result = []

    entries = raw.split(",")

    for e in entries:
        e = e.strip()

        # remove numbering "1. "
        e = re.sub(r"^\d+\.\s*", "", e)

        try:
            name_part = e.split("(")[0].strip()
            inside = e.split("(")[1].replace(")", "")

            parts = inside.split(",")

            faction = parts[0].strip() if len(parts) > 0 else "Unknown"

            vp = 0
            if len(parts) > 1:
                try:
                    vp = float(parts[1].strip())
                except:
                    vp = 0

            result.append({
                "name": name_part,
                "faction": faction,
                "vp": vp
            })

        except:
            continue

    return result

# =========================================================
# 🏆 HALL OF FAME
# =========================================================
def get_halloffame():
    data = sheet.get_all_records()

    winners = []

    for row in data:
        w = row.get("Gewinner")
        if w and str(w).strip():
            winners.append(str(w).strip())

    counts = Counter(winners)
    sorted_data = counts.most_common()

    result = []
    last_wins = None
    rank = 0
    skip = 0

    for player, wins in sorted_data:

        if wins != last_wins:
            rank += 1 + skip
            skip = 0
        else:
            skip += 1

        last_wins = wins
        result.append((rank, player, wins))

    return result

# =========================================================
# ❤️ COMMUNITY
# =========================================================
def get_community():
    data = sheet.get_all_records()

    players = []

    for row in data:
        for p in parse_players(row.get("Community Preis")):
            players.append(p)

    return Counter(players)

# =========================================================
# 👤 PLAYER STATS
# =========================================================
def get_player_stats(name: str):

    data = sheet.get_all_records()

    n = normalize_name(name)

    games = 0
    wins = 0
    community = 0
    total_vp = 0.0

    factions = Counter()
    faction_wins = Counter()

    for row in data:

        players = parse_game_players(row.get("Spieler (Volk, VP)"))
        if not players:
            continue

        found = False

        for p in players:

            if normalize_name(p["name"]) == n:

                found = True
                games += 1

                total_vp += p["vp"]
                factions[p["faction"]] += 1

                if normalize_name(row.get("Gewinner", "")) == n:
                    wins += 1
                    faction_wins[p["faction"]] += 1

        for c in parse_players(row.get("Community Preis")):
            if normalize_name(c) == n:
                community += 1

    winrate = (wins / games * 100) if games else 0
    avg_vp = (total_vp / games) if games else 0

    return {
        "games": games,
        "wins": wins,
        "community": community,
        "winrate": winrate,
        "total_vp": total_vp,
        "avg_vp": avg_vp,
        "factions": factions,
        "faction_wins": faction_wins
    }

# =========================================================
# 🏆 /statistics halloffame
# =========================================================
@statistics.command(name="halloffame")
async def halloffame(interaction: discord.Interaction):

    data = get_halloffame()

    text = "🏆 **Twilight Imperium Hall of Fame**\n\n"

    for rank, player, wins in data:

        win_text = "1 Sieg" if wins == 1 else f"{wins} Siege"

        if rank == 1:
            medal = "🥇"
        elif rank == 2:
            medal = "🥈"
        elif rank == 3:
            medal = "🥉"
        else:
            medal = f"{rank}."

        text += f"{medal} **{player}** — {win_text}\n"

    await interaction.response.send_message(text)

# =========================================================
# ❤️ /statistics siegerderherzen
# =========================================================
@statistics.command(name="siegerderherzen")
async def siegerderherzen(interaction: discord.Interaction):

    data = get_community()

    text = "❤️ **Sieger der Herzen**\n\n"

    medal_map = ["🥇", "🥈", "🥉"]

    last = None
    i = 0

    for player, count in data.most_common():

        if count != last:
            last = count
            medal = medal_map[i] if i < len(medal_map) else f"{i+1}."
            i += 1

        label = "1-facher Preisträger" if count == 1 else f"{count}-facher Preisträger"
        text += f"{medal} **{player}** — {label}\n"

    await interaction.response.send_message(text)

# =========================================================
# 👤 /statistics player
# =========================================================
@statistics.command(name="player")
@app_commands.describe(name="Spielername")
async def player(interaction: discord.Interaction, name: str):

    s = get_player_stats(name)

    factions = "\n".join([f"{k}: {v}" for k, v in s["factions"].most_common()]) or "Keine Daten"
    faction_wins = "\n".join([f"{k}: {v}" for k, v in s["faction_wins"].most_common()]) or "Keine Daten"

    text = f"""
👤 **Statistik für {name}**

🎮 Spiele: {s['games']}
🏆 Siege: {s['wins']}
❤️ Community Preise: {s['community']}

📊 Winrate: {s['winrate']:.1f}%

⭐ Gesamt VP: {s['total_vp']:.1f}
📈 Ø VP: {s['avg_vp']:.2f}

🌍 Völker gespielt:
{factions}

🏆 Siege mit Völkern:
{faction_wins}
"""

    await interaction.response.send_message(text)

# =========================================================
# 🚀 START
# =========================================================
@client.event
async def on_ready():
    await tree.sync()
    print(f"Bot läuft als {client.user}")

client.run(TOKEN)