"""Single source of truth for incident colour and status transitions."""
from collections.abc import Iterable
from typing import Protocol

from app.core.taxonomy import Colour, IncidentStatus, MeasurePriority, MeasureStatus


class MeasureLike(Protocol):
    priority: str
    status: str


def incident_colour(measures: Iterable[MeasureLike]) -> Colour:
    """Worst-measure rule.

    grey   - no measures yet, or any measure still pending
    red    - any MUST measure not applied
    yellow - all MUST applied, some SHOULD not applied
    green  - every measure applied
    """
    items = list(measures)
    if not items or any(m.status == MeasureStatus.PENDING for m in items):
        return Colour.GREY
    if any(m.priority == MeasurePriority.MUST and m.status == MeasureStatus.NOT_APPLIED for m in items):
        return Colour.RED
    if any(m.status == MeasureStatus.NOT_APPLIED for m in items):
        return Colour.YELLOW
    return Colour.GREEN


def measure_icon(m: MeasureLike) -> str:
    """tick / exclamation / cross / pending, as shown on the admin panel."""
    if m.status == MeasureStatus.APPLIED:
        return "tick"
    if m.status == MeasureStatus.NOT_APPLIED:
        return "cross" if m.priority == MeasurePriority.MUST else "exclamation"
    return "pending"


ALLOWED_TRANSITIONS: dict[IncidentStatus, set[IncidentStatus]] = {
    IncidentStatus.SUBMITTED: {IncidentStatus.UNDER_REVIEW},
    IncidentStatus.UNDER_REVIEW: {IncidentStatus.MEASURES_PENDING},
    IncidentStatus.MEASURES_PENDING: {IncidentStatus.CLOSED},
    IncidentStatus.CLOSED: set(),
}


def can_transition(current: str, target: str) -> bool:
    return IncidentStatus(target) in ALLOWED_TRANSITIONS[IncidentStatus(current)]


def close_blockers(measures: Iterable[MeasureLike], summary_status: str | None) -> list[str]:
    """Reasons an incident cannot be closed yet (empty list = can close)."""
    items = list(measures)
    problems = []
    if not items:
        problems.append("Add at least one measure before closing.")
    pending = sum(1 for m in items if m.status == MeasureStatus.PENDING)
    if pending:
        problems.append(f"{pending} measure(s) still pending. Mark each one applied or not applied.")
    if summary_status in ("draft", "generating"):
        problems.append("Approve or discard the AI summary before closing.")
    return problems
