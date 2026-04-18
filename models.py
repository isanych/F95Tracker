from enum import IntEnum
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class Status(IntEnum):
    Normal = 1
    Completed = 2
    OnHold = 3
    Abandoned = 4
    Unchecked = 5
    Custom = 6


STATUS_NAMES = {v: k for k, v in Status.__members__.items()}
STATUS_COLORS = {
    Status.Normal: "#5a9e5a",
    Status.Completed: "#00de00",
    Status.OnHold: "#0080f0",
    Status.Abandoned: "#de3333",
    Status.Unchecked: "#808080",
    Status.Custom: "#f28000",
}


class GameType(IntEnum):
    ADRIFT = 2
    Flash = 4
    HTML = 5
    Java = 6
    Others = 9
    QSP = 10
    RAGS = 11
    Cheat_Mod = 3
    Mod = 8
    READ_ME = 12
    Request = 15
    Tutorial = 17
    Tool = 18
    RenPy = 14
    RPGM = 13
    Unity = 19
    Unreal_Eng = 20
    WebGL = 21
    Wolf_RPG = 22
    Tads = 16
    CG = 30
    Collection = 7
    Comics = 24
    GIF = 25
    Manga = 26
    Pinup = 27
    SiteRip = 28
    Video = 29
    Misc = 1
    Unchecked = 23


TYPE_COLORS = {
    GameType.ADRIFT: "#2196F3",
    GameType.Flash: "#616161",
    GameType.HTML: "#689F38",
    GameType.Java: "#52A6B0",
    GameType.Others: "#8BC34A",
    GameType.QSP: "#D32F2F",
    GameType.RAGS: "#FF9800",
    GameType.Cheat_Mod: "#D32F2F",
    GameType.Mod: "#BA4545",
    GameType.READ_ME: "#DC143C",
    GameType.Request: "#D32F2F",
    GameType.Tutorial: "#EC5555",
    GameType.Tool: "#EC5555",
    GameType.RenPy: "#B069E8",
    GameType.RPGM: "#2196F3",
    GameType.Unity: "#FE5901",
    GameType.Unreal_Eng: "#0D47A1",
    GameType.WebGL: "#FE5901",
    GameType.Wolf_RPG: "#4CAF50",
    GameType.Tads: "#2196F3",
    GameType.CG: "#DFCB37",
    GameType.Collection: "#616161",
    GameType.Comics: "#FF9800",
    GameType.GIF: "#03A9F4",
    GameType.Manga: "#0FB2FC",
    GameType.Pinup: "#2196F3",
    GameType.SiteRip: "#8BC34A",
    GameType.Video: "#FF9800",
    GameType.Misc: "#B8B00C",
    GameType.Unchecked: "#393939",
}

CATEGORY_MAP = {
    "games": [
        GameType.ADRIFT,
        GameType.Flash,
        GameType.HTML,
        GameType.Java,
        GameType.Others,
        GameType.QSP,
        GameType.RAGS,
        GameType.RenPy,
        GameType.RPGM,
        GameType.Unity,
        GameType.Unreal_Eng,
        GameType.WebGL,
        GameType.Wolf_RPG,
        GameType.Tads,
    ],
    "media": [
        GameType.CG,
        GameType.Collection,
        GameType.Comics,
        GameType.GIF,
        GameType.Manga,
        GameType.Pinup,
        GameType.SiteRip,
        GameType.Video,
    ],
    "misc": [
        GameType.Cheat_Mod,
        GameType.Mod,
        GameType.READ_ME,
        GameType.Request,
        GameType.Tutorial,
        GameType.Tool,
        GameType.Misc,
    ],
}

TYPE_NAMES = {v: k for k, v in GameType.__members__.items()}


class TimelineEventType(IntEnum):
    GameAdded = 1
    GameLaunched = 2
    GameFinished = 3
    GameInstalled = 4
    ChangedName = 5
    ChangedStatus = 6
    ChangedVersion = 7
    ChangedDeveloper = 8
    ChangedType = 9
    TagsAdded = 10
    TagsRemoved = 11
    ScoreIncreased = 12
    ScoreDecreased = 13
    RecheckExpired = 14
    RecheckUserReq = 15


