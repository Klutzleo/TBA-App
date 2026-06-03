"""
backend/stats_tracker.py
Helpers for incrementing user_stats, character_stats, campaign_stats, and site_stats.

All functions are fire-and-forget — call them after the main action completes.
They upsert rows so first-time players get a row automatically.
"""

import logging
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

logger = logging.getLogger(__name__)


def _now():
    return datetime.utcnow()


def _upsert_user_stats(db: Session, user_id: str, **increments):
    from backend.models import UserStats
    try:
        row = db.query(UserStats).filter(UserStats.user_id == user_id).first()
        if not row:
            row = UserStats(user_id=user_id, first_played_at=_now())
            db.add(row)
            db.flush()
        for col, val in increments.items():
            if col.startswith('biggest_'):
                current = getattr(row, col, 0) or 0
                if val > current:
                    setattr(row, col, val)
            else:
                current = getattr(row, col, 0) or 0
                setattr(row, col, current + val)
        row.last_played_at = _now()
        row.updated_at = _now()
    except Exception as e:
        logger.warning(f"UserStats upsert failed: {e}")


def _upsert_character_stats(db: Session, character_id: str, user_id: str, **increments):
    from backend.models import CharacterStats
    try:
        row = db.query(CharacterStats).filter(CharacterStats.character_id == character_id).first()
        if not row:
            row = CharacterStats(character_id=character_id, user_id=user_id, first_played_at=_now())
            db.add(row)
            db.flush()
        for col, val in increments.items():
            if col.startswith('biggest_'):
                current = getattr(row, col, 0) or 0
                if val > current:
                    setattr(row, col, val)
            else:
                current = getattr(row, col, 0) or 0
                setattr(row, col, current + val)
        row.last_played_at = _now()
        row.updated_at = _now()
    except Exception as e:
        logger.warning(f"CharacterStats upsert failed: {e}")


def _upsert_campaign_stats(db: Session, campaign_id: str, **increments):
    from backend.models import CampaignStats
    try:
        row = db.query(CampaignStats).filter(CampaignStats.campaign_id == campaign_id).first()
        if not row:
            row = CampaignStats(campaign_id=campaign_id)
            db.add(row)
            db.flush()
        for col, val in increments.items():
            if col == 'biggest_hit':
                current = getattr(row, col, 0) or 0
                if val > current:
                    setattr(row, col, val)
            else:
                current = getattr(row, col, 0) or 0
                setattr(row, col, current + val)
        row.updated_at = _now()
    except Exception as e:
        logger.warning(f"CampaignStats upsert failed: {e}")


def _upsert_site_stats(db: Session, **increments):
    from backend.models import SiteStats
    try:
        row = db.query(SiteStats).filter(SiteStats.id == 1).first()
        if not row:
            row = SiteStats(id=1)
            db.add(row)
            db.flush()
        for col, val in increments.items():
            current = getattr(row, col, 0) or 0
            setattr(row, col, current + val)
        row.updated_at = _now()
    except Exception as e:
        logger.warning(f"SiteStats upsert failed: {e}")


def _check_rolls(rolls: list[int], die_size: int) -> dict:
    """Return counts of 1s and max rolls from a list of individual die results."""
    ones = sum(1 for r in rolls if r == 1)
    maxes = sum(1 for r in rolls if r == die_size)
    return {"total_ones": ones, "total_max_rolls": maxes}


# ============================================================
# Public API
# ============================================================

def track_dice_roll(db: Session, user_id: str, character_id: str | None,
                    rolls: list[int], die_size: int, campaign_id: str | None = None):
    """Track a free /roll XdY."""
    extras = _check_rolls(rolls, die_size)
    kwargs = {"total_rolls": len(rolls), **extras}
    _upsert_user_stats(db, user_id, **kwargs)
    if character_id:
        _upsert_character_stats(db, character_id, user_id, **kwargs)
    if campaign_id:
        _upsert_campaign_stats(db, campaign_id, total_rolls=len(rolls),
                               total_ones=extras["total_ones"])
    _upsert_site_stats(db, total_rolls=len(rolls), total_ones=extras["total_ones"],
                       total_max_rolls=extras["total_max_rolls"])


