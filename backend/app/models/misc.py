from app.extensions import db
from .base import user_fk, utcnow


class MockInterview(db.Model):
    __tablename__ = "mock_interviews"
    id = db.Column(db.Integer, primary_key=True)
    user_id = user_fk()
    role_id = db.Column(db.Integer, db.ForeignKey("career_roles.id", ondelete="SET NULL"))
    difficulty = db.Column(db.String(20), nullable=False)
    mode = db.Column(db.String(10), nullable=False)  # ai | bank
    status = db.Column(db.String(20), nullable=False, default="in_progress")
    questions = db.Column(db.JSON, nullable=False, default=list)
    answers = db.Column(db.JSON, nullable=False, default=dict)
    feedback = db.Column(db.JSON)  # null unless a real AI provider produced it
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    completed_at = db.Column(db.DateTime)


class Notification(db.Model):
    __tablename__ = "notifications"
    __table_args__ = (db.Index("ix_notifications_user_read", "user_id", "is_read"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = user_fk()
    kind = db.Column(db.String(30), nullable=False, default="info")
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.String(400))
    link = db.Column(db.String(200))
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def to_dict(self):
        return {"id": self.id, "kind": self.kind, "title": self.title, "message": self.message,
                "link": self.link, "is_read": self.is_read, "created_at": self.created_at.isoformat()}
