import pytest

from app.extensions import db
from app.models import (AssessmentAttempt, CareerRole, Education, LearningRoadmap, MockInterview, Project, RoadmapItem,
                        Skill, UserInterest, UserSkill)
from app.services import career_service
from tests.test_assessments import aid, correct_answer, start
from app.models import Question


def put_skill(uid, name, prof=None, status="user_confirmed"):
    sk = Skill.query.filter_by(name=name).one()
    us = UserSkill(user_id=uid, skill_id=sk.id, status=status, source="manual", proficiency_pct=prof)
    db.session.add(us); db.session.commit()
    return us


def role_id(slug):
    return CareerRole.query.filter_by(slug=slug).one().id


def rec(c, slug):
    return next(r for r in c.get("/api/careers/recommendations").json["data"]["recommendations"] if r["role_id"] == role_id(slug))


class TestMatchingAlgorithm:
    """frontend-developer weights: HTML 3, CSS 3, JavaScript 3, React 2, Git 1, REST APIs 1, Communication 1 (total 14)."""

    @pytest.fixture()
    def user(self, seeded, make_client):
        c = make_client()
        put_skill(1, "HTML", 70)          # at the required 70  -> 1.0
        put_skill(1, "CSS", 35)           # below required 70   -> 35/70 = 0.5
        put_skill(1, "JavaScript")        # confirmed, unassessed -> 0.4
        return c

    def test_base_score_by_hand(self, user):
        r = rec(user, "frontend-developer")
        # (3x1.0 + 3x0.5 + 3x0.4) / 14 = 5.7 / 14 = 40.714...%
        assert r["base_pct"] == 40.7 and r["match_pct"] == 40.7 and r["adjustments"] == []
        assert [s["skill"] for s in r["matching_skills"]] == ["HTML"]
        assert [s["skill"] for s in r["partial_skills"]] == ["CSS"]
        assert [s["skill"] for s in r["unverified_skills"]] == ["JavaScript"]
        assert {s["skill"] for s in r["missing_skills"]} == {"React", "Git", "REST APIs", "Communication"}
        assert any("haven't been verified" in w for w in r["why"])

    def test_adjustments_by_hand(self, user):
        db.session.add_all([UserInterest(user_id=1, interest="Web design"),
                            Education(user_id=1, institution="X", degree="B.Tech", specialization="Computer Science"),
                            Project(user_id=1, name="Site", technologies=["HTML", "CSS"], description="landing page")])
        db.session.commit()
        r = rec(user, "frontend-developer")
        adj = {a["name"]: a["points"] for a in r["adjustments"]}
        # interests: {"web design"} matches "web" -> 3 x min(1, 1/2) = 1.5 ; education "computer" -> 3 ; projects 2 of 7 skills -> 4 x 2/7 = 1.1
        assert adj == {"Projects": 1.1, "Education": 3.0, "Interests": 1.5}
        assert r["match_pct"] == round(40.7 + 1.1 + 3.0 + 1.5, 1) == 46.3

    def test_confirmed_but_unassessed_skills_cannot_exceed_partial_credit(self, seeded, make_client):
        c = make_client()
        for s in ("HTML", "CSS", "JavaScript", "React", "Git", "REST APIs", "Communication"):
            put_skill(1, s)               # everything confirmed, nothing verified
        assert rec(c, "frontend-developer")["base_pct"] == 40.0     # 0.4 credit each; resume claims never equal proficiency

    def test_interests_and_education_alone_never_create_a_match(self, seeded, make_client):
        c = make_client()
        put_skill(1, "Python")           # only a skill irrelevant to the frontend role
        db.session.add_all([UserInterest(user_id=1, interest="web"), Education(user_id=1, institution="X", degree="Computer")])
        db.session.commit()
        slugs = {r["role_id"] for r in c.get("/api/careers/recommendations").json["data"]["recommendations"]}
        assert role_id("frontend-developer") not in slugs

    def test_no_skills_means_no_fabricated_recommendations(self, seeded, make_client):
        c = make_client()
        d = c.get("/api/careers/recommendations").json["data"]
        assert d["recommendations"] == [] and "Confirm skills" in d["message"]

    def test_ranking_target_and_persistence(self, user):
        put_skill(1, "SQL", 90); put_skill(1, "Python", 80)
        r = user.get("/api/careers/recommendations").json["data"]["recommendations"]
        pcts = [x["match_pct"] for x in r]
        assert pcts == sorted(pcts, reverse=True) and len(r) >= 3
        assert user.put("/api/careers/target", json={"role_id": role_id("data-analyst")}).status_code == 200
        r2 = user.get("/api/careers/recommendations").json["data"]
        assert r2["target"]["role_id"] == role_id("data-analyst") and sum(1 for x in r2["recommendations"] if x["is_target"]) == 1
        assert user.put("/api/careers/target", json={"role_id": 9999}).status_code == 404
        dash = user.get("/api/dashboard").json["data"]["career"]
        assert dash["top_matches"] and dash["target_role_id"] == role_id("data-analyst")

    def test_gap_priorities_and_states(self, user):
        g = user.get(f"/api/careers/{role_id('frontend-developer')}/gap").json["data"]
        by = {s["skill"]: s for s in g["skills"]}
        assert by["HTML"]["state"] == "met" and by["HTML"]["priority"] == "none" and by["HTML"]["evidence_level"] == "assessment_verified"
        assert by["CSS"]["state"] == "below" and by["CSS"]["priority"] == "medium"     # deficit 3 x 0.5 = 1.5
        assert by["JavaScript"]["state"] == "unverified" and by["JavaScript"]["priority"] == "medium"  # 3 x 0.6 = 1.8
        assert by["React"]["state"] == "missing" and by["React"]["priority"] == "high"             # deficit 2 x 1 = 2.0 meets the >= 2.0 high threshold
        assert by["Communication"]["priority"] == "medium"
        assert g["skills"][0]["priority"] != "none" and g["counts"]["met"] == 1


