#!/usr/bin/env python3
"""Mint the committed .test_durations shard-planning file from CI junit XMLs.

    uv run python scripts/mint-test-durations.py <results-dir> [<results-dir> ...] \
        [--out .test_durations]

<results-dir> is a directory tree of JUnit XMLs from ONE main-branch CI run —
the shard junits the `test-results-*` artifacts carry. Recipe (the corpus the
2026-10-09 mint used, run 37940703535 @ 5689e80ef):

    gh run download <run-id> --repo mikesvoboda/nemotron-v3-home-security-intelligence \
        --pattern "test-results-unit-shard-*" --dir /tmp/junit
    gh run download <run-id> ... --pattern "test-results-integration-*" --dir /tmp/junit
    uv run python scripts/mint-test-durations.py /tmp/junit

Why a committed file at all (batch-9 row 2, backend lane): with no durations,
pytest-split count-balances, and because pytest-randomly 5.0.0 keeps whole
module files contiguous (its _reorganize_items shuffles WITHIN a module, then
permutes module blocks by a seed-keyed sort), count-balanced shards are not
time-balanced. Measured on run 37940703535: shard test counts 7851/7851/7851/
7849 (1.0003x) but junit time sums 168.2/166.8/148.3/76.2 s (2.207x); run
37933347572 spread 1.207x (same testcase-sum method). test_redis.py alone
(30.9 s / 152 tests) decides
which shard wins the lottery.

The nodeid keys: pytest-split looks durations up by item.nodeid
(algorithms.py:157, "durations.get(item.nodeid, avg)"), but junit's
classname/name attrs are pytest's MANGLED form (dots, class folded in) —
_pytest/junitxml.py mangle_test_address. This script inverts that mangling;
the inversion joined 31402 of 31406 collected unit nodeids (99.99%) on the
mint corpus, the 4 misses being tests merged to main after the artifact run —
they take the file's mean-duration default, exactly as a never-seen test does.

Durations here are planning WEIGHTS, never pass/fail data; stale ones age as
gently as this file can. Refresh = rerun the recipe on a fresh green main run;
scripts/test_shard_durations.py pins the consumer contract.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import defusedxml.ElementTree as ET

# Only real test tiers belong in a planning file (defends the mean-duration
# default from junk keys a stray artifact could smuggle in).
ALLOWED_PREFIXES = ("backend/tests/",)


def junit_to_nodeid(classname: str | None, name: str | None) -> str | None:
    """Invert _pytest/junitxml.py mangle_test_address for our test layout.

    mangle joins the nodeid's path parts and class chain with ".":
    "backend/tests/unit/x/test_m.py::TestC::test_f" -> classname
    "backend.tests.unit.x.test_m.TestC", name "test_f". The module file is the
    first component starting "test_"; everything before it is directories,
    everything after it is the class chain. Returns None for anything not on
    that shape (root-level or non-test artifacts) — skipped, never guessed.
    """
    parts = (classname or "").split(".")
    idx = [i for i, p in enumerate(parts) if p.startswith("test_")]
    if not idx or not name:
        return None
    i = idx[0]
    path = "/".join(parts[:i] + [parts[i]]) + ".py"
    tail = parts[i + 1:] + [name]
    nodeid = "::".join([path] + tail)
    return nodeid if nodeid.startswith(ALLOWED_PREFIXES) else None


def mint(dirs: list[Path]) -> tuple[dict[str, float], int, int]:
    """Aggregate per-nodeid seconds over every testcase in every XML under dirs.

    A test appears in exactly one shard's junit of one run, so summing across
    files is an identity for a single-run corpus and a correct union if the
    caller passes unit and integration dirs together.
    """
    durations: dict[str, float] = {}
    rows = unmatched = 0
    xmls = sorted(p for d in dirs for p in d.rglob("*.xml"))
    if not xmls:
        sys.exit(f"error: no *.xml found under {dirs} (pass the junit artifact dirs)")
    for xml in xmls:
        root = ET.parse(xml).getroot()
        for tc in root.iter("testcase"):
            nodeid = junit_to_nodeid(tc.get("classname"), tc.get("name"))
            rows += 1
            if nodeid is None:
                unmatched += 1
                continue
            durations[nodeid] = durations.get(nodeid, 0.0) + float(tc.get("time") or 0.0)
    return durations, rows, unmatched


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dirs", nargs="+", type=Path, help="dirs of CI junit XMLs (one run)")
    ap.add_argument("--out", type=Path, default=Path(".test_durations"))
    args = ap.parse_args(argv)

    durations, rows, unmatched = mint(args.dirs)
    # Shape pytest-split's own --store-durations writes: sorted JSON, indent 4.
    args.out.write_text(json.dumps(durations, indent=4, sort_keys=True) + "\n")
    unit = sum(v for k, v in durations.items() if "/unit/" in k)
    total = sum(durations.values())
    print(
        f"wrote {args.out}: {len(durations)} nodeids from {rows} testcase rows"
        f" ({unmatched} rows not on the test-layout shape, skipped);"
        f" {total:.1f}s total, unit tier {unit:.1f}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
