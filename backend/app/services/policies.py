from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PolicyChunk, PolicyDocument
from app.services.ai.embeddings import get_embedder
from app.services.policy_parser import parse_policy


def ingest_policy(db: Session, text: str) -> PolicyDocument:
    """Create or replace a policy document, re-chunk and re-embed it."""
    parsed = parse_policy(text)
    if not parsed.chunks:
        raise ValueError("Policy has no '## ' sections to index")

    doc = db.scalar(select(PolicyDocument).where(PolicyDocument.code == parsed.code))
    if doc is None:
        doc = PolicyDocument(code=parsed.code)
        db.add(doc)
    doc.title, doc.category, doc.source, doc.content = parsed.title, parsed.category, parsed.source, parsed.content
    doc.chunks.clear()
    db.flush()

    vectors = get_embedder().embed([c.content for c in parsed.chunks])
    for ch, vec in zip(parsed.chunks, vectors):
        doc.chunks.append(PolicyChunk(chunk_index=ch.index, section_ref=ch.section_ref, content=ch.content, embedding=vec))
    db.flush()
    return doc
