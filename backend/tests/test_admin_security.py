import re

import pytest

from app.extensions import db
from app.models import (Assessment, AssessmentCategory, CareerRole, InterviewQuestion, LearningResource, LearningRoadmap,
                        PracticeProject, Question, RoadmapItem, Skill, User)
from tests.conftest import PASSWORD, register
from tests.test_assessments import aid, start
from tests.test_careers_learning import put_skill, role_id


@pytest.fixture()
def admin(seeded, app):
    c = app.test_client()
    register(c, "admin@example.com", "Admin")
    User.query.filter_by(email="admin@example.com").one().is_admin = True
    db.session.commit()
    return c


def mcq(skill_id, **over):
    d = {"skill_id": skill_id, "topic": "T", "difficulty": "beginner", "type": "single", "text": "Pick the right one",
         "options": [{"text": "a", "is_correct": True}, {"text": "b"}], "explanation": "because"}
    d.update(over)
    return d


class TestAdminAccess:
    def _admin_rules(self, app):
        out = []
        for rule in app.url_map.iter_rules():
            if rule.rule.startswith("/api/admin"):
                path = re.sub(r"<int:\w+>", "1", rule.rule)
                for m in rule.methods - {"HEAD", "OPTIONS"}:
                    out.append((m, path))
        return out

    def test_every_admin_route_rejects_anonymous_and_normal_users(self, seeded, make_client):
        user, anon = make_client(), seeded.test_client()
        rules = self._admin_rules(seeded)
        assert len(rules) >= 20
        for method, path in rules:
            assert getattr(anon, method.lower())(path, json={}).status_code == 401, (method, path)
            assert getattr(user, method.lower())(path, json={}).status_code == 403, (method, path)

    def test_every_non_public_api_route_requires_login(self, seeded):
        public = {"/api/health", "/api/auth/csrf", "/api/auth/register", "/api/auth/login", "/api/auth/logout", "/api/auth/forgot-password",
                  "/api/auth/reset-password", "/api/auth/me"}
        anon = seeded.test_client()
        checked = 0
        for rule in seeded.url_map.iter_rules():
            if not rule.rule.startswith("/api/") or rule.rule in public:
                continue
            path = re.sub(r"<int:\w+>", "1", re.sub(r"<\w+>", "education", rule.rule))
            for m in rule.methods - {"HEAD", "OPTIONS"}:
                r = getattr(anon, m.lower())(path, json={})
                assert r.status_code == 401, (m, rule.rule, r.status_code)
                checked += 1
        assert checked > 50

    def test_deactivated_user_loses_existing_session(self, seeded, make_client, admin):
        victim = make_client("victim@example.com")
        assert victim.get("/api/profile").status_code == 200
        uid = User.query.filter_by(email="victim@example.com").one().id
        assert admin.patch(f"/api/admin/users/{uid}", json={"is_active": False}).status_code == 200
        assert victim.get("/api/profile").status_code == 401
        assert seeded.test_client().post("/api/auth/login", json={"email": "victim@example.com", "password": PASSWORD}).status_code == 401
        admin.patch(f"/api/admin/users/{uid}", json={"is_active": True})
        assert seeded.test_client().post("/api/auth/login", json={"email": "victim@example.com", "password": PASSWORD}).status_code == 200

    def test_admin_cannot_lock_themselves_out_and_listing_hides_secrets(self, admin):
        me = User.query.filter_by(email="admin@example.com").one().id
        assert admin.patch(f"/api/admin/users/{me}", json={"is_active": False}).status_code == 400
        assert admin.patch(f"/api/admin/users/{me}", json={"is_admin": False}).status_code == 400
        text = admin.get("/api/admin/users").get_data(as_text=True)
        assert "password" not in text and "scrypt" not in text
        assert admin.get("/api/admin/users?q=admin").json["meta"]["total"] == 1

    def test_stats(self, admin):
        s = admin.get("/api/admin/stats").json["data"]
        total_q = Question.query.count()
        assert s["users"] == 1 and s["admins"] == 1 and s["questions"] == total_q and s["roles"] == 11


