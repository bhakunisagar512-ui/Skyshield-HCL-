"""Completing a 'not applied' measure after the incident was closed."""
import pytest


@pytest.fixture
def closed_red(client, auth, analysed_incident):
    """Closed incident: first MUST not applied (red), first SHOULD not applied, rest applied."""
    inc, h = analysed_incident, auth("officer")
    client.post(f"/api/incidents/{inc['id']}/ai-summary/approve", headers=h)
    must = next(m["id"] for m in inc["measures"] if m["priority"] == "must")
    should = next(m["id"] for m in inc["measures"] if m["priority"] == "should")
    for m in inc["measures"]:
        body = ({"status": "not_applied", "reason": "Part on order"} if m["id"] in (must, should)
                else {"status": "applied"})
        assert client.patch(f"/api/measures/{m['id']}", json=body, headers=h).status_code == 200
    closed = client.post(f"/api/incidents/{inc['id']}/close", json={}, headers=h).json()
    assert closed["status"] == "closed" and closed["colour"] == "red"
    return {"id": inc["id"], "must": must, "should": should}


def test_any_officer_completes_and_colour_updates(client, auth, closed_red, db):
    from app.core.security import hash_password
    from app.models import User
    db.add(User(email="officer2@test.in", full_name="Second Officer", password_hash=hash_password("Password@123"),
                role="safety_officer"))
    db.commit()
    r = client.post("/api/auth/login", json={"email": "officer2@test.in", "password": "Password@123"})
    other = {"Authorization": f"Bearer {r.json()['access_token']}"}

    m = client.post(f"/api/measures/{closed_red['must']}/complete", headers=other,
                    json={"note": "Part fitted 12 Dec, work order WO-4471"}).json()
    assert m["status"] == "applied" and m["icon"] == "tick"
    assert m["completed_late"] is True and m["completed_by"] == "Second Officer"
    assert m["reason"] == "Part on order"          # original reason kept
    assert m["completion_note"] == "Part fitted 12 Dec, work order WO-4471"

    inc = client.get(f"/api/incidents/{closed_red['id']}", headers=other).json()
    assert inc["status"] == "closed" and inc["colour"] == "yellow"   # Must done; one Should still open
    assert inc["history"][-1]["note"].startswith("Follow-up: MUST measure completed after closing")

    client.post(f"/api/measures/{closed_red['should']}/complete", headers=other, json={"note": "Crew briefed on 14 Dec"})
    assert client.get(f"/api/incidents/{closed_red['id']}", headers=other).json()["colour"] == "green"


def test_note_required(client, auth, closed_red):
    h = auth("officer")
    assert client.post(f"/api/measures/{closed_red['must']}/complete", json={"note": ""}, headers=h).status_code == 422
    assert client.post(f"/api/measures/{closed_red['must']}/complete", json={}, headers=h).status_code == 422


def test_only_not_applied_on_closed(client, auth, closed_red, analysed_incident):
    h = auth("officer")
    applied = next(m["id"] for m in analysed_incident["measures"]
                   if m["id"] not in (closed_red["must"], closed_red["should"]))
    assert client.post(f"/api/measures/{applied}/complete", json={"note": "Already applied"},
                       headers=h).status_code == 409
    client.post(f"/api/measures/{closed_red['must']}/complete", json={"note": "Done now"}, headers=h)
    assert client.post(f"/api/measures/{closed_red['must']}/complete", json={"note": "Done twice"},
                       headers=h).status_code == 409


def test_not_allowed_while_open(client, auth, analysed_incident):
    h = auth("officer")
    m = analysed_incident["measures"][0]
    client.patch(f"/api/measures/{m['id']}", json={"status": "not_applied", "reason": "later"}, headers=h)
    r = client.post(f"/api/measures/{m['id']}/complete", json={"note": "Done now"}, headers=h)
    assert r.status_code == 409 and "still open" in r.text


def test_admin_and_reporter_cannot_complete(client, auth, closed_red):
    for who in ("admin", "reporter"):
        assert client.post(f"/api/measures/{closed_red['must']}/complete", json={"note": "Trying to complete"},
                           headers=auth(who)).status_code == 403


def test_admin_sees_followup(client, auth, closed_red):
    client.post(f"/api/measures/{closed_red['must']}/complete", json={"note": "Part fitted, WO-4471"},
                headers=auth("officer"))
    h = auth("admin")
    detail = client.get(f"/api/admin/incidents/{closed_red['id']}", headers=h).json()
    late = [m for m in detail["applied_measures"] if m["completed_late"]]
    assert len(late) == 1 and late[0]["completion_note"] == "Part fitted, WO-4471" and late[0]["reason"] == "Part on order"
    page = client.get("/api/admin/incidents?completed_late=true", headers=h).json()
    assert page["total"] == 1 and page["completed_late_total"] == 1
    assert page["items"][0]["counts"]["completed_late"] == 1
    assert client.get("/api/admin/incidents", headers=h).json()["completed_late_total"] == 1
    # other measures on a closed incident stay frozen
    assert client.patch(f"/api/measures/{closed_red['should']}", json={"status": "applied"},
                        headers=auth("officer")).status_code == 409
