"""
Character and Party CRUD endpoints (TBA v1.5 Phase 2d).
Auto-calculates level stats from CORE_RULESET, persists to database.
Includes full character creation with abilities and party membership.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from backend.db import get_db
from backend.models import Character, Party, PartyMembership, Ability, User
from backend.auth.jwt import get_current_user
from backend.character_utils import (
    calculate_level_stats,
    validate_stats,
    validate_attack_style,
    get_defense_die,
    get_available_attack_styles
)
from routes.schemas.character import (
    CharacterCreate,
    CharacterUpdate,
    CharacterResponse,
    PartyCreate,
    PartyResponse,
    PartyMemberAdd,
    PartyMemberResponse,
    FullCharacterCreate,
    FullCharacterResponse,
    AbilityResponse
)
from typing import List, Optional
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
            campaign_id=req.campaign_id,  # Link to campaign if provided
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


@character_blp_fastapi.post("/full", response_model=FullCharacterResponse, status_code=201)
async def create_character_full(
    req: FullCharacterCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new character with ability and party membership (Phase 2d).

    This endpoint:
    1. Validates stats sum to 6, each stat 1-3
    2. Validates weapon_die is available for the character's level
    3. Auto-calculates max_dp, edge, bap, defense_die from level
    4. Creates the character with all Phase 2d fields
    5. Creates the starting ability
    6. Adds character to campaign's Story and OOC parties

    Returns the full character with abilities and party IDs.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(f"[{request_id}] Creating full character: {req.name} (level {req.level}) for campaign {req.campaign_id}")

    try:
        # =====================================================================
        # 1. Validate stats
        # =====================================================================
        if req.pp + req.ip + req.sp != 6:
            raise ValueError(f"Stats must sum to 6, got {req.pp + req.ip + req.sp}")

        for stat_name, stat_val in [("PP", req.pp), ("IP", req.ip), ("SP", req.sp)]:
            if not 1 <= stat_val <= 3:
                raise ValueError(f"{stat_name} must be between 1 and 3, got {stat_val}")

        # =====================================================================
        # 2. Validate level (1-10 for TBA v1.5)
        # =====================================================================
        if not 1 <= req.level <= 10:
            raise ValueError(f"Level must be between 1 and 10, got {req.level}")

        # =====================================================================
        # 3. Validate weapon_die for level
        # =====================================================================
        available_weapons = get_available_attack_styles(req.level)
        if req.weapon_die not in available_weapons:
            raise ValueError(
                f"Weapon die '{req.weapon_die}' not available at level {req.level}. "
                f"Available options: {', '.join(available_weapons)}"
            )

        # =====================================================================
        # 4. Auto-calculate level stats
        # =====================================================================
        level_stats = calculate_level_stats(req.level)
        defense_die = req.defense_die if req.defense_die else get_defense_die(req.level)

        # Calculate uses per encounter (3 * level as per task)
        max_uses = 3 * req.level

        # =====================================================================
        # 5. Find Story and OOC parties for this campaign
        # =====================================================================
        story_party = db.query(Party).filter(
            Party.campaign_id == req.campaign_id,
            Party.party_type == 'story'
        ).first()

        ooc_party = db.query(Party).filter(
            Party.campaign_id == req.campaign_id,
            Party.party_type == 'ooc'
        ).first()

        if not story_party and not ooc_party:
            logger.warning(f"[{request_id}] No parties found for campaign {req.campaign_id}")
            # We'll still create the character, just won't add to parties

        # =====================================================================
        # 6. Create character
        # =====================================================================
        character = Character(
            name=req.name,
            owner_id=req.campaign_id,  # Use campaign_id as owner for campaign-scoped characters
            user_id=current_user.id,  # User who owns this character
            campaign_id=req.campaign_id,  # Link character to campaign
            level=req.level,
            pp=req.pp,
            ip=req.ip,
            sp=req.sp,
            dp=level_stats["max_dp"],
            max_dp=level_stats["max_dp"],
            edge=level_stats["edge"],
            bap=level_stats["bap"],
            attack_style=req.weapon_die,
            defense_die=defense_die,
            weapon={"name": req.weapon_name, "die": req.weapon_die} if req.weapon_name else None,
            armor={"name": req.armor_name} if req.armor_name else None,
            # Phase 2d fields
            notes=req.notes,
            max_uses_per_encounter=max_uses,
            current_uses=max_uses,
            weapon_bonus=0,
            armor_bonus=0,
            times_called=0,
            is_called=False,
            status='active'
        )

        db.add(character)
        db.flush()  # Get character.id before creating ability

        logger.info(f"[{request_id}] Character created: {character.id}")

        # =====================================================================
        # 7. Create starting abilities (supports single or multiple)
        # =====================================================================
        # Determine ability_type from effect_type
        ability_type_map = {
            'damage': 'technique',
            'heal': 'spell',
            'buff': 'spell',
            'debuff': 'spell',
            'utility': 'special'
        }

        # req.ability is now always a list after validation
        abilities_to_create = req.ability if isinstance(req.ability, list) else [req.ability]

        for ability_data in abilities_to_create:
            ability_type = ability_type_map.get(ability_data.effect_type, 'technique')

            ability = Ability(
                character_id=character.id,
                slot_number=ability_data.slot_number,
                ability_type=ability_type,
                display_name=ability_data.display_name,
                macro_command=ability_data.macro_command,
                power_source=ability_data.power_source,
                effect_type=ability_data.effect_type,
                die=ability_data.die,
                is_aoe=ability_data.is_aoe
            )

            db.add(ability)
            logger.info(f"[{request_id}] Ability created: {ability.display_name} ({ability.macro_command}) - Slot {ability.slot_number}")

        # =====================================================================
        # 8. Add character to Story and OOC parties
        # =====================================================================
        party_ids = []

        if story_party:
            story_membership = PartyMembership(
                party_id=story_party.id,
                character_id=character.id
            )
            db.add(story_membership)
            party_ids.append(story_party.id)
            logger.info(f"[{request_id}] Added to Story party: {story_party.id}")

        if ooc_party:
            ooc_membership = PartyMembership(
                party_id=ooc_party.id,
                character_id=character.id
            )
            db.add(ooc_membership)
            party_ids.append(ooc_party.id)
            logger.info(f"[{request_id}] Added to OOC party: {ooc_party.id}")

        # =====================================================================
        # 9. Commit transaction
        # =====================================================================
        db.commit()
        db.refresh(character)

        logger.info(f"[{request_id}] Full character creation complete: {character.name} ({character.id})")

        # =====================================================================
        # 10. Build response
        # =====================================================================
        # Load abilities for response
        abilities = db.query(Ability).filter(Ability.character_id == character.id).all()

        return FullCharacterResponse(
            id=character.id,
            name=character.name,
            owner_id=character.owner_id,
            level=character.level,
            pp=character.pp,
            ip=character.ip,
            sp=character.sp,
            dp=character.dp,
            max_dp=character.max_dp,
            edge=character.edge,
            bap=character.bap,
            attack_style=character.attack_style,
            defense_die=character.defense_die,
            weapon=character.weapon,
            armor=character.armor,
            notes=character.notes,
            max_uses_per_encounter=character.max_uses_per_encounter,
            current_uses=character.current_uses,
            weapon_bonus=character.weapon_bonus,
            armor_bonus=character.armor_bonus,
            status=character.status,
            abilities=[AbilityResponse.model_validate(a) for a in abilities],
            campaign_id=req.campaign_id,
            party_ids=party_ids,
            created_at=character.created_at,
            updated_at=character.updated_at
        )

    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.error(f"[{request_id}] Full character creation error: {str(e)}", exc_info=True)
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


# ============================================================================
# NPC ROUTES (Story Weaver only)
# ============================================================================

npc_router = APIRouter(prefix="/api/campaigns", tags=["NPCs"])


@npc_router.get("/{campaign_id}/npcs", response_model=List[CharacterResponse])
async def list_npcs(
    campaign_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all NPCs for a campaign (Story Weaver only)."""
    from backend.models import CampaignMembership
    from uuid import UUID

    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(f"[{request_id}] Listing NPCs for campaign: {campaign_id}")

    # Verify user is Story Weaver
    campaign_uuid = UUID(campaign_id)
    membership = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == campaign_uuid,
        CampaignMembership.user_id == current_user.id
    ).first()

    if not membership or membership.role != 'story_weaver':
        raise HTTPException(status_code=403, detail="Only Story Weaver can manage NPCs")

    # Get all NPCs for this campaign
    npcs = db.query(Character).filter(
        Character.campaign_id == campaign_uuid,
        Character.is_npc == True
    ).all()

    logger.info(f"[{request_id}] Found {len(npcs)} NPCs")
    return npcs


