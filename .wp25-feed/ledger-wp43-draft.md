## WP4.3 MUTATION WIDENING — DENOMINATOR `backend/services/` + `backend/api/routes/`, WEEKLY SCHEDULE, HISTORY IN GIT

PARALLEL FEED (same day, while run5/run6 checked; full program post-close-out):
waves 1-47 triaged 17,127 survivors across 117 modules read-only (detector gate

> =150 checked & >=100 survivors, tree-canonical dedupe ledger
> .wp25-feed/triage-waves/dispatched.txt) -> 63% TEST-GAP / 22% EQUIVALENT /
> 15% LOW-VALUE, 767 drafted UNVERIFIED kill-tests + 8 cross-module fix
> patterns (.wp25-feed/wp44-triage/ + wp44-queue-index.md). The ~22% EQUIVALENT
> share is SURVIVOR-WEIGHTED (64/22/14 held thirty-one waves; container_discovery's dataclass-table weight moved the aggregate to 66/21/13 — one
> 93%-gap module can shift the survivor-weighted share, and wave 33's
> mqtt_publisher (43 of 100 LOW-VALUE) settled it at 65/21/13 and wave 36's
> pipeline_workers (96 LOW-VALUE log/otel noise of 282) moved LOW to 14%;
> per-module shape, not the aggregate, is the classifier signal), and it tracks
> module SHAPE (florence_client supplied the program's strongest classifier
> proof — KILLED-TWIN ASYMMETRY: the IDENTICAL textual mutation dies in the
> asserted methods extract/ocr/detect and survives in ocr_with_regions/
> describe_regions/phrase_grounding/detect_security_objects, proving those
> survivors are real behavior changes under un-asserting tests, not equivalents
> — so the 64-66% gap share (wave 40 landed it back at 64, the earliest
> waves' triple) is a genuine work list, not classifier optimism).
> Module SHAPE also drives the noise: zone_comparison/prompt_service/zone_anomaly = 96-98% TEST-GAP (pure
> logic, barely asserted), while nemotron_latency_optimizer sits at 71%
> EQUIVALENT (log-heavy singleton, config kwargs == dataclass defaults),
> calibration_service 68% EQUIVALENT (its redundant clamp+cascade chain
> re-derives the same output for 21 provably-identical arithmetic mutants —
> a code-SIMPLIFICATION signal, plus a dead `new_low < 0` branch) and
> household_matcher 89% EQUIVALENT+LOW-VALUE (already well-tested);
> polygon_zone_service 56% EQUIVALENT (StrEnum + pydantic coercion makes its
> `hasattr(x,"value")` guard provably two-branch-identical), batch_aggregator
> 62% (log-heavy coalescer), clip_client 69%
> log-noise (duration_ms arithmetic, exc_info, `extra` payloads — real changes,
> log-only observability); gpu_config is the status-code-only-asserted endpoint
> at scale — 81 of 111 survivors are the whole auto-assign algorithm under
> `len>=3`/`commit.called`-only tests, and its SYMMETRIC-FIXTURE ABSORPTION
> deserves naming next to mock-absorption: the LATENCY sort-flip mutants are
> test-no-ops because every fixture GPU shares compute_capability '8.6', so the
> tie swallows the mutation before any assert (fixture DATA can be as unassertive
> as a mock); registry 90% log-text noise, and mutation evidence
> CORRECTED the screen on it — the "ZERO test files" finding was true for the
> module but a pure-re-export shim (services/service_registry.py:56) gives it a
> rich covering surface, so the screen's v1 metric needed the shim join;
> segformer_loader is
> the wide-except-crash-swallow at its WORST — 152 of `segment_clothing`'s 153
> mutants survive because the covering tests assert only `isinstance(result,
ClothingSegmentationResult)` while the module's blanket `except Exception:
return ClothingSegmentationResult()` converts any mutation breakage into an
> empty-but-valid result (its fully value-asserted `to_dict` died 9/9 — the
> control case). Wave 21 surfaced a TIER-SCOPE blind spot: cleanup_service's two highest-blast-radius
> survivors (retention cutoff `-timedelta`->`+` deletes EVERY log row; `<`->`<=`
> boundary) are asserted in INTEGRATION tests, but pyproject's
> pytest_add_cli_args_test_selection is unit-tier only — covered-in-the-wrong-
> tier mutants cannot be killed by design, so the score understates real safety
> there (unit drafts close it; the scope question itself is a program note,
> not a mutmut-semantics change). Evidence
> the completed baseline will overstate real gaps even after unchecked-caught
> pessimism unwinds — but the gap share, not the noise share, is the WP4.4
> work list: it starts from the ordered queue, not raw counts. Surfaced en
> route: dead production code (florence \_parse_list_response L419-423,
> unreachable — simplification note, not a test), shipped-behavior gaps the
> mutants proved (tz-guard inversion -> jobs never time out; retry-budget
> off-by-one; circuit-gauge lying after reset; gpu_monitor recorded_at tz-strip
> -> history-read TypeError; auto-enroll is_household_member default flipped ->
> auto-enrolled strangers would read as trusted household members; scenario_classifier tailgating alert payload — all 5 keys + the dict — wholly
> unasserted, the covering test's disjunction passes on score alone;
> vehicle_classifier_loader NEM-4519 `torch.load(weights_only=True)` droppable
> to arbitrary-pickle loading under a MagicMock load; file_service Redis zrem
> member clobber leaves a cancelled file deletion ARMED; debug ltrim off-by-one
> `start 0->1` discards EVERY recorded pipeline error while returning True;
> orchestrator registry singleton can discard its redis client -> the global
> registry persists NOTHING; threat_monitor alert.created WS + webhook payloads
> wholly unobserved (58 key-rename mutants, pattern-6's biggest instance);
> prompt_storage naive-`now()` timestamp leak; system.py /system/health
> exporter-target matching + degradation payload 166-gap module asserted only
> as status.value=='up'), and the
> mock-absorption family (~90 survivors:
> lenient AsyncMocks swallowing call-argument damage across baseline/florence/
> redis/job_timeout — one key-aware-fake contract test per call site kills each
> family).

MEASURE (the finding that reframed the WP): the mutation pipeline was DEAD,
not narrow. mutmut 3.8 rejects every flag the call sites passed
(`--paths-to-mutate/--tests-dir/--runner` -> "Error: No such option"), the
config carried deprecated 2.x keys that only parsed behind warnings,
`mutmut html` (workflow step) does not exist in 3.x, and every invocation sat
behind `|| true` — so the weekly schedule "succeeded" for months producing
zero data, and the doc's "Overall Mutation Score: 89.2%" predates the mutmut
3 migration and was unreproducible. First honest baseline (this commit):
<BASELINE — filled from the run>.

DECIDE (target set + cadence, PLAN's prioritisation executed): denominator =
every module under backend/services/ + backend/api/routes/ — 266 concrete

- 3 package `__init__`s = 269 generated (the mutmut baseline confirmed
  should_mutate(init)=True, so the scorer's --targets counts them too:
  services/**init**.py alone is 703 real lines). Cadence
  stays WEEKLY schedule + workflow_dispatch, never per-PR (mutmut is hours, not
  minutes, at this scale). Prioritisation inside the set came from a static
  assertion-density screen (AST, no pytest): 149 modules screened (>=60
  operator nodes, >=2 test files), thinnest-asserted first —
  `analytics_zones.py` ~71 asserts/kloc at 521 op nodes, `admin.py` 165 at 677,
  `debug.py` 181 at 655, then `dwell_time_service` / `ai_quality_metrics` /
  `batch_coalescer` on the services side. (Screen v1 used non-recursive globs
  and missed nested dirs — caught reconciling 263 vs the tree's 266; v2
  rglob-found `orchestrator/registry.py`: 531 lines, 121 op nodes, ZERO test
  files — the screen's own first catch, fed to WP4.4.) 4 of WP4.5's five
  coverage-omits are inside the denominator by construction (alerts, audit,
  video_processor, degradation_manager; core/tls.py sits outside both trees).

DECIDE (formula, stated with its cost): headline = mutmut's own badge,
(killed+timeout)/(total−skipped), imported semantics not re-derived —
mutation-score.py's verdict table is PINNED against mutmut.stats.
status_by_exit_code in CI (test_mutation_score), so a mutmut upgrade that
moves exit-code meanings fails the pin instead of silently moving the score.
mutate_only_covered_lines=true scopes generation to unit-executed lines: the
score answers "do tests catch behavior changes in code they execute" (WP4.3's
subject); never-executed lines are WP4.5's complaint and every run lists
"targets with no mutants" so the exclusion never hides anything. The 4 covered
omits (alerts/audit/video_processor/degradation_manager) generate ZERO mutants
under this flag — `omit` means mutmut sees no executed lines — surfaced by the
gap list every run until WP4.5 closes them.

HOW it rides: scripts/mutation-run.sh is the ONE runner (workflow + docs +
mutation-test.sh all delegate — the 2.x flag rot could fester in 3 places
because each call site was independent; now there is one, unshielded, and it
fails loudly). scripts/mutation-score.py aggregates mutmut's per-file verdict
cache (mutants/\*.py.meta) into per-module scores — mutmut 3 only publishes ONE
aggregate, so per-module reporting is the missing piece this WP adds; its tests
are in ci.yml's anti-rot list. .github/mutation-history.json is the committed
series (workflow appends on fetched main and pushes — house pattern is
semantic-release's bot commit; a run that measured nothing is rc=1 and never
touches the series). mutants/ cache is gitignored (regenerable); the series is
not.

TDD record: 8 tests scripts/test_mutation_score.py, red-first — formula
against mutmut's badge math, all-unchecked files excluded (nothing measured !=
score 0), --targets denominator from the tree (flipped red mid-WP when the
baseline proved mutmut mutates package **init**.py files — a denominator
excluding them would print a false "skipped module" gap), missing cache is
rc=1 NOT a silent zero report (a 0-module artifact committed as "baseline
reset" is the failure mode this guards), verdict-pin against the installed
mutmut. History
append caps at 60 runs (~1yr weekly), checked in-process so the 5s tier
doesn't hinge on 70 subprocess starts.

Baseline runs 1–2 (2026-09-17) died at the stats pass, NOT at mutant
checking — generation OK'd the whole denominator (269 files mutated in 21s)
and then the stats-pass pytest died inside mutants/: the harness cwd
has no editable install and no repo-root parent on sys.path, so imports AND
parents[N]-relative file reads must exist UNDER mutants/. -x made each death
one-at-a-time; the doctrine became: run the whole selected suite in the
mutant home once, inventory every failure class, fix in one commit. Round 1:
ModuleNotFoundError scripts.synthetic (unit/scripts tests resolve the
first-party package via **file**-relative sys.path arithmetic →
mutants/scripts/) and setup_lib (test_deploy_phases top-level). Round 2:
models.yml — model_zoo.py's Path(**file**).parents[2] read lands on
mutants/models.yml. A whole-suite inventory pass in the mutant home
(-n8, 91s) then named the remaining 17 path/read failures -- each would have
died one-at-a-time under mutmut's -x: 4 infra-exists tests (docker-compose.prod.yml,
monitoring/, frontend/nginx.conf, docker-entrypoint.sh), 12 version-
consistency fixtures (the drift gate reads .nvmrc/.python-version/.github/
workflows/ci.yml/Dockerfiles relative to a tree root = mutants/), one
introspection artifact: mutmut renames covered methods
xǁClassǁmethod**mutmut_orig/\_1 inside the mutated class, so
test_mock_system_broadcaster_has_real_public_methods saw harness
temporaries as "the real API" — the mock-completeness tests now skip names
marked **mutmut (the real-API comparison is unchanged; 67 tests pass
against the real tree). The final also_copy = the IMPORT/READ set, distinct
from source_paths' MUTATE set — frontend FILES listed individually because
copytree would drag node_modules (493MB) and mutmut's file-copy branch
mkdirs no parents (runner pre-mkdirs mutants/frontend; that copytree-parent
gap is mutmut upstream behavior, worked around, not patched).

Run 3 was killed mid-generation (operator kill unblocking a deadlocked
watcher; no verdict). Run 4 (06:01) became the first to clear generation
AND the full stats pass (27k tests mapped, cache mutants/mutmut-stats.json),
then died at the clean-test gate with
hypothesis.errors.FailedHealthCheck: "…test_valid_json_always_parses was
called from multiple different executors". Root-caused into both installed
packages, not papered over: mutmut's DEFAULT process_isolation="fork" runs
collect_stats and run_clean_tests in the SAME parent process ("Already in a
clean process, so run stats directly without forking" — isolation.py
ForkRunner), so the clean pass re-executes every @given test still in
sys.modules; Hypothesis 6.168's differing_executors health check fires on a
second execution from a different executor instance (core.py thread_local
prev_self). Deterministic repro, one python process: pytest.main() twice
over the test → rc1=0 rc2=1, FailedHealthCheck on the second run. The crash
was the LUCKY outcome: the same inheritance reaches every forked mutant
worker ("every worker inherits whatever the test setup left in that
process" — mutmut's own ProcessIsolation docstring), so under fork
isolation ANY mutant covered by a property test would error on the health
check and be scored KILLED with its test never run — an inflated baseline,
silent. Fix = harness configuration, not test surgery: [tool.mutmut]
process_isolation="forkserver" — mutmut's own knob, and its design docstring
names exactly this class of setup as fork-unsafe. ForkServerRunner keeps
mutmut's parent pytest-free and forks each op (stats, clean tests, forced
fail, every mutant check) from a dedicated warm server, so each @given test
executes exactly once per interpreter. Rejected: adding
suppress_health_check to the repo's four property-test files — the tests are
correct under every normal single-execution run; bending them to a harness
process model would be aligning tests to the tool, the mirror of this
program's align-to-shipped-contract rule. The key is deliberately OUT of
mutmut's config_fingerprint groups (test_execution/test_selection/timeout/
type_check), so the stats cache survives the switch — run 5 loads it and
never re-executes the 27k-test stats pass.

MEASURE (weekly-convergence arithmetic, found while wiring the workflow
against the run's real numbers): run5's denominator is 88,329 mutants;
mutmut submits estimated-FASTEST-first (**main**.py:1014, its own comment),
and the first ~4,000 checked consumed ~2 SECONDS of estimated test time out
of ~31h total — every mutant pays a fresh pytest boot (~8-9s here, 12
workers). Boot-bound wall = count/rate: ~18-20h local baseline. The failure
mode this exposed: CI cold-starts, on a 4-core runner the cold set is far
beyond ANY job budget, and a timeout-killed job that keeps nothing restarts
cold forever — the weekly series would never converge. Projected against
mutmut's OWN cost model (estimated_worst_case_time over run5's stats cache,
measured at its 5,282-checked point): remaining 83,047 unchecked = 30.7h of
test time, but per-mutant pytest boot (~8.5s) dominates the wall — 19h at 12
workers locally, and a 240min@12 CI step projects to ~20,300 mutants ≈ 24.5%
per week: ~4 weekly runs to convergence, each preserving the prior verdicts.
The durability
half was source-verified before designing on it: \_register_mutant_result
saves the meta on EVERY checked mutant (**main**.py:920); generation
never touches metas and its hash-merge preserves restored verdicts
(create_mutants_for_file). Fix = carry verdict state across runs:
actions/cache of a few-MB pack (metas+stats+spans — measured 2.6 MB /
539 files; the 1.4GB regenerated tree is reproducible and would blow the
500MB free-tier artifact cap, so neither cache nor artifact carries it
anymore), run step budgeted 240min + continue-on-error so the budget
fires as a STEP kill inside the 6h job cap (CI prep eats 60-90 min) and
pack/score/history always get their turn; a week that overran even that
loses nothing — next run resumes.

DECIDE (the honesty contract that makes an accumulating cache safe): the
scorer publishes progress{checked,total,not_checked,torn_metas,completed};
history entries carry it. Partial points are pessimistic BY CONSTRUCTION
(mutmut's own badge denominator includes unchecked — an unchecked mutant
sits there as uncaught, and no_tests counts against too; imported+formula-
pinned, never locally re-derived — do NOT "fix" these categories without a
ruling) and RISE as the cache converges; only completed points are
comparable as a trend. Torn metas (budget-kill mid-save; json.dump is not
atomic and mutmut's loader guards only FileNotFoundError — proven by the
red test crashing exactly there) are DELETED with their mutant copies by a
pre-run --repair step. Deletion, not reset, is the sound repair — the trap
caught in review: create_mutants_for_file SKIPS regeneration when the
mutant copy is newer than the source (mtime gate before any meta read), so
a reset-but-present meta never refills and the module silently vanishes
from the denominator; removing the copy forces the regeneration path.

Collateral: pyproject [tool.mutmut] rebuilt 2.x->3.x (source_paths /
pytest_add_cli_args_test_selection — the deprecation warnings are gone under
-W error::UserWarning); pytest_add_cli_args gained -m "not gpu" (addopts=
neutralisation had been silently re-enabling gpu-marked mutants) and
--timeout=120 (mutant checks boot the app graph; 5s tier default would fake-
timeout a class of mutants); ci.yml anti-rot list + mutation docs rewritten
(the 2.x commands documented "how to run it" are now a warning box);
frontend/stryker.config.mjs keeps its 3-module set on purpose (no baseline ->
no widening; header records the ruling).
