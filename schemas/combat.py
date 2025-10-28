from marshmallow import Schema, fields, validate

class CharacterSchema(Schema):
    name = fields.String(required=True)
    stats = fields.Dict(
        keys=fields.String(validate=validate.OneOf(["IP", "PP", "SP"])),
        values=fields.Integer(),
        required=True
    )
    traits = fields.List(fields.String(), load_default=[])
    bap = fields.Integer()
    edge = fields.Integer()
    defense_die = fields.String()
    spells = fields.Dict()
    current_dp = fields.Integer()
    
class EquipmentSchema(Schema):
    """Defines a piece of equipment used in combat."""
    name = fields.String(required=True, metadata={"description": "Equipment name"})
    type = fields.String(
        required=True,
        metadata={
            "example": "armor",
            "description": "Type of equipment (armor, shield, weapon)"
        }
    )
    bonus = fields.Integer(
        load_default=0,
        metadata={"description": "Flat bonus applied during combat"}
    )
    durability = fields.Integer(
        load_default=100,
        metadata={"description": "Remaining durability (0–100)"}
    )
    traits = fields.List(
        fields.String(),
        load_default=[],
        metadata={"description": "Special traits or effects granted by the item"}
    )

class CombatRollRequest(Schema):
    """Request payload for resolving a single combat roll."""
    attacker = fields.Nested(CharacterSchema, required=True, metadata={"description": "Attacking character"})
    defender = fields.Nested(CharacterSchema, required=True, metadata={"description": "Defending character"})
    weapon = fields.Nested(EquipmentSchema, required=False, metadata={"description": "Weapon used by attacker"})
    armor = fields.List(fields.Nested(EquipmentSchema), required=False, metadata={"description": "List of armor pieces worn by defender"})
    shield = fields.Nested(EquipmentSchema, required=False, metadata={"description": "Shield used by defender"})
    weapon_die = fields.String(required=True, metadata={"example": "1d8", "description": "Die used for weapon damage"})
    defense_die = fields.String(required=True, metadata={"example": "1d6", "description": "Die used for defense roll"})
    distance = fields.String(load_default="melee", metadata={"example": "melee", "description": "Combat range (melee, ranged, etc.)"})
    bap = fields.Boolean(load_default=False, metadata={"description": "Whether BAP (Battle Advantage Protocol) is active"})
    log = fields.Boolean(load_default=False, metadata={"description": "Whether to return detailed combat log"})
    encounter_id = fields.String(required=False, metadata={"description": "Optional encounter identifier for logging or tracking"})

class CombatRollResponse(Schema):
    """Response payload for a resolved combat roll."""
    result = fields.String(required=True, metadata={"example": "win", "description": "Outcome of the roll (win, loss, draw)"})
    damage = fields.Integer(required=False, metadata={"description": "Damage dealt to defender"})
    blocked_by = fields.String(required=False, metadata={"example": "shield", "description": "What blocked the attack, if any"})
    log = fields.List(fields.String(), required=False, metadata={"description": "Detailed log of combat events"})
    notes = fields.List(fields.String(), required=False, metadata={"description": "Additional notes or trait effects"})

class SimulatedCombatResponse(Schema):
    """Response payload for a multi-round combat simulation."""
    rounds = fields.List(fields.Dict(), required=True, metadata={"description": "List of round-by-round combat results"})
    outcome = fields.String(required=True, metadata={"example": "attacker wins", "description": "Final outcome of the simulation"})
    log = fields.List(fields.String(), required=False, metadata={"description": "Verbose log of all combat actions"})
    summary = fields.Dict(required=False, metadata={"description": "Summary of damage, turns, and effects"})

class SpellCastRequest(Schema):
    """Request payload for casting a spell in combat."""
    caster = fields.Nested(CharacterSchema, required=True, metadata={"description": "Character casting the spell"})
    target = fields.Nested(CharacterSchema, required=True, metadata={"description": "Target of the spell"})
    spell = fields.Dict(
        required=True,
        metadata={
            "description": "Spell details including name, traits, power, and range",
            "example": {
                "name": "Fireball",
                "traits": ["burn", "area"],
                "power": 7,
                "range": "medium"
            }
        }
    )
    distance = fields.String(load_default="medium", metadata={"description": "Distance between caster and target"})
    log = fields.Boolean(load_default=False, metadata={"description": "Whether to return detailed spellcasting log"})
    encounter_id = fields.String(required=False, metadata={"description": "Optional encounter identifier for tracking"})

