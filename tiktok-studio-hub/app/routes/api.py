from fastapi import APIRouter, HTTPException, Request

from app.database import ConnectedAccount
from app.services import account_to_dict, build_dashboard, ensure_demo_accounts, sync_account
from app.tiktok_client import TikTokApiError

router = APIRouter()


@router.get("/api/config")
async def get_config(request: Request):
    settings = request.app.state.settings
    return {
        "oauth_configured": settings.oauth_configured,
        "demo_mode": settings.demo_mode,
        "redirect_uri": settings.redirect_uri,
    }


@router.get("/api/dashboard")
async def dashboard(request: Request):
    session_factory = request.app.state.session_factory
    settings = request.app.state.settings
    with session_factory() as session:
        if settings.demo_mode:
            ensure_demo_accounts(session)
        return build_dashboard(session)


@router.get("/api/accounts")
async def list_accounts(request: Request):
    session_factory = request.app.state.session_factory
    with session_factory() as session:
        accounts = (
            session.query(ConnectedAccount)
            .order_by(ConnectedAccount.display_name)
            .all()
        )
        return [account_to_dict(a) for a in accounts]


@router.post("/api/accounts/{account_id}/refresh")
async def refresh_account(account_id: int, request: Request):
    session_factory = request.app.state.session_factory
    settings = request.app.state.settings
    client = request.app.state.tiktok_client

    with session_factory() as session:
        account = session.get(ConnectedAccount, account_id)
        if account is None:
            raise HTTPException(404, "Compte introuvable")
        try:
            updated = await sync_account(session, account, client, settings)
        except TikTokApiError as exc:
            raise HTTPException(502, str(exc)) from exc
        return account_to_dict(updated)


@router.post("/api/refresh-all")
async def refresh_all(request: Request):
    session_factory = request.app.state.session_factory
    settings = request.app.state.settings
    client = request.app.state.tiktok_client

    with session_factory() as session:
        accounts = session.query(ConnectedAccount).all()
        errors: list[str] = []
        for account in accounts:
            try:
                await sync_account(session, account, client, settings)
            except TikTokApiError as exc:
                errors.append(f"{account.display_name}: {exc}")
        payload = build_dashboard(session)
        payload["errors"] = errors
        return payload


@router.delete("/api/accounts/{account_id}")
async def delete_account(account_id: int, request: Request):
    session_factory = request.app.state.session_factory
    with session_factory() as session:
        account = session.get(ConnectedAccount, account_id)
        if account is None:
            raise HTTPException(404, "Compte introuvable")
        session.delete(account)
        session.commit()
    return {"ok": True}
