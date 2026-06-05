"""
routes/bonds.py
Bond management — SW declares/breaks bonds between characters.
"""
import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from backend.db import get_db
from backend.models import Bond, Character, Campaign, CampaignMembership, User
from routes.auth import get_current_user

logger = logging.getLogger(__name__)

bonds_router = APIRouter(prefix="/api/campaigns", tags=["Bonds"])


def _is_sw(campaign_id: UUID, user: User, db: Session) -> bool:
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    return campaign and str(campaign.created_by_user_id) == str(user.id)


def _bond_dict(bond: Bond, db: Session) -> dict:
    char_a = db.query(Character).filter(Character.id == bond.character_id_a).first()
    char_b = db.query(Character).filter(Character.id == bond.character_id_b).first()
    return {
        "id": str(bond.id),
        "campaign_id": str(bond.campaign_id),
        "character_id_a": str(bond.character_id_a),
        "character_id_b": str(bond.character_id_b),
        "character_name_a": char_a.name if char_a else "Unknown",
        "character_name_b": char_b.name if char_b else "Unknown",
        "combo_name": bond.combo_name,
        "combo_description": bond.combo_description,
        "created_at": bond.created_at.isoformat() if bond.created_at else None,
        "broken_at": bond.broken_at.isoformat() if bond.broken_at else None,
        "is_active": bond.is_active,
    }


class BondCreate(BaseModel):
    character_id_a: UUID
    character_id_b: UUID
    combo_name: Optional[str] = None
    combo_description: Optional[str] = None


class BondBreak(BaseModel):
    pass


# ── GET /api/campaigns/{id}/bonds ──────────────────────────────────
@bonds_router.get("/{campaign_id}/bonds")
async def list_bonds(
    campaign_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all active bonds in a campaign. Visible to all members."""
    bonds = db.query(Bond).filter(
        Bond.campaign_id == campaign_id,
        Bond.broken_at == None,  # noqa: E711
    ).all()
    return {"bonds": [_bond_dict(b, db) for b in bonds]}


# ── POST /api/campaigns/{id}/bonds ─────────────────────────────────
@bonds_router.post("/{campaign_id}/bonds")
async def create_bond(
    campaign_id: UUID,
    req: BondCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """SW declares a bond between two characters."""
    if not _is_sw(campaign_id, current_user, db):
        raise HTTPException(status_code=403, detail="Only the Story Weaver can declare bonds")

    # Validate both characters exist in this campaign
    char_a = db.query(Character).filter(
        Character.id == req.character_id_a,
        Character.campaign_id == str(campaign_id),
    ).first()
    char_b = db.query(Character).filter(
        Character.id == req.character_id_b,
        Character.campaign_id == str(campaign_id),
    ).first()

    if not char_a or not char_b:
        raise HTTPException(status_code=404, detail="One or both characters not found in this campaign")
    if str(req.character_id_a) == str(req.character_id_b):
        raise HTTPException(status_code=400, detail="A character cannot bond with themselves")

    # Check for existing active bond between these two
    existing = db.query(Bond).filter(
        Bond.campaign_id == campaign_id,
        Bond.broken_at == None,  # noqa: E711
    ).filter(
        ((Bond.character_id_a == req.character_id_a) & (Bond.character_id_b == req.character_id_b)) |
        ((Bond.character_id_a == req.character_id_b) & (Bond.character_id_b == req.character_id_a))
    ).first()

    if existing:
        raise HTTPException(status_code=409, detail="An active bond already exists between these characters")

    bond = Bond(
        campaign_id=campaign_id,
        character_id_a=req.character_id_a,
        character_id_b=req.character_id_b,
        combo_name=req.combo_name,
        combo_description=req.combo_description,
    )
    db.add(bond)
    db.commit()
    db.refresh(bond)

    logger.info(f"Bond created: {char_a.name} ↔ {char_b.name} in campaign {campaign_id}")
    return {"ok": True, "bond": _bond_dict(bond, db)}


# ── PATCH /api/campaigns/{id}/bonds/{bond_id} ──────────────────────
class BondUpdate(BaseModel):
    combo_name: Optional[str] = None
    combo_description: Optional[str] = None

@bonds_router.patch("/{campaign_id}/bonds/{bond_id}")
async def update_bond(
    campaign_id: UUID,
    bond_id: UUID,
    req: BondUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """SW updates combo name/description on an existing bond."""
    if not _is_sw(campaign_id, current_user, db):
        raise HTTPException(status_code=403, detail="Only the Story Weaver can update bonds")

    bond = db.query(Bond).filter(Bond.id == bond_id, Bond.campaign_id == campaign_id).first()
    if not bond:
        raise HTTPException(status_code=404, detail="Bond not found")

    if req.combo_name is not None:
        bond.combo_name = req.combo_name
    if req.combo_description is not None:
        bond.combo_description = req.combo_description

    db.commit()
    return {"ok": True, "bond": _bond_dict(bond, db)}


# ── DELETE /api/campaigns/{id}/bonds/{bond_id} ─────────────────────
@bonds_router.delete("/{campaign_id}/bonds/{bond_id}")
async def break_bond(
    campaign_id: UUID,
    bond_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """SW breaks a bond. Triggers grief tether on both characters via WS."""
    if not _is_sw(campaign_id, current_user, db):
        raise HTTPException(status_code=403, detail="Only the Story Weaver can break bonds")

    bond = db.query(Bond).filter(
        Bond.id == bond_id,
        Bond.campaign_id == campaign_id,
        Bond.broken_at == None,  # noqa: E711
    ).first()
    if not bond:
        raise HTTPException(status_code=404, detail="Bond not found or already broken")

    bond.broken_at = datetime.utcnow()
    bond.broken_by_user_id = current_user.id

    # Apply grief tether (−1) to both characters
    grief_applied = []
    for char_id in [bond.character_id_a, bond.character_id_b]:
        char = db.query(Character).filter(Character.id == char_id).first()
        if char and not char.is_npc:
            tethers = list(char.tethers or [])
            tethers.append({
                "id": str(bond.id) + "_grief",
                "description": f"Grief Tether — bond with {bond.char_b.name if str(char_id) == str(bond.character_id_a) else bond.char_a.name} broken",
                "is_active": True,
                "modifier": -1,
                "source": "grief",
            })
            char.tethers = tethers
            grief_applied.append({"character_id": str(char.id), "name": char.name})

    db.commit()

    logger.info(f"Bond broken: {bond_id} in campaign {campaign_id}, grief tether applied to {len(grief_applied)} characters")
    return {
        "ok": True,
        "bond_id": str(bond_id),
        "grief_applied": grief_applied,
    }
