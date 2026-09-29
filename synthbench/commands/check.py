"""`check --batch <b>`: validate prompts, freeze them, verify the batch (design §3 step 3).

The agent runs it after writing prompts.jsonl. When every prompt passes, it freezes each one
into spec.json with the fixed camera suffix and opens provenance.json with attempt 1. It also
verifies what the batch already holds: the facts against the sampler, every frozen prompt
against the rules, every recorded image against its sha256, and the triage limits against
provenance and triage.jsonl. The owner runs the same command on the host to confirm a batch
before relying on it.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence

from pydantic import ValidationError

from synthbench.commands.common import (
    EXIT_OK,
    AskOwner,
    CorpusError,
    Parser,
    RequestError,
    append_index,
    batch_name,
    now_iso,
    open_batch,
    read,
    read_index,
    replace_json,
    taxonomy,
    write_new,
)
from synthbench.commands.triage import is_reroll, reroll_allowance, rerolls_scheduled, triage_rows
from synthbench.contract.corpus import BatchRecord, IndexRow, PromptRow
from synthbench.contract.provenance import (
    Attempt,
    Provenance,
    attempt_seed,
    render_name,
    still_name,
)
from synthbench.contract.spec import Spec
from synthbench.contract.store import CorpusStore, sha256_file
from synthbench.prompt import rules
from synthbench.taxonomy.model import Taxonomy
from synthbench.taxonomy.sampler import sample_specs

_OUTPUT_DIRS = ("renders", "stills")


def add_parser(commands: argparse._SubParsersAction[Parser]) -> None:
    parser = commands.add_parser(
        "check",
        help="validate prompts.jsonl, freeze passing prompts, and verify the batch's files",
        allow_abbrev=False,
    )
    parser.add_argument("--batch", type=batch_name, required=True, help="batch name")
    parser.set_defaults(run=run)


def run(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    tax = taxonomy()
    store, record = open_batch(tax, env, args.batch)
    specs = _sampled_specs(tax, store, record)
    rows = _prompt_rows(store, record)
    ask: list[str] = []
    fix: list[str] = []
    pending: dict[str, str] = {}
    for spec in specs:
        row = rows.get(spec.event_id)
        if spec.frozen:
            ask.extend(_frozen_problems(spec, tax))
            if row is not None and row != spec.prompt:
                fix.append(
                    f"{spec.event_id}: the frozen prompt never changes; restore it in "
                    "prompts.jsonl (a different prompt is a new event)"
                )
        elif row is None:
            fix.append(f"{spec.event_id}: no row in prompts.jsonl")
        else:
            fix.extend(f"{spec.event_id}: {problem}" for problem in rules.problems(spec, row, tax))
            pending[spec.event_id] = row
    provs = _provenances(store, specs)
    output_problems, verified = _output_problems(store, specs, provs)
    ask.extend(output_problems)
    ask.extend(_triage_problems(store, record, provs))
    if ask:
        raise AskOwner(
            f"batch {record.name} is not in the state check expects:\n  " + "\n  ".join(ask) + "\n"
        )
    if fix:
        raise RequestError(
            f"{len(fix)} problem(s) in batch {record.name}; fix prompts.jsonl and run check "
            "again:\n  " + "\n  ".join(fix)
        )
    index = read_index(store)
    frozen_now = _freeze(store, record, specs, pending, index)
    sys.stdout.write(
        f"check {record.name}: {len(specs)} events, {frozen_now} frozen now, every prompt "
        f"frozen; {verified} recorded output file(s) verified\n"
    )
    if _awaiting_render(specs, provs, index):
        sys.stdout.write(f"Next: render --batch {record.name}\n")
    return EXIT_OK


def _sampled_specs(tax: Taxonomy, store: CorpusStore, record: BatchRecord) -> list[Spec]:
    """The batch's specs, each compared with what the sampler makes from batch.json."""
    expected = sample_specs(
        tax,
        version=store.version,
        batch=record.name,
        n=record.n,
        seed=record.seed,
        prior=record.prior_counts,
        only=record.only or None,
    )
    if tuple(spec.event_id for spec in expected) != record.event_ids:
        raise AskOwner(f"batch.json of {record.name} lists events the sampler does not make.")
    if missing := [s.event_id for s in expected if not store.spec_file(s.event_id).exists()]:
        only = f" --only {','.join(record.only)}" if record.only else ""
        raise RequestError(
            f"{len(missing)} spec(s) of batch {record.name} were never written; run "
            f"`python -m synthbench sample --batch {record.name} --n {record.n} "
            f"--seed {record.seed}{only}` to finish the batch"
        )
    specs: list[Spec] = []
    drift: list[str] = []
    for want in expected:
        have = read(store, store.spec_file(want.event_id), Spec)
        if have.facts() != want.facts():
            drift.append(f"{want.event_id}: spec.json facts differ from the sampler's")
        specs.append(have)
    if drift:
        raise AskOwner(f"batch {record.name} was changed by hand:\n  " + "\n  ".join(drift) + "\n")
    return specs


