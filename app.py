import asyncio
import httpx
import json
import os
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Form, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import db
import f95api
import background
from models import (
    Status,
    GameType,
    STATUS_NAMES,
    TYPE_NAMES,
    STATUS_COLORS,
    TYPE_COLORS,
    TAG_TEXT,
    TIMELINE_TEMPLATES,
    TIMELINE_ICONS,
    TimelineEventType,
    CATEGORY_MAP,
)


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    global _proxy_client
    await db.init_db()
    await f95api.get_client()
    _proxy_client = httpx.AsyncClient(
        timeout=60.0,
        follow_redirects=False,
        headers={"User-Agent": "F95Tracker/1.0"},
    )
    await background.start_auto_refresh()
    yield
    background.stop_auto_refresh()
    await f95api.close_client()
    if _proxy_client and not _proxy_client.is_closed:
        await _proxy_client.aclose()
    await db.close_db()


app = FastAPI(title="F95Tracker", lifespan=app_lifespan)

static_path = Path(__file__).parent / "static"
templates_path = Path(__file__).parent / "templates"
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
templates = Jinja2Templates(directory=str(templates_path))

PROXY_PREFIX = "/proxy"

_proxy_client: httpx.AsyncClient = None


def _rewrite_proxied_content(content: bytes, content_type: str) -> bytes:
    """Rewrite URLs in proxied HTML/CSS so they go through /proxy.

    JavaScript is intentionally NOT rewritten: replacing URL fragments inside JS
    easily corrupts regex literals, string escapes and minified code, breaking
    execution of the entire script. We only handle HTML and CSS here.
    """
    is_rewritable = "text/html" in content_type or "text/css" in content_type
    if not is_rewritable:
        return content

    text = content.decode("utf-8", errors="replace")

    if "text/html" in content_type:
        # Unescape forward-slash escaping ONLY inside JSON strings (double-quoted).
        # This catches XF config blocks and JSON-LD data without corrupting JS regex
        # literals like /\/page-\d+$/ where \/ is a legitimate escaped slash.
        def _unescape_json_slashes(m):
            return '"' + m.group(1).replace("\\/", "/") + '"'
        text = re.sub(r'"((?:[^"\\]|\\.)*)"', _unescape_json_slashes, text)

        # Primary domains: replace with /proxy prefix (same server paths)
        for domain in ("f95zone.to", "f95zone.isany.ch"):
            text = text.replace(f"https://{domain}", PROXY_PREFIX)
            text = text.replace(f"http://{domain}", PROXY_PREFIX)
            text = text.replace(f"//{domain}", PROXY_PREFIX)

        # Attachments server: different host, encode with __att__ sentinel
        ATT_PREFIX = f"{PROXY_PREFIX}/__att__"
        att_domain = "attachments.f95zone.to"
        text = text.replace(f"https://{att_domain}", ATT_PREFIX)
        text = text.replace(f"http://{att_domain}", ATT_PREFIX)
        text = text.replace(f"//{att_domain}", ATT_PREFIX)

        text = re.sub(
            r'''((?:href|src|srcset|action|data-[a-z-]*?(?:url|href|src)|poster|content))=["']/(?!proxy/|/)''',
            r'\1="/proxy/',
            text,
        )
        text = re.sub(
            r'''(["'])(/(?!proxy/|/)[^"']*\.[a-z]{2,5}(?:[?#;][^"']*)?)''',
            r'\1/proxy\2',
            text,
        )
        text = re.sub(
            r'''url\((['"]?)/(?!proxy/|/)''',
            lambda m: f'url({m.group(1)}/proxy/',
            text,
        )
        text = re.sub(
            r"url\(&#39;/(?!proxy/|/)",
            "url(&#39;/proxy/",
            text,
        )
        text = re.sub(
            r'url\(&quot;/(?!proxy/|/)',
            "url(&quot;/proxy/",
            text,
        )
        text = re.sub(
            r'<meta[^>]*http-equiv=["\']Content-Security-Policy["\'][^>]*/?>',
            '',
            text,
            flags=re.IGNORECASE,
        )

    elif "text/css" in content_type:
        # CSS may reference the primary f95zone hosts for fonts/images
        for domain in ("f95zone.to", "f95zone.isany.ch"):
            text = text.replace(f"https://{domain}", PROXY_PREFIX)
            text = text.replace(f"http://{domain}", PROXY_PREFIX)
            text = text.replace(f"//{domain}", PROXY_PREFIX)
        text = re.sub(
            r'''url\((['"]?)/(?!proxy/|/)''',
            lambda m: f'url({m.group(1)}/proxy/',
            text,
        )

    return text.encode("utf-8", errors="replace")


