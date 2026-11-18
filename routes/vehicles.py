"""
Vehicle routes (rules v3.1.1). The Story Weaver creates vehicles and the campaign owns them; players take stations on them.

All routes are JWT + campaign membership (they live under /api/campaigns). Creating, editing and deleting a vehicle is Story Weaver only.
A player may put only their own character on a station and take it off again; the Story Weaver can crew anyone.
"""
import logging
import re
import uuid
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.models import Ability, ActiveEffect, CampaignMembership, Character, User, VehicleCrew
from backend.leveling import VEHICLE_MAX_LEVEL, vehicle_stats
from backend.vehicles import (AOE_SLOTS, MULTI_CREW_STATIONS, RESERVED_MACROS, STATIONS, SYSTEM_EFFECTS, VEHICLE_KINDS, apply_level,
                              KNOCKOUT_ROUNDS, KNOCKOUT_TYPE, add_knockout, sync_systems, system_slots, vehicle_dict)
from routes.auth import get_current_user

logger = logging.getLogger(__name__)

vehicles_router = APIRouter(prefix="/api/campaigns", tags=["Vehicles"])


class VehicleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    level: int = Field(1, ge=1, le=VEHICLE_MAX_LEVEL)
    kind: str = "enclosed"
    weapon_die: Optional[str] = None
    visible_to_players: bool = True
    notes: Optional[str] = Field(None, max_length=2000)


class VehicleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    level: Optional[int] = Field(None, ge=1, le=VEHICLE_MAX_LEVEL)
    kind: Optional[str] = None
    weapon_die: Optional[str] = None
    visible_to_players: Optional[bool] = None
    notes: Optional[str] = Field(None, max_length=2000)


class SystemSet(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=60)
    macro_command: str = Field(..., min_length=2, max_length=25)
    power_source: Literal["PP", "IP", "SP"] = "IP"
    effect_type: Literal["damage", "heal", "buff", "debuff", "dot"] = "damage"
    ability_type: Literal["spell", "technique"] = "spell"
    effect_stat: Optional[Literal["PP", "IP", "SP"]] = None   # a buff or debuff changes rolls that use this stat (default: the stat the system uses)


class KnockoutSet(BaseModel):
    kind: Literal["system", "movement"]
    slot: Optional[int] = Field(None, ge=1, le=5)
    rounds: int = Field(KNOCKOUT_ROUNDS, ge=1, le=10)


class CrewAssign(BaseModel):
    character_id: str


def _member(db: Session, campaign_id: UUID, user: User) -> CampaignMembership:
    m = db.query(CampaignMembership).filter(CampaignMembership.campaign_id == campaign_id, CampaignMembership.user_id == user.id).first()
    if not m:
        raise HTTPException(status_code=403, detail="Not a member of this campaign")
    return m


def _uuid(value: str, what: str) -> UUID:
    try:
        return UUID(str(value))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail=f"{what} not found")


def _vehicle(db: Session, campaign_id: UUID, vehicle_id: str) -> Character:
    v = db.query(Character).filter(Character.id == _uuid(vehicle_id, "Vehicle"), Character.campaign_id == campaign_id,
                                   Character.is_vehicle == True).first()  # noqa: E712
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return v


def _check_weapon(level: int, weapon: Optional[str]) -> None:
    if weapon is not None and weapon not in vehicle_stats(level)["weapon_options"]:
        raise HTTPException(status_code=400, detail=f"A level {level} vehicle's weapon must be one of: {', '.join(vehicle_stats(level)['weapon_options'])}")


async def _announce(campaign_id: UUID, text: Optional[str] = None) -> None:
    """Tell everyone connected to refresh their vehicle list. A broadcast failure must never fail the request."""
    try:
        from routes.campaign_websocket import manager
        await manager.broadcast(campaign_id, {"type": "vehicles_changed", "campaign_id": str(campaign_id)})
        if text:
            # no_mirror: setup chatter shows in the app's chat but never goes to the public Discord channel
            await manager.broadcast(campaign_id, {"type": "system", "text": text, "no_mirror": True})
    except Exception as e:  # pragma: no cover - logging only
        logger.warning(f"vehicles_changed broadcast failed: {e}")


