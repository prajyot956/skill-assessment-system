"""Assessment attempts: selection, timing, autosave, scoring. The server is the authority on all of it."""
import random
import re
from datetime import timedelta

from app.extensions import db
from app.models import (Assessment, AssessmentAttempt, AssessmentResult, AttemptAnswer, Notification, Question,
                        UserSkill)
from app.models.base import utcnow
from app.utils.responses import ApiError

DIFFICULTIES = ["beginner", "intermediate", "advanced"]
# A score on an easier test says less about ability, so proficiency is weighted by difficulty (documented in docs/ALGORITHMS.md).
DIFFICULTY_WEIGHT = {"beginner": 0.6, "intermediate": 0.85, "advanced": 1.0}
GRACE_SECONDS = 3
MIN_QUESTIONS = 3


def performance_category(pct: float) -> str:
    return "Advanced" if pct >= 80 else "Proficient" if pct >= 60 else "Developing" if pct >= 40 else "Needs improvement"


def normalize_short(text) -> str:
    return re.sub(r"[^a-z0-9+#]+", "", str(text or "").lower())


def available_counts(skill_id: int) -> dict:
    rows = (db.session.query(Question.difficulty, db.func.count(Question.id))
            .filter_by(skill_id=skill_id, is_active=True).group_by(Question.difficulty).all())
    counts = {d: 0 for d in DIFFICULTIES}
    counts.update(dict(rows))
    counts["total"] = sum(counts[d] for d in DIFFICULTIES)
    return counts


def select_questions(skill_id: int, difficulty: str, n: int, rng=None) -> list[int]:
    """Chosen difficulty first, then nearest difficulties if the pool is short. No repeats."""
    rng = rng or random.Random()
    by_diff = {d: [q.id for q in Question.query.filter_by(skill_id=skill_id, difficulty=d, is_active=True)] for d in DIFFICULTIES}
    order = sorted(DIFFICULTIES, key=lambda d: (abs(DIFFICULTIES.index(d) - DIFFICULTIES.index(difficulty)), DIFFICULTIES.index(d)))
    chosen = []
    for d in order:
        pool = by_diff[d][:]
        rng.shuffle(pool)
        chosen += pool[: n - len(chosen)]
        if len(chosen) >= n:
            break
    rng.shuffle(chosen)
    return chosen


def start_attempt(user_id: int, assessment: Assessment, difficulty: str, n: int, minutes: int):
    counts = available_counts(assessment.skill_id)
    if counts["total"] < MIN_QUESTIONS:
        raise ApiError("not_available", "This assessment doesn't have enough questions yet.", 409)
    n = min(n, counts["total"])
    ids = select_questions(assessment.skill_id, difficulty, n)
    now = utcnow()
    attempt = AssessmentAttempt(user_id=user_id, assessment_id=assessment.id, difficulty=difficulty, num_questions=len(ids),
                                duration_seconds=minutes * 60, question_ids=ids, started_at=now,
                                expires_at=now + timedelta(minutes=minutes))
    db.session.add(attempt)
    db.session.commit()
    return attempt


def start_attempt_with_ids(user_id: int, assessment: Assessment, difficulty: str, question_ids: list[int], minutes: int = 15):
    """Start an attempt using a specific pre-selected list of question IDs (for AI-generated tests)."""
    now = utcnow()
    attempt = AssessmentAttempt(
        user_id=user_id, assessment_id=assessment.id, difficulty=difficulty,
        num_questions=len(question_ids), duration_seconds=minutes * 60,
        question_ids=question_ids, started_at=now,
        expires_at=now + timedelta(minutes=minutes)
    )
    db.session.add(attempt)
    db.session.commit()
    return attempt


def is_expired(attempt, grace=0) -> bool:
    return utcnow() > attempt.expires_at + timedelta(seconds=grace)


def serialize_question(q: Question, attempt_id: int) -> dict:
    """Never includes is_correct, accepted answers or explanations."""
    d = {"id": q.id, "text": q.text, "type": q.qtype, "marks": q.marks, "topic": q.topic}
    if q.qtype not in ("short", "coding"):
        opts = [{"id": o.id, "text": o.text} for o in q.options]
        if q.qtype != "true_false":  # stable per-attempt shuffle so a resumed attempt looks identical
            random.Random(attempt_id * 100003 + q.id).shuffle(opts)
        d["options"] = opts
    return d


