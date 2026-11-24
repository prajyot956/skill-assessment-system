"""Compare an extracted resume draft with the user's saved profile (used for first upload and re-upload)."""
import re

from app.models import Certification, Education, Experience, Project, UserSkill

PERSONAL = [("phone", "Phone"), ("location", "Location"), ("linkedin_url", "LinkedIn"), ("github_url", "GitHub"), ("portfolio_url", "Portfolio")]


def norm(v) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(v or "").lower())


SECTIONS = {
    "education": (Education, lambda d: norm(d.get("institution")) + "|" + norm(d.get("degree")),
                  ["degree", "specialization", "institution", "graduation_year", "details"]),
    "experience": (Experience, lambda d: norm(d.get("company")) + "|" + norm(d.get("title")),
                   ["company", "title", "kind", "duration", "responsibilities"]),
    "projects": (Project, lambda d: norm(d.get("name")), ["name", "description", "technologies", "role"]),
    "certifications": (Certification, lambda d: norm(d.get("name")), ["name", "issuer", "completed_on"]),
}


def row_dict(row, fields):
    d = {f: getattr(row, f) for f in fields}
    d["id"] = row.id
    return d


def _same(a, b):
    if isinstance(a, list) or isinstance(b, list):
        return sorted(map(norm, a or [])) == sorted(map(norm, b or []))
    return norm(a) == norm(b)


def build_diff(user, draft: dict) -> dict:
    profile = user.profile
    diff = {"personal": [], "summary": None}
    for key, label in PERSONAL:
        cur, new = getattr(profile, key), (draft["personal"] or {}).get(key)
        status = "same" if not new or _same(cur, new) else ("new" if not cur else "changed")
        diff["personal"].append({"field": key, "label": label, "current": cur, "new": new, "status": status})
    new_sum = draft.get("summary")
    diff["summary"] = {"current": profile.summary, "new": new_sum,
                       "status": "same" if not new_sum or _same(profile.summary, new_sum) else ("new" if not profile.summary else "changed")}

    for name, (model, keyfn, fields) in SECTIONS.items():
        existing = [row_dict(r, fields) for r in model.query.filter_by(user_id=user.id)]
        by_key = {keyfn(e): e for e in existing}
        res = {"new": [], "changed": [], "unchanged": 0, "missing": []}
        matched = set()
        for item in draft.get(name, []):
            k = keyfn(item)
            if k in by_key:
                cur = by_key[k]
                matched.add(k)
                changes = [{"field": f, "current": cur.get(f), "new": item.get(f)} for f in fields
                           if item.get(f) not in (None, "", []) and not _same(cur.get(f), item.get(f))]
                if changes:
                    res["changed"].append({"id": cur["id"], "current": cur, "item": item, "changes": changes})
                else:
                    res["unchanged"] += 1
            else:
                res["new"].append(item)
        res["missing"] = [e for k, e in by_key.items() if k not in matched]
        diff[name] = res

    mine = {us.skill.name: us for us in UserSkill.query.filter_by(user_id=user.id)}
    drafted = {s["name"] for s in draft.get("skills", [])}
    diff["skills"] = {
        "new": [s for s in draft.get("skills", []) if s["name"] not in mine],
        "existing": [{**s, "user_skill_id": mine[s["name"]].id, "status": mine[s["name"]].status}
                     for s in draft.get("skills", []) if s["name"] in mine],
        "missing": sorted(n for n, us in mine.items() if n not in drafted and us.status == "user_confirmed"),
    }
    return diff
