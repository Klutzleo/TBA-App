"""
Campaign WebSocket endpoint for real-time multiplayer TTRPG.

Handles:
- Player chat (IC/OOC)
- Whispers (private messages)
- Combat commands and results
- GM narration
- Dice rolls
- Image attachments (maps, character art)
- System notifications (player join/leave)
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, List
from uuid import UUID
from datetime import datetime
import logging
import json
import re
import random

from backend.db import get_db
from backend.models import Party, Character, User, CampaignMembership, Message, Ability, Encounter, InitiativeRoll, NPC, Campaign
from backend.auth.jwt import decode_access_token
from backend.roll_logic import roll_dice
from routes.schemas.campaign import (
    ChatMessage,
    WhisperMessage,
    CombatCommand,
    GMNarration,
    DiceRollRequest,
    AbilityCastCommand,
    ChatBroadcast,
    WhisperBroadcast,
    CombatResultBroadcast,
    AbilityCastBroadcast,
    NarrationBroadcast,
    DiceRollBroadcast,
    SystemNotification,
    InitiativeResultBroadcast
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/campaign", tags=["Campaign"])

# ============================================================================
# CONNECTION MANAGER (Tracks active WebSocket connections per campaign)
# ============================================================================

class CampaignConnectionManager:
    """Manages WebSocket connections for campaign chat rooms."""
    
    def __init__(self):
        # campaign_id → list of (websocket, user_id, display_name, username)
        self.active_connections: Dict[UUID, List[tuple[WebSocket, UUID, str, str]]] = {}
    
    async def connect(self, campaign_id: UUID, websocket: WebSocket, user_id: UUID, display_name: str, username: str):
        """Accept WebSocket connection and add to campaign room."""
        await websocket.accept()

        if campaign_id not in self.active_connections:
            self.active_connections[campaign_id] = []

        self.active_connections[campaign_id].append((websocket, user_id, display_name, username))
        logger.info(f"User {display_name} ({user_id}) connected to campaign {campaign_id}")
        
        # Broadcast system notification
        await self.broadcast(campaign_id, SystemNotification(
            event="player_joined",
            message=f"{display_name} joined the campaign"
        ).model_dump(mode='json'))
    
    def disconnect(self, campaign_id: UUID, websocket: WebSocket):
        """Remove WebSocket connection from campaign room."""
        if campaign_id in self.active_connections:
            # Find and remove this connection
            for conn in self.active_connections[campaign_id]:
                if conn[0] == websocket:
                    display_name = conn[2]  # Character name or username
                    self.active_connections[campaign_id].remove(conn)
                    logger.info(f"User {display_name} disconnected from campaign {campaign_id}")

                    # Clean up empty campaign rooms
                    if not self.active_connections[campaign_id]:
                        del self.active_connections[campaign_id]

                    return display_name
        return None
    
    async def broadcast(self, campaign_id: UUID, message: dict):
        """Send message to all connections in a campaign."""
        if campaign_id not in self.active_connections:
            return

        disconnected = []
        for websocket, user_id, display_name, username in self.active_connections[campaign_id]:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to {display_name}: {e}")
                disconnected.append((websocket, user_id, display_name, username))

        # Clean up dead connections
        for conn in disconnected:
            if conn in self.active_connections[campaign_id]:
                self.active_connections[campaign_id].remove(conn)
    
    async def send_to_user(self, campaign_id: UUID, target_user_id: UUID, message: dict):
        """Send message to a specific user in a campaign (for whispers)."""
        if campaign_id not in self.active_connections:
            return False

        for websocket, user_id, display_name, username in self.active_connections[campaign_id]:
            if user_id == target_user_id:
                try:
                    await websocket.send_json(message)
                    return True
                except Exception as e:
                    logger.warning(f"Failed to whisper to {display_name}: {e}")
                    return False

        return False
    
    def get_connected_users(self, campaign_id: UUID) -> List[tuple[UUID, str]]:
        """Get list of (user_id, display_name) for all connected users."""
        if campaign_id not in self.active_connections:
            return []
        return [(user_id, display_name) for _, user_id, display_name, _ in self.active_connections[campaign_id]]

    def get_display_name(self, campaign_id: UUID, user_id: UUID) -> str:
        """Get display name (character name or username) for a specific user."""
        if campaign_id not in self.active_connections:
            return "Unknown"

        for _, uid, display_name, _ in self.active_connections[campaign_id]:
            if uid == user_id:
                return display_name

        return "Unknown"

    def get_username(self, campaign_id: UUID, user_id: UUID) -> str:
        """Get username for a specific user."""
        if campaign_id not in self.active_connections:
            return "Unknown"

        for _, uid, _, username in self.active_connections[campaign_id]:
            if uid == user_id:
                return username

        return "Unknown"


# Global connection manager instance
manager = CampaignConnectionManager()


# ============================================================================
# WEBSOCKET ENDPOINT (Main campaign chat room)
# ============================================================================

@router.websocket("/ws/{campaign_id}")
async def campaign_websocket(
    websocket: WebSocket,
    campaign_id: UUID,
    token: str = Query(...),  # JWT token passed as query param
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for campaign chat room.

    URL: ws://localhost:8000/api/campaign/ws/{campaign_id}?token={jwt_token}

    Requires JWT authentication. Verifies user is a member of the campaign.

    Handles all campaign communication:
    - Player chat (IC/OOC)
    - Whispers
    - Combat commands
    - GM narration
    - Dice rolls
    - System notifications
    """
    # ===== JWT AUTHENTICATION (BEFORE accepting WebSocket) =====
    try:
        # Decode and verify JWT token
        payload = decode_access_token(token)
        if not payload:
            await websocket.close(code=1008, reason="Invalid or expired token")
            return

        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=1008, reason="Invalid token payload")
            return

        # Get user from database
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            await websocket.close(code=1008, reason="User not found")
            return

        # Verify user is a member of this campaign
        membership = db.query(CampaignMembership).filter(
            CampaignMembership.campaign_id == campaign_id,
            CampaignMembership.user_id == user.id,
            CampaignMembership.left_at.is_(None)  # Still active member
        ).first()

        if not membership:
            await websocket.close(code=1008, reason="You are not a member of this campaign")
            return

        # Authentication successful - extract user info
        user_uuid = user.id

        # Look up character name for this campaign (if they have one)
        # Story Weavers don't have characters, so they use username
        character = db.query(Character).filter(
            Character.user_id == user.id,
            Character.campaign_id == campaign_id
        ).first()

        display_name = character.name if character else user.username

    except Exception as e:
        logger.error(f"WebSocket authentication error: {e}")
        await websocket.close(code=1011, reason="Authentication failed")
        return

    # ===== AUTHENTICATION PASSED - Continue with existing logic =====
    campaign_uuid = campaign_id

    await manager.connect(campaign_uuid, websocket, user_uuid, display_name, user.username)

    # Send welcome message directly to the connecting user with in_calling state
    try:
        welcome_payload = {
            "type": "welcome",
            "character_name": display_name,
            "role": "SW" if not character else "player",
        }
        if character:
            welcome_payload["character_id"] = str(character.id)
            welcome_payload["character_status"] = character.status
            welcome_payload["in_calling"] = character.in_calling or False
            welcome_payload["times_called"] = character.times_called or 0
            welcome_payload["character_ip"] = character.ip or 0
            welcome_payload["character_sp"] = character.sp or 0
            welcome_payload["character_edge"] = character.edge or 0
            welcome_payload["character_dp"] = character.dp or 0
        await websocket.send_json(welcome_payload)
    except Exception:
        pass

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            message_type = data.get("type")

            # Route message based on type
            # Support both new format (type: 'chat') and old format (type: 'message' with chat_mode)
            if message_type == "message":
                # Old party chat format - route based on chat_mode
                await handle_legacy_message(campaign_uuid, data, user_uuid, display_name, db)

            elif message_type == "chat":
                await handle_chat(campaign_uuid, data, user_uuid)

            elif message_type == "whisper":
                await handle_whisper(campaign_uuid, data, user_uuid)

            elif message_type == "combat_command":
                await handle_combat_command(campaign_uuid, data, websocket, user_uuid, db)

            elif message_type == "ability_cast":
                await handle_ability_cast(campaign_uuid, data, websocket, user_uuid, db)

            elif message_type == "narration":
                await handle_narration(campaign_uuid, data)

            elif message_type == "dice_roll":
                await handle_dice_roll(campaign_uuid, data, user_uuid, db)  # Pass user_id from WebSocket

            elif message_type == "stat_check":
                await handle_stat_check(campaign_uuid, data, user_uuid, db)

            elif message_type == "initiative_command":
                await handle_initiative_command(campaign_uuid, data, websocket, user_uuid, db)

            elif message_type == "rest_command":
                await restore_all_abilities(campaign_uuid, user_uuid, db, websocket)

            elif message_type == "help_command":
                await send_help_text(websocket)

            else:
                logger.warning(f"Unknown message type: {message_type}")
    
    except WebSocketDisconnect:
        display_name = manager.disconnect(campaign_uuid, websocket)
        if display_name:
            await manager.broadcast(campaign_uuid, SystemNotification(
                event="player_left",
                message=f"{display_name} left the campaign"
            ).model_dump(mode='json'))


