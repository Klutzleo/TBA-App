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
from sqlalchemy import Column, String, DateTime, JSON, Integer, ForeignKey, Boolean, Text, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
import random
import string
from datetime import datetime, timedelta
from argon2 import PasswordHasher
from backend.db import Base  # ✅ This works from project root

# Password hashing using Argon2
pwd_hasher = PasswordHasher()


# ==================== UTILITY FUNCTIONS ====================

def generate_join_code(length: int = 6) -> str:
    """
    Generate a random join code for campaigns.

    Args:
        length: Length of join code (default 6)

    Returns:
        Random uppercase alphanumeric string (e.g., "A3K9M2")
    """
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=length))


class User(Base):
    """
    User account for authentication.

    Users can own characters and campaigns, and be designated as Story Weavers.
    """
    __tablename__ = "users"
    __table_args__ = {'extend_existing': True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    characters = relationship("Character", back_populates="user", foreign_keys="[Character.user_id]")
    password_reset_tokens = relationship("PasswordResetToken", back_populates="user")
    created_campaigns = relationship("Campaign", back_populates="creator", foreign_keys="[Campaign.created_by_user_id]")
    story_weaver_campaigns = relationship("Campaign", back_populates="story_weaver", foreign_keys="[Campaign.story_weaver_id]")
    campaign_memberships = relationship("CampaignMembership", back_populates="user")

    def __repr__(self):
        return f"<User(id={str(self.id)[:8]}..., email={self.email}, username={self.username})>"

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using Argon2."""
        return pwd_hasher.hash(password)

    def verify_password(self, password: str) -> bool:
        """Verify a password against the hash."""
        try:
            pwd_hasher.verify(self.hashed_password, password)
            return True
        except:
            return False

    def set_password(self, password: str):
        """Set the user's password (hashes it automatically)."""
        self.hashed_password = self.hash_password(password)


class PasswordResetToken(Base):
    """
    Password reset token for secure password recovery.

    Tokens are single-use and expire after a set time period.
    """
    __tablename__ = "password_reset_tokens"
    __table_args__ = {'extend_existing': True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    token = Column(String, unique=True, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="password_reset_tokens")

    def __repr__(self):
        return f"<PasswordResetToken(id={str(self.id)[:8]}..., user_id={str(self.user_id)[:8]}..., used={self.used})>"

    @staticmethod
    def generate_token() -> str:
        """Generate a secure random token for password reset."""
        return str(uuid.uuid4())

    @staticmethod
    def create_for_user(user_id: str, hours_valid: int = 24) -> 'PasswordResetToken':
        """
        Create a new password reset token for a user.

        Args:
            user_id: The user's ID
            hours_valid: How many hours the token should be valid (default 24)

        Returns:
            A new PasswordResetToken instance (not yet committed to database)
        """
        token = PasswordResetToken.generate_token()
        expires_at = datetime.utcnow() + timedelta(hours=hours_valid)

        return PasswordResetToken(
            token=token,
            user_id=user_id,
            expires_at=expires_at,
            used=False
        )

    def is_valid(self) -> bool:
        """Check if the token is still valid (not used and not expired)."""
        if self.used:
            return False
        if datetime.utcnow() > self.expires_at:
            return False
        return True

    def mark_used(self):
        """Mark the token as used."""
        self.used = True


class Echo(Base):
    """Legacy echo storage for schema payloads."""
    __tablename__ = "echoes"
    __table_args__ = {'extend_existing': True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime, default=datetime.utcnow)
    schema_type = Column(String)
    payload = Column(JSON)

    def __repr__(self):
        return f"<Echo(id={str(self.id)[:8]}..., schema_type={self.schema_type})>"

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

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, index=True)
    owner_id = Column(String, nullable=False, index=True)  # Legacy field - kept for backward compatibility
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)  # User who owns this character (NULL for NPCs)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True, index=True)  # Campaign this character belongs to
    is_npc = Column(Boolean, nullable=False, default=False, index=True)  # TRUE for NPCs, FALSE for PCs/Allies
    is_ally = Column(Boolean, nullable=False, default=False, index=True)  # TRUE for Allies, FALSE for PCs/NPCs
    parent_character_id = Column(UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), nullable=True, index=True)  # Parent PC for Allies (NULL for PCs/NPCs)

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
    in_calling = Column(Boolean, nullable=False, default=False)  # Currently in The Calling state (at -10 DP)

    # Relationships
    user = relationship("User", back_populates="characters", foreign_keys=[user_id])
    campaign = relationship("Campaign", back_populates="characters", foreign_keys=[campaign_id])
    party_memberships = relationship("PartyMembership", back_populates="character")
    abilities = relationship("Ability", back_populates="character", cascade="all, delete-orphan")

    # Self-referential relationship for Allies
    parent_character = relationship("Character", remote_side=[id], foreign_keys=[parent_character_id], backref="allies")

    def __repr__(self):
        return f"<Character(id={str(self.id)[:8]}..., name={self.name}, level={self.level}, status={self.status})>"


