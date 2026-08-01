import discord
from discord import app_commands
from discord.ext import tasks
import gspread
from gspread.exceptions import WorksheetNotFound
from gspread.utils import rowcol_to_a1
from google.oauth2.service_account import Credentials
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import os
import json
import re
import time
import uuid

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
SESSIONS_SHEET_NAME = "Sessions"
BOT_BUILD = "sessions-chronological-sheet-v10"

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

session = app_commands.Group(
    name="session",
    description="Spieltermine und Erinnerungen verwalten"
)

tree.add_command(statistics)
tree.add_command(siegtabelle)
tree.add_command(session)

# =========================================================
# 🧠 CONSTANTS / HELPERS
# =========================================================
BOTDATA_HEADERS = [
    "PlayerName",
    "FactionName",
    "FactionCategory",
    "PointsValue",
    "ExpansionValue",
    "ModificationValue"
]

BOTDATA_COL_PLAYER = 1
BOTDATA_COL_FACTION = 2
BOTDATA_COL_FACTION_CATEGORY = 3
BOTDATA_COL_POINTS = 4
BOTDATA_COL_EXPANSION = 5
BOTDATA_COL_MODIFICATION = 6

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

DEFAULT_POINTS = [
    "10",
    "12",
    "14"
]

DEFAULT_EXPANSIONS = [
    "Basis",
    "PoK",
    "TE"
]

DEFAULT_MODIFICATIONS = [
    "Standard",
    "Hidden Agenda",
    "Twilights Fall",
    "Absols Agendas",
    "Minor Factions",
    "Cosmic Phenomenae",
    "4/4/4",
    "Total War"
]

PLAYER_COLUMN_CANDIDATES = [
    "Spieler (VP, Volk)",
    "Spieler (Volk, VP)"
]

PLAYER_RENAME_MAP = {
    "chris": "Chris S."
}

EXCLUDED_PLAYER_NAMES = {
    "ben",
    "carmelo",
    "randy",
    "simone",
    "julian"
}

MAX_PLAYERS_PER_GAME = 8
MAX_EXTERNAL_PLAYERS = 7
EXTERNAL_PLAYER_BASE_NAME = "Externer Spieler"

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


def canonical_player_name(name: str) -> str:
    name = clean_text(name)

    if not name:
        return ""

    key = normalize_name(name)

    if key in PLAYER_RENAME_MAP:
        return PLAYER_RENAME_MAP[key]

    if key in EXCLUDED_PLAYER_NAMES:
        return EXTERNAL_PLAYER_BASE_NAME

    return name


def normalize_player_name(name: str) -> str:
    return normalize_name(canonical_player_name(name))


def is_external_player_name(name: str) -> bool:
    return normalize_player_name(name).startswith(normalize_name(EXTERNAL_PLAYER_BASE_NAME))


def is_excluded_from_player_dropdown(name: str) -> bool:
    canonical = canonical_player_name(name)

    if not canonical:
        return True

    if normalize_name(canonical) in EXCLUDED_PLAYER_NAMES:
        return True

    if is_external_player_name(canonical):
        return True

    return False


def unique_preserve_order(values):
    result = []
    seen = set()

    for value in values:
        value = clean_text(value)

        if not value:
            continue

        key = normalize_name(value)

        if key not in seen:
            result.append(value)
            seen.add(key)

    return result


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


def normalize_date_input(value: str):
    text = clean_text(value)

    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%d.%m.%Y")
        except ValueError:
            pass

    return None


def parse_date_for_sort(value: str):
    normalized = normalize_date_input(value)

    if not normalized:
        return None

    try:
        return datetime.strptime(normalized, "%d.%m.%Y")
    except ValueError:
        return None


def get_rows():
    return sheet.get_all_records()


def get_player_column(row):
    for column_name in PLAYER_COLUMN_CANDIDATES:
        if column_name in row and row.get(column_name):
            return row.get(column_name)
    return ""


def split_multi_value_cell(value: str):
    value = clean_text(value)

    if not value:
        return []

    if normalize_name(value) == "nein":
        return []

    if normalize_name(value) == "absols agendas, minor factions":
        return ["Absols Agendas", "Minor Factions"]

    parts = [part.strip() for part in value.split("+")]

    return [part for part in parts if part]


def get_unique_sheet_column_values(column_name, split_multi=False):
    values = []

    for row in get_rows():
        value = clean_text(row.get(column_name, ""))

        if not value:
            continue

        if split_multi:
            values.extend(split_multi_value_cell(value))
        else:
            values.append(value)

    return unique_preserve_order(values)


def split_player_names_cell(entry: str):
    if not entry:
        return []

    names = []

    for name in str(entry).split(","):
        canonical = canonical_player_name(name.strip())

        if canonical:
            names.append(canonical)

    return unique_preserve_order(names)


def split_winner_names(entry: str):
    return split_player_names_cell(entry)


def split_community_names(entry: str):
    return split_player_names_cell(entry)


def is_countable_statistics_player(name: str) -> bool:
    canonical = canonical_player_name(name)

    if not canonical:
        return False

    if is_external_player_name(canonical):
        return False

    return True


def normalize_expansion_values(values):
    raw_values = []

    for value in values or []:
        for part in split_multi_value_cell(value):
            raw_values.append(part)

    raw_values = unique_preserve_order(raw_values)
    keys = {normalize_name(value) for value in raw_values}

    result = []

    for value in raw_values:
        key = normalize_name(value)

        if key in {"te", "pok"}:
            continue

        result.append(value)

    if "te" in keys:
        result.extend(["PoK", "TE"])
    elif "pok" in keys:
        result.append("PoK")

    return unique_preserve_order(result)


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

    name = canonical_player_name(name)
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
            cols=6
        )

    botdata.update(
        values=[BOTDATA_HEADERS],
        range_name="A1:F1"
    )

    return botdata


def get_botdata_column_values(column_index):
    botdata = get_botdata_sheet(create=False)

    if botdata is None:
        return []

    values = botdata.col_values(column_index)

    return [
        value.strip()
        for value in values[1:]
        if value.strip()
    ]


def get_botdata_players():
    return get_botdata_column_values(BOTDATA_COL_PLAYER)


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
    name = canonical_player_name(name)

    if not name:
        return False, "Leerer Spielername."

    existing = get_all_player_names_cached(force_refresh=True)

    if normalize_player_name(name) in [normalize_player_name(p) for p in existing]:
        return False, f"**{name}** existiert bereits."

    botdata = get_botdata_sheet(create=True)
    botdata.append_row([name, "", "", "", "", ""], value_input_option="USER_ENTERED")

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
    botdata.append_row(["", name, category, "", "", ""], value_input_option="USER_ENTERED")

    _faction_name_cache["timestamp"] = 0

    return True, f"Volk **{name}** wurde hinzugefügt."


def add_botdata_setting(column_index: int, value: str):
    value = clean_text(value)

    if not value:
        return False, "Leerer Eintrag."

    botdata = get_botdata_sheet(create=True)

    existing = get_botdata_column_values(column_index)

    if normalize_name(value) in [normalize_name(v) for v in existing]:
        return False, f"**{value}** existiert bereits."

    row = ["", "", "", "", "", ""]
    row[column_index - 1] = value

    botdata.append_row(row, value_input_option="USER_ENTERED")

    return True, f"**{value}** wurde hinzugefügt."


def add_botdata_points(value: str):
    number = parse_number(value)

    if number is None:
        return False, "Punkte müssen eine Zahl sein."

    value = format_number_for_sheet(number)

    existing = get_points_options()

    if normalize_name(value) in [normalize_name(v) for v in existing]:
        return False, f"**{value}** existiert bereits."

    return add_botdata_setting(BOTDATA_COL_POINTS, value)


def add_botdata_expansion(value: str):
    existing = get_expansion_options()

    if normalize_name(value) in [normalize_name(v) for v in existing]:
        return False, f"**{value}** existiert bereits."

    return add_botdata_setting(BOTDATA_COL_EXPANSION, value)


def add_botdata_modification(value: str):
    existing = get_modification_options()

    if normalize_name(value) in [normalize_name(v) for v in existing]:
        return False, f"**{value}** existiert bereits."

    return add_botdata_setting(BOTDATA_COL_MODIFICATION, value)


def get_points_options():
    return unique_preserve_order(
        DEFAULT_POINTS
        + get_unique_sheet_column_values("Punkte")
        + get_botdata_column_values(BOTDATA_COL_POINTS)
    )


def get_expansion_options():
    return normalize_expansion_values(
        DEFAULT_EXPANSIONS
        + get_unique_sheet_column_values("Erweiterung", split_multi=True)
        + get_botdata_column_values(BOTDATA_COL_EXPANSION)
    )


def get_modification_options():
    values = unique_preserve_order(
        ["Standard"]
        + DEFAULT_MODIFICATIONS
        + get_unique_sheet_column_values("Modifikation", split_multi=True)
        + get_botdata_column_values(BOTDATA_COL_MODIFICATION)
    )

    filtered = [
        value for value in values
        if normalize_name(value) not in {
            "nein",
            "absols agendas, minor factions"
        }
    ]

    standard = next(
        (value for value in filtered if normalize_name(value) == "standard"),
        "Standard"
    )

    rest = [
        value for value in filtered
        if normalize_name(value) != "standard"
    ]

    return [standard] + rest


def clean_selected_values(values):
    return unique_preserve_order(values)


def format_expansions_for_sheet(state):
    return " + ".join(normalize_expansion_values(state.erweiterungen))


def format_modifications_for_sheet(state):
    if not state.modifikationen:
        return "Standard"

    return " + ".join(clean_selected_values(state.modifikationen))


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
        player_name = canonical_player_name(saved_name)
        if player_name and not is_excluded_from_player_dropdown(player_name):
            names.add(player_name)

    for row in rows:
        for winner in split_winner_names(row.get("Gewinner", "")):
            if winner and not is_excluded_from_player_dropdown(winner):
                names.add(winner)

        for community_name in split_community_names(row.get("Community Preis")):
            if community_name and not is_excluded_from_player_dropdown(community_name):
                names.add(community_name)

        for player in parse_game_players(get_player_column(row)):
            player_name = player["name"]
            if player_name and not is_excluded_from_player_dropdown(player_name):
                names.add(player_name)

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


def build_select_options_with_add_first(values, selected_value, add_label):
    options = [
        discord.SelectOption(
            label=add_label,
            value="__add__"
        )
    ]

    visible_values = []
    seen = set()

    if selected_value:
        visible_values.append(selected_value)
        seen.add(normalize_name(selected_value))

    for value in values:
        key = normalize_name(value)

        if key not in seen:
            visible_values.append(value)
            seen.add(key)

        if len(visible_values) >= 24:
            break

    for value in visible_values:
        options.append(
            discord.SelectOption(
                label=value,
                value=value,
                default=selected_value == value
            )
        )

    return options[:25]


def build_multi_select_options_with_add_first(values, selected_values, add_label):
    selected_values = selected_values or []
    selected_keys = {normalize_name(value) for value in selected_values}

    options = [
        discord.SelectOption(
            label=add_label,
            value="__add__"
        )
    ]

    visible_values = []
    seen = set()

    for value in selected_values:
        key = normalize_name(value)

        if key not in seen:
            visible_values.append(value)
            seen.add(key)

    for value in values:
        key = normalize_name(value)

        if key not in seen:
            visible_values.append(value)
            seen.add(key)

        if len(visible_values) >= 24:
            break

    for value in visible_values:
        options.append(
            discord.SelectOption(
                label=value,
                value=value,
                default=normalize_name(value) in selected_keys
            )
        )

    return options[:25]


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

    winner_names = {
        normalize_player_name(winner)
        for winner in split_winner_names(row.get("Gewinner", ""))
    }

    if winner_names:
        for player in players:
            if normalize_player_name(player["name"]) in winner_names and player["vp"]:
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


