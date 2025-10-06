from marshmallow import Schema, fields

class CharacterSchema(Schema):
    """Defines a combatant with stats and traits."""
    name = fields.String(required=True, metadata={"description": "Character name"})
    stats = fields.Dict(
        keys=fields.String(),
        values=fields.Integer(),
        required=True,
        metadata={"description": "Stat block with named attributes (e.g., strength, dexterity)"}
    )
    traits = fields.List(
        fields.String(),
        load_default=[],
        metadata={"description": "List of passive or active traits"}
    )

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