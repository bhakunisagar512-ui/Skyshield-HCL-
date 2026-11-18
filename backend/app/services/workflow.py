"""Incident workflow: transitions, history, measures and the AI background job."""
import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.taxonomy import IncidentStatus, MeasureSource, MeasureStatus, SummaryStatus
from app.database import SessionLocal
from app.models import AISummary, Incident, Measure, StatusHistory, User
from app.services.ai.rag import generate_for_incident
from app.services.status_rules import can_transition, close_blockers

log = logging.getLogger("skyshield.workflow")


def now() -> datetime:
    return datetime.now(timezone.utc)


def next_reference(db: Session, year: int) -> str:
    prefix = f"SKY-{year}-"
    last = db.scalar(select(func.max(Incident.reference)).where(Incident.reference.like(f"{prefix}%")))
    seq = int(last.rsplit("-", 1)[1]) + 1 if last else 1
    return f"{prefix}{seq:04d}"


def transition(db: Session, incident: Incident, target: IncidentStatus, user: User, note: str | None = None) -> None:
    if not can_transition(incident.status, target):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"Cannot move incident from '{incident.status}' to '{target}'")
    db.add(StatusHistory(incident_id=incident.id, from_status=incident.status, to_status=target,
                         changed_by_id=user.id, note=note))
    incident.status = target
    if target == IncidentStatus.CLOSED:
        incident.closed_at = now()


def start_ai_summary(db: Session, incident: Incident) -> AISummary:
    """Create a 'generating' summary row; the caller schedules run_ai_summary."""
    summary = AISummary(incident_id=incident.id, status=SummaryStatus.GENERATING)
    db.add(summary)
    db.flush()
    return summary


def run_ai_summary(incident_id: int, summary_id: int) -> None:
    """Background job. Uses its own session so it can run after the response."""
    db = SessionLocal()
    try:
        incident = db.get(Incident, incident_id)
        summary = db.get(AISummary, summary_id)
        if incident is None or summary is None:
            return
        try:
            result = generate_for_incident(db, incident)
        except Exception as exc:  # noqa: BLE001 - any provider failure becomes a 'failed' summary
            log.exception("AI summary failed for incident %s", incident_id)
            summary.status = SummaryStatus.FAILED
            summary.error = str(exc)[:2000]
            db.commit()
            return

        # replace earlier AI suggestions that nobody has acted on yet
        db.execute(delete(Measure).where(Measure.incident_id == incident.id,
                                         Measure.source == MeasureSource.AI,
                                         Measure.status == MeasureStatus.PENDING))
        existing = {m.description.strip().lower() for m in
                    db.scalars(select(Measure).where(Measure.incident_id == incident.id))}
        for m in result.measures:
            if m.description.strip().lower() in existing:
                continue
            db.add(Measure(incident_id=incident.id, description=m.description, priority=m.priority,
                           source=MeasureSource.AI, policy_reference=m.policy_reference))
        summary.summary = result.summary
        summary.citations = "; ".join(result.citations)
        summary.model = result.model
        summary.status = SummaryStatus.DRAFT
        if result.dropped_ungrounded:
            summary.error = f"{result.dropped_ungrounded} ungrounded measure(s) removed by citation check"
        db.commit()
    finally:
        db.close()


def check_can_close(incident: Incident) -> None:
    latest = incident.latest_summary
    problems = close_blockers(incident.measures, latest.status if latest else None)
    if problems:
        raise HTTPException(status.HTTP_409_CONFLICT, " ".join(problems))