def get_next_available_sheet_row():
    all_values = sheet.get_all_values()

    last_non_empty_row = 1

    for index, row in enumerate(all_values, start=1):
        if any(str(cell).strip() for cell in row):
            last_non_empty_row = index

    return max(last_non_empty_row + 1, 2)


def sort_sheet_by_date():
    all_values = sheet.get_all_values()

    if not all_values:
        return

    headers = all_values[0]

    if "Datum" not in headers:
        return

    date_index = headers.index("Datum")
    width = len(headers)

    non_empty_rows = []

    for row in all_values[1:]:
        padded_row = row + [""] * (width - len(row))
        padded_row = padded_row[:width]

        if any(str(cell).strip() for cell in padded_row):
            non_empty_rows.append(padded_row)

    def sort_key(row):
        parsed_date = parse_date_for_sort(row[date_index])

        if parsed_date is None:
            return (1, datetime.max)

        return (0, parsed_date)

    sorted_rows = sorted(non_empty_rows, key=sort_key)

    last_row_to_clear = max(len(all_values), len(sorted_rows) + 1)
    last_col = rowcol_to_a1(1, width).replace("1", "")

    sheet.batch_clear([f"A2:{last_col}{last_row_to_clear}"])

    if sorted_rows:
        end_cell = rowcol_to_a1(len(sorted_rows) + 1, width)
        sheet.update(
            values=sorted_rows,
            range_name=f"A2:{end_cell}",
            value_input_option="USER_ENTERED"
        )


# =========================================================
# 🏆 HALL OF FAME
# =========================================================
def get_halloffame():
    rows = get_rows()

    winners = []

    for row in rows:
        for winner in split_winner_names(row.get("Gewinner")):
            if is_countable_statistics_player(winner):
                winners.append(canonical_player_name(winner))

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
            if is_countable_statistics_player(name):
                players.append(canonical_player_name(name))

    return Counter(players)


