# AI-Provider Conformance and Swap Readiness — 72-Hour Autonomous Plan

**This file is P.** Ledger is **L** = `docs/plans/2026-09-12-context-map-doc-updates.md`.

**Goal:** make it possible to swap this project's AI pipeline for a VSS-derived one and _know_
whether the swap preserved behaviour — by declaring the provider interface that already shipped
undeclared, and writing the conformance suite that proves any implementation satisfies it.

**Every anchor below was re-verified against `docs/vss-integration` HEAD on 2026-09-19.** If an
anchor fails to reproduce, record the discrepancy in L and proceed. A stale line number is not a
reason to re-verify the other forty.

---

## 0. The three facts that shape this plan

### 0.1 Only two AI services are deployed

```
docker-compose.prod.yml:120   ai-llm            (llama.cpp)
docker-compose.prod.yml:219   ai-llm-vllm       (optional profile)
docker-compose.prod.yml:288   ai-gateway        (Triton-backed, 5 adapter slots)
```

There is **no** `ai-yolo26`, `ai-florence`, `ai-clip`, `ai-enrichment` or `ai-enrichment-light`
service in _any_ of the four compose files (`ci`, `ghcr`, `prod`, `test`). The backend is wired
straight at the gateway:

```
:456  USE_AI_GATEWAY=true
:458  YOLO26_URL=http://ai-gateway:8090/yolo26
:459  FLORENCE_URL=http://ai-gateway:8090/florence
:460  CLIP_URL=http://ai-gateway:8090/clip
:461  ENRICHMENT_URL=http://ai-gateway:8090/enrichment
:462  ENRICHMENT_LIGHT_URL=http://ai-gateway:8090/enrich-lt
:454  NEMOTRON_URL=http://ai-llm:8091
```

`ai/gateway/main.py:181-185` mounts the five adapter routers at exactly those prefixes.

**Consequence for this plan:** the contract is derived from the **deployed** surfaces — the five
gateway adapters (`ai/gateway/adapters/*.py`, importable in the backend venv today) and the six
backend clients. The 10,351 lines under `ai/{yolo26,florence,clip,enrichment,enrichment-light}/
model.py` are a _secondary, undeployed_ provider. Extracting schemas from them is a later,
optional work package, not the centrepiece. **RULING (parked, seed it in L on day one):** are the
five per-model servers still a supported deployment target, or is `ai-gateway` the only one? The
ports still exist in `.env.example`; the compose services do not.

### 0.2 The interface already shipped, and it already diverged

- `ai/gateway/main.py`'s docstring states the swap contract verbatim: it "preserves the exact HTTP
  API that the backend's AI clients already use, so the backend only needs a URL change."
- `ai/gateway/adapters/__init__.py` is one line: `# AI Gateway adapter modules`. No Protocol, no
  ABC, no registry.
- `backend/core/protocols.py:76` `AIServiceProtocol` declares `health_check/process/get_metrics`
  and names `DetectorClient`, `NemotronAnalyzer`, `EnrichmentClient` as implementors. **No client
  defines `process()`.** Its only importer is the re-export at `backend/core/__init__.py:113,166`.
  It annotates zero call sites.
- No test anywhere imports `ai.*`. The clients are tested against hand-written dicts, so a
  server-side key rename reddens nothing on either side.

This is NVIDIA VSS's storage-abstraction failure reproduced in-tree, _before_ the VSS swap starts:
a registry with no declared signature, multiple backends, zero cross-backend tests. VSS's ABC
`filter_chunks` takes 7 params while Neo4j's takes 4 with a different 2nd positional; Milvus
filters `doc_type == 'caption'` while Elasticsearch filters `'caption_summary'`.

### 0.3 The divergence is live in production right now

`ai/gateway/adapters/enrichment.py:288-293` (the **heavy** slot, `ENRICHMENT_URL`):

```python
class BBoxRequest(BaseModel):
    image: str = Field(..., description="Base64 encoded image")
    bbox: dict[str, float] | None = Field(default=None, description="Bounding box {x, y, width, height}")
```

`backend/services/enrichment_client.py:1203`:

```python
payload["bbox"] = list(bbox)
```

`ENRICHMENT_VEHICLE_SERVICE`, `_CLOTHING_SERVICE` and `_DEMOGRAPHICS_SERVICE` all default to
`heavy` (`docker-compose.prod.yml:474-477`). So under the shipped default configuration,
`/enrichment/vehicle-classify`, `/clothing-classify` and `/demographics` **422 on every request
that supplies a bbox.** The _light_ adapter (`ai/gateway/adapters/enrichment_light.py:43-68`) was
hand-patched to accept both shapes, with a docstring that says "so the backend client doesn't get
a 422" — someone hit this manually and fixed one of the two adapters. **Contract drift in this
repo is currently repaired by human archaeology.** That is the practice this plan replaces.

---

## 1. NON-NEGOTIABLE: never edit an import in `ai/*/model.py`

> **Every AI service Dockerfile ends `CMD ["python", "model.py"]` with the service directory
> FLATTENED into `/app`. There is no `ai` package inside any container. `python model.py` runs the
> file as `__main__` with no parent package, so a package-relative import (`from .metrics import`)
> raises `ImportError: attempted relative import with no known parent package` at startup. You
> CANNOT detect this in the sandbox: `/dev/fuse` and `/dev/net/tun` are absent, so you can never
> build or boot a container, and no test in the tree exercises a service entrypoint. Converting
> those imports would end 72 hours with green CI and a dead AI fleet.**

Verified Dockerfile shapes:

| Service               | WORKDIR      | COPY style                                           | CMD                      |
| --------------------- | ------------ | ---------------------------------------------------- | ------------------------ |
| `ai/yolo26`           | `/app` (:45) | explicit per-file (:75-83)                           | `python model.py` (:119) |
| `ai/florence`         | `/app` (:36) | explicit per-file (:62-64)                           | `python model.py` (:140) |
| `ai/clip`             | `/app` (:28) | explicit per-file (:58-64)                           | `python model.py` (:104) |
| `ai/enrichment`       | `/app` (:37) | glob `ai/enrichment/*.py ./` (:64)                   | `python model.py` (:149) |
| `ai/enrichment-light` | `/app` (:27) | glob `ai/enrichment-light/*.py ./` (:52)             | `python model.py` (:103) |
| `ai/gateway`          | `/app`       | **whole dir** `COPY ai/gateway/ /app/gateway/` (:38) | entrypoint (:70)         |

The plan's earlier diagnosis ("packaging architecture problem") was wrong. `ai/yolo26/model.py:
104-107` **already self-shims**:

```python
_ai_dir = Path(__file__).parent.parent      # = ai/
if str(_ai_dir) not in sys.path:
    sys.path.insert(0, str(_ai_dir))
