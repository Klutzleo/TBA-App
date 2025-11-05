from pydantic import BaseModel
from typing import Optional, Dict, Any


class EffectPreviewSchema(BaseModel):
    actor: str
    effect: str
    modifiers: Optional[Dict[str, int]] = None
    context: Optional[str] = None
    narrate: Optional[bool] = False


class SimulatedOutcomeSchema(BaseModel):
    DP_change: int
    status: str
    area_damage: bool


class EffectPreviewResponseSchema(BaseModel):
    status: str
    actor: str
    simulated_outcome: SimulatedOutcomeSchema
    narration: Optional[str] = None


class EffectResolveSchema(BaseModel):
    actor: str
    effect: str
    source: Optional[str] = None
    modifiers: Optional[Dict[str, int]] = None
    context: Optional[str] = None


class EffectResolveResponseSchema(BaseModel):
    status: str
    actor: str
    applied_effect: str
    outcome: Dict[str, Any]
    narration: Optional[str] = None


class EffectUndoSchema(BaseModel):
    actor: str
    effect_id: str
    reason: Optional[str] = None


class EffectUndoResponseSchema(BaseModel):
    status: str
    actor: str
    undone_effect: str
    rollback_successful: bool
    narration: Optional[str] = None


class CustomEffectSchema(BaseModel):
    name: str
    type: str  # e.g. damage, healing, control
    base: int
    status: Optional[str] = None
    area: Optional[bool] = False
    narration: Optional[str] = None