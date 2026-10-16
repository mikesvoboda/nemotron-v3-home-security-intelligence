#!/usr/bin/env python3
"""The inventory's status, checked against the golden run that just executed ([r218], ruling 218).

    python3 -m scripts.uplevel.inventory_witness --run-root "$FEATURE_CHECK_ROOT"   # the CI step
    python3 -m scripts.uplevel.inventory_witness --summary A/summary.json [--summary B/summary.json]

Each Feature check job records every golden leg it ran in its ``summary.json``
(``results.golden.playwright_specs`` and, on the fake AI job, ``backend_specs``: ``"<spec>::<title>"``
-> ``passed`` / ``failed`` / ``skipped``, ``scripts/feature_check.py`` ``junit_results``). The golden
specs carry their rows' ids in their titles (``test.describe('F-048 full-text search', ...)``). This
check maps each executed leg to the ``docs/reference/feature-inventory.md`` rows its title names and
holds each row's ``status`` to what the run shows (UR-128; rulings 103, 114, 148, 218):

* **Mapping.** A Playwright leg's title is its describe titles and test title (``›``-joined); the
  INNERMOST segment that names any ``F-NNN`` gives the leg's rows, so a describe naming
  ``(F-164..F-167, F-169, F-174)`` lends its ids only to a test whose own title names none, and a
  failing ``F-165 ...`` test never fails F-164. A range, ``F-164..F-167`` or ``F-240 to F-243``,
  names every id from one end to the other. A pytest leg (``backend/tests/golden``) cannot spell a
  hyphen, so its function or class name carries the id as an ``_``-delimited ``f190`` word
  (``test_f190_feature_toggle_...``).
* **awaiting real tier / works** need at least one mapped leg, and every mapped leg must have
  executed and passed in this run. A failed or skipped leg (``test.fixme`` included) fails the row.
* **unverified** is never failed. When it has mapped legs and every one passed, it prints as READY
  to flip to **awaiting real tier**, with evidence-cell text to paste. Only fake-tier legs are read:
  promoting to **works** is the operator's real-tier confirmation (ruling 148), so a ``real`` run's
  summary is refused rather than read.
* **half-built / leftover** are not judged; legs mapped to them are reported as info.
* **The two jobs.** ``Feature check (fake AI)`` runs every golden spec but ``*.seeded.spec.ts``
  (plus the backend pytest leg); ``Feature check (seeded)`` runs only those. Each job judges a row on
  the legs it ran itself; a failed or skipped leg fails the row in the job that ran it. A row with NO
  mapped leg in a job's run fails there only if that job is the row's HOME, read from the checked-out
  specs: the jobs whose spec files carry the row's id in a test or describe title (the seeded job
  for a ``*.seeded.spec.ts``, the fake AI job for any other golden spec, both when both do). A row
  no title names takes its home from the specs its evidence cites (seeded when it cites only
  ``*.seeded.spec.ts``), else the fake AI job. So a job never fails a row for lacking a leg it was
  never meant to run; a passing mention of a spec in the evidence cannot move a titled row's home;
  and a READY line speaks for the legs of its own job only.
* **Known disagreements** (``inventory_witness_known.toml``, beside this file) excuse named LEGS,
  not rows: each entry names a row, its job(s), the exact test titles it excuses, and why. In a job
  it names, those legs may fail or skip and the row reports as KNOWN; any other mapped leg that
  does not pass, or no mapped leg at all, still fails the row. An entry that excuses nothing fails
  the check: a listed leg that now passes, or that this run did not map to the row, or a row that
  no longer claims a status. So the list can only shrink to what is still true.
* Every golden spec whose legs name no row is listed (not failed): its legs witness nothing.

Exit 0: every judged row agrees (known legs reported). 1: a row claims more than the run shows, a
leg names a row the inventory lacks, or a known entry is stale. 2: an input could not be read -- no
or several summaries, a summary whose Playwright project executed no test or with an unknown
outcome, an unreadable inventory, known list or spec tree -- always with its reason (fail closed:
no read, no green). The last line counts what was read, so an empty read cannot pass as clean.

Evidence cells name the spec and its legs; run and job ids are no longer required there, because
this check re-proves every judged row at every head that runs the Feature check jobs (UR-181,
ruling 218).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import tomllib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[2]
INVENTORY = REPO_ROOT / "docs" / "reference" / "feature-inventory.md"
KNOWN = Path(__file__).resolve().parent / "inventory_witness_known.toml"
FRONTEND_GOLDEN = Path("frontend") / "tests" / "golden"
BACKEND_GOLDEN = Path("backend") / "tests" / "golden"
# The inventory's table parser (escape-aware cell split, columns by header name), reused rather
# than re-implemented. Its file name has hyphens, so it is loaded by path.
ARITH = REPO_ROOT / "scripts" / "check-inventory-summary-arith.py"

AWAITING = "awaiting real tier"
CLAIMS = ("works", AWAITING)  # statuses a run must witness
STATUSES = ("unverified", "half-built", "leftover", AWAITING, "works")
OUTCOMES = ("passed", "failed", "skipped")

# summary["mode"] -> the job (feature_check.py Run.shape: "fake", "fake-seeded"; real modes refused).
JOBS = {"fake": "fake", "fake-seeded": "seeded"}
JOB_NAMES = {"fake": "Feature check (fake AI)", "seeded": "Feature check (seeded)"}

ROW_ID = re.compile(r"^F-\d+$")
# One id, or a range of them: `F-164..F-167`, `F-240 to F-243`.
TITLE_ID = re.compile(r"(?<![\w-])F-(\d{3,})(?:\s*(?:\.\.|to)\s*F-(\d{3,}))?(?!\d)")
PYTEST_ID = re.compile(r"(?:^|_)[fF](\d{3,})(?=_|$)")
SEGMENT = " › "  # Playwright's junit title separator (describe › … › test)
SEEDED_SPEC = re.compile(r"[\w./-]*\.seeded\.spec\.ts")
GOLDEN_SPEC = re.compile(r"[\w./-]*golden/[\w./-]+\.(?:spec\.ts|py)\b")
# A title-declaring call in a golden spec: test(…), test.describe(…), test.fixme(…), test.skip('…'),
# with its first argument a string literal. test.step / test.info / test.skip(condition) declare none.
TS_TITLE = re.compile(
    r"\btest(?:\.(?:describe|serial|parallel|only|skip|fixme|fail|slow))*\(\s*"
    r"(['\"`])((?:\\.|(?!\1)[^\\])*)\1"
)
PY_TITLE = re.compile(r"^\s*(?:async\s+)?def\s+(test_\w+)|^\s*class\s+(Test\w+)", re.M)
COMMENT_LINE = re.compile(r"^\s*(?://|/\*|\*).*$", re.M)
PASTE_LIMIT = 500  # UR-181: an evidence cell is about 500 characters


class ReadError(Exception):
    """An input the check cannot read. Always exit 2, with the reason."""


@dataclass(frozen=True)
class Row:
    id: str
    status: str
    evidence: str


@dataclass(frozen=True)
class Leg:
    spec: str  # repo-relative path
    title: str  # the title as the junit report gives it
    outcome: str
    rows: tuple[str, ...]

    @property
    def own(self) -> str:
        """The test's own title (a pytest leg's function name), as a known entry lists it."""
        return self.title.split(SEGMENT)[-1]


@dataclass(frozen=True)
class Known:
    legs: tuple[str, ...]  # the test titles this entry excuses, exactly as written
    why: str


@dataclass
class Verdict:
    job: str
    run: str
    legs: list[Leg]
    failures: list[str] = field(default_factory=list)
    known: list[str] = field(default_factory=list)
    ready: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)
    deferred: list[str] = field(default_factory=list)
    unnamed_specs: list[str] = field(default_factory=list)
    witnessed: int = 0


# -- reading -------------------------------------------------------------------------------------


def _arith() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_inventory_summary_arith", ARITH)
    if spec is None or spec.loader is None:
        raise ReadError(f"cannot load the inventory parser {ARITH}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except (OSError, SyntaxError) as error:
        raise ReadError(f"cannot load the inventory parser {ARITH}: {error}") from error
    return module


def read_inventory(text: str) -> dict[str, Row]:
    """Every ``F-NNN`` row of every table whose header has ``id``, ``status`` and ``evidence``."""
    arith = _arith()
    rows: dict[str, Row] = {}
    try:
        for table in arith.tables(text.splitlines()):
            if len(table) < 2 or not arith.is_separator(arith.split_row(table[1])):
                continue
            cols = arith.header_columns(table)
            if not {"id", "status", "evidence"} <= cols.keys():
                continue
            for line in table[2:]:
                cells = arith.split_row(line)
                if not ROW_ID.match(cells[0]):
                    raise ReadError(f"a table line is not an F-NNN row: {line[:60]!r}")
                if len(cells) <= max(cols["status"], cols["evidence"]):
                    raise ReadError(f"{cells[0]}: {len(cells)} cells, too few for status/evidence")
                status = cells[cols["status"]]
                if status not in STATUSES:
                    raise ReadError(f"{cells[0]}: status {status!r} is not one of {', '.join(STATUSES)}")
                if cells[0] in rows:
                    raise ReadError(f"{cells[0]} is declared twice")
                rows[cells[0]] = Row(cells[0], status, cells[cols["evidence"]])
    except arith.InventoryError as error:
        raise ReadError(f"inventory: {error}") from error
    if not rows:
        raise ReadError("the inventory has no F-NNN rows")
    return rows


def title_ids(text: str) -> tuple[str, ...]:
    """Every row id a Playwright title names, ranges expanded end to end, in order, once each."""
    ids: list[str] = []
    for match in TITLE_ID.finditer(text):
        first = int(match[1])
        last = int(match[2]) if match[2] else first
        step = 1 if last >= first else -1
        ids += [f"F-{n:03d}" for n in range(first, last + step, step)]
    return tuple(dict.fromkeys(ids))


def _spec_path(classname: str, backend: bool) -> tuple[str, list[str]]:
    """(repo-relative spec path, the class names a pytest leg sits in)."""
    if backend:
        parts = classname.split(".")
        module = max((i for i, p in enumerate(parts) if p.startswith("test_")), default=len(parts) - 1)
        return "/".join(parts[: module + 1]) + ".py", parts[module + 1 :]
    _, sep, rest = classname.partition("golden/")
    return (f"frontend/tests/golden/{rest}" if sep else classname), []


def leg_rows(title: str, *, backend: bool, classes: Sequence[str] = ()) -> tuple[str, ...]:
    """The rows a leg's title names: its innermost id-bearing segment (see the module docstring)."""
    if backend:
        for segment in reversed([*classes, title]):
            ids = PYTEST_ID.findall(segment)
            if ids:
                return tuple(dict.fromkeys(f"F-{n}" for n in ids))
        return ()
    for segment in reversed(title.split(SEGMENT)):
        ids = title_ids(segment)
        if ids:
            return ids
    return ()


