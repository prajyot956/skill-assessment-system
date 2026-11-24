"""Admin API. Every route is behind @admin_required, enforced server-side."""
from flask import Blueprint, request
from flask_login import current_user

from app.extensions import db
from app.models import (Assessment, AssessmentAttempt, AssessmentCategory, CareerRole, InterviewQuestion,
                        LearningResource, PracticeProject, Question, QuestionOption, Resume, RoleSkill,
                        SKILL_CATEGORIES, Skill, User, UserSkill)
from app.services.assessment_service import DIFFICULTIES
from app.services.seed_service import slugify
from app.seeds.questions import MARKS
from app.utils.decorators import admin_required, get_json_body
from app.utils.responses import ApiError, ValidationError, ok
from app.utils.validators import URL_RE, clean_str

bp = Blueprint("admin", __name__, url_prefix="/api/admin")
bp.before_request(admin_required(lambda: None))  # gate every route in this blueprint, including ones added later


def _paging():
    return max(request.args.get("page", 1, type=int), 1), min(max(request.args.get("per_page", 25, type=int), 1), 100)


def _get(model, id_, label):
    row = db.session.get(model, id_)
    if row is None:
        raise ApiError("not_found", f"{label} not found.", 404)
    return row


def _str(data, field, n, label, required=True):
    try:
        return clean_str(data.get(field), n, required=required, field=label)
    except ValueError as e:
        raise ValidationError({field: str(e)})


# ---- overview and users -------------------------------------------------------------------------
@bp.get("/stats")
def stats():
    return ok({"users": User.query.count(), "admins": User.query.filter_by(is_admin=True).count(),
               "active_users": User.query.filter_by(is_active_account=True).count(),
               "resumes": Resume.query.count(), "attempts": AssessmentAttempt.query.count(),
               "completed_attempts": AssessmentAttempt.query.filter(AssessmentAttempt.status != "in_progress").count(),
               "questions": Question.query.filter_by(is_active=True).count(), "skills": Skill.query.filter_by(is_active=True).count(),
               "roles": CareerRole.query.filter_by(is_active=True).count(),
               "projects": PracticeProject.query.filter_by(is_active=True).count(),
               "interview_questions": InterviewQuestion.query.filter_by(is_active=True).count(),
               "questions_by_skill": [{"skill": s, "count": n} for s, n in
                                      db.session.query(Skill.name, db.func.count(Question.id)).join(Question).filter(Question.is_active.is_(True))
                                      .group_by(Skill.name).order_by(db.func.count(Question.id).desc()).all()]})


@bp.get("/users")
def users():
    page, per = _paging()
    q = User.query
    term = (request.args.get("q") or "").strip().lower()
    if term:
        q = q.filter(db.or_(User.email.contains(term), db.func.lower(User.full_name).contains(term)))
    total = q.count()
    rows = q.order_by(User.created_at.desc()).offset((page - 1) * per).limit(per).all()
    return ok([{"id": u.id, "full_name": u.full_name, "email": u.email, "is_admin": u.is_admin, "is_active": u.is_active_account,
                "created_at": u.created_at.isoformat() + "Z", "last_login_at": u.last_login_at.isoformat() + "Z" if u.last_login_at else None,
                "skills": UserSkill.query.filter_by(user_id=u.id).count(),
                "attempts": AssessmentAttempt.query.filter_by(user_id=u.id).count()} for u in rows],
              meta={"page": page, "per_page": per, "total": total})


@bp.patch("/users/<int:uid>")
def patch_user(uid):
    u = _get(User, uid, "User")
    data = get_json_body()
    if u.id == current_user.id and (data.get("is_active") is False or data.get("is_admin") is False):
        raise ApiError("forbidden", "You can't deactivate or demote your own account.", 400)
    for f, col in (("is_active", "is_active_account"), ("is_admin", "is_admin")):
        if f in data:
            if not isinstance(data[f], bool):
                raise ValidationError({f: "Must be true or false."})
            setattr(u, col, data[f])
    db.session.commit()
    return ok({"id": u.id, "is_active": u.is_active_account, "is_admin": u.is_admin})


