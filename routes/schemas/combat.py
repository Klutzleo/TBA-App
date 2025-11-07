from typing import Dict, Optional, List
from pydantic import BaseModel

class CombatLogEntrySchema(BaseModel):
    actor: str
    timestamp: str
    context: Optional[str] = None
    triggered_by: Optional[str] = None
    narration: Optional[str] = None
    action: Optional[Dict[str, any]] = None
    roll: Optional[Dict[str, any]] = None
    outcome: Optional[str] = None
    tethers: Optional[List[str]] = None
    log: Optional[List[Dict[str, any]]] = None