from __future__ import annotations
import argparse, csv, sys
from pathlib import Path
from typing import List, Dict

from .csvlog import append_row 

# CSV utils
def _read_csv(path: str) -> List[Dict[str, str]]:
    p = Path(path)
    if not p.exists():
        print(f"[error] CSV not found: {path}", file=sys.stderr)
        sys.exit(2)
    with p.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def _write_csv(path: str, rows: List[Dict[str, str]]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    # preserve existing columns + add our judge columns if missing
    fieldnames = list(rows[0].keys()) if rows else ["question","answer","references","correct","complete"]
    for extra in ["correct", "complete", "correct_auto", "complete_auto", "judge_reason"]:
        if extra not in fieldnames:
            fieldnames.append(extra)
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

# MANUAL mode
def judge_manual(csv_in: str, csv_out: str | None) -> None:
    rows = _read_csv(csv_in)
    changed = False
    for r in rows:
        # skip already labeled
        if (r.get("correct") or "").strip() and (r.get("complete") or "").strip():
            continue
        q = (r.get("question") or "").strip()
        a = (r.get("answer") or "").strip()
        refs = (r.get("references") or "").strip()
        print("\n---")
        print("QUESTION:", q)
        print("ANSWER:", (a[:500] + ("…" if len(a) > 500 else "")))
        print("REFS:", refs)
        c = input("Is the answer CORRECT? [y/n]: ").strip().lower()
        m = input("Is the answer COMPLETE? [y/n]: ").strip().lower()
        r["correct"] = "Y" if c.startswith("y") else "N"
        r["complete"] = "Y" if m.startswith("y") else "N"
        changed = True
    _write_csv(csv_out or csv_in, rows)
    print(f"\nSaved: {csv_out or csv_in}")
    if not changed:
        print("Nothing to label (all rows already have correct/complete).")

# LLM mode (optional)
def judge_llm(csv_in: str, csv_out: str | None, model_name: str, limit: int | None) -> None:
    from pydantic import BaseModel
    from pydantic_ai import Agent, UsageLimits
    from pydantic_ai.models.openai import OpenAIChatModel

    class Verdict(BaseModel):
        correct: bool
        complete: bool
        reason: str

    judge = Agent(
        model=OpenAIChatModel(model_name),
        instructions=(
            "You will evaluate an agent's answer about Wikipedia topics.\n"
            "You are *strict*. Use the provided answer and references as evidence.\n"
            "- correct = true iff the answer's facts match Wikipedia.\n"
            "- complete = true iff the answer covers the key aspects implied by the question.\n"
            "Reply as JSON with fields: correct, complete, reason (short)."
        ),
        output_type=Verdict,
    )

    rows = _read_csv(csv_in)
    n = 0
    for r in rows:
        if limit is not None and n >= limit:
            break
        # skip if we already have manual labels
        if (r.get("correct") or "").strip() and (r.get("complete") or "").strip():
            continue
        q = r.get("question") or ""
        a = r.get("answer") or ""
        refs = r.get("references") or ""
        prompt = (
            "QUESTION:\n" + q + "\n\n"
            "ANSWER:\n" + a + "\n\n"
            "REFERENCES (Wikipedia URLs):\n" + refs + "\n"
        )
        verdict = judge.run_sync(
            prompt,
            usage_limits=UsageLimits(request_limit=2),
        ).output
        r["correct_auto"] = "Y" if verdict.correct else "N"
        r["complete_auto"] = "Y" if verdict.complete else "N"
        r["judge_reason"] = verdict.reason
        n += 1

    _write_csv(csv_out or csv_in, rows)
    print(f"\nSaved: {csv_out or csv_in} (auto-labeled {n} rows)")
    print("Review/override in your spreadsheet by filling 'correct'/'complete' columns.")
    
# CLI
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Input CSV (from wikiagent main batch)")
    ap.add_argument("--out", help="Output CSV (default: overwrite input)")
    ap.add_argument("--mode", choices=["manual", "llm"], default="manual")
    ap.add_argument("--model", default="gpt-4o-mini", help="OpenAI chat model for LLM judge")
    ap.add_argument("--limit", type=int, help="Limit #rows to auto-label (LLM mode)")
    args = ap.parse_args()

    if args.mode == "manual":
        judge_manual(args.csv, args.out)
    else:
        judge_llm(args.csv, args.out, args.model, args.limit)

if __name__ == "__main__":
    main()
