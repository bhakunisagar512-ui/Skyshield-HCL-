from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import officer_only
from app.core.taxonomy import IncidentStatus, MeasureStatus
from app.database import get_db
from app.models import Measure, User
from app.schemas import MeasureOut, MeasureUpdate
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