# ============================================================================
# MESSAGE HANDLERS (Business logic for each message type)
# ============================================================================

async def handle_legacy_message(campaign_id: UUID, data: dict, user_id: str, display_name: str, db: Session):
    """
    Handle legacy party chat format messages (type: 'message').

    Routes based on chat_mode, whisper_targets, and command detection.
    This maintains backward compatibility with the old ws-test.html format.
    Saves all messages to the database for history.
    """
    text = data.get("text", "")
    actor = data.get("actor", display_name)
    chat_mode = data.get("chat_mode", "ic")
    whisper_targets = data.get("whisper_targets", [])
    message_type = "chat"
    broadcast_type = "chat_ic"

    # Determine message type and broadcast type
    if text.startswith("/"):
        # Commands
        message_type = "system"
        broadcast_type = "system"
        broadcast_data = {
            "type": "system",
            "text": f"{actor}: {text}",
            "actor": actor,
            "timestamp": datetime.utcnow().isoformat()
        }
    elif whisper_targets and len(whisper_targets) > 0:
        # Whispers
        message_type = "chat"
        chat_mode = "whisper"
        broadcast_type = "chat_whisper"
        broadcast_data = {
            "type": "chat_whisper",
            "chat_mode": "whisper",
            "actor": actor,
            "text": text,
            "whisper_targets": whisper_targets,
            "timestamp": datetime.utcnow().isoformat()
        }
    else:
        # Regular chat (IC/OOC)
        broadcast_type = "chat_ooc" if chat_mode == "ooc" else "chat_ic"
        is_ooc_command = data.get("is_ooc_command", False)
        broadcast_data = {
            "type": broadcast_type,
            "chat_mode": chat_mode,
            "actor": actor,
            "text": text,
            "is_ooc_command": is_ooc_command,
            "timestamp": datetime.utcnow().isoformat()
        }

    # Save ALL messages to database
    try:
        message_record = Message(
            campaign_id=str(campaign_id),
            sender_id=user_id,
            sender_name=actor,
            message_type=message_type,
            mode=chat_mode.upper() if chat_mode else None,  # 'IC', 'OOC', 'WHISPER'
            content=text
        )
        db.add(message_record)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to save message to database: {e}")
        db.rollback()

    # Broadcast to all connected clients
    await manager.broadcast(campaign_id, broadcast_data)


async def handle_chat(campaign_id: UUID, data: dict, user_id: UUID):
    """Handle regular chat message (IC or OOC)."""
    msg = ChatMessage(**data)

    # Get display name and username from connection manager
    display_name = manager.get_display_name(campaign_id, user_id)  # Character name or username
    username = manager.get_username(campaign_id, user_id)

    # Format sender name based on mode
    if msg.mode.upper() == 'IC':
        # IC: Just character name (e.g., "Tanion")
        sender = display_name
    else:
        # OOC: Username - "Character name" (e.g., "JGerm - \"Tanion\"")
        # If display_name == username (Story Weaver with no character), just show username
        if display_name == username:
            sender = username
        else:
            sender = f'{username} - "{display_name}"'

    # Broadcast to everyone in campaign
    await manager.broadcast(campaign_id, ChatBroadcast(
        mode=msg.mode,
        sender=sender,
        user_id=msg.user_id,
        message=msg.message,
        attachment=msg.attachment
    ).model_dump(mode='json'))


async def handle_whisper(campaign_id: UUID, data: dict, user_id: UUID):
    """Handle private whisper message."""
    msg = WhisperMessage(**data)

    # Get display name from connection manager
    display_name = manager.get_display_name(campaign_id, user_id)

    # Send to recipient only
    success = await manager.send_to_user(campaign_id, msg.recipient_user_id, WhisperBroadcast(
        sender=display_name,  # Use character name from connection manager
        message=msg.message
    ).model_dump(mode='json'))
    
    if not success:
        logger.warning(f"Failed to deliver whisper from {msg.sender} to {msg.recipient_user_id}")


