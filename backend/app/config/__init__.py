"""Environment-driven configuration. No secrets are hardcoded."""
import os
import secrets
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent
# Load .env before BaseConfig class attributes are evaluated
load_dotenv(PROJECT_DIR / ".env")


def _bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _database_url() -> str:
    url = os.environ.get(
        "DATABASE_URL", f"sqlite:///{(BACKEND_DIR / 'instance' / 'app.db').as_posix()}"
    )
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


class BaseConfig:
    ENV_NAME = "base"
    DEBUG = False
    TESTING = False

    # SECRET_KEY must come from the environment. Development falls back to a
    # random per-process key (sessions reset on restart); production refuses to start.
    SECRET_KEY = os.environ.get("SECRET_KEY")

    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Sessions / cookies
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool("COOKIE_SECURE", False)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = _bool("COOKIE_SECURE", False)
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)

    # CSRF (token is delivered via GET /api/auth/csrf, sent as X-CSRFToken)
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None  # token lives as long as the session
    WTF_CSRF_HEADERS = ["X-CSRFToken"]

    # Uploads
    UPLOAD_DIR = os.environ.get("UPLOAD_DIR", str(BACKEND_DIR / "uploads"))
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_UPLOAD_MB", "5")) * 1024 * 1024

    # CORS (only needed if the frontend is served from another origin)
    CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
    FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")

    # Rate limiting
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True

    # Password reset
    PASSWORD_RESET_TTL_MINUTES = 30

    # Optional SMTP (if unset, reset links are written to the server log)
    SMTP_HOST = os.environ.get("SMTP_HOST")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("SMTP_USER")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
    SMTP_FROM = os.environ.get("SMTP_FROM", "no-reply@skill-assessment.local")

    # AI provider (the app works without it)
    # Supported values: none | anthropic | groq
    AI_PROVIDER = os.environ.get("AI_PROVIDER", "none")
    AI_API_KEY = os.environ.get("AI_API_KEY")
    AI_MODEL = os.environ.get("AI_MODEL", "openai/gpt-oss-120b")
    AI_TIMEOUT_SECONDS = int(os.environ.get("AI_TIMEOUT_SECONDS", "30"))


class DevelopmentConfig(BaseConfig):
    ENV_NAME = "development"
    DEBUG = True
    SECRET_KEY = BaseConfig.SECRET_KEY or secrets.token_hex(32)


class TestingConfig(BaseConfig):
    ENV_NAME = "testing"
    TESTING = True
    SECRET_KEY = "test-only-secret-not-for-use"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    UPLOAD_DIR = str(BACKEND_DIR / "uploads" / "_test")
    AI_PROVIDER = "none"
    AI_API_KEY = None


class ProductionConfig(BaseConfig):
    ENV_NAME = "production"
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True

    @classmethod
    def validate(cls):
        if not cls.SECRET_KEY:
            raise RuntimeError("SECRET_KEY must be set in production.")


CONFIGS = {"development": DevelopmentConfig, "testing": TestingConfig, "production": ProductionConfig}


def get_config(name: str | None = None):
    name = name or os.environ.get("APP_ENV", "development")
    cfg = CONFIGS.get(name)
    if cfg is None:
        raise RuntimeError(f"Unknown APP_ENV '{name}'")
    if hasattr(cfg, "validate"):
        cfg.validate()
    return cfg
