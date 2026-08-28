import random
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from sqlalchemy import func

from app.extensions import db
from app.models import (
    TeacherQuestion,
    QuestionStatus,
    MockExam,
    TestAttempt,
    TestAnswer,
    TestType,
    UserRole,
)
from app.auth.decorators import role_required

bp = Blueprint("teacher_tests", __name__, url_prefix="/api/teacher")

ANY_USER = UserRole.ALL


@bp.get("/mock-exams")
def list_mock_exams():
    exams = MockExam.query.filter_by(status="published").order_by(MockExam.created_at.desc()).all()
    return jsonify([e.to_dict() for e in exams])


@bp.post("/tests/start")
@role_required(*ANY_USER)
def start_test():
    data = request.get_json(silent=True) or {}
    test_type = data.get("test_type", TestType.PRACTICE)

    if test_type == TestType.MOCK_EXAM:
        mock_exam_id = data.get("mock_exam_id")
        exam = MockExam.query.get(mock_exam_id)
        if not exam:
            return jsonify({"error": "Mock exam not found"}), 404
        questions = [meq.question for meq in exam.questions if meq.question]
        test_id = exam.id
    else:
        query = TeacherQuestion.query.filter_by(status=QuestionStatus.PUBLISHED)
        if data.get("topic_id"):
            query = query.filter_by(topic_id=data["topic_id"])
        if data.get("difficulty"):
            query = query.filter_by(difficulty=data["difficulty"])
        if data.get("year"):
            query = query.filter_by(year=data["year"])
        if data.get("question_type"):
            query = query.filter_by(question_type=data["question_type"])

        all_matching = query.all()
        num_questions = min(int(data.get("num_questions", 20)), len(all_matching)) if all_matching else 0
        questions = random.sample(all_matching, num_questions) if num_questions else []
        test_id = None

    if not questions:
        return jsonify({"error": "No questions available for the selected criteria"}), 400

    attempt = TestAttempt(
        user_id=request.current_user.id,
        test_type=test_type,
        test_id=test_id,
        total_questions=len(questions),
        started_at=datetime.now(timezone.utc),
    )
    db.session.add(attempt)
    db.session.commit()

    return jsonify(
        {
            "attempt_id": attempt.id,
            "test_type": test_type,
            "duration_minutes": exam.duration_minutes if test_type == TestType.MOCK_EXAM else None,
            "questions": [q.to_dict() for q in questions],
        }
    )


@bp.post("/tests/<int:attempt_id>/submit")
@role_required(*ANY_USER)
def submit_test(attempt_id):
    attempt = TestAttempt.query.get_or_404(attempt_id)
    if attempt.user_id != request.current_user.id:
        return jsonify({"error": "Not allowed"}), 403
    if attempt.completed_at:
        return jsonify({"error": "This test has already been submitted"}), 400

    data = request.get_json(silent=True) or {}
    submitted_answers = data.get("answers", [])

    score = 0
    for ans in submitted_answers:
        question = TeacherQuestion.query.get(ans.get("question_id"))
        if not question:
            continue
        selected = (ans.get("selected_answer") or "").strip()
        is_correct = selected.lower() == (question.correct_answer or "").strip().lower()
        if is_correct:
            score += 1
        db.session.add(
            TestAnswer(
                attempt_id=attempt.id,
                question_id=question.id,
                selected_answer=selected,
                is_correct=is_correct,
            )
        )

    attempt.score = score
    attempt.percentage = round((score / attempt.total_questions) * 100, 2) if attempt.total_questions else 0
    attempt.time_taken_seconds = data.get("time_taken_seconds")
    attempt.completed_at = datetime.now(timezone.utc)
    db.session.commit()

    return jsonify(attempt.to_dict(with_answers=True))


@bp.get("/tests/history")
@role_required(*ANY_USER)
def test_history(**kwargs):
    attempts = (
        TestAttempt.query.filter_by(user_id=request.current_user.id)
        .filter(TestAttempt.completed_at.isnot(None))
        .order_by(TestAttempt.completed_at.desc())
        .limit(50)
        .all()
    )
    return jsonify([a.to_dict() for a in attempts])


@bp.get("/tests/<int:attempt_id>")
@role_required(*ANY_USER)
def get_attempt(attempt_id):
    attempt = TestAttempt.query.get_or_404(attempt_id)
    if attempt.user_id != request.current_user.id:
        return jsonify({"error": "Not allowed"}), 403
    return jsonify(attempt.to_dict(with_answers=True))


@bp.get("/progress")
@role_required(*ANY_USER)
def progress(**kwargs):
    user_id = request.current_user.id
    attempts = (
        TestAttempt.query.filter_by(user_id=user_id)
        .filter(TestAttempt.completed_at.isnot(None))
        .all()
    )

    total_tests = len(attempts)
    avg_score = round(sum(a.percentage for a in attempts) / total_tests, 2) if total_tests else 0
    highest_score = max((a.percentage for a in attempts), default=0)
    questions_attempted = sum(a.total_questions for a in attempts)
    correct_answers = sum(a.score for a in attempts)
    incorrect_answers = questions_attempted - correct_answers
    total_time = sum(a.time_taken_seconds or 0 for a in attempts)

    topic_stats = (
        db.session.query(
            TeacherQuestion.topic_id,
            func.sum(func.cast(TestAnswer.is_correct, db.Integer)).label("correct"),
            func.count(TestAnswer.id).label("total"),
        )
        .join(TestAnswer, TestAnswer.question_id == TeacherQuestion.id)
        .join(TestAttempt, TestAttempt.id == TestAnswer.attempt_id)
        .filter(TestAttempt.user_id == user_id)
        .group_by(TeacherQuestion.topic_id)
        .all()
    )

    from app.models import TeacherTopic

    topic_performance = []
    for topic_id, correct, total in topic_stats:
        topic = TeacherTopic.query.get(topic_id) if topic_id else None
        topic_performance.append(
            {
                "topic": topic.to_dict() if topic else {"id": None, "name": "Uncategorized"},
                "correct": int(correct or 0),
                "total": total,
                "percentage": round((correct / total) * 100, 2) if total else 0,
            }
        )
    topic_performance.sort(key=lambda t: t["percentage"], reverse=True)

    return jsonify(
        {
            "total_tests": total_tests,
            "average_score": avg_score,
            "highest_score": highest_score,
            "questions_attempted": questions_attempted,
            "correct_answers": correct_answers,
            "incorrect_answers": incorrect_answers,
            "time_spent_seconds": total_time,
            "strongest_topics": topic_performance[:3],
            "weakest_topics": list(reversed(topic_performance[-3:])) if topic_performance else [],
            "recent_tests": [a.to_dict() for a in sorted(attempts, key=lambda a: a.completed_at, reverse=True)[:5]],
        }
    )