async def handle_combat_command(campaign_id: UUID, data: dict, websocket: WebSocket, user_id: UUID, db: Session):
    """
    Handle combat command (/attack @Target).

    Parses command, looks up characters, resolves combat, updates DB, broadcasts result.
    """
    request_id = "websocket"  # Could pass from main handler if you add request tracking

    try:
        # Parse command
        cmd = CombatCommand(**data)
        command_text = cmd.raw_command.strip()

        # Parse /attack @TargetName
        if not command_text.startswith("/attack"):
            await manager.broadcast(campaign_id, {
                "type": "system",
                "text": "❌ Unknown combat command. Use: /attack @TargetName"
            })
            return

        # Extract target name (supports both "@Name" and "Name")
        match = re.match(r'/attack\s+@?(.+)', command_text, re.IGNORECASE)
        if not match:
            await manager.broadcast(campaign_id, {
                "type": "system",
                "text": "❌ Invalid attack syntax. Use: /attack @TargetName"
            })
            return

        target_name = match.group(1).strip()

        # =====================================================================
        # Look up attacker (user's character in this campaign)
        # =====================================================================
        attacker = db.query(Character).filter(
            Character.user_id == user_id,
            Character.campaign_id == campaign_id
        ).first()

        if not attacker:
            await manager.broadcast(campaign_id, {
                "type": "system",
                "text": "❌ You don't have a character in this campaign"
            })
            return

        # Check if attacker is alive
        if attacker.dp <= 0:
            await manager.broadcast(campaign_id, {
                "type": "system",
                "text": f"❌ {attacker.name} is unconscious (DP: {attacker.dp})"
            })
            return

        # =====================================================================
        # Look up defender (by character name in this campaign)
        # =====================================================================
        defender = db.query(Character).filter(
            Character.campaign_id == campaign_id,
            Character.name.ilike(target_name)  # Case-insensitive match
        ).first()

        if not defender:
            await manager.broadcast(campaign_id, {
                "type": "system",
                "text": f"❌ Character '{target_name}' not found in this campaign"
            })
            return

        # Check if defender is alive
        if defender.dp <= 0:
            await manager.broadcast(campaign_id, {
                "type": "system",
                "text": f"❌ {defender.name} is already unconscious (DP: {defender.dp})"
            })
            return

        # Can't attack yourself
        if attacker.id == defender.id:
            await manager.broadcast(campaign_id, {
                "type": "system",
                "text": "❌ You can't attack yourself!"
            })
            return
        
        # =====================================================================
        # Resolve combat (reuse logic from combat_fastapi.py)
        # =====================================================================
        from backend.roll_logic import resolve_multi_die_attack
        
        # Use Physical for basic attacks (default)
        stat_type = "pp"
        attacker_stat_value = attacker.pp
        defender_stat_value = defender.pp
        
        # Get weapon bonus
        weapon_bonus = 0
        if attacker.weapon and isinstance(attacker.weapon, dict):
            weapon_bonus = attacker.weapon.get("bonus_damage", 0)
        
        # Resolve multi-die attack
        result = resolve_multi_die_attack(
            attacker={"name": attacker.name},
            attacker_die_str=attacker.attack_style,
            attacker_stat_value=attacker_stat_value,
            defender={"name": defender.name},
            defense_die_str=defender.defense_die,
            defender_stat_value=defender_stat_value,
            edge=attacker.edge,
            bap_triggered=False,  # TODO: Add BAP detection later
            weapon_bonus=weapon_bonus
        )
        
        # =====================================================================
        # Apply damage and persist to database (no floor — can go negative for The Calling)
        # =====================================================================
        old_dp = defender.dp
        defender.dp = defender.dp - result["total_damage"]
        db.commit()
        
        logger.info(
            f"[{request_id}] {attacker.name} dealt {result['total_damage']} damage "
            f"to {defender.name} (DP: {old_dp} → {defender.dp}) [PERSISTED]"
        )
        
        # =====================================================================
        # Persist combat result to database (save first to get message_id)
        # =====================================================================
        combat_message = Message(
            campaign_id=str(campaign_id),
            party_id=None,  # Combat visible to all tabs
            sender_id=str(user_id),
            sender_name=attacker.name,
            content=f"{attacker.name} attacks {defender.name} - {result['total_damage']} damage",
            message_type="combat_result",
            extra_data={
                "attacker": attacker.name,
                "attacker_id": str(attacker.id),
                "defender": defender.name,
                "defender_id": str(defender.id),
                "technique": "Attack",
                "damage": result["total_damage"],
                "defender_new_dp": defender.dp,
                "narrative": result["narrative"],
                "individual_rolls": result["individual_rolls"],
                "outcome": result["outcome"]
            }
        )
        db.add(combat_message)
        db.commit()
        db.refresh(combat_message)

        # =====================================================================
        # Broadcast combat result to all players (with message_id for BAP)
        # =====================================================================
        combat_broadcast = CombatResultBroadcast(
            attacker=attacker.name,
            defender=defender.name,
            technique="Attack",  # Default technique name
            damage=result["total_damage"],
            defender_new_dp=defender.dp,
            narrative=result["narrative"],
            individual_rolls=result["individual_rolls"],
            outcome=result["outcome"],
            message_id=str(combat_message.id),
            attacker_id=str(attacker.id),
            defender_id=str(defender.id)
        )
        await manager.broadcast(campaign_id, combat_broadcast.model_dump(mode='json'))

        # =====================================================================
        # Check for knockout / The Calling
        # =====================================================================
        if defender.dp <= 0:
            if defender.dp <= -10 and not defender.is_npc and not defender.in_calling:
                if (defender.times_called or 0) >= 4:
                    # 5th Calling — no roll, instant permadeath
                    defender.status = 'archived'
                    defender.times_called = (defender.times_called or 0) + 1
                    db.commit()
                    await manager.broadcast(campaign_id, {
                        "type": "permadeath",
                        "character_id": str(defender.id),
                        "character_name": defender.name,
                        "times_called": defender.times_called
                    })
                    await manager.broadcast(campaign_id, {
                        "type": "character_archived",
                        "character_id": str(defender.id),
                        "character_name": defender.name
                    })
                else:
                    # The Calling triggered!
                    defender.in_calling = True
                    calling_msg = Message(
                        campaign_id=campaign_id,
                        party_id=None,
                        sender_id=user_id,
                        sender_name="System",
                        message_type="calling_triggered",
                        content=f"{defender.name} has entered The Calling!",
                        extra_data={
                            "character_id": str(defender.id),
                            "defender": defender.name,
                            "defender_new_dp": defender.dp,
                            "defender_ip": defender.ip,
                            "defender_sp": defender.sp,
                            "defender_edge": defender.edge or 0,
                            "defender_times_called": defender.times_called or 0
                        }
                    )
                    db.add(calling_msg)
                    db.commit()
                    await manager.broadcast(campaign_id, {
                        "type": "calling_triggered",
                        "character_id": str(defender.id),
                        "defender": defender.name,
                        "defender_new_dp": defender.dp,
                        "defender_ip": defender.ip,
                        "defender_sp": defender.sp,
                        "defender_edge": defender.edge or 0,
                        "defender_times_called": defender.times_called or 0
                    })
            elif defender.dp <= 0:
                # Just knocked out
                await manager.broadcast(campaign_id, {
                    "type": "system",
                    "text": f"💥 {defender.name} is knocked out! (DP: {defender.dp})"
                })

    except Exception as e:
        logger.error(f"Combat command error: {str(e)}", exc_info=True)
        await manager.broadcast(campaign_id, {
            "type": "system",
            "text": f"❌ Combat error: {str(e)}"
        })



def _dice_str(die_type: str, rolls: list) -> str:
    """Format dice rolls as e.g. '2d6(3+5)'"""
    inner = "+".join(str(r) for r in rolls)
    return f"{die_type}({inner})"


