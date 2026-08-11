"""
backend/discord_mirror.py

Live-mirrors campaign activity to a Discord channel and forwards Discord
reactions back into the campaign as a cosmetic "hype" signal.

Architecture: no persistent Discord Gateway connection — outbound posts and
inbound reaction polling both go through Discord's plain REST API via httpx,
paced to stay well under Discord's per-route rate limit (5 req/2s). Two small
background asyncio tasks, started from backend/app.py's lifespan() only when
DISCORD_BOT_TOKEN is set (the feature is a no-op without it — no queue is even
created, and enqueue_outbound() becomes a cheap no-op check).

HARD CONSTRAINT: nothing in this module may ever write to a game-state table
(Character, Message, InitiativeRoll, ActiveEffect, etc.). Its only writes are
to its own bookkeeping tables (discord_mirrored_messages, discord_reaction_counts)
and its only way back into the app is the narrow `discord_reaction` broadcast
built in _poll_reactions_for_row(). Reactions are cosmetic by hard requirement.
"""
import asyncio
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

import httpx

from backend.db import SessionLocal
from backend.models import Campaign, DiscordMirroredMessage, DiscordReactionCount

logger = logging.getLogger(__name__)

DISCORD_API_BASE = "https://discord.com/api/v10"
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

_OUTBOUND_PACE_SECONDS = 0.35
_REACTION_POLL_INTERVAL_SECONDS = 25
_REACTION_POLL_WINDOW_MINUTES = 45
_QUEUE_MAXSIZE = 500
_CHANNEL_CACHE_TTL_SECONDS = 60

_outbound_queue: Optional["asyncio.Queue"] = None
_outbound_task = None
_reaction_poll_task = None

_channel_cache = {}  # campaign_id (str) -> (channel_id | None, cached_at_monotonic)

# Types that must NEVER be mirrored, regardless of the default-mirror policy.
# Everything else mirrors by default — an allowlist would silently miss new
# broadcast types as the app grows; this denylist is the deliberate exception list.
DENYLIST_TYPES = {
    # Pure UI-sync noise, no narrative value
    "online_users", "welcome", "typing", "effects_sync",
    # Mid-negotiation AOE/combo states — only the terminal result mirrors
    "aoe_pending", "aoe_review", "aoe_cancelled",
    "combo_incoming", "combo_proposed", "combo_holding",
    "combo_partner_locked", "combo_fire_ready",
    # Roster/admin churn — keeps the channel focused on play, not membership churn
    "character_approved", "character_rejected", "pc_converted_to_npc",
    "pc_transferred", "character_created", "player_joined_campaign",
    "player_left_campaign",
    # Privacy: SW's private /s roll routes through broadcast() but is rendered
    # SW-only client-side — must never leak to a public Discord channel.
    "secret_roll_result",
    # This module's own reaction-poller output loops back through broadcast()
    # like everything else — mirroring it as a message would be a feedback loop.
    "discord_reaction",
}

# Small, hand-verified formatters for the types whose exact field names are
# well known. Everything else falls back to the generic content/message/text
# chain in _format_message() — additive over time, not required to be
# exhaustive at launch (see plan doc).
_LABEL_FORMATTERS = {
    "combat_result": lambda d: f"⚔️ **{d.get('attacker', '?')}** → **{d.get('defender', '?')}**: {d.get('damage', '?')} dmg ({d.get('outcome', '?')})",
    "damage_applied": lambda d: f"💥 **{d.get('source', '?')}** hits **{d.get('character_name', '?')}** for {d.get('amount', '?')} DP ({d.get('old_dp', '?')} → {d.get('new_dp', '?')}/{d.get('max_dp', '?')})",
    "bap_granted": lambda d: f"✦ **{d.get('character_name', '?')}** received a BAP token",
}


def _format_message(d: dict) -> Optional[str]:
    """Turn a broadcast payload into readable Discord text, or None to skip posting."""
    msg_type = d.get("type")
    formatter = _LABEL_FORMATTERS.get(msg_type)
    if formatter:
        try:
            return formatter(d)
        except Exception:
            pass  # fall through to the generic chain below

    for key in ("content", "message", "text"):
        val = d.get(key)
        if val:
            actor = d.get("actor") or d.get("sender_name") or d.get("character_name") or d.get("attacker")
            if actor and key in ("content", "text"):
                return f"**{actor}**: {val}"
            return str(val)

    logger.info(f"discord_mirror: no formatter/fallback for type={msg_type!r}, skipping")
    return None


def _get_channel_id(campaign_id: str) -> Optional[str]:
    cached = _channel_cache.get(campaign_id)
    if cached and (time.monotonic() - cached[1]) < _CHANNEL_CACHE_TTL_SECONDS:
        return cached[0]
    db = SessionLocal()
    try:
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        channel_id = campaign.discord_channel_id if campaign else None
    except Exception as e:
        logger.warning(f"discord_mirror: failed to look up campaign {campaign_id}: {e}")
        channel_id = cached[0] if cached else None
    finally:
        db.close()
    _channel_cache[campaign_id] = (channel_id, time.monotonic())
    return channel_id


