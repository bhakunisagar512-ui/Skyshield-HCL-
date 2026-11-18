"""Evaluate retrieval and measure generation on database/eval/eval_set.json.

Metrics
  retrieval hit@1 / hit@3 : expected policy is the top / in the top 3 chunks
                            (reported with and without the category boost)
  generation format       : output parsed and every measure has a citation
  grounding               : share of measures citing a retrieved chunk
  keyword recall          : expected MUST keywords found in the MUST measures
  has must + should       : output contains both priorities

Usage (from backend/, with policies loaded):  python -m scripts.evaluate_ai [--provider mock|anthropic|openai]
"""
import argparse
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

EVAL = Path(__file__).resolve().parents[2] / "database" / "eval" / "eval_set.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default=None, help="override LLM_PROVIDER")
    ap.add_argument("--out", default=None, help="write per-case results to this JSON file")
    args = ap.parse_args()
    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider

    from app.database import SessionLocal
    from app.services.ai import rag

    cases = json.loads(EVAL.read_text(encoding="utf-8"))
    db = SessionLocal()
    rows = []
    try:
        for c in cases:
            query = rag.build_query("", c["text"], None, None)
            plain = rag.retrieve(db, query, None, top_k=3, use_category=False)
            boosted = rag.retrieve(db, rag.build_query("", c["text"], None, c["category"]), c["category"], top_k=6)
            incident = SimpleNamespace(reference=c["id"], category=c["category"], severity="incident",
                                       airport_code="DEL", flight_phase="approach", title=c["text"][:60],
                                       description=c["text"], analysis=None)
            try:
                gen = (rag._generate_mock if rag.get_llm() is None else rag._generate_with_llm)(incident, boosted)
                error = None
            except Exception as exc:  # noqa: BLE001
                gen, error = None, str(exc)
            musts = " ".join(m.description.lower() for m in gen.measures if m.priority == "must") if gen else ""
            kw_hits = sum(1 for k in c["must_keywords"] if k.lower() in musts)
            retrieved_refs = {ch.section_ref for ch in boosted}
            rows.append({
                "id": c["id"], "expected": c["expected_policy"],
                "plain_top": plain[0].policy_code, "plain_hit1": plain[0].policy_code == c["expected_policy"],
                "plain_hit3": any(h.policy_code == c["expected_policy"] for h in plain),
                "boost_hit1": boosted[0].policy_code == c["expected_policy"],
                "ok": gen is not None, "error": error,
                "grounded": (sum(m.policy_reference in retrieved_refs for m in gen.measures) / len(gen.measures)) if gen else 0,
                "kw_recall": kw_hits / len(c["must_keywords"]),
                "both_priorities": bool(gen) and {m.priority for m in gen.measures} == {"must", "should"},
                "dropped": gen.dropped_ungrounded if gen else 0,
            })
    finally:
        db.close()

    n = len(rows)
    pct = lambda key: 100 * sum(r[key] for r in rows) / n  # noqa: E731
    print(f"cases: {n}   provider: {os.environ.get('LLM_PROVIDER', 'from .env')}")
    print(f"retrieval hit@1 (text only)       {pct('plain_hit1'):5.1f}%")
    print(f"retrieval hit@3 (text only)       {pct('plain_hit3'):5.1f}%")
    print(f"retrieval hit@1 (with category)   {pct('boost_hit1'):5.1f}%")
    print(f"generation succeeded              {pct('ok'):5.1f}%")
    print(f"measures grounded in context      {pct('grounded'):5.1f}%")
    print(f"MUST keyword recall               {pct('kw_recall'):5.1f}%")
    print(f"has both must and should          {pct('both_priorities'):5.1f}%")
    misses = [f"{r['id']}: expected {r['expected']}, got {r['plain_top']}" for r in rows if not r["plain_hit1"]]
    if misses:
        print("\ntext-only top-1 misses:\n  " + "\n  ".join(misses))
    weak = [f"{r['id']} ({r['kw_recall']:.0%})" for r in rows if r["kw_recall"] < 1]
    if weak:
        print("\nincomplete MUST keyword recall: " + ", ".join(weak))
    if args.out:
        Path(args.out).write_text(json.dumps(rows, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
