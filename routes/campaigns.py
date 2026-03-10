"""
Campaign Routes - Create and manage campaigns
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID, uuid4
from datetime import datetime
import logging
import random
import string

logger = logging.getLogger(__name__)

from backend.db import get_db
from backend.models import Campaign, Party, Character, PartyMembership, Message, User, CampaignMembership, LoreEntry, InventoryItem
from backend.auth.jwt import get_current_user
from sqlalchemy import or_, func

router = APIRouter(tags=["campaigns"])


def generate_join_code(db: Session) -> str:
    """Generate a unique 6-character join code."""
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        # Check if code already exists
        existing = db.query(Campaign).filter(Campaign.join_code == code).first()
        if not existing:
            return code


class CampaignCreate(BaseModel):
    """Request to create a new campaign (Phase 3)."""
    name: str = Field(..., min_length=3, max_length=100)
    description: str = Field(..., min_length=10, max_length=2000)
    is_public: bool = Field(default=True)
    posting_frequency: str = Field(..., pattern="^(slow|medium|high)$")
    min_players: int = Field(..., ge=2, le=20)
    max_players: int = Field(..., ge=2, le=20)
    max_spectators: Optional[int] = Field(None, ge=0, le=500)  # None = unlimited
    timezone: str = Field(..., min_length=1)


class CampaignResponse(BaseModel):
    """Campaign response (Phase 3)."""
    id: UUID
    name: str
    description: Optional[str] = None
    join_code: Optional[str] = None
    is_public: Optional[bool] = True
    min_players: Optional[int] = 2
    max_players: Optional[int] = 6
    max_spectators: Optional[int] = None  # None = unlimited
    timezone: Optional[str] = 'America/New_York'
    posting_frequency: Optional[str] = 'medium'
    status: Optional[str] = 'active'
    story_weaver_id: Optional[UUID] = None
    created_by_user_id: Optional[UUID] = None
    is_active: bool
    user_role: Optional[str] = None  # 'story_weaver' or 'player'
    member_count: Optional[int] = None  # Number of active members
    character_creation_mode: Optional[str] = 'open'  # 'open', 'approval_required', 'sw_only'
    max_characters_per_player: Optional[int] = 1
    my_character_status: Optional[str] = None  # Player's character status: 'active', 'pending_approval', 'rejected'
    my_rejection_reason: Optional[str] = None  # SW's rejection message if rejected
    pending_approval_count: Optional[int] = 0  # SW only: number of pending character approvals

    class Config:
        from_attributes = True


class JoinCampaignRequest(BaseModel):
    """Request to join a campaign by join code."""
    join_code: str


class CampaignUpdate(BaseModel):
    """Request to update campaign settings."""
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    description: Optional[str] = Field(None, min_length=10, max_length=2000)
    is_public: Optional[bool] = None
    posting_frequency: Optional[str] = Field(None, pattern="^(slow|medium|high)$")
    status: Optional[str] = Field(None, pattern="^(active|archived|on_break)$")
    character_creation_mode: Optional[str] = Field(None, pattern="^(open|approval_required|sw_only)$")
    max_characters_per_player: Optional[int] = Field(None, ge=1, le=999)
    max_spectators: Optional[int] = Field(None, ge=0, le=500)  # None = unlimited


@router.post("/create", response_model=CampaignResponse)
def create_campaign(
    req: CampaignCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new campaign (Phase 3).

    Requires JWT authentication. The current user becomes the Story Weaver.

    Returns the campaign with a unique join code.
    """
    # Generate unique join code
    join_code = generate_join_code(db)

    # Create campaign with current user as Story Weaver
    campaign = Campaign(
        id=str(uuid4()),
        name=req.name,
        description=req.description,
        join_code=join_code,
        is_public=req.is_public,
        min_players=req.min_players,
        max_players=req.max_players,
        max_spectators=req.max_spectators,
        timezone=req.timezone,
        posting_frequency=req.posting_frequency,
        status='active',
        story_weaver_id=current_user.id,  # Current user is the Story Weaver
        created_by_user_id=current_user.id,
        is_active=True
    )

    db.add(campaign)
    db.flush()  # Get the campaign.id before creating membership

    # Create CampaignMembership record for the Story Weaver
    membership = CampaignMembership(
        campaign_id=campaign.id,
        user_id=current_user.id,
        role="story_weaver"
    )
    db.add(membership)
    db.commit()
    db.refresh(campaign)

    return CampaignResponse(
        id=campaign.id,
        name=campaign.name,
        description=campaign.description,
        join_code=campaign.join_code,
        is_public=campaign.is_public,
        min_players=campaign.min_players,
        max_players=campaign.max_players,
        max_spectators=campaign.max_spectators,
        timezone=campaign.timezone,
        posting_frequency=campaign.posting_frequency,
        status=campaign.status,
        story_weaver_id=str(campaign.story_weaver_id) if campaign.story_weaver_id else None,
        created_by_user_id=str(campaign.created_by_user_id) if campaign.created_by_user_id else None,
        is_active=campaign.is_active,
        user_role='story_weaver',  # Creator is always the Story Weaver
        member_count=1  # Creator is the first member
    )


