"""Lightweight, opportunity-only crawler that runs inside a single admin
request (Render's free tier has no background workers, so this must stay
fast — capped at a handful of items per run).

This is a trimmed port of the standalone content_agent/ project's Stage 1
pipeline, adapted to run inside the Flask backend and dedupe against the
real database (content_agent's SQLite dedup cache wouldn't survive Render's
ephemeral filesystem between deploys). content_agent/ remains the
full-featured tool (teacher questions, PDFs, etc.) for local/manual use.

Like the existing /api/opportunities/ingest endpoint, this never publishes
anything — everything it creates lands as pending_review/unverified with
source_type=ai_agent for a human to review.
"""

import logging
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from app.extensions import db
from app.models import Opportunity, OpportunityCategory, OpportunityStatus, SourceType, VerificationStatus
from app.utils.slugify import unique_slug

logger = logging.getLogger("crawler_service")

USER_AGENT = "OpportunityHubContentAgent/0.1 (+https://ndeogtie.vercel.app; contact: ayambaisaac2@gmail.com)"
REQUEST_TIMEOUT_SECONDS = 15
MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = 2
PER_DOMAIN_DELAY_SECONDS = 3

# Only sources whose robots.txt has been manually checked and found
# permissive belong here — same rule as content_agent/config/sources.yaml.
# Checked and deliberately left OUT as of 2026-08-28:
#   - opportunitydesk.org: robots.txt reserves rights under the EU Copyright
#     Directive's text-and-data-mining opt-out (Article 4) rather than a
#     plain allow/disallow — ambiguous enough to skip rather than assume.
#   - scholarship-positions.com: robots.txt request itself is blocked by a
#     Cloudflare bot challenge — respecting that, not working around it.
#   - youthop.com: /robots.txt redirects to the homepage instead of a real
#     robots.txt or a 404 — too ambiguous to treat as "unrestricted."
CRAWLER_SOURCES = [
    {
        "name": "opportunities_for_africans",
        "url": "https://www.opportunitiesforafricans.com/category/scholarships/",
    },
    {
        "name": "opportunities_guide",
        "url": "https://opportunitiesguide.com/category/scholarships/",
    },
    {
        "name": "after_school_africa",
        "url": "https://www.afterschoolafrica.com/scholarship/",
    },
    {
        "name": "scholars4dev",
        "url": "https://www.scholars4dev.com/",
    },
]

OPPORTUNITY_KEYWORDS = [
    "scholarship", "fellowship", "grant", "internship", "job", "vacancy",
    "admission", "course", "competition", "programme", "program",
    "opportunity", "bursary", "award", "training", "exchange",
]
EXCLUDED_PATH_MARKERS = [
    "/category/", "/tag/", "/tags/", "/author/", "/page/",
    "/wp-content/", "/wp-json/", "/feed/",
]

CATEGORY_KEYWORDS = {
    "Scholarship": ["scholarship", "scholarships"],
    "Fellowship": ["fellowship", "fellowships"],
    "Grant": ["grant", "grants", "funding opportunity"],
    "Internship": ["internship", "internships"],
    "Job": ["vacancy", "job opening", "recruitment", "hiring"],
    "Competition": ["competition", "challenge", "contest"],
}

_MONTHS = (
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?"
    r"|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
)
DEADLINE_PATTERN = re.compile(
    r"(deadline|closing date|apply before|application closes)[^.\n]{0,60}", re.IGNORECASE,
)
DATE_TOKEN_PATTERN = re.compile(
    rf"\b(?:\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{_MONTHS})\s+\d{{4}}"
    rf"|(?:{_MONTHS})\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}})\b",
    re.IGNORECASE,
)


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _strip_site_suffix(title: str) -> str:
    if " | " in title:
        head, _, _tail = title.rpartition(" | ")
        if head:
            return head
    return title


