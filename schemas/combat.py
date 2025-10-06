from marshmallow import Schema, fields

class CombatRollRequest(Schema):
    attacker = fields.Dict(required=True)
    defender = fields.Dict(required=True)
    weapon_die = fields.String(required=True)
    defense_die = fields.String(required=True)
    bap = fields.Boolean(load_default=False)

class CombatRollResponse(Schema):
    value = fields.Integer()
    sides = fields.Integer()
    modifier = fields.Integer()
    type = fields.String()
    property = fields.String(allow_none=True)