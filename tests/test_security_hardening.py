"""Security hardening: the API-key gate cannot be skipped with a crafted Host header, a prod deploy refuses the public
dev secret, and cover images only ever reach the JPEG/PNG/WebP decoders."""
import importlib
import io
import os
import subprocess
import sys

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_security_hardening.db")
os.environ.setdefault("API_KEY", "devkey")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from backend.app import application
    return TestClient(application)


def test_api_key_gate_holds_against_a_crafted_host_header(client):
    assert client.get("/api/zzz-not-a-route").status_code == 403
    for host in ("x/api/public", "x/api/campaigns", "x/health"):
        assert client.get("/api/zzz-not-a-route", headers={"Host": host}).status_code == 403, host


def test_gate_still_lets_public_and_keyed_requests_through(client):
    assert client.get("/api/zzz-not-a-route", headers={"X-API-Key": "devkey"}).status_code == 404
    assert client.get("/health").status_code == 200


def _import_jwt_with(env):
    code = "import backend.auth.jwt"
    full = {k: v for k, v in os.environ.items() if k not in ("SECRET_KEY", "RAILWAY_ENVIRONMENT", "RAILWAY_ENVIRONMENT_NAME")}
    full["SECRET_KEY"] = ""  # set-but-empty so a developer's local .env can't fill it in (dotenv never overrides a set variable)
    full.update(env)
    full["PYTHONPATH"] = os.getcwd()
    return subprocess.run([sys.executable, "-c", code], env=full, capture_output=True, text=True)


def test_railway_refuses_to_start_without_a_real_secret():
    assert _import_jwt_with({"RAILWAY_ENVIRONMENT": "production"}).returncode != 0
    assert _import_jwt_with({"RAILWAY_ENVIRONMENT": "production", "SECRET_KEY": "your-secret-key-change-in-production"}).returncode != 0
    assert _import_jwt_with({"RAILWAY_ENVIRONMENT": "production", "SECRET_KEY": "a-real-long-random-secret-value"}).returncode == 0


def test_local_dev_keeps_the_fallback_secret():
    assert _import_jwt_with({}).returncode == 0


def test_cover_images_reject_other_formats_at_open():
    from PIL import Image
    from backend.cover_image import CoverImageError, process_cover_image
    buf = io.BytesIO()
    Image.new("RGB", (900, 300), (10, 20, 30)).save(buf, format="TIFF")
    with pytest.raises(CoverImageError):
        process_cover_image(buf.getvalue())
    buf = io.BytesIO()
    Image.new("RGB", (900, 300), (10, 20, 30)).save(buf, format="PNG")
    data, w, h = process_cover_image(buf.getvalue())
    assert data[:2] == b"\xff\xd8" and w == 900
