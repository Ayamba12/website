from datetime import datetime, timezone
from app.extensions import db


class TestType:
    PRACTICE = "practice"
    MOCK_EXAM = "mock_exam"

    ALL = [PRACTICE, MOCK_EXAM]


class TestAttempt(db.Model):
    __tablename__ = "test_attempts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    test_type = db.Column(db.String(20), nullable=False)
    test_id = db.Column(db.Integer)  # mock_exam id, null for ad-hoc practice
    score = db.Column(db.Integer, default=0)
    total_questions = db.Column(db.Integer, default=0)
    percentage = db.Column(db.Float, default=0.0)
    time_taken_seconds = db.Column(db.Integer)
    started_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime)

    answers = db.relationship(
        "TestAnswer", backref="attempt", lazy="dynamic", cascade="all, delete-orphan"
    )

    def to_dict(self, with_answers=False):
        data = {
            "id": self.id,
            "test_type": self.test_type,
            "test_id": self.test_id,
            "score": self.score,
            "total_questions": self.total_questions,
            "percentage": self.percentage,
            "time_taken_seconds": self.time_taken_seconds,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
        if with_answers:
            data["answers"] = [a.to_dict() for a in self.answers]
        return data


class TestAnswer(db.Model):
    __tablename__ = "test_answers"

    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey("test_attempts.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("teacher_questions.id"), nullable=False)
    selected_answer = db.Column(db.String(10))
    is_correct = db.Column(db.Boolean, default=False)

    question = db.relationship("TeacherQuestion")

    def to_dict(self):
        return {
            "id": self.id,
            "question": self.question.to_dict(include_answer=True) if self.question else None,
            "selected_answer": self.selected_answer,
            "is_correct": self.is_correct,
        }
