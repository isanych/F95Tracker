import asyncio
import time
import json
from db import (
    get_all_games,
    get_settings,
    get_cookies,
    update_game,
    update_settings,
    create_timeline_event,
)
from models import (
    Status,
    TimelineEventType,
    TYPE_NAMES,
    STATUS_NAMES,
    TAG_TEXT,
    GameType,
)
from f95api import fast_check, full_check as api_full_check, get_game_image

_refresh_task: asyncio.Task = None
_refresh_running = False
_refresh_progress = {"total": 0, "done": 0, "status": "idle", "updated": []}


def get_refresh_status():
    return _refresh_progress.copy()


async def refresh_games(force_full: bool = False):
    global _refresh_running
    if _refresh_running:
        return _refresh_progress

    _refresh_running = True
    _refresh_progress.update(
        {"total": 0, "done": 0, "status": "running", "updated": []}
    )

    try:
        games = await get_all_games()
        settings = await get_settings()
        non_custom = [g for g in games if not g.get("custom")]

        if not force_full and not settings.get("refresh_archived_games", True):
            non_custom = [g for g in non_custom if not g.get("archived")]
        if not force_full and not settings.get("refresh_completed_games", True):
            non_custom = [g for g in non_custom if g.get("status") != Status.Completed]

        game_ids = [g["id"] for g in non_custom]
        id_to_game = {g["id"]: g for g in non_custom}

        _refresh_progress["total"] = len(game_ids)

        if not game_ids:
            _refresh_progress["status"] = "done"
            _refresh_running = False
            return _refresh_progress

        # Fast check in batches of 10
        all_last_changes = {}
        for i in range(0, len(game_ids), 10):
            batch = game_ids[i : i + 10]
            result = await fast_check(batch)
            if result:
                all_last_changes.update(result)

        need_full = []
        for gid in game_ids:
            game = id_to_game[gid]
            last_changed = all_last_changes.get(str(gid), 0)
            if last_changed == 0:
                continue
            if (
                force_full
                or game.get("status") == Status.Unchecked
                or last_changed > game.get("last_full_check", 0)
                or not game.get("image_url")
                or not game.get("last_check_version")
            ):
                need_full.append((gid, last_changed))

        # Full check with concurrency limit
        sem = asyncio.Semaphore(settings.get("max_connections", 10))
        _refresh_progress["total"] = len(game_ids)

        async def do_full_check(gid, ts):
            async with sem:
                data = await api_full_check(gid, ts)
                if data is None:
                    _refresh_progress["done"] += 1
                    return
                try:
                    await _apply_full_check(gid, data, ts)
                except Exception:
                    pass
                _refresh_progress["done"] += 1

        tasks = [do_full_check(gid, ts) for gid, ts in need_full]

        # Also count fast check progress for games that didn't need full check
        fast_only = len(game_ids) - len(need_full)
        _refresh_progress["done"] = fast_only

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        _refresh_progress["status"] = "done"
        await update_settings(last_successful_refresh=int(time.time()))

    except Exception as e:
        _refresh_progress["status"] = f"error: {str(e)}"
    finally:
        _refresh_running = False

    return _refresh_progress


