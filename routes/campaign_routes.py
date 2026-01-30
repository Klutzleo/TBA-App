"""
Campaign Routes - Create and manage campaigns
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List
import uuid
import random
import string

from backend.db import get_db
from backend.models import Campaign, Party, Character, PartyMembership, Message, User
from backend.auth.jwt import get_current_user

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


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
    id: str
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

    class Config:
        from_attributes = True


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
        id=str(uuid.uuid4()),
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
        is_active=campaign.is_active
    )


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
    db: Session = Depends(get_db)
):
    """
    Get recent message history for a campaign.

    Returns messages from all channels in the campaign, sorted by timestamp.
    Used to restore chat history when a user connects.
    """
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()

    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Get all messages for this campaign, sorted by time
    messages = db.query(Message)\
        .filter(Message.campaign_id == campaign_id)\
        .order_by(Message.created_at.asc())\
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
                "message_type": msg.message_type,
                "mode": msg.mode,
                "timestamp": msg.created_at.isoformat() if msg.created_at else None
            }
            for msg in messages
        ]
    }
