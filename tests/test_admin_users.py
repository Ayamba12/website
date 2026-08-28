from app.extensions import db
from app.models import User, UserRole, UserType


def _create_user(app, email, role=UserRole.USER):
    with app.app_context():
        user = User(name="Someone", email=email, role=role, user_type=UserType.STUDENT)
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()
        return user.id


def test_create_user_requires_super_admin(client, auth_header):
    # auth_header belongs to a super_admin fixture, so this should succeed
    resp = client.post(
        "/api/admin/users",
        json={"name": "New Admin", "email": "newadmin@test.com", "password": "password123", "role": "content_editor"},
        headers=auth_header,
    )
    assert resp.status_code == 201
    assert resp.get_json()["role"] == "content_editor"


def test_non_admin_cannot_create_user(app, client):
    _create_user(app, "regular@test.com")
    resp = client.post("/api/auth/login", json={"email": "regular@test.com", "password": "password123"})
    token = resp.get_json()["token"]
    resp = client.post(
        "/api/admin/users",
        json={"name": "X", "email": "x@test.com", "password": "password123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_cannot_delete_self(client, auth_header, admin_user):
    resp = client.delete(f"/api/admin/users/{admin_user}", headers=auth_header)
    assert resp.status_code == 400


def test_cannot_delete_last_super_admin(app, client, auth_header, admin_user):
    # admin_user is the only super_admin in this test DB
    resp = client.delete(f"/api/admin/users/{admin_user}", headers=auth_header)
    assert resp.status_code == 400


def test_delete_other_user(app, client, auth_header):
    other_id = _create_user(app, "todelete@test.com")
    resp = client.delete(f"/api/admin/users/{other_id}", headers=auth_header)
    assert resp.status_code == 200


def test_cannot_remove_own_super_admin_role(client, auth_header, admin_user):
    resp = client.put(f"/api/admin/users/{admin_user}", json={"role": "user"}, headers=auth_header)
    assert resp.status_code == 400


def test_reset_password(app, client, auth_header):
    other_id = _create_user(app, "resetme@test.com")
    resp = client.put(f"/api/admin/users/{other_id}", json={"password": "newpassword456"}, headers=auth_header)
    assert resp.status_code == 200

    resp = client.post("/api/auth/login", json={"email": "resetme@test.com", "password": "newpassword456"})
    assert resp.status_code == 200
