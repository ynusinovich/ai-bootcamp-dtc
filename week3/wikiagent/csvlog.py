from __future__ import annotations
import csv
from pathlib import Path
from typing import List

def append_row(csv_path: str, question: str, answer: str, references: List[str],
               correct: str = "", complete: str = "") -> None:
    """
    Append one row to the CSV. Creates the file and header if missing.
    Columns: question, answer, references (semicolon-separated), correct, complete
    """
    path = Path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    need_header = not path.exists()

    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if need_header:
            w.writerow(["question", "answer", "references", "correct", "complete"])
        w.writerow([question, answer, "; ".join(references), correct, complete])
