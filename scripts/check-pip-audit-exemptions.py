#!/usr/bin/env python3
"""pip-audit exemption registry checker (mirror of check-npm-audit-exemptions.py).

The Python leg of .github/workflows/dependency-audit.yml used to run a bare
`pip-audit … --ignore-vuln CVE-…`. That shape fails OPEN in both directions:
the flag silences an advisory with no reason, no owner and no expiry, and a
STALE ignore (the advisory no longer fires at all) suppresses nothing while
still reading as "there is a carve-out here" - the CVE-2026-0994 entry added
in 91a841507 had a "Review date: 2026-01-23" comment that expired eight-plus
months before O1.8 measured, on 2026-10-09, that it no longer reproduces
(protobuf is at 7.36.1; pip-audit 2.10.1 reports zero findings WITHOUT the
flag). This checker replaces it and fails CLOSED, red when ANY of:

  1. a REVIEW BY (reviewBy) date has passed (or expires within --warn-days),
  2. a missing/malformed reviewBy on any entry,
  3. a pip-audit finding (vulnerability id) is NOT covered by an active
     exemption - the registry IS the allowlist, so without this file any
     finding at all is red,
  4. an exemption matches NOTHING in the current audit (stale entry - the
     failure mode the inline --ignore-vuln could never report; remove it),
  5. an exempted advisory that pip-audit reports WITH fix_versions (the
     sanctioned premise is "awaiting an upstream fix"; a released fix ends
     the exemption - take the bump),
  6. the advisory id a registry entry cites is not the id pip-audit reports
     for the package it names (id drift - e.g. a PYSEC/PYSEC-alias change).

Run it on an exported requirements file (the same export the audit job uses):

    uv export --no-hashes > requirements-audit.txt
    pip-audit -r requirements-audit.txt --desc -f json > /tmp/pa.json
    python3 scripts/check-pip-audit-exemptions.py --audit-json /tmp/pa.json \
        --registry .pip-audit-exemptions.json --warn-days 14

Exit codes: 0 clean, 1 violations, 2 --warn-days advisory only.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

DEFAULT_REGISTRY = ".pip-audit-exemptions.json"


def load_audit(path: Path) -> dict:
    """Read a pip-audit `-f json` report; '-' means stdin."""
    raw = sys.stdin.read() if str(path) == "-" else path.read_text()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(
            "pip-audit JSON report is unparsable - the gate fails closed "
            "(an unparsable audit must never read as a clean audit)",
            file=sys.stderr,
        )
        sys.exit(1)


def advisories(audit: dict) -> dict[str, dict]:
    """vuln id -> packages / versions / fix_versions across all dependencies.

    pip-audit's report is per-dependency: {"dependencies": [{"name","version",
    "vulns":[{"id","fix_versions",...}]}]}. One advisory can hit several
    dependencies (or the same dependency at several versions), so merge on the
    id and keep every (package, version) it was reported against.
    """
    out: dict[str, dict] = {}
    for dep in audit.get("dependencies") or []:
        name = dep.get("name", "?")
        version = dep.get("version", "?")
        for vuln in dep.get("vulns") or []:
            vid = vuln.get("id")
            if not vid:
                continue
            a = out.setdefault(
                vid,
                {"packages": set(), "fix_versions": [], "aliases": set()},
            )
            a["packages"].add(f"{name}=={version}")
            fixes = vuln.get("fix_versions") or []
            if fixes:
                a["fix_versions"] = fixes
            for alias in vuln.get("aliases") or []:
                a["aliases"].add(alias)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit-json", default="-", help="pip-audit -f json output (- for stdin)")
    ap.add_argument("--registry", default=DEFAULT_REGISTRY)
    ap.add_argument("--warn-days", type=int, default=14)
    args = ap.parse_args()

    reg_path = Path(args.registry)
    if not reg_path.is_file():
        print(
            f"MISSING {reg_path}: the gate fails closed without the registry. "
            "Any pip-audit finding is red until an entry here (with reason, "
            "owner and a REVIEW BY date) covers it.",
            file=sys.stderr,
        )
        return 1

    reg = json.loads(reg_path.read_text())
    exceptions = reg.get("exceptions")
    if not isinstance(exceptions, list):
        print(f"{reg_path}: missing 'exceptions' array", file=sys.stderr)
        return 1

    found = advisories(load_audit(Path(args.audit_json)))
    today = date.today()

    errors: list[str] = []
    warns: list[str] = []
    covered: set[str] = set()

    for e in exceptions:
        eid = e.get("id", "?")
        rb = e.get("reviewBy") or e.get("review_by")
        if not rb:
            errors.append(f"{eid}: missing reviewBy (REVIEW BY) date")
            continue
        try:
            review = datetime.strptime(rb, "%Y-%m-%d").date()
        except ValueError:
            errors.append(f"{eid}: malformed reviewBy {rb!r} (want YYYY-MM-DD)")
            continue
        if review < today:
            errors.append(f"{eid}: REVIEW BY {rb} has PASSED - re-review, fix, or remove")
        elif review <= today + timedelta(days=args.warn_days):
            warns.append(f"{eid}: REVIEW BY {rb} expires within {args.warn_days}d")

        ids = {eid, *(e.get("aliases") or [])}
        hit = next((i for i in ids if i in found), None)
        if hit is None:
            errors.append(
                f"{eid}: registered but NO current pip-audit finding matches - "
                "stale (the advisory is fixed or no longer reachable); remove it"
            )
            continue
        covered.add(hit)

        a = found[hit]
        if a["fix_versions"]:
            errors.append(
                f"{eid}: exemption premise broken - pip-audit reports fix_versions "
                f"{a['fix_versions']} (sanctioned premise is 'awaiting upstream "
                f"fix'); take the bump and drop this entry"
            )
        pkg = e.get("package")
        if pkg and not any(p.split("==", 1)[0].lower() == pkg.lower() for p in a["packages"]):
            errors.append(
                f"{eid}: registered for {pkg!r}, pip-audit attributes it to {sorted(a['packages'])}"
            )

    for vid, a in found.items():
        if vid not in covered:
            errors.append(
                f"{vid}: pip-audit finding on {sorted(a['packages'])} is UNEXEMPTED "
                f"(fix_versions={a['fix_versions'] or 'none reported'})"
            )

    for w in warns:
        print(f"WARN: {w}")
    if errors:
        print(f"{len(errors)} pip-audit exemption violation(s):", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print(
        f"pip-audit exemptions OK: {len(exceptions)} active, "
        f"{len(found)} advisories all covered, no expiry within {args.warn_days}d"
    )
    return 2 if warns else 0


if __name__ == "__main__":
    sys.exit(main())