@vehicles_router.get("/{campaign_id}/vehicle-table")
async def vehicle_table(campaign_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """The vehicle numbers and station list, so the page carries no hand-typed copy that could drift from the rules."""
    from backend.leveling import VEHICLE_LEVELS
    _member(db, _uuid(campaign_id, "Campaign"), current_user)
    return {
        "levels": {str(k): v for k, v in VEHICLE_LEVELS.items()},
        "stations": [{"key": k, "label": v[0], "stat": v[1].upper(), "help": v[2]} for k, v in STATIONS.items()],
        "kinds": list(VEHICLE_KINDS),
    }


@vehicles_router.get("/{campaign_id}/vehicles")
async def list_vehicles(campaign_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """The campaign's vehicles. The Story Weaver sees all of them, players only the ones marked visible."""
    cid = _uuid(campaign_id, "Campaign")
    m = _member(db, cid, current_user)
    q = db.query(Character).filter(Character.campaign_id == cid, Character.is_vehicle == True)  # noqa: E712
    if m.role != "story_weaver":
        q = q.filter(Character.visible_to_players == True)  # noqa: E712
    return [vehicle_dict(db, v, m.role == "story_weaver") for v in q.order_by(Character.created_at).all()]


@vehicles_router.post("/{campaign_id}/vehicles", status_code=201)
async def create_vehicle(campaign_id: str, req: VehicleCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    cid = _uuid(campaign_id, "Campaign")
    if _member(db, cid, current_user).role != "story_weaver":
        raise HTTPException(status_code=403, detail="Only the Story Weaver can add a vehicle")
    if req.kind not in VEHICLE_KINDS:
        raise HTTPException(status_code=400, detail="kind must be 'open' or 'enclosed'")
    _check_weapon(req.level, req.weapon_die)
    # A vehicle has no PP/IP/SP of its own: whoever operates it brings their stats. The columns are non-null, so they are 0.
    v = Character(id=uuid.uuid4(), name=req.name.strip(), owner_id=str(current_user.id), user_id=None, campaign_id=cid,
                  is_npc=True, is_vehicle=True, vehicle_kind=req.kind, level=req.level, pp=0, ip=0, sp=0, dp=0, max_dp=0, edge=0,
                  bap=0, attack_style="1d4", defense_die="1d4", max_uses_per_encounter=0, current_uses=0,
                  visible_to_players=req.visible_to_players, notes=req.notes, status="active")
    apply_level(v, req.level, req.weapon_die)
    db.add(v)
    db.commit()
    db.refresh(v)
    await _announce(cid, f"🚀 {v.name} (level {v.level}) joins the campaign" if v.visible_to_players else None)
    return vehicle_dict(db, v, True)


@vehicles_router.patch("/{campaign_id}/vehicles/{vehicle_id}")
async def update_vehicle(campaign_id: str, vehicle_id: str, req: VehicleUpdate, db: Session = Depends(get_db),
                         current_user: User = Depends(get_current_user)):
    cid = _uuid(campaign_id, "Campaign")
    if _member(db, cid, current_user).role != "story_weaver":
        raise HTTPException(status_code=403, detail="Only the Story Weaver can change a vehicle")
    v = _vehicle(db, cid, vehicle_id)
    if req.kind is not None:
        if req.kind not in VEHICLE_KINDS:
            raise HTTPException(status_code=400, detail="kind must be 'open' or 'enclosed'")
        v.vehicle_kind = req.kind
    level = req.level if req.level is not None else v.level
    _check_weapon(level, req.weapon_die)
    if req.name is not None:
        v.name = req.name.strip()
    if req.visible_to_players is not None:
        v.visible_to_players = req.visible_to_players
    if req.notes is not None:
        v.notes = req.notes
    if req.level is not None or req.weapon_die is not None:
        apply_level(v, level, req.weapon_die)
        sync_systems(db, v)
    db.commit()
    db.refresh(v)
    await _announce(cid)
    return vehicle_dict(db, v, True)


@vehicles_router.delete("/{campaign_id}/vehicles/{vehicle_id}", status_code=204)
async def delete_vehicle(campaign_id: str, vehicle_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    cid = _uuid(campaign_id, "Campaign")
    if _member(db, cid, current_user).role != "story_weaver":
        raise HTTPException(status_code=403, detail="Only the Story Weaver can remove a vehicle")
    v = _vehicle(db, cid, vehicle_id)
    db.query(VehicleCrew).filter(VehicleCrew.vehicle_id == v.id).delete()
    db.query(Ability).filter(Ability.character_id == v.id).delete()
    db.delete(v)
    db.commit()
    await _announce(cid)


@vehicles_router.put("/{campaign_id}/vehicles/{vehicle_id}/systems/{slot}")
async def set_system(campaign_id: str, vehicle_id: str, slot: int, req: SystemSet, db: Session = Depends(get_db),
                     current_user: User = Depends(get_current_user)):
    """Put a system (a spell or technique the crew can fire) in one of the vehicle's slots. The die comes from the Vehicle Leveling
    Table for that slot, and the 2nd and 4th slots are area attacks, whatever the Story Weaver sends."""
    cid = _uuid(campaign_id, "Campaign")
    if _member(db, cid, current_user).role != "story_weaver":
        raise HTTPException(status_code=403, detail="Only the Story Weaver can install a system")
    v = _vehicle(db, cid, vehicle_id)
    slots = {s["slot"]: s for s in system_slots(v.level or 1)}
    if slot not in slots:
        raise HTTPException(status_code=400, detail=f"A level {v.level} vehicle has no system slot {slot} (it has {len(slots)})")
    macro = req.macro_command.strip().lower()
    if not re.fullmatch(r"/[a-z][a-z0-9_]{1,23}", macro):
        raise HTTPException(status_code=400, detail="The command must start with / and use letters, numbers or _ (for example /missiles)")
    if macro in RESERVED_MACROS:
        raise HTTPException(status_code=400, detail=f"{macro} is already a built-in command. Pick another")
    clash = db.query(Ability).filter(Ability.character_id == v.id, Ability.macro_command == macro, Ability.slot_number != slot).first()
    if clash:
        raise HTTPException(status_code=409, detail=f"{macro} is already used by another system on this vehicle")
    row = db.query(Ability).filter(Ability.character_id == v.id, Ability.slot_number == slot).first()
    if row is None:
        row = Ability(id=uuid.uuid4(), character_id=v.id, slot_number=slot, ability_type=req.ability_type, display_name=req.display_name.strip(),
                      macro_command=macro, power_source=req.power_source, effect_type=req.effect_type, die=slots[slot]["die"])
        db.add(row)
    row.ability_type, row.display_name, row.macro_command = req.ability_type, req.display_name.strip(), macro
    row.power_source, row.effect_type, row.debuff_stat = req.power_source, req.effect_type, req.effect_stat
    row.die, row.is_aoe, row.is_summon = slots[slot]["die"], slot in AOE_SLOTS, False
    row.max_uses = row.uses_remaining = v.max_uses_per_encounter or 3
    db.commit()
    await _announce(cid)
    return vehicle_dict(db, v, True)


@vehicles_router.delete("/{campaign_id}/vehicles/{vehicle_id}/systems/{slot}")
async def clear_system(campaign_id: str, vehicle_id: str, slot: int, db: Session = Depends(get_db),
                       current_user: User = Depends(get_current_user)):
    cid = _uuid(campaign_id, "Campaign")
    if _member(db, cid, current_user).role != "story_weaver":
        raise HTTPException(status_code=403, detail="Only the Story Weaver can remove a system")
    v = _vehicle(db, cid, vehicle_id)
    row = db.query(Ability).filter(Ability.character_id == v.id, Ability.slot_number == slot).first()
    if not row:
        raise HTTPException(status_code=404, detail="Nothing is installed in that slot")
    db.delete(row)
    db.commit()
    await _announce(cid)
    return vehicle_dict(db, v, True)


@vehicles_router.post("/{campaign_id}/vehicles/{vehicle_id}/knockouts")
async def knock_out(campaign_id: str, vehicle_id: str, req: KnockoutSet, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    """Story Weaver: knock out one system or the vehicle's movement for 2 rounds (a landed called shot, sabotage, hacking). It costs
    the vehicle no DP. A knocked-out system can't be fired until it comes back."""
    cid = _uuid(campaign_id, "Campaign")
    if _member(db, cid, current_user).role != "story_weaver":
        raise HTTPException(status_code=403, detail="Only the Story Weaver can knock out a system")
    v = _vehicle(db, cid, vehicle_id)
    slot = None
    if req.kind == "system":
        slot = req.slot
        if slot is None or not db.query(Ability).filter(Ability.character_id == v.id, Ability.slot_number == slot).first():
            raise HTTPException(status_code=400, detail="Pick a slot that has a system installed")
    add_knockout(db, cid, v, req.kind, slot, req.rounds, applied_by=current_user.username)
    db.commit()
    await _announce(cid)
    return vehicle_dict(db, v, True)


@vehicles_router.delete("/{campaign_id}/vehicles/{vehicle_id}/knockouts/{effect_id}")
async def restore_knockout(campaign_id: str, vehicle_id: str, effect_id: str, db: Session = Depends(get_db),
                           current_user: User = Depends(get_current_user)):
    """Story Weaver: bring a system or the movement back online early (for example when an Engineer's repair roll earns it)."""
    cid = _uuid(campaign_id, "Campaign")
    if _member(db, cid, current_user).role != "story_weaver":
        raise HTTPException(status_code=403, detail="Only the Story Weaver can restore a system")
    v = _vehicle(db, cid, vehicle_id)
    row = db.query(ActiveEffect).filter(ActiveEffect.id == _uuid(effect_id, "Knock-out"), ActiveEffect.character_id == v.id,
                                        ActiveEffect.modifier_type == KNOCKOUT_TYPE).first()
    if not row:
        raise HTTPException(status_code=404, detail="That knock-out is already over")
    db.delete(row)
    db.commit()
    await _announce(cid)
    return vehicle_dict(db, v, True)


@vehicles_router.put("/{campaign_id}/vehicles/{vehicle_id}/crew/{station}")
async def take_station(campaign_id: str, vehicle_id: str, station: str, req: CrewAssign, db: Session = Depends(get_db),
                       current_user: User = Depends(get_current_user)):
    """Put a character on a station. The Story Weaver can crew anyone; a player can only crew their own character."""
    cid = _uuid(campaign_id, "Campaign")
    m = _member(db, cid, current_user)
    is_sw = m.role == "story_weaver"
    if station not in STATIONS:
        raise HTTPException(status_code=400, detail=f"Unknown station. Choose one of: {', '.join(STATIONS)}")
    v = _vehicle(db, cid, vehicle_id)
    if not is_sw and not v.visible_to_players:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    c = db.query(Character).filter(Character.id == _uuid(req.character_id, "Character"), Character.campaign_id == cid).first()
    if not c or c.is_vehicle or c.is_object or c.is_summon:
        raise HTTPException(status_code=404, detail="Character not found")
    if c.status in ("dead", "rejected", "pending_approval"):
        raise HTTPException(status_code=400, detail=f"{c.name} can't crew a vehicle right now")
    if not is_sw and (c.is_npc or c.user_id != current_user.id):
        raise HTTPException(status_code=403, detail="You can only put your own character on a station")

    existing = db.query(VehicleCrew).filter(VehicleCrew.vehicle_id == v.id).all()
    held = next((r for r in existing if r.station == station), None)
    if held and held.character_id != c.id:
        who = db.query(Character).filter(Character.id == held.character_id).first()
        raise HTTPException(status_code=409, detail=f"The {STATIONS[station][0]} station is already held by {who.name if who else 'someone'}")
    others = [r for r in existing if r.character_id != c.id]
    if station == "operator" and any(r.station in MULTI_CREW_STATIONS for r in others):
        raise HTTPException(status_code=409, detail="This vehicle is crewed by stations. Clear them before naming a single operator")
    if station in MULTI_CREW_STATIONS and any(r.station == "operator" for r in others):
        raise HTTPException(status_code=409, detail="This vehicle has a single operator. Clear the operator before adding stations")

    # One station at a time: moving a character leaves wherever they were.
    db.query(VehicleCrew).filter(VehicleCrew.character_id == c.id).delete()
    db.add(VehicleCrew(id=uuid.uuid4(), vehicle_id=v.id, character_id=c.id, station=station))
    db.commit()
    await _announce(cid, f"🧑‍🚀 {c.name} takes the {STATIONS[station][0]} station on {v.name}")
    return vehicle_dict(db, v, is_sw)


@vehicles_router.delete("/{campaign_id}/vehicles/{vehicle_id}/crew/{station}")
async def leave_station(campaign_id: str, vehicle_id: str, station: str, db: Session = Depends(get_db),
                        current_user: User = Depends(get_current_user)):
    """Clear a station. The Story Weaver can clear any; a player can only step off their own character's station."""
    cid = _uuid(campaign_id, "Campaign")
    m = _member(db, cid, current_user)
    v = _vehicle(db, cid, vehicle_id)
    row = db.query(VehicleCrew).filter(VehicleCrew.vehicle_id == v.id, VehicleCrew.station == station).first()
    if not row:
        raise HTTPException(status_code=404, detail="Nobody holds that station")
    who = db.query(Character).filter(Character.id == row.character_id).first()
    if m.role != "story_weaver" and not (who and who.user_id == current_user.id):
        raise HTTPException(status_code=403, detail="You can only leave your own station")
    db.delete(row)
    db.commit()
    await _announce(cid, f"{who.name if who else 'Someone'} leaves the {STATIONS.get(station, (station,))[0]} station on {v.name}")
    return vehicle_dict(db, v, m.role == "story_weaver")