TIMELINE_TEMPLATES = {
    TimelineEventType.GameAdded: "Added to the library",
    TimelineEventType.GameLaunched: "Launched {}",
    TimelineEventType.GameFinished: "Finished {}",
    TimelineEventType.GameInstalled: "Installed {}",
    TimelineEventType.ChangedName: 'Name changed from "{}" to "{}"',
    TimelineEventType.ChangedStatus: 'Status changed from "{}" to "{}"',
    TimelineEventType.ChangedVersion: 'Version changed from "{}" to "{}"',
    TimelineEventType.ChangedDeveloper: 'Developer changed from "{}" to "{}"',
    TimelineEventType.ChangedType: 'Type changed from "{}" to "{}"',
    TimelineEventType.TagsAdded: "Tags were added: {}",
    TimelineEventType.TagsRemoved: "Tags were removed: {}",
    TimelineEventType.ScoreIncreased: "Forum score increased from {} ({}) to {} ({})",
    TimelineEventType.ScoreDecreased: "Forum score decreased from {} ({}) to {} ({})",
    TimelineEventType.RecheckExpired: "Forcefully performed a full recheck because game has remained idle for {} day(s)",
    TimelineEventType.RecheckUserReq: "Forcefully performed a full recheck requested by user",
}

TIMELINE_ICONS = {
    TimelineEventType.GameAdded: "🔔",
    TimelineEventType.GameLaunched: "▶️",
    TimelineEventType.GameFinished: "🏁",
    TimelineEventType.GameInstalled: "📥",
    TimelineEventType.ChangedName: "✏️",
    TimelineEventType.ChangedStatus: "⚡",
    TimelineEventType.ChangedVersion: "⭐",
    TimelineEventType.ChangedDeveloper: "👤",
    TimelineEventType.ChangedType: "🔷",
    TimelineEventType.TagsAdded: "➕",
    TimelineEventType.TagsRemoved: "➖",
    TimelineEventType.ScoreIncreased: "👍",
    TimelineEventType.ScoreDecreased: "👎",
    TimelineEventType.RecheckExpired: "⏰",
    TimelineEventType.RecheckUserReq: "🔄",
}


