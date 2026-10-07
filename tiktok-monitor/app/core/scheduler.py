from __future__ import annotations
import asyncio
from apscheduler.schedulers.background import BackgroundScheduler
from app.core.check_orchestrator import CheckOrchestrator


class HealthScheduler:
    def __init__(self, orchestrator: CheckOrchestrator, interval_hours: float = 4.0):
        self.orchestrator = orchestrator
        self.interval_hours = interval_hours
        self._scheduler = BackgroundScheduler()
        self._loop: asyncio.AbstractEventLoop | None = None

    def start(self, loop: asyncio.AbstractEventLoop | None = None):
        self._loop = loop or asyncio.get_event_loop()
        self._scheduler.add_job(
            self._run_checks,
            "interval",
            hours=self.interval_hours,
            id="health_check_all",
            replace_existing=True,
        )
        self._scheduler.start()

    def stop(self):
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    def _run_checks(self):
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.orchestrator.check_all(),
                self._loop,
            )

    @property
    def running(self) -> bool:
        return self._scheduler.running

    def get_next_run(self) -> str | None:
        job = self._scheduler.get_job("health_check_all")
        if job and job.next_run_time:
            return job.next_run_time.isoformat()
        return None
