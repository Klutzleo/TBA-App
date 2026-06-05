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
from backend.models import User, UserAchievement
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


def _build_achievements_response(user_id, db: Session) -> dict:
    """Shared logic for building the full achievements payload for any user."""
    from backend.models import UserProfile

    # Count earn records per achievement across all users (for rarity)
    earn_counts: dict[str, int] = {
        row.achievement_id: row.count
        for row in db.query(
            UserAchievement.achievement_id,
            func.count(UserAchievement.id).label("count"),
        ).group_by(UserAchievement.achievement_id).all()
    }

    # Count active users directly — SiteStats.total_players isn't maintained
    total_players = db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 1

    earned_rows = (
        db.query(UserAchievement)
        .filter(UserAchievement.user_id == user_id)
        .all()
    )
    earned_map: dict[str, str] = {
        row.achievement_id: row.earned_at.isoformat()
        for row in earned_rows
    }

    total_points = sum(
        ACHIEVEMENTS[aid]["points"]
        for aid in earned_map
        if aid in ACHIEVEMENTS
    )

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

    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
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


@achievements_router.get("/me")
async def get_my_achievements(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns every achievement for the current user — earned and unearned."""
    return _build_achievements_response(current_user.id, db)


@achievements_router.get("/{username}")
async def get_user_achievements(
    username: str,
    db: Session = Depends(get_db),
):
    """Public achievements for any user. Respects profile is_public setting."""
    from fastapi import HTTPException
    from backend.models import UserProfile

    target = db.query(User).filter(User.username == username).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    profile = db.query(UserProfile).filter(UserProfile.user_id == target.id).first()
    if profile and not profile.is_public:
        raise HTTPException(status_code=403, detail="This profile is private")

    return _build_achievements_response(target.id, db)


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
