# models.py
"""
TBA-App SQLAlchemy Models

Phase 2d schema with:
- Characters with abilities and status tracking
- Parties (tabs) with campaign grouping
- Party memberships (many-to-many)
- Messages with party routing
- NPCs and combat turns
"""
from sqlalchemy import Column, String, DateTime, JSON, Integer, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from backend.db import Base  # ✅ This works from project root


class Echo(Base):
    """Legacy echo storage for schema payloads."""
    __tablename__ = "echoes"
    __table_args__ = {'extend_existing': True}

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime, default=datetime.utcnow)
    schema_type = Column(String)
    payload = Column(JSON)

    def __repr__(self):
        return f"<Echo(id={self.id[:8]}..., schema_type={self.schema_type})>"

class RollLog(Base):
    """Log of dice rolls for audit/replay."""
    __tablename__ = "roll_logs"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    actor = Column(String)
    target = Column(String)
    roll_type = Column(String)  # e.g., "combat", "skill"
    roll_mode = Column(String)  # e.g., "manual", "auto", "prompt"
    triggered_by = Column(String)
    result = Column(JSON)       # Full roll result dict
    modifiers = Column(JSON)    # Any edge, bap, tether, echo bonuses
    session_id = Column(String, nullable=True)
    encounter_id = Column(String, nullable=True)

    def __repr__(self):
        return f"<RollLog(id={self.id}, actor={self.actor}, roll_type={self.roll_type})>"


class Character(Base):
    """TBA v1.5 Character model (persistent storage)."""
    __tablename__ = "characters"
    __table_args__ = {'extend_existing': True}
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, index=True)
    owner_id = Column(String, nullable=False, index=True)  # User who created this character
    
    # Core stats (1-3 each, must sum to 6)
    level = Column(Integer, nullable=False, default=1)  # 1-10
    pp = Column(Integer, nullable=False)  # Physical Power
    ip = Column(Integer, nullable=False)  # Intellect Power
    sp = Column(Integer, nullable=False)  # Social Power
    
    # Derived stats (auto-calculated from level)
    dp = Column(Integer, nullable=False)  # Current Damage Points
    max_dp = Column(Integer, nullable=False)  # Max DP for this level
    edge = Column(Integer, nullable=False, default=0)  # 0-5
    bap = Column(Integer, nullable=False, default=1)  # 1-5
    
    # Combat configuration
    attack_style = Column(String, nullable=False)  # e.g., "3d4", "2d6"
    defense_die = Column(String, nullable=False)  # e.g., "1d8"
    
    # Equipment (Phase 2 - store as JSON for now)
    weapon = Column(JSON, nullable=True)  # {"name": str, "bonus_attack": int, "bonus_damage": int}
    armor = Column(JSON, nullable=True)  # {"name": str, "bonus_defense": int, "bonus_dp": int}
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Phase 2d: Additional character columns
    notes = Column(String, nullable=True)  # Character backstory, personality notes
    max_uses_per_encounter = Column(Integer, nullable=False, default=3)  # Limited ability uses
    current_uses = Column(Integer, nullable=False, default=3)  # Remaining uses this encounter
    weapon_bonus = Column(Integer, nullable=False, default=0)  # Weapon attack bonus
    armor_bonus = Column(Integer, nullable=False, default=0)  # Armor defense bonus
    times_called = Column(Integer, nullable=False, default=0)  # Times summoned/called
    is_called = Column(Boolean, nullable=False, default=False)  # Currently summoned
    status = Column(String, nullable=False, default='active')  # 'active', 'unconscious', 'dead'

    # Relationships
    party_memberships = relationship("PartyMembership", back_populates="character")
    abilities = relationship("Ability", back_populates="character", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Character(id={self.id[:8]}..., name={self.name}, level={self.level}, status={self.status})>"


class Party(Base):
    """
    Party/Session grouping for multiplayer.

    Represents a chat tab/channel within a campaign. Types:
    - 'story': Main in-character gameplay
    - 'ooc': Out-of-character discussion
    - 'standard': Custom party/group
    - 'whisper': Private conversation
    """
    __tablename__ = "parties"
    __table_args__ = {'extend_existing': True}

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)  # Optional party description
    session_id = Column(String, nullable=True)  # Active session ID (for WebSocket routing)

    # Story Weaver tracking
    story_weaver_id = Column(String, ForeignKey("characters.id"), nullable=False, index=True)
    created_by_id = Column(String, ForeignKey("characters.id"), nullable=False, index=True)

    # Phase 2d: Tab system columns
    campaign_id = Column(String, nullable=True, index=True)  # Campaign this party belongs to
    party_type = Column(String, nullable=False, default='standard')  # 'story', 'ooc', 'standard', 'whisper'
    is_active = Column(Boolean, nullable=False, default=True)  # Whether tab is displayed
    archived_at = Column(DateTime, nullable=True)  # Soft delete timestamp

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    memberships = relationship("PartyMembership", back_populates="party", cascade="all, delete-orphan")
    npcs = relationship("NPC", back_populates="party", cascade="all, delete-orphan")
    combat_turns = relationship("CombatTurn", back_populates="party", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="party")

    # Relationships to Character for SW and creator
    story_weaver = relationship("Character", foreign_keys=[story_weaver_id])
    creator = relationship("Character", foreign_keys=[created_by_id])

    def __repr__(self):
        return f"<Party(id={self.id[:8]}..., name={self.name}, type={self.party_type}, campaign={self.campaign_id[:8] if self.campaign_id else None}...)>"


