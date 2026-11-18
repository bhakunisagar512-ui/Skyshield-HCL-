from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def consistent_read(db: Session) -> None:
    """Run the rest of this request's reads in one REPEATABLE READ snapshot.

    An incident, its measures and its summary are loaded by separate queries. Without a
    snapshot the AI background job can commit between them, and a reader would see a
    'draft' summary with no measures yet. Any open read-only transaction (for example
    from loading the current user) is ended first so the new isolation level applies.
    """
    if db.in_transaction():
        db.commit()
    db.connection(execution_options={"isolation_level": "REPEATABLE READ"})
