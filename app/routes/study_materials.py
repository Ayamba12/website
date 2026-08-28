from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models import StudyMaterial, StudyMaterialStatus
from app.auth.decorators import admin_required
from app.utils.slugify import unique_slug
from app.utils.pagination import paginate_query

bp = Blueprint("study_materials", __name__, url_prefix="/api/teacher/study-materials")


@bp.get("")
def list_materials():
    query = StudyMaterial.query.filter_by(status=StudyMaterialStatus.PUBLISHED)
    topic_id = request.args.get("topic_id")
    if topic_id:
        query = query.filter_by(topic_id=topic_id)
    query = query.order_by(StudyMaterial.created_at.desc())
    result = paginate_query(query, serializer=lambda m: m.to_dict())
    return jsonify(result)


@bp.get("/admin/list")
@admin_required
def admin_list(**kwargs):
    materials = StudyMaterial.query.order_by(StudyMaterial.created_at.desc()).all()
    return jsonify([m.to_dict(detailed=True) for m in materials])


@bp.get("/<slug>")
def get_material(slug):
    material = StudyMaterial.query.filter_by(slug=slug).first()
    if not material or material.status != StudyMaterialStatus.PUBLISHED:
        return jsonify({"error": "Study material not found"}), 404
    return jsonify(material.to_dict(detailed=True))


@bp.post("")
@admin_required
def create_material(**kwargs):
    data = request.get_json(silent=True) or {}
    if not data.get("title"):
        return jsonify({"error": "Title is required"}), 400

    material = StudyMaterial(
        title=data["title"],
        slug=unique_slug(data.get("slug") or data["title"], StudyMaterial),
        description=data.get("description"),
        content=data.get("content"),
        topic_id=data.get("topic_id"),
        source=data.get("source"),
        file_url=data.get("file_url"),
        status=data.get("status", StudyMaterialStatus.DRAFT),
    )
    db.session.add(material)
    db.session.commit()
    return jsonify(material.to_dict(detailed=True)), 201


@bp.put("/<int:material_id>")
@admin_required
def update_material(material_id):
    material = StudyMaterial.query.get_or_404(material_id)
    data = request.get_json(silent=True) or {}
    for field in ("title", "description", "content", "topic_id", "source", "file_url", "status"):
        if field in data:
            setattr(material, field, data[field])
    db.session.commit()
    return jsonify(material.to_dict(detailed=True))


@bp.delete("/<int:material_id>")
@admin_required
def delete_material(material_id):
    material = StudyMaterial.query.get_or_404(material_id)
    db.session.delete(material)
    db.session.commit()
    return jsonify({"message": "Study material deleted"})
