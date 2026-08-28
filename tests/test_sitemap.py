from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models import Opportunity, OpportunityStatus, VerificationStatus


def test_sitemap_includes_static_routes(client):
    resp = client.get("/sitemap.xml")
    assert resp.status_code == 200
    assert resp.content_type.startswith("application/xml")
    body = resp.get_data(as_text=True)
    assert "<urlset" in body
    assert "/opportunities</loc>" in body
    assert "/teachers</loc>" in body


def test_sitemap_includes_published_opportunity_but_not_draft(app, client):
    with app.app_context():
        published = Opportunity(
            title="Published One",
            slug="published-one",
            status=OpportunityStatus.PUBLISHED,
            verification_status=VerificationStatus.VERIFIED,
            deadline=datetime.now(timezone.utc) + timedelta(days=10),
        )
        draft = Opportunity(
            title="Draft One",
            slug="draft-one",
            status=OpportunityStatus.DRAFT,
            verification_status=VerificationStatus.UNVERIFIED,
        )
        db.session.add_all([published, draft])
        db.session.commit()

    resp = client.get("/sitemap.xml")
    body = resp.get_data(as_text=True)
    assert "/opportunities/published-one</loc>" in body
    assert "/opportunities/draft-one</loc>" not in body
