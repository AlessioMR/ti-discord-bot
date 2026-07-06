import discord
from discord import app_commands
import gspread
from gspread.exceptions import WorksheetNotFound
from gspread.utils import rowcol_to_a1
from google.oauth2.service_account import Credentials
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
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
BOT_BUILD = "multi-winners-external-filter-v6"

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
        "A1:F1",
        [BOTDATA_HEADERS]
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
            f"A2:{end_cell}",
            sorted_rows,
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
        f"A{next_row}:{end_cell}",
        [row],
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
# 🚀 BOT START
# =========================================================
@client.event
async def on_ready():
    await tree.sync()
    print(f"Bot läuft als {client.user}")


client.run(TOKEN)
