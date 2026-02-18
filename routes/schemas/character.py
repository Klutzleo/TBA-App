"""
Pydantic schemas for Character and Party management (TBA v1.5).
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List, Union
from datetime import datetime
from uuid import UUID


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
    campaign_id: Optional[UUID] = Field(None, description="Optional campaign ID to link this character to")
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
    id: UUID
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
    in_calling: bool = False
    times_called: int = 0
    is_called: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PartyCreate(BaseModel):
    """Request to create a new party."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500, description="Optional party description")
    creator_character_id: str = Field(..., description="Character ID of the Story Weaver creating this party")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "The Crimson Dawn",
            "description": "A group of adventurers seeking the ancient artifact",
            "creator_character_id": "550e8400-e29b-41d4-a716-446655440000"
        }
    })


class PartyResponse(BaseModel):
    """Party response (from DB)."""
    id: UUID
    name: str
    description: Optional[str] = None
    story_weaver_id: UUID
    created_by_id: UUID
    session_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PartyMemberAdd(BaseModel):
    """Request to add a character to a party."""
    character_id: UUID = Field(..., description="Character UUID to add")


class PartyMemberResponse(BaseModel):
    """Party member response (character + join date)."""
    character: CharacterResponse
    joined_at: datetime


# ============================================================================
# Phase 2d: Full Character Creation with Ability
# ============================================================================

class AbilityCreate(BaseModel):
    """Ability to create with a character."""
    slot_number: int = Field(default=1, ge=1, le=5, description="Ability slot (1-5)")
    display_name: str = Field(..., min_length=1, max_length=100, description="Human-readable ability name")
    macro_command: str = Field(..., min_length=2, max_length=50, description="Chat command (e.g., /fireball)")
    power_source: str = Field(..., description="Power source: PP, IP, or SP")
    effect_type: str = Field(..., description="Effect: damage, heal, buff, debuff, utility")
    die: str = Field(..., description="Dice expression (e.g., 2d6)")
    is_aoe: bool = Field(default=False, description="Area of effect ability")

    @field_validator('macro_command')
    @classmethod
    def validate_macro_command(cls, v):
        if not v.startswith('/'):
            raise ValueError("Macro command must start with '/'")
        if ' ' in v:
            raise ValueError("Macro command cannot contain spaces")
        return v.lower()

    @field_validator('power_source')
    @classmethod
    def validate_power_source(cls, v):
        valid = ['PP', 'IP', 'SP']
        if v.upper() not in valid:
            raise ValueError(f"Power source must be one of: {', '.join(valid)}")
        return v.upper()

    @field_validator('effect_type')
    @classmethod
    def validate_effect_type(cls, v):
        valid = ['damage', 'heal', 'buff', 'debuff', 'utility']
        if v.lower() not in valid:
            raise ValueError(f"Effect type must be one of: {', '.join(valid)}")
        return v.lower()

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "slot_number": 1,
            "display_name": "Fireball",
            "macro_command": "/fireball",
            "power_source": "IP",
            "effect_type": "damage",
            "die": "2d6",
            "is_aoe": True
        }
    })


class AbilityResponse(BaseModel):
    """Ability response from database."""
    id: UUID
    character_id: UUID
    slot_number: int
    ability_type: str
    display_name: str
    macro_command: str
    power_source: str
    effect_type: str
    die: str
    is_aoe: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FullCharacterCreate(BaseModel):
    """
    Full character creation request with ability and campaign association.

    Creates a character, their starting ability, and adds them to
    the campaign's Story and OOC parties.
    """
    # Campaign association
    campaign_id: UUID = Field(..., description="Campaign ID to join")

    # Character basics
    name: str = Field(..., min_length=1, max_length=100)
    notes: Optional[str] = Field(None, max_length=500, description="Character description/backstory")
    level: int = Field(default=1, ge=1, le=10, description="Starting level (1-10)")

    # Stats (must sum to 6)
    pp: int = Field(..., ge=1, le=3, description="Physical Power (1-3)")
    ip: int = Field(..., ge=1, le=3, description="Intellect Power (1-3)")
    sp: int = Field(..., ge=1, le=3, description="Social Power (1-3)")

    # Weapon
    weapon_die: str = Field(..., description="Weapon die (e.g., '2d4', '1d6')")
    weapon_name: Optional[str] = Field(None, max_length=100, description="Optional weapon name")

    # Defense
    defense_die: Optional[str] = Field(None, description="Defense die (auto-calculated if not provided)")
    armor_name: Optional[str] = Field(None, max_length=100, description="Optional armor name")

    # Starting abilities - can be single ability or list of abilities
    # Accepts either a single AbilityCreate or a list of AbilityCreate
    ability: Union[AbilityCreate, List[AbilityCreate]] = Field(
        ...,
        description="Starting ability or list of abilities for this character"
    )

    @field_validator('pp', 'ip', 'sp', mode='after')
    @classmethod
    def check_stat_range(cls, v):
        if not 1 <= v <= 3:
            raise ValueError('Each stat must be between 1 and 3')
        return v

    @field_validator('ability', mode='after')
    @classmethod
    def normalize_abilities(cls, v):
        """Ensure abilities is always a list."""
        if isinstance(v, list):
            return v
        return [v]

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "campaign_id": "550e8400-e29b-41d4-a716-446655440000",
            "name": "Kai the Bold",
            "level": 3,
            "pp": 3,
            "ip": 2,
            "sp": 1,
            "weapon_die": "2d4",
            "weapon_name": "Steel Longsword",
            "defense_die": None,
            "armor_name": "Leather Armor",
            "ability": {
                "slot_number": 1,
                "display_name": "Power Strike",
                "macro_command": "/strike",
                "power_source": "PP",
                "effect_type": "damage",
                "die": "2d6",
                "is_aoe": False
            }
        }
    })


class FullCharacterResponse(BaseModel):
    """Full character response with abilities and party info."""
    id: UUID
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

    # Phase 2d fields
    notes: Optional[str] = None
    max_uses_per_encounter: int
    current_uses: int
    weapon_bonus: int
    armor_bonus: int
    status: str
    in_calling: bool = False
    times_called: int = 0
    is_called: bool = False

    # Relationships
    abilities: list[AbilityResponse] = []

    # Campaign info
    campaign_id: Optional[UUID] = None
    party_ids: list[str] = []  # IDs of parties the character was added to

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
