"""`sample --batch <b> --n <n>`: fact-only Tier B specs into a new batch (design §3 step 1)."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Mapping

from synthbench.commands.common import (
    EXIT_OK,
    AskOwner,
    Parser,
    RequestError,
    append_index,
    batch_name,
    check_manifest,
    now_iso,
    read,
    read_index,
    taxonomy,
    write_new,
)
from synthbench.contract.corpus import TIER_B_RENDER_SIZE, BatchRecord, CorpusManifest, IndexRow
from synthbench.contract.spec import Spec
from synthbench.contract.store import CorpusStore
from synthbench.taxonomy.model import Taxonomy, taxonomy_sha256
from synthbench.taxonomy.sampler import MAX_BATCH, default_seed, sample_specs


def _batch_size(text: str) -> int:
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


def add_parser(commands: argparse._SubParsersAction[Parser]) -> None:
    parser = commands.add_parser(
        "sample",
        help="sample Tier B specs (facts only, no prompt) into a new batch",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--batch",
        type=batch_name,
        required=True,
        help="new batch name: lowercase letters, digits and hyphens",
    )
    parser.add_argument(
        "--n", type=_batch_size, required=True, help=f"number of events, 1..{MAX_BATCH}"
    )
    parser.add_argument(
        "--seed",
        type=_seed,
        default=None,
        help="sampler seed (default: derived from the batch name)",
    )
    parser.add_argument(
        "--only", default="", help="comma-separated scenario ids to sample from (default: all)"
    )
    parser.set_defaults(run=run)


def run(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    tax = taxonomy()
    only = tuple(sorted({s for s in args.only.split(",") if s}))
    if unknown := sorted(set(only) - {s.id for s in tax.scenarios}):
        valid = ", ".join(s.id for s in tax.scenarios)
        raise RequestError(f"unknown scenario(s): {', '.join(unknown)}; valid: {valid}")
    seed: int = args.seed if args.seed is not None else default_seed(args.batch)
    store = CorpusStore.from_env(tax.version, env)
    return _sample(tax, store, batch=args.batch, n=args.n, seed=seed, only=only)


def _sample(
    tax: Taxonomy, store: CorpusStore, *, batch: str, n: int, seed: int, only: tuple[str, ...]
) -> int:
    version = store.version
    if store.manifest_file.exists():
        check_manifest(store)
    else:
        write_new(
            store,
            store.manifest_file,
            CorpusManifest(
                version=version,
                taxonomy_sha256=taxonomy_sha256(),
                render_size=TIER_B_RENDER_SIZE,
                created=now_iso(),
            ),
        )

    batch_file = store.batch_file(batch)
    record = read(store, batch_file, BatchRecord) if batch_file.exists() else None
    if record is not None and (record.seed, record.n, record.only) != (seed, n, only):
        raise RequestError(
            f"batch {batch} already exists with seed={record.seed}, n={record.n}, "
            f"only={','.join(record.only) or 'all'}; choose a new batch name"
        )
    index = read_index(store)
    if record is not None:
        prior = record.prior_counts
    else:
        prior = dict(Counter(row.scenario for row in index.values()))
    specs = sample_specs(
        tax, version=version, batch=batch, n=n, seed=seed, prior=prior, only=only or None
    )
    if record is None:
        write_new(
            store,
            batch_file,
            BatchRecord(
                name=batch,
                version=version,
                seed=seed,
                n=n,
                only=only,
                prior_counts=prior,
                event_ids=tuple(s.event_id for s in specs),
                created=now_iso(),
            ),
        )

    written = 0
    for spec in specs:
        path = store.spec_file(spec.event_id)
        if not path.exists():
            write_new(store, path, spec)
            written += 1
        elif read(store, path, Spec).facts() != spec.facts():
            raise AskOwner(
                f"{path} is not what the sampler produces for batch {batch}: the corpus was "
                "changed by hand."
            )
    append_index(
        store,
        [
            IndexRow(
                event_id=s.event_id,
                batch=batch,
                scenario=s.cell.scenario,
                label=s.label,
                status="sampled",
                time=now_iso(),
            )
            for s in specs
            if s.event_id not in index
        ],
    )
    counts = ", ".join(
        f"{k} {v}" for k, v in sorted(Counter(s.cell.scenario for s in specs).items())
    )
    sys.stdout.write(
        f"batch {batch} in corpus version {version}: {len(specs)} events ({written} written now)\n"
        f"  scenarios: {counts}\n"
        f"  specs: {store.event_dir(specs[0].event_id).parent}/"
        f"{specs[0].event_id} .. {specs[-1].event_id}\n"
    )
    return EXIT_OK
