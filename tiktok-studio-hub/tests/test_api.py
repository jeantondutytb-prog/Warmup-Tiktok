import os
import tempfile

import pytest
from httpx import ASGITransport, AsyncClient

os.environ["DEMO_MODE"] = "1"
os.environ.pop("TIKTOK_CLIENT_KEY", None)
os.environ.pop("TIKTOK_CLIENT_SECRET", None)

from app.config import get_settings
from app.main import create_app


@pytest.fixture
def app(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.setenv("TIKTOK_CLIENT_KEY", "")
    monkeypatch.setenv("TIKTOK_CLIENT_SECRET", "")

    from app import config, database, main

    config.get_settings.cache_clear() if hasattr(config.get_settings, "cache_clear") else None

    settings = get_settings()
    object.__setattr__(settings, "db_path", str(db_path))
    object.__setattr__(settings, "demo_mode", True)

    application = main.create_app()
    application.state.settings = settings
    application.state.session_factory = database.build_session_factory(str(db_path))
    return application


@pytest.mark.asyncio
async def test_dashboard_returns_aggregated_totals(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["totals"]["accounts"] == 4
    assert data["totals"]["followers"] > 0
    assert len(data["accounts"]) == 4


@pytest.mark.asyncio
async def test_index_page_loads(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/")
    assert resp.status_code == 200
    assert "TikTok Studio" in resp.text


@pytest.mark.asyncio
async def test_delete_account(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        dash = await client.get("/api/dashboard")
        account_id = dash.json()["accounts"][0]["id"]
        del_resp = await client.delete(f"/api/accounts/{account_id}")
        assert del_resp.status_code == 200
        dash2 = await client.get("/api/dashboard")
        assert dash2.json()["totals"]["accounts"] == 3
