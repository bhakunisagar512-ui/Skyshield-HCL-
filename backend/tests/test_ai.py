import json

import pytest
from app.models import Incident
from app.services.ai import rag
from app.services.serialize import colour_subquery
from app.services.status_rules import incident_colour
from sqlalchemy import select


class FakeLLM:
    name = "fake:test"

    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts: list[str] = []

    def generate(self, system: str, user: str, schema: dict):
        assert "POLICY EXCERPTS" in user and "[C1]" in user
        assert schema["required"] == ["summary", "measures"]
        self.prompts.append(user)
        return self.replies[min(len(self.prompts), len(self.replies)) - 1]


@pytest.fixture
def use_llm(monkeypatch):
    holder = {}

    def _use(*replies):
        holder["llm"] = FakeLLM(*replies)
        monkeypatch.setattr(rag, "get_llm", lambda: holder["llm"])
        return holder["llm"]
    return _use


def run_analysis(client, auth, make_incident):
    inc = make_incident()
    h = auth("officer")
    client.post(f"/api/incidents/{inc['id']}/start-review", headers=h)
    client.post(f"/api/incidents/{inc['id']}/analysis", headers=h,
                json={"severity": "serious_incident", "analysis": "Engine ingestion suspected, vibration noted."})
    return client.get(f"/api/incidents/{inc['id']}", headers=h).json()


def test_llm_output_is_grounded(client, auth, make_incident, use_llm):
    use_llm("```json\n" + json.dumps({
        "summary": "Bird strike with suspected engine ingestion on approach to BLR.",
        "measures": [
            {"description": "Borescope the No. 2 engine", "priority": "must", "citation": "C1"},
            {"description": "Invented rule from nowhere", "priority": "must", "citation": "C99"},
            {"description": "Brief crews about dusk bird activity", "priority": "should", "citation": "[C2]"},
            {"description": "borescope the no. 2 engine", "priority": "must", "citation": "C1"},
        ],
    }) + "\n```")
    inc = run_analysis(client, auth, make_incident)
    s = inc["summary"]
    assert s["status"] == "draft" and s["model"] == "fake:test"
    assert "1 ungrounded" in s["error"]
    assert [m["description"] for m in inc["measures"]] == ["Borescope the No. 2 engine",
                                                           "Brief crews about dusk bird activity"]
    assert all(m["policy_reference"] for m in inc["measures"])


def test_invalid_llm_output_fails_safely(client, auth, make_incident, use_llm):
    use_llm("Sorry, I cannot help with that.")
    inc = run_analysis(client, auth, make_incident)
    assert inc["summary"]["status"] == "failed"
    assert inc["measures"] == []
    h = auth("officer")
    # officer carries on without AI: discard, add own measure, mark, close
    assert client.post(f"/api/incidents/{inc['id']}/ai-summary/discard", headers=h).status_code == 200
    m = client.post(f"/api/incidents/{inc['id']}/measures", headers=h,
                    json={"description": "Inspect engine as per AMM", "priority": "must"}).json()
    client.patch(f"/api/measures/{m['id']}", json={"status": "applied"}, headers=h)
    closed = client.post(f"/api/incidents/{inc['id']}/close", json={}, headers=h).json()
    assert closed["status"] == "closed" and closed["colour"] == "green"


def test_bad_priority_rejected(client, auth, make_incident, use_llm):
    use_llm(json.dumps({"summary": "A summary that is long enough.",
                        "measures": [{"description": "Do something", "priority": "urgent", "citation": "C1"}]}))
    inc = run_analysis(client, auth, make_incident)
    assert inc["summary"]["status"] == "failed"


@pytest.mark.parametrize("query, category, expected", [
    ("bird hit the engine on take-off vibration", "wildlife_strike", "SOP-WIL"),
    ("crossed the stop bar onto the runway without clearance", "runway_incursion", "SOP-RIN"),
    ("laser beam in cockpit on final", None, "SOP-LSR"),
    ("TCAS resolution advisory traffic conflict", None, "SOP-MAC"),
])
def test_retrieval_finds_right_policy(db, query, category, expected):
    hits = rag.retrieve(db, query, category, top_k=3)
    assert hits[0].policy_code == expected


