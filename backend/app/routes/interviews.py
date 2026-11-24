import random

from flask import Blueprint
from flask_login import current_user

from app.ai import features
from app.ai.provider import AIUnavailable, ai_enabled
from app.extensions import db, limiter
from app.models import CareerRole, MockInterview, UserSkill
from app.models.base import utcnow
from app.seeds.learning import BEHAVIOURAL, INTERVIEW_BANK
from app.utils.decorators import get_json_body, login_required_api
from app.utils.responses import ApiError, ValidationError, ok

bp = Blueprint("interviews", __name__, url_prefix="/api/interviews")
LEVELS = ["beginner", "intermediate", "advanced"]


def _owned(iid) -> MockInterview:
    m = MockInterview.query.filter_by(id=iid, user_id=current_user.id).first()
    if not m:
        raise ApiError("not_found", "Interview not found.", 404)
    return m


def build_questions(role, difficulty, n, rng=None):
    rng = rng or random.Random()
    role_name = role.name if role else "General"

    # Track previously asked questions for this user to avoid repeating same questions
    past = MockInterview.query.filter_by(user_id=current_user.id).all()
    asked_texts = {q.get("text") for mi in past for q in (mi.questions or []) if isinstance(q, dict) and q.get("text")}

    # If AI is enabled, generate fresh role-specific questions and avoid asking already-seen questions
    if ai_enabled():
        try:
            ai_qs = features.generate_interview_questions(role_name, difficulty, n, exclude_texts=list(asked_texts))
            if len(ai_qs) >= 3:
                return ai_qs[:n]
        except Exception:
            pass

    # Bank fallback: select role-relevant skills, prioritizing unasked questions
    skills = [rs.skill.name for rs in sorted(role.skills, key=lambda r: -r.weight)] if role else \
        [us.skill.name for us in UserSkill.query.filter_by(user_id=current_user.id, status="user_confirmed")]
    pool = [{"skill": s, "difficulty": d, "text": q, "keywords": kw} for s in skills for d, q, kw in INTERVIEW_BANK.get(s, [])]

    unasked_exact = [q for q in pool if q["difficulty"] == difficulty and q["text"] not in asked_texts]
    unasked_rest = [q for q in pool if q["difficulty"] != difficulty and q["text"] not in asked_texts]
    asked_exact = [q for q in pool if q["difficulty"] == difficulty and q["text"] in asked_texts]
    asked_rest = [q for q in pool if q["difficulty"] != difficulty and q["text"] in asked_texts]

    rng.shuffle(unasked_exact)
    rng.shuffle(unasked_rest)
    rng.shuffle(asked_exact)
    rng.shuffle(asked_rest)
    tech = (unasked_exact + unasked_rest + asked_exact + asked_rest)[: max(n - 1, 1)]

    behav_pool = [{"skill": "Behavioural", "difficulty": d, "text": q, "keywords": kw} for d, q, kw in BEHAVIOURAL]
    unasked_behav = [b for b in behav_pool if b["text"] not in asked_texts]
    asked_behav = [b for b in behav_pool if b["text"] in asked_texts]
    rng.shuffle(unasked_behav)
    rng.shuffle(asked_behav)
    behav = unasked_behav + asked_behav

    return (tech + behav[: max(n - len(tech), 0)])[:n]


def keyword_check(question, answer):
    low = (answer or "").lower()
    hit = [k for k in question["keywords"] if k in low]
    return {"mentioned": hit, "not_mentioned": [k for k in question["keywords"] if k not in hit]}


def dump(m: MockInterview, full=False):
    d = {"id": m.id, "role": db.session.get(CareerRole, m.role_id).name if m.role_id else "General", "difficulty": m.difficulty, "mode": m.mode,
         "status": m.status, "created_at": m.created_at.isoformat() + "Z", "question_count": len(m.questions),
         "answered": len([a for a in m.answers.values() if a])}
    if full:
        d["questions"] = [{"index": i, "text": q["text"], "skill": q["skill"], "difficulty": q["difficulty"], "answer": m.answers.get(str(i), ""),
                           "keyword_check": keyword_check(q, m.answers.get(str(i))) if m.status == "completed" else None} for i, q in enumerate(m.questions)]
        d["feedback"] = m.feedback
    return d


@bp.get("")
@login_required_api
def history():
    rows = MockInterview.query.filter_by(user_id=current_user.id).order_by(MockInterview.created_at.desc()).limit(50).all()
    return ok({"interviews": [dump(m) for m in rows], "ai_enabled": ai_enabled()})


@bp.post("")
@login_required_api
def start():
    data = get_json_body()
    errors = {}
    n = data.get("num_questions", 5)
    if data.get("difficulty") not in LEVELS: errors["difficulty"] = "Choose a difficulty."
    if not isinstance(n, int) or isinstance(n, bool) or not 3 <= n <= 10: errors["num_questions"] = "Choose between 3 and 10 questions."
    role = None
    if data.get("role_id") is not None:
        role = db.session.get(CareerRole, data["role_id"]) if isinstance(data["role_id"], int) else None
        if role is None or not role.is_active: errors["role_id"] = "Choose a valid role."
    if errors:
        raise ValidationError(errors)
    qs = build_questions(role, data["difficulty"], n)
    if len(qs) < 3:
        raise ApiError("not_available", "Not enough interview questions for this role yet. Try another role.", 409)
    m = MockInterview(user_id=current_user.id, role_id=role.id if role else None, difficulty=data["difficulty"],
                      mode="ai" if ai_enabled() else "bank", questions=qs, answers={})
    db.session.add(m)
    db.session.commit()
    return ok(dump(m, True), 201)


@bp.get("/<int:iid>")
@login_required_api
def get_one(iid):
    return ok(dump(_owned(iid), True))


@bp.put("/<int:iid>/answers/<int:index>")
@login_required_api
def answer(iid, index):
    m = _owned(iid)
    if m.status != "in_progress":
        raise ApiError("finished", "This interview is already complete.", 409)
    if not 0 <= index < len(m.questions):
        raise ApiError("not_found", "Question not found.", 404)
    text = get_json_body().get("answer")
    if not isinstance(text, str) or len(text) > 4000:
        raise ValidationError({"answer": "Write an answer of up to 4000 characters."})
    m.answers = {**m.answers, str(index): text.strip()}
    db.session.commit()
    return ok({"saved": True})


@bp.post("/<int:iid>/complete")
@login_required_api
@limiter.limit("20 per hour")
def complete(iid):
    m = _owned(iid)
    if m.status == "completed":
        return ok(dump(m, True))
    if not any(a for a in m.answers.values()):
        raise ApiError("no_answers", "Answer at least one question first.", 409)
    m.status, m.completed_at, m.feedback = "completed", utcnow(), None
    if m.mode == "ai":
        qa = [{"index": i, "question": q["text"], "answer": m.answers.get(str(i), "")} for i, q in enumerate(m.questions) if m.answers.get(str(i))]
        try:
            m.feedback = {**features.interview_feedback(db.session.get(CareerRole, m.role_id).name if m.role_id else "General", qa), "source": "ai"}
        except AIUnavailable:
            m.feedback = {"source": "none", "note": "AI feedback wasn't available. Use the key-point check below to review your answers."}
    db.session.commit()
    return ok(dump(m, True))
