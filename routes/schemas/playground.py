import datetime
from flask import jsonify
from routes.schemas.blp import schemas_blp

@schemas_blp.route("/playground/<schema_name>", methods=["GET"])
@schemas_blp.response(200)
@schemas_blp.alt_response(404, description="No playground available")
def playground(schema_name):
    if schema_name == "memory_echoes":
        sample = {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "emotion": "hope",
            "summary": "Reboot succeeded"
        }
        return sample

    return {
        "error": f"No playground available for schema '{schema_name}'."
    }, 404