"""Client HTTP du cockpit Vercel."""

from __future__ import annotations

import os
from typing import Any

import httpx


class ControlPlane:
    def __init__(self, base_url: str | None = None, token: str | None = None) -> None:
        self.base_url = (base_url or os.environ.get("WARMUP_URL", "")).rstrip("/")
        self.token = token or os.environ.get("AGENT_TOKEN", "")
        if not self.base_url:
            raise RuntimeError("WARMUP_URL manquant (ex. https://tiktok-warmup.vercel.app)")
        if not self.token:
            raise RuntimeError("AGENT_TOKEN manquant — même valeur que sur Vercel")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def heartbeat(self, payload: dict[str, Any]) -> None:
        self._post("/api/agent/heartbeat", payload)

    def claim_jobs(self) -> list[dict[str, Any]]:
        data = self._post("/api/agent/jobs", {})
        jobs = data.get("jobs") if isinstance(data, dict) else None
        return jobs if isinstance(jobs, list) else []

    def snapshot(self, payload: dict[str, Any]) -> None:
        self._post("/api/agent/snapshot", payload)

    def events(self, events: list[dict[str, Any]]) -> None:
        if not events:
            return
        self._post("/api/agent/events", {"events": events})

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(url, headers=self._headers(), json=payload)
        if resp.status_code >= 400:
            raise RuntimeError(f"{path} → {resp.status_code} {resp.text[:200]}")
        data = resp.json()
        return data if isinstance(data, dict) else {}
