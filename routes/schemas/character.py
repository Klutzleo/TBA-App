"""
Pydantic schemas for Character and Party management (TBA v1.5).
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional
from datetime import datetime


class CharacterStats(BaseModel):
    """Character stats (must sum to 6)."""
    pp: int = Field(..., ge=1, le=3, description="Physical Power (1-3)")
    ip: int = Field(..., ge=1, le=3, description="Intellect Power (1-3)")
    sp: int = Field(..., ge=1, le=3, description="Social Power (1-3)")
    
    @field_validator('pp', 'ip', 'sp')
    @classmethod
    def validate_stat_range(cls, v):
        if not 1 <= v <= 3:
            raise ValueError('Each stat must be between 1 and 3')
        return v


class WeaponSchema(BaseModel):
    """Weapon (Phase 2)."""
    name: str
    bonus_attack: int = Field(default=0, description="Bonus to attack rolls")
    bonus_damage: int = Field(default=0, description="Bonus to damage")


class ArmorSchema(BaseModel):
    """Armor (Phase 2)."""
    name: str
    bonus_defense: int = Field(default=0, description="Bonus to defense rolls")
    bonus_dp: int = Field(default=0, description="Bonus to max DP")


class CharacterCreate(BaseModel):
    """Request to create a new character."""
    name: str = Field(..., min_length=1, max_length=100)
    owner_id: str = Field(..., description="User ID or API key identifier")
    level: int = Field(default=1, ge=1, le=10, description="Starting level (1-10)")
    pp: int = Field(..., ge=1, le=3)
    ip: int = Field(..., ge=1, le=3)
    sp: int = Field(..., ge=1, le=3)
    attack_style: str = Field(..., description="Chosen attack die (e.g., '3d4', '2d6')")
    weapon: Optional[WeaponSchema] = None
    armor: Optional[ArmorSchema] = None
    
    @field_validator('pp', 'ip', 'sp', mode='before')
    @classmethod
    def validate_stats_sum(cls, v, info):
        # Collect all three stats when they're available
        if info.data:
            pp = info.data.get('pp', v if info.field_name == 'pp' else None)
            ip = info.data.get('ip', v if info.field_name == 'ip' else None)
            sp = info.data.get('sp', v if info.field_name == 'sp' else None)
            
            if all(s is not None for s in [pp, ip, sp]):
                if pp + ip + sp != 6:
                    raise ValueError(f'Stats must sum to 6, got {pp + ip + sp}')
        return v
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "Kai",
            "owner_id": "user_123",
            "level": 5,
            "pp": 3,
            "ip": 2,
            "sp": 1,
            "attack_style": "3d4",
            "weapon": None,
            "armor": None
        }
    })


class CharacterUpdate(BaseModel):
    """Request to update an existing character."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    level: Optional[int] = Field(None, ge=1, le=10, description="Level (auto-recalculates stats)")
    dp: Optional[int] = Field(None, ge=0, description="Current DP (manual adjustment)")
    attack_style: Optional[str] = Field(None, description="Change attack style")
    weapon: Optional[WeaponSchema] = None
    armor: Optional[ArmorSchema] = None


class CharacterResponse(BaseModel):
    """Character response (from DB)."""
    id: str
    name: str
    owner_id: str
    level: int
    pp: int
    ip: int
    sp: int
    dp: int
    max_dp: int
    edge: int
    bap: int
    attack_style: str
    defense_die: str
    weapon: Optional[dict] = None
    armor: Optional[dict] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class PartyCreate(BaseModel):
    """Request to create a new party."""
    name: str = Field(..., min_length=1, max_length=100)
    gm_id: str = Field(..., description="GM/Storyweaver user ID")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "The Crimson Dawn",
            "gm_id": "gm_alice"
        }
    })


class PartyResponse(BaseModel):
    """Party response (from DB)."""
    id: str
    name: str
    gm_id: str
    session_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class PartyMemberAdd(BaseModel):
    """Request to add a character to a party."""
    character_id: str = Field(..., description="Character UUID to add")


class PartyMemberResponse(BaseModel):
    """Party member response (character + join date)."""
    character: CharacterResponse
    joined_at: datetime
