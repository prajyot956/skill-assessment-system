from flask import Blueprint, request
from flask_login import current_user

from app.ai import features
from app.ai.provider import AIUnavailable, ai_enabled
from app.extensions import db, limiter
from app.models import CareerRole, LearningRoadmap, RoadmapItem, UserProjectStatus, PracticeProject
from app.services import roadmap_service
from app.utils.decorators import get_json_body, login_required_api
from app.utils.responses import ApiError, ValidationError, ok

bp = Blueprint("learning", __name__, url_prefix="/api")
STATUSES = ("pending", "in_progress", "completed")


@bp.get("/roadmap")
@login_required_api
def get_roadmap():
    road = LearningRoadmap.query.filter_by(user_id=current_user.id, status="active").first()
    return ok({"roadmap": roadmap_service.serialize(current_user, road) if road else None,
               "target_role_id": current_user.profile.target_role_id, "ai_enabled": ai_enabled()})


@bp.post("/roadmap/generate")
@login_required_api
def generate():
    data = request.get_json(silent=True) or {}
    rid = data.get("role_id") or current_user.profile.target_role_id
    role = db.session.get(CareerRole, rid) if isinstance(rid, int) else None
    if role is None or not role.is_active:
        raise ApiError("no_target", "Choose a target career first.", 409)
    current_user.profile.target_role_id = role.id
    road = roadmap_service.generate(current_user, role)
    return ok(roadmap_service.serialize(current_user, road), 201)


@bp.patch("/roadmap/items/<int:item_id>")
@login_required_api
def update_item(item_id):
    item = (RoadmapItem.query.join(LearningRoadmap).filter(RoadmapItem.id == item_id, LearningRoadmap.user_id == current_user.id).first())
    if not item:
        raise ApiError("not_found", "Roadmap item not found.", 404)
    status = get_json_body().get("status")
    if status not in STATUSES:
        raise ValidationError({"status": "Choose pending, in_progress or completed."})
    roadmap_service.set_status(item, status)
    db.session.commit()
    return ok(roadmap_service.serialize(current_user, item.roadmap))


@bp.post("/roadmap/suggest-resources")
@login_required_api
@limiter.limit("10 per hour")
def suggest_resources():
    data = get_json_body()
    skill = str(data.get("skill") or "")[:100]
    if not skill:
        raise ValidationError({"skill": "Choose a skill."})
    try:
        return ok({"suggestions": features.suggest_resources(skill, str(data.get("level") or "beginner")[:20]), "source": "ai"})
    except AIUnavailable:
        raise ApiError("ai_unavailable", "AI suggestions aren't available right now. The curated resources in your roadmap are still valid.", 503)


@bp.get("/practice/projects")
@login_required_api
def projects():
    return ok(roadmap_service.recommend_projects(current_user))


@bp.put("/practice/projects/<int:project_id>/status")
@login_required_api
def project_status(project_id):
    status = get_json_body().get("status")
    if status not in ("not_started", "in_progress", "completed"):
        raise ValidationError({"status": "Choose not_started, in_progress or completed."})
    if not db.session.get(PracticeProject, project_id):
        raise ApiError("not_found", "Project not found.", 404)
    row = UserProjectStatus.query.filter_by(user_id=current_user.id, project_id=project_id).first()
    if row is None:
        row = UserProjectStatus(user_id=current_user.id, project_id=project_id)
        db.session.add(row)
    row.status = status
    db.session.commit()
    return ok({"project_id": project_id, "status": status})
