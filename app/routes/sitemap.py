from flask import Blueprint, Response, current_app

from app.models import (
    Opportunity,
    OpportunityStatus,
    StudyMaterial,
    StudyMaterialStatus,
)

# Registered without a URL prefix — sitemap.xml and robots.txt are expected
# at the site root by convention, not under /api.
bp = Blueprint("sitemap", __name__)


def _url_entry(loc, lastmod=None, changefreq="weekly", priority="0.5"):
    lastmod_xml = f"<lastmod>{lastmod.date().isoformat()}</lastmod>" if lastmod else ""
    return (
        f"<url><loc>{loc}</loc>{lastmod_xml}"
        f"<changefreq>{changefreq}</changefreq><priority>{priority}</priority></url>"
    )


@bp.get("/sitemap.xml")
def sitemap():
    """Generated from live published content, not a static file — new
    opportunities and study materials show up automatically, no rebuild
    needed. Served at the frontend's own domain via a Vercel rewrite
    (see frontend/vercel.json), since that's where crawlers expect it."""
    base = current_app.config.get("FRONTEND_URL", "").rstrip("/")
    entries = [
        _url_entry(f"{base}/", changefreq="daily", priority="1.0"),
        _url_entry(f"{base}/opportunities", changefreq="daily", priority="0.9"),
        _url_entry(f"{base}/teachers", changefreq="weekly", priority="0.8"),
        _url_entry(f"{base}/teachers/questions", changefreq="weekly", priority="0.6"),
        _url_entry(f"{base}/teachers/study-materials", changefreq="weekly", priority="0.6"),
    ]

    opportunities = Opportunity.query.filter_by(status=OpportunityStatus.PUBLISHED).all()
    for o in opportunities:
        entries.append(
            _url_entry(f"{base}/opportunities/{o.slug}", lastmod=o.updated_at, priority="0.7")
        )

    materials = StudyMaterial.query.filter_by(status=StudyMaterialStatus.PUBLISHED).all()
    for m in materials:
        entries.append(
            _url_entry(
                f"{base}/teachers/study-materials/{m.slug}", lastmod=m.updated_at, priority="0.5"
            )
        )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(entries)
        + "</urlset>"
    )
    return Response(xml, mimetype="application/xml")
