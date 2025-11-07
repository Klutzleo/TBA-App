from typing import Dict, Optional
from pydantic import BaseModel

class ResolveRollSchema(BaseModel):
    actor: str  # Who is resolving the roll
    roll_type: str  # e.g. "defense", "attack", "check"
    die: str  # e.g. "1d10"
    modifiers: Optional[Dict[str, int]] = None
    result: int  # Final roll result
    context: Optional[str] = None
    triggered_by: Optional[str] = None