@router.get("", response_model=List[CampaignResponse])
def list_my_campaigns(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all campaigns for the current user.

    Returns campaigns where the user is the Story Weaver OR a player (member).
    Includes user_role field to distinguish between Story Weaver and player.
    """
    # Debug: Print current user ID
    print(f"DEBUG: Current user ID: {current_user.id}, type: {type(current_user.id)}")

    # Get campaigns where user is Story Weaver
    sw_campaigns = db.query(Campaign).filter(
        Campaign.story_weaver_id == current_user.id,
        Campaign.is_active == True
    ).all()

    # Debug: Print found campaigns
    print(f"DEBUG: Found {len(sw_campaigns)} Story Weaver campaigns")
    for c in sw_campaigns:
        print(f"DEBUG: Campaign {c.id}, story_weaver_id: {c.story_weaver_id}, type: {type(c.story_weaver_id)}")

    # Get campaigns where user is a member (player)
    member_campaigns = db.query(Campaign).join(
        CampaignMembership,
        Campaign.id == CampaignMembership.campaign_id
    ).filter(
        CampaignMembership.user_id == current_user.id,
        CampaignMembership.left_at.is_(None),  # Still active member
        Campaign.is_active == True
    ).all()

    # Build response with role info and member count
    result = []

    # Add Story Weaver campaigns
    for c in sw_campaigns:
        member_count = db.query(func.count(CampaignMembership.id)).filter(
            CampaignMembership.campaign_id == c.id,
            CampaignMembership.left_at.is_(None)
        ).scalar()

        pending_count = db.query(func.count(Character.id)).filter(
            Character.campaign_id == c.id,
            Character.status == 'pending_approval',
            Character.is_npc == False
        ).scalar()

        result.append(CampaignResponse(
            id=c.id,
            name=c.name,
            description=c.description,
            join_code=c.join_code,
            is_public=c.is_public,
            min_players=c.min_players,
            max_players=c.max_players,
            max_spectators=c.max_spectators,
            timezone=c.timezone,
            posting_frequency=c.posting_frequency,
            status=c.status,
            story_weaver_id=c.story_weaver_id,
            created_by_user_id=c.created_by_user_id,
            is_active=c.is_active,
            user_role='story_weaver',
            member_count=member_count or 0,
            character_creation_mode=c.character_creation_mode,
            max_characters_per_player=c.max_characters_per_player,
            pending_approval_count=pending_count or 0
        ))

    # Add player campaigns (avoid duplicates if user is both SW and member)
    sw_campaign_ids = {c.id for c in sw_campaigns}
    for c in member_campaigns:
        if c.id not in sw_campaign_ids:
            member_count = db.query(func.count(CampaignMembership.id)).filter(
                CampaignMembership.campaign_id == c.id,
                CampaignMembership.left_at.is_(None)
            ).scalar()

            # Check player's character status in this campaign
            my_char = db.query(Character).filter(
                Character.user_id == current_user.id,
                Character.campaign_id == c.id,
                Character.is_npc == False
            ).order_by(Character.created_at.desc()).first()

            result.append(CampaignResponse(
                id=c.id,
                name=c.name,
                description=c.description,
                join_code=c.join_code,
                is_public=c.is_public,
                min_players=c.min_players,
                max_players=c.max_players,
                max_spectators=c.max_spectators,
                timezone=c.timezone,
                posting_frequency=c.posting_frequency,
                status=c.status,
                story_weaver_id=c.story_weaver_id,
                created_by_user_id=c.created_by_user_id,
                is_active=c.is_active,
                user_role='player',
                member_count=member_count or 0,
                character_creation_mode=c.character_creation_mode,
                max_characters_per_player=c.max_characters_per_player,
                my_character_status=my_char.status if my_char else None,
                my_rejection_reason=my_char.rejection_reason if my_char else None
            ))

    # Sort by created_at descending (Story Weaver campaigns first, then player campaigns)
    result.sort(key=lambda x: (x.user_role != 'story_weaver', x.created_by_user_id), reverse=True)

    return result


@router.get("/browse", response_model=List[CampaignResponse])
def browse_public_campaigns(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Browse all public campaigns.

    Returns campaigns that are marked as public with member counts.
    """
    campaigns = db.query(Campaign).filter(
        Campaign.is_public == True,
        Campaign.is_active == True
    ).order_by(Campaign.created_at.desc()).all()

    result = []
    for c in campaigns:
        # Get member count for each campaign
        member_count = db.query(func.count(CampaignMembership.id)).filter(
            CampaignMembership.campaign_id == c.id,
            CampaignMembership.left_at.is_(None)
        ).scalar()

        result.append(CampaignResponse(
            id=c.id,
            name=c.name,
            description=c.description,
            join_code=c.join_code,
            is_public=c.is_public,
            min_players=c.min_players,
            max_players=c.max_players,
            max_spectators=c.max_spectators,
            timezone=c.timezone,
            posting_frequency=c.posting_frequency,
            status=c.status,
            story_weaver_id=c.story_weaver_id,
            created_by_user_id=c.created_by_user_id,
            is_active=c.is_active,
            user_role=None,  # Not showing role for browse
            member_count=member_count or 0,
            character_creation_mode=c.character_creation_mode,
            max_characters_per_player=c.max_characters_per_player
        ))

    return result


@router.post("/join")
async def join_campaign(
    req: JoinCampaignRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Join a campaign using a join code."""

    # Find campaign by join code
    campaign = db.query(Campaign).filter(
        Campaign.join_code == req.join_code.upper()
    ).first()

    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found with that join code")

    # Check if already a member
    existing = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == campaign.id,
        CampaignMembership.user_id == current_user.id,
        CampaignMembership.left_at.is_(None)
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="You are already a member of this campaign")

    # Count active PC-holders (player memberships with an active character)
    pc_count = db.query(func.count(CampaignMembership.id)).filter(
        CampaignMembership.campaign_id == campaign.id,
        CampaignMembership.left_at.is_(None),
        CampaignMembership.role == 'player'
    ).join(
        Character,
        (Character.owner_id == CampaignMembership.user_id) &
        (Character.campaign_id == campaign.id) &
        (Character.status == 'active') &
        (Character.is_npc == False)
    ).scalar()

    if pc_count >= campaign.max_players:
        raise HTTPException(status_code=400, detail="Campaign is full — no open player slots")

    # If spectator cap is set, check spectators (players without an active PC)
    if campaign.max_spectators is not None:
        spectator_count = db.query(func.count(CampaignMembership.id)).filter(
            CampaignMembership.campaign_id == campaign.id,
            CampaignMembership.left_at.is_(None),
            CampaignMembership.role == 'player'
        ).outerjoin(
            Character,
            (Character.owner_id == CampaignMembership.user_id) &
            (Character.campaign_id == campaign.id) &
            (Character.status == 'active') &
            (Character.is_npc == False)
        ).filter(Character.id.is_(None)).scalar()

        if spectator_count >= campaign.max_spectators:
            raise HTTPException(status_code=400, detail="Campaign has reached its spectator limit")

    # Create membership
    membership = CampaignMembership(
        campaign_id=campaign.id,
        user_id=current_user.id,
        role="player"
    )
    db.add(membership)
    db.commit()

    # Broadcast so the SW gets a real-time toast + party panel refresh
    try:
        from routes.campaign_websocket import broadcast_player_joined
        import asyncio
        asyncio.create_task(broadcast_player_joined(campaign.id, current_user.username))
    except Exception:
        pass

    # Push notify the SW (they may be offline)
    if campaign.story_weaver_id:
        try:
            from backend.notifications import send_push
            send_push(
                db, str(campaign.story_weaver_id),
                "🧑‍🤝‍🧑 New Player Joined",
                f"{current_user.username} joined {campaign.name}.",
                url=f"/game.html?campaign_id={campaign.id}",
                campaign_id=str(campaign.id),
            )
        except Exception as _pe:
            logger.warning(f"Push notification failed (player joined): {_pe}")

    return {"success": True, "message": f"Successfully joined {campaign.name}"}


@router.delete("/{campaign_id}/leave")
async def leave_campaign(
    campaign_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Leave a campaign. Story Weavers cannot leave (they must delete the campaign)."""
    membership = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == campaign_id,
        CampaignMembership.user_id == current_user.id,
        CampaignMembership.left_at.is_(None)
    ).first()

    if not membership:
        raise HTTPException(status_code=404, detail="You are not a member of this campaign")

    if membership.role == "story_weaver":
        raise HTTPException(status_code=403, detail="Story Weavers cannot leave a campaign. Transfer ownership or delete the campaign instead.")

    membership.left_at = datetime.utcnow()
    db.commit()

    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()

    # Notify SW via WebSocket (if online)
    try:
        from routes.campaign_websocket import manager
        import asyncio
        asyncio.create_task(manager.broadcast(campaign_id, {
            "type": "player_left_campaign",
            "username": current_user.username,
            "message": f"{current_user.username} left the campaign."
        }))
    except Exception:
        pass

    # Push notify SW (if offline)
    if campaign and campaign.story_weaver_id:
        try:
            from backend.notifications import send_push
            send_push(
                db, str(campaign.story_weaver_id),
                "🚪 Player Left",
                f"{current_user.username} left {campaign.name}.",
                url=f"/game.html?campaign_id={campaign_id}",
                campaign_id=str(campaign_id),
            )
        except Exception as _pe:
            logger.warning(f"Push notification failed (player left): {_pe}")

    return {"success": True, "message": "You have left the campaign"}

@router.get("/{campaign_id}/check-character")
def check_campaign_character(
    campaign_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check if the current user has a character in this campaign.
    Also returns the user's role (story_weaver or player).

    Returns:
        {"role": "story_weaver", "has_character": False} if user is SW
        {"role": "player", "has_character": True, "character_id": str} if player with character
        {"role": "player", "has_character": False} if player without character
    """
    # Check membership role first
    membership = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == campaign_id,
        CampaignMembership.user_id == current_user.id,
        CampaignMembership.left_at.is_(None)
    ).first()

    if membership and membership.role == "story_weaver":
        return {"role": "story_weaver", "has_character": False, "can_create": False}

    # Check campaign's character limit
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    max_chars = campaign.max_characters_per_player if campaign else 1

    # Count active characters only — rejected and archived (dead) don't block new character creation
    existing_count = db.query(Character).filter(
        Character.user_id == current_user.id,
        Character.campaign_id == campaign_id,
        Character.is_npc == False,
        Character.status.notin_(['rejected', 'archived'])
    ).count()
    can_create = existing_count < max_chars

    # Check if user has character in this campaign
    character = db.query(Character).filter(
        Character.user_id == current_user.id,
        Character.campaign_id == campaign_id
    ).first()

    if character:
        return {
            "role": "player",
            "has_character": character.status == 'active',
            "character_id": str(character.id) if character.status == 'active' else None,
            "character_status": character.status,
            "rejection_reason": character.rejection_reason,
            "can_create": can_create
        }
    return {"role": "player", "has_character": False, "character_status": None, "can_create": can_create}


@router.get("/{campaign_id}", response_model=CampaignResponse)
def get_campaign(campaign_id: str, db: Session = Depends(get_db)):
    """Get campaign details."""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()

    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Get channels
    story_channel = db.query(Party).filter(
        Party.campaign_id == campaign_id,
        Party.party_type == 'story'
    ).first()

    ooc_channel = db.query(Party).filter(
        Party.campaign_id == campaign_id,
        Party.party_type == 'ooc'
    ).first()

    return CampaignResponse(
        id=campaign.id,
        name=campaign.name,
        description=campaign.description,
        story_weaver_id=campaign.story_weaver_id,
        created_by_id=campaign.created_by_id,
        is_active=campaign.is_active,
        story_channel_id=story_channel.id if story_channel else None,
        ooc_channel_id=ooc_channel.id if ooc_channel else None,
        join_code=campaign.join_code,
        is_public=campaign.is_public,
        min_players=campaign.min_players,
        max_players=campaign.max_players,
        max_spectators=campaign.max_spectators,
        timezone=campaign.timezone,
        posting_frequency=str(campaign.posting_frequency) if campaign.posting_frequency else 'medium',
        status=str(campaign.status) if campaign.status else 'active',
        character_creation_mode=campaign.character_creation_mode or 'open',
        max_characters_per_player=campaign.max_characters_per_player or 1,
    )


@router.patch("/{campaign_id}", response_model=CampaignResponse)
@router.put("/{campaign_id}", response_model=CampaignResponse)
def update_campaign(
    campaign_id: str,
    updates: CampaignUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update campaign settings (Story Weaver only)."""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()

    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Check if user is Story Weaver
    membership = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == campaign_id,
        CampaignMembership.user_id == current_user.id
    ).first()

    if not membership or membership.role != 'story_weaver':
        raise HTTPException(status_code=403, detail="Only Story Weaver can update campaign settings")

    # Update fields if provided
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Updating campaign {campaign_id}: character_creation_mode={updates.character_creation_mode}, max_characters={updates.max_characters_per_player}")

    if updates.name is not None:
        campaign.name = updates.name
    if updates.description is not None:
        campaign.description = updates.description
    if updates.is_public is not None:
        campaign.is_public = updates.is_public
    if updates.posting_frequency is not None:
        campaign.posting_frequency = updates.posting_frequency
    if updates.status is not None:
        campaign.status = updates.status
    if updates.character_creation_mode is not None:
        campaign.character_creation_mode = updates.character_creation_mode
    if updates.max_characters_per_player is not None:
        campaign.max_characters_per_player = updates.max_characters_per_player
    if 'max_spectators' in updates.model_fields_set:
        campaign.max_spectators = updates.max_spectators  # None = unlimited

    db.commit()
    db.refresh(campaign)

    logger.info(f"Campaign updated: mode={campaign.character_creation_mode}, max_chars={campaign.max_characters_per_player}")

    return campaign


@router.get("/{campaign_id}/orphaned-characters")
def get_orphaned_characters(
    campaign_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Return active PCs in this campaign whose owner is no longer an active member.
    SW only. Used by the settings modal rescue flow.
    """
    membership = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == campaign_id,
        CampaignMembership.user_id == current_user.id
    ).first()
    if not membership or membership.role != 'story_weaver':
        raise HTTPException(status_code=403, detail="Story Weaver only")

    # Active member user_ids
    active_member_ids = {
        m.user_id for m in db.query(CampaignMembership).filter(
            CampaignMembership.campaign_id == campaign_id,
            CampaignMembership.left_at.is_(None)
        ).all()
    }

    # PCs whose owner is NOT in the active member set
    orphaned = db.query(Character).filter(
        Character.campaign_id == campaign_id,
        Character.is_npc == False,
        Character.status == 'active',
        Character.user_id.is_not(None),
        ~Character.user_id.in_(active_member_ids)
    ).all()

    result = []
    for char in orphaned:
        owner = db.query(User).filter(User.id == char.user_id).first()
        result.append({
            "id": str(char.id),
            "name": char.name,
            "level": char.level,
            "former_owner": owner.username if owner else "Unknown"
        })
    return result


@router.get("/{campaign_id}/members")
async def get_campaign_members(
    campaign_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all members of a campaign with their characters"""
    
    # Verify user is a member
    membership = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == campaign_id,
        CampaignMembership.user_id == current_user.id
    ).first()
    
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this campaign")
    
    # Get all members with their characters
    members = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == campaign_id,
        CampaignMembership.left_at.is_(None)
    ).all()
    
    result = []
    for member in members:
        user = db.query(User).filter(User.id == member.user_id).first()
        character = db.query(Character).filter(
            Character.campaign_id == campaign_id,
            Character.user_id == member.user_id,
            Character.status == 'active'
        ).first()
        
        result.append({
            "user_id": str(user.id),
            "username": user.username,
            "role": member.role,
            "membership_chat_color": member.chat_color or '#d4af37',
            "character": {
                "id": str(character.id),
                "user_id": str(character.user_id) if character.user_id else None,
                "name": character.name,
                "level": character.level,
                "dp": character.dp,
                "max_dp": character.max_dp,
                "edge": character.edge,
                "bap": character.bap,
                "pp": character.pp,
                "ip": character.ip,
                "sp": character.sp,
                "in_calling": character.in_calling or False,
                "times_called": character.times_called or 0,
                "is_called": character.is_called or False,
                "bap_token_active": character.bap_token_active or False,
                "bap_token_type": character.bap_token_type,
                "battle_scars": character.battle_scars or [],
                "chat_color": character.chat_color or '#d4af37',
            } if character else None
        })
    
    return result