def attempt_payload(attempt: AssessmentAttempt) -> dict:
    qs = {q.id: q for q in Question.query.filter(Question.id.in_(attempt.question_ids))}
    saved = {a.question_id: a.answer for a in attempt.answers}
    return {"id": attempt.id, "status": attempt.status, "skill": attempt.assessment.skill.name, "title": attempt.assessment.title,
            "difficulty": attempt.difficulty, "duration_seconds": attempt.duration_seconds,
            "started_at": attempt.started_at.isoformat() + "Z", "expires_at": attempt.expires_at.isoformat() + "Z",
            "server_now": utcnow().isoformat() + "Z",
            "questions": [serialize_question(qs[i], attempt.id) for i in attempt.question_ids if i in qs],
            "answers": {str(k): v for k, v in saved.items()}}


def validate_answer(q: Question, value):
    """Returns a clean, storable answer or None (= cleared). Rejects options that don't belong to the question."""
    if value is None or value == "" or value == []:
        return None
    ids = {o.id for o in q.options}
    if q.qtype in ("single", "true_false"):
        if isinstance(value, bool) or not isinstance(value, int) or value not in ids:
            raise ApiError("invalid_answer", f"Invalid answer for question {q.id}.", 422)
        return value
    if q.qtype == "multiple":
        if not isinstance(value, list) or not all(isinstance(v, int) and not isinstance(v, bool) and v in ids for v in value):
            raise ApiError("invalid_answer", f"Invalid answer for question {q.id}.", 422)
        return sorted(set(value))
    if q.qtype in ("short", "coding") and (not isinstance(value, str) or len(value) > 300):
        raise ApiError("invalid_answer", f"Invalid answer for question {q.id}.", 422)
    return value.strip()


def save_answers(attempt: AssessmentAttempt, answers: dict):
    if not isinstance(answers, dict) or len(answers) > 200:
        raise ApiError("invalid_json", "'answers' must be an object keyed by question id.", 400)
    allowed = set(attempt.question_ids)
    qs = {q.id: q for q in Question.query.filter(Question.id.in_(allowed))}
    existing = {a.question_id: a for a in attempt.answers}
    for key, value in answers.items():
        try:
            qid = int(key)
        except (TypeError, ValueError):
            raise ApiError("invalid_answer", "Unknown question.", 422)
        if qid not in allowed:
            raise ApiError("invalid_answer", "That question is not part of this attempt.", 422)
        clean = validate_answer(qs[qid], value)
        row = existing.get(qid)
        if clean is None:
            if row:
                db.session.delete(row)
        elif row:
            row.answer = clean
        else:
            db.session.add(AttemptAnswer(attempt_id=attempt.id, question_id=qid, answer=clean))
    db.session.flush()


def score_answer(q: Question, answer):
    """-> (is_correct | None, marks). Multiple-select is all-or-nothing; short answers match normalized accepted forms."""
    if answer is None:
        return None, 0.0
    if q.qtype in ("short", "coding"):
        ok = normalize_short(answer) in {normalize_short(a) for a in (q.accepted_answers or [])}
    elif q.qtype == "multiple":
        ok = set(answer) == {o.id for o in q.options if o.is_correct}
    else:
        ok = answer in {o.id for o in q.options if o.is_correct}
    return ok, (q.marks if ok else 0.0)


