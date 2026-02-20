"""
Character and Party CRUD endpoints (TBA v1.5 Phase 2d).
Auto-calculates level stats from CORE_RULESET, persists to database.
Includes full character creation with abilities and party membership.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from backend.db import get_db
from backend.models import Character, Party, PartyMembership, Ability, User, Message, InventoryItem, CampaignMembership
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
        # 4. Campaign governance checks
        # =====================================================================
        from backend.models import Campaign, CampaignMembership

        campaign = db.query(Campaign).filter(Campaign.id == req.campaign_id).first()
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        # Determine initial status and whether to skip party assignment
        initial_status = 'active'
        skip_parties = False

        # Check character creation mode
        if campaign.character_creation_mode == 'sw_only':
            # Only Story Weaver can create characters
            membership = db.query(CampaignMembership).filter(
                CampaignMembership.campaign_id == req.campaign_id,
                CampaignMembership.user_id == current_user.id
            ).first()

            if not membership or membership.role != 'story_weaver':
                raise HTTPException(
                    status_code=403,
                    detail="Character creation is restricted to the Story Weaver in this campaign"
                )

        elif campaign.character_creation_mode == 'approval_required':
            # Character created in pending state - SW must approve before it becomes active
            initial_status = 'pending_approval'
            skip_parties = True

        # Count active characters only — rejected and archived (dead) don't block new character creation
        existing_char_count = db.query(Character).filter(
            Character.user_id == current_user.id,
            Character.campaign_id == req.campaign_id,
            Character.is_npc == False,
            Character.status.notin_(['rejected', 'archived'])
        ).count()

        if existing_char_count >= campaign.max_characters_per_player:
            raise HTTPException(
                status_code=403,
                detail=f"You've reached the character limit for this campaign ({campaign.max_characters_per_player})"
            )

        # =====================================================================
        # 5. Auto-calculate level stats
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
            status=initial_status
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
        # 8. Add character to Story and OOC parties (skipped if pending approval)
        # =====================================================================
        party_ids = []

        if not skip_parties:
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
        else:
            logger.info(f"[{request_id}] Character pending approval - skipping party assignment")

        # =====================================================================
        # 9. Commit transaction
        # =====================================================================
        db.commit()
        db.refresh(character)

        logger.info(f"[{request_id}] Full character creation complete: {character.name} ({character.id})")

        # Broadcast to campaign so SW gets a real-time toast + party panel refresh
        try:
            from routes.campaign_websocket import broadcast_character_created
            import asyncio
            asyncio.create_task(broadcast_character_created(
                character.campaign_id,
                str(character.id),
                character.name,
                current_user.username,
                character.status
            ))
        except Exception as _be:
            logger.warning(f"Could not broadcast character creation: {_be}")

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
async def get_character(
    character_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a single character by ID. Allows Story Weavers to access NPCs in their campaigns."""
    from uuid import UUID
    from backend.models import CampaignMembership

    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(f"[{request_id}] Fetching character: {character_id}")

    char_uuid = UUID(character_id)
    character = db.query(Character).filter(Character.id == char_uuid).first()
    if not character:
        raise HTTPException(status_code=404, detail=f"Character {character_id} not found")

    # Permission check
    if character.is_npc:
        # Check if user is Story Weaver for this campaign
        logger.info(f"[{request_id}] NPC access check - character.campaign_id: {character.campaign_id}, current_user.id: {current_user.id}")
        membership = db.query(CampaignMembership).filter(
            CampaignMembership.campaign_id == character.campaign_id,
            CampaignMembership.user_id == current_user.id
        ).first()
        logger.info(f"[{request_id}] Membership found: {membership is not None}, Role: {membership.role if membership else 'N/A'}")
        if not membership or membership.role != 'story_weaver':
            logger.warning(f"[{request_id}] Access denied - membership exists: {membership is not None}, role: {membership.role if membership else 'N/A'}")
            raise HTTPException(status_code=403, detail="Only Story Weaver can access NPCs")
    else:
        # Check if user owns this character
        logger.info(f"[{request_id}] PC access check - character.user_id: {character.user_id}, current_user.id: {current_user.id}")
        if character.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="You don't own this character")

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
            npc.current_uses = max_uses  # Restore uses on level up
            # Cap current DP at new max (don't auto-heal unless explicitly requested)
            if npc.dp > npc.max_dp:
                npc.dp = npc.max_dp
        if req.dp is not None:
            # Cap DP at max_dp
            npc.dp = min(req.dp, npc.max_dp)
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


@npc_router.post("/{campaign_id}/npcs/{npc_id}/transfer", response_model=CharacterResponse)
async def transfer_npc_to_player(
    campaign_id: str,
    npc_id: str,
    request: Request,
    req: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Transfer an NPC to a player (Story Weaver only). Converts NPC to a player character."""
    from backend.models import CampaignMembership
    from uuid import UUID

    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(f"[{request_id}] Transferring NPC {npc_id} to player")

    # Verify user is Story Weaver
    campaign_uuid = UUID(campaign_id)
    membership = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == campaign_uuid,
        CampaignMembership.user_id == current_user.id
    ).first()

    if not membership or membership.role != 'story_weaver':
        raise HTTPException(status_code=403, detail="Only Story Weaver can transfer NPCs")

    # Get NPC
    npc = db.query(Character).filter(
        Character.id == UUID(npc_id),
        Character.campaign_id == campaign_uuid,
        Character.is_npc == True
    ).first()

    if not npc:
        raise HTTPException(status_code=404, detail="NPC not found")

    # Get target user
    target_user_id = req.get("target_user_id")
    if not target_user_id:
        raise HTTPException(status_code=400, detail="target_user_id is required")

    target_user = db.query(User).filter(User.id == UUID(target_user_id)).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")

    # Verify target user is a member of this campaign
    target_membership = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == campaign_uuid,
        CampaignMembership.user_id == UUID(target_user_id)
    ).first()

    if not target_membership:
        raise HTTPException(status_code=400, detail="Target user is not a member of this campaign")

    # Check character limit for target player
    from backend.models import Campaign
    campaign = db.query(Campaign).filter(Campaign.id == campaign_uuid).first()
    existing_count = db.query(Character).filter(
        Character.user_id == UUID(target_user_id),
        Character.campaign_id == campaign_uuid,
        Character.is_npc == False
    ).count()

    if existing_count >= campaign.max_characters_per_player:
        raise HTTPException(
            status_code=403,
            detail=f"Target player has reached the character limit ({campaign.max_characters_per_player})"
        )

    # Transfer the NPC to the player
    old_name = npc.name
    npc.is_npc = False
    npc.is_ally = False
    npc.user_id = UUID(target_user_id)
    npc.owner_id = str(target_user_id)

    db.commit()
    db.refresh(npc)

    logger.info(f"[{request_id}] NPC '{old_name}' transferred to user {target_user_id}")
    return npc


@npc_router.post("/{campaign_id}/characters/{character_id}/convert-to-npc")
async def convert_pc_to_npc(
    campaign_id: str,
    character_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Convert a player character to an NPC (Story Weaver only). Keeps all stats and abilities."""
    from backend.models import CampaignMembership
    from uuid import UUID

    request_id = getattr(request.state, "request_id", "unknown")
    campaign_uuid = UUID(campaign_id)
    char_uuid = UUID(character_id)

    # Verify SW
    membership = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == campaign_uuid,
        CampaignMembership.user_id == current_user.id
    ).first()
    if not membership or membership.role != 'story_weaver':
        raise HTTPException(status_code=403, detail="Only Story Weaver can convert characters to NPCs")

    # Get the character — must be a PC in this campaign
    char = db.query(Character).filter(
        Character.id == char_uuid,
        Character.campaign_id == campaign_uuid,
        Character.is_npc == False
    ).first()
    if not char:
        raise HTTPException(status_code=404, detail="Player character not found in this campaign")

    old_owner = str(char.user_id) if char.user_id else None
    char_name = char.name

    # Convert to NPC — SW takes ownership, clear player user_id
    char.is_npc = True
    char.is_ally = False
    char.user_id = None
    char.owner_id = str(current_user.id)  # owner_id is NOT NULL; SW becomes the NPC owner

    db.commit()
    db.refresh(char)

    logger.info(f"[{request_id}] Character '{char_name}' (owner: {old_owner}) converted to NPC by SW {current_user.username}")

    # Broadcast so the SW's bubble bar refreshes and the player loses their PC
    try:
        from routes.campaign_websocket import broadcast_pc_converted_to_npc
        import asyncio
        asyncio.create_task(broadcast_pc_converted_to_npc(campaign_uuid, str(char.id), char_name))
    except Exception as e:
        logger.warning(f"Could not broadcast PC→NPC conversion: {e}")

    return {"message": f"'{char_name}' is now an NPC.", "character_id": str(char.id), "character_name": char_name}


