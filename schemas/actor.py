from pydantic import BaseModel
from typing import Optional
from marshmallow import Schema, fields

class Actor(BaseModel):
    name: str
    dp: int
    max_dp: int
    initiative: Optional[int] = None
    status: Optional[str] = None  # e.g. "conscious", "unconscious", "dead"
    tags: Optional[list[str]] = []  # e.g. ["tank", "caster", "vengeful"]
    
class ActorResponseSchema(Schema):
    name = fields.Str(required=True)
    dp = fields.Int(required=True)
    max_dp = fields.Int(required=True)

class ActorRequestSchema(Schema):
    name = fields.Str(required=True)
    dp = fields.Int(required=True)
    max_dp = fields.Int(required=True)
    initiative = fields.Int()
    status = fields.Str()
    tags = fields.List(fields.Str())

