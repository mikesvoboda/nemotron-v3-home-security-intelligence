#!/usr/bin/env python3
"""The suppression ratchet (WP1.3): counts may only FALL.

Three committed artifacts, one gate:

  .github/suppression-baseline.json   per-category counts — the ratchet's
                                      teeth. Decreases lower automatically
                                      with --update; an increase is only
                                      legitimate with a registry entry for
                                      every new id AND a hand-raised
                                      baseline in the same commit (--update
                                      refuses to raise — the adjudication
                                      must be a human's diff).
  .github/suppression-registry.yml    every surviving suppression, one entry
                                      per census id, owner+kind+expiry per
                                      the registry header's schema. An id
                                      without an entry fails naming the id;
                                      an entry without an id is STALE and
                                      fails too (a zombie launders the next
                                      re-addition). Entry fields (kind/owner;
                                      tracking for non-exempt kinds) are
                                      schema-checked here so CI never enforces
                                      against an unparseable adjudication.
  scripts/suppression-census.py       the measurement, re-run here — the
                                      registry is only as honest as the census.

CI wiring: collection-sanity job. Done-when: adding an unregistered
@pytest.mark.skip fails CI (pinned by test_increase_without_registry_entry_fails
AND test_real_tree_ratchet_is_green).

WP1.4's expiry check joins this script (same gate, one job).

Usage:
    ./scripts/ratchet-check.py              # check (exit 1 on any violation)
    ./scripts/ratchet-check.py --update     # commit decreases to the baseline
    ./scripts/ratchet-check.py --root DIR   # check another tree (fixtures)
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT_DEFAULT = Path(__file__).resolve().parent.parent

# Kinds the spec exempts (see registry header): `environment` carries neither
# tracking nor expiry; `scoped` names its schedule file but carries no date.
# Every other kind is an adjudication: tracking required (WP1.3) and an ISO
# expiry whose lapse FAILS the build naming the owner (WP1.4 — "It does not
# warn, and it does not silently lapse").
EXEMPT_KINDS = ("environment", "scoped")
REQUIRED_FIELDS = ("id", "kind", "owner")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

CENSUS_ERRORS = (subprocess.SubprocessError, OSError, json.JSONDecodeError, ValueError)


def census_locations(root: Path) -> dict[str, list[dict]]:
    # The census's default root derives from ITS __file__, not cwd — pass the
    # tree explicitly or fixture runs would silently census the real repo.
    proc = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).parent / "suppression-census.py"),
            "--locations",
            "--root",
            str(root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f"census failed (rc={proc.returncode}):\n{proc.stderr[-800:]}")
    loc: dict[str, list[dict]] = json.loads(proc.stdout)
    return loc


def load_state(root: Path) -> tuple[dict[str, int], dict[str, list[dict]]]:
    bl_path = root / ".github/suppression-baseline.json"
    rg_path = root / ".github/suppression-registry.yml"
    try:
        baseline = json.loads(bl_path.read_text())
        registry = yaml.safe_load(rg_path.read_text()) or {}
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as e:
        raise SystemExit(f"cannot read ratchet state: {e}") from e
    if not isinstance(baseline, dict) or not isinstance(registry, dict):
        raise SystemExit("ratchet state malformed: baseline/registry must be objects")
    return baseline, registry


def check(root: Path, update: bool, today: dt.date) -> int:
    loc = census_locations(root)
    baseline, registry = load_state(root)
    errors: list[str] = []

    # 1. structural schema — a malformed entry is not an adjudication.
    entry_ids: dict[str, set[str]] = {}
    for cat, rows in registry.items():
        for row in rows or []:
            if not isinstance(row, dict) or any(row.get(f) in (None, "") for f in REQUIRED_FIELDS):
                errors.append(
                    f"REGISTRY {cat}: entry {row.get('id', row)!r} missing required "
                    f"field(s): {[f for f in REQUIRED_FIELDS if row.get(f) in (None, '')]}"
                )
                continue
            kind = row["kind"]
            if kind not in (*EXEMPT_KINDS, "todo", "quarantine", "flaky", "retired", "defect"):
                errors.append(f"REGISTRY {cat}: {row['id']}: unknown kind {kind!r}")
                entry_ids.setdefault(cat, set()).add(row["id"])
                continue
            # exemption integrity: an exemption is a CLASSIFICATION, and a
            # field that contradicts it means the classification is wrong (or
            # decoration that no rule would ever enforce).
            if kind == "environment" and row.get("tracking") not in (None, ""):
                errors.append(
                    f"REGISTRY {cat}: {row['id']}: kind=environment requires null "
                    "tracking (a tracked finding is a todo/defect, not an exemption)"
                )
            if kind in EXEMPT_KINDS and row.get("expires") not in (None, ""):
                errors.append(
                    f"REGISTRY {cat}: {row['id']}: kind={kind} requires null expires "
                    "(exempt kinds have no deadline — an unenforced date is decoration)"
                )
            if kind not in EXEMPT_KINDS:
                if not row.get("tracking"):
                    errors.append(
                        f"REGISTRY {cat}: {row['id']}: kind={kind} requires a tracking ref"
                    )
                # 2. WP1.4 expiry — expired means BROKEN, not lapsed quietly.
                expires = row.get("expires")
                if expires in (None, ""):
                    errors.append(
                        f"REGISTRY {cat}: {row['id']}: kind={kind} requires expires "
                        "(ISO YYYY-MM-DD) — kind=environment/scoped is the only exemption"
                    )
                elif not (isinstance(expires, str) and ISO_DATE_RE.match(expires)):
                    errors.append(
                        f"REGISTRY {cat}: {row['id']}: expires={expires!r} is not ISO "
                        "YYYY-MM-DD — an unparseable date cannot be enforced"
                    )
                else:
                    try:
                        deadline = dt.date.fromisoformat(expires)
                    except ValueError:
                        errors.append(
                            f"REGISTRY {cat}: {row['id']}: expires={expires!r} is not a real date"
                        )
                    else:
                        if deadline < today:
                            errors.append(
                                f"EXPIRED {cat}: {row['id']} expired {expires} — owner "
                                f"{row['owner']} (tracking {row.get('tracking')}): fix it, "
                                "or adjudicate a NEW expiry in a reviewed commit; the "
                                "gate does not warn and does not silently lapse"
                            )
            entry_ids.setdefault(cat, set()).add(row["id"])

    # 2. per-category: ids vs entries, counts vs baseline.
    new_baseline = dict(baseline)
    for cat, items in loc.items():
        ids = {it["id"] for it in items}
        if len(ids) != len(items):  # census self-check: duplicate ids would launder
            seen: set[str] = set()
            dupes: set[str] = set()
            for it in items:
                (dupes if it["id"] in seen else seen).add(it["id"])
            errors.append(f"CENSUS {cat}: duplicate ids {sorted(dupes)}")
        entries = entry_ids.get(cat, set())
        # a category may not hide: baseline and registry must know it exists
        if cat not in baseline:
            errors.append(f"BASELINE: category {cat} absent from suppression-baseline.json")
        if cat not in registry:
            errors.append(f"REGISTRY: category {cat} absent from suppression-registry.yml")
        for missing in sorted(ids - entries):
            errors.append(
                f"UNREGISTERED {cat}: {missing} — add it to "
                f".github/suppression-registry.yml (kind+owner+expiry) or remove the suppression"
            )
        for stale in sorted(entries - ids):
            errors.append(
                f"STALE {cat}: registry entry {stale} has no census site — the "
                "suppression is gone; delete the entry (registry entries must not outlive what they license)"
            )
        count = len(ids)
        allowed = baseline.get(cat, 0)
        if count > allowed:
            errors.append(
                f"RATCHET {cat}: {count} > baseline {allowed} — counts may only "
                "fall; an increase needs a registry entry for every new id AND "
                "the baseline raised in this same commit (a human reviews that diff)"
            )
        elif count < allowed:
            new_baseline[cat] = count  # the ratchet only ever falls
    # registry categories the census no longer knows (typo'd name)
    for cat in sorted(set(registry) - set(loc)):
        errors.append(f"REGISTRY: category {cat} is not a census category")

    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        print(
            f"\nratchet: {len(errors)} violation(s) — see scripts/ratchet-check.py "
            "for the three artifacts this gate diffs",
            file=sys.stderr,
        )
        return 1

    if update:
        # decreases-only by construction: this branch is unreachable with any
        # count above baseline (that's an error above); never an increase.
        path = root / ".github/suppression-baseline.json"
        lowered = {k: new_baseline.get(k, v) for k, v in baseline.items()}
        if lowered != baseline:
            path.write_text(json.dumps(lowered, indent=2, sort_keys=True) + "\n")
            moved = {k: (baseline[k], v) for k, v in lowered.items() if baseline[k] != v}
            print(f"baseline lowered: {moved}")
        else:
            print("baseline already at the floor")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Suppression ratchet: counts may only fall (WP1.3)")
    ap.add_argument("--root", default=str(REPO_ROOT_DEFAULT), help="tree to check (fixtures)")
    ap.add_argument(
        "--update",
        action="store_true",
        help="write decreases into the baseline (never an increase; that needs a hand edit)",
    )
    ap.add_argument(
        "--today",
        default=None,
        help="override the expiry clock (YYYY-MM-DD) — tests and deadline drills; CI never passes it",
    )
    args = ap.parse_args()
    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    return check(Path(args.root).resolve(), args.update, today)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except CENSUS_ERRORS as e:
        print(f"ratchet-check: {e}", file=sys.stderr)
        sys.exit(2)
