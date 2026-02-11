from urllib import response
from fastapi import APIRouter, Request, Form, Body, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from backend.magic_logic import resolve_spellcast
from backend.db import SessionLocal
from backend.models import Character, Party, NPC, PartyMembership, CombatTurn, Ability, Campaign, Message
from routes.schemas.chat import ChatMessageSchema
from routes.schemas.resolve import ResolveRollSchema
from typing import Dict, Any, Optional, List
from time import monotonic
from datetime import datetime
import json
import logging
import random
import httpx  # For making async HTTP requests
import os
import re

COMBAT_LOG_URL = os.getenv("COMBAT_LOG_URL", "https://tba-app-production.up.railway.app/api/combat/log")
WS_LOG_VERBOSITY = os.getenv("WS_LOG_VERBOSITY", "macros")  # macros|minimal|off
try:
    WS_MACRO_THROTTLE_MS = int(os.getenv("WS_MACRO_THROTTLE_MS", "700"))
except ValueError:
    WS_MACRO_THROTTLE_MS = 700

chat_blp = APIRouter()
templates = Jinja2Templates(directory="templates")
logger = logging.getLogger("uvicorn")

# Macro throttle tracking (preserved for backward compatibility)
macro_last_ts: Dict[str, float] = {}


class ConnectionManager:
    """
    Manages WebSocket connections with character caching for macro support.

    Features:
    - Tracks active WebSocket connections per party
    - Caches character stats on connection to avoid DB hits
    - Tracks Story Weaver role per connection
    - Broadcasts messages to all party members
    """

    def __init__(self):
        # Structure: {party_id: [(ws, character_id, metadata)]}
        self.active_connections: Dict[str, List[tuple[WebSocket, str, Dict[str, Any]]]] = {}

        # Character cache: {party_id: {character_id: stats_dict}}
        self.character_cache: Dict[str, Dict[str, Dict[str, Any]]] = {}

        # Party metadata cache: {party_id: {"story_weaver_id": str}}
        self.party_cache: Dict[str, Dict[str, Any]] = {}

        # Active encounters: {party_id: encounter_data}
        self.active_encounters: Dict[str, Dict[str, Any]] = {}

    async def add_connection(
        self,
        party_id: str,
        ws: WebSocket,
        character_id: Optional[str] = None
    ):
        """
        Add a WebSocket connection and cache character data.

        Args:
            party_id: The party ID
            ws: The WebSocket connection
            character_id: Optional character ID to associate with this connection
        """
        # Initialize party structures
        if party_id not in self.active_connections:
            self.active_connections[party_id] = []
        if party_id not in self.character_cache:
            self.character_cache[party_id] = {}

        # Fetch and cache character data if provided
        metadata = {"role": "player", "character_id": character_id}

        if character_id:
            db = SessionLocal()
            try:
                # Try to load campaign metadata (for SW check)
                if party_id not in self.party_cache:
                    party = db.query(Party).filter(Party.id == party_id).first()
                    if party and party.campaign_id:
                        # Get the Story Weaver from the Campaign, not the Party
                        campaign = db.query(Campaign).filter(Campaign.id == party.campaign_id).first()
                        if campaign:
                            self.party_cache[party_id] = {
                                "story_weaver_id": campaign.story_weaver_id,
                                "created_by_id": campaign.created_by_id,
                                "campaign_id": campaign.id
                            }
                    elif party:
                        # Legacy: Party without campaign (fallback to party's SW)
                        self.party_cache[party_id] = {
                            "story_weaver_id": party.story_weaver_id,
                            "created_by_id": party.created_by_id,
                            "campaign_id": None
                        }

                # Check if this character is the Story Weaver
                party_meta = self.party_cache.get(party_id, {})
                is_sw = (character_id == party_meta.get("story_weaver_id"))
                metadata["role"] = "SW" if is_sw else "player"

                # Try Character first
                character = db.query(Character).filter(Character.id == character_id).first()

                if character:
                    self.character_cache[party_id][character_id] = {
                        "id": character.id,
                        "name": character.name,
                        "type": "character",
                        "pp": character.pp,
                        "ip": character.ip,
                        "sp": character.sp,
                        "edge": character.edge,
                        "bap": character.bap,
                        "level": character.level,
                        "dp": character.dp,
                        "max_dp": character.max_dp,
                        "attack_style": character.attack_style,
                        "defense_die": character.defense_die
                    }
                    metadata["character_name"] = character.name
                else:
                    # Try NPC
                    npc = db.query(NPC).filter(NPC.id == character_id).first()
                    if npc:
                        self.character_cache[party_id][character_id] = {
                            "id": npc.id,
                            "name": npc.name,
                            "type": "npc",
                            "pp": npc.pp,
                            "ip": npc.ip,
                            "sp": npc.sp,
                            "edge": npc.edge,
                            "bap": npc.bap,
                            "level": npc.level,
                            "dp": npc.dp,
                            "max_dp": npc.max_dp,
                            "attack_style": npc.attack_style,
                            "defense_die": npc.defense_die,
                            "npc_type": npc.npc_type,
                            "visible_to_players": npc.visible_to_players
                        }
                        metadata["character_name"] = npc.name
                    else:
                        logger.warning(f"Character/NPC not found: {character_id}")

            except Exception as e:
                logger.error(f"Failed to cache character {character_id}: {e}")
            finally:
                db.close()

        # Add connection with metadata
        self.active_connections[party_id].append((ws, character_id or "", metadata))
        logger.info(
            f"Connection added: party={party_id}, character={character_id}, "
            f"role={metadata['role']}, total_connections={len(self.active_connections[party_id])}"
        )

    def remove_connection(self, party_id: str, ws: WebSocket):
        """Remove a WebSocket connection and clean up if party is empty."""
        if party_id in self.active_connections:
            # Find and remove the connection
            self.active_connections[party_id] = [
                (w, cid, meta) for w, cid, meta in self.active_connections[party_id]
                if w != ws
            ]

            # Clean up empty party
            if not self.active_connections[party_id]:
                del self.active_connections[party_id]
                # Also clear character cache for this party
                if party_id in self.character_cache:
                    del self.character_cache[party_id]
                if party_id in self.party_cache:
                    del self.party_cache[party_id]
                logger.info(f"Party {party_id} cleaned up (no active connections)")

    async def broadcast(self, party_id: str, message: Dict[str, Any]):
        """Broadcast a message to all connections in a party."""
        for ws, _, _ in self.active_connections.get(party_id, []):
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning(f"Broadcast failed to connection: {e}")
                # Connection will be cleaned up on next disconnect

    async def broadcast_whisper(
        self,
        party_id: str,
        message: Dict[str, Any],
        target_names: List[str],
        sender_name: str
    ):
        """
        Broadcast a whisper message only to specific targets and the Story Weaver.

        Args:
            party_id: The party ID
            message: The message to send
            target_names: List of character names who should receive the whisper
            sender_name: Name of the sender (so they don't receive their own message back)
        """
        # Normalize target names for case-insensitive matching
        target_names_lower = [name.lower() for name in target_names]
        sender_name_lower = sender_name.lower() if sender_name else ""

        for ws, char_id, metadata in self.active_connections.get(party_id, []):
            try:
                char_name = metadata.get("character_name", "").lower()
                is_sw = metadata.get("role") == "SW"

                # Send to: targets, Story Weaver (always sees whispers), but not back to sender
                should_receive = (
                    (char_name in target_names_lower and char_name != sender_name_lower) or
                    (is_sw and char_name != sender_name_lower)
                )

                if should_receive:
                    await ws.send_json(message)
                    logger.debug(f"Whisper sent to {char_name} (SW={is_sw})")

            except Exception as e:
                logger.warning(f"Whisper broadcast failed to connection: {e}")

    async def send_to_character(
        self,
        party_id: str,
        character_id: str,
        message: Dict[str, Any]
    ):
        """
        Send a private message to a specific character only.

        Args:
            party_id: The party ID
            character_id: The character ID to send to
            message: The message to send
        """
        for ws, char_id, _ in self.active_connections.get(party_id, []):
            try:
                if char_id == character_id:
                    await ws.send_json(message)
                    logger.debug(f"Private message sent to character {character_id}")
                    return
            except Exception as e:
                logger.warning(f"Send to character failed: {e}")

    def get_character_stats(self, party_id: str, character_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached character stats.

        Returns:
            Dict with character stats or None if not found
        """
        return self.character_cache.get(party_id, {}).get(character_id)

    def get_party_sw(self, party_id: str) -> Optional[str]:
        """
        Get the Story Weaver character ID for a party.

        Returns:
            Character ID of the Story Weaver or None
        """
        return self.party_cache.get(party_id, {}).get("story_weaver_id")

    def get_connection_metadata(self, party_id: str, ws: WebSocket) -> Optional[Dict[str, Any]]:
        """Get metadata for a specific connection."""
        for w, _, meta in self.active_connections.get(party_id, []):
            if w == ws:
                return meta
        return None

    def is_story_weaver(self, party_id: str, character_id: str) -> bool:
        """Check if a character is the Story Weaver for a party."""
        sw_id = self.get_party_sw(party_id)
        return sw_id is not None and sw_id == character_id

    def get_character(self, party_id: str, character_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached character data for a specific character in a party.

        Returns:
            Dict with character stats including:
            - id, name, type (character/npc)
            - pp, ip, sp, edge, bap, level
            - dp, max_dp, attack_style, defense_die
            - is_story_weaver (bool)
        """
        char_data = self.get_character_stats(party_id, character_id)
        if char_data:
            # Add is_story_weaver flag
            char_data['is_story_weaver'] = self.is_story_weaver(party_id, character_id)
        return char_data

    # ========================================================================
    # ENCOUNTER STATE MANAGEMENT (Phase 2b Task 3)
    # ========================================================================

    def start_encounter(self, party_id: str, initiator_id: str) -> str:
        """
        Start combat encounter for party.

        Args:
            party_id: Party UUID
            initiator_id: Character ID who started encounter (usually SW)

        Returns:
            encounter_id: UUID for this encounter

        State:
            {
                'encounter_id': uuid,
                'turn_number': 0,
                'combatants': [
                    {
                        'id': character/npc uuid,
                        'name': str,
                        'type': 'character' or 'npc',
                        'initiative': None (not rolled yet)
                    }
                ],
                'turn_order': [],  # Sorted by initiative after rolls
                'current_turn_index': 0,
                'started_by': initiator_id
            }
        """
        import uuid
        encounter_id = str(uuid.uuid4())

        self.active_encounters[party_id] = {
            'encounter_id': encounter_id,
            'turn_number': 0,
            'combatants': [],
            'turn_order': [],
            'current_turn_index': 0,
            'started_by': initiator_id
        }

        return encounter_id

    def add_combatant(self, party_id: str, combatant_id: str, name: str, combatant_type: str):
        """
        Add character/NPC to active encounter.

        Args:
            party_id: Party UUID
            combatant_id: Character or NPC UUID
            name: Display name
            combatant_type: 'character' or 'npc'
        """
        if party_id not in self.active_encounters:
            return

        encounter = self.active_encounters[party_id]

        # Check if already added
        if any(c['id'] == combatant_id for c in encounter['combatants']):
            return

        encounter['combatants'].append({
            'id': combatant_id,
            'name': name,
            'type': combatant_type,
            'initiative': None
        })

    def roll_initiative(self, party_id: str, combatant_id: str, roll_result: int):
        """
        Record initiative roll for combatant.

        Args:
            party_id: Party UUID
            combatant_id: Character or NPC UUID
            roll_result: Initiative roll total
        """
        if party_id not in self.active_encounters:
            return

        encounter = self.active_encounters[party_id]

        # Find combatant and update initiative
        for combatant in encounter['combatants']:
            if combatant['id'] == combatant_id:
                combatant['initiative'] = roll_result
                break

    def sort_initiative(self, party_id: str):
        """
        Sort combatants by initiative rolls (highest first).

        Ties broken by: PP > IP > SP > random coin flip (from character cache)
        """
        if party_id not in self.active_encounters:
            return

        encounter = self.active_encounters[party_id]

        # Filter combatants with initiative rolled
        combatants_with_init = [c for c in encounter['combatants'] if c['initiative'] is not None]

        # Add stats and random tiebreaker to each combatant for sorting
        for combatant in combatants_with_init:
            char_stats = self.get_character_stats(party_id, combatant['id'])
            combatant['pp'] = char_stats.get('pp', 0) if char_stats else 0
            combatant['ip'] = char_stats.get('ip', 0) if char_stats else 0
            combatant['sp'] = char_stats.get('sp', 0) if char_stats else 0
            combatant['tiebreaker'] = random.random()  # Random for final tie-break

        # Sort by initiative (highest first), with tiebreaker using stats then random
        def sort_key(combatant):
            # Return tuple: (initiative desc, pp desc, ip desc, sp desc, random desc)
            return (
                -combatant['initiative'],
                -combatant['pp'],
                -combatant['ip'],
                -combatant['sp'],
                -combatant['tiebreaker']
            )

        sorted_combatants = sorted(combatants_with_init, key=sort_key)

        # Determine tie-breaker reason for display
        for i, combatant in enumerate(sorted_combatants):
            combatant['tiebreaker_reason'] = None
            if i > 0:
                prev = sorted_combatants[i - 1]
                if combatant['initiative'] == prev['initiative']:
                    # They tied on initiative - figure out what broke the tie
                    if combatant['pp'] != prev['pp']:
                        combatant['tiebreaker_reason'] = 'PP'
                    elif combatant['ip'] != prev['ip']:
                        combatant['tiebreaker_reason'] = 'IP'
                    elif combatant['sp'] != prev['sp']:
                        combatant['tiebreaker_reason'] = 'SP'
                    else:
                        combatant['tiebreaker_reason'] = 'coin flip'

        encounter['turn_order'] = sorted_combatants
        encounter['current_turn_index'] = 0

    def get_current_turn(self, party_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current combatant whose turn it is.

        Returns:
            Dict with combatant data or None if no active encounter
        """
        if party_id not in self.active_encounters:
            return None

        encounter = self.active_encounters[party_id]

        if not encounter['turn_order']:
            return None

        return encounter['turn_order'][encounter['current_turn_index']]

    def next_turn(self, party_id: str):
        """
        Advance to next combatant, increment turn_number if looped.
        """
        if party_id not in self.active_encounters:
            return

        encounter = self.active_encounters[party_id]

        if not encounter['turn_order']:
            return

        # Advance index
        encounter['current_turn_index'] += 1

        # Wrap around and increment turn number
        if encounter['current_turn_index'] >= len(encounter['turn_order']):
            encounter['current_turn_index'] = 0
            encounter['turn_number'] += 1

    def get_turn_number(self, party_id: str) -> int:
        """Get current turn number for encounter."""
        if party_id not in self.active_encounters:
            return 0
        return self.active_encounters[party_id]['turn_number']

    def end_encounter(self, party_id: str):
        """Clear encounter state."""
        if party_id in self.active_encounters:
            del self.active_encounters[party_id]

    def get_encounter(self, party_id: str) -> Optional[Dict[str, Any]]:
        """Get active encounter data for party."""
        return self.active_encounters.get(party_id)


# Global connection manager instance
connection_manager = ConnectionManager()


# ============================================================================
# MESSAGE PERSISTENCE (Save chat to database)
# ============================================================================

def save_message_to_db(
    party_id: str,
    character_id: Optional[str],
    character_name: str,
    message_text: str,
    message_type: str = 'chat',
    chat_mode: Optional[str] = None
) -> Optional[str]:
    """
    Save a chat message to the database for persistence.

    Args:
        party_id: Party UUID
        character_id: Character ID who sent the message (or None for system)
        character_name: Display name of the sender
        message_text: The message content
        message_type: Type of message (chat, combat, system, narration)
        chat_mode: Chat mode (ic, ooc, whisper)

    Returns:
        Message ID if saved successfully, None otherwise
    """
    db = SessionLocal()
    try:
        # Get party to find campaign_id
        party = db.query(Party).filter(Party.id == party_id).first()
        if not party or not party.campaign_id:
            logger.warning(f"Cannot save message: party {party_id} not found or has no campaign")
            return None

        # Create message record
        message = Message(
            campaign_id=party.campaign_id,
            party_id=party_id,
            sender_id=character_id or "system",
            sender_name=character_name,
            message_type=message_type,
            mode=chat_mode,
            content=message_text
        )

        db.add(message)
        db.commit()
        db.refresh(message)

        return message.id
    except Exception as e:
        logger.error(f"Failed to save message to database: {e}")
        db.rollback()
        return None
    finally:
        db.close()


# ============================================================================
# COMBAT TURN DATABASE LOGGING (Phase 2b Task 3)
# ============================================================================

async def log_combat_action(
    party_id: str,
    combatant_id: str,
    combatant_name: str,
    action_type: str,
    result_data: Dict[str, Any],
    bap_applied: bool = False
) -> Optional[str]:
    """
    Log combat action to database for retroactive BAP grants and combat history.

    Args:
        party_id: Party UUID
        combatant_id: Character or NPC UUID who performed the action
        combatant_name: Display name of combatant
        action_type: Type of action ('initiative', 'attack', 'defend', 'spell', 'roll')
        result_data: Full roll results, damage, etc. (stored as JSON)
        bap_applied: Whether BAP was already applied to this action

    Returns:
        message_id: Unique identifier for this combat turn (format: "{name}_turn_{num}")
                   or None if no active encounter

    Example:
        await log_combat_action(
            party_id="party-123",
            combatant_id="char-456",
            combatant_name="Alice",
            action_type="attack",
            result_data={'attack_roll': 15, 'damage': 8, 'target': 'Goblin'},
            bap_applied=False
        )
        # Returns: "alice_turn_1"
    """
    # Get current turn number from active encounter
    turn_number = connection_manager.get_turn_number(party_id)

    # Generate message_id: lowercase name with underscores, plus turn number
    sanitized_name = combatant_name.lower().replace(' ', '_')
    message_id = f"{sanitized_name}_turn_{turn_number}"

    # Create database record
    db = SessionLocal()
    try:
        turn = CombatTurn(
            party_id=party_id,
            combatant_id=combatant_id,
            combatant_name=combatant_name,
            turn_number=turn_number,
            action_type=action_type,
            result_data=result_data,
            bap_applied=bap_applied,
            message_id=message_id
        )
        db.add(turn)
        db.commit()
        db.refresh(turn)

        logger.info(f"Combat action logged: {message_id} ({action_type}) in party {party_id}")
        return message_id

    except Exception as e:
        logger.error(f"Failed to log combat action: {e}")
        db.rollback()
        return None
    finally:
        db.close()


def get_combat_history(party_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get recent combat turn history for a party.

    Args:
        party_id: Party UUID
        limit: Maximum number of turns to retrieve (default 50)

    Returns:
        List of combat turn records, ordered by timestamp (newest first)
    """
    db = SessionLocal()
    try:
        turns = db.query(CombatTurn).filter(
            CombatTurn.party_id == party_id
        ).order_by(
            CombatTurn.timestamp.desc()
        ).limit(limit).all()

        return [{
            'id': turn.id,
            'combatant_id': turn.combatant_id,
            'combatant_name': turn.combatant_name,
            'turn_number': turn.turn_number,
            'action_type': turn.action_type,
            'result_data': turn.result_data,
            'bap_applied': turn.bap_applied,
            'message_id': turn.message_id,
            'timestamp': turn.timestamp.isoformat()
        } for turn in turns]

    except Exception as e:
        logger.error(f"Failed to get combat history: {e}")
        return []
    finally:
        db.close()


def mark_turn_bap_applied(message_id: str) -> bool:
    """
    Mark a combat turn as having BAP applied (for retroactive BAP grants).

    Args:
        message_id: The unique message_id of the combat turn

    Returns:
        True if successful, False otherwise
    """
    db = SessionLocal()
    try:
        turn = db.query(CombatTurn).filter(
            CombatTurn.message_id == message_id
        ).first()

        if turn:
            turn.bap_applied = True
            db.commit()
            logger.info(f"BAP applied to turn: {message_id}")
            return True

        logger.warning(f"Combat turn not found: {message_id}")
        return False

    except Exception as e:
        logger.error(f"Failed to mark BAP applied: {e}")
        db.rollback()
        return False
    finally:
        db.close()


# Legacy functions (preserved for backward compatibility with existing code)
def add_connection(party_id: str, ws: WebSocket):
    """Legacy: Add connection without character_id (for backward compatibility)."""
    import asyncio
    asyncio.create_task(connection_manager.add_connection(party_id, ws, None))


def remove_connection(party_id: str, ws: WebSocket):
    """Legacy: Remove connection."""
    connection_manager.remove_connection(party_id, ws)


async def broadcast(party_id: str, message: Dict[str, Any]):
    """Legacy: Broadcast message."""
    await connection_manager.broadcast(party_id, message)


async def broadcast_combat_event(party_id: str, event: Dict[str, Any]):
    """Broadcast a combat event to all sockets in a party."""
    payload = {"type": "combat_event", "party_id": party_id, **event}
    await broadcast(party_id, payload)


async def log_if_allowed(event_type: str, entry: Dict[str, Any]):
    """Log macro events based on verbosity setting."""
    if WS_LOG_VERBOSITY == "off":
        return
    if WS_LOG_VERBOSITY == "minimal" and event_type not in {"dice_roll", "initiative"}:
        return
    await log_combat_event(entry)


def parse_dice_notation(expr: str) -> Dict[str, Any]:
    """Parse dice like '3d6+2' and roll it. Returns breakdown and total."""
    m = re.fullmatch(r"\s*(\d+)d(\d+)([+\-]\d+)?\s*", expr)
    if not m:
        raise ValueError("Invalid dice expression. Try like 3d6+2")
    num = int(m.group(1))
    sides = int(m.group(2))
    mod = int(m.group(3)) if m.group(3) else 0
    rolls = [random.randint(1, sides) for _ in range(num)]
    total = sum(rolls) + mod
    return {"rolls": rolls, "modifier": mod, "total": total}


def check_story_weaver(character_id: Optional[str], party_id: str) -> tuple[bool, Optional[str]]:
    """
    Check if character is the Story Weaver for this party.

    Args:
        character_id: The character ID to check
        party_id: The party ID

    Returns:
        Tuple of (is_sw: bool, error_message: Optional[str])
    """
    if not character_id:
        return False, "⚠️ Cannot verify Story Weaver status without character_id. Please reconnect."

    # Check cached party data first
    party_meta = connection_manager.party_cache.get(party_id, {})
    sw_id = party_meta.get("story_weaver_id")

    if sw_id:
        if character_id == sw_id:
            return True, None
        return False, "⚠️ Only the Story Weaver can use this command."

    # Fallback to database query
    db = SessionLocal()
    try:
        party = db.query(Party).filter(Party.id == party_id).first()
        if not party:
            return False, "Party not found."

        if character_id != party.story_weaver_id:
            return False, "⚠️ Only the Story Weaver can use this command."

        return True, None
    finally:
        db.close()


async def handle_ability_macro(
    party_id: str,
    actor: str,
    macro_command: str,
    target_args: str,
    character_id: Optional[str],
    context: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Handle custom ability/spell execution via macro command.

    When a player types /<macro_command> @target:
    1. Look up ability by macro_command for this character
    2. Validate ability exists, has uses, target exists, effect_type is 'damage'
    3. Execute attack: roll spell die + power_source_stat + edge vs defense
    4. Apply damage and broadcast results

    Returns:
        Dict with spell_cast event data, or None if not a custom ability
    """
    if not character_id:
        return None

    db = SessionLocal()
    try:
        # 1. Look up ability by macro_command for this character
        ability = db.query(Ability).filter(
            Ability.character_id == character_id,
            Ability.macro_command == macro_command
        ).first()

        if not ability:
            return None  # Not a custom ability, let other handlers try

        # 2. Validate effect_type is 'damage' (only type we support for MVP)
        if ability.effect_type != 'damage':
            return {
                "type": "system",
                "actor": "system",
                "text": f"⚠️ {ability.display_name} is a {ability.effect_type} ability. Only attack (damage) abilities are supported for MVP.",
                "party_id": party_id
            }

        # Get caster data
        caster = db.query(Character).filter(Character.id == character_id).first()
        if not caster:
            return {
                "type": "system",
                "actor": "system",
                "text": "⚠️ Could not find your character data.",
                "party_id": party_id
            }

        # 3. Validate character has current_uses > 0
        if caster.current_uses <= 0:
            return {
                "type": "system",
                "actor": "system",
                "text": f"⚠️ {caster.name} has no ability uses remaining this encounter! (0/{caster.max_uses_per_encounter})",
                "party_id": party_id
            }

        # 4. Parse @mention target
        if not target_args or not target_args.strip():
            return {
                "type": "system",
                "actor": "system",
                "text": f"Usage: {macro_command} @target (e.g., {macro_command} @goblin)",
                "party_id": party_id
            }

        from backend.mention_parser import parse_mentions

        # Determine if sender is SW for hidden NPC visibility
        sender_is_sw = connection_manager.is_story_weaver(party_id, character_id)

        parsed = parse_mentions(target_args, party_id, db, sender_is_sw, connection_manager)

        if parsed['unresolved']:
            unresolved_str = ', '.join(parsed['unresolved'])
            return {
                "type": "system",
                "actor": "system",
                "text": f"Target not found: {unresolved_str}. Use /who to see available targets.",
                "party_id": party_id
            }

        if not parsed['mentions']:
            return {
                "type": "system",
                "actor": "system",
                "text": f"No valid target found. Use @name to target (e.g., {macro_command} @goblin)",
                "party_id": party_id
            }

        # Get first target
        target_mention = parsed['mentions'][0]
        target_name = target_mention['name']
        target_id = target_mention['id']
        target_type = target_mention['type']

        # 5. Get target data
        if target_type == "character":
            target = db.query(Character).filter(Character.id == target_id).first()
        else:  # npc
            target = db.query(NPC).filter(NPC.id == target_id).first()

        if not target:
            return {
                "type": "system",
                "actor": "system",
                "text": f"Target '{target_name}' not found in database.",
                "party_id": party_id
            }

        # Allow attacks even when unconscious (needed to reach -10 DP for The Calling)
        target_dp = getattr(target, 'dp', 0)
        if target_dp <= -10:
            # Only block if already past The Calling threshold
            return {
                "type": "system",
                "actor": "system",
                "text": f"⚠️ {target_name} has already faced The Calling (DP: {target_dp}).",
                "party_id": party_id
            }
        # Otherwise allow the attack to continue even if unconscious

        # 6. Execute attack spell
        # Get power source stat value
        power_source = ability.power_source.lower()  # 'pp', 'ip', or 'sp'
        caster_stat_value = getattr(caster, power_source, 1)
        caster_edge = caster.edge or 0

        # Parse and roll spell die
        spell_die = ability.die  # e.g., "2d6", "1d8"
        spell_roll_result = parse_dice_notation(spell_die)
        spell_base_roll = spell_roll_result["total"] - spell_roll_result["modifier"]  # Get just the dice
        spell_total = spell_base_roll + caster_stat_value + caster_edge

        # Check if defender is unconscious (≤ 0 DP) - unconscious targets don't defend
        target_dp = getattr(target, 'dp', 0)
        if target_dp <= 0:
            # Unconscious - no defense roll, attack automatically hits
            defense_total = 0
            defense_die = target.defense_die or "1d6"
            defense_roll_result = {"rolls": [0], "total": 0, "modifier": 0}
            defense_base_roll = 0
            target_pp = target.pp or 1
            target_edge = getattr(target, 'edge', 0) or 0
            damage = spell_total  # Full spell damage hits
        else:
            # Conscious - normal defense roll: defense_die + PP + edge
            defense_die = target.defense_die or "1d6"
            defense_roll_result = parse_dice_notation(defense_die)
            defense_base_roll = defense_roll_result["total"] - defense_roll_result["modifier"]
            target_pp = target.pp or 1
            target_edge = getattr(target, 'edge', 0) or 0
            defense_total = defense_base_roll + target_pp + target_edge
            damage = max(0, spell_total - defense_total)

        # 8. Update defender's current_dp
        old_dp = target.dp or 0
        new_dp = old_dp - damage
        target.dp = new_dp

        # 9. Decrement caster's current_uses
        caster.current_uses = max(0, caster.current_uses - 1)

        # 10. Check for unconscious status at 0 DP or below
        knocked_out = False
        calling_triggered = False

        # Get current target status
        current_status = getattr(target, 'status', 'active')
        if new_dp <= 0 and current_status == 'active':
            target.status = 'unconscious'
            knocked_out = True

        # 11. Check for The Calling at -10 DP (only for Characters, not NPCs)
        if target_type == "character" and new_dp <= -10:
            if not target.in_calling:
                target.in_calling = True
                calling_triggered = True

        db.commit()

        # Update cache if target is cached
        if target_id in connection_manager.character_cache.get(party_id, {}):
            connection_manager.character_cache[party_id][target_id]["dp"] = new_dp
            if knocked_out:
                connection_manager.character_cache[party_id][target_id]["status"] = 'unconscious'

        # 11. Build broadcast message
        # Format spell roll breakdown
        spell_rolls_str = " + ".join(map(str, spell_roll_result["rolls"]))
        spell_breakdown = f"{spell_die} = [{spell_rolls_str}] + {power_source.upper()}({caster_stat_value}) + Edge({caster_edge}) = {spell_total}"

        # Format defense roll breakdown
        if target_dp <= 0:
            defense_breakdown = "No defense (unconscious)"
        else:
            defense_rolls_str = " + ".join(map(str, defense_roll_result["rolls"]))
            defense_breakdown = f"{defense_die} = [{defense_rolls_str}] + PP({target_pp}) + Edge({target_edge}) = {defense_total}"

        # Determine outcome text
        if damage > 0:
            outcome_text = f"💥 {damage} damage! {target_name} at {new_dp}/{target.max_dp or 20} DP"
        else:
            outcome_text = f"🛡️ No damage! {target_name} defends successfully ({new_dp}/{target.max_dp or 20} DP)"

        # Build result message
        result = {
            "type": "spell_cast",
            "actor": actor,
            "caster_name": caster.name,
            "target_name": target_name,
            "spell_name": ability.display_name,
            "ability_type": ability.ability_type,
            "power_source": ability.power_source,
            "spell_die": spell_die,
            "spell_roll": spell_total,
            "spell_breakdown": spell_breakdown,
            "defense_die": defense_die,
            "defense_roll": defense_total,
            "defense_breakdown": defense_breakdown,
            "damage": damage,
            "target_old_dp": old_dp,
            "target_new_dp": new_dp,
            "target_max_dp": target.max_dp or 20,
            "caster_uses_remaining": caster.current_uses,
            "caster_max_uses": caster.max_uses_per_encounter,
            "outcome_text": outcome_text,
            "knocked_out": knocked_out,
            "party_id": party_id,
            "text": f"✨ {caster.name} casts {ability.display_name} on {target_name}!\n"
                    f"🎲 Attack: {spell_breakdown}\n"
                    f"🛡️ Defense: {defense_breakdown}\n"
                    f"{outcome_text}"
        }

        # Add knockout message if applicable
        if knocked_out:
            result["text"] += f"\n💀 {target_name} is knocked unconscious!"
            result["knockout_message"] = f"{target_name} is knocked unconscious!"

        # Add calling trigger if applicable
        if calling_triggered:
            result["text"] += f"\n⚠️ {target_name} has reached -10 DP and enters The Calling!"
            result["calling_triggered"] = True
            result["calling_message"] = f"{target_name} enters The Calling!"

        return result

    except Exception as e:
        logger.error(f"Ability macro error: {e}")
        return {
            "type": "system",
            "actor": "system",
            "text": f"Spell failed: {str(e)}",
            "party_id": party_id
        }
    finally:
        db.close()


async def handle_macro(party_id: str, actor: str, text: str, context: Optional[str] = None, encounter_id: Optional[str] = None, character_id: Optional[str] = None) -> Dict[str, Any]:
    """Handle simple system macros: /roll, /pp, /ip, /sp, /initiative, /attack, /defend, combat management."""
    parts = text.strip().split()
    cmd = parts[0].lower()
    if cmd == "/roll":
        if len(parts) < 2:
            return {"type": "system", "actor": "system", "text": "Usage: /roll 3d6+2", "party_id": party_id}
        try:
            result = parse_dice_notation(parts[1])
            # Math-first formatting: "(4 + 3 + 3) + 2 = 12" or "4 + 3 + 3 = 10"
            plus_join = " + ".join(map(str, result["rolls"]))
            modifier = result["modifier"]
            if modifier:
                mod_str = f" + {abs(modifier)}" if modifier > 0 else f" - {abs(modifier)}"
                equation = f"({plus_join}){mod_str} = {result['total']}"
            else:
                equation = f"{plus_join} = {result['total']}"
            # Include the original expression so the origin of the math is visible in chat
            pretty_text = f"{parts[1]} → {equation}"
            # Log to combat log so dice rolls appear alongside chat events
            try:
                await log_if_allowed("dice_roll", {
                    "event": "dice_roll",
                    "actor": actor,
                    "party_id": party_id,
                    "dice": parts[1],
                    "breakdown": result["rolls"],
                    "modifier": modifier,
                    "result": result["total"],
                    "text": pretty_text,
                    "context": context,
                    "encounter_id": encounter_id,
                    "timestamp": datetime.utcnow().isoformat()
                })
            except Exception:
                # Best-effort logging; ignore failures
                pass
            return {
                "type": "dice_roll",
                "actor": actor,
                "text": pretty_text,
                "dice": parts[1],
                "result": result["total"],
                "breakdown": result["rolls"],
                "party_id": party_id,
            }
        except Exception as e:
            return {"type": "system", "actor": "system", "text": f"Dice error: {e}", "party_id": party_id}
    if cmd in {"/pp", "/ip", "/sp"}:
        # Placeholder: roll 1d6 + stat; later tie to character data
        stat = cmd[1:].upper()
        base_roll = random.randint(1, 6)
        edge_mod = 1  # simple edge placeholder
        result = base_roll + edge_mod
        formula = "1d6+1"
        equation = f"{base_roll} + {edge_mod} = {result}"
        pretty_text = f"{formula} → {equation}"
        # Log stat roll to combat log
        try:
            await log_if_allowed("stat_roll", {
                "event": "stat_roll",
                "actor": actor,
                "party_id": party_id,
                "stat": stat,
                "result": result,
                "text": pretty_text,
                "dice": formula,
                "breakdown": [base_roll],
                "modifier": edge_mod,
                "context": context,
                "encounter_id": encounter_id,
                "timestamp": datetime.utcnow().isoformat()
            })
        except Exception:
            pass
        return {
            "type": "stat_roll",
            "actor": actor,
            "text": pretty_text,
            "stat": stat,
            "result": result,
            "dice": formula,
            "breakdown": [base_roll],
            "modifier": edge_mod,
            "party_id": party_id,
        }
    if cmd == "/initiative":
        # Get character stats from cache for PP and Edge bonus
        char_data = None
        char_id = None

        # First try by character_id
        if character_id:
            char_data = connection_manager.character_cache.get(party_id, {}).get(character_id)
            char_id = character_id

        # Fallback: search by actor name
        if not char_data:
            for cid, data in connection_manager.character_cache.get(party_id, {}).items():
                if data.get("name", "").lower() == actor.lower():
                    char_data = data
                    char_id = cid
                    break

        # Get PP and Edge from character data (1d6 + PP + Edge per rules)
        pp_mod = char_data.get("pp", 1) if char_data else 1
        edge_mod = char_data.get("edge", 0) if char_data else 0
        total_mod = pp_mod + edge_mod

        base_roll = random.randint(1, 6)
        result = base_roll + total_mod
        formula = f"1d6+{pp_mod}+{edge_mod}" if edge_mod else f"1d6+{pp_mod}"
        equation = f"{base_roll} + {pp_mod}" + (f" + {edge_mod}" if edge_mod else "") + f" = {result}"
        pretty_text = f"{formula} → {equation}"

        # Register with active encounter if one exists
        encounter = connection_manager.get_encounter(party_id)
        if encounter and char_id:
            char_type = char_data.get("type", "character") if char_data else "character"
            connection_manager.add_combatant(party_id, char_id, actor, char_type)
            connection_manager.roll_initiative(party_id, char_id, result)

        # Check if encounter exists - show helpful message
        encounter_status = ""
        if not encounter:
            encounter_status = " (No active combat - use /start-combat first)"

        # Log initiative to combat log
        try:
            await log_if_allowed("initiative", {
                "event": "initiative",
                "actor": actor,
                "party_id": party_id,
                "result": result,
                "text": pretty_text,
                "dice": formula,
                "breakdown": [base_roll],
                "modifier": total_mod,
                "context": context,
                "encounter_id": encounter_id,
                "timestamp": datetime.utcnow().isoformat()
            })
        except Exception:
            pass
        return {
            "type": "initiative",
            "actor": actor,
            "text": pretty_text + encounter_status,
            "result": result,
            "dice": formula,
            "breakdown": [base_roll],
            "modifier": total_mod,
            "party_id": party_id
        }

    if cmd == "/attack":
        # Parse @mention target from remaining text
        args = " ".join(parts[1:]) if len(parts) > 1 else ""

        if not args or not args.strip():
            return {
                "type": "system",
                "actor": "system",
                "text": "Usage: /attack @target (e.g., /attack @goblin)",
                "party_id": party_id
            }

        # Parse mentions using mention_parser
        from backend.mention_parser import parse_mentions
        from backend.roll_logic import resolve_multi_die_attack

        db = SessionLocal()
        try:
            # Determine if sender is SW for hidden NPC visibility
            sender_is_sw = False

            # Pass connection_manager to check cached characters first
            parsed = parse_mentions(args, party_id, db, sender_is_sw, connection_manager)

            if parsed['unresolved']:
                unresolved_str = ', '.join(parsed['unresolved'])
                return {
                    "type": "system",
                    "actor": "system",
                    "text": f"Target not found: {unresolved_str}. Use /who to see available targets.",
                    "party_id": party_id
                }

            if not parsed['mentions']:
                return {
                    "type": "system",
                    "actor": "system",
                    "text": "No valid target found. Use @name to target (e.g., /attack @goblin)",
                    "party_id": party_id
                }

            # Get first mention as target
            target_mention = parsed['mentions'][0]
            target_name = target_mention['name']
            target_id = target_mention['id']
            target_type = target_mention['type']

            # Get attacker stats from cache - first try by character_id, then by name
            attacker_data = None
            if character_id:
                attacker_data = connection_manager.character_cache.get(party_id, {}).get(character_id)

            # Fallback: search by name
            if not attacker_data:
                for _, data in connection_manager.character_cache.get(party_id, {}).items():
                    if data.get("name", "").lower() == actor.lower():
                        attacker_data = data
                        break

            # Fallback: load from database if not in cache
            if not attacker_data and character_id:
                char = db.query(Character).filter(Character.id == character_id).first()
                if char:
                    attacker_data = {
                        "id": char.id,
                        "name": char.name,
                        "type": "character",
                        "pp": char.pp,
                        "ip": char.ip,
                        "sp": char.sp,
                        "edge": char.edge,
                        "dp": char.dp,
                        "max_dp": char.max_dp,
                        "attack_style": char.attack_style,
                        "defense_die": char.defense_die
                    }
                    # Cache it for future use
                    if party_id not in connection_manager.character_cache:
                        connection_manager.character_cache[party_id] = {}
                    connection_manager.character_cache[party_id][character_id] = attacker_data

            # Get target stats from cache or database
            defender_data = connection_manager.character_cache.get(party_id, {}).get(target_id)

            if not defender_data:
                # Try to get from database
                if target_type == "character":
                    char = db.query(Character).filter(Character.id == target_id).first()
                    if char:
                        defender_data = {
                            "id": char.id,
                            "name": char.name,
                            "type": "character",
                            "pp": char.pp,
                            "ip": char.ip,
                            "sp": char.sp,
                            "edge": char.edge,
                            "dp": char.dp,
                            "max_dp": char.max_dp,
                            "attack_style": char.attack_style,
                            "defense_die": char.defense_die
                        }
                elif target_type == "npc":
                    npc = db.query(NPC).filter(NPC.id == target_id).first()
                    if npc:
                        defender_data = {
                            "id": npc.id,
                            "name": npc.name,
                            "type": "npc",
                            "pp": npc.pp,
                            "ip": npc.ip,
                            "sp": npc.sp,
                            "edge": npc.edge,
                            "dp": npc.dp,
                            "max_dp": npc.max_dp,
                            "attack_style": npc.attack_style,
                            "defense_die": npc.defense_die
                        }

            if not attacker_data:
                return {
                    "type": "system",
                    "actor": "system",
                    "text": f"Cannot attack: Your character data is not cached. Please reconnect with character_id.",
                    "party_id": party_id
                }

            if not defender_data:
                return {
                    "type": "system",
                    "actor": "system",
                    "text": f"Cannot attack: Target '{target_name}' data not found.",
                    "party_id": party_id
                }

            # DISABLED: Allow attacking unconscious characters to reach -10 DP for The Calling
            # Characters can take damage below 0 DP to trigger The Calling at -10 DP
            # if defender_data.get("dp", 0) <= 0:
            #     return {
            #         "type": "system",
            #         "actor": "system",
            #         "text": f"{target_name} is already defeated (DP: {defender_data.get('dp', 0)}).",
            #         "party_id": party_id
            #     }

            # Get attack and defense stats
            attacker_die = attacker_data.get("attack_style", "1d6")
            defense_die = defender_data.get("defense_die", "1d6")
            attacker_pp = attacker_data.get("pp", 1)
            defender_pp = defender_data.get("pp", 1)
            attacker_edge = attacker_data.get("edge", 0)

            # Resolve multi-die attack
            # Pass defender_dp to check if unconscious (≤ 0 DP = no defense)
            old_dp = defender_data.get("dp", 20)
            result = resolve_multi_die_attack(
                attacker={"name": actor},
                attacker_die_str=attacker_die,
                attacker_stat_value=attacker_pp,
                defender={"name": target_name},
                defense_die_str=defense_die,
                defender_stat_value=defender_pp,
                edge=attacker_edge,
                bap_triggered=False,
                weapon_bonus=0,
                defender_dp=old_dp
            )

            # Calculate new DP
            new_dp = max(0, old_dp - result["total_damage"])
            defender_edge = defender_data.get("edge", 0)

            # Persist DP change to database and check for calling
            knocked_out = False
            calling_triggered = False

            if target_type == "character":
                char = db.query(Character).filter(Character.id == target_id).first()
                if char:
                    char.dp = new_dp
                    if new_dp <= 0 and char.status == 'active':
                        char.status = 'unconscious'
                        knocked_out = True
                    if new_dp <= -10 and not char.in_calling:
                        char.in_calling = True
                        calling_triggered = True
                    db.commit()
            elif target_type == "npc":
                npc = db.query(NPC).filter(NPC.id == target_id).first()
                if npc:
                    npc.dp = new_dp
                    # NPCs don't have calling, just track unconscious
                    if new_dp <= 0:
                        knocked_out = True
                    db.commit()

            # Update cache
            if target_id in connection_manager.character_cache.get(party_id, {}):
                connection_manager.character_cache[party_id][target_id]["dp"] = new_dp
                if knocked_out:
                    connection_manager.character_cache[party_id][target_id]["status"] = 'unconscious'

            # Build detailed attack breakdown
            attack_rolls_str = ", ".join([str(r["total"]) for r in result["individual_rolls"]])
            attack_breakdown = f"{attacker_die} = [{attack_rolls_str}] + PP({attacker_pp}) + Edge({attacker_edge})"

            # Build detailed defense breakdown (for each attack roll)
            # Unconscious defenders (≤ 0 DP) don't defend
            defense_breakdowns = []
            if old_dp <= 0:
                # Unconscious - no defense roll
                defense_breakdown = "No defense (unconscious)"
                for idx, roll_data in enumerate(result["individual_rolls"]):
                    defense_breakdowns.append(defense_breakdown)
            else:
                # Conscious - normal defense rolls
                for idx, roll_data in enumerate(result["individual_rolls"]):
                    defense_roll = roll_data.get("defense_roll", 0)
                    defense_breakdown = f"{defense_die} = [{defense_roll}] + PP({defender_pp}) + Edge({defender_edge})"
                    defense_breakdowns.append(defense_breakdown)

            # Build outcome text
            outcome_lines = []
            outcome_lines.append(f"⚔️ {actor} attacks {target_name}")
            outcome_lines.append(f"")
            outcome_lines.append(f"🎲 Attack: {attack_breakdown}")

            # Add individual roll results
            for idx, roll_data in enumerate(result["individual_rolls"], 1):
                attack_total = roll_data["total"]
                defense_total = roll_data["defense_total"]
                damage = roll_data["damage"]
                hit = damage > 0

                outcome_lines.append(f"   Roll {idx}: {attack_total} vs {defense_total} → {'HIT' if hit else 'MISS'} ({damage} damage)")

            outcome_lines.append(f"")

            if result["total_damage"] > 0:
                outcome_lines.append(f"💥 {result['total_damage']} total damage! {target_name} at {new_dp}/{defender_data.get('max_dp', 20)} DP")
            else:
                outcome_lines.append(f"🛡️ BLOCKED")
                outcome_lines.append(f"")
                outcome_lines.append(f"\"{target_name} blocks all of {actor}'s attacks!\"")

            if knocked_out:
                outcome_lines.append(f"💀 {target_name} is knocked unconscious!")

            if calling_triggered:
                outcome_lines.append(f"⚠️ {target_name} has reached -10 DP and enters The Calling!")

            outcome_text = "\n".join(outcome_lines)

            # Return combat event message for broadcast
            return {
                "type": "combat_event",
                "attacker": actor,
                "attacker_name": actor,
                "defender": target_name,
                "defender_name": target_name,
                "technique": "Basic Attack",
                "attacker_weapon": attacker_die,
                "defender_defense": defense_die,
                "total_damage": result["total_damage"],
                "outcome": result["outcome"],
                "narrative": result["narrative"],
                "text": outcome_text,
                "defender_old_dp": old_dp,
                "defender_new_dp": new_dp,
                "defender_max_dp": defender_data.get("max_dp", 20),
                "individual_rolls": result["individual_rolls"],
                "hit_count": result["details"]["hit_count"],
                "total_rolls": result["details"]["total_rolls"],
                "auto_defense": True,
                "knocked_out": knocked_out,
                "calling_triggered": calling_triggered,
                "party_id": party_id
            }

        except Exception as e:
            logger.error(f"Attack macro error: {e}")
            return {
                "type": "system",
                "actor": "system",
                "text": f"Attack failed: {str(e)}",
                "party_id": party_id
            }
        finally:
            db.close()

    if cmd == "/defend":
        # Roll defense die for the character
        # Get character stats from cache if available
        char_data = None
        for char_id, data in connection_manager.character_cache.get(party_id, {}).items():
            if data.get("name", "").lower() == actor.lower():
                char_data = data
                break

        # Default defense die is 1d6 if not found
        defense_die = "1d6"
        if char_data and char_data.get("defense_die"):
            defense_die = char_data["defense_die"]

        # Parse and roll the defense die
        try:
            result = parse_dice_notation(defense_die)
            plus_join = " + ".join(map(str, result["rolls"]))
            modifier = result["modifier"]
            if modifier:
                mod_str = f" + {abs(modifier)}" if modifier > 0 else f" - {abs(modifier)}"
                equation = f"({plus_join}){mod_str} = {result['total']}"
            else:
                equation = f"{plus_join} = {result['total']}"
            pretty_text = f"{defense_die} → {equation}"

            # Log defense roll
            try:
                await log_if_allowed("defend", {
                    "event": "defend",
                    "actor": actor,
                    "party_id": party_id,
                    "dice": defense_die,
                    "breakdown": result["rolls"],
                    "modifier": modifier,
                    "result": result["total"],
                    "text": pretty_text,
                    "context": context,
                    "encounter_id": encounter_id,
                    "timestamp": datetime.utcnow().isoformat()
                })
            except Exception:
                pass

            return {
                "type": "defend",
                "actor": actor,
                "text": pretty_text,
                "dice": defense_die,
                "result": result["total"],
                "breakdown": result["rolls"],
                "modifier": modifier,
                "party_id": party_id,
            }
        except Exception as e:
            return {"type": "system", "actor": "system", "text": f"Defense roll error: {e}", "party_id": party_id}

    if cmd == "/who":
        # List all available targets (characters and NPCs) in the party with stats
        db = SessionLocal()
        try:
            # Check if sender is SW for visibility
            sender_is_sw = False
            if character_id:
                is_sw, _ = check_story_weaver(character_id, party_id)
                sender_is_sw = is_sw

            # Get cached characters (actively connected via WebSocket)
            cached_chars = connection_manager.character_cache.get(party_id, {})
            online_characters = []

            for char_id, char_data in cached_chars.items():
                char_type = char_data.get('type', 'character')
                if char_type == 'character':
                    # Format: @Name (DP: X/Y, Weapon: 2d4, Defense: 1d6) 🟢
                    dp = char_data.get('dp', '?')
                    max_dp = char_data.get('max_dp', '?')
                    weapon = char_data.get('attack_style', '1d6')
                    defense = char_data.get('defense_die', '1d6')
                    online_characters.append(
                        f"  @{char_data['name']} (DP: {dp}/{max_dp}, Weapon: {weapon}, Defense: {defense}) 🟢"
                    )

            # Get party members from database (may include offline members)
            db_characters = (
                db.query(Character)
                .join(PartyMembership, PartyMembership.character_id == Character.id)
                .filter(PartyMembership.party_id == party_id)
                .all()
            )

            offline_characters = []
            online_char_ids = set(cached_chars.keys())

            for char in db_characters:
                if char.id not in online_char_ids:
                    # Format with stats for offline players
                    dp = char.dp if char.dp is not None else '?'
                    max_dp = char.max_dp if char.max_dp is not None else '?'
                    weapon = char.attack_style or '1d6'
                    defense = char.defense_die or '1d6'
                    offline_characters.append(
                        f"  @{char.name} (DP: {dp}/{max_dp}, Weapon: {weapon}, Defense: {defense}) ⚫"
                    )

            # Get NPCs (visible only, unless sender is SW)
            npc_query = db.query(NPC).filter(NPC.party_id == party_id)
            if not sender_is_sw:
                npc_query = npc_query.filter(NPC.visible_to_players == True)

            npcs = npc_query.all()
            npc_list = []
            for npc in npcs:
                dp = npc.dp if npc.dp is not None else '?'
                max_dp = npc.max_dp if npc.max_dp is not None else '?'
                weapon = npc.attack_style or '1d6'
                defense = npc.defense_die or '1d6'
                # Check if NPC is in cache (active in combat)
                npc_in_cache = npc.id in cached_chars
                status = "🔴" if npc_in_cache else "⚪"
                npc_list.append(
                    f"  @{npc.name} (DP: {dp}/{max_dp}, Weapon: {weapon}, Defense: {defense}) {status}"
                )

            # Format response
            lines = ["📋 **Available Targets:**"]

            if online_characters:
                lines.append("**Players (online):**")
                lines.extend(online_characters)

            if offline_characters:
                lines.append("**Players (offline):**")
                lines.extend(offline_characters)

            if npc_list:
                lines.append("**NPCs:**")
                lines.extend(npc_list)

            if not online_characters and not offline_characters and not npc_list:
                lines.append("No characters or NPCs found in this party.")

            lines.append("\n💡 Multi-die weapons (2d4, 3d6) attack multiple times per action!")

            return {
                "type": "system",
                "actor": "system",
                "text": "\n".join(lines),
                "party_id": party_id
            }

        except Exception as e:
            logger.error(f"/who command error: {e}")
            return {
                "type": "system",
                "actor": "system",
                "text": f"Failed to list targets: {str(e)}",
                "party_id": party_id
            }
        finally:
            db.close()

    if cmd == "/start-combat":
        # SW-only: Start a combat encounter
        is_sw, error_msg = check_story_weaver(character_id, party_id)
        if not is_sw:
            return {
                "type": "system",
                "actor": "system",
                "text": error_msg,
                "party_id": party_id
            }

        encounter_id = connection_manager.start_encounter(party_id, actor)

        instructions = """⚔️ **Combat encounter started!**

📜 **Quick Guide:**
1. Everyone roll `/initiative` to determine turn order
2. Story Weaver uses `/turn-order` to lock in order
3. On your turn, `/attack @target` to strike
4. Story Weaver uses `/next-turn` to advance
5. End combat with `/end-combat`

💡 Use `/who` to see everyone's DP and weapon dice!
💡 Use `/combat-help` for detailed combat rules."""

        return {
            "type": "system",
            "actor": "system",
            "text": instructions,
            "party_id": party_id
        }

    if cmd == "/end-combat":
        # SW-only: End the current combat encounter
        is_sw, error_msg = check_story_weaver(character_id, party_id)
        if not is_sw:
            return {
                "type": "system",
                "actor": "system",
                "text": error_msg,
                "party_id": party_id
            }

        encounter = connection_manager.get_encounter(party_id)
        if not encounter:
            return {
                "type": "system",
                "actor": "system",
                "text": "No active combat encounter to end.",
                "party_id": party_id
            }
        connection_manager.end_encounter(party_id)
        return {
            "type": "system",
            "actor": "system",
            "text": "🏁 Combat encounter ended.",
            "party_id": party_id
        }

    if cmd == "/end-encounter":
        # SW-only: End encounter and reset all ability uses for party members
        is_sw, error_msg = check_story_weaver(character_id, party_id)
        if not is_sw:
            return {
                "type": "system",
                "actor": "system",
                "text": error_msg,
                "party_id": party_id
            }

        db = SessionLocal()
        try:
            # Get all characters in this party via PartyMembership
            party_members = db.query(Character).join(
                PartyMembership, PartyMembership.character_id == Character.id
            ).filter(PartyMembership.party_id == party_id).all()

            reset_count = 0
            for char in party_members:
                char.current_uses = char.max_uses_per_encounter
                reset_count += 1

            db.commit()

            # Also end any active combat encounter
            if connection_manager.get_encounter(party_id):
                connection_manager.end_encounter(party_id)

            return {
                "type": "system",
                "actor": "system",
                "text": f"✨ **Encounter ended!** All ability uses restored for {reset_count} character(s).",
                "party_id": party_id
            }

        except Exception as e:
            logger.error(f"/end-encounter error: {e}")
            db.rollback()
            return {
                "type": "system",
                "actor": "system",
                "text": f"Failed to end encounter: {str(e)}",
                "party_id": party_id
            }
        finally:
            db.close()

    if cmd == "/turn-order":
        # Display current turn order
        encounter = connection_manager.get_encounter(party_id)
        if not encounter:
            return {
                "type": "system",
                "actor": "system",
                "text": "No active combat encounter. Use /start-combat to begin.",
                "party_id": party_id
            }

        # Sort initiative if not already sorted
        if not encounter.get('turn_order'):
            connection_manager.sort_initiative(party_id)
            encounter = connection_manager.get_encounter(party_id)

        turn_order = encounter.get('turn_order', [])
        if not turn_order:
            return {
                "type": "system",
                "actor": "system",
                "text": "No combatants have rolled initiative yet. Everyone roll /initiative!",
                "party_id": party_id
            }

        # Format turn order display
        current_idx = encounter.get('current_turn_index', 0)
        turn_num = encounter.get('turn_number', 0)

        # If turn_number is 0, this is the first time showing turn order - start round 1
        if turn_num == 0:
            encounter['turn_number'] = 1
            turn_num = 1

        lines = [f"🧭 **Turn Order** (Round {turn_num})"]

        for i, combatant in enumerate(turn_order):
            marker = "▶️ " if i == current_idx else "   "
            init_val = combatant.get('initiative', '?')
            line = f"{marker}{i+1}. {combatant['name']} (Init: {init_val})"

            # Show tie-breaker reason if applicable
            tiebreaker_reason = combatant.get('tiebreaker_reason')
            if tiebreaker_reason:
                line += f" ✓won on {tiebreaker_reason}"

            lines.append(line)

        # Show whose turn it is
        current_combatant = turn_order[current_idx] if turn_order else None
        if current_combatant:
            lines.append(f"\n⚔️ **{current_combatant['name']}**'s turn!")

        return {
            "type": "system",
            "actor": "system",
            "text": "\n".join(lines),
            "party_id": party_id
        }

    if cmd == "/next-turn":
        # SW-only: Advance to next combatant
        is_sw, error_msg = check_story_weaver(character_id, party_id)
        if not is_sw:
            return {
                "type": "system",
                "actor": "system",
                "text": error_msg,
                "party_id": party_id
            }

        encounter = connection_manager.get_encounter(party_id)
        if not encounter:
            return {
                "type": "system",
                "actor": "system",
                "text": "No active combat encounter.",
                "party_id": party_id
            }

        turn_order = encounter.get('turn_order', [])
        if not turn_order:
            return {
                "type": "system",
                "actor": "system",
                "text": "Turn order not established. Everyone roll /initiative first!",
                "party_id": party_id
            }

        # Track round before advancing to detect round change
        old_round = encounter.get('turn_number', 1)

        # Advance turn
        connection_manager.next_turn(party_id)
        encounter = connection_manager.get_encounter(party_id)

        current_combatant = connection_manager.get_current_turn(party_id)
        turn_num = encounter.get('turn_number', 1)

        if current_combatant:
            # Check if we wrapped to a new round
            if turn_num > old_round:
                return {
                    "type": "system",
                    "actor": "system",
                    "text": f"🔄 **Round {turn_num} begins!**\n⏭️ **{current_combatant['name']}**'s turn!",
                    "party_id": party_id
                }
            return {
                "type": "system",
                "actor": "system",
                "text": f"⏭️ **{current_combatant['name']}**'s turn! (Round {turn_num})",
                "party_id": party_id
            }
        return {
            "type": "system",
            "actor": "system",
            "text": "Turn advanced.",
            "party_id": party_id
        }

    if cmd == "/combat-help":
        help_text = """⚔️ **Combat System Guide**

**Initiative & Encounters:**
• `/initiative` - Roll your initiative (1d20)
• `/initiative show` - Display initiative order
• `/initiative @target` (SW) - Roll for someone else
• `/initiative silent @target` (SW) - Hidden roll for NPCs
• `/initiative end` (SW) - End encounter & restore ability uses
• `/initiative clear` (SW) - Clear initiative

**Abilities & Powers:**
• Custom macros (e.g., `/heal`, `/fireball`, `/shield`)
• 3 uses per encounter per character level
• Target with `@name` for specific targets
• Restored automatically when encounter ends

**Combat Actions:**
• `/attack @target` - Attack a target
  → Defense is auto-rolled for the defender
  → Multi-die weapons (2d4, 2d6) make multiple attacks
• `/defend` - Manually roll defense (optional)
• `/pp`, `/ip`, `/sp` - Roll stat checks

**Combat Info:**
• `/who` - See everyone's DP, weapons, and status
• Multi-die weapons attack multiple times per action
• Defense is automatically rolled during attacks
• At 0 DP, you're knocked out
• At -10 DP, you face The Calling

**Legacy Commands:**
• `/start-combat` (SW) - Old combat system
• `/turn-order` - Old turn tracking
• `/next-turn` (SW) - Old turn advance
• `/end-combat` (SW) - Old combat end"""

        return {
            "type": "system",
            "actor": "system",
            "text": help_text,
            "party_id": party_id
        }

    if cmd == "/ooc":
        # OOC command - handled client-side but we need to echo it properly
        ooc_text = " ".join(parts[1:]) if len(parts) > 1 else ""
        if not ooc_text:
            return {
                "type": "system",
                "actor": "system",
                "text": "Usage: /ooc <message>",
                "party_id": party_id
            }
        return {
            "type": "message",
            "actor": actor,
            "text": ooc_text,
            "party_id": party_id,
            "chat_mode": "ooc",
            "is_ooc_command": True
        }

    if cmd == "/say":
        # Say command - explicit IC message
        say_text = " ".join(parts[1:]) if len(parts) > 1 else ""
        if not say_text:
            return {
                "type": "system",
                "actor": "system",
                "text": "Usage: /say <message>",
                "party_id": party_id
            }
        return {
            "type": "message",
            "actor": actor,
            "text": say_text,
            "party_id": party_id,
            "chat_mode": "ic"
        }

    if cmd == "/help":
        help_text = """📜 **Available Commands:**

**Chat:**
• `/say <message>` - In-character speech (green)
• `/ooc <message>` - Out-of-character chat (gray, goes to OOC tab)
• `/whisper @player <message>` - Private message (purple)
• `/w @player <message>` - Whisper shorthand

**Dice & Stat Checks:**
• `/roll XdY+Z` - Roll dice (e.g., /roll 2d6+3)
• `/pp`, `/ip`, `/sp` - Roll stat checks (1d6 + stat + Edge)
• `/who` - List party members with stats

**Abilities & Macros:**
• `/<custom>` - Cast abilities/spells/techniques (e.g., /heal, /fireball)
• `/<custom> @target` - Cast on specific target(s)
• Uses: 3 per encounter per character level

**Initiative & Encounters:**
• `/initiative` - Roll your own initiative (1d20)
• `/initiative show` - Display full initiative order
• `/initiative @target` (SW) - Roll initiative for PC/NPC
• `/initiative silent @target` (SW) - Hidden roll (only SW sees result)
• `/initiative end` (SW) - End encounter & restore all ability uses
• `/initiative clear` (SW) - Clear initiative without ending encounter
• `/rest` (SW) - Restore all ability uses (short rest)

**Combat (Legacy):**
• `/combat-help` - Full combat guide
• `/attack @target` - Attack someone
• `/defend` - Roll defense manually

**Legend:** (SW) = Story Weaver only"""

        return {
            "type": "system",
            "actor": "system",
            "text": help_text,
            "party_id": party_id
        }

    # Try custom ability macro before returning unknown
    # Extract target args (everything after the command)
    target_args = " ".join(parts[1:]) if len(parts) > 1 else ""
    ability_result = await handle_ability_macro(
        party_id=party_id,
        actor=actor,
        macro_command=cmd,
        target_args=target_args,
        character_id=character_id,
        context=context
    )
    if ability_result is not None:
        return ability_result

    # Unknown macro → echo as system
    return {"type": "system", "actor": "system", "text": f"Unknown command: {cmd}", "party_id": party_id}

@chat_blp.get("/chat/party/{party_id}/connections", response_model=Dict[str, Any])
async def party_connections(party_id: str):
    """
    Debug endpoint: see active WebSocket connections for a party.

    Returns connection count, character IDs, roles, and cached character names.
    """
    conns = connection_manager.active_connections.get(party_id, [])
    connection_details = []

    for ws, char_id, metadata in conns:
        connection_details.append({
            "character_id": char_id or None,
            "character_name": metadata.get("character_name", "Unknown"),
            "role": metadata.get("role", "player")
        })

    return {
        "party_id": party_id,
        "connection_count": len(conns),
        "connections": connection_details,
        "story_weaver_id": connection_manager.get_party_sw(party_id),
        "cached_characters": list(connection_manager.character_cache.get(party_id, {}).keys())
    }


@chat_blp.get("/chat/party/{party_id}/messages")
async def get_party_messages(
    party_id: str,
    limit: int = Query(50, description="Maximum number of messages to return"),
    offset: int = Query(0, description="Number of messages to skip")
):
    """
    Get message history for a party.

    Returns recent messages ordered by timestamp (oldest first).
    Used by frontend to load chat history on connection.

    Query Parameters:
        limit: Maximum number of messages to return (default: 50)
        offset: Number of messages to skip for pagination (default: 0)
    """
    db = SessionLocal()
    try:
        # Fetch messages for this party
        messages = db.query(Message)\
            .filter(Message.party_id == party_id)\
            .order_by(Message.created_at.desc())\
            .offset(offset)\
            .limit(limit)\
            .all()

        # Reverse to get oldest-first ordering
        messages = list(reversed(messages))

        # Format for frontend
        return {
            "party_id": party_id,
            "count": len(messages),
            "messages": [
                {
                    "id": msg.id,
                    "sender_id": msg.sender_id,
                    "sender_name": msg.sender_name,
                    "content": msg.content,
                    "message_type": msg.message_type,
                    "chat_mode": msg.mode,
                    "timestamp": msg.created_at.isoformat(),
                    "type": f"chat_{msg.mode}" if msg.mode else "chat"
                }
                for msg in messages
            ]
        }
    except Exception as e:
        logger.error(f"Failed to fetch message history: {e}")
        return {"party_id": party_id, "count": 0, "messages": [], "error": str(e)}
    finally:
        db.close()


async def log_combat_event(entry: Dict[str, Any]):
    try:
        async with httpx.AsyncClient() as client:
            await client.post(COMBAT_LOG_URL, json=entry)
    except Exception as e:
        logger.warning(f"Combat log failed: {e}")

actor_roll_modes = {
    "Kai": "manual",
    "Aria": "auto",
    "NPC Guard": "auto",
    "Bill": "prompt"
}

@chat_blp.get("/chat", response_class=HTMLResponse)
async def chat_get(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request, "response": None})


@chat_blp.websocket("/chat/party/{party_id}")
async def chat_party_ws(
    websocket: WebSocket,
    party_id: str,
    character_id: Optional[str] = Query(None, description="Character or NPC ID to associate with this connection")
):
    """
    WebSocket endpoint for party chat with character caching.

    Query Parameters:
        character_id: Optional UUID of Character or NPC to associate with connection.
                      If provided, character stats are cached for macro support.

    Connection Flow:
        1. Accept WebSocket connection
        2. If character_id provided, fetch and cache character data
        3. Determine if character is Story Weaver
        4. Handle messages and macros with cached stats

    Examples:
        ws://localhost:8000/api/chat/party/test-party
        ws://localhost:8000/api/chat/party/test-party?character_id=char-uuid-123
    """
    # Accept connection; optional api_key via query param for convenience
    # Note: API key enforcement is not applied to WebSocket in HTTP middleware
    await websocket.accept()

    # Add connection with character caching
    await connection_manager.add_connection(party_id, websocket, character_id)

    # Get connection metadata
    metadata = connection_manager.get_connection_metadata(party_id, websocket)
    role = metadata.get("role", "player") if metadata else "player"
    character_name = metadata.get("character_name", "Unknown") if metadata else "Unknown"

    # Send welcome message to the connecting client with their character info
    # This allows the frontend to update the Actor field with the correct name
    if character_id:
        try:
            await websocket.send_json({
                "type": "welcome",
                "character_id": character_id,
                "character_name": character_name,
                "role": role,
                "party_id": party_id
            })
        except Exception:
            pass

    # Notify party of join (if character_id provided)
    if character_id and character_name != "Unknown":
        await connection_manager.broadcast(party_id, {
            "type": "system",
            "actor": "system",
            "text": f"{character_name} ({role}) joined the party",
            "party_id": party_id
        })

    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                payload = {"type": "message", "actor": "unknown", "text": data}

            actor = payload.get("actor", character_name if character_id else "unknown")
            text = payload.get("text", "")
            ctx = payload.get("context")
            enc_id = payload.get("encounter_id")
            chat_mode = payload.get("chat_mode")  # ic, ooc, or whisper
            whisper_targets = payload.get("whisper_targets", [])  # List of target names

            if isinstance(text, str) and text.startswith("/"):
                # Simple macro throttle per actor in party to prevent spam
                key = f"{party_id}:{actor}"
                now = monotonic()
                last = macro_last_ts.get(key, 0.0)
                threshold = WS_MACRO_THROTTLE_MS / 1000.0
                if now - last < threshold:
                    remaining = max(0.0, threshold - (now - last))
                    try:
                        await websocket.send_json({
                            "type": "system",
                            "actor": "system",
                            "text": f"Rate-limited. Try again in {remaining:.2f}s",
                            "party_id": party_id
                        })
                    except Exception:
                        pass
                    continue
                macro_last_ts[key] = now
                msg = await handle_macro(party_id, actor, text, ctx, enc_id, character_id)

                # Check if this is an error/unknown command or help text - send only to sender
                is_private_message = (
                    msg.get("type") == "system" and
                    msg.get("actor") == "system" and
                    any(phrase in msg.get("text", "").lower() for phrase in [
                        "unknown command", "usage:", "not found", "error", "failed", "invalid",
                        "only the story weaver", "cannot verify", "has no ability uses",
                        "available commands", "📜"  # Help text markers
                    ])
                )

                if is_private_message:
                    # Send private messages (errors, help text) only to the sender
                    try:
                        await websocket.send_json(msg)
                    except Exception:
                        pass
                else:
                    # Regular broadcast for valid macro results
                    await broadcast(party_id, msg)
            elif chat_mode == "whisper" and whisper_targets:
                # Private whisper - only send to targets and SW
                msg = {
                    "type": "chat_whisper",
                    "actor": actor,
                    "text": text,
                    "party_id": party_id,
                    "chat_mode": "whisper",
                    "whisper_targets": whisper_targets,
                }
                await connection_manager.broadcast_whisper(
                    party_id, msg, whisper_targets, actor
                )
                logger.info(f"Whisper from {actor} to {whisper_targets}: {text[:50]}...")

                # Save whisper to database
                save_message_to_db(
                    party_id=party_id,
                    character_id=character_id,
                    character_name=actor,
                    message_text=text,
                    message_type='chat',
                    chat_mode='whisper'
                )
            else:
                # Regular message or IC/OOC (broadcast to all)
                # Determine message type based on chat_mode for proper tab routing
                if chat_mode == 'ooc':
                    message_type = 'chat_ooc'
                elif chat_mode == 'ic':
                    message_type = 'chat_ic'
                else:
                    message_type = payload.get("type", "message")

                msg = {
                    "type": message_type,
                    "actor": actor,
                    "text": text,
                    "party_id": party_id,
                    "chat_mode": chat_mode if chat_mode else None
                }
                await broadcast(party_id, msg)

                # Save regular message to database
                save_message_to_db(
                    party_id=party_id,
                    character_id=character_id,
                    character_name=actor,
                    message_text=text,
                    message_type='chat',
                    chat_mode=chat_mode
                )
    except WebSocketDisconnect:
        # Notify party of leave
        if character_id and character_name != "Unknown":
            try:
                await connection_manager.broadcast(party_id, {
                    "type": "system",
                    "actor": "system",
                    "text": f"{character_name} left the party",
                    "party_id": party_id
                })
            except Exception:
                pass
        connection_manager.remove_connection(party_id, websocket)
    except Exception as e:
        logger.error(f"WebSocket error for {character_name} in {party_id}: {e}")
        connection_manager.remove_connection(party_id, websocket)
        # Attempt to notify others of disconnect
        try:
            await connection_manager.broadcast(party_id, {
                "type": "system",
                "actor": "system",
                "text": f"{character_name} disconnected: {e}",
                "party_id": party_id
            })
        except Exception:
            pass


@chat_blp.post("/chat", response_class=HTMLResponse)
async def chat_post(request: Request, payload: str = Form(...)):
    try:
        data = json.loads(payload)
        result = resolve_spellcast(
            caster=data["caster"],
            target=data["target"],
            spell=data["spell"],
            encounter_id=data.get("encounter_id"),
            log=True
        )
        response = {
            "narration": result.get("notes", []),
            "effects": result.get("effects", []),
            "log": result.get("log", [])
        }
    except Exception as e:
        logger.error(f"Chat error: {e}")
        response = {
            "narration": [f"Error: {str(e)}"],
            "effects": [],
            "log": []
        }

    return templates.TemplateResponse("chat.html", {"request": request, "response": response})

@chat_blp.post("/chat/api", response_model=Dict[str, Any])
async def chat_api(data: ChatMessageSchema = Body(...)):
    response = {
        "actor": data.actor,
        "triggered_by": data.triggered_by or data.actor,
        "message": data.message,
        "context": data.context,
        "timestamp": data.timestamp,
        }

    # Handle action logic
    if data.action:
        if data.action.type in ["spell", "technique"]:
            response["narration"] = f"{data.actor} uses {data.action.name} ({data.action.type})!"
            response["simulated_outcome"] = {
                "traits": data.action.traits,
                "tags": data.action.tags
            }

        elif data.action.type == "custom":
            response["narration"] = f"{data.actor} performs a custom move: {data.action.name}. {data.action.description or ''}"

        elif data.action.type in ["buff", "debuff"]:
            response["narration"] = f"{data.actor} applies a {data.action.type}: {data.action.name}."

        elif data.action.type == "summon":
            response["narration"] = f"{data.actor} summons: {data.action.name}. {data.action.description or ''}"

    # Handle tethers
    if data.tethers:
        response["tether_echoes"] = [
            f"Tether '{t}' may trigger a bonus or memory echo." for t in data.tethers
        ]

    # Handle roll metadata
    if data.roll:
        response["roll_metadata"] = data.roll

    # Handle roll mode logic
    target = data.actor
    roll_mode = actor_roll_modes.get(target, "manual")

    if roll_mode in ["manual", "prompt"]:
        response["roll_request"] = {
            "target": target,
            "type": "defense",
            "reason": f"Incoming action: {data.action.name}",
            "expected_die": "1d10 + PP + Edge",
            "submit_to": "/resolve_roll",
            "example_payload": {
                "actor": target,
                "roll_type": "defense",
                "die": "1d10",
                "modifiers": {"PP": 2, "Edge": 1},
                "result": 11,
                "context": data.context,
                "triggered_by": data.triggered_by or target
                        }
                    }   
    
    if roll_mode == "prompt":
        response["roll_request"]["fallback_time"] = "5 minutes"
    elif roll_mode == "auto":
        modifiers = {"PP": 2, "Edge": 1}  # Stubbed for now
        result = simulate_roll("1d10", modifiers)
        response["auto_roll"] = {
            "target": target,
            "type": "defense",
            "die": "1d10",
            **result
        }
        response.setdefault("log", []).append({
            "event": "auto_roll",
            "actor": target,
            "details": result
        })

    await log_combat_event({
    "actor": data.actor,
    "timestamp": data.timestamp,
    "context": data.context,
    "encounter_id": data.context,
    "triggered_by": data.triggered_by or data.actor,
    "narration": response.get("narration"),
    "action": data.action.dict() if data.action else None,
    "roll": data.roll,
    "tethers": data.tethers,
    "log": response.get("log")
    })

    return response

@chat_blp.get("/chat/schema", response_model=Dict[str, Any])
async def chat_schema():
    return {
        "actor": "Kai",
        "triggered_by": "Story Weaver",
        "message": "Kai casts Ember Veil!",
        "context": "Volcanic battlefield",
        "action": {
            "name": "Ember Veil",
            "type": "spell",
            "target": "aoe",
            "traits": {"IP": 3, "Edge": 2},
            "tags": ["fire", "protective"],
            "description": "A veil of flame shields allies and scorches nearby foes."
        },
        "tethers": ["Protect the innocent"],
        "roll": {
            "die": "1d10",
            "modifiers": {"IP": 3, "Edge": 2},
            "result": 9
        },
        "timestamp": "2025-11-07T11:30:00"
    }

def simulate_roll(die: str, modifiers: Dict[str, int]) -> Dict[str, Any]:
    """
    Simulates a roll like '1d10' and adds modifiers.
    Returns the breakdown and total.
    """
    num, sides = map(int, die.lower().split("d"))
    rolls = [random.randint(1, sides) for _ in range(num)]
    mod_total = sum(modifiers.values())
    total = sum(rolls) + mod_total

    return {
        "rolls": rolls,
        "modifiers": modifiers,
        "total": total
    }

@chat_blp.post("/resolve_roll", response_model=Dict[str, Any])
async def resolve_roll(data: ResolveRollSchema = Body(...)):
    narration = f"{data.actor} resolves a {data.roll_type} roll with {data.result} using {data.die}."
    
    # Stubbed logic — later compare against incoming threat
    outcome = "success" if data.result >= 10 else "failure"

    await log_combat_event({
        "actor": data.actor,
        "timestamp": getattr(data, "timestamp", "unknown"),
        "context": data.context,
        "encounter_id": data.encounter_id,
        "triggered_by": data.triggered_by or data.actor,
        "narration": narration,
        "roll": {
            "die": data.die,
            "modifiers": data.modifiers,
            "result": data.result
        },
        "outcome": outcome,
        "log": [{
            "event": "resolve_roll",
            "actor": data.actor,
            "result": data.result,
            "outcome": outcome
        }]
    })

    return {
        "actor": data.actor,
        "triggered_by": data.triggered_by or data.actor,
        "roll_type": data.roll_type,
        "result": data.result,
        "outcome": outcome,
        "narration": narration,
        "log": [{
            "event": "resolve_roll",
            "actor": data.actor,
            "roll": {
                "die": data.die,
                "modifiers": data.modifiers,
                "result": data.result
            },
            "outcome": outcome
        }]
    }