class PartyMembership(Base):
    """
    Join table: which characters belong to which parties.

    Tracks membership history with joined_at and left_at timestamps.
    """
    __tablename__ = "party_memberships"
    __table_args__ = {'extend_existing': True}

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    party_id = Column(String, ForeignKey("parties.id"), nullable=False, index=True)
    character_id = Column(String, ForeignKey("characters.id"), nullable=False, index=True)
    joined_at = Column(DateTime, default=datetime.utcnow)
    left_at = Column(DateTime, nullable=True)  # NULL = still active member

    # Relationships
    party = relationship("Party", back_populates="memberships")
    character = relationship("Character", back_populates="party_memberships")

    def __repr__(self):
        status = "active" if self.left_at is None else "left"
        return f"<PartyMembership(party={self.party_id[:8]}..., character={self.character_id[:8]}..., {status})>"


class NPC(Base):
    """
    Non-Player Characters created by Story Weavers for encounters.

    NPCs have similar stats to Characters but are party-scoped and
    controlled by the Story Weaver.
    """
    __tablename__ = "npcs"
    __table_args__ = {'extend_existing': True}

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    party_id = Column(String, ForeignKey("parties.id"), nullable=False, index=True)
    name = Column(String, nullable=False, index=True)  # Unique per party enforced at application level

    # Character stats (same as Character model)
    level = Column(Integer, nullable=False, default=1)
    pp = Column(Integer, nullable=False, default=2)  # Physical Power (1-3)
    ip = Column(Integer, nullable=False, default=2)  # Intellect Power (1-3)
    sp = Column(Integer, nullable=False, default=2)  # Social Power (1-3)
    dp = Column(Integer, nullable=False, default=10)  # Current Damage Points
    max_dp = Column(Integer, nullable=False, default=10)  # Maximum DP
    edge = Column(Integer, nullable=False, default=0)  # Edge bonus (0-5)
    bap = Column(Integer, nullable=False, default=1)  # Bonus Action Points (1-5)

    # Combat configuration
    attack_style = Column(String, nullable=False, default="1d4")  # e.g., "3d4", "2d6"
    defense_die = Column(String, nullable=False, default="1d4")  # e.g., "1d6", "1d8"

    # Phase 2b: NPC metadata
    visible_to_players = Column(Boolean, nullable=False, default=True)  # Hidden NPCs for surprise encounters
    created_by = Column(String, ForeignKey("characters.id"), nullable=False, index=True)  # Story Weaver who created this NPC
    npc_type = Column(String, nullable=False, default="neutral")  # "enemy", "ally", "neutral"

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    party = relationship("Party", back_populates="npcs")
    creator = relationship("Character", foreign_keys=[created_by])

    def __repr__(self):
        return f"<NPC(id={self.id[:8]}..., name={self.name}, type={self.npc_type}, dp={self.dp}/{self.max_dp})>"


