import datetime
from typing import Any

import httpx

TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
USER_INFO_URL = "https://open.tiktokapis.com/v2/user/info/"
VIDEO_LIST_URL = "https://open.tiktokapis.com/v2/video/list/"
AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"

USER_FIELDS = (
    "open_id,union_id,avatar_url,display_name,"
    "follower_count,following_count,likes_count,video_count"
)
VIDEO_FIELDS = (
    "id,title,cover_image_url,create_time,"
    "view_count,like_count,comment_count,share_count"
)


class TikTokApiError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class TikTokClient:
    def __init__(self, client_key: str, client_secret: str):
        self.client_key = client_key
        self.client_secret = client_secret

    def authorize_url(self, redirect_uri: str, state: str, scope: str) -> str:
        from urllib.parse import urlencode

        query = urlencode(
            {
                "client_key": self.client_key,
                "scope": scope,
                "response_type": "code",
                "redirect_uri": redirect_uri,
                "state": state,
            }
        )
        return f"{AUTH_URL}?{query}"

    async def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        return await self._token_request(
            {
                "client_key": self.client_key,
                "client_secret": self.client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            }
        )

    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        return await self._token_request(
            {
                "client_key": self.client_key,
                "client_secret": self.client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            }
        )

    async def _token_request(self, data: dict[str, str]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        return self._parse_token_response(resp)

    def _parse_token_response(self, resp: httpx.Response) -> dict[str, Any]:
        if resp.status_code >= 400:
            raise TikTokApiError(resp.text, status_code=resp.status_code)
        payload = resp.json()
        err = payload.get("error") or {}
        if isinstance(err, str):
            raise TikTokApiError(err)
        if err.get("code") not in (None, "ok"):
            raise TikTokApiError(err.get("message") or str(err))
        # v2 renvoie souvent les tokens dans `data`, v1 les met à la racine.
        token_data = payload.get("data") or payload
        if not token_data.get("access_token"):
            raise TikTokApiError("Réponse OAuth TikTok sans access_token")
        return token_data

    async def fetch_user_info(self, access_token: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                USER_INFO_URL,
                params={"fields": USER_FIELDS},
                headers={"Authorization": f"Bearer {access_token}"},
            )
        return self._parse_data(resp)

    async def fetch_all_videos(self, access_token: str) -> list[dict[str, Any]]:
        videos: list[dict[str, Any]] = []
        cursor: int | None = None
        while True:
            body: dict[str, Any] = {"max_count": 20}
            if cursor is not None:
                body["cursor"] = cursor
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{VIDEO_LIST_URL}?fields={VIDEO_FIELDS}",
                    json=body,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                )
            data = self._parse_data(resp)
            videos.extend(data.get("videos", []))
            if not data.get("has_more"):
                break
            cursor = data.get("cursor")
            if cursor is None:
                break
        return videos

    def _parse_data(self, resp: httpx.Response) -> dict[str, Any]:
        if resp.status_code >= 400:
            raise TikTokApiError(resp.text, status_code=resp.status_code)
        payload = resp.json()
        err = payload.get("error") or {}
        if err.get("code") not in (None, "ok"):
            raise TikTokApiError(err.get("message") or str(err))
        return payload.get("data") or {}


def token_expiry(expires_in: int | None) -> datetime.datetime | None:
    if not expires_in:
        return None
    return datetime.datetime.utcnow() + datetime.timedelta(seconds=int(expires_in))
