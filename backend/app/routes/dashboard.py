from flask import Blueprint, request
from flask_login import current_user

from app.extensions import db
from app.models import Notification
from app.services import dashboard_service
from app.utils.decorators import login_required_api
from app.utils.responses import ApiError, ok

bp = Blueprint("dashboard", __name__, url_prefix="/api")


@bp.get("/dashboard")
@login_required_api
def dashboard():
    return ok(dashboard_service.build(current_user))


@bp.get("/notifications")
@login_required_api
def list_notifications():
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = min(max(request.args.get("per_page", 20, type=int), 1), 50)
    q = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc())
    total = q.count()
    items = q.offset((page - 1) * per_page).limit(per_page).all()
    unread = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return ok([n.to_dict() for n in items],
              meta={"page": page, "per_page": per_page, "total": total, "unread": unread})


@bp.post("/notifications/<int:note_id>/read")
@login_required_api
def mark_read(note_id):
    n = Notification.query.filter_by(id=note_id, user_id=current_user.id).first()
    if not n:  # same answer whether it doesn't exist or belongs to someone else
        raise ApiError("not_found", "Notification not found.", 404)
    n.is_read = True
    db.session.commit()
    return ok(n.to_dict())


@bp.post("/notifications/read-all")
@login_required_api
def mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return ok({"updated": True})
