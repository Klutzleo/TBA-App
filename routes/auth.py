"""
Authentication Routes

Handles user registration, login, password reset, and profile management.
"""

from datetime import datetime, timedelta
from typing import Optional
import re
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
from uuid import UUID

from backend.db import get_db
from backend.models import User, PasswordResetToken
from backend.auth.jwt import create_access_token, get_current_user
from backend.email_service import send_password_reset_email

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Create router
auth_router = APIRouter(prefix="/api/auth", tags=["authentication"])


# ==================== REQUEST/RESPONSE MODELS ====================

class RegisterRequest(BaseModel):
    """User registration request."""
    email: EmailStr
    username: str
    password: str

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format."""
        if len(v) < 3 or len(v) > 20:
            raise ValueError('Username must be 3-20 characters')
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username can only contain letters, numbers, hyphens, and underscores')
        return v

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v


class LoginRequest(BaseModel):
    """User login request."""
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Login/registration response with JWT token."""
    access_token: str
    token_type: str = "bearer"
    user_id: UUID
    username: str
    email: str


class UserProfileResponse(BaseModel):
    """User profile response."""
    user_id: UUID
    username: str
    email: str
    created_at: datetime


class ForgotPasswordRequest(BaseModel):
    """Password reset request."""
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Password reset with token."""
    token: str
    new_password: str

    @field_validator('new_password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate new password strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v


class ChangePasswordRequest(BaseModel):
    """Change password for logged-in user."""
    current_password: str
    new_password: str

    @field_validator('new_password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate new password strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str


# ==================== ENDPOINTS ====================

@auth_router.post("/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/hour")
async def register(
    request: Request,
    data: RegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new user account.

    Rate limit: 10 registrations per hour per IP.

    Returns:
        LoginResponse with JWT token and user info

    Raises:
        400: Email or username already exists
        400: Validation error (weak password, invalid username)
    """
    # Normalize email to lowercase for case-insensitive comparison
    email_lower = data.email.lower()

    # Check if email already exists
    existing_email = db.query(User).filter(User.email == email_lower).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to create account. Please check your information and try again."
        )

    # Check if username already exists
    existing_username = db.query(User).filter(User.username == data.username).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )

    # Create new user (use lowercase email)
    new_user = User(
        email=email_lower,
        username=data.username,
        hashed_password=User.hash_password(data.password),
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Generate JWT token (convert UUID to string for JSON serialization)
    access_token = create_access_token(
        user_id=str(new_user.id),
        email=new_user.email,
        username=new_user.username
    )

    return LoginResponse(
        access_token=access_token,
        user_id=str(new_user.id),
        username=new_user.username,
        email=new_user.email
    )


@auth_router.post("/login", response_model=LoginResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    data: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Login with email and password.

    Rate limit: 5 login attempts per minute per IP.

    Returns:
        LoginResponse with JWT token and user info

    Raises:
        401: Invalid email or password
    """
    # Normalize email to lowercase for case-insensitive comparison
    email_lower = data.email.lower()

    # Find user by email
    user = db.query(User).filter(User.email == email_lower).first()

    # Verify password (use constant-time comparison to prevent timing attacks)
    if not user or not user.verify_password(data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Check if account is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled"
        )

    # Update last login timestamp
    user.last_login = datetime.utcnow()
    db.commit()

    # Generate JWT token (convert UUID to string for JSON serialization)
    access_token = create_access_token(
        user_id=str(user.id),
        email=user.email,
        username=user.username
    )

    return LoginResponse(
        access_token=access_token,
        user_id=str(user.id),
        username=user.username,
        email=user.email
    )


@auth_router.get("/me", response_model=UserProfileResponse)
async def get_profile(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user profile.

    Requires: Bearer token in Authorization header

    Returns:
        User profile information

    Raises:
        401: Invalid or missing token
    """
    return UserProfileResponse(
        user_id=str(current_user.id),
        username=current_user.username,
        email=current_user.email,
        created_at=current_user.created_at
    )


@auth_router.post("/forgot-password", response_model=MessageResponse)
@limiter.limit("3/hour")
async def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Request a password reset email.

    Rate limit: 3 requests per hour per IP.

    Always returns success message (even if email doesn't exist)
    to prevent email enumeration attacks.

    Returns:
        Generic success message
    """
    # Normalize email to lowercase for case-insensitive comparison
    email_lower = data.email.lower()

    # Find user by email
    user = db.query(User).filter(User.email == email_lower).first()

    if user:
        # Delete any existing unused reset tokens for this user
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used == False
        ).delete()

        # Create new reset token (expires in 1 hour)
        reset_token = PasswordResetToken.create_for_user(
            user_id=user.id,
            hours_valid=1
        )

        db.add(reset_token)
        db.commit()

        # Send password reset email
        send_password_reset_email(
            to_email=user.email,
            reset_token=reset_token.token
        )

    # Always return the same message (don't reveal if email exists)
    return MessageResponse(
        message="If that email exists in our system, a password reset link has been sent"
    )


@auth_router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    data: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Reset password using a reset token.

    Returns:
        Success message

    Raises:
        400: Invalid, expired, or used token
    """
    # Find reset token
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == data.token
    ).first()

    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )

    # Check if token is valid
    if not reset_token.is_valid():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired or been used"
        )

    # Get the user
    user = db.query(User).filter(User.id == reset_token.user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Update user's password
    user.set_password(data.new_password)
    user.updated_at = datetime.utcnow()

    # Mark token as used
    reset_token.mark_used()

    db.commit()

    return MessageResponse(
        message="Password has been reset successfully"
    )


@auth_router.post("/change-password", response_model=MessageResponse)
async def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Change password for logged-in user.

    Requires: Bearer token in Authorization header

    Returns:
        Success message

    Raises:
        401: Current password is incorrect
        401: Invalid or missing token
    """
    # Verify current password
    if not current_user.verify_password(data.current_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )

    # Update password
    current_user.set_password(data.new_password)
    current_user.updated_at = datetime.utcnow()

    db.commit()

    return MessageResponse(
        message="Password has been changed successfully"
    )


@auth_router.post("/logout", response_model=MessageResponse)
async def logout():
    """
    Logout (client-side operation).

    JWT tokens are stateless, so logout is handled client-side
    by deleting the token from storage.

    Returns:
        Success message
    """
    return MessageResponse(
        message="Logged out successfully"
    )
