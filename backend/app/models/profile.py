from app.extensions import db
from .base import TimestampMixin, user_fk, utcnow


class UserProfile(TimestampMixin, db.Model):
    __tablename__ = "user_profiles"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
                        nullable=False, unique=True)
    phone = db.Column(db.String(30))
    location = db.Column(db.String(120))
    linkedin_url = db.Column(db.String(300))
    portfolio_url = db.Column(db.String(300))
    github_url = db.Column(db.String(300))
    summary = db.Column(db.Text)
    target_role_id = db.Column(db.Integer, db.ForeignKey("career_roles.id", ondelete="SET NULL"))
    preferences = db.Column(db.JSON, nullable=False, default=dict)  # work type, locations, etc.

    user = db.relationship("User", back_populates="profile")


class Resume(db.Model):
    """An uploaded file plus its *draft* parse. Parsed data never reaches the profile
    until the user confirms it."""
    __tablename__ = "resumes"
    __table_args__ = (db.Index("ix_resumes_user_current", "user_id", "is_current"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = user_fk()
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(80), nullable=False, unique=True)  # random, never user-controlled
    file_size = db.Column(db.Integer, nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    sha256 = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="uploaded")
    # uploaded | processing | parsed | failed | confirmed
    parse_method = db.Column(db.String(20))  # ai | local
    raw_text = db.Column(db.Text)
    parsed_json = db.Column(db.JSON)
    error_message = db.Column(db.String(500))
    is_current = db.Column(db.Boolean, nullable=False, default=True)
    uploaded_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    confirmed_at = db.Column(db.DateTime)


def _src():
    return db.Column(db.Integer, db.ForeignKey("resumes.id", ondelete="SET NULL"))


class Education(TimestampMixin, db.Model):
    __tablename__ = "education"
    id = db.Column(db.Integer, primary_key=True)
    user_id = user_fk()
    degree = db.Column(db.String(150))
    specialization = db.Column(db.String(150))
    institution = db.Column(db.String(200), nullable=False)
    graduation_year = db.Column(db.Integer)
    details = db.Column(db.Text)
    source_resume_id = _src()


class Experience(TimestampMixin, db.Model):
    __tablename__ = "experience"
    id = db.Column(db.Integer, primary_key=True)
    user_id = user_fk()
    company = db.Column(db.String(200), nullable=False)
    title = db.Column(db.String(150))
    kind = db.Column(db.String(20), nullable=False, default="job")  # job | internship
    duration = db.Column(db.String(100))
    responsibilities = db.Column(db.Text)
    source_resume_id = _src()


class Project(TimestampMixin, db.Model):
    __tablename__ = "projects"
    id = db.Column(db.Integer, primary_key=True)
    user_id = user_fk()
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    technologies = db.Column(db.JSON, nullable=False, default=list)
    role = db.Column(db.String(150))
    url = db.Column(db.String(300))
    source_resume_id = _src()


class Certification(TimestampMixin, db.Model):
    __tablename__ = "certifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = user_fk()
    name = db.Column(db.String(200), nullable=False)
    issuer = db.Column(db.String(200))
    completed_on = db.Column(db.String(40))
    source_resume_id = _src()


class UserInterest(db.Model):
    __tablename__ = "user_interests"
    __table_args__ = (db.UniqueConstraint("user_id", "interest"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = user_fk()
    interest = db.Column(db.String(80), nullable=False)
