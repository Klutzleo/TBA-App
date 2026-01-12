from urllib import response
from fastapi import APIRouter, Request, Form, Body, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from backend.magic_logic import resolve_spellcast
from backend.db import SessionLocal
from backend.models import Character, Party, NPC, PartyMembership, CombatTurn
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
                # Try to load party metadata (for SW check)
                if party_id not in self.party_cache:
                    party = db.query(Party).filter(Party.id == party_id).first()
                    if party:
                        self.party_cache[party_id] = {
                            "story_weaver_id": party.story_weaver_id,
                            "created_by_id": party.created_by_id
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

        Ties broken by: PP > IP > SP (from character cache)
        """
        if party_id not in self.active_encounters:
            return

        encounter = self.active_encounters[party_id]

        # Filter combatants with initiative rolled
        combatants_with_init = [c for c in encounter['combatants'] if c['initiative'] is not None]

        # Sort by initiative (highest first), with tiebreaker using stats
        def sort_key(combatant):
            char_stats = self.get_character_stats(party_id, combatant['id'])
            pp = char_stats.get('pp', 0) if char_stats else 0
            ip = char_stats.get('ip', 0) if char_stats else 0
            sp = char_stats.get('sp', 0) if char_stats else 0

            # Return tuple: (initiative desc, pp desc, ip desc, sp desc)
            return (-combatant['initiative'], -pp, -ip, -sp)

        encounter['turn_order'] = sorted(combatants_with_init, key=sort_key)
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


async def handle_macro(party_id: str, actor: str, text: str, context: Optional[str] = None, encounter_id: Optional[str] = None) -> Dict[str, Any]:
    """Handle simple system macros: /roll, /pp, /ip, /sp, /initiative (placeholder)."""
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
        base_roll = random.randint(1, 6)
        edge_mod = 1  # simple edge placeholder
        result = base_roll + edge_mod
        formula = "1d6+1"
        equation = f"{base_roll} + {edge_mod} = {result}"
        pretty_text = f"{formula} → {equation}"
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
                "modifier": edge_mod,
                "context": context,
                "encounter_id": encounter_id,
                "timestamp": datetime.utcnow().isoformat()
            })
        except Exception:
            pass
        return {
            "type": "initiative",
            "actor": actor,
            "text": pretty_text,
            "result": result,
            "dice": formula,
            "breakdown": [base_roll],
            "modifier": edge_mod,
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

        db = SessionLocal()
        try:
            # Determine if sender is SW for hidden NPC visibility
            sender_is_sw = False
            # TODO: Get character_id from connection metadata and check if SW

            parsed = parse_mentions(args, party_id, db, sender_is_sw)

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
            target = parsed['mentions'][0]
            target_name = target['name']
            target_id = target['id']
            target_type = target['type']

            # For now, return a placeholder attack message
            # TODO: Implement full combat resolution with cached character stats
            return {
                "type": "system",
                "actor": "system",
                "text": f"⚔️ {actor} attacks {target_name} ({target_type})! [Combat system integration pending]",
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
                msg = await handle_macro(party_id, actor, text, ctx, enc_id)
            else:
                msg = {
                    "type": payload.get("type", "message"),
                    "actor": actor,
                    "text": text,
                    "party_id": party_id,
                }
            await broadcast(party_id, msg)
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
