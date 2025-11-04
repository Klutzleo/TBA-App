from marshmallow import Schema, fields

class EffectPreviewSchema(Schema):
    actor = fields.Str(required=True)
    effect = fields.Str(required=True)
    modifiers = fields.Dict(keys=fields.Str(), values=fields.Int(), required=False)
    context = fields.Str(required=False)
    narrate = fields.Bool(required=False)

class SimulatedOutcomeSchema(Schema):
    HP_change = fields.Int()
    status = fields.Str()
    area_damage = fields.Bool()

class EffectPreviewResponseSchema(Schema):
    status = fields.Str()
    actor = fields.Str()
    simulated_outcome = fields.Nested(SimulatedOutcomeSchema)
    narration = fields.Str(allow_none=True)