import discord
from discord import app_commands
import gspread
from gspread.exceptions import WorksheetNotFound
from google.oauth2.service_account import Credentials
from collections import Counter
from dataclasses import dataclass, field
import os
import json
import re
import time

# =========================================================
# 🔐 DISCORD TOKEN
# =========================================================
TOKEN = os.getenv("DISCORD_TOKEN")

# =========================================================
# 📊 GOOGLE SHEETS SETUP
# =========================================================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

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
BOTDATA_SHEET_NAME = "BotData"

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

siegtabelle = app_commands.Group(
    name="siegtabelle",
    description="Siegtabelle verwalten"
)

tree.add_command(statistics)
tree.add_command(siegtabelle)

# =========================================================
# 🧠 CONSTANTS / HELPERS
# =========================================================
FACTION_CATEGORY_STANDARD_A_M = "standard_a_m"
FACTION_CATEGORY_STANDARD_N_Z = "standard_n_z"
FACTION_CATEGORY_TWILIGHTS_FALL = "twilights_fall"
FACTION_CATEGORY_DISCORDANT_STARS = "discordant_stars"

FACTION_CATEGORY_LABELS = {
    FACTION_CATEGORY_STANDARD_A_M: "Standard A-M",
    FACTION_CATEGORY_STANDARD_N_Z: "Standard N-Z",
    FACTION_CATEGORY_TWILIGHTS_FALL: "Twilights Fall",
    FACTION_CATEGORY_DISCORDANT_STARS: "Discordant Stars"
}

STANDARD_FACTIONS_A_M = [
    "Arborec",
    "Argent",
    "Barony",
    "Bastion",
    "Cabal",
    "Creuss",
    "Crimson",
    "DWS",
    "Empyrean",
    "Hacan",
    "Jol Nar",
    "Keleres",
    "L1",
    "Mahact",
    "Mentak",
    "Muaat"
]

STANDARD_FACTIONS_N_Z = [
    "Naalu",
    "Naaz",
    "Nekro",
    "Nomad",
    "Obsidian",
    "Ralnel",
    "Saar",
    "Sardakk",
    "Sol",
    "Titans",
    "Winnu",
    "Xxcha",
    "Yin",
    "Yssaril"
]

TWILIGHTS_FALL_FACTIONS = [
    "TF_Orange",
    "TF_Grün",
    "TF_Lila",
    "TF_Gelb",
    "TF_Rot"
]

DISCORDANT_STARS_FACTIONS = []

FACTION_CANONICAL = {
    "arborec": "Arborec",
    "argent": "Argent",
    "barony": "Barony",
    "bastion": "Bastion",
    "cabal": "Cabal",
    "creuss": "Creuss",
    "crimson": "Crimson",
    "dws": "DWS",
    "empyrean": "Empyrean",
    "hacan": "Hacan",
    "jol nar": "Jol Nar",
    "jolnar": "Jol Nar",
    "keleres": "Keleres",
    "l1": "L1",
    "letnev": "Barony",
    "mahact": "Mahact",
    "mentak": "Mentak",
    "muaat": "Muaat",
    "naalu": "Naalu",
    "naaz": "Naaz",
    "nekro": "Nekro",
    "nomad": "Nomad",
    "obsidian": "Obsidian",
    "ralnel": "Ralnel",
    "saar": "Saar",
    "sardakk": "Sardakk",
    "sol": "Sol",
    "titans": "Titans",
    "winnu": "Winnu",
    "xxcha": "Xxcha",
    "yin": "Yin",
    "yssaril": "Yssaril",
    "tf_orange": "TF_Orange",
    "tf_grün": "TF_Grün",
    "tf_lila": "TF_Lila",
    "tf_gelb": "TF_Gelb",
    "tf_rot": "TF_Rot"
}

STANDARD_FACTIONS_ALL = (
    STANDARD_FACTIONS_A_M
    + STANDARD_FACTIONS_N_Z
    + TWILIGHTS_FALL_FACTIONS
    + DISCORDANT_STARS_FACTIONS
)

KNOWN_FACTIONS = set(FACTION_CANONICAL.keys())

PLAYER_COLUMN_CANDIDATES = [
    "Spieler (VP, Volk)",
    "Spieler (Volk, VP)"
]

_player_name_cache = {
    "timestamp": 0,
    "names": []
}

_faction_name_cache = {
    "timestamp": 0,
    "names": []
}


def normalize_name(name: str) -> str:
    return str(name).strip().lower()


