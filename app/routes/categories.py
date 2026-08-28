from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models import OpportunityCategory
from app.auth.decorators import admin_required
from app.utils.slugify import unique_slug

bp = Blueprint("categories", __name__, url_prefix="/api/categories")


@bp.get("")
def list_categories():
    active_only = request.args.get("active", "true") == "true"
    query = OpportunityCategory.query
    if active_only:
        query = query.filter_by(is_active=True)
    categories = query.order_by(OpportunityCategory.name.asc()).all()
    return jsonify([c.to_dict() for c in categories])


@bp.post("")
@admin_required
def create_category(**kwargs):
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Name is required"}), 400
    if OpportunityCategory.query.filter_by(name=name).first():
        return jsonify({"error": "Category already exists"}), 409

    category = OpportunityCategory(
        name=name,
        slug=unique_slug(name, OpportunityCategory),
        description=data.get("description"),
        is_active=data.get("is_active", True),
    )
    db.session.add(category)
    db.session.commit()
    return jsonify(category.to_dict()), 201


@bp.put("/<int:category_id>")
@admin_required
def update_category(category_id):
    category = OpportunityCategory.query.get_or_404(category_id)
    data = request.get_json(silent=True) or {}
    if "name" in data:
        category.name = data["name"]
    if "description" in data:
        category.description = data["description"]
    if "is_active" in data:
        category.is_active = data["is_active"]
    db.session.commit()
    return jsonify(category.to_dict())


@bp.delete("/<int:category_id>")
@admin_required
def delete_category(category_id):
    category = OpportunityCategory.query.get_or_404(category_id)
    db.session.delete(category)
    db.session.commit()
    return jsonify({"message": "Category deleted"})
