import discord
from discord import app_commands
import gspread
from google.oauth2.service_account import Credentials
from collections import Counter
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

# =========================================================
# 📦 STATISTICS GROUP (/statistics ...)
# =========================================================
statistics = app_commands.Group(
    name="statistics",
    description="Twilight Imperium Statistiken"
)

tree.add_command(statistics)

# =========================================================
# 🏆 HALL OF FAME LOGIC
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
# ❤️ COMMUNITY PREIS LOGIC
# =========================================================
def get_community():
    data = sheet.get_all_records()

    players = []

    for row in data:
        entry = row.get("Community Preis")

        if entry and str(entry).strip():
            parts = str(entry).split(",")

            for p in parts:
                name = p.strip()
                if name:
                    players.append(name)

    counts = Counter(players)
    sorted_data = counts.most_common()

    result = []
    last_count = None
    rank = 0
    skip = 0

    for player, count in sorted_data:
        if count != last_count:
            rank += 1 + skip
            skip = 0
        else:
            skip += 1

        last_count = count
        result.append((rank, player, count))

    return result

# =========================================================
# 🏆 /statistics halloffame
# =========================================================
@statistics.command(
    name="halloffame",
    description="Zeigt die Hall of Fame"
)
async def halloffame(interaction: discord.Interaction):

    data = get_halloffame()

    text = "🏆 **Twilight Imperium Hall of Fame**\n\n"

    for rank, player, wins in data:

        if rank == 1:
            medal = "🥇"
        elif rank == 2:
            medal = "🥈"
        elif rank == 3:
            medal = "🥉"
        else:
            medal = f"{rank}."

        text += f"{medal} **{player}** — {wins} Siege\n"

    embed = discord.Embed(
        title="Hall of Fame",
        description=text,
        color=0xF1C40F
    )

    await interaction.response.send_message(embed=embed)

# =========================================================
# ❤️ /statistics siegerderherzen
# =========================================================
@statistics.command(
    name="siegerderherzen",
    description="Zeigt die Community-Preisträger"
)
async def siegerderherzen(interaction: discord.Interaction):

    data = get_community()

    text = "❤️ **Sieger der Herzen**\n\n"

    medal_map = ["🥇", "🥈", "🥉"]

    last_count = None
    medal_index = 0

    for rank, player, count in data:

        if count != last_count:
            last_count = count

            if medal_index < len(medal_map):
                medal = medal_map[medal_index]
            else:
                medal = f"{medal_index + 1}."

            medal_index += 1

        if count == 1:
            label = "1-facher Preisträger"
        else:
            label = f"{count}-facher Preisträger"

        text += f"{medal} **{player}** — {label}\n"

    embed = discord.Embed(
        title="Sieger der Herzen",
        description=text,
        color=0xE74C3C
    )

    await interaction.response.send_message(embed=embed)

# =========================================================
# 🚀 BOT START
# =========================================================
@client.event
async def on_ready():
    await tree.sync()
    print(f"Bot läuft als {client.user}")

client.run(TOKEN)