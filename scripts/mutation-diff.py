#!/usr/bin/env python3
"""PR mutation evidence diff tool (O3.6 / `01-mutation-policy.md` §M4).

Compares a module's mutation results before and after a test-only PR against a
fixed baseline mutant set (`mutate_only_covered_lines = false`, so mutant
generation depends on production bytes alone):

1. Matches each baseline mutant across `--before` and `--after` by stable
   identity — `(module, function, body_sha256, occurrence_index)` — never by
   mutmut's positional key (`__mutmut_N`) alone.
2. Classifies a mutant as **caught** when its verdict is `killed` or `timeout`
   (the same set `scripts/mutation-score.py` counts). Moving between `killed`
   and `timeout` is not a kill-loss.
3. Reports every **kill-loss**: a baseline mutant caught in `--before` whose
   `--after` verdict is `survived`, `no tests`, `not checked`, `suspicious`,
   `skipped`, or `missing`.
4. Checks each kill-loss against `backend/tests/mutation/accepted_survivors.toml`
   (or `--survivors <path>`), validating the TOML schema first. Exits non-zero
   when any kill-loss is not covered by an accepted-survivor entry.

Inputs accepted by `--before` and `--after`:
- A JSON snapshot/fixture file (`{"mutants": [...]}`) produced by `--snapshot`
  or authored in tests.
- A mutmut `.py.meta` file path (with its sibling mutated `.py` file alongside).
- A `mutants/` directory (or a checkout root containing `mutants/`).

Helper modes for the documented PR evidence workflow:
- `--snapshot <out.json> --from <meta-or-dir> [--module <mod>]`
- `--configure-toml <pyproject.toml> --module <mod.py> --tests <test_path>...`
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
import tomllib
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SURVIVORS_PATH = REPO_ROOT / "backend" / "tests" / "mutation" / "accepted_survivors.toml"
CLASS_SEPARATOR = "ǁ"

CAUGHT_STATUSES = frozenset({"killed", "timeout"})
REQUIRED_SURVIVOR_FIELDS = ("module", "mutant", "body_sha256", "kind", "reason", "date")
ALLOWED_SURVIVOR_FIELDS = frozenset(REQUIRED_SURVIVOR_FIELDS)
VALID_SURVIVOR_KINDS = frozenset({"equivalent", "below-bar"})
HEX64_RE = re.compile(r"[0-9a-f]{64}")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

FALLBACK_STATUS_BY_CODE: dict[int | None, str] = {
    1: "killed",
    3: "killed",
    0: "survived",
    36: "timeout",
    255: "timeout",
    24: "timeout",
    -24: "timeout",
    152: "timeout",
    5: "no tests",
    33: "no tests",
    34: "skipped",
    35: "suspicious",
    37: "caught by type check",
    2: "check was interrupted by user",
    None: "not checked",
}


@dataclass(frozen=True, slots=True)
class MutantRecord:
    """One mutant with its stable identity and verdict."""

    key: str
    module: str
    function: str
    mutant: str
    body_sha256: str
    orig_body_sha256: str
    status: str
    occurrence: int = 0

    @property
    def short_function(self) -> str:
        return self.function.rpartition(".")[2] if "." in self.function else self.function

    @property
    def identity(self) -> tuple[str, str, str, int]:
        return (self.module, self.function, self.body_sha256, self.occurrence)


@dataclass(frozen=True, slots=True)
class KillLoss:
    """A baseline mutant caught in `--before` that was not caught in `--after`."""

    before: MutantRecord
    after_status: str
    after_key: str | None
    accepted_by: dict[str, str] | None

    @property
    def transition(self) -> str:
        return f"{self.before.status} -> {self.after_status}"


def _status_from_exit_code(exit_code: int | None) -> str:
    if exit_code is None:
        return "not checked"
    try:
        from mutmut.stats import status_by_exit_code

        raw = str(status_by_exit_code[int(exit_code)])
    except Exception:
        raw = FALLBACK_STATUS_BY_CODE.get(int(exit_code), "suspicious")
    return _normalize_status(raw)


def _normalize_status(status: str) -> str:
    norm = status.strip().lower().replace("_", " ")
    if norm in {"not checked", "unchecked", "none"}:
        return "not checked"
    if norm in {"no tests", "no test"}:
        return "no tests"
    return norm


def _normalize_module_name(raw: str) -> str:
    cleaned = raw.strip().removesuffix(".py").replace("/", ".").strip(".")
    return cleaned


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


def _extract_functions_from_mutated_py(py_path: Path) -> dict[str, tuple[str, list[str]]]:
    """Map generated function name -> `(full_source_from_def, lines)` via AST."""
    resolved = py_path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"mutated source file not found: {py_path}")
    code = resolved.read_text(encoding="utf-8")
    lines = code.splitlines(keepends=True)
    tree = ast.parse(code, filename=str(resolved))
    out: dict[str, tuple[str, list[str]]] = {}

    def _collect(stmts: list[ast.stmt]) -> None:
        for node in stmts:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if "__mutmut_" in node.name and node.end_lineno is not None:
                    segment = lines[node.lineno - 1 : node.end_lineno]
                    src = "".join(segment)
                    if not src.endswith("\n"):
                        src += "\n"
                    out[node.name] = (src, [ln.rstrip("\r\n") for ln in segment])
            elif isinstance(node, ast.ClassDef):
                _collect(node.body)

    _collect(tree.body)
    return out


def _restore_original_def_name(src: str, gen_name: str, short_fn: str) -> str:
    return re.sub(
        rf"^(\s*(?:async\s+def|def)\s+){re.escape(gen_name)}\b",
        rf"\1{short_fn}",
        src,
        count=1,
        flags=re.MULTILINE,
    )


def _single_line_diff_summary(
    qual_fn: str,
    orig_lines: list[str],
    mut_lines: list[str],
) -> str:
    """Format `<function> <orig_expr> -> <mut_expr>` for readability and TOML matching."""
    for orig_ln, mut_ln in zip(orig_lines[1:], mut_lines[1:], strict=False):
        if orig_ln != mut_ln:
            return f"{qual_fn} {orig_ln.strip()} -> {mut_ln.strip()}"
    if len(orig_lines) != len(mut_lines):
        return f"{qual_fn} lines {len(orig_lines)} -> {len(mut_lines)}"
    return f"{qual_fn} <body change>"


def _records_from_meta_file(
    meta_path: Path, module_filter: str | None = None
) -> list[MutantRecord]:
    resolved_meta = meta_path.resolve()
    if not resolved_meta.is_file():
        raise FileNotFoundError(f"meta file not found: {meta_path}")
    meta_data = json.loads(resolved_meta.read_text(encoding="utf-8"))
    exit_code_by_key: dict[str, int | None] = meta_data.get("exit_code_by_key", {})
    if not exit_code_by_key:
        return []

    py_path = resolved_meta.with_suffix("")
    func_map = _extract_functions_from_mutated_py(py_path)

    raw_records: list[tuple[str, str, str, str, str, str, str]] = []
    for key, exit_code in exit_code_by_key.items():
        mod, qual_fn, short_fn, gen_name = _parse_key_parts(key)
        if module_filter and not _module_matches(mod, module_filter):
            continue
        if gen_name not in func_map:
            raise ValueError(
                f"{resolved_meta}: mutant function {gen_name!r} missing from {py_path}"
            )
        mut_raw_src, mut_lines = func_map[gen_name]
        mut_norm_src = _restore_original_def_name(mut_raw_src, gen_name, short_fn)
        body_sha = hashlib.sha256(mut_norm_src.encode("utf-8")).hexdigest()

        orig_gen_name = gen_name.rpartition("__mutmut_")[0] + "__mutmut_orig"
        if orig_gen_name in func_map:
            orig_raw_src, orig_lines = func_map[orig_gen_name]
            orig_norm_src = _restore_original_def_name(orig_raw_src, orig_gen_name, short_fn)
            orig_sha = hashlib.sha256(orig_norm_src.encode("utf-8")).hexdigest()
            mutant_desc = _single_line_diff_summary(qual_fn, orig_lines, mut_lines)
        else:
            orig_sha = body_sha
            mutant_desc = f"{qual_fn} {gen_name}"

        status = _status_from_exit_code(exit_code)
        raw_records.append((key, mod, qual_fn, mutant_desc, body_sha, orig_sha, status))

    return _assign_occurrences(raw_records)


def _assign_occurrences(
    raw_records: list[tuple[str, str, str, str, str, str, str]],
) -> list[MutantRecord]:
    counts: Counter[tuple[str, str, str]] = Counter()
    records: list[MutantRecord] = []
    for key, mod, qual_fn, mutant_desc, body_sha, orig_sha, status in raw_records:
        base_id = (mod, qual_fn, body_sha)
        occ = counts[base_id]
        counts[base_id] += 1
        records.append(
            MutantRecord(
                key=key,
                module=mod,
                function=qual_fn,
                mutant=mutant_desc,
                body_sha256=body_sha,
                orig_body_sha256=orig_sha,
                status=status,
                occurrence=occ,
            )
        )
    return records


def _module_matches(mod: str, module_filter: str) -> bool:
    norm_filter = _normalize_module_name(module_filter)
    return mod == norm_filter or mod.endswith(f".{norm_filter}")


def load_results(target: Path, module_filter: str | None = None) -> list[MutantRecord]:
    """Load `MutantRecord` items from a JSON file, a `.py.meta` file, or a directory."""
    resolved = target.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"results path does not exist: {target}")

    if resolved.is_dir():
        mutants_root = resolved / "mutants" if (resolved / "mutants").is_dir() else resolved
        meta_files = sorted(
            p
            for p in mutants_root.rglob("*.py.meta")
            if "tests" not in p.relative_to(mutants_root).parts
        )
        records: list[MutantRecord] = []
        for meta_file in meta_files:
            records.extend(_records_from_meta_file(meta_file, module_filter=module_filter))
        return records

    if resolved.name.endswith(".py.meta"):
        return _records_from_meta_file(resolved, module_filter=module_filter)

    data = json.loads(resolved.read_text(encoding="utf-8"))
    items = data["mutants"] if isinstance(data, dict) and "mutants" in data else data
    if not isinstance(items, list):
        raise ValueError(f"{target}: expected a JSON list or {{'mutants': [...]}} object")

    raw_records: list[tuple[str, str, str, str, str, str, str]] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"{target}[{idx}]: expected object")
        key = str(item.get("key") or f"fixture_{idx}")
        mod = _normalize_module_name(str(item["module"]))
        if module_filter and not _module_matches(mod, module_filter):
            continue
        func = str(item["function"])
        body_sha = str(item["body_sha256"])
        orig_sha = str(item.get("orig_body_sha256") or body_sha)
        mutant_desc = str(item.get("mutant") or f"{func} {key}")
        if "status" in item and item["status"] is not None:
            status = _normalize_status(str(item["status"]))
        else:
            raw_code = item.get("exit_code")
            status = _status_from_exit_code(int(raw_code) if raw_code is not None else None)
        raw_records.append((key, mod, func, mutant_desc, body_sha, orig_sha, status))

    return _assign_occurrences(raw_records)


def load_accepted_survivors(path: Path) -> list[dict[str, str]]:
    """Parse and validate `accepted_survivors.toml` entries."""
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"accepted-survivors file not found: {path}")
    data = tomllib.loads(resolved.read_text(encoding="utf-8"))
    unexpected = sorted(set(data) - {"survivor"})
    if unexpected:
        raise ValueError(
            f"{path}: unexpected top-level key(s) {unexpected}; entries must use [[survivor]]"
        )
    entries = data.get("survivor", [])
    if not isinstance(entries, list):
        raise ValueError(f"{path}: [[survivor]] must be a list of tables")

    seen: set[tuple[str, str, str]] = set()
    validated: list[dict[str, str]] = []
    for i, entry in enumerate(entries):
        loc = f"{path}[{i}]"
        if not isinstance(entry, dict):
            raise ValueError(f"{loc}: entry must be a table")
        for req in REQUIRED_SURVIVOR_FIELDS:
            if req not in entry:
                raise ValueError(f"{loc}: missing required field {req!r}")
            if not isinstance(entry[req], str):
                raise ValueError(f"{loc}: field {req!r} must be a string")
        unknown = sorted(set(entry) - ALLOWED_SURVIVOR_FIELDS)
        if unknown:
            raise ValueError(f"{loc}: unknown field(s) {unknown}")
        kind = entry["kind"]
        if kind not in VALID_SURVIVOR_KINDS:
            raise ValueError(f"{loc}: invalid kind {kind!r}")
        digest = entry["body_sha256"]
        if not HEX64_RE.fullmatch(digest):
            raise ValueError(f"{loc}: body_sha256 {digest!r} is not 64 lowercase hex chars")
        mutant_str = entry["mutant"].strip()
        reason_str = entry["reason"].strip()
        module_str = _normalize_module_name(entry["module"])
        date_str = entry["date"]
        if not mutant_str or not reason_str or not module_str:
            raise ValueError(f"{loc}: module, mutant, and reason must be non-empty")
        if not DATE_RE.fullmatch(date_str):
            raise ValueError(f"{loc}: date {date_str!r} is not YYYY-MM-DD")
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError(f"{loc}: date {date_str!r} is not a valid calendar date") from exc
        dedup_key = (module_str, mutant_str, digest)
        if dedup_key in seen:
            raise ValueError(f"{loc}: duplicate survivor entry {dedup_key}")
        seen.add(dedup_key)
        validated.append(
            {
                "module": module_str,
                "mutant": mutant_str,
                "body_sha256": digest,
                "kind": kind,
                "reason": reason_str,
                "date": date_str,
            }
        )
    return validated


def _matching_survivor(
    record: MutantRecord,
    survivors: list[dict[str, str]],
    used_indices: set[int],
) -> dict[str, str] | None:
    """Return and consume the `[[survivor]]` entry covering `record`, if any.

    Each `[[survivor]]` entry is a claim about one mutant, so an entry can cover
    at most one kill-loss. Supports both `body_sha256` conventions documented in
    the repo:
    1. `body_sha256` is the mutated function body's sha256 (`01-mutation-policy.md`
       §"The floor" step 3 and §M3), with `mutant` naming the function (`func ...`).
    2. `body_sha256` is `inspect.getsource(fn)` of the unmutated function
       (`accepted_survivors.toml` header comment), paired with the exact
       `mutant = "<function> <expression> <change>"` string so a sibling mutant
       in the same function is never covered by accident.
    """
    for idx, entry in enumerate(survivors):
        if idx in used_indices:
            continue
        if entry["module"] != record.module:
            continue
        entry_mutant = entry["mutant"].strip()
        entry_fn_token = entry_mutant.split()[0] if entry_mutant else ""
        fn_matches = entry_fn_token in {record.function, record.short_function} or (
            entry_mutant == record.mutant
        )
        if entry["body_sha256"] == record.body_sha256 and fn_matches:
            used_indices.add(idx)
            return entry
        if entry["body_sha256"] == record.orig_body_sha256 and entry_mutant == record.mutant:
            used_indices.add(idx)
            return entry
    return None


def diff_runs(
    before: list[MutantRecord],
    after: list[MutantRecord],
    survivors: list[dict[str, str]],
) -> tuple[list[KillLoss], dict[str, int]]:
    """Diff `--before` and `--after` mutant sets by stable identity."""
    after_by_id: dict[tuple[str, str, str, int], MutantRecord] = {
        rec.identity: rec for rec in after
    }
    kill_losses: list[KillLoss] = []
    used_survivors: set[int] = set()
    caught_before = 0
    caught_after = 0

    for b_rec in before:
        a_rec = after_by_id.get(b_rec.identity)
        a_status = a_rec.status if a_rec is not None else "missing"
        if b_rec.status in CAUGHT_STATUSES:
            caught_before += 1
        if a_status in CAUGHT_STATUSES:
            caught_after += 1
        if b_rec.status in CAUGHT_STATUSES and a_status not in CAUGHT_STATUSES:
            accepted = _matching_survivor(b_rec, survivors, used_survivors)
            kill_losses.append(
                KillLoss(
                    before=b_rec,
                    after_status=a_status,
                    after_key=a_rec.key if a_rec is not None else None,
                    accepted_by=accepted,
                )
            )

    uncovered = sum(1 for kl in kill_losses if kl.accepted_by is None)
    accepted_count = sum(1 for kl in kill_losses if kl.accepted_by is not None)
    summary = {
        "baseline_total": len(before),
        "after_total": len(after),
        "caught_before": caught_before,
        "caught_after": caught_after,
        "raw_kill_loss": len(kill_losses),
        "accepted_kill_loss": accepted_count,
        "uncovered_kill_loss": uncovered,
    }
    return kill_losses, summary


def configure_toml_for_evidence(
    pyproject_path: Path,
    module_arg: str,
    test_paths: list[str],
) -> None:
    """Configure `[tool.mutmut]` in `pyproject.toml` for a single-module evidence run."""
    resolved = pyproject_path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"pyproject.toml not found: {pyproject_path}")

    mod_clean = module_arg.strip()
    if mod_clean.endswith(".py"):
        only_mutate = [mod_clean]
    else:
        stem = mod_clean.split(".")[-1]
        only_mutate = [
            f"backend/services/{stem}.py",
            f"backend/api/routes/{stem}.py",
        ]

    text = resolved.read_text(encoding="utf-8")
    text = re.sub(
        r"^mutate_only_covered_lines\s*=\s*(?:true|false)\s*$",
        "mutate_only_covered_lines = false",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    only_line = f"only_mutate = {json.dumps(only_mutate)}"
    if re.search(r"^only_mutate\s*=", text, flags=re.MULTILINE):
        text = re.sub(
            r"^only_mutate\s*=\s*\[[^\]]*\]",
            only_line,
            text,
            count=1,
            flags=re.MULTILINE,
        )
    else:
        text = text.replace(
            "mutate_only_covered_lines = false",
            f"mutate_only_covered_lines = false\n{only_line}",
            1,
        )

    if test_paths:
        selection_lines = (
            "pytest_add_cli_args_test_selection = [\n"
            + "".join(f'    "{p}",\n' for p in test_paths)
            + "]"
        )
        text = re.sub(
            r"^pytest_add_cli_args_test_selection\s*=\s*\[[^\]]*\]",
            selection_lines,
            text,
            count=1,
            flags=re.MULTILINE | re.DOTALL,
        )

    resolved.write_text(text, encoding="utf-8")


def _print_report(
    kill_losses: list[KillLoss],
    summary: dict[str, int],
    *,
    as_json: bool,
) -> None:
    if as_json:
        payload = {
            "summary": summary,
            "kill_losses": [
                {
                    "module": kl.before.module,
                    "function": kl.before.function,
                    "mutant": kl.before.mutant,
                    "body_sha256": kl.before.body_sha256,
                    "orig_body_sha256": kl.before.orig_body_sha256,
                    "before_key": kl.before.key,
                    "after_key": kl.after_key,
                    "before_status": kl.before.status,
                    "after_status": kl.after_status,
                    "transition": kl.transition,
                    "accepted": kl.accepted_by is not None,
                    "accepted_kind": kl.accepted_by["kind"] if kl.accepted_by else None,
                }
                for kl in kill_losses
            ],
        }
        print(json.dumps(payload, indent=2))
        return

    print(
        f"Baseline mutants: {summary['baseline_total']} | "
        f"caught before -> after: {summary['caught_before']}/{summary['baseline_total']} "
        f"-> {summary['caught_after']}/{summary['baseline_total']} | "
        f"kill-loss: {summary['uncovered_kill_loss']} "
        f"(raw {summary['raw_kill_loss']}, accepted {summary['accepted_kill_loss']})"
    )
    for kl in kill_losses:
        tag = (
            f"ACCEPTED ({kl.accepted_by['kind']})"
            if kl.accepted_by is not None
            else "KILL-LOSS (uncovered)"
        )
        occ_suffix = f" [twin #{kl.before.occurrence}]" if kl.before.occurrence else ""
        print(
            f"  [{tag}] {kl.before.module}.{kl.before.function}{occ_suffix}: "
            f"{kl.transition}\n"
            f"    mutant      = {kl.before.mutant!r}\n"
            f"    body_sha256 = {kl.before.body_sha256!r}\n"
            f"    before_key  = {kl.before.key}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PR mutation evidence diff tool (O3.6 / 01 §M4)")
    parser.add_argument("--before", type=Path, help="Before-run results (.json, .py.meta, or dir)")
    parser.add_argument("--after", type=Path, help="After-run results (.json, .py.meta, or dir)")
    parser.add_argument(
        "--survivors",
        type=Path,
        default=DEFAULT_SURVIVORS_PATH,
        help="Path to accepted_survivors.toml",
    )
    parser.add_argument("--module", default=None, help="Optional module filter or module path")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=None,
        help="Write a self-contained JSON snapshot of mutants to this path",
    )
    parser.add_argument(
        "--from",
        dest="snapshot_from",
        type=Path,
        default=Path("mutants"),
        help="Source `.py.meta` or `mutants/` directory for `--snapshot` (default: mutants)",
    )
    parser.add_argument(
        "--configure-toml",
        type=Path,
        default=None,
        help="Configure `[tool.mutmut]` in the given pyproject.toml for an evidence run",
    )
    parser.add_argument(
        "--tests",
        nargs="*",
        default=[],
        help="Test file/dir paths for `--configure-toml`",
    )
    args = parser.parse_args(argv)

    try:
        if args.configure_toml is not None:
            if not args.module:
                print("--configure-toml requires --module", file=sys.stderr)
                return 2
            configure_toml_for_evidence(args.configure_toml, args.module, list(args.tests))
            return 0

        if args.snapshot is not None:
            records = load_results(args.snapshot_from, module_filter=args.module)
            if not records:
                print(
                    f"no mutants found in {args.snapshot_from} (module={args.module!r})",
                    file=sys.stderr,
                )
                return 2
            out_path = args.snapshot.resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(
                json.dumps({"mutants": [asdict(r) for r in records]}, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"snapshot written: {out_path} ({len(records)} mutants)")
            return 0

        if args.before is None or args.after is None:
            parser.error(
                "--before and --after are required unless --snapshot or --configure-toml is used"
            )

        survivors = load_accepted_survivors(args.survivors)
        before_records = load_results(args.before, module_filter=args.module)
        if not before_records:
            print(
                f"empty --before results in {args.before}: no mutants measured at base",
                file=sys.stderr,
            )
            return 2
        after_records = load_results(args.after, module_filter=args.module)
    except (
        FileNotFoundError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
        tomllib.TOMLDecodeError,
    ) as exc:
        print(f"mutation-diff error: {exc}", file=sys.stderr)
        return 2

    kill_losses, summary = diff_runs(before_records, after_records, survivors)
    _print_report(kill_losses, summary, as_json=args.json)
    return 1 if summary["uncovered_kill_loss"] > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