def track_stat_check(db: Session, user_id: str, character_id: str | None,
                     stat: str, die_roll: int, campaign_id: str | None = None):
    """Track /pp, /ip, /sp."""
    stat = stat.upper()
    stat_key = f"total_{stat.lower()}_checks"
    extras = _check_rolls([die_roll], 6)
    kwargs = {"total_rolls": 1, "total_stat_checks": 1, stat_key: 1, **extras}
    _upsert_user_stats(db, user_id, **kwargs)
    if character_id:
        _upsert_character_stats(db, character_id, user_id, **kwargs)
    if campaign_id:
        _upsert_campaign_stats(db, campaign_id, total_rolls=1,
                               total_ones=extras["total_ones"])
    _upsert_site_stats(db, total_rolls=1, total_ones=extras["total_ones"],
                       total_max_rolls=extras["total_max_rolls"])


def track_initiative(db: Session, user_id: str, character_id: str | None,
                     die_roll: int, campaign_id: str | None = None):
    """Track an initiative roll."""
    extras = _check_rolls([die_roll], 6)
    kwargs = {"total_rolls": 1, "total_initiatives": 1, **extras}
    _upsert_user_stats(db, user_id, **kwargs)
    if character_id:
        _upsert_character_stats(db, character_id, user_id, **kwargs)
    if campaign_id:
        _upsert_campaign_stats(db, campaign_id, total_rolls=1)
    _upsert_site_stats(db, total_rolls=1)


def track_attack(db: Session, user_id: str, character_id: str | None,
                 damage_dealt: int, individual_rolls: list[dict],
                 campaign_id: str | None = None):
    """Track an attack roll."""
    all_rolls = []
    for r in individual_rolls:
        if r.get("attacker_roll"):
            all_rolls.append(r["attacker_roll"])
    extras = _check_rolls(all_rolls, 12) if all_rolls else {}
    kwargs = {
        "total_rolls": len(all_rolls),
        "total_attacks": 1,
        "total_damage_dealt": damage_dealt,
        "biggest_hit_dealt": damage_dealt,
        **extras,
    }
    _upsert_user_stats(db, user_id, **kwargs)
    if character_id:
        _upsert_character_stats(db, character_id, user_id, **kwargs)
    if campaign_id:
        _upsert_campaign_stats(db, campaign_id, total_rolls=len(all_rolls),
                               total_attacks=1, total_damage_dealt=damage_dealt,
                               biggest_hit=damage_dealt,
                               total_ones=extras.get("total_ones", 0))
    _upsert_site_stats(db, total_rolls=len(all_rolls), total_attacks=1,
                       total_damage_dealt=damage_dealt,
                       total_ones=extras.get("total_ones", 0),
                       total_max_rolls=extras.get("total_max_rolls", 0))


def track_damage_taken(db: Session, user_id: str, character_id: str | None, damage: int):
    """Track damage taken by a character."""
    kwargs = {"total_damage_taken": damage, "biggest_hit_taken": damage}
    _upsert_user_stats(db, user_id, **kwargs)
    if character_id:
        _upsert_character_stats(db, character_id, user_id, **kwargs)


def track_ability_cast(db: Session, user_id: str, character_id: str | None):
    """Track an ability/spell/technique cast."""
    _upsert_user_stats(db, user_id, total_abilities_cast=1)
    if character_id:
        _upsert_character_stats(db, character_id, user_id, total_abilities_cast=1)


def track_calling(db: Session, user_id: str, character_id: str | None,
                  campaign_id: str | None = None):
    """Track a Calling (DP reached 0)."""
    _upsert_user_stats(db, user_id, total_callings=1)
    if character_id:
        _upsert_character_stats(db, character_id, user_id, total_callings=1)
    if campaign_id:
        _upsert_campaign_stats(db, campaign_id, total_callings=1)
    _upsert_site_stats(db, total_callings=1)


def track_calling_outcome(db: Session, user_id: str, character_id: str | None,
                          outcome: str):
    """Track the result of a Calling roll: 'clean', 'scarred', or 'dead'."""
    kwargs = {}
    if outcome == "clean":
        kwargs = {"callings_survived": 1, "callings_clean": 1}
    elif outcome == "scarred":
        kwargs = {"callings_survived": 1, "callings_scarred": 1}
    elif outcome == "dead":
        kwargs = {"callings_died": 1}
    if not kwargs:
        return
    _upsert_user_stats(db, user_id, **kwargs)
    if character_id:
        _upsert_character_stats(db, character_id, user_id, **kwargs)


def track_level_up(db: Session, user_id: str, character_id: str | None, new_level: int):
    """Track a character level up."""
    kwargs = {"total_level_ups": 1, "highest_level_reached": new_level}
    _upsert_user_stats(db, user_id, **kwargs)
    if character_id:
        _upsert_character_stats(db, character_id, user_id, **kwargs)


def track_battle_scar(db: Session, user_id: str, character_id: str | None):
    _upsert_user_stats(db, user_id, total_battle_scars=1)
    if character_id:
        _upsert_character_stats(db, character_id, user_id, total_battle_scars=1)


