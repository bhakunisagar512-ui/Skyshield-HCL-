from dataclasses import dataclass

import pytest
from app.services.status_rules import can_transition, close_blockers, incident_colour, measure_icon


@dataclass
class M:
    priority: str
    status: str


A_MUST, A_SHOULD = M("must", "applied"), M("should", "applied")
X_MUST, X_SHOULD = M("must", "not_applied"), M("should", "not_applied")
P_MUST, P_SHOULD = M("must", "pending"), M("should", "pending")


@pytest.mark.parametrize("measures, expected", [
    ([], "grey"),
    ([A_MUST, A_SHOULD], "green"),
    ([A_MUST], "green"),
    ([A_MUST, X_SHOULD], "yellow"),
    ([A_MUST, A_SHOULD, X_SHOULD], "yellow"),
    ([X_MUST, A_SHOULD], "red"),
    ([X_MUST, X_SHOULD], "red"),
    ([A_MUST, P_SHOULD], "grey"),
    ([X_MUST, P_SHOULD], "grey"),  # pending wins: still being worked on
    ([P_MUST], "grey"),
])
def test_incident_colour(measures, expected):
    assert incident_colour(measures) == expected


@pytest.mark.parametrize("measure, icon", [
    (A_MUST, "tick"), (A_SHOULD, "tick"), (X_MUST, "cross"), (X_SHOULD, "exclamation"), (P_MUST, "pending"),
])
def test_measure_icon(measure, icon):
    assert measure_icon(measure) == icon


@pytest.mark.parametrize("current, target, ok", [
    ("submitted", "under_review", True),
    ("under_review", "measures_pending", True),
    ("measures_pending", "closed", True),
    ("submitted", "closed", False),
    ("submitted", "measures_pending", False),
    ("closed", "under_review", False),
    ("measures_pending", "under_review", False),
])
def test_transitions(current, target, ok):
    assert can_transition(current, target) is ok


def test_close_blockers():
    assert close_blockers([], None) == ["Add at least one measure before closing."]
    assert any("pending" in p for p in close_blockers([A_MUST, P_SHOULD], "approved"))
    assert any("AI summary" in p for p in close_blockers([A_MUST], "draft"))
    assert close_blockers([A_MUST, X_SHOULD], "approved") == []
    assert close_blockers([X_MUST], None) == []  # a red incident may close
