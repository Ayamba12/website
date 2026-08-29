from app.extensions import db
from app.models import TeacherQuestion, TeacherTopic


def _make_topic(name="Assistant Director II"):
    topic = TeacherTopic(name=name, slug=name.lower().replace(" ", "-"))
    db.session.add(topic)
    db.session.commit()
    return topic


def _row(question_text, topic_name="Assistant Director II"):
    return {
        "question": question_text,
        "option_a": "Option A",
        "option_b": "Option B",
        "option_c": "Option C",
        "option_d": "Option D",
        "correct_answer": "A",
        "explanation": "",
        "topic": topic_name,
        "difficulty": "medium",
        "content_type": "ai_generated_practice",
        "year": "",
        "source": "test",
    }


def test_bulk_import_requires_admin(client):
    resp = client.post("/api/teacher/questions/bulk-import", json={"rows": []})
    assert resp.status_code == 401


def test_bulk_import_inserts_valid_rows(app, client, auth_header):
    with app.app_context():
        _make_topic()

    rows = [_row("What is the capital of Ghana?"), _row("What year did Ghana gain independence?")]
    resp = client.post(
        "/api/teacher/questions/bulk-import", json={"rows": rows, "dry_run": False}, headers=auth_header,
    )
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["inserted"] == 2
    assert data["duplicate_rows"] == 0

    with app.app_context():
        assert TeacherQuestion.query.count() == 2


def test_bulk_import_skips_duplicates_within_the_same_file(app, client, auth_header):
    with app.app_context():
        _make_topic()

    rows = [_row("Repeated question text?"), _row("Repeated question text?")]
    resp = client.post(
        "/api/teacher/questions/bulk-import", json={"rows": rows, "dry_run": False}, headers=auth_header,
    )
    data = resp.get_json()
    assert data["inserted"] == 1
    assert data["duplicate_rows"] == 1
    assert data["results"][1]["status"] == "duplicate"

    with app.app_context():
        assert TeacherQuestion.query.count() == 1


def test_bulk_import_skips_duplicates_already_in_database(app, client, auth_header):
    with app.app_context():
        topic = _make_topic()
        db.session.add(TeacherQuestion(
            question_text="Already imported question?", option_a="A", option_b="B",
            correct_answer="A", topic_id=topic.id, status="draft",
        ))
        db.session.commit()

    # Re-importing the exact same file a second time — the real-world scenario
    # that motivated this fix (accidental double-upload).
    rows = [_row("Already imported question?")]
    resp = client.post(
        "/api/teacher/questions/bulk-import", json={"rows": rows, "dry_run": False}, headers=auth_header,
    )
    data = resp.get_json()
    assert data["inserted"] == 0
    assert data["duplicate_rows"] == 1

    with app.app_context():
        assert TeacherQuestion.query.count() == 1  # still just the original, not doubled


def test_bulk_import_duplicate_check_ignores_whitespace_and_case(app, client, auth_header):
    with app.app_context():
        topic = _make_topic()
        db.session.add(TeacherQuestion(
            question_text="What   is  the Scheme of Service?", option_a="A", option_b="B",
            correct_answer="A", topic_id=topic.id, status="draft",
        ))
        db.session.commit()

    rows = [_row("what is the scheme of service?")]
    resp = client.post(
        "/api/teacher/questions/bulk-import", json={"rows": rows, "dry_run": False}, headers=auth_header,
    )
    data = resp.get_json()
    assert data["duplicate_rows"] == 1
    assert data["inserted"] == 0


def test_dry_run_never_inserts_even_for_valid_rows(app, client, auth_header):
    with app.app_context():
        _make_topic()

    rows = [_row("A dry-run-only question?")]
    resp = client.post(
        "/api/teacher/questions/bulk-import", json={"rows": rows, "dry_run": True}, headers=auth_header,
    )
    data = resp.get_json()
    assert data["valid_rows"] == 1
    assert data["inserted"] == 0

    with app.app_context():
        assert TeacherQuestion.query.count() == 0
