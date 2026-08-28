def test_register_and_login(client):
    resp = client.post(
        "/api/auth/register",
        json={"name": "Jane Doe", "email": "jane@test.com", "password": "password123"},
    )
    assert resp.status_code == 201
    assert "token" in resp.get_json()

    resp = client.post("/api/auth/register", json={"name": "Jane Doe", "email": "jane@test.com", "password": "password123"})
    assert resp.status_code == 409

    resp = client.post("/api/auth/login", json={"email": "jane@test.com", "password": "wrong"})
    assert resp.status_code == 401

    resp = client.post("/api/auth/login", json={"email": "jane@test.com", "password": "password123"})
    assert resp.status_code == 200
    token = resp.get_json()["token"]

    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.get_json()["email"] == "jane@test.com"


def test_me_requires_auth(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
