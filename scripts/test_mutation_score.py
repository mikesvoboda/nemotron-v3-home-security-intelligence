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
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCORER = REPO_ROOT / "scripts" / "mutation-score.py"


def scorer(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
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


def test_per_module_scores_with_mutmut_formula(tmp_path: Path) -> None:
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


def test_unchecked_file_is_excluded_from_run(tmp_path: Path) -> None:
    """An all-None meta means generation happened but nothing was checked --
    mutmut's own export skips it (`if not exit_code_by_key` covers empty; a
    file with every mutant unchecked is reported but with checked=0 and no
    score, so the headline can average only run modules)."""
    meta(tmp_path, "backend/services/a.py", {"f1": None})
    meta(tmp_path, "backend/services/b.py", {"g1": 1, "g2": 0})
    out = json.loads(scorer("--root", str(tmp_path)).stdout)
    assert [m["module"] for m in out["modules"]] == ["backend/services/b.py"]


def test_totals_rollup_and_widened_target_list(tmp_path: Path) -> None:
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


def test_targets_mode_lists_plan_targets(tmp_path: Path) -> None:
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


def test_targets_honors_do_not_mutate_exclusion(tmp_path: Path) -> None:
    """Denominator ruling 2026-09-25: the nemotron model is deprecated and the
    user ruled its modules OUT of the mutation denominator. mutmut 3.8 has no
    path-exclusion at generation we otherwise share, but it DOES ship
    [tool.mutmut] do_not_mutate globs (configuration.py
    _should_ignore_for_mutation) -- generation will not make mutants there.
    The scorer's target_modules must apply the SAME semantics, or the gap
    list shows a permanent false 'run never covered it' hole for a module
    that was deliberately removed (and CI's modules/length-vs-targets line
    would read a shrinking denominator as a shrinking target set forever).
    """
    for rel in (
        "backend/services/severity.py",
        "backend/services/nemotron_analyzer.py",
        "backend/services/nemotron_streaming.py",
        "backend/api/routes/alerts.py",
    ):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("")
    (tmp_path / "pyproject.toml").write_text(
        "[tool.mutmut]\ndo_not_mutate = ['backend/services/nemotron_*']\n"
    )
    r = scorer("--root", str(tmp_path), "--targets")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == [
        "backend/api/routes/alerts.py",
        "backend/services/severity.py",
    ]
    # and the full report path applies it too: a stale nemotron meta must not
    # resurrect the module into the badge
    meta(tmp_path, "backend/services/nemotron_analyzer.py", {"f1": 1, "f2": 0})
    meta(tmp_path, "backend/services/severity.py", {"g1": 1})
    out = json.loads(scorer("--root", str(tmp_path)).stdout)
    assert [m["module"] for m in out["modules"]] == ["backend/services/severity.py"]
    assert out["totals"]["total"] == 1


def test_no_mutants_dir_is_not_a_silent_zero(tmp_path: Path) -> None:
    """A missing mutants/ tree means the run never happened (or the cache was
    dropped) -- fail loudly instead of emitting a 0-module report that a
    workflow would happily commit as 'score: baseline reset'."""
    r = scorer("--root", str(tmp_path))
    assert r.returncode == 1
    assert "no mutants/" in r.stderr


def test_history_append_rolls_and_stamps(tmp_path: Path) -> None:
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


def test_all_unchecked_run_fails_loudly(tmp_path: Path) -> None:
    """Metas exist but every mutant has exit_code None (run interrupted during
    checking) -> nothing was measured -> rc=1, not an IndexError traceback nor
    a vacuous 100%-of-nothing report."""
    meta(tmp_path, "backend/services/a.py", {"f1": None, "f2": None})
    r = scorer("--root", str(tmp_path))
    assert r.returncode == 1
    assert "nothing was measured" in r.stderr


def test_progress_contract_completed_vs_partial(tmp_path: Path) -> None:
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


def test_repair_deletes_torn_metas_AND_their_mutant_copies(tmp_path: Path) -> None:
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


def test_repair_on_missing_tree_is_a_noop(tmp_path: Path) -> None:
    """CI ordering fact: the repair step runs BEFORE the first generation
    (a cold cache has no mutants/ yet -- mutation-run.sh creates it). Repair
    has nothing to repair there and must exit 0, not trip the
    "run mutation-run.sh first" guard meant for scoring."""
    r = scorer("--root", str(tmp_path), "--repair")
    assert r.returncode == 0, r.stderr


def test_torn_meta_without_repair_is_counted_not_silent(tmp_path: Path) -> None:
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


def test_never_checked_modules_still_ride_progress(tmp_path: Path) -> None:
    """The cold-cache honesty hole: 266 generated-but-never-checked metas +
    ONE finished module is the real state after a targeted local run, and
    the skip-before-progress path made it read total=18/checked=18/
    completed=True -- a 1-module cache claiming a finished denominator,
    exactly the trend-laundering M3 exists to stop. Generated-but-unchecked
    keys are KNOWN quantities (meta key count), so they must count into
    progress.total/not_checked and force completed=False -- while the
    modules list and badge totals keep mutmut's export shape (only run
    modules score)."""
    meta(tmp_path, "backend/services/done.py", {"f1": 1, "f2": 1})
    meta(tmp_path, "backend/services/untouched.py", {"g1": None, "g2": None, "g3": None})
    out = json.loads(scorer("--root", str(tmp_path)).stdout)
    p = out["progress"]
    assert p["total"] == 5  # 2 done + 3 never-checked keys
    assert p["checked"] == 2
    assert p["not_checked"] == 3
    assert p["completed"] is False  # a 1-of-2-modules cache is NOT finished
    # but the badge side is unchanged: only run modules score
    assert [m["module"] for m in out["modules"]] == ["backend/services/done.py"]
    assert out["totals"]["total"] == 2 and out["totals"]["score"] == 100.0


def test_verdict_table_matches_mutmut_import() -> None:
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


def _load_scorer_module() -> Any:
    import importlib.util

    spec = importlib.util.spec_from_file_location("mutation_score_under_test", SCORER)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_scored_set_filters_to_m1_shipping_modules(tmp_path: Path) -> None:
    """O3.5 / 01 M2 Box 1: the scored set is every module in [tool.mutmut]'s
    mutation paths that SHIPS per M1 (scripts/reachability.py), including
    keep.toml declarations. Non-shipping modules are excluded from both
    target_modules() and aggregate()['modules'], even if a stale .meta exists."""
    for rel, code in (
        ("backend/main.py", "from backend.services.live_svc import run\n"),
        ("backend/services/live_svc.py", "def run():\n    return 1\n"),
        ("backend/services/kept_svc.py", "def kept():\n    return 2\n"),
        ("backend/services/dead_svc.py", "def dead():\n    return 0\n"),
    ):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(code)

    reach_dir = tmp_path / "scripts" / "reachability"
    reach_dir.mkdir(parents=True)
    (reach_dir / "entry_points.toml").write_text(
        'entries = ["backend/main.py"]\ndynamic_allow = []\n'
    )
    (reach_dir / "keep.toml").write_text(
        '[[keep]]\nmodule = "backend/services/kept_svc"\nreason = "ships by declaration"\n'
    )

    meta(tmp_path, "backend/services/live_svc.py", {"f1": 1})
    meta(tmp_path, "backend/services/kept_svc.py", {"k1": 1})
    meta(tmp_path, "backend/services/dead_svc.py", {"d1": 0})

    targets = json.loads(scorer("--root", str(tmp_path), "--targets").stdout)
    assert targets == [
        "backend/services/kept_svc.py",
        "backend/services/live_svc.py",
    ]

    out = json.loads(scorer("--root", str(tmp_path)).stdout)
    assert [m["module"] for m in out["modules"]] == [
        "backend/services/kept_svc.py",
        "backend/services/live_svc.py",
    ]
    assert out["totals"]["total"] == 2
    assert out["totals"]["score"] == 100.0


@pytest.mark.timeout(
    120
)  # full-tree reachability AST walk (scripts/test_reachability.py:388 precedent)
def test_repo_targets_match_m1_shipping_set() -> None:
    """O3.5 / 01 M2 Box 1 on REPO_ROOT: vlm_analyzer ships and is in the scored
    set; redis_json, scenario_classifier, managed_service, and
    orphan_cleanup_service do not ship and are excluded."""
    mod = _load_scorer_module()
    targets = set(mod.target_modules(REPO_ROOT))
    assert "backend/services/vlm_analyzer.py" in targets
    for dead_mod in (
        "backend/services/redis_json.py",
        "backend/services/scenario_classifier.py",
        "backend/services/managed_service.py",
        "backend/services/orphan_cleanup_service.py",
    ):
        assert dead_mod not in targets, f"non-shipping module {dead_mod} leaked into scored set"


def test_scores_with_and_without_accepted_survivors(tmp_path: Path) -> None:
    """O3.5 / 01 M2 Box 1: each scored module is scored both without and with
    accepted survivors (backend/tests/mutation/accepted_survivors.toml)."""
    import hashlib

    fn_src = "def calc(x):\n    return x + 1\n"
    fn_sha = hashlib.sha256(fn_src.encode("utf-8")).hexdigest()
    mod_file = tmp_path / "backend/services/a.py"
    mod_file.parent.mkdir(parents=True, exist_ok=True)
    mod_file.write_text(fn_src)

    surv_toml = tmp_path / "backend/tests/mutation/accepted_survivors.toml"
    surv_toml.parent.mkdir(parents=True, exist_ok=True)
    surv_toml.write_text(
        f"[[survivor]]\n"
        f'module = "backend.services.a"\n'
        f'mutant = "calc return x + 1 -> return x + 2"\n'
        f'body_sha256 = "{fn_sha}"\n'
        f'kind = "equivalent"\n'
        f'reason = "equivalent in test fixture"\n'
        f'date = "2026-10-20"\n'
    )

    meta(
        tmp_path,
        "backend/services/a.py",
        {
            "backend.services.a.x_calc__mutmut_1": 1,
            "backend.services.a.x_calc__mutmut_2": 1,
            "backend.services.a.x_calc__mutmut_3": 0,
            "backend.services.a.x_other__mutmut_1": 0,
        },
    )

    r = scorer("--root", str(tmp_path))
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    m = out["modules"][0]
    assert m["score"] == 50.0
    assert m["accepted_survivors"] == 1
    assert m["score_with_accepted"] == 75.0
    assert m["surviving_mutants"] == ["backend.services.a.x_other__mutmut_1"]
    assert out["totals"]["score"] == 50.0
    assert out["totals"]["accepted_survivors"] == 1
    assert out["totals"]["score_with_accepted"] == 75.0


def test_noise_band_constant_matches_measured_derivation() -> None:
    """O3.5 / 01 M2 Box 2: noise band measured across the 57/58 history runs
    for unchanged-source modules (clean re-check drop max 0.5525pp on
    osnet_loader.py; extended non-wipe max 0.7342pp -> 1.0pp band)."""
    mod = _load_scorer_module()
    assert mod.NOISE_BAND_PP == 1.0


def test_dry_run_against_fixture_history_opens_score_drop_and_mutant_count_drop_issues(
    tmp_path: Path,
) -> None:
    """O3.5 / 01 M2 Done when: a dry run against a fixture history opens
    exactly one issue for a module with an injected score drop and exactly one
    for a module whose mutant count fell with unchanged source, while skipping
    partially re-checked modules, drops within the noise band, and mutant-count
    drops where production bytes changed."""
    import hashlib

    files = {
        "backend/services/score_drop.py": "def calc(x):\n    return x + 1\n",
        "backend/services/count_drop.py": "def run(y):\n    return y * 2\n",
        "backend/services/within_band.py": "def ok(z):\n    return z\n",
        "backend/services/partial.py": "def part(w):\n    return w - 1\n",
        "backend/services/changed_src.py": "def chg(v):\n    return v + 99\n",
    }
    shas = {}
    for rel, content in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        shas[rel] = hashlib.sha256(content.encode("utf-8")).hexdigest()

    # Current metas:
    # 1) score_drop.py: was 10/10 (100.0%), now 8/10 (80.0%, -20pp > 1.0pp)
    meta(
        tmp_path,
        "backend/services/score_drop.py",
        {
            **{f"backend.services.score_drop.x_calc__mutmut_{i}": 1 for i in range(1, 9)},
            "backend.services.score_drop.x_calc__mutmut_9": 0,
            "backend.services.score_drop.x_calc__mutmut_10": 0,
        },
    )
    # 2) count_drop.py: was 10/10 (total=10, 100%), now 8/8 (total=8, 100%) with UNCHANGED source_sha256
    meta(
        tmp_path,
        "backend/services/count_drop.py",
        {f"backend.services.count_drop.x_run__mutmut_{i}": 1 for i in range(1, 9)},
    )
    # 3) within_band.py: was 199/200 (99.5%), now 198/200 (99.0%, -0.5pp <= 1.0pp band)
    meta(
        tmp_path,
        "backend/services/within_band.py",
        {
            **{f"backend.services.within_band.x_ok__mutmut_{i}": 1 for i in range(1, 199)},
            "backend.services.within_band.x_ok__mutmut_199": 0,
            "backend.services.within_band.x_ok__mutmut_200": 0,
        },
    )
    # 4) partial.py: was 10/10 (100%), now 5 killed + 5 None (partially re-checked -> not comparable)
    meta(
        tmp_path,
        "backend/services/partial.py",
        {
            **{f"backend.services.partial.x_part__mutmut_{i}": 1 for i in range(1, 6)},
            **{f"backend.services.partial.x_part__mutmut_{i}": None for i in range(6, 11)},
        },
    )
    # 5) changed_src.py: was 10/10 (total=10), now 8/8 (total=8) with DIFFERENT source_sha256
    meta(
        tmp_path,
        "backend/services/changed_src.py",
        {f"backend.services.changed_src.x_chg__mutmut_{i}": 1 for i in range(1, 9)},
    )

    fixture_hist = tmp_path / "fixture-history.json"
    fixture_hist.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "runs": [
                    {
                        "date": "2026-10-13",
                        "killed_or_timeout": 239,
                        "total": 240,
                        "score": 99.5833,
                        "modules": [
                            {
                                "module": "backend/services/score_drop.py",
                                "killed_or_timeout": 10,
                                "total": 10,
                                "not_checked": 0,
                                "score": 100.0,
                                "score_with_accepted": 100.0,
                                "source_sha256": shas["backend/services/score_drop.py"],
                                "survivors": [],
                            },
                            {
                                "module": "backend/services/count_drop.py",
                                "killed_or_timeout": 10,
                                "total": 10,
                                "not_checked": 0,
                                "score": 100.0,
                                "score_with_accepted": 100.0,
                                "source_sha256": shas["backend/services/count_drop.py"],
                                "survivors": [],
                            },
                            {
                                "module": "backend/services/within_band.py",
                                "killed_or_timeout": 199,
                                "total": 200,
                                "not_checked": 0,
                                "score": 99.5,
                                "score_with_accepted": 99.5,
                                "source_sha256": shas["backend/services/within_band.py"],
                                "survivors": ["backend.services.within_band.x_ok__mutmut_200"],
                            },
                            {
                                "module": "backend/services/partial.py",
                                "killed_or_timeout": 10,
                                "total": 10,
                                "not_checked": 0,
                                "score": 100.0,
                                "score_with_accepted": 100.0,
                                "source_sha256": shas["backend/services/partial.py"],
                                "survivors": [],
                            },
                            {
                                "module": "backend/services/changed_src.py",
                                "killed_or_timeout": 10,
                                "total": 10,
                                "not_checked": 0,
                                "score": 100.0,
                                "score_with_accepted": 100.0,
                                "source_sha256": "0" * 64,
                                "survivors": [],
                            },
                        ],
                    }
                ],
            },
            indent=2,
        )
    )

    r = scorer(
        "--root",
        str(tmp_path),
        "--check-floor",
        str(fixture_hist),
        "--dry-run",
    )
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    issues = out["floor_issues"]
    assert len(issues) == 2, f"expected 2 floor issues, got {issues}"
    by_title = {iss["title"]: iss for iss in issues}
    assert set(by_title) == {
        "mutation floor: backend/services/score_drop.py",
        "mutation floor: backend/services/count_drop.py",
    }

    sd = by_title["mutation floor: backend/services/score_drop.py"]
    assert sd["action"] == "open"
    assert sd["reasons"] == ["score_drop"]
    assert sd["newly_surviving"] == [
        "backend.services.score_drop.x_calc__mutmut_10",
        "backend.services.score_drop.x_calc__mutmut_9",
    ]
    assert "x_calc__mutmut_9" in sd["body"] and "x_calc__mutmut_10" in sd["body"]

    cd = by_title["mutation floor: backend/services/count_drop.py"]
    assert cd["action"] == "open"
    assert cd["reasons"] == ["mutant_count_drop"]
    assert "10" in cd["body"] and "8" in cd["body"]

    # Also verify that when an open issue already exists for a module, sync_floor_issues
    # updates that issue in place rather than opening a duplicate.
    mod = _load_scorer_module()
    gh_calls: list[list[str]] = []

    def fake_gh(argv: list[str]) -> subprocess.CompletedProcess[str]:
        gh_calls.append(argv)
        if argv[:2] == ["issue", "list"]:
            if "score_drop.py" in " ".join(argv):
                return subprocess.CompletedProcess(
                    argv,
                    0,
                    stdout=json.dumps(
                        [
                            {
                                "number": 4242,
                                "title": "mutation floor: backend/services/score_drop.py",
                            }
                        ]
                    ),
                    stderr="",
                )
            return subprocess.CompletedProcess(argv, 0, stdout="[]", stderr="")
        return subprocess.CompletedProcess(argv, 0, stdout="https://example/issues/1\n", stderr="")

    synced = mod.sync_floor_issues(out["floor_alerts"], dry_run=False, gh_runner=fake_gh)
    actions = {item["title"]: item["action"] for item in synced}
    assert actions == {
        "mutation floor: backend/services/score_drop.py": "update",
        "mutation floor: backend/services/count_drop.py": "open",
    }
    edit_calls = [c for c in gh_calls if c[:2] == ["issue", "edit"]]
    create_calls = [c for c in gh_calls if c[:2] == ["issue", "create"]]
    assert len(edit_calls) == 1 and "4242" in edit_calls[0]
    assert len(create_calls) == 1


