import pytest

from app.extensions import db
from app.models import PasswordResetToken, User
from app.utils.decorators import admin_required
from tests.conftest import PASSWORD, register


class TestRegistration:
    def test_register_success_logs_in_and_hashes_password(self, client):
        r = register(client)
        assert r.status_code == 201
        assert r.json["data"]["email"] == "ana@example.com"
        assert "password" not in str(r.json)
        user = User.query.one()
        assert user.password_hash != PASSWORD and user.password_hash.startswith("scrypt:")
        assert user.profile is not None
        assert client.get("/api/auth/me").status_code == 200

    def test_email_is_case_insensitive_and_unique(self, client):
        register(client, email="Ana@Example.com")
        r = register(client, email="ana@example.COM", name="Other")
        assert r.status_code == 422
        assert "email" in r.json["error"]["details"]["fields"]

    @pytest.mark.parametrize("pw,fragment", [
        ("short1A", "8 characters"), ("alllowercase1", "uppercase"),
        ("ALLUPPERCASE1", "lowercase"), ("NoNumbersHere", "number")])
    def test_weak_passwords_rejected(self, client, pw, fragment):
        r = register(client, password=pw)
        assert r.status_code == 422
        assert fragment in r.json["error"]["details"]["fields"]["password"]

    def test_password_mismatch(self, client):
        r = client.post("/api/auth/register", json={
            "full_name": "A", "email": "a@b.com", "password": PASSWORD, "confirm_password": "Different1"})
        assert r.status_code == 422
        assert "confirm_password" in r.json["error"]["details"]["fields"]

    def test_invalid_email_and_missing_name(self, client):
        r = client.post("/api/auth/register", json={
            "full_name": " ", "email": "not-an-email", "password": PASSWORD, "confirm_password": PASSWORD})
        fields = r.json["error"]["details"]["fields"]
        assert r.status_code == 422 and "email" in fields and "full_name" in fields

    def test_non_json_body_rejected(self, client):
        r = client.post("/api/auth/register", data="x=1")
        assert r.status_code == 400 and r.json["error"]["code"] == "invalid_json"


class TestLoginLogout:
    def test_login_logout_cycle(self, app):
        register(app.test_client())
        c = app.test_client()
        r = c.post("/api/auth/login", json={"email": "ANA@example.com", "password": PASSWORD})
        assert r.status_code == 200
        assert c.get("/api/auth/me").status_code == 200
        assert c.post("/api/auth/logout").status_code == 200
        assert c.get("/api/auth/me").status_code == 401

    def test_invalid_credentials_give_same_message(self, app):
        register(app.test_client())
        c = app.test_client()
        wrong_pw = c.post("/api/auth/login", json={"email": "ana@example.com", "password": "Wrong123x"})
        no_user = c.post("/api/auth/login", json={"email": "nobody@example.com", "password": "Wrong123x"})
        assert wrong_pw.status_code == no_user.status_code == 401
        assert wrong_pw.json["error"] == no_user.json["error"]

    def test_deactivated_account_cannot_login(self, app):
        register(app.test_client())
        User.query.one().is_active_account = False
        db.session.commit()
        r = app.test_client().post("/api/auth/login", json={"email": "ana@example.com", "password": PASSWORD})
        assert r.status_code == 401

    def test_remember_me_sets_cookie_only_when_requested(self, app):
        register(app.test_client())
        c = app.test_client()
        r = c.post("/api/auth/login", json={"email": "ana@example.com", "password": PASSWORD})
        assert "remember_token" not in r.headers.get("Set-Cookie", "")
        c2 = app.test_client()
        r2 = c2.post("/api/auth/login", json={"email": "ana@example.com", "password": PASSWORD, "remember": True})
        assert any("remember_token" in h for h in r2.headers.getlist("Set-Cookie"))

    def test_session_cookie_flags(self, client):
        r = register(client)
        cookie = [h for h in r.headers.getlist("Set-Cookie") if h.startswith("session=")][0]
        assert "HttpOnly" in cookie and "SameSite=Lax" in cookie


