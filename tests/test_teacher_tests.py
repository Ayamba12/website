from app.extensions import db
from app.models import TeacherQuestion, QuestionStatus


def _create_question(app, i):
    with app.app_context():
        q = TeacherQuestion(
            question_text=f"Question {i}",
            option_a="A",
            option_b="B",
            option_c="C",
            option_d="D",
            correct_answer="A",
            explanation="Because A is correct.",
            status=QuestionStatus.PUBLISHED,
        )
        db.session.add(q)
        db.session.commit()
        return q.id


def test_practice_test_flow(app, client, admin_user, admin_token):
    ids = [_create_question(app, i) for i in range(5)]
    headers = {"Authorization": f"Bearer {admin_token}"}

    resp = client.post(
        "/api/teacher/tests/start",
        json={"test_type": "practice", "num_questions": 3},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["questions"]) == 3
    attempt_id = data["attempt_id"]

    answers = [{"question_id": q["id"], "selected_answer": "A"} for q in data["questions"]]
    resp = client.post(
        f"/api/teacher/tests/{attempt_id}/submit",
        json={"answers": answers, "time_taken_seconds": 60},
        headers=headers,
    )
    assert resp.status_code == 200
    result = resp.get_json()
    assert result["score"] == 3
    assert result["percentage"] == 100.0

    resp = client.post(
        f"/api/teacher/tests/{attempt_id}/submit", json={"answers": []}, headers=headers
    )
    assert resp.status_code == 400  # already submitted


def test_start_test_requires_auth(client):
    resp = client.post("/api/teacher/tests/start", json={"test_type": "practice"})
    assert resp.status_code == 401