async def _proxy_request(request: Request, path: str) -> Response:
    global _proxy_client

    if _proxy_client is None or _proxy_client.is_closed:
        _proxy_client = httpx.AsyncClient(
            timeout=60.0,
            follow_redirects=False,
            headers={"User-Agent": "F95Tracker/1.0"},
        )

    cookies = await db.get_cookies()

    # Route attachment proxy sentinel to the real attachments server
    ATT_SENTINEL = "__att__"
    ATT_HOST = "https://attachments.f95zone.to"
    if path.startswith(f"{ATT_SENTINEL}/"):
        target_domain = ATT_HOST
        path = path[len(f"{ATT_SENTINEL}/"):]
    else:
        target_domain = f95api.F95_HOST

    target_url = f"{target_domain}/{path}" if path else f"{target_domain}/"
    if request.url.query:
        target_url += f"?{request.url.query}"

    fwd_headers = {
        "User-Agent": request.headers.get("user-agent", "F95Tracker/1.0"),
        "Referer": f"{target_domain}/",
        "Accept": request.headers.get(
            "accept",
            "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        ),
        "Accept-Language": request.headers.get("accept-language", "en-US,en;q=0.5"),
    }
    if request.method in ("POST", "PUT", "PATCH"):
        ct = request.headers.get("content-type")
        if ct:
            fwd_headers["Content-Type"] = ct

    body = await request.body()
    if request.method in ("GET", "HEAD"):
        body = None

    try:
        resp = await _proxy_client.request(
            request.method,
            target_url,
            headers=fwd_headers,
            cookies=cookies if cookies else None,
            content=body,
        )
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Proxy error: {str(e)}")

    if resp.status_code in (301, 302, 303, 307, 308):
        location = resp.headers.get("location", "")
        if location:
            for domain in ("f95zone.to", "f95zone.isany.ch"):
                location = location.replace(f"https://{domain}", PROXY_PREFIX)
                location = location.replace(f"http://{domain}", PROXY_PREFIX)
                location = location.replace(f"//{domain}", PROXY_PREFIX)
            for domain in ("attachments.f95zone.to",):
                location = location.replace(
                    f"https://{domain}", f"{PROXY_PREFIX}/__att__"
                )
                location = location.replace(
                    f"http://{domain}", f"{PROXY_PREFIX}/__att__"
                )
                location = location.replace(
                    f"//{domain}", f"{PROXY_PREFIX}/__att__"
                )
            if location.startswith("/") and not location.startswith(PROXY_PREFIX):
                location = f"{PROXY_PREFIX}{location}"
            return RedirectResponse(url=location, status_code=resp.status_code)

    content_type = resp.headers.get("content-type", "")
    response_body = _rewrite_proxied_content(resp.content, content_type)

    skip_headers = {
        "content-encoding",
        "content-length",
        "transfer-encoding",
        "connection",
        "set-cookie",
        "content-security-policy",
        "x-frame-options",
        "strict-transport-security",
        "alt-svc",
        "cf-cache-status",
        "cf-ray",
        "vary",
    }
    response_headers = {}
    for key, value in resp.headers.multi_items():
        if key.lower() not in skip_headers:
            response_headers[key] = value

    media_type = (
        content_type.split(";")[0].strip() if content_type else "application/octet-stream"
    )

    return Response(
        content=response_body,
        status_code=resp.status_code,
        headers=response_headers,
        media_type=media_type,
    )


def _game_to_template(game: dict) -> dict:
    game_type = game.get("type", 23)
    game_status = game.get("status", 5)
    tags = game.get("tags", [])
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except Exception:
            tags = []

    return {
        "id": game["id"],
        "custom": bool(game.get("custom")),
        "name": game.get("name", "Unknown"),
        "version": game.get("version", "Unchecked"),
        "developer": game.get("developer", ""),
        "type": game_type,
        "type_name": TYPE_NAMES.get(GameType(game_type), "Unknown")
        if game_type in GameType._value2member_map_
        else "Unknown",
        "type_color": TYPE_COLORS.get(GameType(game_type), "#393939")
        if game_type in GameType._value2member_map_
        else "#393939",
        "status": game_status,
        "status_name": STATUS_NAMES.get(Status(game_status), "Unknown")
        if game_status in Status._value2member_map_
        else "Unknown",
        "status_color": STATUS_COLORS.get(Status(game_status), "#808080")
        if game_status in Status._value2member_map_
        else "#808080",
        "url": game.get("url", ""),
        "added_on": game.get("added_on", 0),
        "last_updated": game.get("last_updated", 0),
        "score": game.get("score", 0),
        "votes": game.get("votes", 0),
        "rating": game.get("rating", 0),
        "finished": game.get("finished", ""),
        "installed": game.get("installed", ""),
        "updated": bool(game.get("updated", False)),
        "archived": bool(game.get("archived", False)),
        "description": game.get("description", ""),
        "changelog": game.get("changelog", ""),
        "tags": [TAG_TEXT.get(t, f"unknown({t})") for t in tags],
        "unknown_tags": game.get("unknown_tags", []),
        "notes": game.get("notes", ""),
        "image_url": game.get("image_url", ""),
        "image_local": _image_exists(game["id"]),
        "downloads": game.get("downloads", []),
        "reviews_total": game.get("reviews_total", 0),
    }


def _image_exists(game_id: int) -> bool:
    images_dir = Path(__file__).parent / "data" / "images"
    for ext in ("png", "jpg", "jpeg", "gif", "webp"):
        if (images_dir / f"{game_id}.{ext}").exists():
            return True
    return False


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    games_raw = await db.get_all_games()
    games = [_game_to_template(g) for g in games_raw]
    labels = await db.get_labels()
    tabs = await db.get_tabs()
    settings = await db.get_settings()
    refresh_status = background.get_refresh_status()

    stats = {
        "total": len(games),
        "updated": sum(1 for g in games if g["updated"]),
        "installed": sum(1 for g in games if g["installed"]),
        "finished": sum(1 for g in games if g["finished"]),
    }

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "games": games,
            "labels": labels,
            "tabs": tabs,
            "settings": settings,
            "refresh_status": refresh_status,
            "stats": stats,
            "game_types": {k: v for k, v in TYPE_NAMES.items()},
            "game_statuses": {k: v for k, v in STATUS_NAMES.items()},
        },
    )