async def handle_ability_cast(campaign_id: UUID, data: dict, websocket: WebSocket, user_id: UUID, db: Session):
    """
    Handle custom ability/spell/technique casting.

    Supports:
    - Single target damage/heal
    - AOE damage/heal (multiple targets)
    - Buffs (self or target)
    - Debuffs (contested roll)

    Usage tracking: 3 uses per encounter per character level
    """
    request_id = "ability_cast"

    try:
        # Parse command
        cmd = AbilityCastCommand(**data)
        command_text = cmd.raw_command.strip()

        # Extract macro and targets (e.g., "/heal @Target" or "/fireball @E1 @E2")
        parts = command_text.split()
        if not parts or not parts[0].startswith("/"):
            await manager.broadcast(campaign_id, {
                "type": "system",
                "text": "❌ Invalid ability command format. Use: /ability @Target"
            })
            return

        macro_command = parts[0].lower()  # e.g., "/heal"
        target_names = [p.lstrip("@") for p in parts[1:] if p.startswith("@")]

        # Get caster's character (PC lookup by user_id, or NPC lookup by speaker_id)
        if cmd.speaker_id and cmd.speaker_type == 'npc':
            caster = db.query(Character).filter(
                Character.id == cmd.speaker_id
            ).first()
        else:
            caster = db.query(Character).filter(
                Character.user_id == str(user_id)
            ).first()

        if not caster:
            await manager.broadcast(campaign_id, {
                "type": "system",
                "text": "❌ You need a character to cast abilities"
            })
            return

        # Look up ability
        ability = db.query(Ability).filter(
            Ability.character_id == caster.id,
            Ability.macro_command == macro_command
        ).first()

        if not ability:
            await manager.broadcast(campaign_id, {
                "type": "system",
                "text": f"❌ Ability '{macro_command}' not found for {caster.name}"
            })
            return

        # Check uses remaining
        if ability.uses_remaining <= 0:
            await manager.broadcast(campaign_id, {
                "type": "system",
                "text": f"❌ {ability.display_name} has no uses remaining! ({ability.uses_remaining}/{ability.max_uses})"
            })
            return

        # Get caster's power stat (PP, IP, or SP)
        power_stat = 0
        if ability.power_source == "PP":
            power_stat = caster.pp
        elif ability.power_source == "IP":
            power_stat = caster.ip
        elif ability.power_source == "SP":
            power_stat = caster.sp

        # Execute based on effect type
        results = []
        narrative_parts = []
        calling_char_id = None  # set if any target triggers The Calling

        if ability.effect_type == "damage":
            # Damage ability (single target or AOE)
            if not target_names:
                await manager.broadcast(campaign_id, {
                    "type": "system",
                    "text": f"❌ {ability.display_name} requires at least one target. Use: {macro_command} @Target"
                })
                return

            for target_name in target_names:
                # Find target character
                target = db.query(Character).filter(
                    Character.name == target_name,
                    Character.campaign_id == str(campaign_id)
                ).first()

                if not target:
                    results.append({
                        "target": target_name,
                        "success": False,
                        "message": "Target not found"
                    })
                    continue

                # Roll attack: ability die + power stat + edge
                attack_dice = ability.die  # e.g., "2d6"
                attack_roll_result = roll_dice(attack_dice)  # Returns list like [3, 5]
                attack_total = sum(attack_roll_result) + power_stat + caster.edge

                # Roll defense: target's defense die + PP + Edge (matches spell_cast formula)
                defense_roll_result = roll_dice(target.defense_die)  # Returns list
                target_edge = target.edge or 0
                defense_total = sum(defense_roll_result) + target.pp + target_edge

                # Calculate damage
                margin = attack_total - defense_total
                damage = max(0, margin)

                # Apply damage (no floor — can go negative for The Calling)
                old_dp = target.dp
                target.dp = target.dp - damage

                # Check for The Calling at -10 DP (PCs only)
                calling_triggered = False
                permadeath_triggered = False
                if target.dp <= -10 and not target.is_npc and not target.in_calling:
                    if (target.times_called or 0) >= 4:
                        # 5th Calling — instant permadeath
                        target.status = 'archived'
                        target.times_called = (target.times_called or 0) + 1
                        permadeath_triggered = True
                    else:
                        target.in_calling = True
                        calling_triggered = True

                db.commit()

                outcome = "hit" if damage > 0 else "miss"
                atk_rolls_str = " + ".join(str(r) for r in attack_roll_result)
                def_rolls_str = " + ".join(str(r) for r in defense_roll_result)
                atk_breakdown = f"{ability.die} = [{atk_rolls_str}] + {ability.power_source}({power_stat}) + Edge({caster.edge}) = {attack_total}"
                def_breakdown = f"{target.defense_die} = [{def_rolls_str}] + PP({target.pp}) + Edge({target_edge}) = {defense_total}"
                results.append({
                    "target": target_name,
                    "success": True,
                    "damage": damage,
                    "old_dp": old_dp,
                    "new_dp": target.dp,
                    "attack_roll": attack_total,
                    "attack_breakdown": atk_breakdown,
                    "defense_roll": defense_total,
                    "defense_breakdown": def_breakdown,
                    "margin": margin,
                    "outcome": outcome,
                    "calling_triggered": calling_triggered
                })

                if calling_triggered:
                    calling_char_id = str(target.id)
                    calling_char_name = target.name
                    calling_char_ip = target.ip
                    calling_char_sp = target.sp
                    calling_char_edge = target.edge or 0
                    calling_char_times = target.times_called or 0
                    calling_char_dp = target.dp

                if permadeath_triggered:
                    # 5th Calling via ability — broadcast permadeath immediately
                    await manager.broadcast(campaign_id, {
                        "type": "permadeath",
                        "character_id": str(target.id),
                        "character_name": target.name,
                        "times_called": target.times_called
                    })
                    await manager.broadcast(campaign_id, {
                        "type": "character_archived",
                        "character_id": str(target.id),
                        "character_name": target.name
                    })

                if damage > 0:
                    narrative_parts.append(f"{target_name} takes {damage} damage (DP: {old_dp} → {target.dp})")
                else:
                    narrative_parts.append(f"{target_name} dodges the attack!")

        elif ability.effect_type == "heal":
            # Healing ability (single target or AOE)
            # If no targets specified, heal self
            if not target_names:
                target_names = [caster.name]

            for target_name in target_names:
                # Find target character
                target = db.query(Character).filter(
                    Character.name == target_name,
                    Character.campaign_id == str(campaign_id)
                ).first()

                if not target:
                    results.append({
                        "target": target_name,
                        "success": False,
                        "message": "Target not found"
                    })
                    continue

                # Roll healing: ability die + power stat
                heal_roll_result = roll_dice(ability.die)  # Returns list
                heal_roll_total = sum(heal_roll_result)
                healing = heal_roll_total + power_stat

                # Apply healing
                old_dp = target.dp
                target.dp = min(target.max_dp, target.dp + healing)
                actual_healing = target.dp - old_dp
                db.commit()

                heal_rolls_str = " + ".join(str(r) for r in heal_roll_result)
                heal_breakdown = f"{ability.die} = [{heal_rolls_str}] + {ability.power_source}({power_stat}) = {healing}"
                results.append({
                    "target": target_name,
                    "success": True,
                    "healing": actual_healing,
                    "old_dp": old_dp,
                    "new_dp": target.dp,
                    "roll_breakdown": heal_breakdown
                })

                narrative_parts.append(f"{target_name} restores {actual_healing} DP (DP: {old_dp} → {target.dp})")

        elif ability.effect_type == "buff":
            # Buff ability (self or target)
            # If no target, buff self
            if not target_names:
                target_names = [caster.name]

            # Roll for buff strength/duration
            buff_roll = roll_dice(ability.die)  # Returns list
            buff_roll_total = sum(buff_roll)
            buff_value = buff_roll_total + power_stat

            buff_rolls_str = " + ".join(str(r) for r in buff_roll)
            buff_breakdown = f"{ability.die} = [{buff_rolls_str}] + {ability.power_source}({power_stat}) = {buff_value}"
            for target_name in target_names:
                results.append({
                    "target": target_name,
                    "success": True,
                    "buff_value": buff_value,
                    "roll_breakdown": buff_breakdown
                })
                narrative_parts.append(f"{target_name} receives {ability.display_name}! (Power: {buff_value})")

        elif ability.effect_type == "debuff":
            # Debuff ability (contested roll required)
            if not target_names:
                await manager.broadcast(campaign_id, {
                    "type": "system",
                    "text": f"❌ {ability.display_name} requires a target. Use: {macro_command} @Target"
                })
                return

            for target_name in target_names:
                # Find target
                target = db.query(Character).filter(
                    Character.name == target_name,
                    Character.campaign_id == str(campaign_id)
                ).first()

                if not target:
                    results.append({
                        "target": target_name,
                        "success": False,
                        "message": "Target not found"
                    })
                    continue

                # Contested roll: caster's ability vs target's defense (matches spell_cast formula)
                caster_roll = roll_dice(ability.die)  # Returns list
                caster_total = sum(caster_roll) + power_stat + caster.edge

                defense_roll = roll_dice(target.defense_die)  # Returns list
                target_edge = target.edge or 0
                defense_total = sum(defense_roll) + target.pp + target_edge

                margin = caster_total - defense_total
                success = margin > 0

                cast_rolls_str = " + ".join(str(r) for r in caster_roll)
                def_rolls_str = " + ".join(str(r) for r in defense_roll)
                atk_breakdown = f"{ability.die} = [{cast_rolls_str}] + {ability.power_source}({power_stat}) + Edge({caster.edge}) = {caster_total}"
                def_breakdown = f"{target.defense_die} = [{def_rolls_str}] + PP({target.pp}) + Edge({target_edge}) = {defense_total}"
                results.append({
                    "target": target_name,
                    "success": success,
                    "caster_roll": caster_total,
                    "defense_roll": defense_total,
                    "attack_breakdown": atk_breakdown,
                    "defense_breakdown": def_breakdown,
                    "margin": margin,
                    "debuff_strength": max(0, margin)
                })

                if success:
                    narrative_parts.append(f"{target_name} is afflicted by {ability.display_name}! (Strength: {margin})")
                else:
                    narrative_parts.append(f"{target_name} resists {ability.display_name}!")

        # Decrement uses only if at least one target was actually found (not a typo/miss-target)
        all_targets_missing = results and all(r.get("message") == "Target not found" for r in results)
        if not all_targets_missing:
            ability.uses_remaining -= 1
        db.commit()

        # Generate narrative (header already shows caster + ability, so just show outcomes)
        narrative = " ".join(narrative_parts)

        # Broadcast result
        broadcast = AbilityCastBroadcast(
            caster=caster.name,
            ability_name=ability.display_name,
            ability_die=ability.die,
            power_source=ability.power_source,
            effect_type=ability.effect_type,
            targets=target_names,
            results=results,
            narrative=narrative,
            uses_remaining=ability.uses_remaining,
            max_uses=ability.max_uses
        )
        await manager.broadcast(campaign_id, broadcast.model_dump(mode='json'))

        # If any target triggered The Calling, save and broadcast it now
        if calling_char_id:
            calling_msg = Message(
                campaign_id=campaign_id,
                party_id=None,
                sender_id=user_id,
                sender_name="System",
                message_type="calling_triggered",
                content=f"{calling_char_name} has entered The Calling!",
                extra_data={
                    "character_id": calling_char_id,
                    "defender": calling_char_name,
                    "defender_new_dp": calling_char_dp,
                    "defender_ip": calling_char_ip,
                    "defender_sp": calling_char_sp,
                    "defender_edge": calling_char_edge,
                    "defender_times_called": calling_char_times
                }
            )
            db.add(calling_msg)
            db.commit()
            await manager.broadcast(campaign_id, {
                "type": "calling_triggered",
                "character_id": calling_char_id,
                "defender": calling_char_name,
                "defender_new_dp": calling_char_dp,
                "defender_ip": calling_char_ip,
                "defender_sp": calling_char_sp,
                "defender_edge": calling_char_edge,
                "defender_times_called": calling_char_times
            })

        # Persist to database
        ability_message = Message(
            campaign_id=str(campaign_id),
            party_id=None,  # Visible to all tabs
            sender_id=str(user_id),
            sender_name=caster.name,
            content=f"{caster.name} casts {ability.display_name}",
            message_type="ability_cast",
            extra_data={
                "caster": caster.name,
                "ability_name": ability.display_name,
                "ability_die": ability.die,
                "power_source": ability.power_source,
                "effect_type": ability.effect_type,
                "targets": target_names,
                "results": results,
                "narrative": narrative,
                "uses_remaining": ability.uses_remaining,
                "max_uses": ability.max_uses
            }
        )
        db.add(ability_message)
        db.commit()

        logger.info(f"[{request_id}] {caster.name} cast {ability.display_name} ({ability.uses_remaining}/{ability.max_uses} uses left)")

    except Exception as e:
        logger.error(f"Ability cast error: {str(e)}", exc_info=True)
        await manager.broadcast(campaign_id, {
            "type": "system",
            "text": f"❌ Ability cast error: {str(e)}"
        })


