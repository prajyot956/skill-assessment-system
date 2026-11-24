"""Idempotent seeding. Existing rows are never overwritten, so admin edits survive re-seeding."""
import re

from app.extensions import db
from app.models import (Assessment, AssessmentCategory, CareerRole, LearningResource, PracticeProject, Question,
                        QuestionOption, RoleSkill, Skill)
from app.seeds import learning, questions as qbank, roles as rbank, skills as sbank


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower().replace("+", "p").replace("#", "sharp")).strip("-") or "x"


def seed_all() -> dict:
    counts = {"skills": 0, "assessments": 0, "questions": 0, "roles": 0, "resources": 0, "projects": 0}
    by_name = {s.name: s for s in Skill.query.all()}

    for name, cat, aliases in sbank.SKILLS:
        if name not in by_name:
            by_name[name] = Skill(name=name, slug=slugify(name), category=cat, aliases=aliases)
            db.session.add(by_name[name])
            counts["skills"] += 1
    db.session.flush()

    cats = {c.name: c for c in AssessmentCategory.query.all()}
    for pos, (cname, desc, items) in enumerate(sbank.CATEGORIES):
        if cname not in cats:
            cats[cname] = AssessmentCategory(name=cname, slug=slugify(cname), description=desc, position=pos)
            db.session.add(cats[cname])
            db.session.flush()
        for skill_name, title in items:
            skill = by_name[skill_name]
            if not Assessment.query.filter_by(skill_id=skill.id).first():
                db.session.add(Assessment(category_id=cats[cname].id, skill_id=skill.id, title=title or skill_name))
                counts["assessments"] += 1

    for skill_name, rows in qbank.QUESTIONS.items():
        skill = by_name[skill_name]
        existing = {q.text for q in Question.query.filter_by(skill_id=skill.id)}
        for topic, diff, qt, text, opts, ans, expl in rows:
            if text in existing:
                continue
            qtype = {"s": "single", "m": "multiple", "t": "true_false", "x": "short", "c": "coding"}[qt]
            q = Question(skill_id=skill.id, topic=topic, difficulty=diff, qtype=qtype, text=text,
                         explanation=expl, marks=float(qbank.MARKS[diff]))
            if qtype in ("short", "coding"):
                q.accepted_answers = ans
            elif qtype == "true_false":
                q.options = [QuestionOption(text="True", is_correct=ans is True, position=0),
                             QuestionOption(text="False", is_correct=ans is False, position=1)]
            else:
                right = set(ans if isinstance(ans, list) else [ans])
                q.options = [QuestionOption(text=t, is_correct=i in right, position=i) for i, t in enumerate(opts)]
            db.session.add(q)
            counts["questions"] += 1

    for slug, name, desc, interests, edu, req in rbank.ROLES:
        if CareerRole.query.filter_by(slug=slug).first():
            continue
        role = CareerRole(slug=slug, name=name, description=desc, interest_tags=interests, education_keywords=edu)
        role.skills = [RoleSkill(skill_id=by_name[s].id, weight=float(w), min_level_pct=float(m), is_core=bool(c))
                       for s, w, m, c in req]
        db.session.add(role)
        counts["roles"] += 1

    have = {(r.skill_id, r.title) for r in LearningResource.query.all()}
    for skill_name, title, url, kind, level in learning.RESOURCES:
        if (by_name[skill_name].id, title) not in have:
            db.session.add(LearningResource(skill_id=by_name[skill_name].id, title=title, url=url, kind=kind, level=level))
            counts["resources"] += 1

    titles = {p.title for p in PracticeProject.query.all()}
    for title, diff, skill_names, desc, objectives, steps, outcome in learning.PROJECTS:
        if title not in titles:
            db.session.add(PracticeProject(title=title, difficulty=diff, description=desc, objectives=objectives,
                                           steps=steps, expected_outcome=outcome,
                                           skill_slugs=[by_name[s].slug for s in skill_names]))
            counts["projects"] += 1
    db.session.commit()
    return counts
