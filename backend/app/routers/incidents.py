from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_current_user, officer_only
from app.core.taxonomy import IncidentStatus, MeasureSource, Role, SummaryStatus
from app.database import consistent_read, get_db
from app.models import AISummary, Incident, Measure, StatusHistory, User
from app.schemas import (
    AnalysisIn,
    CloseIn,
    ColourName,
    IncidentCreate,
    IncidentOut,
    IncidentPage,
    MeasureCreate,
    MeasureOut,
    SummaryEdit,
)
from app.services import workflow
from app.services.serialize import colour_subquery, incident_out, list_item, measure_out

router = APIRouter(prefix="/incidents", tags=["incidents"])
GENERATION_TIMEOUT = timedelta(minutes=2)

LOAD = (selectinload(Incident.measures), selectinload(Incident.summaries),
        selectinload(Incident.history), selectinload(Incident.reporter), selectinload(Incident.officer))


def get_incident(db: Session, incident_id: int, user: User) -> Incident:
    incident = db.scalar(select(Incident).where(Incident.id == incident_id).options(*LOAD))
    if incident is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Incident not found")
    if user.role == Role.REPORTER and incident.reporter_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Incident not found")
    return incident


def reload(db: Session, incident_id: int, user: User) -> IncidentOut:
    db.expire_all()
    consistent_read(db)
    return incident_out(get_incident(db, incident_id, user))


@router.post("", response_model=IncidentOut, status_code=status.HTTP_201_CREATED)
def create_incident(body: IncidentCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    incident = Incident(**body.model_dump(), reference=workflow.next_reference(db, body.occurred_at.year),
                        reporter_id=user.id, status=IncidentStatus.SUBMITTED)
    db.add(incident)
    db.flush()
    db.add(StatusHistory(incident_id=incident.id, from_status=None, to_status=IncidentStatus.SUBMITTED,
                         changed_by_id=user.id, note="Report filed"))
    db.commit()
    return reload(db, incident.id, user)


@router.get("", response_model=IncidentPage)
def list_incidents(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    status_: IncidentStatus | None = Query(None, alias="status"),
    category: str | None = None,
    severity: str | None = None,
    colour: ColourName | None = None,
    airport: str | None = None,
    q: str | None = Query(None, max_length=100),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    workflow.check_date_range(date_from, date_to)
    consistent_read(db)
    stmt = select(Incident)
    if user.role == Role.REPORTER:
        stmt = stmt.where(Incident.reporter_id == user.id)
    if status_:
        stmt = stmt.where(Incident.status == status_)
    if category:
        stmt = stmt.where(Incident.category == category)
    if severity:
        stmt = stmt.where(Incident.severity == severity)
    if airport:
        stmt = stmt.where(Incident.airport_code == airport.upper())
    if date_from:
        stmt = stmt.where(Incident.occurred_at >= date_from)
    if date_to:
        stmt = stmt.where(Incident.occurred_at <= date_to)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Incident.title.ilike(like), Incident.description.ilike(like),
                              Incident.reference.ilike(like), Incident.aircraft_registration.ilike(like)))
    if colour:
        cs = colour_subquery()
        stmt = stmt.join(cs, cs.c.incident_id == Incident.id).where(cs.c.colour == colour)

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.options(*LOAD).order_by(Incident.occurred_at.desc())
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return IncidentPage(total=total, page=page, page_size=page_size, items=[list_item(i) for i in rows])


