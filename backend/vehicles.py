"""
Vehicles (rules v3.1.1).

A vehicle is a Character row with is_npc and is_vehicle set (the same trick Objects use), so it has DP, Edge, a weapon die, a
defense die and a uses pool without any new combat plumbing. The numbers come from the vehicle table in schemas/leveling_v3_1.json
via backend/leveling.py. Who is operating it lives in the vehicle_crew table.

Size is story, not stats: a bike and a battleship at the same level have the same numbers, and the Story Weaver picks the level.
"""
from backend.leveling import VEHICLE_MAX_LEVEL, vehicle_stats

# station -> (label, the stat the crew member rolls, what the station does). The stats are the suggested pairings from the Core.
STATIONS = {
    "operator": ("Operator", "pp", "Flies or drives a single-pilot vehicle: attacks, defends and maneuvers with the vehicle's dice and Edge."),
    "gunner": ("Gunner", "pp", "Attack: the vehicle's weapon die + PP + the vehicle's Edge."),
    "defense_officer": ("Defense Officer", "pp", "Defense: the vehicle's defense die + PP + the vehicle's Edge."),
    "captain": ("Captain", "sp", "Support: 1d6 + SP + Edge, added to the Gunner's or Defense Officer's next roll."),
    "pilot": ("Pilot", "ip", "Support: 1d6 + IP + Edge, added to the Gunner's or Defense Officer's next roll."),
    "engineer": ("Engineer", "ip", "Repair: 1d6 + IP + Edge, restores that much DP to the vehicle."),
}
MULTI_CREW_STATIONS = tuple(s for s in STATIONS if s != "operator")
VEHICLE_KINDS = ("open", "enclosed")


def apply_level(vehicle, level: int, weapon: str = None) -> None:
    """Set a vehicle's numbers from the vehicle table for `level`. Keeps the chosen weapon die if it is still allowed at the new level,
    otherwise the plain single-die option. A vehicle that gains max DP gains that much DP too, like a character levelling up."""
    row = vehicle_stats(level)
    old_max = vehicle.max_dp or 0
    vehicle.level = level
    vehicle.max_dp = row["max_dp"]
    if vehicle.dp is None or old_max == 0:
        vehicle.dp = row["max_dp"]
    elif row["max_dp"] > old_max:
        vehicle.dp = vehicle.dp + (row["max_dp"] - old_max)
    vehicle.dp = min(vehicle.dp, row["max_dp"])
    vehicle.edge = row["edge"]
    vehicle.defense_die = row["defense_die"]
    options = row["weapon_options"]
    chosen = weapon or vehicle.attack_style
    vehicle.attack_style = chosen if chosen in options else options[0]
    gained = row["uses_per_encounter"] - (vehicle.max_uses_per_encounter or 0)
    vehicle.max_uses_per_encounter = row["uses_per_encounter"]
    vehicle.current_uses = row["uses_per_encounter"] if gained != 0 or vehicle.current_uses is None else vehicle.current_uses


def system_slots(level: int) -> list:
    """The system (spell/technique) slots a vehicle has at this level: [{"slot": 1, "die": "1d6"}, ...]."""
    row = vehicle_stats(level)
    return [{"slot": n, "die": row[f"slot_{n}_die"]} for n in range(1, 6) if row.get(f"slot_{n}_die")]


AOE_SLOTS = (2, 4)            # the Vehicle Leveling Table makes the 2nd and 4th system area attacks
SYSTEM_EFFECTS = ("damage", "heal", "buff", "debuff", "dot")
RESERVED_MACROS = {"/attack", "/defense", "/defend", "/pp", "/ip", "/sp", "/roll", "/cast", "/technique", "/support", "/repair", "/s",
                   "/say", "/ooc", "/whisper", "/help", "/initiative", "/scene", "/rest", "/env"}


