"""`clip triage --round <r>`: record the agent's clip verdicts, schedule rerolls (§3.3).

The agent may reroll a clip only for a listed mechanical reason. A clip may use its 3 seeds
(ruling H3-R11): a reroll verdict on attempt 3 fails it. Verdicts are final; nothing is
deleted. There is no per-round reroll cap.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Mapping

from synthbench.commands.clip_rows import triage_rows
from synthbench.commands.common import (
    EXIT_OK,
    Parser,
    RequestError,
    append_clip_index,
    now_iso,
    open_round,
    read,
    replace_json,
    round_name,
    taxonomy,
)
from synthbench.contract.clip import (
    ClipAttempt,
    ClipIndexRow,
    ClipProvenance,
    ClipSpec,
    ClipTriageRow,
)
from synthbench.contract.corpus import EventStatus
from synthbench.contract.provenance import MAX_ATTEMPTS, attempt_seed


def add_parser(actions: argparse._SubParsersAction[Parser]) -> None:
    parser = actions.add_parser(
        "triage",
        help="record triage.jsonl verdicts on the clips' strips; schedule rerolls",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--round", dest="round_name", type=round_name, required=True, help="round name"
    )
    parser.set_defaults(run=run)


def run(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    tax = taxonomy()
    store, record = open_round(tax, env, args.round_name)
    specs = {e: read(store, store.spec_file(e), ClipSpec) for e in record.event_ids}
    provs = {
        e: read(store, store.provenance_file(e), ClipProvenance)
        for e in record.event_ids
        if store.provenance_file(e).exists()
    }
    rows = triage_rows(store, record)
    _validate(rows, provs)
    counts: Counter[str] = Counter()
    index_rows: list[ClipIndexRow] = []
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
        elif len(prov.attempts) >= MAX_ATTEMPTS:
            status = "failed"
        else:
            k = attempt.k + 1
            attempts.append(
                ClipAttempt(
                    k=k, seed=attempt_seed(event_id, k), prompt_sha256=attempt.prompt_sha256
                )
            )
            status = "rerolled"
        counts[status] += 1
        provs[event_id] = prov.updated(attempts=tuple(attempts))
        replace_json(store, store.provenance_file(event_id), provs[event_id])
        spec = specs[event_id]
        index_rows.append(
            ClipIndexRow(
                event_id=event_id,
                round=record.name,
                source=spec.source.event_id,
                scenario=spec.cell.scenario,
                label=spec.label,
                status=status,
                time=now_iso(),
            )
        )
    append_clip_index(store, index_rows)
    awaiting = sum(
        1
        for p in provs.values()
        if p.attempts[-1].clip is not None and p.attempts[-1].triage is None
    )
    sys.stdout.write(
        f"clip triage {record.name}: {counts['ready']} ready, {counts['rerolled']} reroll(s) "
        f"scheduled, {counts['failed']} failed now; {awaiting} clip(s) await a verdict\n"
    )
    if counts["rerolled"]:
        sys.stdout.write("Next: clip render, then clip triage again for the rerolls.\n")
    elif not awaiting:
        sys.stdout.write(f"Next: clip report --round {record.name}\n")
    return EXIT_OK


def _validate(
    rows: Mapping[tuple[str, int], ClipTriageRow], provs: Mapping[str, ClipProvenance]
) -> None:
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
                    f"{event_id}: attempt {k} was recorded as {attempt.triage.verdict}; a "
                    "verdict is final"
                )
        elif attempt.clip is None:
            problems.append(
                f"{event_id}: attempt {k} has no clip yet; run clip render, then look at its strip"
            )
    if problems:
        raise RequestError(
            "triage.jsonl names verdicts clip triage cannot record; fix them and run it "
            "again:\n  " + "\n  ".join(problems)
        )