async def handle_narration(campaign_id: UUID, data: dict):
    """Handle GM narration."""
    narration = GMNarration(**data)
    
    # Broadcast to everyone
    await manager.broadcast(campaign_id, NarrationBroadcast(
        text=narration.text,
        attachment=narration.attachment
    ).model_dump(mode='json'))


async def handle_dice_roll(campaign_id: UUID, data: dict, user_id: UUID, db: Session):
    """Handle dice roll requests with error handling for invalid notation."""
    display_name = manager.get_display_name(campaign_id, user_id)
    dice_notation = data.get("dice", "1d6")
    reason = data.get("reason", "")
    
    # ✅ Use roll_dice for breakdown, sum for total
    try:
        breakdown = roll_dice(dice_notation)  # [3, 5] 
        total = sum(breakdown)  # 8
    except ValueError as e:
        # Invalid dice notation - send error message
        error_msg = f"❌ Invalid dice notation '{dice_notation}'. Use format like 2d6, 3d4, 1d12."
        await manager.broadcast(campaign_id, {
            "type": "system",
            "text": error_msg
        })
        return  # Stop processing
    
    # Format the result text
    result_text = f"rolled {total}"
    
    # Build broadcast message
    broadcast_data = DiceRollBroadcast(
        actor=display_name,
        dice=dice_notation,
        result=total,
        breakdown=breakdown,
        text=result_text,
        reason=reason
    )
    
    # ✅ PERSIST TO DATABASE with extra_data
    message_record = Message(
        campaign_id=str(campaign_id),
        party_id=None,  # Dice rolls visible to all tabs for now
        sender_id=str(user_id),
        sender_name=display_name,
        content=f"{result_text} ({dice_notation})",  # Include dice notation in content
        message_type="dice_roll_result",
        extra_data={
            "breakdown": breakdown,  # [3, 5, 2]
            "dice_notation": dice_notation,  # "3d6"
            "total": total,  # 10
            "reason": reason  # Optional reason for the roll
        }
    )
    db.add(message_record)
    db.commit()
    
    # Broadcast to all clients
    await manager.broadcast(campaign_id, broadcast_data.model_dump(mode='json'))


async def handle_stat_check(campaign_id: UUID, data: dict, user_id: UUID, db: Session):
    """
    Handle stat check macros (/pp, /ip, /sp).

    Rolls 1d6 + stat value + edge, shows full breakdown.
    Formula: 1d6 + PP/IP/SP + Edge = Total
    """
    display_name = manager.get_display_name(campaign_id, user_id)
    stat_type = data.get("stat", "PP").upper()  # "PP", "IP", or "SP"

    # Get character
    character = db.query(Character).filter(
        Character.user_id == str(user_id)
    ).first()

    if not character:
        await manager.broadcast(campaign_id, {
            "type": "system",
            "text": f"❌ {display_name} needs a character to perform stat checks"
        })
        return

    # Get stat value
    stat_value = 0
    if stat_type == "PP":
        stat_value = character.pp
        stat_name = "Physical"
    elif stat_type == "IP":
        stat_value = character.ip
        stat_name = "Intellect"
    elif stat_type == "SP":
        stat_value = character.sp
        stat_name = "Social"
    else:
        await manager.broadcast(campaign_id, {
            "type": "system",
            "text": f"❌ Invalid stat type: {stat_type}. Use PP, IP, or SP."
        })
        return

    # Roll 1d6 (returns list of rolls, e.g., [4])
    roll_result = roll_dice("1d6")
    die_roll = sum(roll_result)  # Sum the list to get the roll value

    # Calculate total: 1d6 + stat + edge
    edge = character.edge
    total = die_roll + stat_value + edge

    # Build breakdown text showing the math
    breakdown_text = f"1d6({die_roll}) + {stat_type}({stat_value}) + Edge({edge}) = {total}"
    result_text = f"{stat_name} Check: {total}"

    # Broadcast with detailed breakdown
    broadcast_data = {
        "type": "stat_roll",
        "actor": character.name,
        "stat": stat_type,
        "stat_name": stat_name,
        "die_roll": die_roll,
        "stat_value": stat_value,
        "edge": edge,
        "total": total,
        "text": result_text,
        "breakdown": breakdown_text
    }

    # Persist to database
    message_record = Message(
        campaign_id=str(campaign_id),
        party_id=None,  # Visible to all tabs
        sender_id=str(user_id),
        sender_name=character.name,
        content=f"{stat_name} Check: {total}",
        message_type="stat_roll",
        extra_data={
            "stat": stat_type,
            "stat_name": stat_name,
            "die_roll": die_roll,
            "stat_value": stat_value,
            "edge": edge,
            "total": total,
            "breakdown": breakdown_text
        }
    )
    db.add(message_record)
    db.commit()

    # Broadcast result
    await manager.broadcast(campaign_id, broadcast_data)
    logger.info(f"[stat_check] {character.name} {stat_type} check: {total} ({breakdown_text})")


# ============================================================================
# BROADCAST HELPER (Called from combat_fastapi.py)
# ============================================================================

async def broadcast_combat_result(campaign_id: UUID, combat_result: dict):
    """
    Broadcast combat result to all players in campaign.
    
    Called from combat_fastapi.py after attack-by-id resolves.
    """
    await manager.broadcast(campaign_id, CombatResultBroadcast(
        attacker=combat_result["attacker_name"],
        defender=combat_result["defender_name"],
        technique=combat_result.get("technique", "Slash"),
        damage=combat_result["total_damage"],
        defender_new_dp=combat_result["defender_new_dp"],
        narrative=combat_result["narrative"],
        individual_rolls=combat_result["individual_rolls"],
        outcome=combat_result["outcome"]
    ).model_dump(mode='json'))


async def broadcast_initiative(campaign_id: UUID, initiative_result: dict):
    """
    Broadcast initiative order to all players.

    Called when combat starts.
    """
    await manager.broadcast(campaign_id, InitiativeResultBroadcast(
        order=initiative_result["initiative_order"],
        rolls=[r.model_dump(mode='json') for r in initiative_result["rolls"]]
    ).model_dump(mode='json'))


async def broadcast_character_approved(campaign_id: UUID, character_id: str, character_name: str):
    """
    Notify all campaign members that a character has been approved.
    The player whose character was approved will auto-reload into the game.
    Called from character_fastapi.py after approval.
    """
    await manager.broadcast(campaign_id, {
        "type": "character_approved",
        "character_id": character_id,
        "character_name": character_name
    })


