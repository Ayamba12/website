from datetime import datetime, timezone
from app.extensions import db
from app.models.category import opportunity_tag_map


class OpportunityStatus:
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    PUBLISHED = "published"
    EXPIRED = "expired"
    ARCHIVED = "archived"
    REJECTED = "rejected"

    ALL = [DRAFT, PENDING_REVIEW, PUBLISHED, EXPIRED, ARCHIVED, REJECTED]


class VerificationStatus:
    UNVERIFIED = "unverified"
    PENDING = "pending"
    VERIFIED = "verified"

    ALL = [UNVERIFIED, PENDING, VERIFIED]


class SourceType:
    MANUAL = "manual"
    AI_AGENT = "ai_agent"
    USER_SUBMISSION = "user_submission"

    ALL = [MANUAL, AI_AGENT, USER_SUBMISSION]


class Opportunity(db.Model):
    __tablename__ = "opportunities"

    id = db.Column(db.Integer, primary_key=True)

    # Basic information
    title = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(300), unique=True, nullable=False, index=True)
    short_description = db.Column(db.String(500))
    description = db.Column(db.Text)
    provider = db.Column(db.String(200))
    category_id = db.Column(db.Integer, db.ForeignKey("opportunity_categories.id"))
    featured_image_url = db.Column(db.String(500))
    organization_logo_url = db.Column(db.String(500))

    # Eligibility
    target_audience = db.Column(db.String(200))  # student, teacher, graduate, other
    eligible_countries = db.Column(db.Text)
    education_level = db.Column(db.String(150))
    field_of_study = db.Column(db.String(150))
    age_requirements = db.Column(db.String(150))
    other_eligibility = db.Column(db.Text)
    country = db.Column(db.String(100))
    location = db.Column(db.String(200))
    is_online = db.Column(db.Boolean, default=False)

    # Funding
    funding_type = db.Column(db.String(60))
    funding_details = db.Column(db.Text)
    application_fee = db.Column(db.String(100))
    benefits = db.Column(db.Text)

    # Dates
    application_opens_at = db.Column(db.DateTime)
    deadline = db.Column(db.DateTime, index=True)
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)

    # Application
    official_url = db.Column(db.String(500))
    application_url = db.Column(db.String(500))
    requirements = db.Column(db.Text)
    required_documents = db.Column(db.Text)
    application_steps = db.Column(db.Text)

    # Publishing
    status = db.Column(db.String(30), default=OpportunityStatus.DRAFT, nullable=False, index=True)
    featured = db.Column(db.Boolean, default=False, nullable=False, index=True)
    is_expired = db.Column(db.Boolean, default=False, nullable=False, index=True)
    scheduled_publish_at = db.Column(db.DateTime)

    # Verification / source
    verification_status = db.Column(
        db.String(30), default=VerificationStatus.UNVERIFIED, nullable=False, index=True
    )
    source_organization = db.Column(db.String(200))
    source_url = db.Column(db.String(500))
    source_notes = db.Column(db.Text)
    source_checked_at = db.Column(db.DateTime)
    source_type = db.Column(db.String(30), default=SourceType.MANUAL, nullable=False)
    raw_source_data = db.Column(db.Text)  # raw scraped payload, for AI-agent submissions

    # Audit trail
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    updated_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    published_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    verified_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    published_at = db.Column(db.DateTime)
    verified_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    tags = db.relationship(
        "OpportunityTag", secondary=opportunity_tag_map, backref="opportunities"
    )
    saved_by = db.relationship(
        "SavedOpportunity", backref="opportunity", lazy="dynamic", cascade="all, delete-orphan"
    )
    reports = db.relationship(
        "OpportunityReport", backref="opportunity", lazy="dynamic", cascade="all, delete-orphan"
    )

    def to_dict(self, detailed=False):
        data = {
            "id": self.id,
            "title": self.title,
            "slug": self.slug,
            "short_description": self.short_description,
            "provider": self.provider,
            "category": self.category.to_dict() if self.category else None,
            "featured_image_url": self.featured_image_url,
            "organization_logo_url": self.organization_logo_url,
            "target_audience": self.target_audience,
            "country": self.country,
            "location": self.location,
            "is_online": self.is_online,
            "education_level": self.education_level,
            "field_of_study": self.field_of_study,
            "funding_type": self.funding_type,
            "application_fee": self.application_fee,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "status": self.status,
            "featured": self.featured,
            "is_expired": self.is_expired,
            "verification_status": self.verification_status,
            "tags": [t.to_dict() for t in self.tags],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if detailed:
            data.update(
                {
                    "description": self.description,
                    "eligible_countries": self.eligible_countries,
                    "age_requirements": self.age_requirements,
                    "other_eligibility": self.other_eligibility,
                    "funding_details": self.funding_details,
                    "benefits": self.benefits,
                    "application_opens_at": self.application_opens_at.isoformat()
                    if self.application_opens_at
                    else None,
                    "end_date": self.end_date.isoformat() if self.end_date else None,
                    "official_url": self.official_url,
                    "application_url": self.application_url,
                    "requirements": self.requirements,
                    "required_documents": self.required_documents,
                    "application_steps": self.application_steps,
                    "source_organization": self.source_organization,
                    "source_url": self.source_url,
                    "source_notes": self.source_notes,
                    "source_checked_at": self.source_checked_at.isoformat()
                    if self.source_checked_at
                    else None,
                    "source_type": self.source_type,
                    "published_at": self.published_at.isoformat() if self.published_at else None,
                    "verified_at": self.verified_at.isoformat() if self.verified_at else None,
                    "scheduled_publish_at": self.scheduled_publish_at.isoformat()
                    if self.scheduled_publish_at
                    else None,
                }
            )
        return data
