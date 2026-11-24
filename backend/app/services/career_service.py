"""Career matching and skill-gap analysis. Deterministic and documented in docs/ALGORITHMS.md; AI is never used for numbers."""
import hashlib
import json

from app.extensions import db
from app.models import (Assessment, CareerRecommendation, CareerRole, Education, Project, RoleSkill, UserInterest,
                        UserSkill)
from app.models.base import utcnow
from app.services import assessment_service

UNVERIFIED_CREDIT = 0.4   # user confirmed the skill, no assessment yet
DETECTED_CREDIT = 0.2     # resume evidence only
MAX_PROJECT_BONUS, MAX_EDU_BONUS, MAX_INTEREST_BONUS = 4.0, 3.0, 3.0


def skill_score(us, min_level: float):
    """-> (score 0..1, state). Assessed proficiency is the only thing that can earn full credit."""
    if us is None:
        return 0.0, "missing"
    if us.proficiency_pct is not None:
        p = us.proficiency_pct
        return (1.0, "met") if p >= min_level else (round(p / min_level, 3), "below")
    if us.status == "user_confirmed":
        return UNVERIFIED_CREDIT, "unverified"
    return DETECTED_CREDIT, "detected"


def _priority(weight: float, score: float, state: str) -> str:
    if state == "met":
        return "none"
    deficit = weight * (1 - score)
    return "high" if deficit >= 2.0 else "medium" if deficit >= 1.0 else "low"


def _assessment_info():
    avail = {}
    for a in Assessment.query.filter_by(is_active=True):
        avail[a.skill_id] = {"assessment_id": a.id, "available": assessment_service.available_counts(a.skill_id)["total"] >= assessment_service.MIN_QUESTIONS}
    return avail


def _context(user):
    return {
        "skills": {us.skill_id: us for us in UserSkill.query.filter_by(user_id=user.id)},
        "interests": [i.interest.lower() for i in UserInterest.query.filter_by(user_id=user.id)],
        "education": " ".join(f"{e.degree or ''} {e.specialization or ''}".lower() for e in Education.query.filter_by(user_id=user.id)),
        "project_text": " ".join(f"{p.name} {p.description or ''} {' '.join(p.technologies or [])}".lower() for p in Project.query.filter_by(user_id=user.id)),
        "assess": _assessment_info(),
    }


def gap_for_role(role: CareerRole, ctx) -> dict:
    rows, total_w, earned = [], 0.0, 0.0
    for rs in sorted(role.skills, key=lambda r: -r.weight):
        us = ctx["skills"].get(rs.skill_id)
        score, state = skill_score(us, rs.min_level_pct)
        total_w += rs.weight
        earned += rs.weight * score
        info = ctx["assess"].get(rs.skill_id, {"assessment_id": None, "available": False})
        rows.append({"skill_id": rs.skill_id, "skill": rs.skill.name, "category": rs.skill.category, "weight": rs.weight,
                     "required_level": rs.min_level_pct, "is_core": rs.is_core, "state": state, "score": score,
                     "evidence_level": us.evidence_level if us else "none",
                     "proficiency_pct": round(us.proficiency_pct, 1) if us and us.proficiency_pct is not None else None,
                     "priority": _priority(rs.weight, score, state), "assessment_id": info["assessment_id"],
                     "assessment_available": info["available"]})
    base = round(earned / total_w * 100, 1) if total_w else 0.0
    return {"skills": rows, "base_pct": base}


def adjustments(role: CareerRole, gap: dict, ctx) -> list[dict]:
    if gap["base_pct"] <= 0:
        return []  # interests or education alone never create a match
    out = []
    req = [r["skill"].lower() for r in gap["skills"]]
    in_projects = [s for s in req if s in ctx["project_text"]]
    if req and in_projects:
        out.append({"name": "Projects", "points": round(MAX_PROJECT_BONUS * len(in_projects) / len(req), 1),
                    "detail": f"{len(in_projects)} of {len(req)} required skills appear in your projects"})
    kws = [k.lower() for k in role.education_keywords or []]
    hit = next((k for k in kws if k in ctx["education"]), None)
    if hit:
        out.append({"name": "Education", "points": MAX_EDU_BONUS, "detail": f"Your education mentions “{hit}”"})
    tags = [t.lower() for t in role.interest_tags or []]
    matches = {i for i in ctx["interests"] for t in tags if t in i or i in t}
    if matches:
        out.append({"name": "Interests", "points": round(MAX_INTEREST_BONUS * min(1.0, len(matches) / 2), 1),
                    "detail": f"You listed {', '.join(sorted(matches))}"})
    return out


