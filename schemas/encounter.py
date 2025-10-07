from pydantic import BaseModel
from typing import List, Optional
from schemas.actor import Actor

class Encounter(BaseModel):
    actors: List[Actor]
    round: Optional[int] = 1
    location: Optional[str] = None
    tags: Optional[List[str]] = []