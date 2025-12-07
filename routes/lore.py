"""
Lore routes (stub for compatibility).
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/lore", tags=["Lore"])


@router.get("/")
async def get_lore():
    """Placeholder lore endpoint."""
    return {"message": "Lore system coming soon"}


def add_lore_entry(entry):
    """Stub function for backward compatibility."""
    pass

