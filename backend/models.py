# models.py
from sqlalchemy import Column, String, DateTime, JSON, Integer, ForeignKey, Boolean
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from backend.db import Base  # ✅ This works from project root

class Echo(Base):
    __tablename__ = "echoes"
    __table_args__ = {'extend_existing': True}
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime, default=datetime.utcnow)
    schema_type = Column(String)
    payload = Column(JSON)

class RollLog(Base):
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
    
    # Relationships
    party_memberships = relationship("PartyMembership", back_populates="character")


class Party(Base):
    """Party/Session grouping for multiplayer."""
    __tablename__ = "parties"
    __table_args__ = {'extend_existing': True}

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    gm_id = Column(String, nullable=False, index=True)  # GM/Storyweaver who owns this party
    session_id = Column(String, nullable=True)  # Active session ID (for WebSocket routing)

    # Phase 2b: Story Weaver tracking
    story_weaver_id = Column(String, ForeignKey("characters.id"), nullable=True, index=True)  # Character ID of current SW
    created_by_id = Column(String, ForeignKey("characters.id"), nullable=True, index=True)  # Character ID who created the party

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    memberships = relationship("PartyMembership", back_populates="party")
    npcs = relationship("NPC", back_populates="party", cascade="all, delete-orphan")
    combat_turns = relationship("CombatTurn", back_populates="party", cascade="all, delete-orphan")


class PartyMembership(Base):
    """Join table: which characters belong to which parties."""
    __tablename__ = "party_memberships"
    __table_args__ = {'extend_existing': True}

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    party_id = Column(String, ForeignKey("parties.id"), nullable=False, index=True)
    character_id = Column(String, ForeignKey("characters.id"), nullable=False, index=True)
    joined_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    party = relationship("Party", back_populates="memberships")
    character = relationship("Character", back_populates="party_memberships")


class NPC(Base):
    """Non-Player Characters created by Story Weavers for encounters."""
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


class CombatTurn(Base):
    """Combat turn history and action tracking for parties."""
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
