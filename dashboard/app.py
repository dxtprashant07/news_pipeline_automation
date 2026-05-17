"""
Stage 5 — Editor Review Dashboard (FastAPI).

Run with:
    python manage.py dashboard
    # or directly:
    uvicorn dashboard.app:app --host 127.0.0.1 --port 8000

Open http://127.0.0.1:8000/docs for the auto-generated Swagger UI.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from pathlib import Path

from .routes.articles import router as articles_router
from .routes.stats import router as stats_router
from core.config.settings import get_settings
from core.utils.logger import setup_logger

settings = get_settings()
setup_logger("news_pipeline", settings.log_level, "dashboard.log")

app = FastAPI(
    title="News Pipeline — Editor Dashboard",
    description="Stage 5: Review, approve, or reject AI-generated article drafts before publishing.",
    version="1.0.0",
)

allowed_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type", "X-API-Key"],
)

app.include_router(articles_router)
app.include_router(stats_router)

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"api_key": settings.dashboard_api_key},
    )
