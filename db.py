import aiosqlite
import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "data" / "f95tracker.db"
DATA_DIR = Path(__file__).parent / "data"
IMAGES_DIR = DATA_DIR / "images"

SCHEMA_VERSION = 2

conn: aiosqlite.Connection = None

_MIGRATIONS = {}


def migration(version):
    def decorator(func):
        _MIGRATIONS[version] = func
        return func
    return decorator


@migration(1)
async def _migrate_v0_to_v1(conn):
    """Initial schema creation for fresh databases."""
    await conn.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            _ INTEGER PRIMARY KEY CHECK (_=0),
            auto_refresh_interval INTEGER DEFAULT 30,
            refresh_archived_games INTEGER DEFAULT 1,
            refresh_completed_games INTEGER DEFAULT 1,
            max_connections INTEGER DEFAULT 10,
            request_timeout INTEGER DEFAULT 30,
            f95zone_username TEXT DEFAULT '',
            f95zone_password TEXT DEFAULT ''
        );

        INSERT OR IGNORE INTO settings (_) VALUES (0);

        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY,
            custom INTEGER DEFAULT NULL,
            name TEXT DEFAULT '',
            version TEXT DEFAULT 'Unchecked',
            developer TEXT DEFAULT '',
            type INTEGER DEFAULT 23,
            status INTEGER DEFAULT 5,
            url TEXT DEFAULT '',
            added_on INTEGER DEFAULT 0,
            last_updated INTEGER DEFAULT 0,
            last_full_check INTEGER DEFAULT 0,
            last_check_version TEXT DEFAULT '',
            last_launched INTEGER DEFAULT 0,
            score REAL DEFAULT 0,
            votes INTEGER DEFAULT 0,
            rating INTEGER DEFAULT 0,
            finished TEXT DEFAULT '',
            installed TEXT DEFAULT '',
            updated INTEGER DEFAULT 0,
            archived INTEGER DEFAULT 0,
            description TEXT DEFAULT '',
            changelog TEXT DEFAULT '',
            tags TEXT DEFAULT '[]',
            unknown_tags TEXT DEFAULT '[]',
            unknown_tags_flag INTEGER DEFAULT 0,
            labels TEXT DEFAULT '[]',
            tab INTEGER DEFAULT NULL,
            notes TEXT DEFAULT '',
            image_url TEXT DEFAULT '',
            previews_urls TEXT DEFAULT '[]',
            downloads TEXT DEFAULT '[]',
            reviews_total INTEGER DEFAULT 0,
            reviews TEXT DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS cookies (
            key TEXT PRIMARY KEY,
            value TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS labels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT DEFAULT '',
            color TEXT DEFAULT '#696969'
        );

        CREATE TABLE IF NOT EXISTS tabs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT DEFAULT '',
            icon TEXT DEFAULT '📁',
            color TEXT DEFAULT NULL,
            position INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS timeline_events (
            game_id INTEGER DEFAULT NULL,
            timestamp INTEGER DEFAULT 0,
            arguments TEXT DEFAULT '[]',
            type INTEGER DEFAULT 1
        );
    """)
    await conn.commit()


@migration(2)
async def _migrate_v1_to_v2(conn):
    """Add last_successful_refresh column to settings."""
    try:
        await conn.execute(
            "ALTER TABLE settings ADD COLUMN last_successful_refresh INTEGER DEFAULT 0"
        )
        await conn.commit()
    except aiosqlite.OperationalError:
        await conn.commit()


async def _get_db_version(conn) -> int:
    cursor = await conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='settings'"
    )
    if not await cursor.fetchone():
        return 0

    try:
        cursor = await conn.execute("PRAGMA table_info(settings)")
        columns = {row[1] for row in await cursor.fetchall()}
        if "schema_version" not in columns:
            return 1
    except Exception:
        return 1

    cursor = await conn.execute("SELECT schema_version FROM settings WHERE _=0")
    row = await cursor.fetchone()
    return row[0] if row else 1


async def _run_migrations(conn):
    current = await _get_db_version(conn)
    if current >= SCHEMA_VERSION:
        logger.info(f"DB schema is up to date (version {current})")
        return

    if current == 0:
        logger.info("Initializing fresh database")

    for version in range(current + 1, SCHEMA_VERSION + 1):
        if version not in _MIGRATIONS:
            logger.error(f"No migration found for version {version}")
            raise RuntimeError(f"Missing migration for schema version {version}")
        logger.info(f"Running DB migration: v{version - 1} -> v{version}")
        await _MIGRATIONS[version](conn)

    try:
        await conn.execute(
            "ALTER TABLE settings ADD COLUMN schema_version INTEGER DEFAULT 0"
        )
        await conn.commit()
    except aiosqlite.OperationalError:
        await conn.commit()

    await conn.execute(
        "UPDATE settings SET schema_version = ? WHERE _ = 0", (SCHEMA_VERSION,)
    )
    await conn.commit()
    logger.info(f"DB schema upgraded to version {SCHEMA_VERSION}")


async def init_db():
    global conn
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(str(DB_PATH))
    conn.row_factory = aiosqlite.Row

    await _run_migrations(conn)


async def close_db():
    global conn
    if conn:
        await conn.commit()
        await conn.close()


async def get_settings() -> dict:
    cursor = await conn.execute("SELECT * FROM settings")
    row = await cursor.fetchone()
    return dict(row)


async def update_settings(**kwargs):
    sets = []
    vals = []
    for k, v in kwargs.items():
        sets.append(f"{k} = ?")
        vals.append(v)
    if sets:
        await conn.execute(f"UPDATE settings SET {', '.join(sets)} WHERE _=0", vals)
        await conn.commit()


async def get_cookies() -> dict:
    cursor = await conn.execute("SELECT key, value FROM cookies")
    rows = await cursor.fetchall()
    return {row["key"]: row["value"] for row in rows}


async def update_cookies(cookies: dict):
    await conn.execute("DELETE FROM cookies")
    for k, v in cookies.items():
        await conn.execute("INSERT INTO cookies (key, value) VALUES (?, ?)", (k, v))
    await conn.commit()


async def get_all_games() -> list[dict]:
    cursor = await conn.execute("SELECT * FROM games ORDER BY added_on DESC")
    rows = await cursor.fetchall()
    return [_game_row_to_dict(r) for r in rows]


async def get_game(game_id: int) -> dict | None:
    cursor = await conn.execute("SELECT * FROM games WHERE id=?", (game_id,))
    row = await cursor.fetchone()
    if row:
        return _game_row_to_dict(row)
    return None


async def create_game(
    game_id: int, custom: bool = False, name: str = "", url: str = ""
):
    now = int(time.time())
    status = 6 if custom else 5
    await conn.execute(
        """INSERT OR IGNORE INTO games
           (id, custom, name, url, added_on, status)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            game_id,
            int(custom),
            name or (f"Custom game ({game_id})" if custom else f"Unknown ({game_id})"),
            url,
            now,
            status,
        ),
    )
    await conn.commit()
    return game_id


