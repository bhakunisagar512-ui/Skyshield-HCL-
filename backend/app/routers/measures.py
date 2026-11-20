from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import officer_only
from app.core.taxonomy import IncidentStatus, MeasureStatus
from app.database import get_db
from app.models import Measure, StatusHistory, User
from app.schemas import MeasureComplete, MeasureOut, MeasureUpdate
from app.services.serialize import measure_out
from app.services.workflow import now

router = APIRouter(prefix="/measures", tags=["measures"])


@router.patch("/{measure_id}", response_model=MeasureOut)
def update_measure(measure_id: int, body: MeasureUpdate, db: Session = Depends(get_db),
                   user: User = Depends(officer_only)):
    m = db.get(Measure, measure_id)
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Measure not found")
    if m.incident.status != IncidentStatus.MEASURES_PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, "Measures can only change while the incident is open")
    if body.priority is not None:
        m.priority = body.priority
    if body.status is not None:
        m.status = body.status
        if body.status == MeasureStatus.PENDING:
            m.reason, m.marked_by_id, m.marked_at = None, None, None
        else:
            m.reason = body.reason.strip() if body.status == MeasureStatus.NOT_APPLIED else (body.reason or None)
            m.marked_by_id, m.marked_at = user.id, now()
    db.commit()
    return measure_out(m)


@router.post("/{measure_id}/complete", response_model=MeasureOut)
def complete_after_closing(measure_id: int, body: MeasureComplete, db: Session = Depends(get_db),
                           user: User = Depends(officer_only)):
    """Record that a measure left 'not applied' at closing has since been carried out.
    Any Safety Officer may do this. The incident stays closed, the original reason is
    kept, and the follow-up is written to the incident history."""
    m = db.get(Measure, measure_id)
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Measure not found")
    if m.incident.status != IncidentStatus.CLOSED:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "The incident is still open: mark the measure applied in the checklist instead")
    if m.status != MeasureStatus.NOT_APPLIED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a measure that was not applied can be completed later")
    note = body.note.strip()
    m.status = MeasureStatus.APPLIED
    m.completion_note, m.completed_by_id, m.completed_at = note, user.id, now()
    db.add(StatusHistory(incident_id=m.incident_id, from_status=IncidentStatus.CLOSED, to_status=IncidentStatus.CLOSED,
                         changed_by_id=user.id,
                         note=f"Follow-up: {m.priority.upper()} measure completed after closing ({m.description[:120]}). {note}"))
    db.commit()
    db.refresh(m)
    return measure_out(m)
