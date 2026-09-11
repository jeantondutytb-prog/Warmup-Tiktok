import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport
from app.main import create_app


@pytest.fixture
def mock_orchestrator():
    orch = MagicMock()
    orch.get_status.return_value = {
        "u1": {
            "status": "idle",
            "ramp_up_day": 1,
            "protocol_day": 1,
            "role": "flagship",
            "protected": False,
            "used_24h": {"likes": 0, "follows": 0, "comments": 0},
            "caps_24h": {"likes": (20, 30), "follows": (10, 15), "comments": (0, 3)},
            "last_session": None,
            "counters": {"likes": 0, "follows": 0, "comments": 0, "videos_watched": 0, "scrolls": 0},
            "recent_logs": [],
        },
        "locked": {
            "status": "idle",
            "ramp_up_day": 1,
            "protocol_day": 1,
            "role": "capiria",
            "protected": True,
            "used_24h": {"likes": 0, "follows": 0, "comments": 0},
            "caps_24h": {"likes": (20, 30), "follows": (10, 15), "comments": (0, 3)},
            "last_session": {
                "id": 3, "keyword": "filtre digicam",
                "started_at": "2026-09-03T10:00:00", "completed": True,
                "fyp_niche_count": 3, "fyp_verdict": "ready",
            },
            "counters": {"likes": 0, "follows": 0, "comments": 0, "videos_watched": 0, "scrolls": 0},
            "recent_logs": [],
        }
    }
    orch.start_all = AsyncMock()
    orch.stop_all = AsyncMock()
    orch.start_account = AsyncMock()
    orch.stop_account = AsyncMock()
    return orch


@pytest.mark.asyncio
async def test_get_status(mock_orchestrator):
    app = create_app(mock_orchestrator)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "u1" in data


@pytest.mark.asyncio
async def test_start_all(mock_orchestrator):
    app = create_app(mock_orchestrator)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/start-all")
    assert resp.status_code == 200
    mock_orchestrator.start_all.assert_awaited_once()


@pytest.mark.asyncio
async def test_stop_all(mock_orchestrator):
    app = create_app(mock_orchestrator)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/stop-all")
    assert resp.status_code == 200
    mock_orchestrator.stop_all.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_single_account(mock_orchestrator):
    app = create_app(mock_orchestrator)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/start/u1")
    assert resp.status_code == 200
    mock_orchestrator.start_account.assert_awaited_once_with("u1", force=False)


@pytest.mark.asyncio
async def test_stop_single_account(mock_orchestrator):
    app = create_app(mock_orchestrator)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/stop/u1")
    assert resp.status_code == 200
    mock_orchestrator.stop_account.assert_awaited_once_with("u1")


@pytest.mark.asyncio
async def test_dashboard_page(mock_orchestrator):
    app = create_app(mock_orchestrator)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    # Un compte protégé n'expose pas de bouton Start.
    assert "Aucun warmup sur ce compte." in resp.text
    assert "startAccount('locked')" not in resp.text
    assert "startAccount('u1')" in resp.text
    # L'état protocole est visible sur la carte.
    assert "Jour 1 / 14" in resp.text
    assert "filtre digicam" in resp.text
    assert "FYP ready" in resp.text