@router.get("/{campaign_id}/sw-notes")
async def get_sw_notes(
    campaign_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the SW's private notes for this campaign (SW only)."""
    membership = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == campaign_id,
        CampaignMembership.user_id == current_user.id
    ).first()
    if not membership or membership.role != 'story_weaver':
        raise HTTPException(status_code=403, detail="SW only")

    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return {"sw_notes": campaign.sw_notes or ""}


@router.patch("/{campaign_id}/sw-notes")
async def update_sw_notes(
    campaign_id: UUID,
    req: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Save the SW's private notes for this campaign (SW only)."""
    membership = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == campaign_id,
        CampaignMembership.user_id == current_user.id
    ).first()
    if not membership or membership.role != 'story_weaver':
        raise HTTPException(status_code=403, detail="SW only")

    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign.sw_notes = req.get("sw_notes", "")
    db.commit()
    return {"sw_notes": campaign.sw_notes}


@router.get("/{campaign_id}/currency-name")
async def get_currency_name(
    campaign_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the campaign's currency name (all members)."""
    membership = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == campaign_id,
        CampaignMembership.user_id == current_user.id,
        CampaignMembership.left_at.is_(None)
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this campaign")
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {"currency_name": campaign.currency_name or "Gold"}


@router.patch("/{campaign_id}/currency-name")
async def update_currency_name(
    campaign_id: UUID,
    req: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """SW sets the campaign's currency name."""
    _require_sw(campaign_id, current_user, db)
    name = (req.get("currency_name") or "Gold").strip()[:50]
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    campaign.currency_name = name
    db.commit()
    return {"currency_name": campaign.currency_name}


@router.patch("/{campaign_id}/pin")
async def pin_message(
    campaign_id: UUID,
    req: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """SW pins a message text to the campaign banner."""
    _require_sw(campaign_id, current_user, db)
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    campaign.pin_text = req.get("text", "").strip()[:500]
    campaign.pin_actor = req.get("actor", "").strip()[:200]
    db.commit()
    return {"pin_text": campaign.pin_text, "pin_actor": campaign.pin_actor}


@router.delete("/{campaign_id}/pin", status_code=204)
async def unpin_message(
    campaign_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """SW clears the pinned message."""
    _require_sw(campaign_id, current_user, db)
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    campaign.pin_text = None
    campaign.pin_actor = None
    db.commit()


@router.get("/{campaign_id}/channels")
def get_campaign_channels(campaign_id: str, db: Session = Depends(get_db)):
    """Get all channels for a campaign."""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()

    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    channels = db.query(Party).filter(Party.campaign_id == campaign_id).all()

    return {
        "campaign_id": campaign_id,
        "campaign_name": campaign.name,
        "channels": [
            {
                "id": channel.id,
                "name": channel.name,
                "type": channel.party_type,
                "is_active": channel.is_active
            }
            for channel in channels
        ]
    }


@router.get("/{campaign_id}/messages")
def get_campaign_messages(
    campaign_id: str,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get recent message history for a campaign.

    Returns messages from all channels in the campaign, sorted by timestamp.
    Supports pagination via limit and offset parameters.
    Used to restore chat history when a user connects and for "Load More" functionality.
    """
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()

    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Verify user is a member of this campaign
    membership = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == campaign_id,
        CampaignMembership.user_id == current_user.id,
        CampaignMembership.left_at.is_(None)
    ).first()

    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this campaign")

    # Get messages for this campaign, sorted by time (newest first), with pagination
    # Exclude soft-deleted messages
    messages = db.query(Message)\
        .filter(Message.campaign_id == campaign_id)\
        .filter(Message.deleted_at == None)\
        .order_by(Message.created_at.desc())\
        .offset(offset)\
        .limit(limit)\
        .all()

    return {
        "campaign_id": campaign_id,
        "messages": [
            {
                "id": msg.id,
                "party_id": msg.party_id,
                "sender_id": msg.sender_id,
                "sender_name": msg.sender_name,
                "content": msg.content,
                "type": msg.message_type,  # Frontend expects 'type'
                "chat_mode": msg.mode,     # Frontend expects 'chat_mode'
                "message_type": msg.message_type,  # Keep for backward compatibility
                "mode": msg.mode,                  # Keep for backward compatibility
                "extra_data": msg.extra_data,      # Include extra_data (dice roll breakdowns, etc.)
                "is_edited": msg.is_edited or False,
                "timestamp": msg.created_at.isoformat() if msg.created_at else None
            }
            for msg in messages
        ]
    }


# ============================================================
# Lore Endpoints
# ============================================================

def _lore_dict(entry: LoreEntry) -> dict:
    return {
        "id": str(entry.id),
        "title": entry.title,
        "content": entry.content,
        "created_by": str(entry.created_by) if entry.created_by else None,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
    }


def _require_sw(campaign_id: UUID, current_user: User, db: Session):
    """Raise 403 if the user is not the SW of this campaign."""
    membership = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == campaign_id,
        CampaignMembership.user_id == current_user.id
    ).first()
    if not membership or membership.role != 'story_weaver':
        raise HTTPException(status_code=403, detail="Only the Story Weaver can do that")
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.get("/{campaign_id}/lore")
async def list_lore(
    campaign_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Return all lore entries for the campaign (all members)."""
    membership = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == campaign_id,
        CampaignMembership.user_id == current_user.id,
        CampaignMembership.left_at.is_(None)
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this campaign")

    entries = (
        db.query(LoreEntry)
        .filter(LoreEntry.campaign_id == campaign_id)
        .order_by(LoreEntry.created_at.asc())
        .all()
    )
    return [_lore_dict(e) for e in entries]


@router.post("/{campaign_id}/lore", status_code=201)
async def create_lore(
    campaign_id: UUID,
    req: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """SW creates a new lore entry."""
    _require_sw(campaign_id, current_user, db)

    title = (req.get("title") or "").strip()
    content = (req.get("content") or "").strip()
    if not title:
        raise HTTPException(status_code=422, detail="Title is required")

    entry = LoreEntry(
        campaign_id=campaign_id,
        title=title,
        content=content,
        created_by=current_user.id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    try:
        from routes.campaign_websocket import manager
        import asyncio
        asyncio.create_task(manager.broadcast(str(campaign_id), {
            "type": "lore_created",
            "entry": _lore_dict(entry),
        }))
    except Exception:
        pass

    return _lore_dict(entry)


@router.patch("/{campaign_id}/lore/{entry_id}")
async def update_lore(
    campaign_id: UUID,
    entry_id: UUID,
    req: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """SW edits an existing lore entry."""
    _require_sw(campaign_id, current_user, db)

    entry = db.query(LoreEntry).filter(
        LoreEntry.id == entry_id,
        LoreEntry.campaign_id == campaign_id
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Lore entry not found")

    if "title" in req:
        entry.title = (req["title"] or "").strip() or entry.title
    if "content" in req:
        entry.content = req["content"]

    db.commit()
    db.refresh(entry)

    try:
        from routes.campaign_websocket import manager
        import asyncio
        asyncio.create_task(manager.broadcast(str(campaign_id), {
            "type": "lore_updated",
            "entry": _lore_dict(entry),
        }))
    except Exception:
        pass

    return _lore_dict(entry)


@router.delete("/{campaign_id}/lore/{entry_id}", status_code=204)
async def delete_lore(
    campaign_id: UUID,
    entry_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """SW deletes a lore entry."""
    _require_sw(campaign_id, current_user, db)

    entry = db.query(LoreEntry).filter(
        LoreEntry.id == entry_id,
        LoreEntry.campaign_id == campaign_id
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Lore entry not found")

    db.delete(entry)
    db.commit()

    try:
        from routes.campaign_websocket import manager
        import asyncio
        asyncio.create_task(manager.broadcast(str(campaign_id), {
            "type": "lore_deleted",
            "entry_id": str(entry_id),
        }))
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# LOOT POOL  (SW-managed items not yet assigned to any character)
# ─────────────────────────────────────────────────────────────────────────────

def _item_dict(item: InventoryItem) -> dict:
    return {
        "id":           str(item.id),
        "character_id": str(item.character_id) if item.character_id else None,
        "name":         item.name,
        "item_type":    item.item_type,
        "quantity":     item.quantity,
        "description":  item.description,
        "tier":         item.tier,
        "effect_type":  item.effect_type,
        "bonus":        item.bonus,
        "bonus_type":   item.bonus_type,
        "is_equipped":  item.is_equipped,
        "given_by_sw":  item.given_by_sw,
        "created_at":   item.created_at.isoformat() if item.created_at else None,
    }


@router.get("/{campaign_id}/loot-pool")
async def get_loot_pool(
    campaign_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """SW views all unassigned campaign items."""
    _require_sw(campaign_id, current_user, db)
    items = db.query(InventoryItem).filter(
        InventoryItem.campaign_id == campaign_id,
        InventoryItem.character_id.is_(None)
    ).order_by(InventoryItem.item_type, InventoryItem.name).all()
    return {"items": [_item_dict(i) for i in items]}


@router.post("/{campaign_id}/loot-pool", status_code=201)
async def create_loot_pool_item(
    campaign_id: UUID,
    req: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """SW creates an item in the loot pool (no character assigned yet)."""
    _require_sw(campaign_id, current_user, db)

    name = (req.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="Item name is required")

    item = InventoryItem(
        character_id = None,
        campaign_id  = campaign_id,
        name         = name,
        item_type    = req.get("item_type", "misc"),
        quantity     = max(1, int(req.get("quantity", 1))),
        description  = req.get("description"),
        tier         = req.get("tier"),
        effect_type  = req.get("effect_type"),
        bonus        = req.get("bonus"),
        bonus_type   = req.get("bonus_type"),
        given_by_sw  = True,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _item_dict(item)


@router.patch("/{campaign_id}/loot-pool/{item_id}")
async def edit_loot_pool_item(
    campaign_id: UUID,
    item_id: UUID,
    req: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """SW edits an item in the loot pool."""
    _require_sw(campaign_id, current_user, db)
    item = db.query(InventoryItem).filter(
        InventoryItem.id == item_id,
        InventoryItem.campaign_id == campaign_id,
        InventoryItem.character_id.is_(None)
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found in loot pool")

    if "name"        in req: item.name        = req["name"].strip() or item.name
    if "item_type"   in req: item.item_type   = req["item_type"]
    if "quantity"    in req: item.quantity     = max(1, int(req["quantity"]))
    if "description" in req: item.description = req["description"]
    if "tier"        in req: item.tier        = req["tier"]
    if "effect_type" in req: item.effect_type = req["effect_type"]
    if "bonus"       in req: item.bonus       = req["bonus"]
    if "bonus_type"  in req: item.bonus_type  = req["bonus_type"]
    db.commit()
    db.refresh(item)
    return _item_dict(item)


@router.delete("/{campaign_id}/loot-pool/{item_id}", status_code=204)
async def delete_loot_pool_item(
    campaign_id: UUID,
    item_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """SW removes an item from the loot pool."""
    _require_sw(campaign_id, current_user, db)
    item = db.query(InventoryItem).filter(
        InventoryItem.id == item_id,
        InventoryItem.campaign_id == campaign_id,
        InventoryItem.character_id.is_(None)
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found in loot pool")
    db.delete(item)
    db.commit()


@router.post("/{campaign_id}/loot-pool/{item_id}/award")
async def award_loot_pool_item(
    campaign_id: UUID,
    item_id: UUID,
    req: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """SW clones an item from the loot pool to a character. Original stays in pool."""
    _require_sw(campaign_id, current_user, db)

    source = db.query(InventoryItem).filter(
        InventoryItem.id == item_id,
        InventoryItem.campaign_id == campaign_id,
        InventoryItem.character_id.is_(None)
    ).first()
    if not source:
        raise HTTPException(status_code=404, detail="Item not found in loot pool")

    target_id = req.get("character_id")
    if not target_id:
        raise HTTPException(status_code=422, detail="character_id is required")

    from uuid import UUID as _UUID
    target = db.query(Character).filter(
        Character.id == _UUID(str(target_id)),
        Character.campaign_id == campaign_id
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="Character not found in campaign")

    qty = max(1, int(req.get("quantity", source.quantity)))

    clone = InventoryItem(
        character_id = target.id,
        campaign_id  = campaign_id,
        name         = source.name,
        item_type    = source.item_type,
        quantity     = qty,
        description  = source.description,
        tier         = source.tier,
        effect_type  = source.effect_type,
        bonus        = source.bonus,
        bonus_type   = source.bonus_type,
        given_by_sw  = True,
    )
    db.add(clone)
    db.commit()
    db.refresh(clone)

    try:
        from routes.campaign_websocket import manager
        import asyncio
        asyncio.create_task(manager.broadcast(str(campaign_id), {
            "type":         "item_added",
            "character_id": str(target.id),
            "item":         _item_dict(clone),
            "given_by_sw":  True,
            "given_to":     target.name,
        }))
    except Exception:
        pass

    return _item_dict(clone)


@router.delete("/{campaign_id}", status_code=204)
async def delete_campaign(
    campaign_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """SW deletes a campaign. Notifies all members via push before deletion."""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if str(campaign.story_weaver_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Only the Story Weaver can delete a campaign")

    campaign_name = campaign.name

    # Notify all members before deletion
    try:
        from backend.notifications import send_push_to_campaign
        send_push_to_campaign(
            db=db,
            campaign_id=str(campaign_id),
            exclude_user_id=str(current_user.id),
            title="📢 Campaign Deleted",
            body=f'"{campaign_name}" has been deleted by the Story Weaver.',
            url="/campaigns.html",
        )
    except Exception as _e:
        import logging
        logging.getLogger(__name__).warning(f"Push failed on campaign delete: {_e}")

    # Manually delete characters (and their abilities — FK cascades from character).
    # The FK on characters.campaign_id is SET NULL, not CASCADE, so we must do this explicitly.
    characters = db.query(Character).filter(Character.campaign_id == campaign_id).all()
    for char in characters:
        db.delete(char)

    # Messages have no FK to campaigns (plain UUID column), so they orphan without this.
    db.query(Message).filter(Message.campaign_id == str(campaign_id)).delete(synchronize_session=False)

    db.delete(campaign)
    db.commit()


# ============================================================
# Memory Echoes
# ============================================================

def _echo_dict(echo) -> dict:
    return {
        "id": str(echo.id),
        "campaign_id": str(echo.campaign_id),
        "character_id": str(echo.character_id) if echo.character_id else None,
        "character_name": echo.character_name,
        "echo_text": echo.echo_text,
        "created_at": echo.created_at.isoformat() if echo.created_at else None,
    }


@router.get("/{campaign_id}/memory-echoes")
async def list_memory_echoes(
    campaign_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Return all memory echoes for a campaign (all members)."""
    membership = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == campaign_id,
        CampaignMembership.user_id == current_user.id,
        CampaignMembership.left_at.is_(None)
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this campaign")
    from backend.models import MemoryEcho
    echoes = db.query(MemoryEcho).filter(
        MemoryEcho.campaign_id == campaign_id
    ).order_by(MemoryEcho.created_at.asc()).all()
    return [_echo_dict(e) for e in echoes]


@router.post("/{campaign_id}/memory-echoes", status_code=201)
async def create_memory_echo(
    campaign_id: UUID,
    req: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """SW saves a memory echo for a fallen character."""
    _require_sw(campaign_id, current_user, db)
    from backend.models import MemoryEcho
    from uuid import UUID as _UUID

    character_name = (req.get("character_name") or "Unknown").strip()[:200]
    echo_text = (req.get("echo_text") or "").strip()
    if not echo_text:
        raise HTTPException(status_code=400, detail="echo_text is required")
    char_id_raw = req.get("character_id")
    character_id = _UUID(char_id_raw) if char_id_raw else None

    echo = MemoryEcho(
        campaign_id=campaign_id,
        character_id=character_id,
        character_name=character_name,
        echo_text=echo_text,
        created_by_user_id=current_user.id,
    )
    db.add(echo)
    db.commit()
    db.refresh(echo)

    try:
        from routes.campaign_websocket import manager
        import asyncio
        asyncio.create_task(manager.broadcast(str(campaign_id), {
            "type": "memory_echo_created",
            "echo": _echo_dict(echo),
        }))
    except Exception:
        pass

    return _echo_dict(echo)


# ─── Initiative State (REST) ───────────────────────────────────────────────────

@router.get("/{campaign_id}/initiative-state")
async def get_initiative_state(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the active encounter's initiative order for page-load hydration."""
    from backend.models import Encounter, InitiativeRoll
    from routes.campaign_websocket import _sort_initiative_rolls

    membership = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == campaign_id,
        CampaignMembership.user_id == current_user.id,
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this campaign")

    encounter = db.query(Encounter).filter(
        Encounter.campaign_id == campaign_id,
        Encounter.is_active == True,
    ).first()

    if not encounter:
        return {"active": False, "rolls": [], "current_turn_index": 0}

    all_rolls = db.query(InitiativeRoll).filter(
        InitiativeRoll.encounter_id == encounter.id
    ).all()
    all_rolls = _sort_initiative_rolls(all_rolls, db)

    is_sw = membership.role == "story_weaver"
    result = []
    for roll in all_rolls:
        if roll.is_silent and not is_sw:
            continue
        entry = {
            "name": roll.name,
            "roll": roll.roll_result,
            "is_silent": roll.is_silent,
            "rolled_by_sw": roll.rolled_by_sw,
            "character_id": str(roll.character_id) if roll.character_id else None,
            "is_npc": roll.npc_id is not None,
            "dp": None,
            "max_dp": None,
            "user_id": None,
        }
        if roll.character_id:
            char = db.query(Character).filter(Character.id == roll.character_id).first()
            if char:
                entry["dp"] = char.dp
                entry["max_dp"] = char.max_dp
                entry["user_id"] = str(char.user_id) if char.user_id else None
        result.append(entry)

    return {
        "active": True,
        "rolls": result,
        "current_turn_index": encounter.current_turn_index,
    }
