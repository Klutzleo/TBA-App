"""
Buffs and debuffs (rules v3.1).

- A buff or debuff is tied to a stat (IP, PP or SP) and only changes rolls that use that stat.
- One buff and one debuff per stat per target. A new one replaces the old one. Both apply to the roll, so a +3 buff
  and a -2 debuff on the same stat leave you at +1.
- Every one lasts 2 rounds: the round it is cast and the next. Duration counts down once per ROUND, not on each
  character's own turn, so the caster, the target and everyone in between get the same window.
- Tethers are a separate layer and never count here.

Effects with modifier_type 'custom' (Env Check and other Story Weaver effects that have no stat) apply to every roll.
Effects typed 'attack' or 'defense' (added by hand by the SW) apply to basic attacks and defenses only.
"""
from backend.models import ActiveEffect

STAT_KEYS = ("pp", "ip", "sp")


def effect_modifier(db, character_id, stat, extra_types=()) -> int:
    """Net modifier for a roll that uses `stat`: the strongest buff plus the strongest debuff that apply to it."""
    if character_id is None:
        return 0
    stat = (stat or "").lower()
    applicable = [
        e.modifier or 0
        for e in db.query(ActiveEffect).filter(ActiveEffect.character_id == character_id).all()
        if e.modifier_type in (stat, "custom") or e.modifier_type in extra_types
    ]
    buff = max((m for m in applicable if m > 0), default=0)
    debuff = min((m for m in applicable if m < 0), default=0)
    return buff + debuff


def add_effect(db, *, campaign_id, character_id, name, modifier, modifier_type, duration_rounds, applied_by):
    """Attach an effect. For a stat (or 'custom') effect, any existing effect of the same sign on the same target and
    stat is removed first, so there is never more than one buff and one debuff per stat. The caller commits."""
    modifier_type = (modifier_type or "custom").lower()
    if modifier_type in STAT_KEYS or modifier_type == "custom":
        for old in db.query(ActiveEffect).filter(
            ActiveEffect.character_id == character_id,
            ActiveEffect.modifier_type == modifier_type,
        ).all():
            if (old.modifier or 0) * (modifier or 0) > 0:      # same sign: buff replaces buff, debuff replaces debuff
                db.delete(old)
    effect = ActiveEffect(
        campaign_id=campaign_id, character_id=character_id, name=name, modifier=modifier,
        modifier_type=modifier_type, duration_rounds=duration_rounds, applied_by=applied_by,
    )
    db.add(effect)
    return effect


def tick_round(db, campaign_id) -> list:
    """A new round has started: count every timed effect in the campaign down by one and remove the ones that ran out.
    Returns the ids of the removed effects. The caller commits."""
    expired = []
    for e in db.query(ActiveEffect).filter(ActiveEffect.campaign_id == campaign_id).all():
        if e.duration_rounds is None:
            continue
        e.duration_rounds -= 1
        if e.duration_rounds <= 0:
            expired.append(str(e.id))
            db.delete(e)
    return expired
