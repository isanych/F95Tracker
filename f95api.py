import httpx
import json
import re
import asyncio
from typing import Optional

F95_HOST = "https://f95zone.to"
F95_THREADS_PAGE = f"{F95_HOST}/threads/"
F95_CHECK_LOGIN = f"{F95_HOST}/sam/latest_alpha/"
F95_LATEST_ENDPOINT = f"{F95_HOST}/sam/latest_alpha/latest_data.php"
F95_LOGIN_URL = f"{F95_HOST}/login/login"

API_HOST = "https://api.f95checker.dev"
API_FAST_CHECK_URL = f"{API_HOST}/fast?ids={{ids}}"
API_FULL_CHECK_URL = f"{API_HOST}/full/{{id}}?ts={{ts}}"

LOGIN_ERROR_MESSAGES = [
    b'<a href="/login/" data-xf-click="overlay">Log in or register now.</a>',
    b"<title>Log in | F95zone</title>",
    b'<form action="/login/login" method="post" class="block"',
]

RATELIMIT_ERRORS = [
    b"<title>429 Too Many Requests</title>",
    b"<h1>429 Too Many Requests</h1>",
]

TEMP_ERRORS = [
    b"<title>502 Bad Gateway</title>",
    b"<b>504 - Gateway Timeout .</b>",
]

_client: httpx.AsyncClient = None


async def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=60.0,
            follow_redirects=True,
            headers={"User-Agent": "F95Tracker/1.0"},
        )
    return _client


async def close_client():
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()


async def fetch(method: str, url: str, cookies: dict = None, **kwargs) -> bytes:
    client = await get_client()
    resp = await client.request(method, url, cookies=cookies, **kwargs)
    return resp.content


async def fetch_json(method: str, url: str, cookies: dict = None, **kwargs):
    data = await fetch(method, url, cookies=cookies, **kwargs)
    return json.loads(data)


async def is_logged_in(cookies: dict) -> bool:
    try:
        data = await fetch("GET", F95_CHECK_LOGIN, cookies=cookies)
        return (
            b'<pre>Sorry, you have to be <a href="/login">logged in</a> to access this page</a></pre>'
            not in data
        )
    except Exception:
        return False


async def login_f95zone(username: str, password: str) -> dict | str:
    """Attempt to log into F95zone and return cookies dict, or error message string."""
    client = await get_client()

    try:
        login_page = await client.get(F95_HOST + "/login/")
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(login_page.text, "lxml")

        token_input = soup.find("input", {"name": "_xfToken"})
        if not token_input:
            return "Could not find login form. F95zone might be down or blocked."
        xf_token = token_input.get("value", "")

        login_data = {
            "login": username,
            "password": password,
            "_xfToken": xf_token,
            "remember": "1",
        }

        resp = await client.post(
            F95_LOGIN_URL,
            data=login_data,
            headers={"Referer": F95_HOST + "/login/"},
            follow_redirects=True,
        )

        if resp.status_code == 200:
            cookies = {}
            for name, value in resp.cookies.items():
                cookies[name] = value
            if not cookies:
                for name, value in client.cookies.items():
                    cookies[name] = value

            if "xf_user" in cookies:
                return cookies
            else:
                return "Login failed. Check your credentials."
        else:
            return f"Login request failed with status {resp.status_code}"

    except Exception as e:
        return f"Login error: {str(e)}"


def extract_thread_id(url: str) -> int | None:
    match = re.search(r"threads/([^/]*)\.(\d+)", url)
    if match:
        return int(match.group(2))
    match = re.search(r"threads/(\d+)", url)
    if match:
        return int(match.group(1))
    return None


async def latest_updates_search(
    category: str,
    search_type: str,
    query: str,
    sort: str = "likes",
    count: int = 15,
    page: int = 1,
    cookies: dict = None,
) -> list[dict]:
    params = {
        "cmd": "list",
        "cat": category,
        "page": page,
        search_type: query,
        "sort": sort,
        "rows": count,
    }
    try:
        data = await fetch_json(
            "GET", F95_LATEST_ENDPOINT, cookies=cookies, params=params
        )
        if isinstance(data, dict) and data.get("status") == "error":
            return []
        results = []
        for item in data.get("msg", {}).get("data", []):
            results.append(
                {
                    "title": item.get("title", ""),
                    "creator": item.get("creator", ""),
                    "url": f"{F95_THREADS_PAGE}{item['thread_id']}",
                    "id": int(item["thread_id"]),
                }
            )
        return results
    except Exception:
        return []


async def fast_check(game_ids: list[int]) -> dict:
    """Get last_change timestamps from cache API."""
    ids_str = ",".join(str(gid) for gid in game_ids[:10])
    url = API_FAST_CHECK_URL.format(ids=ids_str)
    try:
        data = await fetch_json("GET", url)
        if isinstance(data, dict) and data.get("INDEX_ERROR"):
            return {}
        return data
    except Exception:
        return {}


async def full_check(game_id: int, last_changed: int = 0) -> dict | None:
    """Get full game data from cache API."""
    url = API_FULL_CHECK_URL.format(id=game_id, ts=last_changed)
    try:
        client = await get_client()
        resp = await client.get(url)
        if resp.status_code in (403, 404):
            return None
        data = resp.json()
        if isinstance(data, dict) and data.get("INDEX_ERROR"):
            return None
        return data
    except Exception:
        return None


async def get_game_image(image_url: str) -> bytes | None:
    """Download game header image."""
    if not image_url or not image_url.startswith("http"):
        return None
    try:
        return await fetch("GET", image_url)
    except Exception:
        return None


def sanitize_search_query(query: str) -> str:
    stopwords = {
        "a",
        "is",
        "the",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "but",
        "by",
        "for",
        "if",
        "in",
        "into",
        "it",
        "no",
        "not",
        "of",
        "on",
        "or",
        "such",
        "that",
        "their",
        "then",
        "there",
        "these",
        "they",
        "this",
        "to",
        "was",
        "will",
        "with",
    }
    query = re.sub(r"'s ", " ", query)
    query = query.encode("ascii", errors="replace").decode()
    for char in "?&/':;-.+!~(),*":
        query = query.replace(char, " ")
    query = re.sub(r"\s+", " ", query).strip()
    words = [w for w in query.split() if w.lower() not in stopwords]
    result = " ".join(words)
    return result[:30] if len(result) > 30 else result
