"""`clip check --round <r>`: validate motions, freeze them, verify the round (clips design §3.2).

The agent runs it after writing motions.jsonl. When every motion passes, it freezes each into
spec.json with the fixed clip suffix and opens provenance.json with attempt 1. It also verifies
what the round holds:

- each clip's source still: still ready, the same attempt, its render's bytes unchanged;
- the copied facts, and every frozen motion against the rules;
- every recorded clip and strip against its sha256;
- the triage chain.

The owner runs the same command on the host to confirm a round.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence

from synthbench.clips.rules import clip_problems, motion_sha256
from synthbench.clips.settings import CLIP_SUFFIX
from synthbench.commands.clip_rows import motion_rows, triage_rows
from synthbench.commands.common import (
    EXIT_OK,
    AskOwner,
    CorpusError,
    Parser,
    RequestError,
    append_clip_index,
    now_iso,
    open_round,
    read,
    read_clip_index,
    read_index,
    replace_json,
    round_name,
    taxonomy,
    write_new,
)
from synthbench.contract.clip import (
    ClipAttempt,
    ClipIndexRow,
    ClipProvenance,
    ClipSpec,
    RoundRecord,
    clip_name,
    source_facts,
    strip_name,
)
from synthbench.contract.corpus import IndexRow
from synthbench.contract.provenance import Provenance, attempt_seed
from synthbench.contract.spec import Spec
from synthbench.contract.store import CorpusStore, sha256_file
from synthbench.taxonomy.model import Taxonomy

_OUTPUT_DIRS = ("clips", "strips")


def add_parser(actions: argparse._SubParsersAction[Parser]) -> None:
    parser = actions.add_parser(
        "check",
        help="validate motions.jsonl, freeze passing motions, and verify the round's files",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--round", dest="round_name", type=round_name, required=True, help="round name"
    )
    parser.set_defaults(run=run)


def run(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    tax = taxonomy()
    store, record = open_round(tax, env, args.round_name)
    specs, ask = _clip_specs(store, record)
    index = read_index(store)
    rows = motion_rows(store, record)
    fix: list[str] = []
    pending: dict[str, str] = {}
    for spec in specs:
        ask.extend(_source_problems(store, spec, index))
        row = rows.get(spec.event_id)
        if spec.frozen:
            ask.extend(_frozen_problems(spec, tax))
            if row is not None and row != spec.prompt:
                fix.append(
                    f"{spec.event_id}: the frozen motion never changes; restore it in "
                    "motions.jsonl (a different motion is a new clip event)"
                )
        elif row is None:
            fix.append(f"{spec.event_id}: no row in motions.jsonl")
        else:
            fix.extend(f"{spec.event_id}: {problem}" for problem in clip_problems(spec, row, tax))
            pending[spec.event_id] = row
    provs = _provenances(store, specs)
    output_problems, verified = _output_problems(store, specs, provs)
    ask.extend(output_problems)
    ask.extend(_triage_problems(store, record, provs))
    if ask:
        raise AskOwner(
            f"round {record.name} is not in the state clip check expects:\n  "
            + "\n  ".join(ask)
            + "\n"
        )
    if fix:
        raise RequestError(
            f"{len(fix)} problem(s) in round {record.name}; fix motions.jsonl and run clip "
            "check again:\n  " + "\n  ".join(fix)
        )
    clip_index = read_clip_index(store)
    frozen_now = _freeze(store, record, specs, pending, clip_index)
    sys.stdout.write(
        f"clip check {record.name}: {len(specs)} clips, {frozen_now} frozen now, every motion "
        f"frozen; {verified} recorded output file(s) verified\n"
    )
    failed = {e for e, row in clip_index.items() if row.status == "failed"}
    if _awaiting_render(specs, provs, pending, failed):
        sys.stdout.write(f"Next: clip render --round {record.name}\n")
    return EXIT_OK


def _awaiting_render(
    specs: Sequence[ClipSpec],
    provs: Mapping[str, ClipProvenance],
    pending: Mapping[str, str],
    failed: set[str],
) -> bool:
    """Some frozen clip's current attempt has no clip yet (_freeze just opened attempt 1 for
    the clips frozen now, and for any frozen clip that had no provenance)."""
    for spec in specs:
        if spec.event_id in failed or not (spec.frozen or spec.event_id in pending):
            continue
        prov = provs.get(spec.event_id)
        if prov is None or prov.attempts[-1].clip is None:
            return True
    return False


def _clip_specs(store: CorpusStore, record: RoundRecord) -> tuple[list[ClipSpec], list[str]]:
    """The round's clip specs, and any that no longer name the source round.json lists."""
    missing = [e for e in record.event_ids if not store.spec_file(e).exists()]
    if missing:
        raise RequestError(
            f"{len(missing)} spec(s) of round {record.name} were never written; run "
            f"`python -m synthbench clip sample --round {record.name} --n {record.n} "
            f"--seed {record.seed}` to finish the round"
        )
    specs: list[ClipSpec] = []
    problems: list[str] = []
    for event_id, source_id in zip(record.event_ids, record.source_event_ids, strict=True):
        spec = read(store, store.spec_file(event_id), ClipSpec)
        if spec.source.event_id != source_id:
            problems.append(f"{event_id}: its source is not {source_id}, as round.json says")
        specs.append(spec)
    return specs, problems