async def update_game(game_id: int, **kwargs):
    json_fields = {
        "tags",
        "unknown_tags",
        "labels",
        "previews_urls",
        "downloads",
        "reviews",
    }
    sets = []
    vals = []
    for k, v in kwargs.items():
        if k in json_fields:
            v = json.dumps(v)
        elif isinstance(v, bool):
            v = int(v)
        elif v is None and k != "tab":
            continue
        sets.append(f"{k} = ?")
        vals.append(v)
    if sets:
        vals.append(game_id)
        await conn.execute(f"UPDATE games SET {', '.join(sets)} WHERE id=?", vals)
        await conn.commit()


async def delete_game(game_id: int):
    await conn.execute("DELETE FROM games WHERE id=?", (game_id,))
    await conn.execute("DELETE FROM timeline_events WHERE game_id=?", (game_id,))
    import shutil

    for img in IMAGES_DIR.glob(f"{game_id}.*"):
        try:
            img.unlink()
        except Exception:
            pass
    await conn.commit()


async def get_labels() -> list[dict]:
    cursor = await conn.execute("SELECT * FROM labels ORDER BY id")
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def create_label(name: str = "", color: str = "#696969") -> int:
    cursor = await conn.execute(
        "INSERT INTO labels (name, color) VALUES (?, ?)", (name, color)
    )
    await conn.commit()
    return cursor.lastrowid


async def update_label(label_id: int, **kwargs):
    sets = []
    vals = []
    for k, v in kwargs.items():
        sets.append(f"{k} = ?")
        vals.append(v)
    if sets:
        vals.append(label_id)
        await conn.execute(f"UPDATE labels SET {', '.join(sets)} WHERE id=?", vals)
        await conn.commit()


async def delete_label(label_id: int):
    await conn.execute("DELETE FROM labels WHERE id=?", (label_id,))
    await conn.execute("DELETE FROM timeline_events WHERE game_id=?", (label_id,))
    games = await get_all_games()
    for game in games:
        if label_id in game.get("labels", []):
            game["labels"].remove(label_id)
            await update_game(game["id"], labels=game["labels"])
    await conn.commit()


async def get_tabs() -> list[dict]:
    cursor = await conn.execute("SELECT * FROM tabs ORDER BY position")
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def create_tab(name: str = "", icon: str = "📁") -> int:
    cursor = await conn.execute(
        "INSERT INTO tabs (name, icon, position) VALUES (?, ?, 0)", (name, icon)
    )
    await conn.commit()
    return cursor.lastrowid


async def update_tab(tab_id: int, **kwargs):
    sets = []
    vals = []
    for k, v in kwargs.items():
        sets.append(f"{k} = ?")
        vals.append(v)
    if sets:
        vals.append(tab_id)
        await conn.execute(f"UPDATE tabs SET {', '.join(sets)} WHERE id=?", vals)
        await conn.commit()


async def delete_tab(tab_id: int):
    await conn.execute("DELETE FROM tabs WHERE id=?", (tab_id,))
    await conn.commit()


async def create_timeline_event(game_id: int, event_type: int, arguments: list[str]):
    await conn.execute(
        "INSERT INTO timeline_events (game_id, timestamp, arguments, type) VALUES (?, ?, ?, ?)",
        (game_id, int(time.time()), json.dumps(arguments), event_type),
    )
    await conn.commit()


async def get_timeline_events(game_id: int) -> list[dict]:
    cursor = await conn.execute(
        "SELECT * FROM timeline_events WHERE game_id=? ORDER BY timestamp DESC",
        (game_id,),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_games_count() -> int:
    cursor = await conn.execute("SELECT COUNT(*) as cnt FROM games")
    row = await cursor.fetchone()
    return row["cnt"]


def _game_row_to_dict(row) -> dict:
    d = dict(row)
    for field in (
        "tags",
        "unknown_tags",
        "labels",
        "previews_urls",
        "downloads",
        "reviews",
    ):
        val = d.get(field, "[]")
        if isinstance(val, str):
            try:
                d[field] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                d[field] = []
    return d
