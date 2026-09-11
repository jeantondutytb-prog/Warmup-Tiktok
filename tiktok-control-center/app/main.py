"""API de contrôle pour les sessions de warmup TikTok."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).parent.parent
WARMUP_ROOT = ROOT.parent / "tiktok-warmup"
CONFIG_PATH = WARMUP_ROOT / "config" / "warmup_profiles.yaml"
LOGS_DIR = WARMUP_ROOT / "logs"
STATIC_DIR = ROOT / "static"

load_dotenv(ROOT / ".env")

app = FastAPI(title="TikTok Control Center", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_active_process: subprocess.Popen | None = None


class SessionStartRequest(BaseModel):
    profile: str = Field(default="observer")
    duration_minutes: int = Field(default=0, ge=0)


class ProfileInfo(BaseModel):
    name: str
    description: str
    like_probability: float
    session_duration_minutes: int
    max_videos_per_session: int


def load_config() -> dict[str, Any]:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def get_profiles() -> list[ProfileInfo]:
    config = load_config()
    profiles = []
    for name, data in config["profiles"].items():
        profiles.append(
            ProfileInfo(
                name=name,
                description=data["description"],
                like_probability=data["like_probability"],
                session_duration_minutes=data["session_duration_minutes"],
                max_videos_per_session=data["max_videos_per_session"],
            )
        )
    return profiles


def list_session_logs(limit: int = 20) -> list[dict]:
    if not LOGS_DIR.exists():
        return []
    files = sorted(LOGS_DIR.glob("session_*.json"), reverse=True)[:limit]
    logs = []
    for f in files:
        try:
            data = json.loads(f.read_text())
            data["filename"] = f.name
            logs.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    return logs


@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/profiles", response_model=list[ProfileInfo])
def api_profiles():
    return get_profiles()


@app.get("/api/sessions")
def api_sessions():
    return list_session_logs()


@app.get("/api/sessions/{filename}")
def api_session_detail(filename: str):
    path = LOGS_DIR / filename
    if not path.exists() or ".." in filename:
        raise HTTPException(404, "Session introuvable")
    return json.loads(path.read_text())


@app.get("/api/status")
def api_status():
    global _active_process
    running = _active_process is not None and _active_process.poll() is None
    return {
        "running": running,
        "pid": _active_process.pid if running and _active_process else None,
    }


@app.post("/api/sessions/start")
def start_session(req: SessionStartRequest):
    global _active_process

    if _active_process and _active_process.poll() is None:
        raise HTTPException(409, "Une session est déjà en cours")

    profiles = [p.name for p in get_profiles()]
    if req.profile not in profiles:
        raise HTTPException(400, f"Profil inconnu. Disponibles: {profiles}")

    cmd = [
        sys.executable,
        "-m",
        "src.main",
        "--profile",
        req.profile,
    ]
    if req.duration_minutes > 0:
        cmd.extend(["--duration", str(req.duration_minutes)])

    env = os.environ.copy()
    env["PYTHONPATH"] = str(WARMUP_ROOT)

    _active_process = subprocess.Popen(
        cmd,
        cwd=str(WARMUP_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    return {
        "started": True,
        "pid": _active_process.pid,
        "profile": req.profile,
        "duration_minutes": req.duration_minutes,
    }


@app.post("/api/sessions/stop")
def stop_session():
    global _active_process

    if not _active_process or _active_process.poll() is not None:
        raise HTTPException(404, "Aucune session active")

    _active_process.terminate()
    try:
        _active_process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        _active_process.kill()

    pid = _active_process.pid
    _active_process = None
    return {"stopped": True, "pid": pid}


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