class Campaign(Base):
    """
    Campaign - The main game container.

    A campaign holds all players, channels (story, ooc, whispers, etc.),
    and game data for a single story/adventure.

    Each campaign automatically gets:
    - 1 Story channel (shared by all players)
    - 1 OOC channel (out-of-character chat)
    - N Whisper channels (created on-demand for private conversations)
    - N Split Group channels (when the party splits in-game)

    Phase 3 Part 2 Updates:
    - Auto-generated 6-character join codes for easy sharing
    - Public/Private visibility options
    - User-based ownership (migrated from character-based)
    - Campaign settings (timezone, posting frequency, player limits)
    """
    __tablename__ = "campaigns"
    __table_args__ = {'extend_existing': True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)

    # User ownership (migrated from character-based)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    story_weaver_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Join settings
    join_code = Column(String(6), unique=True, nullable=False, index=True, default=generate_join_code)
    is_public = Column(Boolean, nullable=False, default=True)

    # Player limits
    min_players = Column(Integer, nullable=False, default=2)
    max_players = Column(Integer, nullable=False, default=6)

    # Campaign settings
    timezone = Column(String, nullable=False, default="America/New_York")
    posting_frequency = Column(Enum('slow', 'medium', 'high', name='posting_frequency_enum'), nullable=False, default='medium')
    status = Column(Enum('active', 'archived', 'on_break', name='campaign_status_enum'), nullable=False, default='active')

    # Legacy fields (kept for backward compatibility)
    created_by_id = Column(String, nullable=True, index=True)  # Old character-based creator ID
    is_active = Column(Boolean, nullable=False, default=True)
    archived_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    channels = relationship("Party", back_populates="campaign", foreign_keys="Party.campaign_id")
    creator = relationship("User", back_populates="created_campaigns", foreign_keys=[created_by_user_id])
    story_weaver = relationship("User", back_populates="story_weaver_campaigns", foreign_keys=[story_weaver_id])
    memberships = relationship("CampaignMembership", back_populates="campaign", cascade="all, delete-orphan")
    characters = relationship("Character", back_populates="campaign", foreign_keys="Character.campaign_id")

    def __repr__(self):
        return f"<Campaign(id={str(self.id)[:8]}..., name={self.name}, code={self.join_code}, public={self.is_public})>"


