"""Development seed data. Populates a small, clearly-fake dataset for local testing.

Run with: python seed.py
"""
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402
from app.extensions import db
from app.models import (
    User,
    UserRole,
    UserType,
    OpportunityCategory,
    Opportunity,
    OpportunityStatus,
    VerificationStatus,
    SourceType,
    TeacherTopic,
    TeacherQuestion,
    QuestionType,
    ContentType,
    QuestionStatus,
    MockExam,
    MockExamQuestion,
    MockExamStatus,
    StudyMaterial,
    StudyMaterialStatus,
)

SAMPLE_TAG = "[SAMPLE DATA]"

CATEGORIES = [
    ("Scholarships", "Fully or partially funded study opportunities."),
    ("Fellowships", "Funded professional or research fellowships."),
    ("Jobs", "Full-time and part-time job openings."),
    ("Internships", "Short-term work-experience placements."),
    ("Grants", "Funding for projects, research or organisations."),
    ("Competitions", "Contests, hackathons and challenges."),
    ("University Admissions", "Undergraduate and postgraduate admissions."),
    ("Courses", "Free and paid online/offline courses."),
    ("Teacher Opportunities", "Opportunities specifically for teachers."),
    ("Research Opportunities", "Research assistantships and programmes."),
]

TOPICS = [
    ("Educational Administration", "Sample topic — verify against the official syllabus before real use."),
    ("Pedagogy", "Sample topic — verify against the official syllabus before real use."),
    ("Educational Psychology", "Sample topic — verify against the official syllabus before real use."),
    ("ICT in Education", "Sample topic — verify against the official syllabus before real use."),
    ("Professional Practice", "Sample topic — verify against the official syllabus before real use."),
]


def upsert_category(name, description):
    cat = OpportunityCategory.query.filter_by(name=name).first()
    if cat:
        return cat
    from app.utils.slugify import unique_slug

    cat = OpportunityCategory(name=name, slug=unique_slug(name, OpportunityCategory), description=description)
    db.session.add(cat)
    db.session.flush()
    return cat


def upsert_topic(name, description):
    topic = TeacherTopic.query.filter_by(name=name).first()
    if topic:
        return topic
    from app.utils.slugify import unique_slug

    topic = TeacherTopic(name=name, slug=unique_slug(name, TeacherTopic), description=description)
    db.session.add(topic)
    db.session.flush()
    return topic


