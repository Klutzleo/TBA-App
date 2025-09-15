# backend/logging_config.py

import logging
import sys
import json

# Custom formatter that outputs logs as structured JSON
class JsonFormatter(logging.Formatter):
    def format(self, record):
        # Build a dictionary with key log fields
        payload = {
            "timestamp": self.formatTime(record),     # Human-readable timestamp
            "level": record.levelname,                # Log level (INFO, ERROR, etc.)
            "logger": record.name,                    # Logger name (usually 'root')
            "message": record.getMessage(),           # The actual log message
            "module": record.module,                  # Module where the log was triggered
        }

        # Optionally include request_id if it's been injected into the record
        if hasattr(record, "request_id"):
            payload["request_id"] = record.request_id

        # Convert the dictionary to a JSON string
        return json.dumps(payload)

# Function to configure the root logger with our JSON formatter
def setup_logging():
    # Create a stream handler that writes to stdout (for Railway logs)
    handler = logging.StreamHandler(sys.stdout)

    # Attach our custom JSON formatter to the handler
    handler.setFormatter(JsonFormatter())

    # Get the root logger (used by Flask and most libraries)
    root = logging.getLogger()

    # Set the logging level to INFO (can be changed to DEBUG or WARNING)
    root.setLevel(logging.INFO)

    # Clear any existing handlers to avoid duplicate logs
    root.handlers.clear()

    # Attach our configured handler
    root.addHandler(handler)