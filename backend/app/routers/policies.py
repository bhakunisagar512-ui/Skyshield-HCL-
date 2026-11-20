from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import admin_only, officer_or_admin
from app.database import get_db
from app.models import PolicyChunk, PolicyDocument
from app.schemas import PolicyIn, PolicyOut, PolicySearchHit
from app.services.ai.rag import retrieve
from app.services.policies import ingest_policy

router = APIRouter(prefix="/policies", tags=["policies"])


@router.get("", response_model=list[PolicyOut], dependencies=[Depends(officer_or_admin)])
def list_policies(db: Session = Depends(get_db)):
    rows = db.execute(
        select(PolicyDocument, func.count(PolicyChunk.id))
        .outerjoin(PolicyChunk).group_by(PolicyDocument.id).order_by(PolicyDocument.code)
    ).all()
    return [PolicyOut(id=d.id, code=d.code, title=d.title, category=d.category, source=d.source, chunk_count=n)
            for d, n in rows]


@router.post("", response_model=PolicyOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(admin_only)])
def upload_policy(body: PolicyIn, db: Session = Depends(get_db)):
    try:
        doc = ingest_policy(db, body.content)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    db.commit()
    return PolicyOut(id=doc.id, code=doc.code, title=doc.title, category=doc.category, source=doc.source,
                     chunk_count=len(doc.chunks))


@router.get("/search", response_model=list[PolicySearchHit], dependencies=[Depends(officer_or_admin)])
def search_policies(q: str = Query(min_length=3, max_length=500), category: str | None = None,
                    k: int = Query(5, ge=1, le=20), db: Session = Depends(get_db)):
    return [PolicySearchHit(key=c.key, section_ref=c.section_ref, policy_code=c.policy_code, score=c.score,
                            content=c.content) for c in retrieve(db, q, category, top_k=k)]