def clean_text(value: str) -> str:
    return str(value).strip()


def canonical_faction(faction: str) -> str:
    faction = clean_text(faction)

    if not faction:
        return "Unbekannt"

    key = faction.lower()

    return FACTION_CANONICAL.get(key, faction)


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


def format_number_for_sheet(value):
    if value is None:
        return ""

    if float(value).is_integer():
        return str(int(value))

    return str(value).replace(".", ",")


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
    if not raw:
        return []

    raw = str(raw).strip()

    matches = re.findall(
        r"\d+\.\s*(.*?)(?=,\s*\d+\.\s*|$)",
        raw
    )

    return [m.strip() for m in matches if m.strip()]


def parse_player_entry(entry: str):
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

    if not faction:
        faction = "Unbekannt"

    if (
        normalize_name(name) in KNOWN_FACTIONS
        and normalize_name(faction) not in KNOWN_FACTIONS
        and faction != "Unbekannt"
    ):
        name, faction = faction, name

    faction = canonical_faction(faction)

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


def get_botdata_sheet(create=False):
    try:
        botdata = spreadsheet.worksheet(BOTDATA_SHEET_NAME)
    except WorksheetNotFound:
        if not create:
            return None

        botdata = spreadsheet.add_worksheet(
            title=BOTDATA_SHEET_NAME,
            rows=500,
            cols=3
        )

    botdata.update(
        "A1:C1",
        [["PlayerName", "FactionName", "FactionCategory"]]
    )

    return botdata


def get_botdata_players():
    botdata = get_botdata_sheet(create=False)

    if botdata is None:
        return []

    values = botdata.col_values(1)

    return [
        value.strip()
        for value in values[1:]
        if value.strip()
    ]


def get_botdata_faction_records():
    botdata = get_botdata_sheet(create=False)

    if botdata is None:
        return []

    rows = botdata.get_all_records()
    result = []

    for row in rows:
        faction_name = clean_text(row.get("FactionName", ""))

        if not faction_name:
            continue

        category = clean_text(row.get("FactionCategory", ""))

        if not category:
            category = FACTION_CATEGORY_DISCORDANT_STARS

        result.append({
            "name": canonical_faction(faction_name),
            "category": category
        })

    return result


def add_botdata_player(name: str):
    name = clean_text(name)

    if not name:
        return False, "Leerer Spielername."

    existing = get_all_player_names_cached(force_refresh=True)

    if normalize_name(name) in [normalize_name(p) for p in existing]:
        return False, f"**{name}** existiert bereits."

    botdata = get_botdata_sheet(create=True)
    botdata.append_row([name, "", ""], value_input_option="USER_ENTERED")

    _player_name_cache["timestamp"] = 0

    return True, f"Spieler **{name}** wurde hinzugefügt."


def add_botdata_faction(name: str, category: str):
    name = canonical_faction(name)

    if not name:
        return False, "Leerer Völkername."

    existing = get_all_faction_names_cached(force_refresh=True)

    if normalize_name(name) in [normalize_name(f) for f in existing]:
        return False, f"Volk **{name}** existiert bereits."

    botdata = get_botdata_sheet(create=True)
    botdata.append_row(["", name, category], value_input_option="USER_ENTERED")

    _faction_name_cache["timestamp"] = 0

    return True, f"Volk **{name}** wurde hinzugefügt."


def get_all_player_names_cached(force_refresh=False):
    now = time.time()

    if (
        not force_refresh
        and now - _player_name_cache["timestamp"] < 300
        and _player_name_cache["names"]
    ):
        return _player_name_cache["names"]

    rows = get_rows()
    names = set()

    for saved_name in get_botdata_players():
        names.add(saved_name)

    for row in rows:
        winner = row.get("Gewinner")
        if winner and str(winner).strip():
            names.add(str(winner).strip())

        for community_name in split_community_names(row.get("Community Preis")):
            names.add(community_name)

        for player in parse_game_players(get_player_column(row)):
            if player["name"]:
                names.add(player["name"])

    sorted_names = sorted(names, key=lambda x: x.lower())

    _player_name_cache["timestamp"] = now
    _player_name_cache["names"] = sorted_names

    return sorted_names


