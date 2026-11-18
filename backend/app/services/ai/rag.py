"""Retrieval-augmented generation of the incident summary and measures.

Pipeline:
  1. Build a query from the incident (title, description, analysis, category).
  2. Retrieve policy chunks with pgvector cosine distance, boosting chunks whose
     policy matches the incident category (the category is reported, so it is fair
     to use it).
  3. Generate a summary + must/should measures, each citing a retrieved chunk.
  4. Grounding check: any measure citing a chunk that was not retrieved is dropped.
"""
import json
import re
from dataclasses import dataclass, field

from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.taxonomy import AIRPORTS, CATEGORIES, MeasurePriority
from app.models import Incident, PolicyChunk, PolicyDocument
from app.services.ai.embeddings import get_embedder
from app.services.ai.llm import get_llm
from app.services.policy_parser import MEASURE_RE

CATEGORY_BOOST = 0.25


@dataclass
class RetrievedChunk:
    key: str  # C1, C2 ...
    section_ref: str
    policy_code: str
    policy_category: str | None
    content: str
    score: float


@dataclass
class GeneratedMeasure:
    description: str
    priority: str
    policy_reference: str


@dataclass
class GenerationResult:
    summary: str
    measures: list[GeneratedMeasure]
    citations: list[str]
    model: str
    dropped_ungrounded: int = 0
    chunks: list[RetrievedChunk] = field(default_factory=list)


def build_query(title: str, description: str, analysis: str | None, category: str | None) -> str:
    label = CATEGORIES.get(category or "", ("", False))[0]
    return " ".join(p for p in [label, title, description, analysis or ""] if p)


def retrieve(db: Session, query: str, category: str | None, top_k: int | None = None,
             use_category: bool = True) -> list[RetrievedChunk]:
    top_k = top_k or get_settings().rag_top_k
    [qvec] = get_embedder().embed([query])
    distance = PolicyChunk.embedding.cosine_distance(qvec)
    rows = db.execute(
        select(PolicyChunk, PolicyDocument, distance.label("dist"))
        .join(PolicyDocument)
        .order_by(distance)
        .limit(max(top_k * 4, 20))
    ).all()
    scored = []
    for chunk, doc, dist in rows:
        score = 1.0 - float(dist)
        if use_category and category and doc.category == category:
            score += CATEGORY_BOOST
        scored.append((score, chunk, doc))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [
        RetrievedChunk(f"C{i}", c.section_ref, d.code, d.category, c.content, round(s, 4))
        for i, (s, c, d) in enumerate(scored[:top_k], start=1)
    ]


# ------------------------------------------------------------------ generation

SYSTEM_PROMPT = """You are an aviation safety analyst for an Indian airline's safety department.
You write a short case summary and the measures the Safety Officer should take.

Rules:
- Use ONLY the policy excerpts provided. Never invent regulations or references.
- Every measure must cite exactly one excerpt key such as "C2".
- priority is "must" when the excerpt marks it MUST or it is safety-critical, otherwise "should".
- Summary: at most 70 words. One sentence on what happened, then the main safety risk
  and why it matters (use the Safety Officer's analysis), then the severity.
  Do not repeat the description word for word.
- 3 to 8 measures, specific to this incident (name the engine, runway, airport or
  system involved where known), no duplicates.

Return the result in the required structure: a summary string and a list of
measures, each with description, priority ("must" or "should") and citation."""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "Case summary, at most 70 words"},
        "measures": {
            "type": "array",
            "minItems": 1,
            "maxItems": 10,
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "priority": {"type": "string", "enum": ["must", "should"]},
                    "citation": {"type": "string", "description": "Excerpt key such as C1"},
                },
                "required": ["description", "priority", "citation"],
            },
        },
    },
    "required": ["summary", "measures"],
}
RETRY_NOTE = ("\n\nYour previous answer could not be used ({error}). "
              "Return ONLY the required structure with valid values.")


class _LLMMeasure(BaseModel):
    description: str = Field(min_length=5)
    priority: MeasurePriority
    citation: str

    @field_validator("priority", mode="before")
    @classmethod
    def _lower(cls, v):
        return v.strip().lower() if isinstance(v, str) else v


class _LLMOutput(BaseModel):
    summary: str = Field(min_length=10)
    measures: list[_LLMMeasure]


