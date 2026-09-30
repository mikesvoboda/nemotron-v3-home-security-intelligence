"""`clip sample --round <r> --n <n>`: draw ready stills into a new clip round (clips design §3.1).

The first round for a set of clip settings is the pilot: at most 20 clips, and no further round
until the owner's audit has rated it (status/clip-gate.json). The draw is seeded by the round
name, as a batch's is by its name. Running it again for an existing round finishes writing that
round and changes nothing else.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping
from pathlib import Path

from pydantic import ValidationError

from synthbench.clips import settings as clip_settings
from synthbench.clips.gate import PILOT_MAX_N, GateRefused, gate_file, read_gate, round_kind
from synthbench.clips.sample import Candidate, draw
from synthbench.commands.common import (
    EXIT_OK,
    AskOwner,
    Parser,
    RequestError,
    append_clip_index,
    check_manifest,
    now_iso,
    read,
    read_clip_index,
    read_index,
    round_name,
    taxonomy,
    write_new,
)
from synthbench.contract.clip import ClipIndexRow, ClipSource, ClipSpec, RoundRecord, clip_id
from synthbench.contract.provenance import Provenance
from synthbench.contract.spec import Spec
from synthbench.contract.store import CorpusStore
from synthbench.taxonomy.sampler import MAX_BATCH, default_seed


def _size(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"n must be an integer 1..{MAX_BATCH}: {text!r}") from None
    if not 1 <= value <= MAX_BATCH:
        raise argparse.ArgumentTypeError(f"n must be 1..{MAX_BATCH}, got {value}")
    return value


def _seed(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"seed must be an integer >= 0: {text!r}") from None
    if value < 0:
        raise argparse.ArgumentTypeError(f"seed must be an integer >= 0, got {value}")
    return value


def add_parser(actions: argparse._SubParsersAction[Parser]) -> None:
    parser = actions.add_parser(
        "sample",
        help="draw ready stills that have no clip yet into a new clip round (a pilot first)",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--round",
        dest="round_name",
        type=round_name,
        required=True,
        help="new round name: lowercase letters, digits and hyphens",
    )
    parser.add_argument(
        "--n",
        type=_size,
        required=True,
        help=f"clips in the round, 1..{MAX_BATCH} (a pilot: at most {PILOT_MAX_N})",
    )
    parser.add_argument(
        "--seed", type=_seed, default=None, help="draw seed (default: derived from the round name)"
    )
    parser.set_defaults(run=run)


def run(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    tax = taxonomy()
    store = CorpusStore.from_env(tax.version, env)
    if not store.manifest_file.exists():
        raise RequestError(f"corpus version {tax.version} has no stills yet")
    check_manifest(store)
    seed: int = args.seed if args.seed is not None else default_seed(args.round_name)
    record = _round(store, args.round_name, args.n, seed, gate_file(env))
    written = _write_specs(store, record)
    groups = ", ".join(
        f"{group} {sum(lights.values())}" for group, lights in sorted(record.allocation.items())
    )
    kind = "the pilot" if record.pilot else "a volume round"
    first, last = record.event_ids[0], record.event_ids[-1]
    sys.stdout.write(
        f"clip round {record.name} in corpus version {store.version}: {record.n} clips "
        f"({written} written now), {kind}\n"
        f"  groups: {groups}\n"
        f"  specs: {store.event_dir(first).parent}/{first} .. {last}\n"
        f"Next: write {store.round_dir(record.name) / 'motions.jsonl'}, then "
        f"clip check --round {record.name}\n"
    )
    return EXIT_OK


def _round(store: CorpusStore, name: str, n: int, seed: int, gate_path: Path) -> RoundRecord:
    """The round's record: read if the round exists, else drawn now and written once."""
    path = store.round_file(name)
    if path.exists():
        record = read(store, path, RoundRecord)
        if (record.seed, record.n) != (seed, n):
            raise RequestError(
                f"round {name} already exists with seed={record.seed}, n={record.n}; "
                "choose a new round name"
            )
        return record
    settings = clip_settings.current()
    try:
        kind = round_kind(settings, read_gate(gate_path), _rounds(store))
    except (OSError, UnicodeDecodeError, ValidationError) as error:
        raise AskOwner(f"cannot read {gate_path} ({type(error).__name__}).") from error
    except GateRefused as error:
        raise AskOwner(str(error)) from error
    if kind == "pilot" and n > PILOT_MAX_N:
        raise RequestError(
            f"no pilot has passed for these clip settings, so round {name} is the pilot: "
            f"--n at most {PILOT_MAX_N}"
        )
    pool = _pool(store)
    if len(pool) < n:
        raise RequestError(
            f"{len(pool)} ready still(s) have no clip yet; ask for --n {len(pool)} or fewer"
            if pool
            else "every ready still already has a clip"
        )
    chosen = draw(pool, n, seed)
    allocation: dict[str, dict[str, int]] = {}
    for candidate in chosen:
        lights = allocation.setdefault(candidate.group, {})
        lights[candidate.lighting] = lights.get(candidate.lighting, 0) + 1
    record = RoundRecord(
        name=name,
        version=store.version,
        seed=seed,
        n=n,
        pilot=kind == "pilot",
        settings=settings,
        allocation=allocation,
        event_ids=tuple(clip_id(name, i) for i in range(n)),
        source_event_ids=tuple(candidate.event_id for candidate in chosen),
        created=now_iso(),
    )
    write_new(store, path, record)
    return record