class _Fetcher:
    """Robots.txt-aware, per-domain rate-limited, retrying HTTP fetcher —
    same rules as content_agent/crawlers/base_crawler.py."""

    def __init__(self):
        self._robots_cache: dict = {}
        self._last_request_at: dict = {}
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT

    def _robots_for(self, url: str) -> RobotFileParser:
        domain = urlparse(url).netloc
        if domain not in self._robots_cache:
            scheme = urlparse(url).scheme
            robots_url = f"{scheme}://{domain}/robots.txt"
            rp = RobotFileParser()
            rp.set_url(robots_url)
            try:
                resp = self.session.get(robots_url, timeout=REQUEST_TIMEOUT_SECONDS)
                if resp.status_code == 404:
                    rp.parse([])
                elif resp.ok:
                    rp.parse(resp.text.splitlines())
                else:
                    rp.parse(["User-agent: *", "Disallow: /"])
            except requests.RequestException:
                logger.warning("Could not fetch robots.txt for %s; proceeding cautiously", domain)
            self._robots_cache[domain] = rp
        return self._robots_cache[domain]

    def can_fetch(self, url: str) -> bool:
        try:
            return self._robots_for(url).can_fetch(USER_AGENT, url)
        except Exception:
            return True

    def _respect_rate_limit(self, url: str) -> None:
        domain = urlparse(url).netloc
        last = self._last_request_at.get(domain)
        if last is not None:
            wait = PER_DOMAIN_DELAY_SECONDS - (time.monotonic() - last)
            if wait > 0:
                time.sleep(wait)
        self._last_request_at[domain] = time.monotonic()

    def fetch(self, url: str) -> requests.Response | None:
        if not self.can_fetch(url):
            logger.warning("robots.txt disallows fetching %s", url)
            return None

        for attempt in range(MAX_RETRIES + 1):
            self._respect_rate_limit(url)
            try:
                resp = self.session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
                resp.raise_for_status()
                return resp
            except requests.RequestException as exc:
                logger.warning("Fetch failed (attempt %d/%d) for %s: %s", attempt + 1, MAX_RETRIES + 1, url, exc)
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_BACKOFF_SECONDS * (2 ** attempt))
        return None


def _discover_candidate_links(listing_url: str, html: str, max_items: int) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    # Site navigation links (e.g. a "WhatsApp alerts" signup page linked from
    # the header nav) can have a long, real-looking slug and match a keyword
    # by coincidence ("opportunity") without being an opportunity listing at
    # all. Structural nav/header/footer regions are never where individual
    # posts live, so drop them before even considering their links.
    for tag in soup(["nav", "header", "footer"]):
        tag.decompose()
    domain = urlparse(listing_url).netloc
    seen: set[str] = set()
    candidates: list[str] = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#") or href.startswith("mailto:"):
            continue

        full_url = urljoin(listing_url, href).split("#", 1)[0].rstrip("/")
        if urlparse(full_url).netloc != domain:
            continue
        if full_url.lower().endswith(".pdf"):
            continue  # this lightweight service handles HTML pages only

        path = urlparse(full_url).path.lower()
        if any(marker in path for marker in EXCLUDED_PATH_MARKERS):
            continue

        # A same-domain link whose final slug is only 1-2 words (e.g.
        # "/scholarships") is almost always a category/hub/index page, never
        # a single opportunity post — real posts have long descriptive slugs
        # (e.g. "kfw-eac-masters-scholarships-2026-2027"). Catches hub pages
        # that don't happen to sit under "/category/" like the ones
        # EXCLUDED_PATH_MARKERS already filters.
        last_segment = path.rsplit("/", 1)[-1]
        if last_segment and len(last_segment.split("-")) < 3:
            continue

        text = (a.get_text() or "").strip().lower()
        haystack = f"{text} {full_url.lower()}"
        if not any(kw in haystack for kw in OPPORTUNITY_KEYWORDS):
            continue

        if full_url in seen:
            continue
        seen.add(full_url)
        candidates.append(full_url)
        if len(candidates) >= max_items:
            break

    return candidates


def _guess_category_name(text: str) -> str | None:
    lowered = text.lower()
    best_name, best_hits = None, 0
    for name, keywords in CATEGORY_KEYWORDS.items():
        hits = sum(lowered.count(kw) for kw in keywords)
        if hits > best_hits:
            best_name, best_hits = name, hits
    return best_name


