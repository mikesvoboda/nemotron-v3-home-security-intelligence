"""Tests for scripts/mutation-score.py (WP4.3).

The WP4.3 "tracked over time" spine: mutmut 3.x parks per-source-file mutant
verdicts in `mutants/<path>.meta` (exit_code_by_key) and offers only an
aggregate publish path (export-cicd-stats -> a single total). "Mutation score
reported FOR the widened set" needs per-module aggregation -- this script is
that aggregation, and its output is the commit/publish artifact.

Classification is NOT reimplemented from intuition: the test pins it to
mutmut's own status_by_exit_code map imported from the installed package, so
a mutmut upgrade that changes verdict codes moves this scorer's semantics
with it (or the pin fails and says so).

Score formula pinned to mutmut's own `badge` command:
    score = (killed + timeout) / (total - skipped) * 100

Run: uv run pytest scripts/test_mutation_score.py -q  (ci.yml anti-rot list)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCORER = REPO_ROOT / "scripts" / "mutation-score.py"


def scorer(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCORER), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd,
    )


def meta(root: Path, rel: str, exit_code_by_key: dict[str, int | None]) -> None:
    p = root / "mutants" / (rel + ".meta")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(
            {
                "exit_code_by_key": exit_code_by_key,
                "hash_by_function_name": {},
                "type_check_error_by_key": {},
                "durations_by_key": {},
                "estimated_durations_by_key": {},
            }
        )
    )


def test_per_module_scores_with_mutmut_formula(tmp_path):
    """One meta with 8 mutants: killed(1)+timeout(36) count as caught;
    survived(0)/suspicious(99)/not-checked(None) do not; skipped(34) leaves
    the denominator. -> caught 5 / checked 8-1 = 62.5"""
    meta(
        tmp_path,
        "backend/services/a.py",
        {"f1": 1, "f2": 1, "f3": 0, "f4": 36, "f5": 99, "f6": None, "f7": 34, "f8": 1},
    )
    r = scorer("--root", str(tmp_path))
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    m = {x["module"]: x for x in out["modules"]}["backend/services/a.py"]
    assert m["killed"] == 3
    assert m["timeout"] == 1
    assert m["survived"] == 1
    assert m["suspicious"] == 1
    assert m["not_checked"] == 1
    assert m["skipped"] == 1
    assert m["total"] == 8
    assert m["score"] == (4 / 7) * 100  # killed+timeout over (total - skipped)


def test_unchecked_file_is_excluded_from_run(tmp_path):
    """An all-None meta means generation happened but nothing was checked --
    mutmut's own export skips it (`if not exit_code_by_key` covers empty; a
    file with every mutant unchecked is reported but with checked=0 and no
    score, so the headline can average only run modules)."""
    meta(tmp_path, "backend/services/a.py", {"f1": None})
    meta(tmp_path, "backend/services/b.py", {"g1": 1, "g2": 0})
    out = json.loads(scorer("--root", str(tmp_path)).stdout)
    assert [m["module"] for m in out["modules"]] == ["backend/services/b.py"]


def test_totals_rollup_and_widened_target_list(tmp_path):
    for rel in ("backend/services/a.py", "backend/api/routes/r.py"):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("")
    meta(tmp_path, "backend/services/a.py", {"f1": 1, "f2": 0})
    meta(tmp_path, "backend/api/routes/r.py", {"g1": 1, "g2": 1, "g3": 34})
    out = json.loads(scorer("--root", str(tmp_path)).stdout)
    t = out["totals"]
    assert t["killed"] == 3 and t["survived"] == 1 and t["skipped"] == 1
    assert t["total"] == 5
    # mutmut's badge: (killed+timeout)/(total-skipped)*100 = 3/(5-1)*100
    assert t["score"] == 75.0
    # the PLAN's widened denominator ships in the artifact: every module under
    # backend/services/ and backend/api/routes/ that mutation runs against.
    assert out["target_modules"] == ["backend/api/routes/r.py", "backend/services/a.py"]


def test_targets_mode_lists_plan_targets(tmp_path):
    """--targets enumerates the WP4.3 denominator from the tree (no mutants
    needed): EVERY module under backend/services and backend/api/routes,
    sorted relpaths. Package __init__.py files are in the denominator because
    mutmut mutates them (baseline run: should_mutate(init)=True, 269 files =
    266 concrete + 3 init; services/__init__.py alone is 703 real lines of
    re-export logic) -- a denominator that omits them would report a clean gap
    list while a silently-skipped __init__ went unreported."""
    for rel in (
        "backend/services/severity.py",
        "backend/services/__init__.py",
        "backend/api/routes/alerts.py",
        "backend/api/routes/__init__.py",
        "backend/tests/unit/test_x.py",
    ):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("")
    r = scorer("--root", str(tmp_path), "--targets")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == [
        "backend/api/routes/__init__.py",
        "backend/api/routes/alerts.py",
        "backend/services/__init__.py",
        "backend/services/severity.py",
    ]


def test_no_mutants_dir_is_not_a_silent_zero(tmp_path):
    """A missing mutants/ tree means the run never happened (or the cache was
    dropped) -- fail loudly instead of emitting a 0-module report that a
    workflow would happily commit as 'score: baseline reset'."""
    r = scorer("--root", str(tmp_path))
    assert r.returncode == 1
    assert "no mutants/" in r.stderr


def test_history_append_rolls_and_stamps(tmp_path):
    """--history is the 'tracked over time' half: the run entry appends to a
    committed JSON file, oldest-first, capped -- so the weekly schedule
    accumulates a visible series instead of overwriting the last number."""
    hist = tmp_path / "hist.json"
    (tmp_path / "mutants").mkdir()
    # a checked meta so aggregate() passes with one module
    meta(tmp_path, "backend/services/a.py", {"f1": 1})
    (tmp_path / "backend/services").mkdir(parents=True)
    (tmp_path / "backend/services/a.py").write_text("")
    r = scorer("--root", str(tmp_path), "--history", str(hist), "--date", "2026-09-17")
    assert r.returncode == 0, (r.stdout, r.stderr)
    h = json.loads(hist.read_text())
    assert [e["date"] for e in h["runs"]] == ["2026-09-17"]
    assert h["runs"][0]["totals"]["score"] == 100.0
    # the entry carries its own completeness (weekly-convergence contract):
    # a partial run's score is pessimistic BY CONSTRUCTION (unchecked counts
    # as uncaught), and the series must be readable without side-context --
    # progress.completed=False says "this point is mid-progress", not "drop".
    assert h["runs"][0]["progress"]["completed"] is True
    assert h["runs"][0]["progress"]["checked"] == 1
    # cap keeps the file bounded (weekly -> ~1yr kept); checked in-process so
    # the 5s tier doesn't hinge on 70 subprocess starts
    import importlib.util

    spec = importlib.util.spec_from_file_location("ms_hist", SCORER)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for i in range(70):
        mod.append_history(hist, {"date": f"d{i}", "totals": {}})
    h = json.loads(hist.read_text())
    assert len(h["runs"]) == 60
    assert h["runs"][-1]["date"] == "d69"
    # 71 entries in, 60 kept -> the seeded first run and d0..d9 rolled off
    assert h["runs"][0]["date"] == "d10"


def test_all_unchecked_run_fails_loudly(tmp_path):
    """Metas exist but every mutant has exit_code None (run interrupted during
    checking) -> nothing was measured -> rc=1, not an IndexError traceback nor
    a vacuous 100%-of-nothing report."""
    meta(tmp_path, "backend/services/a.py", {"f1": None, "f2": None})
    r = scorer("--root", str(tmp_path))
    assert r.returncode == 1
    assert "nothing was measured" in r.stderr


def test_progress_contract_completed_vs_partial(tmp_path):
    """The weekly-convergence contract (WP4.3 CI repair): a cold run cannot
    finish 88k mutants inside one job budget, so verdicts accumulate across
    runs -- and an accumulating cache MUST be distinguishable from a complete
    one, or the history series launders progress into trend. The scorer
    already counts not_checked honestly (it sits in mutmut's badge
    denominator by design); what it must PUBLISH is the completeness:
    progress.checked/progress.total and completed iff nothing is unchecked.
    A partial cache still scores (mutmut's formula, unchecked counted as
    uncaught -- pessimistic, never flattering); completed=False says so."""
    meta(tmp_path, "backend/services/a.py", {"f1": 1, "f2": 1})  # done
    meta(tmp_path, "backend/services/b.py", {"g1": 1, "g2": None, "g3": None})  # partial
    out = json.loads(scorer("--root", str(tmp_path)).stdout)
    p = out["progress"]
    assert p["total"] == 5 and p["checked"] == 3 and p["not_checked"] == 2
    assert p["completed"] is False
    # partial score stays mutmut's formula over the FULL denominator:
    # caught 3 / (5 - 0 skipped) = 60.0 (the 2 unchecked count as uncaught),
    # pessimistic by construction
    assert out["totals"]["score"] == 60.0
    meta(tmp_path, "backend/services/b.py", {"g1": 1, "g2": 0, "g3": 1})  # finished
    out = json.loads(scorer("--root", str(tmp_path)).stdout)
    assert out["progress"]["completed"] is True
    assert out["progress"]["not_checked"] == 0
    assert out["totals"]["score"] == (4 / 5) * 100


def test_repair_deletes_torn_metas_AND_their_mutant_copies(tmp_path):
    """A timeout-SIGKILLed checking step (the weekly budget design kills the
    STEP, not the cache -- verdicts persist per-mutant by design) can die
    mid-save and leave a truncated JSON. mutmut's own SourceFileMutationData.
    load() guards only FileNotFoundError -- a JSONDecodeError would crash
    every subsequent run against a restored cache.

    --repair must DELETE the torn meta AND its mutant .py copy, not write a
    fresh all-empty meta: create_mutants_for_file skips regeneration whenever
    the mutant copy is newer than the source (mtime check, before any meta
    is consulted), so a reset-but-present meta would never be refilled and
    the module's mutants would silently vanish from the denominator -- the
    exact completeness hole repair exists to close. Removing the copy forces
    the getmtime-OSError regeneration path; generation then writes a fresh
    meta with None for every mutant, so they all recount and recheck."""
    meta(tmp_path, "backend/services/a.py", {"f1": 1, "f2": 1})
    torn = tmp_path / "mutants" / "backend/services/b.py.meta"
    torn.parent.mkdir(parents=True, exist_ok=True)
    torn.write_text('{"exit_code_by_key": {"g1": 1, "g2": ')  # killed mid-save
    copy = torn.with_suffix("")  # mutants/backend/services/b.py
    copy.write_text("x = 1\n")
    r = scorer("--root", str(tmp_path), "--repair")
    assert r.returncode == 0, r.stderr
    assert "b.py.meta" in r.stderr  # repair is spoken, not silent
    assert not torn.exists() and not copy.exists()
    intact = json.loads((tmp_path / "mutants/backend/services/a.py.meta").read_text())
    assert intact["exit_code_by_key"] == {"f1": 1, "f2": 1}  # untouched


def test_repair_on_missing_tree_is_a_noop(tmp_path):
    """CI ordering fact: the repair step runs BEFORE the first generation
    (a cold cache has no mutants/ yet -- mutation-run.sh creates it). Repair
    has nothing to repair there and must exit 0, not trip the
    "run mutation-run.sh first" guard meant for scoring."""
    r = scorer("--root", str(tmp_path), "--repair")
    assert r.returncode == 0, r.stderr


def test_torn_meta_without_repair_is_counted_not_silent(tmp_path):
    """Without --repair a torn meta must NOT be silently skipped as "nothing
    to report" (its mutant count is unknowable, but treating it as absent is
    how a cache grows holes while claiming completeness): it is counted in
    progress.torn_metas and forces completed=False. Loud, countable,
    fixable."""
    meta(tmp_path, "backend/services/a.py", {"f1": 1})
    torn = tmp_path / "mutants" / "backend/services/b.py.meta"
    torn.parent.mkdir(parents=True, exist_ok=True)
    torn.write_text('{"exit_code_by_key": {"g1": 1')
    r = scorer("--root", str(tmp_path))
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["progress"]["torn_metas"] == 1
    assert out["progress"]["completed"] is False
    assert "torn" in r.stderr.lower()


def test_verdict_table_matches_mutmut_import():
    """The pin: our classification of the codes that matter equals mutmut's
    own status_by_exit_code as INSTALLED here. If mutmut changes what exit
    code 5 or 36 means, this test fails at the same moment our scorer would
    drift -- and the scorer is read from the same map, not copied."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("mutation_score_under_test", SCORER)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    from mutmut.stats import status_by_exit_code

    for code, want in mod.VERDICT_CODES.items():
        # underscores are our namespacing of mutmut's spaced status names
        assert status_by_exit_code[code].replace(" ", "_") == want, (
            f"mutmut says {code} is {status_by_exit_code[code]!r}"
        )
