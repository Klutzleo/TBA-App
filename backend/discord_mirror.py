"""
backend/discord_mirror.py

Live-mirrors campaign activity to a Discord channel and forwards Discord
reactions back into the campaign as a cosmetic "hype" signal.

Architecture: outbound posts go through Discord's plain REST API via httpx, paced
to stay well under Discord's per-route rate limit (5 req/2s). Inbound reactions
arrive in real time over a single Discord Gateway websocket (_gateway_worker);
each MESSAGE_REACTION_ADD triggers one authoritative REST re-fetch of that
message. A slow backstop sweep reconciles anything missed during a reconnect gap.
Set DISCORD_REACTION_MODE=poll to fall back to the legacy 45-minute REST poller
(escape hatch — no Gateway connection). Background asyncio tasks are started from
backend/app.py's lifespan() only when DISCORD_BOT_TOKEN is set (the feature is a
no-op without it — no queue is even created, and enqueue_outbound() becomes a
cheap no-op check).

HARD CONSTRAINT: nothing in this module may ever write to a game-state table
(Character, Message, InitiativeRoll, ActiveEffect, etc.). Its only writes are
to its own bookkeeping tables (discord_mirrored_messages, discord_reaction_counts)
and its only way back into the app is the narrow `discord_reaction` broadcast
built in _sync_message_reactions(). Reactions are cosmetic by hard requirement.
"""
import asyncio
import json
import logging
import os
import random
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

# Inbound reaction transport: "gateway" (websocket, real-time, no time window) or
# "poll" (legacy 45-min REST polling). Escape hatch for live ops — flip the
# Railway var + restart, no code deploy needed.
_REACTION_MODE = os.getenv("DISCORD_REACTION_MODE", "gateway").strip().lower()

_OUTBOUND_PACE_SECONDS = 0.35
_QUEUE_MAXSIZE = 500
_CHANNEL_CACHE_TTL_SECONDS = 60

# Gateway
_GATEWAY_URL = "wss://gateway.discord.gg/?v=10&encoding=json"
_INTENTS = 1 << 10  # GUILD_MESSAGE_REACTIONS — NOT privileged, no Dev Portal toggle
_REACTION_SYNC_DEBOUNCE_SECONDS = 2.0  # coalesce a burst of reactions on one message
_GATEWAY_BURST_SETTLE_SECONDS = 1.0    # wait this long after a reaction before the authoritative GET

# Backstop sweep — reconciles events missed during a reconnect gap
_BACKSTOP_SWEEP_SECONDS = 600
_BACKSTOP_WINDOW_MINUTES = 24 * 60

# Legacy polling (only used when _REACTION_MODE == "poll")
_LEGACY_POLL_INTERVAL_SECONDS = 25
_LEGACY_POLL_WINDOW_MINUTES = 45

_outbound_queue: Optional["asyncio.Queue"] = None
_outbound_task = None
_reaction_poll_task = None
_gateway_task = None
_backstop_task = None

_stopping = False
_gateway_fatal = False  # set on a close code that won't recover (bad token / bad intents)

# Gateway session state (module-level so a reconnect can RESUME)
_session_id: Optional[str] = None
_resume_gateway_url: Optional[str] = None
_last_seq: Optional[int] = None
_bot_user_id: str = ""

_channel_cache = {}  # campaign_id (str) -> (channel_id | None, cached_at_monotonic)
_campaign_by_channel = {}  # channel_id (str) -> (campaign_id | None, cached_at_monotonic)
_reaction_sync_debounce = {}  # discord_message_id (str) -> monotonic ts of last sync

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


def _get_campaign_for_channel(channel_id: str) -> Optional[str]:
    """Reverse of _get_channel_id — which campaign (if any) mirrors to this Discord channel.
    Used by the Gateway to route inbound reaction events. 60s TTL cache; unknown
    channels resolve to None and the event is dropped with no further work."""
    cached = _campaign_by_channel.get(channel_id)
    if cached and (time.monotonic() - cached[1]) < _CHANNEL_CACHE_TTL_SECONDS:
        return cached[0]
    db = SessionLocal()
    try:
        campaign = db.query(Campaign).filter(Campaign.discord_channel_id == channel_id).first()
        campaign_id = str(campaign.id) if campaign else None
    except Exception as e:
        logger.warning(f"discord_mirror: channel->campaign lookup failed for {channel_id}: {e}")
        campaign_id = cached[0] if cached else None
    finally:
        db.close()
    _campaign_by_channel[channel_id] = (campaign_id, time.monotonic())
    return campaign_id


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
    # WS connect/disconnect presence pings (SystemNotification event="player_joined"/
    # "player_left") fire on every reconnect/tab-switch/page-reload — noisy, not a real
    # membership change (that's the separate, already-denylisted player_joined_campaign/
    # player_left_campaign types).
    if msg_type == "system" and message.get("event") in ("player_joined", "player_left"):
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


