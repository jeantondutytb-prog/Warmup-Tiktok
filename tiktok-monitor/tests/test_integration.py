import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from app.config import load_settings
from app.core.check_orchestrator import CheckOrchestrator
from app.main import create_app


def make_integration_orchestrator():
    settings = {
        "accounts": [
            {"username": "emma.srpt", "tiktok_handle": "@emma.srpt", "role": "flagship"},
            {"username": "chloe.rtps", "tiktok_handle": "@chloe.rtps", "role": "secondary"},
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
    return CheckOrchestrator(db_url="sqlite:///:memory:", settings=settings)


MOCK_PROFILE = {
    "handle": "test",
    "followers": 5000,
    "following": 400,
    "total_likes": 120000,
    "video_count": 45,
    "bio": "Integration test",
    "verified": False,
    "nickname": "Test",
}


@pytest.mark.asyncio
async def test_full_flow():
    orch = make_integration_orchestrator()

    status = orch.get_all_status()
    assert "emma.srpt" in status
    assert "chloe.rtps" in status
    assert status["emma.srpt"]["last_score"] is None

    with orch.Session() as db:
        from app.models.models import MonitoredAccount
        for acc in db.query(MonitoredAccount).all():
            acc.set_cookies({"sessionid": "integration_test_cookie"})
        db.commit()

    with patch("app.core.check_orchestrator.scrape_profile", new_callable=AsyncMock, return_value=MOCK_PROFILE):
        results = await orch.check_all()

    assert results["emma.srpt"]["status"] == "completed"
    assert results["chloe.rtps"]["status"] == "completed"
    assert results["emma.srpt"]["score"] > 0
    assert results["emma.srpt"]["level"] in ("healthy", "warning", "critical")

    status = orch.get_all_status()
    assert status["emma.srpt"]["last_score"] is not None
    assert status["emma.srpt"]["last_check_at"] is not None
    assert len(status["emma.srpt"]["history"]) == 1


@pytest.mark.asyncio
async def test_api_integration():
    orch = make_integration_orchestrator()

    with orch.Session() as db:
        from app.models.models import MonitoredAccount
        for acc in db.query(MonitoredAccount).all():
            acc.set_cookies({"sessionid": "test"})
        db.commit()

    app = create_app(orch, settings={"check_interval_hours": 4})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "emma.srpt" in resp.text

        resp = await client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "emma.srpt" in data
        assert "chloe.rtps" in data

        with patch("app.core.check_orchestrator.scrape_profile", new_callable=AsyncMock, return_value=MOCK_PROFILE):
            resp = await client.post("/api/check/emma.srpt")
            assert resp.status_code == 200
            result = resp.json()
            assert result["status"] == "completed"

        resp = await client.get("/api/history/emma.srpt")
        assert resp.status_code == 200
        history = resp.json()
        assert len(history["history"]) == 1

        resp = await client.get("/api/scheduler")
        assert resp.status_code == 200
        assert resp.json()["interval_hours"] == 4


@pytest.mark.asyncio
async def test_error_handling_integration():
    orch = make_integration_orchestrator()
    app = create_app(orch, settings={"check_interval_hours": 4})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/check/nonexistent")
        assert resp.status_code == 404

        resp = await client.get("/api/history/nonexistent")
        assert resp.status_code == 404

        resp = await client.post("/api/check/emma.srpt")
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "failed"
        assert "cookies" in result["error"].lower()