def _rounds(store: CorpusStore) -> list[RoundRecord]:
    folder = store.version_dir / "rounds"
    if not folder.is_dir():
        return []
    return [read(store, path, RoundRecord) for path in sorted(folder.glob("*/round.json"))]


def _source(store: CorpusStore, event_id: str) -> tuple[Spec, ClipSource]:
    """A ready still's spec, and its ready attempt's render as a clip source."""
    spec = read(store, store.spec_file(event_id), Spec)
    attempt = read(store, store.provenance_file(event_id), Provenance).attempts[-1]
    if attempt.render is None or attempt.triage is None or attempt.triage.verdict != "ok":
        raise AskOwner(
            f"{event_id} is ready in the index, but its attempt {attempt.k} has no render or "
            "no ok verdict."
        )
    return spec, ClipSource(event_id=event_id, k=attempt.k, render_sha256=attempt.render.sha256)


def _pool(store: CorpusStore) -> list[Candidate]:
    """Every ready still that no clip event names as its source (ruling H3-R4)."""
    taken = {row.source for row in read_clip_index(store).values()}
    pool: list[Candidate] = []
    for event_id, row in sorted(read_index(store).items()):
        if row.status == "ready" and event_id not in taken:
            spec, _ = _source(store, event_id)
            pool.append(Candidate(event_id, spec.cell.group, spec.cell.lighting))
    return pool


def _write_specs(store: CorpusStore, record: RoundRecord) -> int:
    """Write the round's clip specs that are missing; exit 2 on one changed by hand."""
    known = read_clip_index(store)
    written = 0
    rows: list[ClipIndexRow] = []
    pairs = zip(record.event_ids, record.source_event_ids, strict=True)
    for number, (event_id, source_id) in enumerate(pairs):
        spec, source = _source(store, source_id)
        want = ClipSpec.from_source(
            spec,
            round_name=record.name,
            number=number,
            k=source.k,
            render_sha256=source.render_sha256,
        )
        path = store.spec_file(event_id)
        if not path.exists():
            write_new(store, path, want)
            written += 1
        else:
            have = read(store, path, ClipSpec)
            if have.facts() != want.facts() or have.source != want.source:
                raise AskOwner(
                    f"{path} is not what clip sample makes for round {record.name}: the corpus "
                    "was changed by hand."
                )
        if event_id not in known:
            rows.append(
                ClipIndexRow(
                    event_id=event_id,
                    round=record.name,
                    source=source_id,
                    scenario=spec.cell.scenario,
                    label=spec.label,
                    status="sampled",
                    time=now_iso(),
                )
            )
    append_clip_index(store, rows)
    return written
