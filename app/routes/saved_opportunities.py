from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models import SavedOpportunity, Opportunity
from app.auth.decorators import role_required
from app.models import UserRole, UserType

bp = Blueprint("saved_opportunities", __name__, url_prefix="/api/saved-opportunities")

ANY_USER = UserRole.ALL


@bp.get("")
@role_required(*ANY_USER)
def list_saved():
    saved = (
        SavedOpportunity.query.filter_by(user_id=request.current_user.id)
        .order_by(SavedOpportunity.created_at.desc())
        .all()
    )
    return jsonify([s.to_dict() for s in saved])


@bp.post("")
@role_required(*ANY_USER)
def save_opportunity():
    data = request.get_json(silent=True) or {}
    opportunity_id = data.get("opportunity_id")
    opp = Opportunity.query.get(opportunity_id)
    if not opp:
        return jsonify({"error": "Opportunity not found"}), 404

    existing = SavedOpportunity.query.filter_by(
        user_id=request.current_user.id, opportunity_id=opportunity_id
    ).first()
    if existing:
        return jsonify(existing.to_dict()), 200

    saved = SavedOpportunity(user_id=request.current_user.id, opportunity_id=opportunity_id)
    db.session.add(saved)
    db.session.commit()
    return jsonify(saved.to_dict()), 201


@bp.delete("/<int:saved_id>")
@role_required(*ANY_USER)
def remove_saved(saved_id):
    saved = SavedOpportunity.query.get_or_404(saved_id)
    if saved.user_id != request.current_user.id:
        return jsonify({"error": "Not allowed"}), 403
    db.session.delete(saved)
    db.session.commit()
    return jsonify({"message": "Removed"})
