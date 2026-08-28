from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from sqlalchemy import or_
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import (
    Opportunity,
    OpportunityStatus,
    VerificationStatus,
    OpportunityCategory,
    OpportunityTag,
    SourceType,
)
from app.auth.decorators import admin_required, api_key_required, get_current_user
from app.utils.slugify import unique_slug
from app.utils.pagination import paginate_query
from app.services.opportunity_service import sync_expired_opportunities, days_remaining

bp = Blueprint("opportunities", __name__, url_prefix="/api/opportunities")

FILTER_FIELDS = ["country", "education_level", "funding_type", "field_of_study", "target_audience"]


def _apply_public_filters(query):
    args = request.args

    search = args.get("search")
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                Opportunity.title.ilike(like),
                Opportunity.short_description.ilike(like),
                Opportunity.provider.ilike(like),
            )
        )

    category_slug = args.get("category")
    if category_slug:
        query = query.join(OpportunityCategory).filter(OpportunityCategory.slug == category_slug)

    for field in FILTER_FIELDS:
        value = args.get(field)
        if value:
            query = query.filter(getattr(Opportunity, field).ilike(value))

    if args.get("fully_funded") == "true":
        query = query.filter(Opportunity.funding_type.ilike("fully funded"))

    if args.get("online") == "true":
        query = query.filter(Opportunity.is_online.is_(True))

    if args.get("deadline_before"):
        try:
            dt = datetime.fromisoformat(args["deadline_before"])
            query = query.filter(Opportunity.deadline <= dt)
        except ValueError:
            pass

    include_expired = args.get("include_expired") == "true"
    if not include_expired:
        query = query.filter(Opportunity.is_expired.is_(False))

    return query


def _serialize_card(opp: Opportunity):
    data = opp.to_dict()
    data["days_remaining"] = days_remaining(opp)
    return data


def _with_relations(query):
    """Eager-load category/tags so serializing a list doesn't trigger an N+1 —
    one extra query per opportunity for each relationship, each a full
    round-trip to the database. Cheap locally, very noticeable over a real
    network connection to a remote Postgres."""
    return query.options(selectinload(Opportunity.category), selectinload(Opportunity.tags))


@bp.get("")
def list_opportunities():
    sync_expired_opportunities()
    query = Opportunity.query.filter(Opportunity.status == OpportunityStatus.PUBLISHED)
    query = _with_relations(query)
    query = _apply_public_filters(query)

    sort = request.args.get("sort", "-created_at")
    if sort == "deadline":
        query = query.order_by(Opportunity.deadline.asc())
    elif sort == "-deadline":
        query = query.order_by(Opportunity.deadline.desc())
    else:
        query = query.order_by(Opportunity.created_at.desc())

    result = paginate_query(query, serializer=_serialize_card)
    return jsonify(result)


@bp.get("/featured")
def featured_opportunities():
    sync_expired_opportunities()
    query = _with_relations(
        Opportunity.query.filter(
            Opportunity.status == OpportunityStatus.PUBLISHED,
            Opportunity.featured.is_(True),
            Opportunity.is_expired.is_(False),
        )
    ).order_by(Opportunity.created_at.desc()).limit(12)
    return jsonify([_serialize_card(o) for o in query.all()])


@bp.get("/deadlines")
def upcoming_deadlines():
    sync_expired_opportunities()
    query = _with_relations(
        Opportunity.query.filter(
            Opportunity.status == OpportunityStatus.PUBLISHED,
            Opportunity.is_expired.is_(False),
            Opportunity.deadline.isnot(None),
        )
    ).order_by(Opportunity.deadline.asc()).limit(20)
    return jsonify([_serialize_card(o) for o in query.all()])


@bp.get("/admin/list")
@admin_required
def admin_list_opportunities(**kwargs):
    sync_expired_opportunities()
    query = _with_relations(Opportunity.query)

    status = request.args.get("status")
    if status:
        query = query.filter(Opportunity.status == status)

    verification_status = request.args.get("verification_status")
    if verification_status:
        query = query.filter(Opportunity.verification_status == verification_status)

    if request.args.get("featured") == "true":
        query = query.filter(Opportunity.featured.is_(True))

    search = request.args.get("search")
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(Opportunity.title.ilike(like), Opportunity.provider.ilike(like))
        )

    query = query.order_by(Opportunity.updated_at.desc())
    result = paginate_query(query, serializer=lambda o: o.to_dict())
    return jsonify(result)


@bp.get("/admin/<int:opportunity_id>")
@admin_required
def admin_get_opportunity(opportunity_id, **kwargs):
    opp = _with_relations(Opportunity.query).get_or_404(opportunity_id)
    return jsonify(opp.to_dict(detailed=True))


