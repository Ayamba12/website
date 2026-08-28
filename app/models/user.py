from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


class UserRole:
    SUPER_ADMIN = "super_admin"
    CONTENT_EDITOR = "content_editor"
    MODERATOR = "moderator"
    USER = "user"

    ALL = [SUPER_ADMIN, CONTENT_EDITOR, MODERATOR, USER]
    ADMIN_ROLES = [SUPER_ADMIN, CONTENT_EDITOR, MODERATOR]


class UserType:
    STUDENT = "student"
    TEACHER = "teacher"
    GRADUATE = "graduate"
    OTHER = "other"

    ALL = [STUDENT, TEACHER, GRADUATE, OTHER]


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), default=UserRole.USER, nullable=False)
    user_type = db.Column(db.String(30), default=UserType.STUDENT)
    education_level = db.Column(db.String(100))
    field_of_study = db.Column(db.String(150))
    country = db.Column(db.String(100))
    interests = db.Column(db.Text)  # comma-separated tags, simple v1 approach
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    saved_opportunities = db.relationship(
        "SavedOpportunity", backref="user", lazy="dynamic", cascade="all, delete-orphan"
    )
    test_attempts = db.relationship(
        "TestAttempt", backref="user", lazy="dynamic", cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role in UserRole.ADMIN_ROLES

    def to_dict(self, include_private=False):
        data = {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "user_type": self.user_type,
            "education_level": self.education_level,
            "field_of_study": self.field_of_study,
            "country": self.country,
            "interests": self.interests.split(",") if self.interests else [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_private:
            data["is_active"] = self.is_active
        return data
