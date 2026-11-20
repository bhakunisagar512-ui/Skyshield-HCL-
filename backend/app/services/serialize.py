"""Turn ORM objects into API shapes, and the SQL mirror of the colour rule."""
from sqlalchemy import Integer, case, func, select
from sqlalchemy.sql import Subquery

from app.core.taxonomy import MeasurePriority, MeasureStatus
from app.models import Incident, Measure
from app.schemas import (
    AdminIncidentDetail,
    AdminIncidentItem,
    HistoryOut,
    IncidentListItem,
    IncidentOut,
    MeasureCounts,
    MeasureOut,
    SummaryOut,
)
from app.services.status_rules import incident_colour, measure_icon

_COMPUTED = {"icon", "completed_late", "completed_by"}


def measure_out(m: Measure) -> MeasureOut:
    data = {c: getattr(m, c) for c in MeasureOut.model_fields if c not in _COMPUTED}
    data.update(icon=measure_icon(m), completed_late=m.completed_at is not None,
                completed_by=m.completed_by.full_name if m.completed_by else None)
    return MeasureOut.model_validate(data)


def list_item(i: Incident) -> IncidentListItem:
    return IncidentListItem.model_validate({**_base(i), "colour": incident_colour(i.measures)})


def incident_out(i: Incident) -> IncidentOut:
    latest = i.latest_summary
    return IncidentOut.model_validate({
        **_base(i),
        "colour": incident_colour(i.measures),
        "description": i.description, "flight_phase": i.flight_phase,
        "aircraft_registration": i.aircraft_registration, "aircraft_type": i.aircraft_type,
        "operator_code": i.operator_code, "flight_number": i.flight_number, "analysis": i.analysis,
        "closing_note": i.closing_note, "closed_at": i.closed_at,
        "measures": [measure_out(m) for m in i.measures],
        "summary": SummaryOut.model_validate(latest) if latest else None,
        "history": [HistoryOut.model_validate(h) for h in i.history],
    })


def _base(i: Incident) -> dict:
    return {
        "id": i.id, "reference": i.reference, "title": i.title, "category": i.category,
        "occurred_at": i.occurred_at, "airport_code": i.airport_code, "severity": i.severity,
        "status": i.status, "reporter": i.reporter, "officer": i.officer, "created_at": i.created_at,
    }


def _short(text: str | None, limit: int = 220) -> str | None:
    if not text:
        return None
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


def counts(measures: list[Measure]) -> MeasureCounts:
    return MeasureCounts(
        total=len(measures),
        applied=sum(m.status == MeasureStatus.APPLIED for m in measures),
        not_applied_must=sum(m.status == MeasureStatus.NOT_APPLIED and m.priority == MeasurePriority.MUST for m in measures),
        not_applied_should=sum(m.status == MeasureStatus.NOT_APPLIED and m.priority == MeasurePriority.SHOULD for m in measures),
        pending=sum(m.status == MeasureStatus.PENDING for m in measures),
        completed_late=sum(m.completed_at is not None for m in measures),
    )


def admin_item(i: Incident) -> AdminIncidentItem:
    latest = i.latest_summary
    return AdminIncidentItem(
        id=i.id, reference=i.reference, title=i.title, category=i.category, severity=i.severity,
        status=i.status, colour=incident_colour(i.measures), occurred_at=i.occurred_at,
        airport_code=i.airport_code, short_summary=_short(latest.summary if latest else None),
        counts=counts(i.measures),
    )


def admin_detail(i: Incident) -> AdminIncidentDetail:
    latest = i.latest_summary
    ms = [measure_out(m) for m in i.measures]
    return AdminIncidentDetail(
        id=i.id, reference=i.reference, title=i.title, issue=i.description, category=i.category,
        severity=i.severity, status=i.status, colour=incident_colour(i.measures), airport_code=i.airport_code,
        occurred_at=i.occurred_at, short_summary=latest.summary if latest else None,
        summary_status=latest.status if latest else None,
        suggested_measures=[m for m in ms if m.source == "ai"],
        applied_measures=[m for m in ms if m.status == "applied"],
        not_applied_measures=[m for m in ms if m.status == "not_applied"],
        pending_measures=[m for m in ms if m.status == "pending"],
    )


def colour_subquery() -> Subquery:
    """SQL version of status_rules.incident_colour, used for filtering and totals.
    A test checks that it always agrees with the Python function."""
    total = func.count(Measure.id)
    pending = func.sum(case((Measure.status == MeasureStatus.PENDING, 1), else_=0)).cast(Integer)
    must_not = func.sum(case(((Measure.status == MeasureStatus.NOT_APPLIED) &
                              (Measure.priority == MeasurePriority.MUST), 1), else_=0)).cast(Integer)
    not_applied = func.sum(case((Measure.status == MeasureStatus.NOT_APPLIED, 1), else_=0)).cast(Integer)
    agg = (
        select(Incident.id.label("incident_id"), total.label("total"), pending.label("pending"),
               must_not.label("must_not"), not_applied.label("not_applied"))
        .outerjoin(Measure, Measure.incident_id == Incident.id)
        .group_by(Incident.id)
        .subquery()
    )
    colour = case(
        ((agg.c.total == 0) | (agg.c.pending > 0), "grey"),
        (agg.c.must_not > 0, "red"),
        (agg.c.not_applied > 0, "yellow"),
        else_="green",
    )
    return select(agg.c.incident_id, colour.label("colour")).subquery()
