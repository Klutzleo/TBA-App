"""
Campaign Routes - Create and manage campaigns
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List
import uuid

from backend.database import get_db
from backend.models import Campaign, Party, Character, PartyMembership

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


class CampaignCreate(BaseModel):
    """Request to create a new campaign."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    story_weaver_id: Optional[str] = Field(None, description="Character ID of the Story Weaver")
    created_by_id: str = Field(..., description="User ID who is creating this campaign")


class CampaignResponse(BaseModel):
    """Campaign response."""
    id: str
    name: str
    description: Optional[str]
    story_weaver_id: Optional[str]
    created_by_id: str
    is_active: bool
    story_channel_id: Optional[str] = None
    ooc_channel_id: Optional[str] = None

    class Config:
        from_attributes = True


@router.post("/create", response_model=CampaignResponse)
def create_campaign(req: CampaignCreate, db: Session = Depends(get_db)):
    """
    Create a new campaign.

    Automatically creates:
    - Story channel (main gameplay)
    - OOC channel (out-of-character chat)

    Returns the campaign with channel IDs.
    """
    # Create campaign
    campaign = Campaign(
        id=str(uuid.uuid4()),
        name=req.name,
        description=req.description,
        story_weaver_id=req.story_weaver_id,
        created_by_id=req.created_by_id,
        is_active=True
    )

    db.add(campaign)
    db.flush()  # Flush to trigger the auto-create channels trigger

    # Query the auto-created channels
    story_channel = db.query(Party).filter(
        Party.campaign_id == campaign.id,
        Party.party_type == 'story'
    ).first()

    ooc_channel = db.query(Party).filter(
        Party.campaign_id == campaign.id,
        Party.party_type == 'ooc'
    ).first()

    db.commit()
    db.refresh(campaign)

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
