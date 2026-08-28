import os


def test_ingest_requires_api_key(client):
    resp = client.post("/api/opportunities/ingest", json={"title": "X", "description": "Y"})
    assert resp.status_code == 401


def test_ingest_rejects_wrong_key(client, app):
    app.config["AI_AGENT_API_KEY"] = "correct-key"
    resp = client.post(
        "/api/opportunities/ingest",
        json={"title": "X", "description": "Y"},
        headers={"X-API-Key": "wrong-key"},
    )
    assert resp.status_code == 401


def test_ingest_creates_pending_review_draft(client, app):
    app.config["AI_AGENT_API_KEY"] = "correct-key"
    resp = client.post(
        "/api/opportunities/ingest",
        json={
            "title": "Sample Agent-Found Scholarship",
            "description": "Full description here.",
            "provider": "Example Foundation",
            "official_url": "https://example.com",
            "source_url": "https://example.com/scholarship",
            "source_notes": "Confidence: 0.8. Verified page exists and describes an open scholarship.",
        },
        headers={"X-API-Key": "correct-key"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["status"] == "pending_review"
    assert data["verification_status"] == "pending"


def test_ingest_requires_title_and_description(client, app):
    app.config["AI_AGENT_API_KEY"] = "correct-key"
    resp = client.post(
        "/api/opportunities/ingest",
        json={"title": "No description"},
        headers={"X-API-Key": "correct-key"},
    )
    assert resp.status_code == 400