def _incident_block(incident: Incident) -> str:
    airport = AIRPORTS.get(incident.airport_code, ("", incident.airport_code))[1]
    return (
        f"Reference: {incident.reference}\nCategory: {CATEGORIES.get(incident.category, ('Other',))[0]}\n"
        f"Severity: {incident.severity or 'not set'}\nLocation: {airport} ({incident.airport_code}), "
        f"phase: {incident.flight_phase}\nTitle: {incident.title}\nDescription: {incident.description}\n"
        f"Safety Officer analysis: {incident.analysis or 'none'}"
    )


def _parse_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"no JSON object in reply: {text[:120]!r}")
    return json.loads(text[start : end + 1])


def _to_output(raw: dict | str) -> "_LLMOutput":
    data = raw if isinstance(raw, dict) else _parse_json(raw)
    return _LLMOutput.model_validate(data)


def _generate_with_llm(incident: Incident, chunks: list[RetrievedChunk]) -> GenerationResult:
    llm = get_llm()
    assert llm is not None
    excerpts = "\n\n".join(f"[{c.key}] {c.section_ref}\n{c.content}" for c in chunks)
    user = f"INCIDENT\n{_incident_block(incident)}\n\nPOLICY EXCERPTS\n{excerpts}"
    try:
        out = _to_output(llm.generate(SYSTEM_PROMPT, user, OUTPUT_SCHEMA))
    except (ValueError, ValidationError) as first_error:
        # one retry, telling the model what was wrong
        short = str(first_error).splitlines()[0][:200]
        try:
            out = _to_output(llm.generate(SYSTEM_PROMPT, user + RETRY_NOTE.format(error=short), OUTPUT_SCHEMA))
        except (ValueError, ValidationError) as exc:
            raise RuntimeError(f"Model returned invalid output twice: {exc}") from exc

    by_key = {c.key: c for c in chunks}
    measures, dropped, seen = [], 0, set()
    for m in out.measures:
        chunk = by_key.get(m.citation.strip().strip("[]"))
        if chunk is None:
            dropped += 1  # grounding check: citation not in retrieved context
            continue
        key = m.description.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        measures.append(GeneratedMeasure(m.description.strip(), m.priority.value, chunk.section_ref))
    if not measures:
        raise RuntimeError("Model returned no grounded measures")
    return GenerationResult(out.summary.strip(), measures, sorted({m.policy_reference for m in measures}),
                            llm.name, dropped, chunks)


def _generate_mock(incident: Incident, chunks: list[RetrievedChunk]) -> GenerationResult:
    """Offline generator: takes MUST/SHOULD lines from the best-matching policy."""
    if not chunks:
        raise RuntimeError("No policy documents loaded")
    target = incident.category if any(c.policy_category == incident.category for c in chunks) else chunks[0].policy_category
    musts, shoulds = [], []
    for c in chunks:
        if c.policy_category != target:
            continue
        for line in c.content.splitlines():
            m = MEASURE_RE.match(line.strip())
            if m:
                bucket = musts if m.group(1) == "MUST" else shoulds
                bucket.append(GeneratedMeasure(m.group(2).strip(), m.group(1).lower(), c.section_ref))
    measures = musts[:4] + shoulds[:3]
    if not measures:
        raise RuntimeError("No measures found in retrieved policies")
    airport = AIRPORTS.get(incident.airport_code, ("", incident.airport_code))[1]
    first_analysis = (incident.analysis or "").split(".")[0].strip()
    summary = (
        f"{CATEGORIES.get(incident.category, ('Occurrence',))[0]} at {airport} during {incident.flight_phase.replace('_', ' ')}"
        f"{', classified as ' + incident.severity.replace('_', ' ') if incident.severity else ''}. "
        f"{incident.title}. {first_analysis + '.' if first_analysis else ''} "
        f"{len(musts[:4])} mandatory and {len(shoulds[:3])} recommended measures apply."
    ).replace("  ", " ").strip()
    return GenerationResult(summary, measures, sorted({m.policy_reference for m in measures}),
                            "mock:policy-extract", 0, chunks)


def generate_for_incident(db: Session, incident: Incident) -> GenerationResult:
    query = build_query(incident.title, incident.description, incident.analysis, incident.category)
    chunks = retrieve(db, query, incident.category)
    if get_llm() is None:
        return _generate_mock(incident, chunks)
    return _generate_with_llm(incident, chunks)
