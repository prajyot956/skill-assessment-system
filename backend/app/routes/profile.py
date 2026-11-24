from flask import Blueprint
from flask_login import current_user

from app.extensions import db
from app.models import CareerRole, UserInterest
from app.services import profile_service
from app.utils.decorators import get_json_body, login_required_api
from app.utils.responses import ValidationError, ok
from app.utils.validators import PHONE_RE, URL_RE, clean_str

bp = Blueprint("profile", __name__, url_prefix="/api/profile")

ALLOWED_WORK_TYPES = {"full_time", "internship", "part_time", "freelance", "remote_only"}


@bp.get("")
@login_required_api
def get_profile():
    return ok(profile_service.profile_dict(current_user))


@bp.put("")
@login_required_api
def update_profile():
    """Updates only the current user's own profile. Fields not sent are left unchanged."""
    data = get_json_body()
    p, errors, changes = current_user.profile, {}, {}

    def take(field, max_len, label, check=None, msg=None):
        if field not in data:
            return
        try:
            val = clean_str(data[field], max_len, field=label)
        except ValueError as e:
            errors[field] = str(e)
            return
        if val and check and not check(val):
            errors[field] = msg
            return
        changes[field] = val

    take("phone", 30, "Phone", lambda v: PHONE_RE.match(v), "Enter a valid phone number.")
    take("location", 120, "Location")
    take("summary", 2000, "Summary")
    for f, label in (("linkedin_url", "LinkedIn URL"), ("github_url", "GitHub URL"),
                     ("portfolio_url", "Portfolio URL")):
        take(f, 300, label, lambda v: URL_RE.match(v), "Enter a full link starting with http:// or https://.")

    if "full_name" in data:
        try:
            current_user.full_name = clean_str(data["full_name"], 120, required=True, field="Full name")
        except ValueError as e:
            errors["full_name"] = str(e)

    if "target_role_id" in data:
        rid = data["target_role_id"]
        if rid is None:
            changes["target_role_id"] = None
        elif isinstance(rid, int) and db.session.get(CareerRole, rid) and db.session.get(CareerRole, rid).is_active:
            changes["target_role_id"] = rid
        else:
            errors["target_role_id"] = "Choose a valid career role."

    if "preferences" in data:
        prefs = data["preferences"]
        if not isinstance(prefs, dict):
            errors["preferences"] = "Preferences must be an object."
        else:
            wt = prefs.get("work_types", [])
            if not isinstance(wt, list) or any(w not in ALLOWED_WORK_TYPES for w in wt):
                errors["preferences"] = "Unknown work type."
            else:
                changes["preferences"] = {"work_types": sorted(set(wt))}

    interests = None
    if "interests" in data:
        raw = data["interests"]
        if not isinstance(raw, list) or len(raw) > 30:
            errors["interests"] = "Provide up to 30 interests."
        else:
            try:
                interests = sorted({clean_str(i, 80, required=True, field="Interest") for i in raw})
            except ValueError as e:
                errors["interests"] = str(e)

    if errors:
        raise ValidationError(errors)

    for k, v in changes.items():
        setattr(p, k, v)
    if interests is not None:
        UserInterest.query.filter_by(user_id=current_user.id).delete()
        db.session.add_all(UserInterest(user_id=current_user.id, interest=i) for i in interests)
    db.session.commit()
    return ok(profile_service.profile_dict(current_user))


from app.services import profile_items  # noqa: E402
from app.utils.responses import ApiError  # noqa: E402


def _section(section):
    if section not in profile_items.SPECS:
        raise ApiError("not_found", "Unknown profile section.", 404)


@bp.post("/<section>")
@login_required_api
def add_item(section):
    _section(section)
    row = profile_items.create_item(current_user.id, section, get_json_body())
    db.session.commit()
    return ok(profile_items.serialize(section, row), 201)


@bp.put("/<section>/<int:item_id>")
@login_required_api
def edit_item(section, item_id):
    _section(section)
    row = profile_items.update_item(current_user.id, section, item_id, get_json_body())
    if row is None:
        raise ApiError("not_found", "Item not found.", 404)
    db.session.commit()
    return ok(profile_items.serialize(section, row))


@bp.delete("/<section>/<int:item_id>")
@login_required_api
def delete_item(section, item_id):
    _section(section)
    model, _ = profile_items.SPECS[section]
    row = model.query.filter_by(id=item_id, user_id=current_user.id).first()
    if row is None:
        raise ApiError("not_found", "Item not found.", 404)
    db.session.delete(row)
    db.session.commit()
    return ok({"deleted": True})


@bp.post("/suggest-summary")
@login_required_api
def suggest_summary():
    """Returns a SUGGESTION only; the user decides whether to save it."""
    from app.ai import features
    from app.ai.provider import AIUnavailable
    from app.models import Education, UserSkill
    edu = Education.query.filter_by(user_id=current_user.id).first()
    skills = [us.skill.name for us in UserSkill.query.filter_by(user_id=current_user.id, status="user_confirmed").limit(8)]
    if not edu and not skills:
        raise ApiError("not_enough_data", "Add education or confirm some skills first.", 409)
    facts = {"degree": edu.degree if edu else None, "field": edu.specialization if edu else None,
             "institution": edu.institution if edu else None, "skills": skills}
    try:
        return ok({"summary": features.suggest_summary(facts), "source": "ai"})
    except AIUnavailable:
        who = " ".join(x for x in [edu.degree if edu else None, "student" if edu and not edu.graduation_year else "graduate" if edu else "learner"] if x)
        text = f"{who.capitalize()}" + (f" in {edu.specialization}" if edu and edu.specialization else "") + (f" at {edu.institution}" if edu else "")
        text += (f" with skills in {', '.join(skills[:5])}." if skills else ".") + " Looking for opportunities to apply and grow these skills."
        return ok({"summary": text, "source": "template"})
