import os
import uuid

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5MB
ALLOWED_FOLDERS = {"opportunities", "logos", "study-materials"}


class UploadError(Exception):
    pass


def _client():
    endpoint = os.environ.get("AWS_ENDPOINT_URL_S3")
    if not endpoint:
        raise UploadError("Image storage is not configured (AWS_ENDPOINT_URL_S3 missing).")
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=os.environ.get("AWS_REGION", "us-east-2"),
        config=Config(signature_version="s3v4"),
    )


def upload_image(file_storage, folder="opportunities"):
    """Upload an image (a Flask FileStorage) to the object storage bucket and
    return its URL. The bucket must be set to public-read for the returned
    URL to be viewable without credentials — see the storage provider's
    bucket settings."""
    if folder not in ALLOWED_FOLDERS:
        folder = "opportunities"

    content_type = file_storage.mimetype
    ext = ALLOWED_CONTENT_TYPES.get(content_type)
    if not ext:
        raise UploadError("Unsupported image type. Use JPEG, PNG, WebP, or GIF.")

    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size == 0:
        raise UploadError("The uploaded file is empty.")
    if size > MAX_UPLOAD_BYTES:
        raise UploadError("Image is too large (max 5MB).")

    bucket = os.environ.get("STORAGE_BUCKET")
    if not bucket:
        raise UploadError("Image storage is not configured (STORAGE_BUCKET missing).")

    key = f"{folder}/{uuid.uuid4().hex}.{ext}"
    client = _client()
    try:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=file_storage.stream.read(),
            ContentType=content_type,
        )
    except ClientError as exc:
        raise UploadError(f"Upload failed: {exc}") from exc

    endpoint = os.environ.get("AWS_ENDPOINT_URL_S3")
    return f"{endpoint}/{bucket}/{key}"
