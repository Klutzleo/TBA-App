"""
routes/moderation.py
Reporting and removal of public user content (campaign banners for now; LBA packages and
characters plug in later by adding a content type).

- Any logged-in user can report content they can see (rate-limited, one report per person per item).
- Admins (user ids in the ADMIN_USER_IDS env var, comma separated) review and act on reports.
- Reporter identity is only ever returned by the admin endpoints. The content's owner never sees it.
"""
import logging
import os
from datetime import datetime, timedelta
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.auth.jwt import get_current_user
from backend.db import get_db
from backend.email_service import send_report_email
from backend.models import (
    Campaign,
    CampaignMembership,
    ContentReport,
    REPORT_REASON_LABELS,
    REPORT_REASONS,
    User,
)
from backend.notification_center import create_notification
from routes.upload import delete_banner_from_r2

logger = logging.getLogger(__name__)

moderation_router = APIRouter(prefix="/api/moderation", tags=["Moderation"])

REPORTS_PER_DAY = 10


def _admin_ids() -> set:
    """Read on every call (not at import) so config changes and tests take effect immediately."""
    return {i.strip() for i in os.getenv("ADMIN_USER_IDS", "").split(",") if i.strip()}


def _admin_emails(db: Session) -> list:
    ids = []
    for raw in _admin_ids():
        try:
            ids.append(UUID(raw))
        except ValueError:
            continue
    if not ids:
        return []
    return [u.email for u in db.query(User).filter(User.id.in_(ids)).all() if u.email]


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if str(current_user.id) not in _admin_ids():
        raise HTTPException(status_code=403, detail="Admin only")
    return current_user


class ReportRequest(BaseModel):
    content_type: Literal["campaign_banner"]
    content_id: UUID
    reason: str
    note: Optional[str] = Field(None, max_length=500)

    @field_validator("reason")
    @classmethod
    def _reason_known(cls, v):
        if v not in REPORT_REASONS:
            raise ValueError("Unknown reason")
        return v

    @model_validator(mode="after")
    def _other_needs_note(self):
        if self.note is not None:
            self.note = self.note.strip() or None
        if self.reason == "other" and not self.note:
            raise ValueError("Please add a short note when choosing Other")
        return self


class ResolveRequest(BaseModel):
    action: Literal["remove", "remove_and_lock", "dismiss"]
    message: Optional[str] = Field(None, max_length=300)  # shown to the campaign's SW


@moderation_router.get("/reasons")
def list_reasons(current_user: User = Depends(get_current_user)):
    """The report dropdown options, so the UI never keeps its own copy of the list."""
    return [{"value": v, "label": REPORT_REASON_LABELS[v]} for v in REPORT_REASONS]


@moderation_router.post("/report")
def report_content(
    req: ReportRequest,
    background: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    already = db.query(ContentReport).filter(
        ContentReport.reporter_user_id == current_user.id,
        ContentReport.content_type == req.content_type,
        ContentReport.content_id == req.content_id,
    ).first()
    if already:
        return {"status": "already_reported"}

    since = datetime.utcnow() - timedelta(days=1)
    recent = db.query(ContentReport).filter(
        ContentReport.reporter_user_id == current_user.id,
        ContentReport.created_at >= since,
    ).count()
    if recent >= REPORTS_PER_DAY:
        raise HTTPException(status_code=429, detail="Report limit reached for today. Please try again tomorrow.")

    campaign = db.query(Campaign).filter(Campaign.id == req.content_id).first()
    # One generic 404 for "no such campaign", "no banner", and "you can't see it", so this
    # endpoint can't be used to probe which private campaigns exist.
    if not campaign or not campaign.banner_url:
        raise HTTPException(status_code=404, detail="Nothing to report")
    is_member = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == campaign.id,
        CampaignMembership.user_id == current_user.id,
        CampaignMembership.left_at.is_(None),
    ).first() is not None
    if not (is_member or (campaign.is_public and campaign.is_active)):
        raise HTTPException(status_code=404, detail="Nothing to report")
    if current_user.id in (campaign.story_weaver_id, campaign.created_by_user_id):
        raise HTTPException(status_code=400, detail="You can't report your own banner")

    db.add(ContentReport(
        reporter_user_id=current_user.id,
        content_type=req.content_type,
        content_id=campaign.id,
        reason=req.reason,
        note=req.note,
        snapshot={"campaign_name": campaign.name, "banner_url": campaign.banner_url},
    ))
    try:
        db.commit()
    except IntegrityError:  # two taps at once: the unique constraint already holds one
        db.rollback()
        return {"status": "already_reported"}

    admin_emails = _admin_emails(db)
    background.add_task(_email_admins, admin_emails, {
        "content_label": "Campaign banner",
        "campaign_name": campaign.name,
        "reason": REPORT_REASON_LABELS[req.reason],
        "note": req.note,
        "reporter": current_user.username,
    })
    return {"status": "reported"}