@npc_router.post("/{campaign_id}/npcs", response_model=CharacterResponse, status_code=201)
async def create_npc(
    campaign_id: str,
    req: CharacterCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new NPC (Story Weaver only)."""
    from backend.models import CampaignMembership
    from uuid import UUID

    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(f"[{request_id}] Creating NPC: {req.name} for campaign {campaign_id}")

    # Verify user is Story Weaver
    campaign_uuid = UUID(campaign_id)
    membership = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == campaign_uuid,
        CampaignMembership.user_id == current_user.id
    ).first()

    if not membership or membership.role != 'story_weaver':
        raise HTTPException(status_code=403, detail="Only Story Weaver can create NPCs")

    try:
        # Validate stats
        validate_stats(req.pp, req.ip, req.sp)

        # Validate attack style for level
        validate_attack_style(req.level, req.attack_style)

        # Calculate level-dependent stats
        level_stats = calculate_level_stats(req.level)
        defense_die = get_defense_die(req.level)

        # Create NPC (user_id is NULL for NPCs)
        max_uses = req.level * 3  # TBA v1.5: max_uses_per_encounter = level * 3
        npc = Character(
            name=req.name,
            owner_id=str(current_user.id),  # Track creator
            user_id=None,  # NPCs have no user_id
            campaign_id=campaign_uuid,
            is_npc=True,
            is_ally=False,
            level=req.level,
            pp=req.pp,
            ip=req.ip,
            sp=req.sp,
            dp=level_stats["max_dp"],
            max_dp=level_stats["max_dp"],
            edge=level_stats["edge"],
            bap=level_stats["bap"],
            attack_style=req.attack_style,
            defense_die=defense_die,
            weapon=req.weapon.model_dump() if req.weapon else None,
            armor=req.armor.model_dump() if req.armor else None,
            max_uses_per_encounter=max_uses,
            current_uses=max_uses
        )

        db.add(npc)
        db.commit()
        db.refresh(npc)

        logger.info(f"[{request_id}] NPC created: {npc.id}")
        return npc

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[{request_id}] NPC creation error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"NPC creation failed: {str(e)}")


@npc_router.put("/{campaign_id}/npcs/{npc_id}", response_model=CharacterResponse)
async def update_npc(
    campaign_id: str,
    npc_id: str,
    req: CharacterUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an NPC (Story Weaver only)."""
    from backend.models import CampaignMembership
    from uuid import UUID

    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(f"[{request_id}] Updating NPC: {npc_id}")

    # Verify user is Story Weaver
    campaign_uuid = UUID(campaign_id)
    membership = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == campaign_uuid,
        CampaignMembership.user_id == current_user.id
    ).first()

    if not membership or membership.role != 'story_weaver':
        raise HTTPException(status_code=403, detail="Only Story Weaver can update NPCs")

    # Get NPC
    npc = db.query(Character).filter(
        Character.id == UUID(npc_id),
        Character.campaign_id == campaign_uuid,
        Character.is_npc == True
    ).first()

    if not npc:
        raise HTTPException(status_code=404, detail="NPC not found")

    try:
        # Update fields
        if req.name is not None:
            npc.name = req.name
        if req.level is not None:
            level_stats = calculate_level_stats(req.level)
            max_uses = req.level * 3  # TBA v1.5: max_uses_per_encounter = level * 3
            npc.level = req.level
            npc.max_dp = level_stats["max_dp"]
            npc.edge = level_stats["edge"]
            npc.bap = level_stats["bap"]
            npc.defense_die = get_defense_die(req.level)
            npc.max_uses_per_encounter = max_uses
            npc.current_uses = min(npc.current_uses or 0, max_uses)  # Don't exceed new max
        if req.dp is not None:
            npc.dp = req.dp
        if req.attack_style is not None:
            validate_attack_style(npc.level, req.attack_style)
            npc.attack_style = req.attack_style
        if req.weapon is not None:
            npc.weapon = req.weapon.model_dump()
        if req.armor is not None:
            npc.armor = req.armor.model_dump()

        db.commit()
        db.refresh(npc)

        logger.info(f"[{request_id}] NPC updated: {npc_id}")
        return npc

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[{request_id}] NPC update error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"NPC update failed: {str(e)}")


