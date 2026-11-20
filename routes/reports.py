"""
Admin center, phase B: report a player or a chat message, report a bug, and the admin inbox.

Privacy rules (Jason, 2026-11-19):
- The reporter is visible to the admin only, never to the person reported (the reported person is never told).
- A report carries a frozen snapshot: the reported message and the lines around it, limited to what the REPORTER could see (so a report can
  never expose a whisper the reporter was not part of).
- For harassment the admin can open the full conversation between the reporter and the reported person, whispers included, but only from
  inside a report, and every opening is written to the audit log.
"""
import logging
from datetime import datetime, timedelta
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from backend.auth.jwt import get_current_user
from backend.db import get_db
from backend.email_service import send_admin_alert_email
from backend.models import AdminAuditLog, Campaign, CampaignMembership, Character, Message, MessageRecipient, Report, User
from backend.notification_center import create_notification
from backend.whispers import hide_foreign_whispers
from routes.moderation import _admin_emails, _admin_ids, require_admin

logger = logging.getLogger(__name__)

reports_router = APIRouter(prefix="/api/reports")
admin_router = APIRouter(prefix="/api/admin")

PLAYER_REASONS = {
    "harassment": "Harassment or bullying",
    "hate": "Hate or discrimination",
    "threats": "Threats or doxxing",
    "sexual": "Sexual content that is not okay at the table",
    "cheating": "Cheating or exploiting",
    "spam": "Spam or scams",
    "other": "Something else",
}
REPORTS_PER_HOUR = 5
CONTEXT_BEFORE, CONTEXT_AFTER = 10, 5
CONVERSATION_LIMIT = 500


class PlayerReport(BaseModel):
    campaign_id: UUID
    reported_user_id: UUID
    message_id: Optional[UUID] = None
    reason: Literal["harassment", "hate", "threats", "sexual", "cheating", "spam", "other"]
    note: Optional[str] = Field(None, max_length=1000)


class BugReport(BaseModel):
    description: str = Field(..., min_length=10, max_length=2000)
    page: Optional[str] = Field(None, max_length=300)
    user_agent: Optional[str] = Field(None, max_length=300)
    campaign_id: Optional[UUID] = None


class UpdateReport(BaseModel):
    status: Optional[Literal["open", "reviewing", "resolved", "dismissed"]] = None
    admin_note: Optional[str] = Field(None, max_length=2000)


def _too_many(db, user_id) -> bool:
    since = datetime.utcnow() - timedelta(hours=1)
    return db.query(Report).filter(Report.reporter_user_id == user_id, Report.created_at >= since).count() >= REPORTS_PER_HOUR


def _line(m: Message) -> dict:
    return {"id": str(m.id), "sender": m.sender_name, "mode": (m.mode or "").lower(), "text": (m.content or "")[:1000],
            "at": m.created_at.isoformat() if m.created_at else None}


def _snapshot_for_player(db, reporter: User, reported: User, campaign: Campaign, message_id) -> dict:
    snap = {
        "campaign_name": campaign.name,
        "reported_username": reported.username,
        "reported_characters": [c.name for c in db.query(Character).filter(
            Character.campaign_id == campaign.id, Character.user_id == reported.id, Character.is_npc == False).all()],  # noqa: E712
    }
    if message_id:
        visible = hide_foreign_whispers(db.query(Message).filter(Message.campaign_id == campaign.id, Message.deleted_at.is_(None)), reporter.id)
        msg = visible.filter(Message.id == message_id).first()
        if not msg or str(msg.sender_id) != str(reported.id):
            raise HTTPException(status_code=404, detail="That message was not found")
        before = visible.filter(Message.created_at < msg.created_at).order_by(Message.created_at.desc()).limit(CONTEXT_BEFORE).all()
        after = visible.filter(Message.created_at > msg.created_at).order_by(Message.created_at.asc()).limit(CONTEXT_AFTER).all()
        snap["message"] = _line(msg)
        snap["context"] = [_line(m) for m in list(reversed(before)) + [msg] + after]
    return snap


def _alert_admins(db, background: BackgroundTasks, report: Report, subject: str, lines: list):
    for raw in _admin_ids():
        try:
            create_notification(db, UUID(raw), "system", subject, body=lines[0] if lines else None, icon="flag",
                                data={"kind": "report", "report_id": str(report.id), "url": "/admin.html"})
        except Exception as e:
            logger.warning(f"Could not notify an admin of a report: {type(e).__name__}")
    emails = _admin_emails(db)

    def _send():
        try:
            send_admin_alert_email(emails, subject, lines)
        except Exception as e:  # a mail failure never loses or fails the report
            logger.error(f"Could not email admins about a report: {e}")
    background.add_task(_send)


