from __future__ import annotations
import httpx
from app.core.cookie_manager import cookies_to_header

TIKTOK_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def build_headers(cookies: dict) -> dict:
    return {
        "User-Agent": TIKTOK_USER_AGENT,
        "Cookie": cookies_to_header(cookies),
        "Referer": "https://www.tiktok.com/",
        "Accept": "application/json, text/plain, */*",
    }


async def scrape_profile(handle: str, cookies: dict, client: httpx.AsyncClient | None = None) -> dict:
    clean_handle = handle.lstrip("@")
    url = f"https://www.tiktok.com/@{clean_handle}"
    headers = build_headers(cookies)

    should_close = False
    if client is None:
        client = httpx.AsyncClient(timeout=15.0)
        should_close = True

    try:
        resp = await client.get(url, headers=headers, follow_redirects=True)
        resp.raise_for_status()
        return _parse_profile_page(resp.text, clean_handle)
    finally:
        if should_close:
            await client.aclose()


def _parse_profile_page(html: str, handle: str) -> dict:
    import json
    import re

    result = {
        "handle": handle,
        "followers": 0,
        "following": 0,
        "total_likes": 0,
        "video_count": 0,
        "bio": "",
        "verified": False,
        "nickname": "",
    }

    sigi_match = re.search(r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not sigi_match:
        sigi_match = re.search(r'<script id="SIGI_STATE"[^>]*>(.*?)</script>', html, re.DOTALL)

    if sigi_match:
        try:
            data = json.loads(sigi_match.group(1))
            user_info = _extract_user_info(data, handle)
            if user_info:
                result.update(user_info)
        except (json.JSONDecodeError, KeyError):
            pass

    return result


def _extract_user_info(data: dict, handle: str) -> dict | None:
    user_detail = None
    if "__DEFAULT_SCOPE__" in data:
        scope = data["__DEFAULT_SCOPE__"]
        if "webapp.user-detail" in scope:
            user_detail = scope["webapp.user-detail"].get("userInfo")
    if not user_detail and "UserModule" in data:
        users = data["UserModule"].get("users", {})
        stats = data["UserModule"].get("stats", {})
        if handle in users:
            user = users[handle]
            user_stats = stats.get(handle, {})
            return {
                "followers": user_stats.get("followerCount", 0),
                "following": user_stats.get("followingCount", 0),
                "total_likes": user_stats.get("heartCount", 0),
                "video_count": user_stats.get("videoCount", 0),
                "bio": user.get("signature", ""),
                "verified": user.get("verified", False),
                "nickname": user.get("nickname", ""),
            }
    if user_detail:
        user = user_detail.get("user", {})
        stats = user_detail.get("stats", {})
        return {
            "followers": stats.get("followerCount", 0),
            "following": stats.get("followingCount", 0),
            "total_likes": stats.get("heartCount", 0),
            "video_count": stats.get("videoCount", 0),
            "bio": user.get("signature", ""),
            "verified": user.get("verified", False),
            "nickname": user.get("nickname", ""),
        }
    return None
