import json
import random
from datetime import timedelta

import pytest

from app.extensions import db
from app.models import (Assessment, AssessmentAttempt, AssessmentCategory, AttemptAnswer, Notification, Question,
                        QuestionOption, Skill, UserSkill)
from app.models.base import utcnow
from app.services import assessment_service as svc
from app.seeds.skills import CATEGORIES


def aid(skill_name):
    return Assessment.query.join(Skill).filter(Skill.name == skill_name).one().id


def start(c, skill="Python", difficulty="beginner", n=5, minutes=10):
    return c.post("/api/assessments/attempts", json={"assessment_id": aid(skill), "difficulty": difficulty,
                                                      "num_questions": n, "duration_minutes": minutes})


def correct_answer(q):
    if q.qtype == "short":
        return q.accepted_answers[0]
    ids = [o.id for o in q.options if o.is_correct]
    return ids if q.qtype == "multiple" else ids[0]


def wrong_answer(q):
    if q.qtype == "short":
        return "definitely not it"
    wrong = [o.id for o in q.options if not o.is_correct]
    return [wrong[0]] if q.qtype == "multiple" else wrong[0]


class TestCatalogAndStart:
    def test_every_builtin_assessment_has_a_seeded_question_pool(self, seeded):
        skill_names = {name for _, _, skills in CATEGORIES for name, _ in skills}
        assert len(skill_names) == 26
        for name in skill_names:
            skill = Skill.query.filter_by(name=name).one()
            counts = svc.available_counts(skill.id)
            assert counts["total"] >= svc.MIN_QUESTIONS, name
            assert all(counts[difficulty] >= 3 for difficulty in svc.DIFFICULTIES), (name, counts)

    def test_catalog_lists_available_assessments_without_answers(self, seeded, make_client):
        c = make_client()
        r = c.get("/api/assessments/catalog")
        assert r.json["data"]["ai_enabled"] is False
        cats = {x["name"]: x for x in r.json["data"]["categories"]}
        assert set(cats) == {"Programming", "Web Development", "Database", "Data Analytics", "AI and Machine Learning", "Other"}
        prog = {a["skill"]: a for a in cats["Programming"]["assessments"]}
        assert prog["Python"]["available"] is True and prog["Python"]["questions"]["total"] == 13
        assert prog["Java"]["available"] is True
        assert "is_correct" not in r.get_data(as_text=True) and "accepted_answers" not in r.get_data(as_text=True)

    def test_start_validation(self, seeded, make_client):
        c = make_client()
        bad = c.post("/api/assessments/attempts", json={"assessment_id": 999, "difficulty": "x", "num_questions": 1, "duration_minutes": 0})
        assert bad.status_code == 422 and set(bad.json["error"]["details"]["fields"]) == {"assessment_id", "difficulty", "num_questions", "duration_minutes"}
        sid = Skill.query.filter_by(name="Java").one().id
        Question.query.filter_by(skill_id=sid).update({"is_active": False})
        db.session.commit()
        assert start(c, "Java").status_code == 409  # not enough questions
        Question.query.filter_by(skill_id=sid).update({"is_active": True})
        db.session.commit()

    def test_count_is_capped_to_the_pool(self, seeded, make_client):
        r = start(make_client(), "HTML", n=30)
        assert r.status_code == 201 and r.json["data"]["num_questions"] == 10 and r.json["data"]["capped"] is True

    def test_starting_again_resumes_the_open_attempt(self, seeded, make_client):
        c = make_client()
        a1 = start(c).json["data"]["attempt_id"]
        r = start(c)
        assert r.status_code == 200 and r.json["data"] == {"attempt_id": a1, "resumed": True}
        assert AssessmentAttempt.query.count() == 1


class TestSelection:
    def test_no_repeats_and_difficulty_preferred(self, seeded):
        skill = Skill.query.filter_by(name="Python").one()
        ids = svc.select_questions(skill.id, "beginner", 5)
        assert len(ids) == len(set(ids)) == 5
        assert {Question.query.get(i).difficulty for i in ids} == {"beginner"}
        mixed = svc.select_questions(skill.id, "advanced", 6)  # only 3 advanced exist: nearest levels fill in
        diffs = [Question.query.get(i).difficulty for i in mixed]
        assert diffs.count("advanced") == 3 and diffs.count("intermediate") == 3

    def test_selection_is_randomised(self, seeded):
        skill = Skill.query.filter_by(name="Python").one()
        results = {tuple(svc.select_questions(skill.id, "intermediate", 5, random.Random(s))) for s in range(10)}
        assert len(results) > 1


