from app.extensions import db
from app.models import (Assessment, AssessmentAttempt, AssessmentResult, LearningResource, LearningRoadmap, PracticeProject,
                        RoadmapItem, Skill, UserProjectStatus, UserSkill)
from app.models.base import utcnow
from app.services import assessment_service, career_service

MAX_SKILLS = 8


def _weak_topics(user_id, skill_id):
    row = (db.session.query(AssessmentResult).join(AssessmentAttempt).join(Assessment, Assessment.id == AssessmentAttempt.assessment_id)
           .filter(AssessmentAttempt.user_id == user_id, Assessment.skill_id == skill_id)
           .order_by(AssessmentAttempt.submitted_at.desc()).first())
    if not row:
        return []
    return [t for t, v in sorted(row.topic_breakdown.items(), key=lambda kv: kv[1]["earned"] / kv[1]["total"] if kv[1]["total"] else 0)
            if v["total"] and v["earned"] / v["total"] < 0.6][:3]


def _level_for(state):
    return "beginner" if state in ("missing", "detected") else "intermediate"


def _fit_projects(skill, state, used):
    want = {"beginner": ["beginner"], "intermediate": ["beginner", "intermediate"]}.get(_level_for(state), ["intermediate"])
    for p in PracticeProject.query.filter_by(is_active=True).order_by(PracticeProject.id):
        if skill.slug in (p.skill_slugs or []) and p.difficulty in want and p.id not in used:
            return p
    return None


def generate(user, role) -> LearningRoadmap:
    gap = career_service.gap_analysis(user, role)
    old = LearningRoadmap.query.filter_by(user_id=user.id, status="active").all()
    carried = {}
    for r in old:
        for it in r.items:
            if it.status != "pending":
                carried[(it.skill_id, it.item_type, it.title)] = (it.status, it.started_at, it.completed_at)
        r.status = "archived"
    todo = [g for g in gap["skills"] if g["state"] != "met"][:MAX_SKILLS]
    road = LearningRoadmap(user_id=user.id, role_id=role.id, status="active",
                           basis={"role_id": role.id, "signature": career_service.gap_signature(user, role),
                                  "gaps": [{"skill": g["skill"], "state": g["state"], "priority": g["priority"]} for g in todo]})
    db.session.add(road)
    pos, used_projects = 0, set()

    def add(skill_id, kind, title, desc, prio, resource_id=None):
        nonlocal pos
        item = RoadmapItem(skill_id=skill_id, item_type=kind, title=title[:200], description=desc, priority=prio if prio != "none" else "low",
                           position=pos, resource_id=resource_id)
        prev = carried.get((skill_id, kind, item.title))
        if prev:
            item.status, item.started_at, item.completed_at = prev
        road.items.append(item)
        pos += 1

    for g in todo:
        skill = db.session.get(Skill, g["skill_id"])
        weak = _weak_topics(user.id, skill.id)
        focus = f" Focus on: {', '.join(weak)}." if weak else ""
        level = _level_for(g["state"])
        resources = (LearningResource.query.filter_by(skill_id=skill.id, is_active=True)
                     .order_by((LearningResource.level != level), LearningResource.id).limit(2).all())
        for res in resources:
            add(skill.id, "learn", f"Learn {skill.name}: {res.title}", f"Study this {res.kind}.{focus}", g["priority"], res.id)
        if not resources:
            add(skill.id, "learn", f"Learn {skill.name} fundamentals", "No curated resource is available yet. Search for an official guide or a beginner course." + focus, g["priority"])
        add(skill.id, "exercise", f"Practise {skill.name}: 10 exercises",
            f"Write or solve ten small {skill.name} problems at {level} level without looking at solutions first." + focus, g["priority"])
        proj = _fit_projects(skill, g["state"], used_projects)
        if proj:
            used_projects.add(proj.id)
            add(skill.id, "mini_project", f"Build: {proj.title}", proj.description, g["priority"])
        if g["assessment_available"]:
            target = "Take" if g["state"] != "below" else "Retake"
            add(skill.id, "assess", f"{target} the {skill.name} assessment",
                f"Verify your progress. Required level for this career: {int(g['required_level'])}%.", g["priority"])
    db.session.commit()
    return road