def _guess_deadline(text: str) -> datetime | None:
    match = DEADLINE_PATTERN.search(text)
    if not match:
        return None
    date_match = DATE_TOKEN_PATTERN.search(_clean_text(match.group(0)))
    if not date_match:
        return None
    try:
        return dateparser.parse(date_match.group(0))
    except (ValueError, OverflowError):
        return None


def _extract_short_description(soup: BeautifulSoup) -> str:
    """A concise ~1-2 sentence summary for short_description (the SEO meta
    description field) — the page's own meta description if present, since
    site owners usually already write these to a sensible length."""
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        return _clean_text(meta["content"])
    p = soup.find("p")
    return _clean_text(p.get_text()) if p else ""


def _extract_full_description(soup: BeautifulSoup) -> str:
    """The full description field needs real substance (the admin SEO
    checker flags anything under ~60 words) — a single meta description or
    first paragraph is nowhere near enough, so this joins every paragraph
    on the page instead, capped to a sane length."""
    paragraphs = [_clean_text(p.get_text()) for p in soup.find_all("p")]
    paragraphs = [p for p in paragraphs if p]
    return " ".join(paragraphs)[:3000]


def _extract_fields(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    title = _strip_site_suffix(_clean_text(soup.title.string)) if soup.title and soup.title.string else ""
    if not title:
        h1 = soup.find("h1")
        title = _clean_text(h1.get_text()) if h1 else ""

    short_description = _extract_short_description(soup)
    full_description = _extract_full_description(soup)
    if not full_description:
        full_description = short_description  # last-resort fallback, better than nothing

    body_text = _clean_text(soup.get_text(" "))
    category_name = _guess_category_name(f"{title} {short_description} {body_text[:2000]}")
    deadline = _guess_deadline(body_text)

    return {
        "title": title,
        "short_description": short_description,
        "full_description": full_description,
        "category_name": category_name,
        "deadline": deadline,
    }


def run_crawl(max_items: int = 4) -> dict:
    """Crawls the configured sources, capped at `max_items` new opportunities
    total. Skips anything whose source_url already exists in the database —
    the database itself is the dedup memory (a local cache file wouldn't
    survive Render's ephemeral filesystem)."""
    fetcher = _Fetcher()
    created = []
    skipped_duplicate = 0
    errors = []

    for source in CRAWLER_SOURCES:
        if len(created) >= max_items:
            break

        listing_resp = fetcher.fetch(source["url"])
        if listing_resp is None:
            errors.append(f"{source['name']}: could not fetch listing page")
            continue

        remaining = max_items - len(created)
        candidate_urls = _discover_candidate_links(source["url"], listing_resp.text, remaining)

        for url in candidate_urls:
            if len(created) >= max_items:
                break

            if Opportunity.query.filter_by(source_url=url).first():
                skipped_duplicate += 1
                continue

            detail_resp = fetcher.fetch(url)
            if detail_resp is None:
                errors.append(f"{url}: could not fetch")
                continue

            try:
                fields = _extract_fields(detail_resp.text)
            except Exception as exc:
                logger.exception("Failed to extract %s", url)
                errors.append(f"{url}: {exc}")
                continue

            if not fields["title"]:
                errors.append(f"{url}: no title found, skipped")
                continue

            category = None
            if fields["category_name"]:
                category = OpportunityCategory.query.filter(
                    OpportunityCategory.name.ilike(fields["category_name"])
                ).first()

            opp = Opportunity(
                title=fields["title"],
                slug=unique_slug(fields["title"], Opportunity),
                short_description=fields["short_description"] or None,
                description=fields["full_description"] or None,
                status=OpportunityStatus.PENDING_REVIEW,
                verification_status=VerificationStatus.PENDING,
                source_type=SourceType.AI_AGENT,
                source_url=url,
                source_organization=source["name"],
                source_checked_at=datetime.now(timezone.utc),
                deadline=fields["deadline"],
                category_id=category.id if category else None,
            )
            db.session.add(opp)
            created.append(opp)

        db.session.commit()

    return {
        "created": len(created),
        "created_titles": [o.title for o in created],
        "skipped_duplicate": skipped_duplicate,
        "errors": errors,
    }
