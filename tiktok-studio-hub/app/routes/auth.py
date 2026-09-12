from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.database import ConnectedAccount
from app.services import consume_oauth_state, new_oauth_state
from app.tiktok_client import TikTokApiError, token_expiry

router = APIRouter()


@router.get("/auth/login")
async def login(request: Request):
    settings = request.app.state.settings
    if not settings.oauth_configured and not settings.demo_mode:
        raise HTTPException(
            503,
            "Configurez TIKTOK_CLIENT_KEY et TIKTOK_CLIENT_SECRET dans .env",
        )
    if settings.demo_mode and not settings.oauth_configured:
        raise HTTPException(
            400,
            "Mode démo actif — les comptes fictifs sont déjà chargés.",
        )

    state = new_oauth_state()
    client = request.app.state.tiktok_client
    url = client.authorize_url(
        settings.redirect_uri,
        state,
        settings.oauth_scopes,
    )
    return RedirectResponse(url)


@router.get("/auth/callback")
async def callback(request: Request, code: str = "", state: str = "", error: str = ""):
    if error:
        return RedirectResponse(f"/?auth_error={error}")
    if not code or not consume_oauth_state(state):
        return RedirectResponse("/?auth_error=invalid_state")

    settings = request.app.state.settings
    client = request.app.state.tiktok_client
    session_factory = request.app.state.session_factory

    try:
        token_data = await client.exchange_code(code, settings.redirect_uri)
        access_token = token_data["access_token"]
        user = await client.fetch_user_info(access_token)
        videos = await client.fetch_all_videos(access_token)
    except TikTokApiError as exc:
        return RedirectResponse(f"/?auth_error={str(exc)[:120]}")

    open_id = user.get("open_id") or token_data.get("open_id")
    if not open_id:
        return RedirectResponse("/?auth_error=missing_open_id")

    with session_factory() as session:
        account = session.query(ConnectedAccount).filter_by(open_id=open_id).first()
        if account is None:
            account = ConnectedAccount(open_id=open_id)
            session.add(account)

        account.display_name = user.get("display_name") or account.display_name
        account.avatar_url = user.get("avatar_url") or ""
        account.access_token = access_token
        account.refresh_token = token_data.get("refresh_token") or account.refresh_token
        account.token_expires_at = token_expiry(token_data.get("expires_in"))
        account.refresh_expires_at = token_expiry(token_data.get("refresh_expires_in"))
        account.follower_count = int(user.get("follower_count") or 0)
        account.following_count = int(user.get("following_count") or 0)
        account.likes_count = int(user.get("likes_count") or 0)
        account.video_count = int(user.get("video_count") or 0)
        account.total_views = sum(int(v.get("view_count") or 0) for v in videos)
        account.total_video_likes = sum(int(v.get("like_count") or 0) for v in videos)
        account.total_comments = sum(int(v.get("comment_count") or 0) for v in videos)
        account.total_shares = sum(int(v.get("share_count") or 0) for v in videos)
        from datetime import datetime

        account.last_synced_at = datetime.utcnow()
        session.commit()

    return RedirectResponse("/?connected=1")
