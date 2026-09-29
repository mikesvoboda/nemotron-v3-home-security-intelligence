"""`corpus coverage`: the corpus's spread against the taxonomy's, and a draft's. Read-only.

Owner request, 2026-09-29; first written by the generation agent. For every axis it prints each
value's long-run chance per event, how many more events 30 ready ones would take, and the
expected, drawn and ready counts; then the next n events `sample` would draw from this corpus
(the same allocation, so a targeted batch's aftermath shows); then how much of each design space
is drawn. `--against DRAFT.yaml` compares a draft taxonomy's spread with the committed one's,
without installing it. The model is synthbench/taxonomy/coverage.py.
"""

from __future__ import annotations

import argparse
import math
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

import yaml
from pydantic import ValidationError

from synthbench.commands.common import (
    EXIT_OK,
    Parser,
    RequestError,
    check_manifest,
    read,
    read_index,
    taxonomy,
)
from synthbench.contract.spec import Spec
from synthbench.contract.store import CorpusStore
from synthbench.taxonomy.coverage import (
    AXES,
    SPACES,
    CellProb,
    cell_probs,
    cover,
    expected_counts,
    marginals,
    n_for_count,
    n_for_cover,
    space_size,
    within_scenario,
)
from synthbench.taxonomy.model import Taxonomy, load_taxonomy, taxonomy_sha256
from synthbench.taxonomy.sampler import allocate

NEXT_N = 400  # default --n: the run the owner first planned
MAX_N = 100_000  # allocate() is linear in n; this keeps the command under a few seconds
TARGET = 30  # events of a value that make it measurable at all
THIN = 0.02  # below this chance per event a value is listed with the scenarios that can show it


def add_parser(actions: argparse._SubParsersAction[Parser]) -> None:
    """Register `coverage` in the `corpus` command group."""
    parser = actions.add_parser(
        "coverage",
        help="show the corpus's spread, the next n events' and a draft taxonomy's (read-only)",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--n",
        type=_next_n,
        default=NEXT_N,
        help=f"the next n events to plan, as `sample` would draw them (default {NEXT_N})",
    )
    plan = parser.add_mutually_exclusive_group()
    plan.add_argument(
        "--only",
        default="",
        help="comma-separated scenario ids: draw the next n from these, as `sample --only`",
    )
    plan.add_argument(
        "--against",
        type=Path,
        default=None,
        metavar="DRAFT",
        help="a draft taxonomy YAML to compare with the committed one; never installed",
    )
    parser.set_defaults(run=run)


def _next_n(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"n must be an integer 1..{MAX_N}: {text!r}") from None
    if not 1 <= value <= MAX_N:
        raise argparse.ArgumentTypeError(f"n must be 1..{MAX_N}, got {value}")
    return value