class CombatTurn(Base):
    """
    Combat turn history and action tracking for parties.

    Logs each combat action for replay, BAP tracking, and audit purposes.
    """
    __tablename__ = "combat_turns"
    __table_args__ = {'extend_existing': True}

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    party_id = Column(String, ForeignKey("parties.id"), nullable=False, index=True)

    # Combatant identification (can be Character or NPC)
    combatant_id = Column(String, nullable=False, index=True)  # Character.id or NPC.id
    combatant_name = Column(String, nullable=False)  # Display name for chat/logs

    # Turn metadata
    turn_number = Column(Integer, nullable=False, index=True)  # Sequential counter per party
    action_type = Column(String, nullable=False)  # "attack", "defend", "cast", "roll"
    result_data = Column(JSON, nullable=False)  # Full combat result (rolls, damage, narrative)
    bap_applied = Column(Boolean, nullable=False, default=False)  # Whether BAP was triggered
    message_id = Column(String, nullable=False, index=True)  # Format: "{name}_turn_{turn_number}"

    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    party = relationship("Party", back_populates="combat_turns")

    def __repr__(self):
        return f"<CombatTurn(id={self.id[:8]}..., turn={self.turn_number}, combatant={self.combatant_name}, action={self.action_type})>"


class Ability(Base):
    """
    Custom spells, techniques, and abilities for characters.

    Each character can have up to 5 abilities in numbered slots.
    Abilities are triggered via chat macros and use the character's
    power source (PP/IP/SP) for rolls.
    """
    __tablename__ = "abilities"
    __table_args__ = {'extend_existing': True}

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    character_id = Column(String, ForeignKey("characters.id"), nullable=False, index=True)
    slot_number = Column(Integer, nullable=False)  # 1-5, determines hotkey/UI position
    ability_type = Column(String, nullable=False)  # 'spell', 'technique', 'special'
    display_name = Column(String, nullable=False)  # Human-readable name
    macro_command = Column(String, nullable=False)  # Chat command (e.g., /fireball)
    power_source = Column(String, nullable=False)  # 'PP', 'IP', or 'SP'
    effect_type = Column(String, nullable=False)  # 'damage', 'heal', 'buff', 'debuff', 'utility'
    die = Column(String, nullable=False)  # Dice expression (e.g., 2d6, 3d4)
    is_aoe = Column(Boolean, nullable=False, default=False)  # Area of effect

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    character = relationship("Character", back_populates="abilities")

    def __repr__(self):
        return f"<Ability(id={self.id[:8]}..., name={self.display_name}, slot={self.slot_number}, type={self.ability_type})>"


class Message(Base):
    """
    Chat messages within a campaign/party.

    Messages are routed to specific parties (tabs) within a campaign.
    Types: chat, combat, system, narration
    Modes: IC (in-character), OOC (out-of-character)
    """
    __tablename__ = "messages"
    __table_args__ = {'extend_existing': True}

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id = Column(String, nullable=False, index=True)  # Campaign this message belongs to
    party_id = Column(String, ForeignKey("parties.id"), nullable=True, index=True)  # Tab/channel (nullable for legacy)

    # Sender info
    sender_id = Column(String, nullable=False, index=True)  # Character ID or system
    sender_name = Column(String, nullable=False)  # Display name

    # Message content
    message_type = Column(String, nullable=False, default='chat')  # 'chat', 'combat', 'system', 'narration'
    mode = Column(String, nullable=True)  # 'IC' (in-character) or 'OOC' (out-of-character)
    content = Column(Text, nullable=False)  # Message body
    attachment_url = Column(String, nullable=True)  # Optional image/file URL

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    party = relationship("Party", back_populates="messages")

    def __repr__(self):
        preview = self.content[:20] + "..." if len(self.content) > 20 else self.content
        return f"<Message(id={self.id[:8]}..., sender={self.sender_name}, type={self.message_type}, preview='{preview}')>"