def _email_admins(emails: list, report: dict) -> None:
    try:
        send_report_email(emails, report)
    except Exception as e:  # a mail failure must never lose or fail the report itself
        logger.error(f"Could not email admins about a report: {e}")


@moderation_router.get("/reports")
def list_reports(
    status: Literal["open", "resolved", "all"] = "open",
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(ContentReport)
    if status != "all":
        query = query.filter(ContentReport.status == status)
    reports = query.order_by(ContentReport.created_at.desc()).limit(100).all()

    reporters = {
        u.id: u.username
        for u in db.query(User).filter(User.id.in_({r.reporter_user_id for r in reports})).all()
    } if reports else {}
    campaigns = {
        c.id: c
        for c in db.query(Campaign).filter(Campaign.id.in_({r.content_id for r in reports})).all()
    } if reports else {}

    out = []
    for r in reports:
        c = campaigns.get(r.content_id)
        reported_url = (r.snapshot or {}).get("banner_url")
        out.append({
            "id": str(r.id),
            "content_type": r.content_type,
            "content_id": str(r.content_id),
            "reason": r.reason,
            "reason_label": REPORT_REASON_LABELS.get(r.reason, r.reason),
            "note": r.note,
            "snapshot": r.snapshot,
            "status": r.status,
            "resolution": r.resolution,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "reporter_username": reporters.get(r.reporter_user_id),
            "campaign_exists": c is not None,
            "banner_still_live": bool(c and c.banner_url and c.banner_url == reported_url),
            "banner_locked": bool(c and c.banner_locked),
        })
    return out


@moderation_router.post("/reports/{report_id}/resolve")
def resolve_report(
    report_id: UUID,
    req: ResolveRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    report = db.query(ContentReport).filter(ContentReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.status != "open":
        raise HTTPException(status_code=409, detail="Already resolved")

    now = datetime.utcnow()

    def _close(reports, resolution):
        for r in reports:
            r.status = "resolved"
            r.resolution = resolution
            r.resolved_at = now
            r.resolved_by_user_id = admin.id

    if req.action == "dismiss":
        _close([report], "dismissed")
        db.commit()
        return {"outcome": "dismissed", "file_deleted": False}

    campaign = db.query(Campaign).filter(Campaign.id == report.content_id).first()
    siblings = db.query(ContentReport).filter(
        ContentReport.content_type == report.content_type,
        ContentReport.content_id == report.content_id,
        ContentReport.status == "open",
    ).all()

    if not campaign:
        _close(siblings, "stale")
        db.commit()
        return {"outcome": "stale", "file_deleted": False}

    reported_url = (report.snapshot or {}).get("banner_url")
    still_live = bool(campaign.banner_url and campaign.banner_url == reported_url)
    file_deleted = False
    if still_live:
        file_deleted = delete_banner_from_r2(campaign.banner_url)
        campaign.banner_url = None
    # If the SW already swapped the image since the report, the reported file is gone; never
    # remove a different, newer image on the strength of an old report.
    locking = req.action == "remove_and_lock"
    if locking:
        campaign.banner_locked = True

    outcome = ("removed_locked" if locking else "removed") if still_live else "stale"
    _close(siblings, outcome)

    if still_live or locking:
        sw_id = campaign.story_weaver_id or campaign.created_by_user_id
        body = f"Reason: {REPORT_REASON_LABELS.get(report.reason, report.reason)}."
        if req.message and req.message.strip():
            body += f" {req.message.strip()}"
        if locking:
            body += " Uploading a new banner is disabled for this campaign."
        create_notification(
            db=db,
            user_id=sw_id,
            type="system",
            title=f"Banner removed from {campaign.name}"[:200],
            body=body,
            icon="shield-alert",
            data={"campaign_id": str(campaign.id)},
        )
    db.commit()
    return {"outcome": outcome, "file_deleted": file_deleted}