def _row_dict(r: "DiscordMirroredMessage") -> dict:
    return {
        "id": str(r.id), "campaign_id": str(r.campaign_id), "channel_id": r.discord_channel_id,
        "discord_message_id": r.discord_message_id,
        "source_message_id": str(r.source_message_id) if r.source_message_id else None,
    }


def _get_pollable_rows(window_minutes: int) -> list:
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
        rows = db.query(DiscordMirroredMessage).filter(
            DiscordMirroredMessage.posted_at > cutoff,
        ).all()
        return [_row_dict(r) for r in rows]
    finally:
        db.close()


def _find_mirrored_row_by_discord_id(campaign_id: str, discord_message_id: str) -> Optional[dict]:
    """Locate the mirrored-message row for an inbound Gateway reaction event."""
    db = SessionLocal()
    try:
        row = db.query(DiscordMirroredMessage).filter(
            DiscordMirroredMessage.discord_message_id == discord_message_id,
            DiscordMirroredMessage.campaign_id == campaign_id,
        ).order_by(DiscordMirroredMessage.posted_at.desc()).first()
        return _row_dict(row) if row else None
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


async def _sync_message_reactions(client: httpx.AsyncClient, row: dict, manager):
    """Authoritative reconcile: GET one message's live reactions from Discord and
    broadcast a cosmetic hype signal for any emoji whose count went up. Shared by
    the Gateway event handler and the backstop/legacy sweeps."""
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
        logger.warning(
            f"discord_mirror: reaction GET {resp.status_code} for msg "
            f"{row['discord_message_id']}: {resp.text[:150]}"
        )
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


async def _sweep_worker(interval_seconds: int, window_minutes: int, label: str):
    """Periodic full reconcile over a time window. Used as the Gateway backstop
    (slow, wide window) and as the legacy standalone poller (fast, narrow window)."""
    from routes.campaign_websocket import manager  # deferred import — avoids circular import at load time

    async with httpx.AsyncClient(timeout=10.0) as client:
        while not _stopping:
            try:
                await asyncio.sleep(interval_seconds)
                for row in _get_pollable_rows(window_minutes):
                    await _sync_message_reactions(client, row, manager)
                    await asyncio.sleep(_OUTBOUND_PACE_SECONDS)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"discord_mirror: {label} sweep error: {e}")


# ============================================================================
# GATEWAY (real-time inbound reactions — replaces polling when _REACTION_MODE == "gateway")
# ============================================================================

async def _handle_reaction_event(d: dict):
    """MESSAGE_REACTION_ADD dispatch → authoritative re-fetch of that one message."""
    if _bot_user_id and str(d.get("user_id")) == _bot_user_id:
        return
    channel_id = str(d.get("channel_id") or "")
    discord_message_id = str(d.get("message_id") or "")
    if not channel_id or not discord_message_id:
        return

    campaign_id = _get_campaign_for_channel(channel_id)
    if not campaign_id:
        return  # reaction in a channel no campaign mirrors
    row = _find_mirrored_row_by_discord_id(campaign_id, discord_message_id)
    if not row:
        return  # reaction on a Discord message we never mirrored

    now = time.monotonic()
    if now - _reaction_sync_debounce.get(discord_message_id, 0.0) < _REACTION_SYNC_DEBOUNCE_SECONDS:
        return  # a sync for this message just ran / is about to — the GET is authoritative
    _reaction_sync_debounce[discord_message_id] = now

    from routes.campaign_websocket import manager
    await asyncio.sleep(_GATEWAY_BURST_SETTLE_SECONDS)  # let a rapid burst settle into one GET
    async with httpx.AsyncClient(timeout=10.0) as client:
        await _sync_message_reactions(client, row, manager)


async def _dispatch_gateway_event(msg: dict):
    global _session_id, _resume_gateway_url, _bot_user_id
    t = msg.get("t")
    d = msg.get("d") or {}
    if t == "READY":
        _session_id = d.get("session_id")
        base = (d.get("resume_gateway_url") or "").rstrip("/")
        _resume_gateway_url = f"{base}/?v=10&encoding=json" if base else None
        _bot_user_id = str((d.get("user") or {}).get("id") or "")
        logger.info(f"discord_mirror: gateway READY (session {_session_id})")
    elif t == "RESUMED":
        logger.info("discord_mirror: gateway resumed")
    elif t == "MESSAGE_REACTION_ADD":
        await _handle_reaction_event(d)


async def _heartbeat_loop(ws, interval_ms: int, state: dict):
    from websockets.exceptions import ConnectionClosed
    try:
        await asyncio.sleep(interval_ms / 1000 * random.random())  # initial jitter per Discord docs
        while True:
            if not state.get("acked", False):
                logger.warning("discord_mirror: gateway heartbeat not ACKed — forcing reconnect")
                await ws.close(code=4000)
                return
            state["acked"] = False
            await ws.send(json.dumps({"op": 1, "d": _last_seq}))
            await asyncio.sleep(interval_ms / 1000)
    except (asyncio.CancelledError, ConnectionClosed):
        return
    except Exception as e:
        logger.warning(f"discord_mirror: gateway heartbeat error: {e!r}")


