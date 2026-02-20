"""
routes/notifications.py
PWA Web Push subscription management.

Endpoints:
  GET  /api/notifications/vapid-public-key  — return VAPID public key for browser
  POST /api/notifications/subscribe         — register a push subscription
  POST /api/notifications/unsubscribe       — remove a push subscription
  POST /api/notifications/ping              — SW pings a specific player (test / attention)
"""

import os
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db import get_db
from routes.auth import get_current_user
from backend.models import PushSubscription, User, CampaignMembership

logger = logging.getLogger(__name__)

notifications_router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


# ---------- Schemas ----------

class SubscribeRequest(BaseModel):
    endpoint: str
    p256dh: str
    auth: str
    campaign_id: Optional[str] = None


class UnsubscribeRequest(BaseModel):
    endpoint: str


class PingRequest(BaseModel):
    target_user_id: str
    campaign_id: str
    message: str = "The Story Weaver is calling for you!"


# ---------- Routes ----------

@notifications_router.get("/vapid-public-key")
async def get_vapid_public_key():
    """Return the VAPID public key so the browser can subscribe."""
    key = os.getenv("VAPID_PUBLIC_KEY", "")
    if not key:
        raise HTTPException(
            status_code=503,
            detail="Push notifications not configured on this server."
        )
    return {"publicKey": key}


@notifications_router.post("/subscribe", status_code=201)
async def subscribe(
    req: SubscribeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Register or update a Web Push subscription for the current user."""
    # Upsert: if same (user, endpoint) exists update keys, else create
    existing = (
        db.query(PushSubscription)
        .filter(
            PushSubscription.user_id == current_user.id,
            PushSubscription.endpoint == req.endpoint,
        )
        .first()
    )

    if existing:
        existing.p256dh = req.p256dh
        existing.auth = req.auth
        if req.campaign_id:
            existing.campaign_id = req.campaign_id
    else:
        sub = PushSubscription(
            user_id=current_user.id,
            endpoint=req.endpoint,
            p256dh=req.p256dh,
            auth=req.auth,
            campaign_id=req.campaign_id or None,
        )
        db.add(sub)

    db.commit()
    return {"status": "subscribed"}


@notifications_router.post("/unsubscribe")
async def unsubscribe(
    req: UnsubscribeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a push subscription (user unsubscribed in browser)."""
    deleted = (
        db.query(PushSubscription)
        .filter(
            PushSubscription.user_id == current_user.id,
            PushSubscription.endpoint == req.endpoint,
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"status": "unsubscribed", "deleted": deleted}


@notifications_router.post("/ping")
async def ping_player(
    req: PingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    SW pings a player with a push notification.
    Only the Story Weaver of the campaign can use this.
    """
    from backend.models import Campaign

    campaign = db.query(Campaign).filter(Campaign.id == req.campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if str(campaign.story_weaver_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Only the Story Weaver can ping players")

    from backend.notifications import send_push

    delivered = send_push(
        db=db,
        user_id=req.target_user_id,
        title="📣 Story Weaver is calling!",
        body=req.message,
        url=f"/game.html?campaign_id={req.campaign_id}",
        campaign_id=req.campaign_id,
    )
    return {"status": "sent", "delivered": delivered}