```

That is why `from compile_utils import` (:109) resolves from the repo and `from metrics import`
(:117) does not — the shim inserts `ai/`, not the service's own directory. `ai/enrichment/model.py`
has the identical shim at :38-40 and the same gap for `from model_manager import` (:33).

**Permitted moves, in order of preference:**

1. **Extend the existing shim** to also insert `Path(__file__).parent`. This is additive, resolves
   in both the flat container and the packaged repo, and touches no import statement.
2. **New `contract.py` files are pure leaves**: stdlib + pydantic only, zero sibling imports, zero
   torch. Such a module resolves as `contract` inside the flat container and as
   `ai.<svc>.contract` from the repo, with no Dockerfile change needed for `ai/gateway`,
   `ai/enrichment` and `ai/enrichment-light` (whole-dir or glob COPY).
3. **`ai/yolo26`, `ai/florence`, `ai/clip` use explicit per-file COPY lists.** Adding a file to
   those images requires a Dockerfile edit that cannot be verified here. Therefore: do **not** make
   their `model.py` import a new `contract.py`. If a contract module is generated for them, it is a
   _derived_ artifact guarded by an AST parity test (WP9.1), and the Dockerfile wiring is a parked
   RULING for the owner.

**All Dockerfile edits are owner-review-required. Park them; do not land them.**

---

## 2. Why this order

Ranked by swap-protection value per hour, subject to hard dependencies.

1. **Instruments before measurements (Phase 5).** Backend coverage is computed nowhere in CI.
   Frontend shards run without `--coverage`. Every "coverage went up" claim for the next 62 hours
   is unfalsifiable until these compute. Cheap, blocking, first.
2. **Pre-flight before instruments.** `pre-commit`, the repo-root `.env`, Postgres durability and
   the CI round trip can each silently invalidate days of work, and all four are checkable inside
   three hours.
3. **Un-dark the tier being swapped (Phase 6) before any gate points at it.** You cannot evidence
   "the swap preserved behaviour" in `ai/` when `ai/`'s own tests never ran. Fix collection first,
   gate last — a red gate under schedule pressure is exactly the condition under which allowlists
   get widened.
4. **The contract (Phase 7) before more coverage and before more mutation kills.** Covering a
   fixture the shipped provider cannot produce is _negative-value_ work: it protects a branch
   nobody executes while leaving the real branch dark.
5. **Conformance (Phase 8) before static guards (Phase 9),** because a parity checker with no
   executable reference implementation just relocates the argument.
6. **Reachability classification (WP5.5) before deletions (WP5.6),** so the general rule handles
   the two known-bad mutation records rather than being retrofitted to them.

---

## 3. Global constraints

### 3.1 Sandbox (hard, verified)

- 16 CPU / 94 GiB / **no GPU**. `/dev/fuse` and `/dev/net/tun` are absent, so **podman and docker
  always fail**. The CLAUDE.md infrastructure verification loop (`podman ps`, Prometheus targets,
  `/api/system/health`) is unreachable: note its absence **once** in L and move on. Any step
  phrased "start the service and call it" is **INVALID**.
- Postgres 16 and Redis are **host processes**; `TEST_DATABASE_URL` / `TEST_REDIS_URL` point at
  them. **Zero env-skips are expected on the integration tier.** An env-skip firing is a finding.
- **Not installed** (verified by `importlib.util.find_spec` in `.venv`): `respx`, `pre_commit`,
  `pandas`, `triton`. **Installed:** `torch` (CPU), `transformers` 5.10.1.
  **Do not build anything on respx.** `httpx.ASGITransport` is already proven in-tree, needs no new
  dependency, and gives strictly more (real routing, real pydantic validation, real status codes).
  Working template: `ai/gateway/tests/test_adapters_yolo26.py:99-104`.
- **All AST tooling must run under `.venv/bin/python` (3.14.7).** System `python3.12` reports 37
  false `SyntaxError`s in `backend/services` because the repo uses PEP 758 unparenthesized `except`
  clauses (e.g. `backend/services/detector_client.py:825`). Manufacturing 37 false positives and
  then "fixing" them is the single most expensive available mistake.
- `pyproject.toml:487`: `timeout = 5` per test, `addopts = -n 8 --dist=worksteal -p randomly
-m 'not gpu'`. The conformance suite must fit a 5-second per-case budget and be order-independent.
- **ONE heavy pytest/mutmut job at a time**, with the existing owner-approved carve-out for ≤8
  single-file unit-probe workers (L, 2026-09-18).
- `ci.yml` fires only on `push`/`pull_request` to `main`. A feature-branch push runs **nothing**.
  Use a draft PR, or `gh workflow run` (`ci.yml`, `nightly-full-gate.yml`, `mutation-testing.yml`,
  `flaky-test-detection.yml` carry `workflow_dispatch`). **`gh pr edit` is broken in this
  environment** (Projects-classic GraphQL error aborts it silently) — use
  `gh api -X PATCH repos/{owner}/{repo}/pulls/{n}`.

### 3.2 Inherited discipline

- **TDD is mandatory.** Every behavioural change starts with a failing test, and the red is
  observed before the fix.
- **Never bypass pre-commit.** No `--no-verify`, no `SKIP=`.
- **Coverage floors:** backend 85%, frontend 83/77/81/84. Never lowered to make a gate pass.
- **Never** add a source file to a coverage `exclude`/`omit`, widen an allowlist or quarantine, or
  scope a tree out of a gate.
- **Align tests to the SHIPPED contract** rather than bending production code — with the WP7.4
  caveat.
- Linear via `/linear-python` only.

### 3.3 The ratchet: decreases are yours, increases are the owner's

`scripts/ratchet-check.py:8-13` states it plainly: "_an increase is only legitimate with a registry
entry for every new id AND a hand-raised baseline in the same commit (`--update` refuses to raise —
the adjudication must be a human's diff)_." With the owner away, **you are not that human.**

- **Ratchet DECREASES are expected and are yours to land.** Nearly every work package in this plan
  lowers a census count: WP5.6 deletes modules and their tests; WP6.4 fixes reds; WP7.3 deletes
  five client methods; WP7.4 migrates fixtures; WP8.4 replaces `AsyncMock`/`MagicMock` client tests
  with ASGITransport-driven ones (which lowers `unspecced_patch`, currently 322, whose top
  contributors — `test_detector_routes.py`, `test_nemotron_analyzer.py` — are exactly the files
  this plan rewrites). Procedure, every time: run `scripts/ratchet-check.py --update` **and** edit
  the `ci.yml:107` `--expect` literal **in the same commit**, pasting the full before/after census
  JSON in the commit body as a MEASURE.
- **Ratchet INCREASES require the owner. No exception is available to you.** Not for a new skip,
  not for a new xfail, not for a new excluded tree, not "with paperwork."

### 3.4 Where RULING-blocked findings live

This plan will produce findings whose remediation is a product decision (widen a DB CHECK vs
normalize at the boundary; who owns a 422). You must record them without going red and without
creating a suppression.

- **Never** `xfail` or `skip` a RULING-blocked finding. `pytest_xfail` (baseline 4) and
  `pytest_skip` (32) are ratcheted categories; adding one is a prohibited increase.
- **Never** create a new excluded tree or quarantine directory for them. Same reason.
- **Do this instead:** pin today's behaviour with a **characterization test** — a passing test that
  asserts what the system _currently_ does, whose docstring names the L ruling id and states what
  the assertion should become once the owner rules. Example:

```python
def test_gateway_heavy_bbox_rejects_list_form():
    """CHARACTERIZATION — RULING L#2026-09-19-bbox-shape.

    Pins today's behaviour: the deployed heavy adapter types bbox as
    dict[str, float], so the client's list(bbox) payload 422s. When the owner
    rules, invert this to assert 200 and delete this docstring.
    """
    assert post(...).status_code == 422
```

This keeps the branch green, makes the defect executable, and makes the fix a one-line inversion.
**Your branch stays GREEN.** Do not chase red; do not hide red.

### 3.5 Deletion rule

Delete only where **both**: (a) unreachable — no non-test importer, proven by a census whose number
is in the commit body — **and** (b) either already carrying a mutation deletion-license, **or**
covered by this plan's carve-out.

> **Carve-out, for this plan only, recorded in L on first use:** zero-non-test-importer **AI-tier
> production surface** may be deleted on a call-site census alone, without a surviving-mutant
> record. This covers: AI client methods with zero non-test call sites, AI server routes with zero
> callers, and modules WP5.5 classifies `DEAD`.
>
> **The carve-out covers production AI surface only. No test file, no fixture and no conftest is
> ever deleted under it.** Anything else is a _proposal in L_, not a deletion.

**Generalized retraction rule:** any WP4.4 surviving-mutant record naming a module that WP5.5
classifies `DEAD` is retracted **by name, in L, in the same commit that deletes the module**. A
mutation record is evidence about test strength; it is never a deletion veto for unreachable code.

### 3.6 Caps

Every work package carries an hour cap. **Caps are maxima, not budgets.** At **150% of a cap**:
land what exists, write the residual into L, and advance. Overrunning a cap is never a reason to
skip the next WP.

### 3.7 Branch and commit hygiene

- WP5.4 and WP5.6's record retraction land on the existing **#6556** branch; get it green and
  merged **first**. Everything from Phase 6 onward is a fresh branch off `main`.
- **One PR per phase, stacked**: `fix/ai-tier-collection` (P6) → `feat/ai-contract` (P7) →
  `feat/ai-conformance` (P8) → `feat/ai-swap-guards` (P9). Never carry more than one phase in an
  open PR. Each PR body is assembled from its WP commit bodies and lists every MEASURE number.
- Draft PR into `main` opened at the **start** of each phase — `ci.yml` fires nowhere else.
- One WP per commit where the WP is small; one file group per commit where it is not. Never mix a
  workflow change with a test change with a deletion.
- **Every commit body carries its MEASURE numbers.** "Improved coverage" without a number is not
  done. Every DECIDE gets a ledger row before the commit that depends on it.
- Never force-push a branch with a live PR. Rebase on `main` at the start of each phase.

### 3.8 L hygiene

L is 5,199 lines / 408 KB. **Append-only at EOF, one `## HEADING (date)` section per WP**, matching
the existing format. Never edit an existing section except to mark a RULING resolved. To read it,
`grep -n '^## ' L | tail -30` and read only the section you need. Do not read L whole.

---

# Phase 5 — Repair the instruments (hours 0–13)

Expect Phase 5 to _increase_ visible failures and _reveal_ sub-floor coverage. That is the fix
working. Publish the number; do not move the line.

### WP5.0: Pre-flight — four probes, cap 3h total

Four environment facts can each silently invalidate days of work.

**(a) pre-commit — cap 45 min.** `pre-commit` is not installed and is not a project dependency
(`importlib.util.find_spec("pre_commit")` → None); `.git/hooks/` holds only `.sample` files;
`hadolint` is absent; the semgrep hook needs python3.12. If you cannot build the hook environments,
you face a choice between not committing and `--no-verify`, which is forbidden — so resolve it
**before the first commit**, not at the first commit.

- Verify `pre-commit install && pre-commit install --hook-type pre-push` succeeds and every hook
  environment builds. If it does not, repair it (add to dev deps / install the missing linters) as
  the **first commit of the run**.
- **If the sandbox has no outbound network and hook envs cannot be built:** record it in L, and use
  `pre-commit run --all-files` locally against whatever hooks _do_ build, plus `ruff check`,
  `ruff format --check` and `mypy backend` run explicitly before every commit. Document in every
  commit body which gates ran. Do **not** `--no-verify`.

**(b) Neutralize the repo-root `.env` — cap 45 min.** `backend/core/config.py:52` sets
`env_file=".env"` and CI has none. Eight integration failures reproduce deterministically in
isolation even under CI's env block — four `assert 4001 == 1008` in `test_websocket_auth.py`, a
`DID NOT RAISE ValidationError` in `test_config_validation.py`, an `assert 200 == 500`, and a
host-dependent disk-usage assertion — yet `main`'s last green run shows the WebSocket integration
job succeeding. Until `.env` is neutralized these are phantoms.

