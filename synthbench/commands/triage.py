"""`triage --batch <b>`: record the agent's verdicts and schedule rerolls (design §3 step 7, §4).

The agent may reroll only for a listed mechanical reason, once per event. A second triage
failure fails the event. A batch may schedule at most floor(n / 10) triage rerolls; a reroll
verdict past that fails its event and stops the run (plan ruling P3-R11). Nothing is deleted.
"""

from __future__ import annotations

import argparse
import math
import sys
from collections import Counter
from collections.abc import Mapping

from pydantic import ValidationError

from synthbench.commands.common import (
    EXIT_OK,
    AskOwner,
    Parser,
    RequestError,
    append_index,
    batch_name,
    now_iso,
    open_batch,
    read,
    replace_json,
    taxonomy,
)
from synthbench.contract.corpus import BatchRecord, EventStatus, IndexRow, TriageRow
from synthbench.contract.provenance import MAX_ATTEMPTS, Attempt, Provenance, attempt_seed
from synthbench.contract.spec import Spec
from synthbench.contract.store import CorpusStore

REROLL_SHARE = 0.10  # design §4: triage rerolls may not exceed 10% of a batch's events

Rows = dict[tuple[str, int], TriageRow]


def reroll_allowance(n: int) -> int:
    """Triage rerolls a batch of n events may schedule over its lifetime."""
    return math.floor(n * REROLL_SHARE + 1e-9)


def add_parser(commands: argparse._SubParsersAction[Parser]) -> None:
    parser = commands.add_parser(
        "triage",
        help="record triage.jsonl verdicts; schedule the allowed rerolls",
        allow_abbrev=False,
    )
    parser.add_argument("--batch", type=batch_name, required=True, help="batch name")
    parser.set_defaults(run=run)


def run(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    tax = taxonomy()
    store, record = open_batch(tax, env, args.batch)
    specs = {e: read(store, store.spec_file(e), Spec) for e in record.event_ids}
    provs = {
        e: read(store, store.provenance_file(e), Provenance)
        for e in record.event_ids
        if store.provenance_file(e).exists()
    }
    rows = _rows(store, record)
    _validate(rows, provs)
    allowance = reroll_allowance(record.n)
    scheduled = sum(1 for prov in provs.values() if _rerolled_before(prov))
    counts: Counter[str] = Counter()
    over_cap: list[str] = []
    index_rows: list[IndexRow] = []
    for event_id in record.event_ids:
        prov = provs.get(event_id)
        if prov is None:
            continue
        attempt = prov.attempts[-1]
        row = rows.get((event_id, attempt.k))
        if row is None or attempt.triage is not None:
            continue
        verdict = row.triage()
        attempts = [*prov.attempts[:-1], attempt.updated(triage=verdict)]
        status: EventStatus
        if verdict.verdict == "ok":
            status = "ready"
        elif _rerolled_before(prov) or len(prov.attempts) >= MAX_ATTEMPTS:
            status = "failed"
        elif scheduled >= allowance:
            status = "failed"
            over_cap.append(event_id)
        else:
            k = attempt.k + 1
            attempts.append(
                Attempt(k=k, seed=attempt_seed(event_id, k), prompt_sha256=attempt.prompt_sha256)
            )
            scheduled += 1
            status = "rerolled"
        counts[status] += 1
        provs[event_id] = prov.updated(attempts=tuple(attempts))
        replace_json(store, store.provenance_file(event_id), provs[event_id])
        spec = specs[event_id]
        index_rows.append(
            IndexRow(
                event_id=event_id,
                batch=record.name,
                scenario=spec.cell.scenario,
                label=spec.label,
                status=status,
                time=now_iso(),
            )
        )
    append_index(store, index_rows)
    awaiting = sum(
        1
        for p in provs.values()
        if p.attempts[-1].still is not None and p.attempts[-1].triage is None
    )
    sys.stdout.write(
        f"triage {record.name}: {counts['ready']} ready, {counts['rerolled']} reroll(s) scheduled, "
        f"{counts['failed']} failed now; {awaiting} still(s) await a verdict; triage rerolls used "
        f"{scheduled} of {allowance}\n"
    )
    if counts["rerolled"]:
        sys.stdout.write("Next: render, camera and triage again for the rerolls (attempt 2).\n")
    if over_cap:
        raise AskOwner(
            f"triage rerolls in batch {record.name} would exceed 10% of its {record.n} events "
            f"({allowance} allowed, all used). These events are now failed, their verdicts "
            f"recorded: {', '.join(over_cap)}."
        )
    return EXIT_OK


def _rerolled_before(prov: Provenance) -> bool:
    """Triage already rerolled this event: an earlier attempt has a reroll verdict."""
    return any(a.triage is not None and a.triage.verdict == "reroll" for a in prov.attempts[:-1])


def _rows(store: CorpusStore, record: BatchRecord) -> Rows:
    path = store.batch_dir(record.name) / "triage.jsonl"
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise RequestError(f"cannot read {path} ({type(error).__name__}); rewrite it") from error
    rows: Rows = {}
    problems: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = TriageRow.model_validate_json(line)
        except ValidationError as error:
            problems.append(f"line {number}: not a triage row ({error.errors()[0]['msg']})")
            continue
        key = (row.event_id, row.k)
        if row.event_id not in record.event_ids:
            problems.append(f"line {number}: {row.event_id} is not in batch {record.name}")
        elif key in rows:
            problems.append(f"line {number}: a second row for {row.event_id} attempt {row.k}")
        else:
            rows[key] = row
    if problems:
        raise RequestError(f"{path}:\n  " + "\n  ".join(problems))
    return rows


def _validate(rows: Rows, provs: Mapping[str, Provenance]) -> None:
    problems: list[str] = []
    for (event_id, k), row in sorted(rows.items()):
        prov = provs.get(event_id)
        if prov is None or k > len(prov.attempts):
            problems.append(f"{event_id}: attempt {k} does not exist")
            continue
        attempt = prov.attempts[k - 1]
        if attempt.triage is not None:
            if attempt.triage != row.triage():
                problems.append(
                    f"{event_id}: attempt {k} was recorded as {attempt.triage.verdict}; a verdict "
                    "is final"
                )
        elif attempt.still is None:
            problems.append(
                f"{event_id}: attempt {k} has no still yet; run render and camera, then look at it"
            )
    if problems:
        raise RequestError(
            "triage.jsonl names verdicts triage cannot record; fix them and run triage again:\n  "
            + "\n  ".join(problems)
        )
