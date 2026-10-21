#!/usr/bin/env python3
"""Weekly per-module mutation scorer, floor checker, and history writer (WP4.3 / O3.5 / 01 M2).

mutmut 3 parks verdicts in `mutants/<source-path>.meta` (`exit_code_by_key`:
mutant-key -> pytest exit code) and publishes only ONE aggregate
(`export-cicd-stats` -> `mutants/mutmut-cicd-stats.json`). This script computes
the per-module view over the scored set (`01-mutation-policy.md` §M1/§M2):

1. **Scored set (M1):** every module in `[tool.mutmut]`'s mutation paths
   (`backend/services/` and `backend/api/routes/`, minus `do_not_mutate`) that
   **ships** per `scripts/reachability.py` (including `keep.toml` declarations).
2. **With and without accepted survivors (M3):** each scored module is scored
   both without accepted survivors (`score`) and with accepted survivors from
   `backend/tests/mutation/accepted_survivors.toml` (`score_with_accepted`).
3. **Comparable modules only:** the weekly CI job is incremental (a 240-minute
   budget that resumes across runs), so only modules whose mutants were all
   checked (`not_checked == 0`) are comparable against the previous entry.
4. **Weekly floor alert (noise band = 1.0pp):** on a per-module score drop
   beyond `NOISE_BAND_PP` (`1.0pp`, measured across the 57/58 campaign history
   runs where unchanged-source re-check drops ranged `0.1339pp` to `0.5525pp`,
   max `0.5525pp` on `osnet_loader.py`), or when a module's mutant count
   (`total`) falls while its production bytes (`source_sha256`) are unchanged,
   opens or updates one GitHub issue per module titled
   `mutation floor: <module>` listing the newly surviving mutants. The job's
   conclusion reports the job's health, never the drop.
5. **Single history writer (UR-7):** `.github/mutation-history.json` is written
   only by the weekly CI job (`GITHUB_ACTIONS=true`), keeping compacted summary
   lines (`date`, `killed_or_timeout`, `total`, `score`) for historical runs
   and full per-module entries for the most recent weekly runs (< 200 KB).

Usage:
    uv run python scripts/mutation-score.py [--root DIR]
    uv run python scripts/mutation-score.py --targets
    uv run python scripts/mutation-score.py --check-floor HISTORY.json [--dry-run] [--sync-issues]
    uv run python scripts/mutation-score.py --history .github/mutation-history.json --date YYYY-MM-DD [--sync-issues]

Tests: uv run pytest scripts/test_mutation_score.py -q
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any

REPO_ROOT_DEFAULT = Path(__file__).resolve().parent.parent
DEFAULT_SURVIVORS_REL = Path("backend/tests/mutation/accepted_survivors.toml")
REPO_HISTORY_PATH = (REPO_ROOT_DEFAULT / ".github" / "mutation-history.json").resolve()
CLASS_SEPARATOR = "ǁ"

# Measured across the 57/58 campaign history runs (11,601 unchanged-source
# module transitions, 11,498 with unchanged total): excluding the two documented
# harness incidents (run[1->2] config-invalidation wipe and run[6->7] 3-module
# coverage rc-ignore strip), only 11 unchanged-source module pairs had a negative
# delta, ranging from -0.1339pp (-1/747 on reid_service.py) to -0.5525pp (-2/362
# on osnet_loader.py; -0.7342pp if prompt_service.py in run[1->2] is included),
# and 0 drops occurred across all 9,447 unchanged-source pairs in runs 10..57.
# 1.0pp (~1.8x the 0.5525pp clean max) suppresses 1-2 mutant timeout/scheduling
# jitter while alerting on real regressions.
NOISE_BAND_PP = 1.0

HISTORY_MAX_RUNS = 60  # weekly cadence -> ~a year of runs kept in the file
HISTORY_DETAILED_RUNS = 3  # keep full per-module maps on the most recent weekly entries (< 200 KB)

# The codes the score formula cares about, as mutmut names them. The test
# file pins every pair against mutmut.stats.status_by_exit_code.
VERDICT_CODES = {
    1: "killed",
    3: "killed",  # internal error in pytest means a kill
    0: "survived",
    36: "timeout",
    255: "timeout",
    24: "timeout",
    -24: "timeout",
    152: "timeout",
    5: "no_tests",
    33: "no_tests",
    34: "skipped",
    35: "suspicious",
    37: "caught_by_type_check",
}
_KILLED = {"killed", "timeout"}  # badge: timeout counts as caught

_SHIPPING_CACHE: dict[Path, set[str] | None] = {}


def _mutmut_status_map() -> dict[int, str]:
    """mutmut's authoritative exit-code -> status map (imported, not copied)."""
    from mutmut.stats import status_by_exit_code

    return {
        int(code): str(status).replace(" ", "_")
        for code, status in status_by_exit_code.items()
        if code is not None
    }


