"""
Whisper privacy.

A whisper reaches only its sender and the people it was addressed to. Targets arrive as typed names (a character, an NPC, a username or
"Story Weaver"); they are turned into user ids here. Whether the Story Weaver can read whispers between players is one switch:
SW_SEES_ALL_WHISPERS, off by decision (Jason, 2026-11-19). Admin review happens only through a report, never here.
"""
from sqlalchemy import and_, exists, or_

from backend.models import Campaign, CampaignMembership, Character, Message, MessageRecipient, User

SW_SEES_ALL_WHISPERS = False
_SW_NAMES = {"story weaver", "narrator", "sw"}


def resolve_whisper_targets(db, campaign_id, targets) -> tuple[set, list]:
    """Returns (user ids, names that matched nobody). NPC names and the Story Weaver's names go to the Story Weaver."""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    member_ids = {m.user_id for m in db.query(CampaignMembership).filter(CampaignMembership.campaign_id == campaign_id)}
    sw_id = campaign.story_weaver_id if campaign else None
    users = {u.id: u for u in db.query(User).filter(User.id.in_(member_ids))} if member_ids else {}
    by_username = {u.username.lower(): u.id for u in users.values()}
    chars = db.query(Character).filter(Character.campaign_id == campaign_id).all()
    by_char = {}
    for c in chars:
        if c.is_npc or c.is_vehicle or c.is_object or c.is_summon:
            if sw_id:
                by_char.setdefault(c.name.lower(), sw_id)
        elif c.user_id in member_ids and c.status not in ("dead", "rejected"):
            by_char[c.name.lower()] = c.user_id
    found, missing = set(), []
    for raw in targets or []:
        name = str(raw).strip().lstrip("@").strip().lower()
        uid = by_username.get(name) or by_char.get(name) or (sw_id if name in _SW_NAMES else None)
        if uid and uid in member_ids:
            found.add(uid)
        else:
            missing.append(str(raw))
    return found, missing


def save_recipients(db, message_id, user_ids) -> None:
    for uid in user_ids:
        db.add(MessageRecipient(message_id=message_id, user_id=uid))


def hide_foreign_whispers(query, viewer_id, is_story_weaver: bool = False):
    """Limit a Message query so whispers show only to their sender or a recipient."""
    if SW_SEES_ALL_WHISPERS and is_story_weaver:
        return query
    mine = or_(
        Message.sender_id == viewer_id,
        exists().where(and_(MessageRecipient.message_id == Message.id, MessageRecipient.user_id == viewer_id)),
    )
    return query.filter(or_(Message.mode.is_(None), Message.mode != "WHISPER", mine))
