"""
routes/lba.py
LBA ("Lore for the Bad-Ass" / "Lore for Being Awesome") — authenticated
endpoints: authoring (create/edit/delete your own package), the full-tier
reveal (any public package, login required to read story/NPCs/items/quests/
attachments), and Start Campaign (clones NPCs+abilities+items into a brand
new campaign the caller becomes Story Weaver of).

Teaser-tier, no-login browsing lives in routes/public_lba.py. See the plan
doc for the full design — two visibility tiers, not one flat public page.
"""
import logging
import uuid
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.auth.jwt import get_current_user
from backend.db import get_db
from backend.models import (
    Ability,
    Campaign,
    CampaignMembership,
    Character,
    InventoryItem,
    LBA_CONTENT_RATINGS,
    LBA_FORMATS,
    LBA_GENRES,
    LBA_PARTY_SIZES,
    LbaPackage,
    LoreEntry,
    User,
)

logger = logging.getLogger(__name__)

lba_router = APIRouter(prefix="/api/lba", tags=["LBA"])


# ============================================================================
# Shared helpers
# ============================================================================

def _is_owner(package: LbaPackage, user: User) -> bool:
    if str(package.author_user_id) == str(user.id):
        return True
    return str(user.id) in [str(x) for x in (package.co_author_user_ids or [])]


def _clean_tags(raw) -> list:
    """Same defensive shape as any other free-text-ish list field the author
    controls — don't trust the client to self-limit."""
    if not isinstance(raw, list):
        return []
    seen = []
    for t in raw:
        if not isinstance(t, str):
            continue
        t = t.strip().lower()[:30]
        if t and t not in seen:
            seen.append(t)
        if len(seen) >= 15:
            break
    return seen


def _clean_genres(raw) -> list:
    """Multi-value, but still constrained to LBA_GENRES — not freeform like
    tags. Silently drops anything not in the allowed list rather than
    erroring, same defensive posture as the other dropdown fields."""
    if not isinstance(raw, list):
        return []
    seen = []
    for g in raw:
        if isinstance(g, str) and g in LBA_GENRES and g not in seen:
            seen.append(g)
    return seen


def _clean_side_quests(raw) -> list:
    if not isinstance(raw, list):
        return []
    out = []
    for sq in raw:
        if not isinstance(sq, dict):
            continue
        title = (sq.get("title") or "").strip()[:200]
        hook = (sq.get("hook") or "").strip()[:2000]
        if title:
            out.append({"title": title, "hook": hook})
        if len(out) >= 25:
            break
    return out


