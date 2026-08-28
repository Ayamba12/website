from datetime import datetime, timezone
from app.extensions import db


class SavedOpportunity(db.Model):
    __tablename__ = "saved_opportunities"
    __table_args__ = (db.UniqueConstraint("user_id", "opportunity_id", name="uq_user_opportunity"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    opportunity_id = db.Column(db.Integer, db.ForeignKey("opportunities.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "opportunity": self.opportunity.to_dict() if self.opportunity else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ReminderStatus:
    PENDING = "pending"
    SENT = "sent"
    CANCELLED = "cancelled"


class ReminderPreference(db.Model):
    __tablename__ = "reminder_preferences"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    opportunity_id = db.Column(db.Integer, db.ForeignKey("opportunities.id"), nullable=False)
    reminder_days = db.Column(db.Integer, nullable=False)
    sent_at = db.Column(db.DateTime)
    status = db.Column(db.String(20), default=ReminderStatus.PENDING)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "opportunity_id": self.opportunity_id,
            "reminder_days": self.reminder_days,
            "status": self.status,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
        }


class ReportStatus:
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class OpportunityReport(db.Model):
    __tablename__ = "opportunity_reports"

    id = db.Column(db.Integer, primary_key=True)
    opportunity_id = db.Column(db.Integer, db.ForeignKey("opportunities.id"), nullable=False)
    reporter_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reporter_email = db.Column(db.String(255))
    reason = db.Column(db.String(60), nullable=False)
    details = db.Column(db.Text)
    status = db.Column(db.String(20), default=ReportStatus.OPEN, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "opportunity_id": self.opportunity_id,
            "reason": self.reason,
            "details": self.details,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
