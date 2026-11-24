from app.models import (Certification, Education, Experience, Project, Resume, UserInterest,
                        UserSkill)


def completion(user) -> dict:
    """Profile completion = share of 10 equally weighted checklist items that are done."""
    p = user.profile
    uid = user.id
    has = lambda model, **f: model.query.filter_by(user_id=uid, **f).first() is not None
    items = [
        ("phone", "Add a phone number", bool(p and p.phone)),
        ("location", "Add your location", bool(p and p.location)),
        ("summary", "Write a professional summary", bool(p and p.summary)),
        ("links", "Link LinkedIn, GitHub or a portfolio",
         bool(p and (p.linkedin_url or p.github_url or p.portfolio_url))),
        ("education", "Add your education", has(Education)),
        ("skills", "Confirm at least one skill", has(UserSkill, status="user_confirmed")),
        ("projects", "Add a project", has(Project)),
        ("experience", "Add experience or an internship", has(Experience)),
        ("interests", "Choose your interests", has(UserInterest)),
        ("target", "Pick a target career", bool(p and p.target_role_id)),
    ]
    done = sum(1 for _, _, d in items if d)
    return {
        "percent": round(done / len(items) * 100),
        "items": [{"key": k, "label": label, "done": d} for k, label, d in items],
    }


def profile_dict(user) -> dict:
    p = user.profile
    uid = user.id
    return {
        "full_name": user.full_name,
        "email": user.email,
        "phone": p.phone, "location": p.location,
        "linkedin_url": p.linkedin_url, "portfolio_url": p.portfolio_url, "github_url": p.github_url,
        "summary": p.summary,
        "target_role_id": p.target_role_id,
        "preferences": p.preferences or {},
        "interests": [i.interest for i in UserInterest.query.filter_by(user_id=uid)
                      .order_by(UserInterest.interest)],
        "education": [{"id": e.id, "degree": e.degree, "specialization": e.specialization,
                       "institution": e.institution, "graduation_year": e.graduation_year,
                       "details": e.details} for e in Education.query.filter_by(user_id=uid)],
        "experience": [{"id": e.id, "company": e.company, "title": e.title, "kind": e.kind,
                        "duration": e.duration, "responsibilities": e.responsibilities}
                       for e in Experience.query.filter_by(user_id=uid)],
        "projects": [{"id": x.id, "name": x.name, "description": x.description,
                      "technologies": x.technologies, "role": x.role, "url": x.url}
                     for x in Project.query.filter_by(user_id=uid)],
        "certifications": [{"id": c.id, "name": c.name, "issuer": c.issuer,
                            "completed_on": c.completed_on}
                           for c in Certification.query.filter_by(user_id=uid)],
        "completion": completion(user),
    }