TAG_TEXT = {
    1: "2d game",
    2: "2dcg",
    3: "3d game",
    4: "3dcg",
    5: "adventure",
    6: "ahegao",
    7: "anal sex",
    8: "animated",
    9: "asset-addon",
    10: "asset-ai-shoujo",
    11: "asset-animal",
    12: "asset-animation",
    13: "asset-audio",
    14: "asset-bundle",
    15: "asset-character",
    16: "asset-clothing",
    17: "asset-environment",
    18: "asset-expression",
    19: "asset-hair",
    20: "asset-hdri",
    21: "asset-honey-select",
    22: "asset-honey-select2",
    23: "asset-koikatu",
    24: "asset-light",
    25: "asset-morph",
    26: "asset-plugin",
    27: "asset-pose",
    28: "asset-prop",
    29: "asset-script",
    30: "asset-shader",
    31: "asset-texture",
    32: "asset-utility",
    33: "asset-vehicle",
    34: "bdsm",
    35: "bestiality",
    36: "big ass",
    37: "big tits",
    38: "blackmail",
    39: "bukkake",
    40: "censored",
    41: "character creation",
    42: "cheating",
    43: "combat",
    44: "corruption",
    45: "cosplay",
    46: "creampie",
    47: "dating sim",
    48: "dilf",
    49: "drugs",
    50: "dystopian setting",
    51: "exhibitionism",
    52: "fantasy",
    53: "female domination",
    54: "female protagonist",
    55: "footjob",
    56: "furry",
    57: "futa/trans",
    58: "futa/trans protagonist",
    59: "gay",
    60: "graphic violence",
    61: "groping",
    62: "group sex",
    63: "handjob",
    64: "harem",
    65: "horror",
    66: "humiliation",
    67: "humor",
    68: "incest",
    69: "internal view",
    70: "interracial",
    71: "japanese game",
    72: "kinetic novel",
    73: "lactation",
    74: "lesbian",
    75: "loli",
    76: "male domination",
    77: "male protagonist",
    78: "management",
    79: "masturbation",
    80: "milf",
    81: "mind control",
    82: "mobile game",
    83: "monster",
    84: "monster girl",
    85: "multiple endings",
    86: "multiple penetration",
    87: "multiple protagonist",
    88: "necrophilia",
    89: "no sexual content",
    90: "netorare",
    91: "oral sex",
    92: "paranormal",
    93: "parody",
    94: "platformer",
    95: "point & click",
    96: "possession",
    97: "pov",
    98: "pregnancy",
    99: "prostitution",
    100: "puzzle",
    101: "rape",
    102: "real porn",
    103: "religion",
    104: "romance",
    105: "rpg",
    106: "sandbox",
    107: "scat",
    108: "school setting",
    109: "sci-fi",
    110: "sex toys",
    111: "sexual harassment",
    112: "shooter",
    113: "shota",
    114: "side-scroller",
    115: "simulator",
    116: "sissification",
    117: "slave",
    118: "sleep sex",
    119: "spanking",
    120: "strategy",
    121: "stripping",
    122: "superpowers",
    123: "swinging",
    124: "teasing",
    125: "tentacles",
    126: "text based",
    127: "titfuck",
    128: "trainer",
    129: "transformation",
    130: "trap",
    131: "turn based combat",
    132: "twins",
    133: "urination",
    134: "vaginal sex",
    135: "virgin",
    136: "virtual reality",
    137: "voiced",
    138: "vore",
    139: "voyeurism",
    140: "ai cg",
    141: "asset-daz-gen2",
    142: "asset-daz-gen3",
    143: "asset-daz-gen8",
    144: "asset-daz-gen81",
    145: "asset-daz-gen9",
    146: "asset-female",
    147: "asset-male",
    148: "asset-nonbinary",
    149: "asset-scene",
    150: "asset-playhome",
    151: "asset-daz-gen1",
    152: "asset-daz-m4",
    153: "asset-daz-v4",
}


class Tag(IntEnum):
    _2d_game = 1
    _2dcg = 2
    _3d_game = 3
    _3dcg = 4


def tag_text(tag_id):
    return TAG_TEXT.get(tag_id, f"unknown({tag_id})")


class GameRead(BaseModel):
    id: int
    custom: bool = False
    name: str = ""
    version: str = "Unchecked"
    developer: str = ""
    type: int = GameType.Unchecked
    status: int = Status.Unchecked
    url: str = ""
    added_on: int = 0
    last_updated: int = 0
    last_full_check: int = 0
    last_check_version: str = ""
    score: float = 0
    votes: int = 0
    rating: int = 0
    finished: str = ""
    installed: str = ""
    updated: bool = False
    archived: bool = False
    description: str = ""
    changelog: str = ""
    tags: list[int] = []
    unknown_tags: list[str] = []
    labels: list[int] = []
    tab: Optional[int] = None
    notes: str = ""
    image_url: str = ""
    previews_urls: list[str] = []
    downloads: list = []
    reviews_total: int = 0
    reviews: list = []


class GameCreate(BaseModel):
    url: Optional[str] = None
    custom: bool = False
    name: Optional[str] = None


class SearchResultModel(BaseModel):
    title: str
    creator: str
    url: str
    id: int


class LabelRead(BaseModel):
    id: int
    name: str
    color: str


class LabelCreate(BaseModel):
    name: str = ""
    color: str = "#696969"


class TabRead(BaseModel):
    id: int
    name: str
    icon: str = "📁"
    color: Optional[str] = None
    position: int = 0


class TabCreate(BaseModel):
    name: str = ""
    icon: str = "📁"


class SettingsRead(BaseModel):
    auto_refresh_interval: int = 30
    refresh_archived_games: bool = True
    refresh_completed_games: bool = True
    max_connections: int = 10
    request_timeout: int = 30
    f95zone_username: str = ""
    f95zone_password: str = ""


class TimelineEventRead(BaseModel):
    game_id: int
    timestamp: int
    arguments: list[str]
    type: int
