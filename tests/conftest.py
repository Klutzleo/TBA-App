"""Test-only setup.

Production runs on Postgres, but the tests use SQLite. Two things Postgres does that SQLite
does not, both handled here so the app code can stay as it is:

1. Postgres-only column types (JSONB) cannot be created on SQLite. Render JSONB as plain JSON.
2. Postgres quietly accepts a UUID string where a UUID column is compared (the login check does
   `User.id == token_data.user_id`, where the id is a string). SQLite's UUID handling calls
   `.hex` on it and fails, so convert strings to UUID objects for SQLite only.
"""
import os
import tempfile
import uuid

# Every test run gets its own throwaway SQLite database. A leftover .db file from an earlier
# run has an outdated schema (create_all never alters existing tables), and this also keeps the
# tests away from any DATABASE_URL in the environment or .env. Must run before backend.db is imported.
_test_db_dir = tempfile.mkdtemp(prefix="tba_tests_")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_test_db_dir, "test.db").replace("\\", "/")
os.environ.setdefault("API_KEY", "devkey")

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql import sqltypes


@compiles(JSONB, "sqlite")
def _jsonb_as_json_on_sqlite(type_, compiler, **kw):
    return "JSON"


_original_uuid_bind_processor = sqltypes.Uuid.bind_processor


def _lenient_uuid_bind_processor(self, dialect):
    processor = _original_uuid_bind_processor(self, dialect)
    if processor is None or dialect.name != "sqlite":
        return processor

    def process(value):
        if isinstance(value, str):
            value = uuid.UUID(value)
        return processor(value)

    return process


sqltypes.Uuid.bind_processor = _lenient_uuid_bind_processor


import pytest  # noqa: E402  (kept below the environment setup above on purpose)


@pytest.fixture(scope="session", autouse=True)
def _test_schema():
    """Build the test schema once, before any test.

    Two model classes define the same `roll_logs` table (backend/models.py and
    models/roll_log.py), so the first `create_all` on a fresh SQLite file trips over the
    duplicate index after creating the other tables, and the second pass finishes the job.
    Production builds its schema from SQL migrations, so it never hits this.
    """
    from sqlalchemy.exc import OperationalError

    from backend.db import init_db

    for attempt in range(2):
        try:
            init_db()
            return
        except OperationalError:
            if attempt:
                raise