class TestAdminQuestions:
    def test_create_each_type_and_use_it(self, admin, seeded):
        cat = AssessmentCategory.query.first()
        skill = Skill(name="Rust", slug="rust", category="Programming", aliases=[])
        db.session.add(skill); db.session.commit()
        assert admin.post("/api/admin/assessments", json={"category_id": cat.id, "skill_id": skill.id, "title": "Rust"}).status_code == 201
        sid = skill.id
        made = [
            admin.post("/api/admin/questions", json=mcq(sid)),
            admin.post("/api/admin/questions", json=mcq(sid, type="multiple", text="Pick all", options=[{"text": "a", "is_correct": True}, {"text": "b", "is_correct": True}, {"text": "c"}])),
            admin.post("/api/admin/questions", json={"skill_id": sid, "topic": "T", "difficulty": "advanced", "type": "true_false", "text": "Statement", "correct": False}),
            admin.post("/api/admin/questions", json={"skill_id": sid, "topic": "T", "difficulty": "intermediate", "type": "short", "text": "Name it", "accepted_answers": ["cargo"]}),
        ]
        assert [m.status_code for m in made] == [201] * 4
        assert made[0].json["data"]["marks"] == 1.0 and made[2].json["data"]["marks"] == 3.0   # default marks come from difficulty
        assert [o["is_correct"] for o in made[2].json["data"]["options"]] == [False, True]
        user = seeded.test_client(); register(user, "u@example.com")
        cat_resp = user.get("/api/assessments/catalog").get_data(as_text=True)
        assert '"skill":"Rust"' in cat_resp.replace(" ", "")
        assert start(user, "Rust", "beginner", 4).status_code == 201

    @pytest.mark.parametrize("override,field", [
        ({"type": "single", "options": [{"text": "a"}, {"text": "b"}]}, "options"),                                  # no correct option
        ({"type": "single", "options": [{"text": "a", "is_correct": True}, {"text": "b", "is_correct": True}]}, "options"),  # two correct
        ({"type": "multiple", "options": [{"text": "a"}, {"text": "b"}]}, "options"),
        ({"type": "single", "options": [{"text": "only", "is_correct": True}]}, "options"),
        ({"type": "short"}, "accepted_answers"), ({"type": "true_false"}, "correct"),
        ({"difficulty": "expert"}, "difficulty"), ({"type": "essay"}, "type"), ({"text": " "}, "text"),
        ({"marks": 0}, "marks"), ({"marks": 99}, "marks"), ({"skill_id": 99999}, "skill_id"), ({"topic": ""}, "topic"),
    ])
    def test_validation(self, admin, override, field):
        initial_q = Question.query.count()
        sid = Skill.query.filter_by(name="Python").one().id
        r = admin.post("/api/admin/questions", json={**mcq(sid), **override})
        assert r.status_code == 422 and field in r.json["error"]["details"]["fields"], r.json
        assert Question.query.count() == initial_q

    def test_edit_filter_and_retire_keeps_history(self, admin, seeded):
        sid = Skill.query.filter_by(name="SQL").one().id
        listed = admin.get(f"/api/admin/questions?skill_id={sid}&difficulty=advanced").json
        assert listed["meta"]["total"] == 4 and all(q["difficulty"] == "advanced" for q in listed["data"])
        qid = listed["data"][0]["id"]
        edited = admin.put(f"/api/admin/questions/{qid}", json=mcq(sid, difficulty="advanced", text="Edited question"))
        assert edited.status_code == 200 and edited.json["data"]["text"] == "Edited question"
        assert admin.get("/api/admin/questions?q=Edited").json["meta"]["total"] == 1
        assert admin.delete(f"/api/admin/questions/{qid}").status_code == 200
        assert db.session.get(Question, qid).is_active is False          # retired, not removed
        assert admin.get("/api/admin/questions?active=0").json["meta"]["total"] == 1

    def test_admin_views_include_answers_but_user_views_never_do(self, admin, seeded, make_client):
        assert "is_correct" in admin.get("/api/admin/questions").get_data(as_text=True)
        assert "is_correct" not in make_client("z@example.com").get("/api/assessments/catalog").get_data(as_text=True)


