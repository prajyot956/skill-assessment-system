"""Validation and persistence for profile sections. Used by manual editing AND resume confirmation."""
from app.extensions import db
from app.models import Certification, Education, Experience, Project
from app.utils.responses import ValidationError
from app.utils.validators import URL_RE, clean_str

# field -> (kind, max/choices, required)
SPECS = {
    "education": (Education, {"degree": ("str", 150, False), "specialization": ("str", 150, False),
                              "institution": ("str", 200, True), "graduation_year": ("year", None, False),
                              "details": ("str", 2000, False)}),
    "experience": (Experience, {"company": ("str", 200, True), "title": ("str", 150, False),
                                "kind": ("choice", ("job", "internship"), False), "duration": ("str", 100, False),
                                "responsibilities": ("str", 4000, False)}),
    "projects": (Project, {"name": ("str", 200, True), "description": ("str", 3000, False),
                           "technologies": ("list", 40, False), "role": ("str", 150, False), "url": ("url", 300, False)}),
    "certifications": (Certification, {"name": ("str", 200, True), "issuer": ("str", 200, False),
                                       "completed_on": ("str", 40, False)}),
}
LABELS = {"institution": "Institution", "company": "Company", "name": "Name"}


def clean_item(section: str, data: dict, partial: bool = False) -> dict:
    _, spec = SPECS[section]
    out, errors = {}, {}
    for field, (kind, limit, required) in spec.items():
        if field not in data:
            if required and not partial:
                errors[field] = f"{LABELS.get(field, field.replace('_', ' ').title())} is required."
            continue
        v = data[field]
        try:
            if kind == "str":
                out[field] = clean_str(v, limit, required=required, field=LABELS.get(field, field.replace("_", " ").title()))
            elif kind == "url":
                s = clean_str(v, limit, field="Link")
                if s and not URL_RE.match(s):
                    raise ValueError("Enter a full link starting with http:// or https://.")
                out[field] = s
            elif kind == "year":
                if v in (None, ""):
                    out[field] = None
                else:
                    y = int(v)
                    if not 1950 <= y <= 2100:
                        raise ValueError("Enter a year between 1950 and 2100.")
                    out[field] = y
            elif kind == "choice":
                if v not in limit:
                    raise ValueError("Invalid value.")
                out[field] = v
            elif kind == "list":
                if not isinstance(v, list) or len(v) > 30:
                    raise ValueError("Provide up to 30 items.")
                out[field] = [clean_str(t, limit, required=True, field="Item") for t in v]
        except (ValueError, TypeError) as e:
            errors[field] = str(e) if isinstance(e, ValueError) and str(e) else "Invalid value."
    if errors:
        raise ValidationError(errors)
    return out


def serialize(section: str, row) -> dict:
    _, spec = SPECS[section]
    d = {f: getattr(row, f) for f in spec}
    d["id"] = row.id
    return d


def create_item(user_id: int, section: str, data: dict, source_resume_id=None):
    model, _ = SPECS[section]
    row = model(user_id=user_id, source_resume_id=source_resume_id, **clean_item(section, data))
    if section in ("projects",) and row.technologies is None:
        row.technologies = []
    db.session.add(row)
    return row


def update_item(user_id: int, section: str, item_id: int, data: dict):
    model, _ = SPECS[section]
    row = model.query.filter_by(id=item_id, user_id=user_id).first()
    if not row:
        return None
    for k, v in clean_item(section, data, partial=True).items():
        setattr(row, k, v)
    return row
