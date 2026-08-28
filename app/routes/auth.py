from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from app.extensions import db
from app.models import User, UserType
from app.auth.decorators import get_current_user

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not name or not email or not password:
        return jsonify({"error": "name, email and password are required"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "An account with this email already exists"}), 409

    user_type = data.get("user_type") or UserType.STUDENT
    if user_type not in UserType.ALL:
        user_type = UserType.STUDENT

    interests = data.get("interests")
    if isinstance(interests, list):
        interests = ",".join(interests)

    user = User(
        name=name,
        email=email,
        user_type=user_type,
        education_level=data.get("education_level"),
        field_of_study=data.get("field_of_study"),
        country=data.get("country"),
        interests=interests,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    token = create_access_token(identity=str(user.id))
    return jsonify({"token": token, "user": user.to_dict()}), 201


@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid email or password"}), 401
    if not user.is_active:
        return jsonify({"error": "This account has been disabled"}), 403

    token = create_access_token(identity=str(user.id))
    return jsonify({"token": token, "user": user.to_dict()})


@bp.get("/me")
def me():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401
    return jsonify(user.to_dict(include_private=True))
