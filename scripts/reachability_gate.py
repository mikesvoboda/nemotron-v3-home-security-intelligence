#!/usr/bin/env python3
"""O3.4 — Reachability gates in CI (Python O2.3 + frontend Knip F3.2).

Enforces both reachability gates required by `docs/uplevel/packages/ops.md` §O3.4
and owner ruling 257 (`#6854` record `6250472120`):

1. Python reachability (`O2.3` / `scripts/reachability.py`):
   Fails when any new non-shipping Python module under `backend/`, `ai/`, or
   `synthbench/` appears without a `scripts/reachability/keep.toml` entry
   (where "new" means not in the pre-`B3.2` baseline recorded at `F3.2`'s merge),
   or when `scripts/reachability.py` reports an un-allowlisted first-party
   dynamic import or a missing declared entry point.
2. Frontend reachability (`F3.2` / `npx knip --production --reporter json`):
   Fails when `knip --production` finds a new unused frontend file or a new
   unused export not in the baseline `F3.2` (`#7246`) recorded at its merge
   (`ca0e5a081`).

Usage:
    uv run python -m scripts.reachability_gate
    uv run python -m scripts.reachability_gate --python
    uv run python -m scripts.reachability_gate --knip [--knip-json path/to/knip.json]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
REPO_ROOT = _HERE.parent
DEFAULT_BASELINE = _HERE / "reachability" / "baseline.json"
DEFAULT_ENTRIES = _HERE / "reachability" / "entry_points.toml"
DEFAULT_KEEP = _HERE / "reachability" / "keep.toml"
DEFAULT_CANDIDATE_DIRS = ["backend", "ai", "synthbench"]


def _resolve_file(path: Path, label: str) -> Path:
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise SystemExit(f"reachability_gate: {label} file not found: {resolved}")
    return resolved


def _resolve_dir(path: Path, label: str) -> Path:
    resolved = Path(path).resolve()
    if not resolved.is_dir():
        raise SystemExit(f"reachability_gate: {label} directory not found: {resolved}")
    return resolved


def _load_reachability_module() -> Any:
    reach_path = _resolve_file(_HERE / "reachability.py", "reachability.py")
    spec = importlib.util.spec_from_file_location("reachability", reach_path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"reachability_gate: unable to load {reach_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_baseline(path: Path = DEFAULT_BASELINE) -> dict[str, Any]:
    resolved = _resolve_file(path, "baseline")
    try:
        data = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"reachability_gate: invalid baseline JSON {resolved}: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise SystemExit(f"reachability_gate: unsupported baseline schema in {resolved}")
    return data


def check_python_reachability(
    root: Path = REPO_ROOT,
    baseline: dict[str, Any] | None = None,
    *,
    entries_path: Path = DEFAULT_ENTRIES,
    keep_path: Path = DEFAULT_KEEP,
    candidate_dirs: list[str] | None = None,
) -> list[str]:
    """Return findings for new non-shipping Python modules or broken reachability inputs."""
    resolved_root = _resolve_dir(root, "repo root")
    if baseline is None:
        baseline = load_baseline(DEFAULT_BASELINE)
    reach = _load_reachability_module()
    entries, allow = reach.load_entry_points(_resolve_file(entries_path, "entry_points.toml"))
    keep = reach.load_keep(_resolve_file(keep_path, "keep.toml"))
    dirs = list(candidate_dirs) if candidate_dirs is not None else list(DEFAULT_CANDIDATE_DIRS)
    out = reach.analyze(
        resolved_root,
        entries=entries,
        candidate_dirs=dirs,
        keep=keep,
        dynamic_allow=allow,
    )

    baseline_py = baseline.get("python") or {}
    allowed_not_shipping = {str(m) for m in (baseline_py.get("not_shipping") or [])}

    findings: list[str] = []
    for row in out.get("not_shipping") or []:
        mod = str(row["module"])
        lines = int(row["lines"])
        if mod not in allowed_not_shipping:
            findings.append(
                f"new non-shipping Python module without a keep.toml entry: {mod} ({lines} lines)"
            )
    for u in out.get("unresolved") or []:
        findings.append(f"unresolved first-party dynamic import: {u['module']} -> {u['target']}")
    for e in out.get("entry_missing") or []:
        findings.append(f"declared entry point missing on disk: {e}")
    return findings


def parse_knip_json(raw: str) -> dict[str, Any]:
    """Parse and validate `knip --production --reporter json` output (fail-closed)."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"knip output is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("knip JSON root must be an object")
    files = data.get("files")
    issues = data.get("issues")
    if not isinstance(files, list) or not all(isinstance(f, str) for f in files):
        raise ValueError("knip JSON '.files' must be a list of strings")
    if not isinstance(issues, list) or not all(
        isinstance(i, dict) and isinstance(i.get("file"), str) for i in issues
    ):
        raise ValueError("knip JSON '.issues' must be a list of issue objects with 'file'")
    return data