@reports_router.get("/reasons")
def reasons(current_user: User = Depends(get_current_user)):
    return [{"value": k, "label": v} for k, v in PLAYER_REASONS.items()]


@reports_router.post("/player")
def report_player(req: PlayerReport, background: BackgroundTasks, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # One generic 404 for "no such campaign", "you are not in it" and "they are not in it", so this cannot be used to probe who is where.
    nothing = HTTPException(status_code=404, detail="Nothing to report")
    campaign = db.query(Campaign).filter(Campaign.id == req.campaign_id).first()
    if not campaign:
        raise nothing
    if db.query(CampaignMembership).filter(CampaignMembership.campaign_id == campaign.id, CampaignMembership.user_id == current_user.id).first() is None:
        raise nothing
    reported_member = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == campaign.id, CampaignMembership.user_id == req.reported_user_id
    ).execution_options(include_left_members=True).first()  # someone who just left can still be reported
    reported = db.query(User).filter(User.id == req.reported_user_id).first()
    if reported_member is None or reported is None:
        raise nothing
    if reported.id == current_user.id:
        raise HTTPException(status_code=400, detail="You can't report yourself")

    dup = db.query(Report).filter(
        Report.kind == "player", Report.reporter_user_id == current_user.id, Report.reported_user_id == reported.id,
        Report.campaign_id == campaign.id, Report.message_id == req.message_id, Report.status.in_(("open", "reviewing")),
    ).first()
    if dup:
        return {"status": "already_reported"}
    if _too_many(db, current_user.id):
        raise HTTPException(status_code=429, detail="You've sent a lot of reports in the last hour. Please try again later.")

    snapshot = _snapshot_for_player(db, current_user, reported, campaign, req.message_id)
    report = Report(kind="player", reporter_user_id=current_user.id, reported_user_id=reported.id, campaign_id=campaign.id,
                    message_id=req.message_id, reason=req.reason, note=(req.note or None), snapshot=snapshot)
    db.add(report)
    db.commit()
    _alert_admins(db, background, report, "New player report",
                  [f"{current_user.username} reported {reported.username} in {campaign.name}: {PLAYER_REASONS[req.reason]}."])
    db.commit()
    return {"status": "reported"}


