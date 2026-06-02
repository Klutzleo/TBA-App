"""
backend/achievements.py
Achievement engine — all conditions hardcoded here.

To add an achievement:
  1. Add its metadata to ACHIEVEMENTS.
  2. Add an award() call in evaluate() under the right stat block.
"""
from sqlalchemy.orm import Session


ACHIEVEMENTS = {
    # ── Roll milestones ────────────────────────────────────────────
    "first_roll": {
        "name": "Dice Touched",
        "description": "Roll your first die.",
        "icon": "🎲",
        "tier": "bronze",
        "points": 5,
    },
    "century_roller": {
        "name": "Century Roller",
        "description": "Roll 100 times.",
        "icon": "💯",
        "tier": "silver",
        "points": 20,
    },
    "thousand_roller": {
        "name": "Thousand Roller",
        "description": "Roll 1,000 times.",
        "icon": "🎯",
        "tier": "gold",
        "points": 50,
    },
    "snake_eyes": {
        "name": "Snake Eyes",
        "description": "Roll a 1.",
        "icon": "💀",
        "tier": "bronze",
        "points": 5,
    },
    "critter": {
        "name": "The Critter",
        "description": "Roll a critical max 3 times.",
        "icon": "⚡",
        "tier": "silver",
        "points": 25,
    },

    # ── Combat ─────────────────────────────────────────────────────
    "first_blood": {
        "name": "First Blood",
        "description": "Land your first attack.",
        "icon": "⚔️",
        "tier": "bronze",
        "points": 5,
    },
    "damage_dealer": {
        "name": "Damage Dealer",
        "description": "Deal 100 total damage.",
        "icon": "💥",
        "tier": "silver",
        "points": 20,
    },
    "heavy_hitter": {
        "name": "Heavy Hitter",
        "description": "Deal 30 or more damage in a single blow.",
        "icon": "🔨",
        "tier": "gold",
        "points": 40,
    },
    "battle_worn": {
        "name": "Battle-Worn",
        "description": "Survive 5 encounters.",
        "icon": "🛡️",
        "tier": "silver",
        "points": 20,
    },

    # ── Callings ───────────────────────────────────────────────────
    "survivor": {
        "name": "Survivor",
        "description": "Survive your first calling.",
        "icon": "🌅",
        "tier": "bronze",
        "points": 10,
    },
    "untouched": {
        "name": "Untouched",
        "description": "Come out clean from a calling (no scars).",
        "icon": "✨",
        "tier": "silver",
        "points": 30,
    },
    "scarred": {
        "name": "Scarred",
        "description": "Earn your first battle scar.",
        "icon": "🩹",
        "tier": "bronze",
        "points": 10,
    },

    # ── Stat Checks ────────────────────────────────────────────────
    "check_novice": {
        "name": "Checking In",
        "description": "Make your first stat check.",
        "icon": "🎯",
        "tier": "bronze",
        "points": 5,
    },
    "iron_will": {
        "name": "Iron Will",
        "description": "Win a stat check while debuffed.",
        "icon": "💪",
        "tier": "silver",
        "points": 30,
    },
    "bottom_of_the_barrel": {
        "name": "Bottom of the Barrel",
        "description": "Roll a total of 0 or below on a stat check.",
        "icon": "📉",
        "tier": "bronze",
        "points": 5,
    },

    # ── Leveling ───────────────────────────────────────────────────
    "rising_star": {
        "name": "Rising Star",
        "description": "Reach level 3.",
        "icon": "⭐",
        "tier": "bronze",
        "points": 15,
    },
    "veteran": {
        "name": "Veteran",
        "description": "Reach level 5.",
        "icon": "🌟",
        "tier": "silver",
        "points": 30,
    },
    "legend": {
        "name": "Legend",
        "description": "Reach level 10.",
        "icon": "🏆",
        "tier": "platinum",
        "points": 100,
    },

    # ── Abilities & Boosts ─────────────────────────────────────────
    "ability_user": {
        "name": "Ability User",
        "description": "Cast your first ability.",
        "icon": "✨",
        "tier": "bronze",
        "points": 5,
    },
    "tethered": {
        "name": "Tethered",
        "description": "Invoke a tether for the first time.",
        "icon": "🔗",
        "tier": "bronze",
        "points": 10,
    },

    # ── Social ─────────────────────────────────────────────────────
    "voice_of_the_tavern": {
        "name": "Voice of the Tavern",
        "description": "Send 100 messages.",
        "icon": "💬",
        "tier": "silver",
        "points": 20,
    },

    # ── Story Weaver (SW-only) ─────────────────────────────────────
    "worldbuilder": {
        "name": "Worldbuilder",
        "description": "Create your first campaign.",
        "icon": "🗺️",
        "tier": "bronze",
        "points": 10,
    },
    "chronicler": {
        "name": "Chronicler",
        "description": "Write 5 lore entries.",
        "icon": "📖",
        "tier": "silver",
        "points": 25,
    },
}


