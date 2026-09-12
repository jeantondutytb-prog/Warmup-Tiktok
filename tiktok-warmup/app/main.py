import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.api.routes import router
from app.core.orchestrator import Orchestrator

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


def create_app(orchestrator: Orchestrator | None = None) -> FastAPI:
    app = FastAPI(title="TikTok Stats")
    app.include_router(router)

    if orchestrator is None:
        base_dir = os.path.dirname(os.path.dirname(__file__))
        os.makedirs(os.path.join(base_dir, "db"), exist_ok=True)
        orchestrator = Orchestrator(
            db_url=f"sqlite:///{os.path.join(base_dir, 'db', 'warmup.db')}",
            config_dir=os.path.join(base_dir, "config"),
        )
    app.state.orchestrator = orchestrator

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request):
        status = orchestrator.get_status()
        summary = orchestrator.get_summary()
        return templates.TemplateResponse(
            "dashboard.html",
            {"request": request, "accounts": status, "summary": summary},
        )

    return app


if __name__ == "__main__":
    import uvicorn
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)