# ---- categories, skills, assessments --------------------------------------------------------------
@bp.get("/catalog")
def catalog():
    return ok({"categories": [{"id": c.id, "name": c.name, "description": c.description, "is_active": c.is_active} for c in AssessmentCategory.query.order_by(AssessmentCategory.position)],
               "skills": [{"id": s.id, "name": s.name, "slug": s.slug, "category": s.category,
                           "aliases": s.aliases, "is_active": s.is_active} for s in Skill.query.order_by(Skill.name)],
               "assessments": [{"id": a.id, "title": a.title, "skill_id": a.skill_id, "skill": a.skill.name, "category_id": a.category_id, "is_active": a.is_active,
                                "questions": Question.query.filter_by(skill_id=a.skill_id, is_active=True).count()} for a in Assessment.query.order_by(Assessment.title)],
               "skill_categories": SKILL_CATEGORIES, "difficulties": DIFFICULTIES})


@bp.post("/categories")
def add_category():
    d = get_json_body()
    name = _str(d, "name", 100, "Name")
    if AssessmentCategory.query.filter(db.func.lower(AssessmentCategory.name) == name.lower()).first():
        raise ValidationError({"name": "A category with this name exists."})
    c = AssessmentCategory(name=name, slug=slugify(name), description=_str(d, "description", 300, "Description", False),
                           position=AssessmentCategory.query.count())
    db.session.add(c); db.session.commit()
    return ok({"id": c.id}, 201)


@bp.put("/categories/<int:cid>")
def edit_category(cid):
    c, d = _get(AssessmentCategory, cid, "Category"), get_json_body()
    if "name" in d: c.name = _str(d, "name", 100, "Name")
    if "description" in d: c.description = _str(d, "description", 300, "Description", False)
    if isinstance(d.get("is_active"), bool): c.is_active = d["is_active"]
    db.session.commit()
    return ok({"id": c.id})


@bp.post("/skills")
def add_skill():
    d = get_json_body()
    name = _str(d, "name", 100, "Name")
    if d.get("category") not in SKILL_CATEGORIES:
        raise ValidationError({"category": "Choose a category."})
    if Skill.query.filter(db.func.lower(Skill.name) == name.lower()).first() or Skill.query.filter_by(slug=slugify(name)).first():
        raise ValidationError({"name": "This skill already exists."})
    aliases = d.get("aliases", [])
    if not isinstance(aliases, list) or any(not isinstance(a, str) for a in aliases):
        raise ValidationError({"aliases": "Aliases must be a list of text."})
    s = Skill(name=name, slug=slugify(name), category=d["category"], aliases=[a.strip() for a in aliases if a.strip()][:20])
    db.session.add(s); db.session.commit()
    return ok({"id": s.id}, 201)


@bp.put("/skills/<int:sid>")
def edit_skill(sid):
    s, d = _get(Skill, sid, "Skill"), get_json_body()
    if "category" in d:
        if d["category"] not in SKILL_CATEGORIES: raise ValidationError({"category": "Choose a category."})
        s.category = d["category"]
    if isinstance(d.get("aliases"), list): s.aliases = [str(a).strip() for a in d["aliases"] if str(a).strip()][:20]
    if isinstance(d.get("is_active"), bool): s.is_active = d["is_active"]   # skills are deactivated, never deleted: user data points at them
    db.session.commit()
    return ok({"id": s.id})


@bp.post("/assessments")
def add_assessment():
    d = get_json_body()
    cat, skill = _get(AssessmentCategory, d.get("category_id"), "Category"), _get(Skill, d.get("skill_id"), "Skill")
    if Assessment.query.filter_by(skill_id=skill.id).first():
        raise ValidationError({"skill_id": "This skill already has an assessment."})
    a = Assessment(category_id=cat.id, skill_id=skill.id, title=_str(d, "title", 150, "Title"), description=_str(d, "description", 300, "Description", False))
    db.session.add(a); db.session.commit()
    return ok({"id": a.id}, 201)


