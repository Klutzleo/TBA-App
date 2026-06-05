"""
routes/public_profile.py
No-auth public profile endpoints — accessible without login.
Used by /u/{username} shareable profile pages.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.models import User, UserProfile, UserStats, Character, Campaign, CampaignMembership

public_router = APIRouter(prefix="/api/public", tags=["Public"])


def _public_stats(stats) -> dict:
    if not stats:
        return {}
    return {
        "total_rolls":         stats.total_rolls or 0,
        "total_ones":          stats.total_ones or 0,
        "total_max_rolls":     stats.total_max_rolls or 0,
        "total_attacks":       stats.total_attacks or 0,
        "total_damage_dealt":  stats.total_damage_dealt or 0,
        "biggest_hit_dealt":   stats.biggest_hit_dealt or 0,
        "total_stat_checks":   stats.total_stat_checks or 0,
        "total_abilities_cast":stats.total_abilities_cast or 0,
        "battles_survived":    stats.battles_survived or 0,
        "total_callings":      stats.total_callings or 0,
        "total_messages_sent": stats.total_messages_sent or 0,
        "total_bap_used":      stats.total_bap_used or 0,
    }


def _public_char(char) -> dict:
    return {
        "id":          str(char.id),
        "name":        char.name,
        "level":       char.level,
        "portrait_url":char.portrait_url,
        "pp": char.pp, "ip": char.ip, "sp": char.sp,
        "dp": char.dp, "edge": char.edge, "bap": char.bap,
    }


@public_router.get("/profile/{username}")
async def public_profile(username: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="Player not found")

    profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
    if profile and not profile.is_public:
        raise HTTPException(status_code=403, detail="This profile is private")

    stats = db.query(UserStats).filter(UserStats.user_id == user.id).first()

    characters = db.query(Character).filter(
        Character.user_id == str(user.id),
        Character.is_npc == False,
        Character.status != "archived",
    ).order_by(Character.created_at.desc()).all()

    campaigns = db.query(Campaign).filter(
        Campaign.created_by_user_id == user.id,
    ).order_by(Campaign.created_at.desc()).all()

    sw_campaigns = []
    for c in campaigns:
        player_count = db.query(CampaignMembership).filter(
            CampaignMembership.campaign_id == c.id,
            CampaignMembership.role == "player",
            CampaignMembership.left_at == None,
        ).count()
        sw_campaigns.append({
            "id":         str(c.id),
            "name":       c.name,
            "status":     c.status,
            "player_count": player_count,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })

    from backend.models import UserAchievement
    from backend.achievements import ACHIEVEMENTS
    earned_rows = db.query(UserAchievement).filter(UserAchievement.user_id == user.id).all()
    total_points = sum(
        ACHIEVEMENTS[r.achievement_id]["points"]
        for r in earned_rows if r.achievement_id in ACHIEVEMENTS
    )

    return {
        "username":    user.username,
        "created_at":  user.created_at.isoformat() if user.created_at else None,
        "profile": {
            "bio":           profile.bio if profile else None,
            "avatar_url":    profile.avatar_url if profile else None,
            "featured_badges": profile.featured_badges if profile and profile.featured_badges else [],
        },
        "stats":            _public_stats(stats),
        "last_played_at":   stats.last_played_at.isoformat() if stats and stats.last_played_at else None,
        "characters":       [_public_char(c) for c in characters],
        "sw_campaigns":     sw_campaigns,
        "total_achievements": len(earned_rows),
        "total_points":     total_points,
    }


@public_router.get("/achievements/{username}")
async def public_achievements(username: str, db: Session = Depends(get_db)):
    """Full achievement list for any public profile — earned and locked, for FOMO."""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="Player not found")

    profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
    if profile and not profile.is_public:
        raise HTTPException(status_code=403, detail="This profile is private")

    from routes.achievements import _build_achievements_response
    return _build_achievements_response(user.id, db)