async def broadcast_pc_converted_to_npc(campaign_id: UUID, character_id: str, character_name: str):
    """
    Notify all campaign members that a PC was converted to an NPC.
    The SW's bubble bar will refresh to show the new NPC.
    Called from character_fastapi.py after PC→NPC conversion.
    """
    await manager.broadcast(campaign_id, {
        "type": "pc_converted_to_npc",
        "character_id": character_id,
        "character_name": character_name
    })


async def broadcast_pc_transferred(campaign_id: UUID, character_id: str, character_name: str, new_owner_id: str):
    """
    Notify all campaign members that a PC was transferred to another player.
    The original owner is dropped to spectator; the new owner gains the character.
    """
    await manager.broadcast(campaign_id, {
        "type": "pc_transferred",
        "character_id": character_id,
        "character_name": character_name,
        "new_owner_id": new_owner_id
    })


async def broadcast_character_created(campaign_id: UUID, character_id: str, character_name: str, owner_username: str, status: str):
    """
    Notify all campaign members that a new character was submitted.
    SW gets a toast + party panel refresh; other players are unaffected.
    """
    await manager.broadcast(campaign_id, {
        "type": "character_created",
        "character_id": character_id,
        "character_name": character_name,
        "owner_username": owner_username,
        "status": status
    })


async def broadcast_character_rejected(campaign_id: UUID, character_id: str, character_name: str, owner_id: str, reason: str):
    """
    Notify all campaign members that a character was rejected.
    Only the owning player acts on this (shows rejection toast).
    """
    await manager.broadcast(campaign_id, {
        "type": "character_rejected",
        "character_id": character_id,
        "character_name": character_name,
        "owner_id": owner_id,
        "reason": reason
    })


async def broadcast_player_joined(campaign_id: UUID, username: str):
    """
    Notify all campaign members that a new player joined.
    SW gets a toast + party panel refresh.
    """
    await manager.broadcast(campaign_id, {
        "type": "player_joined_campaign",
        "username": username
    })


async def broadcast_level_up(campaign_id: UUID, character_id: str, character_name: str, old_level: int, new_level: int, new_slot_unlocked: bool):
    """
    Notify all campaign members that a character leveled up.
    Triggers party panel refresh and celebration message in chat.
    """
    await manager.broadcast(campaign_id, {
        "type": "character_leveled_up",
        "character_id": character_id,
        "character_name": character_name,
        "old_level": old_level,
        "new_level": new_level,
        "new_slot_unlocked": new_slot_unlocked
    })


async def broadcast_bap_granted(campaign_id: UUID, character_id: str, character_name: str, owner_id: str, token_type: str):
    """SW granted a BAP token to a character. All clients update the party panel."""
    await manager.broadcast(campaign_id, {
        "type": "bap_granted",
        "character_id": character_id,
        "character_name": character_name,
        "owner_id": owner_id,
        "token_type": token_type
    })


async def broadcast_bap_revoked(campaign_id: UUID, character_id: str, character_name: str, owner_id: str):
    """SW revoked a BAP token. All clients update the party panel."""
    await manager.broadcast(campaign_id, {
        "type": "bap_revoked",
        "character_id": character_id,
        "character_name": character_name,
        "owner_id": owner_id
    })


async def broadcast_bap_retroactive(campaign_id: UUID, character_id: str, character_name: str, message_id: str, bap_bonus: int):
    """SW awarded retroactive BAP on a specific combat roll. Clients update that card."""
    await manager.broadcast(campaign_id, {
        "type": "bap_retroactive",
        "character_id": character_id,
        "character_name": character_name,
        "message_id": message_id,
        "bap_bonus": bap_bonus
    })


# ============================================================================
# INITIATIVE & ENCOUNTER SYSTEM
# ============================================================================

async def is_story_weaver(campaign_uuid: UUID, user_uuid: UUID, db: Session) -> bool:
    """Check if user is the Story Weaver for this campaign."""
    # Check if user has Story Weaver role in campaign membership
    membership = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == campaign_uuid,
        CampaignMembership.user_id == user_uuid
    ).first()

    if not membership:
        return False

    # Check if their role is story_weaver
    return membership.role == 'story_weaver'


async def get_or_create_active_encounter(campaign_uuid: UUID, db: Session) -> Encounter:
    """Get the active encounter for a campaign, or create one if none exists."""
    encounter = db.query(Encounter).filter(
        Encounter.campaign_id == campaign_uuid,
        Encounter.is_active == True
    ).first()

    if not encounter:
        encounter = Encounter(
            campaign_id=campaign_uuid,
            is_active=True,
            started_at=datetime.now()
        )
        db.add(encounter)
        db.commit()
        db.refresh(encounter)

    return encounter


async def roll_initiative_self(
    campaign_uuid: UUID,
    user_uuid: UUID,
    db: Session,
    websocket: WebSocket
):
    """
    Player rolls initiative for themselves.
    Command: /initiative
    """
    try:
        # Get user's character in this campaign
        character = db.query(Character).filter(
            Character.campaign_id == campaign_uuid,
            Character.user_id == user_uuid
        ).first()

        if not character:
            await websocket.send_json({
                "type": "error",
                "message": "Character not found"
            })
            return

        # Get or create active encounter
        encounter = await get_or_create_active_encounter(campaign_uuid, db)

        # Check if character already rolled initiative
        existing = db.query(InitiativeRoll).filter(
            InitiativeRoll.encounter_id == encounter.id,
            InitiativeRoll.character_id == character.id
        ).first()

        if existing:
            await websocket.send_json({
                "type": "error",
                "message": f"You already rolled initiative this encounter ({existing.roll_result})"
            })
            return

        # Roll 1d6 + Edge (TBA v1.5)
        die_result = roll_dice("1d6")[0]
        roll_total = die_result + character.edge

        # Create initiative roll
        initiative_roll = InitiativeRoll(
            encounter_id=encounter.id,
            character_id=character.id,
            name=character.name,
            roll_result=roll_total,
            is_silent=False,
            rolled_by_sw=False
        )
        db.add(initiative_roll)
        db.commit()

        # Broadcast to all players
        await manager.broadcast(campaign_uuid, {
            "type": "initiative_roll",
            "actor": character.name,
            "roll": roll_total,
            "is_silent": False,
            "timestamp": datetime.now().isoformat()
        })

        # Persist message
        msg = Message(
            campaign_id=campaign_uuid,
            party_id=None,  # Initiative is campaign-wide
            sender_id=character.id,
            sender_name=character.name,
            message_type="initiative_roll",
            content=f"{character.name} rolled {roll_total} for initiative",
            extra_data={
                "actor": character.name,
                "roll": roll_total,
                "is_silent": False
            }
        )
        db.add(msg)
        db.commit()

    except Exception as e:
        logger.error(f"Initiative self-roll error: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Initiative roll failed: {str(e)}"
        })


