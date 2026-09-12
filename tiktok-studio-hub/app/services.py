import datetime
import secrets
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings
from app.database import ConnectedAccount
from app.tiktok_client import TikTokApiError, TikTokClient, token_expiry


_oauth_states: dict[str, float] = {}


def remember_oauth_state(state: str) -> None:
    _oauth_states[state] = datetime.datetime.utcnow().timestamp()


def consume_oauth_state(state: str, *, max_age_seconds: int = 600) -> bool:
    created = _oauth_states.pop(state, None)
    if created is None:
        return False
    return (datetime.datetime.utcnow().timestamp() - created) <= max_age_seconds


def ensure_demo_accounts(session: Session) -> None:
    if session.query(ConnectedAccount).count():
        return
    demos = [
        ("demo-emma", "emma.srpt", 12400, 890000, 156, 42),
        ("demo-chloe", "chloe.rtps", 8200, 420000, 98, 31),
        ("demo-eva", "eva.drtp", 5600, 210000, 74, 28),
        ("demo-ftpl", "emma.ftpl", 98000, 1200000, 412, 89),
    ]
    now = datetime.datetime.utcnow()
    for open_id, name, followers, views, likes, videos in demos:
        session.add(
            ConnectedAccount(
                open_id=open_id,
                display_name=name,
                avatar_url="",
                access_token="demo",
                refresh_token="demo",
                follower_count=followers,
                following_count=120,
                likes_count=likes * 120,
                video_count=videos,
                total_views=views,
                total_video_likes=likes,
                total_comments=likes // 8,
                total_shares=likes // 15,
                last_synced_at=now,
            )
        )
    session.commit()


async def sync_account(
    session: Session,
    account: ConnectedAccount,
    client: TikTokClient,
    settings: Settings,
) -> ConnectedAccount:
    if settings.demo_mode or account.access_token == "demo":
        account.last_synced_at = datetime.datetime.utcnow()
        session.commit()
        session.refresh(account)
        return account

    token = account.access_token
    if account.token_expires_at and account.token_expires_at <= datetime.datetime.utcnow():
        if not account.refresh_token:
            raise TikTokApiError("Token expiré — reconnectez le compte.")
        refreshed = await client.refresh_access_token(account.refresh_token)
        token = refreshed["access_token"]
        account.access_token = token
        account.refresh_token = refreshed.get("refresh_token") or account.refresh_token
        account.token_expires_at = token_expiry(refreshed.get("expires_in"))
        account.refresh_expires_at = token_expiry(refreshed.get("refresh_expires_in"))

    user = await client.fetch_user_info(token)
    videos = await client.fetch_all_videos(token)

    account.display_name = user.get("display_name") or account.display_name
    account.avatar_url = user.get("avatar_url") or account.avatar_url
    account.follower_count = int(user.get("follower_count") or 0)
    account.following_count = int(user.get("following_count") or 0)
    account.likes_count = int(user.get("likes_count") or 0)
    account.video_count = int(user.get("video_count") or 0)
    account.total_views = sum(int(v.get("view_count") or 0) for v in videos)
    account.total_video_likes = sum(int(v.get("like_count") or 0) for v in videos)
    account.total_comments = sum(int(v.get("comment_count") or 0) for v in videos)
    account.total_shares = sum(int(v.get("share_count") or 0) for v in videos)
    account.last_synced_at = datetime.datetime.utcnow()
    session.commit()
    session.refresh(account)
    return account


def account_to_dict(account: ConnectedAccount) -> dict[str, Any]:
    return {
        "id": account.id,
        "open_id": account.open_id,
        "display_name": account.display_name,
        "avatar_url": account.avatar_url,
        "follower_count": account.follower_count,
        "following_count": account.following_count,
        "likes_count": account.likes_count,
        "video_count": account.video_count,
        "total_views": account.total_views,
        "total_video_likes": account.total_video_likes,
        "total_comments": account.total_comments,
        "total_shares": account.total_shares,
        "last_synced_at": account.last_synced_at.isoformat() if account.last_synced_at else None,
        "is_demo": account.access_token == "demo",
    }


def build_dashboard(session: Session) -> dict[str, Any]:
    accounts = session.query(ConnectedAccount).order_by(ConnectedAccount.display_name).all()
    rows = [account_to_dict(a) for a in accounts]
    totals = {
        "accounts": len(rows),
        "followers": sum(r["follower_count"] for r in rows),
        "following": sum(r["following_count"] for r in rows),
        "profile_likes": sum(r["likes_count"] for r in rows),
        "videos": sum(r["video_count"] for r in rows),
        "views": sum(r["total_views"] for r in rows),
        "likes": sum(r["total_video_likes"] for r in rows),
        "comments": sum(r["total_comments"] for r in rows),
        "shares": sum(r["total_shares"] for r in rows),
    }
    return {"totals": totals, "accounts": rows}


def new_oauth_state() -> str:
    state = secrets.token_urlsafe(24)
    remember_oauth_state(state)
    return state
