from fastapi import APIRouter, Body
from typing import Dict, Any, List
from pydantic import BaseModel

combat_blp_fastapi = APIRouter(prefix="/api/combat", tags=["Combat"])

# Temporary in-memory store for combat logs
combat_log_store: List[Dict[str, Any]] = []

# Pydantic schema for a combat log entry
class CombatLogEntry(BaseModel):
    actor: str
    timestamp: str
    context: str | None = None
    triggered_by: str | None = None
    narration: str | None = None
    action: Dict[str, Any] | None = None
    roll: Dict[str, Any] | None = None
    outcome: str | None = None
    tethers: List[str] | None = None
    log: List[Dict[str, Any]] | None = None

# POST endpoint to record a combat log entry
@combat_blp_fastapi.post("/log", response_model=Dict[str, Any])
async def post_combat_log(entry: CombatLogEntry = Body(...)):
    combat_log_store.append(entry.dict())
    return {
        "message": "Combat log entry recorded",
        "entry": entry.dict(),
        "total_entries": len(combat_log_store)
    }

# GET endpoint to retrieve the most recent combat logs
@combat_blp_fastapi.get("/log/recent", response_model=Dict[str, Any])
async def get_recent_combat_logs():
    return {
        "entries": combat_log_store[-10:]
    }