@bp.put("/assessments/<int:aid>")
def edit_assessment(aid):
    a, d = _get(Assessment, aid, "Assessment"), get_json_body()
    if "title" in d: a.title = _str(d, "title", 150, "Title")
    if "category_id" in d: a.category_id = _get(AssessmentCategory, d["category_id"], "Category").id
    if isinstance(d.get("is_active"), bool): a.is_active = d["is_active"]
    db.session.commit()
    return ok({"id": a.id})


# ---- questions ------------------------------------------------------------------------------------
def _question_dict(q):
    d = {"id": q.id, "skill_id": q.skill_id, "skill": q.skill.name, "topic": q.topic, "difficulty": q.difficulty, "type": q.qtype, "text": q.text,
         "explanation": q.explanation, "marks": q.marks, "is_active": q.is_active, "accepted_answers": q.accepted_answers}
    d["options"] = [{"text": o.text, "is_correct": o.is_correct} for o in q.options]
    return d


def _apply_question(q: Question, d: dict):
    errors = {}
    skill = db.session.get(Skill, d.get("skill_id")) if isinstance(d.get("skill_id"), int) else None
    if not skill: errors["skill_id"] = "Choose a skill."
    if d.get("difficulty") not in DIFFICULTIES: errors["difficulty"] = "Choose a difficulty."
    qtype = d.get("type")
    if qtype not in ("single", "multiple", "true_false", "short"): errors["type"] = "Choose a question type."
    for f, n, label in (("topic", 100, "Topic"), ("text", 2000, "Question text")):
        try: clean_str(d.get(f), n, required=True, field=label)
        except ValueError as e: errors[f] = str(e)
    marks = d.get("marks", MARKS.get(d.get("difficulty"), 1))
    if isinstance(marks, bool) or not isinstance(marks, (int, float)) or not 0 < marks <= 10: errors["marks"] = "Marks must be between 0 and 10."
    options, accepted = [], None
    if qtype == "true_false":
        if not isinstance(d.get("correct"), bool): errors["correct"] = "Say whether the statement is true or false."
        else: options = [("True", d["correct"]), ("False", not d["correct"])]
    elif qtype in ("single", "multiple"):
        raw = d.get("options")
        if not isinstance(raw, list) or not 2 <= len(raw) <= 8 or any(not isinstance(o, dict) or not str(o.get("text", "")).strip() for o in raw):
            errors["options"] = "Provide 2 to 8 options with text."
        else:
            options = [(str(o["text"]).strip()[:500], bool(o.get("is_correct"))) for o in raw]
            right = sum(1 for _, c in options if c)
            if qtype == "single" and right != 1: errors["options"] = "Mark exactly one option as correct."
            if qtype == "multiple" and right < 1: errors["options"] = "Mark at least one option as correct."
    elif qtype == "short":
        a = d.get("accepted_answers")
        if not isinstance(a, list) or not [x for x in a if isinstance(x, str) and x.strip()]: errors["accepted_answers"] = "Provide at least one accepted answer."
        else: accepted = [x.strip() for x in a if isinstance(x, str) and x.strip()][:20]
    if errors:
        raise ValidationError(errors)
    q.skill_id, q.difficulty, q.qtype, q.marks = skill.id, d["difficulty"], qtype, float(marks)
    q.topic, q.text = d["topic"].strip(), d["text"].strip()
    q.explanation = _str(d, "explanation", 2000, "Explanation", False)
    q.accepted_answers = accepted
    if isinstance(d.get("is_active"), bool): q.is_active = d["is_active"]
    q.options = [QuestionOption(text=t, is_correct=c, position=i) for i, (t, c) in enumerate(options)]


@bp.get("/questions")
def list_questions():
    page, per = _paging()
    q = Question.query
    if request.args.get("skill_id", type=int): q = q.filter_by(skill_id=request.args.get("skill_id", type=int))
    if request.args.get("difficulty") in DIFFICULTIES: q = q.filter_by(difficulty=request.args["difficulty"])
    if request.args.get("active") in ("0", "1"): q = q.filter_by(is_active=request.args["active"] == "1")
    term = (request.args.get("q") or "").strip()
    if term: q = q.filter(Question.text.contains(term))
    total = q.count()
    rows = q.order_by(Question.id.desc()).offset((page - 1) * per).limit(per).all()
    return ok([_question_dict(x) for x in rows], meta={"page": page, "per_page": per, "total": total})