def _source_problems(
    store: CorpusStore, spec: ClipSpec, index: Mapping[str, IndexRow]
) -> list[str]:
    """The source still is ready, at the pinned attempt, with the pinned render's bytes."""
    source = spec.source
    where = f"{spec.event_id} (source {source.event_id})"
    row = index.get(source.event_id)
    if row is None or row.status != "ready":
        return [f"{where}: the source still is no longer ready"]
    problems: list[str] = []
    still = read(store, store.spec_file(source.event_id), Spec)
    if source_facts(still) != spec.facts():
        problems.append(f"{where}: the clip's facts differ from the source still's")
    attempt = read(store, store.provenance_file(source.event_id), Provenance).attempts[-1]
    if attempt.k != source.k or attempt.render is None:
        return [*problems, f"{where}: the source's ready attempt is no longer {source.k}"]
    if attempt.render.sha256 != source.render_sha256:
        return [*problems, f"{where}: the source attempt's render is not the pinned render"]
    file = store.event_dir(source.event_id) / attempt.render.path
    try:
        digest = sha256_file(file)
    except OSError as error:
        raise CorpusError("read", file, error) from error
    if digest != source.render_sha256:
        problems.append(f"{where}: the source render {attempt.render.path} was modified")
    return problems


def _frozen_problems(spec: ClipSpec, tax: Taxonomy) -> list[str]:
    assert spec.prompt is not None
    found = [
        f"{spec.event_id}: the frozen motion now breaks {problem}"
        for problem in clip_problems(spec, spec.prompt, tax)
    ]
    if spec.clip_suffix != CLIP_SUFFIX:
        found.append(f"{spec.event_id}: clip_suffix differs from the committed suffix")
    return found


def _provenances(store: CorpusStore, specs: Sequence[ClipSpec]) -> dict[str, ClipProvenance]:
    return {
        spec.event_id: read(store, store.provenance_file(spec.event_id), ClipProvenance)
        for spec in specs
        if spec.frozen and store.provenance_file(spec.event_id).exists()
    }


