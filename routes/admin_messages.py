"""
Admin center, phase D: the admin can message one player or a whole campaign (bell notification, push, email), with saved templates.

Every send is written to the audit log with its subject, text, target and recipient count. Messages go only to active accounts and, for a campaign,
only to current members. Bell, push and email are separate choices because an email is the most intrusive.
"""
import logging
from typing import List, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.db import SessionLocal, get_db
from backend.email_service import send_admin_message_email
from backend.models import AdminAuditLog, AdminTemplate, Campaign, CampaignMembership, User
from backend.notification_center import create_notification
from routes.moderation import require_admin

logger = logging.getLogger(__name__)

messages_router = APIRouter(prefix="/api/admin")

MAX_RECIPIENTS = 100

BUILTIN_TEMPLATES = [
    {"id": "builtin:warning", "name": "Behavior warning", "subject": "A note about your behavior in TBA",
     "body": "We have received a report about your conduct in a campaign. Please keep the table welcoming for everyone. If this continues we may have to suspend your account."},
    {"id": "builtin:maintenance", "name": "Maintenance heads-up", "subject": "TBA will be briefly down for maintenance",
     "body": "TBA will be offline for a short maintenance window. Your campaigns and characters are safe. We will be back shortly."},
    {"id": "builtin:thanks", "name": "Thank you", "subject": "Thank you for playing TBA",
     "body": "Thank you for playing TBA and for the feedback you have given. It really helps."},
    {"id": "builtin:bugfixed", "name": "Bug fixed", "subject": "The bug you reported is fixed",
     "body": "Thanks for reporting that bug. It has been fixed. If you still see it, please send another report."},
]


class MessageRequest(BaseModel):
    target: Literal["user", "campaign"]
    target_id: UUID
    subject: str = Field(..., min_length=3, max_length=100)
    body: str = Field(..., min_length=3, max_length=1000)
    channels: List[Literal["bell", "push", "email"]] = Field(default_factory=lambda: ["bell"], min_length=1)
    dry_run: bool = False


class TemplateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=60)
    subject: str = Field(..., min_length=3, max_length=100)
    body: str = Field(..., min_length=3, max_length=1000)


def _recipients(db, req: MessageRequest) -> tuple:
    """Returns (users, label). Active accounts only; a campaign means its current members."""
    if req.target == "user":
        u = db.query(User).filter(User.id == req.target_id, User.is_active == True).first()  # noqa: E712
        if not u:
            raise HTTPException(status_code=404, detail="No active player with that id")
        return [u], u.username
    camp = db.query(Campaign).filter(Campaign.id == req.target_id).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    ids = [m.user_id for m in db.query(CampaignMembership).filter(CampaignMembership.campaign_id == camp.id).all()]  # current members only
    users = db.query(User).filter(User.id.in_(ids), User.is_active == True).all() if ids else []  # noqa: E712
    if len(users) > MAX_RECIPIENTS:
        raise HTTPException(status_code=400, detail=f"That campaign has more than {MAX_RECIPIENTS} members")
    return users, camp.name


def _deliver_slow_channels(user_ids: list, emails: dict, subject: str, body: str, channels: list) -> None:
    """Push and email, off the request path (a campaign can be dozens of people). A failure for one person never stops the rest."""
    db = SessionLocal()
    try:
        if "push" in channels:
            from backend.notifications import send_push
            for uid in user_ids:
                try:
                    send_push(db, str(uid), subject, body[:140], url="/campaigns.html")
                except Exception as e:
                    logger.warning(f"Admin message push failed: {type(e).__name__}")
        if "email" in channels:
            for uid in user_ids:
                addr = emails.get(uid)
                if not addr:
                    continue
                try:
                    send_admin_message_email(addr, subject, body)
                except Exception as e:
                    logger.warning(f"Admin message email failed: {type(e).__name__}")
    finally:
        db.close()


@messages_router.get("/lookup")
def lookup(q: str = Query(..., min_length=2, max_length=50), admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Find a player by username or a campaign by name, for the message form."""
    term = q.strip().replace("%", "").replace("\\", "")
    if len(term) < 2:  # a wildcard-only search must not list everyone
        return {"users": [], "campaigns": []}
    like = "%" + term.replace("_", r"\_") + "%"
    users = db.query(User).filter(User.username.ilike(like, escape="\\")).order_by(User.username).limit(10).all()
    camps = db.query(Campaign).filter(Campaign.name.ilike(like, escape="\\")).order_by(Campaign.name).limit(10).all()
    return {"users": [{"id": str(u.id), "username": u.username, "active": bool(u.is_active)} for u in users],
            "campaigns": [{"id": str(c.id), "name": c.name} for c in camps]}


@messages_router.get("/templates")
def list_templates(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    saved = db.query(AdminTemplate).order_by(AdminTemplate.name).all()
    return {"templates": BUILTIN_TEMPLATES + [{"id": str(t.id), "name": t.name, "subject": t.subject, "body": t.body} for t in saved]}


@messages_router.post("/templates")
def save_template(req: TemplateRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    t = AdminTemplate(name=req.name.strip(), subject=req.subject.strip(), body=req.body.strip(), created_by_user_id=admin.id)
    db.add(t)
    db.commit()
    return {"id": str(t.id)}


@messages_router.delete("/templates/{template_id}")
def delete_template(template_id: UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    t = db.query(AdminTemplate).filter(AdminTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(t)
    db.commit()
    return {"deleted": True}


@messages_router.post("/messages")
def send_message(req: MessageRequest, background: BackgroundTasks, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    users, label = _recipients(db, req)
    summary = {"recipients": len(users), "usernames": [u.username for u in users][:50], "target": label}
    if req.dry_run or not users:
        return {**summary, "sent": False}
    subject, body, channels = req.subject.strip(), req.body.strip(), list(dict.fromkeys(req.channels))
    if "bell" in channels:
        for u in users:
            create_notification(db, u.id, "system", subject, body=body, icon="megaphone", data={"kind": "admin_message", "url": "/campaigns.html"})
    db.add(AdminAuditLog(admin_user_id=admin.id, action="message_sent", detail={
        "target_type": req.target, "target_id": str(req.target_id), "target": label, "recipients": len(users), "channels": channels,
        "subject": subject, "body": body}))
    db.commit()
    if "push" in channels or "email" in channels:
        background.add_task(_deliver_slow_channels, [u.id for u in users], {u.id: u.email for u in users}, subject, body, channels)
    return {**summary, "sent": True, "channels": channels}
