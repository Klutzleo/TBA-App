"""
Campaign Management Routes

Handles campaign creation, browsing, joining, and management.
Users can create campaigns, join via codes, and Story Weavers have special permissions.
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from backend.db import get_db
from backend.models import Campaign, CampaignMembership, User, generate_join_code
from backend.auth.jwt import get_current_user

# Create router
campaigns_router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


# ==================== REQUEST/RESPONSE MODELS ====================

class CreateCampaignRequest(BaseModel):
    """Campaign creation request."""
    name: str
    description: str
    is_public: bool = True
    min_players: int = 2
    max_players: int = 6
    timezone: str = "America/New_York"
    posting_frequency: str = "medium"

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate campaign name."""
        if len(v) < 3 or len(v) > 100:
            raise ValueError('Campaign name must be 3-100 characters')
        return v

    @field_validator('description')
    @classmethod
    def validate_description(cls, v: str) -> str:
        """Validate campaign description."""
        if len(v) < 10 or len(v) > 2000:
            raise ValueError('Description must be 10-2000 characters')
        return v

    @field_validator('posting_frequency')
    @classmethod
    def validate_posting_frequency(cls, v: str) -> str:
        """Validate posting frequency."""
        if v not in ['slow', 'medium', 'high']:
            raise ValueError('Posting frequency must be slow, medium, or high')
        return v

    @field_validator('min_players')
    @classmethod
    def validate_min_players(cls, v: int) -> int:
        """Validate minimum players."""
        if v < 2 or v > 20:
            raise ValueError('Minimum players must be 2-20')
        return v

    @field_validator('max_players')
    @classmethod
    def validate_max_players(cls, v: int) -> int:
        """Validate maximum players."""
        if v < 2 or v > 20:
            raise ValueError('Maximum players must be 2-20')
        return v


class UpdateCampaignRequest(BaseModel):
    """Campaign update request (Story Weaver only)."""
    name: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None
    min_players: Optional[int] = None
    max_players: Optional[int] = None
    timezone: Optional[str] = None
    posting_frequency: Optional[str] = None
    status: Optional[str] = None

    @field_validator('status')
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        """Validate campaign status."""
        if v is not None and v not in ['active', 'archived', 'on_break']:
            raise ValueError('Status must be active, archived, or on_break')
        return v


class JoinCampaignRequest(BaseModel):
    """Join campaign request."""
    join_code: str

    @field_validator('join_code')
    @classmethod
    def validate_join_code(cls, v: str) -> str:
        """Validate join code format."""
        v = v.upper().strip()
        if len(v) != 6:
            raise ValueError('Join code must be 6 characters')
        if not v.isalnum():
            raise ValueError('Join code must contain only letters and numbers')
        return v


class KickPlayerRequest(BaseModel):
    """Kick player request."""
    user_id: str


class CampaignMemberResponse(BaseModel):
    """Campaign member info."""
    user_id: str
    username: str
    email: str
    role: str
    joined_at: datetime


class CampaignResponse(BaseModel):
    """Campaign response with details."""
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
    created_by_user_id: str
    story_weaver_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    member_count: int
    user_role: Optional[str] = None  # User's role in this campaign


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str


# ==================== HELPER FUNCTIONS ====================

def get_user_role_in_campaign(db: Session, campaign_id: str, user_id: str) -> Optional[str]:
    """Get user's role in a campaign (or None if not a member)."""
    membership = db.query(CampaignMembership).filter(
        and_(
            CampaignMembership.campaign_id == campaign_id,
            CampaignMembership.user_id == user_id,
            CampaignMembership.left_at == None
        )
    ).first()
    return membership.role if membership else None


def is_story_weaver(db: Session, campaign_id: str, user_id: str) -> bool:
    """Check if user is the Story Weaver for this campaign."""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        return False
    return campaign.story_weaver_id == user_id


def ensure_unique_join_code(db: Session) -> str:
    """Generate a unique join code."""
    for _ in range(100):  # Try up to 100 times
        code = generate_join_code()
        existing = db.query(Campaign).filter(Campaign.join_code == code).first()
        if not existing:
            return code
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to generate unique join code"
    )


# ==================== ENDPOINTS ====================

