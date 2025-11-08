from typing import Dict, Optional, List, Any
from pydantic import BaseModel

class CombatLogEntrySchema(BaseModel):
    actor: str
    timestamp: str
    context: Optional[str] = None
    triggered_by: Optional[str] = None
    narration: Optional[str] = None
    action: Optional[Dict[str, Any]] = None
    roll: Optional[Dict[str, Any]] = None
    outcome: Optional[str] = None
    tethers: Optional[List[str]] = None
    log: Optional[List[Dict[str, Any]]] = None

class CombatReplayRequest(BaseModel):
    actor: Optional[str] = None
    encounter_id: Optional[str] = None
    since: Optional[str] = None  # ISO timestamp

class CombatEchoRequest(BaseModel):
    actor: Optional[str] = None
    encounter_id: Optional[str] = None
    tether: Optional[str] = None
    since: Optional[str] = None