def classify(exit_code: int | None, status_map: dict[int, str]) -> str:
    if exit_code is None:
        return "not_checked"
    return status_map.get(exit_code, "suspicious")


def _mutmut_path_knobs(root: Path) -> tuple[list[str], list[str]]:
    """[tool.mutmut] only_mutate / do_not_mutate from the root pyproject."""
    try:
        cfg = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["mutmut"]
    except OSError, KeyError, tomllib.TOMLDecodeError:
        return [], []
    return list(cfg.get("only_mutate", [])), list(cfg.get("do_not_mutate", []))


def _mutmut_excluded(rel: str, root: Path) -> bool:
    """mutmut's should_mutate() mirrored: include (if only_mutate set) and not-ignore."""
    only, dont = _mutmut_path_knobs(root)
    if only and not any(fnmatch.fnmatch(rel, p) for p in only):
        return True
    return any(fnmatch.fnmatch(rel, p) for p in dont)


def _shipping_set(root: Path) -> set[str] | None:
    """Return the M1 reachability shipping set for `root`, or None if `root` has no reachability config."""
    resolved = root.resolve()
    if resolved in _SHIPPING_CACHE:
        return _SHIPPING_CACHE[resolved]
    entries_toml = resolved / "scripts" / "reachability" / "entry_points.toml"
    keep_toml = resolved / "scripts" / "reachability" / "keep.toml"
    reach_script = REPO_ROOT_DEFAULT / "scripts" / "reachability.py"
    if not (entries_toml.is_file() and keep_toml.is_file() and reach_script.is_file()):
        _SHIPPING_CACHE[resolved] = None
        return None
    spec = importlib.util.spec_from_file_location("_reachability_for_scorer", reach_script)
    if spec is None or spec.loader is None:
        _SHIPPING_CACHE[resolved] = None
        return None
    reach = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reach)
    entries, allow = reach.load_entry_points(entries_toml)
    keep = reach.load_keep(keep_toml)
    out = reach.analyze(
        resolved,
        entries=entries,
        candidate_dirs=reach.DEFAULT_CANDIDATE_DIRS,
        keep=keep,
        dynamic_allow=allow,
    )
    shipping = set(out["shipping"])
    _SHIPPING_CACHE[resolved] = shipping
    return shipping


def _excluded_from_scored_set(rel: str, root: Path) -> bool:
    """True if `rel` is excluded by `[tool.mutmut]` or does not ship per M1."""
    if _mutmut_excluded(rel, root):
        return True
    shipping = _shipping_set(root)
    return shipping is not None and rel not in shipping


def target_modules(root: Path) -> list[str]:
    """The scored set (01 §M1/§M2, UR-3): every module under `[tool.mutmut]`'s
    mutation paths (`backend/services/` and `backend/api/routes/`) that is not
    excluded by `do_not_mutate` and that ships per `scripts/reachability.py`."""
    out = []
    for base in ("backend/services", "backend/api/routes"):
        base_dir = root / base
        if not base_dir.is_dir():
            continue
        for p in sorted(base_dir.rglob("*.py")):
            rel = p.relative_to(root).as_posix()
            if not _excluded_from_scored_set(rel, root):
                out.append(rel)
    return sorted(out)


