from fastapi import APIRouter, Request, Query, Depends
from sqlalchemy.orm import Session
from backend.db import get_db
from backend.models import RollLog
from backend.roll_logic import resolve_skill_roll, resolve_combat_roll

roll_blp_fastapi = APIRouter(prefix="/api/roll", tags=["Rolls"])

@roll_blp_fastapi.get("/replay")
def replay_rolls(
    actor: str = Query(...),
    session_id: str = Query(None),
    encounter_id: str = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(RollLog).filter(RollLog.actor == actor)
    if session_id:
        query = query.filter(RollLog.session_id == session_id)
    if encounter_id:
        query = query.filter(RollLog.encounter_id == encounter_id)
    results = query.order_by(RollLog.id.asc()).all()
    return [r.result for r in results]