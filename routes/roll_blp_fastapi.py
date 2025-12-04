from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Dict, List
import logging

from backend.roll_logic import resolve_combat_roll, simulate_combat

logger = logging.getLogger(__name__)

roll_blp_fastapi = APIRouter(prefix="/roll", tags=["Roll"])

# ============ Pydantic Schemas ============

class CombatRollRequest(BaseModel):
    actor: str
    roll_type: str  # "attack", "defense", "dodge", etc.
    die: str  # e.g., "1d10"
    modifiers: Dict[str, int] = {}
    context: str = ""

class CombatRollResponse(BaseModel):
    actor: str
    roll_type: str
    die: str
    rolls: List[int]
    modifiers: Dict[str, int]
    total: int
    outcome: str  # "success", "failure", "critical"
    context: str

# ============ Endpoints ============

@roll_blp_fastapi.post("/combat", response_model=CombatRollResponse)
async def post_combat_roll(request: Request, data: CombatRollRequest):
    """Resolve a combat roll using backend roll_logic."""
    try:
        # Call domain logic from backend/roll_logic.py
        result = resolve_combat_roll(
            actor=data.actor,
            roll_type=data.roll_type,
            die=data.die,
            modifiers=data.modifiers
        )
        
        logger.info(
            f"[{request.state.request_id}] Combat roll: {data.actor} "
            f"rolled {data.die} = {result['total']}"
        )
        
        return CombatRollResponse(
            actor=data.actor,
            roll_type=data.roll_type,
            die=data.die,
            rolls=result.get("rolls", []),
            modifiers=result.get("modifiers", data.modifiers),
            total=result.get("total", 0),
            outcome=result.get("outcome", "neutral"),
            context=data.context
        )
    except Exception as e:
        logger.error(f"[{request.state.request_id}] Combat roll error: {e}")
        raise

@roll_blp_fastapi.get("/schema")
async def get_roll_schema(request: Request):
    """Get example roll request schema."""
    return {
        "example_combat_roll": {
            "actor": "Kai",
            "roll_type": "attack",
            "die": "1d10",
            "modifiers": {"PP": 2, "Edge": 1},
            "context": "Attacking goblin in volcanic cave"
        }
    }