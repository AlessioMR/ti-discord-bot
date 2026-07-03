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
# 🧠 CONSTANTS / HELPERS
# =========================================================
KNOWN_FACTIONS = {
    "arborec", "argent", "barony", "cabal", "creuss", "empyrean",
    "hacan", "jol nar", "jolnar", "keleres", "l1", "letnev",
    "mahact", "mentak", "muaat", "naalu", "naaz", "nekro",
    "nomad", "saar", "sardakk", "sol", "titans", "winnu",
    "xxcha", "yin", "yssaril",

    # Custom / Homebrew / Varianten aus eurem Sheet
    "dws", "crimson", "bastion", "obsidian", "ralnel",
    "tf_orange", "tf_grün", "tf_lila", "tf_gelb", "tf_rot"
}

PLAYER_COLUMN_CANDIDATES = [
    "Spieler (VP, Volk)",
    "Spieler (Volk, VP)"
]


def normalize_name(name: str) -> str:
    return str(name).strip().lower()


def clean_text(value: str) -> str:
    return str(value).strip()


def parse_number(value):
    if value is None:
        return None

    text = str(value).strip().replace(",", ".")

    if text == "":
        return None

    try:
        return float(text)
    except ValueError:
        return None


def get_rows():
    return sheet.get_all_records()


def get_player_column(row):
    for column_name in PLAYER_COLUMN_CANDIDATES:
        if column_name in row and row.get(column_name):
            return row.get(column_name)
    return ""


def split_community_names(entry: str):
    if not entry:
        return []

    return [
        name.strip()
        for name in str(entry).split(",")
        if name.strip()
    ]


def split_game_entries(raw: str):
    """
    Trennt eine komplette Spieler-Zelle in einzelne Spieler-Einträge.

    Beispiel:
    "1. Chris (10, Yssaril), 2. Timo (9, Hacan)"

    wird zu:
    [
        "Chris (10, Yssaril)",
        "Timo (9, Hacan)"
    ]
    """
    if not raw:
        return []

    raw = str(raw).strip()

    matches = re.findall(
        r"\d+\.\s*(.*?)(?=,\s*\d+\.\s*|$)",
        raw
    )

    return [m.strip() for m in matches if m.strip()]


def parse_player_entry(entry: str):
    """
    Unterstützt:
    - Chris (10, Yssaril)
    - Chris (Yssaril, 10)
    - Alessio (, Saar)
    - Alessio (12, Nekro,)
    - 4.Yogi (6, Nekro)

    Gibt zurück:
    {
        "name": "Chris",
        "vp": 10.0 oder None,
        "faction": "Yssaril" oder None
    }
    """
    if not entry:
        return None

    entry = str(entry).strip()
    entry = re.sub(r"^\d+\.\s*", "", entry)

    match = re.match(r"^(.*?)\s*\((.*?)\)\s*$", entry)

    if not match:
        return None

    name = clean_text(match.group(1))
    inside = match.group(2)

    parts = [
        p.strip()
        for p in inside.split(",")
        if p.strip() != ""
    ]

    vp = None
    faction = None

    for part in parts:
        number = parse_number(part)

        if number is not None and vp is None:
            vp = number
        elif number is None and faction is None:
            faction = clean_text(part)

    # Fallback: falls kein Volk erkannt wurde
    if not faction:
        faction = "Unbekannt"

    # Autokorrektur für Fälle wie:
    # "Keleres (11, Malte)" -> eigentlich "Malte (11, Keleres)"
    if (
        normalize_name(name) in KNOWN_FACTIONS
        and normalize_name(faction) not in KNOWN_FACTIONS
        and faction != "Unbekannt"
    ):
        name, faction = faction, name

    return {
        "name": name,
        "vp": vp,
        "faction": faction
    }


def parse_game_players(raw: str):
    result = []

    for entry in split_game_entries(raw):
        parsed = parse_player_entry(entry)

        if parsed and parsed["name"]:
            result.append(parsed)

    return result