class TestAnalysis:
    def test_evidence_levels_trends_and_topics(self, seeded, make_client):
        c = make_client()
        put_skill(1, "Git")                          # confirmed only
        a = start(c, "Python", "beginner", 5).json["data"]["attempt_id"]
        qs = Question.query.filter(Question.id.in_(AssessmentAttempt.query.get(a).question_ids)).all()
        c.put(f"/api/assessments/attempts/{a}/answers", json={"answers": {str(q.id): correct_answer(q) for q in qs}})
        c.post(f"/api/assessments/attempts/{a}/submit")
        d = c.get("/api/analysis").json["data"]
        assert d["evidence_counts"] == {"resume_detected": 0, "user_confirmed": 1, "assessment_verified": 1}
        assert d["trends"][0]["skill"] == "Python" and d["trends"][0]["points"][0]["percentage"] == 100.0
        assert [s["name"] for s in d["unassessed"]] == ["Git"] and d["topics"] and d["total_attempts"] == 1

    def test_empty_for_new_user(self, seeded, make_client):
        d = make_client().get("/api/analysis").json["data"]
        assert d["skills"] == [] and d["trends"] == [] and d["total_attempts"] == 0


class TestRoadmap:
    @pytest.fixture()
    def c(self, seeded, make_client):
        c = make_client()
        put_skill(1, "HTML", 80); put_skill(1, "CSS", 30); put_skill(1, "JavaScript")
        return c

    def test_requires_a_target(self, c):
        assert c.post("/api/roadmap/generate").status_code == 409
        assert c.get("/api/roadmap").json["data"]["roadmap"] is None

    def test_generation_covers_gaps_only(self, c):
        r = c.post("/api/roadmap/generate", json={"role_id": role_id("frontend-developer")})
        assert r.status_code == 201
        road = r.json["data"]
        skills = {i["skill"] for i in road["items"]}
        assert "HTML" not in skills                          # already meets the requirement
        assert {"CSS", "JavaScript", "React"} <= skills
        types = {i["type"] for i in road["items"]}
        assert {"learn", "exercise", "mini_project", "assess"} <= types
        assert all(i["status"] == "pending" for i in road["items"]) and road["progress_pct"] == 0 and road["completed"] == 0
        css_assess = next(i for i in road["items"] if i["skill"] == "CSS" and i["type"] == "assess")
        assert css_assess["title"].startswith("Retake") and css_assess["assessment_id"]
        assert next(i for i in road["items"] if i["type"] == "learn")["resource_url"].startswith("https://")
        react = [i for i in road["items"] if i["skill"] == "React"]
        assert any(i["type"] == "assess" for i in react)  # React now has assessment questions: offered

    def test_progress_only_changes_when_the_user_marks_items(self, c):
        road = c.post("/api/roadmap/generate", json={"role_id": role_id("frontend-developer")}).json["data"]
        first, second = road["items"][0]["id"], road["items"][1]["id"]
        r = c.patch(f"/api/roadmap/items/{first}", json={"status": "completed"}).json["data"]
        assert r["completed"] == 1 and r["progress_pct"] == round(100 / r["total"])
        item = next(i for i in r["items"] if i["id"] == first)
        assert item["completed_at"] and item["started_at"]
        r = c.patch(f"/api/roadmap/items/{second}", json={"status": "in_progress"}).json["data"]
        assert r["in_progress"] == 1 and r["pending"] == r["total"] - 2
        assert c.patch(f"/api/roadmap/items/{first}", json={"status": "pending"}).json["data"]["completed"] == 0
        assert c.patch(f"/api/roadmap/items/{first}", json={"status": "done!"}).status_code == 422

    def test_taking_an_assessment_does_not_auto_complete_items_and_marks_roadmap_stale(self, c):
        road = c.post("/api/roadmap/generate", json={"role_id": role_id("frontend-developer")}).json["data"]
        assert road["is_stale"] is False
        a = start(c, "CSS", "beginner", 5).json["data"]["attempt_id"]
        qs = Question.query.filter(Question.id.in_(AssessmentAttempt.query.get(a).question_ids)).all()
        c.put(f"/api/assessments/attempts/{a}/answers", json={"answers": {str(q.id): correct_answer(q) for q in qs}})
        c.post(f"/api/assessments/attempts/{a}/submit")
        now = c.get("/api/roadmap").json["data"]["roadmap"]
        assert now["completed"] == 0 and now["is_stale"] is True      # progress untouched; user is offered an update

    def test_regeneration_keeps_user_progress(self, c):
        rid = role_id("frontend-developer")
        road = c.post("/api/roadmap/generate", json={"role_id": rid}).json["data"]
        done = road["items"][0]
        c.patch(f"/api/roadmap/items/{done['id']}", json={"status": "completed"})
        new = c.post("/api/roadmap/generate", json={"role_id": rid}).json["data"]
        assert new["id"] != road["id"] and LearningRoadmap.query.filter_by(status="active").count() == 1
        kept = next(i for i in new["items"] if i["title"] == done["title"])
        assert kept["status"] == "completed" and new["completed"] == 1 and new["is_stale"] is False

    def test_fully_qualified_user_gets_an_empty_honest_roadmap(self, seeded, make_client):
        c = make_client()
        for rs in CareerRole.query.filter_by(slug="database-developer").one().skills:
            put_skill(1, rs.skill.name, 100)
        road = c.post("/api/roadmap/generate", json={"role_id": role_id("database-developer")}).json["data"]
        assert road["items"] == [] and road["progress_pct"] == 0

    def test_other_users_cannot_touch_my_items(self, c, make_client):
        road = c.post("/api/roadmap/generate", json={"role_id": role_id("frontend-developer")}).json["data"]
        other = make_client("b@example.com")
        assert other.patch(f"/api/roadmap/items/{road['items'][0]['id']}", json={"status": "completed"}).status_code == 404
        assert other.get("/api/roadmap").json["data"]["roadmap"] is None
        assert RoadmapItem.query.filter_by(status="completed").count() == 0

    def test_ai_resource_suggestions_unavailable_without_key(self, c):
        r = c.post("/api/roadmap/suggest-resources", json={"skill": "CSS"})
        assert r.status_code == 503 and r.json["error"]["code"] == "ai_unavailable"