def title_homes(root: Path) -> dict[str, frozenset[str]]:
    """{row id: the jobs whose golden spec files name it in a test or describe title}.

    A static read of the checked-out specs, so it knows which job is MEANT to run a row's legs
    even when this run shows none. ``*.seeded.spec.ts`` is the seeded job's; every other golden
    spec, Playwright or pytest, is the fake AI job's. Comment lines are skipped.
    """
    frontend = sorted((root / FRONTEND_GOLDEN).rglob("*.spec.ts"))
    backend = sorted((root / BACKEND_GOLDEN).rglob("test_*.py"))
    if not frontend:
        raise ReadError(f"{root / FRONTEND_GOLDEN}: no golden spec to read the rows' home jobs from")
    homes: dict[str, set[str]] = {}
    try:
        for path in frontend:
            job = "seeded" if path.name.endswith(".seeded.spec.ts") else "fake"
            text = COMMENT_LINE.sub("", path.read_text(encoding="utf-8"))
            for match in TS_TITLE.finditer(text):
                for row_id in title_ids(match[2]):
                    homes.setdefault(row_id, set()).add(job)
        for path in backend:
            for match in PY_TITLE.finditer(path.read_text(encoding="utf-8")):
                for number in PYTEST_ID.findall(match[1] or match[2]):
                    homes.setdefault(f"F-{number}", set()).add("fake")
    except (OSError, UnicodeDecodeError) as error:
        raise ReadError(f"cannot read a golden spec: {error}") from error
    return {row_id: frozenset(jobs) for row_id, jobs in homes.items()}


