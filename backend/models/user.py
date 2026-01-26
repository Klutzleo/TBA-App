"""
User model for authentication.

Handles user accounts, password hashing, and authentication.
"""
from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from passlib.context import CryptContext
from backend.db import Base

# Password hashing context using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class User(Base):
    """
    User account for authentication.

    Users can own characters and campaigns, and be designated as Story Weavers.
    """
    __tablename__ = "users"
    __table_args__ = {'extend_existing': True}

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships (will be populated when other models are updated)
    characters = relationship("Character", back_populates="user", foreign_keys="[Character.user_id]")
    created_campaigns = relationship("Campaign", back_populates="creator", foreign_keys="[Campaign.created_by_user_id]")
    story_weaver_campaigns = relationship("Campaign", back_populates="story_weaver", foreign_keys="[Campaign.story_weaver_id]")
    password_reset_tokens = relationship("PasswordResetToken", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id[:8]}..., email={self.email}, username={self.username})>"

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a plain text password using bcrypt."""
        return pwd_context.hash(password)

    def verify_password(self, password: str) -> bool:
        """Verify a plain text password against the hashed password."""
        return pwd_context.verify(password, self.hashed_password)

    def set_password(self, password: str):
        """Set the user's password (hashes it automatically)."""
        self.hashed_password = self.hash_password(password)
