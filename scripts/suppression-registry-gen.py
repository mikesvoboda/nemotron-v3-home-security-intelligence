#!/usr/bin/env python3
"""Regenerate .github/suppression-registry.yml from suppression-census.py --locations.

WP1.2's generator, committed so the registry stays machine-mintable: the census
mints ids, this file mints kinds/tracking/expires via the rules below, and CI's
ratchet (WP1.3) diffs the result against the committed registry. Run with
--check to fail (exit 1) on drift instead of writing.

kind classification is deliberately simple (reason-text + per-category
defaults); ambiguous sites are resolved by reading the guard at the site and
then encoding the verdict here, so the registry is regenerable rather than
hand-tended.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY = REPO_ROOT / ".github" / "suppression-registry.yml"
HEADER = REPO_ROOT / ".github" / "suppression-registry-header.txt"

ENV_RE = re.compile(
    r"not installed|not available|not found|only available|non-root|Windows|"
    r"TEST_DATABASE_URL|DATABASE_URL|service not available|nvidia|timed out|"
    r"returned error|Could not parse|require.*permissions|requires? a reachable|"
    r"cannot test missing package|filesystem|GPU-dependent|Refresh blocked|"
    r"not in compose|not found at|may not be applicable|No nginx configuration|"
    r"using memray tests instead|CUDA|pandas",
    re.I,
)
DEFECT_RE = re.compile(r"shipped defect", re.I)
RETIRED_RE = re.compile(
    r"moved to|see test_|now uses|uses old |placeholder for future|not alembic|"
    r"mocking mismatch|misnamed test-infra|zero-byte|genuinely disabled",
    re.I,
)
FLAKY_RE = re.compile(r"flaky", re.I)
TRACK_RE = re.compile(r"(NEM-\d+|R-[A-Z0-9][A-Z0-9-]*)")

EXPIRES = {
    "defect": "2026-10-15",
    "flaky": "2026-10-15",
    "todo": "2026-12-31",
    "retired": "2026-12-31",
    "quarantine": "2026-12-31",
    "environment": None,
    "scoped": None,
}
EXEMPT = ("environment", "scoped")
OWNER = "mikesvoboda"


def family(reason: str) -> str:
    r = (reason or "").lower()
    if "onvif" in r or "ptz" in r or "encoder" in r or "stream" in r:
        return "UNTRACKED:ONVIF-SUITES"
    if "performance rest" in r:
        return "NEM-1900"
    if "soft-delete" in r:
        return "UNTRACKED:SOFT-DELETE-FILTERING"
    if "token refresh" in r:
        return "UNTRACKED:WEBSOCKET-TOKEN-REFRESH"
    if "session invalidation" in r:
        return "UNTRACKED:SESSION-INVALIDATION"
    if "auth router" in r or "tdd red" in r:
        return "UNTRACKED:AUTH-ROUTE-IMPLEMENTATION"
    if "rate limiting" in r:
        return "UNTRACKED:RATE-LIMIT-SPEC"
    if "dwell" in r:
        return "UNTRACKED:DWELL-THRESHOLD-SUPERSEDED"
    if "app initialization" in r:
        return "UNTRACKED:APPINIT-TIMING"
    if "moved to test_model_management" in r:
        return "UNTRACKED:MODEL-MANAGEMENT-MOVED"
    if "mocking mismatch" in r:
        return "UNTRACKED:SETUPGUARD-MOCK-MISMATCH"
    if "coverage" in r:
        return "UNTRACKED:COVERAGE-OMIT"
    return "UNTRACKED:GENERAL"


def classify(cat: str, item: dict) -> str:
    reason = item["reason"] or ""
    if cat == "pytest_skip_imperative":
        f = item["id"].rsplit(":", 1)[0]
        # The only two imperative TODOs (guard read site by site in WP1.2):
        if f.endswith("test_auth_routes.py") or f.endswith("test_preview_api.py"):
            return "todo"
        return "environment"
    if cat == "excluded_test_trees":
        return "scoped"
    if cat == "collection_allowlist":
        return "retired"
    if cat == "coverage_omit":
        return "todo"
    if cat == "frontend_quarantine":
        return "quarantine"
    if cat == "frontend_skip":
        return "todo"
    if DEFECT_RE.search(reason):
        return "defect"
    if FLAKY_RE.search(reason):
        return "flaky"
    if RETIRED_RE.search(reason):
        return "retired"
    if ENV_RE.search(reason):
        return "environment"
    return "todo"


def tracking_for(kind: str, item: dict, cat: str) -> str | None:
    reason = item["reason"] or ""
    if kind in EXEMPT:
        return "nightly-full-gate.yml" if kind == "scoped" else None
    if cat == "frontend_quarantine":
        return "R-T7-VITEST"
    m = TRACK_RE.search(reason)
    if m:
        return m.group(1)
    return family(reason)


def build(loc: dict) -> dict:
    out: dict = {"flake_allowlist": [], "frontend_only": [], "frontend_todo": []}
    for cat, items in sorted(loc.items()):
        rows = []
        for it in items:
            kind = classify(cat, it)
            rows.append(
                {
                    "id": it["id"],
                    "kind": kind,
                    "owner": OWNER,
                    "tracking": tracking_for(kind, it, cat),
                    "expires": EXPIRES[kind],
                    "reason": it["reason"] or None,
                }
            )
        out[cat] = sorted(rows, key=lambda x: x["id"])
    return out


def render(reg: dict) -> str:
    buf = io.StringIO()
    for cat in ("flake_allowlist", "frontend_only", "frontend_todo"):
        yaml.dump({cat: reg[cat]}, buf, sort_keys=False)
    for cat in sorted(
        k for k in reg if k not in ("flake_allowlist", "frontend_only", "frontend_todo")
    ):
        if reg[cat]:
            yaml.dump({cat: reg[cat]}, buf, sort_keys=False, allow_unicode=True, width=110)
    return HEADER.read_text() + buf.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail on drift, write nothing")
    ap.add_argument(
        "--only",
        default=None,
        help="comma-separated categories (WP1.2's one-category-per-commit staging); "
        "the always-present empty categories are kept",
    )
    args = ap.parse_args()

    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "suppression-census.py"), "--locations"],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
    )
    loc = json.loads(proc.stdout)
    if args.only:
        wanted = {c.strip() for c in args.only.split(",")}
        unknown = wanted - set(loc)
        if unknown:
            print(f"unknown categories: {sorted(unknown)}", file=sys.stderr)
            return 2
        loc = {c: items for c, items in loc.items() if c in wanted}
    text = render(build(loc))
    if args.check:
        # Semantic, not byte, comparison: pre-commit's prettier hook owns YAML
        # formatting and reformats the committed file (indent/quote/wrap), so a
        # text diff would drift on every unrelated reformat. Registry data is
        # machine-minted here; the census+rules ARE the source of truth.
        try:
            current = yaml.safe_load(REGISTRY.read_text())
        except OSError, yaml.YAMLError:
            print(f"{REGISTRY} absent/unparseable", file=sys.stderr)
            return 1
        if current != yaml.safe_load(text):
            print(
                "suppression-registry.yml DRIFTS from the census+rules "
                "(run scripts/suppression-registry-gen.py)",
                file=sys.stderr,
            )
            return 1
        return 0
    REGISTRY.write_text(text)
    print(f"wrote {REGISTRY}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
