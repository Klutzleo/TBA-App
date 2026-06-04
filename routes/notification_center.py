"""
routes/notification_center.py

GET  /api/notifications          — fetch grouped notifications for the drawer
POST /api/notifications/read-all — mark all non-permanent as read
POST /api/notifications/{id}/read — mark one as read
DELETE /api/notifications/recent  — clear all non-permanent read notifications
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.models import User, Notification
from routes.auth import get_current_user

notifications_router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


@notifications_router.get("")
async def get_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns notifications grouped for the drawer:
      unread_count   — badge number for the icon
      achievements   — recent achievement unlocks (non-permanent, newest first)
      hall_of_fame   — permanent non-shame notifications
      hall_of_shame  — permanent shame notifications
      recent         — all other non-permanent notifications (newest first)
    """
    all_notifs = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .all()
    )

    def serialize(n: Notification) -> dict:
        return {
            "id": str(n.id),
            "type": n.type,
            "title": n.title,
            "body": n.body,
            "icon": n.icon,
            "data": n.data,
            "is_permanent": n.is_permanent,
            "shame": n.shame,
            "silent": n.silent,
            "read": n.read,
            "created_at": n.created_at.isoformat(),
        }

    hall_of_fame  = []
    hall_of_shame = []
    achievements  = []
    recent        = []

    for n in all_notifs:
        s = serialize(n)
        if n.is_permanent and n.shame:
            hall_of_shame.append(s)
        elif n.is_permanent:
            hall_of_fame.append(s)
        elif n.type == "achievement":
            achievements.append(s)
        else:
            recent.append(s)

    unread_count = sum(1 for n in all_notifs if not n.read)

    return {
        "unread_count": unread_count,
        "achievements": achievements,
        "hall_of_fame": hall_of_fame,
        "hall_of_shame": hall_of_shame,
        "recent": recent,
    }


@notifications_router.post("/read-all")
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.read == False,
    ).update({"read": True})
    db.commit()
    return {"ok": True}


@notifications_router.post("/{notification_id}/read")
async def mark_one_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notif = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id,
    ).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.read = True
    db.commit()
    return {"ok": True}


@notifications_router.delete("/recent")
async def clear_recent(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete all non-permanent read notifications for the current user."""
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_permanent == False,
        Notification.read == True,
    ).delete()
    db.commit()
    return {"ok": True}
