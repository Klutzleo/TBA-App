from flask_smorest import Blueprint
from flask.views import MethodView
from flask import request
from backend.magic_logic import resolve_spellcast

chat_blp = Blueprint("chat", "chat", url_prefix="/api/chat", description="Chat-driven actions")

@chat_blp.route("/submit", methods=["POST"])
class ChatSubmit(MethodView):
    def post(self):
        payload = request.get_json()
        result = resolve_spellcast(
            caster=payload["caster"],
            target=payload["target"],
            spell=payload["spell"],
            encounter_id=payload.get("encounter_id"),
            log=True
        )
        return {
            "narration": result["notes"],
            "effects": result["effects"],
            "log": result["log"]
        }