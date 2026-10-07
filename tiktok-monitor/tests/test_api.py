import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport
from app.main import create_app
from app.core.check_orchestrator import CheckOrchestrator


def make_mock_orchestrator():
    orch = MagicMock(spec=CheckOrchestrator)
    orch.Session = MagicMock()
    orch.get_all_status.return_value = {
        "u1": {
            "tiktok_handle": "@u1",
            "role": "flagship",
            "has_cookies": True,
            "last_check_at": "2026-10-07T10:00:00",
            "last_score": 75.0,
            "last_level": "healthy",
            "history": [],
        }
    }
    orch.check_all = AsyncMock(return_value={"u1": {"status": "completed", "score": 75.0, "level": "healthy"}})
    orch.check_account = AsyncMock(return_value={"status": "completed", "score": 75.0, "level": "healthy"})
    orch.subscribe.return_value = MagicMock()
    return orch


@pytest.fixture
def mock_orch():
    return make_mock_orchestrator()


@pytest.mark.asyncio
async def test_get_status(mock_orch):
    app = create_app(mock_orch, settings={"check_interval_hours": 4})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "u1" in data


@pytest.mark.asyncio
async def test_check_all(mock_orch):
    app = create_app(mock_orch, settings={"check_interval_hours": 4})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/check-all")
    assert resp.status_code == 200
    mock_orch.check_all.assert_awaited_once()


@pytest.mark.asyncio
async def test_check_single(mock_orch):
    app = create_app(mock_orch, settings={"check_interval_hours": 4})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/check/u1")
    assert resp.status_code == 200
    mock_orch.check_account.assert_awaited_once_with("u1")


@pytest.mark.asyncio
async def test_check_unknown(mock_orch):
    mock_orch.check_account = AsyncMock(side_effect=ValueError("Unknown account: xxx"))
    app = create_app(mock_orch, settings={"check_interval_hours": 4})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/check/xxx")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_history(mock_orch):
    app = create_app(mock_orch, settings={"check_interval_hours": 4})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/history/u1")
    assert resp.status_code == 200
    assert "history" in resp.json()


@pytest.mark.asyncio
async def test_history_unknown(mock_orch):
    app = create_app(mock_orch, settings={"check_interval_hours": 4})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/history/xxx")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_scheduler_status(mock_orch):
    app = create_app(mock_orch, settings={"check_interval_hours": 4})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/scheduler")
    assert resp.status_code == 200
    data = resp.json()
    assert "running" in data
    assert "interval_hours" in data


@pytest.mark.asyncio
async def test_dashboard_page(mock_orch):
    app = create_app(mock_orch, settings={"check_interval_hours": 4})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
