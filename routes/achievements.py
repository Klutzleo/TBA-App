"""
routes/achievements.py
Achievement endpoints — read earned achievements, trigger evaluation.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.models import User, UserAchievement
from backend.achievements import ACHIEVEMENTS, check_and_award
from routes.auth import get_current_user

achievements_router = APIRouter(prefix="/api/achievements", tags=["Achievements"])


@achievements_router.get("/me")
async def get_my_achievements(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(UserAchievement)
        .filter(UserAchievement.user_id == current_user.id)
        .order_by(UserAchievement.earned_at.desc())
        .all()
    )

    result = []
    for row in rows:
        meta = ACHIEVEMENTS.get(row.achievement_id)
        if meta:
            result.append({
                "id": row.achievement_id,
                "earned_at": row.earned_at.isoformat(),
                **meta,
            })

    return {
        "achievements": result,
        "total_earned": len(result),
        "total_points": sum(a["points"] for a in result),
    }


@achievements_router.post("/me/evaluate")
async def evaluate_my_achievements(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Re-check all achievement conditions for the current user. Returns any newly awarded IDs."""
    newly_awarded = check_and_award(current_user.id, db)
    return {
        "newly_awarded": newly_awarded,
        "count": len(newly_awarded),
    }
