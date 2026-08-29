from app.extensions import db
from app.models import TeacherQuestion, TeacherTopic


def _make_topic():
    topic = TeacherTopic(name="Assistant Director II", slug="assistant-director-ii")
    db.session.add(topic)
    db.session.commit()
    return topic


def _make_question(topic_id, status="draft", text="Sample question?"):
    q = TeacherQuestion(
        question_text=text, option_a="A", option_b="B", correct_answer="A",
        topic_id=topic_id, status=status,
    )
    db.session.add(q)
    db.session.commit()
    return q


def test_bulk_question_action_requires_admin(client):
    resp = client.post("/api/teacher/questions/bulk", json={"ids": [1], "action": "publish"})
    assert resp.status_code == 401


def test_bulk_publish_updates_status(app, client, auth_header):
    with app.app_context():
        topic = _make_topic()
        q1 = _make_question(topic.id, status="draft", text="Question one?")
        q2 = _make_question(topic.id, status="draft", text="Question two?")
        ids = [q1.id, q2.id]

    resp = client.post(
        "/api/teacher/questions/bulk", json={"ids": ids, "action": "publish"}, headers=auth_header,
    )
    assert resp.status_code == 200

    with app.app_context():
        for qid in ids:
            assert TeacherQuestion.query.get(qid).status == "published"


def test_bulk_unpublish_reverts_to_draft(app, client, auth_header):
    with app.app_context():
        topic = _make_topic()
        q = _make_question(topic.id, status="published", text="Published question?")
        qid = q.id

    client.post("/api/teacher/questions/bulk", json={"ids": [qid], "action": "unpublish"}, headers=auth_header)

    with app.app_context():
        assert TeacherQuestion.query.get(qid).status == "draft"


def test_bulk_reject_sets_rejected_status(app, client, auth_header):
    with app.app_context():
        topic = _make_topic()
        q = _make_question(topic.id, status="pending_review", text="Pending question?")
        qid = q.id

    client.post("/api/teacher/questions/bulk", json={"ids": [qid], "action": "reject"}, headers=auth_header)

    with app.app_context():
        assert TeacherQuestion.query.get(qid).status == "rejected"


def test_bulk_delete_removes_questions(app, client, auth_header):
    with app.app_context():
        topic = _make_topic()
        q = _make_question(topic.id, status="draft", text="To be deleted?")
        qid = q.id

    client.post("/api/teacher/questions/bulk", json={"ids": [qid], "action": "delete"}, headers=auth_header)

    with app.app_context():
        assert TeacherQuestion.query.get(qid) is None


def test_bulk_action_only_affects_selected_ids(app, client, auth_header):
    with app.app_context():
        topic = _make_topic()
        q1 = _make_question(topic.id, status="draft", text="Selected question?")
        q2 = _make_question(topic.id, status="draft", text="Untouched question?")
        selected_id, other_id = q1.id, q2.id

    client.post("/api/teacher/questions/bulk", json={"ids": [selected_id], "action": "publish"}, headers=auth_header)

    with app.app_context():
        assert TeacherQuestion.query.get(selected_id).status == "published"
        assert TeacherQuestion.query.get(other_id).status == "draft"


def test_bulk_action_unknown_action_rejected(app, client, auth_header):
    with app.app_context():
        topic = _make_topic()
        q = _make_question(topic.id)
        qid = q.id

    resp = client.post(
        "/api/teacher/questions/bulk", json={"ids": [qid], "action": "nonsense"}, headers=auth_header,
    )
    assert resp.status_code == 400


def test_bulk_action_no_matching_ids_returns_404(client, auth_header):
    resp = client.post(
        "/api/teacher/questions/bulk", json={"ids": [999999], "action": "publish"}, headers=auth_header,
    )
    assert resp.status_code == 404
