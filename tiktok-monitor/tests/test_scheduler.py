import asyncio
import time
from unittest.mock import patch, AsyncMock, MagicMock
from app.core.scheduler import HealthScheduler
from app.core.check_orchestrator import CheckOrchestrator


def make_scheduler():
    orch = MagicMock(spec=CheckOrchestrator)
    orch.check_all = AsyncMock(return_value={})
    return HealthScheduler(orchestrator=orch, interval_hours=1.0)


def test_scheduler_init():
    sched = make_scheduler()
    assert sched.interval_hours == 1.0
    assert not sched.running


def test_scheduler_start_stop():
    sched = make_scheduler()
    loop = asyncio.new_event_loop()
    try:
        sched.start(loop)
        assert sched.running is True
        assert sched.get_next_run() is not None
        sched.stop()
        assert sched.running is False
    finally:
        loop.close()


def test_scheduler_next_run():
    sched = make_scheduler()
    loop = asyncio.new_event_loop()
    try:
        sched.start(loop)
        next_run = sched.get_next_run()
        assert next_run is not None
        assert "T" in next_run
        sched.stop()
    finally:
        loop.close()


def test_scheduler_not_started_next_run():
    sched = make_scheduler()
    assert sched.get_next_run() is None