class TestAccessControl:
    @pytest.mark.parametrize("method,path", [
        ("get", "/api/profile"), ("put", "/api/profile"), ("get", "/api/dashboard"),
        ("get", "/api/notifications"), ("post", "/api/notifications/read-all"),
        ("post", "/api/auth/change-password")])
    def test_protected_routes_require_login(self, client, method, path):
        r = getattr(client, method)(path, json={})
        assert r.status_code == 401
        assert r.json["success"] is False and r.json["error"]["code"] == "unauthorized"

    def test_admin_required_blocks_normal_users(self, app):
        @app.get("/api/_admin_probe")
        @admin_required
        def probe():
            return {"ok": True}

        anon = app.test_client()
        assert anon.get("/api/_admin_probe").status_code == 401
        user = app.test_client(); register(user)
        assert user.get("/api/_admin_probe").status_code == 403
        User.query.one().is_admin = True
        db.session.commit()
        assert user.get("/api/_admin_probe").status_code == 200

    def test_unknown_route_returns_json_404(self, client):
        r = client.get("/api/does-not-exist")
        assert r.status_code == 404 and r.json["error"]["code"] == "not_found"

    def test_api_responses_are_not_cached(self, client):
        assert client.get("/api/health").headers["Cache-Control"] == "no-store"


class TestCsrf:
    def test_post_without_token_rejected_and_with_token_accepted(self, csrf_app):
        c = csrf_app.test_client()
        body = {"full_name": "A B", "email": "a@b.com", "password": PASSWORD, "confirm_password": PASSWORD}
        r = c.post("/api/auth/register", json=body)
        assert r.status_code == 400 and r.json["error"]["code"] == "csrf_failed"
        token = c.get("/api/auth/csrf").json["data"]["csrf_token"]
        r = c.post("/api/auth/register", json=body, headers={"X-CSRFToken": token})
        assert r.status_code == 201

    def test_token_from_another_session_rejected(self, csrf_app):
        a, b = csrf_app.test_client(), csrf_app.test_client()
        token_a = a.get("/api/auth/csrf").json["data"]["csrf_token"]
        b.get("/api/auth/csrf")
        r = b.post("/api/auth/logout", headers={"X-CSRFToken": token_a})
        assert r.status_code == 400


class TestPasswordFlows:
    def test_change_password(self, make_client, app):
        c = make_client()
        bad = c.post("/api/auth/change-password", json={
            "current_password": "nope", "new_password": "NewPass123", "confirm_password": "NewPass123"})
        assert bad.status_code == 422
        good = c.post("/api/auth/change-password", json={
            "current_password": PASSWORD, "new_password": "NewPass123", "confirm_password": "NewPass123"})
        assert good.status_code == 200
        fresh = app.test_client()
        assert fresh.post("/api/auth/login", json={"email": "ana@example.com", "password": PASSWORD}).status_code == 401
        assert fresh.post("/api/auth/login", json={"email": "ana@example.com", "password": "NewPass123"}).status_code == 200

    def test_forgot_and_reset_flow(self, app, monkeypatch):
        sent = []
        monkeypatch.setattr("app.routes.auth.send_email", lambda to, subj, body: sent.append((to, body)))
        register(app.test_client())
        c = app.test_client()
        # unknown email gets the identical response and no email
        r_unknown = c.post("/api/auth/forgot-password", json={"email": "ghost@example.com"})
        r_known = c.post("/api/auth/forgot-password", json={"email": "ana@example.com"})
        assert r_unknown.json == r_known.json and len(sent) == 1
        token = sent[0][1].split("token=")[1].split()[0]
        assert PasswordResetToken.query.one().token_hash != token  # only the hash is stored
        r = c.post("/api/auth/reset-password", json={
            "token": token, "password": "Reset12345", "confirm_password": "Reset12345"})
        assert r.status_code == 200
        assert c.post("/api/auth/login", json={"email": "ana@example.com", "password": "Reset12345"}).status_code == 200
        reuse = c.post("/api/auth/reset-password", json={
            "token": token, "password": "Another1234", "confirm_password": "Another1234"})
        assert reuse.status_code == 400 and reuse.json["error"]["code"] == "invalid_token"

    def test_expired_token_rejected(self, app, monkeypatch):
        sent = []
        monkeypatch.setattr("app.routes.auth.send_email", lambda to, subj, body: sent.append(body))
        c = app.test_client(); register(c)
        c.post("/api/auth/forgot-password", json={"email": "ana@example.com"})
        t = PasswordResetToken.query.one()
        from datetime import timedelta
        t.expires_at = t.expires_at - timedelta(hours=2)
        db.session.commit()
        token = sent[0].split("token=")[1].split()[0]
        r = c.post("/api/auth/reset-password", json={
            "token": token, "password": "Reset12345", "confirm_password": "Reset12345"})
        assert r.status_code == 400
