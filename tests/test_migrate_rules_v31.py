"""
scripts/migrate_rules_v31.py: moves existing characters to the v3.1 numbers.
Health is kept as a PERCENTAGE of max, the old values are saved first, and --undo puts them back.
"""
import importlib.util
import os
import uuid

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_migrate_rules_v31.db")
os.environ.setdefault("API_KEY", "devkey")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("migrate_rules_v31", os.path.join(ROOT, "scripts", "migrate_rules_v31.py"))
mig = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mig)


@pytest.fixture()
def world():
    from backend.db import SessionLocal, init_db
    from backend.models import Ability, Campaign, CampaignMembership, Character, User
    init_db()
    db = SessionLocal()
    tag = uuid.uuid4().hex[:8]
    sw = User(id=uuid.uuid4(), email=f"sw_{tag}@example.com", username=f"sw_{tag}", hashed_password="x")
    db.add(sw)
    db.commit()
    camp = Campaign(id=uuid.uuid4(), name="Migration test", description="x" * 12, created_by_user_id=sw.id,
                    created_by_id=str(sw.id), story_weaver_id=sw.id)
    db.add(camp)
    db.commit()
    db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=sw.id, role="story_weaver"))
    db.commit()

    def make(name, level, dp, max_dp, uses=None, **kw):
        c = Character(id=uuid.uuid4(), name=f"{name}_{tag}", owner_id=str(sw.id), user_id=sw.id, campaign_id=camp.id,
                      level=level, pp=2, ip=3, sp=1, dp=dp, max_dp=max_dp, edge=0, attack_style="1d4",
                      defense_die="1d4", max_uses_per_encounter=uses or 3 * level, current_uses=uses or 3 * level, **kw)
        db.add(c)
        db.commit()
        db.add(Ability(id=uuid.uuid4(), character_id=c.id, slot_number=1, ability_type="spell", display_name="Zap",
                       macro_command="/zap", power_source="IP", effect_type="damage", die="1d6",
                       max_uses=3 * level, uses_remaining=2))
        db.commit()
        return c

    yield dict(db=db, make=make, tag=tag, camp=camp, Character=Character, Ability=Ability)
    mig.undo(db)   # leave the shared test DB as we found it
    db.close()


def _reload(w, c):
    w["db"].expire_all()
    return w["db"].query(w["Character"]).filter_by(id=c.id).one()


def test_percentages():
    f = mig.new_current_dp
    assert f(14, 15, 10) == 9            # 93% of 15 -> 9 of 10
    assert f(9, 15, 10) == 6
    assert f(15, 15, 10) == 10           # full stays full
    assert f(1, 55, 26) == 1             # a living character never rounds to 0
    assert f(60, 55, 26) == 26           # never above the new max
    assert f(0, 15, 10) == 0 and f(-6, 15, 10) == -6          # down characters untouched
    assert f(5, 15, 10, in_calling=True) == 5                  # The Calling untouched
    assert f(7, 0, 10) == 10                                   # no usable old max: treat as full


def test_apply_moves_everyone_to_the_table_and_keeps_health_percentage(world):
    pc = world["make"]("Hero", 2, 9, 15)             # 60% -> 6 of 10
    full = world["make"]("Fresh", 5, 30, 30)         # full stays full: 16
    npc = world["make"]("Goon", 1, 6, 10, is_npc=True)   # 60% of 8 -> 5
    mig.apply(world["db"])
    pc, full, npc = (_reload(world, c) for c in (pc, full, npc))
    assert (pc.max_dp, pc.dp) == (10, 6)
    assert (full.max_dp, full.dp) == (16, 16)
    assert (npc.max_dp, npc.dp) == (8, 5)
    assert pc.max_uses_per_encounter == 4 and pc.current_uses == 4        # level 2 + 2
    ab = world["db"].query(world["Ability"]).filter_by(character_id=pc.id).one()
    assert (ab.max_uses, ab.uses_remaining) == (4, 4)