def check_and_award(user_id, db: Session) -> list[str]:
    """
    Load the user's stats, evaluate all achievement conditions, and award any
    newly earned achievements. Returns the list of newly-awarded achievement IDs.
    Call this after any stat update.
    """
    from backend.models import UserStats, UserAchievement

    stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()
    if not stats:
        return []

    earned = {
        row.achievement_id
        for row in db.query(UserAchievement.achievement_id)
        .filter(UserAchievement.user_id == user_id)
        .all()
    }

    newly_awarded: list[str] = []

    def award(achievement_id: str):
        if achievement_id not in earned:
            db.add(UserAchievement(user_id=user_id, achievement_id=achievement_id))
            earned.add(achievement_id)
            newly_awarded.append(achievement_id)

    # ── Roll milestones ────────────────────────────────────────────
    if stats.total_rolls >= 1:
        award("first_roll")
    if stats.total_rolls >= 100:
        award("century_roller")
    if stats.total_rolls >= 1000:
        award("thousand_roller")
    if stats.total_ones >= 1:
        award("snake_eyes")
    if stats.total_max_rolls >= 3:
        award("critter")

    # ── Combat ─────────────────────────────────────────────────────
    if stats.total_attacks >= 1:
        award("first_blood")
    if stats.total_damage_dealt >= 100:
        award("damage_dealer")
    if stats.biggest_hit_dealt >= 30:
        award("heavy_hitter")
    if stats.battles_survived >= 5:
        award("battle_worn")

    # ── Callings ───────────────────────────────────────────────────
    if stats.callings_survived >= 1:
        award("survivor")
    if stats.callings_clean >= 1:
        award("untouched")
    if stats.total_battle_scars >= 1:
        award("scarred")

    # ── Stat checks ────────────────────────────────────────────────
    if stats.total_stat_checks >= 1:
        award("check_novice")
    if stats.checks_while_debuffed_won >= 1:
        award("iron_will")
    if stats.checks_total_zero_or_below >= 1:
        award("bottom_of_the_barrel")

    # ── Leveling ───────────────────────────────────────────────────
    if stats.highest_level_reached >= 3:
        award("rising_star")
    if stats.highest_level_reached >= 5:
        award("veteran")
    if stats.highest_level_reached >= 10:
        award("legend")

    # ── Abilities & boosts ─────────────────────────────────────────
    if stats.total_abilities_cast >= 1:
        award("ability_user")
    if stats.total_tethers_invoked >= 1:
        award("tethered")

    # ── Social ─────────────────────────────────────────────────────
    if stats.total_messages_sent >= 100:
        award("voice_of_the_tavern")

    # ── SW ─────────────────────────────────────────────────────────
    if stats.campaigns_created >= 1:
        award("worldbuilder")
    if stats.lore_entries_created >= 5:
        award("chronicler")

    if newly_awarded:
        db.commit()

    return newly_awarded
