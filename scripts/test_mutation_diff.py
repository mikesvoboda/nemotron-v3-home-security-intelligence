"""Tests for scripts/mutation-diff.py (O3.6 / `01` §M4).

M4's specification (`docs/uplevel/01-mutation-policy.md` §"The floor", §M4):
- Match mutants across `--before` and `--after` runs by stable identity
  (`module`, `function`, and the mutated function body's `body_sha256`, paired
  in occurrence order when two mutations in one function produce identical
  bodies) — never by positional mutmut key alone.
- A mutant is caught when its status is `killed` or `timeout`.
- A kill-loss is a baseline mutant caught in `--before` whose `--after` status
  is anything else: `survived`, `no tests`, `not checked`, `suspicious`,
  `skipped`, or `missing`.
- Moving between `killed` and `timeout` (`killed -> timeout` and
  `timeout -> killed`) is NOT a kill-loss.
- Exit non-zero when any kill-loss is not covered by an entry in
  `backend/tests/mutation/accepted_survivors.toml` (or `--survivors <path>`),
  and exit zero when all kill-losses are covered.

Run: uv run python -m pytest scripts/test_mutation_diff.py -q
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL_PATH = REPO_ROOT / "scripts" / "mutation-diff.py"

SAMPLE_MODULE = "backend.services.verdict_engine_status"
SAMPLE_FUNCTION = "_derive_state"
SAMPLE_ORIG_BODY = (
    "def _derive_state(details: dict | None, message: str | None):\n"
    "    if details is None:\n"
    '        return ("unknown", message or "probe failed")\n'
    '    return ("available", None)\n'
)
SAMPLE_MUTATED_BODY_A = (
    "def _derive_state(details: dict | None, message: str | None):\n"
    "    if details is not None:\n"
    '        return ("unknown", message or "probe failed")\n'
    '    return ("available", None)\n'
)
SAMPLE_MUTATED_BODY_B = (
    "def _derive_state(details: dict | None, message: str | None):\n"
    "    if details is None:\n"
    '        return ("unknown", message and "probe failed")\n'
    '    return ("available", None)\n'
)
SAMPLE_HASH_ORIG = hashlib.sha256(SAMPLE_ORIG_BODY.encode("utf-8")).hexdigest()
SAMPLE_HASH_A = hashlib.sha256(SAMPLE_MUTATED_BODY_A.encode("utf-8")).hexdigest()
SAMPLE_HASH_B = hashlib.sha256(SAMPLE_MUTATED_BODY_B.encode("utf-8")).hexdigest()


def _load_tool() -> Any:
    assert TOOL_PATH.is_file(), f"missing {TOOL_PATH.relative_to(REPO_ROOT)}"
    spec = importlib.util.spec_from_file_location("mutation_diff", TOOL_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["mutation_diff"] = mod
    spec.loader.exec_module(mod)
    return mod


def _run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # real
        [sys.executable, str(TOOL_PATH), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd or REPO_ROOT,
        timeout=30,
    )


def _write_results(path: Path, mutants: list[dict[str, object]]) -> Path:
    path.write_text(json.dumps({"mutants": mutants}, indent=2) + "\n", encoding="utf-8")
    return path


def _mutant_record(
    *,
    key: str = f"{SAMPLE_MODULE}.x__derive_state__mutmut_1",
    module: str = SAMPLE_MODULE,
    function: str = SAMPLE_FUNCTION,
    mutant: str = "_derive_state if details is None: -> if details is not None:",
    body_sha256: str = SAMPLE_HASH_A,
    orig_body_sha256: str = SAMPLE_HASH_ORIG,
    status: str = "killed",
) -> dict[str, object]:
    return {
        "key": key,
        "module": module,
        "function": function,
        "mutant": mutant,
        "body_sha256": body_sha256,
        "orig_body_sha256": orig_body_sha256,
        "status": status,
    }


def _write_survivors(path: Path, entries: list[dict[str, str]]) -> Path:
    lines = ["# fixture accepted_survivors.toml\n"]
    for entry in entries:
        lines.append("[[survivor]]\n")
        for k, v in entry.items():
            lines.append(f'{k} = "{v}"\n')
        lines.append("\n")
    path.write_text("".join(lines), encoding="utf-8")
    return path


def test_no_change_exits_zero_and_reports_zero_kill_loss(tmp_path: Path) -> None:
    """Fixture case 1: no change -> exit 0, zero kill-loss."""
    before = _write_results(
        tmp_path / "before.json",
        [
            _mutant_record(status="killed"),
            _mutant_record(
                key=f"{SAMPLE_MODULE}.x__derive_state__mutmut_2",
                mutant='_derive_state message or "probe failed" -> message and "probe failed"',
                body_sha256=SAMPLE_HASH_B,
                status="survived",
            ),
        ],
    )
    after = _write_results(
        tmp_path / "after.json",
        [
            _mutant_record(status="killed"),
            _mutant_record(
                key=f"{SAMPLE_MODULE}.x__derive_state__mutmut_2",
                mutant='_derive_state message or "probe failed" -> message and "probe failed"',
                body_sha256=SAMPLE_HASH_B,
                status="survived",
            ),
        ],
    )
    survivors = _write_survivors(tmp_path / "survivors.toml", [])

    proc = _run_cli("--before", str(before), "--after", str(after), "--survivors", str(survivors))
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    assert "kill-loss: 0" in proc.stdout.lower()


@pytest.mark.parametrize(
    ("before_status", "after_status", "expected_transition"),
    [
        ("killed", "survived", "killed -> survived"),
        ("killed", "no tests", "killed -> no tests"),
        ("killed", "not checked", "killed -> not checked"),
        ("timeout", "survived", "timeout -> survived"),
    ],
)
def test_caught_to_uncaught_status_is_a_kill_loss(
    tmp_path: Path,
    before_status: str,
    after_status: str,
    expected_transition: str,
) -> None:
    """Fixture cases: killed -> survived, killed -> no tests, killed -> not checked,
    timeout -> survived all report a kill-loss and exit non-zero."""
    before = _write_results(tmp_path / "before.json", [_mutant_record(status=before_status)])
    after = _write_results(tmp_path / "after.json", [_mutant_record(status=after_status)])
    survivors = _write_survivors(tmp_path / "survivors.toml", [])

    proc = _run_cli("--before", str(before), "--after", str(after), "--survivors", str(survivors))
    assert proc.returncode != 0, (proc.stdout, proc.stderr)
    assert expected_transition in proc.stdout
    assert SAMPLE_FUNCTION in proc.stdout


@pytest.mark.parametrize(
    ("before_status", "expected_transition"),
    [
        ("killed", "killed -> missing"),
        ("timeout", "timeout -> missing"),
    ],
)
def test_caught_to_missing_is_a_kill_loss(
    tmp_path: Path,
    before_status: str,
    expected_transition: str,
) -> None:
    """Fixture cases: killed -> missing and timeout -> missing both report a
    kill-loss and exit non-zero (guards against uncovered lines vanishing in the
    head run)."""
    before = _write_results(
        tmp_path / "before.json",
        [
            _mutant_record(status=before_status),
            _mutant_record(
                key=f"{SAMPLE_MODULE}.x__derive_state__mutmut_2",
                mutant='_derive_state message or "probe failed" -> message and "probe failed"',
                body_sha256=SAMPLE_HASH_B,
                status="survived",
            ),
        ],
    )
    after = _write_results(
        tmp_path / "after.json",
        [
            _mutant_record(
                key=f"{SAMPLE_MODULE}.x__derive_state__mutmut_1",
                mutant='_derive_state message or "probe failed" -> message and "probe failed"',
                body_sha256=SAMPLE_HASH_B,
                status="survived",
            ),
        ],
    )
    survivors = _write_survivors(tmp_path / "survivors.toml", [])

    proc = _run_cli("--before", str(before), "--after", str(after), "--survivors", str(survivors))
    assert proc.returncode != 0, (proc.stdout, proc.stderr)
    assert expected_transition in proc.stdout


@pytest.mark.parametrize(
    ("before_status", "after_status"),
    [
        ("killed", "timeout"),
        ("timeout", "killed"),
    ],
)
def test_moving_between_killed_and_timeout_is_not_a_kill_loss(
    tmp_path: Path,
    before_status: str,
    after_status: str,
) -> None:
    """Fixture cases: killed -> timeout and timeout -> killed are both caught
    in both runs and are NOT kill-losses."""
    before = _write_results(tmp_path / "before.json", [_mutant_record(status=before_status)])
    after = _write_results(tmp_path / "after.json", [_mutant_record(status=after_status)])
    survivors = _write_survivors(tmp_path / "survivors.toml", [])

    proc = _run_cli("--before", str(before), "--after", str(after), "--survivors", str(survivors))
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    assert "kill-loss: 0" in proc.stdout.lower()


def test_kill_loss_covered_by_accepted_survivors_exits_zero(tmp_path: Path) -> None:
    """Fixture case: one kill-loss covered by the accepted-survivors file exits 0."""
    before = _write_results(tmp_path / "before.json", [_mutant_record(status="killed")])
    after = _write_results(tmp_path / "after.json", [_mutant_record(status="survived")])
    survivors = _write_survivors(
        tmp_path / "survivors.toml",
        [
            {
                "module": SAMPLE_MODULE,
                "mutant": "_derive_state if details is None: -> if details is not None:",
                "body_sha256": SAMPLE_HASH_A,
                "kind": "below-bar",
                "reason": "Surrendered below-bar assertion from test_old_spy.",
                "date": "2026-10-18",
            }
        ],
    )

    proc = _run_cli("--before", str(before), "--after", str(after), "--survivors", str(survivors))
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    assert "accepted" in proc.stdout.lower()


def test_kill_loss_covered_by_orig_function_body_hash_and_exact_mutant_exits_zero(
    tmp_path: Path,
) -> None:
    """`accepted_survivors.toml` header also documents `inspect.getsource(fn)`
    hashes paired with `mutant = "<function> <expression> <change>"`. That form
    must cover only the exact named mutant, never a sibling mutant in the same
    function."""
    rec_a = _mutant_record(status="killed")
    rec_b = _mutant_record(
        key=f"{SAMPLE_MODULE}.x__derive_state__mutmut_2",
        mutant='_derive_state message or "probe failed" -> message and "probe failed"',
        body_sha256=SAMPLE_HASH_B,
        status="killed",
    )
    before = _write_results(tmp_path / "before.json", [rec_a, rec_b])
    after_one = _write_results(
        tmp_path / "after_one.json",
        [{**rec_a, "status": "survived"}, rec_b],
    )
    after_both = _write_results(
        tmp_path / "after_both.json",
        [{**rec_a, "status": "survived"}, {**rec_b, "status": "survived"}],
    )
    survivors = _write_survivors(
        tmp_path / "survivors.toml",
        [
            {
                "module": SAMPLE_MODULE,
                "mutant": "_derive_state if details is None: -> if details is not None:",
                "body_sha256": SAMPLE_HASH_ORIG,
                "kind": "below-bar",
                "reason": "Surrendered below-bar kill from test_old_spy.",
                "date": "2026-10-18",
            }
        ],
    )

    proc_one = _run_cli(
        "--before", str(before), "--after", str(after_one), "--survivors", str(survivors)
    )
    assert proc_one.returncode == 0, (proc_one.stdout, proc_one.stderr)

    # Sibling mutant rec_b in the same function shares orig_body_sha256 but has a
    # different mutant description, so it must NOT be covered by rec_a's entry.
    proc_both = _run_cli(
        "--before", str(before), "--after", str(after_both), "--survivors", str(survivors)
    )
    assert proc_both.returncode != 0, (proc_both.stdout, proc_both.stderr)


def test_matches_by_stable_identity_across_key_renumbering(tmp_path: Path) -> None:
    """Mutant keys are positional (`__mutmut_1`, `__mutmut_2`); when keys shift
    between runs while `(module, function, body_sha256)` is unchanged, matching
    by stable identity reports zero kill-loss."""
    before = _write_results(
        tmp_path / "before.json",
        [
            _mutant_record(
                key=f"{SAMPLE_MODULE}.x__derive_state__mutmut_9",
                body_sha256=SAMPLE_HASH_A,
                status="killed",
            ),
            _mutant_record(
                key=f"{SAMPLE_MODULE}.x__derive_state__mutmut_10",
                mutant='_derive_state message or "probe failed" -> message and "probe failed"',
                body_sha256=SAMPLE_HASH_B,
                status="survived",
            ),
        ],
    )
    after = _write_results(
        tmp_path / "after.json",
        [
            _mutant_record(
                key=f"{SAMPLE_MODULE}.x__derive_state__mutmut_1",
                body_sha256=SAMPLE_HASH_A,
                status="killed",
            ),
            _mutant_record(
                key=f"{SAMPLE_MODULE}.x__derive_state__mutmut_2",
                mutant='_derive_state message or "probe failed" -> message and "probe failed"',
                body_sha256=SAMPLE_HASH_B,
                status="survived",
            ),
        ],
    )
    survivors = _write_survivors(tmp_path / "survivors.toml", [])

    proc = _run_cli("--before", str(before), "--after", str(after), "--survivors", str(survivors))
    assert proc.returncode == 0, (proc.stdout, proc.stderr)


def test_occurrence_twins_with_identical_body_hash_do_not_collapse(tmp_path: Path) -> None:
    """When two mutations in the same function produce identical mutated bodies
    (e.g. dropping either of two identical positional args in a call), both
    twins are tracked in occurrence order so losing one kill is caught."""
    twin_1 = _mutant_record(
        key=f"{SAMPLE_MODULE}.x__derive_state__mutmut_1",
        body_sha256=SAMPLE_HASH_A,
        status="killed",
    )
    twin_2 = _mutant_record(
        key=f"{SAMPLE_MODULE}.x__derive_state__mutmut_2",
        body_sha256=SAMPLE_HASH_A,
        status="killed",
    )
    before = _write_results(tmp_path / "before.json", [twin_1, twin_2])
    after = _write_results(
        tmp_path / "after.json",
        [twin_1, {**twin_2, "status": "survived"}],
    )
    survivors = _write_survivors(tmp_path / "survivors.toml", [])

    proc = _run_cli("--before", str(before), "--after", str(after), "--survivors", str(survivors))
    assert proc.returncode != 0, (proc.stdout, proc.stderr)
    assert "killed -> survived" in proc.stdout

    # And if BOTH twins lose their kill, a single [[survivor]] entry covers only
    # one of the two twins (one entry = one claim about one mutant).
    after_both = _write_results(
        tmp_path / "after_both.json",
        [{**twin_1, "status": "survived"}, {**twin_2, "status": "survived"}],
    )
    one_survivor = _write_survivors(
        tmp_path / "one_survivor.toml",
        [
            {
                "module": SAMPLE_MODULE,
                "mutant": "_derive_state if details is None: -> if details is not None:",
                "body_sha256": SAMPLE_HASH_A,
                "kind": "below-bar",
                "reason": "Covers only one twin.",
                "date": "2026-10-18",
            }
        ],
    )
    proc_both = _run_cli(
        "--before", str(before), "--after", str(after_both), "--survivors", str(one_survivor)
    )
    assert proc_both.returncode != 0, (proc_both.stdout, proc_both.stderr)
    assert "kill-loss: 1 (raw 2, accepted 1)" in proc_both.stdout


def test_reads_mutmut_meta_and_mutated_py_directly(tmp_path: Path) -> None:
    """`mutation-diff.py` can read mutmut's `.py.meta` + mutated `.py` files
    directly (or via `--snapshot`) and extract stable identities from AST."""
    from mutmut.mutation.file_mutation import mutate_file_contents

    source = (
        "def classify(score: int) -> str:\n"
        "    if score >= 80:\n"
        '        return "high"\n'
        '    return "low"\n'
    )
    mf = mutate_file_contents("backend/services/sample_mod.py", source, None, set())
    assert len(mf.mutant_names) >= 2

    def make_mutants_tree(root: Path, exit_codes: Mapping[str, int | None]) -> Path:
        mod_dir = root / "mutants" / "backend" / "services"
        mod_dir.mkdir(parents=True, exist_ok=True)
        py_path = mod_dir / "sample_mod.py"
        py_path.write_text(mf.code, encoding="utf-8")
        meta_path = mod_dir / "sample_mod.py.meta"
        meta_path.write_text(
            json.dumps(
                {
                    "exit_code_by_key": exit_codes,
                    "hash_by_function_name": dict(mf.hash_by_function_name),
                    "type_check_error_by_key": {},
                    "durations_by_key": {},
                    "estimated_durations_by_key": {},
                }
            ),
            encoding="utf-8",
        )
        return meta_path

    keys = [f"backend.services.sample_mod.{name}" for name in mf.mutant_names]
    before_meta = make_mutants_tree(tmp_path / "run_before", dict.fromkeys(keys, 1))
    after_codes = dict.fromkeys(keys, 1)
    after_codes[keys[0]] = 0  # first mutant survived in after run
    after_meta = make_mutants_tree(tmp_path / "run_after", after_codes)
    survivors = _write_survivors(tmp_path / "survivors.toml", [])

    proc = _run_cli(
        "--before", str(before_meta), "--after", str(after_meta), "--survivors", str(survivors)
    )
    assert proc.returncode != 0, (proc.stdout, proc.stderr)
    assert "killed -> survived" in proc.stdout

    # Also test --snapshot producing JSON that --before/--after consumes identically
    snap_before = tmp_path / "snap_before.json"
    snap_after = tmp_path / "snap_after.json"
    r1 = _run_cli("--snapshot", str(snap_before), "--from", str(before_meta))
    r2 = _run_cli("--snapshot", str(snap_after), "--from", str(after_meta))
    assert r1.returncode == 0 and r2.returncode == 0
    proc_snap = _run_cli(
        "--before", str(snap_before), "--after", str(snap_after), "--survivors", str(survivors)
    )
    assert proc_snap.returncode != 0
    assert "killed -> survived" in proc_snap.stdout


def test_malformed_survivors_file_is_rejected(tmp_path: Path) -> None:
    """A typo in `accepted_survivors.toml` (e.g. `[[survivors]]` plural) must fail
    loudly rather than silently failing to match or passing."""
    before = _write_results(tmp_path / "before.json", [_mutant_record(status="killed")])
    after = _write_results(tmp_path / "after.json", [_mutant_record(status="killed")])
    bad_survivors = tmp_path / "bad_survivors.toml"
    bad_survivors.write_text('[[survivors]]\nmodule = "x"\n', encoding="utf-8")

    proc = _run_cli(
        "--before", str(before), "--after", str(after), "--survivors", str(bad_survivors)
    )
    assert proc.returncode != 0
    assert "survivor" in proc.stderr.lower()


def test_empty_before_results_fails_loudly(tmp_path: Path) -> None:
    """An empty `--before` set means nothing was measured at the base commit and
    must exit non-zero rather than passing as zero kill-loss."""
    before = _write_results(tmp_path / "before.json", [])
    after = _write_results(tmp_path / "after.json", [])
    survivors = _write_survivors(tmp_path / "survivors.toml", [])

    proc = _run_cli("--before", str(before), "--after", str(after), "--survivors", str(survivors))
    assert proc.returncode != 0
    assert "empty" in proc.stderr.lower() or "no mutants" in proc.stderr.lower()


def test_configure_toml_sets_evidence_mode_knobs(tmp_path: Path) -> None:
    """`--configure-toml` rewrites `[tool.mutmut]` in a target `pyproject.toml` so
    `mutate_only_covered_lines = false`, `only_mutate` scopes to the module, and
    `pytest_add_cli_args_test_selection` scopes to the module's unit tests."""
    import tomllib

    pyproj = tmp_path / "pyproject.toml"
    pyproj.write_text(
        "[tool.mutmut]\n"
        'source_paths = ["backend/services", "backend/api/routes"]\n'
        'pytest_add_cli_args_test_selection = [\n    "backend/tests/unit",\n]\n'
        "mutate_only_covered_lines = true\n",
        encoding="utf-8",
    )
    proc = _run_cli(
        "--configure-toml",
        str(pyproj),
        "--module",
        "backend/services/verdict_engine_status.py",
        "--tests",
        "backend/tests/unit/services/test_verdict_engine_status.py",
    )
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    cfg = tomllib.loads(pyproj.read_text(encoding="utf-8"))["tool"]["mutmut"]
    assert cfg["mutate_only_covered_lines"] is False
    assert cfg["only_mutate"] == ["backend/services/verdict_engine_status.py"]
    assert cfg["pytest_add_cli_args_test_selection"] == [
        "backend/tests/unit/services/test_verdict_engine_status.py"
    ]
