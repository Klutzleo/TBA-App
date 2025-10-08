from marshmallow import Schema, fields

class LoreEntrySchema(Schema):
    actor = fields.Str()
    round = fields.Int()
    tag = fields.Str()
    message = fields.Str()
    encounter_id = fields.Str()