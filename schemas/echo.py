from pydantic import BaseModel
from typing import Optional

class Echo(BaseModel):
    actor: str
    round: Optional[int]
    tag: Optional[str]
    effect: Optional[str]
    duration: Optional[int]
    encounter_id: Optional[str]