@bp.get("/<slug>")
def get_opportunity(slug):
    sync_expired_opportunities()
    opp = _with_relations(Opportunity.query).filter_by(slug=slug).first()
    if not opp:
        return jsonify({"error": "Opportunity not found"}), 404

    if opp.status != OpportunityStatus.PUBLISHED:
        user = get_current_user()
        if not user or not user.is_admin():
            return jsonify({"error": "Opportunity not found"}), 404

    data = opp.to_dict(detailed=True)
    data["days_remaining"] = days_remaining(opp)
    return jsonify(data)


def _apply_opportunity_fields(opp: Opportunity, data: dict):
    simple_fields = [
        "title", "short_description", "description", "provider",
        "featured_image_url", "organization_logo_url",
        "target_audience", "eligible_countries", "education_level", "field_of_study",
        "age_requirements", "other_eligibility", "country", "location", "is_online",
        "funding_type", "funding_details", "application_fee", "benefits",
        "official_url", "application_url", "requirements", "required_documents",
        "application_steps", "source_organization", "source_url", "source_notes",
        "source_type", "raw_source_data",
    ]
    for field in simple_fields:
        if field in data:
            setattr(opp, field, data[field])

    date_fields = ["application_opens_at", "deadline", "start_date", "end_date", "scheduled_publish_at"]
    for field in date_fields:
        if field in data and data[field]:
            try:
                setattr(opp, field, datetime.fromisoformat(data[field]))
            except (ValueError, TypeError):
                pass

    if "category_id" in data:
        opp.category_id = data["category_id"]

    if "tags" in data and isinstance(data["tags"], list):
        tags = []
        for name in data["tags"]:
            name = name.strip()
            if not name:
                continue
            tag = OpportunityTag.query.filter_by(name=name).first()
            if not tag:
                tag = OpportunityTag(name=name, slug=unique_slug(name, OpportunityTag))
                db.session.add(tag)
            tags.append(tag)
        opp.tags = tags


@bp.post("")
@admin_required
def create_opportunity(**kwargs):
    data = request.get_json(silent=True) or {}
    if not data.get("title"):
        return jsonify({"error": "Title is required"}), 400

    opp = Opportunity(
        title=data["title"],
        slug=unique_slug(data.get("slug") or data["title"], Opportunity),
        status=data.get("status", OpportunityStatus.DRAFT),
        verification_status=data.get("verification_status", VerificationStatus.UNVERIFIED),
        created_by_id=request.current_user.id,
    )
    _apply_opportunity_fields(opp, data)
    db.session.add(opp)
    db.session.commit()
    return jsonify(opp.to_dict(detailed=True)), 201


@bp.put("/<int:opportunity_id>")
@admin_required
def update_opportunity(opportunity_id):
    opp = Opportunity.query.get_or_404(opportunity_id)
    data = request.get_json(silent=True) or {}

    if "title" in data and data["title"] != opp.title and data.get("regenerate_slug"):
        opp.slug = unique_slug(data["title"], Opportunity, exclude_id=opp.id)

    _apply_opportunity_fields(opp, data)
    opp.updated_by_id = request.current_user.id
    db.session.commit()
    return jsonify(opp.to_dict(detailed=True))


@bp.delete("/<int:opportunity_id>")
@admin_required
def delete_opportunity(opportunity_id):
    opp = Opportunity.query.get_or_404(opportunity_id)
    db.session.delete(opp)
    db.session.commit()
    return jsonify({"message": "Opportunity deleted"})


@bp.post("/<int:opportunity_id>/duplicate")
@admin_required
def duplicate_opportunity(opportunity_id):
    original = Opportunity.query.get_or_404(opportunity_id)
    copy = Opportunity(
        title=f"{original.title} (Copy)",
        slug=unique_slug(f"{original.title}-copy", Opportunity),
        short_description=original.short_description,
        description=original.description,
        provider=original.provider,
        category_id=original.category_id,
        featured_image_url=original.featured_image_url,
        organization_logo_url=original.organization_logo_url,
        target_audience=original.target_audience,
        eligible_countries=original.eligible_countries,
        education_level=original.education_level,
        field_of_study=original.field_of_study,
        age_requirements=original.age_requirements,
        other_eligibility=original.other_eligibility,
        country=original.country,
        location=original.location,
        is_online=original.is_online,
        funding_type=original.funding_type,
        funding_details=original.funding_details,
        application_fee=original.application_fee,
        benefits=original.benefits,
        official_url=original.official_url,
        application_url=original.application_url,
        requirements=original.requirements,
        required_documents=original.required_documents,
        application_steps=original.application_steps,
        source_organization=original.source_organization,
        source_url=original.source_url,
        status=OpportunityStatus.DRAFT,
        verification_status=VerificationStatus.UNVERIFIED,
        tags=original.tags,
        created_by_id=request.current_user.id,
    )
    db.session.add(copy)
    db.session.commit()
    return jsonify(copy.to_dict(detailed=True)), 201


