from pydantic import BaseModel
from typing import Optional

class LoreEntry(BaseModel):
    actor: str  # Who triggered the echo
    round: Optional[int] = None
    tag: Optional[str] = None  # e.g. "vengeful", "blessing", "critical"
    message: str  # The actual echo or memory fragment