- There are 69 `env_file=` sites repo-wide and `env_file=".env"` resolves relative to CWD, so there
  is no single general mechanism. **Do not try to solve this generally.**
- **Bounded option set, pick one, record it in L:** (i) a test wrapper script exporting CI's exact
  env block (`DATABASE_URL`, `TEST_DATABASE_URL`, `REDIS_URL/HOST/PORT`, `LOG_DB_ENABLED=false`,
  `ENVIRONMENT=development`, `CI=true`) and running pytest from a directory with no `.env`;
  (ii) a session-scoped autouse fixture that monkeypatches the settings source; (iii) running
  pytest from a sibling CWD.
- **Fallback at the cap:** take option (i), record the residual in L, proceed. **Do not delete or
  edit the owner's `.env`.**
- **MEASURE:** how many of the 8 phantom failures survive neutralization. Survivors are real.

**(c) Postgres durability — cap 45 min.** Integration wall-clock is ~20x dominated by durability,
not CPU. On the evidence host the same 220 tests took **178.33s** untuned vs **9.01s** with
`fsync=off`, `synchronous_commit=off`, `full_page_writes=off` and a tmpfs datadir — identical user
CPU (~1m20) both runs, so the delta is pure I/O wait. Full tier: ~90 min projected untuned vs
**3m37** tuned. This is the largest throughput lever in the plan.

- **MEASURE:** `uv run pytest backend/tests/integration/repositories backend/tests/integration/
models -n 8 --timeout=30`, before and (if tuning the host Postgres is available) after.
- If tuning is not available on the sandbox's host Postgres, record that and **rebudget every
  integration run in this plan accordingly** — it is the difference between ~5 runs/hour and ~0.7.

**(d) Prove the CI round trip — cap 30 min.** Six Done-when clauses in this plan require a real
GitHub Actions run. The repo carries local-path remotes (e.g. `agent-nemo2 →
/agents/agent-nemo2/workspace`) alongside `origin`, so a push to the wrong remote silently produces
no CI.

- Push an empty commit to a throwaway branch, `gh pr create --draft` into `main`, confirm a run
  appears with `gh run list`, read one conclusion with `gh run view`. Confirm the push went to
  `origin`.
- **`gh pr edit` is broken here** — use `gh api -X PATCH repos/{owner}/{repo}/pulls/{n}` for any PR
  metadata change, and do not rely on `gh pr ready`.
- **Fallback:** if the round trip fails, record it in L, mark every CI-dependent Done-when as
  `DEFERRED-NO-CI`, and discharge those WPs structurally via
  `backend/tests/integration/test_github_workflows.py` assertions alone. **Spend no more than 30
  further minutes on CI access.** Phases 7 and 8 need no CI and are the deliverable.

**Done when:** all four probes have a recorded verdict in L, and the run's baseline numbers are
written down. Commit.

### WP5.1: D1 — make backend coverage actually merge. Cap 3h

**Files:** `.github/workflows/ci.yml:365-390,418-472`; `backend/tests/integration/
test_github_workflows.py`

Unit shards emit `--cov-report=xml:coverage-unit-shard-N.xml` (`:369`) and upload only that XML
(`:386-390`). The merge job tests `compgen -G ".coverage.*"` (`:436`), which an XML filename cannot
match. Every run therefore takes the `touch .coverage` branch (`:459`), and `merged=true` (`:455`)
— the flag that publishes `coverage-baseline.json` (`:466-472`) — **never fires**. Downstream,
`test-coverage-gate.yml`'s baseline-fetch finds no artifact and takes its documented honest skip.
**The 85% floor is enforced by zero gates on a PR.** Note also `--cov-fail-under=0` at `:365`.

**Three traps that will each silently no-op the fix and burn a CI round trip:**

1. **Hidden files.** `.coverage.shard-N` begins with a dot. `ci.yml` uses
   `actions/upload-artifact` **v6**, which excludes hidden files by default, and
   `grep -rn include-hidden-files .github/workflows/` returns **0**. The artifact uploads empty and
   the run looks identical to today's. Either add `include-hidden-files: true` to the upload, or
   copy the data file to a non-hidden name before upload and `mv` it back in the merge job.
2. **Download path.** `:421-425` downloads with `path: coverage-reports/`, but `compgen -G
".coverage.*"` at `:436` runs in the job CWD. Adding a data file to the existing artifact
   changes nothing. Setting `path: .` fixes compgen but breaks `find coverage-reports/ -name
"*.xml"` at `:430`. Prefer moving the combine step to operate on `coverage-reports/` explicitly.
3. **Artifact-name glob.** The merge downloads `pattern: coverage-unit-shard-*`.
   `scripts/test_shard_retry_wiring.py:178-179` pin-tests exactly this class of glob coupling for
   the integration tier. **Keep the artifact name
   `coverage-unit-shard-${{ matrix.shard }}-py${{ matrix.python-version }}` unchanged.** Renaming it
   to describe its new contents breaks the download with no error — it just finds nothing.

Note: pytest-cov already writes a `.coverage` data file per shard today. The shards need a
rename/upload step, not a new `--cov-report`.

- [ ] Red first: assert in `test_github_workflows.py` that every unit shard uploads a coverage
      _data_ file whose name the merge job's glob matches, **and** that the upload sets
      `include-hidden-files: true` (or the non-hidden rename exists), **and** that the artifact name
      pattern still matches the download `pattern:`. Watch it fail.
- [ ] Fix. Keep the per-shard XML for Codecov.
- [ ] Green the test. Land on the draft PR and watch a real run: `merged=true` must fire and
      `coverage-baseline.json` must publish.
