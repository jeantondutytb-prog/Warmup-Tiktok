import asyncio
import json
import pytest
from unittest.mock import patch, AsyncMock
from app.core.check_orchestrator import CheckOrchestrator


def make_settings():
    return {
        "accounts": [
            {"username": "u1", "tiktok_handle": "@u1", "role": "flagship"},
            {"username": "u2", "tiktok_handle": "@u2", "role": "secondary"},
        ],
        "scoring": {
            "weights": {
                "follower_ratio": 0.15,
                "engagement_rate": 0.30,
                "video_count": 0.10,
                "growth_trend": 0.25,
                "consistency": 0.20,
            },
            "thresholds": {"healthy": 70, "warning": 40},
        },
    }


def make_orchestrator():
    return CheckOrchestrator(db_url="sqlite:///:memory:", settings=make_settings())


def test_init_creates_accounts():
    orch = make_orchestrator()
    status = orch.get_all_status()
    assert "u1" in status
    assert "u2" in status
    assert status["u1"]["role"] == "flagship"


def test_get_all_status_structure():
    orch = make_orchestrator()
    status = orch.get_all_status()
    for username, data in status.items():
        assert "tiktok_handle" in data
        assert "has_cookies" in data
        assert "last_score" in data
        assert "history" in data


def test_subscribe_returns_queue():
    orch = make_orchestrator()
    queue = orch.subscribe()
    assert isinstance(queue, asyncio.Queue)


@pytest.mark.asyncio
async def test_check_account_no_cookies():
    orch = make_orchestrator()
    result = await orch.check_account("u1")
    assert result["status"] == "failed"
    assert "cookies" in result["error"].lower()


@pytest.mark.asyncio
async def test_check_account_with_cookies():
    orch = make_orchestrator()
    with orch.Session() as db:
        from app.models.models import MonitoredAccount
        acc = db.query(MonitoredAccount).filter_by(username="u1").first()
        acc.set_cookies({"sessionid": "test123"})
        db.commit()

    mock_profile = {
        "handle": "u1",
        "followers": 2000,
        "following": 300,
        "total_likes": 50000,
        "video_count": 20,
        "bio": "Test",
        "verified": False,
        "nickname": "User1",
    }

    with patch("app.core.check_orchestrator.scrape_profile", new_callable=AsyncMock, return_value=mock_profile):
        result = await orch.check_account("u1")

    assert result["status"] == "completed"
    assert "score" in result
    assert "level" in result
    assert result["level"] in ("healthy", "warning", "critical")


@pytest.mark.asyncio
async def test_check_account_scrape_error():
    orch = make_orchestrator()
    with orch.Session() as db:
        from app.models.models import MonitoredAccount
        acc = db.query(MonitoredAccount).filter_by(username="u1").first()
        acc.set_cookies({"sessionid": "test123"})
        db.commit()

    with patch("app.core.check_orchestrator.scrape_profile", new_callable=AsyncMock, side_effect=Exception("Network error")):
        result = await orch.check_account("u1")

    assert result["status"] == "failed"
    assert "Network error" in result["error"]


@pytest.mark.asyncio
async def test_check_unknown_account():
    orch = make_orchestrator()
    with pytest.raises(ValueError, match="Unknown account"):
        await orch.check_account("nonexistent")


@pytest.mark.asyncio
async def test_check_broadcasts_events():
    orch = make_orchestrator()
    queue = orch.subscribe()

    with orch.Session() as db:
        from app.models.models import MonitoredAccount
        acc = db.query(MonitoredAccount).filter_by(username="u1").first()
        acc.set_cookies({"sessionid": "test123"})
        db.commit()

    mock_profile = {
        "handle": "u1", "followers": 1000, "following": 100,
        "total_likes": 25000, "video_count": 15,
        "bio": "", "verified": False, "nickname": "",
    }

    with patch("app.core.check_orchestrator.scrape_profile", new_callable=AsyncMock, return_value=mock_profile):
        await orch.check_account("u1")

    events = []
    while not queue.empty():
        events.append(queue.get_nowait())

    types = [e["type"] for e in events]
    assert "check_start" in types
    assert "check_done" in types


@pytest.mark.asyncio
async def test_check_all():
    orch = make_orchestrator()
    mock_profile = {
        "handle": "test", "followers": 1000, "following": 100,
        "total_likes": 25000, "video_count": 15,
        "bio": "", "verified": False, "nickname": "",
    }

    with orch.Session() as db:
        from app.models.models import MonitoredAccount
        for acc in db.query(MonitoredAccount).all():
            acc.set_cookies({"sessionid": "test"})
        db.commit()

    with patch("app.core.check_orchestrator.scrape_profile", new_callable=AsyncMock, return_value=mock_profile):
        results = await orch.check_all()

    assert "u1" in results
    assert "u2" in results
    assert results["u1"]["status"] == "completed"


@pytest.mark.asyncio
async def test_check_updates_account():
    orch = make_orchestrator()
    with orch.Session() as db:
        from app.models.models import MonitoredAccount
        acc = db.query(MonitoredAccount).filter_by(username="u1").first()
        acc.set_cookies({"sessionid": "test"})
        db.commit()

    mock_profile = {
        "handle": "u1", "followers": 3000, "following": 200,
        "total_likes": 80000, "video_count": 30,
        "bio": "Hello", "verified": False, "nickname": "U1",
    }

    with patch("app.core.check_orchestrator.scrape_profile", new_callable=AsyncMock, return_value=mock_profile):
        await orch.check_account("u1")

    status = orch.get_all_status()
    assert status["u1"]["last_score"] is not None
    assert status["u1"]["last_level"] is not None
    assert status["u1"]["last_check_at"] is not None
    assert len(status["u1"]["history"]) == 1