def test_committed_mutation_history_compacted_and_under_200kb() -> None:
    """O3.5 / 01 M2 Box 4 & Done when: .github/mutation-history.json compacts
    the existing campaign runs to one summary entry each (date,
    killed_or_timeout, total, score) and stays under 200 KB."""
    hist_path = REPO_ROOT / ".github" / "mutation-history.json"
    assert hist_path.is_file()
    size_bytes = hist_path.stat().st_size
    assert size_bytes < 200_000, f"mutation-history.json is {size_bytes} bytes (>= 200 KB)"
    data = json.loads(hist_path.read_text(encoding="utf-8"))
    runs = data["runs"]
    assert len(runs) >= 57
    for entry in runs[:57]:
        assert set(entry.keys()) >= {"date", "killed_or_timeout", "total", "score"}
        assert "modules" not in entry, (
            "compacted campaign entries must not carry full per-module blobs"
        )


def test_only_weekly_workflow_writes_repo_history(tmp_path: Path, monkeypatch: Any) -> None:
    """O3.5 / 01 M2 Box 5: .github/mutation-history.json is written ONLY by the
    weekly CI job; calling --history on the repo file outside GitHub Actions is
    refused, and no other script or workflow invokes --history."""
    meta(tmp_path, "backend/services/a.py", {"f1": 1})
    (tmp_path / "backend/services").mkdir(parents=True, exist_ok=True)
    (tmp_path / "backend/services/a.py").write_text("x = 1\n")

    repo_hist = REPO_ROOT / ".github" / "mutation-history.json"
    before_bytes = repo_hist.read_bytes()
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    r = subprocess.run(
        [
            sys.executable,
            str(SCORER),
            "--root",
            str(tmp_path),
            "--history",
            str(repo_hist),
            "--date",
            "2026-10-20",
        ],
        capture_output=True,
        text=True,
        check=False,
        env={k: v for k, v in __import__("os").environ.items() if k != "GITHUB_ACTIONS"},
    )
    assert r.returncode == 1
    assert "weekly CI job" in r.stderr
    assert repo_hist.read_bytes() == before_bytes

    # Static check: no script or workflow other than .github/workflows/mutation-testing.yml
    # invokes mutation-score.py with --history.
    writers: list[str] = []
    for search_dir in (REPO_ROOT / "scripts", REPO_ROOT / ".github" / "workflows"):
        for path in sorted(search_dir.rglob("*")):
            if (
                not path.is_file()
                or "__pycache__" in path.parts
                or path.suffix == ".pyc"
                or path.name in {"mutation-score.py", "test_mutation_score.py"}
            ):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "mutation-score.py" in text and "--history" in text:
                writers.append(path.relative_to(REPO_ROOT).as_posix())
    assert writers == [".github/workflows/mutation-testing.yml"]
