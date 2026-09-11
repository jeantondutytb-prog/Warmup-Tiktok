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
