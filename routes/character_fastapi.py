"""
Character and Party CRUD endpoints (TBA v1.5 Phase 1).
Auto-calculates level stats from CORE_RULESET, persists to database.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from backend.db import get_db
from backend.models import Character, Party, PartyMembership
from backend.character_utils import (
    calculate_level_stats,
    validate_stats,
    validate_attack_style,
    get_defense_die
)
from routes.schemas.character import (
    CharacterCreate,
    CharacterUpdate,
    CharacterResponse,
    PartyCreate,
    PartyResponse,
    PartyMemberAdd,
    PartyMemberResponse
)
from typing import List
import logging

logger = logging.getLogger(__name__)

character_blp_fastapi = APIRouter(prefix="/api/characters", tags=["Characters"])
party_router = APIRouter(prefix="/api/parties", tags=["Parties"])


# ============================================================================
# CHARACTER CRUD
# ============================================================================

@character_blp_fastapi.post("", response_model=CharacterResponse, status_code=201)
async def create_character(req: CharacterCreate, request: Request, db: Session = Depends(get_db)):
    """
    Create a new character with auto-calculated level stats.
    
    - Validates stats sum to 6
    - Validates attack style available for level
    - Auto-calculates Edge, BAP, max_dp from CORE_RULESET
    - Sets defense die based on level
    """
    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(f"[{request_id}] Creating character: {req.name} (level {req.level})")
    
    try:
        # Validate stats
        validate_stats(req.pp, req.ip, req.sp)
        
        # Validate attack style for level
        validate_attack_style(req.level, req.attack_style)
        
        # Calculate level-dependent stats
        level_stats = calculate_level_stats(req.level)
        defense_die = get_defense_die(req.level)
        
        # Create character
        character = Character(
            name=req.name,
            owner_id=req.owner_id,
            level=req.level,
            pp=req.pp,
            ip=req.ip,
            sp=req.sp,
            dp=level_stats["max_dp"],  # Start at full HP
            max_dp=level_stats["max_dp"],
            edge=level_stats["edge"],
            bap=level_stats["bap"],
            attack_style=req.attack_style,
            defense_die=defense_die,
            weapon=req.weapon.model_dump() if req.weapon else None,
            armor=req.armor.model_dump() if req.armor else None
        )
        
        db.add(character)
        db.commit()
        db.refresh(character)
        
        logger.info(f"[{request_id}] Character created: {character.id}")
        return character
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[{request_id}] Character creation error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Character creation failed: {str(e)}")


@character_blp_fastapi.get("", response_model=List[CharacterResponse])
async def list_characters(owner_id: str, request: Request, db: Session = Depends(get_db)):
    """
    List all characters owned by a user.
    
    Query params:
        owner_id: User ID to filter by
    """
    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(f"[{request_id}] Listing characters for owner: {owner_id}")
    
    characters = db.query(Character).filter(Character.owner_id == owner_id).all()
    return characters


@character_blp_fastapi.get("/{character_id}", response_model=CharacterResponse)
async def get_character(character_id: str, request: Request, db: Session = Depends(get_db)):
    """Get a single character by ID."""
    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(f"[{request_id}] Fetching character: {character_id}")
    
    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        raise HTTPException(status_code=404, detail=f"Character {character_id} not found")
    
    return character


@character_blp_fastapi.patch("/{character_id}", response_model=CharacterResponse)
async def update_character(
    character_id: str,
    updates: CharacterUpdate,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Update a character.
    
    - If level changes, auto-recalculates Edge, BAP, max_dp, defense_die
    - If attack_style changes, validates against current level
    - If dp changes, validates >= 0 and <= max_dp
    """
    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(f"[{request_id}] Updating character: {character_id}")
    
    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        raise HTTPException(status_code=404, detail=f"Character {character_id} not found")
    
    try:
        # Handle level change (auto-recalculate stats)
        if updates.level is not None and updates.level != character.level:
            level_stats = calculate_level_stats(updates.level)
            character.level = updates.level
            character.edge = level_stats["edge"]
            character.bap = level_stats["bap"]
            character.max_dp = level_stats["max_dp"]
            character.defense_die = get_defense_die(updates.level)
            
            # Heal to full on level up
            character.dp = character.max_dp
            
            logger.info(
                f"[{request_id}] Character leveled up: {character.name} → Level {updates.level} "
                f"(Edge: {character.edge}, BAP: {character.bap}, Max DP: {character.max_dp})"
            )
        
        # Handle attack style change
        if updates.attack_style is not None:
            validate_attack_style(character.level, updates.attack_style)
            character.attack_style = updates.attack_style
        
        # Handle DP change (manual adjustment)
        if updates.dp is not None:
            if updates.dp < 0:
                raise ValueError("DP cannot be negative")
            if updates.dp > character.max_dp:
                raise ValueError(f"DP cannot exceed max_dp ({character.max_dp})")
            character.dp = updates.dp
        
        # Handle equipment
        if updates.weapon is not None:
            character.weapon = updates.weapon.model_dump()
        if updates.armor is not None:
            character.armor = updates.armor.model_dump()
        
        # Handle name
        if updates.name is not None:
            character.name = updates.name
        
        db.commit()
        db.refresh(character)
        
        logger.info(f"[{request_id}] Character updated: {character.id}")
        return character
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[{request_id}] Character update error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Character update failed: {str(e)}")