def finalize(attempt: AssessmentAttempt, status: str):
    """Score saved answers, store the result, update the user's proficiency. Idempotent."""
    if attempt.result is not None:
        return attempt.result
    qs = {q.id: q for q in Question.query.filter(Question.id.in_(attempt.question_ids))}
    saved = {a.question_id: a for a in attempt.answers}
    total = obtained = 0.0
    correct = wrong = blank = 0
    topics, diffs = {}, {}
    for qid in attempt.question_ids:
        q = qs[qid]
        row = saved.get(qid)
        is_ok, marks = score_answer(q, row.answer if row else None)
        if row:
            row.is_correct, row.marks_awarded = is_ok, marks
        total += q.marks
        obtained += marks
        if is_ok is None: blank += 1
        elif is_ok: correct += 1
        else: wrong += 1
        for bucket, key in ((topics, q.topic), (diffs, q.difficulty)):
            b = bucket.setdefault(key, {"earned": 0.0, "total": 0.0, "correct": 0, "count": 0})
            b["earned"] += marks; b["total"] += q.marks; b["count"] += 1; b["correct"] += 1 if is_ok else 0
    pct = round(obtained / total * 100, 1) if total else 0.0
    answered = correct + wrong
    result = AssessmentResult(attempt_id=attempt.id, total_marks=total, obtained_marks=obtained, percentage=pct,
                              accuracy=round(correct / answered * 100, 1) if answered else 0.0,
                              performance_category=performance_category(pct), correct_count=correct, incorrect_count=wrong,
                              unanswered_count=blank, topic_breakdown=topics, difficulty_breakdown=diffs)
    db.session.add(result)
    attempt.status, attempt.submitted_at = status, utcnow()

    us = UserSkill.query.filter_by(user_id=attempt.user_id, skill_id=attempt.assessment.skill_id).first()
    if us is None:
        us = UserSkill(user_id=attempt.user_id, skill_id=attempt.assessment.skill_id, status="user_confirmed", source="assessment")
        db.session.add(us)
    us.proficiency_pct = round(pct * DIFFICULTY_WEIGHT[attempt.difficulty], 1)  # latest attempt defines current proficiency
    us.last_assessed_at = attempt.submitted_at
    db.session.add(Notification(user_id=attempt.user_id, kind="assessment", title=f"{attempt.assessment.title} assessment complete",
                                message=f"You scored {pct}% ({result.performance_category}).", link=f"/assessments/results/{attempt.id}"))
    db.session.commit()
    return result


def expire_if_needed(attempt: AssessmentAttempt) -> bool:
    if attempt.status == "in_progress" and is_expired(attempt, GRACE_SECONDS):
        finalize(attempt, "expired")
        return True
    return False


def result_payload(attempt: AssessmentAttempt) -> dict:
    r = attempt.result
    qs = {q.id: q for q in Question.query.filter(Question.id.in_(attempt.question_ids))}
    saved = {a.question_id: a for a in attempt.answers}
    review = []
    for qid in attempt.question_ids:
        q, row = qs[qid], saved.get(qid)
        item = {"id": q.id, "text": q.text, "type": q.qtype, "topic": q.topic, "difficulty": q.difficulty, "marks": q.marks,
                "awarded": row.marks_awarded if row and row.marks_awarded is not None else 0.0,
                "status": "unanswered" if not row else ("correct" if row.is_correct else "incorrect"),
                "your_answer": row.answer if row else None, "explanation": q.explanation}
        if q.qtype in ("short", "coding"):
            item["correct_answer"] = (q.accepted_answers or [""])[0]
        else:
            item["options"] = [{"id": o.id, "text": o.text, "is_correct": o.is_correct} for o in q.options]
        review.append(item)
    pct_rows = lambda b: [{"name": k, "percentage": round(v["earned"] / v["total"] * 100, 1) if v["total"] else 0.0,
                           "correct": v["correct"], "count": v["count"]} for k, v in b.items()]
    topics = pct_rows(r.topic_breakdown)
    return {"attempt_id": attempt.id, "skill": attempt.assessment.skill.name, "title": attempt.assessment.title,
            "difficulty": attempt.difficulty, "status": attempt.status, "submitted_at": attempt.submitted_at.isoformat() + "Z",
            "total_marks": r.total_marks, "obtained_marks": r.obtained_marks, "percentage": r.percentage, "accuracy": r.accuracy,
            "performance_category": r.performance_category, "correct": r.correct_count, "incorrect": r.incorrect_count,
            "unanswered": r.unanswered_count, "topics": topics, "difficulties": pct_rows(r.difficulty_breakdown),
            "strengths": [t["name"] for t in sorted(topics, key=lambda t: -t["percentage"]) if t["percentage"] >= 75],
            "weaknesses": [t["name"] for t in sorted(topics, key=lambda t: t["percentage"]) if t["percentage"] < 50],
            "proficiency_pct": round(r.percentage * DIFFICULTY_WEIGHT[attempt.difficulty], 1), "review": review,
            "assessment_id": attempt.assessment_id}
