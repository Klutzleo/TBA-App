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
from backend.models import Party, Character, User, CampaignMembership, Message
from backend.auth.jwt import decode_access_token
from routes.schemas.campaign import (
    ChatMessage,
    WhisperMessage,
    CombatCommand,
    GMNarration,
    DiceRollRequest,
    ChatBroadcast,
    WhisperBroadcast,
    CombatResultBroadcast,
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
        # campaign_id → list of (websocket, user_id, display_name)
        self.active_connections: Dict[UUID, List[tuple[WebSocket, UUID, str]]] = {}
    
    async def connect(self, campaign_id: UUID, websocket: WebSocket, user_id: UUID, display_name: str):
        """Accept WebSocket connection and add to campaign room."""
        await websocket.accept()
        
        if campaign_id not in self.active_connections:
            self.active_connections[campaign_id] = []
        
        self.active_connections[campaign_id].append((websocket, user_id, display_name))
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
                    display_name = conn[2]
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
        for websocket, user_id, display_name in self.active_connections[campaign_id]:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to {display_name}: {e}")
                disconnected.append((websocket, user_id, display_name))
        
        # Clean up dead connections
        for conn in disconnected:
            if conn in self.active_connections[campaign_id]:
                self.active_connections[campaign_id].remove(conn)
    
    async def send_to_user(self, campaign_id: UUID, target_user_id: UUID, message: dict):
        """Send message to a specific user in a campaign (for whispers)."""
        if campaign_id not in self.active_connections:
            return False
        
        for websocket, user_id, display_name in self.active_connections[campaign_id]:
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
        return [(user_id, display_name) for _, user_id, display_name in self.active_connections[campaign_id]]


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
        display_name = user.username

    except Exception as e:
        logger.error(f"WebSocket authentication error: {e}")
        await websocket.close(code=1011, reason="Authentication failed")
        return

    # ===== AUTHENTICATION PASSED - Continue with existing logic =====
    campaign_uuid = campaign_id

    await manager.connect(campaign_uuid, websocket, user_uuid, display_name)
    
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
                await handle_chat(campaign_uuid, data)

            elif message_type == "whisper":
                await handle_whisper(campaign_uuid, data)

            elif message_type == "combat_command":
                await handle_combat_command(campaign_uuid, data, websocket)

            elif message_type == "narration":
                await handle_narration(campaign_uuid, data)

            elif message_type == "dice_roll":
                await handle_dice_roll(campaign_uuid, data)

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


async def handle_chat(campaign_id: UUID, data: dict):
    """Handle regular chat message (IC or OOC)."""
    msg = ChatMessage(**data)
    
    # Look up character name from database
    character_name = None
    async with get_db_session() as db:
        result = await db.execute(
            text("""
                SELECT c.name 
                FROM campaign_memberships cm
                JOIN characters c ON cm.character_id = c.id
                WHERE cm.campaign_id = :campaign_id 
                  AND cm.user_id = :user_id
                  AND cm.status = 'active'
            """),
            {"campaign_id": campaign_id, "user_id": msg.user_id}
        )
        row = result.first()
        if row:
            character_name = row[0]
    
    # Use character name if available, otherwise username
    display_name = character_name or msg.sender
    
    # Broadcast to everyone in campaign
    await manager.broadcast(campaign_id, ChatBroadcast(
        mode=msg.mode,
        sender=display_name,  # ← Now sends character name!
        user_id=msg.user_id,
        message=msg.message,
        attachment=msg.attachment
    ).model_dump(mode='json'))


async def handle_whisper(campaign_id: UUID, data: dict):
    """Handle private whisper message."""
    msg = WhisperMessage(**data)
    
    # Send to recipient only
    success = await manager.send_to_user(campaign_id, msg.recipient_user_id, WhisperBroadcast(
        sender=msg.sender,
        message=msg.message
    ).model_dump(mode='json'))
    
    if not success:
        logger.warning(f"Failed to deliver whisper from {msg.sender} to {msg.recipient_user_id}")


async def handle_combat_command(campaign_id: UUID, data: dict, websocket: WebSocket):
    """
    Handle combat command (/attack, /cast, etc.).
    
    This triggers the actual combat resolution via internal HTTP call.
    Result is broadcast to all players.
    """
    # This is a placeholder—we'll integrate with combat_fastapi.py endpoints
    # For now, just broadcast that a command was received
    cmd = CombatCommand(**data)
    
    await manager.broadcast(campaign_id, SystemNotification(
        event="combat_started",
        message=f"Combat command received: {cmd.command} (integration pending)"
    ).model_dump(mode='json'))
    
    # TODO: Call internal combat resolution and broadcast result


async def handle_narration(campaign_id: UUID, data: dict):
    """Handle GM narration."""
    narration = GMNarration(**data)
    
    # Broadcast to everyone
    await manager.broadcast(campaign_id, NarrationBroadcast(
        text=narration.text,
        attachment=narration.attachment
    ).model_dump(mode='json'))


async def handle_dice_roll(campaign_id: UUID, data: dict):
    """Handle dice roll request (e.g., '3d6+2')."""
    roll_req = DiceRollRequest(**data)
    
    # Parse dice notation (e.g., "3d6+2")
    result, breakdown = roll_dice(roll_req.dice)
    
    # Broadcast result to everyone
    await manager.broadcast(campaign_id, DiceRollBroadcast(
        roller=roll_req.roller,
        dice=roll_req.dice,
        result=result,
        breakdown=breakdown,
        reason=roll_req.reason
    ).model_dump(mode='json'))


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def roll_dice(dice_notation: str) -> tuple[int, List[int]]:
    """
    Parse and roll dice notation (e.g., '3d6+2', '1d20', '2d10-3').
    
    Returns:
        (total, breakdown): e.g., (15, [4, 6, 3]) for "3d6+2"
    """
    # Parse notation: XdY+Z or XdY-Z
    match = re.match(r'(\d+)d(\d+)(([+\-])(\d+))?', dice_notation.lower())
    if not match:
        raise ValueError(f"Invalid dice notation: {dice_notation}")
    
    num_dice = int(match.group(1))
    die_sides = int(match.group(2))
    modifier = 0
    
    if match.group(3):
        sign = match.group(4)
        mod_value = int(match.group(5))
        modifier = mod_value if sign == '+' else -mod_value
    
    # Roll dice
    rolls = [random.randint(1, die_sides) for _ in range(num_dice)]
    total = sum(rolls) + modifier
    
    return total, rolls


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
