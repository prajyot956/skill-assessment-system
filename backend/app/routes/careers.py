from flask import Blueprint
from flask_login import current_user

from app.ai import features
from app.ai.provider import AIUnavailable, ai_enabled
from app.extensions import db, limiter
from app.models import CareerRole
from app.services import analysis_service, career_service
from app.utils.decorators import get_json_body, login_required_api
from app.utils.responses import ApiError, ok

bp = Blueprint("careers", __name__, url_prefix="/api")


def _role(role_id) -> CareerRole:
    r = db.session.get(CareerRole, role_id)
    if not r or not r.is_active:
        raise ApiError("not_found", "Career role not found.", 404)
    return r


@bp.get("/analysis")
@login_required_api
def analysis():
    return ok(analysis_service.build(current_user))


@bp.get("/careers/roles")
@login_required_api
def roles():
    return ok([{"id": r.id, "name": r.name, "description": r.description, "skill_count": len(r.skills)}
               for r in CareerRole.query.filter_by(is_active=True).order_by(CareerRole.name)])


@bp.get("/careers/recommendations")
@login_required_api
def recommendations():
    return ok({**career_service.recommend(current_user), "ai_enabled": ai_enabled()})


@bp.get("/careers/<int:role_id>/gap")
@login_required_api
def gap(role_id):
    return ok(career_service.gap_analysis(current_user, _role(role_id)))


@bp.put("/careers/target")
@login_required_api
def set_target():
    rid = get_json_body().get("role_id")
    if rid is not None:
        _role(rid if isinstance(rid, int) else -1)
    current_user.profile.target_role_id = rid
    db.session.commit()
    return ok({"target_role_id": rid})


@bp.post("/careers/<int:role_id>/explain")
@login_required_api
@limiter.limit("10 per hour")
def explain(role_id):
    role = _role(role_id)
    rec = career_service.recommendation_for(role, career_service._context(current_user))
    try:
        return ok({"explanation": features.explain_career(rec), "source": "ai"})
    except AIUnavailable:
        raise ApiError("ai_unavailable", "AI explanations aren't available right now. The reasons listed above are always accurate.", 503)