def _next_steps(gap_rows) -> list[str]:
    steps = []
    for r in [g for g in gap_rows if g["state"] != "met"][:3]:
        if r["assessment_available"] and r["state"] in ("missing", "unverified", "detected", "below"):
            verb = "Take" if r["state"] != "below" else "Practise, then retake"
            steps.append(f"{verb} the {r['skill']} assessment" + (f" (aim for {int(r['required_level'])}%+)" if r["state"] == "below" else ""))
        else:
            steps.append(f"Learn {r['skill']}" + (" (no assessment available yet)" if not r["assessment_available"] else ""))
    return steps


def recommendation_for(role, ctx, is_target=False) -> dict:
    gap = gap_for_role(role, ctx)
    adj = adjustments(role, gap, ctx)
    pct = round(min(100.0, gap["base_pct"] + sum(a["points"] for a in adj)), 1)
    rows = gap["skills"]
    met = [r for r in rows if r["state"] == "met"]
    below = [r for r in rows if r["state"] == "below"]
    unver = [r for r in rows if r["state"] in ("unverified", "detected")]
    missing = [r for r in rows if r["state"] == "missing"]
    why = []
    if met: why.append(f"Assessments show you meet the required level in {', '.join(r['skill'] for r in met[:4])}.")
    if below: why.append(f"You've started on {', '.join(r['skill'] for r in below[:3])} but are below the required level.")
    if unver: why.append(f"You list {', '.join(r['skill'] for r in unver[:4])} but they haven't been verified by an assessment, so they earn partial credit.")
    if missing: why.append(f"{len(missing)} required skill(s) are not in your profile yet.")
    why += [a["detail"] + f" (+{a['points']} points)." for a in adj]
    return {"role_id": role.id, "role": role.name, "description": role.description, "match_pct": pct, "base_pct": gap["base_pct"],
            "adjustments": adj, "is_target": is_target, "why": why, "matching_skills": met, "partial_skills": below,
            "unverified_skills": unver, "missing_skills": missing,
            "improvement_areas": [r["skill"] for r in sorted(below + unver + missing, key=lambda r: -r["weight"] * (1 - r["score"]))[:5]],
            "next_steps": _next_steps(sorted(rows, key=lambda r: -r["weight"] * (1 - r["score"])))}


def recommend(user) -> dict:
    ctx = _context(user)
    if not any(us.status == "user_confirmed" or us.proficiency_pct is not None for us in ctx["skills"].values()):
        CareerRecommendation.query.filter_by(user_id=user.id).delete()
        db.session.commit()
        return {"recommendations": [], "target": None,
                "message": "Confirm skills from your resume, or take an assessment, to get career matches."}
    target_id = user.profile.target_role_id
    recs = [recommendation_for(r, ctx, r.id == target_id) for r in CareerRole.query.filter_by(is_active=True)]
    recs = sorted([r for r in recs if r["base_pct"] > 0 or r["is_target"]], key=lambda r: (-r["match_pct"], r["role"]))
    CareerRecommendation.query.filter_by(user_id=user.id).delete()
    for r in recs:
        db.session.add(CareerRecommendation(user_id=user.id, role_id=r["role_id"], match_pct=r["match_pct"],
                                            breakdown={"base_pct": r["base_pct"], "adjustments": r["adjustments"]}, generated_at=utcnow()))
    db.session.commit()
    return {"recommendations": recs, "target": next((r for r in recs if r["is_target"]), None), "message": None}


def gap_analysis(user, role: CareerRole) -> dict:
    ctx = _context(user)
    rec = recommendation_for(role, ctx, role.id == user.profile.target_role_id)
    gap = gap_for_role(role, ctx)
    order = {"high": 0, "medium": 1, "low": 2, "none": 3}
    skills = sorted(gap["skills"], key=lambda r: (order[r["priority"]], -r["weight"]))
    return {"role_id": role.id, "role": role.name, "match_pct": rec["match_pct"], "skills": skills,
            "counts": {s: sum(1 for r in skills if r["state"] == s) for s in ("met", "below", "unverified", "detected", "missing")}}


def gap_signature(user, role: CareerRole) -> str:
    """Changes when assessments, confirmed skills or the target change; used to flag a roadmap as out of date."""
    g = gap_analysis(user, role)
    payload = [role.id] + [[r["skill_id"], r["state"], r["proficiency_pct"]] for r in g["skills"]]
    return hashlib.sha256(json.dumps(payload).encode()).hexdigest()[:16]