class TestAdminRolesAndResources:
    def test_changing_role_requirements_changes_matching(self, admin, seeded):
        put_skill(2 if False else User.query.filter_by(email="admin@example.com").one().id, "Python", 100)
        rid = role_id("software-developer")
        before = admin.get("/api/careers/recommendations").json["data"]["recommendations"]
        py = Skill.query.filter_by(name="Python").one().id
        r = admin.put(f"/api/admin/roles/{rid}/skills", json={"skills": [{"skill_id": py, "weight": 1, "min_level_pct": 60}]})
        assert r.status_code == 200 and len(r.json["data"]["skills"]) == 1
        after = next(x for x in admin.get("/api/careers/recommendations").json["data"]["recommendations"] if x["role_id"] == rid)
        assert after["base_pct"] == 100.0 and next(x for x in before if x["role_id"] == rid)["base_pct"] < 100

    @pytest.mark.parametrize("skills", [[], [{"skill_id": 99999}], [{"skill_id": 1}, {"skill_id": 1}], [{"skill_id": 1, "weight": 0}],
                                         [{"skill_id": 1, "min_level_pct": 150}], "nope"])
    def test_role_skill_validation(self, admin, skills):
        assert admin.put(f"/api/admin/roles/{role_id('data-analyst')}/skills", json={"skills": skills}).status_code == 422
        assert len(CareerRole.query.filter_by(slug="data-analyst").one().skills) == 8       # untouched on failure

    def test_add_role_skill_and_resource_crud(self, admin, seeded):
        r = admin.post("/api/admin/roles", json={"name": "Game Developer", "interest_tags": ["Games"], "education_keywords": ["computer"]})
        assert r.status_code == 201 and r.json["data"]["interest_tags"] == ["games"]
        assert admin.post("/api/admin/roles", json={"name": "game developer"}).status_code == 422
        assert admin.post("/api/admin/skills", json={"name": "Unity", "category": "Programming", "aliases": ["unity3d"]}).status_code == 201
        assert admin.post("/api/admin/skills", json={"name": "unity", "category": "Programming"}).status_code == 422
        sid = Skill.query.filter_by(name="Python").one().id
        res = admin.post("/api/admin/resources", json={"skill_id": sid, "title": "New", "url": "https://example.com/x", "kind": "docs", "level": "beginner"})
        assert res.status_code == 201
        assert admin.post("/api/admin/resources", json={"skill_id": sid, "title": "Bad", "url": "ftp://x"}).status_code == 422
        rid = res.json["data"]["id"]
        assert admin.put(f"/api/admin/resources/{rid}", json={"skill_id": sid, "title": "Renamed", "url": "https://example.com/y"}).json["data"]["title"] == "Renamed"
        assert admin.delete(f"/api/admin/resources/{rid}").status_code == 200 and db.session.get(LearningResource, rid) is None

    def test_project_and_interview_banks_are_admin_managed(self, admin, seeded, make_client):
        skill = Skill.query.filter_by(name="Python").one()
        project = admin.post("/api/admin/projects", json={
            "title": "Python practice", "description": "Build a small tool.", "difficulty": "beginner",
            "skill_slugs": [skill.slug], "objectives": ["Use functions"], "steps": ["Plan", "Build"],
            "expected_outcome": "A working tool.",
        })
        assert project.status_code == 201 and project.json["data"]["skills"] == ["Python"]
        project_id = project.json["data"]["id"]
        user = make_client()
        assert any(row["id"] == project_id for row in user.get("/api/practice/projects").json["data"])
        assert admin.put(f"/api/admin/projects/{project_id}", json={"is_active": False}).status_code == 200
        assert all(row["id"] != project_id for row in user.get("/api/practice/projects").json["data"])
        assert admin.post("/api/admin/projects", json={
            "title": "Invalid project", "description": "Bad skill.", "difficulty": "beginner",
            "skill_slugs": ["unknown"], "objectives": ["Learn"], "steps": ["Start"],
        }).status_code == 422

        InterviewQuestion.query.filter_by(skill_id=skill.id).update({"is_active": False})
        db.session.commit()
        created = []
        for text in ("How do Python generators save memory?", "When would you use a context manager?"):
            response = admin.post("/api/admin/interview-questions", json={
                "skill_id": skill.id, "difficulty": "beginner", "text": text, "keywords": ["yield", "iterator"],
            })
            assert response.status_code == 201
            created.append(response.json["data"])
        assert admin.get("/api/admin/catalog").json["data"]["skills"][0].get("slug") is not None
        put_skill(User.query.filter_by(email="ana@example.com").one().id, "Python")
        started = user.post("/api/interviews", json={"difficulty": "beginner", "num_questions": 3})
        assert started.status_code == 201
        asked = {row["text"] for row in started.json["data"]["questions"]}
        assert {row["text"] for row in created} <= asked

        iid = started.json["data"]["id"]
        admin.put(f"/api/admin/interview-questions/{created[0]['id']}", json={"text": "Updated generator question"})
        saved = user.get(f"/api/interviews/{iid}").json["data"]["questions"]
        assert created[0]["text"] in {row["text"] for row in saved}  # existing attempts retain their question snapshot
        assert admin.put(f"/api/admin/interview-questions/{created[0]['id']}", json={"is_active": False}).status_code == 200

        seed_project = PracticeProject.query.filter(PracticeProject.seed_key.isnot(None)).first()
        seed_question = InterviewQuestion.query.filter(InterviewQuestion.seed_key.isnot(None)).first()
        original_project_title, original_question_text = seed_project.title, seed_question.text
        seed_project.title = "Admin-edited seeded project"
        seed_question.text = "Admin-edited seeded interview question"
        db.session.commit()
        project_count, question_count = PracticeProject.query.count(), InterviewQuestion.query.count()
        from app.services.seed_service import seed_all
        seed_all()
        assert PracticeProject.query.count() == project_count and InterviewQuestion.query.count() == question_count
        assert PracticeProject.query.filter_by(title=original_project_title).count() == 0
        assert InterviewQuestion.query.filter_by(text=original_question_text).count() == 0

    def test_deleting_a_resource_keeps_roadmap_items(self, admin, seeded):
        uid = User.query.filter_by(email="admin@example.com").one().id
        put_skill(uid, "HTML", 20)
        admin.post("/api/roadmap/generate", json={"role_id": role_id("frontend-developer")})
        item = RoadmapItem.query.filter(RoadmapItem.resource_id.isnot(None)).first()
        rid, count = item.resource_id, RoadmapItem.query.count()
        admin.delete(f"/api/admin/resources/{rid}")
        assert RoadmapItem.query.count() == count and db.session.get(RoadmapItem, item.id).resource_id is None

    def test_catalog_and_category_management(self, admin):
        assert admin.post("/api/admin/categories", json={"name": "Security"}).status_code == 201
        assert admin.post("/api/admin/categories", json={"name": "security"}).status_code == 422
        cid = admin.get("/api/admin/catalog").json["data"]["categories"][-1]["id"]
        assert admin.put(f"/api/admin/categories/{cid}", json={"is_active": False}).status_code == 200
        names = [c["name"] for c in admin.get("/api/admin/catalog").json["data"]["categories"]]
        assert "Security" in names


