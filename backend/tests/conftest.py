import pytest
from flask import g

from app import create_app
from app.extensions import db as _db

PASSWORD = "Str0ngPass1"


def _isolate_requests(app):
    """The fixtures keep one app context open so tests can query the DB directly. Flask-Login
    caches the current user on flask.g, which that shared context would carry across requests
    and across clients. Real requests each get a fresh context, so clear the cache per request.
    (test_isolation_without_shared_context proves the real behaviour with no shared context.)"""
    @app.before_request
    def _clear_login_cache():
        g.pop("_login_user", None)


@pytest.fixture()
def app():
    app = create_app("testing")
    _isolate_requests(app)
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def csrf_app():
    """App with CSRF enforcement switched on, as in production."""
    app = create_app("testing", overrides={"WTF_CSRF_ENABLED": True})
    _isolate_requests(app)
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


def register(client, email="ana@example.com", name="Ana Rao", password=PASSWORD):
    return client.post("/api/auth/register", json={
        "full_name": name, "email": email, "password": password, "confirm_password": password})


@pytest.fixture()
def make_client(app):
    """Returns a factory for independent logged-in clients (separate cookie jars)."""
    def _make(email="ana@example.com", name="Ana Rao"):
        c = app.test_client()
        assert register(c, email, name).status_code == 201
        return c
    return _make


@pytest.fixture()
def seeded(app):
    from app.services.seed_service import seed_all
    seed_all()
    return app
