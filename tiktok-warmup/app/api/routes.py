import asyncio
import json
import os
from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.core.device_status import get_device_status

router = APIRouter()


@router.get("/api/status")
async def get_status(request: Request):
    return request.app.state.orchestrator.get_status()


@router.get("/api/device")
async def device_status():
    """État iPhone + WDA pour l'écran de lancement rapide."""
    wda_url = os.environ.get("WDA_URL")
    return get_device_status(wda_url)


@router.get("/api/launcher/accounts")
async def launcher_accounts(request: Request):
    """Liste simplifiée des comptes warmup (sans les comptes protégés)."""
    status = request.app.state.orchestrator.get_status()
    accounts = []
    for username, info in status.items():
        if info.get("protected"):
            continue
        accounts.append({
            "username": username,
            "role": info.get("role", ""),
            "protocol_day": info.get("protocol_day", 1),
            "status": info.get("status", "idle"),
            "can_start": info.get("status") != "running",
        })
    return accounts


@router.post("/api/start-all")
async def start_all(request: Request):
    await request.app.state.orchestrator.start_all()
    return {"ok": True}


@router.get("/api/rotation")
async def rotation_status(request: Request):
    return request.app.state.orchestrator.rotation_status()


@router.post("/api/stop-all")
async def stop_all(request: Request):
    await request.app.state.orchestrator.stop_all()
    return {"ok": True}


@router.post("/api/start/{username}")
async def start_account(username: str, request: Request, force: bool = False):
    """Démarre une session. `force=1` passe outre la porte de cadence.

    Le contournement est explicite et jamais implicite : les règles
    d'espacement du protocole existent pour une raison, et il faut le vouloir
    pour s'en affranchir.
    """
    await request.app.state.orchestrator.start_account(username, force=force)
    return {"ok": True, "forced": force}


@router.post("/api/stop/{username}")
async def stop_account(username: str, request: Request):
    await request.app.state.orchestrator.stop_account(username)
    return {"ok": True}


@router.get("/api/fyp/pending")
async def pending_fyp(request: Request):
    """Sessions en attente d'un comptage FYP."""
    return request.app.state.orchestrator.pending_fyp()


@router.post("/api/fyp/{session_id}")
async def record_fyp(session_id: int, request: Request):
    """Saisit le comptage de la phase 13-18' : vidéos de la niche sur 20 scrolls."""
    body = await request.json()
    try:
        count = int(body["count"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(400, "corps attendu : {\"count\": <entier>}")
    try:
        return request.app.state.orchestrator.record_fyp_count(session_id, count)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/api/protocol-day/{username}")
async def set_protocol_day(username: str, request: Request):
    body = await request.json()
    try:
        day = int(body["day"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(400, "corps attendu : {\"day\": <entier>}")
    try:
        return request.app.state.orchestrator.advance_protocol_day(username, day)
    except KeyError as e:
        raise HTTPException(404, str(e))


@router.post("/api/accounts")
async def add_account(request: Request):
    body = await request.json()
    username = body.get("username", "").strip()
    if not username:
        raise HTTPException(400, "username requis")
    role = body.get("role", "flagship")
    comment_style = body.get("comment_style", "casual")
    protected = bool(body.get("protected", False))
    try:
        return request.app.state.orchestrator.add_account(
            username, role=role, comment_style=comment_style, protected=protected,
        )
    except ValueError as e:
        raise HTTPException(409, str(e))


@router.delete("/api/accounts/{username}")
async def delete_account(username: str, request: Request):
    try:
        return request.app.state.orchestrator.delete_account(username)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))


# --------------------------------------------------------- mode navigateur PC


@router.post("/api/start-browser/{username}")
async def start_browser(username: str, request: Request, force: bool = False):
    """Démarre une session warmup via navigateur PC."""
    try:
        await request.app.state.orchestrator.start_account_browser(username, force=force)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"ok": True, "mode": "browser", "forced": force}


@router.post("/api/start-all-browser")
async def start_all_browser(request: Request, force: bool = False):
    """Démarre le warmup navigateur pour tous les comptes en parallèle."""
    started = await request.app.state.orchestrator.start_all_browser(force=force)
    return {"ok": True, "started": started, "count": len(started)}


@router.post("/api/browser/login/{username}")
async def browser_login(username: str, request: Request):
    """Ouvre un Chromium visible pour connexion manuelle à TikTok."""
    mgr = request.app.state.orchestrator.browser_manager
    if mgr.is_logging_in(username):
        raise HTTPException(409, f"connexion déjà en cours pour {username}")
    try:
        await mgr.start_login(username)
    except Exception as e:
        raise HTTPException(500, f"impossible d'ouvrir le navigateur : {e}")
    return {"ok": True, "message": "Navigateur ouvert — connecte-toi puis clique « Sauvegarder »"}


@router.post("/api/browser/login/{username}/save")
async def browser_login_save(username: str, request: Request):
    """Sauvegarde les cookies après connexion manuelle."""
    mgr = request.app.state.orchestrator.browser_manager
    try:
        await mgr.finish_login(username)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@router.get("/api/browser/status")
async def browser_status(request: Request):
    """État des cookies par compte (pour le mode navigateur)."""
    mgr = request.app.state.orchestrator.browser_manager
    status = request.app.state.orchestrator.get_status()
    return {
        username: {
            "has_cookies": mgr.has_cookies(username),
            "logging_in": mgr.is_logging_in(username),
        }
        for username in status
    }


@router.get("/api/events")
async def events(request: Request):
    queue = request.app.state.orchestrator.subscribe()

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield {"event": event["type"], "data": json.dumps(event)}
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": ""}

    return EventSourceResponse(event_generator())