@campaigns_router.post("/create", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    data: CreateCampaignRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new campaign.

    Requires: Bearer token in Authorization header

    Returns:
        Campaign details with join code

    Raises:
        400: Validation error (min_players > max_players, etc.)
        401: Invalid or missing token
    """
    # Validate player limits
    if data.min_players > data.max_players:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Minimum players cannot exceed maximum players"
        )

    # Generate unique join code
    join_code = ensure_unique_join_code(db)

    # Create campaign
    campaign = Campaign(
        name=data.name,
        description=data.description,
        created_by_user_id=current_user.id,
        story_weaver_id=current_user.id,  # Creator is default Story Weaver
        join_code=join_code,
        is_public=data.is_public,
        min_players=data.min_players,
        max_players=data.max_players,
        timezone=data.timezone,
        posting_frequency=data.posting_frequency,
        status='active',
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    # Add creator as member with story_weaver role
    membership = CampaignMembership(
        campaign_id=campaign.id,
        user_id=current_user.id,
        role='story_weaver',
        joined_at=datetime.utcnow()
    )

    db.add(membership)
    db.commit()

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
        created_by_user_id=campaign.created_by_user_id,
        story_weaver_id=campaign.story_weaver_id,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
        member_count=1,
        user_role='story_weaver'
    )


@campaigns_router.get("", response_model=List[CampaignResponse])
async def get_my_campaigns(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all campaigns the current user is a member of.

    Requires: Bearer token in Authorization header

    Returns:
        List of campaigns with member counts and user's role

    Raises:
        401: Invalid or missing token
    """
    # Get active memberships for current user
    memberships = db.query(CampaignMembership).filter(
        and_(
            CampaignMembership.user_id == current_user.id,
            CampaignMembership.left_at == None
        )
    ).all()

    campaigns = []
    for membership in memberships:
        campaign = db.query(Campaign).filter(Campaign.id == membership.campaign_id).first()
        if campaign:
            # Count active members
            member_count = db.query(CampaignMembership).filter(
                and_(
                    CampaignMembership.campaign_id == campaign.id,
                    CampaignMembership.left_at == None
                )
            ).count()

            campaigns.append(CampaignResponse(
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
                created_by_user_id=campaign.created_by_user_id,
                story_weaver_id=campaign.story_weaver_id,
                created_at=campaign.created_at,
                updated_at=campaign.updated_at,
                member_count=member_count,
                user_role=membership.role
            ))

    # Sort by updated_at descending (most recently updated first)
    campaigns.sort(key=lambda c: c.updated_at, reverse=True)

    return campaigns


@campaigns_router.get("/browse", response_model=List[CampaignResponse])
async def browse_public_campaigns(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Browse public campaigns (excluding campaigns user is already in).

    Requires: Bearer token in Authorization header

    Returns:
        List of public campaigns available to join

    Raises:
        401: Invalid or missing token
    """
    # Get campaigns user is already in
    user_campaign_ids = [
        m.campaign_id for m in
        db.query(CampaignMembership.campaign_id).filter(
            and_(
                CampaignMembership.user_id == current_user.id,
                CampaignMembership.left_at == None
            )
        ).all()
    ]

    # Get public campaigns user is NOT in
    query = db.query(Campaign).filter(
        and_(
            Campaign.is_public == True,
            Campaign.status == 'active'
        )
    )

    if user_campaign_ids:
        query = query.filter(Campaign.id.notin_(user_campaign_ids))

    public_campaigns = query.all()

    campaigns = []
    for campaign in public_campaigns:
        # Count active members
        member_count = db.query(CampaignMembership).filter(
            and_(
                CampaignMembership.campaign_id == campaign.id,
                CampaignMembership.left_at == None
            )
        ).count()

        # Skip if campaign is full
        if member_count >= campaign.max_players:
            continue

        campaigns.append(CampaignResponse(
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
            created_by_user_id=campaign.created_by_user_id,
            story_weaver_id=campaign.story_weaver_id,
            created_at=campaign.created_at,
            updated_at=campaign.updated_at,
            member_count=member_count,
            user_role=None
        ))

    # Sort by created_at descending (newest first)
    campaigns.sort(key=lambda c: c.created_at, reverse=True)

    return campaigns


@campaigns_router.post("/join", response_model=CampaignResponse)
async def join_campaign(
    data: JoinCampaignRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Join a campaign using a join code.

    Requires: Bearer token in Authorization header

    Returns:
        Campaign details

    Raises:
        400: Invalid join code, campaign full, or already a member
        401: Invalid or missing token
        404: Campaign not found
    """
    # Find campaign by join code
    campaign = db.query(Campaign).filter(Campaign.join_code == data.join_code).first()

    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found with that join code"
        )

    # Check if campaign is active
    if campaign.status != 'active':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Campaign is {campaign.status} and not accepting new members"
        )

    # Check if already a member
    existing_membership = db.query(CampaignMembership).filter(
        and_(
            CampaignMembership.campaign_id == campaign.id,
            CampaignMembership.user_id == current_user.id,
            CampaignMembership.left_at == None
        )
    ).first()

    if existing_membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are already a member of this campaign"
        )

    # Count current members
    member_count = db.query(CampaignMembership).filter(
        and_(
            CampaignMembership.campaign_id == campaign.id,
            CampaignMembership.left_at == None
        )
    ).count()

    # Check if campaign is full
    if member_count >= campaign.max_players:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Campaign is full ({member_count}/{campaign.max_players} players)"
        )

    # Create membership
    membership = CampaignMembership(
        campaign_id=campaign.id,
        user_id=current_user.id,
        role='player',
        joined_at=datetime.utcnow()
    )

    db.add(membership)
    db.commit()

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
        created_by_user_id=campaign.created_by_user_id,
        story_weaver_id=campaign.story_weaver_id,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
        member_count=member_count + 1,
        user_role='player'
    )


