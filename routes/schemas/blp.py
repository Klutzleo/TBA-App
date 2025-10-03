from flask_smorest import Blueprint

schemas_blp = Blueprint(
    "Schemas",
    "schemas",
    url_prefix="/api/schemas",
    description="Schema validation, emotional reflection, and playgrounds"
)