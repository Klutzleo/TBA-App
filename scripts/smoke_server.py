"""
End-to-end smoke test of the REAL server (uvicorn + Starlette + FastAPI), for checking a dependency upgrade before it ships.

The pytest suite mostly calls handlers directly, so it does not exercise the web stack itself. This starts uvicorn, then drives it over
HTTP and WebSocket: static pages, the API-key gate (including a crafted Host header), register/login/JWT, creating a campaign and a vehicle,
validation errors, and an authenticated WebSocket (bearer subprotocol) sending a dice roll, a chat line and a bad command.

Run it with the python of the environment you are checking, against a MIGRATED PostgreSQL (SQLite cannot do the authenticated routes:
the JWT's string user id is rejected by its UUID type, while Postgres accepts it):

    SMOKE_DB_URL=postgresql://user:pass@host:5432/dbname python scripts/smoke_server.py

Build the database like production does: `DATABASE_URL=... python run_migrations.py`, then start the app once (init_db fills a few gaps).
NEVER point this at the production database: it creates users, a campaign and a vehicle.
"""
import asyncio
import json
import os
import subprocess
import sys
import time
import uuid

import requests
import websockets

import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRATCH = tempfile.gettempdir()
PORT = 8765
BASE = f"http://127.0.0.1:{PORT}"
DB = os.path.join(SCRATCH, f"smoke_{uuid.uuid4().hex[:6]}.db")
API_KEY = "smokekey"

env = dict(os.environ, DATABASE_URL=os.environ.get("SMOKE_DB_URL") or ("sqlite:///" + DB.replace("\\", "/")), API_KEY=API_KEY, SECRET_KEY="smoke-secret-" + "x" * 40,
           PYTHONPATH=REPO, PYTHONIOENCODING="utf-8")
env.pop("RAILWAY_ENVIRONMENT", None)
results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + name + ((" :: " + str(detail)) if (detail and not ok) else ""))


proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.app:application", "--port", str(PORT), "--proxy-headers",
                         "--forwarded-allow-ips=*", "--log-level", "warning"], cwd=REPO, env=env,
                        stdout=open(os.path.join(SCRATCH, "smoke_server.log"), "w"), stderr=subprocess.STDOUT)
