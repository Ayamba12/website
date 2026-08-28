import os

from flask import Blueprint, request, jsonify

from app.auth.decorators import admin_required
from app.services.storage_service import upload_image, UploadError

bp = Blueprint("uploads", __name__, url_prefix="/api/uploads")


@bp.get("/debug-env")
@admin_required
def debug_env_route(**kwargs):
    """Temporary diagnostic route — reports non-sensitive characteristics of the
    S3 credential env vars (never the values themselves) to debug SignatureDoesNotMatch
    without exposing secrets. Delete this route once the issue is resolved."""
    def describe(name):
        raw = os.environ.get(name)
        if raw is None:
            return {"present": False}
        return {
            "present": True,
            "length": len(raw),
            "has_leading_whitespace": raw != raw.lstrip(),
            "has_trailing_whitespace": raw != raw.rstrip(),
            "is_ascii": raw.isascii(),
            "has_quote_chars": '"' in raw or "'" in raw,
            "first_2_chars": raw[:2],
            "last_2_chars": raw[-2:],
        }

    return jsonify({
        "AWS_ACCESS_KEY_ID": describe("AWS_ACCESS_KEY_ID"),
        "AWS_SECRET_ACCESS_KEY": describe("AWS_SECRET_ACCESS_KEY"),
        "AWS_REGION": describe("AWS_REGION"),
        "AWS_ENDPOINT_URL_S3": os.environ.get("AWS_ENDPOINT_URL_S3"),
        "STORAGE_BUCKET": os.environ.get("STORAGE_BUCKET"),
        "AWS_SESSION_TOKEN_present": "AWS_SESSION_TOKEN" in os.environ,
    })


@bp.post("/image")
@admin_required
def upload_image_route(**kwargs):
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"error": "No file uploaded"}), 400

    folder = request.form.get("folder", "opportunities")

    try:
        url = upload_image(file, folder=folder)
    except UploadError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"url": url}), 201
