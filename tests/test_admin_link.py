"""The Admin link is shown only to admins; the endpoint behind it reports admin status and nothing else."""
import os
import uuid
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_admin_link.db")
os.environ.setdefault("API_KEY", "devkey")


def test_am_i_admin(monkeypatch):
    from routes.moderation import am_i_admin
    admin, other = SimpleNamespace(id=uuid.uuid4()), SimpleNamespace(id=uuid.uuid4())
    monkeypatch.setenv("ADMIN_USER_IDS", str(admin.id))
    assert am_i_admin(admin) == {"admin": True}
    assert am_i_admin(other) == {"admin": False}
    monkeypatch.setenv("ADMIN_USER_IDS", "")
    assert am_i_admin(admin) == {"admin": False}
