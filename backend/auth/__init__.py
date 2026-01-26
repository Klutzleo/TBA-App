"""
Authentication module for TBA-App.

Provides JWT token generation, verification, and authentication dependencies.
"""

from .jwt import (
    create_access_token,
    verify_token,
    get_current_user,
    require_story_weaver,
    TokenData,
)

__all__ = [
    'create_access_token',
    'verify_token',
    'get_current_user',
    'require_story_weaver',
    'TokenData',
]
