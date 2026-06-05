"""
routes/profile.py
Player profile + stats API endpoints.
"""

import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.models import User, UserStats, CharacterStats, UserProfile, Character, SiteStats, Campaign, CampaignMembership
from routes.auth import get_current_user

logger = logging.getLogger(__name__)

profile_router = APIRouter(prefix="/api/profile", tags=["profile"])


def _stats_dict(row) -> dict:
    if not row:
        return {}
    exclude = {"user_id", "character_id", "updated_at", "first_played_at", "last_played_at"}
    return {c.name: getattr(row, c.name) or 0
            for c in row.__table__.columns if c.name not in exclude}


# Points needed to unlock each badge showcase slot
BADGE_SLOT_THRESHOLDS = [150, 300, 500]  # 3, 4, 5 slots

def _badge_slots_available(total_points: int) -> int:
    slots = 0
    for threshold in BADGE_SLOT_THRESHOLDS:
        if total_points >= threshold:
            slots += 1
    return slots  # 0 = locked, 1 = 3 slots, 2 = 4 slots, 3 = 5 slots

def _max_featured(total_points: int) -> int:
    unlocked = _badge_slots_available(total_points)
    if unlocked == 0: return 0
    return unlocked + 2  # 1→3, 2→4, 3→5

def _profile_dict(profile: UserProfile | None) -> dict:
    if not profile:
        return {"bio": None, "is_public": True, "discord_username": None, "avatar_url": None, "featured_badges": []}
    return {
        "bio": profile.bio,
        "is_public": profile.is_public,
        "discord_username": profile.discord_username,
        "avatar_url": profile.avatar_url,
        "featured_badges": profile.featured_badges or [],
    }


def _character_summary(char: Character, stats: CharacterStats | None) -> dict:
    return {
        "id": str(char.id),
        "name": char.name,
        "level": char.level,
        "campaign_id": str(char.campaign_id),
        "portrait_url": char.portrait_url,
        "is_npc": char.is_npc,
        "status": char.status,
        "pp": char.pp, "ip": char.ip, "sp": char.sp,
        "dp": char.dp, "edge": char.edge, "bap": char.bap,
        "stats": _stats_dict(stats),
        "first_played_at": stats.first_played_at.isoformat() if stats and stats.first_played_at else None,
        "last_played_at": stats.last_played_at.isoformat() if stats and stats.last_played_at else None,
    }