def run_knip_production(frontend_dir: Path) -> dict[str, Any]:
    """Run `npx knip --production --reporter json` inside `frontend_dir`."""
    resolved_fe = _resolve_dir(frontend_dir, "frontend")
    proc = subprocess.run(
        ["npx", "knip", "--production", "--reporter", "json"],
        cwd=str(resolved_fe),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode not in (0, 1):
        detail = (proc.stderr or proc.stdout or "").strip()[:500]
        raise ValueError(f"npx knip exited with status {proc.returncode}: {detail}")
    return parse_knip_json(proc.stdout)


def check_knip_reachability(
    knip_data: dict[str, Any],
    baseline: dict[str, Any],
) -> list[str]:
    """Return findings for new unused frontend files or exports outside the F3.2 baseline."""
    baseline_knip = baseline.get("knip") or {}
    allowed_files = {str(f) for f in (baseline_knip.get("files") or [])}
    raw_exports = baseline_knip.get("exports") or {}
    allowed_exports: dict[str, set[str]] = {
        str(k): {str(exp) for exp in v} for k, v in raw_exports.items() if isinstance(v, list)
    }

    findings: list[str] = []
    current_files = sorted({str(f) for f in (knip_data.get("files") or [])})
    for f in current_files:
        if f not in allowed_files:
            findings.append(f"new unused frontend file (knip --production): {f}")

    for issue in knip_data.get("issues") or []:
        file_path = str(issue["file"])
        file_allowed = allowed_exports.get(file_path, set())
        for exp in issue.get("exports") or []:
            if not isinstance(exp, dict) or not isinstance(exp.get("name"), str):
                continue
            name = exp["name"]
            if name not in file_allowed:
                line = exp.get("line")
                suffix = f" (line {line})" if line is not None else ""
                findings.append(
                    f"new unused frontend export (knip --production): {file_path}: {name}{suffix}"
                )
    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--python", action="store_true", help="run only the Python O2.3 check")
    ap.add_argument("--knip", action="store_true", help="run only the frontend Knip F3.2 check")
    ap.add_argument("--root", type=Path, default=REPO_ROOT, help="repository root")
    ap.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE, help="baseline JSON path")
    ap.add_argument("--entries", type=Path, default=DEFAULT_ENTRIES, help="entry_points.toml path")
    ap.add_argument("--keep", type=Path, default=DEFAULT_KEEP, help="keep.toml path")
    ap.add_argument(
        "--candidate-dir",
        action="append",
        dest="candidate_dirs",
        default=None,
        help="candidate directory (repeatable; defaults to backend, ai, synthbench)",
    )
    ap.add_argument(
        "--knip-json",
        type=Path,
        default=None,
        help="read pre-collected `knip --production --reporter json` output from this file",
    )
    args = ap.parse_args(argv)

    run_py = args.python or not args.knip
    run_knip = args.knip or not args.python

    baseline = load_baseline(args.baseline)
    all_findings: list[str] = []

    if run_py:
        py_findings = check_python_reachability(
            args.root,
            baseline,
            entries_path=args.entries,
            keep_path=args.keep,
            candidate_dirs=args.candidate_dirs,
        )
        all_findings.extend(py_findings)
        print(f"python-reachability: {len(py_findings)} new finding(s)")

    if run_knip:
        try:
            if args.knip_json is not None:
                knip_raw = _resolve_file(args.knip_json, "knip-json").read_text(encoding="utf-8")
                knip_data = parse_knip_json(knip_raw)
            else:
                knip_data = run_knip_production(_resolve_dir(args.root, "repo root") / "frontend")
        except ValueError as exc:
            print(f"ERROR: knip reachability check failed closed: {exc}", file=sys.stderr)
            return 2
        knip_findings = check_knip_reachability(knip_data, baseline)
        all_findings.extend(knip_findings)
        print(f"knip-reachability: {len(knip_findings)} new finding(s)")

    if all_findings:
        for finding in all_findings:
            print(f"FAIL: {finding}", file=sys.stderr)
        return 1

    print("OK: reachability gates passed (0 new Python or frontend findings)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
