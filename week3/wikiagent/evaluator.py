from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple

import psycopg


# Data structures

@dataclass
class CheckResult:
    log_id: int
    check_name: str
    passed: Optional[bool]
    score: Optional[float]
    details: str


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_]+", text.lower())


# Postgres helpers

def get_connection() -> psycopg.Connection:
    url = os.getenv(
        "DATABASE_URL",
        "postgresql://monitoring:monitoring@localhost:5432/wikiagent_monitoring",
    )
    # autocommit
    return psycopg.connect(url, autocommit=True)


def ensure_schema(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS wikiagent_logs (
                id SERIAL PRIMARY KEY,
                filename TEXT UNIQUE NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                user_prompt TEXT,
                answer TEXT,
                instructions TEXT,
                n_references INTEGER,
                raw_json TEXT NOT NULL
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS wikiagent_checks (
                id SERIAL PRIMARY KEY,
                log_id INTEGER NOT NULL REFERENCES wikiagent_logs(id) ON DELETE CASCADE,
                check_name TEXT NOT NULL,
                passed BOOLEAN,
                score DOUBLE PRECISION,
                details TEXT
            );
            """
        )


# Log parsing helpers

def extract_core_fields(entry: dict) -> Tuple[str, str, str, List[str]]:
    """
    Returns (user_prompt, answer, instructions, references).
    """
    instructions = entry.get("system_prompt") or ""

    # Output should be the WikiAnswer dict: {"answer": "...", "references": [...]}
    out = entry.get("output") or {}
    if isinstance(out, dict):
        answer = out.get("answer") or ""
        references = out.get("references") or []
    else:
        # Fallback if output is just a string
        answer = str(out)
        references = []

    # Extract first user prompt from messages
    user_prompt = ""
    for msg in entry.get("messages", []):
        for part in msg.get("parts", []) or []:
            if part.get("part_kind") == "user-prompt":
                content = part.get("content", "")
                user_prompt = content if isinstance(content, str) else str(content)
                break
        if user_prompt:
            break

    return user_prompt, answer, instructions, references


def extract_tool_calls(entry: dict) -> list[str]:
    """Return sequence of tool names in chronological order."""
    tool_calls: list[str] = []
    for msg in entry.get("messages", []):
        for part in msg.get("parts", []) or []:
            if part.get("part_kind") == "tool-call":
                name = part.get("tool_name")
                if name:
                    tool_calls.append(name)
    return tool_calls


# Rule-based evaluation

def evaluate_entry(log_id: int, entry: dict) -> List[CheckResult]:
    user_prompt, answer, instructions, references = extract_core_fields(entry)
    tool_calls = extract_tool_calls(entry)

    checks: List[CheckResult] = []

    # Follow instruction

    # Search_wikipedia should be first tool
    search_first = bool(tool_calls) and tool_calls[0] == "search_wikipedia"

    num_get_page = sum(1 for t in tool_calls if t == "get_page_raw")
    refs_ok_count = 1 <= len(references) <= 5
    refs_ok_format = all("wikipedia.org/wiki" in r for r in references)
    follow_all = search_first and (2 <= num_get_page <= 5) and refs_ok_count and refs_ok_format

    checks.append(
        CheckResult(
            log_id=log_id,
            check_name="follow_instruction",
            passed=follow_all if answer else None,
            score=None,
            details=(
                f"search_first={search_first}, "
                f"num_get_page={num_get_page}, "
                f"n_refs={len(references)}, "
                f"refs_ok_format={refs_ok_format}"
            ),
        )
    )

    # Answer relevant

    p_tokens = set(_tokenize(user_prompt))
    a_tokens = set(_tokenize(answer))
    overlap = len(p_tokens & a_tokens)
    jaccard = overlap / max(1, len(p_tokens | a_tokens))
    relevant = jaccard >= 0.08 if user_prompt and answer else None

    checks.append(
        CheckResult(
            log_id=log_id,
            check_name="answer_relevant",
            passed=relevant,
            score=jaccard if user_prompt and answer else None,
            details=f"token_overlap={overlap}, jaccard={jaccard:.3f}",
        )
    )

    # Has references

    has_ref = len(references) > 0 or ("wikipedia.org/wiki" in answer)
    checks.append(
        CheckResult(
            log_id=log_id,
            check_name="has_references",
            passed=has_ref if answer else None,
            score=None,
            details=f"n_refs={len(references)}",
        )
    )

    return checks


# Main ingestion/eval pipeline

def iter_log_files(logs_dir: Path) -> list[Path]:
    return sorted(logs_dir.glob("*.json"))


def upsert_log_and_checks(conn: psycopg.Connection, path: Path, entry: dict) -> None:
    user_prompt, answer, instructions, references = extract_core_fields(entry)
    with conn.cursor() as cur:
        # Avoid duplicate logs on re-run
        cur.execute(
            "SELECT id FROM wikiagent_logs WHERE filename = %s",
            (path.name,),
        )
        row = cur.fetchone()
        if row:
            log_id = row[0]
            # Replace checks on re-run
            cur.execute("DELETE FROM wikiagent_checks WHERE log_id = %s", (log_id,))
        else:
            cur.execute(
                """
                INSERT INTO wikiagent_logs (filename, user_prompt, answer, instructions, n_references, raw_json)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (path.name, user_prompt, answer, instructions, len(references), json.dumps(entry)),
            )
            log_id = cur.fetchone()[0]

        checks = evaluate_entry(log_id, entry)
        for c in checks:
            cur.execute(
                """
                INSERT INTO wikiagent_checks (log_id, check_name, passed, score, details)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (c.log_id, c.check_name, c.passed, c.score, c.details),
            )


def main() -> None:
    logs_dir = Path(os.getenv("WIKIAGENT_LOGS_DIR", "week4/logs"))
    if not logs_dir.exists():
        print(f"No log directory found at {logs_dir}; nothing to do.")
        return

    files = iter_log_files(logs_dir)
    if not files:
        print(f"No JSON log files found in {logs_dir}.")
        return

    conn = get_connection()
    ensure_schema(conn)

    print(f"Evaluating {len(files)} logs from {logs_dir}...")
    for path in files:
        try:
            with path.open("r", encoding="utf-8") as f:
                entry = json.load(f)
            upsert_log_and_checks(conn, path, entry)
            print(f"  processed {path.name}")
        except Exception as e:
            print(f"  ERROR processing {path}: {e}")

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