def get_all_faction_names_cached(force_refresh=False):
    now = time.time()

    if (
        not force_refresh
        and now - _faction_name_cache["timestamp"] < 300
        and _faction_name_cache["names"]
    ):
        return _faction_name_cache["names"]

    rows = get_rows()
    factions = set(STANDARD_FACTIONS_ALL)

    for record in get_botdata_faction_records():
        factions.add(canonical_faction(record["name"]))

    for row in rows:
        for player in parse_game_players(get_player_column(row)):
            faction = player.get("faction")

            if faction and faction != "Unbekannt":
                factions.add(canonical_faction(faction))

    sorted_factions = sorted(factions, key=lambda x: x.lower())

    _faction_name_cache["timestamp"] = now
    _faction_name_cache["names"] = sorted_factions

    return sorted_factions


def get_factions_for_category(category: str):
    if category == FACTION_CATEGORY_STANDARD_N_Z:
        base_factions = STANDARD_FACTIONS_N_Z
    elif category == FACTION_CATEGORY_TWILIGHTS_FALL:
        base_factions = TWILIGHTS_FALL_FACTIONS
    elif category == FACTION_CATEGORY_DISCORDANT_STARS:
        base_factions = DISCORDANT_STARS_FACTIONS
    else:
        base_factions = STANDARD_FACTIONS_A_M

    result = []
    seen = set()

    for faction in base_factions:
        faction = canonical_faction(faction)
        result.append(faction)
        seen.add(normalize_name(faction))

    for record in get_botdata_faction_records():
        if record["category"] != category:
            continue

        faction = canonical_faction(record["name"])
        key = normalize_name(faction)

        if key not in seen:
            result.append(faction)
            seen.add(key)

    return result


async def player_name_autocomplete(
    interaction: discord.Interaction,
    current: str
):
    names = get_all_player_names_cached()
    current_lower = current.lower()

    if current_lower:
        filtered = [
            name for name in names
            if current_lower in name.lower()
        ]
    else:
        filtered = names

    return [
        app_commands.Choice(name=name, value=name)
        for name in filtered[:25]
    ]


def get_target_points(row, players):
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


def format_winrate(wins: int, games: int):
    if games == 0:
        return "0.0%"
    return f"{(wins / games) * 100:.1f}%"


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

        if winner_name == search_name:
            wins += 1

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
# 🪐 FACTION STATS
# =========================================================
def get_faction_stats():
    rows = get_rows()

    faction_stats = {}

    for row in rows:
        players = parse_game_players(get_player_column(row))

        if not players:
            continue

        winner_name = normalize_name(row.get("Gewinner", ""))

        for player in players:
            faction = player["faction"] or "Unbekannt"
            player_name = player["name"]

            if faction not in faction_stats:
                faction_stats[faction] = {
                    "games": 0,
                    "wins": 0,
                    "players": Counter()
                }

            faction_stats[faction]["games"] += 1
            faction_stats[faction]["players"][player_name] += 1

            if winner_name and normalize_name(player_name) == winner_name:
                faction_stats[faction]["wins"] += 1

    result = []

    for faction, stats in faction_stats.items():
        games = stats["games"]
        wins = stats["wins"]
        winrate = (wins / games * 100) if games else 0

        top_count = 0
        top_players = []

        if stats["players"]:
            top_count = max(stats["players"].values())
            top_players = [
                player
                for player, count in stats["players"].items()
                if count == top_count
            ]

        result.append({
            "faction": faction,
            "games": games,
            "wins": wins,
            "winrate": winrate,
            "top_players": sorted(top_players),
            "top_count": top_count
        })

    result.sort(
        key=lambda x: (
            x["games"],
            x["winrate"],
            x["faction"].lower()
        ),
        reverse=True
    )

    return result


def build_faction_table(stats):
    header = f"{'Volk':<16} {'Spiele':>6} {'Winrate':>8}  Top-Spieler"
    divider = "-" * len(header)

    lines = [header, divider]

    for row in stats:
        faction = row["faction"]
        games = row["games"]
        winrate = f"{row['winrate']:.1f}%"

        top_players = ", ".join(row["top_players"])

        if len(top_players) > 24:
            top_players = top_players[:21] + "..."

        if row["top_count"] >= 2 and top_players:
            top_text = f"{top_players} ({row['top_count']}x)"
        else:
            top_text = "-"

        lines.append(
            f"{faction:<16} {games:>6} {winrate:>8}  {top_text}"
        )

    return "```text\n" + "\n".join(lines) + "\n```"


# =========================================================
# 📝 SIEGTABELLE ADD GAME STATE / HELPERS
# =========================================================
@dataclass
class AddGameState:
    owner_id: int
    datum: str = ""
    punkte: str = ""
    erweiterung: str = ""
    modifikation: str = ""
    kommentare: str = ""
    async_value: str = ""
    participants: list = field(default_factory=list)
    winner: str = ""
    winner_selected: bool = False
    community_awards: list = field(default_factory=list)
    player_details: dict = field(default_factory=dict)
    faction_categories: dict = field(default_factory=dict)