def get_target_points(row, players):
    """
    Normalisierung auf 10 Punkte.

    Priorität:
    1. Spalte "Punkte", falls vorhanden
    2. VP des Gewinners
    3. None, wenn nicht zuverlässig bestimmbar
    """
    points_from_sheet = parse_number(row.get("Punkte"))

    if points_from_sheet and points_from_sheet > 0:
        return points_from_sheet

    winner = normalize_name(row.get("Gewinner", ""))

    if winner:
        for player in players:
            if normalize_name(player["name"]) == winner and player["vp"]:
                return player["vp"]

    return None


def format_count_sieg(count: int):
    return "1 Sieg" if count == 1 else f"{count} Siege"


def format_count_preis(count: int):
    return "1-facher Preisträger" if count == 1 else f"{count}-facher Preisträger"


# =========================================================
# 🏆 HALL OF FAME
# =========================================================
def get_halloffame():
    rows = get_rows()

    winners = []

    for row in rows:
        winner = row.get("Gewinner")

        if winner and str(winner).strip():
            winners.append(str(winner).strip())

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
# ❤️ COMMUNITY PREIS
# =========================================================
def get_community():
    rows = get_rows()

    players = []

    for row in rows:
        for name in split_community_names(row.get("Community Preis")):
            players.append(name)

    return Counter(players)


# =========================================================
# 👤 PLAYER STATS
# =========================================================
def get_player_stats(name: str):
    rows = get_rows()

    search_name = normalize_name(name)

    games_played = 0
    wins = 0
    community_awards = 0

    raw_vp_total = 0.0
    known_raw_vp_games = 0

    normalized_vp_total = 0.0
    known_normalized_vp_games = 0

    factions_played = Counter()
    faction_wins = Counter()

    for row in rows:
        players = parse_game_players(get_player_column(row))

        if not players:
            continue

        target_points = get_target_points(row, players)

        player_entry = None

        for player in players:
            if normalize_name(player["name"]) == search_name:
                player_entry = player
                break

        winner_name = normalize_name(row.get("Gewinner", ""))

        # Siege sollen mit Hall of Fame übereinstimmen:
        # Quelle ist immer die Gewinner-Spalte.
        if winner_name == search_name:
            wins += 1

        # Community Preis unabhängig von Spielereintrag zählen
        for community_name in split_community_names(row.get("Community Preis")):
            if normalize_name(community_name) == search_name:
                community_awards += 1

        if not player_entry:
            continue

        games_played += 1

        faction = player_entry["faction"] or "Unbekannt"
        vp = player_entry["vp"]

        factions_played[faction] += 1

        if winner_name == search_name:
            faction_wins[faction] += 1

        if vp is not None:
            raw_vp_total += vp
            known_raw_vp_games += 1

            if target_points and target_points > 0:
                normalized_vp_total += (vp / target_points) * 10
                known_normalized_vp_games += 1

    winrate = (wins / games_played * 100) if games_played else 0

    avg_raw_vp = (
        raw_vp_total / known_raw_vp_games
        if known_raw_vp_games
        else None
    )

    avg_normalized_vp = (
        normalized_vp_total / known_normalized_vp_games
        if known_normalized_vp_games
        else None
    )

    return {
        "games_played": games_played,
        "wins": wins,
        "community_awards": community_awards,
        "winrate": winrate,
        "raw_vp_total": raw_vp_total,
        "known_raw_vp_games": known_raw_vp_games,
        "avg_raw_vp": avg_raw_vp,
        "normalized_vp_total": normalized_vp_total,
        "known_normalized_vp_games": known_normalized_vp_games,
        "avg_normalized_vp": avg_normalized_vp,
        "factions_played": factions_played,
        "faction_wins": faction_wins
    }