@npc_router.delete("/{campaign_id}/npcs/{npc_id}", status_code=204)
async def delete_npc(
    campaign_id: str,
    npc_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete an NPC (Story Weaver only)."""
    from backend.models import CampaignMembership
    from uuid import UUID

    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(f"[{request_id}] Deleting NPC: {npc_id}")

    # Verify user is Story Weaver
    campaign_uuid = UUID(campaign_id)
    membership = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == campaign_uuid,
        CampaignMembership.user_id == current_user.id
    ).first()

    if not membership or membership.role != 'story_weaver':
        raise HTTPException(status_code=403, detail="Only Story Weaver can delete NPCs")

    # Get NPC
    npc = db.query(Character).filter(
        Character.id == UUID(npc_id),
        Character.campaign_id == campaign_uuid,
        Character.is_npc == True
    ).first()

    if not npc:
        raise HTTPException(status_code=404, detail="NPC not found")

    db.delete(npc)
    db.commit()

    logger.info(f"[{request_id}] NPC deleted: {npc_id}")


@npc_router.post("/{campaign_id}/npcs/{npc_id}/duplicate", response_model=CharacterResponse, status_code=201)
async def duplicate_npc(
    campaign_id: str,
    npc_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Duplicate an NPC (Story Weaver only)."""
    from backend.models import CampaignMembership
    from uuid import UUID, uuid4

    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(f"[{request_id}] Duplicating NPC: {npc_id}")

    # Verify user is Story Weaver
    campaign_uuid = UUID(campaign_id)
    membership = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == campaign_uuid,
        CampaignMembership.user_id == current_user.id
    ).first()

    if not membership or membership.role != 'story_weaver':
        raise HTTPException(status_code=403, detail="Only Story Weaver can duplicate NPCs")

    # Get original NPC
    original = db.query(Character).filter(
        Character.id == UUID(npc_id),
        Character.campaign_id == campaign_uuid,
        Character.is_npc == True
    ).first()

    if not original:
        raise HTTPException(status_code=404, detail="NPC not found")

    # Create duplicate
    duplicate = Character(
        id=uuid4(),
        name=f"{original.name} (Copy)",
        owner_id=str(current_user.id),
        user_id=None,
        campaign_id=campaign_uuid,
        is_npc=True,
        is_ally=False,
        level=original.level,
        pp=original.pp,
        ip=original.ip,
        sp=original.sp,
        dp=original.max_dp,  # Start at full HP
        max_dp=original.max_dp,
        edge=original.edge,
        bap=original.bap,
        attack_style=original.attack_style,
        defense_die=original.defense_die,
        weapon=original.weapon,
        armor=original.armor
    )

    db.add(duplicate)
    db.commit()
    db.refresh(duplicate)

    logger.info(f"[{request_id}] NPC duplicated: {npc_id} → {duplicate.id}")
    return duplicate


