# week3/wikiagent/main.py

from __future__ import annotations

import argparse
import os

from . import agent, run_sync
from .csvlog import append_row
from .agent_logging import log_run, save_log
from .wikiagent import CapybaraGuardrailError

DEFAULT_QUESTION = "where do capybaras live?"
# For the manual spreadsheet work:
LOG_CSV = os.getenv("WIKIAGENT_LOG_CSV", "week3/wikiagent/wikiagent_runs.csv")


def format_and_print(result):
    out = result.output
    print("\n=== ANSWER ===\n")
    print(out.answer.strip())
    print("\n=== REFERENCES ===")
    for ref in out.references:
        print(ref)


def ask(question: str, out_csv: str = LOG_CSV):
    # Run the agent
    try:
        result = run_sync(question)
    except CapybaraGuardrailError as e:
        print(f"\n[GUARDRAIL BLOCKED] {e}")
        return None

    # Print to console
    format_and_print(result)

    # Append to CSV (for your manual correct/complete labeling)
    append_row(out_csv, question, result.output.answer, result.output.references)

    # JSON log for monitoring / evaluation
    log_entry = log_run(agent, result)
    path = save_log(log_entry)
    print(f"\n[log] saved JSON log to {path}")

    return result


def ask_batch(questions_file: str, out_csv: str):
    with open(questions_file, "r", encoding="utf-8") as f:
        questions = [q.strip() for q in f if q.strip()]

    for q in questions:
        print(f"\n---\nQ: {q}")
        ask(q, out_csv=out_csv)

    print(f"\nSaved CSV: {out_csv}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", help="Text file with one question per line")
    parser.add_argument("--out", default=LOG_CSV, help="Output CSV path")
    parser.add_argument("--q", help="Single question")
    args = parser.parse_args()

    if args.batch:
        ask_batch(args.batch, args.out)
    else:
        ask(args.q or DEFAULT_QUESTION, out_csv=args.out)
