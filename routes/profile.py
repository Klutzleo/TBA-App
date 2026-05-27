"""
routes/profile.py
Player profile + stats API endpoints.
"""

import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.models import User, UserStats, CharacterStats, UserProfile, Character, SiteStats
from routes.auth import get_current_user

logger = logging.getLogger(__name__)

profile_router = APIRouter(prefix="/api/profile", tags=["profile"])


def _stats_dict(row) -> dict:
    if not row:
        return {}
    exclude = {"user_id", "character_id", "updated_at", "first_played_at", "last_played_at"}
    return {c.name: getattr(row, c.name) or 0
            for c in row.__table__.columns if c.name not in exclude}


def _profile_dict(profile: UserProfile | None) -> dict:
    if not profile:
        return {"bio": None, "is_public": True, "discord_username": None, "avatar_url": None}
    return {
        "bio": profile.bio,
        "is_public": profile.is_public,
        "discord_username": profile.discord_username,
        "avatar_url": profile.avatar_url,
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
# GET /api/profile/site/stats — global boast bar numbers
# ----------------------------------------------------------------
@profile_router.get("/site/stats")
async def get_site_stats(db: Session = Depends(get_db)):
    row = db.query(SiteStats).filter(SiteStats.id == 1).first()
    if not row:
        return {"total_rolls": 0, "total_ones": 0, "total_attacks": 0,
                "total_callings": 0, "total_messages": 0, "total_battles": 0,
                "total_players": 0, "total_damage_dealt": 0}
    return {
        "total_rolls": row.total_rolls,
        "total_ones": row.total_ones,
        "total_attacks": row.total_attacks,
        "total_callings": row.total_callings,
        "total_messages": row.total_messages,
        "total_battles": row.total_battles,
        "total_players": row.total_players,
        "total_damage_dealt": row.total_damage_dealt,
    }
