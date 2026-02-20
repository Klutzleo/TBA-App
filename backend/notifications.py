"""
backend/notifications.py
Helper for sending Web Push notifications via pywebpush + VAPID.

SETUP (run once to generate keys):
    python -c "
    from py_vapid import Vapid
    v = Vapid()
    v.generate_keys()
    v.save_key('vapid_private.pem')
    print('VAPID_PUBLIC_KEY:', v.public_key.public_bytes(
        __import__('cryptography').hazmat.primitives.serialization.Encoding.X962,
        __import__('cryptography').hazmat.primitives.serialization.PublicFormat.UncompressedPoint
    ).hex())
    "

Set environment variables:
    VAPID_PRIVATE_KEY = path to vapid_private.pem (or base64 raw private key)
    VAPID_PUBLIC_KEY  = base64url-encoded uncompressed public key
    VAPID_CLAIMS_EMAIL = mailto:your@email.com
"""

import os
import json
import logging
from datetime import datetime

from sqlalchemy.orm import Session
from pywebpush import webpush, WebPushException

logger = logging.getLogger(__name__)

VAPID_PRIVATE_KEY  = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC_KEY   = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_CLAIMS_EMAIL = os.getenv("VAPID_CLAIMS_EMAIL", "mailto:admin@tba-app.com")


def send_push(
    db: Session,
    user_id: str,
    title: str,
    body: str,
    url: str = "/",
    icon: str = "/icons/icon-192.png",
    campaign_id: str | None = None,
) -> int:
    """
    Send a Web Push notification to all subscriptions for a user.

    Returns the number of successfully delivered notifications.
    Automatically removes expired/invalid subscriptions from the DB.
    """
    from backend.models import PushSubscription

    if not VAPID_PRIVATE_KEY or not VAPID_PUBLIC_KEY:
        logger.warning("VAPID keys not configured — skipping push notification")
        return 0

    query = db.query(PushSubscription).filter(PushSubscription.user_id == user_id)
    if campaign_id:
        # Send to subscriptions for this campaign OR global subscriptions
        from sqlalchemy import or_
        query = query.filter(
            or_(
                PushSubscription.campaign_id == campaign_id,
                PushSubscription.campaign_id == None,  # noqa: E711
            )
        )
    subscriptions = query.all()

    payload = json.dumps({
        "title": title,
        "body": body,
        "url": url,
        "icon": icon,
    })

    delivered = 0
    to_delete = []

    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {
                        "p256dh": sub.p256dh,
                        "auth":   sub.auth,
                    },
                },
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": VAPID_CLAIMS_EMAIL},
            )
            sub.last_used_at = datetime.utcnow()
            delivered += 1
        except WebPushException as e:
            status = e.response.status_code if e.response is not None else None
            if status in (404, 410):
                # Subscription expired / unsubscribed by browser
                logger.info(f"Removing stale push subscription: {sub.endpoint[:60]}")
                to_delete.append(sub)
            else:
                logger.warning(f"Push failed ({status}): {e}")
        except Exception as e:
            logger.warning(f"Push error: {e}")

    for sub in to_delete:
        db.delete(sub)

    try:
        db.commit()
    except Exception:
        db.rollback()

    return delivered


def send_push_to_campaign(
    db: Session,
    campaign_id: str,
    exclude_user_id: str | None,
    title: str,
    body: str,
    url: str = "/",
) -> int:
    """Send a notification to everyone in a campaign except the sender."""
    from backend.models import PushSubscription
    from sqlalchemy import distinct

    user_ids = (
        db.query(distinct(PushSubscription.user_id))
        .filter(
            PushSubscription.campaign_id == campaign_id
        )
        .all()
    )

    total = 0
    for (uid,) in user_ids:
        if str(uid) == str(exclude_user_id):
            continue
        total += send_push(db, str(uid), title, body, url, campaign_id=campaign_id)
    return total
