"""
Tethers (rules v3.1).

- Their own scale: +1 to +4 / -1 to -4 (no duration). Grief and Emptiness run -1 to -3, and the SW may turn a Grief Tether
  into a +1 to +3 bonus when the character faces the one who killed the fallen.
- A character has up to 3 STORY Tethers. Marked by Death, Grief and Emptiness are extra and do not use those slots.
- If more than one Tether could apply to a roll, only the strongest bonus and the strongest penalty count, and you take the
  difference (a +3 and a -4 leave -1). A Tether is its own layer on top of buffs and debuffs, and can add to or take from a
  Calling roll when the Story Weaver says one fits the moment.
"""
from datetime import datetime
from uuid import uuid4

STORY_TETHER_LIMIT = 3
EXTRA_SOURCES = ("marked", "grief", "emptiness")   # Tethers that do not use one of the 3 story slots


def source_of(tether) -> str:
    return (tether.get("source") or "story")


def story_tether_count(tethers) -> int:
    return sum(1 for t in (tethers or []) if source_of(t) not in EXTRA_SOURCES)


def clamp_tether_modifier(modifier, source="story") -> int:
    """-4..+4 for story and Marked Tethers; -3..+3 for Grief and Emptiness."""
    lim = 3 if source in ("grief", "emptiness") else 4
    try:
        value = int(modifier)
    except (TypeError, ValueError):
        value = 0
    return max(-lim, min(lim, value))


def net_modifier(modifiers) -> int:
    """The strongest bonus plus the strongest penalty (a +3 and a -4 leaves -1)."""
    mods = [int(m or 0) for m in modifiers]
    return max((m for m in mods if m > 0), default=0) + min((m for m in mods if m < 0), default=0)


def active_net(tethers):
    """(net modifier, [{"description", "modifier"}]) over the ACTIVE Tethers. The rows list every active Tether; only the
    strongest bonus and strongest penalty count toward the net."""
    rows = [
        {"description": (t.get("description") or "Tether")[:60], "modifier": int(t.get("modifier") or 0)}
        for t in (tethers or [])
        if t.get("is_active") and (t.get("modifier") or 0) != 0
    ]
    return net_modifier(r["modifier"] for r in rows), rows


def new_tether(description, modifier, source="story", active=False, tether_id=None) -> dict:
    return {
        "id": tether_id or str(uuid4()),
        "description": description,
        "is_active": bool(active),
        "modifier": clamp_tether_modifier(modifier, source),
        "source": source,
    }


def apply_ally_death(db, ally):
    """An Ally died for good (rules v3.1). The Ally's player gets an Emptiness Tether (-1 to start; the SW sets the weight
    by how deep the bond ran), anyone else Bonded to the Ally gets a Grief Tether, and every Combo with the Ally is lost.
    Returns the names of the characters who gained a Tether."""
    from backend.models import Bond, Character
    owner = db.query(Character).filter(Character.id == ally.parent_character_id).first() if ally.parent_character_id else None
    affected = []
    for bond in db.query(Bond).filter(
        Bond.broken_at == None,  # noqa: E711
        (Bond.character_id_a == ally.id) | (Bond.character_id_b == ally.id),
    ).all():
        bond.broken_at = datetime.utcnow()                       # every Combo with the Ally is lost
        partner_id = bond.character_id_b if bond.character_id_a == ally.id else bond.character_id_a
        partner = db.query(Character).filter(Character.id == partner_id).first()
        if partner and not partner.is_npc and (owner is None or partner.id != owner.id):
            partner.tethers = list(partner.tethers or []) + [new_tether(
                f"Grief: the loss of {ally.name}", -1, source="grief", active=True, tether_id=f"{bond.id}_grief")]
            affected.append(partner.name)
    if owner and not owner.is_npc:
        owner.tethers = list(owner.tethers or []) + [new_tether(
            f"Emptiness: the loss of {ally.name}", -1, source="emptiness", active=False)]
        affected.insert(0, owner.name)
    return affected