class TestPractice:
    def test_projects_ranked_by_target_gaps(self, seeded, make_client):
        c = make_client()
        put_skill(1, "HTML", 90); put_skill(1, "Python")
        c.put("/api/careers/target", json={"role_id": role_id("frontend-developer")})
        p = c.get("/api/practice/projects").json["data"]
        assert p[0]["relevance"] >= p[-1]["relevance"]
        top = next(x for x in p if x["title"] == "To-Do App with React")
        assert any("target career" in r for r in top["reasons"]) and top["steps"] and top["objectives"] and top["expected_outcome"]

    def test_status_tracking_is_per_user(self, seeded, make_client):
        a, b = make_client("a@example.com"), make_client("b@example.com")
        pid = a.get("/api/practice/projects").json["data"][0]["id"]
        assert a.put(f"/api/practice/projects/{pid}/status", json={"status": "in_progress"}).status_code == 200
        assert a.put(f"/api/practice/projects/{pid}/status", json={"status": "nope"}).status_code == 422
        assert next(x for x in a.get("/api/practice/projects").json["data"] if x["id"] == pid)["status"] == "in_progress"
        assert next(x for x in b.get("/api/practice/projects").json["data"] if x["id"] == pid)["status"] == "not_started"
        assert a.put("/api/practice/projects/9999/status", json={"status": "completed"}).status_code == 404