@bp.post("/questions")
def add_question():
    q = Question()
    _apply_question(q, get_json_body())
    db.session.add(q); db.session.commit()
    return ok(_question_dict(q), 201)


@bp.put("/questions/<int:qid>")
def edit_question(qid):
    q = _get(Question, qid, "Question")
    _apply_question(q, get_json_body())
    db.session.commit()
    return ok(_question_dict(q))


@bp.delete("/questions/<int:qid>")
def retire_question(qid):
    """Soft delete: past attempts reference the question, so it is deactivated instead of removed."""
    q = _get(Question, qid, "Question")
    q.is_active = False
    db.session.commit()
    return ok({"id": q.id, "is_active": False})


# ---- career roles ---------------------------------------------------------------------------------
def _role_dict(r):
    return {"id": r.id, "name": r.name, "description": r.description, "interest_tags": r.interest_tags, "education_keywords": r.education_keywords,
            "is_active": r.is_active, "skills": [{"skill_id": s.skill_id, "skill": s.skill.name, "weight": s.weight, "min_level_pct": s.min_level_pct, "is_core": s.is_core}
                                                 for s in sorted(r.skills, key=lambda x: -x.weight)]}


def _tags(d, field):
    v = d.get(field, [])
    if not isinstance(v, list) or any(not isinstance(x, str) for x in v):
        raise ValidationError({field: "Provide a list of text values."})
    return [x.strip().lower() for x in v if x.strip()][:20]


@bp.get("/roles")
def list_roles():
    return ok([_role_dict(r) for r in CareerRole.query.order_by(CareerRole.name)])


@bp.post("/roles")
def add_role():
    d = get_json_body()
    name = _str(d, "name", 120, "Name")
    if CareerRole.query.filter(db.func.lower(CareerRole.name) == name.lower()).first():
        raise ValidationError({"name": "A role with this name exists."})
    r = CareerRole(name=name, slug=slugify(name), description=_str(d, "description", 2000, "Description", False),
                   interest_tags=_tags(d, "interest_tags"), education_keywords=_tags(d, "education_keywords"))
    db.session.add(r); db.session.commit()
    return ok(_role_dict(r), 201)


@bp.put("/roles/<int:rid>")
def edit_role(rid):
    r, d = _get(CareerRole, rid, "Role"), get_json_body()
    if "name" in d: r.name = _str(d, "name", 120, "Name")
    if "description" in d: r.description = _str(d, "description", 2000, "Description", False)
    if "interest_tags" in d: r.interest_tags = _tags(d, "interest_tags")
    if "education_keywords" in d: r.education_keywords = _tags(d, "education_keywords")
    if isinstance(d.get("is_active"), bool): r.is_active = d["is_active"]
    db.session.commit()
    return ok(_role_dict(r))


@bp.put("/roles/<int:rid>/skills")
def set_role_skills(rid):
    r, rows = _get(CareerRole, rid, "Role"), get_json_body().get("skills")
    if not isinstance(rows, list) or not rows or len(rows) > 40:
        raise ValidationError({"skills": "Provide between 1 and 40 required skills."})
    seen, built = set(), []
    for i, row in enumerate(rows):
        if not isinstance(row, dict) or not isinstance(row.get("skill_id"), int) or not db.session.get(Skill, row["skill_id"]):
            raise ValidationError({f"skills.{i}.skill_id": "Choose a valid skill."})
        if row["skill_id"] in seen: raise ValidationError({f"skills.{i}.skill_id": "Each skill can appear once."})
        seen.add(row["skill_id"])
        w, m = row.get("weight", 1), row.get("min_level_pct", 60)
        if isinstance(w, bool) or not isinstance(w, (int, float)) or not 0 < w <= 5: raise ValidationError({f"skills.{i}.weight": "Weight must be between 0 and 5."})
        if isinstance(m, bool) or not isinstance(m, (int, float)) or not 1 <= m <= 100: raise ValidationError({f"skills.{i}.min_level_pct": "Level must be between 1 and 100."})
        built.append(RoleSkill(skill_id=row["skill_id"], weight=float(w), min_level_pct=float(m), is_core=bool(row.get("is_core", True))))
    r.skills = []
    db.session.flush()      # delete the old rows first, or re-using a skill hits the unique constraint
    r.skills = built
    db.session.commit()
    return ok(_role_dict(r))