class TestAttemptPayloadAndAutosave:
    def test_payload_exposes_no_answer_keys(self, seeded, make_client):
        c = make_client()
        aid_ = start(c, n=13, difficulty="intermediate").json["data"]["attempt_id"]
        r = c.get(f"/api/assessments/attempts/{aid_}")
        body = r.get_data(as_text=True)
        for leaked in ("is_correct", "accepted_answers", "explanation", "correct_answer"):
            assert leaked not in body
        qs = r.json["data"]["questions"]
        assert len({q["id"] for q in qs}) == len(qs) == 13
        assert all(set(q) <= {"id", "text", "type", "marks", "topic", "options"} for q in qs)
        assert r.json["data"]["expires_at"].endswith("Z") and r.json["data"]["server_now"]

    def test_autosave_then_resume_shows_answers_and_same_order(self, seeded, make_client):
        c = make_client()
        a = start(c).json["data"]["attempt_id"]
        first = c.get(f"/api/assessments/attempts/{a}").json["data"]
        q = first["questions"][0]
        val = "len" if q["type"] == "short" else ([q["options"][0]["id"]] if q["type"] == "multiple" else q["options"][0]["id"])
        assert c.put(f"/api/assessments/attempts/{a}/answers", json={"answers": {str(q["id"]): val}}).status_code == 200
        again = c.get(f"/api/assessments/attempts/{a}").json["data"]
        assert again["answers"][str(q["id"])] == val
        assert [x["id"] for x in again["questions"]] == [x["id"] for x in first["questions"]]
        assert [o["id"] for o in again["questions"][0].get("options", [])] == [o["id"] for o in first["questions"][0].get("options", [])]
        c.put(f"/api/assessments/attempts/{a}/answers", json={"answers": {str(q["id"]): None}})
        assert c.get(f"/api/assessments/attempts/{a}").json["data"]["answers"] == {}

    def test_invalid_answers_rejected(self, seeded, make_client):
        c = make_client()
        a = start(c).json["data"]["attempt_id"]
        qs = c.get(f"/api/assessments/attempts/{a}").json["data"]["questions"]
        mcq = next(q for q in qs if q["type"] == "single")
        other = Question.query.filter(~Question.id.in_([q["id"] for q in qs])).first()
        foreign_option = other.options[0].id if other.options else 999999
        put = lambda ans: c.put(f"/api/assessments/attempts/{a}/answers", json={"answers": ans})
        assert put({str(mcq["id"]): foreign_option}).status_code == 422       # option from another question
        assert put({str(other.id): "x"}).status_code == 422                    # question not in this attempt
        assert put({"abc": 1}).status_code == 422
        assert put({str(mcq["id"]): True}).status_code == 422                  # bool is not an option id
        assert put({str(mcq["id"]): [mcq["options"][0]["id"]]}).status_code == 422
        assert c.put(f"/api/assessments/attempts/{a}/answers", json={"answers": [1]}).status_code == 400
        assert AttemptAnswer.query.count() == 0