@campaigns_router.delete("/{campaign_id}/leave", response_model=MessageResponse)
async def leave_campaign(
    campaign_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Leave a campaign.

    Requires: Bearer token in Authorization header

    Returns:
        Success message

    Raises:
        400: Story Weaver cannot leave (must transfer role or delete campaign)
        401: Invalid or missing token
        404: Campaign not found or user is not a member
    """
    # Find active membership
    membership = db.query(CampaignMembership).filter(
        and_(
            CampaignMembership.campaign_id == campaign_id,
            CampaignMembership.user_id == current_user.id,
            CampaignMembership.left_at == None
        )
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You are not a member of this campaign"
        )

    # Check if user is Story Weaver
    if membership.role == 'story_weaver':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Story Weaver cannot leave campaign. Transfer Story Weaver role or delete campaign instead."
        )

    # Mark membership as left
    membership.left_at = datetime.utcnow()
    db.commit()

    return MessageResponse(message="Successfully left campaign")


@campaigns_router.put("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: str,
    data: UpdateCampaignRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update campaign settings (Story Weaver only).

    Requires: Bearer token in Authorization header + Story Weaver role

    Returns:
        Updated campaign details

    Raises:
        401: Invalid or missing token
        403: User is not the Story Weaver
        404: Campaign not found
    """
    # Find campaign
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()

    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )

    # Check if user is Story Weaver
    if not is_story_weaver(db, campaign_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the Story Weaver can update campaign settings"
        )

    # Update fields if provided
    if data.name is not None:
        campaign.name = data.name
    if data.description is not None:
        campaign.description = data.description
    if data.is_public is not None:
        campaign.is_public = data.is_public
    if data.min_players is not None:
        campaign.min_players = data.min_players
    if data.max_players is not None:
        campaign.max_players = data.max_players
    if data.timezone is not None:
        campaign.timezone = data.timezone
    if data.posting_frequency is not None:
        campaign.posting_frequency = data.posting_frequency
    if data.status is not None:
        campaign.status = data.status

    campaign.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(campaign)

    # Get member count
    member_count = db.query(CampaignMembership).filter(
        and_(
            CampaignMembership.campaign_id == campaign.id,
            CampaignMembership.left_at == None
        )
    ).count()

    # Get user role
    user_role = get_user_role_in_campaign(db, campaign_id, current_user.id)

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
        created_by_user_id=campaign.created_by_user_id,
        story_weaver_id=campaign.story_weaver_id,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
        member_count=member_count,
        user_role=user_role
    )


