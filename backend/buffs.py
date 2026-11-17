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


DAMAGE_EFFECT_TYPE = "dot"   # modifier_type of a Damage Effect (poison, burning, bleeding...). It carries no stat modifier.


def add_damage_effect(db, *, campaign_id, character_id, name, die, stat, caster_name, duration_rounds=2):
    """A Damage Effect landed. The target takes `die` once at the start of their next turn and may resist for half (rules
    v3.1). A new one replaces the old one. If their next turn never comes (the encounter ends), it runs out after
    `duration_rounds`. The caller commits."""
    for old in db.query(ActiveEffect).filter(ActiveEffect.character_id == character_id,
                                             ActiveEffect.modifier_type == DAMAGE_EFFECT_TYPE).all():
        db.delete(old)
    effect = ActiveEffect(
        campaign_id=campaign_id, character_id=character_id, name=name, modifier=0, modifier_type=DAMAGE_EFFECT_TYPE,
        duration_rounds=duration_rounds, applied_by=caster_name,
        data={"die": die, "stat": (stat or "PP").upper(), "caster": caster_name, "ability": name},
    )
    db.add(effect)
    return effect


def remove_damage_effect(db, character_id, caster_name=None, name=None):
    """Take a Damage Effect back off (a Boost that turned a landed cast into a resisted one). The caller commits."""
    q = db.query(ActiveEffect).filter(ActiveEffect.character_id == character_id,
                                      ActiveEffect.modifier_type == DAMAGE_EFFECT_TYPE)
    for e in q.all():
        if (caster_name is None or e.applied_by == caster_name) and (name is None or e.name == name):
            db.delete(e)