def ensure_player_detail(state: AddGameState, player_name: str):
    if player_name not in state.player_details:
        state.player_details[player_name] = {
            "vp": None,
            "vp_selected": False,
            "faction": ""
        }

    return state.player_details[player_name]


def build_player_detail_content(state: AddGameState, index: int):
    player_name = state.participants[index]
    detail = ensure_player_detail(state, player_name)

    if detail["vp_selected"]:
        vp_text = "unbekannt" if detail["vp"] is None else format_number_for_sheet(detail["vp"])
    else:
        vp_text = "nicht gewählt"

    faction_text = detail["faction"] if detail["faction"] else "nicht gewählt"
    category = state.faction_categories.get(player_name, FACTION_CATEGORY_STANDARD_A_M)
    category_text = FACTION_CATEGORY_LABELS.get(category, "Standard A-M")

    return (
        f"Schritt 4: VP und Volk auswählen\n\n"
        f"Spieler **{index + 1}/{len(state.participants)}**: **{player_name}**\n"
        f"VP: **{vp_text}**\n"
        f"Kategorie: **{category_text}**\n"
        f"Volk: **{faction_text}**"
    )


def build_player_cell_from_state(state: AddGameState):
    rows = []

    for index, player_name in enumerate(state.participants):
        detail = state.player_details.get(player_name, {})
        rows.append({
            "name": player_name,
            "vp": detail.get("vp"),
            "faction": detail.get("faction", "Unbekannt"),
            "original_index": index
        })

    has_any_vp = any(row["vp"] is not None for row in rows)

    if has_any_vp:
        rows.sort(
            key=lambda row: (
                row["vp"] is None,
                -(row["vp"] if row["vp"] is not None else -999),
                row["original_index"]
            )
        )
    else:
        rows.sort(key=lambda row: row["original_index"])

    entries = []
    last_vp = object()
    rank = 0
    position = 0

    for row in rows:
        position += 1
        current_vp = row["vp"]

        if current_vp is None:
            rank = position
        elif current_vp != last_vp:
            rank = position

        last_vp = current_vp

        vp_text = format_number_for_sheet(current_vp)
        entries.append(
            f"{rank}. {row['name']} ({vp_text}, {row['faction']})"
        )

    return ", ".join(entries)


def build_preview_embed(state: AddGameState):
    player_cell = build_player_cell_from_state(state)

    winner_text = state.winner if state.winner else "Kein Gewinner / abgebrochen"
    community_text = ", ".join(state.community_awards) if state.community_awards else "-"

    embed = discord.Embed(
        title="Vorschau: Neues Spiel",
        color=0x2ECC71
    )

    embed.add_field(
        name="Grunddaten",
        value=(
            f"Datum: **{state.datum}**\n"
            f"Punkte: **{state.punkte}**\n"
            f"Erweiterung: **{state.erweiterung}**\n"
            f"Modifikation: **{state.modifikation}**\n"
            f"ASYNC: **{state.async_value}**"
        ),
        inline=False
    )

    embed.add_field(
        name="Ergebnis",
        value=(
            f"Gewinner: **{winner_text}**\n"
            f"Community Preis: **{community_text}**"
        ),
        inline=False
    )

    embed.add_field(
        name="Spieler",
        value=player_cell if player_cell else "-",
        inline=False
    )

    if state.kommentare:
        embed.add_field(
            name="Kommentare",
            value=state.kommentare,
            inline=False
        )

    return embed


def append_game_to_sheet(state: AddGameState):
    player_cell = build_player_cell_from_state(state)
    community_cell = ", ".join(state.community_awards)
    winner_cell = state.winner if state.winner else ""

    row_data = {
        "Datum": state.datum,
        "Punkte": state.punkte,
        "Erweiterung": state.erweiterung,
        "Modifikation": state.modifikation,
        "Gewinner": winner_cell,
        "Spieler (VP, Volk)": player_cell,
        "Spieler (Volk, VP)": player_cell,
        "Community Preis": community_cell,
        "ASYNC": state.async_value,
        "Kommentare": state.kommentare
    }

    headers = sheet.row_values(1)

    row = [
        row_data.get(header, "")
        for header in headers
    ]

    sheet.append_row(row, value_input_option="USER_ENTERED")

    _player_name_cache["timestamp"] = 0
    _faction_name_cache["timestamp"] = 0