def _teaser_dict(p: LbaPackage) -> dict:
    return {
        "id": str(p.id),
        "title": p.title,
        "tagline": p.tagline,
        "format": p.format,
        "suggested_party_size": p.suggested_party_size,
        "content_rating": p.content_rating,
        "genres": p.genres or [],
        "tags": p.tags or [],
        "is_public": p.is_public,
        "view_count": p.view_count or 0,
        "adoption_count": p.adoption_count or 0,
        "author_user_id": str(p.author_user_id),
        "co_author_user_ids": [str(x) for x in (p.co_author_user_ids or [])],
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def _full_dict(p: LbaPackage, db: Session) -> dict:
    """Teaser fields plus everything behind the login-required tier."""
    npcs = []
    if p.core_npc_character_ids:
        chars = db.query(Character).filter(Character.id.in_(p.core_npc_character_ids)).all()
        npcs = [
            {"id": str(c.id), "name": c.name, "level": c.level, "portrait_url": c.portrait_url,
             "pp": c.pp, "ip": c.ip, "sp": c.sp, "notes": c.notes}
            for c in chars
        ]
    items = []
    if p.core_item_ids:
        rows = db.query(InventoryItem).filter(InventoryItem.id.in_(p.core_item_ids)).all()
        items = [
            {"id": str(i.id), "name": i.name, "item_type": i.item_type, "description": i.description,
             "tier": i.tier}
            for i in rows
        ]
    return {
        **_teaser_dict(p),
        "homebrew_note": p.homebrew_note,
        "story_text": p.story_text,
        "world_text": p.world_text,
        "core_npcs": npcs,
        "core_items": items,
        "side_quests": p.side_quests or [],
        "attachments": p.attachments or [],
    }


# ============================================================================
# Authoring
# ============================================================================

class LbaPackageWrite(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    tagline: Optional[str] = Field(None, max_length=300)
    format: str = "one_shot"
    suggested_party_size: Optional[str] = None
    content_rating: str = "all_ages"
    genres: List[str] = []
    tags: List[str] = []
    homebrew_note: Optional[str] = None
    story_text: Optional[str] = None
    world_text: Optional[str] = None
    core_npc_character_ids: List[UUID] = []
    core_item_ids: List[UUID] = []
    side_quests: List[dict] = []
    co_author_user_ids: List[UUID] = []
    is_public: bool = False


def _apply_write(package: LbaPackage, req: LbaPackageWrite, author_user_id, db: Session):
    """Shared validation + assignment for create and update. Silently
    ignores an NPC/item id that doesn't actually belong to the author (or a
    co-author) — rather than erroring, which would let a crafted id probe
    for the existence of another SW's private content via a validation-error
    side channel. Just drops anything not owned."""
    if req.format in LBA_FORMATS:
        package.format = req.format
    if req.suggested_party_size is None or req.suggested_party_size in LBA_PARTY_SIZES:
        package.suggested_party_size = req.suggested_party_size
    if req.content_rating in LBA_CONTENT_RATINGS:
        package.content_rating = req.content_rating

    package.title = req.title.strip()
    package.tagline = (req.tagline or "").strip()[:300] or None
    package.genres = _clean_genres(req.genres)
    package.tags = _clean_tags(req.tags)
    package.homebrew_note = req.homebrew_note
    package.story_text = req.story_text
    package.world_text = req.world_text
    package.side_quests = _clean_side_quests(req.side_quests)
    package.is_public = bool(req.is_public)

    allowed_owner_ids = {str(author_user_id)} | {str(x) for x in req.co_author_user_ids}

    if req.core_npc_character_ids:
        owned_npcs = db.query(Character.id).filter(
            Character.id.in_(req.core_npc_character_ids),
            Character.is_npc == True,  # noqa: E712
        ).all()
        # Further restrict to campaigns the author/co-authors actually SW —
        # cheap membership check reusing CampaignMembership.
        valid_ids = []
        for (npc_id,) in owned_npcs:
            npc = db.query(Character).filter(Character.id == npc_id).first()
            is_sw = db.query(CampaignMembership).filter(
                CampaignMembership.campaign_id == npc.campaign_id,
                CampaignMembership.user_id.in_(list(allowed_owner_ids)),
                CampaignMembership.role == "story_weaver",
            ).first()
            if is_sw:
                valid_ids.append(str(npc_id))
        package.core_npc_character_ids = valid_ids
    else:
        package.core_npc_character_ids = []

    if req.core_item_ids:
        owned_items = db.query(InventoryItem).filter(InventoryItem.id.in_(req.core_item_ids)).all()
        valid_item_ids = []
        for item in owned_items:
            is_sw = db.query(CampaignMembership).filter(
                CampaignMembership.campaign_id == item.campaign_id,
                CampaignMembership.user_id.in_(list(allowed_owner_ids)),
                CampaignMembership.role == "story_weaver",
            ).first()
            if is_sw:
                valid_item_ids.append(str(item.id))
        package.core_item_ids = valid_item_ids
    else:
        package.core_item_ids = []

    # co-authors must be real users — drop anything else
    real_co_authors = db.query(User.id).filter(User.id.in_(req.co_author_user_ids)).all()
    package.co_author_user_ids = [str(u.id) for u in real_co_authors]


@lba_router.post("/packages", status_code=201)
async def create_package(
    req: LbaPackageWrite,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    package = LbaPackage(author_user_id=current_user.id)
    _apply_write(package, req, current_user.id, db)
    db.add(package)
    db.commit()
    db.refresh(package)
    return _full_dict(package, db)


@lba_router.get("/packages/mine")
async def list_my_packages(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Every package the caller authored or co-authors, any visibility state.
    Filters co-authorship in Python rather than a JSONB `.contains()` query —
    that compiles to Postgres' `@>` operator, which SQLite (used in tests)
    doesn't support. Package counts per user are small enough that this is
    cheap; revisit only if that stops being true."""
    uid = str(current_user.id)
    own = db.query(LbaPackage).filter(LbaPackage.author_user_id == current_user.id).all()
    others = db.query(LbaPackage).filter(LbaPackage.author_user_id != current_user.id).all()
    co_authored = [p for p in others if uid in [str(x) for x in (p.co_author_user_ids or [])]]
    packages = sorted(own + co_authored, key=lambda p: p.updated_at or p.created_at, reverse=True)
    return [_teaser_dict(p) for p in packages]


@lba_router.get("/packages/{package_id}/edit")
async def get_package_for_edit(
    package_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    package = db.query(LbaPackage).filter(LbaPackage.id == package_id).first()
    if not package or not _is_owner(package, current_user):
        raise HTTPException(status_code=404, detail="Package not found")
    return _full_dict(package, db)


@lba_router.patch("/packages/{package_id}")
async def update_package(
    package_id: UUID,
    req: LbaPackageWrite,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    package = db.query(LbaPackage).filter(LbaPackage.id == package_id).first()
    if not package or not _is_owner(package, current_user):
        raise HTTPException(status_code=404, detail="Package not found")
    _apply_write(package, req, package.author_user_id, db)
    db.commit()
    db.refresh(package)
    return _full_dict(package, db)


@lba_router.delete("/packages/{package_id}", status_code=204)
async def delete_package(
    package_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Author only — not co-authors, simplest ownership model for v1."""
    package = db.query(LbaPackage).filter(LbaPackage.id == package_id).first()
    if not package or str(package.author_user_id) != str(current_user.id):
        raise HTTPException(status_code=404, detail="Package not found")
    db.delete(package)
    db.commit()


# ============================================================================
# Reading the full tier (any public package — login required, ownership not)
# ============================================================================

@lba_router.get("/packages/{package_id}/full")
async def get_public_package_full(
    package_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The explicit spoiler-reveal endpoint — any logged-in user, any public
    package. Does not increment view_count (that's the teaser page-open
    action, in routes/public_lba.py) or adoption_count (that's Start
    Campaign specifically, a much stronger signal than just reading)."""
    package = db.query(LbaPackage).filter(
        LbaPackage.id == package_id, LbaPackage.is_public == True  # noqa: E712
    ).first()
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")
    return _full_dict(package, db)


# ============================================================================
# Start Campaign — clone NPCs (+ abilities) and items into a brand-new campaign
# ============================================================================

def _clone_character(db: Session, source: Character, new_campaign_id) -> Character:
    clone = Character(
        id=uuid.uuid4(),
        name=source.name,
        owner_id=source.owner_id,
        user_id=None,
        campaign_id=new_campaign_id,
        is_npc=True,
        is_ally=False,
        level=source.level,
        pp=source.pp, ip=source.ip, sp=source.sp,
        dp=source.max_dp, max_dp=source.max_dp,  # fresh copy starts at full DP
        edge=source.edge, bap=source.bap,
        attack_style=source.attack_style,
        defense_die=source.defense_die,
        weapon=source.weapon, armor=source.armor,
        notes=source.notes,
        max_uses_per_encounter=source.max_uses_per_encounter,
        current_uses=source.max_uses_per_encounter,
        weapon_bonus=source.weapon_bonus,
        armor_bonus=source.armor_bonus,
        chat_color=source.chat_color,
        visible_to_players=source.visible_to_players,
        portrait_url=source.portrait_url,
    )
    db.add(clone)

    for ab in db.query(Ability).filter(Ability.character_id == source.id).all():
        db.add(Ability(
            id=uuid.uuid4(),
            character_id=clone.id,
            slot_number=ab.slot_number,
            ability_type=ab.ability_type,
            display_name=ab.display_name,
            macro_command=ab.macro_command,
            power_source=ab.power_source,
            effect_type=ab.effect_type,
            debuff_stat=ab.debuff_stat,
            die=ab.die,
            is_aoe=ab.is_aoe,
            is_summon=ab.is_summon,
            max_uses=ab.max_uses,
            uses_remaining=ab.max_uses,
        ))
    return clone


def _clone_item(db: Session, source: InventoryItem, new_campaign_id, char_id_map: dict) -> InventoryItem:
    new_char_id = char_id_map.get(str(source.character_id)) if source.character_id else None
    clone = InventoryItem(
        id=uuid.uuid4(),
        character_id=new_char_id,
        campaign_id=new_campaign_id,
        name=source.name,
        item_type=source.item_type,
        quantity=source.quantity,
        description=source.description,
        tier=source.tier,
        effect_type=source.effect_type,
        bonus=source.bonus,
        bonus_type=source.bonus_type,
        is_equipped=False,
        given_by_sw=False,
        secret=source.secret,
    )
    db.add(clone)
    return clone


@lba_router.post("/packages/{package_id}/start-campaign")
async def start_campaign_from_package(
    package_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Clones the package's core NPCs (with abilities) and items into a
    brand-new campaign, seeds the new campaign's private notes/Lore tab with
    the package's story/world/quest text, and increments adoption_count —
    the real popularity signal, not raw views. From this point the new SW's
    copy is fully independent of the source package and of every other
    adopter's copy."""
    package = db.query(LbaPackage).filter(
        LbaPackage.id == package_id, LbaPackage.is_public == True  # noqa: E712
    ).first()
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")

    from routes.campaigns import generate_join_code

    # SW notes (private, never shown to players) gets everything spoiler-sensitive:
    # the plot itself, side quests (hooks/solutions), and homebrew rules notes.
    # The Lore tab (all campaign members can read it) only gets world_text —
    # setting/flavor content, meant to be spoiler-free by design. See the plan
    # doc: these two were briefly swapped, caught and fixed 2026-09-30 before
    # this ever shipped, since the Lore tab's real visibility is "any member,"
    # not SW-only.
    quest_lines = "\n\n".join(
        f"**{sq.get('title', '')}**\n{sq.get('hook', '')}" for sq in (package.side_quests or [])
    )
    sw_notes_parts = [p for p in [
        package.story_text,
        f"## Side Quests\n\n{quest_lines}" if quest_lines else None,
        f"--- Homebrew notes ---\n{package.homebrew_note}" if package.homebrew_note else None,
    ] if p]

    campaign = Campaign(
        id=uuid.uuid4(),
        name=package.title,
        description=package.tagline or "",
        join_code=generate_join_code(db),
        story_weaver_id=current_user.id,
        created_by_user_id=current_user.id,
        sw_notes="\n\n".join(sw_notes_parts),
    )
    db.add(campaign)
    db.flush()  # need campaign.id for the membership row and clones below

    db.add(CampaignMembership(campaign_id=campaign.id, user_id=current_user.id, role="story_weaver"))

    char_id_map = {}
    for npc_id in (package.core_npc_character_ids or []):
        source = db.query(Character).filter(Character.id == npc_id).first()
        if not source:
            continue
        clone = _clone_character(db, source, campaign.id)
        char_id_map[str(npc_id)] = clone.id

    for item_id in (package.core_item_ids or []):
        source = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
        if source:
            _clone_item(db, source, campaign.id, char_id_map)

    if package.world_text:
        db.add(LoreEntry(
            campaign_id=campaign.id,
            title="World (from LBA)",
            content=package.world_text,
            entry_type="lore",
            created_by=current_user.id,
        ))

    package.adoption_count = (package.adoption_count or 0) + 1

    db.commit()
    db.refresh(campaign)

    try:
        from backend.stats_tracker import track_campaign_created, commit_stats
        track_campaign_created(db, str(current_user.id))
        commit_stats(db, str(current_user.id))
    except Exception:
        pass

    return {"ok": True, "campaign_id": str(campaign.id), "join_code": campaign.join_code}
