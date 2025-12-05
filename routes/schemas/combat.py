from typing import Dict, Optional, List, Any
from pydantic import BaseModel, Field


# ============================================================================
# EXISTING SCHEMAS (keep as-is)
# ============================================================================

class CombatLogEntrySchema(BaseModel):
    actor: str
    timestamp: str
    context: Optional[str] = None
    triggered_by: Optional[str] = None
    narration: Optional[str] = None
    action: Optional[Dict[str, Any]] = None
    roll: Optional[Dict[str, Any]] = None
    outcome: Optional[str] = None
    tethers: Optional[List[str]] = None
    log: Optional[List[Dict[str, Any]]] = None


class CombatReplayRequest(BaseModel):
    actor: Optional[str] = None
    encounter_id: Optional[str] = None
    since: Optional[str] = None  # ISO timestamp


class CombatEchoRequest(BaseModel):
    actor: Optional[str] = None
    encounter_id: Optional[str] = None
    tether: Optional[str] = None
    since: Optional[str] = None


# ============================================================================
# PHASE 1 MVP SCHEMAS (TBA v1.5 Multi-Die Combat)
# ============================================================================

class CharacterStats(BaseModel):
    """TBA v1.5 character stats (1-3 each, total = 6)."""
    pp: int = Field(..., ge=1, le=3, description="Physical Power (1-3)")
    ip: int = Field(..., ge=1, le=3, description="Intellect Power (1-3)")
    sp: int = Field(..., ge=1, le=3, description="Social Power (1-3)")

    class Config:
        json_schema_extra = {"example": {"pp": 3, "ip": 2, "sp": 1}}


class Weapon(BaseModel):
    """Weapon (stubbed for Phase 2)."""
    name: str
    bonus_attack: int = Field(default=0, description="Bonus to attack rolls (Phase 2)")
    bonus_damage: int = Field(default=0, description="Bonus to damage (Phase 2)")

    class Config:
        json_schema_extra = {"example": {"name": "Iron Sword", "bonus_attack": 1, "bonus_damage": 2}}


class Armor(BaseModel):
    """Armor (stubbed for Phase 2)."""
    name: str
    bonus_defense: int = Field(default=0, description="Bonus to defense rolls (Phase 2)")
    bonus_dp: int = Field(default=0, description="Bonus to DP (Phase 2)")

    class Config:
        json_schema_extra = {"example": {"name": "Leather Armor", "bonus_defense": 1, "bonus_dp": 3}}


class Character(BaseModel):
    """TBA v1.5 character for combat."""
    name: str
    level: int = Field(..., ge=1, le=10, description="Character level (1-10)")
    stats: CharacterStats
    dp: int = Field(..., ge=1, description="Current Damage Points")
    edge: int = Field(default=0, ge=0, le=5, description="Edge bonus (0-5)")
    bap: int = Field(default=1, ge=1, le=5, description="Bonus Action Points (1-5)")
    attack_style: str = Field(description="Chosen attack die (e.g., '3d4', '2d6', '1d8')")
    defense_die: str = Field(description="Fixed defense die per level (e.g., '1d8')")
    weapon: Optional[Weapon] = Field(default=None, description="Weapon (Phase 2)")
    armor: Optional[Armor] = Field(default=None, description="Armor (Phase 2)")
    session_id: Optional[str] = Field(default=None, description="Session ID for grouping")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Alice",
                "level": 5,
                "stats": {"pp": 3, "ip": 2, "sp": 1},
                "dp": 30,
                "edge": 2,
                "bap": 3,
                "attack_style": "3d4",
                "defense_die": "1d8",
                "weapon": None,
                "armor": None,
                "session_id": "party-123"
            }
        }


class AttackRequest(BaseModel):
    """Request for multi-die attack resolution."""
    attacker: Character
    defender: Character
    technique_name: str = Field(description="e.g., 'Slash', 'Fireball', 'Persuade'")
    stat_type: str = Field(description="Stat type: 'PP' | 'IP' | 'SP'")
    bap_triggered: bool = Field(default=False, description="Trigger BAP bonus?")

    class Config:
        json_schema_extra = {
            "example": {
                "attacker": {
                    "name": "Alice",
                    "level": 5,
                    "stats": {"pp": 3, "ip": 2, "sp": 1},
                    "dp": 30,
                    "edge": 2,
                    "bap": 3,
                    "attack_style": "3d4",
                    "defense_die": "1d8"
                },
                "defender": {
                    "name": "Goblin",
                    "level": 2,
                    "stats": {"pp": 2, "ip": 1, "sp": 1},
                    "dp": 15,
                    "edge": 1,
                    "bap": 1,
                    "attack_style": "1d4",
                    "defense_die": "1d4"
                },
                "technique_name": "Slash",
                "stat_type": "PP",
                "bap_triggered": False
            }
        }


class IndividualRollResult(BaseModel):
    """Single attacker die vs defense die."""
    attacker_roll: int
    defense_roll: int
    margin: int
    damage: int


class AttackResult(BaseModel):
    """Response from multi-die attack."""
    type: str = "multi_die_attack"
    attacker_name: str
    defender_name: str
    individual_rolls: List[IndividualRollResult]
    total_damage: int
    outcome: str = Field(description="'hit' | 'miss' | 'partial_hit'")
    narrative: str
    defender_new_dp: int = Field(description="Defender's DP after damage")
    details: Dict[str, Any] = Field(description="Debug: die strings, stats, edge, bap, etc.")


class InitiativeRequest(BaseModel):
    """Request to roll initiative."""
    combatants: List[Character]

    class Config:
        json_schema_extra = {
            "example": {
                "combatants": [
                    {
                        "name": "Alice",
                        "level": 5,
                        "stats": {"pp": 3, "ip": 2, "sp": 1},
                        "dp": 30,
                        "edge": 2,
                        "bap": 3,
                        "attack_style": "3d4",
                        "defense_die": "1d8"
                    },
                    {
                        "name": "Bob",
                        "level": 4,
                        "stats": {"pp": 2, "ip": 3, "sp": 2},
                        "dp": 25,
                        "edge": 2,
                        "bap": 2,
                        "attack_style": "2d6",
                        "defense_die": "1d6"
                    }
                ]
            }
        }


class InitiativeRoll(BaseModel):
    """Single combatant's initiative result."""
    name: str
    initiative_roll: int
    edge: int
    total: int
    pp: int
    ip: int
    sp: int


class InitiativeResult(BaseModel):
    """Response from initiative roll."""
    initiative_order: List[str] = Field(description="Names in order (highest total first)")
    rolls: List[InitiativeRoll] = Field(description="Detailed roll breakdown")


class Encounter1v1Request(BaseModel):
    """Request for 1v1 encounter simulation."""
    attacker: Character
    defender: Character
    technique_name: str = Field(description="e.g., 'Slash'")
    stat_type: str = Field(description="'PP' | 'IP' | 'SP'")
    max_rounds: int = Field(default=10, ge=1, le=50, description="Max rounds before auto-end")


class RoundAction(BaseModel):
    """Single action in a combat round."""
    actor_name: str
    target_name: str
    technique: str
    damage: int
    narrative: str
    actor_dp: int
    target_dp: int


class Encounter1v1Result(BaseModel):
    """Response from 1v1 encounter."""
    type: str = "encounter_1v1"
    initiative_order: List[str]
    rounds: List[List[RoundAction]] = Field(description="Rounds of combat")
    round_count: int
    final_dp: Dict[str, int] = Field(description="{'attacker_name': int, 'defender_name': int}")
    outcome: str = Field(description="'attacker_wins' | 'defender_wins' | 'timeout'")
    summary: str