- [ ] **MEASURE:** the first real merged backend coverage percentage this repo has ever produced in
      CI. **Record it in L before any Phase 7 commit lands** (see WP7.1's coverage-denominator note).

**Done when:** a CI run shows `merged=true`, publishes a non-vacuous `coverage-baseline.json`, and
`test-coverage-gate.yml` stops taking its honest skip. (Or `DEFERRED-NO-CI` per WP5.0(d), with the
structural assertions green.)

### WP5.2: D2 — frontend shards compute coverage. Cap 5h. **Lands REPORTING, not enforcing**

**Files:** `.github/workflows/ci.yml:1411,1428-1430,1444,1452-1487`; `frontend/package.json`

`ci.yml:1411` and `:1444` run `npx vitest run --shard=N/8` with no `--coverage`, under a comment at
`:1428-1430` saying not to add it because per-shard thresholds fail at ~6% each. That reasoning is
right about _per-shard_ thresholds and wrong as a conclusion.

**This is not a one-line flag addition.** `frontend-coverage-merge` (`:1459-1487`) **does not merge
and does not enforce**: it downloads `frontend-coverage-shard-*-node-*` into `coverage-reports/` and
hands the directory to codecov-action. There is no istanbul/v8 merge step and no threshold step.
Worse, `merge-multiple: true` flattens 8 shards whose uploaded path is `frontend/coverage/` — every
shard produces an identically-named `coverage-final.json`, so they collide and one shard's data
survives.

**Four pieces are required:**

1. Add `nyc` or `istanbul-lib-coverage` to `frontend` devDependencies.
2. Give each shard a distinct coverage output directory/filename so `merge-multiple` cannot collide.
3. Write an actual merge step in `frontend-coverage-merge`.
4. Write a threshold-**reporting** step (see below).

Vitest has no "disable thresholds" switch. Per-shard runs need explicit
`--coverage.thresholds.statements=0 --coverage.thresholds.branches=0
--coverage.thresholds.functions=0 --coverage.thresholds.lines=0`, or a second config file.

**DECIDE is pre-supplied: the merge job lands REPORTING.** Measured actuals are
**80.00 / 74.61 / 78.44 / 80.93** against thresholds **83 / 77 / 81 / 84**
(`frontend/vite.config.ts:421-428`) — a 2.4-to-3.1-point shortfall on all four metrics. Lowering is
forbidden; adding sources to `exclude` is forbidden. **There is no compliant lever that closes this
gap inside this WP,** so publish all four numbers and stage the enforcement flip as a parked RULING.
An unattended agent does not get to decide when `main` goes red.

The one honest lever is quarantine repair: `vite.config.ts:357-377` excludes 16 test files (62
deterministic failures + 3 zero-byte files) from the _run_, but the coverage `include` is still
`src/**/*.{ts,tsx}` and the exclude list does **not** exclude those components' sources — their
lines sit in the denominator with near-zero coverage. Repairing it **lowers** `frontend_quarantine`
(16) and possibly `collection_allowlist` (4, which carries the 3 zero-byte files): that is a ratchet
**decrease**, which per §3.3 you land yourself with `ratchet-check.py --update` and the `ci.yml:107`
literal in the same commit.

- [ ] Red first in `test_github_workflows.py`: every frontend shard passes `--coverage` with
      thresholds zeroed, and exactly one job merges and reports.
- [ ] Build the four pieces. **MEASURE** merged four-metric coverage.
- [ ] If hours permit inside the cap, repair the highest-yield quarantine entries and re-measure.
      Do **not** add sources to the coverage `exclude` list.

**Done when:** the merge job holds a real four-metric number, that number is in L, no threshold has
been reduced, and any census category that fell is reflected in both `suppression-baseline.json` and
the `ci.yml:107` literal.

### WP5.3: The 80-vs-85 discrepancy — RULING, parked. Cap 20 min

`pyproject.toml:557` declares `fail_under = 85`; both pytest invocations pass `--cov-fail-under=0`
so it can never fire. The only combined gate that executes anywhere is `scripts/validate.sh:376` at
`--fail-under=80`, mirrored by `nightly-full-gate.yml:140`. With D1, the real enforced backend floor
repo-wide is **80% nightly, 0% on PRs**.

- [ ] Write the RULING packet into L: three declared numbers, their enforcement status, the WP5.1
      measured actual, your recommendation. **Do not move either number.** Commit (docs-only).

### WP5.4: D5 — remove the env probe. Cap 1h

PR #6556 is blocked on Collection Sanity: `pytest_skip_imperative` census = 94, `--expect` literal = 93. Verified: on `docs/vss-integration` HEAD the census returns exactly 93. **The 94 exists only on
#6556** — the WIP added one unregistered imperative skip, a `pytest.skip("Symlinks not supported on
this filesystem")` at `backend/tests/unit/api/routes/test_media.py:120`.

**The skip must be REMOVED, not registered.** Registering it is a ratchet _increase_, and
`ratchet-check.py:8-13` says in two places that the adjudication must be a human's diff. With the
owner away, you are that human, and blessing one self-adjudicated increase hands you a template for
absorbing every later one. That is how a ratchet dies.

- [ ] Make the test use a path guaranteed to support symlinks (`tmp_path` on the sandbox's
      filesystem does). The census then returns to 93 and nothing is registered.
- [ ] **MEASURE:** `scripts/suppression-census.py` output before and after, all 13 categories. Only
      `pytest_skip_imperative` may move, and only downward.
- [ ] **If and only if removal proves impossible:** park a RULING in L with the proposed registry
      entry written out, and leave #6556 blocked. **A blocked PR is a cheaper outcome than a
      self-adjudicated ratchet.** Do not stall on it; advance to WP5.5.

**Done when:** Collection Sanity is green on #6556 with 93, or the RULING is parked and you have
moved on.

### WP5.5: Reachability and swap-bucket classification sweep. Cap 3h

**Files:** create `scripts/ai-surface-census.py`, `scripts/test_ai_surface_census.py`; modify L

Runs **before** any deletion, so the general rule (§3.5) governs the two known-bad records rather
than being retrofitted to them.

Classify every module in `backend/services/` into exactly one bucket:

| Bucket      | Meaning                                | Swap implication                   |
| ----------- | -------------------------------------- | ---------------------------------- |
| `HTTP-AI`   | talks to an AI server over HTTP        | in the conformance contract        |
| `INPROC-AI` | loads a model into the backend process | second seam; scope RULING required |
| `DOMAIN`    | pure business logic                    | unaffected by a swap               |
| `DEAD`      | zero non-test importers                | delete under the carve-out         |

The `INPROC-AI` bucket is not hypothetical: `backend/services` holds 22 `*_loader.py` modules, 21 of
which import torch/transformers/ultralytics **directly into the backend process**, plus
`face_detector.py`, `plate_detector.py`, `ocr_service.py`, `scene_ocr_service.py` and the
`ai_services.py:36-350` DI wrappers. An HTTP-level conformance suite leaves that entire tier
unguarded.

- [ ] Red first: TDD the census script against fixtures (a known-dead module, a known-live module, a
      client-bypass module). Run under `.venv/bin/python`.
- [ ] Include **client-bypass** cases explicitly — they are what an extraction most easily misses:
      `scene_ocr_service.py:526,634` builds a raw httpx POST to `/ocr-with-regions` rather than
      going through `FlorenceClient`; `nemotron_streaming.py:99` reaches into the private
      `analyzer._llm_url`. Bypasses are `HTTP-AI`.
- [ ] **MEASURE:** module count per bucket; total lines in `DEAD`; client-bypass call-site count.
      Reference anchors: 18 non-test files reference an AI client, 12 import one directly, 27
      client-method invocation sites.
- [ ] Write the bucket table into L.

**Done when:** every `backend/services` module carries exactly one bucket in L, and the `INPROC-AI`
count is a written number rather than an impression.

### WP5.6: Retract the bad mutation records and delete the dead modules. Cap 2h

WP4.4 minted surviving-mutant records for `job_state_service.py` (385 lines, **zero** non-test
importers) and `scene_change_service.py` (192 lines, exactly one — the re-export at
`backend/services/__init__.py:318`; the live path is `scene_change_detector`, imported at
`enrichment_pipeline.py:141`). 577 lines. Under WP4.4's own no-deletion-without-a-record rule, those
records now **protect dead code**. The ratchet is running backwards.

- [ ] Re-verify the census independently, including non-test callers of every symbol the
      `__init__.py` re-export exposes.
- [ ] **MEASURE:** importer count and line count per module (reference: 0/385 and 1/192), plus the
      same for every module WP5.5 classified `DEAD`.
- [ ] Delete under the carve-out, **one module per commit**, census number in each body. Retract the
      surviving-mutant records **by name in L** in the same commits.
- [ ] Census decreases: `ratchet-check.py --update` + the `ci.yml:107` literal in the same commit.

**Done when:** no surviving-mutant record in L protects a module with zero non-test importers.

> **Not deleted here:** `backend/tests/integration/test_system.py` (a 9-line `from ... import *`
> shim whose docstring says it exists "to satisfy the naming convention check", which collects the
> same 74 tests a second time in any whole-tree run). It is a **test file**, and the carve-out
> covers production AI surface only. Census whether any gate actually enforces that naming
> convention, and record it in L as a **deletion proposal for the owner**.

---

# Phase 6 — Turn on the tier being swapped (hours 13–27)

> **ORDERING HAZARD — read before starting.** Fix collection **first**; add `ai` to the gate
> **last**. If `ai` is added to `ci.yml:93` before the repair and triage, the gate lands red, and a
> red gate under schedule pressure is precisely the condition under which allowlists get widened.
> WP6.5 is gated on WP6.1–6.4.
>
> **Second hazard:** `uv run --no-project python scripts/check-test-collection.py ai` **passes
> today**, in 0.159s, reporting "230 tracked files scanned, all collect >= 1 test." The script is
> AST-based and never imports, so it cannot see the 19 whole-tree import errors. Adding `ai` to that
> gate is cheap and **not sufficient**. A separate `pytest ai/ --collect-only` gate is required.

### WP6.1: Kill the `sys.modules` poisoning. Cap 2h

`ai/enrichment/test_model.py:46-48` installs fake modules into `sys.modules` at **import time**
(`sys.modules["ai"] = _mock_ai`, plus `ai.enrichment` and `ai.enrichment.vitpose`). pytest imports
it during collection, poisoning the whole process for every subsequently collected file.

A/B, verified: `pytest ai/ --collect-only` = **387 collected / 19 errors**; with
`--ignore=ai/enrichment/test_model.py` = **1,343 / 7**. One statement hides 956 tests and 12 of the
19 errors.

- [ ] Red first: assert `sys.modules["ai"]` is the real package after full `ai/` collection.
- [ ] Move the mock installation inside a fixture with teardown, or use
      `monkeypatch.setitem(sys.modules, ...)`. **DECIDE** which; the constraint is that nothing
      mutates `sys.modules` at module scope. Note `from model import (...)` at the bottom of that
      file depends on the flat-directory import style — **do not change it** (§1).
- [ ] **MEASURE:** collected/errors before and after. Reference 387/19 → ≥1,343/7.

### WP6.2: Stop `ai/` shadowing the pip `triton` package. Cap 2h

`ai/tests/conftest.py:13-15` inserts the `ai/` directory at `sys.path[0]`. The repo contains
`ai/triton/`, so that shadows the pip `triton`, turning a _graceful absence_ into transformers
lazy-import **hard failures** (5× `module 'triton' has no attribute 'language'`, 3× `GenerationMixin`,
3× `AutoModelForCausalLM`, 1× `CLIPModel`) — the remaining 7 collect errors.

> **`append` instead of `insert(0, ...)` is a verified NON-FIX.** pip `triton` is not installed in
> this venv at all. With `sys.path.append('ai')`, `import triton` still resolves to
> `ai/triton/__init__.py` with `hasattr(triton, 'language') == False`. Position is irrelevant when
> the real package is absent. Do not spend time on it.

- [ ] Red first: assert `import triton` either resolves outside the repo or raises
      `ModuleNotFoundError` during an `ai/` session.
- [ ] **DECIDE between two real options:** (i) scope the `ai/tests/conftest.py` insertion to a
      fixture with teardown; (ii) rename `ai/triton` — noting that a rename touches
      `ai/gateway/triton_client.py` and `ai/triton/model_repository/`, which
      `ai/gateway/Dockerfile:47` copies to `/models/repository/`, making it an
      **owner-review-required** Dockerfile-adjacent change. Option (i) is strongly
      preferred.
- [ ] **MEASURE:** whole-tree `ai/` collection errors after. Target 0.

### WP6.3: Fix the live `prompts.py` crash — without touching container imports. Cap 4h

`backend/services/prompts.py:4381`, inside `format_detections_with_quality()` (defined at :4348),
does a runtime `from ai.yolo26.model import ConfidenceQuality, EnhancedDetection,
enhance_detections`. That raises `ModuleNotFoundError: No module named 'metrics'` in the backend
process. Its only tests, in `backend/tests/unit/services/test_prompts.py`, assert the **signature**
rather than invoking the function — a production-path function is broken and 100% invisible to the
suite.

Merely making `ai.yolo26.model` importable would also pull torch and ultralytics into the backend
process at request time. **Re-read §1 before writing a single character here.**

- [ ] Red first, two tests: one that **calls** `format_detections_with_quality()` with real
      detections and asserts the formatted output; one that asserts `sys.modules` gains no `torch`
      entry as a result. Watch both fail.
- [ ] **DECIDE the fix**, preferring in this order:
      (i) move `ConfidenceQuality` / `EnhancedDetection` / `enhance_detections` into a new
      **pure-leaf** `ai/yolo26/contract.py` (stdlib + pydantic only, zero sibling imports, zero
      torch) and import it from `prompts.py` — but note `ai/yolo26/Dockerfile:75-83` is an explicit
      per-file COPY list, so **do not** make `ai/yolo26/model.py` import it; leave `model.py`'s copy
      in place and add the WP9.1 parity test, parking the Dockerfile wiring as a RULING;
      (ii) if (i) proves messy, relocate the three symbols into `backend/` and leave `ai/` untouched
      entirely, recording in L that `ai/yolo26/model.py` now holds a duplicate the parity checker
      guards.
- [ ] Extend the `ai/yolo26/model.py:104-107` and `ai/enrichment/model.py:38-40` shims to also
      insert `Path(__file__).parent`, so `from metrics import` and `from model_manager import`
      resolve from the repo as well as the flat container. **This is additive and touches no import
      statement.** Add `ai/clip/__init__.py` and `ai/nemotron/__init__.py` if and only if their
      absence blocks collection.
- [ ] **Do not** rename `ai/enrichment-light`. The hyphen makes it unimportable, but a rename
      touches compose build contexts and the Dockerfile. Park it as a RULING.
- [ ] **MEASURE:** `ai/*` modules importable from the backend venv, before and after; confirm the
      contract import costs no torch import.

**Done when:** `format_detections_with_quality()` executes in the backend process, torch is absent
from `sys.modules` afterwards, and no import statement in any `ai/*/model.py` was modified.

### WP6.4: Triage the 60 red `ai/` tests — time-boxed. Cap 5h

With collection repaired, the tier runs on CPU per-subtree and stands at **896 passed / 60 failed /
5 collect errors**. Measured per subtree: `ai/gateway` 217p/9f, `ai/yolo26` 252p/24f, `ai/tests`
323p/13f/13s, `ai/clip` 78p, `ai/triton` 25p/5f, `ai/enrichment-light` 1p/9f, `ai/enrichment/tests`
3 errors, `ai/florence` 2 errors. (Treat the "~35 seconds total" figure as optimistic: `ai/gateway/
tests` alone measured 38.7s at `-n0` on a 72-core box.)

**Scope, explicitly:** triage **all 60** into one of three classes; **fix only `ai/gateway`'s 9**,
because the gateway is the deployed provider and its reds are the natural first red for Phase 8.
Everything else is parked in L with a one-line classification each.

- [ ] Classes: **product defect** (fix, red-first), **test asserts a contract the provider does not
      ship** (fix the test against the shipped contract), **RULING-shaped** (park in L).
- [ ] Watch for the self-referential class: `ai/yolo26/test_model.py:160` and
      `ai/yolo26/tests/test_model.py:172` **both** assert `expected_classes == SECURITY_CLASSES` —
      the same tautology twice. A test that asserts a server's constants against themselves proves
      nothing about a swap. Flag them for Phase 8; do not expand them.
- [ ] **MEASURE:** per-subtree failures remaining; how many of the 60 were product vs test defects.
- [ ] Commit in subtree-sized batches.

**Done when:** all 60 are classified in L, `ai/gateway` is green, and no subtree is red for an
unrecorded reason.

### WP6.5: Wire `ai/` into CI — only after 6.1–6.4. Cap 2h

- [ ] Red first in `test_github_workflows.py`: `check-test-collection.py` receives `ai`, **and** a
      job runs `pytest ai/`, **and** a step runs `pytest ai/ --collect-only` failing on any collect
      error (the AST gate cannot see import errors; this is the one that can).
- [ ] Add `ai` to `ci.yml:93`. **DECIDE** per-subtree invocations vs whole-tree — per-subtree is
      safer given the conftest history, and the tier is cheap either way.
- [ ] **RULING (parked):** coverage `source = ["backend"]` excludes `ai/` entirely. Un-darkening it
      gives pass/fail signal but **no coverage number** until `source` is extended — and extending
      it moves the combined percentage. **Do not extend `source` unilaterally.**
- [ ] **MEASURE:** tests now gated that were not before (reference: 896+ vs 387 previously
      collected).

**Done when:** a deliberately broken test under `ai/` turns CI red and the `ai/` job is in
`ci-gate`'s needs list. (Or `DEFERRED-NO-CI` with the structural assertions green.)

---

# Phase 7 — The contract (hours 27–43)

Pure Python: no GPU, no containers, no weights. **Built from the deployed surfaces.**

### WP7.1: `backend/ai_contract/` — the 38-operation registry. Cap 6h

**Files:** create `backend/ai_contract/{__init__,operations,provider}.py`,
`backend/ai_contract/schemas/`, `scripts/gen-ai-contract.py`, `scripts/test_gen_ai_contract.py`

**Contract sources, in priority order:**

1. `ai/gateway/adapters/*.py` — **deployed**, importable in the backend venv today, 226 local tests.
2. The six backend clients — the deployed consumer side.
3. `ai/nemotron/model_hf.py` + the llama.cpp wire shape — `ai-llm` is deployed.
4. _(optional, later, only if hours allow)_ the five undeployed per-model servers.

One importable package declaring all 38 AI-tier operations. Per operation: stable id, HTTP method,
path, request model, response model, and a **provider availability matrix** (gateway /
enrichment-light-adapter / real-per-model-server / fake).

**Architecture decision, state it in the module docstring:** the backend must **never import `ai.*`
at runtime**. The servers ship in containers without the backend package, and that dependency
direction is exactly what made `prompts.py:4381` a live crash. `scripts/gen-ai-contract.py` imports
the adapter modules **at generation time**, emits `backend/ai_contract/schemas/`, and CI re-runs the
generator and diffs. That is a drift gate, not a shared import.

**DECIDE package location — recommendation `backend/ai_contract/`** (coverage `source = ["backend"]`
gates it for free). **Consequence you must control for:** this puts the generated `schemas/`
directory and, later, the FakeProvider's FastAPI app into the coverage denominator on the same PRs
where WP5.1 first makes backend coverage compute. **Take and record the WP5.1 baseline MEASURE
before the first `ai_contract` commit lands**, then re-measure and report the delta attributable to
the new package separately. Decide once in L whether generated schema files are code or data — **do
not edit the omit list.**

**The LLM operation has no seam at all.** Six modules independently construct
`POST {llm_url}/completion`: `nemotron_analyzer.py:465,1046,3978`, `summary_generator.py:440`,
`nemotron_streaming.py:99` (via the private `analyzer._llm_url`), `prompt_service.py:938`,
`pipeline_quality_audit_service.py:391`, `evaluation/harness.py:549`. Consolidating them is a
prerequisite to any LLM-side swap and the highest-churn part of the extraction. **DECIDE** whether
consolidation lands here or is a recorded follow-on; if it slips, write all seven sites into L so
the next agent does not rediscover them.

- [ ] Red first: assert the registry contains all 38 operations and that every non-test
      client-method invocation site maps to one.
- [ ] TDD the generator.
- [ ] **MEASURE:** operations registered (38); call sites mapped (reference: 27 in 18 non-test
      files). Extraction estimate **300–600 lines**. **If it exceeds 900, stop and record why in L
      before continuing.**

**Done when:** `backend/ai_contract` imports with no `ai.*` runtime dependency, covers 38
operations, and the availability matrix is generated rather than hand-maintained.

### WP7.2: Golden fixtures and JSON-Schema snapshots. Cap 4h

**Files:** `backend/tests/contracts/ai_providers/golden/`,
`backend/tests/contracts/ai_providers/test_schema_snapshots.py`; CI

Two artifacts. **Golden fixtures** — wire payloads generated from the contract models, imported by
_both_ sides, replacing hand-written dicts. **JSON-Schema snapshots** — `model_json_schema()` per
endpoint, committed, diffed in CI. Any future provider (VSS included) that renames a key fails the
build. Pure static generation: the cheapest permanent swap guard in this plan.

`backend/tests/contracts/` is the natural home and is currently the wrong shape:
`test_api_contracts.py:231` validates only our **outbound** OpenAPI (events, cameras, detections,
health) and never an **inbound** AI-provider payload.

- [ ] Red first: a snapshot test with an empty golden directory.
- [ ] Generate goldens from the contract models. Mark generated files clearly; never hand-edit them.
- [ ] CI failure message must **name the renamed key**.
- [ ] **MEASURE:** endpoints with a committed snapshot; goldens generated; hand-written dicts they
      can replace. Census reference: **572** hand-written AI-response dict literals across **110**
      backend test files (88 detection items in 4 key-shapes; 122 detect-responses in 26 key-shapes;
      244 llm_risk dicts in 38 shapes; 58 OCR-ish in 15; 24 embedding dicts in 8).

**Done when:** renaming a key in a contract model reddens CI with a message naming the key.

### WP7.3: Availability matrix + carve-out deletions. Cap 3h

The matrix is where verified gaps become machine-readable. **Ranked by deployment status — Tier A
gaps are live in production today; Tier B are latent on an undeployed path.**

**Tier A — live under `docker-compose.prod.yml`:**

| Gap                                                                                                                                     | Evidence                                                                                                                                                                                                                                                                                            |
| --------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **bbox shape 422** on `/enrichment/{vehicle,clothing,demographics}-classify`                                                            | `adapters/enrichment.py:289` types `bbox: dict[str,float]`; `enrichment_client.py:1203` sends `list(bbox)`; those three services default to `heavy` (`compose:474-477`)                                                                                                                             |
| `models/status`, `models/preload`, `models/unload`, `object-distance` **do not exist on the gateway**                                   | `grep` over `ai/gateway/adapters/` returns **0** hits. `EnrichmentClient.get_model_status`, `.preload_model` and all of `backend/api/routes/model_management.py` **404 in production today**                                                                                                        |
| backend posts `POST /models/{name}/unload`; the real heavy server route is `POST /models/unload` with `model_name` as a **query** param | `model_management.py:560,639` vs `ai/enrichment/model.py:3545` — a 404 even against the undeployed server                                                                                                                                                                                           |
| `/segment` exists **only** on the gateway                                                                                               | `adapters/yolo26.py:447`; `grep -c segment ai/yolo26/model.py` = **0**. Client method has zero non-test callers                                                                                                                                                                                     |
| **class vocabulary 9 vs 81**                                                                                                            | `ai/yolo26/model.py:143` and `ai/triton/client.py:230` filter to 9 `SECURITY_CLASSES`; `adapters/yolo26.py:186` does **not** filter and returns all 80 COCO names plus a synthetic `class_{id}`. **The deployed provider is the unfiltered one**, and `detections.object_type` has no DB constraint |
| geometry rounding                                                                                                                       | `adapters/yolo26.py:199` uses `round()`; `ai/yolo26/model.py:1413` uses `int()` truncation                                                                                                                                                                                                          |
| CLIP validation divergence                                                                                                              | gateway types `camera_type` as bare `str` vs the server's `CameraType` enum; gateway lacks the server's `MAX_BATCH_TEXTS_SIZE` `field_validator` (DoS-shaped)                                                                                                                                       |

**Tier B — latent (undeployed native-host path only):** the enrichment-**light server**'s
`ImageRequest`/`PoseAnalyzeRequest` field-name 422s for `classify_pet` / `estimate_depth`. The
deployed `/enrich-lt` route is served by `adapters/enrichment_light.py:43-68`, which declares
`populate_by_name` with `alias="image_base64"` and types `bbox` as `dict | list | None` — **it
accepts the client's payload.** Record these as latent; do not lead with them.

**Tier C — swap-forward risks (not live, but they break provider #4):** `/v1/completions` (served by
llama.cpp, absent from `ai/nemotron/model_hf.py`, which implements `/v1/chat/completions` at :664);
`/slots` (llama.cpp-only, scraped by `performance_collector.py:214`). Any non-llama.cpp provider —
including VSS — silently loses warmup and that metric.

**Zero-caller carry-cost, pre-approved for deletion under the carve-out** (re-verify each census
first, number in the commit body): `detect_objects_batch`, `segment_image`, `similarity`,
`estimate_depth`, `estimate_object_distance`; florence `/analyze-scene` (implemented on **both**
providers, called by nobody); yolo26 `/track`.

- [ ] Red first per deletion: a census assertion that the symbol has zero non-test call sites.
- [ ] One commit per method. Ratchet decreases handled per §3.3.
- [ ] **MEASURE:** methods deleted; lines removed; call sites re-verified.

### WP7.4: Migrate the impossible fixtures — demonstration scope. Cap 4h

**Scope this small deliberately: parametrize `test_detector_client.py` and
`test_detector_client_integration.py` over both shapes, and migrate the 27 impossible
detect-responses. The remaining ~545 dicts are a recorded follow-on, and are the designated overflow
work if hours remain (see §Autonomy).**

The most persuasive artifact in this plan, reproducible in under a minute: the same 3-detection
scene routed through `DetectorClient` returns **3 unclamped detections with `video_width=None`**
under the current fixture shape, and **2 clamped detections with `video_width=640`** under the
shipped shape (300×400 → 300×330; 200×150 → 140×150). **74/74 tests pass either way.** Two code
paths, one green file. Reproduce it first and put the transcript in L.

Of 122 detect-response fixtures, **27** use `{detections, image_size, processing_time_ms}` — a shape
**no provider emits** — against only **4** correct `{detections, image_height, image_width,
inference_time_ms}`. The canonical fixture is impossible on a second axis: `test_detector_client.py:
69` annotates a dog at confidence 0.45 as "(at threshold of 0.45, passes)", but `ai/yolo26/
model.py:174` drops any dog below 0.55.

> **The warning that makes or breaks this WP.** Do **not** discharge "align tests to the shipped
> contract" by rewriting every detector fixture to the dict shape. That flips which branch is
> covered and silently drops coverage of the list branch `detect_objects` still accepts. **Parametrize
> over both accepted shapes while pinning which one the deployed provider produces.**

- [ ] **MEASURE:** dicts replaced (of 572); `detector_client.py` coverage before and after — it must
      not fall.

---

# Phase 8 — Conformance (hours 43–63)

The deliverable. Entirely GPU-free and container-free, which is precisely why it is the right use of
this sandbox.

### WP8.1: Declare the interface that already shipped. Cap 4h

**Files:** `ai/gateway/adapters/__init__.py`; `backend/core/protocols.py:76-144`;
`backend/ai_contract/provider.py`

- [ ] Red first: assert every registered provider satisfies the Protocol via `runtime_checkable`
      **plus an `inspect.signature` check against the contract**. Attribute presence alone is what
      let `AIServiceProtocol` rot — do not reproduce it.
- [ ] Define `AIProvider` over the WP7.1 registry: provider id → adapter set → availability matrix.
- [ ] **DECIDE:** repair `AIServiceProtocol` in place, or deprecate it and point
      `backend/core/__init__.py:113,166` at the new Protocol. A Protocol nothing implements is worse
      than no Protocol; the decorative one must not survive either way.
- [ ] Register the providers: `gateway` (deployed), `gateway-light` (the `/enrich-lt` slot),
      `llamacpp-llm` (deployed), and — matrix-declared as undeployed — `per-model-http`.
- [ ] **MEASURE:** operations declared; providers registered; signature mismatches caught at
      registration.

**Done when:** adding a provider that omits a declared operation fails a test **at import time**,
naming the operation.

### WP8.2: The deterministic FakeProvider. Cap 5h

**Files:** `backend/ai_contract/fake/` (FastAPI app + seeded generators),
`backend/tests/contracts/ai_providers/test_fake_provider.py`

A FastAPI app implementing all 38 operations with fixed, seeded outputs, served over
`httpx.ASGITransport`. Simultaneously the **reference implementation** of the interface and the
**fixture source** for every downstream service test. No weights, no GPU, no network. It must be
byte-deterministic, fit the 5s per-test timeout, and run correctly under `pytest-randomly`.

It must emit shipped-correct values:

- `SECURITY_CLASSES` (9) for the filtered provider, and the unfiltered 81 for the gateway profile —
  **the divergence is the point; the fake must be able to express both.**
- bbox **dict** `{x,y,width,height}` of ints for yolo26; bbox **list** `[x1,y1,x2,y2]` floats for
  florence.
- `inference_time_ms` — never `processing_time_ms`.
- 768-dim **L2-normalized** CLIP embeddings.
- `class` as the detection key (a pydantic alias over `class_name`).

- [ ] Red first: two identical requests produce byte-identical responses; the fake satisfies the
      WP8.1 Protocol.
- [ ] Drive it from the contract models so it cannot drift from the schema.
- [ ] **MEASURE:** operations implemented (38/38); wall-clock for a full fake-backed pass.

### WP8.3: The conformance suite. Cap 8h

**Files:** `backend/tests/contracts/ai_providers/test_conformance.py` + per-property modules

One parametrized suite running the **same assertions** against every registered provider.

**Mechanical detail that will otherwise cost an hour:** the gateway adapters take no injected
client. Each calls a **module-level** `get_triton_client()` imported at the top of its own module —
`adapters/yolo26.py:28`, `adapters/enrichment.py:31`, `adapters/enrichment_light.py:30`,
`adapters/florence.py:39`, and the clip adapter. **Patching is per-adapter-module: five distinct
targets.** A suite that patches one symbol silently exercises a real gRPC client for four of five.
Carry the patch target as **provider metadata** in the parametrization. Copy the working template at
`ai/gateway/tests/test_adapters_yolo26.py:99-104` rather than inventing one. (Note: importing
`ai.gateway.main` does pull `torch` via `adapters/clip.py:36`; the CPU wheel is installed and the
import succeeds — no GPU, no Triton.)

**Properties to assert.** These are the properties a swap breaks, and none is asserted anywhere
today.

_Geometry and encoding_

- yolo26 bbox: dict of **ints**, absolute pixels, top-left origin, from model xyxy by `int()`
  **truncation** (`ai/yolo26/model.py:1413`); the gateway uses `round()` (`adapters/yolo26.py:199`).
- Florence bbox: **list** `[x1,y1,x2,y2]` floats. **Opposite convention, same pipeline.** A bare
  4-element list is ambiguous repo-wide, and 180 corpus fixtures use one.
- Florence OCR regions return **eight** floats — quadrilateral corners flattened from `quad_boxes`
  (`ai/florence/model.py:190,1101`). Unpacking 4 raises; slicing `[:4]` gets a wrong box.
- A **fourth** spelling exists in enrichment: `{x1,y1,x2,y2}` dicts (30 literals).
- `backend/services/bbox_validation.py:7` asserts a **false** global invariant in its docstring
  ("All bounding boxes in this system use the format (x1,y1,x2,y2)"). Feeding it a yolo xywh box
  `(100,150,300,400)` passes every check and silently reinterprets a 300×400 box at (100,150) as a
  200×250 box. Callers at `reid_service.py:482` and `enrichment_client.py:1965` are unprotected.
- A provider emitting normalized [0,1] floats truncates to 0 in the Integer DB columns
  (`backend/models/detection.py:55`) with no error.
- `FlorenceClient.detect` performs **zero** validation of bbox arity, dtype or convention
  (`florence_client.py:1101`); Florence detection `score` defaults to **1.0** when absent
  (`ai/florence/model.py:208`), so an omitted confidence becomes maximum confidence.

_Vocabulary — the property a swap changes first, with no enforcement anywhere_

- 9 vs 81 classes (Tier A above).
- Two divergent per-class confidence tables filter the same stream in series: server (person 0.45,
  car/truck/bus 0.70, moto/bike 0.65, dog/cat/bird 0.55) and backend (`config.py:1694`, every value
  lower, plus backpack/handbag/suitcase entries that can never fire because the server drops those
  classes).
- Three names for one concept: `class` (yolo), `label` (florence), `type` falling back to
  `class_name` (enrichment threat, `enrichment_pipeline.py:3890`).
- `detections` must be **present and a list**. Absence — not emptiness — routes to the
  `malformed_response` metric (`detector_client.py:1419`), turning "nothing detected" into a
  recorded pipeline error.

_Numeric invariants_

- CLIP embeddings: 768-dim **and L2-normalized**, epsilon-guarded (`ai/clip/model.py:800`). 87
  fixed-dim embedding literals exist in `backend/tests` and **not one** asserts unit norm; the
  canonical `[0.1] * 768` has L2 norm 2.77 and is commented "# Normalized CLIP embedding".
- `/classify` scores are a **softmax over exactly the requested labels**, summing to 1.0, with
  `top_label` a member of that list. A SigLIP-style provider returns independent per-label
  probabilities and every absolute threshold downstream shifts — and the gateway **already** swaps
  CLIP ViT-L for SigLIP-2 at the same 768 dims.
- `similarity` is cosine in [-1,1]; `anomaly_score` is `ge=0.0/le=1.0` computed **assuming unit-norm
  inputs**.
- `risk_score` is an **integer** in [0,100] enforced at three layers with different strictness —
  guided_json, pydantic (`llm_response.py:393,436`, whose before-validator silently truncates floats
  and parses strings), and a Postgres CHECK (`event.py:241`). A provider returning 0–1 floats
  becomes 0 for everything below 1.0: valid, stored, catastrophically wrong.
- Competing dimensionalities with **inconsistent failure modes**: `scene_baseline.py:260` raises
  unless 768; `reid_matcher.py:57` defaults 512; `osnet_loader.py:347` silently pads/truncates to
  512; face identities are 512-dim ArcFace.
- `summary` carries a 200-char maxLength in the guided schema that `LLMRiskResponse` does **not**
  enforce.

_Semantics no schema can catch_

- Pose keypoints are **positional COCO-17** as `[[x,y,conf], ...]` in JSONB with **no names on the
  wire** (`backend/models/enrichment.py:53`). **Order is the entire contract.** BODY_25 /
  MediaPipe-33 / Halpe-26 produce structurally valid payloads with every joint mislabeled.
- `Entity.set_embedding(model="clip")` records an embedding-space tag; `get_embedding_model()` has
  **zero** production callers. Post-swap, cosine similarity compares vectors from two unrelated
  spaces and reports plausible numbers.
- Florence prompts are literal Florence-2 control tokens (`<CAPTION>`, `<OD>`, `<OCR_WITH_REGION>`…)
  passed through as `prompt` (`vision_extractor.py:673`). A VLM taking natural-language instructions
  echoes the token text back as a caption and every consumer accepts it.
- **Caption language is an unwritten contract.** `frontend/src/utils/severityCalculator.ts:56`
  classifies summaries by English keyword matching ('intruder', 'breach', 'weapon', 'loitering',
  'trespassing', 'routine', 'delivery').
- `nemotron_analyzer.py:154,4280` strips `<think>…</think>` by regex and treats an unclosed tag as
  "no reasoning" while passing the raw text through as JSON. A reasoning model using `<reasoning>`,
  OpenAI `reasoning_content` or Harmony channels has its chain-of-thought parsed as the payload.
- `frontend/src/utils/confidence.ts:12` **throws** if confidence is outside [0,1]. A provider
  emitting percentages crashes the detection UI rather than degrading.
- Four divergent risk-band tables for one 0–100 score: `llm_response.py:118` (0-29/30-59/60-84/
  85-100), `event.py:374`, `severity.py:155`, and the frontend's hardcoded `critical>=80, high>=60,
medium>=40, low>=20` (`severityCalculator.ts:99`). A backend "high" at 82 renders as "critical".
- OP 28 `action-classify` is the **only multi-frame operation in the whole contract** — the one place
  VSS's video-native models change the _shape_ rather than the implementation. Give it its own
  property block.
- The composite `/enrich` is the **highest-value single conformance target**: one call exercising the
  whole enrichment contract at once (`adapters/enrichment.py:899`).

**Procedure.**

- [ ] **Run the suite against the gateway provider in discovery mode before writing any fix, and
      record the first-run red count in L as the headline MEASURE of this plan.**
- [ ] Then land each divergence as either (a) a fix, making a real assertion green, or (b) a
      **characterization test** per §3.4 with a parked RULING. **The branch ends green.** Do not
      leave permanently-red tests and do not xfail/skip them.
- [ ] Where the availability matrix says an operation is genuinely absent on a provider, assert the
      **absence matches the matrix** — that is a green guard, not a skip.
- [ ] Assert properties in the order written above. **Anything unasserted at the cap is listed in L
      as the next agent's first task.**
- [ ] **MEASURE:** properties asserted; `(provider, operation)` pairs covered; first-run reds; reds
      converted to fixes vs parked.

**Done when:** the suite is green against FakeProvider and against the gateway, every divergence is
either fixed or pinned by a characterization test with a ledger reference, and a new provider is one
registration away.

### WP8.4: Drive the real clients through the suite. Cap 5h

**Files:** `backend/tests/contracts/ai_providers/test_client_conformance.py`; the six client test
modules

WP8.3 tests _providers_. This tests the **other half**, so the two can no longer stay green
independently. Today **zero** tests import `ai.*`; the `*_client_gateway.py` files assert only
base-URL **string** construction, and `ai/gateway/tests/test_adapters_enrichment.py` contains zero
occurrences of "bbox". That is why every divergence in this plan is invisible.

- [ ] Red first: point `DetectorClient` at the FakeProvider over `ASGITransport` and assert parsed
      output matches the golden.
- [ ] Repeat for `FlorenceClient`, `CLIPClient`, `EnrichmentClient`, `NemotronAnalyzer`, and the
      WP5.5 client-bypass sites (`scene_ocr_service.py:526,634`; `nemotron_streaming.py:99`).
- [ ] **Prove the Tier A defects at the ASGI level.** They cannot be proven against a live server
      here, and the ASGI proof is **the stronger artifact** because it runs in CI forever: the
      heavy-gateway bbox 422; the four missing `models/*` and `object-distance` 404s; the
      `/models/{name}/unload` path mismatch; `/segment` present only on the gateway; the CLIP
      `camera_type` and `MAX_BATCH_TEXTS_SIZE` divergences.
- [ ] Also pin: `EnrichmentClient.is_healthy` probes **only** the heavy base URL
      (`enrichment_client.py:1100,1149`), so a dead light service reads as healthy.
- [ ] **MEASURE:** client-method / provider pairs covered end-to-end; 422s and 404s reproduced.

**Done when:** renaming a response key in a contract model reddens a **client** test, not just a
schema snapshot.

### WP8.5: Vocabulary conformance against the database. Cap 3h

The database is already the de-facto conformance spec — enforced too late (at INSERT) and nowhere in
unit tests. Postgres is a host process here, so these are reproducible in minutes.

| Vocabulary  | Server emits                                                                              | DB CHECK allows                                   | Result                                                                           |
| ----------- | ----------------------------------------------------------------------------------------- | ------------------------------------------------- | -------------------------------------------------------------------------------- |
| pose class  | `ai/enrichment/vitpose.py:44` adds `walking`, `running`                                   | `enrichment.py:77` has neither                    | live constraint violation                                                        |
| age range   | `demographics.py:44` `21-35/36-50/51-65/65+`                                              | `enrichment.py:197` `21-30/31-40/…`               | 4 of 6 rejected                                                                  |
| threat type | `threat_detector.py:66,76` 12 values                                                      | `enrichment.py:139` 6 values                      | 9 of 12 rejected; `grenade`/`explosive` legal and produced by nothing            |
| gender      | `demographics.py:53` `GENDER_LABELS = ['female','male']` — **list index is the class id** | `enrichment.py:193` `('male','female','unknown')` | a provider reordering labels inverts every prediction while staying schema-valid |

And the safety-relevant one: `is_minor` is exact membership in the literal tuple
`('0-10','11-20','child','teenager')`, duplicated at `enrichment_pipeline.py:3868` and `:5324`. A
provider emitting `0-9`, `13-17`, `under_18` or `teen` yields `is_minor=False` **for every child in
frame**.

Conversely the two properties a swap changes first have **no enforcement anywhere**:
`detections.object_type` is an unconstrained String with a trigram index, and
`entities.embedding_vector` is free JSONB.

- [ ] Red first: a static cross-check that every server vocabulary constant is a subset of its DB
      CHECK. Four will fail.
- [ ] **Execute** the violations against the host Postgres and capture the raised errors in L. This
      converts each from static claim to reproduced failure.
- [ ] Add the missing invariants: `is_minor` membership, embedding dimensionality and unit norm,
      `risk_score` integrality.
- [ ] **RULING (parked), one per vocabulary:** widen the CHECK, or normalize at the client boundary?
      Pin today's behaviour with characterization tests, record the evidence, mark remediation
      RULING-blocked, move on. **Do not guess. Do not widen a CHECK on your own authority.**
- [ ] **MEASURE:** pairs checked; violations reproduced; `is_minor` false-negative inputs enumerated.

---

# Phase 9 — Permanent guards (hours 63–69)

### WP9.1: Static cross-provider parity checker. Cap 4h

**Files:** `scripts/check-ai-provider-parity.py`, `scripts/test_check_ai_provider_parity.py`; CI

AST-walk `ai/gateway/adapters/*.py`, the six client modules, and (where importable) `ai/*/model.py`;
extract `(method, route, payload keys, response keys)`; assert the sets agree or that a disagreement
is **declared in the WP7.3 availability matrix**. **Every defect in this plan would have been caught
automatically by this script**, and it is how provider #4 is prevented from drifting silently. It
also guards any duplicated `contract.py` that WP6.3 option (i)/(ii) left un-shared.

Run under `.venv/bin/python` (3.14.7).

- [ ] Red first: run it against the tree and confirm it reproduces the known Tier A/B/C list. **If it
      finds fewer, the checker is wrong, not the tree.**
- [ ] TDD against fixtures including a synthetic "provider renames a key" case.
- [ ] Wire into CI following WP1.3's ratchet shape; do not build parallel machinery.
- [ ] **MEASURE:** divergences detected vs the known list; false-positive rate; runtime.

### WP9.2: Declare the in-process AI tier in or out of scope. Cap 1h

From WP5.5: 22 `*_loader.py` modules (21 importing torch/transformers/ultralytics into the backend
process), plus `face_detector.py`, `plate_detector.py`, `ocr_service.py`, `scene_ocr_service.py` and
the `ai_services.py:36-350` DI wrappers. **Invisible to any HTTP-level conformance suite.**

- [ ] Write one unambiguous paragraph into `docs/vss-integration/` backed by the counted module
      list. **If out of scope, say so in those words, and say what remains unguarded** — otherwise
      "swap the AI pipeline" quietly means two different projects and the second is discovered
      mid-swap.
- [ ] **RULING (parked):** does the VSS swap cover the in-process tier? Commit (docs-only).

### WP9.3: CI economics — ongoing, no separate cap

`ci.yml` has 35 jobs against a measured 20-job concurrency cap (L, WP3.1). Batch 4–6 fixes per round
trip and spend wall-clock on local iteration: the full local loop is ~2 min unit + ~4 min tuned
integration + ~3 min frontend-with-coverage + `ai/` per-subtree — well under fifteen minutes.

- [ ] Open each phase's draft PR at the **start** of the phase; do not save pushes for the end.
- [ ] **MEASURE:** round trips consumed; jobs red on each.

---

# Phase 10 — Close (hours 69–71)

### WP10.1: Write up and stop. Cap 2h

- [ ] Handoff section in P: what landed, every MEASURE number, every parked RULING with its evidence
      and your recommendation, and the exact next WP with its first red-first step.
- [ ] List the full contents of any characterization-test set, by ruling id.
- [ ] Re-run the full local loop once more and record end-state numbers beside the WP5.0 baselines.
- [ ] State the CI state of each phase PR plainly, including anything red and why, and **state the
      order the PRs must be read in**.
- [ ] Commit. **Stop.**

**Done when:** an owner returning cold can read one ledger section and know the state, the numbers,
and the decisions waiting on them.

---

## Out of scope — and why

- **Further WP4.4 band drain.** Actively harmful at the margin: its no-deletion-without-a-record
  rule converted 577 lines of dead code into protected code, and the contract work adds more
  zero-caller surface to the same category. WP5.6 retracts the two bad records; the rest of WP4.4 is
  **paused**, not cancelled.
- **run7 (30.7 test-hours).** It measures a corpus this plan changes underneath it — Phase 6 alters
  what collects, WP7.4 rewrites fixtures, WP5.6 and WP7.3 delete modules. That is 43% of the
  envelope spent producing unusable numbers. Re-run **after** the tree settles.
- **Anything needing live model inference.** No GPU; `/dev/fuse` and `/dev/net/tun` absent. Any step
  phrased "call the real service and compare" is invalid. This is not a limitation to work around —
  it is _why_ the schema/ASGI-level proof is the right artifact: it runs in CI forever, on every PR,
  on hardware with no GPU.
- **Triton Inference Server.** The gateway's `triton_client` speaks gRPC to a real server; only the
  mocked path is reachable — which is enough, and is how `ai/gateway/tests` already works.
- **Accuracy, latency, VRAM, throughput or FP4 comparison with VSS.** Needs both pipelines on real
  frames on real silicon.
- **CUDA-gated tests.** 13 in `ai/tests` alone, plus `backend/tests/gpu/` nvidia-smi probes and
  `test_benchmark_vram.py`. A fake provider cannot unskip these. Do not budget them.
- **Container/compose verification**, the `/platform-healthcheck` skill, Windows/deploy matrix jobs,
  and Playwright/e2e frontend suites (browser-dependent, excluded from vitest by `vite.config.ts`).
- **Raising or lowering any coverage threshold.**
- **Schema extraction from the five undeployed per-model servers** beyond what WP6.3 requires. It is
  10,351 lines serving nothing in production. Optional continuation work only.

---

## Autonomy protocol

**Execute WP5.0 → WP10.1 in order.** Within a phase, a WP may be reordered if blocked, provided the
reason is recorded in L. **Across phases, do not reorder** — the phase order is load-bearing.

**If hours run short**, the drop order is: **WP7.4** (partial migration is fine — the parametrization
matters more than the count) → **WP8.5** (keep the static cross-check, drop the live-Postgres
reproduction) → **WP9.2** (one paragraph, do not research it) → **WP6.4's non-gateway triage** (park
the classifications).
**Never drop:** WP5.0, WP5.1, WP6.1, WP6.2, WP6.3, WP7.1, WP8.1, WP8.2, WP8.3, WP10.1.

**If hours remain after WP10.1**, spend them on, in order: (a) properties enumerated in WP8.3 but not
yet asserted; (b) **continuing the WP7.4 fixture migration from wherever its ledger row records it
stopped** — it is the designated overflow work precisely because it is safely partial; (c) the
remaining `ai/` red triage. **Nothing else. Do not invent work.**

**Publish the number, do not move the line.** Enabling a gate that has never computed will reveal
sub-floor numbers. Frontend is already known: 80.00/74.61/78.44/80.93 against 83/77/81/84. Backend's
merged number is unknown to anyone. The honest response is to record it and stage the gating
decision. **A number that embarrasses the project is worth more than a threshold that flatters it.**
When a newly-true gate would turn `main` red, the default is **report, do not enforce**.

**Park, don't guess.** Anything RULING-shaped goes into L **with your recommendation**, and you move
to the next task. Do not stall; do not decide on the owner's behalf. RULING-shaped means: a product
decision (widen a DB CHECK vs normalize at the boundary), a policy decision (floor 80 or 85; does
`ai/` enter the coverage denominator), a scope decision (in-process tier; are the per-model servers
still a deployment target), a ratchet increase, or anything that would make `main` red without the
owner having asked for it.

Parked items seeded by this plan: per-model servers' deployment status (§0.1), 80-vs-85 (WP5.3),
`ai/` in the coverage denominator (WP6.5), `ai/enrichment-light` rename (WP6.3), Dockerfile COPY
edits (§1), frontend gate enforcement (WP5.2), the four vocabulary mismatches (WP8.5), in-process
tier scope (WP9.2).

---

## Budget

| Phase | Hours | Cumulative | Content                                                                                                |
| ----- | ----- | ---------- | ------------------------------------------------------------------------------------------------------ |
| 5     | 13    | 13         | pre-flight (incl. CI round trip), D1, D2, floor RULING, D5, classification sweep, dead-code deletion   |
| 6     | 14    | 27         | collection repair, live-crash fix, red triage, CI wiring                                               |
| 7     | 16    | 43         | 38-op registry from deployed surfaces, goldens + snapshots, matrix + carve-out deletions, fixture demo |
| 8     | 20    | 63         | Protocol, FakeProvider, conformance suite, client conformance, vocabulary                              |
| 9     | 6     | 69         | AST parity checker, scope declaration, CI round trips                                                  |
| 10    | 2     | 71         | write-up and stop                                                                                      |
| slack | 1     | 72         |                                                                                                        |

Phase 8 is the largest allocation on purpose: it is the deliverable. Phases 5 and 6 are its
preconditions, not its competitors. **WP caps sum to more than each phase budget — caps are worst
case. If actuals exceed the phase budget, apply the drop order.**
