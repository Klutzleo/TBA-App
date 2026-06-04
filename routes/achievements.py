"""
routes/achievements.py
Achievement endpoints.

GET  /api/achievements/me          — all achievements (earned + locked) with rarity %
POST /api/achievements/me/evaluate — re-run check_and_award for the current user
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.db import get_db
from backend.models import User, UserAchievement, SiteStats
from backend.achievements import ACHIEVEMENTS, BADGE_SHOWCASE_THRESHOLD, check_and_award
from routes.auth import get_current_user

achievements_router = APIRouter(prefix="/api/achievements", tags=["Achievements"])


def _rarity_label(pct: float) -> str:
    if pct > 25:
        return "common"
    if pct > 10:
        return "uncommon"
    if pct > 1:
        return "rare"
    if pct > 0.1:
        return "ultra_rare"
    return "legendary"


def _format_rarity(pct: float) -> str:
    """Format rarity % — three decimal places for ultra rare and legendary."""
    if pct <= 0.1:
        return f"{pct:.3f}%"
    if pct <= 1:
        return f"{pct:.2f}%"
    return f"{pct:.1f}%"


@achievements_router.get("/me")
async def get_my_achievements(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns every achievement — earned and unearned — so the frontend can
    render all profile sections with locked achievements greyed out.

    Each achievement includes:
      earned        bool
      earned_at     ISO string or null
      rarity_pct    float (% of all players who earned it)
      rarity_label  common / uncommon / rare / ultra_rare / legendary
      rarity_display formatted string e.g. "0.031%"
      ...all metadata fields from ACHIEVEMENTS dict
    """
    # Count earn records per achievement across all users (for rarity)
    earn_counts: dict[str, int] = {
        row.achievement_id: row.count
        for row in db.query(
            UserAchievement.achievement_id,
            func.count(UserAchievement.id).label("count"),
        ).group_by(UserAchievement.achievement_id).all()
    }

    # Total player count from site stats
    site = db.query(SiteStats).filter(SiteStats.id == 1).first()
    total_players = max(site.total_players, 1) if site else 1

    # This user's earned achievements
    earned_rows = (
        db.query(UserAchievement)
        .filter(UserAchievement.user_id == current_user.id)
        .all()
    )
    earned_map: dict[str, str] = {
        row.achievement_id: row.earned_at.isoformat()
        for row in earned_rows
    }

    # Total points earned
    total_points = sum(
        ACHIEVEMENTS[aid]["points"]
        for aid in earned_map
        if aid in ACHIEVEMENTS
    )

    # Badge showcase unlocked?
    badge_showcase_unlocked = (
        "badges_we_aint_got" in earned_map or total_points >= BADGE_SHOWCASE_THRESHOLD
    )

    results = []
    for achievement_id, meta in ACHIEVEMENTS.items():
        earned_at = earned_map.get(achievement_id)
        count = earn_counts.get(achievement_id, 0)
        pct = round((count / total_players) * 100, 3)
        label = _rarity_label(pct)

        results.append({
            "id": achievement_id,
            "earned": earned_at is not None,
            "earned_at": earned_at,
            "rarity_pct": pct,
            "rarity_label": label,
            "rarity_display": _format_rarity(pct),
            **meta,
        })

    # Sort: earned first (desc by earned_at), then unearned alphabetically by name
    earned_list = sorted(
        [a for a in results if a["earned"]],
        key=lambda a: a["earned_at"],
        reverse=True,
    )
    unearned_list = sorted(
        [a for a in results if not a["earned"]],
        key=lambda a: a["name"],
    )

    from routes.profile import _max_featured
    max_featured = _max_featured(total_points)

    # Load featured badges from profile
    from backend.models import UserProfile
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    featured_badges = profile.featured_badges if profile and profile.featured_badges else []

    return {
        "achievements": earned_list + unearned_list,
        "total_earned": len(earned_map),
        "total_possible": len(ACHIEVEMENTS),
        "total_points": total_points,
        "badge_showcase_unlocked": badge_showcase_unlocked,
        "badge_showcase_threshold": BADGE_SHOWCASE_THRESHOLD,
        "max_featured_slots": max_featured,
        "featured_badges": featured_badges,
        "slot_thresholds": [150, 300, 500],
    }


@achievements_router.post("/me/evaluate")
async def evaluate_my_achievements(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Re-check all achievement conditions for the current user. Returns newly awarded IDs."""
    newly_awarded = check_and_award(current_user.id, db)
    return {
        "newly_awarded": newly_awarded,
        "count": len(newly_awarded),
    }