def home(row: Row, homes: Mapping[str, frozenset[str]]) -> frozenset[str]:
    """The job(s) that must carry this row's legs when a run shows none (the split rule)."""
    if row.id in homes:
        return homes[row.id]
    seeded = bool(SEEDED_SPEC.search(row.evidence))
    other = any(not s.endswith(".seeded.spec.ts") for s in GOLDEN_SPEC.findall(row.evidence))
    return frozenset({"seeded"} if seeded and not other else {"fake"})


def read_summary(path: Path) -> tuple[str, str, list[Leg]]:
    """(job, a run label, every executed leg) from one Feature check ``summary.json``."""
    try:
        summary = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReadError(f"{path}: cannot read the run summary: {error}") from error
    mode = summary.get("mode") if isinstance(summary, dict) else None
    if mode not in JOBS:
        raise ReadError(
            f"{path}: mode {mode!r} is not a CI fake-tier run ({', '.join(JOBS)}); real-tier"
            " confirmation is the operator's (ruling 148), so only fake-tier legs are judged here"
        )
    golden = (summary.get("results") or {}).get("golden")
    if not isinstance(golden, dict):
        raise ReadError(
            f"{path}: no results.golden -- the golden stage did not run or did not record"
            f" (results: {sorted((summary.get('results') or {}).keys())}), so nothing can witness a row"
        )
    playwright = golden.get("playwright_specs")
    if not isinstance(playwright, dict):
        raise ReadError(
            f"{path}: results.golden has no playwright_specs (playwright: {golden.get('playwright')!r})"
        )
    if not playwright:
        # Not ~120 "no leg names it" lines: the Playwright project carries nearly every row's legs,
        # so a run where it executed nothing (image unavailable, no tag, an empty report) is a run
        # that cannot witness, whatever the backend leg did (UR-128).
        raise ReadError(
            f"{path}: the golden Playwright project executed no test (playwright:"
            f" {golden.get('playwright')!r}), so this run cannot witness the rows"
        )
    backend = golden.get("backend_specs", {})
    if not isinstance(backend, dict):
        raise ReadError(f"{path}: results.golden.backend_specs is not a mapping")
    legs: list[Leg] = []
    for specs, is_backend in ((playwright, False), (backend, True)):
        for key, outcome in specs.items():
            if outcome not in OUTCOMES:
                raise ReadError(f"{path}: leg {key!r} has outcome {outcome!r}, not one of {OUTCOMES}")
            classname, sep, title = key.partition("::")
            if not sep:
                raise ReadError(f"{path}: leg {key!r} is not '<spec>::<title>'")
            spec, classes = _spec_path(classname, is_backend)
            legs.append(Leg(spec, title, outcome, leg_rows(title, backend=is_backend, classes=classes)))
    run = f"{summary.get('project', '?')} at {str(summary.get('commit') or '?')[:9]}"
    return JOBS[mode], run, legs