def systems_view(db, vehicle) -> list:
    """The vehicle's system slots at its level, each with the ability set in it (or None)."""
    from backend.models import Ability
    abilities = {a.slot_number: a for a in db.query(Ability).filter(Ability.character_id == vehicle.id).all()}
    out = []
    for slot in system_slots(vehicle.level or 1):
        a = abilities.get(slot["slot"])
        out.append({
            "slot": slot["slot"], "die": slot["die"], "aoe": slot["slot"] in AOE_SLOTS,
            "ability": None if a is None else {
                "display_name": a.display_name, "macro_command": a.macro_command, "power_source": a.power_source,
                "effect_type": a.effect_type, "ability_type": a.ability_type, "effect_stat": a.debuff_stat,
            },
        })
    return out


def sync_systems(db, vehicle) -> None:
    """After a level change: each system takes the die its slot has at the new level, and a system whose slot no longer exists is removed."""
    from backend.models import Ability
    slots = {s["slot"]: s for s in system_slots(vehicle.level or 1)}
    for a in db.query(Ability).filter(Ability.character_id == vehicle.id).all():
        slot = slots.get(a.slot_number)
        if slot is None:
            db.delete(a)
        else:
            a.die = slot["die"]
            a.is_aoe = a.slot_number in AOE_SLOTS
            a.max_uses = vehicle.max_uses_per_encounter or a.max_uses
            a.uses_remaining = a.max_uses


KNOCKOUT_TYPE = "knockout"      # ActiveEffect.modifier_type for a system or the movement knocked out (no stat modifier, just a timer)
KNOCKOUT_ROUNDS = 2


def knockouts(db, vehicle_id) -> list:
    from backend.models import ActiveEffect
    return db.query(ActiveEffect).filter(ActiveEffect.character_id == vehicle_id, ActiveEffect.modifier_type == KNOCKOUT_TYPE).all()


def add_knockout(db, campaign_id, vehicle, kind: str, slot=None, rounds: int = KNOCKOUT_ROUNDS, applied_by: str = "Story Weaver"):
    """Knock out one system (by slot) or the vehicle's movement for `rounds`, at no DP cost (rules v3.1.1). Knocking out the same
    thing again just restarts its timer. The caller commits."""
    from backend.models import ActiveEffect
    for old in knockouts(db, vehicle.id):
        d = old.data or {}
        if d.get("kind") == kind and d.get("slot") == slot:
            db.delete(old)
    label = "Movement" if kind == "movement" else f"System {slot}"
    effect = ActiveEffect(campaign_id=campaign_id, character_id=vehicle.id, name=f"{label} knocked out", modifier=0, modifier_type=KNOCKOUT_TYPE,
                          duration_rounds=rounds, applied_by=applied_by, data={"kind": kind, "slot": slot})
    db.add(effect)
    return effect


def system_knockout(db, vehicle_id, slot):
    """The knock-out holding system `slot` offline, or None."""
    for e in knockouts(db, vehicle_id):
        d = e.data or {}
        if d.get("kind") == "system" and d.get("slot") == slot:
            return e
    return None


def knockouts_view(db, vehicle) -> list:
    from backend.models import Ability
    names = {a.slot_number: a.display_name for a in db.query(Ability).filter(Ability.character_id == vehicle.id).all()}
    out = []
    for e in knockouts(db, vehicle.id):
        d = e.data or {}
        out.append({"id": str(e.id), "kind": d.get("kind"), "slot": d.get("slot"), "rounds_left": e.duration_rounds,
                    "name": "Movement" if d.get("kind") == "movement" else names.get(d.get("slot"), f"System {d.get('slot')}")})
    return out


def crew_rows(db, vehicle_id):
    from backend.models import VehicleCrew
    return db.query(VehicleCrew).filter(VehicleCrew.vehicle_id == vehicle_id).all()


def crew_character(db, vehicle_id, station: str):
    """The character holding `station` on the vehicle, or None when it is unmanned."""
    from backend.models import Character, VehicleCrew
    row = db.query(VehicleCrew).filter(VehicleCrew.vehicle_id == vehicle_id, VehicleCrew.station == station).first()
    return db.query(Character).filter(Character.id == row.character_id).first() if row else None


def crew_post(db, character):
    """(vehicle, station) for the vehicle this character is crewing, or (None, None) when they are on no station."""
    from backend.models import Character, VehicleCrew
    row = db.query(VehicleCrew).filter(VehicleCrew.character_id == character.id).first()
    if not row:
        return None, None
    vehicle = db.query(Character).filter(Character.id == row.vehicle_id).first()
    return (vehicle, row.station) if vehicle else (None, None)


