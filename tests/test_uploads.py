import io
from unittest.mock import patch


def test_upload_requires_admin(client):
    resp = client.post("/api/uploads/image", data={}, content_type="multipart/form-data")
    assert resp.status_code == 401


def test_upload_requires_file(client, auth_header):
    resp = client.post("/api/uploads/image", data={}, headers=auth_header, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_upload_success(client, auth_header):
    with patch("app.routes.uploads.upload_image", return_value="https://example.com/bucket/opportunities/abc.jpg"):
        data = {"file": (io.BytesIO(b"fake image bytes"), "photo.jpg")}
        resp = client.post(
            "/api/uploads/image", data=data, headers=auth_header, content_type="multipart/form-data"
        )
    assert resp.status_code == 201
    assert resp.get_json()["url"] == "https://example.com/bucket/opportunities/abc.jpg"


def test_upload_rejects_bad_type(client, auth_header):
    from app.services.storage_service import UploadError

    with patch("app.routes.uploads.upload_image", side_effect=UploadError("Unsupported image type.")):
        data = {"file": (io.BytesIO(b"not an image"), "readme.txt")}
        resp = client.post(
            "/api/uploads/image", data=data, headers=auth_header, content_type="multipart/form-data"
        )
    assert resp.status_code == 400