class TestScoring:
    @pytest.fixture()
    def tiny(self, seeded):
        """A 3-question assessment with marks 1, 2, 3 so results can be computed by hand."""
        cat = AssessmentCategory.query.first()
        skill = Skill(name="Tiny Skill", slug="tiny-skill", category="Programming", aliases=[])
        db.session.add(skill); db.session.flush()
        a = Assessment(category_id=cat.id, skill_id=skill.id, title="Tiny")
        db.session.add(a)
        qs = []
        for i, (topic, diff, marks) in enumerate([("A", "beginner", 1), ("B", "beginner", 2), ("A", "advanced", 3)]):
            q = Question(skill_id=skill.id, topic=topic, difficulty=diff, qtype="single", text=f"Q{i}", marks=marks, explanation=f"E{i}")
            q.options = [QuestionOption(text="right", is_correct=True, position=0), QuestionOption(text="wrong", is_correct=False, position=1)]
            db.session.add(q); qs.append(q)
        db.session.commit()
        return a, qs

    def test_hand_computed_result(self, tiny, make_client):
        a, qs = tiny
        c = make_client()
        att = c.post("/api/assessments/attempts", json={"assessment_id": a.id, "difficulty": "beginner", "num_questions": 3, "duration_minutes": 5}).json["data"]["attempt_id"]
        ans = {str(qs[0].id): qs[0].options[0].id,      # correct (1 mark)
               str(qs[1].id): qs[1].options[1].id}      # wrong; Q3 unanswered
        c.put(f"/api/assessments/attempts/{att}/answers", json={"answers": ans})
        assert c.post(f"/api/assessments/attempts/{att}/submit").status_code == 200
        r = c.get(f"/api/assessments/attempts/{att}/result").json["data"]
        assert (r["total_marks"], r["obtained_marks"], r["percentage"]) == (6, 1, 16.7)
        assert (r["correct"], r["incorrect"], r["unanswered"], r["accuracy"]) == (1, 1, 1, 50.0)
        assert r["performance_category"] == "Needs improvement"
        topics = {t["name"]: t["percentage"] for t in r["topics"]}
        assert topics == {"A": 25.0, "B": 0.0}               # A: 1/(1+3); B: 0/2
        diffs = {d["name"]: d["percentage"] for d in r["difficulties"]}
        assert diffs == {"beginner": 33.3, "advanced": 0.0}  # 1/3 and 0/3
        assert r["weaknesses"] == ["B", "A"] and r["strengths"] == []  # weakest first
        assert r["proficiency_pct"] == 10.0                    # 16.7 x 0.6 (beginner weight)
        us = UserSkill.query.filter_by(user_id=1).one()
        assert us.proficiency_pct == 10.0 and us.evidence_level == "assessment_verified"
        review = {q["text"]: q for q in r["review"]}
        assert review["Q0"]["status"] == "correct" and review["Q1"]["status"] == "incorrect" and review["Q2"]["status"] == "unanswered"
        assert any(o["is_correct"] for o in review["Q1"]["options"]) and review["Q1"]["explanation"] == "E1"
        assert Notification.query.filter_by(user_id=1, kind="assessment").count() == 1

    def test_perfect_score_and_weights(self, seeded, make_client):
        c = make_client()
        a = start(c, "SQL", "advanced", 13, 20).json["data"]["attempt_id"]
        att = AssessmentAttempt.query.get(a)
        qs = Question.query.filter(Question.id.in_(att.question_ids)).all()
        c.put(f"/api/assessments/attempts/{a}/answers", json={"answers": {str(q.id): correct_answer(q) for q in qs}})
        c.post(f"/api/assessments/attempts/{a}/submit")
        r = c.get(f"/api/assessments/attempts/{a}/result").json["data"]
        assert r["percentage"] == 100.0 and r["performance_category"] == "Advanced" and r["incorrect"] == 0 and r["proficiency_pct"] == 100.0

    def test_all_question_types_score_correctly(self, seeded, make_client):
        by_type = {}
        for q in Question.query.all():
            by_type.setdefault(q.qtype, q)
        assert set(by_type) == {"single", "multiple", "true_false", "short", "coding"}
        m = by_type["multiple"]
        assert svc.score_answer(m, sorted(o.id for o in m.options if o.is_correct)) == (True, m.marks)
        assert svc.score_answer(m, [m.options[0].id]) [0] is False or len([o for o in m.options if o.is_correct]) == 1
        assert svc.score_answer(m, [o.id for o in m.options]) == (False, 0.0)    # selecting everything is not correct
        s = by_type["short"]
        accepted = s.accepted_answers[0]
        for variant in (accepted.upper(), f"  {accepted}. ", f"{accepted}()" if not accepted.endswith(")") else accepted):
            ok, marks = svc.score_answer(s, variant)
            assert ok is True or variant.endswith("()"), variant
        assert svc.score_answer(s, "wrong")[0] is False and svc.score_answer(s, None) == (None, 0.0)
        t = by_type["true_false"]
        assert svc.score_answer(t, next(o.id for o in t.options if o.is_correct))[0] is True

    def test_submitting_twice_does_not_double_count(self, seeded, make_client):
        c = make_client()
        a = start(c).json["data"]["attempt_id"]
        c.post(f"/api/assessments/attempts/{a}/submit"); c.post(f"/api/assessments/attempts/{a}/submit")
        assert Notification.query.filter_by(kind="assessment").count() == 1
        assert c.get(f"/api/assessments/attempts/{a}/result").json["data"]["unanswered"] == 5

    def test_result_hidden_until_finished(self, seeded, make_client):
        c = make_client()
        a = start(c).json["data"]["attempt_id"]
        r = c.get(f"/api/assessments/attempts/{a}/result")
        assert r.status_code == 409 and r.json["error"]["code"] == "not_finished"

    def test_latest_attempt_defines_proficiency_and_history_trend(self, seeded, make_client):
        c = make_client()
        for good in (False, True):
            a = start(c, "Python", "beginner", 5).json["data"]["attempt_id"]
            att = AssessmentAttempt.query.get(a)
            qs = Question.query.filter(Question.id.in_(att.question_ids)).all()
            c.put(f"/api/assessments/attempts/{a}/answers", json={"answers": {str(q.id): (correct_answer(q) if good else wrong_answer(q)) for q in qs}})
            c.post(f"/api/assessments/attempts/{a}/submit")
        h = c.get("/api/assessments/attempts").json
        assert h["meta"]["total"] == 2 and [x["percentage"] for x in h["data"]] == [100.0, 0.0]
        assert UserSkill.query.one().proficiency_pct == 60.0  # 100% x 0.6
        assert c.get(f"/api/assessments/attempts?assessment_id={aid('SQL')}").json["meta"]["total"] == 0


