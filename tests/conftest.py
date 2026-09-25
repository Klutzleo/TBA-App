"""Test-only setup.

Production runs on Postgres, but the tests build their schema in SQLite, which cannot
create Postgres-only column types. Render JSONB as plain JSON there so the schema builds.
"""
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles


@compiles(JSONB, "sqlite")
def _jsonb_as_json_on_sqlite(type_, compiler, **kw):
    return "JSON"