class TestInterviews:
    def test_bank_interview_flow_has_no_fake_scores(self, seeded, make_client):
        c = make_client()
        put_skill(1, "Python", 70)
        r = c.post("/api/interviews", json={"role_id": role_id("backend-developer"), "difficulty": "beginner", "num_questions": 5})
        assert r.status_code == 201 and r.json["data"]["mode"] == "bank" and len(r.json["data"]["questions"]) == 5
        iid, qs = r.json["data"]["id"], r.json["data"]["questions"]
        assert c.post(f"/api/interviews/{iid}/complete").status_code == 409            # nothing answered yet
        c.put(f"/api/interviews/{iid}/answers/0", json={"answer": "A list is mutable and ordered while a tuple is immutable."})
        done = c.post(f"/api/interviews/{iid}/complete").json["data"]
        assert done["status"] == "completed" and done["feedback"] is None
        body = str(done).lower()
        assert "score" not in body and "grade" not in body and "rating" not in body
        q0 = done["questions"][0]["keyword_check"]
        assert set(q0) == {"mentioned", "not_mentioned"}
        assert c.put(f"/api/interviews/{iid}/answers/0", json={"answer": "late"}).status_code == 409
        assert len(c.get("/api/interviews").json["data"]["interviews"]) == 1

    def test_validation_and_isolation(self, seeded, make_client):
        a, b = make_client("a@example.com"), make_client("b@example.com")
        assert a.post("/api/interviews", json={"difficulty": "x", "num_questions": 99}).status_code == 422
        iid = a.post("/api/interviews", json={"role_id": role_id("data-analyst"), "difficulty": "intermediate", "num_questions": 4}).json["data"]["id"]
        assert b.get(f"/api/interviews/{iid}").status_code == 404
        assert b.put(f"/api/interviews/{iid}/answers/0", json={"answer": "x"}).status_code == 404
        assert a.put(f"/api/interviews/{iid}/answers/99", json={"answer": "x"}).status_code == 404
        assert a.put(f"/api/interviews/{iid}/answers/0", json={"answer": 5}).status_code == 422

    def test_ai_feedback_when_configured_and_graceful_failure(self, seeded, make_client, monkeypatch):
        seeded.config.update(AI_PROVIDER="anthropic", AI_API_KEY="k")
        c = make_client()
        iid = c.post("/api/interviews", json={"role_id": role_id("data-analyst"), "difficulty": "beginner", "num_questions": 3}).json["data"]["id"]
        assert c.get(f"/api/interviews/{iid}").json["data"]["mode"] == "ai"
        c.put(f"/api/interviews/{iid}/answers/0", json={"answer": "WHERE filters rows and HAVING filters groups."})
        monkeypatch.setattr("app.routes.interviews.features.interview_feedback",
                            lambda role, qa: {"overall": "Clear and concise.", "per_question": [{"index": 0, "strengths": ["Accurate"], "improvements": []}], "knowledge_gaps": []})
        fb = c.post(f"/api/interviews/{iid}/complete").json["data"]["feedback"]
        assert fb["source"] == "ai" and fb["overall"] == "Clear and concise."
        iid2 = c.post("/api/interviews", json={"role_id": role_id("data-analyst"), "difficulty": "beginner", "num_questions": 3}).json["data"]["id"]
        c.put(f"/api/interviews/{iid2}/answers/0", json={"answer": "text"})
        from app.ai.provider import AIUnavailable
        def boom(*a): raise AIUnavailable("down")
        monkeypatch.setattr("app.routes.interviews.features.interview_feedback", boom)
        fb2 = c.post(f"/api/interviews/{iid2}/complete").json["data"]["feedback"]
        assert fb2["source"] == "none" and "overall" not in fb2


class TestSummarySuggestion:
    def test_needs_data_then_template_fallback(self, seeded, make_client):
        c = make_client()
        assert c.post("/api/profile/suggest-summary").status_code == 409
        c.post("/api/profile/education", json={"institution": "ABC College", "degree": "B.Tech", "specialization": "Computer Science"})
        put_skill(1, "Python"); put_skill(1, "SQL")
        r = c.post("/api/profile/suggest-summary").json["data"]
        assert r["source"] == "template" and "Python" in r["summary"] and "ABC College" in r["summary"]
        assert c.get("/api/profile").json["data"]["summary"] is None            # a suggestion is never saved automatically
