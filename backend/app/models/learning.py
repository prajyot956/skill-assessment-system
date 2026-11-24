from app.extensions import db
from .base import TimestampMixin, user_fk, utcnow


class LearningResource(db.Model):
    __tablename__ = "learning_resources"
    id = db.Column(db.Integer, primary_key=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(400))
    kind = db.Column(db.String(30), nullable=False, default="article")  # article|video|course|docs|book
    level = db.Column(db.String(20), nullable=False, default="beginner")
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    skill = db.relationship("Skill")


class LearningRoadmap(db.Model):
    __tablename__ = "learning_roadmaps"
    id = db.Column(db.Integer, primary_key=True)
    user_id = user_fk()
    role_id = db.Column(db.Integer, db.ForeignKey("career_roles.id", ondelete="SET NULL"))
    status = db.Column(db.String(20), nullable=False, default="active")  # active | archived
    basis = db.Column(db.JSON, nullable=False, default=dict)  # snapshot of gaps used to generate it
    generated_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    role = db.relationship("CareerRole")
    items = db.relationship("RoadmapItem", back_populates="roadmap", cascade="all, delete-orphan",
                            passive_deletes=True, order_by="RoadmapItem.position")


class RoadmapItem(db.Model):
    __tablename__ = "roadmap_items"
    id = db.Column(db.Integer, primary_key=True)
    roadmap_id = db.Column(db.Integer, db.ForeignKey("learning_roadmaps.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id", ondelete="SET NULL"))
    resource_id = db.Column(db.Integer, db.ForeignKey("learning_resources.id", ondelete="SET NULL"))
    item_type = db.Column(db.String(20), nullable=False, default="learn")  # learn|exercise|mini_project
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    priority = db.Column(db.String(10), nullable=False, default="medium")
    position = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default="pending")  # pending|in_progress|completed
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)

    roadmap = db.relationship("LearningRoadmap", back_populates="items")
    skill = db.relationship("Skill")


class PracticeProject(db.Model):
    __tablename__ = "practice_projects"
    id = db.Column(db.Integer, primary_key=True)
    seed_key = db.Column(db.String(200), unique=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.String(20), nullable=False)
    skill_slugs = db.Column(db.JSON, nullable=False, default=list)
    objectives = db.Column(db.JSON, nullable=False, default=list)
    steps = db.Column(db.JSON, nullable=False, default=list)
    expected_outcome = db.Column(db.Text)
    is_active = db.Column(db.Boolean, nullable=False, default=True)


class InterviewQuestion(db.Model):
    __tablename__ = "interview_question_bank"
    id = db.Column(db.Integer, primary_key=True)
    seed_key = db.Column(db.String(64), unique=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id", ondelete="SET NULL"), index=True)
    difficulty = db.Column(db.String(20), nullable=False)
    text = db.Column(db.Text, nullable=False)
    keywords = db.Column(db.JSON, nullable=False, default=list)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    skill = db.relationship("Skill")


class UserProjectStatus(db.Model):
    __tablename__ = "user_project_status"
    __table_args__ = (db.UniqueConstraint("user_id", "project_id"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = user_fk()
    project_id = db.Column(db.Integer, db.ForeignKey("practice_projects.id", ondelete="CASCADE"),
                           nullable=False)
    status = db.Column(db.String(20), nullable=False, default="not_started")
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