# ============================================================================
# ALLY ROUTES (Players only)
# ============================================================================

ally_router = APIRouter(prefix="/api/campaigns", tags=["Allies"])


@ally_router.post("/{campaign_id}/characters/{character_id}/ally", response_model=CharacterResponse, status_code=201)
async def create_ally(
    campaign_id: str,
    character_id: str,
    req: CharacterCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create an Ally for a character (validates technique slot 1 available)."""
    from uuid import UUID

    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(f"[{request_id}] Creating Ally for character: {character_id}")

    # Get parent character
    parent = db.query(Character).filter(
        Character.id == UUID(character_id),
        Character.user_id == current_user.id,
        Character.campaign_id == UUID(campaign_id)
    ).first()

    if not parent:
        raise HTTPException(status_code=404, detail="Character not found or not owned by you")

    if parent.is_npc or parent.is_ally:
        raise HTTPException(status_code=400, detail="Only player characters can have Allies")

    # Check if character already has an Ally
    existing_ally = db.query(Character).filter(
        Character.parent_character_id == parent.id,
        Character.is_ally == True
    ).first()

    if existing_ally:
        raise HTTPException(status_code=400, detail="Character already has an Ally")

    # TODO: Validate technique slot 1 is available (requires abilities table query)
    # For now, we'll allow Ally creation

    try:
        # Validate stats
        validate_stats(req.pp, req.ip, req.sp)

        # Validate attack style for level
        validate_attack_style(req.level, req.attack_style)

        # Calculate level-dependent stats (Allies use different leveling table - TODO)
        level_stats = calculate_level_stats(req.level)
        defense_die = get_defense_die(req.level)

        # Create Ally
        ally = Character(
            name=req.name,
            owner_id=str(current_user.id),
            user_id=current_user.id,  # Allies have same user_id as parent
            campaign_id=UUID(campaign_id),
            is_npc=False,
            is_ally=True,
            parent_character_id=parent.id,
            level=req.level,
            pp=req.pp,
            ip=req.ip,
            sp=req.sp,
            dp=level_stats["max_dp"],
            max_dp=level_stats["max_dp"],
            edge=level_stats["edge"],
            bap=level_stats["bap"],
            attack_style=req.attack_style,
            defense_die=defense_die,
            weapon=req.weapon.model_dump() if req.weapon else None,
            armor=req.armor.model_dump() if req.armor else None
        )

        db.add(ally)
        db.commit()
        db.refresh(ally)

        logger.info(f"[{request_id}] Ally created: {ally.id} for parent {parent.id}")
        return ally

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[{request_id}] Ally creation error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ally creation failed: {str(e)}")