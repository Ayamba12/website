from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models import TeacherQuestion, TeacherTopic, QuestionStatus, ContentType
from app.auth.decorators import admin_required
from app.utils.pagination import paginate_query

bp = Blueprint("teacher_questions", __name__, url_prefix="/api/teacher")


@bp.get("/topics")
def list_topics():
    active_only = request.args.get("active", "true") == "true"
    query = TeacherTopic.query
    if active_only:
        query = query.filter_by(is_active=True)
    return jsonify([t.to_dict() for t in query.order_by(TeacherTopic.name.asc()).all()])


@bp.post("/topics")
@admin_required
def create_topic(**kwargs):
    from app.utils.slugify import unique_slug

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Name is required"}), 400
    topic = TeacherTopic(
        name=name, slug=unique_slug(name, TeacherTopic), description=data.get("description")
    )
    db.session.add(topic)
    db.session.commit()
    return jsonify(topic.to_dict()), 201


@bp.get("/questions")
def list_questions():
    """Public browsing of the question bank (published only, no answers revealed)."""
    query = TeacherQuestion.query.filter_by(status=QuestionStatus.PUBLISHED)

    topic_id = request.args.get("topic_id")
    if topic_id:
        query = query.filter_by(topic_id=topic_id)

    content_type = request.args.get("content_type")
    if content_type:
        query = query.filter_by(content_type=content_type)

    difficulty = request.args.get("difficulty")
    if difficulty:
        query = query.filter_by(difficulty=difficulty)

    year = request.args.get("year")
    if year:
        query = query.filter_by(year=year)

    query = query.order_by(TeacherQuestion.created_at.desc())
    result = paginate_query(query, serializer=lambda q: q.to_dict())
    return jsonify(result)


@bp.get("/questions/admin/<int:question_id>")
@admin_required
def admin_get_question(question_id, **kwargs):
    question = TeacherQuestion.query.get_or_404(question_id)
    return jsonify(question.to_dict(include_answer=True))


@bp.get("/questions/<int:question_id>")
def get_question(question_id):
    question = TeacherQuestion.query.get_or_404(question_id)
    if question.status != QuestionStatus.PUBLISHED:
        return jsonify({"error": "Question not found"}), 404
    return jsonify(question.to_dict())


def _apply_question_fields(question: TeacherQuestion, data: dict):
    fields = [
        "question_text", "question_type", "option_a", "option_b", "option_c", "option_d",
        "correct_answer", "explanation", "topic_id", "subject", "difficulty",
        "content_type", "year", "source", "status",
    ]
    for field in fields:
        if field in data:
            setattr(question, field, data[field])
    if "tags" in data and isinstance(data["tags"], list):
        question.tags = ",".join(t.strip() for t in data["tags"] if t.strip())


@bp.post("/questions")
@admin_required
def create_question(**kwargs):
    data = request.get_json(silent=True) or {}
    if not data.get("question_text") or not data.get("correct_answer"):
        return jsonify({"error": "question_text and correct_answer are required"}), 400

    question = TeacherQuestion(
        question_text=data["question_text"],
        correct_answer=data["correct_answer"],
        status=data.get("status", QuestionStatus.DRAFT),
    )
    _apply_question_fields(question, data)
    db.session.add(question)
    db.session.commit()
    return jsonify(question.to_dict(include_answer=True)), 201


@bp.put("/questions/<int:question_id>")
@admin_required
def update_question(question_id):
    question = TeacherQuestion.query.get_or_404(question_id)
    data = request.get_json(silent=True) or {}
    _apply_question_fields(question, data)
    db.session.commit()
    return jsonify(question.to_dict(include_answer=True))


@bp.delete("/questions/<int:question_id>")
@admin_required
def delete_question(question_id):
    question = TeacherQuestion.query.get_or_404(question_id)
    db.session.delete(question)
    db.session.commit()
    return jsonify({"message": "Question deleted"})


@bp.get("/questions/admin/list")
@admin_required
def admin_list_questions(**kwargs):
    query = TeacherQuestion.query
    status = request.args.get("status")
    if status:
        query = query.filter_by(status=status)
    query = query.order_by(TeacherQuestion.created_at.desc())
    result = paginate_query(query, serializer=lambda q: q.to_dict(include_answer=True))
    return jsonify(result)


