"""End-to-end check against a running SkyShield API.

Logs in as a reporter and an officer, files an incident, submits the analysis,
waits for the AI summary and prints the result.

Usage (server must be running, from backend/):
    python -m scripts.smoke_test
    python -m scripts.smoke_test --url http://localhost:8000/api
"""
import argparse
import sys
import time
from datetime import datetime, timedelta, timezone

import httpx

PASSWORD = "Password@123"
REPORTER = "ananya.iyer@skyshield.example"
OFFICER = "arjun.mehta@skyshield.example"


def fail(msg: str) -> None:
    print(f"\nFAILED: {msg}")
    sys.exit(1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000/api")
    ap.add_argument("--timeout", type=int, default=90, help="seconds to wait for the AI")
    args = ap.parse_args()
    c = httpx.Client(base_url=args.url, timeout=30)

    try:
        health = c.get("/health").json()
    except httpx.ConnectError:
        fail(f"cannot reach {args.url}. Is uvicorn running?")
    print(f"1. API is up. LLM provider: {health['llm_provider']}, embeddings: {health['embedding_provider']}")

    def login(email: str) -> dict:
        r = c.post("/auth/login", json={"email": email, "password": PASSWORD})
        if r.status_code != 200:
            fail(f"login for {email} returned {r.status_code}. Did you run 'python -m app.seed --reset'?")
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    rep, off = login(REPORTER), login(OFFICER)
    print("2. Logged in as reporter and safety officer")

    r = c.post("/incidents", headers=rep, json={
        "title": "Bird strike on take-off at Bengaluru",
        "description": "During take-off from runway 09L at Bengaluru a flock of birds hit the aircraft at about 300 ft. "
                       "A loud bang was heard and engine 2 vibration rose briefly. The crew returned and landed safely.",
        "category": "wildlife_strike",
        "occurred_at": (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(),
        "airport_code": "BLR", "flight_phase": "takeoff",
        "aircraft_registration": "VT-TST", "aircraft_type": "A320neo", "operator_code": "SHA", "flight_number": "SHA321",
    })
    if r.status_code != 201:
        fail(f"create incident returned {r.status_code}: {r.text}")
    inc = r.json()
    print(f"3. Incident filed: {inc['reference']}")

    c.post(f"/incidents/{inc['id']}/start-review", headers=off).raise_for_status()
    c.post(f"/incidents/{inc['id']}/analysis", headers=off, json={
        "severity": "serious_incident",
        "analysis": "Bird remains found on the engine 2 inlet. Vibration spike suggests possible fan blade damage. "
                    "High bird activity reported near the runway at dawn.",
    }).raise_for_status()
    print("4. Analysis submitted, waiting for the AI", end="", flush=True)

    start = time.time()
    while True:
        d = c.get(f"/incidents/{inc['id']}", headers=off).json()
        status = d["summary"]["status"]
        if status != "generating":
            break
        if time.time() - start > args.timeout:
            fail("AI did not finish in time. Check the uvicorn window for errors.")
        print(".", end="", flush=True)
        time.sleep(1)
    print(f" done in {time.time() - start:.1f}s")

    s = d["summary"]
    if status == "failed":
        fail(f"AI summary failed: {s['error']}")

    print(f"\n5. AI summary ({s['model']}):\n   {s['summary']}")
    if s.get("error"):
        print(f"   note: {s['error']}")
    print(f"\n   Measures ({len(d['measures'])}):")
    for m in d["measures"]:
        print(f"   [{m['priority'].upper():6}] {m['description']}")
        print(f"            ref: {m['policy_reference']}")
    print(f"\n   Citations: {s['citations']}")
    print("\nSUCCESS: the backend and AI are working.")


if __name__ == "__main__":
    main()