class TestGeneralSecurity:
    def test_injection_strings_are_inert(self, seeded, make_client):
        r = seeded.test_client().post("/api/auth/login", json={"email": "' OR 1=1 --", "password": "' OR '1'='1"})
        assert r.status_code == 401 and User.query.count() == 0
        c = make_client()
        c.put("/api/profile", json={"location": "x'; DROP TABLE users; --", "summary": "<script>alert(1)</script>"})
        assert User.query.count() == 1
        got = c.get("/api/profile")
        assert got.mimetype == "application/json" and got.json["data"]["summary"] == "<script>alert(1)</script>"   # stored as data, returned as JSON

    def test_uploaded_files_are_not_publicly_served(self, seeded, make_client):
        from tests.helpers import make_pdf, upload
        c = make_client()
        upload(c, make_pdf(), "r.pdf")
        name = __import__("app.models", fromlist=["Resume"]).Resume.query.one().stored_filename
        anon = seeded.test_client()
        for path in (f"/uploads/{name}", f"/uploads/1/{name}", f"/static/{name}", f"/api/resumes/1/file", f"/backend/uploads/1/{name}"):
            assert anon.get(path).status_code in (404, 405), path
            assert c.get(path).status_code in (404, 405), path

    def test_security_headers_and_json_errors(self, seeded, client):
        r = client.get("/api/health")
        assert r.headers["X-Content-Type-Options"] == "nosniff" and r.headers["X-Frame-Options"] == "DENY"
        assert client.delete("/api/auth/me").json["error"]["code"] == "method_not_allowed"

    def test_unhandled_errors_do_not_leak_internals(self, seeded, make_client, monkeypatch):
        c = make_client()
        monkeypatch.setattr("app.routes.dashboard.dashboard_service.build", lambda u: 1 / 0)
        seeded.config["PROPAGATE_EXCEPTIONS"] = False
        r = c.get("/api/dashboard")
        assert r.status_code == 500 and r.json["error"]["code"] == "server_error"
        assert "ZeroDivision" not in r.get_data(as_text=True) and "Traceback" not in r.get_data(as_text=True)

    def test_production_config_refuses_missing_secret(self, monkeypatch):
        from app.config import ProductionConfig, get_config
        monkeypatch.setattr(ProductionConfig, "SECRET_KEY", None)
        with pytest.raises(RuntimeError):
            get_config("production")
        assert ProductionConfig.SESSION_COOKIE_SECURE is True

    def test_no_secrets_in_source(self):
        import pathlib
        bad = re.compile(r"sk-ant-[A-Za-z0-9]|AKIA[0-9A-Z]{12}")
        for p in pathlib.Path(__file__).resolve().parents[1].joinpath("app").rglob("*.py"):
            assert not bad.search(p.read_text()), p
