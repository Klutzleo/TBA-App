from pydantic import BaseModel
from typing import Optional

class Actor(BaseModel):
    name: str
    dp: int
    max_dp: int
    initiative: Optional[int] = None
    status: Optional[str] = None  # e.g. "conscious", "unconscious", "dead"
    tags: Optional[list[str]] = []  # e.g. ["tank", "caster", "vengeful"]