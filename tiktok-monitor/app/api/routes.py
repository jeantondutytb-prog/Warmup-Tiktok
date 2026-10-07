import asyncio
import json
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

router = APIRouter()


@router.get("/api/status")
async def get_status(request: Request):
    return request.app.state.orchestrator.get_all_status()


@router.post("/api/check-all")
async def check_all(request: Request):
    results = await request.app.state.orchestrator.check_all()
    return results


@router.post("/api/check/{username}")
async def check_account(username: str, request: Request):
    try:
        result = await request.app.state.orchestrator.check_account(username)
        return result
    except ValueError as e:
        return JSONResponse(status_code=404, content={"error": str(e)})


@router.put("/api/cookies/{username}")
async def update_cookies(username: str, request: Request):
    body = await request.json()
    cookies = body.get("cookies", {})
    from app.core.cookie_manager import store_cookies
    with request.app.state.orchestrator.Session() as db:
        ok = store_cookies(db, username, cookies)
    if not ok:
        return JSONResponse(status_code=404, content={"error": "Account not found"})
    return {"ok": True}


@router.get("/api/history/{username}")
async def get_history(username: str, request: Request):
    status = request.app.state.orchestrator.get_all_status()
    if username not in status:
        return JSONResponse(status_code=404, content={"error": "Account not found"})
    return {"username": username, "history": status[username]["history"]}


@router.get("/api/scheduler")
async def scheduler_status(request: Request):
    sched = request.app.state.scheduler
    return {
        "running": sched.running,
        "next_run": sched.get_next_run(),
        "interval_hours": sched.interval_hours,
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
                yield {"event": event.get("type", "message"), "data": json.dumps(event)}
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": ""}

    return EventSourceResponse(event_generator())