@campaigns_router.delete("/{campaign_id}", response_model=MessageResponse)
async def delete_campaign(
    campaign_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a campaign (creator only).

    Requires: Bearer token in Authorization header + campaign creator

    Returns:
        Success message

    Raises:
        401: Invalid or missing token
        403: User is not the creator
        404: Campaign not found
    """
    # Find campaign
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()

    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )

    # Check if user is creator
    if campaign.created_by_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the campaign creator can delete the campaign"
        )

    # Delete campaign (cascade will delete memberships)
    db.delete(campaign)
    db.commit()

    return MessageResponse(message="Campaign deleted successfully")


@campaigns_router.post("/{campaign_id}/kick", response_model=MessageResponse)
async def kick_player(
    campaign_id: str,
    data: KickPlayerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Kick a player from the campaign (Story Weaver only).

    Requires: Bearer token in Authorization header + Story Weaver role

    Returns:
        Success message

    Raises:
        400: Cannot kick the Story Weaver
        401: Invalid or missing token
        403: User is not the Story Weaver
        404: Campaign or player not found
    """
    # Find campaign
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()

    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )

    # Check if user is Story Weaver
    if not is_story_weaver(db, campaign_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the Story Weaver can kick players"
        )

    # Cannot kick yourself
    if data.user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot kick yourself from the campaign"
        )

    # Find player's membership
    membership = db.query(CampaignMembership).filter(
        and_(
            CampaignMembership.campaign_id == campaign_id,
            CampaignMembership.user_id == data.user_id,
            CampaignMembership.left_at == None
        )
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player is not a member of this campaign"
        )

    # Mark membership as left
    membership.left_at = datetime.utcnow()
    db.commit()

    return MessageResponse(message="Player kicked successfully")


@campaigns_router.post("/{campaign_id}/regenerate-code", response_model=CampaignResponse)
async def regenerate_join_code(
    campaign_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Regenerate campaign join code (Story Weaver only).

    Useful when code has been shared publicly and needs to be changed.

    Requires: Bearer token in Authorization header + Story Weaver role

    Returns:
        Campaign details with new join code

    Raises:
        401: Invalid or missing token
        403: User is not the Story Weaver
        404: Campaign not found
    """
    # Find campaign
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()

    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )

    # Check if user is Story Weaver
    if not is_story_weaver(db, campaign_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the Story Weaver can regenerate the join code"
        )

    # Generate new unique join code
    new_code = ensure_unique_join_code(db)
    campaign.join_code = new_code
    campaign.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(campaign)

    # Get member count
    member_count = db.query(CampaignMembership).filter(
        and_(
            CampaignMembership.campaign_id == campaign.id,
            CampaignMembership.left_at == None
        )
    ).count()

    # Get user role
    user_role = get_user_role_in_campaign(db, campaign_id, current_user.id)

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
        created_by_user_id=campaign.created_by_user_id,
        story_weaver_id=campaign.story_weaver_id,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
        member_count=member_count,
        user_role=user_role
    )


@campaigns_router.get("/{campaign_id}/members", response_model=List[CampaignMemberResponse])
async def get_campaign_members(
    campaign_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get list of campaign members.

    Requires: Bearer token in Authorization header + campaign membership

    Returns:
        List of campaign members with roles

    Raises:
        401: Invalid or missing token
        403: User is not a member of this campaign
        404: Campaign not found
    """
    # Find campaign
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()

    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )

    # Check if user is a member
    user_role = get_user_role_in_campaign(db, campaign_id, current_user.id)
    if not user_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be a campaign member to view members"
        )

    # Get all active members
    memberships = db.query(CampaignMembership).filter(
        and_(
            CampaignMembership.campaign_id == campaign_id,
            CampaignMembership.left_at == None
        )
    ).all()

    members = []
    for membership in memberships:
        user = db.query(User).filter(User.id == membership.user_id).first()
        if user:
            members.append(CampaignMemberResponse(
                user_id=user.id,
                username=user.username,
                email=user.email,
                role=membership.role,
                joined_at=membership.joined_at
            ))

    # Sort by role (story_weaver first) then by joined_at
    members.sort(key=lambda m: (m.role != 'story_weaver', m.joined_at))

    return members
