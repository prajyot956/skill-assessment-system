from app.extensions import db
from app.models import Assessment, AssessmentAttempt, AssessmentResult, Skill, UserSkill


def build(user) -> dict:
    from app.routes.skills import user_skill_dict
    rows = UserSkill.query.filter_by(user_id=user.id).join(Skill).order_by(Skill.category, Skill.name).all()
    skills = [user_skill_dict(r) for r in rows]
    assessed = sorted([s for s in skills if s["proficiency_pct"] is not None], key=lambda s: -s["proficiency_pct"])
    counts = {"resume_detected": 0, "user_confirmed": 0, "assessment_verified": 0}
    for s in skills:
        counts[s["evidence_level"]] += 1
    by_cat = {}
    for s in skills:
        by_cat.setdefault(s["category"], []).append(s)

    attempts = (db.session.query(AssessmentAttempt, AssessmentResult).join(AssessmentResult, AssessmentResult.attempt_id == AssessmentAttempt.id)
                .filter(AssessmentAttempt.user_id == user.id).order_by(AssessmentAttempt.submitted_at).all())
    trends, topics = {}, {}
    for a, r in attempts:
        name = a.assessment.skill.name
        trends.setdefault(name, []).append({"attempt_id": a.id, "date": a.submitted_at.isoformat() + "Z", "percentage": r.percentage, "difficulty": a.difficulty})
        for topic, v in r.topic_breakdown.items():
            t = topics.setdefault((name, topic), {"earned": 0.0, "total": 0.0})
            t["earned"] += v["earned"]; t["total"] += v["total"]
    topic_rows = sorted(({"skill": k[0], "topic": k[1], "percentage": round(v["earned"] / v["total"] * 100, 1)} for k, v in topics.items() if v["total"]),
                        key=lambda t: t["percentage"])
    avail = {a.skill_id for a in Assessment.query.filter_by(is_active=True)}
    return {"skills": skills, "by_category": by_cat, "evidence_counts": counts,
            "strongest": assessed[:5], "weakest": [s for s in assessed[::-1] if s["proficiency_pct"] < 60][:5],
            "unassessed": [s for s in skills if s["proficiency_pct"] is None and s["status"] == "user_confirmed"],
            "unassessed_with_test": [s["name"] for s in skills if s["proficiency_pct"] is None and s["skill_id"] in avail],
            "trends": [{"skill": k, "points": v} for k, v in trends.items()], "topics": topic_rows,
            "total_attempts": len(attempts)}