class TestTimerAndExpiry:
    def _expire(self, a, seconds=60):
        att = AssessmentAttempt.query.get(a)
        att.expires_at = utcnow() - timedelta(seconds=seconds)
        db.session.commit()

    def test_expired_attempt_is_scored_on_saved_answers(self, seeded, make_client):
        c = make_client()
        a = start(c).json["data"]["attempt_id"]
        att = AssessmentAttempt.query.get(a)
        q = Question.query.get(att.question_ids[0])
        c.put(f"/api/assessments/attempts/{a}/answers", json={"answers": {str(q.id): correct_answer(q)}})
        self._expire(a)
        r = c.get(f"/api/assessments/attempts/{a}")
        assert r.json["data"]["finished"] is True and r.json["data"]["status"] == "expired"
        res = c.get(f"/api/assessments/attempts/{a}/result").json["data"]
        assert res["status"] == "expired" and res["correct"] == 1 and res["unanswered"] == 4

    def test_autosave_and_submit_cannot_add_answers_after_expiry(self, seeded, make_client):
        c = make_client()
        a = start(c).json["data"]["attempt_id"]
        att = AssessmentAttempt.query.get(a)
        q = Question.query.get(att.question_ids[0])
        self._expire(a)
        r = c.put(f"/api/assessments/attempts/{a}/answers", json={"answers": {str(q.id): correct_answer(q)}})
        assert r.status_code == 409 and r.json["error"]["code"] == "attempt_expired"
        c.post(f"/api/assessments/attempts/{a}/submit", json={"answers": {str(q.id): correct_answer(q)}})
        assert AttemptAnswer.query.count() == 0
        assert c.get(f"/api/assessments/attempts/{a}/result").json["data"]["correct"] == 0

    def test_new_attempt_allowed_after_previous_expired(self, seeded, make_client):
        c = make_client()
        a = start(c).json["data"]["attempt_id"]
        self._expire(a)
        r = start(c)
        assert r.status_code == 201 and r.json["data"]["attempt_id"] != a

    def test_just_inside_grace_period_is_accepted(self, seeded, make_client):
        c = make_client()
        a = start(c).json["data"]["attempt_id"]
        self._expire(a, seconds=1)
        att = AssessmentAttempt.query.get(a)
        assert not svc.is_expired(att, svc.GRACE_SECONDS)


class TestAccessControl:
    def test_other_users_attempts_are_invisible(self, seeded, make_client):
        a, b = make_client("a@example.com"), make_client("b@example.com")
        att = start(a).json["data"]["attempt_id"]
        a.post(f"/api/assessments/attempts/{att}/submit")
        for method, path in [("get", f"/api/assessments/attempts/{att}"), ("put", f"/api/assessments/attempts/{att}/answers"),
                             ("post", f"/api/assessments/attempts/{att}/submit"), ("get", f"/api/assessments/attempts/{att}/result")]:
            assert getattr(b, method)(path, json={"answers": {}}).status_code == 404, path
        assert b.get("/api/assessments/attempts").json["data"] == []

    def test_requires_login(self, seeded, client):
        assert client.get("/api/assessments/catalog").status_code == 401
        assert client.post("/api/assessments/attempts", json={}).status_code == 401
