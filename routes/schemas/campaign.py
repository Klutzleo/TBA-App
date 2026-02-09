"""
Pydantic schemas for campaign WebSocket messages.
Supports chat (IC/OOC), whispers, combat events, GM narration, and image attachments.
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID


# ============================================================================
# INCOMING MESSAGES (Client → Server)
# ============================================================================

class ChatMessage(BaseModel):
    """Player sends a chat message (IC or OOC)."""
    type: Literal["chat"] = "chat"
    mode: Literal["IC", "OOC"] = "IC"  # In-character or out-of-character
    sender: str  # Character name or player name
    user_id: UUID  # Player's user ID
    message: str
    attachment: Optional[str] = None  # Image URL (uploaded separately)


class WhisperMessage(BaseModel):
    """Player sends a private message to another player."""
    type: Literal["whisper"] = "whisper"
    sender: str
    user_id: UUID
    recipient_user_id: UUID  # Target player
    message: str


class CombatCommand(BaseModel):
    """Player issues a combat command (/attack, /cast, /defend)."""
    type: Literal["combat_command"] = "combat_command"
    command: Literal["attack", "cast", "defend", "item"]
    attacker_id: UUID  # Character performing action
    target_id: Optional[UUID] = None  # Target character (None for self-buffs)
    technique_name: str = "Slash"
    stat_type: Literal["PP", "IP", "SP"] = "PP"
    bap_triggered: bool = False


class GMNarration(BaseModel):
    """GM/Storyweaver sends narrative text to the campaign."""
    type: Literal["narration"] = "narration"
    text: str
    gm_user_id: UUID
    attachment: Optional[str] = None  # Map image, scene art, etc.


class DiceRollRequest(BaseModel):
    """Player requests a dice roll (for skill checks, etc.)."""
    type: Literal["dice_roll"] = "dice_roll"  # ✅ Request type
    roller: str
    dice: str
    reason: Optional[str] = None
    user_id: Optional[UUID] = None  # Make optional (server will provide)


# ============================================================================
# OUTGOING MESSAGES (Server → Clients)
# ============================================================================

class ChatBroadcast(BaseModel):
    """Server broadcasts a chat message to all players in campaign."""
    type: Literal["chat"] = "chat"
    mode: Literal["IC", "OOC"]
    sender: str
    user_id: UUID
    message: str
    attachment: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class WhisperBroadcast(BaseModel):
    """Server sends a private message to a specific player."""
    type: Literal["whisper"] = "whisper"
    sender: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)


class CombatResultBroadcast(BaseModel):
    """Server broadcasts combat result after attack resolution."""
    type: Literal["combat_result"] = "combat_result"
    attacker: str
    defender: str
    technique: str
    damage: int
    defender_new_dp: int
    narrative: str
    individual_rolls: List[Dict[str, Any]]  # Detailed roll breakdown
    outcome: str  # "hit", "partial_hit", "miss"
    timestamp: datetime = Field(default_factory=datetime.now)


class NarrationBroadcast(BaseModel):
    """Server broadcasts GM narration to all players."""
    type: Literal["narration"] = "narration"
    text: str
    attachment: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class DiceRollBroadcast(BaseModel):
    """Broadcast dice roll result to all players."""
    type: Literal["dice_roll_result"] = "dice_roll_result"  # ✅ Result type (different!)
    actor: str
    dice: str
    result: int
    breakdown: List[int]
    text: str = ""
    reason: Optional[str] = ""
    timestamp: Optional[str] = None


class SystemNotification(BaseModel):
    """Server sends system notifications (player joined/left, etc.)."""
    type: Literal["system"] = "system"
    event: Literal["player_joined", "player_left", "combat_started", "combat_ended"]
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)


class InitiativeResultBroadcast(BaseModel):
    """Server broadcasts initiative order at combat start."""
    type: Literal["initiative"] = "initiative"
    order: List[str]  # Character names in turn order
    rolls: List[Dict[str, Any]]  # Detailed roll breakdown
    timestamp: datetime = Field(default_factory=datetime.now)
