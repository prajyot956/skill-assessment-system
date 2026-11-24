from app.extensions import db
from .base import TimestampMixin, user_fk, utcnow


class CareerRole(TimestampMixin, db.Model):
    __tablename__ = "career_roles"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    slug = db.Column(db.String(120), nullable=False, unique=True)
    description = db.Column(db.Text)
    interest_tags = db.Column(db.JSON, nullable=False, default=list)
    education_keywords = db.Column(db.JSON, nullable=False, default=list)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    skills = db.relationship("RoleSkill", back_populates="role", cascade="all, delete-orphan",
                             passive_deletes=True)


class RoleSkill(db.Model):
    __tablename__ = "role_skills"
    __table_args__ = (db.UniqueConstraint("role_id", "skill_id"),)
    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey("career_roles.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id", ondelete="RESTRICT"), nullable=False)
    weight = db.Column(db.Float, nullable=False, default=1.0)  # relative importance
    min_level_pct = db.Column(db.Float, nullable=False, default=60.0)  # required assessed %
    is_core = db.Column(db.Boolean, nullable=False, default=True)

    role = db.relationship("CareerRole", back_populates="skills")
    skill = db.relationship("Skill")


class CareerRecommendation(db.Model):
    __tablename__ = "career_recommendations"
    __table_args__ = (db.UniqueConstraint("user_id", "role_id"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = user_fk()
    role_id = db.Column(db.Integer, db.ForeignKey("career_roles.id", ondelete="CASCADE"), nullable=False)
    match_pct = db.Column(db.Float, nullable=False)
    breakdown = db.Column(db.JSON, nullable=False, default=dict)  # per-skill and adjustment detail
    generated_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    role = db.relationship("CareerRole")