# =========================================================
# 👤 PLAYER STATS
# =========================================================
def get_player_stats(name: str):
    rows = get_rows()

    search_name = normalize_player_name(name)

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
            if normalize_player_name(player["name"]) == search_name:
                player_entry = player
                break

        winner_names = {
            normalize_player_name(winner)
            for winner in split_winner_names(row.get("Gewinner", ""))
        }

        player_won = search_name in winner_names

        if player_won:
            wins += 1

        for community_name in split_community_names(row.get("Community Preis")):
            if normalize_player_name(community_name) == search_name:
                community_awards += 1

        if not player_entry:
            continue

        games_played += 1

        faction = player_entry["faction"] or "Unbekannt"
        vp = player_entry["vp"]

        factions_played[faction] += 1

        if player_won:
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

        winner_names = {
            normalize_player_name(winner)
            for winner in split_winner_names(row.get("Gewinner", ""))
        }

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

            if not is_external_player_name(player_name):
                faction_stats[faction]["players"][player_name] += 1

            if winner_names and normalize_player_name(player_name) in winner_names:
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
    faction_width = 14
    header = f"{'Volk':<{faction_width}}{'Spiele':>6} {'Winrate':>8}  Top-Spieler"
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
            f"{faction:<{faction_width}}{games:>6} {winrate:>8}  {top_text}"
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
    erweiterungen: list = field(default_factory=list)
    modifikationen: list = field(default_factory=list)
    kommentare: str = ""
    async_value: str = ""
    participants: list = field(default_factory=list)
    winners: list = field(default_factory=list)
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

    winner_text = ", ".join(state.winners) if state.winners else "Kein Gewinner / abgebrochen"
    community_text = ", ".join(state.community_awards) if state.community_awards else "-"
    expansion_text = format_expansions_for_sheet(state) if state.erweiterungen else "-"
    modification_text = format_modifications_for_sheet(state)

    embed = discord.Embed(
        title="Vorschau: Neues Spiel",
        color=0x2ECC71
    )

    embed.add_field(
        name="Grunddaten",
        value=(
            f"Datum: **{state.datum}**\n"
            f"Punkte: **{state.punkte}**\n"
            f"Erweiterung: **{expansion_text}**\n"
            f"Modifikation: **{modification_text}**\n"
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
    winner_cell = ", ".join(state.winners)
    expansion_cell = format_expansions_for_sheet(state)
    modification_cell = format_modifications_for_sheet(state)

    row_data = {
        "Datum": state.datum,
        "Punkte": state.punkte,
        "Erweiterung": expansion_cell,
        "Modifikation": modification_cell,
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

    next_row = get_next_available_sheet_row()
    end_cell = rowcol_to_a1(next_row, len(headers))

    sheet.update(
        values=[row],
        range_name=f"A{next_row}:{end_cell}",
        value_input_option="USER_ENTERED"
    )

    sort_sheet_by_date()

    _player_name_cache["timestamp"] = 0
    _faction_name_cache["timestamp"] = 0


def add_external_players_to_state(state: AddGameState, count: int):
    current_external_count = sum(
        1 for player_name in state.participants
        if is_external_player_name(player_name)
    )

    remaining_external_slots = MAX_EXTERNAL_PLAYERS - current_external_count
    remaining_player_slots = MAX_PLAYERS_PER_GAME - len(state.participants)
    amount_to_add = min(count, remaining_external_slots, remaining_player_slots)

    if amount_to_add <= 0:
        return 0

    existing_names = {normalize_name(name) for name in state.participants}
    added = 0
    next_number = 1

    while added < amount_to_add and next_number <= MAX_EXTERNAL_PLAYERS:
        if next_number == 1:
            candidate = EXTERNAL_PLAYER_BASE_NAME
        else:
            candidate = f"{EXTERNAL_PLAYER_BASE_NAME} {next_number}"

        if normalize_name(candidate) not in existing_names:
            state.participants.append(candidate)
            existing_names.add(normalize_name(candidate))
            added += 1

        next_number += 1

    return added


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


class BasicGameModal(discord.ui.Modal, title="Neues Spiel - Datum"):
    datum = discord.ui.TextInput(
        label="Datum",
        placeholder="TT.MM.JJJJ, z.B. 14.06.2026",
        required=True,
        max_length=20
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
        normalized_date = normalize_date_input(str(self.datum.value))

        if not normalized_date:
            await interaction.response.send_message(
                "Ungültiges Datum. Bitte nutze das Format `TT.MM.JJJJ`, z.B. `14.06.2026`.",
                ephemeral=True
            )
            return

        self.state.datum = normalized_date
        self.state.kommentare = str(self.kommentare.value).strip()

        view = GameSettingsSelectionView(self.state)

        await interaction.response.send_message(
            "Schritt 1: Wähle Punkte, Erweiterungen und Modifikationen.",
            view=view,
            ephemeral=True
        )


class PointsSelect(discord.ui.Select):
    def __init__(self, state: AddGameState):
        self.state = state

        options = build_select_options_with_add_first(
            get_points_options(),
            state.punkte,
            "Neue Punkte eintragen"
        )

        super().__init__(
            placeholder="Punkte auswählen",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        value = self.values[0]

        if value == "__add__":
            await interaction.response.send_modal(
                CustomSettingModal(self.state, "points")
            )
            return

        self.state.punkte = value

        await interaction.response.edit_message(
            content="Schritt 1: Wähle Punkte, Erweiterungen und Modifikationen.",
            view=GameSettingsSelectionView(self.state)
        )


class ExpansionSelect(discord.ui.Select):
    def __init__(self, state: AddGameState):
        self.state = state

        options = build_multi_select_options_with_add_first(
            get_expansion_options(),
            state.erweiterungen,
            "Neue Erweiterung eintragen"
        )

        super().__init__(
            placeholder="Erweiterung(en) auswählen",
            min_values=1,
            max_values=len(options),
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        selected = [
            value for value in self.values
            if value != "__add__"
        ]

        self.state.erweiterungen = normalize_expansion_values(selected)

        if "__add__" in self.values:
            await interaction.response.send_modal(
                CustomSettingModal(self.state, "expansion")
            )
            return

        await interaction.response.edit_message(
            content="Schritt 1: Wähle Punkte, Erweiterungen und Modifikationen.",
            view=GameSettingsSelectionView(self.state)
        )


class ModificationSelect(discord.ui.Select):
    def __init__(self, state: AddGameState):
        self.state = state

        options = build_multi_select_options_with_add_first(
            get_modification_options(),
            state.modifikationen,
            "Neue Modifikation eintragen"
        )

        super().__init__(
            placeholder="Modifikation(en) auswählen, optional",
            min_values=0,
            max_values=len(options),
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        selected = [
            value for value in self.values
            if value != "__add__"
        ]

        self.state.modifikationen = clean_selected_values(selected)

        if "__add__" in self.values:
            await interaction.response.send_modal(
                CustomSettingModal(self.state, "modification")
            )
            return

        await interaction.response.edit_message(
            content="Schritt 1: Wähle Punkte, Erweiterungen und Modifikationen.",
            view=GameSettingsSelectionView(self.state)
        )


class CustomSettingModal(discord.ui.Modal):
    value = discord.ui.TextInput(
        label="Neuer Eintrag",
        placeholder="Neuen Wert eintragen",
        required=True,
        max_length=100
    )

    def __init__(self, state: AddGameState, setting_type: str):
        title_map = {
            "points": "Neue Punkte eintragen",
            "expansion": "Neue Erweiterung eintragen",
            "modification": "Neue Modifikation eintragen"
        }

        super().__init__(title=title_map.get(setting_type, "Neuer Eintrag"))

        self.state = state
        self.setting_type = setting_type

    async def on_submit(self, interaction: discord.Interaction):
        value = clean_text(str(self.value.value))

        if not value:
            await interaction.response.send_message(
                "Leerer Eintrag.",
                ephemeral=True
            )
            return

        if self.setting_type == "points":
            number = parse_number(value)

            if number is None:
                await interaction.response.send_message(
                    "Punkte müssen eine Zahl sein.",
                    ephemeral=True
                )
                return

            value = format_number_for_sheet(number)
            add_botdata_points(value)
            self.state.punkte = value
            label = "Punkte"

        elif self.setting_type == "expansion":
            add_botdata_expansion(value)

            current = [
                expansion for expansion in self.state.erweiterungen
                if normalize_name(expansion) != normalize_name(value)
            ]

            current.append(value)
            self.state.erweiterungen = normalize_expansion_values(current)
            label = "Erweiterung"

        else:
            add_botdata_modification(value)

            current = [
                modification for modification in self.state.modifikationen
                if normalize_name(modification) != normalize_name(value)
            ]

            current.append(value)
            self.state.modifikationen = clean_selected_values(current)
            label = "Modifikation"

        await interaction.response.send_message(
            f"{label} **{value}** wurde gesetzt.\n\nSchritt 1: Prüfe die Auswahl und klicke auf Weiter.",
            view=GameSettingsSelectionView(self.state),
            ephemeral=True
        )


class GameSettingsSelectionView(OwnerOnlyView):
    def __init__(self, state: AddGameState):
        super().__init__(state)

        self.add_item(PointsSelect(state))
        self.add_item(ExpansionSelect(state))
        self.add_item(ModificationSelect(state))

    @discord.ui.button(
        label="Weiter",
        style=discord.ButtonStyle.primary
    )
    async def next_step(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not self.state.punkte:
            await interaction.response.send_message(
                "Bitte Punkte auswählen.",
                ephemeral=True
            )
            return

        if not self.state.erweiterungen:
            await interaction.response.send_message(
                "Bitte mindestens eine Erweiterung auswählen.",
                ephemeral=True
            )
            return

        self.state.erweiterungen = normalize_expansion_values(self.state.erweiterungen)

        if not self.state.modifikationen:
            self.state.modifikationen = ["Standard"]
        else:
            self.state.modifikationen = clean_selected_values(self.state.modifikationen)

        player_names = get_all_player_names_cached()
        view = PlayerAsyncSelectionView(self.state, player_names)

        await interaction.response.edit_message(
            content="Schritt 2: Wähle ASYNC und bis zu 8 Spieler aus. Falls ein Name fehlt, wähle 'Neuen Spieler eintragen'. Für externe Spieler wähle 'Externe Spieler hinzufügen'.",
            view=view
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
            if is_external_player_name(name):
                continue

            key = normalize_player_name(name)
            if key not in seen:
                visible_names.append(name)
                seen.add(key)

        for name in player_names:
            key = normalize_player_name(name)
            if key not in seen:
                visible_names.append(name)
                seen.add(key)
            if len(visible_names) >= 23:
                break

        options = [
            discord.SelectOption(
                label="Neuen Spieler eintragen",
                value="__add_player__"
            ),
            discord.SelectOption(
                label="Externe Spieler hinzufügen",
                value="__add_external__"
            )
        ]

        options.extend([
            discord.SelectOption(
                label=name,
                value=name,
                default=name in state.participants
            )
            for name in visible_names
        ])

        super().__init__(
            placeholder="Spieler auswählen, maximal 8",
            min_values=1,
            max_values=min(MAX_PLAYERS_PER_GAME, len(options)),
            options=options[:25]
        )

    async def callback(self, interaction: discord.Interaction):
        selected_real_players = [
            value for value in self.values
            if value not in {"__add_player__", "__add_external__"}
        ]

        current_external_players = [
            player_name for player_name in self.state.participants
            if is_external_player_name(player_name)
        ]

        self.state.participants = selected_real_players + current_external_players

        if "__add_player__" in self.values:
            await interaction.response.send_modal(CustomPlayerModal(self.state))
            return

        if "__add_external__" in self.values:
            await interaction.response.send_modal(ExternalPlayersModal(self.state))
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

        final_name = canonical_player_name(raw_name)

        existing_names = get_all_player_names_cached(force_refresh=True)
        existing_match = next(
            (
                name for name in existing_names
                if normalize_player_name(name) == normalize_player_name(final_name)
            ),
            None
        )

        if existing_match:
            final_name = existing_match
            message = f"Spieler **{final_name}** existiert bereits und wurde ausgewählt."
        else:
            success, message = add_botdata_player(final_name)

            if not success and "existiert bereits" not in message:
                await interaction.response.send_message(
                    message,
                    ephemeral=True
                )
                return

        if normalize_player_name(final_name) not in [normalize_player_name(p) for p in self.state.participants]:
            if len(self.state.participants) >= MAX_PLAYERS_PER_GAME:
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


class ExternalPlayersModal(discord.ui.Modal, title="Externe Spieler hinzufügen"):
    amount = discord.ui.TextInput(
        label="Anzahl externer Spieler",
        placeholder="1-7",
        required=True,
        max_length=1
    )

    def __init__(self, state: AddGameState):
        super().__init__()
        self.state = state

    async def on_submit(self, interaction: discord.Interaction):
        try:
            requested_amount = int(str(self.amount.value).strip())
        except ValueError:
            await interaction.response.send_message(
                "Bitte eine Zahl zwischen 1 und 7 eingeben.",
                ephemeral=True
            )
            return

        if requested_amount < 1 or requested_amount > MAX_EXTERNAL_PLAYERS:
            await interaction.response.send_message(
                "Bitte eine Zahl zwischen 1 und 7 eingeben.",
                ephemeral=True
            )
            return

        added = add_external_players_to_state(self.state, requested_amount)

        player_names = get_all_player_names_cached(force_refresh=True)
        view = PlayerAsyncSelectionView(self.state, player_names)

        await interaction.response.send_message(
            f"{added} externe Spieler wurden hinzugefügt.\n\nSchritt 2: Prüfe ASYNC und Spielerauswahl, dann klicke auf Weiter.",
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

        if len(self.state.participants) > MAX_PLAYERS_PER_GAME:
            await interaction.response.send_message(
                "Es dürfen maximal 8 Spieler ausgewählt sein.",
                ephemeral=True
            )
            return

        view = WinnerCommunitySelectionView(self.state)

        await interaction.response.edit_message(
            content="Schritt 3: Wähle einen oder mehrere Gewinner und Community Preis.",
            view=view
        )


class WinnerSelect(discord.ui.Select):
    def __init__(self, state: AddGameState):
        self.state = state

        options = [
            discord.SelectOption(
                label="Kein Gewinner / abgebrochen",
                value="__none__",
                default=state.winner_selected and not state.winners
            )
        ]

        options.extend([
            discord.SelectOption(
                label=name,
                value=name,
                default=name in state.winners
            )
            for name in state.participants
        ])

        super().__init__(
            placeholder="Gewinner auswählen, mehrere möglich",
            min_values=1,
            max_values=len(options),
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if "__none__" in self.values:
            self.state.winners = []
        else:
            self.state.winners = list(self.values)

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
                "Bitte mindestens einen Gewinner oder 'Kein Gewinner / abgebrochen' auswählen.",
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

        options = [
            discord.SelectOption(
                label="Neues Volk eintragen",
                value="__custom__"
            )
        ]

        for faction in visible_factions:
            options.append(
                discord.SelectOption(
                    label=faction,
                    value=faction,
                    default=detail["faction"] == faction
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
# 📅 SESSION / REMINDER SYSTEM
# =========================================================
SESSION_TIMEZONE = ZoneInfo("Europe/Berlin")
SESSION_HEADERS = [
    "SessionID",
    "GuildID",
    "ChannelID",
    "CreatorID",
    "Title",
    "StartUTC",
    "Location",
    "ParticipantIDs",
    "ReminderDays",
    "SentReminderDays",
    "Status",
    "CreatedAt",
    "EventID"
]

GERMAN_WEEKDAYS = [
    "Montag",
    "Dienstag",
    "Mittwoch",
    "Donnerstag",
    "Freitag",
    "Samstag",
    "Sonntag"
]

GERMAN_MONTHS = [
    "Januar",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember"
]


@dataclass
class SessionDraft:
    owner_id: int
    guild_id: int
    channel_id: int
    title: str
    start_utc: datetime
    location: str
    reminder_days: list[int]


def get_sessions_sheet(create=False):
    try:
        worksheet = spreadsheet.worksheet(SESSIONS_SHEET_NAME)
    except WorksheetNotFound:
        if not create:
            return None

        worksheet = spreadsheet.add_worksheet(
            title=SESSIONS_SHEET_NAME,
            rows=500,
            cols=len(SESSION_HEADERS)
        )
        worksheet.update(
            values=[SESSION_HEADERS],
            range_name=f"A1:{rowcol_to_a1(1, len(SESSION_HEADERS))}"
        )
        return worksheet

    first_row = worksheet.row_values(1)

    if not first_row:
        worksheet.update(
            values=[SESSION_HEADERS],
            range_name=f"A1:{rowcol_to_a1(1, len(SESSION_HEADERS))}"
        )
    elif first_row[:len(SESSION_HEADERS)] != SESSION_HEADERS:
        raise RuntimeError(
            f"Das Tabellenblatt '{SESSIONS_SHEET_NAME}' hat unerwartete Spalten. "
            "Bitte die Kopfzeile nicht manuell verändern."
        )

    return worksheet


def parse_session_datetime(date_value: str, time_value: str) -> datetime:
    date_value = str(date_value).strip()
    time_value = str(time_value).strip()

    parsed_date = None
    for date_format in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            parsed_date = datetime.strptime(date_value, date_format).date()
            break
        except ValueError:
            continue

    if parsed_date is None:
        raise ValueError("Ungültiges Datum. Nutze `TT.MM.JJJJ`, z.B. `08.08.2026`.")

    try:
        parsed_time = datetime.strptime(time_value, "%H:%M").time()
    except ValueError as exc:
        raise ValueError("Ungültige Uhrzeit. Nutze `HH:MM`, z.B. `09:00`.") from exc

    local_datetime = datetime.combine(
        parsed_date,
        parsed_time,
        tzinfo=SESSION_TIMEZONE
    )

    if local_datetime <= datetime.now(SESSION_TIMEZONE):
        raise ValueError("Der Termin muss in der Zukunft liegen.")

    return local_datetime.astimezone(timezone.utc)


def parse_reminder_days(value: str) -> list[int]:
    value = str(value).strip().lower()

    if value in {"", "0", "keine", "none", "-"}:
        return []

    raw_values = [part for part in re.split(r"[,;\s]+", value) if part]
    reminder_days = []

    for raw_value in raw_values:
        try:
            day = int(raw_value)
        except ValueError as exc:
            raise ValueError(
                "Erinnerungen müssen als Tage angegeben werden, z.B. `3, 1`."
            ) from exc

        if day == 0:
            raise ValueError("`0` bedeutet keine Erinnerung und kann nur alleine stehen.")
        if day < 1 or day > 30:
            raise ValueError("Erinnerungstage müssen zwischen 1 und 30 liegen.")

        if day not in reminder_days:
            reminder_days.append(day)

    return sorted(reminder_days, reverse=True)


def serialize_number_list(values) -> str:
    return ",".join(str(int(value)) for value in values)


def parse_number_list(value: str) -> list[int]:
    result = []

    for part in re.split(r"[,;\s]+", str(value).strip()):
        if not part:
            continue
        try:
            result.append(int(part))
        except ValueError:
            continue

    return result


def session_datetime_from_record(record) -> datetime:
    value = str(record.get("StartUTC", "")).strip()
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def format_session_date_de(start_utc: datetime) -> str:
    local_start = start_utc.astimezone(SESSION_TIMEZONE)
    return (
        f"{GERMAN_WEEKDAYS[local_start.weekday()]}, "
        f"{local_start.day}. {GERMAN_MONTHS[local_start.month - 1]} {local_start.year}"
    )


def format_days_until(start_utc: datetime) -> str:
    today = datetime.now(SESSION_TIMEZONE).date()
    session_date = start_utc.astimezone(SESSION_TIMEZONE).date()
    days = (session_date - today).days

    if days <= 0:
        return "Heute ist der Termin!"
    if days == 1:
        return "Noch 1 Tag bis zum Termin!"
    return f"Noch {days} Tage bis zum Termin!"


def format_session_message(record, heading: str) -> str:
    start_utc = session_datetime_from_record(record)
    local_start = start_utc.astimezone(SESSION_TIMEZONE)
    participant_ids = parse_number_list(record.get("ParticipantIDs", ""))
    mentions = " ".join(f"<@{user_id}>" for user_id in participant_ids)

    return (
        f"⏰ **{heading}**\n"
        f"{mentions}\n"
        f"📅 {format_session_date_de(start_utc)}\n"
        f"🕘 {local_start.strftime('%H:%M')} Uhr\n"
        f"📍 Wir spielen bei **{record.get('Location', '-')}**\n"
        f"⏳ {format_days_until(start_utc)}"
    )


def get_session_records(guild_id=None, active_only=False):
    worksheet = get_sessions_sheet(create=False)

    if worksheet is None:
        return []

    values = worksheet.get_all_values()

    if len(values) < 2:
        return []

    headers = values[0]
    records = []

    for row_index, row in enumerate(values[1:], start=2):
        padded_row = row + [""] * max(0, len(headers) - len(row))
        record = dict(zip(headers, padded_row))
        record["_row"] = row_index

        if not str(record.get("SessionID", "")).strip():
            continue

        if guild_id is not None and str(record.get("GuildID")) != str(guild_id):
            continue

        if active_only and str(record.get("Status", "")).lower() != "active":
            continue

        records.append(record)

    return records


def append_session_record(record):
    worksheet = get_sessions_sheet(create=True)
    row = [str(record.get(header, "") or "") for header in SESSION_HEADERS]
    worksheet.append_row(row, value_input_option="RAW")
    return len(worksheet.get_all_values())


def update_session_record(row_number: int, updates: dict):
    worksheet = get_sessions_sheet(create=True)
    header_columns = {
        header: index
        for index, header in enumerate(SESSION_HEADERS, start=1)
    }
    cells = []

    for key, value in updates.items():
        column = header_columns.get(key)
        if column is None:
            continue
        cells.append(gspread.Cell(row_number, column, str(value)))

    if cells:
        worksheet.update_cells(cells, value_input_option="RAW")


def delete_session_record(row_number: int):
    worksheet = get_sessions_sheet(create=False)

    if worksheet is not None:
        worksheet.delete_rows(int(row_number))


def sort_sessions_sheet_by_start():
    worksheet = get_sessions_sheet(create=False)

    if worksheet is None:
        return

    values = worksheet.get_all_values()

    if len(values) < 3:
        return

    headers = values[0]

    if "StartUTC" not in headers:
        return

    start_column = headers.index("StartUTC") + 1
    last_column = rowcol_to_a1(1, len(headers)).replace("1", "")
    worksheet.sort(
        (start_column, "asc"),
        range=f"A2:{last_column}{len(values)}"
    )


def delete_session_records(row_numbers):
    sorted_rows = sorted(
        {int(row) for row in row_numbers if row},
        reverse=True
    )

    for row_number in sorted_rows:
        delete_session_record(row_number)

    if sorted_rows:
        sort_sessions_sheet_by_start()


def delete_session_records_for_event(record) -> int:
    event_id = str(record.get("EventID", "")).strip()
    matching_rows = []

    if event_id:
        matching_rows = [
            existing["_row"]
            for existing in get_session_records(active_only=False)
            if str(existing.get("EventID", "")).strip() == event_id
            and existing.get("_row")
        ]

    if not matching_rows and record.get("_row"):
        matching_rows = [record["_row"]]

    delete_session_records(matching_rows)
    return len(matching_rows)


def upsert_session_record(record, preferred_row=None) -> int:
    event_id = str(record.get("EventID", "")).strip()

    if not event_id:
        raise ValueError("Eine Session kann ohne Discord-Event-ID nicht gespeichert werden.")

    matching_records = [
        existing for existing in get_session_records(active_only=False)
        if str(existing.get("EventID", "")).strip() == event_id
    ]
    matching_rows = {
        int(existing["_row"]): existing
        for existing in matching_records
        if existing.get("_row")
    }
    preferred_row = int(preferred_row) if preferred_row else None

    if preferred_row in matching_rows:
        target_row = preferred_row
    elif matching_rows:
        target_row = max(matching_rows)
    elif preferred_row:
        target_row = preferred_row
    else:
        append_session_record(record)
        sort_sessions_sheet_by_start()
        matching_after_sort = [
            existing for existing in get_session_records(active_only=False)
            if str(existing.get("EventID", "")).strip() == event_id
        ]
        return matching_after_sort[0]["_row"]

    existing_record = matching_rows.get(target_row)

    if existing_record:
        record["SessionID"] = (
            existing_record.get("SessionID") or record.get("SessionID", "")
        )
        record["CreatedAt"] = (
            existing_record.get("CreatedAt") or record.get("CreatedAt", "")
        )

    update_session_record(
        target_row,
        {header: record.get(header, "") for header in SESSION_HEADERS}
    )

    duplicate_rows = [
        row_number for row_number in matching_rows
        if row_number != target_row
    ]
    delete_session_records(duplicate_rows)
    sort_sessions_sheet_by_start()
    matching_after_sort = [
        existing for existing in get_session_records(active_only=False)
        if str(existing.get("EventID", "")).strip() == event_id
    ]
    return matching_after_sort[0]["_row"]


def find_session_record(interaction: discord.Interaction, session_id: str = ""):
    records = get_session_records(
        guild_id=interaction.guild_id,
        active_only=True
    )

    session_id = str(session_id or "").strip().lower()

    if session_id:
        for record in records:
            if str(record.get("SessionID", "")).lower() == session_id:
                return record
        return None

    channel_records = [
        record for record in records
        if str(record.get("ChannelID")) == str(interaction.channel_id)
    ]

    if not channel_records:
        return None

    channel_records.sort(key=session_datetime_from_record)
    return channel_records[0]


def can_manage_session(interaction: discord.Interaction, record) -> bool:
    if str(record.get("CreatorID")) == str(interaction.user.id):
        return True

    permissions = getattr(interaction.user, "guild_permissions", None)
    return bool(permissions and permissions.manage_events)


def prefer_current_channel_sessions(interaction: discord.Interaction, records):
    records = list(records)
    channel_records = [
        record for record in records
        if str(record.get("ChannelID")) == str(interaction.channel_id)
    ]
    selected_records = channel_records or records
    selected_records.sort(key=session_datetime_from_record)
    return selected_records[:25]


def build_session_select_options(records):
    options = []

    for record in records[:25]:
        start_local = session_datetime_from_record(record).astimezone(SESSION_TIMEZONE)
        title = str(record.get("Title", "Mecatol-West-Runde"))
        location = str(record.get("Location", "-"))
        short_id = str(record.get("SessionID", ""))[-6:]
        options.append(
            discord.SelectOption(
                label=title[:100],
                description=(
                    f"{start_local.strftime('%d.%m.%Y · %H:%M')} Uhr · "
                    f"{location} · ID {short_id}"
                )[:100],
                value=str(record.get("SessionID"))
            )
        )

    return options


def initial_sent_reminders(start_utc: datetime, reminder_days: list[int]) -> list[int]:
    now_utc = datetime.now(timezone.utc)
    return [
        day for day in reminder_days
        if start_utc - timedelta(days=day) <= now_utc
    ]


async def get_native_scheduled_event(guild, event_id):
    if not guild or not event_id:
        return None

    try:
        event_id = int(event_id)
    except (TypeError, ValueError):
        return None

    cached_event = guild.get_scheduled_event(event_id)
    if cached_event is not None:
        return cached_event

    try:
        return await guild.fetch_scheduled_event(event_id)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return None


async def create_native_scheduled_event(guild, channel, record):
    start_utc = session_datetime_from_record(record)
    participant_ids = parse_number_list(record.get("ParticipantIDs", ""))
    participant_text = " ".join(f"<@{user_id}>" for user_id in participant_ids)
    reminder_channel_id = str(record.get("ChannelID", "")).strip()
    description = (
        f"Mecatol-West-Spieltermin in {channel.mention}.\n"
        f"Erinnerungskanal: <#{reminder_channel_id}>\n"
        f"Teilnehmer: {participant_text}"
    )

    return await guild.create_scheduled_event(
        name=str(record.get("Title", "Mecatol-West-Runde"))[:100],
        description=description[:1000],
        start_time=start_utc,
        end_time=start_utc + timedelta(hours=12),
        entity_type=discord.EntityType.external,
        privacy_level=discord.PrivacyLevel.guild_only,
        location=str(record.get("Location", "Mecatol West"))[:100],
        reason="Session über MW_bot angelegt"
    )


async def send_session_channel_message(
    channel,
    record,
    heading: str,
    include_reminders: bool = False
):
    content = format_session_message(record, heading)

    if include_reminders:
        content += f"\n{format_session_reminder_details(record)}"

    await channel.send(
        content,
        allowed_mentions=discord.AllowedMentions(
            everyone=False,
            roles=False,
            users=True,
            replied_user=False
        )
    )


def build_session_record_from_draft(
    draft: SessionDraft,
    participant_ids: list[int],
    session_id: str = ""
):
    sent_days = initial_sent_reminders(
        draft.start_utc,
        draft.reminder_days
    )

    return {
        "SessionID": session_id,
        "GuildID": str(draft.guild_id),
        "ChannelID": str(draft.channel_id),
        "CreatorID": str(draft.owner_id),
        "Title": draft.title,
        "StartUTC": draft.start_utc.isoformat(),
        "Location": draft.location,
        "ParticipantIDs": serialize_number_list(participant_ids),
        "ReminderDays": serialize_number_list(draft.reminder_days),
        "SentReminderDays": serialize_number_list(sent_days),
        "Status": "active",
        "CreatedAt": datetime.now(timezone.utc).isoformat(),
        "EventID": ""
    }


def format_session_summary(record, heading="Termin prüfen") -> str:
    return (
        f"**{heading}**\n"
        f"**Name:** {record.get('Title', 'Mecatol-West-Runde')}\n"
        f"{format_session_message(record, 'Zusammenfassung')}\n"
        f"{format_session_reminder_details(record)}"
    )


def format_session_reminder_details(record) -> str:
    channel_id = str(record.get("ChannelID", "")).strip()
    channel_line = (
        f"📣 **Erinnerungskanal:** <#{channel_id}>\n"
        if channel_id
        else "📣 **Erinnerungskanal:** nicht festgelegt\n"
    )

    if record.get("_native_only"):
        return (
            channel_line
            + "🔕 **Bot-Erinnerungen:** bisher keine Daten vorhanden\n"
            "Dieses ältere Discord-Event ist noch nicht mit dem Sessions-Sheet verknüpft. "
            "Beim Bearbeiten kannst du jetzt Erinnerungen neu einrichten."
        )

    reminder_days = sorted(
        set(parse_number_list(record.get("ReminderDays", ""))),
        reverse=True
    )

    if not reminder_days:
        return f"{channel_line}🔕 **Bot-Erinnerungen:** keine eingerichtet"

    sent_days = set(parse_number_list(record.get("SentReminderDays", "")))
    start_utc = session_datetime_from_record(record)
    lines = [channel_line.rstrip(), "🔔 **Bot-Erinnerungen:**"]

    for day in reminder_days:
        reminder_local = (start_utc - timedelta(days=day)).astimezone(SESSION_TIMEZONE)
        day_text = "1 Tag vorher" if day == 1 else f"{day} Tage vorher"
        state = "nicht mehr ausstehend" if day in sent_days else "ausstehend"
        lines.append(
            f"• **{day_text}:** {reminder_local.strftime('%d.%m.%Y um %H:%M Uhr')} "
            f"({state})"
        )

    return "\n".join(lines)


async def get_session_participant_names(guild, record) -> list[str]:
    names = []

    for user_id in parse_number_list(record.get("ParticipantIDs", "")):
        member = guild.get_member(user_id) if guild else None

        if member is None and guild is not None:
            try:
                member = await guild.fetch_member(user_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                member = None

        if member is None:
            names.append(f"Unbekannter Spieler ({user_id})")
        else:
            names.append(discord.utils.escape_markdown(member.display_name))

    return names


def format_public_session_summary(record, participant_names: list[str]) -> str:
    start_utc = session_datetime_from_record(record)
    local_start = start_utc.astimezone(SESSION_TIMEZONE)
    participant_text = (
        "\n".join(f"• {name}" for name in participant_names)
        if participant_names
        else "• Keine Teilnehmerdaten vorhanden"
    )

    return (
        "📋 **Termindetails**\n"
        f"**Name:** {record.get('Title', 'Mecatol-West-Runde')}\n"
        f"👥 **Teilnehmer:**\n{participant_text}\n"
        f"📅 {format_session_date_de(start_utc)}\n"
        f"🕘 {local_start.strftime('%H:%M')} Uhr\n"
        f"📍 Wir spielen bei **{record.get('Location', '-')}**\n"
        f"⏳ {format_days_until(start_utc)}\n"
        f"{format_session_reminder_details(record)}"
    )


async def finalize_session_creation(
    interaction: discord.Interaction,
    draft: SessionDraft,
    participant_ids: list[int]
):
    session_id = uuid.uuid4().hex[:8]
    record = build_session_record_from_draft(
        draft,
        participant_ids,
        session_id=session_id
    )

    try:
        native_event = await create_native_scheduled_event(
            interaction.guild,
            interaction.channel,
            record
        )
        record["EventID"] = str(native_event.id)
    except (discord.Forbidden, discord.HTTPException, ValueError) as exc:
        await interaction.edit_original_response(
            content=(
                "Der Termin wurde nicht angelegt, weil das Discord-Event nicht erstellt "
                f"werden konnte (`{type(exc).__name__}`). Prüfe für den Bot die "
                "Berechtigung **Events verwalten**."
            ),
            view=None
        )
        return

    try:
        record["_row"] = upsert_session_record(record)
    except Exception as exc:
        rollback_warning = ""

        try:
            await native_event.delete(
                reason="Session-Speicherung fehlgeschlagen; Event zurückgerollt"
            )
        except (discord.Forbidden, discord.HTTPException):
            rollback_warning = " Das bereits erstellte Discord-Event konnte nicht entfernt werden."

        await interaction.edit_original_response(
            content=(
                "Der Termin konnte nicht im Google Sheet gespeichert werden:\n"
                f"```text\n{exc}\n```{rollback_warning}"
            ),
            view=None
        )
        return

    try:
        await send_session_channel_message(
            interaction.channel,
            record,
            "Termin angelegt!",
            include_reminders=True
        )
    except discord.HTTPException as exc:
        await interaction.edit_original_response(
            content=(
                "Der Termin wurde gespeichert, aber die öffentliche Bestätigung "
                f"konnte nicht gesendet werden: `{exc}`"
            ),
            view=None
        )
        return

    await interaction.edit_original_response(
        content=(
            f"Session `{session_id}` wurde angelegt.\n"
            f"{format_session_reminder_details(record)}"
        ),
        view=None
    )


class SessionCreateModal(discord.ui.Modal, title="Neue Session anlegen"):
    session_title = discord.ui.TextInput(
        label="Name des Termins",
        placeholder="z.B. TI4-Runde August",
        required=True,
        max_length=100
    )
    date_value = discord.ui.TextInput(
        label="Datum",
        placeholder="z.B. heutiges Datum",
        required=True,
        max_length=10
    )
    time_value = discord.ui.TextInput(
        label="Uhrzeit",
        placeholder="HH:MM, z.B. 09:00",
        required=True,
        max_length=5
    )
    location = discord.ui.TextInput(
        label="Gespielt wird bei:",
        placeholder="z.B.: Max, Musterstraße 11, 40723 Hilden (Klingeln bei Mustermann)",
        required=True,
        max_length=100
    )
    reminders = discord.ui.TextInput(
        label="Erinnerungen (Tage vorher)",
        placeholder="0 = keine Erinnerung, 1 = 1 Tag vorher, 1,7 = 1 und 7 Tage vorher",
        required=False,
        max_length=50
    )

    def __init__(self, owner_id: int, guild_id: int, channel_id: int):
        super().__init__()
        self.owner_id = owner_id
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.date_value.placeholder = (
            f"z.B. {datetime.now(SESSION_TIMEZONE).strftime('%d.%m.%Y')}"
        )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            start_utc = parse_session_datetime(
                self.date_value.value,
                self.time_value.value
            )
            reminder_days = parse_reminder_days(self.reminders.value)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        draft = SessionDraft(
            owner_id=self.owner_id,
            guild_id=self.guild_id,
            channel_id=self.channel_id,
            title=str(self.session_title.value).strip(),
            start_utc=start_utc,
            location=str(self.location.value).strip(),
            reminder_days=reminder_days
        )

        await interaction.response.send_message(
            "Wähle alle Teilnehmer (maximal 8) und den Kanal für automatische Erinnerungen aus. "
            "Der aktuelle Kanal ist vorausgewählt.",
            view=SessionParticipantView(draft),
            ephemeral=True
        )


def reminder_channel_permission_error(guild, channel) -> str:
    bot_member = guild.me if guild else None

    if bot_member is None or channel is None:
        return "Der gewählte Erinnerungskanal wurde nicht gefunden."

    permissions = channel.permissions_for(bot_member)

    if not permissions.view_channel:
        return "Der Bot darf den gewählten Erinnerungskanal nicht sehen."
    if not permissions.send_messages:
        return "Der Bot darf im gewählten Erinnerungskanal keine Nachrichten senden."

    return ""


class SessionParticipantSelect(discord.ui.UserSelect):
    def __init__(self, setup_view, default_participant_ids=None):
        default_values = [
            discord.SelectDefaultValue(
                id=int(user_id),
                type=discord.SelectDefaultValueType.user
            )
            for user_id in (default_participant_ids or [])[:8]
        ]
        super().__init__(
            placeholder="Teilnehmer auswählen",
            min_values=1,
            max_values=8,
            default_values=default_values,
            row=0
        )
        self.setup_view = setup_view

    async def callback(self, interaction: discord.Interaction):
        participants = [user for user in self.values if not user.bot]

        if not participants:
            await interaction.response.send_message(
                "Bitte wähle mindestens einen menschlichen Teilnehmer aus.",
                ephemeral=True
            )
            return

        self.setup_view.participant_ids = [user.id for user in participants]
        await interaction.response.defer()


class SessionReminderChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, setup_view, default_channel_id: int | str = 0):
        default_values = []

        if str(default_channel_id or "").isdigit():
            default_values.append(
                discord.SelectDefaultValue(
                    id=int(default_channel_id),
                    type=discord.SelectDefaultValueType.channel
                )
            )

        super().__init__(
            placeholder="Kanal für automatische Erinnerungen auswählen",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            min_values=1,
            max_values=1,
            default_values=default_values,
            row=1
        )
        self.setup_view = setup_view

    async def callback(self, interaction: discord.Interaction):
        selected_channel = self.values[0]
        channel = interaction.guild.get_channel(selected_channel.id)
        permission_error = reminder_channel_permission_error(
            interaction.guild,
            channel
        )

        if permission_error:
            self.setup_view.reminder_channel_id = None
            await interaction.response.send_message(permission_error, ephemeral=True)
            return

        self.setup_view.reminder_channel_id = selected_channel.id
        await interaction.response.defer()


class SessionParticipantView(discord.ui.View):
    def __init__(self, draft: SessionDraft):
        super().__init__(timeout=300)
        self.draft = draft
        self.participant_ids = []
        self.reminder_channel_id = draft.channel_id
        self.add_item(SessionParticipantSelect(self))
        self.add_item(
            SessionReminderChannelSelect(
                self,
                default_channel_id=draft.channel_id
            )
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.draft.owner_id:
            await interaction.response.send_message(
                "Nur die Person, die den Vorgang gestartet hat, kann diese Auswahl benutzen.",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(
        label="Weiter zur Zusammenfassung",
        style=discord.ButtonStyle.primary,
        emoji="➡️",
        row=2
    )
    async def continue_to_summary(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not self.participant_ids:
            await interaction.response.send_message(
                "Bitte wähle zuerst mindestens einen Teilnehmer aus.",
                ephemeral=True
            )
            return

        try:
            reminder_channel_id = int(self.reminder_channel_id)
        except (TypeError, ValueError):
            await interaction.response.send_message(
                "Bitte wähle einen gültigen Erinnerungskanal aus.",
                ephemeral=True
            )
            return

        reminder_channel = interaction.guild.get_channel(reminder_channel_id)
        permission_error = reminder_channel_permission_error(
            interaction.guild,
            reminder_channel
        )

        if permission_error:
            await interaction.response.send_message(permission_error, ephemeral=True)
            return

        self.draft.channel_id = reminder_channel_id
        record = build_session_record_from_draft(
            self.draft,
            self.participant_ids
        )
        await interaction.response.edit_message(
            content=format_session_summary(
                record,
                heading="Bitte prüfe den Termin vor dem Anlegen"
            ),
            view=SessionCreateConfirmView(
                self.draft,
                self.participant_ids
            ),
            allowed_mentions=discord.AllowedMentions.none()
        )


class SessionCreateConfirmView(discord.ui.View):
    def __init__(self, draft: SessionDraft, participant_ids: list[int]):
        super().__init__(timeout=300)
        self.draft = draft
        self.participant_ids = participant_ids

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.draft.owner_id:
            await interaction.response.send_message(
                "Nur die Person, die den Vorgang gestartet hat, kann diesen Termin bestätigen.",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(
        label="Termin anlegen",
        style=discord.ButtonStyle.success,
        emoji="✅"
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.defer()
        await finalize_session_creation(
            interaction,
            self.draft,
            self.participant_ids
        )

    @discord.ui.button(
        label="Abbrechen",
        style=discord.ButtonStyle.danger,
        emoji="✖️"
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.edit_message(
            content="Vorgang abgebrochen. Es wurde kein Termin angelegt.",
            view=None
        )


class SessionEditModal(discord.ui.Modal):
    def __init__(self, record):
        super().__init__(title=f"Session {record['SessionID']} bearbeiten")
        self.record = record
        start_local = session_datetime_from_record(record).astimezone(SESSION_TIMEZONE)

        self.session_title = discord.ui.TextInput(
            label="Name des Termins",
            default=str(record.get("Title", ""))[:100],
            required=True,
            max_length=100
        )
        self.date_value = discord.ui.TextInput(
            label="Datum",
            default=start_local.strftime("%d.%m.%Y"),
            placeholder=f"z.B. {datetime.now(SESSION_TIMEZONE).strftime('%d.%m.%Y')}",
            required=True,
            max_length=10
        )
        self.time_value = discord.ui.TextInput(
            label="Uhrzeit",
            default=start_local.strftime("%H:%M"),
            required=True,
            max_length=5
        )
        self.location = discord.ui.TextInput(
            label="Gespielt wird bei:",
            default=str(record.get("Location", ""))[:100],
            placeholder="z.B.: Max, Musterstraße 11, 40723 Hilden (Klingeln bei Mustermann)",
            required=True,
            max_length=100
        )
        self.reminders = discord.ui.TextInput(
            label="Erinnerungen (Tage vorher)",
            default=str(record.get("ReminderDays", "")) or "0",
            placeholder="0 = keine Erinnerung, 1 = 1 Tag vorher, 1,7 = 1 und 7 Tage vorher",
            required=False,
            max_length=50
        )

        self.add_item(self.session_title)
        self.add_item(self.date_value)
        self.add_item(self.time_value)
        self.add_item(self.location)
        self.add_item(self.reminders)

    async def on_submit(self, interaction: discord.Interaction):
        if not can_manage_session(interaction, self.record):
            await interaction.response.send_message(
                "Du darfst diese Session nicht bearbeiten.",
                ephemeral=True
            )
            return

        try:
            start_utc = parse_session_datetime(
                self.date_value.value,
                self.time_value.value
            )
            reminder_days = parse_reminder_days(self.reminders.value)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        updates = {
            "Title": str(self.session_title.value).strip(),
            "StartUTC": start_utc.isoformat(),
            "Location": str(self.location.value).strip(),
            "ReminderDays": serialize_number_list(reminder_days)
        }

        await interaction.response.send_message(
            "Passe jetzt die Teilnehmer und den Kanal für automatische Erinnerungen an. "
            "Die bisherigen Werte sind vorausgewählt.",
            view=SessionEditSetupView(
                owner_id=interaction.user.id,
                record=self.record,
                updates=updates,
                fallback_channel_id=interaction.channel_id
            ),
            ephemeral=True
        )


class NativeEventEditModal(discord.ui.Modal):
    def __init__(self, record):
        super().__init__(title="Discord-Event bearbeiten")
        self.record = record
        start_local = session_datetime_from_record(record).astimezone(SESSION_TIMEZONE)

        self.session_title = discord.ui.TextInput(
            label="Name des Termins",
            default=str(record.get("Title", ""))[:100],
            required=True,
            max_length=100
        )
        self.date_value = discord.ui.TextInput(
            label="Datum",
            default=start_local.strftime("%d.%m.%Y"),
            placeholder=f"z.B. {datetime.now(SESSION_TIMEZONE).strftime('%d.%m.%Y')}",
            required=True,
            max_length=10
        )
        self.time_value = discord.ui.TextInput(
            label="Uhrzeit",
            default=start_local.strftime("%H:%M"),
            required=True,
            max_length=5
        )
        self.location = discord.ui.TextInput(
            label="Gespielt wird bei:",
            default=str(record.get("Location", ""))[:100],
            placeholder="z.B.: Max, Musterstraße 11, 40723 Hilden (Klingeln bei Mustermann)",
            required=True,
            max_length=100
        )
        self.reminders = discord.ui.TextInput(
            label="Erinnerungen (Tage vorher)",
            default="0",
            placeholder="0 = keine Erinnerung, 1 = 1 Tag vorher, 1,7 = 1 und 7 Tage vorher",
            required=False,
            max_length=50
        )

        self.add_item(self.session_title)
        self.add_item(self.date_value)
        self.add_item(self.time_value)
        self.add_item(self.location)
        self.add_item(self.reminders)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            start_utc = parse_session_datetime(
                self.date_value.value,
                self.time_value.value
            )
            reminder_days = parse_reminder_days(self.reminders.value)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        updates = {
            "Title": str(self.session_title.value).strip(),
            "StartUTC": start_utc.isoformat(),
            "Location": str(self.location.value).strip(),
            "ReminderDays": serialize_number_list(reminder_days)
        }

        await interaction.response.send_message(
            "Wähle jetzt die Teilnehmer und den Kanal für automatische Erinnerungen aus.",
            view=SessionEditSetupView(
                owner_id=interaction.user.id,
                record=self.record,
                updates=updates,
                fallback_channel_id=interaction.channel_id,
                native_only=True
            ),
            ephemeral=True
        )


def session_event_description(record) -> str:
    participant_ids = parse_number_list(record.get("ParticipantIDs", ""))
    participant_text = " ".join(f"<@{user_id}>" for user_id in participant_ids)
    reminder_channel_id = str(record.get("ChannelID", "")).strip()
    return (
        "Mecatol-West-Spieltermin.\n"
        f"Erinnerungskanal: <#{reminder_channel_id}>\n"
        f"Teilnehmer: {participant_text}"
    )[:1000]


def calculate_edited_sent_reminders(record, start_utc, reminder_days) -> list[int]:
    old_start = session_datetime_from_record(record)
    old_sent_days = set(parse_number_list(record.get("SentReminderDays", "")))

    if start_utc != old_start:
        return initial_sent_reminders(start_utc, reminder_days)

    return sorted(
        old_sent_days.intersection(reminder_days).union(
            initial_sent_reminders(start_utc, reminder_days)
        ),
        reverse=True
    )


async def finalize_linked_session_edit(
    interaction,
    record,
    base_updates,
    participant_ids,
    reminder_channel_id
):
    start_utc = session_datetime_from_record(base_updates)
    reminder_days = parse_number_list(base_updates.get("ReminderDays", ""))
    sent_days = calculate_edited_sent_reminders(
        record,
        start_utc,
        reminder_days
    )
    updates = {
        **base_updates,
        "ParticipantIDs": serialize_number_list(participant_ids),
        "ChannelID": str(reminder_channel_id),
        "SentReminderDays": serialize_number_list(sent_days),
        "Status": "active",
        "EventID": record.get("EventID", "")
    }

    record.update(updates)

    try:
        record["_row"] = upsert_session_record(
            record,
            preferred_row=record.get("_row")
        )
    except Exception as exc:
        await interaction.edit_original_response(
            content=f"Die Session konnte nicht gespeichert werden:\n```text\n{exc}\n```",
            view=None
        )
        return

    native_event_warning = ""
    native_event = await get_native_scheduled_event(
        interaction.guild,
        record.get("EventID")
    )

    if native_event is not None:
        try:
            await native_event.edit(
                name=updates["Title"][:100],
                description=session_event_description(record),
                start_time=start_utc,
                end_time=start_utc + timedelta(hours=12),
                location=updates["Location"][:100],
                reason="Session über MW_bot bearbeitet"
            )
        except (discord.Forbidden, discord.HTTPException, ValueError) as exc:
            native_event_warning = (
                " Das native Discord-Event konnte nicht aktualisiert werden "
                f"(`{type(exc).__name__}`)."
            )

    try:
        await send_session_channel_message(
            interaction.channel,
            record,
            "Termin aktualisiert!",
            include_reminders=True
        )
    except discord.HTTPException:
        native_event_warning += " Die öffentliche Änderungsnachricht konnte nicht gesendet werden."

    await interaction.edit_original_response(
        content=(
            f"Session `{record['SessionID']}` wurde aktualisiert.\n"
            f"{format_session_reminder_details(record)}"
            f"{native_event_warning}"
        ),
        view=None
    )


async def finalize_native_session_edit(
    interaction,
    record,
    base_updates,
    participant_ids,
    reminder_channel_id
):
    start_utc = session_datetime_from_record(base_updates)
    reminder_days = parse_number_list(base_updates.get("ReminderDays", ""))
    linked_record = {
        "SessionID": uuid.uuid4().hex[:8],
        "GuildID": str(interaction.guild_id),
        "ChannelID": str(reminder_channel_id),
        "CreatorID": str(interaction.user.id),
        "Title": base_updates["Title"],
        "StartUTC": base_updates["StartUTC"],
        "Location": base_updates["Location"],
        "ParticipantIDs": serialize_number_list(participant_ids),
        "ReminderDays": serialize_number_list(reminder_days),
        "SentReminderDays": serialize_number_list(
            initial_sent_reminders(start_utc, reminder_days)
        ),
        "Status": "active",
        "CreatedAt": datetime.now(timezone.utc).isoformat(),
        "EventID": record.get("EventID", "")
    }
    native_event = await get_native_scheduled_event(
        interaction.guild,
        linked_record["EventID"]
    )

    if native_event is None:
        await interaction.edit_original_response(
            content="Das Discord-Event wurde nicht mehr gefunden.",
            view=None
        )
        return

    try:
        await native_event.edit(
            name=linked_record["Title"][:100],
            description=session_event_description(linked_record),
            start_time=start_utc,
            end_time=start_utc + timedelta(hours=12),
            location=linked_record["Location"][:100],
            reason="Discord-Event über MW_bot bearbeitet"
        )
    except (discord.Forbidden, discord.HTTPException, ValueError) as exc:
        await interaction.edit_original_response(
            content=f"Das Discord-Event konnte nicht aktualisiert werden: `{exc}`",
            view=None
        )
        return

    try:
        linked_record["_row"] = upsert_session_record(linked_record)
    except Exception as exc:
        await interaction.edit_original_response(
            content=(
                "Das Discord-Event wurde aktualisiert, aber die Session konnte nicht "
                f"gespeichert werden:\n```text\n{exc}\n```"
            ),
            view=None
        )
        return

    try:
        await send_session_channel_message(
            interaction.channel,
            linked_record,
            "Termin aktualisiert!",
            include_reminders=True
        )
    except discord.HTTPException:
        pass

    await interaction.edit_original_response(
        content=(
            "Das Discord-Event wurde aktualisiert und mit dem Sessions-Sheet verknüpft.\n"
            f"{format_session_reminder_details(linked_record)}"
        ),
        view=None
    )


class SessionEditSetupView(discord.ui.View):
    def __init__(
        self,
        owner_id: int,
        record,
        updates,
        fallback_channel_id: int,
        native_only: bool = False
    ):
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.record = record
        self.updates = updates
        self.native_only = native_only
        self.participant_ids = parse_number_list(record.get("ParticipantIDs", ""))[:8]
        self.reminder_channel_id = (
            record.get("ChannelID") or fallback_channel_id
        )
        self.add_item(
            SessionParticipantSelect(
                self,
                default_participant_ids=self.participant_ids
            )
        )
        self.add_item(
            SessionReminderChannelSelect(
                self,
                default_channel_id=self.reminder_channel_id
            )
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Nur die Person, die den Befehl gestartet hat, kann diese Auswahl verwenden.",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(
        label="Änderungen speichern",
        style=discord.ButtonStyle.success,
        emoji="✅",
        row=2
    )
    async def save(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not can_manage_session(interaction, self.record):
            await interaction.response.send_message(
                "Du darfst diesen Termin nicht verwalten.",
                ephemeral=True
            )
            return
        if not self.participant_ids:
            await interaction.response.send_message(
                "Bitte wähle mindestens einen Teilnehmer aus.",
                ephemeral=True
            )
            return

        try:
            channel_id = int(self.reminder_channel_id)
        except (TypeError, ValueError):
            await interaction.response.send_message(
                "Bitte wähle einen gültigen Erinnerungskanal aus.",
                ephemeral=True
            )
            return

        reminder_channel = interaction.guild.get_channel(channel_id)
        permission_error = reminder_channel_permission_error(
            interaction.guild,
            reminder_channel
        )

        if permission_error:
            await interaction.response.send_message(permission_error, ephemeral=True)
            return

        await interaction.response.defer()

        if self.native_only:
            await finalize_native_session_edit(
                interaction,
                self.record,
                self.updates,
                self.participant_ids,
                channel_id
            )
        else:
            await finalize_linked_session_edit(
                interaction,
                self.record,
                self.updates,
                self.participant_ids,
                channel_id
            )

    @discord.ui.button(
        label="Abbrechen",
        style=discord.ButtonStyle.secondary,
        emoji="✖️",
        row=2
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.edit_message(
            content="Bearbeitung abgebrochen. Es wurde nichts geändert.",
            view=None
        )


def scheduled_event_to_session_record(event):
    location = str(getattr(event, "location", "") or "Discord-Event")
    creator_id = getattr(event, "creator_id", None) or ""
    description = str(getattr(event, "description", "") or "")
    participant_ids = [
        int(user_id)
        for user_id in re.findall(r"<@!?(\d+)>", description)
    ]
    channel_match = re.search(
        r"Erinnerungskanal:\s*<#(\d+)>",
        description,
        flags=re.IGNORECASE
    ) or re.search(r"<#(\d+)>", description)

    return {
        "SessionID": f"discord-{event.id}",
        "GuildID": str(event.guild_id),
        "ChannelID": channel_match.group(1) if channel_match else "",
        "CreatorID": str(creator_id),
        "Title": str(event.name),
        "StartUTC": event.start_time.astimezone(timezone.utc).isoformat(),
        "Location": location,
        "ParticipantIDs": serialize_number_list(participant_ids),
        "ReminderDays": "",
        "SentReminderDays": "",
        "Status": "native_only",
        "CreatedAt": "",
        "EventID": str(event.id),
        "_native_only": True
    }


def session_record_matches_native_event(record, event) -> bool:
    if str(record.get("Status", "")).lower() != "active":
        return False
    if str(record.get("EventID", "")).strip():
        return False

    try:
        record_start = session_datetime_from_record(record)
        event_start = event.start_time.astimezone(timezone.utc)
    except (AttributeError, TypeError, ValueError):
        return False

    same_start = abs((record_start - event_start).total_seconds()) < 60
    same_title = (
        str(record.get("Title", "")).strip().casefold()
        == str(event.name).strip().casefold()
    )
    record_location = str(record.get("Location", "")).strip().casefold()
    event_location = str(getattr(event, "location", "") or "").strip().casefold()
    same_location = not record_location or not event_location or record_location == event_location
    return same_start and same_title and same_location


def repair_session_ids_from_native_event(guild_id, record, event):
    if not record.get("_row"):
        return

    updates = {}
    expected_guild_id = str(guild_id)

    if str(record.get("GuildID", "")) != expected_guild_id:
        updates["GuildID"] = expected_guild_id

    description = str(getattr(event, "description", "") or "")
    channel_match = re.search(
        r"Erinnerungskanal:\s*<#(\d+)>",
        description,
        flags=re.IGNORECASE
    ) or re.search(r"<#(\d+)>", description)

    if channel_match:
        expected_channel_id = channel_match.group(1)
        if str(record.get("ChannelID", "")) != expected_channel_id:
            updates["ChannelID"] = expected_channel_id

    if updates:
        update_session_record(record["_row"], updates)
        record.update(updates)


async def get_selectable_server_session_records(
    interaction: discord.Interaction,
    require_manage: bool
):
    all_sheet_records = get_session_records(active_only=False)
    sheet_records = [
        record for record in all_sheet_records
        if str(record.get("GuildID")) == str(interaction.guild_id)
    ]
    records_by_event_id = {
        str(record.get("EventID")): record
        for record in all_sheet_records
        if str(record.get("EventID", "")).strip()
    }
    selectable_by_key = {
        f"session:{record.get('SessionID')}": record
        for record in sheet_records
        if str(record.get("Status", "")).lower() == "active"
    }

    try:
        native_events = await interaction.guild.fetch_scheduled_events(
            with_counts=False
        )
    except (discord.Forbidden, discord.HTTPException):
        native_events = []

    matched_unlinked_rows = set()

    for event in native_events:
        if event.status not in {
            discord.EventStatus.scheduled,
            discord.EventStatus.active
        }:
            continue

        record = records_by_event_id.get(str(event.id))

        if record is not None:
            repair_session_ids_from_native_event(
                interaction.guild_id,
                record,
                event
            )

        if record is None:
            record = next(
                (
                    candidate for candidate in sheet_records
                    if candidate.get("_row") not in matched_unlinked_rows
                    and session_record_matches_native_event(candidate, event)
                ),
                None
            )

            if record is not None:
                matched_unlinked_rows.add(record.get("_row"))
                record["EventID"] = str(event.id)
                record["_pending_event_link"] = True
            else:
                record = scheduled_event_to_session_record(event)

        selectable_by_key[f"event:{event.id}"] = record

        session_key = f"session:{record.get('SessionID')}"
        selectable_by_key.pop(session_key, None)

    selectable_records = list(selectable_by_key.values())

    if require_manage:
        selectable_records = [
            record for record in selectable_records
            if can_manage_session(interaction, record)
        ]

    selectable_records.sort(
        key=lambda record: (
            str(record.get("ChannelID")) != str(interaction.channel_id),
            session_datetime_from_record(record)
        )
    )
    return selectable_records[:25]


async def build_session_cleanup_plan(guild):
    native_events = await guild.fetch_scheduled_events(with_counts=False)
    active_events = {
        str(event.id): event
        for event in native_events
        if event.status in {
            discord.EventStatus.scheduled,
            discord.EventStatus.active
        }
    }
    records = get_session_records(active_only=False)
    guild_records = [
        record for record in records
        if str(record.get("GuildID", "")) == str(guild.id)
        or str(record.get("EventID", "")) in active_events
    ]
    rows_to_delete = set()
    orphan_rows = set()
    duplicate_rows = set()
    keep_by_event_id = {}

    for record in guild_records:
        event_id = str(record.get("EventID", "")).strip()

        if str(record.get("GuildID", "")) == str(guild.id) and event_id not in active_events:
            rows_to_delete.add(record["_row"])
            orphan_rows.add(record["_row"])

    for event_id, event in active_events.items():
        matching_records = [
            record for record in guild_records
            if str(record.get("EventID", "")).strip() == event_id
        ]

        if not matching_records:
            continue

        keep_record = max(
            matching_records,
            key=lambda record: (
                str(record.get("Status", "")).lower() == "active",
                int(record.get("_row", 0))
            )
        )
        keep_by_event_id[event_id] = (keep_record, event)

        for duplicate in matching_records:
            if duplicate["_row"] != keep_record["_row"]:
                rows_to_delete.add(duplicate["_row"])
                duplicate_rows.add(duplicate["_row"])

    return {
        "rows_to_delete": sorted(rows_to_delete, reverse=True),
        "orphan_count": len(orphan_rows),
        "duplicate_count": len(duplicate_rows),
        "keep_by_event_id": keep_by_event_id
    }


def apply_session_cleanup_plan(guild, plan):
    for record, event in plan["keep_by_event_id"].values():
        repair_session_ids_from_native_event(guild.id, record, event)

        if str(record.get("Status", "")).lower() != "active":
            update_session_record(record["_row"], {"Status": "active"})

    delete_session_records(plan["rows_to_delete"])


async def perform_session_cancellation(
    interaction: discord.Interaction,
    record
):
    warning = ""
    native_event = await get_native_scheduled_event(
        interaction.guild,
        record.get("EventID")
    )

    if native_event is not None:
        try:
            if native_event.status == discord.EventStatus.scheduled:
                await native_event.cancel(reason="Session über MW_bot abgesagt")
            else:
                await native_event.delete(reason="Session über MW_bot entfernt")
        except ValueError:
            try:
                await native_event.delete(reason="Session über MW_bot entfernt")
            except (discord.Forbidden, discord.HTTPException) as exc:
                await interaction.edit_original_response(
                    content=(
                        "Das Discord-Event konnte nicht entfernt werden "
                        f"(`{type(exc).__name__}`). Die Session bleibt gespeichert."
                    ),
                    view=None
                )
                return
        except (discord.Forbidden, discord.HTTPException) as exc:
            await interaction.edit_original_response(
                content=(
                    "Das Discord-Event konnte nicht abgesagt werden "
                    f"(`{type(exc).__name__}`). Die Session bleibt gespeichert."
                ),
                view=None
            )
            return

    if record.get("_row"):
        try:
            delete_session_records_for_event(record)
        except Exception as exc:
            try:
                update_session_record(record["_row"], {"Status": "cancelled"})
            except Exception:
                pass

            await interaction.edit_original_response(
                content=(
                    "Das Discord-Event wurde abgesagt, aber die Zeile konnte nicht aus "
                    f"dem Sessions-Sheet entfernt werden:\n```text\n{exc}\n```"
                ),
                view=None
            )
            return

    try:
        participant_ids = parse_number_list(record.get("ParticipantIDs", ""))
        mentions = " ".join(f"<@{user_id}>" for user_id in participant_ids)
        await interaction.channel.send(
            f"❌ **Termin abgesagt!**\n{mentions}\n"
            f"Der Termin **{record.get('Title', 'Mecatol-West-Runde')}** findet nicht statt.",
            allowed_mentions=discord.AllowedMentions(
                everyone=False,
                roles=False,
                users=True,
                replied_user=False
            )
        )
    except discord.HTTPException:
        warning += " Die öffentliche Absage konnte nicht gesendet werden."

    await interaction.edit_original_response(
        content=(
            f"Session `{record['SessionID']}` wurde abgesagt. "
            "Die Sheet-Zeile wurde entfernt und alle Erinnerungen wurden deaktiviert."
            f"{warning}"
        ),
        view=None
    )


class SessionCancelSelect(discord.ui.Select):
    def __init__(self, owner_id: int, records):
        self.owner_id = owner_id
        self.records = {
            str(record.get("SessionID")): record
            for record in records
        }
        super().__init__(
            placeholder="Termin zum Absagen auswählen",
            min_values=1,
            max_values=1,
            options=build_session_select_options(records)
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Nur die Person, die den Befehl gestartet hat, kann einen Termin auswählen.",
                ephemeral=True
            )
            return

        record = self.records.get(self.values[0])

        if record is None:
            await interaction.response.edit_message(
                content="Der ausgewählte Termin wurde nicht mehr gefunden.",
                view=None
            )
            return

        await interaction.response.edit_message(
            content=(
                f"{format_session_summary(record, heading='Diesen Termin wirklich absagen?')}\n\n"
                "Beim Absagen werden alle noch ausstehenden Erinnerungen deaktiviert."
            ),
            view=SessionCancelConfirmView(
                owner_id=self.owner_id,
                record=record
            )
        )


class SessionCancelSelectView(discord.ui.View):
    def __init__(self, owner_id: int, records):
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.add_item(SessionCancelSelect(owner_id, records))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Nur die Person, die den Befehl gestartet hat, kann diese Auswahl verwenden.",
                ephemeral=True
            )
            return False
        return True


class SessionCancelConfirmView(discord.ui.View):
    def __init__(self, owner_id: int, record):
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.record = record

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Nur die Person, die den Befehl gestartet hat, kann diesen Termin absagen.",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(
        label="Termin absagen",
        style=discord.ButtonStyle.danger,
        emoji="🗑️"
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.defer()
        record = self.record

        if not record.get("_native_only"):
            try:
                session_id = str(record.get("SessionID"))
                fresh_records = get_session_records(
                    guild_id=interaction.guild_id,
                    active_only=False
                )
                record = next(
                    (
                        fresh_record for fresh_record in fresh_records
                        if str(fresh_record.get("SessionID")) == session_id
                    ),
                    None
                )
            except Exception as exc:
                await interaction.edit_original_response(
                    content=f"Die Session konnte nicht geladen werden:\n```text\n{exc}\n```",
                    view=None
                )
                return

            if record is None:
                await interaction.edit_original_response(
                    content="Dieser Termin wurde im Sessions-Sheet nicht mehr gefunden.",
                    view=None
                )
                return

        if not can_manage_session(interaction, record):
            await interaction.edit_original_response(
                content="Du darfst diese Session nicht absagen.",
                view=None
            )
            return

        await perform_session_cancellation(interaction, record)

    @discord.ui.button(
        label="Zurück / nicht absagen",
        style=discord.ButtonStyle.secondary,
        emoji="↩️"
    )
    async def abort(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.edit_message(
            content="Abgebrochen. Der Termin bleibt bestehen und Erinnerungen bleiben aktiv.",
            view=None
        )


class SessionCleanupConfirmView(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=300)
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Nur die Person, die die Bereinigung gestartet hat, kann sie bestätigen.",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(
        label="Sheet bereinigen",
        style=discord.ButtonStyle.danger,
        emoji="🧹"
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        permissions = getattr(interaction.user, "guild_permissions", None)

        if not permissions or not permissions.manage_events:
            await interaction.response.send_message(
                "Du benötigst die Berechtigung **Events verwalten**.",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            plan = await build_session_cleanup_plan(interaction.guild)
            apply_session_cleanup_plan(interaction.guild, plan)
        except Exception as exc:
            await interaction.edit_original_response(
                content=f"Die Bereinigung ist fehlgeschlagen:\n```text\n{exc}\n```",
                view=None
            )
            return

        await interaction.edit_original_response(
            content=(
                f"Bereinigung abgeschlossen: **{len(plan['rows_to_delete'])}** Zeilen entfernt "
                f"({plan['duplicate_count']} Duplikate, "
                f"{plan['orphan_count']} nicht mehr vorhandene Termine)."
            ),
            view=None
        )

    @discord.ui.button(
        label="Abbrechen",
        style=discord.ButtonStyle.secondary,
        emoji="✖️"
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.edit_message(
            content="Bereinigung abgebrochen. Es wurde nichts gelöscht.",
            view=None
        )


class SessionEditReviewView(discord.ui.View):
    def __init__(self, owner_id: int, record):
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.record = record

        if record.get("_native_only"):
            self.edit.label = "Discord-Event bearbeiten"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Nur die Person, die den Befehl gestartet hat, kann diesen Termin bearbeiten.",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(
        label="Termin & Erinnerungen bearbeiten",
        style=discord.ButtonStyle.primary,
        emoji="✏️"
    )
    async def edit(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not can_manage_session(interaction, self.record):
            await interaction.response.send_message(
                "Du darfst diesen Termin nicht verwalten.",
                ephemeral=True
            )
            return

        if self.record.get("_native_only"):
            await interaction.response.send_modal(NativeEventEditModal(self.record))
        else:
            await interaction.response.send_modal(SessionEditModal(self.record))

    @discord.ui.button(
        label="Abbrechen",
        style=discord.ButtonStyle.secondary,
        emoji="✖️"
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.edit_message(
            content="Bearbeitung abgebrochen. Es wurde nichts geändert.",
            view=None
        )


class SessionActionSelect(discord.ui.Select):
    ACTION_PLACEHOLDERS = {
        "show": "Termin zum Anzeigen auswählen",
        "edit": "Termin zum Bearbeiten auswählen",
        "remind": "Termin für die Erinnerung auswählen"
    }

    def __init__(self, owner_id: int, records, action: str):
        self.owner_id = owner_id
        self.action = action
        self.records = {
            str(record.get("SessionID")): record
            for record in records
        }
        super().__init__(
            placeholder=self.ACTION_PLACEHOLDERS[action],
            min_values=1,
            max_values=1,
            options=build_session_select_options(records)
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Nur die Person, die den Befehl gestartet hat, kann einen Termin auswählen.",
                ephemeral=True
            )
            return

        record = self.records.get(self.values[0])

        if record is None:
            await interaction.response.edit_message(
                content="Der ausgewählte Termin wurde nicht mehr gefunden.",
                view=None
            )
            return

        if self.action == "show":
            await interaction.response.defer()
            participant_names = await get_session_participant_names(
                interaction.guild,
                record
            )

            try:
                await interaction.channel.send(
                    format_public_session_summary(record, participant_names),
                    allowed_mentions=discord.AllowedMentions.none()
                )
            except discord.HTTPException as exc:
                await interaction.edit_original_response(
                    content=f"Die Termindetails konnten nicht gesendet werden: `{exc}`",
                    view=None
                )
                return

            await interaction.edit_original_response(
                content="Die Termindetails wurden öffentlich im Kanal angezeigt.",
                view=None
            )
            return

        if not can_manage_session(interaction, record):
            await interaction.response.send_message(
                "Du darfst diesen Termin nicht verwalten.",
                ephemeral=True
            )
            return

        if self.action == "edit":
            await interaction.response.edit_message(
                content=format_session_summary(
                    record,
                    heading="Termin und Erinnerungen bearbeiten"
                ),
                view=SessionEditReviewView(
                    owner_id=self.owner_id,
                    record=record
                ),
                allowed_mentions=discord.AllowedMentions.none()
            )
            return

        if self.action == "remind":
            await interaction.response.defer()

            try:
                await send_session_channel_message(
                    interaction.channel,
                    record,
                    "Termin Erinnerung!"
                )
            except discord.HTTPException as exc:
                await interaction.edit_original_response(
                    content=f"Die Erinnerung konnte nicht gesendet werden: `{exc}`",
                    view=None
                )
                return

            await interaction.edit_original_response(
                content=(
                    f"Erinnerung für Session `{record['SessionID']}` wurde gesendet."
                ),
                view=None
            )


class SessionActionSelectView(discord.ui.View):
    def __init__(self, owner_id: int, records, action: str):
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.add_item(SessionActionSelect(owner_id, records, action))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Nur die Person, die den Befehl gestartet hat, kann diese Auswahl verwenden.",
                ephemeral=True
            )
            return False
        return True


async def open_session_action_picker(
    interaction: discord.Interaction,
    action: str,
    require_manage: bool
):
    await interaction.response.defer(ephemeral=True, thinking=True)

    try:
        if action in {"show", "edit", "remind"}:
            records = await get_selectable_server_session_records(
                interaction,
                require_manage=require_manage
            )
        else:
            records = get_session_records(
                guild_id=interaction.guild_id,
                active_only=True
            )
    except Exception as exc:
        await interaction.edit_original_response(
            content=f"Die Sessions konnten nicht geladen werden:\n```text\n{exc}\n```",
            view=None
        )
        return

    if require_manage and action == "remind":
        records = [
            record for record in records
            if can_manage_session(interaction, record)
            and str(record.get("Status", "")).lower() == "active"
            and not record.get("_native_only")
        ]

    if action == "remind":
        records = prefer_current_channel_sessions(interaction, records)

    if not records:
        await interaction.edit_original_response(
            content="Es wurde kein passender aktiver Termin gefunden.",
            view=None
        )
        return

    prompt = {
        "show": "Wähle den Termin aus, den du anzeigen möchtest:",
        "edit": "Wähle den Termin aus, den du bearbeiten möchtest:",
        "remind": "Wähle den Termin aus, für den du eine Erinnerung senden möchtest:"
    }[action]
    await interaction.edit_original_response(
        content=prompt,
        view=SessionActionSelectView(
            owner_id=interaction.user.id,
            records=records,
            action=action
        )
    )


async def resolve_session_channel(record):
    try:
        channel_id = int(record.get("ChannelID", 0))
    except (TypeError, ValueError):
        channel_id = 0

    channel = client.get_channel(channel_id) if channel_id else None

    if channel is not None:
        return channel

    if channel_id:
        try:
            return await client.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    event_id = record.get("EventID")

    if not event_id:
        return None

    for guild in client.guilds:
        native_event = await get_native_scheduled_event(guild, event_id)

        if native_event is None:
            continue

        repair_session_ids_from_native_event(guild.id, record, native_event)

        try:
            repaired_channel_id = int(record.get("ChannelID", 0))
        except (TypeError, ValueError):
            return None

        repaired_channel = client.get_channel(repaired_channel_id)

        if repaired_channel is not None:
            return repaired_channel

        try:
            return await client.fetch_channel(repaired_channel_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None

    return None


@tasks.loop(minutes=5)
async def session_reminder_loop():
    try:
        records = get_session_records(active_only=True)
    except Exception as exc:
        print(f"Session-Reminder: Google-Sheet-Fehler: {exc}")
        return

    now_utc = datetime.now(timezone.utc)

    for record in records:
        try:
            start_utc = session_datetime_from_record(record)
        except (TypeError, ValueError):
            print(f"Session-Reminder: Ungültige Startzeit in Session {record.get('SessionID')}")
            continue

        if start_utc <= now_utc:
            try:
                delete_session_records_for_event(record)
            except Exception as exc:
                try:
                    update_session_record(record["_row"], {"Status": "completed"})
                except Exception:
                    pass
                print(f"Session-Reminder: Abgelaufene Session konnte nicht entfernt werden: {exc}")
            continue

        reminder_days = set(parse_number_list(record.get("ReminderDays", "")))
        sent_days = set(parse_number_list(record.get("SentReminderDays", "")))
        due_days = {
            day for day in reminder_days - sent_days
            if now_utc >= start_utc - timedelta(days=day)
        }

        if not due_days:
            continue

        channel = await resolve_session_channel(record)

        if channel is None:
            print(f"Session-Reminder: Kanal für Session {record.get('SessionID')} nicht gefunden")
            continue

        try:
            await send_session_channel_message(
                channel,
                record,
                "Termin Erinnerung!"
            )
            sent_days.update(due_days)
            update_session_record(
                record["_row"],
                {"SentReminderDays": serialize_number_list(sorted(sent_days, reverse=True))}
            )
        except Exception as exc:
            print(f"Session-Reminder: Versandfehler für {record.get('SessionID')}: {exc}")


@session_reminder_loop.before_loop
async def before_session_reminder_loop():
    await client.wait_until_ready()


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

    if not text:
        text = "Keine Daten"

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

    if not text:
        text = "Keine Daten"

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
        title=f"Spielerstatistik: {canonical_player_name(name)}",
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
        text=f"Sortiert nach Anzahl der Spiele. Winrate = Siege / Spiele. Build: {BOT_BUILD}"
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
# 📅 /session
# =========================================================
@session.command(
    name="create",
    description="Legt einen Termin mit Teilnehmern und Erinnerungen an"
)
@app_commands.guild_only()
async def session_create(interaction: discord.Interaction):
    if interaction.guild is None or interaction.channel is None:
        await interaction.response.send_message(
            "Dieser Befehl kann nur in einem Serverkanal verwendet werden.",
            ephemeral=True
        )
        return

    await interaction.response.send_modal(
        SessionCreateModal(
            owner_id=interaction.user.id,
            guild_id=interaction.guild.id,
            channel_id=interaction.channel.id
        )
    )


@session.command(
    name="show",
    description="Zeigt einen Termin öffentlich mit Teilnehmernamen, aber ohne Spieler-Pings"
)
@app_commands.guild_only()
async def session_show(interaction: discord.Interaction):
    await open_session_action_picker(
        interaction,
        action="show",
        require_manage=False
    )


@session.command(
    name="edit",
    description="Wählt einen Termin aus und bearbeitet seine Einstellungen"
)
@app_commands.guild_only()
async def session_edit(interaction: discord.Interaction):
    await open_session_action_picker(
        interaction,
        action="edit",
        require_manage=True
    )


@session.command(
    name="cancel",
    description="Wählt einen Termin aus, sagt ihn ab und stoppt seine Erinnerungen"
)
@app_commands.guild_only()
async def session_cancel(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True, thinking=True)

    try:
        selectable_records = await get_selectable_server_session_records(
            interaction,
            require_manage=True
        )
    except Exception as exc:
        await interaction.edit_original_response(
            content=f"Die Sessions konnten nicht geladen werden:\n```text\n{exc}\n```",
            view=None
        )
        return

    if not selectable_records:
        await interaction.edit_original_response(
            content=(
                "Es wurde weder eine aktive Bot-Session noch ein absagbares "
                "Discord-Event gefunden."
            ),
            view=None
        )
        return

    await interaction.edit_original_response(
        content="Wähle den Termin aus, den du absagen möchtest:",
        view=SessionCancelSelectView(
            owner_id=interaction.user.id,
            records=selectable_records[:25]
        )
    )


@session.command(
    name="remind",
    description="Wählt einen Termin aus und sendet eine Erinnerung"
)
@app_commands.guild_only()
async def session_remind(interaction: discord.Interaction):
    await open_session_action_picker(
        interaction,
        action="remind",
        require_manage=True
    )


@session.command(
    name="cleanup",
    description="Entfernt Duplikate und nicht mehr vorhandene Termine aus dem Sessions-Sheet"
)
@app_commands.guild_only()
async def session_cleanup(interaction: discord.Interaction):
    permissions = getattr(interaction.user, "guild_permissions", None)

    if not permissions or not permissions.manage_events:
        await interaction.response.send_message(
            "Du benötigst die Berechtigung **Events verwalten**.",
            ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True, thinking=True)

    try:
        plan = await build_session_cleanup_plan(interaction.guild)
    except Exception as exc:
        await interaction.edit_original_response(
            content=f"Die Bereinigung konnte nicht vorbereitet werden:\n```text\n{exc}\n```",
            view=None
        )
        return

    if not plan["rows_to_delete"]:
        await interaction.edit_original_response(
            content="Das Sessions-Sheet ist bereits sauber. Es wurden keine Zeilen gefunden.",
            view=None
        )
        return

    await interaction.edit_original_response(
        content=(
            f"Es würden **{len(plan['rows_to_delete'])}** Zeilen entfernt:\n"
            f"• **{plan['duplicate_count']}** redundante Zeilen zu vorhandenen Events\n"
            f"• **{plan['orphan_count']}** Zeilen ohne aktuell vorhandenes Discord-Event\n\n"
            "Aktive Discord-Events und jeweils eine zugehörige Sheet-Zeile bleiben erhalten."
        ),
        view=SessionCleanupConfirmView(interaction.user.id)
    )


# =========================================================
# 🚀 BOT START
# =========================================================
@client.event
async def on_ready():
    try:
        sort_sessions_sheet_by_start()
    except Exception as exc:
        print(f"Sessions-Sheet konnte beim Start nicht sortiert werden: {exc}")

    if not session_reminder_loop.is_running():
        session_reminder_loop.start()

    await tree.sync()
    print(f"Bot läuft als {client.user} | Build: {BOT_BUILD}")


client.run(TOKEN)
