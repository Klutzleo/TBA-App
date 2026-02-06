"""
Pydantic schemas for DB-integrated combat (Phase 1 character persistence).
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from uuid import UUID


class AttackByIdRequest(BaseModel):
    """Request for combat attack using persisted character IDs."""
    attacker_id: UUID = Field(..., description="Attacker character UUID")
    defender_id: UUID = Field(..., description="Defender character UUID")
    technique_name: str = Field(description="e.g., 'Slash', 'Fireball', 'Persuade'")
    stat_type: str = Field(description="Stat type: 'PP' | 'IP' | 'SP'")
    bap_triggered: bool = Field(default=False, description="Trigger BAP bonus?")
    campaign_id: Optional[UUID] = Field(default=None, description="Campaign UUID (for WebSocket broadcast)")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "attacker_id": "550e8400-e29b-41d4-a716-446655440000",
            "defender_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
            "technique_name": "Slash",
            "stat_type": "PP",
            "bap_triggered": False
        }
    })


class Encounter1v1ByIdRequest(BaseModel):
    """Request for 1v1 encounter using persisted character IDs."""
    attacker_id: UUID = Field(..., description="Attacker character UUID")
    defender_id: UUID = Field(..., description="Defender character UUID")
    technique_name: str = Field(description="e.g., 'Slash'")
    stat_type: str = Field(description="'PP' | 'IP' | 'SP'")
    max_rounds: int = Field(default=10, ge=1, le=50, description="Max rounds before auto-end")
    persist_results: bool = Field(default=True, description="Save DP changes to database?")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "attacker_id": "550e8400-e29b-41d4-a716-446655440000",
            "defender_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
            "technique_name": "Slash",
            "stat_type": "PP",
            "max_rounds": 5,
            "persist_results": True
        }
    })
