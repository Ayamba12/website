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
  <p>The Mastercard Scholars Program supports academically talented young Africans
     who face financial constraints from accessing quality secondary and university
     education. Scholars receive comprehensive support including tuition, accommodation,
     travel and a living stipend for the full duration of their studies.</p>
  <p>Applicants must be citizens of an African country, demonstrate strong academic
     performance, and show clear leadership potential within their community. Priority
     is given to applicants from underserved regions who intend to return home after
     completing their studies to contribute to local development.</p>
  <p>The application process involves an online form, two reference letters, a
     personal statement, and for shortlisted candidates, a virtual interview with
     the selection committee before final offers are made in the following term.</p>
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

        # short_description and description must NOT be the same text —
        # the admin SEO checker flags descriptions under ~60 words, and a
        # meta description alone is nowhere near that.
        assert opp.short_description == "Fully funded scholarship for African students."
        assert opp.description != opp.short_description
        assert len(opp.description.split()) >= 60


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


def test_extract_fields_separates_short_and_full_description():
    fields = crawler_service._extract_fields(DETAIL_HTML)

    assert fields["short_description"] == "Fully funded scholarship for African students."
    assert fields["full_description"] != fields["short_description"]
    assert "leadership potential" in fields["full_description"]
    assert len(fields["full_description"].split()) >= 60


def test_extract_fields_falls_back_to_short_description_when_no_paragraphs():
    html = (
        "<html><head><title>Test</title>"
        '<meta name="description" content="A short summary only.">'
        "</head><body></body></html>"
    )
    fields = crawler_service._extract_fields(html)
    assert fields["full_description"] == "A short summary only."