def _prompt_rows(store: CorpusStore, record: BatchRecord) -> dict[str, str]:
    path = store.batch_dir(record.name) / "prompts.jsonl"
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise RequestError(f"cannot read {path} ({type(error).__name__}); rewrite it") from error
    rows: dict[str, str] = {}
    problems: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = PromptRow.model_validate_json(line)
        except ValidationError as error:
            problems.append(f"line {number}: not a prompt row ({error.errors()[0]['msg']})")
            continue
        if row.event_id not in record.event_ids:
            problems.append(f"line {number}: {row.event_id} is not in batch {record.name}")
        elif row.event_id in rows:
            problems.append(f"line {number}: a second row for {row.event_id}")
        else:
            rows[row.event_id] = row.prompt.strip()
    if problems:
        raise RequestError(f"{path}:\n  " + "\n  ".join(problems))
    return rows


def _frozen_problems(spec: Spec, tax: Taxonomy) -> list[str]:
    assert spec.prompt is not None
    found = [
        f"{spec.event_id}: the frozen prompt now breaks {problem}"
        for problem in rules.problems(spec, spec.prompt, tax)
    ]
    if spec.camera_suffix != rules.CAMERA_SUFFIX:
        found.append(f"{spec.event_id}: camera_suffix differs from the committed suffix")
    return found


def _provenances(store: CorpusStore, specs: Sequence[Spec]) -> dict[str, Provenance]:
    """provenance.json of every frozen event that has one, by event id."""
    return {
        spec.event_id: read(store, store.provenance_file(spec.event_id), Provenance)
        for spec in specs
        if spec.frozen and store.provenance_file(spec.event_id).exists()
    }


def _output_problems(
    store: CorpusStore, specs: Sequence[Spec], provs: Mapping[str, Provenance]
) -> tuple[list[str], int]:
    """Every recorded image against its sha256, and no image provenance does not name (§2)."""
    problems: list[str] = []
    verified = 0
    for spec in specs:
        prov = provs.get(spec.event_id)
        if prov is None:
            continue
        event_dir = store.event_dir(spec.event_id)
        want = rules.prompt_sha256(spec)
        expected: set[str] = set()
        for attempt in prov.attempts:
            where = f"{spec.event_id} attempt {attempt.k}"
            if attempt.prompt_sha256 != want:
                problems.append(f"{where}: prompt_sha256 is not the frozen prompt's")
            if attempt.seed != attempt_seed(spec.event_id, attempt.k):
                problems.append(f"{where}: seed {attempt.seed} is not the attempt's seed")
            expected |= {render_name(attempt.k, attempt.seed), still_name(attempt.k, attempt.seed)}
            for output in (attempt.render, attempt.still):
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
    store: CorpusStore, record: BatchRecord, provs: Mapping[str, Provenance]
) -> list[str]:
    """The triage limits (design §4, P3-R11), which an edited clone could have got past (R4)."""
    rows = triage_rows(store, record)
    problems: list[str] = []
    total = 0
    rerolled: list[str] = []
    for event_id, prov in provs.items():
        problems.extend(
            f"{event_id}: attempt {attempt.k + 1} exists, but attempt {attempt.k} has no reroll "
            "verdict"
            for attempt in prov.attempts[:-1]
            if not is_reroll(attempt)
        )
        if scheduled := rerolls_scheduled(prov):
            total += scheduled
            rerolled.append(event_id)
        if scheduled > 1:
            problems.append(
                f"{event_id}: {scheduled} triage rerolls scheduled; one is allowed per event"
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
    allowance = reroll_allowance(record.n)
    if total > allowance:
        problems.append(
            f"batch {record.name} scheduled {total} triage reroll(s), {allowance} allowed: "
            + ", ".join(rerolled)
        )
    return problems


def _awaiting_render(
    specs: Sequence[Spec], provs: Mapping[str, Provenance], index: Mapping[str, IndexRow]
) -> bool:
    """Some event's current attempt awaits a render, once _freeze has opened every attempt 1."""
    for spec in specs:
        prov = provs.get(spec.event_id)
        if prov is None:  # _freeze opened its attempt 1 just now
            return True
        row = index.get(spec.event_id)
        if prov.attempts[-1].render is None and (row is None or row.status != "failed"):
            return True
    return False


def _store_temp(name: str) -> bool:
    """CorpusStore's temporary files (`.<name>.<random>.tmp`), left only by a crash."""
    return name.startswith(".") and name.endswith(".tmp")


def _freeze(
    store: CorpusStore,
    record: BatchRecord,
    specs: Sequence[Spec],
    pending: Mapping[str, str],
    index: Mapping[str, IndexRow],
) -> int:
    """Freeze each pending prompt, then open provenance for every frozen spec that lacks it."""
    rows: list[IndexRow] = []
    frozen_now = 0
    for spec in specs:
        current = spec
        if spec.event_id in pending:
            current = spec.with_prompt(pending[spec.event_id], rules.CAMERA_SUFFIX)
            replace_json(store, store.spec_file(spec.event_id), current)
            frozen_now += 1
        if not current.frozen:
            continue
        provenance = store.provenance_file(spec.event_id)
        if not provenance.exists():  # spec.json is written first, so a crash leaves only this
            first = Attempt(
                k=1,
                seed=attempt_seed(spec.event_id, 1),
                prompt_sha256=rules.prompt_sha256(current),
            )
            write_new(store, provenance, Provenance(event_id=spec.event_id, attempts=(first,)))
        latest = index.get(spec.event_id)
        if latest is None or latest.status == "sampled":
            rows.append(
                IndexRow(
                    event_id=spec.event_id,
                    batch=record.name,
                    scenario=spec.cell.scenario,
                    label=spec.label,
                    status="prompted",
                    time=now_iso(),
                )
            )
    append_index(store, rows)
    return frozen_now
