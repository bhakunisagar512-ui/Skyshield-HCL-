"""Load the development dataset and index the policy documents.

Usage (from backend/):
    python -m app.seed            # load into an empty database
    python -m app.seed --reset    # wipe all data first
    python -m app.seed --policies-only
"""
import argparse
import csv
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from app.database import SessionLocal
from app.models import AISummary, Incident, Measure, StatusHistory, User
from app.services.policies import ingest_policy

DATA_ROOT = Path(__file__).resolve().parents[2] / "database"

TABLES = [  # child tables first for deletes
    "policy_chunks", "policy_documents", "measures", "ai_summaries", "incident_status_history", "incidents", "users",
]
LOAD_ORDER = [
    ("users.csv", User), ("incidents.csv", Incident), ("status_history.csv", StatusHistory),
    ("ai_summaries.csv", AISummary), ("measures.csv", Measure),
]
DATETIME_COLS = {"occurred_at", "created_at", "closed_at", "changed_at", "reviewed_at", "marked_at"}
INT_COLS = {"id", "reporter_id", "officer_id", "incident_id", "changed_by_id", "reviewed_by_id", "marked_by_id"}


def _convert(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if v == "":
            out[k] = None
        elif k in DATETIME_COLS:
            out[k] = datetime.fromisoformat(v)
        elif k in INT_COLS:
            out[k] = int(v)
        elif k == "is_active":
            out[k] = v.lower() == "true"
        else:
            out[k] = v
    return out


def load_policies(db) -> int:
    count = 0
    for path in sorted((DATA_ROOT / "policies").glob("*.md")):
        ingest_policy(db, path.read_text(encoding="utf-8"))
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="delete existing data first")
    parser.add_argument("--policies-only", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.reset:
            db.execute(text("TRUNCATE " + ", ".join(TABLES) + " RESTART IDENTITY CASCADE"))
        n_pol = load_policies(db)
        print(f"policies indexed: {n_pol}")
        if not args.policies_only:
            for filename, model in LOAD_ORDER:
                with (DATA_ROOT / "data" / filename).open(encoding="utf-8") as f:
                    rows = [_convert(r) for r in csv.DictReader(f)]
                db.bulk_insert_mappings(model, rows)
                db.flush()
                print(f"{model.__tablename__}: {len(rows)}")
            for table in ("users", "incidents", "incident_status_history", "ai_summaries", "measures"):
                db.execute(text(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                                f"COALESCE((SELECT MAX(id) FROM {table}), 1))"))
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