async def roll_initiative_target(
    campaign_uuid: UUID,
    user_uuid: UUID,
    target_name: str,
    is_silent: bool,
    db: Session,
    websocket: WebSocket
):
    """
    Story Weaver rolls initiative for a target (PC or NPC).
    Commands: /initiative @Target, /initiative silent @Target
    """
    try:
        # Verify user is Story Weaver
        if not await is_story_weaver(campaign_uuid, user_uuid, db):
            await websocket.send_json({
                "type": "error",
                "message": "Only the Story Weaver can roll initiative for others"
            })
            return

        # Get or create active encounter
        encounter = await get_or_create_active_encounter(campaign_uuid, db)

        # Try to find target as character
        character = db.query(Character).filter(
            Character.name.ilike(f"%{target_name}%")
        ).first()

        npc = None
        if not character:
            # Try to find as NPC
            npc = db.query(NPC).filter(
                NPC.campaign_id == campaign_uuid,
                NPC.name.ilike(f"%{target_name}%")
            ).first()

        if not character and not npc:
            await websocket.send_json({
                "type": "error",
                "message": f"Target '{target_name}' not found (searched PCs and NPCs)"
            })
            return

        # Check if already rolled
        if character:
            existing = db.query(InitiativeRoll).filter(
                InitiativeRoll.encounter_id == encounter.id,
                InitiativeRoll.character_id == character.id
            ).first()
            name = character.name
            entity_id = character.id
            entity_type = "character"
        else:
            existing = db.query(InitiativeRoll).filter(
                InitiativeRoll.encounter_id == encounter.id,
                InitiativeRoll.npc_id == npc.id
            ).first()
            name = npc.name
            entity_id = npc.id
            entity_type = "npc"

        if existing:
            await websocket.send_json({
                "type": "error",
                "message": f"{name} already rolled initiative this encounter ({existing.roll_result})"
            })
            return

        # Roll 1d6 + Edge (TBA v1.5)
        die_result = roll_dice("1d6")[0]
        edge = character.edge if character else npc.edge
        roll_total = die_result + edge

        # Create initiative roll
        initiative_roll = InitiativeRoll(
            encounter_id=encounter.id,
            character_id=character.id if character else None,
            npc_id=npc.id if npc else None,
            name=name,
            roll_result=roll_total,
            is_silent=is_silent,
            rolled_by_sw=True
        )
        db.add(initiative_roll)
        db.commit()

        # Broadcast to all players
        if is_silent:
            # Silent roll: Send full details to SW only, broadcast hidden version to everyone
            # Send full details to Story Weaver
            await websocket.send_json({
                "type": "initiative_roll",
                "actor": name,
                "roll": roll_total,
                "is_silent": True,
                "rolled_by_sw": True,
                "sw_only": True,  # Tag for SW
                "timestamp": datetime.now().isoformat()
            })
            # Broadcast hidden version to everyone else
            await manager.broadcast(campaign_uuid, {
                "type": "initiative_roll",
                "actor": name,
                "roll": "???",
                "is_silent": True,
                "rolled_by_sw": True,
                "timestamp": datetime.now().isoformat()
            })
        else:
            # Normal roll: Broadcast full details to everyone
            await manager.broadcast(campaign_uuid, {
                "type": "initiative_roll",
                "actor": name,
                "roll": roll_total,
                "is_silent": False,
                "rolled_by_sw": True,
                "timestamp": datetime.now().isoformat()
            })

        # Persist message
        msg = Message(
            campaign_id=campaign_uuid,
            party_id=None,
            sender_id=entity_id,
            sender_name=name,
            message_type="initiative_roll",
            content=f"{name} rolled {roll_total if not is_silent else '???'} for initiative (SW rolled)",
            extra_data={
                "actor": name,
                "roll": roll_total,  # Always store actual roll
                "is_silent": is_silent,
                "rolled_by_sw": True,
                "entity_type": entity_type
            }
        )
        db.add(msg)
        db.commit()

    except Exception as e:
        logger.error(f"Initiative target-roll error: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Initiative roll failed: {str(e)}"
        })


async def start_encounter(
    campaign_uuid: UUID,
    user_uuid: UUID,
    db: Session,
    websocket: WebSocket
):
    """
    Story Weaver starts an encounter without rolling initiative.
    Command: /initiative start
    """
    try:
        # Verify user is Story Weaver
        if not await is_story_weaver(campaign_uuid, user_uuid, db):
            await websocket.send_json({
                "type": "error",
                "message": "Only the Story Weaver can start encounters"
            })
            return

        # Create or get active encounter
        encounter = await get_or_create_active_encounter(campaign_uuid, db)

        # Check if encounter already has initiative rolls
        existing_rolls = db.query(InitiativeRoll).filter(
            InitiativeRoll.encounter_id == encounter.id
        ).count()

        if existing_rolls > 0:
            await websocket.send_json({
                "type": "info",
                "message": f"Encounter already active with {existing_rolls} initiative rolls. Use /initiative show to see order."
            })
            return

        # Broadcast encounter start
        await manager.broadcast(campaign_uuid, {
            "type": "encounter_start",
            "message": "⚔️ Combat has begun! Roll for initiative!",
            "encounter_id": str(encounter.id),
            "timestamp": datetime.now().isoformat()
        })

        # Persist message
        sw_character = db.query(Character).filter(
            Character.campaign_id == campaign_uuid,
            Character.user_id == user_uuid
        ).first()

        msg = Message(
            campaign_id=campaign_uuid,
            party_id=None,
            sender_id=str(sw_character.id) if sw_character else str(user_uuid),  # Use user_uuid if no character
            sender_name=sw_character.name if sw_character else "Story Weaver",
            message_type="encounter_start",
            content="⚔️ Combat has begun! Roll for initiative!",
            extra_data={
                "encounter_id": str(encounter.id)
            }
        )
        db.add(msg)
        db.commit()

    except Exception as e:
        logger.error(f"Start encounter error: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to start encounter: {str(e)}"
        })


async def show_initiative_order(
    campaign_uuid: UUID,
    user_uuid: UUID,
    db: Session,
    websocket: WebSocket
):
    """
    Display current initiative order.
    Command: /initiative show

    Filters silent rolls based on user role:
    - Story Weaver sees everything
    - Players only see non-silent rolls
    """
    try:
        # Check if user is Story Weaver
        is_sw = await is_story_weaver(campaign_uuid, user_uuid, db)

        # Get active encounter
        encounter = db.query(Encounter).filter(
            Encounter.campaign_id == campaign_uuid,
            Encounter.is_active == True
        ).first()

        if not encounter:
            await websocket.send_json({
                "type": "error",
                "message": "No active encounter"
            })
            return

        # Get all initiative rolls for this encounter
        rolls_query = db.query(InitiativeRoll).filter(
            InitiativeRoll.encounter_id == encounter.id
        ).order_by(InitiativeRoll.roll_result.desc())

        all_rolls = rolls_query.all()

        if not all_rolls:
            await websocket.send_json({
                "type": "error",
                "message": "No initiative rolls yet"
            })
            return

        # Filter based on user role
        if is_sw:
            # SW sees everything, including silent rolls
            visible_rolls = [
                {
                    "name": roll.name,
                    "roll": roll.roll_result,
                    "is_silent": roll.is_silent,
                    "rolled_by_sw": roll.rolled_by_sw
                }
                for roll in all_rolls
            ]
        else:
            # Players only see non-silent rolls
            visible_rolls = [
                {
                    "name": roll.name,
                    "roll": roll.roll_result,
                    "is_silent": False,
                    "rolled_by_sw": roll.rolled_by_sw
                }
                for roll in all_rolls
                if not roll.is_silent
            ]

        # Broadcast initiative order
        await manager.broadcast(campaign_uuid, {
            "type": "initiative_order",
            "rolls": visible_rolls,
            "encounter_id": str(encounter.id),
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Show initiative error: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to show initiative: {str(e)}"
        })