def _sw_campaigns(db: Session, user_id) -> list:
    campaigns = db.query(Campaign).filter(
        Campaign.created_by_user_id == user_id,
    ).order_by(Campaign.created_at.desc()).all()

    result = []
    for c in campaigns:
        player_count = db.query(CampaignMembership).filter(
            CampaignMembership.campaign_id == c.id,
            CampaignMembership.role == 'player',
            CampaignMembership.left_at == None,
        ).count()
        npc_count = db.query(Character).filter(
            Character.campaign_id == str(c.id),
            Character.is_npc == True,
        ).count()
        result.append({
            "id": str(c.id),
            "name": c.name,
            "status": c.status,
            "player_count": player_count,
            "npc_count": npc_count,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return result


# ----------------------------------------------------------------
# GET /api/profile/me — own full profile (always visible)
# ----------------------------------------------------------------
@profile_router.get("/me")
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stats = db.query(UserStats).filter(UserStats.user_id == current_user.id).first()
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    characters = db.query(Character).filter(
        Character.user_id == str(current_user.id),
        Character.is_npc == False,
        Character.status != 'archived',
    ).order_by(Character.created_at.desc()).all()

    char_data = []
    for char in characters:
        cstats = db.query(CharacterStats).filter(CharacterStats.character_id == char.id).first()
        char_data.append(_character_summary(char, cstats))

    return {
        "user_id": str(current_user.id),
        "username": current_user.username,
        "email": current_user.email,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "profile": _profile_dict(profile),
        "stats": _stats_dict(stats),
        "first_played_at": stats.first_played_at.isoformat() if stats and stats.first_played_at else None,
        "last_played_at": stats.last_played_at.isoformat() if stats and stats.last_played_at else None,
        "characters": char_data,
        "sw_campaigns": _sw_campaigns(db, current_user.id),
    }


# ----------------------------------------------------------------
# GET /api/profile/{username} — public profile (respects is_public)
# ----------------------------------------------------------------
@profile_router.get("/{username}")
async def get_public_profile(
    username: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="Player not found")

    profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
    is_own = str(current_user.id) == str(user.id)

    if not is_own and profile and not profile.is_public:
        return {
            "user_id": str(user.id),
            "username": user.username,
            "is_private": True,
            "profile": {"bio": None, "avatar_url": profile.avatar_url if profile else None},
        }

    stats = db.query(UserStats).filter(UserStats.user_id == user.id).first()
    characters = db.query(Character).filter(
        Character.user_id == str(user.id),
        Character.is_npc == False,
        Character.status != 'archived',
    ).order_by(Character.created_at.desc()).all()

    char_data = []
    for char in characters:
        cstats = db.query(CharacterStats).filter(CharacterStats.character_id == char.id).first()
        char_data.append(_character_summary(char, cstats))

    return {
        "user_id": str(user.id),
        "username": user.username,
        "is_own": is_own,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "profile": _profile_dict(profile),
        "stats": _stats_dict(stats),
        "first_played_at": stats.first_played_at.isoformat() if stats and stats.first_played_at else None,
        "last_played_at": stats.last_played_at.isoformat() if stats and stats.last_played_at else None,
        "characters": char_data,
        "sw_campaigns": _sw_campaigns(db, user.id),
    }


# ----------------------------------------------------------------
# PATCH /api/profile/me — update bio, avatar, privacy settings
# ----------------------------------------------------------------
@profile_router.patch("/me")
async def update_my_profile(
    req: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    if not profile:
        profile = UserProfile(user_id=current_user.id)
        db.add(profile)

    if "bio" in req:
        profile.bio = req["bio"][:300] if req["bio"] else None
    if "is_public" in req:
        profile.is_public = bool(req["is_public"])
    if "avatar_url" in req:
        profile.avatar_url = req["avatar_url"]

    db.commit()
    return {"ok": True, "profile": _profile_dict(profile)}


# ----------------------------------------------------------------
# PATCH /api/profile/me/featured-badges — save badge showcase picks
# ----------------------------------------------------------------
@profile_router.patch("/me/featured-badges")
async def update_featured_badges(
    req: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from backend.models import UserAchievement, UserStats
    from backend.achievements import ACHIEVEMENTS

    badge_ids = req.get("featured_badges", [])
    if not isinstance(badge_ids, list):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="featured_badges must be a list")

    # Calculate how many slots this user has
    stats = db.query(UserStats).filter(UserStats.user_id == current_user.id).first()
    earned_pts = 0
    if stats:
        earned_rows = db.query(UserAchievement).filter(UserAchievement.user_id == current_user.id).all()
        earned_pts = sum(ACHIEVEMENTS[r.achievement_id]["points"] for r in earned_rows if r.achievement_id in ACHIEVEMENTS)

    max_slots = _max_featured(earned_pts)
    if max_slots == 0:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Badge showcase not yet unlocked")

    # Validate — must be earned achievements, max slots allowed
    earned_ids = {r.achievement_id for r in db.query(UserAchievement).filter(UserAchievement.user_id == current_user.id).all()}
    valid = [b for b in badge_ids if b in earned_ids and b in ACHIEVEMENTS][:max_slots]

    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    if not profile:
        profile = UserProfile(user_id=current_user.id)
        db.add(profile)

    profile.featured_badges = valid
    db.commit()
    return {"ok": True, "featured_badges": valid, "max_slots": max_slots}


# ----------------------------------------------------------------
# GET /api/profile/site/stats — global boast bar numbers
# ----------------------------------------------------------------
@profile_router.get("/site/stats")
async def get_site_stats(db: Session = Depends(get_db)):
    from sqlalchemy import func as _func
    row = db.query(SiteStats).filter(SiteStats.id == 1).first()

    # Always count players live — total_players was never tracked incrementally
    total_players = db.query(_func.count(_func.distinct(CampaignMembership.user_id))).filter(
        CampaignMembership.role == 'player',
        CampaignMembership.left_at == None,
    ).scalar() or 0

    from backend.models import UserAchievement
    total_achievements = db.query(_func.count(UserAchievement.id)).scalar() or 0

    if not row:
        return {"total_rolls": 0, "total_ones": 0, "total_attacks": 0,
                "total_callings": 0, "total_messages": 0, "total_battles": 0,
                "total_players": total_players, "total_damage_dealt": 0,
                "total_achievements": total_achievements}
    return {
        "total_rolls": row.total_rolls,
        "total_ones": row.total_ones,
        "total_attacks": row.total_attacks,
        "total_callings": row.total_callings,
        "total_messages": row.total_messages,
        "total_battles": row.total_battles,
        "total_players": total_players,
        "total_damage_dealt": row.total_damage_dealt,
        "total_achievements": total_achievements,
    }
