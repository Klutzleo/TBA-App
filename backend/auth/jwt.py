"""
JWT Authentication System for TBA-App.

Handles token creation, verification, and authentication dependencies.
"""

import os
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.db import get_db
from backend.models import User, Campaign

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

# Security scheme for Bearer token
security = HTTPBearer()


class TokenData(BaseModel):
    """Token payload data."""
    user_id: str
    email: str
    username: str


def create_access_token(user_id: str, email: str, username: str) -> str:
    """
    Create a JWT access token for a user.

    Args:
        user_id: The user's ID
        email: The user's email
        username: The user's username

    Returns:
        JWT token string

    Example:
        token = create_access_token(user.id, user.email, user.username)
    """
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)

    payload = {
        "sub": user_id,  # Subject (user ID)
        "email": email,
        "username": username,
        "exp": expire,
        "iat": datetime.utcnow(),  # Issued at
    }

    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token


def verify_token(token: str) -> Optional[TokenData]:
    """
    Verify and decode a JWT token.

    Args:
        token: JWT token string

    Returns:
        TokenData if valid, None if invalid

    Example:
        token_data = verify_token(token)
        if token_data:
            print(f"User ID: {token_data.user_id}")
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        user_id: str = payload.get("sub")
        email: str = payload.get("email")
        username: str = payload.get("username")

        if user_id is None:
            return None

        return TokenData(
            user_id=user_id,
            email=email,
            username=username
        )

    except JWTError:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    FastAPI dependency to get the current authenticated user from Bearer token.

    Extracts user from JWT token in Authorization header.

    Args:
        credentials: HTTP Authorization credentials (Bearer token)
        db: Database session

    Returns:
        User object if authenticated

    Raises:
        HTTPException 401: If token is invalid or user not found
        HTTPException 403: If user account is inactive

    Example:
        @router.get("/profile")
        def get_profile(current_user: User = Depends(get_current_user)):
            return {"user": current_user.username}
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Extract token from credentials
    token = credentials.credentials

    # Verify and decode token
    token_data = verify_token(token)
    if token_data is None:
        raise credentials_exception

    # Fetch user from database
    user = db.query(User).filter(User.id == token_data.user_id).first()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    FastAPI dependency to optionally get the current user.

    Returns None if no token provided or token is invalid.
    Useful for endpoints that work both authenticated and unauthenticated.

    Args:
        credentials: Optional HTTP Authorization credentials
        db: Database session

    Returns:
        User object if authenticated, None otherwise

    Example:
        @router.get("/content")
        def get_content(current_user: Optional[User] = Depends(get_current_user_optional)):
            if current_user:
                return {"message": f"Hello {current_user.username}"}
            else:
                return {"message": "Hello guest"}
    """
    if credentials is None:
        return None

    try:
        token = credentials.credentials
        token_data = verify_token(token)

        if token_data is None:
            return None

        user = db.query(User).filter(User.id == token_data.user_id).first()

        if user is None or not user.is_active:
            return None

        return user

    except Exception:
        return None


def require_story_weaver(campaign_id: str):
    """
    FastAPI dependency factory to check if current user is Story Weaver for a campaign.

    Args:
        campaign_id: The campaign ID to check

    Returns:
        A dependency function that verifies SW status

    Raises:
        HTTPException 403: If user is not the Story Weaver
        HTTPException 404: If campaign not found

    Example:
        @router.post("/campaigns/{campaign_id}/start-combat")
        def start_combat(
            campaign_id: str,
            current_user: User = Depends(get_current_user),
            _: None = Depends(require_story_weaver(campaign_id))
        ):
            # Only Story Weaver can reach this code
            return {"message": "Combat started"}
    """
    async def check_story_weaver(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        # Fetch campaign
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()

        if campaign is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Campaign {campaign_id} not found"
            )

        # Check if current user is the Story Weaver
        if campaign.story_weaver_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the Story Weaver can perform this action"
            )

        return None

    return check_story_weaver


def require_campaign_access(campaign_id: str):
    """
    FastAPI dependency factory to check if user has access to a campaign.

    User has access if they:
    - Are the Story Weaver
    - Are the creator
    - Have a character in the campaign

    Args:
        campaign_id: The campaign ID to check

    Returns:
        A dependency function that verifies access

    Raises:
        HTTPException 403: If user doesn't have access
        HTTPException 404: If campaign not found

    Example:
        @router.get("/campaigns/{campaign_id}")
        def get_campaign(
            campaign_id: str,
            current_user: User = Depends(get_current_user),
            _: None = Depends(require_campaign_access(campaign_id))
        ):
            # User has access to this campaign
            return {"campaign_id": campaign_id}
    """
    async def check_campaign_access(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        from backend.models import Character, PartyMembership, Party

        # Fetch campaign
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()

        if campaign is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Campaign {campaign_id} not found"
            )

        # Check if user is SW or creator
        if campaign.story_weaver_id == current_user.id or campaign.created_by_user_id == current_user.id:
            return None

        # Check if user has a character in any party in this campaign
        user_characters = db.query(Character).filter(Character.user_id == current_user.id).all()
        character_ids = [char.id for char in user_characters]

        if character_ids:
            # Get all parties in this campaign
            campaign_parties = db.query(Party).filter(Party.campaign_id == campaign_id).all()
            party_ids = [party.id for party in campaign_parties]

            # Check if any user character is in any campaign party
            membership = db.query(PartyMembership).filter(
                PartyMembership.character_id.in_(character_ids),
                PartyMembership.party_id.in_(party_ids)
            ).first()

            if membership:
                return None

        # User doesn't have access
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this campaign"
        )

    return check_campaign_access