# ---- learning resources ----------------------------------------------------------------------------
def _res(r): return {"id": r.id, "skill_id": r.skill_id, "skill": r.skill.name, "title": r.title, "url": r.url, "kind": r.kind, "level": r.level, "is_active": r.is_active}


def _apply_resource(r, d):
    skill = db.session.get(Skill, d.get("skill_id")) if isinstance(d.get("skill_id"), int) else None
    if not skill: raise ValidationError({"skill_id": "Choose a skill."})
    url = _str(d, "url", 400, "Link", False)
    if url and not URL_RE.match(url): raise ValidationError({"url": "Enter a full link starting with http:// or https://."})
    if d.get("kind", "article") not in ("article", "video", "course", "docs", "book"): raise ValidationError({"kind": "Choose a resource type."})
    if d.get("level", "beginner") not in DIFFICULTIES: raise ValidationError({"level": "Choose a level."})
    r.skill_id, r.title, r.url = skill.id, _str(d, "title", 200, "Title"), url
    r.kind, r.level = d.get("kind", "article"), d.get("level", "beginner")
    if isinstance(d.get("is_active"), bool): r.is_active = d["is_active"]


@bp.get("/resources")
def list_resources():
    return ok([_res(r) for r in LearningResource.query.order_by(LearningResource.skill_id, LearningResource.id)])


@bp.post("/resources")
def add_resource():
    r = LearningResource(); _apply_resource(r, get_json_body())
    db.session.add(r); db.session.commit()
    return ok(_res(r), 201)


@bp.put("/resources/<int:rid>")
def edit_resource(rid):
    r = _get(LearningResource, rid, "Resource"); _apply_resource(r, get_json_body())
    db.session.commit()
    return ok(_res(r))


@bp.delete("/resources/<int:rid>")
def delete_resource(rid):
    r = _get(LearningResource, rid, "Resource")
    db.session.delete(r); db.session.commit()   # roadmap items keep their text; resource link is set to NULL by the FK
    return ok({"deleted": True})


# ---- practice projects and interview bank -------------------------------------------------------
def _string_list(data, field, label, max_items, max_length, required=True):
    rows = data.get(field)
    if rows is None and not required:
        return []
    if not isinstance(rows, list) or len(rows) > max_items or (required and not rows):
        requirement = f"Provide between 1 and {max_items} {label.lower()}." if required else f"Provide at most {max_items} {label.lower()}."
        raise ValidationError({field: requirement})
    values, seen = [], set()
    for i, row in enumerate(rows):
        try:
            value = clean_str(row, max_length, required=True, field=label)
        except ValueError as exc:
            raise ValidationError({f"{field}.{i}": str(exc)})
        if value not in seen:
            seen.add(value)
            values.append(value)
    if required and not values:
        raise ValidationError({field: f"Provide at least one {label.lower()}."})
    return values


def _project_dict(project):
    skill_names = {s.slug: s.name for s in Skill.query.filter(Skill.slug.in_(project.skill_slugs or [])).all()}
    return {"id": project.id, "title": project.title, "description": project.description,
            "difficulty": project.difficulty, "skill_slugs": project.skill_slugs,
            "skills": [skill_names[slug] for slug in project.skill_slugs if slug in skill_names],
            "objectives": project.objectives, "steps": project.steps,
            "expected_outcome": project.expected_outcome, "is_active": project.is_active}