@character_blp_fastapi.delete("/{character_id}", status_code=204)
async def delete_character(character_id: str, request: Request, db: Session = Depends(get_db)):
    """Soft delete a character (remove from DB)."""
    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(f"[{request_id}] Deleting character: {character_id}")
    
    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        raise HTTPException(status_code=404, detail=f"Character {character_id} not found")
    
    db.delete(character)
    db.commit()
    
    logger.info(f"[{request_id}] Character deleted: {character_id}")


# ============================================================================
# PARTY CRUD
# ============================================================================

@party_router.post("", response_model=PartyResponse, status_code=201)
async def create_party(req: PartyCreate, request: Request, db: Session = Depends(get_db)):
    """Create a new party/session with the creator as Story Weaver and first member."""
    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(f"[{request_id}] Creating party: {req.name}")

    # Validate that the creator character exists
    creator = db.query(Character).filter(Character.id == req.creator_character_id).first()
    if not creator:
        logger.error(f"[{request_id}] Creator character not found: {req.creator_character_id}")
        raise HTTPException(status_code=404, detail=f"Character with ID {req.creator_character_id} not found")

    # Create the party with story_weaver_id and created_by_id set to creator
    party = Party(
        name=req.name,
        description=req.description,
        story_weaver_id=req.creator_character_id,
        created_by_id=req.creator_character_id
    )
    db.add(party)
    db.flush()  # Get party.id before creating membership

    # Auto-add creator as first party member
    membership = PartyMembership(
        party_id=party.id,
        character_id=req.creator_character_id
    )
    db.add(membership)

    db.commit()
    db.refresh(party)

    logger.info(f"[{request_id}] Party created: {party.id} with creator {creator.name} as Story Weaver")
    return party


@party_router.get("", response_model=List[PartyResponse])
async def list_parties(story_weaver_id: str, request: Request, db: Session = Depends(get_db)):
    """List all parties where a character is the Story Weaver."""
    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(f"[{request_id}] Listing parties for Story Weaver: {story_weaver_id}")

    parties = db.query(Party).filter(Party.story_weaver_id == story_weaver_id).all()
    return parties


@party_router.get("/{party_id}", response_model=PartyResponse)
async def get_party(party_id: str, request: Request, db: Session = Depends(get_db)):
    """Get a single party by ID."""
    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(f"[{request_id}] Fetching party: {party_id}")
    
    party = db.query(Party).filter(Party.id == party_id).first()
    if not party:
        raise HTTPException(status_code=404, detail=f"Party {party_id} not found")
    
    return party


@party_router.post("/{party_id}/members", status_code=201)
async def add_party_member(
    party_id: str,
    req: PartyMemberAdd,
    request: Request,
    db: Session = Depends(get_db)
):
    """Add a character to a party."""
    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(f"[{request_id}] Adding character {req.character_id} to party {party_id}")
    
    # Verify party exists
    party = db.query(Party).filter(Party.id == party_id).first()
    if not party:
        raise HTTPException(status_code=404, detail=f"Party {party_id} not found")
    
    # Verify character exists
    character = db.query(Character).filter(Character.id == req.character_id).first()
    if not character:
        raise HTTPException(status_code=404, detail=f"Character {req.character_id} not found")
    
    # Check if already a member
    existing = db.query(PartyMembership).filter(
        PartyMembership.party_id == party_id,
        PartyMembership.character_id == req.character_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Character already in this party")
    
    # Add membership
    membership = PartyMembership(party_id=party_id, character_id=req.character_id)
    db.add(membership)
    db.commit()
    
    logger.info(f"[{request_id}] Character added to party: {req.character_id} → {party_id}")
    return {"message": "Character added to party", "party_id": party_id, "character_id": req.character_id}


@party_router.get("/{party_id}/members", response_model=List[PartyMemberResponse])
async def list_party_members(party_id: str, request: Request, db: Session = Depends(get_db)):
    """List all characters in a party."""
    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(f"[{request_id}] Listing members of party: {party_id}")
    
    memberships = db.query(PartyMembership).filter(PartyMembership.party_id == party_id).all()
    
    result = []
    for membership in memberships:
        result.append({
            "character": membership.character,
            "joined_at": membership.joined_at
        })
    
    return result


@party_router.delete("/{party_id}/members/{character_id}", status_code=204)
async def remove_party_member(
    party_id: str,
    character_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Remove a character from a party."""
    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(f"[{request_id}] Removing character {character_id} from party {party_id}")
    
    membership = db.query(PartyMembership).filter(
        PartyMembership.party_id == party_id,
        PartyMembership.character_id == character_id
    ).first()
    
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found")
    
    db.delete(membership)
    db.commit()
    
    logger.info(f"[{request_id}] Character removed from party: {character_id} → {party_id}")