@app.get("/games", response_class=HTMLResponse)
async def games_partial(
    request: Request,
    filter: str = "all",
    tab: str = "",
    sort: str = "added_on",
    sort_dir: str = "desc",
    search: str = "",
):
    games_raw = await db.get_all_games()
    games = [_game_to_template(g) for g in games_raw]

    # Apply filters
    if filter == "updated":
        games = [g for g in games if g["updated"]]
    elif filter == "installed":
        games = [g for g in games if g["installed"]]
    elif filter == "finished":
        games = [g for g in games if g["finished"]]
    elif filter == "archived":
        games = [g for g in games if g["archived"]]
    elif filter.startswith("status:"):
        status_val = int(filter.split(":")[1])
        games = [g for g in games if g["status"] == status_val]
    elif filter.startswith("type:"):
        type_val = int(filter.split(":")[1])
        games = [g for g in games if g["type"] == type_val]

    if tab:
        tab_id = int(tab)
        games = [g for g in games_raw if g.get("tab") == tab_id]
        games = [_game_to_template(g) for g in games]

    if search:
        search_lower = search.lower()
        games = [
            g
            for g in games
            if search_lower in g["name"].lower()
            or search_lower in g["developer"].lower()
        ]

    # Sort
    reverse = sort_dir == "desc"
    if sort == "name":
        games.sort(key=lambda g: g["name"].lower(), reverse=reverse)
    elif sort == "score":
        games.sort(key=lambda g: g["score"], reverse=not reverse)
    elif sort == "last_updated":
        games.sort(key=lambda g: g["last_updated"], reverse=reverse)
    elif sort == "added_on":
        games.sort(key=lambda g: g["added_on"], reverse=reverse)
    else:
        games.sort(key=lambda g: g["added_on"], reverse=True)

    return templates.TemplateResponse(
        "partials/game_list.html",
        {
            "request": request,
            "games": games,
        },
    )


