"""The agent's two files in a clip round (clips design §3): motions.jsonl and triage.jsonl.

A malformed row, a row for a clip outside the round, or a duplicate exits 1: the agent fixes
its file and runs the command again.
"""

from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from pydantic import ValidationError

from synthbench.commands.common import RequestError
from synthbench.contract.clip import ClipTriageRow, RoundRecord
from synthbench.contract.corpus import PromptRow
from synthbench.contract.store import CorpusStore

R = TypeVar("R", PromptRow, ClipTriageRow)


def _read(path: Path, model: type[R], record: RoundRecord, what: str) -> list[tuple[int, R]]:
    """(line number, row) for every row in path; none when the file does not exist."""
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise RequestError(f"cannot read {path} ({type(error).__name__}); rewrite it") from error
    rows: list[tuple[int, R]] = []
    problems: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = model.model_validate_json(line)
        except ValidationError as error:
            problems.append(f"line {number}: not a {what} row ({error.errors()[0]['msg']})")
            continue
        if row.event_id not in record.event_ids:
            problems.append(f"line {number}: {row.event_id} is not in round {record.name}")
            continue
        rows.append((number, row))
    if problems:
        raise RequestError(f"{path}:\n  " + "\n  ".join(problems))
    return rows


def motion_rows(store: CorpusStore, record: RoundRecord) -> dict[str, str]:
    """The round's motions.jsonl by clip id, each motion stripped."""
    path = store.round_dir(record.name) / "motions.jsonl"
    rows: dict[str, str] = {}
    problems: list[str] = []
    for number, row in _read(path, PromptRow, record, "motion"):
        if row.event_id in rows:
            problems.append(f"line {number}: a second row for {row.event_id}")
        else:
            rows[row.event_id] = row.prompt.strip()
    if problems:
        raise RequestError(f"{path}:\n  " + "\n  ".join(problems))
    return rows


def triage_rows(store: CorpusStore, record: RoundRecord) -> dict[tuple[str, int], ClipTriageRow]:
    """The round's triage.jsonl by (clip id, attempt)."""
    path = store.round_dir(record.name) / "triage.jsonl"
    rows: dict[tuple[str, int], ClipTriageRow] = {}
    problems: list[str] = []
    for number, row in _read(path, ClipTriageRow, record, "triage"):
        key = (row.event_id, row.k)
        if key in rows:
            problems.append(f"line {number}: a second row for {row.event_id} attempt {row.k}")
        else:
            rows[key] = row
    if problems:
        raise RequestError(f"{path}:\n  " + "\n  ".join(problems))
    return rows
