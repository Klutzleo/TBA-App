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

class EffectResolveSchema(Schema):
    actor = fields.Str(required=True)
    effect = fields.Str(required=True)
    source = fields.Str(required=False)
    modifiers = fields.Dict(keys=fields.Str(), values=fields.Int(), required=False)
    context = fields.Str(required=False)

class EffectResolveResponseSchema(Schema):
    status = fields.Str()
    actor = fields.Str()
    applied_effect = fields.Str()
    outcome = fields.Dict()
    narration = fields.Str(allow_none=True)

class EffectUndoSchema(Schema):
    actor = fields.Str(required=True)
    effect_id = fields.Str(required=True)
    reason = fields.Str(required=False)

class EffectUndoResponseSchema(Schema):
    status = fields.Str()
    actor = fields.Str()
    undone_effect = fields.Str()
    rollback_successful = fields.Bool()
    narration = fields.Str(allow_none=True)