@bp.post("/questions/bulk")
@admin_required
def bulk_question_action(**kwargs):
    data = request.get_json(silent=True) or {}
    ids = data.get("ids") or []
    action = data.get("action")

    questions = TeacherQuestion.query.filter(TeacherQuestion.id.in_(ids)).all()
    if not questions:
        return jsonify({"error": "No matching questions"}), 404

    if action == "publish":
        for q in questions:
            q.status = QuestionStatus.PUBLISHED
    elif action == "unpublish":
        for q in questions:
            q.status = QuestionStatus.DRAFT
    elif action == "reject":
        for q in questions:
            q.status = QuestionStatus.REJECTED
    elif action == "delete":
        for q in questions:
            db.session.delete(q)
    else:
        return jsonify({"error": "Unknown action"}), 400

    db.session.commit()
    return jsonify({"message": f"Bulk action '{action}' applied to {len(questions)} question(s)"})


REQUIRED_IMPORT_FIELDS = ("question", "correct_answer")


def _validate_import_row(row):
    """Validate one CSV-derived row. Returns (errors, normalized_fields)."""
    errors = []

    question_text = (row.get("question") or "").strip()
    if not question_text:
        errors.append("question is required")

    correct_answer = (row.get("correct_answer") or "").strip()
    if not correct_answer:
        errors.append("correct_answer is required")

    topic_id = None
    topic_name = (row.get("topic") or "").strip()
    if topic_name:
        topic = TeacherTopic.query.filter_by(name=topic_name).first()
        if not topic:
            errors.append(f"unknown topic '{topic_name}'")
        else:
            topic_id = topic.id

    content_type = (row.get("content_type") or ContentType.PRACTICE_QUESTION).strip()
    if content_type not in ContentType.ALL:
        errors.append(f"invalid content_type '{content_type}'")

    year_raw = row.get("year")
    year = None
    if year_raw not in (None, ""):
        try:
            year = int(year_raw)
        except (TypeError, ValueError):
            errors.append("year must be a number")

    if errors:
        return errors, None

    return errors, {
        "question_text": question_text,
        "option_a": row.get("option_a"),
        "option_b": row.get("option_b"),
        "option_c": row.get("option_c"),
        "option_d": row.get("option_d"),
        "correct_answer": correct_answer,
        "explanation": row.get("explanation"),
        "topic_id": topic_id,
        "difficulty": (row.get("difficulty") or "medium").strip(),
        "content_type": content_type,
        "year": year,
        "source": row.get("source"),
    }


def _normalize_question_text(text):
    return " ".join((text or "").split()).lower()


@bp.post("/questions/bulk-import")
@admin_required
def bulk_import_questions(**kwargs):
    """Validate (and optionally insert) rows parsed client-side from a CSV file.

    Body: { rows: [ {question, option_a..d, correct_answer, explanation,
                      topic, difficulty, content_type, year, source}, ... ],
            dry_run: bool }
    Invalid rows are never inserted. Rows whose question text already exists
    — either elsewhere in this same file or already in the database from a
    prior import — are flagged as duplicates and skipped rather than
    inserted again, so re-uploading the same file (or overlapping files)
    never creates copies.
    """
    data = request.get_json(silent=True) or {}
    rows = data.get("rows") or []
    dry_run = bool(data.get("dry_run"))

    existing_texts = {
        _normalize_question_text(t) for (t,) in db.session.query(TeacherQuestion.question_text).all()
    }
    seen_in_batch = set()

    results = []
    valid_rows = []
    for idx, row in enumerate(rows, start=1):
        errors, normalized = _validate_import_row(row)
        if errors:
            results.append({"row": idx, "status": "error", "errors": errors})
            continue

        key = _normalize_question_text(normalized["question_text"])
        if key in existing_texts or key in seen_in_batch:
            results.append({"row": idx, "status": "duplicate", "errors": ["This question already exists — skipped."]})
            continue

        seen_in_batch.add(key)
        valid_rows.append(normalized)
        results.append({"row": idx, "status": "valid"})

    inserted = 0
    if not dry_run:
        for vr in valid_rows:
            db.session.add(TeacherQuestion(status=QuestionStatus.DRAFT, **vr))
            inserted += 1
        if inserted:
            db.session.commit()

    duplicate_rows = sum(1 for r in results if r["status"] == "duplicate")

    return jsonify(
        {
            "dry_run": dry_run,
            "total_rows": len(rows),
            "valid_rows": len(valid_rows),
            "error_rows": len(rows) - len(valid_rows) - duplicate_rows,
            "duplicate_rows": duplicate_rows,
            "inserted": inserted,
            "results": results,
        }
    )
