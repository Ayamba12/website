from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models import User, UserRole, UserType, Opportunity, OpportunityStatus, TestAttempt
from app.auth.decorators import admin_required, role_required

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@bp.get("/dashboard")
@admin_required
def dashboard(**kwargs):
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    soon = now + timedelta(days=7)

    expiring_soon = Opportunity.query.filter(
        Opportunity.is_expired.is_(False),
        Opportunity.deadline.isnot(None),
        Opportunity.deadline >= now,
        Opportunity.deadline <= soon,
    ).count()
    published_this_month = Opportunity.query.filter(
        Opportunity.published_at.isnot(None),
        Opportunity.published_at >= month_start,
    ).count()

    return jsonify(
        {
            "opportunities": {
                "total": Opportunity.query.count(),
                "published": Opportunity.query.filter_by(status=OpportunityStatus.PUBLISHED).count(),
                "drafts": Opportunity.query.filter_by(status=OpportunityStatus.DRAFT).count(),
                "pending_verification": Opportunity.query.filter_by(
                    status=OpportunityStatus.PENDING_REVIEW
                ).count(),
                "featured": Opportunity.query.filter_by(featured=True).count(),
                "expiring_soon": expiring_soon,
                "expired": Opportunity.query.filter_by(is_expired=True).count(),
                "published_this_month": published_this_month,
            },
            "users": {
                "total": User.query.count(),
                "new_this_month": User.query.filter(User.created_at >= month_start).count(),
            },
            "teacher": {
                "total_test_attempts": TestAttempt.query.filter(
                    TestAttempt.completed_at.isnot(None)
                ).count(),
            },
        }
    )


@bp.get("/users")
@role_required(UserRole.SUPER_ADMIN)
def list_users(**kwargs):
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify([u.to_dict(include_private=True) for u in users])


@bp.post("/users")
@role_required(UserRole.SUPER_ADMIN)
def create_user(**kwargs):
    """Directly create a user account, typically to onboard a new administrator."""
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    role = data.get("role") or UserRole.USER

    if not name or not email or not password:
        return jsonify({"error": "name, email and password are required"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    if role not in UserRole.ALL:
        return jsonify({"error": "Invalid role"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "An account with this email already exists"}), 409

    user = User(name=name, email=email, role=role, user_type=UserType.OTHER)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict(include_private=True)), 201


@bp.put("/users/<int:user_id>")
@role_required(UserRole.SUPER_ADMIN)
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json(silent=True) or {}

    if "role" in data:
        if data["role"] not in UserRole.ALL:
            return jsonify({"error": "Invalid role"}), 400
        if user.id == request.current_user.id and data["role"] != UserRole.SUPER_ADMIN:
            return jsonify({"error": "You cannot remove your own super admin role"}), 400
        user.role = data["role"]

    if "is_active" in data:
        if user.id == request.current_user.id and not data["is_active"]:
            return jsonify({"error": "You cannot disable your own account"}), 400
        user.is_active = bool(data["is_active"])

    if "password" in data and data["password"]:
        if len(data["password"]) < 8:
            return jsonify({"error": "Password must be at least 8 characters"}), 400
        user.set_password(data["password"])

    db.session.commit()
    return jsonify(user.to_dict(include_private=True))


@bp.delete("/users/<int:user_id>")
@role_required(UserRole.SUPER_ADMIN)
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == request.current_user.id:
        return jsonify({"error": "You cannot delete your own account"}), 400
    if user.role == UserRole.SUPER_ADMIN:
        remaining = User.query.filter(User.role == UserRole.SUPER_ADMIN, User.id != user.id).count()
        if remaining == 0:
            return jsonify({"error": "Cannot delete the last super admin"}), 400
    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "User deleted"})