@router.get("/{incident_id}", response_model=IncidentOut)
def read_incident(incident_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    consistent_read(db)
    return incident_out(get_incident(db, incident_id, user))


# ------------------------------------------------------------------ officer workflow
@router.post("/{incident_id}/start-review", response_model=IncidentOut)
def start_review(incident_id: int, db: Session = Depends(get_db), user: User = Depends(officer_only)):
    incident = get_incident(db, incident_id, user)
    workflow.transition(db, incident, IncidentStatus.UNDER_REVIEW, user, "Review started")
    incident.officer_id = user.id
    db.commit()
    return reload(db, incident_id, user)


@router.post("/{incident_id}/analysis", response_model=IncidentOut)
def submit_analysis(incident_id: int, body: AnalysisIn, tasks: BackgroundTasks,
                    db: Session = Depends(get_db), user: User = Depends(officer_only)):
    incident = get_incident(db, incident_id, user)
    incident.severity = body.severity
    incident.analysis = body.analysis
    incident.officer_id = incident.officer_id or user.id
    workflow.transition(db, incident, IncidentStatus.MEASURES_PENDING, user, "Analysis submitted")
    summary = workflow.start_ai_summary(db, incident)
    db.commit()
    tasks.add_task(workflow.run_ai_summary, incident.id, summary.id)
    return reload(db, incident_id, user)


def _require_pending(incident: Incident) -> None:
    if incident.status != IncidentStatus.MEASURES_PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only incidents with measures pending can be changed")


def _latest_summary(incident: Incident) -> AISummary:
    s = incident.latest_summary
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No AI summary for this incident")
    return s


@router.post("/{incident_id}/ai-summary/regenerate", response_model=IncidentOut)
def regenerate_summary(incident_id: int, tasks: BackgroundTasks,
                       db: Session = Depends(get_db), user: User = Depends(officer_only)):
    incident = get_incident(db, incident_id, user)
    _require_pending(incident)
    latest = incident.latest_summary
    if latest and latest.status == SummaryStatus.GENERATING:
        if workflow.now() - latest.created_at < GENERATION_TIMEOUT:
            raise HTTPException(status.HTTP_409_CONFLICT, "A summary is already being generated")
        # the background job was lost (e.g. server restart); allow a retry
        latest.status, latest.error = SummaryStatus.FAILED, "Generation timed out"
    if latest and latest.status == SummaryStatus.DRAFT:
        latest.status = SummaryStatus.DISCARDED
    summary = workflow.start_ai_summary(db, incident)
    db.commit()
    tasks.add_task(workflow.run_ai_summary, incident.id, summary.id)
    return reload(db, incident_id, user)


@router.patch("/{incident_id}/ai-summary", response_model=IncidentOut)
def edit_summary(incident_id: int, body: SummaryEdit, db: Session = Depends(get_db),
                 user: User = Depends(officer_only)):
    incident = get_incident(db, incident_id, user)
    _require_pending(incident)
    s = _latest_summary(incident)
    if s.status not in (SummaryStatus.DRAFT, SummaryStatus.APPROVED):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot edit a summary that is {s.status}")
    s.summary = body.summary
    db.commit()
    return reload(db, incident_id, user)


@router.post("/{incident_id}/ai-summary/approve", response_model=IncidentOut)
def approve_summary(incident_id: int, db: Session = Depends(get_db), user: User = Depends(officer_only)):
    incident = get_incident(db, incident_id, user)
    _require_pending(incident)
    s = _latest_summary(incident)
    if s.status != SummaryStatus.DRAFT:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Only a draft summary can be approved (current: {s.status})")
    s.status, s.reviewed_by_id, s.reviewed_at = SummaryStatus.APPROVED, user.id, workflow.now()
    db.commit()
    return reload(db, incident_id, user)


@router.post("/{incident_id}/ai-summary/discard", response_model=IncidentOut)
def discard_summary(incident_id: int, db: Session = Depends(get_db), user: User = Depends(officer_only)):
    incident = get_incident(db, incident_id, user)
    _require_pending(incident)
    s = _latest_summary(incident)
    if s.status not in (SummaryStatus.DRAFT, SummaryStatus.FAILED):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot discard a summary that is {s.status}")
    s.status, s.reviewed_by_id, s.reviewed_at = SummaryStatus.DISCARDED, user.id, workflow.now()
    db.commit()
    return reload(db, incident_id, user)


@router.post("/{incident_id}/measures", response_model=MeasureOut, status_code=status.HTTP_201_CREATED)
def add_measure(incident_id: int, body: MeasureCreate, db: Session = Depends(get_db),
                user: User = Depends(officer_only)):
    incident = get_incident(db, incident_id, user)
    _require_pending(incident)
    m = Measure(incident_id=incident.id, description=body.description, priority=body.priority,
                source=MeasureSource.OFFICER)
    db.add(m)
    db.commit()
    return measure_out(m)


@router.post("/{incident_id}/close", response_model=IncidentOut)
def close_incident(incident_id: int, body: CloseIn, db: Session = Depends(get_db),
                   user: User = Depends(officer_only)):
    incident = get_incident(db, incident_id, user)
    _require_pending(incident)
    workflow.check_can_close(incident)
    incident.closing_note = body.closing_note
    workflow.transition(db, incident, IncidentStatus.CLOSED, user, body.closing_note or "Incident closed")
    db.commit()
    return reload(db, incident_id, user)
