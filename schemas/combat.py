from marshmallow import Schema, fields

class CharacterSchema(Schema):
    name = fields.String(required=True)
    stats = fields.Dict(required=True)
    traits = fields.List(fields.String(), load_default=[])

class EquipmentSchema(Schema):
    name = fields.String(required=True)
    type = fields.String(required=True, example="armor")  # or "shield", "weapon"
    bonus = fields.Integer(load_default=0)
    durability = fields.Integer(load_default=100)
    traits = fields.List(fields.String(), load_default=[])

class CombatRollRequest(Schema):
    attacker = fields.Nested(CharacterSchema, required=True)
    defender = fields.Nested(CharacterSchema, required=True)
    weapon = fields.Nested(EquipmentSchema, required=False)
    armor = fields.List(fields.Nested(EquipmentSchema), required=False)
    shield = fields.Nested(EquipmentSchema, required=False)
    weapon_die = fields.String(required=True, example="1d8")
    defense_die = fields.String(required=True, example="1d6")
    distance = fields.String(load_default="melee", example="melee")
    bap = fields.Boolean(load_default=False)
    log = fields.Boolean(load_default=False)
    encounter_id = fields.String(required=False)

class SimulatedCombatResponse(Schema):
    rounds = fields.List(fields.Dict(), required=True)
    outcome = fields.String(required=True)
    log = fields.List(fields.String(), required=False)
    summary = fields.Dict(required=False)

class CombatRollResponse(Schema):
    result = fields.String(required=True, example="win")
    damage = fields.Integer(required=False)
    blocked_by = fields.String(required=False, example="shield")
    log = fields.List(fields.String(), required=False)
    notes = fields.List(fields.String(), required=False)