def run():
    app = create_app()
    with app.app_context():
        db.create_all()

        # --- Admin user -------------------------------------------------
        admin_email = "admin@example.com"
        if not User.query.filter_by(email=admin_email).first():
            admin = User(
                name="Platform Admin",
                email=admin_email,
                role=UserRole.SUPER_ADMIN,
                user_type=UserType.OTHER,
                country="Ghana",
            )
            admin.set_password("ChangeMe123!")
            db.session.add(admin)
            print(f"Created admin user: {admin_email} / ChangeMe123! (CHANGE THIS PASSWORD)")

        # --- Categories ---------------------------------------------------
        categories = {name: upsert_category(name, desc) for name, desc in CATEGORIES}
        db.session.flush()

        # --- Opportunities (clearly marked as sample data) ----------------
        if Opportunity.query.count() == 0:
            now = datetime.now(timezone.utc)
            samples = [
                dict(
                    title="Sample Commonwealth Master's Scholarship 2027",
                    category=categories["Scholarships"],
                    provider="Sample Commonwealth Scholarship Commission",
                    short_description=f"{SAMPLE_TAG} Fully funded master's study in the UK for Commonwealth citizens.",
                    description="This is placeholder sample data for local development. Do not treat as a real scholarship.",
                    target_audience="student",
                    country="United Kingdom",
                    location="United Kingdom",
                    education_level="Master's",
                    field_of_study="Any",
                    funding_type="Fully funded",
                    deadline=now + timedelta(days=45),
                    featured=True,
                ),
                dict(
                    title="Sample Ghana ICT Graduate Trainee Programme",
                    category=categories["Jobs"],
                    provider="Sample Tech Ghana Ltd",
                    short_description=f"{SAMPLE_TAG} 12-month graduate trainee programme in software engineering.",
                    description="Placeholder sample data for local development purposes only.",
                    target_audience="graduate",
                    country="Ghana",
                    location="Accra, Ghana",
                    education_level="Bachelor's",
                    field_of_study="Computer Science",
                    funding_type="Paid opportunity",
                    deadline=now + timedelta(days=20),
                    featured=True,
                ),
                dict(
                    title="Sample Teacher Digital Skills Fellowship",
                    category=categories["Teacher Opportunities"],
                    provider="Sample EdTech Africa",
                    short_description=f"{SAMPLE_TAG} A fellowship supporting teachers integrating ICT in classrooms.",
                    description="Placeholder sample data for local development purposes only.",
                    target_audience="teacher",
                    country="Ghana",
                    location="Ghana (hybrid)",
                    is_online=True,
                    education_level="Any",
                    field_of_study="Education",
                    funding_type="Stipend",
                    deadline=now + timedelta(days=10),
                    featured=False,
                ),
                dict(
                    title="Sample Research Grant for Young African Scientists",
                    category=categories["Grants"],
                    provider="Sample African Science Foundation",
                    short_description=f"{SAMPLE_TAG} Seed funding for early-career researchers.",
                    description="Placeholder sample data for local development purposes only.",
                    target_audience="graduate",
                    country="Multiple",
                    location="Remote",
                    is_online=True,
                    education_level="PhD",
                    field_of_study="STEM",
                    funding_type="Grant",
                    deadline=now + timedelta(days=60),
                    featured=False,
                ),
                dict(
                    title="Sample Free Data Analysis Short Course",
                    category=categories["Courses"],
                    provider="Sample Open Learning Ghana",
                    short_description=f"{SAMPLE_TAG} A free 6-week introductory data analysis course.",
                    description="Placeholder sample data for local development purposes only.",
                    target_audience="student",
                    country="Multiple",
                    location="Online",
                    is_online=True,
                    education_level="Any",
                    field_of_study="Data Science",
                    funding_type="Free",
                    deadline=now + timedelta(days=5),
                    featured=False,
                ),
                dict(
                    title="Sample Expired Undergraduate Scholarship (2025)",
                    category=categories["Scholarships"],
                    provider="Sample Foundation",
                    short_description=f"{SAMPLE_TAG} Example of an expired listing kept for historical records.",
                    description="Placeholder sample data for local development purposes only.",
                    target_audience="student",
                    country="Ghana",
                    location="Ghana",
                    education_level="Bachelor's",
                    field_of_study="Any",
                    funding_type="Partially funded",
                    deadline=now - timedelta(days=10),
                    featured=False,
                ),
            ]
            from app.utils.slugify import unique_slug

            for s in samples:
                opp = Opportunity(
                    title=s["title"],
                    slug=unique_slug(s["title"], Opportunity),
                    short_description=s["short_description"],
                    description=s["description"],
                    provider=s["provider"],
                    category_id=s["category"].id,
                    target_audience=s["target_audience"],
                    country=s["country"],
                    location=s["location"],
                    is_online=s.get("is_online", False),
                    education_level=s["education_level"],
                    field_of_study=s["field_of_study"],
                    funding_type=s["funding_type"],
                    deadline=s["deadline"],
                    status=OpportunityStatus.PUBLISHED,
                    verification_status=VerificationStatus.VERIFIED,
                    source_type=SourceType.MANUAL,
                    source_organization=s["provider"],
                    official_url="https://example.com",
                    application_url="https://example.com/apply",
                    requirements="Sample requirements — replace with real eligibility criteria.",
                    featured=s.get("featured", False),
                    published_at=now,
                    verified_at=now,
                    is_expired=s["deadline"] < now,
                )
                db.session.add(opp)

        # --- Teacher topics -------------------------------------------------
        topics = {name: upsert_topic(name, desc) for name, desc in TOPICS}
        db.session.flush()

        # --- Teacher questions (clearly practice/sample, never "past") ------
        if TeacherQuestion.query.count() == 0:
            topic_list = list(topics.values())
            for i in range(1, 41):
                topic = topic_list[i % len(topic_list)]
                q = TeacherQuestion(
                    question_text=f"[SAMPLE PRACTICE QUESTION #{i}] Which of the following best describes {topic.name.lower()}?",
                    question_type=QuestionType.MCQ,
                    option_a="Option A (sample)",
                    option_b="Option B (sample)",
                    option_c="Option C (sample)",
                    option_d="Option D (sample)",
                    correct_answer="A",
                    explanation="This is a sample explanation for local development/testing only.",
                    topic_id=topic.id,
                    subject=topic.name,
                    difficulty=["easy", "medium", "hard"][i % 3],
                    content_type=ContentType.PRACTICE_QUESTION,
                    year=2024,
                    source="Sample seed data",
                    status=QuestionStatus.PUBLISHED,
                    tags="sample,seed",
                )
                db.session.add(q)
            db.session.flush()

        # --- Mock exams -------------------------------------------------
        if MockExam.query.count() == 0:
            all_questions = TeacherQuestion.query.limit(20).all()
            exam1 = MockExam(
                title="Sample Mock Exam — General Practice (20 Questions)",
                description=f"{SAMPLE_TAG} A short mock exam for local development testing.",
                duration_minutes=30,
                question_count=len(all_questions),
                status=MockExamStatus.PUBLISHED,
            )
            db.session.add(exam1)
            db.session.flush()
            for order, q in enumerate(all_questions):
                db.session.add(MockExamQuestion(mock_exam_id=exam1.id, question_id=q.id, question_order=order))

            more_questions = TeacherQuestion.query.limit(10).all()
            exam2 = MockExam(
                title="Sample Mock Exam — Quick Review (10 Questions)",
                description=f"{SAMPLE_TAG} A shorter mock exam for local development testing.",
                duration_minutes=15,
                question_count=len(more_questions),
                status=MockExamStatus.PUBLISHED,
            )
            db.session.add(exam2)
            db.session.flush()
            for order, q in enumerate(more_questions):
                db.session.add(MockExamQuestion(mock_exam_id=exam2.id, question_id=q.id, question_order=order))

        # --- Study materials -------------------------------------------------
        if StudyMaterial.query.count() == 0:
            from app.utils.slugify import unique_slug

            for topic in list(topics.values())[:3]:
                title = f"Sample Study Guide: {topic.name}"
                sm = StudyMaterial(
                    title=title,
                    slug=unique_slug(title, StudyMaterial),
                    description=f"{SAMPLE_TAG} An introductory study guide for {topic.name}.",
                    content=f"This is placeholder sample content for {topic.name}. Replace with reviewed study material.",
                    topic_id=topic.id,
                    source="Sample seed data",
                    status=StudyMaterialStatus.PUBLISHED,
                )
                db.session.add(sm)

        db.session.commit()
        print("Seed data created successfully.")


if __name__ == "__main__":
    run()