@app.get("/game/{game_id}", response_class=HTMLResponse)
async def game_detail(request: Request, game_id: int):
    game = await db.get_game(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    game = _game_to_template(game)
    timeline = await db.get_timeline_events(game_id)
    timeline_formatted = []
    for evt in timeline:
        evt_type = evt.get("type", 1)
        args = (
            json.loads(evt.get("arguments", "[]"))
            if isinstance(evt.get("arguments"), str)
            else evt.get("arguments", [])
        )
        template = TIMELINE_TEMPLATES.get(TimelineEventType(evt_type), "{}")
        try:
            text = template.format(*args) if args else template
        except (IndexError, KeyError):
            text = template
        timeline_formatted.append(
            {
                "type": evt_type,
                "icon": TIMELINE_ICONS.get(TimelineEventType(evt_type), "📋"),
                "text": text,
                "timestamp": evt.get("timestamp", 0),
                "time_str": time.strftime(
                    "%Y-%m-%d %H:%M", time.localtime(evt.get("timestamp", 0))
                )
                if evt.get("timestamp")
                else "",
            }
        )
    return templates.TemplateResponse(
        "game_detail.html",
        {
            "request": request,
            "game": game,
            "timeline": timeline_formatted,
            "labels": await db.get_labels(),
        },
    )


@app.post("/game/{game_id}/update-field")
async def update_game_field(
    game_id: int, field: str = Form(...), value: str = Form(...)
):
    game = await db.get_game(game_id)
    if not game:
        raise HTTPException(404, "Game not found")

    bool_fields = {"archived", "updated"}
    int_fields = {"rating", "tab"}

    if field in bool_fields:
        val = value.lower() in ("true", "1", "yes")
    elif field in int_fields:
        val = int(value) if value else None
    else:
        val = value

    await db.update_game(game_id, **{field: val})
    if field == "rating":
        pass
    elif field == "installed" and val:
        await db.update_game(game_id, updated=False)
        await db.create_timeline_event(game_id, TimelineEventType.GameInstalled, [val])
    elif field == "finished" and val:
        await db.create_timeline_event(game_id, TimelineEventType.GameFinished, [val])

    return JSONResponse({"ok": True})


@app.post("/game/{game_id}/delete")
async def delete_game(game_id: int):
    try:
        await db.delete_game(game_id)
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/game/{game_id}/refresh")
async def refresh_single_game(game_id: int):
    ok = await background.check_single_game(game_id)
    return JSONResponse({"ok": ok})


@app.get("/game/{game_id}/image")
async def game_image(game_id: int):
    images_dir = Path(__file__).parent / "data" / "images"
    for ext in ("png", "jpg", "jpeg", "gif", "webp"):
        path = images_dir / f"{game_id}.{ext}"
        if path.exists():
            return FileResponse(str(path), media_type=f"image/{ext}")
    games = await db.get_all_games()
    for g in games:
        if g["id"] == game_id and g.get("image_url", "").startswith("http"):
            return RedirectResponse(url=g["image_url"])
    raise HTTPException(404, "No image")


@app.post("/games/add-url")
async def add_game_by_url(url: str = Form(...)):
    game_id = f95api.extract_thread_id(url)
    if not game_id:
        return JSONResponse({"ok": False, "error": "Invalid F95zone thread URL"})
    existing = await db.get_game(game_id)
    if existing:
        return JSONResponse({"ok": False, "error": "Game already in library"})
    await db.create_game(game_id, url=url)
    try:
        await background.check_single_game(game_id)
    except Exception:
        pass
    return JSONResponse({"ok": True, "id": game_id})


@app.post("/games/add-custom")
async def add_custom_game(name: str = Form("Custom game")):
    game_id = int(time.time() * 1000) * -1
    await db.create_game(game_id, custom=True, name=name)
    return JSONResponse({"ok": True, "id": game_id})


@app.get("/games/search")
async def search_f95zone(
    q: str = "", category: str = "games", search_type: str = "title"
):
    if not q:
        return JSONResponse({"results": []})

    cookies = await db.get_cookies()

    cat_map = {
        "games": "games",
        "comics": "asr-comics-amp",
        "animations": "asr-animations",
        "assets": "asr-assets",
    }
    search_map = {"title": "search", "creator": "creator"}

    cat = cat_map.get(category, "games")
    stype = search_map.get(search_type, "search")
    query = f95api.sanitize_search_query(q)

    results = await f95api.latest_updates_search(
        cat, stype, query, cookies=cookies if cookies else None
    )
    return JSONResponse({"results": results})


@app.post("/refresh")
async def refresh_all_games(force: bool = False):
    asyncio.create_task(background.refresh_games(force_full=force))
    return JSONResponse({"ok": True})


@app.get("/refresh/status")
async def refresh_status():
    return JSONResponse(background.get_refresh_status())


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    settings = await db.get_settings()
    cookies = await db.get_cookies()
    logged_in = False
    if cookies.get("xf_user"):
        try:
            logged_in = await f95api.is_logged_in(cookies)
        except Exception:
            logged_in = False
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "settings": settings,
            "logged_in": logged_in,
            "cookies": cookies,
        },
    )


