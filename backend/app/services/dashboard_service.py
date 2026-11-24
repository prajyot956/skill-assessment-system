"""Dashboard data. Everything here is read from the database; empty means empty."""
from sqlalchemy import func

from app.extensions import db
from app.models import (AssessmentAttempt, AssessmentResult, LearningRoadmap, Resume, RoadmapItem,
                        UserSkill, Notification)
from . import profile_service


def build(user) -> dict:
    uid = user.id
    resume = (Resume.query.filter_by(user_id=uid, is_current=True)
              .order_by(Resume.uploaded_at.desc()).first())
    skills = UserSkill.query.filter_by(user_id=uid, status="user_confirmed").all()
    assessed = [s for s in skills if s.proficiency_pct is not None]
    ranked = sorted(assessed, key=lambda s: s.proficiency_pct, reverse=True)
    fmt = lambda s: {"skill": s.skill.name, "proficiency_pct": round(s.proficiency_pct, 1)}

    submitted = (AssessmentAttempt.query.filter(AssessmentAttempt.user_id == uid,
                 AssessmentAttempt.status.in_(["submitted", "expired"])))
    pending = AssessmentAttempt.query.filter_by(user_id=uid, status="in_progress").count()
    avg = (db.session.query(func.avg(AssessmentResult.percentage))
           .join(AssessmentAttempt, AssessmentAttempt.id == AssessmentResult.attempt_id)
           .filter(AssessmentAttempt.user_id == uid).scalar())
    recent = (db.session.query(AssessmentResult, AssessmentAttempt)
              .join(AssessmentAttempt, AssessmentAttempt.id == AssessmentResult.attempt_id)
              .filter(AssessmentAttempt.user_id == uid)
              .order_by(AssessmentAttempt.submitted_at.desc()).limit(5).all())

    roadmap = LearningRoadmap.query.filter_by(user_id=uid, status="active").first()
    roadmap_data = None
    if roadmap:
        total = RoadmapItem.query.filter_by(roadmap_id=roadmap.id).count()
        done = RoadmapItem.query.filter_by(roadmap_id=roadmap.id, status="completed").count()
        roadmap_data = {"id": roadmap.id, "role": roadmap.role.name if roadmap.role else None,
                        "total": total, "completed": done, "pending": total - done,
                        "progress_pct": round(done / total * 100) if total else 0}

    from app.models import CareerRecommendation
    top_matches = [{"role": r.role.name, "match_pct": r.match_pct, "role_id": r.role_id} for r in
                   CareerRecommendation.query.filter_by(user_id=uid).order_by(CareerRecommendation.match_pct.desc()).limit(3)]
    notes = (Notification.query.filter_by(user_id=uid)
             .order_by(Notification.created_at.desc()).limit(8).all())
    return {
        "profile": {"completion": profile_service.completion(user),
                    "resume_status": resume.status if resume else "not_uploaded",
                    "confirmed_skills": len(skills)},
        "assessments": {"completed": submitted.count(), "pending": pending,
                        "average_score": round(avg, 1) if avg is not None else None,
                        "recent": [{"attempt_id": a.id, "skill": a.assessment.skill.name,
                                    "percentage": round(r.percentage, 1),
                                    "category": r.performance_category,
                                    "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None}
                                   for r, a in recent]},
        "skills": {"strongest": [fmt(s) for s in ranked[:3]],
                   "weakest": [fmt(s) for s in ranked[::-1][:3]] if len(ranked) > 3 else [],
                   "unassessed": [s.skill.name for s in skills if s.proficiency_pct is None][:10]},
        "career": {"target_role_id": user.profile.target_role_id, "top_matches": top_matches},
        "learning": roadmap_data,
        "activity": [n.to_dict() for n in notes],
    }
