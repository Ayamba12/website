from flask import Blueprint, request, jsonify

from app.auth.decorators import admin_required
from app.services.storage_service import upload_image, UploadError

bp = Blueprint("uploads", __name__, url_prefix="/api/uploads")


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
