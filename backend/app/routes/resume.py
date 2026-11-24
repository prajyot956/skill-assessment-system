import hashlib
import logging
import secrets
from pathlib import Path

from flask import Blueprint, current_app, request
from flask_login import current_user

from app.ai.provider import AIUnavailable, ai_enabled
from app.ai import resume_ai
from app.extensions import db, limiter
from app.models import Notification, Resume, Skill, SkillEvidence, UserSkill
from app.models.base import utcnow
from app.routes.skills import resolve_or_create_skill
from app.services import profile_diff, profile_items
from app.services.resume_parser import build_analysis, parse_resume
from app.services.resume_text import ALLOWED, validate_and_extract
from app.utils.decorators import get_json_body, login_required_api
from app.utils.responses import ApiError, ValidationError, ok
from app.utils.validators import PHONE_RE, URL_RE, clean_str

bp = Blueprint("resume", __name__, url_prefix="/api/resumes")
log = logging.getLogger(__name__)


def resume_dict(r: Resume) -> dict:
    return {"id": r.id, "filename": r.original_filename, "size": r.file_size, "status": r.status,
            "parse_method": r.parse_method, "error": r.error_message, "uploaded_at": r.uploaded_at.isoformat(),
            "confirmed_at": r.confirmed_at.isoformat() if r.confirmed_at else None, "has_draft": bool(r.parsed_json)}


def _owned(resume_id: int) -> Resume:
    r = Resume.query.filter_by(id=resume_id, user_id=current_user.id).first()
    if not r:
        raise ApiError("not_found", "Resume not found.", 404)
    return r


def _file_path(r: Resume) -> Path:
    return Path(current_app.config["UPLOAD_DIR"]) / str(r.user_id) / r.stored_filename


def _remove_file(r: Resume):
    try:
        _file_path(r).unlink(missing_ok=True)
    except OSError:
        log.warning("Could not delete resume file %s", r.stored_filename)


def _taxonomy():
    return [{"name": s.name, "category": s.category, "aliases": list(s.aliases or [])}
            for s in Skill.query.filter_by(is_active=True)]


@bp.get("/current")
@login_required_api
def current():
    r = Resume.query.filter_by(user_id=current_user.id, is_current=True).order_by(Resume.uploaded_at.desc()).first()
    return ok({"resume": resume_dict(r) if r else None, "ai_enabled": ai_enabled()})


@bp.post("")
@login_required_api
@limiter.limit("10 per hour")
def upload():
    f = request.files.get("file")
    if f is None or not f.filename:
        raise ApiError("no_file", "Choose a file to upload.", 400)
    data = f.read(current_app.config["MAX_CONTENT_LENGTH"] + 1)
    if len(data) > current_app.config["MAX_CONTENT_LENGTH"]:
        raise ApiError("file_too_large", "File is too large.", 413)
    ext, text = validate_and_extract(data, f.filename)  # raises before anything is stored

    old = Resume.query.filter_by(user_id=current_user.id).all()
    stored = secrets.token_hex(16) + ext  # server-generated name; the client's name is never used on disk
    folder = Path(current_app.config["UPLOAD_DIR"]) / str(current_user.id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / stored).write_bytes(data)
    resume = Resume(user_id=current_user.id, original_filename=Path(f.filename).name[:255], stored_filename=stored,
                    file_size=len(data), mime_type=ALLOWED[ext], sha256=hashlib.sha256(data).hexdigest(),
                    status="processing", raw_text=text)
    db.session.add(resume)
    db.session.flush()
    for o in old:  # replacing: confirmed profile data is untouched (FKs are SET NULL)
        _remove_file(o)
        db.session.delete(o)
    db.session.commit()

    taxonomy = _taxonomy()
    try:
        local = parse_resume(text, taxonomy)
        draft, method = local, "local"
        if ai_enabled():
            try:
                ai = resume_ai.fill_gaps_locally(resume_ai.extract_with_ai(text, taxonomy), local)
                ai["analysis"] = build_analysis(ai)
                draft, method = ai, "ai"
            except AIUnavailable as e:
                log.info("AI extraction unavailable, using local parser: %s", e)
        resume.parsed_json, resume.parse_method, resume.status = draft, method, "parsed"
    except Exception:
        log.exception("Resume parsing failed")
        resume.status, resume.error_message = "failed", "We couldn't analyse this resume. Try another copy or add details manually."
    db.session.commit()
    return ok(resume_dict(resume), 201)


@bp.get("/<int:resume_id>/review")
@login_required_api
def review(resume_id):
    r = _owned(resume_id)
    if not r.parsed_json:
        raise ApiError("not_ready", "This resume has no analysis yet.", 409)
    draft = r.parsed_json
    return ok({"resume": resume_dict(r), "draft": draft, "diff": profile_diff.build_diff(current_user, draft),
               "has_profile_data": bool(current_user.profile.summary or UserSkill.query.filter_by(user_id=current_user.id).first())})


