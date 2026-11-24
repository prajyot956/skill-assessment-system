import hashlib
import secrets
from datetime import timedelta

from flask import Blueprint, current_app, request
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf.csrf import generate_csrf

from app.extensions import db, limiter
from app.models import PasswordResetToken, User, UserProfile
from app.models.base import utcnow
from app.services.mailer import send_email
from app.utils.decorators import get_json_body
from app.utils.responses import ApiError, ValidationError, ok
from app.utils.validators import clean_str, is_valid_email, normalize_email, password_message

bp = Blueprint("auth", __name__, url_prefix="/api/auth")

_DUMMY = None  # lazily built real hash so unknown-email logins cost the same as wrong-password ones


def _dummy_check(password: str):
    global _DUMMY
    if _DUMMY is None:
        u = User()
        u.set_password(secrets.token_hex(8))
        _DUMMY = u.password_hash
    from werkzeug.security import check_password_hash
    check_password_hash(_DUMMY, password or "")


@bp.get("/csrf")
def csrf_token():
    return ok({"csrf_token": generate_csrf()})


@bp.post("/register")
@limiter.limit("10 per hour")
def register():
    data = get_json_body()
    errors = {}
    try:
        name = clean_str(data.get("full_name"), 120, required=True, field="Full name")
    except ValueError as e:
        errors["full_name"] = str(e)
        name = None
    email = normalize_email(data.get("email"))
    if not is_valid_email(email):
        errors["email"] = "Enter a valid email address."
    password, confirm = data.get("password") or "", data.get("confirm_password") or ""
    if (msg := password_message(password)):
        errors["password"] = msg
    elif password != confirm:
        errors["confirm_password"] = "Passwords do not match."
    if errors:
        raise ValidationError(errors)
    if User.query.filter_by(email=email).first():
        raise ValidationError({"email": "An account with this email already exists."})

    user = User(full_name=name, email=email)
    user.set_password(password)
    user.profile = UserProfile()
    db.session.add(user)
    db.session.commit()
    login_user(user)
    return ok(user.to_dict(), 201)


@bp.post("/login")
@limiter.limit("10 per minute")
def login():
    data = get_json_body()
    email = normalize_email(data.get("email"))
    password = data.get("password") or ""
    user = User.query.filter_by(email=email).first() if email else None
    if user is None:
        _dummy_check(password)
    if user is None or not user.check_password(password) or not user.is_active:
        raise ApiError("invalid_credentials", "Incorrect email or password.", 401)
    login_user(user, remember=bool(data.get("remember")))
    user.last_login_at = utcnow()
    db.session.commit()
    return ok(user.to_dict())


@bp.post("/logout")
def logout():
    logout_user()
    return ok({"logged_out": True})


@bp.get("/me")
def me():
    if not current_user.is_authenticated:
        raise ApiError("unauthorized", "Please sign in to continue.", 401)
    return ok(current_user.to_dict())


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@bp.post("/forgot-password")
@limiter.limit("5 per hour")
def forgot_password():
    """Always answers the same way so the endpoint cannot be used to find registered emails."""
    email = normalize_email(get_json_body().get("email"))
    user = User.query.filter_by(email=email).first() if is_valid_email(email) else None
    if user and user.is_active:
        raw = secrets.token_urlsafe(32)
        PasswordResetToken.query.filter_by(user_id=user.id, used_at=None).delete()
        db.session.add(PasswordResetToken(
            user_id=user.id, token_hash=_hash(raw),
            expires_at=utcnow() + timedelta(minutes=current_app.config["PASSWORD_RESET_TTL_MINUTES"])))
        db.session.commit()
        link = f"{current_app.config['FRONTEND_URL']}/reset-password?token={raw}"
        send_email(user.email, "Reset your Skill Assessment System password",
                   f"Use this link to choose a new password (valid for "
                   f"{current_app.config['PASSWORD_RESET_TTL_MINUTES']} minutes):\n\n{link}\n\n"
                   "If you did not request this, you can ignore this email.")
    return ok({"message": "If that email is registered, a reset link has been sent."})


@bp.post("/reset-password")
@limiter.limit("10 per hour")
def reset_password():
    data = get_json_body()
    password, confirm = data.get("password") or "", data.get("confirm_password") or ""
    if (msg := password_message(password)):
        raise ValidationError({"password": msg})
    if password != confirm:
        raise ValidationError({"confirm_password": "Passwords do not match."})
    token = PasswordResetToken.query.filter_by(token_hash=_hash(data.get("token") or "")).first()
    if not token or token.used_at or token.expires_at < utcnow():
        raise ApiError("invalid_token", "This reset link is invalid or has expired.", 400)
    user = db.session.get(User, token.user_id)
    user.set_password(password)
    token.used_at = utcnow()
    db.session.commit()
    return ok({"message": "Password updated. You can now sign in."})


@bp.post("/change-password")
@login_required
@limiter.limit("10 per hour")
def change_password():
    data = get_json_body()
    if not current_user.check_password(data.get("current_password") or ""):
        raise ValidationError({"current_password": "Current password is incorrect."})
    new, confirm = data.get("new_password") or "", data.get("confirm_password") or ""
    if (msg := password_message(new)):
        raise ValidationError({"new_password": msg})
    if new != confirm:
        raise ValidationError({"confirm_password": "Passwords do not match."})
    current_user.set_password(new)
    db.session.commit()
    return ok({"message": "Password changed."})
