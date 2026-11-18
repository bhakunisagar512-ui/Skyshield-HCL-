from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import incident_payload


def test_report_creates_submitted_incident(make_incident):
    inc = make_incident()
    assert inc["status"] == "submitted"
    assert inc["reference"].startswith(f"SKY-{datetime.now(timezone.utc).year}-")
    assert inc["colour"] == "grey"
    assert [h["to_status"] for h in inc["history"]] == ["submitted"]


def test_references_increment(make_incident):
    a, b = make_incident(), make_incident()
    assert int(b["reference"][-4:]) == int(a["reference"][-4:]) + 1


@pytest.mark.parametrize("override, field", [
    ({"category": "alien_invasion"}, "category"),
    ({"airport_code": "XXX"}, "airport_code"),
    ({"flight_phase": "orbit"}, "flight_phase"),
    ({"occurred_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()}, "occurred_at"),
    ({"occurred_at": "2026-01-01T10:00:00"}, "occurred_at"),  # no timezone
    ({"title": "abc"}, "title"),
    ({"description": "too short"}, "description"),
    ({"title": "x" * 201}, "title"),
])
def test_report_validation(client, auth, users, override, field):
    r = client.post("/api/incidents", json=incident_payload(**override), headers=auth("reporter"))
    assert r.status_code == 422
    assert field in r.text


def test_optional_fields_may_be_empty(client, auth, users):
    r = client.post("/api/incidents", headers=auth("reporter"), json=incident_payload(
        aircraft_registration=None, aircraft_type=None, operator_code=None, flight_number=None))
    assert r.status_code == 201


def test_analysis_runs_ai_and_creates_measures(analysed_incident):
    inc = analysed_incident
    assert inc["status"] == "measures_pending"
    assert inc["severity"] == "incident"
    assert inc["summary"]["status"] == "draft"
    assert inc["summary"]["model"] == "mock:policy-extract"
    assert "SOP-WIL" in inc["summary"]["citations"]
    priorities = {m["priority"] for m in inc["measures"]}
    assert priorities == {"must", "should"}
    assert all(m["source"] == "ai" and m["status"] == "pending" for m in inc["measures"])
    assert all(m["policy_reference"].startswith("SOP-WIL") for m in inc["measures"])
    assert inc["colour"] == "grey"


def test_cannot_skip_steps(client, auth, make_incident):
    inc = make_incident()
    h = auth("officer")
    r = client.post(f"/api/incidents/{inc['id']}/analysis", headers=h,
                    json={"severity": "incident", "analysis": "Trying to analyse before review started."})
    assert r.status_code == 409
    assert client.post(f"/api/incidents/{inc['id']}/close", json={}, headers=h).status_code == 409


def test_not_applied_requires_reason(client, auth, analysed_incident):
    m = analysed_incident["measures"][0]
    r = client.patch(f"/api/measures/{m['id']}", json={"status": "not_applied"}, headers=auth("officer"))
    assert r.status_code == 422
    r = client.patch(f"/api/measures/{m['id']}", json={"status": "not_applied", "reason": "   "}, headers=auth("officer"))
    assert r.status_code == 422


def mark(client, h, measures, status_for):
    for m in measures:
        st = status_for(m)
        body = {"status": st, "reason": "Part on order" if st == "not_applied" else None}
        assert client.patch(f"/api/measures/{m['id']}", json=body, headers=h).status_code == 200


def test_full_flow_to_yellow_and_admin_view(client, auth, analysed_incident):
    inc, h = analysed_incident, auth("officer")
    iid = inc["id"]

    # closing is blocked while measures are pending and the AI draft is unapproved
    r = client.post(f"/api/incidents/{iid}/close", json={}, headers=h)
    assert r.status_code == 409 and "pending" in r.text and "AI summary" in r.text

    # officer edits and approves the AI summary
    assert client.patch(f"/api/incidents/{iid}/ai-summary", json={"summary": "Bird hit the radome on approach to BLR."},
                        headers=h).status_code == 200
    assert client.post(f"/api/incidents/{iid}/ai-summary/approve", headers=h).json()["summary"]["status"] == "approved"

    # officer adds an own measure, then marks: all MUST applied, one SHOULD not applied
    added = client.post(f"/api/incidents/{iid}/measures", headers=h,
                        json={"description": "Brief BLR crews on dusk bird activity", "priority": "should"}).json()
    assert added["source"] == "officer"
    measures = client.get(f"/api/incidents/{iid}", headers=h).json()["measures"]
    first_should = next(m["id"] for m in measures if m["priority"] == "should")
    mark(client, h, measures, lambda m: "not_applied" if m["id"] == first_should else "applied")

    detail = client.get(f"/api/incidents/{iid}", headers=h).json()
    assert detail["colour"] == "yellow"
    icons = {m["id"]: m["icon"] for m in detail["measures"]}
    assert icons[first_should] == "exclamation"

    closed = client.post(f"/api/incidents/{iid}/close", json={"closing_note": "Done"}, headers=h).json()
    assert closed["status"] == "closed" and closed["closed_at"]
    assert [x["to_status"] for x in closed["history"]] == ["submitted", "under_review", "measures_pending", "closed"]

    # measures are frozen after closing
    assert client.patch(f"/api/measures/{first_should}", json={"status": "applied"}, headers=h).status_code == 409

    admin = client.get(f"/api/admin/incidents/{iid}", headers=auth("admin")).json()
    assert admin["colour"] == "yellow"
    assert admin["issue"].startswith("During approach")
    assert admin["short_summary"] == "Bird hit the radome on approach to BLR."
    assert len(admin["suggested_measures"]) == len([m for m in detail["measures"] if m["source"] == "ai"])
    assert len(admin["not_applied_measures"]) == 1
    assert len(admin["applied_measures"]) == len(detail["measures"]) - 1


def test_red_incident_can_close_and_stays_red(client, auth, analysed_incident):
    inc, h = analysed_incident, auth("officer")
    client.post(f"/api/incidents/{inc['id']}/ai-summary/approve", headers=h)
    first_must = next(m["id"] for m in inc["measures"] if m["priority"] == "must")
    mark(client, h, inc["measures"], lambda m: "not_applied" if m["id"] == first_must else "applied")
    closed = client.post(f"/api/incidents/{inc['id']}/close", json={}, headers=h).json()
    assert closed["status"] == "closed" and closed["colour"] == "red"
    page = client.get("/api/admin/incidents?colour=red", headers=auth("admin")).json()
    assert page["total"] == 1 and page["colour_totals"]["red"] == 1


def test_officer_can_change_priority(client, auth, analysed_incident):
    m = next(x for x in analysed_incident["measures"] if x["priority"] == "should")
    r = client.patch(f"/api/measures/{m['id']}", json={"priority": "must"}, headers=auth("officer"))
    assert r.json()["priority"] == "must"


def test_reset_measure_to_pending_clears_reason(client, auth, analysed_incident):
    m, h = analysed_incident["measures"][0], auth("officer")
    client.patch(f"/api/measures/{m['id']}", json={"status": "not_applied", "reason": "x reason"}, headers=h)
    r = client.patch(f"/api/measures/{m['id']}", json={"status": "pending"}, headers=h).json()
    assert r["status"] == "pending" and r["reason"] is None and r["marked_at"] is None


def test_regenerate_keeps_marked_measures(client, auth, analysed_incident):
    inc, h = analysed_incident, auth("officer")
    kept = inc["measures"][0]
    client.patch(f"/api/measures/{kept['id']}", json={"status": "applied"}, headers=h)
    r = client.post(f"/api/incidents/{inc['id']}/ai-summary/regenerate", headers=h)
    assert r.status_code == 200
    after = client.get(f"/api/incidents/{inc['id']}", headers=h).json()
    ids = {m["id"] for m in after["measures"]}
    assert kept["id"] in ids
    descriptions = [m["description"] for m in after["measures"]]
    assert len(descriptions) == len(set(d.lower() for d in descriptions))  # no duplicates
    assert after["summary"]["status"] == "draft"


def test_list_filters(client, auth, make_incident):
    make_incident(category="turbulence", title="Turbulence over Nagpur")
    make_incident()
    h = auth("officer")
    assert client.get("/api/incidents?category=turbulence", headers=h).json()["total"] == 1
    assert client.get("/api/incidents?q=nagpur", headers=h).json()["total"] == 1
    assert client.get("/api/incidents?colour=grey", headers=h).json()["total"] == 2
    assert client.get("/api/incidents?status=closed", headers=h).json()["total"] == 0


def test_dashboard_stats(client, auth, analysed_incident):
    s = client.get("/api/dashboard/stats", headers=auth("admin")).json()
    assert s["total_incidents"] == 1
    assert s["colours"]["grey"] == 1
    assert s["measures"]["pending"] == len(analysed_incident["measures"])
