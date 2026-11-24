from app.extensions import db
from .base import TimestampMixin, user_fk, utcnow


class AssessmentCategory(db.Model):
    __tablename__ = "assessment_categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    slug = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.String(300))
    position = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)


class Assessment(db.Model):
    """One assessable skill within a category (e.g. Python under Programming)."""
    __tablename__ = "assessments"
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("assessment_categories.id", ondelete="RESTRICT"),
                            nullable=False, index=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id", ondelete="RESTRICT"),
                         nullable=False, unique=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.String(300))
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    category = db.relationship("AssessmentCategory")
    skill = db.relationship("Skill")


class Question(TimestampMixin, db.Model):
    __tablename__ = "questions"
    __table_args__ = (db.Index("ix_questions_skill_difficulty", "skill_id", "difficulty"),)
    id = db.Column(db.Integer, primary_key=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id", ondelete="RESTRICT"), nullable=False)
    topic = db.Column(db.String(100), nullable=False)
    difficulty = db.Column(db.String(20), nullable=False)  # beginner | intermediate | advanced
    qtype = db.Column(db.String(20), nullable=False)  # single | multiple | true_false | short
    text = db.Column(db.Text, nullable=False)
    accepted_answers = db.Column(db.JSON)  # short-answer only; never sent to clients
    explanation = db.Column(db.Text)
    marks = db.Column(db.Float, nullable=False, default=1.0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    skill = db.relationship("Skill")
    options = db.relationship("QuestionOption", back_populates="question",
                              cascade="all, delete-orphan", passive_deletes=True,
                              order_by="QuestionOption.position")


class QuestionOption(db.Model):
    __tablename__ = "question_options"
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id", ondelete="CASCADE"),
                            nullable=False, index=True)
    text = db.Column(db.String(500), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False, default=False)
    position = db.Column(db.Integer, nullable=False, default=0)

    question = db.relationship("Question", back_populates="options")


class AssessmentAttempt(db.Model):
    __tablename__ = "assessment_attempts"
    __table_args__ = (db.Index("ix_attempts_user_status", "user_id", "status"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = user_fk()
    assessment_id = db.Column(db.Integer, db.ForeignKey("assessments.id", ondelete="RESTRICT"),
                              nullable=False, index=True)
    difficulty = db.Column(db.String(20), nullable=False)
    num_questions = db.Column(db.Integer, nullable=False)
    duration_seconds = db.Column(db.Integer, nullable=False)
    question_ids = db.Column(db.JSON, nullable=False)  # ordered snapshot taken at start
    started_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)  # authoritative; the client timer is cosmetic
    submitted_at = db.Column(db.DateTime)
    status = db.Column(db.String(20), nullable=False, default="in_progress")
    # in_progress | submitted | expired (expired attempts are scored on what was saved)

    assessment = db.relationship("Assessment")
    answers = db.relationship("AttemptAnswer", back_populates="attempt",
                              cascade="all, delete-orphan", passive_deletes=True)
    result = db.relationship("AssessmentResult", back_populates="attempt", uselist=False,
                             cascade="all, delete-orphan", passive_deletes=True)


class AttemptAnswer(db.Model):
    __tablename__ = "attempt_answers"
    __table_args__ = (db.UniqueConstraint("attempt_id", "question_id"),)
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey("assessment_attempts.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False)
    answer = db.Column(db.JSON)  # option id(s) or text
    is_correct = db.Column(db.Boolean)  # filled at scoring time
    marks_awarded = db.Column(db.Float)
    answered_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    attempt = db.relationship("AssessmentAttempt", back_populates="answers")


class AssessmentResult(db.Model):
    __tablename__ = "assessment_results"
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey("assessment_attempts.id", ondelete="CASCADE"),
                           nullable=False, unique=True)
    total_marks = db.Column(db.Float, nullable=False)
    obtained_marks = db.Column(db.Float, nullable=False)
    percentage = db.Column(db.Float, nullable=False)
    accuracy = db.Column(db.Float, nullable=False)  # correct / attempted
    performance_category = db.Column(db.String(30), nullable=False)
    correct_count = db.Column(db.Integer, nullable=False)
    incorrect_count = db.Column(db.Integer, nullable=False)
    unanswered_count = db.Column(db.Integer, nullable=False)
    topic_breakdown = db.Column(db.JSON, nullable=False, default=dict)
    difficulty_breakdown = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    attempt = db.relationship("AssessmentAttempt", back_populates="result")
