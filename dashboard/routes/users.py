"""User management routes — change password, change username, invite via OTP."""
import secrets
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Request, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select

from core.db.session import get_session_factory
from core.config.settings import get_settings
from core.db.models import DashboardUser, PendingInvite
from dashboard.utils.crypto import hash_password, verify_password
from dashboard.utils.email_otp import send_otp
from core.utils.logger import get_logger

logger = get_logger("dashboard.users")
router = APIRouter(prefix="/users", tags=["users"])

OTP_TTL_MINUTES = 15


def _get_session():
    settings = get_settings()
    return get_session_factory(settings.database_url)


def _require_session(request: Request) -> dict:
    if not request.session.get("logged_in"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return request.session


def _require_admin(request: Request) -> dict:
    sess = _require_session(request)
    if not sess.get("is_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return sess


# ── Schemas ────────────────────────────────────────────────────────────────

class ChangeUsernameRequest(BaseModel):
    new_username: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class InviteRequest(BaseModel):
    email: str

class VerifyOtpRequest(BaseModel):
    email: str
    otp: str
    username: str
    password: str


# ── Routes ────────────────────────────────────────────────────────────────

@router.get("/me")
def get_me(request: Request):
    sess = _require_session(request)
    SessionFactory = _get_session()
    with SessionFactory() as db:
        user = db.get(DashboardUser, sess.get("user_id"))
        if not user:
            return {"username": sess.get("username"), "email": "", "is_admin": sess.get("is_admin", False)}
        return {"id": user.id, "username": user.username, "email": user.email, "is_admin": user.is_admin}


@router.post("/me/username")
def change_username(request: Request, body: ChangeUsernameRequest):
    sess = _require_session(request)
    new = body.new_username.strip()
    if not new or len(new) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")

    SessionFactory = _get_session()
    with SessionFactory() as db:
        user_id = sess.get("user_id")
        if not user_id:
            raise HTTPException(status_code=400, detail="Cannot change username for legacy admin. Set DASHBOARD_USERNAME in .env")

        existing = db.scalar(select(DashboardUser).where(DashboardUser.username == new))
        if existing and existing.id != user_id:
            raise HTTPException(status_code=409, detail="Username already taken")

        user = db.get(DashboardUser, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.username = new
        db.commit()
        request.session["username"] = new

    return {"status": "updated", "username": new}


@router.post("/me/password")
def change_password(request: Request, body: ChangePasswordRequest):
    sess = _require_session(request)
    user_id = sess.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Cannot change password for legacy admin. Set DASHBOARD_PASSWORD in .env")

    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")

    SessionFactory = _get_session()
    with SessionFactory() as db:
        user = db.get(DashboardUser, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if not verify_password(body.current_password, user.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        user.password_hash = hash_password(body.new_password)
        db.commit()

    return {"status": "updated"}


@router.post("/invite")
def invite_user(request: Request, body: InviteRequest):
    _require_admin(request)
    email = body.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email address")

    SessionFactory = _get_session()
    with SessionFactory() as db:
        existing = db.scalar(select(DashboardUser).where(DashboardUser.email == email))
        if existing:
            raise HTTPException(status_code=409, detail="A user with this email already exists")

        # Invalidate previous OTPs for this email
        old = db.scalars(select(PendingInvite).where(PendingInvite.email == email, PendingInvite.used == False)).all()
        for o in old:
            o.used = True

        otp = str(secrets.randbelow(900000) + 100000)  # 6-digit
        invite = PendingInvite(
            email=email,
            otp=otp,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES),
        )
        db.add(invite)
        db.commit()

    sent = send_otp(email, otp, purpose="account setup")
    if not sent:
        # Return OTP in response when email is not configured (dev mode)
        settings = get_settings()
        if not settings.smtp_user:
            return {"status": "sent", "dev_otp": otp, "note": "SMTP not configured — OTP shown here for dev use only"}

    return {"status": "sent"}


@router.post("/verify")
def verify_and_create(body: VerifyOtpRequest):
    email    = body.email.strip().lower()
    username = body.username.strip()
    password = body.password

    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    now = datetime.now(timezone.utc)
    SessionFactory = _get_session()
    with SessionFactory() as db:
        invite = db.scalar(
            select(PendingInvite)
            .where(PendingInvite.email == email, PendingInvite.otp == body.otp, PendingInvite.used == False)
            .order_by(PendingInvite.created_at.desc())
        )
        if not invite:
            raise HTTPException(status_code=400, detail="Invalid or expired verification code")
        if invite.expires_at.replace(tzinfo=timezone.utc) < now:
            raise HTTPException(status_code=400, detail="Verification code has expired. Request a new invite.")

        existing = db.scalar(select(DashboardUser).where(DashboardUser.username == username))
        if existing:
            raise HTTPException(status_code=409, detail="Username already taken")

        invite.used = True
        user = DashboardUser(
            username=username,
            email=email,
            password_hash=hash_password(password),
            is_admin=False,
        )
        db.add(user)
        db.commit()

    return {"status": "created"}


@router.get("/list")
def list_users(request: Request):
    _require_admin(request)
    SessionFactory = _get_session()
    with SessionFactory() as db:
        users = db.scalars(select(DashboardUser).order_by(DashboardUser.created_at.asc())).all()
        return [{"id": u.id, "username": u.username, "email": u.email,
                 "is_admin": u.is_admin, "created_at": u.created_at.isoformat()} for u in users]


@router.delete("/{user_id}")
def delete_user(user_id: int, request: Request):
    sess = _require_admin(request)
    if sess.get("user_id") == user_id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    SessionFactory = _get_session()
    with SessionFactory() as db:
        user = db.get(DashboardUser, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        db.delete(user)
        db.commit()
    return {"status": "deleted"}
