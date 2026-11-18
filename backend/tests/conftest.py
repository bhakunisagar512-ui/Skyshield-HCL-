import os
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _test_db_url() -> str:
    """TEST_DATABASE_URL if set, otherwise DATABASE_URL from .env with the database
    renamed to skyshield_test (so a changed host or port in .env is picked up)."""
    if os.environ.get("TEST_DATABASE_URL"):
        return os.environ["TEST_DATABASE_URL"]
    from app.config import Settings
    return Settings().database_url.rsplit("/", 1)[0] + "/skyshield_test"


os.environ["DATABASE_URL"] = _test_db_url()
os.environ["LLM_PROVIDER"] = "mock"
os.environ["EMBEDDING_PROVIDER"] = "hash"
os.environ["JWT_SECRET"] = "test-secret-0123456789abcdef0123456789"

import pytest  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.services.policies import ingest_policy  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

POLICY_DIR = Path(__file__).resolve().parents[2] / "database" / "policies"
WORKFLOW_TABLES = "measures, ai_summaries, incident_status_history, incidents, users"
PASSWORD = "Password@123"


@pytest.fixture(scope="session", autouse=True)
def schema():
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    for path in sorted(POLICY_DIR.glob("*.md")):
        ingest_policy(db, path.read_text(encoding="utf-8"))
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def clean_tables(schema):
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {WORKFLOW_TABLES} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def users(db):
    specs = {
        "reporter": ("reporter@test.in", "reporter"),
        "reporter2": ("reporter2@test.in", "reporter"),
        "officer": ("officer@test.in", "safety_officer"),
        "admin": ("admin@test.in", "admin"),
    }
    pw = hash_password(PASSWORD)
    out = {}
    for key, (email, role) in specs.items():
        u = User(email=email, full_name=key.title(), password_hash=pw, role=role)
        db.add(u)
        out[key] = u
    db.commit()
    return out


@pytest.fixture
def auth(client, users):
    """auth('officer') -> headers dict"""
    cache: dict[str, dict] = {}

    def _headers(who: str) -> dict:
        if who not in cache:
            r = client.post("/api/auth/login", json={"email": users[who].email, "password": PASSWORD})
            assert r.status_code == 200, r.text
            cache[who] = {"Authorization": f"Bearer {r.json()['access_token']}"}
        return cache[who]

    return _headers


def incident_payload(**overrides) -> dict:
    data = {
        "title": "Bird strike on approach at BLR",
        "description": "During approach to runway 09L at Bengaluru a large bird hit the nose radome. Remains found on walk-around.",
        "category": "wildlife_strike",
        "occurred_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        "airport_code": "BLR",
        "flight_phase": "approach",
        "aircraft_registration": "VT-ABC",
        "aircraft_type": "A320neo",
        "operator_code": "SHA",
        "flight_number": "SHA201",
    }
    data.update(overrides)
    return data


@pytest.fixture
def make_incident(client, auth):
    def _make(**overrides) -> dict:
        r = client.post("/api/incidents", json=incident_payload(**overrides), headers=auth("reporter"))
        assert r.status_code == 201, r.text
        return r.json()

    return _make


@pytest.fixture
def analysed_incident(client, auth, make_incident):
    """Incident taken through review and analysis; mock AI has produced measures."""
    inc = make_incident()
    officer = auth("officer")
    assert client.post(f"/api/incidents/{inc['id']}/start-review", headers=officer).status_code == 200
    r = client.post(f"/api/incidents/{inc['id']}/analysis", headers=officer,
                    json={"severity": "incident", "analysis": "Strike confirmed by remains on the radome. Engines normal."})
    assert r.status_code == 200, r.text
    return client.get(f"/api/incidents/{inc['id']}", headers=officer).json()
