from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models import OpportunityReport, Opportunity, ReportStatus
from app.auth.decorators import admin_required, get_current_user

bp = Blueprint("reports", __name__, url_prefix="/api")

VALID_REASONS = {
    "incorrect_information",
    "expired_opportunity",
    "broken_link",
    "suspicious_fraudulent",
    "incorrect_eligibility",
    "other",
}


@bp.post("/opportunities/<int:opportunity_id>/report")
def report_opportunity(opportunity_id):
    Opportunity.query.get_or_404(opportunity_id)
    data = request.get_json(silent=True) or {}
    reason = data.get("reason")
    if reason not in VALID_REASONS:
        return jsonify({"error": "Invalid report reason"}), 400

    user = get_current_user()
    report = OpportunityReport(
        opportunity_id=opportunity_id,
        reporter_id=user.id if user else None,
        reporter_email=data.get("email") if not user else None,
        reason=reason,
        details=data.get("details"),
    )
    db.session.add(report)
    db.session.commit()
    return jsonify(report.to_dict()), 201


@bp.get("/admin/reports")
@admin_required
def list_reports(**kwargs):
    status = request.args.get("status")
    query = OpportunityReport.query
    if status:
        query = query.filter_by(status=status)
    reports = query.order_by(OpportunityReport.created_at.desc()).all()
    return jsonify([r.to_dict() for r in reports])


@bp.put("/admin/reports/<int:report_id>")
@admin_required
def update_report(report_id):
    report = OpportunityReport.query.get_or_404(report_id)
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    if status not in (ReportStatus.OPEN, ReportStatus.UNDER_REVIEW, ReportStatus.RESOLVED, ReportStatus.REJECTED):
        return jsonify({"error": "Invalid status"}), 400
    report.status = status
    db.session.commit()
    return jsonify(report.to_dict())
