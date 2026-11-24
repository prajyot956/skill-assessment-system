import re

from flask import Blueprint
from flask_login import current_user

from app.extensions import db
from app.models import SKILL_CATEGORIES, Skill, SkillEvidence, UserSkill
from app.services.seed_service import slugify
from app.utils.decorators import get_json_body, login_required_api
from app.utils.responses import ApiError, ValidationError, ok

bp = Blueprint("skills", __name__, url_prefix="/api/skills")


def user_skill_dict(us: UserSkill) -> dict:
    return {"id": us.id, "skill_id": us.skill_id, "name": us.skill.name, "category": us.skill.category,
            "status": us.status, "source": us.source, "evidence_level": us.evidence_level,
            "proficiency_pct": round(us.proficiency_pct, 1) if us.proficiency_pct is not None else None,
            "last_assessed_at": us.last_assessed_at.isoformat() if us.last_assessed_at else None,
            "evidence": [{"section": e.source_section, "snippet": e.snippet, "confidence": e.confidence, "inferred": e.inferred}
                         for e in us.evidence]}


def resolve_or_create_skill(name: str, category: str | None) -> Skill:
    name = re.sub(r"\s+", " ", (name or "").strip())
    if not name or len(name) > 100:
        raise ValidationError({"name": "Enter a skill name (up to 100 characters)."})
    skill = Skill.query.filter(db.func.lower(Skill.name) == name.lower()).first()
    if skill:
        if not skill.is_active:
            raise ValidationError({"name": "This skill is not available."})
        return skill
    if category not in SKILL_CATEGORIES:
        raise ValidationError({"category": "Choose a category for this new skill."})
    skill = Skill(name=name, slug=slugify(name), category=category, aliases=[])
    if Skill.query.filter_by(slug=skill.slug).first():
        raise ValidationError({"name": "A similar skill already exists."})
    db.session.add(skill)
    db.session.flush()
    return skill


@bp.get("")
@login_required_api
def taxonomy():
    rows = Skill.query.filter_by(is_active=True).order_by(Skill.category, Skill.name).all()
    return ok({"skills": [{"id": s.id, "name": s.name, "category": s.category} for s in rows], "categories": SKILL_CATEGORIES})


@bp.get("/mine")
@login_required_api
def mine():
    rows = UserSkill.query.filter_by(user_id=current_user.id).join(Skill).order_by(Skill.category, Skill.name).all()
    return ok([user_skill_dict(r) for r in rows])


@bp.post("/mine")
@login_required_api
def add_mine():
    data = get_json_body()
    skill = resolve_or_create_skill(data.get("name"), data.get("category"))
    us = UserSkill.query.filter_by(user_id=current_user.id, skill_id=skill.id).first()
    if us:
        us.status = "user_confirmed"
    else:
        us = UserSkill(user_id=current_user.id, skill_id=skill.id, status="user_confirmed", source="manual")
        db.session.add(us)
    db.session.commit()
    return ok(user_skill_dict(us), 201)


@bp.delete("/mine/<int:us_id>")
@login_required_api
def delete_mine(us_id):
    us = UserSkill.query.filter_by(id=us_id, user_id=current_user.id).first()
    if not us:
        raise ApiError("not_found", "Skill not found.", 404)
    db.session.delete(us)  # evidence cascades; assessment history is kept
    db.session.commit()
    return ok({"deleted": True})