def serialize(user, road) -> dict:
    role = road.role
    items = road.items
    done = sum(1 for i in items if i.status == "completed")
    resources = {r.id: r for r in LearningResource.query.filter(LearningResource.id.in_([i.resource_id for i in items if i.resource_id]))} if items else {}
    stale = bool(role) and road.basis.get("signature") != career_service.gap_signature(user, role)
    return {"id": road.id, "role_id": road.role_id, "role": role.name if role else None, "generated_at": road.generated_at.isoformat() + "Z",
            "is_stale": stale, "total": len(items), "completed": done, "in_progress": sum(1 for i in items if i.status == "in_progress"),
            "pending": sum(1 for i in items if i.status == "pending"), "progress_pct": round(done / len(items) * 100) if items else 0,
            "items": [{"id": i.id, "skill_id": i.skill_id, "skill": i.skill.name if i.skill else None, "type": i.item_type, "title": i.title,
                       "description": i.description, "priority": i.priority, "status": i.status,
                       "resource_url": resources[i.resource_id].url if i.resource_id in resources else None,
                       "assessment_id": next((a.id for a in Assessment.query.filter_by(skill_id=i.skill_id)), None) if i.item_type == "assess" else None,
                       "started_at": i.started_at.isoformat() + "Z" if i.started_at else None,
                       "completed_at": i.completed_at.isoformat() + "Z" if i.completed_at else None} for i in items],
            "gaps": road.basis.get("gaps", [])}


def set_status(item: RoadmapItem, status: str):
    item.status = status
    now = utcnow()
    if status == "pending":
        item.started_at = item.completed_at = None
    elif status == "in_progress":
        item.started_at, item.completed_at = item.started_at or now, None
    else:
        item.started_at, item.completed_at = item.started_at or now, now


def recommend_projects(user) -> list[dict]:
    ctx = career_service._context(user)
    target = user.profile.target_role_id
    gaps = {}
    if target:
        from app.models import CareerRole
        role = db.session.get(CareerRole, target)
        if role:
            gaps = {g["skill"]: g for g in career_service.gap_analysis(user, role)["skills"] if g["state"] != "met"}
    mine = {us.skill.slug: us for us in ctx["skills"].values() if us.status == "user_confirmed" or us.proficiency_pct is not None}
    status = {s.project_id: s.status for s in UserProjectStatus.query.filter_by(user_id=user.id)}
    out = []
    for p in PracticeProject.query.filter_by(is_active=True):
        skills = Skill.query.filter(Skill.slug.in_(p.skill_slugs or [])).all()
        gap_hits = [s.name for s in skills if s.name in gaps]
        have = [s.name for s in skills if s.slug in mine]
        avg = [mine[s.slug].proficiency_pct for s in skills if s.slug in mine and mine[s.slug].proficiency_pct is not None]
        score = 3 * len(gap_hits) + len(have)
        reasons = []
        if gap_hits: reasons.append(f"Builds skills you need for your target career: {', '.join(gap_hits)}")
        if have: reasons.append(f"Uses skills you already have: {', '.join(have[:4])}")
        if avg and sum(avg) / len(avg) >= 70 and p.difficulty == "beginner": score -= 2; reasons.append("May be easy for your level")
        if not reasons and p.difficulty == "beginner": score += 0.5; reasons.append("A good starter project")
        out.append({"id": p.id, "title": p.title, "description": p.description, "difficulty": p.difficulty,
                    "skills": [s.name for s in skills], "objectives": p.objectives, "steps": p.steps,
                    "expected_outcome": p.expected_outcome, "status": status.get(p.id, "not_started"),
                    "relevance": round(score, 1), "reasons": reasons})
    return sorted(out, key=lambda x: (-x["relevance"], x["title"]))