@bp.delete("/<int:resume_id>")
@login_required_api
def delete(resume_id):
    r = _owned(resume_id)
    _remove_file(r)
    db.session.delete(r)
    db.session.commit()
    return ok({"deleted": True})


PROFILE_FIELDS = {"phone": (30, "phone"), "location": (120, None), "summary": (2000, None),
                  "linkedin_url": (300, "url"), "github_url": (300, "url"), "portfolio_url": (300, "url")}


@bp.post("/<int:resume_id>/confirm")
@login_required_api
def confirm(resume_id):
    """Applies ONLY what the user approved. Requires explicit confirm=true; nothing else touches the profile."""
    r = _owned(resume_id)
    if not r.parsed_json:
        raise ApiError("not_ready", "This resume has no analysis yet.", 409)
    data = get_json_body()
    if data.get("confirm") is not True:
        raise ApiError("confirmation_required", "Confirm the update before saving.", 400)
    errors, profile = {}, current_user.profile
    draft_skills = {s["name"].lower(): s for s in r.parsed_json.get("skills", [])}

    # validate everything first, then write, so a mistake never leaves a half-applied update
    prof_changes = {}
    for k, v in (data.get("profile") or {}).items():
        if k not in PROFILE_FIELDS:
            continue
        limit, kind = PROFILE_FIELDS[k]
        try:
            s = clean_str(v, limit, field=k)
            if s and kind == "url" and not URL_RE.match(s): raise ValueError("Enter a full link starting with http:// or https://.")
            if s and kind == "phone" and not PHONE_RE.match(s): raise ValueError("Enter a valid phone number.")
            prof_changes[k] = s
        except ValueError as e:
            errors[f"profile.{k}"] = str(e)

    plan = {}
    for section in profile_items.SPECS:
        spec = data.get(section) or {}
        adds, updates = spec.get("add") or [], spec.get("update") or []
        if not isinstance(adds, list) or not isinstance(updates, list):
            raise ApiError("invalid_json", f"'{section}' must contain lists.", 400)
        plan[section] = {"add": [], "update": []}
        for i, item in enumerate(adds):
            try: plan[section]["add"].append(profile_items.clean_item(section, item))
            except ValidationError as e:
                for f, m in e.details["fields"].items(): errors[f"{section}.add.{i}.{f}"] = m
        for i, item in enumerate(updates):
            try: plan[section]["update"].append((item.get("id"), profile_items.clean_item(section, item, partial=True)))
            except ValidationError as e:
                for f, m in e.details["fields"].items(): errors[f"{section}.update.{i}.{f}"] = m
    skills_in = data.get("skills") or []
    if not isinstance(skills_in, list) or len(skills_in) > 200:
        raise ApiError("invalid_json", "'skills' must be a list of up to 200 items.", 400)
    if errors:
        raise ValidationError(errors)

    counts = {"profile_fields": len(prof_changes), "skills": 0}
    for k, v in prof_changes.items():
        setattr(profile, k, v)
    for section, ops in plan.items():
        counts[section] = 0
        for clean in ops["add"]:
            model, _ = profile_items.SPECS[section]
            row = model(user_id=current_user.id, source_resume_id=r.id, **clean)
            if section == "projects" and row.technologies is None: row.technologies = []
            db.session.add(row); counts[section] += 1
        for item_id, clean in ops["update"]:
            row = profile_items.update_item(current_user.id, section, item_id, clean) if isinstance(item_id, int) else None
            if row is None:
                raise ApiError("not_found", f"A {section} item to update was not found.", 404)
            counts[section] += 1

    for item in skills_in:
        if not isinstance(item, dict):
            continue
        skill = resolve_or_create_skill(item.get("name"), item.get("category"))
        us = UserSkill.query.filter_by(user_id=current_user.id, skill_id=skill.id).first()
        in_draft = draft_skills.get(skill.name.lower())
        if us is None:
            us = UserSkill(user_id=current_user.id, skill_id=skill.id, source="resume" if in_draft else "manual")
            db.session.add(us); db.session.flush()
        us.status = "user_confirmed"  # the user's explicit approval; proficiency stays untouched
        if in_draft:
            have = {(e.source_section, e.snippet) for e in us.evidence}
            for ev in in_draft["evidence"]:
                if (ev["section"], ev["snippet"]) not in have:
                    db.session.add(SkillEvidence(user_skill_id=us.id, resume_id=r.id, source_section=ev["section"],
                                                 snippet=ev["snippet"], confidence=in_draft["confidence"], inferred=in_draft["inferred"]))
        counts["skills"] += 1

    r.status, r.confirmed_at = "confirmed", utcnow()
    db.session.add(Notification(user_id=current_user.id, kind="profile", title="Profile updated from your resume",
                                message=f"{counts['skills']} skills and your approved details were saved.", link="/profile"))
    db.session.commit()
    return ok({"applied": counts, "resume": resume_dict(r)})
