# backend/error_handlers.py

from flask import jsonify

def register_error_handlers(app):
    @app.errorhandler(Exception)
    def handle_exception(e):
        app.logger.error("Unhandled exception", exc_info=e)
        return jsonify({"error": "Internal server error"}), 500