"""
Leaving and removal (admin center, phase A).

When someone leaves a campaign, or a Story Weaver removes them, the Story Weaver should hear about it with what they need to plan: which
character it was, and whether that character is in the current encounter (a missing player's character holds up the turn order). The
notification is a lasting in-app entry plus a push; the on-screen toast that already existed still fires.

Everything here only builds text and writes notification rows. The caller commits.
"""
import logging

from backend.models import Campaign, Character, Encounter, InitiativeRoll, User
from backend.notification_center import create_notification

logger = logging.getLogger(__name__)

_GONE_STATUSES = ("dead", "rejected")


def departing_characters(db, campaign_id, user_id) -> list:
    """The player characters this person owns in the campaign (not NPCs, summons, objects or vehicles)."""
    return db.query(Character).filter(
        Character.campaign_id == campaign_id, Character.user_id == user_id,
        Character.is_npc == False, Character.is_summon == False,  # noqa: E712
        Character.is_object == False, Character.is_vehicle == False,  # noqa: E712
        Character.status.notin_(_GONE_STATUSES),
    ).all()


def in_active_encounter(db, campaign_id, characters) -> bool:
    """True when any of these characters is in the turn order of the campaign's running encounter."""
    ids = [c.id for c in characters]
    if not ids:
        return False
    enc = db.query(Encounter).filter(Encounter.campaign_id == campaign_id, Encounter.is_active == True).first()  # noqa: E712
    if enc is None:
        return False
    return db.query(InitiativeRoll).filter(InitiativeRoll.encounter_id == enc.id, InitiativeRoll.character_id.in_(ids)).count() > 0


def _names(characters) -> str:
    parts = [f"{c.name} (level {c.level})" for c in characters]
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def leave_message(username: str, campaign_name: str, characters: list, in_encounter: bool) -> str:
    """What the Story Weaver reads when someone leaves: who, which character, and whether it is in a fight."""
    if not characters:
        return f"{username} left {campaign_name}. They had no character in the campaign, so nothing needs sorting out."
    plural = len(characters) > 1
    text = f"{username} left {campaign_name}. Their character{'s' if plural else ''} {_names(characters)} {'are' if plural else 'is'} still in the campaign"
    if in_encounter:
        text += " and in the current encounter, so the turn order will stop on them until you act"
    text += ". You can turn them into an NPC from the party list, or leave them in case the player comes back."
    return text


def notify_story_weaver_of_leave(db, campaign: Campaign, user: User) -> dict:
    """Lasting notification plus a push for the Story Weaver when a player leaves by choice. Returns what it said (for tests)."""
    chars = departing_characters(db, campaign.id, user.id)
    in_enc = in_active_encounter(db, campaign.id, chars)
    body = leave_message(user.username, campaign.name, chars, in_enc)
    info = {"body": body, "characters": [c.name for c in chars], "in_encounter": in_enc}
    if not campaign.story_weaver_id:
        return info
    create_notification(
        db, campaign.story_weaver_id, "system", "A player left your campaign", body=body, icon="door-open",
        data={"kind": "player_left", "campaign_id": str(campaign.id), "user_id": str(user.id), "username": user.username,
              "characters": [c.name for c in chars], "in_encounter": in_enc, "url": f"/game.html?campaign_id={campaign.id}"},
    )
    try:
        from backend.notifications import send_push
        short = f"{user.username} left {campaign.name}."
        if chars:
            short += f" Their character {chars[0].name} is still in the campaign."
        send_push(db, str(campaign.story_weaver_id), "🚪 Player Left", short, url=f"/game.html?campaign_id={campaign.id}",
                  campaign_id=str(campaign.id))
    except Exception as e:  # a push failure must never block the leave itself
        logger.warning(f"Push failed (player left): {type(e).__name__}")
    return info


def notify_removed_player(db, campaign: Campaign, user: User, banned: bool) -> None:
    """Tell a removed player plainly what happened. No reason is included: that stays between the Story Weaver and the admin."""
    body = f"The Story Weaver removed you from {campaign.name}."
    if banned:
        body += " You can't rejoin it."
    create_notification(db, user.id, "system", "Removed from a campaign", body=body, icon="door-open",
                        data={"kind": "removed", "campaign_id": str(campaign.id), "banned": bool(banned)})