def defense_crew(db, vehicle):
    """Whose Physical Power a vehicle defends with: the Defense Officer, else the single Operator. Nobody (None) when
    the station is empty, the holder is down, or the vehicle itself is disabled (0 DP or less). An unmanned vehicle
    still defends with its defense die + its own Edge, just with no character stat added."""
    if (vehicle.dp or 0) <= 0:
        return None
    for station in ("defense_officer", "operator"):
        c = crew_character(db, vehicle.id, station)
        if c is not None and (c.dp or 0) > 0:
            return c
    return None


SUPPORT_STATIONS = {"captain": "sp", "pilot": "ip"}   # the stat each adds with (Core: Captain SP, Pilot IP)


def set_add(db, vehicle_id, station: str, target: str, amount: int, note: str = None) -> None:
    """Store a support roll for the vehicle's next attack or defense roll. One per station: a new one replaces the old."""
    import uuid as _uuid
    from backend.models import VehicleCrewAdd
    row = db.query(VehicleCrewAdd).filter(VehicleCrewAdd.vehicle_id == vehicle_id, VehicleCrewAdd.station == station).first()
    if row is None:
        db.add(VehicleCrewAdd(id=_uuid.uuid4(), vehicle_id=vehicle_id, station=station, target=target, amount=amount, note=note))
    else:
        row.target, row.amount, row.note = target, amount, note
    db.flush()


def take_adds(db, vehicle_id, target: str) -> int:
    """Use up every waiting support add for `target` ("attack" or "defense") and return their total. The deletes ride on the
    caller's next commit, so a roll that fails before then leaves the adds waiting."""
    from backend.models import VehicleCrewAdd
    rows = db.query(VehicleCrewAdd).filter(VehicleCrewAdd.vehicle_id == vehicle_id, VehicleCrewAdd.target == target).all()
    total = sum(r.amount for r in rows)
    for r in rows:
        db.delete(r)
    return total


def pending_adds(db, vehicle_id) -> list:
    from backend.models import VehicleCrewAdd
    return [{"station": r.station, "target": r.target, "amount": r.amount}
            for r in db.query(VehicleCrewAdd).filter(VehicleCrewAdd.vehicle_id == vehicle_id).order_by(VehicleCrewAdd.created_at).all()]


def vehicle_state(vehicle) -> str:
    return "critical" if vehicle.dp <= -10 else ("disabled" if vehicle.dp <= 0 else "active")


def vehicle_dict(db, vehicle, is_sw: bool = False) -> dict:
    """What the clients see for a vehicle: numbers, state and crew. The Story Weaver's notes go only to the Story Weaver."""
    from backend.models import Character
    crew = {}
    for row in crew_rows(db, vehicle.id):
        c = db.query(Character).filter(Character.id == row.character_id).first()
        if c:
            crew[row.station] = {"character_id": str(c.id), "name": c.name, "is_npc": bool(c.is_npc), "owner_user_id": str(c.user_id) if c.user_id else None}
    level = vehicle.level or 1
    table = vehicle_stats(level)
    state = vehicle_state(vehicle)
    return {
        "id": str(vehicle.id), "campaign_id": str(vehicle.campaign_id), "name": vehicle.name, "level": level,
        "kind": vehicle.vehicle_kind or "enclosed", "dp": vehicle.dp, "max_dp": vehicle.max_dp, "edge": vehicle.edge,
        "weapon_die": vehicle.attack_style, "weapon_options": list(table["weapon_options"]), "defense_die": vehicle.defense_die,
        "uses": vehicle.current_uses, "max_uses": vehicle.max_uses_per_encounter, "systems": systems_view(db, vehicle),
        "state": state, "visible_to_players": bool(vehicle.visible_to_players), "portrait_url": vehicle.portrait_url,
        "notes": vehicle.notes if is_sw else None, "crew": crew, "pending_adds": pending_adds(db, vehicle.id), "knockouts": knockouts_view(db, vehicle), "max_level": VEHICLE_MAX_LEVEL,
    }