class CampaignMembership(Base):
    """
    Join table: which users belong to which campaigns.

    Tracks membership history with joined_at and left_at timestamps.
    Users join campaigns via join codes or direct invites.
    """
    __tablename__ = "campaign_memberships"
    __table_args__ = {'extend_existing': True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(Enum('player', 'story_weaver', name='campaign_role_enum'), nullable=False, default='player')
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    left_at = Column(DateTime, nullable=True)  # NULL = still active member

    # Relationships
    campaign = relationship("Campaign", back_populates="memberships")
    user = relationship("User", back_populates="campaign_memberships")

    def __repr__(self):
        status = "active" if self.left_at is None else "left"
        return f"<CampaignMembership(campaign={str(self.campaign_id)[:8]}..., user={str(self.user_id)[:8]}..., role={self.role}, {status})>"


class Party(Base):
    """
    Communication Channel within a Campaign.

    Despite the name "Party", this represents communication channels/tabs within a campaign:
    - 'story': Main in-character gameplay channel (shared by all players)
    - 'ooc': Out-of-character discussion channel
    - 'whisper': Private 1-to-1 or small group DM channels
    - 'split_group': Temporary channels when the party splits in-game
    - 'spectator': Read-only channels for observers (future)

    Note: The Story channel remains accessible even when players split into groups,
    allowing the Story Weaver to narrate cross-group events.
    """
    __tablename__ = "parties"
    __table_args__ = {'extend_existing': True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    session_id = Column(String, nullable=True)  # Active session ID (for WebSocket routing)

    # Campaign relationship
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=True, index=True)

    # Channel type
    party_type = Column(String, nullable=False, default='story')  # 'story', 'ooc', 'whisper', 'split_group', 'spectator'

    # Legacy Story Weaver tracking (deprecated - use campaign.story_weaver_id instead)
    story_weaver_id = Column(String, ForeignKey("characters.id"), nullable=True, index=True)
    created_by_id = Column(String, nullable=False, index=True)

    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    archived_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    campaign = relationship("Campaign", back_populates="channels", foreign_keys=[campaign_id])
    memberships = relationship("PartyMembership", back_populates="party", cascade="all, delete-orphan")
    npcs = relationship("NPC", back_populates="party", cascade="all, delete-orphan")
    combat_turns = relationship("CombatTurn", back_populates="party", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="party")

    # Legacy relationships to Character
    story_weaver = relationship("Character", foreign_keys=[story_weaver_id])
    # TEMPORARY: Disabled until user auth migration (FK was dropped for bootstrap)
    # TODO: Re-enable when created_by_id points to users table
    # creator = relationship("Character", foreign_keys=[created_by_id])

    def __repr__(self):
        return f"<Party(id={str(self.id)[:8]}..., name={self.name}, type={self.party_type}, campaign={str(self.campaign_id)[:8] if self.campaign_id else None}...)>"


class PartyMembership(Base):
    """
    Join table: which characters belong to which parties.

    Tracks membership history with joined_at and left_at timestamps.
    """
    __tablename__ = "party_memberships"
    __table_args__ = {'extend_existing': True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    party_id = Column(UUID(as_uuid=True), ForeignKey("parties.id"), nullable=False, index=True)
    character_id = Column(UUID(as_uuid=True), ForeignKey("characters.id"), nullable=False, index=True)
    joined_at = Column(DateTime, default=datetime.utcnow)
    left_at = Column(DateTime, nullable=True)  # NULL = still active member

    # Relationships
    party = relationship("Party", back_populates="memberships")
    character = relationship("Character", back_populates="party_memberships")

    def __repr__(self):
        status = "active" if self.left_at is None else "left"
        return f"<PartyMembership(party={str(self.party_id)[:8]}..., character={str(self.character_id)[:8]}..., {status})>"


class NPC(Base):
    """
    Non-Player Characters created by Story Weavers for encounters.

    NPCs have similar stats to Characters but are party-scoped and
    controlled by the Story Weaver.
    """
    __tablename__ = "npcs"
    __table_args__ = {'extend_existing': True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    party_id = Column(UUID(as_uuid=True), ForeignKey("parties.id"), nullable=False, index=True)
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
        return f"<NPC(id={str(self.id)[:8]}..., name={self.name}, type={self.npc_type}, dp={self.dp}/{self.max_dp})>"


class CombatTurn(Base):
    """
    Combat turn history and action tracking for parties.

    Logs each combat action for replay, BAP tracking, and audit purposes.
    """
    __tablename__ = "combat_turns"
    __table_args__ = {'extend_existing': True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    party_id = Column(UUID(as_uuid=True), ForeignKey("parties.id"), nullable=False, index=True)

    # Combatant identification (can be Character or NPC)
    combatant_id = Column(UUID(as_uuid=True), nullable=False, index=True)  # Character.id or NPC.id
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
        return f"<CombatTurn(id={str(self.id)[:8]}..., turn={self.turn_number}, combatant={self.combatant_name}, action={self.action_type})>"


class Encounter(Base):
    """
    Combat encounter tracking with initiative system.

    Each encounter represents a distinct combat/challenge that has its own
    initiative order and ability use tracking.
    """
    __tablename__ = "encounters"
    __table_args__ = {'extend_existing': True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False, index=True)

    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    initiative_rolls = relationship("InitiativeRoll", back_populates="encounter", cascade="all, delete-orphan")

    def __repr__(self):
        status = "active" if self.is_active else "ended"
        return f"<Encounter(id={str(self.id)[:8]}..., campaign={str(self.campaign_id)[:8]}..., status={status})>"


class InitiativeRoll(Base):
    """
    Individual initiative roll within an encounter.

    Tracks each participant's initiative order, supporting both PCs and NPCs.
    Can be silent (hidden from players) for surprise encounters.
    """
    __tablename__ = "initiative_rolls"
    __table_args__ = {'extend_existing': True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    encounter_id = Column(UUID(as_uuid=True), ForeignKey("encounters.id"), nullable=False, index=True)
    character_id = Column(UUID(as_uuid=True), ForeignKey("characters.id"), nullable=True, index=True)
    npc_id = Column(UUID(as_uuid=True), ForeignKey("npcs.id"), nullable=True, index=True)

    name = Column(String, nullable=False)  # Cached display name
    roll_result = Column(Integer, nullable=False, index=True)
    is_silent = Column(Boolean, nullable=False, default=False)  # Hidden from players
    rolled_by_sw = Column(Boolean, nullable=False, default=False)  # Forced roll vs self-roll

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    encounter = relationship("Encounter", back_populates="initiative_rolls")
    character = relationship("Character")
    npc = relationship("NPC")

    def __repr__(self):
        entity = f"char={str(self.character_id)[:8]}" if self.character_id else f"npc={str(self.npc_id)[:8]}"
        silent = " [SILENT]" if self.is_silent else ""
        return f"<InitiativeRoll(id={str(self.id)[:8]}..., {entity}, roll={self.roll_result}{silent})>"


class Ability(Base):
    """
    Custom spells, techniques, and abilities for characters.

    Each character can have up to 5 abilities in numbered slots.
    Abilities are triggered via chat macros and use the character's
    power source (PP/IP/SP) for rolls.
    """
    __tablename__ = "abilities"
    __table_args__ = {'extend_existing': True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    character_id = Column(UUID(as_uuid=True), ForeignKey("characters.id"), nullable=False, index=True)
    slot_number = Column(Integer, nullable=False)  # 1-5, determines hotkey/UI position
    ability_type = Column(String, nullable=False)  # 'spell', 'technique', 'special'
    display_name = Column(String, nullable=False)  # Human-readable name
    macro_command = Column(String, nullable=False)  # Chat command (e.g., /fireball)
    power_source = Column(String, nullable=False)  # 'PP', 'IP', or 'SP'
    effect_type = Column(String, nullable=False)  # 'damage', 'heal', 'buff', 'debuff', 'utility'
    die = Column(String, nullable=False)  # Dice expression (e.g., 2d6, 3d4)
    is_aoe = Column(Boolean, nullable=False, default=False)  # Area of effect

    # Usage tracking (3 uses per encounter per character level)
    max_uses = Column(Integer, nullable=False, default=3)  # Total charges per encounter
    uses_remaining = Column(Integer, nullable=False, default=3)  # Current charges

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    character = relationship("Character", back_populates="abilities")

    def __repr__(self):
        return f"<Ability(id={str(self.id)[:8]}..., name={self.display_name}, slot={self.slot_number}, type={self.ability_type})>"


class Message(Base):
    """
    Chat messages within a campaign/party.

    Messages are routed to specific parties (tabs) within a campaign.
    Types: chat, combat, system, narration
    Modes: IC (in-character), OOC (out-of-character)
    """
    __tablename__ = "messages"
    __table_args__ = {'extend_existing': True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), nullable=False, index=True)  # Campaign this message belongs to
    party_id = Column(UUID(as_uuid=True), ForeignKey("parties.id"), nullable=True, index=True)  # Tab/channel (nullable for legacy)

    # Sender info
    sender_id = Column(UUID(as_uuid=True), nullable=False, index=True)  # Character ID or system
    sender_name = Column(String, nullable=False)  # Display name

    # Message content
    message_type = Column(String, nullable=False, default='chat')  # 'chat', 'combat', 'system', 'narration'
    mode = Column(String, nullable=True)  # 'IC' (in-character) or 'OOC' (out-of-character)
    content = Column(Text, nullable=False)  # Message body
    attachment_url = Column(String, nullable=True)  # Optional image/file URL
    extra_data = Column(JSONB, nullable=True)  # Structured data (e.g., dice roll breakdown: {"breakdown": [3, 5, 2]})

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    party = relationship("Party", back_populates="messages")

    def __repr__(self):
        preview = self.content[:20] + "..." if len(self.content) > 20 else self.content
        return f"<Message(id={str(self.id)[:8]}..., sender={self.sender_name}, type={self.message_type}, preview='{preview}')>"