async def _gateway_worker():
    global _last_seq, _session_id, _resume_gateway_url, _gateway_fatal

    try:
        from websockets.asyncio.client import connect as ws_connect  # websockets >= 13
    except ImportError:  # pragma: no cover — older websockets
        from websockets import connect as ws_connect
    from websockets.exceptions import ConnectionClosed

    _FATAL_CLOSE_CODES = {4004, 4010, 4011, 4012, 4013, 4014}
    backoff = 1

    while not _stopping and not _gateway_fatal:
        resume = bool(_session_id and _resume_gateway_url)
        url = _resume_gateway_url if resume else _GATEWAY_URL
        hb_task = None
        close_code = None
        try:
            async with ws_connect(url, max_size=2 ** 20, ping_interval=None) as ws:
                hello = json.loads(await ws.recv())
                interval_ms = hello["d"]["heartbeat_interval"]
                state = {"acked": True}
                hb_task = asyncio.create_task(_heartbeat_loop(ws, interval_ms, state))

                if resume:
                    logger.info("discord_mirror: gateway resuming")
                    await ws.send(json.dumps({"op": 6, "d": {
                        "token": DISCORD_BOT_TOKEN, "session_id": _session_id, "seq": _last_seq,
                    }}))
                else:
                    logger.info("discord_mirror: gateway identifying")
                    await ws.send(json.dumps({"op": 2, "d": {
                        "token": DISCORD_BOT_TOKEN,
                        "intents": _INTENTS,
                        "properties": {"os": "linux", "browser": "tba-app", "device": "tba-app"},
                    }}))

                backoff = 1  # a successful connect resets backoff
                async for raw in ws:
                    msg = json.loads(raw)
                    if msg.get("s") is not None:
                        _last_seq = msg["s"]
                    op = msg.get("op")
                    if op == 0:
                        await _dispatch_gateway_event(msg)
                    elif op == 1:
                        state["acked"] = False
                        await ws.send(json.dumps({"op": 1, "d": _last_seq}))
                    elif op == 7:
                        logger.info("discord_mirror: gateway requested reconnect")
                        break
                    elif op == 9:
                        resumable = bool(msg.get("d"))
                        logger.info(f"discord_mirror: gateway invalid session (resumable={resumable})")
                        if not resumable:
                            _session_id = None
                            _resume_gateway_url = None
                        await asyncio.sleep(random.uniform(1, 5))
                        break
                    elif op == 11:
                        state["acked"] = True
                close_code = getattr(ws, "close_code", None)
        except ConnectionClosed as e:
            close_code = getattr(e, "code", None) or getattr(getattr(e, "rcvd", None), "code", None)
            logger.warning(f"discord_mirror: gateway connection closed ({close_code})")
        except Exception as e:
            logger.warning(f"discord_mirror: gateway connection error: {e!r}")
        finally:
            if hb_task:
                hb_task.cancel()
                try:
                    await hb_task
                except asyncio.CancelledError:
                    pass

        if close_code in _FATAL_CLOSE_CODES:
            logger.error(
                f"discord_mirror: gateway closed with unrecoverable code {close_code} "
                f"(bad token or intents) — stopping gateway; backstop sweep still runs"
            )
            _gateway_fatal = True
            break

        if _stopping:
            break
        await asyncio.sleep(backoff + random.uniform(0, 1))
        backoff = min(backoff * 2, 60)


def start_workers():
    """Call once from backend/app.py's lifespan() startup. No-op if DISCORD_BOT_TOKEN unset."""
    global _outbound_queue, _outbound_task, _reaction_poll_task, _gateway_task, _backstop_task
    global _stopping, _gateway_fatal
    if not DISCORD_BOT_TOKEN:
        logger.info("discord_mirror: DISCORD_BOT_TOKEN not set — mirroring disabled")
        return

    _stopping = False
    _gateway_fatal = False
    _outbound_queue = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
    _outbound_task = asyncio.create_task(_outbound_worker())

    if _REACTION_MODE == "poll":
        _reaction_poll_task = asyncio.create_task(
            _sweep_worker(_LEGACY_POLL_INTERVAL_SECONDS, _LEGACY_POLL_WINDOW_MINUTES, "legacy-poll")
        )
        logger.info("discord_mirror: workers started (legacy reaction polling)")
    else:
        _gateway_task = asyncio.create_task(_gateway_worker())
        _backstop_task = asyncio.create_task(
            _sweep_worker(_BACKSTOP_SWEEP_SECONDS, _BACKSTOP_WINDOW_MINUTES, "backstop")
        )
        logger.info("discord_mirror: workers started (gateway + backstop)")


async def stop_workers():
    """Call once from backend/app.py's lifespan() shutdown."""
    global _stopping
    _stopping = True
    tasks = (_outbound_task, _reaction_poll_task, _gateway_task, _backstop_task)
    for task in tasks:
        if task:
            task.cancel()
    for task in tasks:
        if task:
            try:
                await task
            except asyncio.CancelledError:
                pass
