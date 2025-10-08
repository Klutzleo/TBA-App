from marshmallow import Schema, fields

class EchoSchema(Schema):
    actor = fields.Str(required=True)
    round = fields.Int()
    tag = fields.Str()
    effect = fields.Str()
    duration = fields.Int()
    encounter_id = fields.Str()