def test_down_and_calling_characters_keep_their_dp_but_get_the_new_max(world):
    down = world["make"]("Down", 3, -4, 20)
    calling = world["make"]("Calling", 3, -12, 20, in_calling=True)
    mig.apply(world["db"])
    down, calling = _reload(world, down), _reload(world, calling)
    assert (down.max_dp, down.dp) == (12, -4)
    assert (calling.max_dp, calling.dp) == (12, -12)


def test_summons_and_objects_are_left_alone(world):
    summon = world["make"]("Spirit", 2, 1, 1, is_summon=True, is_npc=True)
    chest = world["make"]("Chest", 1, 0, 0, is_object=True, is_npc=True)
    rows, skipped = mig.plan(world["db"])
    mine = {r["name"] for r in rows}
    assert summon.name not in mine and chest.name not in mine
    mig.apply(world["db"])
    assert (_reload(world, summon).max_dp, _reload(world, chest).max_dp) == (1, 0)


def test_dry_run_writes_nothing_and_apply_twice_is_harmless(world):
    c = world["make"]("Twice", 4, 20, 25)
    mig.plan(world["db"])
    assert _reload(world, c).max_dp == 25                    # plan() is a dry run
    mig.apply(world["db"])
    first = (_reload(world, c).max_dp, _reload(world, c).dp)
    assert first == (14, 11)                                  # 80% of 14 = 11.2 -> 11
    mig.apply(world["db"])                                    # already has a backup row: skipped
    assert (_reload(world, c).max_dp, _reload(world, c).dp) == first


def test_undo_restores_every_old_value(world):
    c = world["make"]("Undo", 3, 17, 20, uses=9)
    mig.apply(world["db"])
    assert _reload(world, c).max_dp == 12
    mig.undo(world["db"])
    c = _reload(world, c)
    assert (c.max_dp, c.dp, c.max_uses_per_encounter, c.current_uses) == (20, 17, 9, 9)
    ab = world["db"].query(world["Ability"]).filter_by(character_id=c.id).one()
    assert (ab.max_uses, ab.uses_remaining) == (9, 2)


def test_an_active_encounter_is_detected(world):
    from backend.models import Encounter
    before = mig.active_encounters(world["db"])
    enc = Encounter(id=uuid.uuid4(), campaign_id=world["camp"].id, is_active=True)
    world["db"].add(enc)
    world["db"].commit()
    assert mig.active_encounters(world["db"]) == before + 1
    world["db"].delete(enc)
    world["db"].commit()


def test_cli_dry_run_writes_nothing_and_apply_refuses_during_an_encounter(world, capsys):
    from backend.models import Encounter
    c = world["make"]("Cli", 2, 15, 15)
    assert mig.main([]) == 0
    assert "Dry run: nothing was written" in capsys.readouterr().out
    assert _reload(world, c).max_dp == 15
    enc = Encounter(id=uuid.uuid4(), campaign_id=world["camp"].id, is_active=True)
    world["db"].add(enc)
    world["db"].commit()
    try:
        assert mig.main(["--apply"]) == 2
        assert "Refusing" in capsys.readouterr().out
        assert _reload(world, c).max_dp == 15            # nothing written
    finally:
        world["db"].delete(enc)
        world["db"].commit()


def test_a_dry_run_does_not_even_create_the_backup_tables(world):
    from sqlalchemy import inspect, text
    world["db"].execute(text(f"DROP TABLE IF EXISTS {mig.ABILITY_BACKUP}"))
    world["db"].execute(text(f"DROP TABLE IF EXISTS {mig.CHAR_BACKUP}"))
    world["db"].commit()
    mig.plan(world["db"])
    insp = inspect(world["db"].get_bind())
    assert not insp.has_table(mig.CHAR_BACKUP) and not insp.has_table(mig.ABILITY_BACKUP)