@app.post("/settings/save")
async def save_settings(
    auto_refresh_interval: int = Form(30),
    refresh_archived_games: bool = Form(False),
    refresh_completed_games: bool = Form(False),
    max_connections: int = Form(10),
    request_timeout: int = Form(30),
):
    await db.update_settings(
        auto_refresh_interval=auto_refresh_interval,
        refresh_archived_games=int(refresh_archived_games),
        refresh_completed_games=int(refresh_completed_games),
        max_connections=max_connections,
        request_timeout=request_timeout,
    )
    background.stop_auto_refresh()
    await background.start_auto_refresh()
    return RedirectResponse("/settings", status_code=303)


@app.post("/settings/login")
async def login_f95zone(
    request: Request, username: str = Form(...), password: str = Form(...)
):
    result = await f95api.login_f95zone(username, password)
    if isinstance(result, dict):
        await db.update_cookies(result)
        await db.update_settings(f95zone_username=username, f95zone_password=password)
        return RedirectResponse("/settings", status_code=303)
    else:
        settings = await db.get_settings()
        cookies = await db.get_cookies()
        return templates.TemplateResponse(
            "settings.html",
            {
                "request": request,
                "settings": settings,
                "logged_in": False,
                "cookies": cookies,
                "error": result,
            },
        )


@app.post("/settings/save-cookies")
async def save_cookies_manually(cookies_text: str = Form(...)):
    try:
        cookies = {}
        for line in cookies_text.strip().split("\n"):
            line = line.strip()
            if "=" in line:
                k, v = line.split("=", 1)
                cookies[k.strip()] = v.strip()
        if cookies:
            await db.update_cookies(cookies)
    except Exception:
        pass
    return RedirectResponse("/settings", status_code=303)


@app.post("/settings/logout")
async def logout_f95zone():
    await db.update_cookies({})
    await db.update_settings(f95zone_username="", f95zone_password="")
    return RedirectResponse("/settings", status_code=303)