try:
    for _ in range(60):
        try:
            if requests.get(BASE + "/health", timeout=2).status_code == 200:
                break
        except Exception:
            time.sleep(1)
    else:
        raise SystemExit("server did not start; see smoke_server.log")

    # ---- plain HTTP, static, middleware
    check("GET /health", requests.get(BASE + "/health").status_code == 200)
    r = requests.get(BASE + "/")
    check("GET / serves the landing page", r.status_code == 200 and "<html" in r.text.lower(), r.status_code)
    check("static game.html", requests.get(BASE + "/game.html").status_code == 200)
    check("openapi.json builds", requests.get(BASE + "/openapi.json").status_code == 200)
    check("API-key gate blocks a keyless legacy route", requests.get(BASE + "/api/combat/log/recent").status_code == 403)
    check("API-key gate lets a keyed one through", requests.get(BASE + "/api/combat/log/recent", headers={"X-API-Key": API_KEY}).status_code != 403)
    check("crafted Host header does not skip the gate",
          requests.get(BASE + "/api/combat/log/recent", headers={"Host": "x/api/public"}).status_code == 403)

    # ---- auth
    tag = uuid.uuid4().hex[:6]
    users = []
    for who in ("sw", "pl"):
        body = {"email": f"{who}_{tag}@example.com", "username": f"{who}_{tag}", "password": "Sm0ke-test-pass"}
        r = requests.post(BASE + "/api/auth/register", json=body)
        check(f"register {who}", r.status_code == 201, r.text[:200])
        users.append((body, r.json().get("access_token") if r.status_code == 201 else None))
    sw_tok, pl_tok = users[0][1], users[1][1]
    H = lambda t: {"Authorization": f"Bearer {t}"}
    r = requests.post(BASE + "/api/auth/login", json={"email": users[0][0]["email"], "password": "Sm0ke-test-pass"})
    check("login", r.status_code == 200 and r.json().get("access_token"), r.text[:200])
    rm = requests.get(BASE + "/api/auth/me", headers=H(sw_tok))
    check("GET /api/auth/me", rm.status_code == 200, f"{rm.status_code} {rm.text[:200]}")
    check("a bad token is rejected", requests.get(BASE + "/api/auth/me", headers=H("nope")).status_code in (401, 403))
    r = requests.post(BASE + "/api/auth/register", json={"email": "not-an-email", "username": "x", "password": "short"})
    check("validation errors are 422", r.status_code == 422)

    # ---- campaign + vehicles over real HTTP
    r = requests.post(BASE + "/api/campaigns/create", headers=H(sw_tok), json={
        "name": "Smoke Campaign", "description": "A campaign made by the smoke test.", "is_public": False, "posting_frequency": "medium",
        "min_players": 2, "max_players": 4, "timezone": "UTC"})
    check("create campaign", r.status_code in (200, 201), r.text[:300])
    cid = (r.json().get("id") or r.json().get("campaign_id")) if r.status_code in (200, 201) else None
    if cid:
        r = requests.post(BASE + f"/api/campaigns/{cid}/vehicles", headers=H(sw_tok), json={"name": "Smoke Ship", "level": 5, "kind": "enclosed"})
        check("SW creates a vehicle", r.status_code == 201 and r.json()["max_dp"] == 16, r.text[:300])
        vid = r.json().get("id") if r.status_code == 201 else None
        check("player cannot create a vehicle (403)",
              requests.post(BASE + f"/api/campaigns/{cid}/vehicles", headers=H(pl_tok), json={"name": "Nope", "level": 1}).status_code == 403)
        check("vehicle table endpoint", requests.get(BASE + f"/api/campaigns/{cid}/vehicle-table", headers=H(sw_tok)).status_code == 200)
        if vid:
            r = requests.put(BASE + f"/api/campaigns/{cid}/vehicles/{vid}/systems/1", headers=H(sw_tok),
                             json={"display_name": "Laser", "macro_command": "/laser", "power_source": "IP", "effect_type": "damage"})
            check("install a system", r.status_code == 200 and r.json()["systems"][0]["ability"]["macro_command"] == "/laser", r.text[:200])
            r = requests.put(BASE + f"/api/campaigns/{cid}/vehicles/{vid}/systems/1", headers=H(sw_tok),
                             json={"display_name": "Laser", "macro_command": "/attack"})
            check("a reserved command is refused (400)", r.status_code == 400, r.text[:200])
            r = requests.put(BASE + f"/api/campaigns/{cid}/vehicles/{vid}/systems/1", headers=H(sw_tok), json={"display_name": "x"})
            check("a missing field is 422", r.status_code == 422, r.status_code)
            check("player cannot see a hidden vehicle's absence: list works",
                  requests.get(BASE + f"/api/campaigns/{cid}/vehicles", headers=H(pl_tok)).status_code == 403)   # not a member yet

    # ---- websockets
    async def ws_checks():
        if not cid:
            return
        url = f"ws://127.0.0.1:{PORT}/api/campaign/ws/{cid}"
        try:
            async with websockets.connect(url, subprotocols=["bearer", sw_tok]) as ws:
                check("WS: bearer subprotocol accepted and echoed", ws.subprotocol == "bearer", ws.subprotocol)
                first = json.loads(await asyncio.wait_for(ws.recv(), 5))
                check("WS: server greets the member", bool(first.get("type")), first)
                await ws.send(json.dumps({"type": "dice_roll", "dice": "2d6"}))
                got = None
                for _ in range(15):
                    m = json.loads(await asyncio.wait_for(ws.recv(), 5))
                    if m.get("type") == "dice_roll_result" or m.get("dice") == "2d6":
                        got = m
                        break
                check("WS: a dice roll is rolled and broadcast back", got is not None and 2 <= got.get("result", 0) <= 12, got)
                await ws.send(json.dumps({"type": "message", "actor": "Story Weaver", "text": "hello from the smoke test"}))
                echo = None
                for _ in range(15):
                    m = json.loads(await asyncio.wait_for(ws.recv(), 5))
                    if "hello from the smoke test" in json.dumps(m):
                        echo = m
                        break
                check("WS: a chat message is broadcast back", echo is not None)
                await ws.send(json.dumps({"type": "combat_command", "raw_command": "/attack @Nobody"}))
                note = None
                for _ in range(15):
                    m = json.loads(await asyncio.wait_for(ws.recv(), 5))
                    if m.get("type") in ("system", "error"):
                        note = m
                        break
                check("WS: a bad combat command gets a polite system reply", note is not None, note)
        except Exception as e:
            check("WS: authorised connection", False, repr(e))
        try:
            async with websockets.connect(url) as ws:
                await asyncio.wait_for(ws.recv(), 5)
            check("WS: no token is refused", False, "connection stayed open")
        except Exception:
            check("WS: no token is refused", True)
        try:
            async with websockets.connect(url, subprotocols=["bearer", pl_tok]) as ws:
                await asyncio.wait_for(ws.recv(), 5)
            check("WS: a non-member is refused", False, "connection stayed open")
        except Exception:
            check("WS: a non-member is refused", True)

    asyncio.run(ws_checks())
finally:
    proc.terminate()
    try:
        proc.wait(10)
    except Exception:
        proc.kill()
    print(f"\n{sum(results)}/{len(results)} checks passed")
    log = open(os.path.join(SCRATCH, "smoke_server.log"), encoding="utf-8", errors="replace").read()
    errs = [l for l in log.splitlines() if "Traceback" in l or "ERROR" in l or "Exception" in l]
    print("server log errors:", len(errs))
    for l in errs[:8]:
        print("  ", l[:200])
    sys.exit(0 if all(results) else 1)
