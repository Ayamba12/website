from unittest.mock import MagicMock, patch

from app.extensions import db
from app.models import Opportunity, OpportunityCategory, OpportunityStatus, SourceType, VerificationStatus
from app.services import crawler_service

LISTING_HTML = """
<html><body>
<nav><a href="/category/scholarships/">Scholarships</a></nav>
<main>
  <a href="/mastercard-scholars-2027/">Mastercard Scholars Program 2027</a>
</main>
</body></html>
"""

DETAIL_HTML = """
<html>
<head>
  <title>Mastercard Scholars Program 2027 | Example Aggregator</title>
  <meta name="description" content="Fully funded scholarship for African students.">
</head>
<body><main>
  <h1>Mastercard Scholars Program 2027</h1>
  <p>Deadline: 15 December 2026 Apply now for this fully funded scholarship.</p>
</main></body>
</html>
"""


def _fake_fetch(url):
    resp = MagicMock()
    if "mastercard-scholars-2027" in url:
        resp.text = DETAIL_HTML
    else:
        resp.text = LISTING_HTML
    return resp


def test_run_crawl_creates_a_pending_review_opportunity(app):
    with app.app_context():
        with patch.object(crawler_service._Fetcher, "fetch", side_effect=_fake_fetch):
            result = crawler_service.run_crawl(max_items=4)

        assert result["created"] == 1
        assert result["skipped_duplicate"] == 0

        opp = Opportunity.query.filter_by(source_url="https://www.opportunitiesforafricans.com/mastercard-scholars-2027/").first()
        assert opp is not None
        assert opp.title == "Mastercard Scholars Program 2027"
        assert opp.status == OpportunityStatus.PENDING_REVIEW
        assert opp.verification_status == VerificationStatus.PENDING
        assert opp.source_type == SourceType.AI_AGENT
        assert opp.deadline is not None


def test_run_crawl_skips_existing_source_url(app):
    with app.app_context():
        existing = Opportunity(
            title="Already Known",
            slug="already-known",
            status=OpportunityStatus.PENDING_REVIEW,
            verification_status=VerificationStatus.PENDING,
            source_type=SourceType.AI_AGENT,
            source_url="https://www.opportunitiesforafricans.com/mastercard-scholars-2027/",
        )
        db.session.add(existing)
        db.session.commit()

        with patch.object(crawler_service._Fetcher, "fetch", side_effect=_fake_fetch):
            result = crawler_service.run_crawl(max_items=4)

        assert result["created"] == 0
        assert result["skipped_duplicate"] == 1


def test_run_crawl_matches_existing_category_case_insensitively(app):
    with app.app_context():
        category = OpportunityCategory(name="Scholarship", slug="scholarship")
        db.session.add(category)
        db.session.commit()

        with patch.object(crawler_service._Fetcher, "fetch", side_effect=_fake_fetch):
            crawler_service.run_crawl(max_items=4)

        opp = Opportunity.query.filter_by(source_url="https://www.opportunitiesforafricans.com/mastercard-scholars-2027/").first()
        assert opp.category_id == category.id


def test_run_crawl_handles_fetch_failure_without_crashing(app):
    with app.app_context():
        with patch.object(crawler_service._Fetcher, "fetch", return_value=None):
            result = crawler_service.run_crawl(max_items=4)

        assert result["created"] == 0
        assert len(result["errors"]) == 1