def test_sql_colour_matches_python(client, auth, make_incident, db):
    """The SQL colour (used for filters) must agree with the Python rule for every case."""
    h = auth("officer")
    plans = ["all_applied", "should_missed", "must_missed", "pending", "none"]
    for plan in plans:
        inc = make_incident()
        client.post(f"/api/incidents/{inc['id']}/start-review", headers=h)
        if plan == "none":
            continue
        client.post(f"/api/incidents/{inc['id']}/analysis", headers=h,
                    json={"severity": "incident", "analysis": "Analysis text long enough for validation."})
        ms = client.get(f"/api/incidents/{inc['id']}", headers=h).json()["measures"]
        for i, m in enumerate(ms):
            if plan == "pending" and i == 0:
                continue
            miss = (plan == "should_missed" and m["priority"] == "should") or \
                   (plan == "must_missed" and m["priority"] == "must" and i == 0)
            body = {"status": "not_applied", "reason": "reason"} if miss else {"status": "applied"}
            client.patch(f"/api/measures/{m['id']}", json=body, headers=h)

    cs = colour_subquery()
    sql = dict(db.execute(select(cs.c.incident_id, cs.c.colour)).all())
    for inc in db.scalars(select(Incident)):
        assert sql[inc.id] == incident_colour(inc.measures), inc.reference
    assert set(sql.values()) == {"green", "yellow", "red", "grey"}


def test_stuck_generation_can_be_retried(client, auth, analysed_incident, db):
    from datetime import timedelta

    from app.models import AISummary
    h, iid = auth("officer"), analysed_incident["id"]
    s = db.get(AISummary, analysed_incident["summary"]["id"])
    s.status = "generating"
    db.commit()
    assert client.post(f"/api/incidents/{iid}/ai-summary/regenerate", headers=h).status_code == 409
    s.created_at = s.created_at - timedelta(minutes=5)
    db.commit()
    r = client.post(f"/api/incidents/{iid}/ai-summary/regenerate", headers=h)
    assert r.status_code == 200
    assert client.get(f"/api/incidents/{iid}", headers=h).json()["summary"]["status"] == "draft"


GOOD = {"summary": "Bird strike on take-off with suspected engine 2 ingestion; aircraft must stay grounded.",
        "measures": [{"description": "Borescope engine 2", "priority": "MUST", "citation": "C1"},
                     {"description": "Brief BLR crews on dawn bird activity", "priority": "Should", "citation": "C2"}]}


def test_structured_dict_reply_and_priority_case(client, auth, make_incident, use_llm):
    use_llm(GOOD)
    inc = run_analysis(client, auth, make_incident)
    assert inc["summary"]["status"] == "draft"
    assert [m["priority"] for m in inc["measures"]] == ["must", "should"]


def test_retry_after_invalid_first_reply(client, auth, make_incident, use_llm):
    llm = use_llm("I think the crew did well.", GOOD)
    inc = run_analysis(client, auth, make_incident)
    assert inc["summary"]["status"] == "draft"
    assert len(llm.prompts) == 2
    assert "previous answer could not be used" in llm.prompts[1]


def test_broken_json_then_valid(client, auth, make_incident, use_llm):
    llm = use_llm('{"summary": "He said "stop" now", "measures": []}', GOOD)
    inc = run_analysis(client, auth, make_incident)
    assert inc["summary"]["status"] == "draft" and len(llm.prompts) == 2


def test_fails_after_two_invalid_replies(client, auth, make_incident, use_llm):
    use_llm("nope", "still nope")
    inc = run_analysis(client, auth, make_incident)
    assert inc["summary"]["status"] == "failed"
    assert "twice" in inc["summary"]["error"]


# ---------------------------------------------------------------- HTTP layer
class FakeResp:
    def __init__(self, status, body=None, headers=None):
        self.status_code, self._body, self.headers = status, body or {}, headers or {}
        self.text = str(self._body)

    def json(self):
        return self._body


def test_post_retries_temporary_errors(monkeypatch):
    from app.services.ai import llm
    calls, sleeps = [], []
    seq = [FakeResp(529), FakeResp(429, headers={"retry-after": "2"}), FakeResp(200, {"ok": True})]
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: calls.append(k) or seq[len(calls) - 1])
    resp = llm.post_with_retry("https://x", headers={}, payload={}, sleep=sleeps.append)
    assert resp.json() == {"ok": True} and len(calls) == 3
    assert sleeps == [1.0, 2.0]  # backoff, then Retry-After


def test_post_does_not_retry_auth_error(monkeypatch):
    from app.services.ai import llm
    calls = []
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: calls.append(1) or FakeResp(401, {"error": "bad key"}))
    with pytest.raises(RuntimeError, match="401"):
        llm.post_with_retry("https://x", headers={}, payload={}, sleep=lambda s: None)
    assert len(calls) == 1


def test_anthropic_uses_forced_tool_call(monkeypatch):
    from app.services.ai import llm
    sent = {}

    def fake_post(url, headers, json, timeout):
        sent.update(json)
        return FakeResp(200, {"content": [{"type": "tool_use", "name": llm.AnthropicLLM.TOOL_NAME, "input": GOOD}]})

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    out = llm.AnthropicLLM("key", "claude-haiku-5-5").generate("sys", "user", rag.OUTPUT_SCHEMA)
    assert out == GOOD
    assert sent["tool_choice"] == {"type": "tool", "name": llm.AnthropicLLM.TOOL_NAME}
    assert sent["tools"][0]["input_schema"] is rag.OUTPUT_SCHEMA
