from typing import Optional, Dict, List, Literal, Any
from pydantic import BaseModel

class ActionSchema(BaseModel):
    name: str
    type: Literal["spell", "technique", "custom", "buff", "debuff", "summon"]
    target: Optional[Literal["single", "aoe"]] = "single"
    traits: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    description: Optional[str] = None

class ChatMessageSchema(BaseModel):
    actor: str  # Character performing the action
    triggered_by: Optional[str] = None  # Who initiated it (player name or "Story Weaver")
    message: str  # Raw narration or dialogue
    context: Optional[str] = None  # Scene, emotional framing, etc.
    action: Optional[ActionSchema] = None  # Spell, technique, or custom move
    tethers: Optional[List[str]] = None  # Emotional anchors
    roll: Optional[Dict[str, Any]] = None  # Dice metadata
    timestamp: Optional[str] = None  # Optional for logging