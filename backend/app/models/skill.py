from app.extensions import db
from .base import TimestampMixin, user_fk, utcnow

SKILL_CATEGORIES = [
    "Programming", "Web Development", "Database Management", "Data Analytics",
    "Artificial Intelligence", "Machine Learning", "Cloud Computing", "Cybersecurity",
    "Software Testing", "Tools and Technologies", "Soft Skills",
]


class Skill(db.Model):
    """Global skill taxonomy. Data, not code: admins can add skills."""
    __tablename__ = "skills"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    slug = db.Column(db.String(100), nullable=False, unique=True)
    category = db.Column(db.String(60), nullable=False, index=True)
    aliases = db.Column(db.JSON, nullable=False, default=list)  # used by the local extractor
    is_active = db.Column(db.Boolean, nullable=False, default=True)


class UserSkill(TimestampMixin, db.Model):
    """How much we know about a skill for one user.

    status:  resume_detected -> user_confirmed (user action). Rejected skills are deleted.
    proficiency_pct is set ONLY by assessments; resume extraction never sets it.
    """
    __tablename__ = "user_skills"
    __table_args__ = (db.UniqueConstraint("user_id", "skill_id"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = user_fk()
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id", ondelete="RESTRICT"),
                         nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="resume_detected")
    source = db.Column(db.String(20), nullable=False, default="resume")  # resume | manual
    proficiency_pct = db.Column(db.Float)
    last_assessed_at = db.Column(db.DateTime)

    skill = db.relationship("Skill")
    evidence = db.relationship("SkillEvidence", back_populates="user_skill",
                               cascade="all, delete-orphan", passive_deletes=True)

    @property
    def evidence_level(self) -> str:
        if self.proficiency_pct is not None:
            return "assessment_verified"
        return "user_confirmed" if self.status == "user_confirmed" else "resume_detected"


class SkillEvidence(db.Model):
    __tablename__ = "skill_evidence"
    id = db.Column(db.Integer, primary_key=True)
    user_skill_id = db.Column(db.Integer, db.ForeignKey("user_skills.id", ondelete="CASCADE"),
                              nullable=False, index=True)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.id", ondelete="SET NULL"))
    source_section = db.Column(db.String(40), nullable=False)  # skills | projects | experience | ...
    snippet = db.Column(db.String(500))
    confidence = db.Column(db.Float, nullable=False, default=0.5)
    inferred = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user_skill = db.relationship("UserSkill", back_populates="evidence")
