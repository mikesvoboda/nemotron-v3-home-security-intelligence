#!/usr/bin/env python3
"""npm-audit exemption registry checker (mirrors check-trivyignore-expiry.sh).

The frontend audit gate in .github/workflows/ci.yml runs THIS instead of a bare
`npm audit --audit-level=high`: the raw audit fails open the day an advisory
arrives with no released fix, while this checker fails CLOSED and proves the
registry is honest. It reads `npm audit --json` and frontend/.npm-audit-exemptions.json
and fails when ANY of:

  1. a REVIEW BY (reviewBy) date has passed (or expires within --warn-days),
  2. a missing/malformed reviewBy on any entry,
  3. an audit finding (advisory GHSA id derived from via[].url) is NOT covered
     by an active exemption (the registry being the allowlist; an exemption
     covers a finding when its id or any entry in its "aliases" list names
     that finding's GHSA id - R76, mirroring R61's pip-checker alias fix),
  4. an exemption matches NOTHING in the current audit - neither its id nor
     any of its "aliases" (stale entry - remove it),
  5. an exempted advisory where npm reports an IN-RANGE fix path (fixAvailable
     truthy without isSemVerMajor at either the advisory or the vulnerability
     level) => a real fix shipped; the exception is invalid, take the fix.
     (npm's fix lives at the vulnerability level - e.g. the only path for the
     braces chain is a semver-major tailwindcss 3 -> 4 migration - while the
     advisory-level fixAvailable reads null; either level reporting a NON-major
     fix is the red signal.)

The gate IS this checker; it runs after npm ci (fresh lockfile-faithful tree).
Exit codes: 0 clean, 1 violations, 2 --warn-days advisory only.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

GHSA_RE = re.compile(r"/GHSA-([0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4})$")


def run_audit(frontend: Path) -> dict:
    r = subprocess.run(
        ["npm", "audit", "--json"],
        cwd=frontend,
        capture_output=True,
        text=True,
        check=False,  # exit 1 means findings exist - parsed below, not a crash
    )
    # npm exits 1 when vulns exist - that is data, not failure; exit 0 (clean)
    # and 1 (vulns) are both parseable; >=2 is a real error.
    if r.returncode not in (0, 1):
        print(f"npm audit --json failed rc={r.returncode}:\n{r.stderr[-800:]}", file=sys.stderr)
        sys.exit(1)
    try:
        loaded: dict[str, Any] = json.loads(r.stdout)
        return loaded
    except json.JSONDecodeError:
        print("npm audit --json produced unparsable output", file=sys.stderr)
        sys.exit(1)


def _fix_state(fix: Any) -> bool:
    """True when npm reports an IN-RANGE (non-major) fix path.

    npm puts the actual fix at the vulnerability level (e.g. the braces chain's
    only path is a semver-major tailwindcss 3 -> 4 migration, fixAvailable =
    {name, version, isSemVerMajor: true}) while the advisory-level fixAvailable
    reads null. Only a truthy fix WITHOUT isSemVerMajor means "just take it".
    """
    if fix is True:
        return True
    return isinstance(fix, dict) and not fix.get("isSemVerMajor")


def advisories(audit: dict) -> dict[str, dict]:
    """GHSA id -> packages/severities + in-range-fix flag across all vulns."""
    out: dict[str, dict] = {}
    for name, info in (audit.get("vulnerabilities") or {}).items():
        vuln_fix_in_range = _fix_state(info.get("fixAvailable"))
        for via in info.get("via", []):
            if not isinstance(via, dict):
                continue  # "Depends on vulnerable versions of X" edges
            url = via.get("url", "") or ""
            m = GHSA_RE.search(url)
            if not m:
                continue
            gid = f"GHSA-{m.group(1)}"
            a = out.setdefault(
                gid,
                {"packages": set(), "severities": set(), "in_range_fix": False, "titles": set()},
            )
            a["packages"].add(name)
            a["severities"].add(via.get("severity", "?"))
            a["in_range_fix"] = (
                a["in_range_fix"] or vuln_fix_in_range or _fix_state(via.get("fixAvailable"))
            )
            if via.get("title"):
                a["titles"].add(via["title"])
    return dict(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frontend", default="frontend")
    ap.add_argument("--registry", default=None)
    ap.add_argument("--warn-days", type=int, default=14)
    ap.add_argument(
        "--base-frontend",
        default=None,
        help="[r291] gate mode: the PR's base tree checkout. Given, the checker "
        "audits BOTH trees in one process (a fake npm on PATH per side) and "
        "fails only on a finding the change ADDS - unexempted at the head and "
        "not unexempted at the base, keyed by advisory id and package.",
    )
    ap.add_argument("--base-registry", default=None, help="registry snapshot of the base tree")
    args = ap.parse_args()
    if args.base_frontend and not args.base_registry:
        print(
            "--base-frontend without --base-registry: the delta adjudicates "
            "BOTH sides, so the base needs its own registry snapshot",
            file=sys.stderr,
        )
        return 1

    # full_report = "print today's per-violation report". In full-lockfile
    # mode that is the ONLY side, so it always reports; in gate mode the head
    # side stays quiet (its shared-violation chatter is not allowed to fail
    # the delta) and the base side stays quiet too (its violations are not
    # the change's fault; only its UNADJUDICABLE state fails the delta).
    if not args.base_frontend:
        head = adjudicate_front(
            Path(args.frontend),
            args.registry,
            args.warn_days,
            full_report=True,
        )
        return head.rc

    # Gate mode. STRICT COVERAGE on both sides (r291 security pass): a
    # finding whose ONLY covering entry itself violates today's rules does
    # NOT count as covered - it lands in `unexempted`. Without this, a PR
    # adding a vulnerable dependency green-lights whenever a pre-existing
    # dead entry (expired REVIEW BY, premise broken) nominally matches its
    # advisory: the PR never touches the registry, yet the head side's
    # unexempted set shrinks instead of growing. With strict coverage on
    # BOTH sides, the same dead entry plus its pre-existing finding on the
    # base keeps case 5 green (the base carries the same strict-unexempted
    # key), while the resurrection shape - no base finding, head finding
    # behind a dead entry - goes red. The base side's VIOLATIONS still stay
    # green: entry-level violations are text-diffed separately below.
    head = adjudicate_front(
        Path(args.frontend),
        args.registry,
        args.warn_days,
        full_report=False,
        strict_coverage=True,
    )

    # The base side's violations are NOT the change's fault: a pre-existing
    # expired REVIEW BY or pre-existing unexempted finding prints and passes
    # (package case 5). The one base-side condition that still fails closed is
    # UNADJUDICABLE - an unparsable base audit or a missing/malformed base
    # registry makes the delta's "was it already there?" question unanswerable
    # (package case 6, "an audit error on either side fails closed").
    base = adjudicate_front(
        Path(args.base_frontend),
        args.base_registry,
        args.warn_days,
        full_report=False,
        strict_coverage=True,
    )
    if base.unadjudicable:
        print(
            "BASE SIDE of the delta is UNADJUDICABLE (npm audit failed/unparsable or "
            "registry missing/malformed) - the gate fails closed:",
            file=sys.stderr,
        )
        return 1
    if head.unadjudicable:
        # The head's own diagnostics (MISSING registry / npm failure) already
        # printed inside its adjudicate_front call.
        return 1

    # Package case 4 vs 5, keyed by ENTRY: a registry violation reddens the
    # delta only when the change ADDED or EDITED that entry - the violation
    # exists at the head and not at the base. The same violation standing on
    # both sides is the base's pre-existing state and stays green in gate mode
    # (full-lockfile mode still reds it on its own trigger).
    entry_added = head.violated_entries - base.violated_entries
    if entry_added:
        print(
            f"{len(entry_added)} registry violation(s) on entries this change "
            f"adds or edits (violation not present at the base):",
            file=sys.stderr,
        )
        for v in sorted(entry_added):
            print(f"  - {v}", file=sys.stderr)
        return 1

    # Package cases 1/2/3: findings keyed (GHSA id, package). npm's audit is
    # alias-blind (R76: aliases live registry-side only), so the raw GHSA id
    # IS the canonical key on both sides - no alias collapse needed here.
    added = head.unexempted - base.unexempted
    if added:
        print(
            f"{len(added)} npm-audit finding(s) this change ADDS "
            f"(unexempted at the head, not unexempted at the base):",
            file=sys.stderr,
        )
        for gid, pkg in sorted(added):
            print(f"  - {gid} on {pkg} is UNEXEMPTED", file=sys.stderr)
        return 1
    # r291 security pass, verdict hygiene: the delta's verdict is about what
    # the change ADDS. Shared pre-existing warnings do not fail the delta,
    # but they print in the OK line so the log never says "OK" beside a red
    # exit code (head.rc's full-lockfile semantics - 2 on warns-only - used
    # to leak through here).
    warn_note = f", {head.warnings} shared expiry warning(s)" if head.warnings else ""
    print(
        f"npm-audit delta OK: {len(head.unexempted)} finding(s) shared with the "
        f"base, none added by the change{warn_note} (full-lockfile mode still "
        f"audits the lock on main on its own trigger)"
    )
    return 0


@dataclass
class Verdict:
    """One tree's full adjudication, reusable by both modes.

    full_lockfile verdict (today's): exit 1 on ANY violation, 2 on warns-only.
    Gate mode reads `unexempted` (the id+package keys of findings no active
    entry covers), `violated_entries` (one text key per registry entry that
    fails today's rules - the entry id is every message's prefix, so
    set-difference on the strings is entry-keyed AND carries the wording),
    and `unadjudicable` (npm audit failed or its JSON did not parse, or the
    registry was missing/malformed - the delta's "was it already there?"
    question is unanswerable, so a side in that state fails closed).
    """

    unexempted: set[tuple[str, str]]
    violated_entries: set[str]
    unadjudicable: bool
    rc: int
    warnings: int


def adjudicate_front(
    frontend: Path,
    registry: str | None,
    warn_days: int,
    full_report: bool,
    strict_coverage: bool = False,
) -> Verdict:
    """Adjudicate ONE tree: run npm audit there, read its registry, apply
    today's rules. `registry` None means the frontend's own
    .npm-audit-exemptions.json, exactly as before this package.

    `strict_coverage` (r291 security pass, gate mode only): an entry that
    violates today's rules does not count as covering its finding - the
    finding lands in `unexempted`. Full-lockfile mode stays lenient: there
    the violated entry already reds the run on its own.
    """
    reg_path = Path(registry) if registry else frontend / ".npm-audit-exemptions.json"
    if not reg_path.is_file():
        print(
            f"MISSING {reg_path}: the gate fails closed without the registry. "
            "Any audit finding is a red until an entry here (with REVIEW BY date) covers it.",
            file=sys.stderr,
        )
        return Verdict(set(), set(), True, 1, 0)

    reg = json.loads(reg_path.read_text())
    exceptions = reg.get("exceptions")
    if not isinstance(exceptions, list):
        print(f"{reg_path}: missing 'exceptions' array", file=sys.stderr)
        return Verdict(set(), set(), True, 1, 0)

    audit = run_audit(frontend)
    found = advisories(audit)
    today = date.today()

    errors: list[str] = []
    warns: list[str] = []
    covered: set[str] = set()
    covered_pairs: set[tuple[str, str]] = set()
    unexempted: set[tuple[str, str]] = set()
    violated_entries: set[str] = set()

    def entry_error(eid: str, msg: str) -> None:
        """A registry entry failing today's rules. The violation TEXT is the
        delta key (see Verdict.violated_entries)."""
        errors.append(msg)
        violated_entries.add(msg)

    for e in exceptions:
        eid = e.get("id", "?")
        gid = e.get("gid", eid)
        rb = e.get("reviewBy") or e.get("review_by")
        if not rb:
            entry_error(gid, f"{gid}: missing reviewBy (REVIEW BY) date")
            continue
        try:
            review = datetime.strptime(rb, "%Y-%m-%d").date()
        except ValueError:
            entry_error(gid, f"{gid}: malformed reviewBy {rb!r} (want YYYY-MM-DD)")
            continue
        errors_before = len(errors)
        if review < today:
            entry_error(gid, f"{gid}: REVIEW BY {rb} has PASSED - re-review, fix, or remove")
        elif review <= today + timedelta(days=warn_days):
            warns.append(f"{gid}: REVIEW BY {rb} expires within {warn_days}d")

        # R76 (R61's twin): an exemption naming ANY alias of a reported advisory
        # counts as matching it, so id drift (a GHSA reassigned, an advisory
        # also published under another GHSA) cannot double-redden the pair -
        # stale entry + UNEXEMPTED finding - and let the advisory slip past the
        # allowlist. npm's audit side is alias-blind: `npm audit --json` emits
        # advisories only as the single GHSA URL in via[].url (no aliases
        # array, unlike pip-audit), so the audit-side second look of R61 is
        # structurally impossible here and every alias must be spelled out in
        # the entry's "aliases" list. Exact-id logic, not fuzzy: the
        # package-attribution check below still adjudicates.
        # Prefer the entry's OWN id when the audit reports it: an entry whose
        # aliases over-list (naming a second, genuinely distinct reported
        # advisory) then adjudicates identically on every run — a bare
        # next(...) over the set would pick by string-hash order, and the same
        # red input would print different violations on different seeds.
        ids = {gid, *(e.get("aliases") or [])}
        hit = gid if gid in found else next((i for i in sorted(ids) if i in found), None)
        if hit is None:
            entry_error(
                gid,
                f"{gid}: registered but NO current audit finding matches - stale, remove it",
            )
            continue
        a = found[hit]
        # Strict coverage (r291 security pass): the entry covers its finding
        # only when the entry itself passed every rule above. An expired or
        # premise-broken entry leaves the finding unexempted, so the gate
        # delta cannot be green-lit by a dead entry's nominal match.
        if not strict_coverage or len(errors) == errors_before:
            covered.add(hit)
            # r291 security re-pass, residual A: coverage is per (gid,
            # package) in gate mode. npm attributes chain advisories to every
            # dependent package (the braces advisory is a via on chokidar,
            # fast-glob, knip ...), so one entry naming `braces` must not
            # cover the advisory on a NEW package a PR adds - the delta key
            # is (gid, package) exactly so that addition is visible. A bare
            # entry naming no package stays a whole-advisory carve-out.
            if strict_coverage:
                named = e.get("package")
                matched = (
                    set(a["packages"])
                    if named is None
                    else {named}
                    if named in a["packages"]
                    else set()
                )
                for p in matched:
                    covered_pairs.add((hit, p))
        if a["in_range_fix"]:
            entry_error(
                gid,
                f"{gid}: exemption premise broken - npm reports an in-range fix "
                f"(sanctioned premise is 'the only fix path is a semver-major migration'); "
                f"apply the fix and drop this entry",
            )
        pkg = e.get("package")
        if pkg and pkg not in a["packages"]:
            entry_error(
                gid,
                f"{gid}: registered for {pkg!r}, audit attributes it to {sorted(a['packages'])}",
            )

    for gid, a in found.items():
        if gid not in covered:
            sev = ",".join(sorted(a["severities"]))
            errors.append(f"{gid}: audit finding ({sev}) on {sorted(a['packages'])} is UNEXEMPTED")
            for pkg in a["packages"]:
                # The delta key: id + each package the advisory is reported
                # against. Package attribution is how the base/head compare
                # distinguishes "the advisory moved to another package" from
                # "the advisory was here all along".
                unexempted.add((gid, pkg))
        elif strict_coverage:
            # r291 security re-pass, residual A: the advisory is covered, but
            # in gate mode coverage is per (gid, package) - a package the
            # entry never named is still an unexempted finding on that
            # package, so it lands in the delta set with the same message.
            for pkg in sorted(set(a["packages"]) - {q for (g, q) in covered_pairs if g == hit}):
                sev = ",".join(sorted(a["severities"]))
                errors.append(f"{gid}: audit finding ({sev}) on ['{pkg}'] is UNEXEMPTED")
                unexempted.add((gid, pkg))

    if full_report:
        for w in warns:
            print(f"WARN: {w}")
        if errors:
            print(f"{len(errors)} npm-audit exemption violation(s):", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
        else:
            print(
                f"npm-audit exemptions OK: {len(exceptions)} active, "
                f"{len(found)} advisories all covered, no expiry within {warn_days}d"
            )
    rc = 1 if errors else (2 if warns else 0)
    return Verdict(unexempted, violated_entries, False, rc, len(warns))


if __name__ == "__main__":
    sys.exit(main())