@npc_router.post("/{campaign_id}/characters/{character_id}/transfer-to-player")
async def transfer_pc_to_player(
    campaign_id: str,
    character_id: str,
    request: Request,
    req: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Transfer a PC to another player (Story Weaver only). Original owner loses the character."""
    from backend.models import CampaignMembership, Campaign
    from uuid import UUID

    request_id = getattr(request.state, "request_id", "unknown")
    campaign_uuid = UUID(campaign_id)
    char_uuid = UUID(character_id)

    # Verify SW
    membership = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == campaign_uuid,
        CampaignMembership.user_id == current_user.id
    ).first()
    if not membership or membership.role != 'story_weaver':
        raise HTTPException(status_code=403, detail="Only Story Weaver can transfer characters")

    # Get the character — must be a PC in this campaign
    char = db.query(Character).filter(
        Character.id == char_uuid,
        Character.campaign_id == campaign_uuid,
        Character.is_npc == False
    ).first()
    if not char:
        raise HTTPException(status_code=404, detail="Player character not found in this campaign")

    target_user_id = req.get("target_user_id")
    if not target_user_id:
        raise HTTPException(status_code=400, detail="target_user_id is required")

    target_uuid = UUID(target_user_id)

    # Verify target is an active campaign member
    target_membership = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == campaign_uuid,
        CampaignMembership.user_id == target_uuid,
        CampaignMembership.left_at.is_(None)
    ).first()
    if not target_membership:
        raise HTTPException(status_code=400, detail="Target player is not an active member of this campaign")

    # Check target player's character limit
    campaign = db.query(Campaign).filter(Campaign.id == campaign_uuid).first()
    existing_count = db.query(Character).filter(
        Character.user_id == target_uuid,
        Character.campaign_id == campaign_uuid,
        Character.is_npc == False,
        Character.status != 'rejected'
    ).count()
    if existing_count >= campaign.max_characters_per_player:
        raise HTTPException(status_code=403, detail=f"Target player has reached the character limit ({campaign.max_characters_per_player})")

    char_name = char.name
    char.user_id = target_uuid
    char.owner_id = str(target_uuid)

    db.commit()
    db.refresh(char)
    logger.info(f"[{request_id}] Character '{char_name}' transferred to user {target_user_id} by SW {current_user.username}")

    # Broadcast so both players' game views update
    try:
        from routes.campaign_websocket import broadcast_pc_transferred
        import asyncio
        asyncio.create_task(broadcast_pc_transferred(campaign_uuid, str(char.id), char_name, str(target_uuid)))
    except Exception as e:
        logger.warning(f"Could not broadcast PC transfer: {e}")

    return {"message": f"'{char_name}' transferred successfully.", "character_id": str(char.id), "character_name": char_name}


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
    duplicate_id = uuid4()
    duplicate = Character(
        id=duplicate_id,
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
        armor=original.armor,
        max_uses_per_encounter=original.max_uses_per_encounter,
        current_uses=original.current_uses
    )

    db.add(duplicate)
    db.flush()  # Flush to get the ID assigned

    # Copy abilities
    original_abilities = db.query(Ability).filter(Ability.character_id == UUID(npc_id)).all()
    for orig_ability in original_abilities:
        new_ability = Ability(
            character_id=duplicate_id,
            slot_number=orig_ability.slot_number,
            ability_type=orig_ability.ability_type,
            display_name=orig_ability.display_name,
            macro_command=orig_ability.macro_command,
            power_source=orig_ability.power_source,
            effect_type=orig_ability.effect_type,
            die=orig_ability.die,
            is_aoe=orig_ability.is_aoe,
            max_uses=orig_ability.max_uses,
            uses_remaining=orig_ability.uses_remaining
        )
        db.add(new_ability)

    db.commit()
    db.refresh(duplicate)

    logger.info(f"[{request_id}] NPC duplicated: {npc_id} → {duplicate.id} with {len(original_abilities)} abilities")
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


# =====================================================================
# Abilities Endpoints
# =====================================================================

@character_blp_fastapi.get("/{character_id}/abilities")
async def get_character_abilities(
    character_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get abilities for a character (PC, NPC, or Ally).
    For NPCs: Checks if user is Story Weaver.
    For PCs/Allies: Checks if user owns the character.
    """
    from uuid import UUID
    from backend.models import CampaignMembership

    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(f"[{request_id}] Fetching abilities for character: {character_id}")

    try:
        char_uuid = UUID(character_id)
        character = db.query(Character).filter(Character.id == char_uuid).first()

        if not character:
            raise HTTPException(status_code=404, detail="Character not found")

        # Permission check
        if character.is_npc:
            # Check if user is Story Weaver
            membership = db.query(CampaignMembership).filter(
                CampaignMembership.campaign_id == character.campaign_id,
                CampaignMembership.user_id == current_user.id
            ).first()
            if not membership or membership.role != 'story_weaver':
                raise HTTPException(status_code=403, detail="Only Story Weaver can view NPC abilities")
        else:
            # Check if user owns this character
            if character.user_id != current_user.id:
                raise HTTPException(status_code=403, detail="You don't own this character")

        # Get abilities
        abilities = db.query(Ability).filter(Ability.character_id == char_uuid).order_by(Ability.slot_number).all()

        logger.info(f"[{request_id}] Found {len(abilities)} abilities for character {character_id}")

        abilities_list = []
        for ability in abilities:
            abilities_list.append({
                "id": str(ability.id),
                "character_id": str(ability.character_id),
                "slot_number": ability.slot_number,
                "ability_type": ability.ability_type,
                "display_name": ability.display_name,
                "macro_command": ability.macro_command,
                "power_source": ability.power_source,
                "effect_type": ability.effect_type,
                "die": ability.die,
                "is_aoe": ability.is_aoe,
                "max_uses": ability.max_uses,
                "uses_remaining": ability.uses_remaining
            })

        return {"abilities": abilities_list}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[{request_id}] Ability fetch error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ability fetch failed: {str(e)}")


@character_blp_fastapi.post("/{character_id}/abilities", status_code=200)
async def update_character_abilities(
    character_id: str,
    request: Request,
    req: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update/create abilities for a character (PC, NPC, or Ally).
    For NPCs: Checks if user is Story Weaver.
    For PCs/Allies: Checks if user owns the character.
    """
    from uuid import UUID
    from backend.models import CampaignMembership

    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(f"[{request_id}] Updating abilities for character: {character_id}")

    try:
        char_uuid = UUID(character_id)
        character = db.query(Character).filter(Character.id == char_uuid).first()

        if not character:
            raise HTTPException(status_code=404, detail="Character not found")

        # Permission check
        if character.is_npc:
            # Check if user is Story Weaver
            membership = db.query(CampaignMembership).filter(
                CampaignMembership.campaign_id == character.campaign_id,
                CampaignMembership.user_id == current_user.id
            ).first()
            if not membership or membership.role != 'story_weaver':
                raise HTTPException(status_code=403, detail="Only Story Weaver can manage NPC abilities")
        else:
            # Check if user owns this character
            if character.user_id != current_user.id:
                raise HTTPException(status_code=403, detail="You don't own this character")

        # Get abilities from request
        abilities_data = req.get('abilities', [])

        # Delete existing abilities and create new ones
        db.query(Ability).filter(Ability.character_id == char_uuid).delete()

        for ability in abilities_data:
            new_ability = Ability(
                character_id=char_uuid,
                slot_number=ability['slot_number'],
                ability_type=ability.get('ability_type', 'spell'),
                display_name=ability['display_name'],
                macro_command=ability['macro_command'],
                power_source=ability.get('power_source', 'PP'),
                effect_type=ability.get('effect_type', 'damage'),
                die=ability.get('die', '1d8'),
                is_aoe=ability.get('is_aoe', False),
                max_uses=ability.get('max_uses', character.level * 3),
                uses_remaining=ability.get('uses_remaining', ability.get('max_uses', character.level * 3))
            )
            db.add(new_ability)

        db.commit()
        logger.info(f"[{request_id}] Updated {len(abilities_data)} abilities for character {character_id}")
        return {"message": "Abilities updated successfully", "count": len(abilities_data)}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[{request_id}] Ability update error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ability update failed: {str(e)}")


# ============================================================================
# CHARACTER APPROVAL SYSTEM
# ============================================================================

@npc_router.get("/{campaign_id}/pending-characters")
async def get_pending_characters(
    campaign_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all characters pending approval for a campaign (Story Weaver only)."""
    from backend.models import CampaignMembership
    from uuid import UUID

    request_id = getattr(request.state, "request_id", "unknown")

    campaign_uuid = UUID(campaign_id)
    membership = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == campaign_uuid,
        CampaignMembership.user_id == current_user.id
    ).first()

    if not membership or membership.role != 'story_weaver':
        raise HTTPException(status_code=403, detail="Only Story Weaver can view pending characters")

    pending = db.query(Character).filter(
        Character.campaign_id == campaign_uuid,
        Character.status == 'pending_approval',
        Character.is_npc == False
    ).all()

    result = []
    for char in pending:
        abilities = db.query(Ability).filter(Ability.character_id == char.id).order_by(Ability.slot_number).all()
        # Get player username
        player = db.query(User).filter(User.id == char.user_id).first()
        result.append({
            "id": str(char.id),
            "name": char.name,
            "player_id": str(char.user_id) if char.user_id else None,
            "player_name": player.username if player else char.owner_id,
            "level": char.level,
            "pp": char.pp,
            "ip": char.ip,
            "sp": char.sp,
            "attack_style": char.attack_style,
            "defense_die": char.defense_die,
            "weapon": char.weapon,
            "armor": char.armor,
            "notes": char.notes,
            "created_at": char.created_at.isoformat(),
            "abilities": [
                {
                    "slot_number": a.slot_number,
                    "display_name": a.display_name,
                    "macro_command": a.macro_command,
                    "power_source": a.power_source,
                    "effect_type": a.effect_type,
                    "die": a.die,
                    "is_aoe": a.is_aoe
                }
                for a in abilities
            ]
        })

    logger.info(f"[{request_id}] Found {len(result)} pending characters for campaign {campaign_id}")
    return {"pending_characters": result}


@character_blp_fastapi.post("/{character_id}/approve")
async def approve_character(
    character_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Approve a pending character (Story Weaver only). Activates character and adds to campaign parties."""
    from backend.models import CampaignMembership
    from uuid import UUID

    request_id = getattr(request.state, "request_id", "unknown")
    char_uuid = UUID(character_id)

    char = db.query(Character).filter(
        Character.id == char_uuid,
        Character.status == 'pending_approval'
    ).first()

    if not char:
        raise HTTPException(status_code=404, detail="Pending character not found")

    # Verify SW of this character's campaign
    membership = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == char.campaign_id,
        CampaignMembership.user_id == current_user.id
    ).first()

    if not membership or membership.role != 'story_weaver':
        raise HTTPException(status_code=403, detail="Only Story Weaver can approve characters")

    # Activate character
    char.status = 'active'
    char.rejection_reason = None

    # Add to Story and OOC parties
    story_party = db.query(Party).filter(
        Party.campaign_id == char.campaign_id,
        Party.party_type == 'story'
    ).first()

    ooc_party = db.query(Party).filter(
        Party.campaign_id == char.campaign_id,
        Party.party_type == 'ooc'
    ).first()

    if story_party:
        db.add(PartyMembership(party_id=story_party.id, character_id=char.id))
    if ooc_party:
        db.add(PartyMembership(party_id=ooc_party.id, character_id=char.id))

    db.commit()
    logger.info(f"[{request_id}] Character '{char.name}' approved by SW {current_user.username}")

    # Broadcast approval to all campaign members so the player auto-reloads
    try:
        from routes.campaign_websocket import broadcast_character_approved
        from uuid import UUID as _UUID
        import asyncio
        asyncio.create_task(broadcast_character_approved(
            _UUID(str(char.campaign_id)),
            str(char.id),
            char.name
        ))
    except Exception as e:
        logger.warning(f"Could not broadcast character approval: {e}")

    return {"message": f"Character '{char.name}' has been approved!", "character_id": str(char.id)}


@character_blp_fastapi.post("/{character_id}/reject")
async def reject_character(
    character_id: str,
    request: Request,
    req: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Reject a pending character with a reason (Story Weaver only)."""
    from backend.models import CampaignMembership
    from uuid import UUID

    request_id = getattr(request.state, "request_id", "unknown")
    char_uuid = UUID(character_id)

    char = db.query(Character).filter(
        Character.id == char_uuid,
        Character.status == 'pending_approval'
    ).first()

    if not char:
        raise HTTPException(status_code=404, detail="Pending character not found")

    membership = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == char.campaign_id,
        CampaignMembership.user_id == current_user.id
    ).first()

    if not membership or membership.role != 'story_weaver':
        raise HTTPException(status_code=403, detail="Only Story Weaver can reject characters")

    reason = req.get("reason", "")
    char.status = 'rejected'
    char.rejection_reason = reason

    db.commit()
    logger.info(f"[{request_id}] Character '{char.name}' rejected by SW {current_user.username}. Reason: {reason}")

    # Broadcast rejection so the owning player gets a real-time toast
    try:
        from routes.campaign_websocket import broadcast_character_rejected
        import asyncio
        asyncio.create_task(broadcast_character_rejected(
            char.campaign_id,
            str(char.id),
            char.name,
            str(char.user_id) if char.user_id else "",
            reason
        ))
    except Exception as _be:
        logger.warning(f"Could not broadcast character rejection: {_be}")

    return {"message": f"Character '{char.name}' has been rejected.", "character_id": str(char.id)}


# ============================================================================
# THE CALLING SYSTEM
# ============================================================================

@character_blp_fastapi.post("/{character_id}/the-calling")
async def resolve_the_calling(
    character_id: str,
    request: Request,
    req: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Resolve The Calling for a character at -10 DP.
    Player chooses IP or SP; backend rolls player die and SW difficulty die.
    Outcomes: clean (win by 4+), scarred (win by 1-3), dead (lose/tie).
    """
    from uuid import UUID
    from backend.roll_logic import roll_dice
    from datetime import datetime, timezone

    request_id = getattr(request.state, "request_id", "unknown")
    char_uuid = UUID(character_id)

    char = db.query(Character).filter(Character.id == char_uuid).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    if not char.in_calling:
        raise HTTPException(status_code=400, detail="This character is not currently in The Calling")

    # 5th time = permanent death, no roll allowed
    if char.times_called >= 4:
        raise HTTPException(status_code=400, detail="There is no fifth Calling.")

    stat_choice = req.get("stat_choice", "ip").lower()
    if stat_choice not in ("ip", "sp"):
        raise HTTPException(status_code=400, detail="stat_choice must be 'ip' or 'sp'")
    bap_bonus = int(req.get("bap_bonus", 0))

    # Determine chosen stat value
    chosen_stat_val = char.ip if stat_choice == "ip" else char.sp
    stat_label = "IP" if stat_choice == "ip" else "SP"

    # Player roll: 1d6 + chosen stat + edge + bap
    player_die_roll = roll_dice("1d6")[0]
    player_total = player_die_roll + chosen_stat_val + (char.edge or 0) + bap_bonus

    # SW difficulty die scales with character level
    if char.level <= 3:
        sw_die_str = "1d6"
    elif char.level <= 6:
        sw_die_str = "1d8"
    elif char.level <= 9:
        sw_die_str = "1d10"
    else:
        sw_die_str = "1d12"

    sw_die_roll = roll_dice(sw_die_str)[0]
    margin = player_total - sw_die_roll

    # Determine outcome
    if margin >= 4:
        outcome = "clean"
    elif margin >= 1:
        outcome = "scarred"
    else:
        outcome = "dead"

    # Apply DB changes
    char.times_called = (char.times_called or 0) + 1
    char.in_calling = False
    char.has_faced_calling_this_encounter = True

    if outcome in ("clean", "scarred"):
        char.dp = 1
        if outcome == "scarred":
            char.is_called = True
    else:
        # Death: archive the character and move all items to loot pool
        char.status = 'archived'
        char.dp = char.dp  # Leave DP as-is (at -10 or worse)
        db.query(InventoryItem).filter(
            InventoryItem.character_id == char.id
        ).update({"character_id": None, "is_equipped": False}, synchronize_session=False)

    db.commit()
    db.refresh(char)
    logger.info(f"[{request_id}] The Calling resolved for '{char.name}': {outcome} (margin {margin})")

    # Build result payload
    narrative_map = {
        "clean": f"{char.name} fights back The Calling — unmarked, unbroken.",
        "scarred": f"{char.name} survives The Calling, but marked by death.",
        "dead": f"{char.name} has fallen to The Calling. A Memory Echo remains."
    }
    result_payload = {
        "type": "calling_result",
        "character_id": str(char.id),
        "character_name": char.name,
        "survived": outcome != "dead",
        "outcome": outcome,
        "margin": margin,
        "player_roll": player_die_roll,
        "player_stat": chosen_stat_val,
        "edge": char.edge or 0,
        "bap": bap_bonus,
        "player_total": player_total,
        "sw_die": sw_die_str,
        "sw_roll": sw_die_roll,
        "sw_total": sw_die_roll,
        "stat_used": stat_label,
        "new_dp": char.dp,
        "times_called": char.times_called,
        "narrative": narrative_map[outcome]
    }

    # Persist to database
    result_message = Message(
        campaign_id=char.campaign_id,
        party_id=None,
        sender_id=current_user.id,
        sender_name=char.name,
        message_type="calling_result",
        content=narrative_map[outcome],
        extra_data=result_payload
    )
    db.add(result_message)
    db.commit()

    # Broadcast to campaign
    try:
        from routes.campaign_websocket import manager
        import asyncio
        asyncio.create_task(manager.broadcast(char.campaign_id, result_payload))
        # If character died, also broadcast so player drops to spectator
        if outcome == "dead":
            asyncio.create_task(manager.broadcast(char.campaign_id, {
                "type": "character_archived",
                "character_id": str(char.id),
                "character_name": char.name
            }))
    except Exception as e:
        logger.warning(f"Could not broadcast calling_result: {e}")

    return result_payload


@character_blp_fastapi.post("/{character_id}/battle-scar")
async def add_battle_scar(
    character_id: str,
    request: Request,
    req: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Append a battle scar description to a character's battle_scars JSON (SW only)."""
    from uuid import UUID
    from backend.models import CampaignMembership
    from datetime import datetime, timezone

    char_uuid = UUID(character_id)
    char = db.query(Character).filter(Character.id == char_uuid).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    # Verify SW
    membership = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == char.campaign_id,
        CampaignMembership.user_id == current_user.id
    ).first()
    if not membership or membership.role != 'story_weaver':
        raise HTTPException(status_code=403, detail="Only Story Weaver can add battle scars")

    scar_text = req.get("scar", "").strip()
    if not scar_text:
        raise HTTPException(status_code=400, detail="scar text is required")

    existing_scars = char.battle_scars or []
    new_scar = {
        "description": scar_text,
        "times_called": char.times_called,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    char.battle_scars = existing_scars + [new_scar]
    db.commit()

    return {"message": "Battle scar saved.", "battle_scars": char.battle_scars}


@character_blp_fastapi.post("/{character_id}/called-check")
async def called_check(
    character_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Trigger a Called check for a character with 'The Called' status (SW only).
    Rolls 1d6: 1-2 nightmare (-1 next roll), 3-5 peaceful, 6 vision (+1 next roll).
    Broadcasts result to campaign.
    """
    from uuid import UUID
    from backend.models import CampaignMembership
    from backend.roll_logic import roll_dice

    request_id = getattr(request.state, "request_id", "unknown")
    char_uuid = UUID(character_id)

    char = db.query(Character).filter(Character.id == char_uuid).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    if not char.is_called:
        raise HTTPException(status_code=400, detail="This character does not have 'The Called' status")

    membership = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == char.campaign_id,
        CampaignMembership.user_id == current_user.id
    ).first()
    if not membership or membership.role != 'story_weaver':
        raise HTTPException(status_code=403, detail="Only Story Weaver can trigger Called checks")

    roll = roll_dice("1d6")[0]
    if roll <= 2:
        effect = "nightmare"
        modifier = -1
        narrative = f"{char.name} is haunted by nightmares of The Calling. -1 to their next roll."
    elif roll <= 5:
        effect = "peaceful"
        modifier = 0
        narrative = f"{char.name} rests without incident."
    else:
        effect = "vision"
        modifier = 1
        narrative = f"{char.name} receives a prophetic vision from The Calling. +1 to their next roll."

    result = {
        "type": "called_check_result",
        "character_id": str(char.id),
        "character_name": char.name,
        "roll": roll,
        "effect": effect,
        "modifier": modifier,
        "narrative": narrative
    }

    try:
        from routes.campaign_websocket import manager
        import asyncio
        asyncio.create_task(manager.broadcast(char.campaign_id, result))
    except Exception as e:
        logger.warning(f"Could not broadcast called_check_result: {e}")

    logger.info(f"[{request_id}] Called check for '{char.name}': roll {roll} → {effect}")
    return result


@character_blp_fastapi.post("/{character_id}/cleanse-called")
async def cleanse_called(
    character_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove 'The Called' status from a character via ritual cleansing (SW only). Death counter remains."""
    from uuid import UUID
    from backend.models import CampaignMembership

    request_id = getattr(request.state, "request_id", "unknown")
    char_uuid = UUID(character_id)

    char = db.query(Character).filter(Character.id == char_uuid).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    membership = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == char.campaign_id,
        CampaignMembership.user_id == current_user.id
    ).first()
    if not membership or membership.role != 'story_weaver':
        raise HTTPException(status_code=403, detail="Only Story Weaver can cleanse The Called status")

    char.is_called = False
    db.commit()
    db.refresh(char)

    logger.info(f"[{request_id}] 'The Called' status cleared for '{char.name}' (times_called remains {char.times_called})")

    try:
        from routes.campaign_websocket import manager
        import asyncio
        asyncio.create_task(manager.broadcast(char.campaign_id, {
            "type": "called_cleansed",
            "character_id": str(char.id),
            "character_name": char.name
        }))
    except Exception as _be:
        logger.warning(f"Could not broadcast called_cleansed: {_be}")

    return {
        "message": f"'{char.name}' has been cleansed. The Called status removed.",
        "times_called": char.times_called
    }


# ============================================================================
# LEVELING SYSTEM
# ============================================================================

LEVEL_TABLE = {
    1:  {"max_dp": 10, "edge": 0, "bap": 1, "uses_per_encounter": 3,  "defense_die": "1d4"},
    2:  {"max_dp": 15, "edge": 1, "bap": 1, "uses_per_encounter": 6,  "defense_die": "1d4"},
    3:  {"max_dp": 20, "edge": 1, "bap": 2, "uses_per_encounter": 9,  "defense_die": "1d6"},
    4:  {"max_dp": 25, "edge": 2, "bap": 2, "uses_per_encounter": 12, "defense_die": "1d6"},
    5:  {"max_dp": 30, "edge": 2, "bap": 3, "uses_per_encounter": 15, "defense_die": "1d8"},
    6:  {"max_dp": 35, "edge": 3, "bap": 3, "uses_per_encounter": 18, "defense_die": "1d8"},
    7:  {"max_dp": 40, "edge": 3, "bap": 4, "uses_per_encounter": 21, "defense_die": "1d10"},
    8:  {"max_dp": 45, "edge": 4, "bap": 4, "uses_per_encounter": 24, "defense_die": "1d10"},
    9:  {"max_dp": 50, "edge": 4, "bap": 5, "uses_per_encounter": 27, "defense_die": "1d12"},
    10: {"max_dp": 55, "edge": 5, "bap": 5, "uses_per_encounter": 30, "defense_die": "1d12"},
}

WEAPON_OPTIONS_BY_LEVEL = {
    1: ["1d4"], 2: ["1d4"],
    3: ["1d6", "2d4"], 4: ["1d6", "2d4"],
    5: ["1d8", "2d6", "3d4"], 6: ["1d8", "2d6", "3d4"],
    7: ["1d10", "2d8", "3d6", "4d4"], 8: ["1d10", "2d8", "3d6", "4d4"],
    9: ["1d12", "2d10", "3d8", "4d6", "5d4"], 10: ["1d12", "2d10", "3d8", "4d6", "5d4"],
}

# New ability slot unlocked at these levels
NEW_SLOT_AT_LEVEL = {3, 5, 7, 9}


@character_blp_fastapi.post("/{character_id}/level-up")
async def level_up_character(
    character_id: str,
    request: Request,
    req: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Level up a character (SW only).
    Body: { heal_dp: bool, weapon_die: str }
    """
    from uuid import UUID
    from backend.models import CampaignMembership

    request_id = getattr(request.state, "request_id", "unknown")
    char_uuid = UUID(character_id)

    char = db.query(Character).filter(Character.id == char_uuid).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    # SW only
    membership = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == char.campaign_id,
        CampaignMembership.user_id == current_user.id
    ).first()
    if not membership or membership.role != 'story_weaver':
        raise HTTPException(status_code=403, detail="Only Story Weaver can level up characters")

    current_level = char.level or 1
    if current_level >= 10:
        raise HTTPException(status_code=400, detail="Character is already at max level (10)")

    new_level = current_level + 1
    stats = LEVEL_TABLE[new_level]
    valid_weapons = WEAPON_OPTIONS_BY_LEVEL[new_level]

    # Validate weapon die choice
    weapon_die = req.get("weapon_die", valid_weapons[0])
    if weapon_die not in valid_weapons:
        raise HTTPException(status_code=400, detail=f"Invalid weapon die for level {new_level}. Valid: {valid_weapons}")

    heal_dp = req.get("heal_dp", False)

    # Apply level-up stats
    old_max_dp = char.max_dp or 10
    old_dp = char.dp or 0

    char.level = new_level
    char.max_dp = stats["max_dp"]
    char.edge = stats["edge"]
    char.bap = stats["bap"]
    char.max_uses_per_encounter = stats["uses_per_encounter"]
    char.defense_die = stats["defense_die"]
    char.attack_style = weapon_die

    # Also update ability max_uses to match new level
    abilities = db.query(Ability).filter(Ability.character_id == char.id).all()
    for ability in abilities:
        ability.max_uses = stats["uses_per_encounter"]
        ability.uses_remaining = stats["uses_per_encounter"]

    # DP handling
    dp_gained = stats["max_dp"] - old_max_dp  # always +5
    if heal_dp:
        char.dp = stats["max_dp"]
    else:
        char.dp = min(old_dp + dp_gained, stats["max_dp"])

    db.commit()
    db.refresh(char)

    new_slot_unlocked = new_level in NEW_SLOT_AT_LEVEL

    logger.info(f"[{request_id}] {char.name} leveled up {current_level}→{new_level} (heal={heal_dp}, weapon={weapon_die})")

    result = {
        "character_id": str(char.id),
        "character_name": char.name,
        "old_level": current_level,
        "new_level": new_level,
        "new_dp": char.dp,
        "new_max_dp": char.max_dp,
        "new_edge": char.edge,
        "new_bap": char.bap,
        "new_uses_per_encounter": char.max_uses_per_encounter,
        "new_defense_die": char.defense_die,
        "new_weapon_die": char.attack_style,
        "new_slot_unlocked": new_slot_unlocked,
        "healed": heal_dp,
    }

    # Broadcast to campaign
    try:
        from routes.campaign_websocket import broadcast_level_up
        import asyncio
        asyncio.create_task(broadcast_level_up(
            char.campaign_id,
            str(char.id),
            char.name,
            current_level,
            new_level,
            new_slot_unlocked
        ))
    except Exception as _be:
        logger.warning(f"Could not broadcast level up: {_be}")

    return result


# ============================================================================
# BAP TOKEN SYSTEM
# ============================================================================

@character_blp_fastapi.post("/{character_id}/grant-bap-token")
async def grant_bap_token(
    character_id: str,
    request: Request,
    req: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    SW grants a banked BAP token to a character.
    Body: { token_type: 'encounter' | '24hrs' | 'sw_choice' }
    """
    from uuid import UUID
    from datetime import datetime, timedelta, timezone
    from backend.models import CampaignMembership

    char_uuid = UUID(character_id)
    char = db.query(Character).filter(Character.id == char_uuid).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    membership = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == char.campaign_id,
        CampaignMembership.user_id == current_user.id
    ).first()
    if not membership or membership.role != 'story_weaver':
        raise HTTPException(status_code=403, detail="SW only")

    token_type = req.get("token_type", "sw_choice")
    if token_type not in ("encounter", "24hrs", "sw_choice"):
        raise HTTPException(status_code=400, detail="token_type must be 'encounter', '24hrs', or 'sw_choice'")

    char.bap_token_active = True
    char.bap_token_type = token_type
    char.bap_token_expires_at = (
        datetime.now(timezone.utc) + timedelta(hours=24) if token_type == "24hrs" else None
    )
    db.commit()
    db.refresh(char)

    owner_id = str(char.user_id) if char.user_id else str(char.owner_id)
    try:
        from routes.campaign_websocket import broadcast_bap_granted
        import asyncio
        asyncio.create_task(broadcast_bap_granted(
            char.campaign_id, str(char.id), char.name, owner_id, token_type
        ))
    except Exception as _be:
        logger.warning(f"Could not broadcast bap_granted: {_be}")

    return {"character_id": str(char.id), "bap_token_active": True, "bap_token_type": token_type}


@character_blp_fastapi.post("/{character_id}/revoke-bap-token")
async def revoke_bap_token(
    character_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """SW revokes a character's BAP token."""
    from uuid import UUID
    from backend.models import CampaignMembership

    char_uuid = UUID(character_id)
    char = db.query(Character).filter(Character.id == char_uuid).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    membership = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == char.campaign_id,
        CampaignMembership.user_id == current_user.id
    ).first()
    if not membership or membership.role != 'story_weaver':
        raise HTTPException(status_code=403, detail="SW only")

    char.bap_token_active = False
    char.bap_token_expires_at = None
    char.bap_token_type = None
    db.commit()

    owner_id = str(char.user_id) if char.user_id else str(char.owner_id)
    try:
        from routes.campaign_websocket import broadcast_bap_revoked
        import asyncio
        asyncio.create_task(broadcast_bap_revoked(
            char.campaign_id, str(char.id), char.name, owner_id
        ))
    except Exception as _be:
        logger.warning(f"Could not broadcast bap_revoked: {_be}")

    return {"character_id": str(char.id), "bap_token_active": False}


@character_blp_fastapi.post("/{character_id}/bap-retroactive")
async def bap_retroactive(
    character_id: str,
    request: Request,
    req: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    SW marks a specific combat message as having received retroactive BAP.
    Body: { message_id: str }
    Updates the message's extra_data and broadcasts so all clients update that card.
    """
    from uuid import UUID
    from sqlalchemy.orm.attributes import flag_modified
    from backend.models import CampaignMembership

    char_uuid = UUID(character_id)
    char = db.query(Character).filter(Character.id == char_uuid).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    membership = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == char.campaign_id,
        CampaignMembership.user_id == current_user.id
    ).first()
    if not membership or membership.role != 'story_weaver':
        raise HTTPException(status_code=403, detail="SW only")

    message_id = req.get("message_id")
    if not message_id:
        raise HTTPException(status_code=400, detail="message_id is required")

    msg = db.query(Message).filter(Message.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    bap_bonus = char.bap or 1
    extra = dict(msg.extra_data or {})

    if extra.get("bap_awarded"):
        raise HTTPException(status_code=400, detail="BAP already awarded for this roll")

    individual_rolls = extra.get("individual_rolls", [])
    old_total_damage = extra.get("damage", 0)

    # Re-resolve each die with BAP added to the attacker's total
    new_individual_rolls = []
    new_total_damage = 0
    for roll in individual_rolls:
        new_roll = dict(roll)
        new_roll["bap_bonus"] = bap_bonus
        new_attacker_roll = (roll.get("attacker_roll") or 0) + bap_bonus
        new_roll["attacker_roll"] = new_attacker_roll
        defense_roll = roll.get("defense_roll", 0)
        new_margin = new_attacker_roll - defense_roll
        new_damage = max(0, new_margin)
        new_roll["margin"] = new_margin
        new_roll["damage"] = new_damage
        new_total_damage += new_damage
        new_individual_rolls.append(new_roll)

    damage_delta = new_total_damage - old_total_damage

    # Apply additional damage to defender
    defender_id = extra.get("defender_id")
    new_defender_dp = extra.get("defender_new_dp")
    if defender_id and damage_delta > 0:
        try:
            def_uuid = UUID(defender_id)
            defender_char = db.query(Character).filter(Character.id == def_uuid).first()
            if defender_char:
                defender_char.dp = max(defender_char.dp - damage_delta, -10)
                new_defender_dp = defender_char.dp
        except Exception:
            pass

    # Build updated narrative
    old_outcome = extra.get("outcome", "")
    if damage_delta > 0 and old_outcome in ("miss", "defend", "block"):
        new_narrative = f"{char.name} lands the blow with BAP! {new_total_damage} total damage."
    elif damage_delta > 0:
        new_narrative = f"{char.name} deals {damage_delta} additional damage with BAP! {new_total_damage} total."
    else:
        new_narrative = extra.get("narrative", "")

    # Persist updated roll data
    extra["bap_awarded"] = True
    extra["bap_bonus"] = bap_bonus
    extra["damage"] = new_total_damage
    extra["defender_new_dp"] = new_defender_dp
    extra["individual_rolls"] = new_individual_rolls
    if damage_delta > 0:
        extra["narrative"] = new_narrative
    msg.extra_data = extra
    flag_modified(msg, "extra_data")
    db.commit()

    try:
        from routes.campaign_websocket import broadcast_bap_retroactive
        import asyncio
        asyncio.create_task(broadcast_bap_retroactive(
            char.campaign_id, str(char.id), char.name, message_id, bap_bonus,
            new_individual_rolls, new_total_damage, damage_delta, new_defender_dp, new_narrative
        ))
    except Exception as _be:
        logger.warning(f"Could not broadcast bap_retroactive: {_be}")

    return {
        "message_id": message_id,
        "bap_awarded": True,
        "bap_bonus": bap_bonus,
        "new_total_damage": new_total_damage,
        "damage_delta": damage_delta,
        "defender_new_dp": new_defender_dp
    }


# ============================================================
# Player Notepad
# ============================================================

@character_blp_fastapi.get("/{character_id}/notes")
async def get_character_notes(
    character_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the player's private notes for their character."""
    from uuid import UUID
    char = db.query(Character).filter(Character.id == UUID(character_id)).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")
    if char.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You don't own this character")
    return {"notes": char.notes or ""}


@character_blp_fastapi.patch("/{character_id}/notes")
async def update_character_notes(
    character_id: str,
    req: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Save the player's private notes for their character."""
    from uuid import UUID
    char = db.query(Character).filter(Character.id == UUID(character_id)).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")
    if char.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You don't own this character")
    char.notes = req.get("notes", "")
    db.commit()
    return {"notes": char.notes}


# ============================================================
# Inventory
# ============================================================

# Tier → heal amount and buff/debuff modifier lookup
TIER_HEAL = {1: 6, 2: 8, 3: 10, 4: 12, 5: 12, 6: 16}
TIER_MOD  = {1: 1, 2: 2, 3: 3,  4: 4,  5: 5,  6: 6}
TIER_DIE  = {1: "1d6", 2: "1d8", 3: "1d10", 4: "1d12", 5: "2d6", 6: "2d8"}


def _item_dict(item: InventoryItem) -> dict:
    return {
        "id":           str(item.id),
        "character_id": str(item.character_id) if item.character_id else None,
        "name":         item.name,
        "item_type":    item.item_type,
        "quantity":     item.quantity,
        "description":  item.description,
        "tier":         item.tier,
        "effect_type":  item.effect_type,
        "bonus":        item.bonus,
        "bonus_type":   item.bonus_type,
        "is_equipped":  item.is_equipped,
        "given_by_sw":  item.given_by_sw,
        "created_at":   item.created_at.isoformat() if item.created_at else None,
    }


def _is_sw(campaign_id, user_id, db) -> bool:
    """Return True if user is the SW of the campaign."""
    from uuid import UUID
    m = db.query(CampaignMembership).filter(
        CampaignMembership.campaign_id == campaign_id,
        CampaignMembership.user_id == user_id
    ).first()
    return m is not None and m.role == 'story_weaver'


@character_blp_fastapi.get("/{character_id}/inventory")
async def get_inventory(
    character_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a character's inventory. Player owns it or SW of that campaign."""
    from uuid import UUID
    char = db.query(Character).filter(Character.id == UUID(character_id)).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")
    if char.user_id != current_user.id and not _is_sw(char.campaign_id, current_user.id, db):
        raise HTTPException(status_code=403, detail="Access denied")
    items = db.query(InventoryItem).filter(InventoryItem.character_id == UUID(character_id)).all()
    return {
        "currency": char.currency,
        "items": [_item_dict(i) for i in items]
    }


@character_blp_fastapi.post("/{character_id}/inventory", status_code=201)
async def add_inventory_item(
    character_id: str,
    req: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add an item to a character's inventory. Player adds to own; SW adds to any."""
    from uuid import UUID
    char = db.query(Character).filter(Character.id == UUID(character_id)).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")
    sw = _is_sw(char.campaign_id, current_user.id, db)
    if char.user_id != current_user.id and not sw:
        raise HTTPException(status_code=403, detail="Access denied")

    name = (req.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="Item name is required")

    item = InventoryItem(
        character_id = char.id,
        campaign_id  = char.campaign_id,
        name         = name,
        item_type    = req.get("item_type", "misc"),
        quantity     = max(1, int(req.get("quantity", 1))),
        description  = req.get("description"),
        tier         = req.get("tier"),
        effect_type  = req.get("effect_type"),
        bonus        = req.get("bonus"),
        given_by_sw  = sw,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    try:
        from routes.campaign_websocket import manager
        import asyncio
        asyncio.create_task(manager.broadcast(str(char.campaign_id), {
            "type":         "item_added",
            "character_id": str(char.id),
            "item":         _item_dict(item),
            "given_by_sw":  sw,
            "given_to":     char.name,
        }))
    except Exception:
        pass

    return _item_dict(item)


@character_blp_fastapi.delete("/{character_id}/inventory/{item_id}", status_code=204)
async def remove_inventory_item(
    character_id: str,
    item_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove an item. Player removes from own inventory; SW removes from any."""
    from uuid import UUID
    char = db.query(Character).filter(Character.id == UUID(character_id)).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")
    if char.user_id != current_user.id and not _is_sw(char.campaign_id, current_user.id, db):
        raise HTTPException(status_code=403, detail="Access denied")

    item = db.query(InventoryItem).filter(
        InventoryItem.id == UUID(item_id),
        InventoryItem.character_id == UUID(character_id)
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.commit()


@character_blp_fastapi.post("/{character_id}/inventory/{item_id}/use")
async def use_inventory_item(
    character_id: str,
    item_id: str,
    req: dict = {},
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Use a consumable item. Player only. Optionally target another PC (heal/buff)."""
    from uuid import UUID
    char = db.query(Character).filter(Character.id == UUID(character_id)).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")
    if char.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You don't own this character")

    item = db.query(InventoryItem).filter(
        InventoryItem.id == UUID(item_id),
        InventoryItem.character_id == UUID(character_id)
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.item_type != 'consumable':
        raise HTTPException(status_code=400, detail="Only consumables can be used this way")
    if item.item_type in ('key_item', 'quest_item'):
        raise HTTPException(status_code=400, detail="Key and quest items are removed by the SW when used")
    if item.quantity < 1:
        raise HTTPException(status_code=400, detail="No uses remaining")

    # Resolve target — defaults to self, ally PCs allowed for heal/buff
    target_id = req.get("target_id")
    target = char
    if target_id and target_id != character_id:
        t = db.query(Character).filter(Character.id == UUID(target_id)).first()
        if not t or str(t.campaign_id) != str(char.campaign_id):
            raise HTTPException(status_code=404, detail="Target not found in campaign")
        if item.effect_type not in ('heal', 'buff'):
            raise HTTPException(status_code=400, detail="Damage items go through combat rolls, not inventory use")
        target = t

    result = {"effect": "none", "value": 0, "new_dp": target.dp}

    if item.effect_type == 'heal' and item.tier:
        heal = TIER_HEAL.get(item.tier, 0)
        target.dp = min(target.max_dp, target.dp + heal)
        result = {"effect": "heal", "value": heal, "new_dp": target.dp}

    elif item.effect_type == 'buff' and item.tier:
        mod = TIER_MOD.get(item.tier, 0)
        result = {"effect": "buff", "value": mod, "rounds": mod, "new_dp": target.dp}

    # Decrement quantity; delete if exhausted
    item.quantity -= 1
    if item.quantity <= 0:
        db.delete(item)
    db.commit()

    # Broadcast to chat
    try:
        from routes.campaign_websocket import manager
        import asyncio
        tier_die = TIER_DIE.get(item.tier, "?") if item.tier else ""
        on_whom = f" on {target.name}" if target.id != char.id else ""
        if result["effect"] == "heal":
            msg = f"🧪 {char.name} uses {item.name}{on_whom} (Tier {item.tier} — {tier_die}) — restores {result['value']} DP!"
        elif result["effect"] == "buff":
            msg = f"⚡ {char.name} uses {item.name}{on_whom} (Tier {item.tier} — {tier_die}) — +{result['value']} for {result['rounds']} round(s)!"
        else:
            msg = f"🎒 {char.name} uses {item.name}{on_whom}."

        asyncio.create_task(manager.broadcast(str(char.campaign_id), {
            "type":           "item_used",
            "character_id":   str(char.id),
            "target_id":      str(target.id),
            "character_name": char.name,
            "target_name":    target.name,
            "item_name":      item.name,
            "item_id":        item_id,
            "new_quantity":   max(0, item.quantity),
            "result":         result,
            "chat_message":   msg,
        }))
    except Exception:
        pass

    return {**result, "item_id": item_id, "remaining": max(0, item.quantity)}


@character_blp_fastapi.patch("/{character_id}/currency")
async def update_currency(
    character_id: str,
    req: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a character's currency. Player updates own; SW updates any."""
    from uuid import UUID
    char = db.query(Character).filter(Character.id == UUID(character_id)).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")
    if char.user_id != current_user.id and not _is_sw(char.campaign_id, current_user.id, db):
        raise HTTPException(status_code=403, detail="Access denied")
    amount = req.get("currency")
    if amount is None or int(amount) < 0:
        raise HTTPException(status_code=422, detail="Currency must be 0 or more")
    char.currency = int(amount)
    db.commit()
    return {"currency": char.currency}


@character_blp_fastapi.patch("/{character_id}/inventory/{item_id}")
async def edit_inventory_item(
    character_id: str,
    item_id: str,
    req: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Edit an item. Player edits own; SW edits any."""
    from uuid import UUID
    char = db.query(Character).filter(Character.id == UUID(character_id)).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")
    if char.user_id != current_user.id and not _is_sw(char.campaign_id, current_user.id, db):
        raise HTTPException(status_code=403, detail="Access denied")

    item = db.query(InventoryItem).filter(
        InventoryItem.id == UUID(item_id),
        InventoryItem.character_id == UUID(character_id)
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if "name"        in req: item.name        = req["name"].strip() or item.name
    if "item_type"   in req: item.item_type   = req["item_type"]
    if "quantity"    in req: item.quantity     = max(1, int(req["quantity"]))
    if "description" in req: item.description = req["description"]
    if "tier"        in req: item.tier        = req["tier"]
    if "effect_type" in req: item.effect_type = req["effect_type"]
    if "bonus"       in req: item.bonus       = req["bonus"]
    if "bonus_type"  in req: item.bonus_type  = req["bonus_type"]
    db.commit()
    db.refresh(item)
    return _item_dict(item)


@character_blp_fastapi.post("/{character_id}/inventory/{item_id}/equip")
async def toggle_equip_item(
    character_id: str,
    item_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Toggle is_equipped on an equipment item. Player or SW."""
    from uuid import UUID
    char = db.query(Character).filter(Character.id == UUID(character_id)).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")
    if char.user_id != current_user.id and not _is_sw(char.campaign_id, current_user.id, db):
        raise HTTPException(status_code=403, detail="Access denied")

    item = db.query(InventoryItem).filter(
        InventoryItem.id == UUID(item_id),
        InventoryItem.character_id == UUID(character_id)
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.item_type != 'equipment':
        raise HTTPException(status_code=400, detail="Only equipment can be equipped")

    item.is_equipped = not item.is_equipped
    db.commit()

    # Broadcast so all clients update bonus totals
    try:
        from routes.campaign_websocket import manager
        import asyncio
        asyncio.create_task(manager.broadcast(str(char.campaign_id), {
            "type":         "item_equip_changed",
            "character_id": str(char.id),
            "item_id":      item_id,
            "is_equipped":  item.is_equipped,
            "item_name":    item.name,
            "bonus":        item.bonus,
            "bonus_type":   item.bonus_type,
        }))
    except Exception:
        pass

    return _item_dict(item)


@character_blp_fastapi.post("/{character_id}/inventory/{item_id}/give")
async def give_inventory_item(
    character_id: str,
    item_id: str,
    req: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Move an item to another character. Player gives from own; SW moves any."""
    from uuid import UUID
    char = db.query(Character).filter(Character.id == UUID(character_id)).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")
    if char.user_id != current_user.id and not _is_sw(char.campaign_id, current_user.id, db):
        raise HTTPException(status_code=403, detail="Access denied")

    target_id = req.get("target_character_id")
    if not target_id:
        raise HTTPException(status_code=422, detail="target_character_id is required")

    target = db.query(Character).filter(Character.id == UUID(target_id)).first()
    if not target or str(target.campaign_id) != str(char.campaign_id):
        raise HTTPException(status_code=404, detail="Target character not found in this campaign")

    item = db.query(InventoryItem).filter(
        InventoryItem.id == UUID(item_id),
        InventoryItem.character_id == UUID(character_id)
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    item.character_id = target.id
    item.is_equipped  = False  # unequip on transfer
    db.commit()
    db.refresh(item)

    try:
        from routes.campaign_websocket import manager
        import asyncio
        asyncio.create_task(manager.broadcast(str(char.campaign_id), {
            "type":          "item_given",
            "from_id":       str(char.id),
            "from_name":     char.name,
            "to_id":         str(target.id),
            "to_name":       target.name,
            "item":          _item_dict(item),
        }))
    except Exception:
        pass

    return _item_dict(item)