@bp.post("/<int:opportunity_id>/status")
@admin_required
def change_status(opportunity_id):
    opp = Opportunity.query.get_or_404(opportunity_id)
    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    if new_status not in OpportunityStatus.ALL:
        return jsonify({"error": "Invalid status"}), 400

    opp.status = new_status
    now = datetime.now(timezone.utc)
    if new_status == OpportunityStatus.PUBLISHED:
        opp.published_at = now
        opp.published_by_id = request.current_user.id
        opp.is_expired = False
    db.session.commit()
    return jsonify(opp.to_dict(detailed=True))


@bp.post("/<int:opportunity_id>/verify")
@admin_required
def verify_opportunity(opportunity_id):
    opp = Opportunity.query.get_or_404(opportunity_id)
    data = request.get_json(silent=True) or {}
    new_status = data.get("verification_status", VerificationStatus.VERIFIED)
    if new_status not in VerificationStatus.ALL:
        return jsonify({"error": "Invalid verification status"}), 400

    opp.verification_status = new_status
    opp.verified_by_id = request.current_user.id
    opp.verified_at = datetime.now(timezone.utc)
    if "source_notes" in data:
        opp.source_notes = data["source_notes"]
    opp.source_checked_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(opp.to_dict(detailed=True))


@bp.post("/<int:opportunity_id>/feature")
@admin_required
def toggle_feature(opportunity_id):
    opp = Opportunity.query.get_or_404(opportunity_id)
    data = request.get_json(silent=True) or {}
    opp.featured = bool(data.get("featured", True))
    db.session.commit()
    return jsonify(opp.to_dict(detailed=True))


@bp.post("/bulk")
@admin_required
def bulk_action():
    data = request.get_json(silent=True) or {}
    ids = data.get("ids") or []
    action = data.get("action")

    opps = Opportunity.query.filter(Opportunity.id.in_(ids)).all()
    if not opps:
        return jsonify({"error": "No matching opportunities"}), 404

    now = datetime.now(timezone.utc)
    if action == "publish":
        for o in opps:
            o.status = OpportunityStatus.PUBLISHED
            o.published_at = now
            o.published_by_id = request.current_user.id
    elif action == "unpublish":
        for o in opps:
            o.status = OpportunityStatus.DRAFT
    elif action == "archive":
        for o in opps:
            o.status = OpportunityStatus.ARCHIVED
    elif action == "verify":
        for o in opps:
            o.verification_status = VerificationStatus.VERIFIED
            o.verified_by_id = request.current_user.id
            o.verified_at = now
    elif action == "unverify":
        for o in opps:
            o.verification_status = VerificationStatus.UNVERIFIED
    elif action == "delete":
        for o in opps:
            db.session.delete(o)
    else:
        return jsonify({"error": "Unknown action"}), 400

    db.session.commit()
    return jsonify({"message": f"Bulk action '{action}' applied to {len(opps)} opportunities"})


INGEST_FIELDS = [
    "title", "provider", "short_description", "description",
    "target_audience", "country", "location", "is_online",
    "education_level", "field_of_study", "funding_type", "funding_details",
    "application_fee", "official_url", "application_url", "requirements",
    "required_documents", "eligible_countries", "other_eligibility",
]


@bp.post("/ingest")
@api_key_required
def ingest_opportunity():
    """Machine-submission endpoint for the local scholarship-finding agent.

    Never publishes automatically: every submission lands as pending_review /
    unverified with source_type=ai_agent, exactly like any other unverified
    lead, so a human always reviews before it goes live.
    """
    data = request.get_json(silent=True) or {}
    if not data.get("title"):
        return jsonify({"error": "title is required"}), 400
    if not data.get("description") and not data.get("short_description"):
        return jsonify({"error": "description or short_description is required"}), 400

    opp = Opportunity(
        title=data["title"],
        slug=unique_slug(data["title"], Opportunity),
        status=OpportunityStatus.PENDING_REVIEW,
        verification_status=VerificationStatus.PENDING,
        source_type=SourceType.AI_AGENT,
    )
    for field in INGEST_FIELDS:
        if field in data:
            setattr(opp, field, data[field])

    if data.get("deadline"):
        try:
            opp.deadline = datetime.fromisoformat(data["deadline"])
        except (ValueError, TypeError):
            pass

    if data.get("source_url"):
        opp.source_url = data["source_url"]
    if data.get("source_organization"):
        opp.source_organization = data["source_organization"]
    if data.get("source_notes"):
        opp.source_notes = data["source_notes"]
    if data.get("raw_source_data"):
        opp.raw_source_data = data["raw_source_data"]
    opp.source_checked_at = datetime.now(timezone.utc)

    category_name = (data.get("category_name") or "").strip()
    if category_name:
        category = OpportunityCategory.query.filter(
            OpportunityCategory.name.ilike(category_name)
        ).first()
        if category:
            opp.category_id = category.id

    db.session.add(opp)
    db.session.commit()
    return jsonify(opp.to_dict(detailed=True)), 201