@app.get("/api/games")
async def api_games():
    games_raw = await db.get_all_games()
    return JSONResponse([_game_to_template(g) for g in games_raw])


@app.get("/labels")
async def get_labels():
    return JSONResponse(await db.get_labels())


@app.post("/labels/create")
async def create_label(name: str = Form(""), color: str = Form("#696969")):
    label_id = await db.create_label(name, color)
    return JSONResponse({"ok": True, "id": label_id})


@app.post("/labels/{label_id}/update")
async def update_label(label_id: int, name: str = Form(None), color: str = Form(None)):
    kwargs = {}
    if name is not None:
        kwargs["name"] = name
    if color is not None:
        kwargs["color"] = color
    if kwargs:
        await db.update_label(label_id, **kwargs)
    return JSONResponse({"ok": True})


@app.post("/labels/{label_id}/delete")
async def delete_label(label_id: int):
    await db.delete_label(label_id)
    return JSONResponse({"ok": True})


@app.get("/tabs")
async def get_tabs():
    return JSONResponse(await db.get_tabs())


@app.post("/tabs/create")
async def create_tab(name: str = Form(""), icon: str = Form("📁")):
    tab_id = await db.create_tab(name, icon)
    return JSONResponse({"ok": True, "id": tab_id})


@app.post("/tabs/{tab_id}/delete")
async def delete_tab(tab_id: int):
    await db.delete_tab(tab_id)
    return JSONResponse({"ok": True})


@app.post("/import")
async def import_f95_data(source: str = Form(...), data: str = Form("")):
    """Import from F95Checker database or JSON."""
    if source == "f95checker":
        import_path = data.strip()
        if not import_path:
            appdata = os.environ.get("APPDATA", "")
            default_path = (
                os.path.join(appdata, "f95checker", "db.sqlite3") if appdata else ""
            )
            path = Path(default_path) if default_path else Path(import_path)
        if not path.exists():
            return JSONResponse({"ok": False, "error": f"Database not found at {path}"})
        count = await _import_f95checker_db(path)
        return JSONResponse({"ok": True, "imported": count})
    return JSONResponse({"ok": False, "error": "Unknown import source"})


async def _import_f95checker_db(db_path: Path) -> int:
    """Import games from a F95Checker SQLite database."""
    import aiosqlite as asql

    try:
        src = await asql.connect(str(db_path))
        src.row_factory = asql.Row
        cursor = await src.execute("SELECT * FROM games")
        rows = await cursor.fetchall()
        count = 0
        for row in rows:
            r = dict(row)
            game_id = r.get("id")
            if not game_id:
                continue
            existing = await db.get_game(game_id)
            if existing:
                continue
            await db.create_game(
                game_id,
                custom=bool(r.get("custom")),
                name=r.get("name", ""),
                url=r.get("url", ""),
            )
            updates = {}
            simple_fields = [
                "version",
                "developer",
                "type",
                "status",
                "added_on",
                "last_updated",
                "last_full_check",
                "last_check_version",
                "score",
                "votes",
                "rating",
                "finished",
                "installed",
                "updated",
                "archived",
                "description",
                "changelog",
                "notes",
                "image_url",
                "reviews_total",
            ]
            for f in simple_fields:
                if r.get(f) is not None:
                    updates[f] = r[f]
            for f in [
                "tags",
                "unknown_tags",
                "labels",
                "previews_urls",
                "downloads",
                "reviews",
            ]:
                if r.get(f) is not None:
                    updates[f] = r[f]
            if updates:
                await db.update_game(game_id, **updates)
            count += 1
        await src.close()
        return count
    except Exception as e:
        return 0


@app.get("/proxy", response_class=HTMLResponse)
async def proxy_f95zone_main(request: Request):
    return await _proxy_request(request, "")


@app.api_route(
    "/proxy/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
)
async def proxy_f95zone_path(request: Request, path: str):
    return await _proxy_request(request, path)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
