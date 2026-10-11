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
from datetime import date, datetime, timedelta
from pathlib import Path

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
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        print("npm audit --json produced unparsable output", file=sys.stderr)
        sys.exit(1)


def _fix_state(fix) -> bool:
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
    args = ap.parse_args()

    frontend = Path(args.frontend)
    reg_path = Path(args.registry) if args.registry else frontend / ".npm-audit-exemptions.json"
    if not reg_path.is_file():
        print(
            f"MISSING {reg_path}: the gate fails closed without the registry. "
            "Any audit finding is a red until an entry here (with REVIEW BY date) covers it.",
            file=sys.stderr,
        )
        return 1

    reg = json.loads(reg_path.read_text())
    exceptions = reg.get("exceptions")
    if not isinstance(exceptions, list):
        print(f"{reg_path}: missing 'exceptions' array", file=sys.stderr)
        return 1

    audit = run_audit(frontend)
    found = advisories(audit)
    today = date.today()

    errors: list[str] = []
    warns: list[str] = []
    covered: set[str] = set()

    for e in exceptions:
        eid = e.get("id", "?")
        gid = e.get("gid", eid)
        rb = e.get("reviewBy") or e.get("review_by")
        if not rb:
            errors.append(f"{gid}: missing reviewBy (REVIEW BY) date")
            continue
        try:
            review = datetime.strptime(rb, "%Y-%m-%d").date()
        except ValueError:
            errors.append(f"{gid}: malformed reviewBy {rb!r} (want YYYY-MM-DD)")
            continue
        if review < today:
            errors.append(f"{gid}: REVIEW BY {rb} has PASSED - re-review, fix, or remove")
        elif review <= today + timedelta(days=args.warn_days):
            warns.append(f"{gid}: REVIEW BY {rb} expires within {args.warn_days}d")

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
            errors.append(
                f"{gid}: registered but NO current audit finding matches - stale, remove it"
            )
            continue
        covered.add(hit)
        a = found[hit]
        if a["in_range_fix"]:
            errors.append(
                f"{gid}: exemption premise broken - npm reports an in-range fix "
                f"(sanctioned premise is 'the only fix path is a semver-major migration'); "
                f"apply the fix and drop this entry"
            )
        pkg = e.get("package")
        if pkg and pkg not in a["packages"]:
            errors.append(
                f"{gid}: registered for {pkg!r}, audit attributes it to {sorted(a['packages'])}"
            )

    for gid, a in found.items():
        if gid not in covered:
            sev = ",".join(sorted(a["severities"]))
            errors.append(f"{gid}: audit finding ({sev}) on {sorted(a['packages'])} is UNEXEMPTED")

    for w in warns:
        print(f"WARN: {w}")
    if errors:
        print(f"{len(errors)} npm-audit exemption violation(s):", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print(
        f"npm-audit exemptions OK: {len(exceptions)} active, "
        f"{len(found)} advisories all covered, no expiry within {args.warn_days}d"
    )
    return 2 if warns else 0


if __name__ == "__main__":
    sys.exit(main())
