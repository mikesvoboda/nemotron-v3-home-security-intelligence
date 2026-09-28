"""`python -m synthbench <command>`: the synthbench command line (agent-driven design §3).

Every command exits 0 when done, 1 on an error (fix the request and retry), and 2 when the
agent must stop and ask the owner (the corpus or taxonomy is not in the state it expects).
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn, TypeVar

from pydantic import ValidationError

from synthbench.contract.common import SLUG, ContractModel
from synthbench.contract.corpus import TIER_B_RENDER_SIZE, BatchRecord, CorpusManifest, IndexRow
from synthbench.contract.spec import Spec
from synthbench.contract.store import CorpusStore
from synthbench.taxonomy.model import Taxonomy, load_taxonomy, taxonomy_sha256
from synthbench.taxonomy.sampler import MAX_BATCH, default_seed, sample_specs

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_ASK = 2

M = TypeVar("M", bound=ContractModel)


class _Parser(argparse.ArgumentParser):
    """argparse exits 2 on a usage error, but 2 means "ask the owner" here, so exit 1."""

    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        self.exit(EXIT_ERROR, f"{self.prog}: error: {message}\n")


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


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="python -m synthbench",
        description=(
            "Synthetic benchmark generation. Exit codes: 0 done, 1 error (fix the request), "
            "2 stop and ask the owner."
        ),
        allow_abbrev=False,
    )
    commands = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)
    sample = commands.add_parser(
        "sample",
        help="sample Tier B specs (facts only, no prompt) into a new batch",
        allow_abbrev=False,
    )
    sample.add_argument(
        "--batch", required=True, help="new batch name: lowercase letters, digits and hyphens"
    )
    sample.add_argument(
        "--n", type=_batch_size, required=True, help=f"number of events, 1..{MAX_BATCH}"
    )
    sample.add_argument(
        "--seed",
        type=_seed,
        default=None,
        help="sampler seed (default: derived from the batch name)",
    )
    sample.add_argument(
        "--only", default="", help="comma-separated scenario ids to sample from (default: all)"
    )
    return parser


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _fail(code: int, message: str) -> int:
    sys.stderr.write(f"synthbench: {message}\n")
    return code


class _CorpusError(Exception):
    """A corpus file could not be read, parsed or written: cmd_sample exits EXIT_ASK."""

    def __init__(self, verb: str, path: Path, error: Exception) -> None:
        lines = str(error).splitlines()
        self.verb = verb
        self.path = path
        self.detail = f"{type(error).__name__}: {lines[0]}" if lines else type(error).__name__
        super().__init__(f"cannot {verb} {path} ({self.detail})")


# Corpus I/O goes through these four. A file that will not read or validate, or a write that
# fails, means the corpus is not in the state the agent expects: that is the owner's call
# (exit 2), not a request to fix (exit 1). Models built from the request are validated by the
# caller, outside these helpers, so their ValidationErrors are not caught here.
def _read(store: CorpusStore, path: Path, model: type[M]) -> M:
    try:
        return store.read(path, model)
    except (OSError, UnicodeDecodeError, ValidationError) as error:
        raise _CorpusError("read", path, error) from error


def _read_index(store: CorpusStore) -> dict[str, IndexRow]:
    try:
        return store.latest_index()
    except (OSError, UnicodeDecodeError, ValidationError) as error:
        raise _CorpusError("read", store.index_file, error) from error


def _write(store: CorpusStore, path: Path, model: ContractModel) -> None:
    try:
        store.write_new(path, model)
    except OSError as error:  # includes FileExistsError when two first runs race
        raise _CorpusError("write", path, error) from error


def _append_index(store: CorpusStore, rows: Iterable[IndexRow]) -> None:
    try:
        store.append_index(rows)
    except OSError as error:
        raise _CorpusError("write", store.index_file, error) from error


def cmd_sample(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    tax = load_taxonomy()
    batch: str = args.batch
    version = tax.version  # load_taxonomy already checked it against SLUG
    if not SLUG.fullmatch(batch):
        return _fail(EXIT_ERROR, f"batch name must match {SLUG.pattern}: {batch!r}")
    only = tuple(sorted({s for s in args.only.split(",") if s}))
    if unknown := sorted(set(only) - {s.id for s in tax.scenarios}):
        valid = ", ".join(s.id for s in tax.scenarios)
        return _fail(EXIT_ERROR, f"unknown scenario(s): {', '.join(unknown)}; valid: {valid}")

    seed: int = args.seed if args.seed is not None else default_seed(batch)
    store = CorpusStore.from_env(version, env)
    try:
        return _sample(tax, store, batch=batch, n=args.n, seed=seed, only=only)
    except _CorpusError as error:
        return _fail(
            EXIT_ASK,
            f"cannot {error.verb} {error.path} ({error.detail}). Stop and ask the owner.",
        )


def _sample(
    tax: Taxonomy, store: CorpusStore, *, batch: str, n: int, seed: int, only: tuple[str, ...]
) -> int:
    """cmd_sample for a valid request. Corpus I/O failures raise _CorpusError."""
    version = store.version
    digest = taxonomy_sha256()
    if store.manifest_file.exists():
        if _read(store, store.manifest_file, CorpusManifest).taxonomy_sha256 != digest:
            return _fail(
                EXIT_ASK,
                f"the taxonomy changed since corpus version {version} was created, so new "
                "batches would not be comparable. Stop and ask the owner: a changed taxonomy "
                "needs a new corpus version, which the owner sets by editing `version:` in "
                "synthbench/taxonomy/tier_b_v0.yaml.",
            )
    else:
        _write(
            store,
            store.manifest_file,
            CorpusManifest(
                version=version,
                taxonomy_sha256=digest,
                render_size=TIER_B_RENDER_SIZE,
                created=_now(),
            ),
        )

    batch_file = store.batch_file(batch)
    record = _read(store, batch_file, BatchRecord) if batch_file.exists() else None
    if record is not None and (record.seed, record.n, record.only) != (seed, n, only):
        return _fail(
            EXIT_ERROR,
            f"batch {batch} already exists with seed={record.seed}, n={record.n}, "
            f"only={','.join(record.only) or 'all'}; choose a new batch name",
        )
    index = _read_index(store)
    if record is not None:
        prior = record.prior_counts
    else:
        prior = dict(Counter(row.scenario for row in index.values()))
    specs = sample_specs(
        tax, version=version, batch=batch, n=n, seed=seed, prior=prior, only=only or None
    )
    if record is None:
        _write(
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
                created=_now(),
            ),
        )

    written = 0
    for spec in specs:
        path = store.spec_file(spec.event_id)
        if not path.exists():
            _write(store, path, spec)
            written += 1
        elif _read(store, path, Spec) != spec:
            return _fail(
                EXIT_ASK,
                f"{path} is not what the sampler produces for batch {batch}: the corpus was "
                "changed by hand. Stop and ask the owner.",
            )
    rows = [
        IndexRow(
            event_id=s.event_id,
            batch=batch,
            scenario=s.cell.scenario,
            label=s.label,
            status="sampled",
            time=_now(),
        )
        for s in specs
        if s.event_id not in index
    ]
    _append_index(store, rows)
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


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    environment: Mapping[str, str] = os.environ if env is None else env
    if args.command == "sample":
        return cmd_sample(args, environment)
    raise AssertionError(f"unhandled command {args.command!r}")  # argparse rejects unknown ones
