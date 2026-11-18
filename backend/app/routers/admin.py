from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import admin_only
from app.core.security import hash_password
from app.core.taxonomy import IncidentStatus
from app.database import consistent_read, get_db
from app.models import Incident, User
from app.schemas import AdminIncidentDetail, AdminIncidentPage, ColourName, UserCreate, UserOut
from app.services.serialize import admin_detail, admin_item, colour_subquery

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(admin_only)])


@router.get("/incidents", response_model=AdminIncidentPage)
def admin_incidents(
    db: Session = Depends(get_db),
    colour: ColourName | None = None,
    status_: IncidentStatus | None = Query(None, alias="status"),
    category: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    consistent_read(db)
    cs = colour_subquery()
    base = select(Incident).join(cs, cs.c.incident_id == Incident.id)
    if status_:
        base = base.where(Incident.status == status_)
    if category:
        base = base.where(Incident.category == category)

    filters = []
    if status_:
        filters.append(Incident.status == status_)
    if category:
        filters.append(Incident.category == category)
    totals_rows = db.execute(
        select(cs.c.colour, func.count())
        .join(Incident, Incident.id == cs.c.incident_id)
        .where(*filters)
        .group_by(cs.c.colour)
    ).all()
    colour_totals = {c: 0 for c in ("red", "yellow", "green", "grey")}
    colour_totals.update({c: n for c, n in totals_rows})

    stmt = base.where(cs.c.colour == colour) if colour else base
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    # red first, then yellow, grey, green; newest first inside each colour
    order = func.array_position(["red", "yellow", "grey", "green"], cs.c.colour)
    rows = db.scalars(
        stmt.options(selectinload(Incident.measures), selectinload(Incident.summaries))
        .order_by(order, Incident.occurred_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return AdminIncidentPage(total=total, page=page, page_size=page_size,
                             items=[admin_item(i) for i in rows], colour_totals=colour_totals)


@router.get("/incidents/{incident_id}", response_model=AdminIncidentDetail)
def admin_incident(incident_id: int, db: Session = Depends(get_db)):
    consistent_read(db)
    i = db.scalar(select(Incident).where(Incident.id == incident_id)
                  .options(selectinload(Incident.measures), selectinload(Incident.summaries)))
    if i is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Incident not found")
    return admin_detail(i)


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.scalars(select(User).order_by(User.role, User.full_name)).all()


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(func.lower(User.email) == body.email.lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with this email already exists")
    user = User(email=body.email.lower(), full_name=body.full_name, password_hash=hash_password(body.password),
                role=body.role, designation=body.designation, base_station=body.base_station)
    db.add(user)
    db.commit()
    return user
