from functools import wraps
from flask import jsonify, current_app, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from app.models import User


def get_current_user():
    """Return the authenticated user, or None if there is no (valid) JWT.

    Safe to call for routes that behave differently for anonymous vs.
    authenticated users without requiring the caller to handle JWT errors.
    """
    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        return None
    user_id = get_jwt_identity()
    return User.query.get(int(user_id)) if user_id else None


def role_required(*roles):
    """Require a logged-in user whose role is in `roles`."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            user = User.query.get(int(user_id)) if user_id else None
            if not user or not user.is_active:
                return jsonify({"error": "Authentication required"}), 401
            if roles and user.role not in roles:
                return jsonify({"error": "Insufficient permissions"}), 403
            request.current_user = user
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def admin_required(fn):
    from app.models import UserRole

    return role_required(*UserRole.ADMIN_ROLES)(fn)


def api_key_required(fn):
    """Authenticate machine clients (e.g. the AI scraping agent) via a static API key."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        expected = current_app.config.get("AI_AGENT_API_KEY")
        provided = request.headers.get("X-API-Key", "")
        if not expected or provided != expected:
            return jsonify({"error": "Invalid or missing API key"}), 401
        return fn(*args, **kwargs)

    return wrapper
