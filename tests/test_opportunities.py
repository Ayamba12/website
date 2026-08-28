from datetime import datetime, timedelta, timezone
from app.extensions import db
from app.models import Opportunity, OpportunityStatus, VerificationStatus


def _create_published(app, title="Test Scholarship", deadline_delta=30):
    with app.app_context():
        opp = Opportunity(
            title=title,
            slug=title.lower().replace(" ", "-"),
            status=OpportunityStatus.PUBLISHED,
            verification_status=VerificationStatus.VERIFIED,
            deadline=datetime.now(timezone.utc) + timedelta(days=deadline_delta),
            country="Ghana",
            funding_type="Fully funded",
        )
        db.session.add(opp)
        db.session.commit()
        return opp.id


def test_admin_required_for_create(client):
    resp = client.post("/api/opportunities", json={"title": "New Opportunity"})
    assert resp.status_code == 401


def test_create_and_publish_opportunity(client, auth_header):
    resp = client.post(
        "/api/opportunities",
        json={"title": "Sample Scholarship", "status": "draft"},
        headers=auth_header,
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["status"] == "draft"

    opp_id = data["id"]
    resp = client.get(f"/api/opportunities/{data['slug']}")
    assert resp.status_code == 404  # draft, not published, no auth

    resp = client.post(
        f"/api/opportunities/{opp_id}/status", json={"status": "published"}, headers=auth_header
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "published"

    resp = client.get(f"/api/opportunities/{data['slug']}")
    assert resp.status_code == 200


def test_list_opportunities_excludes_expired(app, client):
    _create_published(app, "Active Opportunity", deadline_delta=30)
    _create_published(app, "Expiring Opportunity", deadline_delta=-5)

    resp = client.get("/api/opportunities")
    assert resp.status_code == 200
    titles = [o["title"] for o in resp.get_json()["items"]]
    assert "Active Opportunity" in titles
    assert "Expiring Opportunity" not in titles


def test_duplicate_opportunity(client, auth_header):
    resp = client.post("/api/opportunities", json={"title": "Annual Award"}, headers=auth_header)
    opp_id = resp.get_json()["id"]

    resp = client.post(f"/api/opportunities/{opp_id}/duplicate", headers=auth_header)
    assert resp.status_code == 201
    dup = resp.get_json()
    assert dup["id"] != opp_id
    assert dup["status"] == "draft"
    assert "(Copy)" in dup["title"]
