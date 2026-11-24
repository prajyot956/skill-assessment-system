import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, send_from_directory
from sqlalchemy import event
from sqlalchemy.engine import Engine
from werkzeug.exceptions import HTTPException

from .config import PROJECT_DIR, get_config
from .extensions import cors, csrf, db, limiter, login_manager, migrate
from .utils.responses import ApiError, fail


@event.listens_for(Engine, "connect")
def _sqlite_fk_pragma(dbapi_conn, _):
    """SQLite ignores foreign keys unless asked; this makes ON DELETE rules real."""
    if dbapi_conn.__class__.__module__.startswith("sqlite3"):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


def create_app(config_name: str | None = None, overrides: dict | None = None) -> Flask:
    load_dotenv(PROJECT_DIR / ".env")
    frontend_dist = PROJECT_DIR / "frontend" / "dist"
    app = Flask(__name__, instance_relative_config=False,
                static_folder=str(frontend_dist / "assets"), static_url_path="/assets")
    app.config.from_object(get_config(config_name))
    if overrides:
        app.config.update(overrides)
    logging.basicConfig(level=logging.INFO)

    Path(app.config["UPLOAD_DIR"]).mkdir(parents=True, exist_ok=True)
    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:///") and not app.testing:
        Path(app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "", 1)).parent.mkdir(
            parents=True, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    if app.config["CORS_ORIGINS"]:
        cors.init_app(app, origins=app.config["CORS_ORIGINS"], supports_credentials=True,
                      allow_headers=["Content-Type", "X-CSRFToken"])

    from . import models  # noqa: F401  (register tables)

    @login_manager.user_loader
    def load_user(user_id):
        u = db.session.get(models.User, int(user_id))
        return u if u and u.is_active_account else None  # deactivated accounts lose existing sessions too

    @login_manager.unauthorized_handler
    def unauthorized():
        return fail("unauthorized", "Please sign in to continue.", 401)

    from .routes import admin, assessments, auth, careers, dashboard, interviews, learning, profile, resume, skills
    for module in (auth, profile, dashboard, resume, skills, assessments, careers, learning, interviews, admin):
        app.register_blueprint(module.bp)

    @app.get("/api/health")
    def health():
        return jsonify({"success": True, "data": {"status": "ok"}})

    if (frontend_dist / "index.html").is_file():
        @app.get("/")
        @app.get("/<path:path>")
        def frontend(path=""):
            if path == "api" or path.startswith(("api/", "assets/")):
                abort(404)
            if Path(path).suffix:
                return send_from_directory(frontend_dist, path)
            return send_from_directory(frontend_dist, "index.html")

    _register_errors(app)
    _security_headers(app)
    from .cli import register_cli
    register_cli(app)
    return app


def _register_errors(app: Flask):
    from flask_wtf.csrf import CSRFError

    @app.errorhandler(ApiError)
    def _api(e):
        return fail(e.code, e.message, e.status, e.details)

    @app.errorhandler(CSRFError)
    def _csrf(e):
        return fail("csrf_failed", "Security token missing or invalid. Refresh the page and try again.", 400)

    @app.errorhandler(413)
    def _too_large(e):
        mb = app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
        return fail("file_too_large", f"File is too large. Maximum size is {mb} MB.", 413)

    @app.errorhandler(HTTPException)
    def _http(e):
        codes = {400: "bad_request", 401: "unauthorized", 403: "forbidden", 404: "not_found",
                 405: "method_not_allowed", 429: "rate_limited"}
        msg = {429: "Too many requests. Please wait a moment and try again."}.get(e.code, e.description)
        return fail(codes.get(e.code, "http_error"), msg, e.code or 500)

    @app.errorhandler(Exception)
    def _unhandled(e):
        app.logger.exception("Unhandled error")
        db.session.rollback()
        return fail("server_error", "Something went wrong on our side. Please try again.", 500)


def _security_headers(app: Flask):
    @app.after_request
    def add(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        if request_is_api():
            resp.headers.setdefault("Cache-Control", "no-store")
        return resp


def request_is_api() -> bool:
    from flask import request
    return request.path.startswith("/api/")