class SpellCastResponse(Schema):
    """Response payload for a resolved spellcast."""
    outcome = fields.String(required=True, metadata={"example": "hit", "description": "Result of the spellcast"})
    damage = fields.Integer(required=False, metadata={"description": "Damage dealt to target, if any"})
    effects = fields.List(fields.String(), required=False, metadata={"description": "List of triggered spell effects"})
    log = fields.List(fields.String(), required=False, metadata={"description": "Narrative log of spellcasting events"})
    notes = fields.List(fields.String(), required=False, metadata={"description": "Additional notes or trait effects"})

class EncounterRequestSchema(Schema):
    actors = fields.List(fields.Nested(CharacterSchema), required=True)
    rounds = fields.Integer(load_default=3)
    log = fields.Boolean(load_default=True)
    encounter_id = fields.String(required=False)

class ActorStatusSchema(Schema):
    status = fields.Dict(keys=fields.String(), values=fields.List(fields.String()))

class ActorStatusForActorSchema(Schema):
    actor = fields.String()
    active_effects = fields.List(fields.String())

class AllActorStatusSchema(Schema):
    initiative_order = fields.List(fields.String())
    status = fields.Dict(keys=fields.String(), values=fields.List(fields.String()))

class ActorSummarySchema(Schema):
    actor = fields.String()
    timeline = fields.List(fields.Dict())

class ActorCompareSchema(Schema):
    actor_a = fields.Dict()
    actor_b = fields.Dict()

class EchoesSchema(Schema):
    actor = fields.String()
    echoes = fields.List(fields.Dict())
    count = fields.Integer()

class EncounterResetSchema(Schema):
    message = fields.String()
    success = fields.Boolean(load_default=True)

class RoundAdvanceSchema(Schema):
    round = fields.Integer()
    expired_count = fields.Integer()
    expired_effects = fields.List(fields.Dict())

class EncounterStateSchema(Schema):
    round = fields.Integer()
    initiative = fields.List(fields.String())
    effects = fields.List(fields.Dict())
    actors = fields.List(fields.Dict())

class EncounterValidationSchema(Schema):
    valid = fields.Boolean()
    errors = fields.List(fields.String())
    round = fields.Integer()
    initiative_count = fields.Integer()
    effect_count = fields.Integer()

class EncounterExportSchema(Schema):
    encounter_state = fields.Dict()

class EncounterImportSchema(Schema):
    encounter_state = fields.Dict(required=True)

class EchoResolveSchema(Schema):
    active_effects = fields.List(fields.String())

class LoreEntryResponseSchema(Schema):
    message = fields.String()
    entry = fields.Dict()

class EncounterSummarySchema(Schema):
    encounter_id = fields.String()
    echo_count = fields.Integer()
    lore = fields.List(fields.Dict())

class EncounterSnapshotSchema(Schema):
    round = fields.Integer()
    initiative = fields.List(fields.String())
    effects = fields.List(fields.Dict())
    actors = fields.List(fields.Dict())

class EffectExpireSchema(Schema):
    expired_count = fields.Integer()
    expired_effects = fields.List(fields.Dict())

class RoundSummarySchema(Schema):
    round = fields.Integer()
    initiative_order = fields.List(fields.String())
    summary = fields.List(fields.String())

class ActorRequestSchema(Schema):
    name = fields.String(required=True)
    stats = fields.Dict(
        keys=fields.String(validate=validate.OneOf(["IP", "PP", "SP"])),
        values=fields.Integer(),
        required=True
    )
    traits = fields.List(fields.String(), load_default=[])

class ActorResponseSchema(Schema):
    name = fields.String()
    stats = fields.Dict(
        keys=fields.String(validate=validate.OneOf(["IP", "PP", "SP"])),
        values=fields.Integer()
    )
    traits = fields.List(fields.String())