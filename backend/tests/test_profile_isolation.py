from app.extensions import db
from app.models import Education, Notification, User, UserInterest, UserProfile


class TestProfile:
    def test_update_and_read_back(self, make_client):
        c = make_client()
        r = c.put("/api/profile", json={
            "phone": "+91 98765 43210", "location": "Pune", "summary": "CS student.",
            "github_url": "https://github.com/ana", "interests": ["AI", "Web", "AI"],
            "preferences": {"work_types": ["internship", "full_time"]}})
        assert r.status_code == 200
        d = r.json["data"]
        assert d["location"] == "Pune" and d["interests"] == ["AI", "Web"]
        assert d["preferences"]["work_types"] == ["full_time", "internship"]
        assert d["completion"]["percent"] == 50  # phone, location, summary, links, interests
        # untouched fields remain when omitted
        r2 = c.put("/api/profile", json={"location": "Mumbai"})
        assert r2.json["data"]["summary"] == "CS student."

    def test_validation_errors(self, make_client):
        c = make_client()
        r = c.put("/api/profile", json={"phone": "abc", "github_url": "javascript:alert(1)",
                                         "target_role_id": 999, "preferences": {"work_types": ["x"]}})
        assert r.status_code == 422
        assert {"phone", "github_url", "target_role_id", "preferences"} <= set(r.json["error"]["details"]["fields"])

    def test_empty_values_clear_fields(self, make_client):
        c = make_client()
        c.put("/api/profile", json={"location": "Pune"})
        r = c.put("/api/profile", json={"location": "  "})
        assert r.json["data"]["location"] is None


class TestCrossUserIsolation:
    def test_profiles_are_separate(self, make_client):
        a = make_client("a@example.com", "A User")
        b = make_client("b@example.com", "B User")
        a.put("/api/profile", json={"summary": "Only A"})
        assert b.get("/api/profile").json["data"]["summary"] is None
        assert a.get("/api/profile").json["data"]["summary"] == "Only A"

    def test_profile_has_no_user_id_parameter_to_abuse(self, make_client):
        a = make_client("a@example.com"); b = make_client("b@example.com")
        # attempts to smuggle another user's id are ignored; only the session owner is edited
        a.put("/api/profile", json={"user_id": 2, "id": 2, "summary": "mine"})
        assert UserProfile.query.filter_by(user_id=2).one().summary is None

    def test_cannot_read_or_mark_other_users_notifications(self, make_client):
        a = make_client("a@example.com"); b = make_client("b@example.com")
        n = Notification(user_id=1, title="Private")
        db.session.add(n); db.session.commit()
        assert b.get("/api/notifications").json["data"] == []
        assert b.post(f"/api/notifications/{n.id}/read").status_code == 404
        assert Notification.query.get(n.id).is_read is False
        assert a.post(f"/api/notifications/{n.id}/read").status_code == 200

    def test_dashboard_is_scoped_and_empty_for_new_user(self, make_client):
        c = make_client()
        d = c.get("/api/dashboard").json["data"]
        assert d["profile"]["resume_status"] == "not_uploaded"
        assert d["assessments"] == {"completed": 0, "pending": 0, "average_score": None, "recent": []}
        assert d["skills"]["strongest"] == [] and d["learning"] is None and d["activity"] == []

    def test_notifications_pagination_meta(self, make_client):
        c = make_client()
        db.session.add_all(Notification(user_id=1, title=f"n{i}") for i in range(5))
        db.session.commit()
        r = c.get("/api/notifications?per_page=2&page=2")
        assert len(r.json["data"]) == 2
        assert r.json["meta"]["total"] == 5 and r.json["meta"]["unread"] == 5


class TestDeletionSafety:
    def test_deleting_user_removes_only_their_rows(self, make_client):
        make_client("a@example.com"); make_client("b@example.com")
        db.session.add_all([Education(user_id=1, institution="X"), Education(user_id=2, institution="Y"),
                            UserInterest(user_id=1, interest="AI"), UserInterest(user_id=2, interest="AI")])
        db.session.commit()
        db.session.delete(db.session.get(User, 1)); db.session.commit()
        assert [e.institution for e in Education.query.all()] == ["Y"]
        assert UserInterest.query.count() == 1 and UserProfile.query.count() == 1


def test_isolation_without_shared_context():
    """Production-like: no app context is held open between requests."""
    from app import create_app
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    pw = "Str0ngPass1"
    reg = lambda c, e: c.post("/api/auth/register", json={
        "full_name": "U", "email": e, "password": pw, "confirm_password": pw})
    a, b = app.test_client(), app.test_client()
    reg(a, "a@x.com"); reg(b, "b@x.com")
    a.put("/api/profile", json={"summary": "Only A"})
    assert a.get("/api/profile").json["data"]["summary"] == "Only A"
    assert b.get("/api/profile").json["data"]["summary"] is None
    assert b.get("/api/auth/me").json["data"]["email"] == "b@x.com"
