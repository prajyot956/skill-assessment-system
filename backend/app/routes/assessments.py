from flask import Blueprint, request
from flask_login import current_user

from app.ai.provider import ai_enabled
from app.extensions import db
from app.models import Assessment, AssessmentAttempt, AssessmentCategory, AssessmentResult, Question, QuestionOption, UserSkill
from app.services import assessment_service as svc
from app.utils.decorators import get_json_body, login_required_api
from app.utils.responses import ApiError, ValidationError, ok

bp = Blueprint("assessments", __name__, url_prefix="/api/assessments")


def _attempt(attempt_id) -> AssessmentAttempt:
    a = AssessmentAttempt.query.filter_by(id=attempt_id, user_id=current_user.id).first()
    if not a:
        raise ApiError("not_found", "Assessment attempt not found.", 404)
    return a


@bp.get("/catalog")
@login_required_api
def catalog():
    in_progress = {a.assessment_id: a for a in AssessmentAttempt.query.filter_by(user_id=current_user.id, status="in_progress")}
    for a in list(in_progress.values()):
        if svc.expire_if_needed(a):
            del in_progress[a.assessment_id]
    prof = {us.skill_id: us for us in UserSkill.query.filter_by(user_id=current_user.id)}

    # Ensure all user's detected/confirmed resume skills have an assessment entry in catalog
    all_cats = AssessmentCategory.query.filter_by(is_active=True).all()
    cats_by_name = {c.name.lower(): c for c in all_cats}
    other_cat = next((c for c in all_cats if c.name == "Other"), all_cats[0] if all_cats else None)
    added_any = False
    for us in prof.values():
        if us.skill and not Assessment.query.filter_by(skill_id=us.skill_id).first():
            cat = None
            if us.skill.category:
                sc_lower = us.skill.category.lower()
                for cname, c in cats_by_name.items():
                    if cname in sc_lower or sc_lower in cname:
                        cat = c
                        break
            cat = cat or other_cat
            if cat:
                db.session.add(Assessment(category_id=cat.id, skill_id=us.skill_id, title=us.skill.name))
                added_any = True
    if added_any:
        db.session.commit()

    out = []
    for cat in AssessmentCategory.query.filter_by(is_active=True).order_by(AssessmentCategory.position):
        items = []
        for a in Assessment.query.filter_by(category_id=cat.id, is_active=True).order_by(Assessment.title):
            counts = svc.available_counts(a.skill_id)
            us = prof.get(a.skill_id)
            items.append({"id": a.id, "title": a.title, "skill": a.skill.name, "description": a.description,
                          "questions": counts, "available": counts["total"] >= svc.MIN_QUESTIONS,
                          "proficiency_pct": round(us.proficiency_pct, 1) if us and us.proficiency_pct is not None else None,
                          "in_progress_attempt_id": in_progress[a.id].id if a.id in in_progress else None})
        out.append({"id": cat.id, "name": cat.name, "description": cat.description, "assessments": items})
    return ok({"categories": out, "ai_enabled": ai_enabled()})


@bp.post("/attempts")
@login_required_api
def start():
    data = get_json_body()
    errors = {}
    difficulty = data.get("difficulty")
    if difficulty not in svc.DIFFICULTIES: errors["difficulty"] = "Choose beginner, intermediate or advanced."
    n, minutes = data.get("num_questions"), data.get("duration_minutes")
    if not isinstance(n, int) or isinstance(n, bool) or not 3 <= n <= 50: errors["num_questions"] = "Choose between 3 and 50 questions."
    if not isinstance(minutes, int) or isinstance(minutes, bool) or not 1 <= minutes <= 180: errors["duration_minutes"] = "Choose between 1 and 180 minutes."
    assessment = db.session.get(Assessment, data.get("assessment_id")) if isinstance(data.get("assessment_id"), int) else None
    if assessment is None or not assessment.is_active: errors["assessment_id"] = "Choose an assessment."
    if errors:
        raise ValidationError(errors)
    existing = AssessmentAttempt.query.filter_by(user_id=current_user.id, assessment_id=assessment.id, status="in_progress").first()
    if existing and not svc.expire_if_needed(existing):
        return ok({"attempt_id": existing.id, "resumed": True})
    attempt = svc.start_attempt(current_user.id, assessment, difficulty, n, minutes)
    return ok({"attempt_id": attempt.id, "resumed": False, "num_questions": attempt.num_questions,
               "capped": attempt.num_questions < n}, 201)


@bp.get("/attempts")
@login_required_api
def history():
    page, per = max(request.args.get("page", 1, type=int), 1), min(max(request.args.get("per_page", 20, type=int), 1), 100)
    q = (db.session.query(AssessmentAttempt, AssessmentResult).join(AssessmentResult, AssessmentResult.attempt_id == AssessmentAttempt.id)
         .filter(AssessmentAttempt.user_id == current_user.id))
    if request.args.get("assessment_id", type=int):
        q = q.filter(AssessmentAttempt.assessment_id == request.args.get("assessment_id", type=int))
    total = q.count()
    rows = q.order_by(AssessmentAttempt.submitted_at.desc()).offset((page - 1) * per).limit(per).all()
    return ok([{"attempt_id": a.id, "assessment_id": a.assessment_id, "skill": a.assessment.skill.name, "difficulty": a.difficulty,
                "status": a.status, "percentage": r.percentage, "category": r.performance_category,
                "correct": r.correct_count, "total": a.num_questions, "submitted_at": a.submitted_at.isoformat() + "Z"}
               for a, r in rows], meta={"page": page, "per_page": per, "total": total})