def run(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    tax = taxonomy()
    only = tuple(sorted({s for s in args.only.split(",") if s}))
    if unknown := sorted(set(only) - {s.id for s in tax.scenarios}):
        valid = ", ".join(s.id for s in tax.scenarios)
        raise RequestError(f"unknown scenario(s): {', '.join(unknown)}; valid: {valid}")
    draft = _load_draft(args.against) if args.against is not None else None
    corpus = _Corpus.read(CorpusStore.from_env(tax.version, env))
    lines = _report(tax, corpus, args.n, only)
    if draft is not None:
        lines += ["", *_compare(tax, draft, args.against)]
    sys.stdout.write("\n".join(lines) + "\n")
    return EXIT_OK


def _load_draft(path: Path) -> Taxonomy:
    try:
        return load_taxonomy(path)
    except (OSError, UnicodeDecodeError, yaml.YAMLError, ValidationError) as error:
        first = (str(error).splitlines() or [""])[0]
        raise RequestError(
            f"--against {path} does not load ({type(error).__name__}: {first})"
        ) from error


class _Corpus:
    """What the corpus holds: per axis value, the events drawn, held (not failed) and ready."""

    def __init__(self, store: CorpusStore) -> None:
        self.store = store
        self.batches: Counter[str] = Counter()
        self.statuses: Counter[str] = Counter()
        self.drawn: dict[str, Counter[str]] = {axis: Counter() for axis in AXES}
        self.held: dict[str, Counter[str]] = {axis: Counter() for axis in AXES}
        self.ready: dict[str, Counter[str]] = {axis: Counter() for axis in AXES}
        self.rows: list[CellProb] = []  # one per drawn event, probability unused

    @classmethod
    def read(cls, store: CorpusStore) -> _Corpus:
        corpus = cls(store)
        if not store.index_file.exists():
            return corpus
        check_manifest(store)
        for row in read_index(store).values():
            cell = read(store, store.spec_file(row.event_id), Spec).cell
            drawn = CellProb(
                scenario=cell.scenario,
                property_type=cell.property_type,
                zone=cell.zone,
                camera=cell.camera,
                lighting=cell.lighting,
                weather=cell.weather,
                probability=0.0,
            )
            corpus.rows.append(drawn)
            corpus.batches[row.batch] += 1
            corpus.statuses[row.status] += 1
            for axis in AXES:
                corpus.drawn[axis][drawn.value(axis)] += 1
                if row.status != "failed":
                    corpus.held[axis][drawn.value(axis)] += 1
                if row.status == "ready":
                    corpus.ready[axis][drawn.value(axis)] += 1
        return corpus

    @property
    def total(self) -> int:
        return len(self.rows)


def to_target(probability: float, held: int) -> str:
    """How many more random events `TARGET` of a value would take, given `held` of them."""
    if held >= TARGET:
        return "done"
    more = n_for_count(probability, TARGET - held)
    return "never" if more == float("inf") else f"{more:,.0f}"


def _report(tax: Taxonomy, corpus: _Corpus, n: int, only: tuple[str, ...]) -> list[str]:
    cells = cell_probs(tax)
    rates = _rates(tax, cells)
    prior = corpus.drawn["scenario"]
    next_draws = Counter(allocate(tax, n, prior, only or None))
    expected = expected_counts(cells, prior)
    upcoming = expected_counts(cells, next_draws)
    head = [
        f"corpus coverage: {tax.version} (taxonomy sha256 {taxonomy_sha256()[:12]}): "
        f"{len(tax.scenarios)} scenarios, {len(cells):,} legal cells",
        _corpus_line(tax, corpus),
        f"next {n}: the events `sample` would draw next from this corpus, in batches of any size"
        + (f", all with --only {','.join(only)}." if only else "."),
        f"p: the long-run chance per event. to {TARGET}: the events still needed for {TARGET}, by "
        "chance, counting every drawn event that has not failed. share: the scenario's weighted "
        "share of the events drawn. expect: the count p predicts, given the scenarios drawn.",
    ]
    labels = {s.id: s.label for s in tax.scenarios}
    scenarios = [
        [
            s.id,
            s.label,
            f"{rates['scenario'][s.id]:.2%}",
            to_target(rates["scenario"][s.id], corpus.held["scenario"][s.id]),
            f"{corpus.total * rates['scenario'][s.id]:.1f}",
            str(prior[s.id]),
            str(corpus.ready["scenario"][s.id]),
            str(next_draws[s.id]),
        ]
        for s in sorted(tax.scenarios, key=lambda s: (-s.weight, s.id))
    ]
    header = ["scenario", "label", "p", f"to {TARGET}", "share", "drawn", "ready", f"next {n}"]
    lines = [*head, "", *_columns(header, scenarios, text=2)]
    for axis in AXES[1:]:
        rows = [
            [
                value,
                f"{p:.2%}",
                to_target(p, corpus.held[axis][value]),
                f"{expected[axis].get(value, 0.0):.1f}",
                str(corpus.drawn[axis][value]),
                str(corpus.ready[axis][value]),
                f"{upcoming[axis].get(value, 0.0):.1f}",
            ]
            for value, p in sorted(rates[axis].items(), key=lambda kv: (-kv[1], kv[0]))
        ]
        header = [axis, "p", f"to {TARGET}", "expect", "drawn", "ready", f"next {n}"]
        lines += ["", *_columns(header, rows)]
    lines += ["", *_spaces(cells, corpus, next_draws, n), "", *_thin(cells, rates, labels)]
    return lines


def _rates(tax: Taxonomy, cells: tuple[CellProb, ...]) -> dict[str, dict[str, float]]:
    """Every declared value's chance per event, 0.0 for one no scenario can show."""
    declared = {
        "scenario": [s.id for s in tax.scenarios],
        "property": [prop.id for prop in tax.properties],
        "zone": list(tax.zones),
        "camera": [camera.id for camera in tax.cameras],
        "lighting": [light.id for light in tax.lighting],
        "weather": [sky.id for sky in tax.weather],
    }
    reached = marginals(cells)
    return {axis: {v: reached[axis].get(v, 0.0) for v in declared[axis]} for axis in AXES}


def _corpus_line(tax: Taxonomy, corpus: _Corpus) -> str:
    where = corpus.store.version_dir
    if corpus.total == 0:
        return f"corpus {where}: no events drawn yet in {tax.version}."
    batches = ", ".join(f"{b} {count}" for b, count in sorted(corpus.batches.items()))
    return (
        f"corpus {where}: {corpus.total} events drawn ({batches}); "
        f"{corpus.statuses['ready']} ready, {corpus.statuses['failed']} failed."
    )


def _spaces(
    cells: tuple[CellProb, ...], corpus: _Corpus, next_draws: Mapping[str, int], n: int
) -> list[str]:
    rows = []
    for space in SPACES:
        drawn = {row.key(space) for row in corpus.rows}
        rows.append(
            [
                space,
                f"{space_size(cells, space):,}",
                f"{len(drawn):,}",
                f"{cover(cells, space, next_draws, drawn):,.0f}",
                f"{n_for_cover(cells, space, 0.90):,}",
                f"{n_for_cover(cells, space, 0.95):,}",
            ]
        )
    header = ["design space", "rows", "drawn", f"after next {n}", "n for 90%", "n for 95%"]
    return [
        *_columns(header, rows),
        "rows: what a designed quota would draw once each. n for 90% and 95%: the events a",
        "random draw needs, from none, to touch that share of the rows by chance.",
    ]


def _thin(
    cells: tuple[CellProb, ...], rates: Mapping[str, Mapping[str, float]], labels: Mapping[str, str]
) -> list[str]:
    lines = [
        f"thin values (p < {THIN:.0%}): every scenario that can show each, counted by label (no "
        "benign one: no false-alarm rate there), then the three likeliest to:"
    ]
    for axis in AXES[1:]:
        for value, p in sorted(rates[axis].items(), key=lambda kv: (kv[1], kv[0])):
            if p >= THIN:
                continue
            shares = within_scenario(cells, axis, value)
            if not shares:
                lines.append(f"  {axis} {value}  p 0.00%  no scenario can show it")
                continue
            top = ", ".join(
                f"{s} {share:.0%}"
                for s, share in sorted(shares.items(), key=lambda kv: (-round(kv[1], 9), kv[0]))[:3]
            )
            by_label = sorted(Counter(labels[s] for s in shares).items())
            kinds = ", ".join(f"{label} {count}" for label, count in by_label)
            lines.append(
                f"  {axis} {value}  p {p:.2%}  {len(shares)} scenario(s) by label: {kinds}; "
                f"likeliest: {top}"
            )
    return lines


def _compare(committed: Taxonomy, draft: Taxonomy, path: Path) -> list[str]:
    base, alt = cell_probs(committed), cell_probs(draft)
    lines = [
        f"against {path}: {draft.version} (sha256 {taxonomy_sha256(path)[:12]}), read-only: "
        "nothing is installed or sampled.",
    ]
    if draft.version == committed.version:
        lines.append(
            f"WARNING: the draft keeps version {draft.version}. Installed like that, it would make "
            "every command exit 2 (corpus.json records the old taxonomy): a new taxonomy needs a "
            "new version id."
        )
    counts = [
        ("scenarios", len(committed.scenarios), len(draft.scenarios)),
        ("properties", len(committed.properties), len(draft.properties)),
        ("zones", len(committed.zones), len(draft.zones)),
        ("cameras", len(committed.cameras), len(draft.cameras)),
        ("cells", len(base), len(alt)),
        *((space, space_size(base, space), space_size(alt, space)) for space in SPACES),
    ]
    rows = [
        [label, f"{before:,}", f"{after:,}", "" if before == after else f"({after - before:+,})"]
        for label, before, after in counts
    ]
    lines += ["", *_columns(["count", committed.version, draft.version, "change"], rows)]
    lines += ["", f"values whose chance per event moves (p, then the events for {TARGET}):"]
    weights = _weight_notes(committed, draft)
    before, after = _rates(committed, base), _rates(draft, alt)
    moved: list[str] = []
    for axis in AXES:
        for value in sorted(set(before[axis]) | set(after[axis])):
            p0, p1 = before[axis].get(value, 0.0), after[axis].get(value, 0.0)
            new, dropped = value not in before[axis], value not in after[axis]
            if not (new or dropped) and math.isclose(p0, p1, rel_tol=1e-9, abs_tol=1e-12):
                continue
            note = "  (new)" if new else "  (dropped)" if dropped else ""
            weight = weights.get(value, "") if axis == "scenario" else ""
            moved.append(
                f"  {axis} {value}  p {p0:.2%} -> {p1:.2%}  for {TARGET}: "
                f"{to_target(p0, 0)} -> {to_target(p1, 0)}{note}{weight}"
            )
    return [*lines, *(moved or ["  none"])]


def _weight_notes(committed: Taxonomy, draft: Taxonomy) -> dict[str, str]:
    """Per scenario whose weight moved: the setting behind the shift."""
    before = {s.id: s.weight for s in committed.scenarios}
    after = {s.id: s.weight for s in draft.scenarios}
    return {
        sid: f"  (weight {before.get(sid, 0):g} -> {after.get(sid, 0):g})"
        for sid in set(before) | set(after)
        if before.get(sid) != after.get(sid)
    }


def _columns(header: Sequence[str], rows: Sequence[Sequence[str]], text: int = 1) -> list[str]:
    """Aligned plain-text columns: the first `text` columns left-aligned, the numbers right."""
    widths = [max(len(row[i]) for row in (header, *rows)) for i in range(len(header))]

    def line(cells: Sequence[str]) -> str:
        parts = [
            cell.ljust(width) if i < text else cell.rjust(width)
            for i, (cell, width) in enumerate(zip(cells, widths, strict=True))
        ]
        return "  ".join(parts).rstrip()

    return [line(header), *(line(row) for row in rows)]