def enqueue_outbound(campaign_id, message: dict):
    """Called synchronously from ConnectionManager.broadcast(). Must never raise —
    callers already wrap this in try/except, but this stays defensive regardless."""
    if not DISCORD_BOT_TOKEN or _outbound_queue is None:
        return

    msg_type = message.get("type")
    if not msg_type or msg_type in DENYLIST_TYPES:
        return
    if msg_type == "system" and str(message.get("text", "")).startswith("❌"):
        return

    channel_id = _get_channel_id(str(campaign_id))
    if not channel_id:
        return

    if msg_type == "message_deleted":
        item = {
            "action": "delete", "campaign_id": str(campaign_id), "channel_id": channel_id,
            "text": None, "event_type": msg_type,
            "source_message_id": message.get("message_id"),
        }
    else:
        text = _format_message(message)
        if not text:
            return
        action = "edit" if msg_type == "message_edited" else "post"
        item = {
            "action": action, "campaign_id": str(campaign_id), "channel_id": channel_id,
            "text": text[:2000], "event_type": msg_type,
            "source_message_id": message.get("message_id"),
        }

    try:
        _outbound_queue.put_nowait(item)
    except asyncio.QueueFull:
        try:
            _outbound_queue.get_nowait()  # drop oldest — mirroring is best-effort
            _outbound_queue.put_nowait(item)
        except Exception:
            pass


def _save_mirrored_message(item: dict, discord_message_id: str):
    db = SessionLocal()
    try:
        row = DiscordMirroredMessage(
            campaign_id=item["campaign_id"],
            discord_channel_id=item["channel_id"],
            discord_message_id=discord_message_id,
            event_type=item["event_type"],
            source_message_id=item.get("source_message_id"),
        )
        db.add(row)
        db.commit()
    except Exception as e:
        logger.warning(f"discord_mirror: failed to save mirrored message row: {e}")
        db.rollback()
    finally:
        db.close()


def _find_mirrored_row(item: dict) -> Optional[dict]:
    if not item.get("source_message_id"):
        return None
    db = SessionLocal()
    try:
        row = db.query(DiscordMirroredMessage).filter(
            DiscordMirroredMessage.source_message_id == item["source_message_id"],
            DiscordMirroredMessage.campaign_id == item["campaign_id"],
        ).order_by(DiscordMirroredMessage.posted_at.desc()).first()
        if not row:
            return None
        return {"id": str(row.id), "discord_message_id": row.discord_message_id, "channel_id": row.discord_channel_id}
    finally:
        db.close()


def _delete_mirrored_row(row: dict):
    db = SessionLocal()
    try:
        db.query(DiscordMirroredMessage).filter(DiscordMirroredMessage.id == row["id"]).delete()
        db.commit()
    except Exception as e:
        logger.warning(f"discord_mirror: failed to delete mirrored row: {e}")
        db.rollback()
    finally:
        db.close()


async def _process_outbound_item(client: httpx.AsyncClient, item: dict):
    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
    action = item["action"]

    if action == "post":
        resp = await client.post(
            f"{DISCORD_API_BASE}/channels/{item['channel_id']}/messages",
            headers=headers, json={"content": item["text"]},
        )
        if resp.status_code == 429:
            await asyncio.sleep(float(resp.json().get("retry_after", 1)))
            return
        if resp.status_code not in (200, 201):
            logger.warning(f"discord_mirror: post failed {resp.status_code}: {resp.text[:200]}")
            return
        discord_msg_id = resp.json().get("id")
        if discord_msg_id:
            _save_mirrored_message(item, discord_msg_id)

    elif action == "edit":
        row = _find_mirrored_row(item)
        if not row:
            return
        resp = await client.patch(
            f"{DISCORD_API_BASE}/channels/{item['channel_id']}/messages/{row['discord_message_id']}",
            headers=headers, json={"content": item["text"]},
        )
        if resp.status_code == 429:
            await asyncio.sleep(float(resp.json().get("retry_after", 1)))
        elif resp.status_code != 200:
            logger.warning(f"discord_mirror: edit failed {resp.status_code}: {resp.text[:200]}")

    elif action == "delete":
        row = _find_mirrored_row(item)
        if not row:
            return
        resp = await client.delete(
            f"{DISCORD_API_BASE}/channels/{item['channel_id']}/messages/{row['discord_message_id']}",
            headers=headers,
        )
        if resp.status_code == 429:
            await asyncio.sleep(float(resp.json().get("retry_after", 1)))
        elif resp.status_code not in (200, 204):
            logger.warning(f"discord_mirror: delete failed {resp.status_code}: {resp.text[:200]}")
        else:
            _delete_mirrored_row(row)