@reports_router.post("/bug")
def report_bug(req: BugReport, background: BackgroundTasks, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if _too_many(db, current_user.id):
        raise HTTPException(status_code=429, detail="You've sent a lot of reports in the last hour. Please try again later.")
    report = Report(kind="bug", reporter_user_id=current_user.id, campaign_id=req.campaign_id, reason="bug", note=req.description.strip(),
                    snapshot={"page": req.page, "user_agent": req.user_agent})
    db.add(report)
    db.commit()
    _alert_admins(db, background, report, "New bug report", [f"{current_user.username}: {req.description.strip()[:300]}"])
    db.commit()
    return {"status": "reported"}


# ── Admin inbox ──────────────────────────────────────────────────────────────

def _audit(db, admin: User, action: str, report_id=None, **detail) -> None:
    db.add(AdminAuditLog(admin_user_id=admin.id, action=action, report_id=report_id, detail=detail))


def _usernames(db, ids) -> dict:
    ids = [i for i in set(ids) if i]
    return {u.id: u.username for u in db.query(User).filter(User.id.in_(ids)).all()} if ids else {}


def _report_dict(r: Report, names: dict, full: bool = False) -> dict:
    d = {"id": str(r.id), "kind": r.kind, "status": r.status, "reason": r.reason,
         "reason_label": PLAYER_REASONS.get(r.reason, "Bug report" if r.kind == "bug" else r.reason),
         "reporter": names.get(r.reporter_user_id), "reported": names.get(r.reported_user_id),
         "reported_user_id": str(r.reported_user_id) if r.reported_user_id else None,
         "campaign_id": str(r.campaign_id) if r.campaign_id else None,
         "campaign_name": (r.snapshot or {}).get("campaign_name"),
         "note": r.note, "created_at": r.created_at.isoformat() if r.created_at else None}
    if full:
        d.update(snapshot=r.snapshot or {}, admin_note=r.admin_note, message_id=str(r.message_id) if r.message_id else None,
                 resolved_at=r.resolved_at.isoformat() if r.resolved_at else None)
    return d


@admin_router.get("/reports")
def list_reports(kind: Literal["player", "bug", "all"] = "all",
                 status: Literal["active", "open", "reviewing", "resolved", "dismissed", "all"] = "active",
                 admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    q = db.query(Report)
    if kind != "all":
        q = q.filter(Report.kind == kind)
    if status == "active":
        q = q.filter(Report.status.in_(("open", "reviewing")))
    elif status != "all":
        q = q.filter(Report.status == status)
    rows = q.order_by(Report.created_at.desc()).limit(200).all()
    names = _usernames(db, [r.reporter_user_id for r in rows] + [r.reported_user_id for r in rows])
    return {"reports": [_report_dict(r, names) for r in rows]}


@admin_router.get("/reports/{report_id}")
def get_report(report_id: UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    r = db.query(Report).filter(Report.id == report_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Report not found")
    d = _report_dict(r, _usernames(db, [r.reporter_user_id, r.reported_user_id]), full=True)
    if r.reported_user_id:  # context for deciding: how many other reports name the same person
        d["other_reports_about_them"] = db.query(Report).filter(Report.reported_user_id == r.reported_user_id, Report.id != r.id).count()
    return d


@admin_router.post("/reports/{report_id}")
def update_report(report_id: UUID, req: UpdateReport, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    r = db.query(Report).filter(Report.id == report_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Report not found")
    before = r.status
    if req.status:
        r.status = req.status
        if req.status in ("resolved", "dismissed"):
            r.resolved_at, r.resolved_by_user_id = datetime.utcnow(), admin.id
        else:
            r.resolved_at, r.resolved_by_user_id = None, None
    if req.admin_note is not None:
        r.admin_note = req.admin_note or None
    _audit(db, admin, "report_updated", r.id, status_from=before, status_to=r.status, note_changed=req.admin_note is not None)
    db.commit()
    return {"id": str(r.id), "status": r.status}


@admin_router.get("/reports/{report_id}/conversation")
def open_conversation(report_id: UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """The full conversation between the reporter and the reported person (whispers between the two included). Only reachable from a player
    report, and every call is logged BEFORE anything is returned."""
    r = db.query(Report).filter(Report.id == report_id, Report.kind == "player").first()
    if not r or not r.reported_user_id or not r.campaign_id:
        raise HTTPException(status_code=404, detail="No conversation for this report")
    _audit(db, admin, "conversation_opened", r.id, reporter_id=str(r.reporter_user_id), reported_id=str(r.reported_user_id),
           campaign_id=str(r.campaign_id))
    db.commit()
    a, b = r.reporter_user_id, r.reported_user_id
    between = or_(
        and_(Message.sender_id == a, MessageRecipient.user_id == b),
        and_(Message.sender_id == b, MessageRecipient.user_id == a),
    )
    whisper_ids = [mid for (mid,) in db.query(Message.id).join(MessageRecipient, MessageRecipient.message_id == Message.id).filter(
        Message.campaign_id == r.campaign_id, Message.mode == "WHISPER", Message.deleted_at.is_(None), between).all()]
    public = and_(or_(Message.mode.is_(None), Message.mode != "WHISPER"), Message.sender_id.in_([a, b]))
    q = db.query(Message).filter(Message.campaign_id == r.campaign_id, Message.deleted_at.is_(None),
                                 or_(public, Message.id.in_(whisper_ids)) if whisper_ids else public)
    rows = q.order_by(Message.created_at.asc()).limit(CONVERSATION_LIMIT).all()
    names = _usernames(db, [a, b])
    return {"report_id": str(r.id), "reporter": names.get(a), "reported": names.get(b), "limit": CONVERSATION_LIMIT,
            "messages": [{**_line(m), "private": (m.mode or "").upper() == "WHISPER",
                          "from": "reporter" if m.sender_id == a else "reported" if m.sender_id == b else "other"} for m in rows]}


@admin_router.get("/audit")
def audit_log(limit: int = 100, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(AdminAuditLog).order_by(AdminAuditLog.created_at.desc()).limit(max(1, min(limit, 500))).all()
    names = _usernames(db, [r.admin_user_id for r in rows])
    return {"entries": [{"id": str(r.id), "admin": names.get(r.admin_user_id), "action": r.action,
                         "report_id": str(r.report_id) if r.report_id else None, "detail": r.detail,
                         "at": r.created_at.isoformat() if r.created_at else None} for r in rows]}
