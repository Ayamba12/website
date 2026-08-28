import time
from datetime import datetime, timezone
from flask import current_app
from app.extensions import db
from app.models import Opportunity, OpportunityStatus

# Throttle: expiry only needs checking every so often, not on every single
# read request. Missing a deadline by a couple of minutes is a non-issue;
# an unnecessary extra round-trip to the database on every page load isn't.
_SYNC_INTERVAL_SECONDS = 120
_last_sync_monotonic = None


def sync_expired_opportunities(force=False):
    """Flag opportunities whose deadline has passed as expired.

    Preserves the record; only flips is_expired so it drops out of
    'active' listings while remaining available for historical/archive views.

    Throttled to run at most once every _SYNC_INTERVAL_SECONDS per process —
    pass force=True to bypass (used by tests).
    """
    global _last_sync_monotonic
    if current_app.config.get("TESTING"):
        force = True  # each test gets a fresh database; never throttle across them

    now_monotonic = time.monotonic()
    if not force and _last_sync_monotonic is not None:
        if now_monotonic - _last_sync_monotonic < _SYNC_INTERVAL_SECONDS:
            return 0
    _last_sync_monotonic = now_monotonic

    now = datetime.now(timezone.utc)
    stale = Opportunity.query.filter(
        Opportunity.is_expired.is_(False),
        Opportunity.deadline.isnot(None),
        Opportunity.deadline < now,
    ).all()
    for opp in stale:
        opp.is_expired = True
    if stale:
        db.session.commit()
    return len(stale)


def days_remaining(opportunity: Opportunity):
    if not opportunity.deadline:
        return None
    deadline = opportunity.deadline
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    delta = deadline - datetime.now(timezone.utc)
    return delta.days