# =========================================================
# 📝 SIEGTABELLE UI
# =========================================================
class OwnerOnlyView(discord.ui.View):
    def __init__(self, state: AddGameState, timeout=300):
        super().__init__(timeout=timeout)
        self.state = state

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.state.owner_id:
            await interaction.response.send_message(
                "Nur die Person, die den Wizard gestartet hat, kann diese Auswahl benutzen.",
                ephemeral=True
            )
            return False

        return True


class BasicGameModal(discord.ui.Modal, title="Neues Spiel - Grunddaten"):
    datum = discord.ui.TextInput(
        label="Datum",
        placeholder="z.B. 14.06.2026",
        required=True,
        max_length=20
    )

    punkte = discord.ui.TextInput(
        label="Punkte",
        placeholder="z.B. 10, 12 oder 14",
        required=True,
        max_length=10
    )

    erweiterung = discord.ui.TextInput(
        label="Erweiterung",
        placeholder="z.B. Basis, PoK, PoK + TE",
        required=True,
        max_length=50
    )

    modifikation = discord.ui.TextInput(
        label="Modifikation",
        placeholder="z.B. Nein, Hidden Agenda, Total War",
        required=True,
        max_length=100
    )

    kommentare = discord.ui.TextInput(
        label="Kommentare",
        placeholder="Optional",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=500
    )

    def __init__(self, state: AddGameState):
        super().__init__()
        self.state = state

    async def on_submit(self, interaction: discord.Interaction):
        self.state.datum = str(self.datum.value).strip()
        self.state.punkte = str(self.punkte.value).strip()
        self.state.erweiterung = str(self.erweiterung.value).strip()
        self.state.modifikation = str(self.modifikation.value).strip()
        self.state.kommentare = str(self.kommentare.value).strip()

        player_names = get_all_player_names_cached()
        view = PlayerAsyncSelectionView(self.state, player_names)

        await interaction.response.send_message(
            "Schritt 2: Wähle ASYNC und bis zu 8 Spieler aus. Falls ein Name fehlt, wähle 'Neuen Spieler eintragen'.",
            view=view,
            ephemeral=True
        )


