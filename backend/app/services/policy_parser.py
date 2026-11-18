"""Parse SOP markdown files into documents, section chunks and measures.

Format expected:
    # <CODE>: <Title>
    Code: <CODE>
    Category: <category code | general>
    Source: <free text>

    ## 1. Section title
    text ...
    - MUST: measure text
    - SHOULD: measure text
"""
import re
from dataclasses import dataclass, field

MEASURE_RE = re.compile(r"^-\s*(MUST|SHOULD):\s*(.+)$")


@dataclass
class ParsedChunk:
    index: int
    section_ref: str
    content: str
    measures: list[tuple[str, str]] = field(default_factory=list)  # (priority, text)


@dataclass
class ParsedPolicy:
    code: str
    title: str
    category: str | None
    source: str | None
    content: str
    chunks: list[ParsedChunk]


def parse_policy(text: str) -> ParsedPolicy:
    lines = text.strip().splitlines()
    header = lines[0].lstrip("# ").strip()
    code, _, title = header.partition(":")
    meta: dict[str, str] = {}
    body_start = 1
    for i, line in enumerate(lines[1:], start=1):
        if line.startswith("## "):
            body_start = i
            break
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip().lower()] = v.strip()

    code = meta.get("code", code.strip())
    category = meta.get("category")
    if category == "general":
        category = None

    chunks: list[ParsedChunk] = []
    current_title: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        if current_title is None:
            return
        body = "\n".join(current_lines).strip()
        heading = re.sub(r"^\d+\.\s*", "", current_title)
        number = re.match(r"^(\d+)\.", current_title)
        ref = f"{code} §{number.group(1)} {heading}" if number else f"{code} {heading}"
        measures = []
        for bl in body.splitlines():
            m = MEASURE_RE.match(bl.strip())
            if m:
                measures.append((m.group(1).lower(), m.group(2).strip()))
        chunks.append(
            ParsedChunk(
                index=len(chunks),
                section_ref=ref,
                content=f"{title.strip()} - {heading}\n{body}",
                measures=measures,
            )
        )

    for line in lines[body_start:]:
        if line.startswith("## "):
            flush()
            current_title = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)
    flush()

    return ParsedPolicy(
        code=code,
        title=title.strip(),
        category=category,
        source=meta.get("source"),
        content=text.strip(),
        chunks=chunks,
    )