def read_known(text: str, rows: Mapping[str, Row]) -> dict[tuple[str, str], Known]:
    """{(row, job): the legs it excuses and why} from the known-disagreements file."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise ReadError(f"known list: {error}") from error
    entries = data.get("known", [])
    if set(data) - {"known"} or not isinstance(entries, list) or not all(isinstance(e, dict) for e in entries):
        raise ReadError(f"known list: expected only [[known]] tables, read keys {sorted(data)}")
    known: dict[tuple[str, str], Known] = {}
    for entry in entries:
        row, jobs, legs, why = entry.get("row"), entry.get("jobs"), entry.get("legs"), entry.get("why")
        if row not in rows:
            raise ReadError(f"known list: {row!r} is not an inventory row")
        if not isinstance(jobs, list) or not jobs or not set(jobs) <= set(JOB_NAMES):
            raise ReadError(f"known list: {row} jobs {jobs!r} must be a non-empty list of {sorted(JOB_NAMES)}")
        if not isinstance(legs, list) or not legs or not all(isinstance(t, str) and t.strip() for t in legs):
            raise ReadError(f"known list: {row} legs {legs!r} must be a non-empty list of test titles")
        if not isinstance(why, str) or not why.strip():
            raise ReadError(f"known list: {row} says no why")
        for job in jobs:
            if (row, job) in known:
                raise ReadError(f"known list: {row} is listed twice for the {job} job")
            known[(row, job)] = Known(tuple(legs), why.strip())
    return known


def find_summary(root: Path) -> Path:
    """The one ``<run>/artifacts/summary.json`` under a Feature check root."""
    found = sorted(root.glob("*/artifacts/summary.json"))
    if len(found) != 1:
        raise ReadError(
            f"{root}: expected exactly one */artifacts/summary.json, found {len(found)}"
            + (f": {', '.join(str(p) for p in found)}" if found else " (the harness wrote no summary)")
        )
    return found[0]


# -- judging -------------------------------------------------------------------------------------


def _leg_line(leg: Leg) -> str:
    return f"{leg.outcome} {leg.spec} :: {leg.title}"


def paste_text(legs: Sequence[Leg], job: str) -> str:
    """The witness sentence for a row ready to flip: the spec and its legs, no run id (UR-181).

    Legs are named by their own (innermost) title, as many as fit in about 500 characters; the
    rest are counted.
    """
    specs = ", ".join(f"`{spec}`" for spec in dict.fromkeys(leg.spec for leg in legs))
    head = f"Green golden path on the fake tier ({JOB_NAMES[job]} job): {specs}; legs: "
    tail = ". **works** waits on the real tier (ruling 148)."
    names = [f"`{leg.own}`" for leg in legs]
    shown: list[str] = []
    for name in names:
        rest = len(names) - len(shown) - 1
        more = f"; +{rest} more" if rest else ""
        if len(head + "; ".join([*shown, name]) + more + tail) > PASTE_LIMIT:
            break
        shown.append(name)
    rest = len(names) - len(shown)
    listed = "; ".join(shown) if shown else f"{rest} legs"
    if shown and rest:
        listed += f"; +{rest} more"
    return head + listed + tail


def _stale(row: Row, job: str, entry: Known, mapped: Sequence[Leg]) -> list[str]:
    """Why a known entry no longer excuses anything it lists in this job (empty: still true)."""
    where = f"{row.id}'s known entry ({KNOWN.name}, {job} job)"
    if row.status not in CLAIMS:
        return [f"{where} is stale: the row is {row.status} now, so remove the entry"]
    by_title = {leg.own: leg for leg in mapped}
    stale = []
    for title in entry.legs:
        leg = by_title.get(title)
        if leg is None:
            stale.append(f"{where} lists `{title}`, which this run did not map to {row.id}: fix or remove it")
        elif leg.outcome == "passed":
            stale.append(f"{where} lists `{title}`, which passed: remove it from the entry")
    return stale


def judge(
    rows: Mapping[str, Row],
    job: str,
    run: str,
    legs: Sequence[Leg],
    known: Mapping[tuple[str, str], Known],
    homes: Mapping[str, frozenset[str]],
) -> Verdict:
    verdict = Verdict(job=job, run=run, legs=list(legs))
    by_row: dict[str, list[Leg]] = {}
    for leg in legs:
        for row_id in leg.rows:
            if row_id not in rows:
                verdict.failures.append(f"{row_id} is not an inventory row, yet a leg names it: {_leg_line(leg)}")
                continue
            by_row.setdefault(row_id, []).append(leg)
    by_spec: dict[str, bool] = {}
    for leg in legs:
        by_spec[leg.spec] = by_spec.get(leg.spec, False) or bool(leg.rows)
    verdict.unnamed_specs = sorted(spec for spec, named in by_spec.items() if not named)

    for row in rows.values():
        mapped = by_row.get(row.id, [])
        bad = [leg for leg in mapped if leg.outcome != "passed"]
        entry = known.get((row.id, job))
        if row.status in CLAIMS:
            excused = [leg for leg in bad if entry and leg.own in entry.legs]
            unexcused = [leg for leg in bad if leg not in excused]
            if not mapped and job in home(row, homes):
                verdict.failures.append(
                    f"{row.id} ({row.status}): no leg in this run names it -- the {job} job is its"
                    f" home, so a spec there must carry {row.id} in a title and execute"
                )
            elif unexcused:
                verdict.failures.append(f"{row.id} ({row.status}): " + "; ".join(_leg_line(leg) for leg in unexcused))
            elif excused:
                verdict.known.append(
                    f"{row.id} ({row.status}): " + "; ".join(_leg_line(leg) for leg in excused) + f"\n    known: {entry.why}"
                )
            elif not mapped:
                verdict.deferred.append(row.id)
            else:
                verdict.witnessed += 1
        elif row.status == "unverified" and mapped and not bad:
            verdict.ready.append(
                f"{row.id} (unverified -> {AWAITING}): {len(mapped)} leg(s), each passed in this job.\n"
                f"    evidence text: {paste_text(mapped, job)}"
            )
        elif mapped:
            outcomes = ", ".join(f"{n} {o}" for o in OUTCOMES if (n := sum(leg.outcome == o for leg in mapped)))
            verdict.info.append(f"{row.id} ({row.status}): {len(mapped)} leg(s) mapped ({outcomes}); not judged")
        if entry:
            verdict.failures += _stale(row, job, entry, mapped)
    return verdict


# -- reporting -----------------------------------------------------------------------------------


def report(verdict: Verdict) -> None:
    name = JOB_NAMES[verdict.job]
    print(f"inventory witness -- {name}, run {verdict.run}")
    for title, lines in (
        ("FAIL", verdict.failures),
        ("KNOWN", verdict.known),
        ("READY to flip", verdict.ready),
        ("info", verdict.info),
    ):
        for line in lines:
            print(f"{title}: {line}")
    if verdict.deferred:
        print(f"not judged here (no leg in this run; the other job is their home): {', '.join(verdict.deferred)}")
    for spec in verdict.unnamed_specs:
        count = sum(leg.spec == spec for leg in verdict.legs)
        print(f"names no row: {spec} ({count} leg(s))")
    mapped = {r for leg in verdict.legs for r in leg.rows}
    print(
        f"{name}: {len(verdict.legs)} legs read, {len(mapped)} rows named, {verdict.witnessed} claims"
        f" witnessed, {len(verdict.failures)} failing, {len(verdict.known)} known, {len(verdict.ready)}"
        f" ready to flip, {len(verdict.unnamed_specs)} specs name no row"
    )


def run(summaries: Iterable[Path], inventory: Path, known_path: Path, specs_root: Path) -> int:
    try:
        rows = read_inventory(inventory.read_text(encoding="utf-8"))
    except OSError as error:
        raise ReadError(f"{inventory}: cannot read the inventory: {error}") from error
    try:
        known_text = known_path.read_text(encoding="utf-8")
    except OSError as error:
        raise ReadError(f"{known_path}: cannot read the known-disagreement list: {error}") from error
    known = read_known(known_text, rows)
    homes = title_homes(specs_root)
    status = 0
    for path in summaries:
        job, label, legs = read_summary(path)
        verdict = judge(rows, job, label, legs, known, homes)
        report(verdict)
        if verdict.failures:
            status = 1
    return status


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--run-root", type=Path, help="a Feature check root holding exactly one run")
    source.add_argument("--summary", type=Path, action="append", help="a run's summary.json (repeatable)")
    parser.add_argument("--inventory", type=Path, default=INVENTORY)
    parser.add_argument("--known", type=Path, default=KNOWN)
    parser.add_argument(
        "--specs-root", type=Path, default=REPO_ROOT, help="the tree whose golden spec titles give each row's home job"
    )
    args = parser.parse_args(argv)
    try:
        summaries = [find_summary(args.run_root)] if args.run_root else args.summary
        return run(summaries, args.inventory, args.known, args.specs_root)
    except ReadError as error:
        print(f"inventory witness: READ ERROR (fail closed) -- {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