def track_message(db: Session, user_id: str, character_id: str | None,
                  campaign_id: str | None = None):
    _upsert_user_stats(db, user_id, total_messages_sent=1)
    if character_id:
        _upsert_character_stats(db, character_id, user_id, total_messages_sent=1)
    if campaign_id:
        _upsert_campaign_stats(db, campaign_id, total_messages=1)
    _upsert_site_stats(db, total_messages=1)


def track_boost(db: Session, user_id: str, character_id: str | None,
                used_bap: bool, tether_count: int):
    kwargs = {
        "total_boosts_applied": 1,
        "total_bap_used": 1 if used_bap else 0,
        "total_tethers_invoked": tether_count,
    }
    _upsert_user_stats(db, user_id, **kwargs)
    if character_id:
        _upsert_character_stats(db, character_id, user_id, **kwargs)


def track_battle_end(db: Session, participant_ids: list[tuple[str, str | None]],
                     campaign_id: str | None = None):
    """Mark battle survived for all participants. participant_ids = [(user_id, character_id)]"""
    for user_id, character_id in participant_ids:
        _upsert_user_stats(db, user_id, battles_survived=1)
        if character_id:
            _upsert_character_stats(db, character_id, user_id, battles_survived=1)
    if campaign_id:
        _upsert_campaign_stats(db, campaign_id, total_battles=1)
    _upsert_site_stats(db, total_battles=1)


def track_miss(db: Session, user_id: str, character_id: str | None, bap_was_active: bool = False):
    kwargs = {"miss_count": 1}
    if bap_was_active:
        kwargs["bap_miss_count"] = 1
    _upsert_user_stats(db, user_id, **kwargs)
    if character_id:
        _upsert_character_stats(db, character_id, user_id, **kwargs)


def track_npc_damage(db: Session, user_id: str, damage: int):
    _upsert_user_stats(db, user_id, npc_damage_dealt=damage)


def track_scene_update(db: Session, user_id: str):
    _upsert_user_stats(db, user_id, scene_updates=1)


def track_battle_initiated(db: Session, user_id: str):
    _upsert_user_stats(db, user_id, battles_initiated=1)


def track_summon_fired(db: Session, user_id: str, character_id: str | None):
    _upsert_user_stats(db, user_id, summons_fired=1)
    if character_id:
        _upsert_character_stats(db, character_id, user_id, summons_fired=1)


def track_image_shared(db: Session, user_id: str):
    _upsert_user_stats(db, user_id, images_shared=1)


def track_campaign_created(db: Session, user_id: str):
    _upsert_user_stats(db, user_id, campaigns_created=1)


def track_lore_created(db: Session, user_id: str):
    _upsert_user_stats(db, user_id, lore_entries_created=1)


def track_item_gifted(db: Session, user_id: str):
    _upsert_user_stats(db, user_id, items_gifted=1)


def track_npc_created(db: Session, user_id: str):
    _upsert_user_stats(db, user_id, npcs_created=1)


def track_stat_check_outcome(
    db: Session, user_id: str, character_id: str | None,
    stat: str, die_roll: int, stat_value: int, edge: int,
    debuff_modifier: int, player_total: int, outcome: str,
):
    """Track a resolved stat check for achievement purposes."""
    stat = stat.upper()
    kwargs = {}

    # Per-stat ones and maxes
    if die_roll == 1:
        kwargs[f"{stat.lower()}_check_ones"] = 1
    if die_roll == 6:
        kwargs[f"{stat.lower()}_check_maxes"] = 1
        if stat_value == 1:
            kwargs["stat_one_check_maxes"] = 1

    # Debuff-related outcomes
    if debuff_modifier < 0:
        if outcome == "win":
            kwargs["checks_while_debuffed_won"] = 1
        if player_total <= 0:
            kwargs["checks_total_zero_or_below"] = 1

    # Two-parter achievement state
    won = outcome == "win"
    kwargs[f"last_{stat.lower()}_check_won"] = won

    if kwargs:
        _upsert_user_stats(db, user_id, **kwargs)
        if character_id:
            _upsert_character_stats(db, character_id, user_id, **kwargs)


def commit_stats(db: Session, user_id: str | None = None) -> list[str]:
    """Commit stat changes and optionally evaluate achievements. Returns newly-awarded IDs."""
    try:
        db.commit()
        if user_id:
            from backend.achievements import check_and_award
            return check_and_award(user_id, db)
    except Exception as e:
        logger.warning(f"Stats commit failed: {e}")
        db.rollback()
    return []