def _output_problems(
    store: CorpusStore, specs: Sequence[ClipSpec], provs: Mapping[str, ClipProvenance]
) -> tuple[list[str], int]:
    """Every recorded clip and strip against its sha256, and no file provenance does not name."""
    problems: list[str] = []
    verified = 0
    for spec in specs:
        prov = provs.get(spec.event_id)
        if prov is None:
            continue
        event_dir = store.event_dir(spec.event_id)
        want = motion_sha256(spec)
        expected: set[str] = set()
        for attempt in prov.attempts:
            where = f"{spec.event_id} attempt {attempt.k}"
            if attempt.prompt_sha256 != want:
                problems.append(f"{where}: prompt_sha256 is not the frozen motion's")
            if attempt.seed != attempt_seed(spec.event_id, attempt.k):
                problems.append(f"{where}: seed {attempt.seed} is not the attempt's seed")
            expected |= {clip_name(attempt.k, attempt.seed), strip_name(attempt.k, attempt.seed)}
            for output in (attempt.clip, attempt.strip):
                if output is None:
                    continue
                file = event_dir / output.path
                if not file.is_file():
                    problems.append(f"{spec.event_id}: {output.path} is missing")
                    continue
                try:
                    digest = sha256_file(file)
                except OSError as error:
                    raise CorpusError("read", file, error) from error
                if digest != output.sha256:
                    problems.append(f"{spec.event_id}: {output.path} was modified")
                else:
                    verified += 1
        for sub in _OUTPUT_DIRS:
            folder = event_dir / sub
            if not folder.is_dir():
                continue
            for file in sorted(folder.iterdir()):
                name = f"{sub}/{file.name}"
                if name not in expected and not _store_temp(file.name):
                    problems.append(f"{spec.event_id}: unexpected file {name}")
    return problems, verified


def _triage_problems(
    store: CorpusStore, record: RoundRecord, provs: Mapping[str, ClipProvenance]
) -> list[str]:
    """Attempt k+1 exists only after a reroll verdict on k; recorded verdicts match their rows."""
    rows = triage_rows(store, record)
    problems: list[str] = []
    for event_id, prov in provs.items():
        problems.extend(
            f"{event_id}: attempt {attempt.k + 1} exists, but attempt {attempt.k} has no reroll "
            "verdict"
            for attempt in prov.attempts[:-1]
            if attempt.triage is None or attempt.triage.verdict != "reroll"
        )
        for attempt in prov.attempts:
            if attempt.triage is None:
                continue
            row = rows.get((event_id, attempt.k))
            if row is None:
                problems.append(
                    f"{event_id}: attempt {attempt.k}'s recorded verdict has no row in triage.jsonl"
                )
            elif row.triage() != attempt.triage:
                problems.append(
                    f"{event_id}: attempt {attempt.k}'s recorded verdict differs from its "
                    "triage.jsonl row"
                )
    return problems


def _store_temp(name: str) -> bool:
    """CorpusStore's temporary files (`.<name>.<random>.tmp`), left only by a crash."""
    return name.startswith(".") and name.endswith(".tmp")


def _freeze(
    store: CorpusStore,
    record: RoundRecord,
    specs: Sequence[ClipSpec],
    pending: Mapping[str, str],
    clip_index: Mapping[str, ClipIndexRow],
) -> int:
    """Freeze each pending motion, then open provenance for every frozen clip that lacks it."""
    rows: list[ClipIndexRow] = []
    frozen_now = 0
    for spec in specs:
        current = spec
        if spec.event_id in pending:
            current = spec.with_prompt(pending[spec.event_id], CLIP_SUFFIX)
            replace_json(store, store.spec_file(spec.event_id), current)
            frozen_now += 1
        if not current.frozen:
            continue
        provenance = store.provenance_file(spec.event_id)
        if not provenance.exists():  # spec.json is written first, so a crash leaves only this
            first = ClipAttempt(
                k=1,
                seed=attempt_seed(spec.event_id, 1),
                prompt_sha256=motion_sha256(current),
            )
            write_new(store, provenance, ClipProvenance(event_id=spec.event_id, attempts=(first,)))
        latest = clip_index.get(spec.event_id)
        if latest is None or latest.status == "sampled":
            rows.append(
                ClipIndexRow(
                    event_id=spec.event_id,
                    round=record.name,
                    source=spec.source.event_id,
                    scenario=spec.cell.scenario,
                    label=spec.label,
                    status="prompted",
                    time=now_iso(),
                )
            )
    append_clip_index(store, rows)
    return frozen_now
