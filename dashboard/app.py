"""
Stage 5 — Editor Review Dashboard (FastAPI).

Run with:
    python manage.py dashboard
    uvicorn dashboard.app:app --host 127.0.0.1 --port 8000
"""
import hmac
from fastapi import FastAPI, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy import select
from starlette.middleware.sessions import SessionMiddleware

from .routes.articles import router as articles_router
from .routes.stats    import router as stats_router
from .routes.pipeline import router as pipeline_router
from .routes.users    import router as users_router
from dashboard.utils.crypto import hash_password, verify_password
from core.config.settings import get_settings
from core.db.session import get_session_factory
from core.db.models import DashboardUser
from core.utils.logger import setup_logger, get_logger

settings = get_settings()
setup_logger("news_pipeline", settings.log_level, "dashboard.log")
logger = get_logger("dashboard.app")

app = FastAPI(
    title="News Pipeline — Editor Dashboard",
    description="Stage 5: Review, approve, or reject AI-generated article drafts.",
    version="1.0.0",
)

_session_secret = settings.dashboard_secret_key or "dev-only-secret-set-in-production"
app.add_middleware(
    SessionMiddleware,
    secret_key=_session_secret,
    session_cookie="np_session",
    max_age=86400 * 7,
    same_site="lax",
    https_only=False,
)

allowed_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-API-Key"],
)

app.include_router(articles_router)
app.include_router(stats_router)
app.include_router(pipeline_router)
app.include_router(users_router)

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


# ── Auto-migrate .env admin into DB on first startup ──────────────────────

def _bootstrap_admin():
    if not settings.dashboard_password:
        return
    try:
        SessionFactory = get_session_factory(settings.database_url)
        with SessionFactory() as db:
            existing = db.scalar(select(DashboardUser).where(DashboardUser.is_admin == True))
            if existing:
                return
            admin = DashboardUser(
                username=settings.dashboard_username or "admin",
                email="admin@localhost",
                password_hash=hash_password(settings.dashboard_password),
                is_admin=True,
            )
            db.add(admin)
            db.commit()
            logger.info("Bootstrapped admin user '%s' from .env", admin.username)
    except Exception as exc:
        logger.warning("Could not bootstrap admin user: %s", exc)


_bootstrap_admin()


# ── Auth helpers ──────────────────────────────────────────────────────────

def _db_authenticate(username: str, password: str):
    """Return DashboardUser if credentials match, else None."""
    try:
        SessionFactory = get_session_factory(settings.database_url)
        with SessionFactory() as db:
            user = db.scalar(select(DashboardUser).where(DashboardUser.username == username))
            if user and verify_password(password, user.password_hash):
                return user
    except Exception:
        pass
    return None


def _auth_required(request: Request) -> bool:
    if not settings.dashboard_password:
        return False
    return not request.session.get("logged_in")


# ── Routes ────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/login")
def login_page(request: Request):
    if not _auth_required(request):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(request=request, name="login.html", context={"error": None, "tab": "login"})


@app.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    user = _db_authenticate(username, password)
    if user:
        request.session["logged_in"]  = True
        request.session["user_id"]    = user.id
        request.session["username"]   = user.username
        request.session["is_admin"]   = user.is_admin
        return RedirectResponse("/", status_code=302)

    # Fallback: .env credentials (dev / legacy)
    if settings.dashboard_password:
        expected_user = settings.dashboard_username or "admin"
        u_ok = hmac.compare_digest(username.encode(), expected_user.encode())
        p_ok = hmac.compare_digest(password.encode(), settings.dashboard_password.encode())
        if u_ok and p_ok:
            request.session["logged_in"] = True
            request.session["user_id"]   = None
            request.session["username"]  = username
            request.session["is_admin"]  = True
            return RedirectResponse("/", status_code=302)

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": "Invalid username or password", "tab": "login"},
    )


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)


@app.get("/setup")
def setup_page(request: Request, email: str = ""):
    return templates.TemplateResponse(
        request=request, name="login.html",
        context={"error": None, "tab": "setup", "prefill_email": email}
    )


@app.get("/")
def index(request: Request):
    if _auth_required(request):
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "api_key":  settings.dashboard_api_key,
            "username": request.session.get("username", settings.dashboard_username),
            "is_admin": request.session.get("is_admin", True),
        },
    )
