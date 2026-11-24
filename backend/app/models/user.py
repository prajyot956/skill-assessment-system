from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from .base import TimestampMixin, user_fk, utcnow


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), nullable=False, unique=True, index=True)  # stored lowercase
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    is_active_account = db.Column(db.Boolean, nullable=False, default=True)
    last_login_at = db.Column(db.DateTime)

    profile = db.relationship("UserProfile", back_populates="user", uselist=False,
                              cascade="all, delete-orphan", passive_deletes=True)

    # Flask-Login: deactivated accounts cannot keep a session
    @property
    def is_active(self):
        return self.is_active_account

    def set_password(self, raw: str):
        self.password_hash = generate_password_hash(raw, method="scrypt")

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)

    def to_dict(self):
        return {"id": self.id, "full_name": self.full_name, "email": self.email,
                "is_admin": self.is_admin, "created_at": self.created_at.isoformat()}


class PasswordResetToken(db.Model):
    """Only a SHA-256 hash of the emailed token is stored."""
    __tablename__ = "password_reset_tokens"
    id = db.Column(db.Integer, primary_key=True)
    user_id = user_fk()
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
