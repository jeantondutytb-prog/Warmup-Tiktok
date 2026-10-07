import asyncio
import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.api.routes import router
from app.core.check_orchestrator import CheckOrchestrator
from app.core.scheduler import HealthScheduler
from app.config import load_settings

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


def create_app(orchestrator: CheckOrchestrator | None = None, settings: dict | None = None) -> FastAPI:
    app = FastAPI(title="TikTok Health Monitor")
    app.include_router(router)

    base_dir = os.path.dirname(os.path.dirname(__file__))

    if settings is None:
        settings_path = os.path.join(base_dir, "config", "settings.yaml")
        settings = load_settings(settings_path)

    if orchestrator is None:
        os.makedirs(os.path.join(base_dir, "db"), exist_ok=True)
        db_url = settings.get("db_url", f"sqlite:///{os.path.join(base_dir, 'db', 'monitor.db')}")
        orchestrator = CheckOrchestrator(db_url=db_url, settings=settings)

    app.state.orchestrator = orchestrator

    interval = settings.get("check_interval_hours", 4)
    scheduler = HealthScheduler(orchestrator, interval_hours=interval)
    app.state.scheduler = scheduler

    @app.on_event("startup")
    async def on_startup():
        scheduler.start(asyncio.get_event_loop())

    @app.on_event("shutdown")
    async def on_shutdown():
        scheduler.stop()

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request):
        status = orchestrator.get_all_status()
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "accounts": status,
            "scheduler_running": scheduler.running,
        })

    return app


if __name__ == "__main__":
    import uvicorn
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8001)