def score(stats: dict[str, int], accepted_survivors: int = 0) -> float | None:
    tested = stats["total"] - stats["skipped"]
    if tested <= 0:
        return None
    caught = sum(stats[k] for k in _KILLED) + accepted_survivors
    return min(caught, tested) / tested * 100


def _metas(root: Path) -> list[Path]:
    mutants = root / "mutants"
    return sorted(
        p
        for p in mutants.glob("backend/**/*.py.meta")
        if "tests" not in p.relative_to(mutants).parts
        and not _excluded_from_scored_set(p.relative_to(mutants).as_posix()[: -len(".meta")], root)
    )


def repair_metas(root: Path) -> list[str]:
    """Delete torn (unparseable) .meta files AND their mutant .py copies."""
    repaired = []
    for meta_path in _metas(root):
        try:
            json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError, UnicodeDecodeError:
            meta_path.unlink()
            mutant_copy = meta_path.with_suffix("")
            if mutant_copy.exists():
                mutant_copy.unlink()
            repaired.append(meta_path.relative_to(root).as_posix())
    return repaired


def _normalize_module_name(raw: str) -> str:
    return raw.strip().removesuffix(".py").replace("/", ".").strip(".")


def _parse_key_parts(key: str) -> tuple[str, str, str, str]:
    """Return `(module, qualified_function, short_function, generated_func_name)` from a mutmut key."""
    prefix, sep, suffix = key.partition("__mutmut_")
    if not sep:
        mod, _, func = key.rpartition(".")
        return (mod, func, func, func)
    mod, _, mangled = prefix.rpartition(".")
    gen_name = f"{mangled}__mutmut_{suffix}"
    if CLASS_SEPARATOR in mangled:
        parts = mangled.split(CLASS_SEPARATOR)
        cls_name = parts[1]
        fn_name = parts[-1]
        return (mod, f"{cls_name}.{fn_name}", fn_name, gen_name)
    fn_name = mangled[2:] if mangled.startswith("x_") else mangled
    return (mod, fn_name, fn_name, gen_name)


def _restore_original_def_name(src: str, gen_name: str, short_fn: str) -> str:
    return re.sub(
        rf"^(\s*(?:async\s+def|def)\s+){re.escape(gen_name)}\b",
        rf"\1{short_fn}",
        src,
        count=1,
        flags=re.MULTILINE,
    )


def _extract_source_function_shas(py_path: Path) -> dict[str, set[str]]:
    """Map function/method names (`qual_fn` and `short_fn`) in `py_path` to their body sha256s."""
    if not py_path.is_file():
        return {}
    try:
        code = py_path.read_text(encoding="utf-8")
        lines = code.splitlines(keepends=True)
        tree = ast.parse(code, filename=str(py_path))
    except OSError, SyntaxError:
        return {}

    out: dict[str, set[str]] = {}

    def _record(name: str, digest: str) -> None:
        out.setdefault(name, set()).add(digest)

    def _walk(stmts: list[ast.stmt], cls_prefix: str = "") -> None:
        for node in stmts:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.end_lineno is None:
                    continue
                seg = "".join(lines[node.lineno - 1 : node.end_lineno])
                if not seg.endswith("\n"):
                    seg += "\n"
                sha = hashlib.sha256(seg.encode("utf-8")).hexdigest()
                qual = f"{cls_prefix}.{node.name}" if cls_prefix else node.name
                _record(node.name, sha)
                _record(qual, sha)
                if "__mutmut_" in node.name:
                    _, qf, sf, _ = _parse_key_parts(f"mod.{node.name}")
                    norm = _restore_original_def_name(seg, node.name, sf)
                    norm_sha = hashlib.sha256(norm.encode("utf-8")).hexdigest()
                    _record(node.name, norm_sha)
                    _record(qf, norm_sha)
                    _record(sf, norm_sha)
            elif isinstance(node, ast.ClassDef):
                next_cls = f"{cls_prefix}.{node.name}" if cls_prefix else node.name
                _walk(node.body, next_cls)

    _walk(tree.body)
    return out