class AsyncSelect(discord.ui.Select):
    def __init__(self, state: AddGameState):
        self.state = state

        options = [
            discord.SelectOption(
                label="Nein",
                value="n",
                default=state.async_value == "n"
            ),
            discord.SelectOption(
                label="Ja",
                value="y",
                default=state.async_value == "y"
            )
        ]

        super().__init__(
            placeholder="ASYNC auswählen",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        self.state.async_value = self.values[0]
        await interaction.response.defer()


class ParticipantSelect(discord.ui.Select):
    def __init__(self, state: AddGameState, player_names):
        self.state = state

        visible_names = []
        seen = set()

        for name in state.participants:
            key = normalize_name(name)
            if key not in seen:
                visible_names.append(name)
                seen.add(key)

        for name in player_names:
            key = normalize_name(name)
            if key not in seen:
                visible_names.append(name)
                seen.add(key)
            if len(visible_names) >= 24:
                break

        options = [
            discord.SelectOption(
                label=name,
                value=name,
                default=name in state.participants
            )
            for name in visible_names
        ]

        options.append(
            discord.SelectOption(
                label="Neuen Spieler eintragen",
                value="__add_player__"
            )
        )

        super().__init__(
            placeholder="Spieler auswählen, maximal 8",
            min_values=1,
            max_values=min(8, len(options)),
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        selected_players = [
            value for value in self.values
            if value != "__add_player__"
        ]

        self.state.participants = selected_players

        if "__add_player__" in self.values:
            await interaction.response.send_modal(CustomPlayerModal(self.state))
            return

        await interaction.response.defer()


class CustomPlayerModal(discord.ui.Modal, title="Neuen Spieler eintragen"):
    player_name = discord.ui.TextInput(
        label="Spielername",
        placeholder="z.B. Max",
        required=True,
        max_length=50
    )

    def __init__(self, state: AddGameState):
        super().__init__()
        self.state = state

    async def on_submit(self, interaction: discord.Interaction):
        raw_name = str(self.player_name.value).strip()

        if not raw_name:
            await interaction.response.send_message(
                "Leerer Spielername.",
                ephemeral=True
            )
            return

        existing_names = get_all_player_names_cached(force_refresh=True)
        existing_match = next(
            (
                name for name in existing_names
                if normalize_name(name) == normalize_name(raw_name)
            ),
            None
        )

        if existing_match:
            final_name = existing_match
            message = f"Spieler **{final_name}** existiert bereits und wurde ausgewählt."
        else:
            success, message = add_botdata_player(raw_name)
            final_name = raw_name

            if not success and "existiert bereits" not in message:
                await interaction.response.send_message(
                    message,
                    ephemeral=True
                )
                return

        if normalize_name(final_name) not in [normalize_name(p) for p in self.state.participants]:
            if len(self.state.participants) >= 8:
                await interaction.response.send_message(
                    "Es sind bereits 8 Spieler ausgewählt. Entferne erst einen Spieler, bevor du einen neuen hinzufügst.",
                    ephemeral=True
                )
                return

            self.state.participants.append(final_name)

        player_names = get_all_player_names_cached(force_refresh=True)
        view = PlayerAsyncSelectionView(self.state, player_names)

        await interaction.response.send_message(
            f"{message}\n\nSchritt 2: Prüfe ASYNC und Spielerauswahl, dann klicke auf Weiter.",
            view=view,
            ephemeral=True
        )


class PlayerAsyncSelectionView(OwnerOnlyView):
    def __init__(self, state: AddGameState, player_names):
        super().__init__(state)

        self.add_item(AsyncSelect(state))
        self.add_item(ParticipantSelect(state, player_names))

    @discord.ui.button(
        label="Weiter",
        style=discord.ButtonStyle.primary
    )
    async def next_step(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not self.state.async_value:
            await interaction.response.send_message(
                "Bitte ASYNC auswählen.",
                ephemeral=True
            )
            return

        if not self.state.participants:
            await interaction.response.send_message(
                "Bitte mindestens einen Spieler auswählen.",
                ephemeral=True
            )
            return

        view = WinnerCommunitySelectionView(self.state)

        await interaction.response.edit_message(
            content="Schritt 3: Wähle Gewinner und Community Preis.",
            view=view
        )


class WinnerSelect(discord.ui.Select):
    def __init__(self, state: AddGameState):
        self.state = state

        options = [
            discord.SelectOption(
                label="Kein Gewinner / abgebrochen",
                value="__none__",
                default=state.winner_selected and state.winner == ""
            )
        ]

        options.extend([
            discord.SelectOption(
                label=name,
                value=name,
                default=state.winner == name
            )
            for name in state.participants
        ])

        super().__init__(
            placeholder="Gewinner auswählen",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        value = self.values[0]

        if value == "__none__":
            self.state.winner = ""
        else:
            self.state.winner = value

        self.state.winner_selected = True

        await interaction.response.defer()


class CommunitySelect(discord.ui.Select):
    def __init__(self, state: AddGameState):
        self.state = state

        options = [
            discord.SelectOption(
                label="Kein Community Preis",
                value="__none__",
                default=not state.community_awards
            )
        ]

        options.extend([
            discord.SelectOption(
                label=name,
                value=name,
                default=name in state.community_awards
            )
            for name in state.participants
        ])

        super().__init__(
            placeholder="Community Preis auswählen",
            min_values=1,
            max_values=len(options),
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if "__none__" in self.values:
            self.state.community_awards = []
        else:
            self.state.community_awards = list(self.values)

        await interaction.response.defer()


class WinnerCommunitySelectionView(OwnerOnlyView):
    def __init__(self, state: AddGameState):
        super().__init__(state)

        self.add_item(WinnerSelect(state))
        self.add_item(CommunitySelect(state))

    @discord.ui.button(
        label="Weiter zu VP & Völkern",
        style=discord.ButtonStyle.primary
    )
    async def next_step(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not self.state.winner_selected:
            await interaction.response.send_message(
                "Bitte einen Gewinner oder 'Kein Gewinner / abgebrochen' auswählen.",
                ephemeral=True
            )
            return

        view = PlayerDetailView(self.state, index=0)

        await interaction.response.edit_message(
            content=build_player_detail_content(self.state, 0),
            view=view
        )


class VPSelect(discord.ui.Select):
    def __init__(self, state: AddGameState, index: int):
        self.state = state
        self.index = index

        player_name = state.participants[index]
        detail = ensure_player_detail(state, player_name)

        options = [
            discord.SelectOption(
                label="Unbekannt / leer",
                value="__none__",
                default=detail["vp_selected"] and detail["vp"] is None
            )
        ]

        for value in range(0, 15):
            options.append(
                discord.SelectOption(
                    label=str(value),
                    value=str(value),
                    default=detail["vp_selected"] and detail["vp"] == float(value)
                )
            )

        super().__init__(
            placeholder="VP auswählen",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        player_name = self.state.participants[self.index]
        detail = ensure_player_detail(self.state, player_name)

        value = self.values[0]

        if value == "__none__":
            detail["vp"] = None
        else:
            detail["vp"] = float(value)

        detail["vp_selected"] = True

        await interaction.response.edit_message(
            content=build_player_detail_content(self.state, self.index),
            view=PlayerDetailView(self.state, self.index)
        )


class FactionCategorySelect(discord.ui.Select):
    def __init__(self, state: AddGameState, index: int):
        self.state = state
        self.index = index

        player_name = state.participants[index]
        current_category = state.faction_categories.get(
            player_name,
            FACTION_CATEGORY_STANDARD_A_M
        )

        options = [
            discord.SelectOption(
                label="Standard A-M",
                value=FACTION_CATEGORY_STANDARD_A_M,
                default=current_category == FACTION_CATEGORY_STANDARD_A_M
            ),
            discord.SelectOption(
                label="Standard N-Z",
                value=FACTION_CATEGORY_STANDARD_N_Z,
                default=current_category == FACTION_CATEGORY_STANDARD_N_Z
            ),
            discord.SelectOption(
                label="Twilights Fall",
                value=FACTION_CATEGORY_TWILIGHTS_FALL,
                default=current_category == FACTION_CATEGORY_TWILIGHTS_FALL
            ),
            discord.SelectOption(
                label="Discordant Stars",
                value=FACTION_CATEGORY_DISCORDANT_STARS,
                default=current_category == FACTION_CATEGORY_DISCORDANT_STARS
            )
        ]

        super().__init__(
            placeholder="Völker-Kategorie auswählen",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        player_name = self.state.participants[self.index]
        self.state.faction_categories[player_name] = self.values[0]

        await interaction.response.edit_message(
            content=build_player_detail_content(self.state, self.index),
            view=PlayerDetailView(self.state, self.index)
        )


class FactionSelect(discord.ui.Select):
    def __init__(self, state: AddGameState, index: int):
        self.state = state
        self.index = index

        player_name = state.participants[index]
        detail = ensure_player_detail(state, player_name)

        category = state.faction_categories.get(
            player_name,
            FACTION_CATEGORY_STANDARD_A_M
        )

        faction_names = get_factions_for_category(category)
        visible_factions = faction_names[:24]

        options = []

        for faction in visible_factions:
            options.append(
                discord.SelectOption(
                    label=faction,
                    value=faction,
                    default=detail["faction"] == faction
                )
            )

        options.append(
            discord.SelectOption(
                label="Neues Volk eintragen",
                value="__custom__"
            )
        )

        super().__init__(
            placeholder="Volk auswählen",
            min_values=1,
            max_values=1,
            options=options[:25]
        )

    async def callback(self, interaction: discord.Interaction):
        value = self.values[0]

        if value == "__custom__":
            await interaction.response.send_modal(
                CustomFactionModal(self.state, self.index)
            )
            return

        player_name = self.state.participants[self.index]
        detail = ensure_player_detail(self.state, player_name)

        detail["faction"] = canonical_faction(value)

        await interaction.response.edit_message(
            content=build_player_detail_content(self.state, self.index),
            view=PlayerDetailView(self.state, self.index)
        )


class CustomFactionModal(discord.ui.Modal, title="Neues Volk eintragen"):
    faction_name = discord.ui.TextInput(
        label="Name des Volks",
        placeholder="z.B. Discordant Stars Volk",
        required=True,
        max_length=50
    )

    def __init__(self, state: AddGameState, index: int):
        super().__init__()
        self.state = state
        self.index = index

    async def on_submit(self, interaction: discord.Interaction):
        faction_name = canonical_faction(str(self.faction_name.value).strip())

        if not faction_name or faction_name == "Unbekannt":
            await interaction.response.send_message(
                "Leerer Völkername.",
                ephemeral=True
            )
            return

        player_name = self.state.participants[self.index]
        category = self.state.faction_categories.get(
            player_name,
            FACTION_CATEGORY_STANDARD_A_M
        )
        detail = ensure_player_detail(self.state, player_name)

        detail["faction"] = faction_name

        add_botdata_faction(faction_name, category)

        await interaction.response.send_message(
            content=(
                f"Volk **{faction_name}** wurde für **{player_name}** gesetzt.\n\n"
                f"{build_player_detail_content(self.state, self.index)}"
            ),
            view=PlayerDetailView(self.state, self.index),
            ephemeral=True
        )


class PlayerDetailView(OwnerOnlyView):
    def __init__(self, state: AddGameState, index: int):
        super().__init__(state)
        self.index = index

        self.add_item(VPSelect(state, index))
        self.add_item(FactionCategorySelect(state, index))
        self.add_item(FactionSelect(state, index))

    @discord.ui.button(
        label="Zurück",
        style=discord.ButtonStyle.secondary
    )
    async def previous_player(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if self.index == 0:
            await interaction.response.send_message(
                "Du bist bereits beim ersten Spieler.",
                ephemeral=True
            )
            return

        new_index = self.index - 1

        await interaction.response.edit_message(
            content=build_player_detail_content(self.state, new_index),
            view=PlayerDetailView(self.state, new_index)
        )

    @discord.ui.button(
        label="Weiter",
        style=discord.ButtonStyle.primary
    )
    async def next_player(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        player_name = self.state.participants[self.index]
        detail = ensure_player_detail(self.state, player_name)

        if not detail["vp_selected"]:
            await interaction.response.send_message(
                "Bitte VP auswählen. Wenn VP unbekannt sind, wähle 'Unbekannt / leer'.",
                ephemeral=True
            )
            return

        if not detail["faction"]:
            await interaction.response.send_message(
                "Bitte ein Volk auswählen.",
                ephemeral=True
            )
            return

        next_index = self.index + 1

        if next_index < len(self.state.participants):
            await interaction.response.edit_message(
                content=build_player_detail_content(self.state, next_index),
                view=PlayerDetailView(self.state, next_index)
            )
            return

        embed = build_preview_embed(self.state)
        view = ConfirmGameView(self.state)

        await interaction.response.edit_message(
            content="Schritt 5: Bitte prüfe die Vorschau.",
            embed=embed,
            view=view
        )


class ConfirmGameView(OwnerOnlyView):
    def __init__(self, state: AddGameState):
        super().__init__(state)

    @discord.ui.button(
        label="In Sheet eintragen",
        style=discord.ButtonStyle.success
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.defer(ephemeral=True)

        try:
            append_game_to_sheet(self.state)
        except Exception as e:
            await interaction.followup.send(
                f"Fehler beim Schreiben ins Google Sheet:\n```text\n{e}\n```",
                ephemeral=True
            )
            return

        embed = build_preview_embed(self.state)
        embed.title = "Spiel wurde eingetragen"
        embed.color = 0x2ECC71

        await interaction.edit_original_response(
            content="Das Spiel wurde erfolgreich in die Siegtabelle eingetragen.",
            embed=embed,
            view=None
        )

    @discord.ui.button(
        label="Abbrechen",
        style=discord.ButtonStyle.danger
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.edit_message(
            content="Vorgang abgebrochen. Es wurde nichts ins Sheet geschrieben.",
            embed=None,
            view=None
        )


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

    text = ""

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
        title="🏆 Hall of Fame",
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

    text = ""

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
        title="❤️ Sieger der Herzen",
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
@app_commands.autocomplete(name=player_name_autocomplete)
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
        avg_normalized_text = f"{stats['avg_normalized_vp']:.2f} VP"

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
# 🪐 /statistics factions
# =========================================================
@statistics.command(
    name="factions",
    description="Zeigt Statistiken zu allen Völkern"
)
async def factions(interaction: discord.Interaction):
    await interaction.response.defer()

    stats = get_faction_stats()

    table = build_faction_table(stats)

    embed = discord.Embed(
        title="Fraktionsstatistiken",
        description=table,
        color=0x9B59B6
    )

    embed.set_footer(
        text="Sortiert nach Anzahl der Spiele. Winrate = Siege / Spiele."
    )

    await interaction.followup.send(embed=embed)


# =========================================================
# 📝 /siegtabelle add_game
# =========================================================
@siegtabelle.command(
    name="add_game",
    description="Fügt ein neues Spiel zur Siegtabelle hinzu"
)
async def add_game(interaction: discord.Interaction):
    state = AddGameState(owner_id=interaction.user.id)

    await interaction.response.send_modal(
        BasicGameModal(state)
    )


# =========================================================
# 🚀 BOT START
# =========================================================
@client.event
async def on_ready():
    await tree.sync()
    print(f"Bot läuft als {client.user}")


client.run(TOKEN)