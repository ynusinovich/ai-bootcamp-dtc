import os, argparse
from .wikiagent import run_sync
from .csvlog import append_row

DEFAULT_QUESTION = "where do capybaras live?"
LOG_CSV = os.getenv("WIKIAGENT_LOG_CSV", "wikiagent/wikiagent_runs.csv")


def format_and_print(result):
    out = result.output
    print("\n=== ANSWER ===\n")
    print(out.answer.strip())
    print("\n=== REFERENCES ===")
    for ref in out.references:
        print(ref)


def ask(question: str, out_csv: str = LOG_CSV):
    result = run_sync(question)
    format_and_print(result)
    # log to CSV (correct/complete left blank for you to annotate later)
    append_row(out_csv, question, result.output.answer, result.output.references)
    return result


def ask_batch(questions_file: str, out_csv: str):
    with open(questions_file, "r", encoding="utf-8") as f:
        questions = [q.strip() for q in f if q.strip()]
    for q in questions:
        print(f"\n---\nQ: {q}")
        ask(q, out_csv=out_csv)
    print(f"\nSaved: {out_csv}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", help="Path to a text file with one question per line")
    parser.add_argument("--out", default=LOG_CSV, help="Output CSV path")
    parser.add_argument("--q", help="Ask a single question")
    args = parser.parse_args()

    if args.batch:
        ask_batch(args.batch, args.out)
    else:
        ask(args.q or DEFAULT_QUESTION, out_csv=args.out)
