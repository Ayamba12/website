from datetime import datetime, timezone
from app.extensions import db


class TeacherTopic(db.Model):
    __tablename__ = "teacher_topics"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)
    slug = db.Column(db.String(180), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    questions = db.relationship("TeacherQuestion", backref="topic", lazy="dynamic")
    materials = db.relationship("StudyMaterial", backref="topic", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "is_active": self.is_active,
        }


class QuestionType:
    MCQ = "mcq"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"

    ALL = [MCQ, TRUE_FALSE, SHORT_ANSWER]


class ContentType:
    PAST_QUESTION = "past_question"
    PRACTICE_QUESTION = "practice_question"
    AI_GENERATED = "ai_generated_practice"

    ALL = [PAST_QUESTION, PRACTICE_QUESTION, AI_GENERATED]


class QuestionStatus:
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    PUBLISHED = "published"
    REJECTED = "rejected"

    ALL = [DRAFT, PENDING_REVIEW, PUBLISHED, REJECTED]


class TeacherQuestion(db.Model):
    __tablename__ = "teacher_questions"

    id = db.Column(db.Integer, primary_key=True)
    question_text = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.String(20), default=QuestionType.MCQ, nullable=False)

    option_a = db.Column(db.Text)
    option_b = db.Column(db.Text)
    option_c = db.Column(db.Text)
    option_d = db.Column(db.Text)
    correct_answer = db.Column(db.String(10), nullable=False)  # 'A' / 'B' / 'true' / free text
    explanation = db.Column(db.Text)

    topic_id = db.Column(db.Integer, db.ForeignKey("teacher_topics.id"))
    subject = db.Column(db.String(150))
    difficulty = db.Column(db.String(20), default="medium")  # easy/medium/hard
    content_type = db.Column(db.String(30), default=ContentType.PRACTICE_QUESTION, nullable=False)
    year = db.Column(db.Integer)
    source = db.Column(db.String(255))
    status = db.Column(db.String(30), default=QuestionStatus.DRAFT, nullable=False, index=True)
    tags = db.Column(db.String(300))

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self, include_answer=False):
        data = {
            "id": self.id,
            "question_text": self.question_text,
            "question_type": self.question_type,
            "option_a": self.option_a,
            "option_b": self.option_b,
            "option_c": self.option_c,
            "option_d": self.option_d,
            "topic": self.topic.to_dict() if self.topic else None,
            "subject": self.subject,
            "difficulty": self.difficulty,
            "content_type": self.content_type,
            "year": self.year,
            "status": self.status,
            "tags": self.tags.split(",") if self.tags else [],
        }
        if include_answer:
            data["correct_answer"] = self.correct_answer
            data["explanation"] = self.explanation
            data["source"] = self.source
        return data


class MockExamStatus:
    DRAFT = "draft"
    PUBLISHED = "published"
    UNPUBLISHED = "unpublished"


class MockExam(db.Model):
    __tablename__ = "mock_exams"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    duration_minutes = db.Column(db.Integer, nullable=False, default=60)
    question_count = db.Column(db.Integer, nullable=False, default=50)
    status = db.Column(db.String(20), default=MockExamStatus.DRAFT, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    questions = db.relationship(
        "MockExamQuestion", backref="mock_exam", lazy="dynamic", cascade="all, delete-orphan",
        order_by="MockExamQuestion.question_order",
    )

    def to_dict(self, with_questions=False):
        data = {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "duration_minutes": self.duration_minutes,
            "question_count": self.question_count,
            "status": self.status,
        }
        if with_questions:
            data["questions"] = [
                meq.question.to_dict() for meq in self.questions if meq.question
            ]
        return data


class MockExamQuestion(db.Model):
    __tablename__ = "mock_exam_questions"

    id = db.Column(db.Integer, primary_key=True)
    mock_exam_id = db.Column(db.Integer, db.ForeignKey("mock_exams.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("teacher_questions.id"), nullable=False)
    question_order = db.Column(db.Integer, default=0)

    question = db.relationship("TeacherQuestion")


class StudyMaterialStatus:
    DRAFT = "draft"
    PUBLISHED = "published"


class StudyMaterial(db.Model):
    __tablename__ = "study_materials"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(230), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)
    content = db.Column(db.Text)
    topic_id = db.Column(db.Integer, db.ForeignKey("teacher_topics.id"))
    source = db.Column(db.String(255))
    file_url = db.Column(db.String(500))
    status = db.Column(db.String(20), default=StudyMaterialStatus.DRAFT, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self, detailed=False):
        data = {
            "id": self.id,
            "title": self.title,
            "slug": self.slug,
            "description": self.description,
            "topic": self.topic.to_dict() if self.topic else None,
            "source": self.source,
            "file_url": self.file_url,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if detailed:
            data["content"] = self.content
        return data