async def end_encounter(
    campaign_uuid: UUID,
    user_uuid: UUID,
    db: Session,
    websocket: WebSocket
):
    """
    End the current encounter.
    Command: /initiative end

    - Marks encounter as inactive
    - Restores all ability uses for all characters in the campaign
    - Broadcasts encounter end message
    """
    try:
        # Verify user is Story Weaver
        if not await is_story_weaver(campaign_uuid, user_uuid, db):
            await websocket.send_json({
                "type": "error",
                "message": "Only the Story Weaver can end encounters"
            })
            return

        # Get active encounter
        encounter = db.query(Encounter).filter(
            Encounter.campaign_id == campaign_uuid,
            Encounter.is_active == True
        ).first()

        if not encounter:
            await websocket.send_json({
                "type": "error",
                "message": "No active encounter to end"
            })
            return

        # Mark encounter as ended
        encounter.is_active = False
        encounter.ended_at = datetime.now()
        db.commit()

        # Restore all ability uses for characters in this campaign
        # Get all characters in the campaign
        characters = db.query(Character).filter(
            Character.campaign_id == campaign_uuid
        ).all()

        character_ids = [c.id for c in characters]

        # Restore ability uses (set uses_remaining = max_uses)
        abilities = db.query(Ability).filter(
            Ability.character_id.in_(character_ids)
        ).all()

        restored_count = 0
        for ability in abilities:
            ability.uses_remaining = ability.max_uses
            restored_count += 1

        # Reset has_faced_calling_this_encounter for all active PCs
        for char in characters:
            if not char.is_npc and char.status == 'active':
                char.has_faced_calling_this_encounter = False

        db.commit()

        # Broadcast encounter end
        await manager.broadcast(campaign_uuid, {
            "type": "encounter_end",
            "message": f"Encounter ended. {restored_count} abilities restored.",
            "encounter_id": str(encounter.id),
            "timestamp": datetime.now().isoformat()
        })

        # Persist message
        sw_character = db.query(Character).filter(
            Character.campaign_id == campaign_uuid,
            Character.user_id == user_uuid
        ).first()

        msg = Message(
            campaign_id=campaign_uuid,
            party_id=None,
            sender_id=str(sw_character.id) if sw_character else str(user_uuid),
            sender_name=sw_character.name if sw_character else "Story Weaver",
            message_type="encounter_end",
            content=f"Encounter ended. All abilities restored.",
            extra_data={
                "encounter_id": str(encounter.id),
                "abilities_restored": restored_count
            }
        )
        db.add(msg)
        db.commit()

    except Exception as e:
        logger.error(f"End encounter error: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to end encounter: {str(e)}"
        })


async def clear_initiative(
    campaign_uuid: UUID,
    user_uuid: UUID,
    db: Session,
    websocket: WebSocket
):
    """
    Clear initiative without ending the encounter.
    Command: /initiative clear

    - Deletes all initiative rolls for the active encounter
    - Does NOT restore ability uses
    - Useful for restarting initiative order
    """
    try:
        # Verify user is Story Weaver
        if not await is_story_weaver(campaign_uuid, user_uuid, db):
            await websocket.send_json({
                "type": "error",
                "message": "Only the Story Weaver can clear initiative"
            })
            return

        # Get active encounter
        encounter = db.query(Encounter).filter(
            Encounter.campaign_id == campaign_uuid,
            Encounter.is_active == True
        ).first()

        if not encounter:
            await websocket.send_json({
                "type": "error",
                "message": "No active encounter"
            })
            return

        # Delete all initiative rolls for this encounter
        deleted_count = db.query(InitiativeRoll).filter(
            InitiativeRoll.encounter_id == encounter.id
        ).delete()

        db.commit()

        # Broadcast clear
        await manager.broadcast(campaign_uuid, {
            "type": "initiative_clear",
            "message": f"Initiative cleared. {deleted_count} rolls removed.",
            "timestamp": datetime.now().isoformat()
        })

        # Persist message
        sw_character = db.query(Character).filter(
            Character.campaign_id == campaign_uuid,
            Character.user_id == user_uuid
        ).first()

        msg = Message(
            campaign_id=campaign_uuid,
            party_id=None,
            sender_id=str(sw_character.id) if sw_character else str(user_uuid),
            sender_name=sw_character.name if sw_character else "Story Weaver",
            message_type="initiative_clear",
            content=f"Initiative cleared. Roll again!",
            extra_data={
                "rolls_cleared": deleted_count
            }
        )
        db.add(msg)
        db.commit()

    except Exception as e:
        logger.error(f"Clear initiative error: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to clear initiative: {str(e)}"
        })


async def send_help_text(websocket: WebSocket):
    """
    Send help text with all available commands.
    Command: /help
    """
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
• `/initiative start` (SW) - Start encounter without rolling
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

    await websocket.send_json({
        "type": "help_text",
        "text": help_text,
        "timestamp": datetime.now().isoformat()
    })


async def restore_all_abilities(
    campaign_uuid: UUID,
    user_uuid: UUID,
    db: Session,
    websocket: WebSocket
):
    """
    Story Weaver restores all ability uses for the entire party.
    Does NOT end the encounter - just a quick rest/restoration.
    Command: /rest
    """
    try:
        # Verify user is Story Weaver
        if not await is_story_weaver(campaign_uuid, user_uuid, db):
            await websocket.send_json({
                "type": "error",
                "message": "Only the Story Weaver can use /rest"
            })
            return

        # Get all characters in this campaign
        characters = db.query(Character).filter(
            Character.campaign_id == campaign_uuid
        ).all()

        character_ids = [c.id for c in characters]

        # Restore ability uses (set uses_remaining = max_uses)
        abilities = db.query(Ability).filter(
            Ability.character_id.in_(character_ids)
        ).all()

        restored_count = 0
        for ability in abilities:
            ability.uses_remaining = ability.max_uses
            restored_count += 1

        db.commit()

        # Broadcast restoration
        await manager.broadcast(campaign_uuid, {
            "type": "abilities_restored",
            "message": f"🛏️ The party rests. {restored_count} abilities restored.",
            "abilities_restored": restored_count,
            "timestamp": datetime.now().isoformat()
        })

        # Persist message
        sw_character = db.query(Character).filter(
            Character.campaign_id == campaign_uuid,
            Character.user_id == user_uuid
        ).first()

        msg = Message(
            campaign_id=campaign_uuid,
            party_id=None,
            sender_id=str(sw_character.id) if sw_character else str(user_uuid),
            sender_name=sw_character.name if sw_character else "Story Weaver",
            message_type="abilities_restored",
            content=f"🛏️ The party rests. All abilities restored.",
            extra_data={
                "abilities_restored": restored_count
            }
        )
        db.add(msg)
        db.commit()

    except Exception as e:
        logger.error(f"Restore abilities error: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to restore abilities: {str(e)}"
        })


async def handle_initiative_command(
    campaign_uuid: UUID,
    data: dict,
    websocket: WebSocket,
    user_uuid: UUID,
    db: Session
):
    """
    Main router for initiative commands.

    Commands:
    - /initiative              -> roll_initiative_self()
    - /initiative show         -> show_initiative_order()
    - /initiative start (SW)   -> start_encounter()
    - /initiative @Target (SW) -> roll_initiative_target()
    - /initiative silent @Target (SW) -> roll_initiative_target(is_silent=True)
    - /initiative end (SW)     -> end_encounter()
    - /initiative clear (SW)   -> clear_initiative()
    """
    try:
        raw_command = data.get("raw_command", "").strip()

        if not raw_command:
            await websocket.send_json({
                "type": "error",
                "message": "Invalid initiative command"
            })
            return

        # Parse command
        parts = raw_command.split()

        # /initiative (self-roll)
        if len(parts) == 1:
            await roll_initiative_self(campaign_uuid, user_uuid, db, websocket)
            return

        subcommand = parts[1].lower()

        # /initiative show
        if subcommand == "show":
            await show_initiative_order(campaign_uuid, user_uuid, db, websocket)
            return

        # /initiative start
        if subcommand == "start":
            await start_encounter(campaign_uuid, user_uuid, db, websocket)
            return

        # /initiative end
        if subcommand == "end":
            await end_encounter(campaign_uuid, user_uuid, db, websocket)
            return

        # /initiative clear
        if subcommand == "clear":
            await clear_initiative(campaign_uuid, user_uuid, db, websocket)
            return

        # /initiative silent @Target
        if subcommand == "silent":
            if len(parts) < 3:
                await websocket.send_json({
                    "type": "error",
                    "message": "Usage: /initiative silent @TargetName"
                })
                return

            target_name = parts[2].lstrip("@")
            await roll_initiative_target(
                campaign_uuid, user_uuid, target_name, is_silent=True, db=db, websocket=websocket
            )
            return

        # /initiative @Target
        if subcommand.startswith("@"):
            target_name = subcommand.lstrip("@")
            await roll_initiative_target(
                campaign_uuid, user_uuid, target_name, is_silent=False, db=db, websocket=websocket
            )
            return

        # Unknown subcommand
        await websocket.send_json({
            "type": "error",
            "message": f"Unknown initiative command: {subcommand}\nUse: /initiative, /initiative show, /initiative end, /initiative clear, /initiative @Target, /initiative silent @Target"
        })

    except Exception as e:
        logger.error(f"Initiative command error: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Initiative command failed: {str(e)}"
        })