async def _outbound_worker():
    async with httpx.AsyncClient(timeout=10.0) as client:
        while True:
            try:
                item = await _outbound_queue.get()
                await _process_outbound_item(client, item)
                await asyncio.sleep(_OUTBOUND_PACE_SECONDS)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"discord_mirror: outbound worker error: {e}")


def _get_pollable_rows() -> list:
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(minutes=_REACTION_POLL_WINDOW_MINUTES)
        rows = db.query(DiscordMirroredMessage).filter(
            DiscordMirroredMessage.posted_at > cutoff,
        ).all()
        return [
            {
                "id": str(r.id), "campaign_id": str(r.campaign_id), "channel_id": r.discord_channel_id,
                "discord_message_id": r.discord_message_id,
                "source_message_id": str(r.source_message_id) if r.source_message_id else None,
            }
            for r in rows
        ]
    finally:
        db.close()


def _upsert_reaction_count(mirrored_message_id: str, emoji_key: str, new_count: int) -> Optional[int]:
    """Returns new_count if it increased (caller should broadcast the hype), else None."""
    db = SessionLocal()
    try:
        existing = db.query(DiscordReactionCount).filter(
            DiscordReactionCount.mirrored_message_id == mirrored_message_id,
            DiscordReactionCount.emoji_key == emoji_key,
        ).first()
        if existing:
            if new_count <= existing.last_count:
                return None
            existing.last_count = new_count
            db.commit()
            return new_count
        db.add(DiscordReactionCount(
            mirrored_message_id=mirrored_message_id, emoji_key=emoji_key, last_count=new_count,
        ))
        db.commit()
        return new_count if new_count > 0 else None
    except Exception as e:
        logger.warning(f"discord_mirror: failed to upsert reaction count: {e}")
        db.rollback()
        return None
    finally:
        db.close()


async def _poll_reactions_for_row(client: httpx.AsyncClient, row: dict, manager):
    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
    resp = await client.get(
        f"{DISCORD_API_BASE}/channels/{row['channel_id']}/messages/{row['discord_message_id']}",
        headers=headers,
    )
    if resp.status_code == 429:
        await asyncio.sleep(float(resp.json().get("retry_after", 1)))
        return
    if resp.status_code == 404:
        _delete_mirrored_row(row)  # deleted on Discord's side directly — stop tracking it
        return
    if resp.status_code != 200:
        return

    for r in (resp.json().get("reactions") or []):
        emoji = r.get("emoji", {})
        emoji_key = f"{emoji.get('name')}:{emoji['id']}" if emoji.get("id") else emoji.get("name")
        count = r.get("count", 0)
        if not emoji_key or count <= 0:
            continue
        if _upsert_reaction_count(row["id"], emoji_key, count) is not None:
            # NEVER call anything else here — this broadcast is the only write path
            # back into the app, and it must stay this narrow. Reactions are cosmetic
            # by hard requirement; nothing in this module may touch game-state tables.
            # Routed through DiscordReactionBroadcast so the payload can't accidentally
            # carry a stray game-state field.
            from routes.schemas.campaign import DiscordReactionBroadcast
            payload = DiscordReactionBroadcast(
                emoji=emoji_key,
                count=count,
                message_id=row["source_message_id"],
            )
            await manager.broadcast(UUID(row["campaign_id"]), payload.model_dump(mode='json'))


async def _reaction_poll_worker():
    from routes.campaign_websocket import manager  # deferred import — avoids circular import at load time

    async with httpx.AsyncClient(timeout=10.0) as client:
        while True:
            try:
                await asyncio.sleep(_REACTION_POLL_INTERVAL_SECONDS)
                for row in _get_pollable_rows():
                    await _poll_reactions_for_row(client, row, manager)
                    await asyncio.sleep(_OUTBOUND_PACE_SECONDS)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"discord_mirror: reaction poll worker error: {e}")


def start_workers():
    """Call once from backend/app.py's lifespan() startup. No-op if DISCORD_BOT_TOKEN unset."""
    global _outbound_queue, _outbound_task, _reaction_poll_task
    if not DISCORD_BOT_TOKEN:
        logger.info("discord_mirror: DISCORD_BOT_TOKEN not set — mirroring disabled")
        return
    _outbound_queue = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
    _outbound_task = asyncio.create_task(_outbound_worker())
    _reaction_poll_task = asyncio.create_task(_reaction_poll_worker())
    logger.info("discord_mirror: workers started")


async def stop_workers():
    """Call once from backend/app.py's lifespan() shutdown."""
    for task in (_outbound_task, _reaction_poll_task):
        if task:
            task.cancel()
    for task in (_outbound_task, _reaction_poll_task):
        if task:
            try:
                await task
            except asyncio.CancelledError:
                pass
