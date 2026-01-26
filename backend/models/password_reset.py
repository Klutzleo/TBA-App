"""
PasswordResetToken model for password reset functionality.

Handles secure password reset tokens with expiration.
"""
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, timedelta
from backend.db import Base


class PasswordResetToken(Base):
    """
    Password reset token for secure password recovery.

    Tokens are single-use and expire after a set time period.
    """
    __tablename__ = "password_reset_tokens"
    __table_args__ = {'extend_existing': True}

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    token = Column(String, unique=True, nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="password_reset_tokens")

    def __repr__(self):
        return f"<PasswordResetToken(id={self.id[:8]}..., user_id={self.user_id[:8]}..., used={self.used})>"

    @staticmethod
    def generate_token() -> str:
        """Generate a secure random token for password reset."""
        return str(uuid.uuid4())

    @staticmethod
    def create_for_user(user_id: str, hours_valid: int = 24) -> 'PasswordResetToken':
        """
        Create a new password reset token for a user.

        Args:
            user_id: The user's ID
            hours_valid: How many hours the token should be valid (default 24)

        Returns:
            A new PasswordResetToken instance (not yet committed to database)
        """
        token = PasswordResetToken.generate_token()
        expires_at = datetime.utcnow() + timedelta(hours=hours_valid)

        return PasswordResetToken(
            token=token,
            user_id=user_id,
            expires_at=expires_at,
            used=False
        )

    def is_valid(self) -> bool:
        """Check if the token is still valid (not used and not expired)."""
        if self.used:
            return False
        if datetime.utcnow() > self.expires_at:
            return False
        return True

    def mark_used(self):
        """Mark the token as used."""
        self.used = True
