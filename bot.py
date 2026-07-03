import discord
from discord import app_commands
import gspread
from google.oauth2.service_account import Credentials
from collections import Counter, defaultdict
import os
import json

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
# 📦 HELPER
# =========================================================
def parse_players(entry: str):
    if not entry:
        return []
    return [p.strip() for p in str(entry).split(",") if p.strip()]

def normalize_score(val):
    try:
        val = str(val).strip()
        return float(val)
    except:
        return 0.0

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
# 📊 PLAYER STATISTICS CORE
# =========================================================
def get_player_stats(name: str):
    data = sheet.get_all_records()

    games_played = 0
    wins = 0
    community = 0
    total_score = 0.0
    normalized_score = 0.0

    faction_counter = Counter()
    faction_wins = Counter()

    for row in data:

        players_raw = row.get("Spieler (Volk, VP)")
        if not players_raw:
            continue

        players = parse_players(players_raw)

        found = False
        game_score = 0.0

        for entry in players:
            if "(" not in entry:
                continue

            try:
                player_name = entry.split("(")[0].strip()
                faction = entry.split("(")[1].split(",")[0].strip()
                score = entry.split(",")[1].replace(")", "").strip()
                score = normalize_score(score)
            except:
                continue

            if player_name == name:
                found = True
                faction_counter[faction] += 1
                total_score += score
                normalized_score += (score / 10) * 10  # already normalized scale
                game_score = score

        if found:
            games_played += 1

            if row.get("Gewinner") == name:
                wins += 1

            for p in parse_players(row.get("Community Preis")):
                if p == name:
                    community += 1

            # faction win tracking
            if row.get("Gewinner") == name:
                for entry in players:
                    if name in entry:
                        faction = entry.split("(")[1].split(",")[0].strip()
                        faction_wins[faction] += 1

    winrate = (wins / games_played * 100) if games_played else 0
    avg_score = (total_score / games_played) if games_played else 0

    return {
        "games": games_played,
        "wins": wins,
        "community": community,
        "winrate": winrate,
        "total_score": total_score,
        "avg_score": avg_score,
        "factions": faction_counter,
        "faction_wins": faction_wins
    }

# =========================================================
# 🏆 halloffame
# =========================================================
@statistics.command(name="halloffame")
async def halloffame(interaction: discord.Interaction):

    data = get_halloffame()

    text = "🏆 **Twilight Imperium Hall of Fame**\n\n"

    for rank, player, wins in data:

        if wins == 1:
            win_text = "1 Sieg"
        else:
            win_text = f"{wins} Siege"

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
# ❤️ sieger der herzen
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
# 👤 PLAYER STATISTICS
# =========================================================
@statistics.command(name="player")
@app_commands.describe(name="Spielername")
async def player(interaction: discord.Interaction, name: str):

    s = get_player_stats(name)

    factions = "\n".join([f"{f}: {c}" for f, c in s["factions"].most_common()]) or "Keine Daten"
    faction_wins = "\n".join([f"{f}: {c} Siege" for f, c in s["faction_wins"].most_common()]) or "Keine Daten"

    text = f"""
👤 **Statistik für {name}**

🎮 Spiele: {s['games']}
🏆 Siege: {s['wins']}
❤️ Community Preise: {s['community']}

📊 Winrate: {s['winrate']:.1f}%

⭐ Gesamt VP: {s['total_score']:.1f}
📈 Ø VP: {s['avg_score']:.2f}

🌍 Völker gespielt:
{factions}

🏆 Siege mit Völkern:
{faction_wins}
"""

    await interaction.response.send_message(text)

# =========================================================
# 🚀 BOT
# =========================================================
@client.event
async def on_ready():
    await tree.sync()
    print(f"Bot läuft als {client.user}")

client.run(TOKEN)