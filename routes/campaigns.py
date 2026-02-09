"""
Campaign Routes - Create and manage campaigns
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID, uuid4
import random
import string

from backend.db import get_db
from backend.models import Campaign, Party, Character, PartyMembership, Message, User, CampaignMembership
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
    timezone: str = Field(..., min_length=1)


class CampaignResponse(BaseModel):
    """Campaign response (Phase 3)."""
    id: UUID
    name: str
    description: str
    join_code: str
    is_public: bool
    min_players: int
    max_players: int
    timezone: str
    posting_frequency: str
    status: str
    story_weaver_id: Optional[str] = None
    created_by_user_id: Optional[str] = None
    is_active: bool
    user_role: Optional[str] = None  # 'story_weaver' or 'player'
    member_count: Optional[int] = None  # Number of active members

    class Config:
        from_attributes = True


class JoinCampaignRequest(BaseModel):
    """Request to join a campaign by join code."""
    join_code: str


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

        result.append(CampaignResponse(
            id=c.id,
            name=c.name,
            description=c.description,
            join_code=c.join_code,
            is_public=c.is_public,
            min_players=c.min_players,
            max_players=c.max_players,
            timezone=c.timezone,
            posting_frequency=c.posting_frequency,
            status=c.status,
            story_weaver_id=str(c.story_weaver_id) if c.story_weaver_id else None,
            created_by_user_id=str(c.created_by_user_id) if c.created_by_user_id else None,
            is_active=c.is_active,
            user_role='story_weaver',
            member_count=member_count or 0
        ))

    # Add player campaigns (avoid duplicates if user is both SW and member)
    sw_campaign_ids = {c.id for c in sw_campaigns}
    for c in member_campaigns:
        if c.id not in sw_campaign_ids:
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
                timezone=c.timezone,
                posting_frequency=c.posting_frequency,
                status=c.status,
                story_weaver_id=str(c.story_weaver_id) if c.story_weaver_id else None,
                created_by_user_id=str(c.created_by_user_id) if c.created_by_user_id else None,
                is_active=c.is_active,
                user_role='player',
                member_count=member_count or 0
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
            timezone=c.timezone,
            posting_frequency=c.posting_frequency,
            status=c.status,
            story_weaver_id=str(c.story_weaver_id) if c.story_weaver_id else None,
            created_by_user_id=str(c.created_by_user_id) if c.created_by_user_id else None,
            is_active=c.is_active,
            user_role=None,  # Not showing role for browse
            member_count=member_count or 0
        ))

    return result


@router.post("/join")
def join_campaign(
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

    # Check if campaign is full
    member_count = db.query(func.count(CampaignMembership.id)).filter(
        CampaignMembership.campaign_id == campaign.id,
        CampaignMembership.left_at.is_(None)
    ).scalar()

    if member_count >= campaign.max_players:
        raise HTTPException(status_code=400, detail="Campaign is full")

    # Create membership
    membership = CampaignMembership(
        campaign_id=campaign.id,
        user_id=current_user.id,
        role="player"
    )
    db.add(membership)
    db.commit()

    return {"success": True, "message": f"Successfully joined {campaign.name}"}


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
        CampaignMembership.user_id == current_user.id
    ).first()
    
    if membership and membership.role == "story_weaver":
        return {"role": "story_weaver", "has_character": False}
    
    # Check if user has character in this campaign
    character = db.query(Character).filter(
        Character.user_id == current_user.id,
        Character.campaign_id == campaign_id
    ).first()
    
    if character:
        return {"role": "player", "has_character": True, "character_id": str(character.id)}
    return {"role": "player", "has_character": False}


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
        ooc_channel_id=ooc_channel.id if ooc_channel else None
    )

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
        CampaignMembership.campaign_id == campaign_id
    ).all()
    
    result = []
    for member in members:
        user = db.query(User).filter(User.id == member.user_id).first()
        character = db.query(Character).filter(
            Character.campaign_id == campaign_id,
            Character.user_id == member.user_id
        ).first()
        
        result.append({
            "user_id": str(user.id),
            "username": user.username,
            "role": member.role,
            "character": {
                "id": str(character.id),
                "name": character.name,
                "level": character.level,
                "dp": character.dp,
                "max_dp": character.max_dp,
                "edge": character.edge,
                "bap": character.bap,
                "pp": character.pp,
                "ip": character.ip,
                "sp": character.sp
            } if character else None
        })
    
    return result

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
    messages = db.query(Message)\
        .filter(Message.campaign_id == campaign_id)\
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
                "timestamp": msg.created_at.isoformat() if msg.created_at else None
            }
            for msg in messages
        ]
    }