def _apply_project(project, data):
    title = _str(data, "title", 200, "Title")
    description = _str(data, "description", 2000, "Description")
    if data.get("difficulty") not in DIFFICULTIES:
        raise ValidationError({"difficulty": "Choose a difficulty."})
    slugs = _string_list(data, "skill_slugs", "Skills", 20, 100)
    known = {s.slug for s in Skill.query.filter(Skill.slug.in_(slugs)).all()}
    if known != set(slugs):
        raise ValidationError({"skill_slugs": "Choose existing skills."})
    objectives = _string_list(data, "objectives", "Objectives", 12, 300)
    steps = _string_list(data, "steps", "Steps", 16, 500)
    expected = _str(data, "expected_outcome", 2000, "Expected outcome", False)
    if "is_active" in data and not isinstance(data["is_active"], bool):
        raise ValidationError({"is_active": "Must be true or false."})
    project.title, project.description, project.difficulty = title, description, data["difficulty"]
    project.skill_slugs, project.objectives, project.steps = slugs, objectives, steps
    project.expected_outcome = expected
    if "is_active" in data:
        project.is_active = data["is_active"]


@bp.get("/projects")
def list_projects():
    rows = PracticeProject.query.order_by(PracticeProject.title, PracticeProject.id).all()
    return ok([_project_dict(project) for project in rows])


@bp.post("/projects")
def add_project():
    project = PracticeProject()
    _apply_project(project, get_json_body())
    db.session.add(project)
    db.session.commit()
    return ok(_project_dict(project), 201)


@bp.put("/projects/<int:pid>")
def edit_project(pid):
    project, data = _get(PracticeProject, pid, "Project"), get_json_body()
    merged = {"title": project.title, "description": project.description, "difficulty": project.difficulty,
              "skill_slugs": project.skill_slugs, "objectives": project.objectives, "steps": project.steps,
              "expected_outcome": project.expected_outcome, "is_active": project.is_active}
    merged.update(data)
    _apply_project(project, merged)
    db.session.commit()
    return ok(_project_dict(project))


def _interview_question_dict(question):
    return {"id": question.id, "skill_id": question.skill_id,
            "skill": question.skill.name if question.skill_id else "Behavioural",
            "difficulty": question.difficulty, "text": question.text, "keywords": question.keywords,
            "is_active": question.is_active}


def _apply_interview_question(question, data):
    skill_id = data.get("skill_id")
    if skill_id is not None and (isinstance(skill_id, bool) or not isinstance(skill_id, int) or not db.session.get(Skill, skill_id)):
        raise ValidationError({"skill_id": "Choose a valid skill or Behavioural."})
    if data.get("difficulty") not in DIFFICULTIES:
        raise ValidationError({"difficulty": "Choose a difficulty."})
    text = _str(data, "text", 1000, "Question")
    keywords = _string_list(data, "keywords", "Keywords", 20, 100)
    if "is_active" in data and not isinstance(data["is_active"], bool):
        raise ValidationError({"is_active": "Must be true or false."})
    question.skill_id, question.difficulty = skill_id, data["difficulty"]
    question.text, question.keywords = text, keywords
    if "is_active" in data:
        question.is_active = data["is_active"]


@bp.get("/interview-questions")
def list_interview_questions():
    rows = InterviewQuestion.query.order_by(InterviewQuestion.skill_id, InterviewQuestion.difficulty,
                                            InterviewQuestion.id).all()
    return ok([_interview_question_dict(question) for question in rows])


@bp.post("/interview-questions")
def add_interview_question():
    question = InterviewQuestion()
    _apply_interview_question(question, get_json_body())
    db.session.add(question)
    db.session.commit()
    return ok(_interview_question_dict(question), 201)


@bp.put("/interview-questions/<int:qid>")
def edit_interview_question(qid):
    question, data = _get(InterviewQuestion, qid, "Interview question"), get_json_body()
    merged = {"skill_id": question.skill_id, "difficulty": question.difficulty, "text": question.text,
              "keywords": question.keywords, "is_active": question.is_active}
    merged.update(data)
    _apply_interview_question(question, merged)
    db.session.commit()
    return ok(_interview_question_dict(question))