# =========================================================
# 🏆 /statistics halloffame
# =========================================================
@statistics.command(
    name="halloffame",
    description="Zeigt die Hall of Fame"
)
async def halloffame(interaction: discord.Interaction):
    await interaction.response.defer()

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

        text += f"{medal} **{player}** — {format_count_sieg(wins)}\n"

    embed = discord.Embed(
        title="Hall of Fame",
        description=text,
        color=0xF1C40F
    )

    await interaction.followup.send(embed=embed)


# =========================================================
# ❤️ /statistics siegerderherzen
# =========================================================
@statistics.command(
    name="siegerderherzen",
    description="Zeigt die Community-Preisträger"
)
async def siegerderherzen(interaction: discord.Interaction):
    await interaction.response.defer()

    data = get_community()

    text = "❤️ **Sieger der Herzen**\n\n"

    medal_map = ["🥇", "🥈", "🥉"]
    last_count = None
    medal_index = 0

    for player, count in data.most_common():
        if count != last_count:
            last_count = count

            if medal_index < len(medal_map):
                medal = medal_map[medal_index]
            else:
                medal = f"{medal_index + 1}."

            medal_index += 1

        text += f"{medal} **{player}** — {format_count_preis(count)}\n"

    embed = discord.Embed(
        title="Sieger der Herzen",
        description=text,
        color=0xE74C3C
    )

    await interaction.followup.send(embed=embed)


# =========================================================
# 👤 /statistics player
# =========================================================
@statistics.command(
    name="player",
    description="Zeigt eine Spielerstatistik"
)
@app_commands.describe(name="Spielername")
async def player(interaction: discord.Interaction, name: str):
    await interaction.response.defer()

    stats = get_player_stats(name)

    factions_text = "\n".join(
        f"• {faction}: {count}x"
        for faction, count in stats["factions_played"].most_common()
    ) or "Keine Daten"

    faction_wins_text = "\n".join(
        f"• {faction}: {format_count_sieg(count)}"
        for faction, count in stats["faction_wins"].most_common()
    ) or "Keine Daten"

    if stats["avg_raw_vp"] is None:
        raw_vp_text = "Keine bekannten VP"
        avg_raw_vp_text = "Keine bekannten VP"
    else:
        raw_vp_text = f"{stats['raw_vp_total']:.1f} VP aus {stats['known_raw_vp_games']} Spielen"
        avg_raw_vp_text = f"{stats['avg_raw_vp']:.2f} VP"

    if stats["avg_normalized_vp"] is None:
        avg_normalized_text = "Keine berechenbaren VP"
    else:
        avg_normalized_text = (
            f"{stats['avg_normalized_vp']:.2f} VP "
            f"(aus {stats['known_normalized_vp_games']} Spielen)"
        )

    embed = discord.Embed(
        title=f"Spielerstatistik: {name}",
        color=0x3498DB
    )

    embed.add_field(
        name="Grundwerte",
        value=(
            f"🎮 Spiele: **{stats['games_played']}**\n"
            f"🏆 Siege: **{stats['wins']}**\n"
            f"❤️ Community Preise: **{stats['community_awards']}**\n"
            f"📊 Winrate: **{stats['winrate']:.1f}%**"
        ),
        inline=False
    )

    embed.add_field(
        name="Siegpunkte",
        value=(
            f"⭐ Gesamt VP: **{raw_vp_text}**\n"
            f"📈 Ø VP: **{avg_raw_vp_text}**\n"
            f"⚖️ Ø VP normalisiert auf 10: **{avg_normalized_text}**"
        ),
        inline=False
    )

    embed.add_field(
        name="Völker gespielt",
        value=factions_text,
        inline=False
    )

    embed.add_field(
        name="Siege mit Völkern",
        value=faction_wins_text,
        inline=False
    )

    await interaction.followup.send(embed=embed)


# =========================================================
# 🚀 BOT START
# =========================================================
@client.event
async def on_ready():
    await tree.sync()
    print(f"Bot läuft als {client.user}")


client.run(TOKEN)