async def _apply_full_check(game_id: int, data: dict, last_changed: int):
    game = await _get_game_raw(game_id)
    if not game:
        return

    version = data.get("version", "")
    if not version:
        version = "N/A"

    old_name = game.get("name", "")
    old_version = game.get("version", "")
    old_status = game.get("status", Status.Unchecked)

    old_tags = set(
        json.loads(game.get("tags", "[]"))
        if isinstance(game.get("tags"), str)
        else game.get("tags", [])
    )
    new_tags = set(
        json.loads(data.get("tags", "[]"))
        if isinstance(data.get("tags", "[]"), str)
        else data.get("tags", [])
    )

    updates = {
        "name": data.get("name", game.get("name", "")),
        "version": version,
        "developer": data.get("developer", game.get("developer", "")),
        "type": int(data.get("type", game.get("type", 23))),
        "status": int(data.get("status", game.get("status", 5))),
        "last_updated": int(data.get("last_updated", game.get("last_updated", 0))),
        "last_full_check": last_changed,
        "last_check_version": "1.0.0",
        "score": float(data.get("score", game.get("score", 0))),
        "votes": int(data.get("votes", game.get("votes", 0))),
        "description": data.get("description", game.get("description", "")),
        "changelog": data.get("changelog", game.get("changelog", "")),
        "tags": json.loads(data.get("tags", "[]"))
        if isinstance(data.get("tags"), str)
        else data.get("tags", []),
        "unknown_tags": json.loads(data.get("unknown_tags", "[]"))
        if isinstance(data.get("unknown_tags"), str)
        else data.get("unknown_tags", []),
        "image_url": data.get("image_url", game.get("image_url", "")),
        "previews_urls": json.loads(data.get("previews_urls", "[]"))
        if isinstance(data.get("previews_urls"), str)
        else data.get("previews_urls", []),
        "downloads": json.loads(data.get("downloads", "[]"))
        if isinstance(data.get("downloads"), str)
        else data.get("downloads", []),
        "reviews_total": int(data.get("reviews_total", "0")),
        "url": f"https://f95zone.to/threads/{game_id}",
    }

    finished = game.get("finished", "")
    installed = game.get("installed", "")
    updated = bool(game.get("updated", False))

    if old_status != Status.Unchecked and old_status != Status.Custom:
        if version != old_version and not game.get("archived"):
            updated = True

    if game.get("status") == Status.Unchecked:
        if old_version == finished:
            finished = version
        if old_version == installed:
            installed = version

    updates["finished"] = finished
    updates["installed"] = installed
    updates["updated"] = updated

    await update_game(game_id, **updates)

    image_url = updates.get("image_url", "")
    if image_url and image_url.startswith("http"):
        await _download_image(game_id, image_url)

    # Timeline events
    if old_status not in (Status.Unchecked, Status.Custom):
        new_status_val = int(data.get("status", 5))
        if data.get("name") != old_name:
            await create_timeline_event(
                game_id, TimelineEventType.ChangedName, [old_name, data.get("name", "")]
            )
        if new_status_val != old_status:
            await create_timeline_event(
                game_id,
                TimelineEventType.ChangedStatus,
                [
                    STATUS_NAMES.get(old_status, str(old_status)),
                    STATUS_NAMES.get(new_status_val, str(new_status_val)),
                ],
            )
        if version != old_version:
            await create_timeline_event(
                game_id, TimelineEventType.ChangedVersion, [old_version, version]
            )

    if updated:
        _refresh_progress["updated"].append(
            {
                "id": game_id,
                "name": data.get("name", game.get("name", "")),
                "old_version": old_version,
                "new_version": version,
            }
        )


async def _get_game_raw(game_id: int):
    from db import conn

    cursor = await conn.execute("SELECT * FROM games WHERE id=?", (game_id,))
    row = await cursor.fetchone()
    if row:
        from db import _game_row_to_dict

        return _game_row_to_dict(row)
    return None


async def start_auto_refresh():
    global _refresh_task
    settings = await get_settings()
    interval = settings.get("auto_refresh_interval", 30)

    async def _loop():
        while True:
            await asyncio.sleep(interval * 60)
            try:
                await refresh_games()
            except Exception:
                pass

    _refresh_task = asyncio.create_task(_loop())


def stop_auto_refresh():
    global _refresh_task
    if _refresh_task and not _refresh_task.done():
        _refresh_task.cancel()


async def check_single_game(game_id: int):
    """Force a full recheck of a single game."""
    result = await fast_check([game_id])
    last_changed = result.get(str(game_id), 0)
    if last_changed > 0:
        data = await api_full_check(game_id, last_changed)
        if data:
            await _apply_full_check(game_id, data, last_changed)
            return True
    return False


async def _download_image(game_id: int, image_url: str):
    """Download and save game header image locally."""
    from pathlib import Path

    images_dir = Path(__file__).parent / "data" / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    existing = None
    for ext in ("png", "jpg", "jpeg", "gif", "webp"):
        if (images_dir / f"{game_id}.{ext}").exists():
            existing = ext
            break

    if existing and existing in ("png", "gif"):
        return

    try:
        data = await get_game_image(image_url)
        if not data:
            return
        for ext in ("jpeg", "jpg", "png", "webp", "gif"):
            if data.lower().startswith(b"%pdf") or (
                ext == "png" and b"PNG" in data[:8]
            ):
                pass
        if b"\x89PNG" in data[:8]:
            ext = "png"
        elif data.startswith(b"\xff\xd8\xff"):
            ext = "jpg"
        elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
            ext = "webp"
        else:
            ext = "jpg"

        path = images_dir / f"{game_id}.{ext}"
        with open(path, "wb") as f:
            f.write(data)
    except Exception:
        pass