@bp.get("/attempts/<int:attempt_id>")
@login_required_api
def get_attempt(attempt_id):
    a = _attempt(attempt_id)
    svc.expire_if_needed(a)
    if a.status != "in_progress":
        return ok({"id": a.id, "status": a.status, "finished": True})
    return ok({**svc.attempt_payload(a), "finished": False})


@bp.put("/attempts/<int:attempt_id>/answers")
@login_required_api
def autosave(attempt_id):
    a = _attempt(attempt_id)
    if a.status != "in_progress" or svc.expire_if_needed(a):
        raise ApiError("attempt_expired", "Time is up. Your saved answers were submitted.", 409)
    svc.save_answers(a, get_json_body().get("answers"))
    db.session.commit()
    return ok({"saved": True, "server_now": svc.utcnow().isoformat() + "Z"})


@bp.post("/attempts/<int:attempt_id>/submit")
@login_required_api
def submit(attempt_id):
    a = _attempt(attempt_id)
    if a.status != "in_progress":
        return ok({"attempt_id": a.id, "status": a.status})
    data = request.get_json(silent=True) or {}
    if "answers" in data and not svc.is_expired(a, svc.GRACE_SECONDS):
        svc.save_answers(a, data["answers"])  # last-second answers count only inside the time limit
    svc.finalize(a, "expired" if svc.is_expired(a, svc.GRACE_SECONDS) else "submitted")
    return ok({"attempt_id": a.id, "status": a.status})


@bp.get("/attempts/<int:attempt_id>/result")
@login_required_api
def result(attempt_id):
    a = _attempt(attempt_id)
    svc.expire_if_needed(a)
    if a.result is None:
        raise ApiError("not_finished", "Finish the assessment to see results.", 409)
    return ok(svc.result_payload(a))


@bp.post("/attempts/ai-generate")
@login_required_api
def ai_generate():
    """Generate AI questions for a skill and immediately start an attempt."""
    from app.ai.features import generate_questions, AIUnavailable as _AIUnavailable
    from app.ai.provider import get_provider

    if not get_provider():
        raise ApiError("ai_unavailable", "AI is not configured. Set AI_PROVIDER and AI_API_KEY in .env.", 503)

    data = get_json_body()
    assessment_id = data.get("assessment_id")
    difficulty = data.get("difficulty", "intermediate")
    num_q = data.get("num_questions", 5)

    if difficulty not in svc.DIFFICULTIES:
        raise ApiError("invalid_input", "difficulty must be beginner, intermediate, or advanced.", 400)
    if not isinstance(num_q, int) or not 3 <= num_q <= 15:
        raise ApiError("invalid_input", "num_questions must be between 3 and 15.", 400)

    assessment = db.session.get(Assessment, assessment_id) if isinstance(assessment_id, int) else None
    if assessment is None or not assessment.is_active:
        raise ApiError("not_found", "Assessment not found.", 404)

    skill = assessment.skill

    try:
        raw_questions = generate_questions(skill.name, difficulty, num_q)
    except Exception as e:
        raise ApiError("ai_error", f"AI failed to generate questions: {str(e)[:200]}", 502)

    # Persist generated questions to DB
    generated_ids = []
    TYPE_MAP = {"single": "single", "multiple": "multiple", "true_false": "true_false",
                "short": "short", "coding": "coding"}
    marks_map = {"beginner": 1.0, "intermediate": 2.0, "advanced": 3.0}
    for item in raw_questions:
        qtype = TYPE_MAP.get(str(item.get("type", "single")), "single")
        q = Question(
            skill_id=skill.id,
            topic=str(item.get("topic", "AI-Generated"))[:100],
            difficulty=difficulty,
            qtype=qtype,
            text=str(item.get("text", ""))[:2000],
            explanation=str(item.get("explanation", ""))[:1000] if item.get("explanation") else None,
            marks=marks_map.get(difficulty, 1.0)
        )

        opts = item.get("options")
        ans = item.get("answer")
        if qtype in ("short", "coding"):
            q.accepted_answers = [str(ans)] if isinstance(ans, str) else ([str(a) for a in ans] if isinstance(ans, list) else [])
        elif qtype == "true_false":
            truth = bool(ans) if not isinstance(ans, bool) else ans
            q.options = [
                QuestionOption(text="True", is_correct=truth is True, position=0),
                QuestionOption(text="False", is_correct=truth is False, position=1),
            ]
        elif isinstance(opts, list) and opts:
            right = set(ans if isinstance(ans, list) else [ans]) if ans is not None else set()
            q.options = [QuestionOption(text=str(t)[:400], is_correct=i in right, position=i)
                         for i, t in enumerate(opts[:6])]

        db.session.add(q)
        db.session.flush()
        generated_ids.append(q.id)

    if not generated_ids:
        raise ApiError("ai_error", "AI did not produce any usable questions.", 502)

    attempt = svc.start_attempt_with_ids(current_user.id, assessment, difficulty, generated_ids)
    return ok({"attempt_id": attempt.id, "num_questions": len(generated_ids), "ai_generated": True}, 201)