def load_accepted_survivors(root: Path, survivors_path: Path | None = None) -> list[dict[str, str]]:
    """Load `[[survivor]]` entries from `backend/tests/mutation/accepted_survivors.toml`."""
    path = survivors_path if survivors_path is not None else (root / DEFAULT_SURVIVORS_REL)
    if not path.is_file():
        return []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except OSError, tomllib.TOMLDecodeError:
        return []
    entries = data.get("survivor", [])
    if not isinstance(entries, list):
        return []
    out: list[dict[str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        mod = _normalize_module_name(str(entry.get("module", "")))
        mutant = str(entry.get("mutant", "")).strip()
        sha = str(entry.get("body_sha256", "")).strip()
        kind = str(entry.get("kind", "")).strip()
        if mod and mutant and sha and kind in {"equivalent", "below-bar"}:
            out.append(
                {
                    "module": mod,
                    "mutant": mutant,
                    "body_sha256": sha,
                    "kind": kind,
                }
            )
    return out


def _match_module_survivors(
    rel: str,
    uncaught_keys: list[str],
    meta: dict[str, Any],
    root: Path,
    survivors: list[dict[str, str]],
) -> tuple[int, list[str]]:
    """Return `(accepted_count, unaccepted_surviving_keys)` for module `rel`."""
    dotted_mod = _normalize_module_name(rel)
    mod_entries = [e for e in survivors if e["module"] == dotted_mod]
    if not mod_entries or not uncaught_keys:
        return 0, sorted(uncaught_keys)

    src_shas = _extract_source_function_shas(root / rel)
    mut_shas = _extract_source_function_shas(root / "mutants" / rel)
    meta_shas = meta.get("body_sha256_by_key", {})
    if not isinstance(meta_shas, dict):
        meta_shas = {}

    used_indices: set[int] = set()
    unaccepted: list[str] = []
    accepted_count = 0

    for key in sorted(uncaught_keys):
        _, qual_fn, short_fn, gen_name = _parse_key_parts(key)
        candidate_shas: set[str] = set()
        if key in meta_shas and isinstance(meta_shas[key], str):
            candidate_shas.add(meta_shas[key])
        for fn_id in (qual_fn, short_fn, gen_name, key):
            candidate_shas.update(src_shas.get(fn_id, set()))
            candidate_shas.update(mut_shas.get(fn_id, set()))

        matched = False
        for idx, entry in enumerate(mod_entries):
            if idx in used_indices:
                continue
            entry_mutant = entry["mutant"]
            entry_fn = entry_mutant.split()[0] if entry_mutant else ""
            fn_ok = entry_fn in {qual_fn, short_fn, gen_name, key} or key in entry_mutant
            sha_ok = entry["body_sha256"] in candidate_shas
            if fn_ok and sha_ok:
                used_indices.add(idx)
                accepted_count += 1
                matched = True
                break
        if not matched:
            unaccepted.append(key)

    return accepted_count, unaccepted


def _source_sha256(root: Path, rel: str) -> str | None:
    src = root / rel
    if not src.is_file():
        return None
    try:
        return hashlib.sha256(src.read_bytes()).hexdigest()
    except OSError:
        return None


def aggregate(root: Path, survivors_path: Path | None = None) -> dict[str, Any]:
    status_map = _mutmut_status_map()
    mutants = root / "mutants"
    metas = _metas(root)
    if not metas:
        raise SystemExit
    survivors = load_accepted_survivors(root, survivors_path=survivors_path)
    modules = []
    stats_list: list[dict[str, int]] = []
    torn_metas = 0
    never_checked_keys = 0
    total_accepted = 0

    for meta_path in metas:
        rel = meta_path.relative_to(mutants).as_posix()[: -len(".meta")]
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError, UnicodeDecodeError:
            torn_metas += 1
            print(f"torn meta (unparseable): {rel} -- run with --repair", file=sys.stderr)
            continue
        stats = dict.fromkeys(
            (
                "killed",
                "timeout",
                "survived",
                "suspicious",
                "no_tests",
                "skipped",
                "not_checked",
                "caught_by_type_check",
                "segfault",
                "check_was_interrupted_by_user",
            ),
            0,
        )
        uncaught_keys: list[str] = []
        for key, code in meta["exit_code_by_key"].items():
            verdict = classify(code, status_map)
            stats[verdict] += 1
            if code is not None and verdict not in _KILLED and verdict != "skipped":
                uncaught_keys.append(key)
        stats["total"] = sum(stats.values())
        if stats["total"] - stats["not_checked"] == 0:
            never_checked_keys += stats["total"]
            continue
        accepted_cnt, unaccepted_survivors = _match_module_survivors(
            rel, uncaught_keys, meta, root, survivors
        )
        total_accepted += accepted_cnt
        stats_list.append(stats)
        tested = stats["total"] - stats["skipped"]
        modules.append(
            {
                "module": rel,
                **stats,
                "accepted_survivors": accepted_cnt,
                "score": score(stats, accepted_survivors=0),
                "score_with_accepted": score(stats, accepted_survivors=accepted_cnt),
                "comparable": stats["not_checked"] == 0 and tested > 0,
                "source_sha256": _source_sha256(root, rel),
                "surviving_mutants": unaccepted_survivors,
            }
        )
    if not stats_list:
        raise SystemExit
    counts = {k: sum(s[k] for s in stats_list) for k in stats_list[0]}
    totals: dict[str, object] = {
        **counts,
        "accepted_survivors": total_accepted,
        "score": score(counts, accepted_survivors=0),
        "score_with_accepted": score(counts, accepted_survivors=total_accepted),
    }
    progress = {
        "total": counts["total"] + never_checked_keys,
        "checked": counts["total"] - counts["not_checked"],
        "not_checked": counts["not_checked"] + never_checked_keys,
        "torn_metas": torn_metas,
        "completed": counts["not_checked"] + never_checked_keys == 0 and torn_metas == 0,
    }
    return {
        "schema_version": 2,
        "modules": modules,
        "totals": totals,
        "progress": progress,
        "target_modules": target_modules(root),
    }


def _find_previous_detailed_entry(runs: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the most recent entry in `runs` that carries per-module records."""
    for entry in reversed(runs):
        if not isinstance(entry, dict):
            continue
        mods = entry.get("modules")
        if isinstance(mods, list) and mods:
            return dict(entry)
    return None


def _format_floor_issue_body(alert: dict[str, Any]) -> str:
    mod = alert["module"]
    lines = [
        f"## Mutation floor alert: `{mod}`",
        "",
    ]
    if "score_drop" in alert["reasons"]:
        lines.append(
            f"- **Score drop beyond {NOISE_BAND_PP:.1f}pp noise band:** "
            f"`{alert['prev_score']:.2f}%` -> `{alert['cur_score']:.2f}%` "
            f"(`-{alert['drop_pp']:.2f}pp`)"
        )
    if "mutant_count_drop" in alert["reasons"]:
        lines.append(
            f"- **Mutant count fell with unchanged source (`source_sha256` `{alert['source_sha256'][:12]}…`):** "
            f"`{alert['prev_total']}` -> `{alert['cur_total']}` mutants "
            f"(lost line coverage under `mutate_only_covered_lines = true`)"
        )
    newly = alert.get("newly_surviving", [])
    if newly:
        lines.extend(["", "### Newly surviving mutants", ""])
        for m in newly:
            lines.append(f"- `{m}`")
    return "\n".join(lines) + "\n"


def compare_floor(
    report: dict[str, Any],
    previous_entry: dict[str, Any] | None,
    noise_band_pp: float = NOISE_BAND_PP,
) -> list[dict[str, Any]]:
    """Compare `report['modules']` against `previous_entry['modules']` (01 §M2).

    Compares only modules in the scored set whose mutants were all checked in
    both entries (`not_checked == 0`). Emits at most one alert per module
    (`title = "mutation floor: <module>"`) when:
    - its score (with accepted survivors) drops by more than `noise_band_pp`, or
    - its mutant count (`total`) falls while `source_sha256` is unchanged.
    """
    if not previous_entry or not isinstance(previous_entry.get("modules"), list):
        return []
    prev_by_mod = {
        str(m["module"]): m
        for m in previous_entry["modules"]
        if isinstance(m, dict) and "module" in m
    }
    scored_targets = set(report.get("target_modules", []))
    alerts: list[dict[str, Any]] = []

    for cur in report.get("modules", []):
        mod = str(cur["module"])
        if scored_targets and mod not in scored_targets:
            continue
        if mod not in prev_by_mod:
            continue
        prev = prev_by_mod[mod]

        # Compare only modules whose mutants were all re-checked (not_checked == 0).
        cur_unchecked = int(cur.get("not_checked", 0))
        prev_unchecked = int(prev.get("not_checked", 0))
        cur_tested = int(cur.get("total", 0)) - int(cur.get("skipped", 0))
        prev_tested = int(prev.get("total", 0)) - int(prev.get("skipped", 0))
        if cur_unchecked > 0 or prev_unchecked > 0 or cur_tested <= 0 or prev_tested <= 0:
            continue

        prev_score_raw = prev.get("score_with_accepted")
        if prev_score_raw is None:
            prev_score_raw = prev.get("score")
        cur_score_raw = cur.get("score_with_accepted")
        if cur_score_raw is None:
            cur_score_raw = cur.get("score")
        if prev_score_raw is None or cur_score_raw is None:
            continue
        prev_score = float(prev_score_raw)
        cur_score = float(cur_score_raw)
        drop_pp = prev_score - cur_score

        reasons: list[str] = []
        newly_surviving: list[str] = []
        if drop_pp > noise_band_pp:
            reasons.append("score_drop")
            cur_surv = list(cur.get("surviving_mutants", []))
            prev_surv_raw = prev.get("survivors", prev.get("surviving_mutants", []))
            prev_surv = set(prev_surv_raw) if isinstance(prev_surv_raw, list) else set()
            diff_surv = [k for k in cur_surv if k not in prev_surv]
            newly_surviving = sorted(diff_surv if diff_surv else cur_surv)

        prev_sha = prev.get("source_sha256")
        cur_sha = cur.get("source_sha256")
        prev_total = int(prev.get("total", 0))
        cur_total = int(cur.get("total", 0))
        if (
            isinstance(prev_sha, str)
            and isinstance(cur_sha, str)
            and prev_sha
            and prev_sha == cur_sha
            and cur_total < prev_total
        ):
            reasons.append("mutant_count_drop")

        if not reasons:
            continue

        alert: dict[str, Any] = {
            "module": mod,
            "title": f"mutation floor: {mod}",
            "reasons": reasons,
            "prev_score": prev_score,
            "cur_score": cur_score,
            "drop_pp": drop_pp,
            "prev_total": prev_total,
            "cur_total": cur_total,
            "source_sha256": cur_sha,
            "newly_surviving": newly_surviving,
        }
        alert["body"] = _format_floor_issue_body(alert)
        alerts.append(alert)

    return alerts


def _default_gh_runner(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["gh", *argv],
        capture_output=True,
        text=True,
        check=False,
    )


def sync_floor_issues(
    alerts: list[dict[str, Any]],
    repo: str | None = None,
    dry_run: bool = False,
    gh_runner: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None,
) -> list[dict[str, Any]]:
    """Open or update one GitHub issue (`mutation floor: <module>`) per alerting module."""
    runner = gh_runner or _default_gh_runner
    repo_args = ["--repo", repo] if repo else []
    results: list[dict[str, Any]] = []

    for alert in alerts:
        title = str(alert["title"])
        body = str(alert["body"])
        if dry_run and gh_runner is None:
            results.append(
                {
                    "module": alert["module"],
                    "title": title,
                    "action": "open",
                    "reasons": list(alert["reasons"]),
                    "newly_surviving": list(alert.get("newly_surviving", [])),
                    "body": body,
                }
            )
            continue

        list_res = runner(
            [
                "issue",
                "list",
                *repo_args,
                "--state",
                "open",
                "--search",
                f'"{title}" in:title',
                "--json",
                "number,title",
            ]
        )
        existing_num: int | None = None
        if list_res.returncode == 0 and list_res.stdout.strip():
            try:
                items = json.loads(list_res.stdout)
                for item in items:
                    if isinstance(item, dict) and item.get("title") == title:
                        existing_num = int(item["number"])
                        break
            except ValueError, KeyError, TypeError:
                existing_num = None

        if existing_num is not None:
            action = "update"
            if not dry_run:
                runner(["issue", "edit", str(existing_num), *repo_args, "--body", body])
        else:
            action = "open"
            if not dry_run:
                runner(["issue", "create", *repo_args, "--title", title, "--body", body])

        results.append(
            {
                "module": alert["module"],
                "title": title,
                "action": action,
                "issue_number": existing_num,
                "reasons": list(alert["reasons"]),
                "newly_surviving": list(alert.get("newly_surviving", [])),
                "body": body,
            }
        )

    return results


def _compact_summary_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Compact an older history run entry to one summary object: date, killed_or_timeout, total, score."""
    tot = entry.get("totals", entry)
    if not isinstance(tot, dict):
        tot = entry
    caught = tot.get("killed_or_timeout")
    if caught is None:
        caught = int(tot.get("killed", 0)) + int(tot.get("timeout", 0))
    total = int(tot.get("total", entry.get("total", 0)))
    raw_score = tot.get("score", entry.get("score"))
    sc = round(float(raw_score), 4) if isinstance(raw_score, (int, float)) else None
    return {
        "date": str(entry.get("date", "")),
        "killed_or_timeout": int(caught),
        "total": total,
        "score": sc,
    }


def _compact_module_for_history(mod_entry: dict[str, Any]) -> dict[str, Any]:
    caught = int(mod_entry.get("killed", 0)) + int(mod_entry.get("timeout", 0))
    sc = mod_entry.get("score")
    sca = mod_entry.get("score_with_accepted")
    return {
        "module": mod_entry["module"],
        "killed_or_timeout": caught,
        "total": int(mod_entry.get("total", 0)),
        "skipped": int(mod_entry.get("skipped", 0)),
        "not_checked": int(mod_entry.get("not_checked", 0)),
        "accepted_survivors": int(mod_entry.get("accepted_survivors", 0)),
        "score": round(float(sc), 4) if isinstance(sc, (int, float)) else None,
        "score_with_accepted": round(float(sca), 4) if isinstance(sca, (int, float)) else None,
        "source_sha256": mod_entry.get("source_sha256"),
    }


def append_history(path: Path, entry: dict[str, Any], cap: int = HISTORY_MAX_RUNS) -> None:
    """Add this run to the committed history file, oldest-first, capped, keeping it < 200 KB."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        runs = list(data["runs"])
    except OSError, KeyError, ValueError:
        runs = []

    tot = entry.get("totals", {})
    if not isinstance(tot, dict):
        tot = {}
    caught = entry.get("killed_or_timeout")
    if caught is None:
        caught = int(tot.get("killed", 0)) + int(tot.get("timeout", 0))
    total = int(entry.get("total", tot.get("total", 0)))
    raw_score = entry.get("score", tot.get("score"))
    raw_score_acc = entry.get("score_with_accepted", tot.get("score_with_accepted"))

    normalized_entry: dict[str, Any] = {
        "date": entry.get("date", ""),
        "killed_or_timeout": int(caught),
        "total": total,
        "score": raw_score,
    }
    if raw_score_acc is not None:
        normalized_entry["score_with_accepted"] = raw_score_acc
    if "totals" in entry:
        normalized_entry["totals"] = entry["totals"]
    if "progress" in entry:
        normalized_entry["progress"] = entry["progress"]
    if "modules" in entry and isinstance(entry["modules"], list):
        normalized_entry["modules"] = [
            _compact_module_for_history(m) if "killed" in m else m for m in entry["modules"]
        ]

    runs.append(normalized_entry)
    runs = runs[-cap:]

    # Compact older entries beyond the most recent HISTORY_DETAILED_RUNS so the
    # committed history file stays well under 200 KB across years of weekly runs.
    if len(runs) > HISTORY_DETAILED_RUNS:
        cutoff = len(runs) - HISTORY_DETAILED_RUNS
        for idx in range(cutoff):
            if "modules" in runs[idx]:
                runs[idx] = _compact_summary_entry(runs[idx])

    path.write_text(
        json.dumps({"schema_version": 2, "runs": runs}, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    ap = argparse.ArgumentParser(
        description="WP4.3 / O3.5 per-module mutation score from mutmut's cache"
    )
    ap.add_argument("--root", default=str(REPO_ROOT_DEFAULT))
    ap.add_argument("--targets", action="store_true", help="print the M1 shipping scored set only")
    ap.add_argument(
        "--survivors",
        type=Path,
        default=None,
        help="path to accepted_survivors.toml (defaults to <root>/backend/tests/mutation/accepted_survivors.toml)",
    )
    ap.add_argument(
        "--history",
        type=Path,
        help="append the run entry to this JSON history file (weekly CI job only for .github/mutation-history.json)",
    )
    ap.add_argument("--date", default="", help="stamp for the history entry (CI passes run_date)")
    ap.add_argument(
        "--check-floor",
        type=Path,
        default=None,
        help="compare per-module scores against the previous entry in this history JSON file",
    )
    ap.add_argument(
        "--sync-issues",
        action="store_true",
        help="open or update one GitHub issue (`mutation floor: <module>`) per floor alert",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="preview floor issue actions without calling gh over the network or mutating history",
    )
    ap.add_argument(
        "--repo",
        default=os.environ.get("GITHUB_REPOSITORY", ""),
        help="GitHub repository (owner/name) for gh issue operations",
    )
    ap.add_argument(
        "--repair",
        action="store_true",
        help="delete torn (unparseable) .meta files and their mutant copies, then exit 0",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    if args.targets:
        print(json.dumps(target_modules(root), indent=2))
        return 0
    if args.repair:
        for rel in repair_metas(root):
            print(f"deleted torn meta + mutant copy (will regenerate): {rel}", file=sys.stderr)
        return 0
    if args.history and args.history.resolve() == REPO_HISTORY_PATH:
        if os.environ.get("GITHUB_ACTIONS") != "true":
            print(
                "refusing to write .github/mutation-history.json outside the weekly CI job (UR-7 / 01 M2)",
                file=sys.stderr,
            )
            return 1
    if not (root / "mutants").is_dir():
        print(
            "no mutants/ tree -- mutation-run.sh must run first (a missing cache is not a score of 0)",
            file=sys.stderr,
        )
        return 1
    try:
        report = aggregate(root, survivors_path=args.survivors)
    except SystemExit:
        print(
            "no mutants/*.meta with checked verdicts under mutants/ -- nothing was measured",
            file=sys.stderr,
        )
        return 1

    floor_source = args.check_floor or args.history
    if floor_source and floor_source.is_file():
        try:
            hist_data = json.loads(floor_source.read_text(encoding="utf-8"))
            prev_entry = _find_previous_detailed_entry(list(hist_data.get("runs", [])))
        except OSError, ValueError, KeyError, TypeError:
            prev_entry = None
        alerts = compare_floor(report, prev_entry, noise_band_pp=NOISE_BAND_PP)
        report["floor_alerts"] = alerts
        if args.sync_issues or args.dry_run or args.check_floor is not None:
            report["floor_issues"] = sync_floor_issues(
                alerts,
                repo=args.repo or None,
                dry_run=args.dry_run,
            )

    print(json.dumps(report, indent=2, sort_keys=False))
    if args.history and not args.dry_run:
        append_history(
            args.history,
            {
                "date": args.date,
                "totals": report["totals"],
                "progress": report["progress"],
                "modules": report["modules"],
            },
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
