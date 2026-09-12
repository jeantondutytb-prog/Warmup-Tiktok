import os

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import build_session_factory
from app.routes import api, auth
from app.services import ensure_demo_accounts
from app.tiktok_client import TikTokClient


def create_app() -> FastAPI:
    settings = get_settings()
    session_factory = build_session_factory(settings.db_path)

    if settings.demo_mode:
        with session_factory() as session:
            ensure_demo_accounts(session)

    app = FastAPI(title="TikTok Studio Hub")
    app.state.settings = settings
    app.state.session_factory = session_factory
    app.state.tiktok_client = TikTokClient(settings.client_key, settings.client_secret)

    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    app.include_router(auth.router)
    app.include_router(api.router)

    @app.get("/")
    async def index():
        return FileResponse(os.path.join(static_dir, "index.html"))

    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(create_app(), host="0.0.0.0", port=8080)
