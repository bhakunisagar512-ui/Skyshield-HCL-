from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import officer_or_admin
from app.core.taxonomy import MeasurePriority, MeasureStatus
from app.database import get_db
from app.models import Incident, Measure
from app.services.serialize import colour_subquery

router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(officer_or_admin)])


def _pairs(rows) -> list[dict]:
    return [{"key": k, "count": n} for k, n in rows]


@router.get("/stats")
def stats(db: Session = Depends(get_db), months: int = Query(12, ge=1, le=36)):
    since = datetime.now(timezone.utc) - timedelta(days=months * 31)
    cs = colour_subquery()
    month = func.to_char(func.date_trunc("month", Incident.occurred_at), "YYYY-MM")

    by_month = db.execute(
        select(month, func.count()).where(Incident.occurred_at >= since).group_by(month).order_by(month)
    ).all()
    by_category = db.execute(
        select(Incident.category, func.count()).group_by(Incident.category).order_by(func.count().desc())
    ).all()
    by_severity = db.execute(
        select(func.coalesce(Incident.severity, "unclassified"), func.count()).group_by(Incident.severity)
    ).all()
    by_status = db.execute(select(Incident.status, func.count()).group_by(Incident.status)).all()
    by_airport = db.execute(
        select(Incident.airport_code, func.count()).group_by(Incident.airport_code)
        .order_by(func.count().desc()).limit(8)
    ).all()
    by_colour = db.execute(select(cs.c.colour, func.count()).group_by(cs.c.colour)).all()

    m_total = db.scalar(select(func.count(Measure.id))) or 0
    m_applied = db.scalar(select(func.count()).where(Measure.status == MeasureStatus.APPLIED)) or 0
    m_pending = db.scalar(select(func.count()).where(Measure.status == MeasureStatus.PENDING)) or 0
    must_not = db.scalar(select(func.count()).where(Measure.status == MeasureStatus.NOT_APPLIED,
                                                    Measure.priority == MeasurePriority.MUST)) or 0
    decided = m_total - m_pending

    colours = {c: 0 for c in ("red", "yellow", "green", "grey")}
    colours.update(dict(by_colour))
    return {
        "total_incidents": db.scalar(select(func.count(Incident.id))) or 0,
        "colours": colours,
        "by_status": _pairs(by_status),
        "by_month": _pairs(by_month),
        "by_category": _pairs(by_category),
        "by_severity": _pairs(by_severity),
        "top_airports": _pairs(by_airport),
        "measures": {
            "total": m_total, "applied": m_applied, "pending": m_pending,
            "must_not_applied": must_not,
            "applied_rate": round(m_applied / decided, 3) if decided else None,
        },
    }
