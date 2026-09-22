"""Boucle principale : WDA + jobs Vercel + orchestrateur local."""

from __future__ import annotations

import asyncio
import datetime
import os
from typing import Any

from agent.client import ControlPlane
from agent.wda import WDASupervisor


def make_orchestrator():
    from app.core.orchestrator import Orchestrator
    base_dir = os.path.dirname(os.path.dirname(__file__))
    os.makedirs(os.path.join(base_dir, "db"), exist_ok=True)
    return Orchestrator(
        db_url=f"sqlite:///{os.path.join(base_dir, 'db', 'warmup.db')}",
        config_dir=os.path.join(base_dir, "config"),
    )


async def handle_job(orch: Orchestrator, job: dict[str, Any]) -> None:
    kind = job.get("type")
    if kind == "start":
        await orch.start_account(str(job.get("username") or ""), force=bool(job.get("force")))
    elif kind == "start-all":
        await orch.start_all()
    elif kind == "stop-all":
        await orch.stop_all()
    elif kind == "fyp":
        orch.record_fyp_count(int(job["sessionId"]), int(job["count"]))
    elif kind == "protocol-day":
        orch.advance_protocol_day(str(job["username"]), int(job["day"]))
    else:
        raise ValueError(f"job inconnu : {kind}")


async def flush_events(orch: Orchestrator, plane: ControlPlane, queue: asyncio.Queue) -> None:
    batch: list[dict[str, Any]] = []
    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=1.5)
            batch.append(event)
            while not queue.empty() and len(batch) < 20:
                batch.append(queue.get_nowait())
        except asyncio.TimeoutError:
            pass
        if batch:
            try:
                await asyncio.to_thread(plane.events, batch)
            except Exception as exc:
                print(f"[agent] events: {exc}", flush=True)
            batch = []


async def run_bridge(
    *,
    plane: ControlPlane | None = None,
    orch: Orchestrator | None = None,
    wda: WDASupervisor | None = None,
    once: bool = False,
    poll_seconds: float = 2.5,
) -> None:
    plane = plane or ControlPlane()
    orch = orch or make_orchestrator()
    wda = wda or WDASupervisor()
    queue = orch.subscribe()
    forwarder = asyncio.create_task(flush_events(orch, plane, queue))
    last_snapshot = 0.0

    try:
        while True:
            try:
                state = await asyncio.to_thread(wda.refresh)
                await asyncio.to_thread(plane.heartbeat, state)
            except Exception as exc:
                print(f"[agent] heartbeat: {exc}", flush=True)

            try:
                jobs = await asyncio.to_thread(plane.claim_jobs)
            except Exception as exc:
                print(f"[agent] jobs: {exc}", flush=True)
                jobs = []

            for job in jobs:
                print(f"[agent] job #{job.get('id')} {job.get('type')}", flush=True)
                if job.get("type") in {"start", "start-all"}:
                    try:
                        await asyncio.to_thread(wda.ensure)
                    except Exception as exc:
                        await orch._broadcast({
                            "type": "error",
                            "username": job.get("username") or "",
                            "data": str(exc),
                            "timestamp": datetime.datetime.now().isoformat(),
                        })
                        continue
                try:
                    await handle_job(orch, job)
                except Exception as exc:
                    print(f"[agent] job failed: {exc}", flush=True)
                    await orch._broadcast({
                        "type": "error",
                        "username": job.get("username") or "",
                        "data": str(exc),
                        "timestamp": datetime.datetime.now().isoformat(),
                    })

            now = asyncio.get_event_loop().time()
            if now - last_snapshot > 4:
                last_snapshot = now
                try:
                    await asyncio.to_thread(
                        plane.snapshot,
                        {
                            "accounts": orch.get_status(),
                            "pendingFyp": orch.pending_fyp(),
                            "agent": wda.snapshot(),
                        },
                    )
                except Exception as exc:
                    print(f"[agent] snapshot: {exc}", flush=True)

            if once:
                break
            await asyncio.sleep(poll_seconds)
    finally:
        forwarder.cancel()
        try:
            await forwarder
        except asyncio.CancelledError:
            pass
        wda.stop()
