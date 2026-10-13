# Packages done

Definitions of the packages whose row in the [README status table](../README.md#status) reads
`done`, copied verbatim from the lane plans as they stood when the plan was reorganised, grouped by
lane. They are reference only: open packages live in `docs/uplevel/packages/`. Their links
were rewritten to resolve from this file (`../README.md`, `../01-mutation-policy.md`), and the lane-plan files they cite (`10-backend.md`, `30-ops.md`,
`50-coordination.md`, `operator.md`) have been replaced by `packages/`, `rules.md` and `roles/`.

## Backend

### B1.2 Replay parity (D6)

**Files:** `backend/evaluation/vlm_replay.py`, `backend/services/vlm_analyzer.py`.

Replay records the raw `verdict.risk_score`; production passes every verdict through
`apply_verdict_invariants`, which clamps scores. Replay also takes the first `MAX_REPLAY_IMAGES`
media paths instead of production's key-frame selection (`00 §3` D6). Every threshold chosen from
replay numbers was chosen on scores production never emits.

- [ ] Write the failing test: one `VlmVerdict` that the invariant table clamps (a `rejected`
      verdict with a high score) gives the same verdict, score and level through replay as through
      the analyzer.
- [ ] Route replay through `apply_verdict_invariants` and through production's key-frame
      selection. **DECIDE** the mechanism, keeping one implementation of each: call the shared
      functions, or store production-selected frames in the corpus.
- [ ] **MEASURE** on the real tier: re-run the latest replay report and count the items whose
      score or verdict changes. The replay targets a test deployment's `ai-vlm`, never the live
      engine (README vocabulary).
- [ ] Lift the pause (UR-8): in `docs/vss-integration/17-action-plan.md`, record that replay now
      matches production and which earlier results it affects (OD-29's floor at least). Change the
      README's "Paused while Phase 1 runs" paragraph to say the pause has lifted.

**Done when:** the parity test passes, the register and README record the lifted pause, and the
operator's count of changed replay items is posted on the PR (`awaiting real tier` until then).

### B1.3 Honest inbound webhooks (D3, UR-12)

**Files:** `backend/api/routes/inbound_webhooks.py`, the API-key dependency, tests; regenerate
`docs/openapi.json` and the frontend's generated types if responses change.

The four endpoints accept any key of 16 or more characters and answer success for actions they
never take — `arm_zones` replies "Arm command for N zones queued" with nothing queued.

- [ ] Write the failing tests: a 16-character key absent from `settings.api_keys` gets `401`; each
      endpoint with a valid key answers `501 Not Implemented` with a body naming UR-12.
- [ ] Create one shared dependency that validates keys against `settings.api_keys`
      (`config.py:1949`), and use it in these routes. `verify_api_key` exists three times today
      (`inbound_webhooks.py`, `dlq.py`, `system.py`). **DECIDE** whether `dlq.py` and `system.py`
      move to it in this PR: they do if their behaviour is identical; otherwise list the
      differences in the PR.
- [ ] Keep the request schemas; the arming feature reuses them.

**Done when:** the tests pass and no inbound-webhook handler returns a success status.

### B1.4 Verdict-engine status (UR-18, backend part)

**Files:** the readiness route (`backend/api/routes/system.py:1455`), the VLM client or breaker
that owns engine state, the WebSocket system-event schema, tests. Unblocks `F1.2`.

Today an unreachable `ai-vlm` turns every event into `verification_failed` while the platform
looks healthy.

- [ ] Write the failing test: with the engine unreachable, `GET /api/system/health/ready` reports
      `verdict_engine: {state: "unavailable", since, reason}`; when the engine returns, `available`.
- [ ] Keep the readiness **HTTP status at 200** when only the engine is down. The backend
      container's healthcheck (`docker-compose.prod.yml:646`) and every `service_healthy`
      dependency read that status; a down engine must not take the platform with it.
- [ ] **DECIDE** the source of truth for engine state (the circuit breaker, the last successful
      assess, the startup probe), and push a WebSocket system event when it changes.
- [ ] Publish the field and the event in `docs/openapi.json` so `F1.2` builds against the schema.

**Done when:** the test passes, and stopping `ai-vlm` on a running stack flips the readiness field
and emits the event while the readiness status stays 200 (the PR carries the commands and output).

### B1.5 Exposure and auth, backend part (D10, D8; OD-12; ISS-029)

**Files:** `backend/api/middleware/auth.py`, `backend/main.py`, `backend/core/config.py`, routes,
tests. Parts in other lanes: `F1.3` (nginx and the login flow), `O1.6` (compose binding). This
package leads; land it first.

OD-12 is ruled: loopback unless `EXPOSE_LAN=true`; deny-by-default auth on `/api` and `/ws` when
exposed. None of it is built (`00 §3` D10). ISS-029 in the register carries the evidence.

- [ ] Write a design note into the PR description before code, one page at most: the credential
      (reuse the first-admin account the setup guard creates and `backend/api/routes/auth.py`), the
      session or token mechanism, WebSocket auth, and which routes stay open (health, first-run
      setup). Choices inside OD-12's ruling are **DECIDE**; anything outside it is a **RULING**.
- [ ] Write the failing tests. A test enumerates every mounted route, so a route added later is
      covered automatically: with `EXPOSE_LAN=true`, every `/api` data route and `/ws` refuse an
      unauthenticated request; with `EXPOSE_LAN` unset, behaviour matches today.
- [ ] **DECIDE** the fate of `auth_enabled` (D8): it becomes the switch, or it is deleted with its
      `.env.example` and compose lines.
- [ ] Replace `python-jose`, the JWT library in `backend/services/auth_service.py:21`. It carries a
      critical advisory with no patched release, and it is the only reason `ecdsa` (high, also
      unpatched) is installed (`00 §7`). **DECIDE** the replacement — a maintained JWT library — in
      the design note. Remove `python-jose` from `pyproject.toml` and `uv.lock` in the same PR; the
      existing token tests must pass unchanged.
- [ ] `POST /api/notification/test` records the authenticated user as the audit actor.
- [ ] Rewrite the "Auth model" bullet in the root `AGENTS.md`.

**Done when:** the route-enumerating test passes in both modes. (ISS-029 is marked done by
whichever of `F1.3` and `O1.6` lands last.)

### B1.6 Scope the orchestrator and its recovery to its own project (D11)

**Files:** `backend/services/container_discovery.py`, `backend/services/lifecycle_manager.py`, their
tests; the orchestrator's settings in `backend/core/config.py` if a new one is needed.

The backend mounts the host Podman socket (`docker-compose.prod.yml:468`), and its orchestrator —
on by default (`config.py:134-135`) — reaches beyond its own stack twice:

- **Discovery** lists every container on the host (`container_discovery.py:647`) and adopts any
  whose name contains a configured pattern (`:713-715`), whatever compose project it belongs to.
- **Recovery** stops and **removes** a container, then recreates it with
  `podman-compose -f <file> up -d <service>` with no project and no env file
  (`lifecycle_manager.py:247-268`). It can recreate into the wrong project, and when recreation
  fails the service stays deleted.

- [ ] Write the failing tests:
  - two containers whose names both match a configured pattern, one in the backend's own compose
    project and one in another; discovery adopts only the first;
  - recovery of an own-project service recreates it in the own project with the stack's effective
    configuration, and never touches the other project's container;
  - recovery whose recreation fails leaves the service running or restored, and raises an alert.
- [ ] Filter discovery by the backend's own compose project. **DECIDE** how the backend learns its
      project name (a label read at startup, or a setting the launcher passes). With no project
      known, the orchestrator adopts nothing and logs why — it never matches across projects.
- [ ] Make recovery project-scoped and failure-safe: an explicit project and the stack's own env
      file on every compose call, and no container removed before its replacement can be created.
      **DECIDE** the mechanism — restart in place, or create the replacement before removing the
      original.

**Done when:** all three tests pass, and on a machine running two stacks the orchestrator's
discovery and recovery logs touch only its own project's containers (the PR shows the command and
output).

### B2.1 The interface bar and the accepted-survivors file (`01` M3)

Specified in [`01-mutation-policy.md`](../01-mutation-policy.md) §M3.

**Supporting the inventory.** `F2.2` traces every feature through `backend/` read-only. Answer its
questions about backend behaviour from the code and from the fake stack; a behaviour you cannot
explain is itself an inventory finding.

### B2.2 Re-ID on the GPU (OD-17, re-ID half)

Approved by owner ruling 68 (issue #6854, comment `6099657064`, 2026-10-10). The text below is the
ruling's, verbatim: its package bullet first, then its **Why** bullet.

> **Package `B2.2` — Re-ID on the GPU (OD-17, re-ID half).** Lane backend; Phase 2; flags `heavy · owner` (production safety: it changes the verdict path); label `cell:heavy-2`; depends on `O2.1` (merged).
>
> - **The seam:** `osnet_loader.extract_person_embedding`, which both live callers use (`vlm_specialists.py:754`, `reid_service.py:567`). Put a gateway-backed embedding behind it (`/enrich-lt/person-reid`), so neither caller changes.
> - **MEASURE first:** time per crop and per event, CPU path and GPU path, in the PR.
> - **Parity gate, in CI:** the same crop pixels through both paths, with the same weights in each, give cosine similarity of at least 0.999 on the final vector. That covers resize, normalisation, the wire encoding (no lossy round-trip) and L2 normalisation (the gateway returns the raw vector). If the gate fails, stop and report; do not loosen it.
> - **Model ID, never asserted:** the model ID on a gateway embedding comes from the source checkpoint's sha256, recorded at export and reported by the gateway. If that provenance is missing, the embedding carries the sentinel, which `compare_person_vectors` refuses (`space_mismatch`, "unavailable (re-enroll)"). It is never relabelled with the enrolled rows' ID.
> - **Failure:** the gateway being down degrades the step with its own reason code; the step's never-raise contract stands.
> - **Fake stack:** the fake-AI overlay serves `/enrich-lt/person-reid` with deterministic vectors under a fake model ID that never matches a real one.
> - **Owner run:** a command in the PR body that checks parity on the owner's host with the production weights (`operator.md`, "The owner on the host"). The row is `awaiting real tier` until its output is posted.
> - **Cleanup, in a follow-up PR after the owner run is posted:** remove the backend's CPU OSNet path, `torchreid` if nothing else imports it, and the backend's GPU reservation in compose if nothing in the backend uses it. Until then, reverting the switch is the rollback.
> - **Done when:** the measurements, the parity gate green in CI, the switch merged, the owner run's output posted with parity at or above the gate, and the cleanup merged.
>
> **Why:** the backend runs OSNet-AIN x1.0 on CPU (`uv.lock`: `torch 2.14.0+cpu`; 2-CPU limit) on every event with person crops (`backend/services/vlm_specialists.py:754`), while the same network and weights sit resident and uncalled in Triton (ruling 67's facts).

**Parked** (owner ruling 106, 2026-10-11): on the owner's GB300 host every gateway inference failed
(`cudaErrorSymbolNotFound` in ONNX Runtime's CUDA execution provider), and the CPU path measured
56.3 ms per crop (p95 59.0 ms) on two cores. The switch stays `local`, the cleanup is cancelled,
and the merged switch, parity gate and provenance stay as a ready option.

## Frontend

### F1.1 Endpoint truth (D2)

**Files:** `frontend/src/services/api.ts`, `frontend/src/hooks/useHouseholdApi.ts`, a new contract
test under `frontend/src/__tests__/`, a known-missing list beside it.

The Cameras settings page calls `/api/cameras/{id}/anomalies`; the backend serves
`/api/cameras/{camera_id}/baseline/anomalies`. Four more client paths are absent from
`docs/openapi.json` (`00 §3` D2). Every test passes because every layer mocks the API.

- [ ] Write the failing contract test: every method and path the client calls exists in
      `docs/openapi.json`. Cover `fetchApi` callers and the ~24 hooks that call `fetch(` directly.
      **DECIDE** the mechanism: a static scan of the URL templates, or typing the client's path
      argument against the generated `paths` type so a wrong path fails to compile.
- [ ] Fix the anomalies path. Check that the response shape (`AnomalyListResponse`) matches what
      `CameraAnomalyTimeline` renders.
- [ ] Put the other four paths (`/api/jobs/{id}/retry`, `/api/events/{id}/entity-matches`,
      `/api/debug/profile/download`, `/api/household/members/{id}/detections`) on the known-missing
      list, each pointing to `00 §3` D2. Each is a half-built seed for `F2.2`, which replaces the
      pointers with inventory row ids; the list drains as `R2` rulings land.

**Done when:** the contract test runs in CI and fails on any mismatch not on the known-missing
list; the PR shows the anomaly timeline's request answered `200` by a running backend.

### F1.3 Exposure and auth, frontend part (D10; OD-12)

**Depends on:** `B1.5` (its design note fixes the credential and session mechanism).

**Files:** `frontend/docker-entrypoint.sh`, the auth context and login flow, `fetchApi`'s error
handling, the WebSocket manager.

- [ ] Write the failing tests: a `401` from `fetchApi` routes to login; the WebSocket manager
      attaches the credential.
- [ ] nginx forwards the credential `B1.5` chose to `/api` and `/ws`.
- [ ] A login screen appears only when the backend reports auth required.

**Done when:** on a running stack with `EXPOSE_LAN=true` the UI requires login and works after it,
and with `EXPOSE_LAN` unset no login appears. The PR carries both runs. If `O1.6` has already
landed, this PR marks ISS-029 done in the register.

### F2.1 Golden-path harness

**Depends on:** `O2.1` (fake AI stack), `O2.2` (harness script).

**Files:** `frontend/playwright.config.ts` (a new `golden` project), `frontend/tests/golden/`.

- [ ] Add a Playwright project with **no API mocking**, pointed at the stack `O2.2` brings up.
      A guard fails the run if any spec in the project calls `page.route` on `/api` or `/ws`, so
      mocks cannot creep back in.
- [ ] Write the first golden path: a fixture image dropped into a camera folder (through `O2.2`'s
      helper) → an event on the dashboard carrying the fake VLM's verdict → the event detail shows
      its score and summary.

**Done when:** the `golden` project runs green inside `O2.2`'s CI job on the fake stack, and a
deliberately mocked spec in it fails the guard.

### F2.2 Feature inventory (UR-13)

**Files:** create `docs/reference/feature-inventory.md`; edit `frontend/knip.json`, fill
`docs/uplevel/r2-sheet.md` (it exists; fill it around its §2b, never copy the template over it)
and set the `next` fields of `frontend/src/__tests__/api-endpoint-contract-known-missing.json`
(owner, 2026-10-09). Read-only everywhere else.

The long-lived map of the product. Start from the seeds in `00 §10`; re-verify each one.

- [ ] Enumerate every feature: each route in `App.tsx`, each panel, tab and modal reachable from
      them, each user action that calls the API, each settings toggle, and the external interfaces
      (inbound webhooks, MQTT commands).
- [ ] Trace each one: component → API calls → backend route → service → store. List its modules
      in every lane.
- [ ] Give each a status with evidence: **unverified** (appears to work; `F2.3` decides),
      **half-built** (cite the stub, the missing endpoint, or the false success, by file and line),
      or **leftover** (cite the retirement).
- [ ] Fix `knip.json` so it can see unreachable files: entry points are `src/main.tsx` and config
      files (tests are not entries); `exports` checking on; the six ignore entries that name
      deleted files removed. Today's config hides them (`00 §4.3`).
- [ ] Attach the **modules serving no feature**: the non-shipping lists from `O2.3` (Python) and
      `npx knip --production` (frontend), minus every module some row claims.
- [ ] Replace `F1.1`'s known-missing pointers with inventory row ids.
- [ ] **DECIDE** the row format. It carries at least: id, surface, action, API calls, backend
      route/service/store, status, evidence, modules, real-tier last verified, ruling, priority.
- [ ] Prepare the `R2` sheet: copy [`templates/r2-sheet.md`](../templates/r2-sheet.md) to
      `docs/uplevel/r2-sheet.md` and fill it — every half-built and leftover feature, OD-7 and
      OD-17 with the facts the inventory found, and the modules serving no feature.

**Done when:** every route in `App.tsx` and every API-calling action maps to a row; every row has a
status with evidence; the module list is attached; the `R2` sheet is drafted (`F2.3` finalises it).

### R2a — Record `R2`, part 1

The section below is `20-frontend.md`'s "Record `R2`", verbatim. It ran for `R2a` (#6980); the
open half, `R2b`, is in [`../packages/frontend.md`](../packages/frontend.md).

After the owner's ruling session, this lane writes the record in one PR: each ruling and priority
into the inventory's ruling column, the OD-7 and OD-17 rulings into
`docs/vss-integration/17-action-plan.md`, and `R2` set to `done` in the README status table. Every
Phase 3 package waits on this PR.

**Ruling 86 split the session into `R2a` and `R2b`.** This section ran for `R2a` — the sheet as it
stood — on 2026-10-10 (#6980): rulings and tiers into the inventory, and OD-7, OD-17 and OD-33 – OD-39
into `docs/vss-integration/17-action-plan.md`. A Phase 3 package may start once that PR and the owner’s
plan PR carrying ruling 86 have merged, if it touches only `R2a`-ruled features and modules. `R2b` —
the rows `F2.3` demotes plus the sheet’s §3 — is recorded the same way after the owner’s `R2b` session;
`R2` is `done` only when both records are.

## Ops

### O0.1 The sandbox launcher (UR-26, UR-28)

**Files:** `scripts/uplevel/launch.py`, `scripts/uplevel/sandboxes.toml`, their tests in
`backend/tests/unit/scripts/`, and the "Where agents run" section of `50-coordination.md`. A
host-side tool: the owner runs it; no agent does.

The owner creates sandboxes with `agent-dgx`, which gives each session its own clone of the host
checkout (`50-coordination.md`, "Where agents run"). This launcher drives `agent-dgx` from a
manifest, so a phase boundary takes one command, and retires sandboxes without losing work. The
owner started Phases 0 and 1 by hand (UR-28); the launcher takes over from the Phase 2 boundary.

Follow `synthbench/host/agent.py`, which already drives `agent-dgx` from the host: every command
goes through a `Host` seam, `--dry-run` prints each step instead of running it, all checks run
before any change, and a refusal exits 2 naming the next step. Its tests run against a fake host
(`backend/tests/unit/synthbench/test_host_agent.py`); test this launcher the same way.

- [ ] Use only the `agent-dgx` and `sbx` commands and flags shown in `synthbench/host/agent.py`,
      `docs/synthbench/operator-runbook.md`, or the stack repository's
      `docs/operations/agent-dgx-sessions.md`. In the draft PR, ask the owner to paste that file and
      the `agent-dgx run` arguments that select the strongest model. `agent-dgx` reads an unknown
      word as a new session's name, so the launcher always names its subcommand, and nobody runs
      `agent-dgx help` or `agent-dgx ls`.
- [ ] `sandboxes.toml` declares, per phase, each session: its name (`uplevel-<lane>[-<cell>]`,
      `uplevel-coordinator`, `uplevel-heavy`; the sandbox is `agent-<name>`), its `agent-dgx run`
      arguments (`--agent claude --endpoint dgx` for the fast model, the owner's arguments for the
      strongest), and its kickoff line: "Follow the kickoff prompt in <the roster's file>", plus the
      cell sentence for a split lane. Network profiles and secrets go in only if the `agent-dgx`
      docs show a flag for them.
- [ ] `launch.py up --phase <n>` refuses unless it runs inside herdr and the host checkout is clean
      and at `origin/main`. It creates each missing session with `agent-dgx run <name> … --split`
      from the host checkout, checks that `agent-dgx inspect <name> --json` reports that commit as
      `manifest.source_repository.head`, and prints each kickoff line. Re-running creates only what
      is missing.
- [ ] **`launch.py retire <name>` never loses work.** The owner ends the agent's session first.
      Inspect inside the sandbox, running git with `sbx exec agent-<name>` in
      `/agents/agent-<name>/workspace`: changed or untracked files, stashes, and refs not pushed to
      `origin`, on every branch. On the host, read the workspace's files but run git
      there only through `sbx exec`: its `.git/config` is the agent's to write, and settings such
      as `core.fsmonitor` run commands (`docs/synthbench/operator-runbook.md`). Refuse if any of
      these exist or the inspection fails; retirement is then the owner's manual call. Otherwise
      export first: a `git bundle create --all` and an archive of the working tree, made inside
      the sandbox, copied to a host directory and verified there (`git bundle verify` from the
      owner's checkout; the archive listed). Only then run `agent-dgx stop <name>` and
      `agent-dgx session rm <name> --force`. **MEASURE** whether `sbx exec` still reaches the
      sandbox once the agent's session has ended, and order the steps to fit.
- [ ] Keep the refusal logic in functions with tests on fixture outputs: for `retire`, changed
      files, untracked files, a stash, an unpushed ref and a failed inspection each refuse, and a
      clean sandbox with a verified export proceeds; for `up`, a dirty or stale host checkout and a
      session cloned from the wrong commit each refuse.

**Done when:** the tests pass, and the PR shows the owner's output of `up --phase 2 --dry-run` and
of `retire` on a throwaway session (`agent-dgx run uplevel-scratch --agent claude --endpoint dgx`),
which refuses while it holds an unpushed commit and succeeds once that commit is pushed.

### O1.1 Mutation hold and supersede (`01` M5)

Specified in [`01-mutation-policy.md`](../01-mutation-policy.md) §M5.

### O1.2 Retire ghcr (UR-17)

The ghcr compose file has no `ai-vlm`, yet `docs/operator/ai-ghcr-deployment.md` advertises it as
an install path (`00 §3` D5, `00 §7`).

- [ ] Delete `docker-compose.ghcr.yml` and `docs/operator/ai-ghcr-deployment.md`. Rewrite the
      references in `docs/operator/README.md`, `docs/operator/AGENTS.md`,
      `docs/operator/ai-installation.md`, `docs/operator/ai-services.md` and
      `docs/guides/profiling.md`. Dated plans and specs keep their references; they are history.
- [ ] **DECIDE** which image publishing in `deploy.yml` survives: what its smoke job pulls (the
      stack it starts from `docker-compose.ci.yml`) stays; anything published only for the ghcr
      path goes.
- [ ] Commit a **retired-paths check**: `scripts/retired_paths.txt` lists paths that must stay
      gone, and `scripts/test_retired_paths.py` fails when a living doc, workflow, hook or script
      names one. Add `docker-compose.ghcr.yml` and `docs/operator/ai-ghcr-deployment.md`. `O1.4`
      and `O1.5` add their own entries.

**Done when:** the retired-paths check runs in CI and passes, and the operator docs describe one
install path: `setup.py` plus the prod compose file.

### O1.3 `ai-vlm` on by default (UR-18, compose part)

- [ ] Remove `profiles: [vlm]` from `ai-vlm` in `docker-compose.prod.yml`. Update the deploy
      tool's profile mapping (`setup_lib/deploy_phases.py:106`) and its tests, and
      `scripts/inspect-model-tensors.sh`.
- [ ] Document that a machine without a GPU fails at `ai-vlm` start, and that the fake-AI overlay
      (`O2.1`) is the explicit GPU-less path. Until `O2.1` lands, document the interim.
- [ ] Leave the `vllm` profile alone; OD-17 decides it at `R2`.

**Done when:** `podman compose -f docker-compose.prod.yml config --services` with no profile
flag lists `ai-vlm`, and the deploy tool's tests pass.

### O1.4 Broken workflows (D9)

- [ ] `preview-deploy.yml` reads `github.event.pull_request.*` under a dispatch-only trigger and
      sets retired service URLs. **DECIDE** from `gh run list --workflow preview-deploy.yml`: no
      successful run in 90 days means delete; otherwise fix it.
- [ ] Fix `deploy.yml:498` and `:553`, which cite two docs that do not exist.
- [ ] Remove the dead `.pre-commit-config.yaml` excludes (`^\.wp25-feed/`,
      `vehicle_classifier_loader.py`).
- [ ] Commit the check as a test that runs in CI: every repository path named in
      `.github/workflows/*.yml` and `.pre-commit-config.yaml` exists. If `preview-deploy.yml` is
      deleted, add it to the retired-paths list (`O1.2`).

**Done when:** that test runs in CI and passes.

### O1.5 Delete the archives (UR-19)

- [ ] Return the installer's tests to the live suite first: move `archive/test_setup.py` and
      `archive/test_setup_core.py` under `backend/tests/unit/setup_lib/`. **MEASURE** whether they
      pass against today's `setup.py`; fix or rewrite them until they do.
- [ ] Repoint `backend/tests/unit/scripts/test_backend_image_trivy_clean.py:179` and
      `.trivyignore`, which name `archive/Dockerfile.yolo26-benchmark`.
- [ ] `git rm -r archive docs/archive`. Remove the archive excludes from `.pre-commit-config.yaml`,
      `.prettierignore`, `.semgrepignore`, `.agents-md-validator.yml` and any other config that
      names them. Update the root `AGENTS.md` directory tree.
- [ ] Regenerate `.secrets.baseline`. **MEASURE** its size before and after (4.97 MB at
      `d6ba78d5`).
- [ ] Add `archive/` and `docs/archive/` to the retired-paths list (`O1.2`).

**Done when:** both directories are gone, the setup tests run green in CI, the link checker
passes, and the PR reports the baseline's new size.

### O1.6 Exposure and auth, compose part (D10; OD-12)

**Depends on:** `B1.5`.

- [ ] Bind the frontend's published ports to `127.0.0.1` unless `EXPOSE_LAN=true`
      (`docker-compose.prod.yml:907`). Compose has no conditionals: **DECIDE** the mechanism, such
      as a bind-address variable that `setup.py` derives from `EXPOSE_LAN`.
- [ ] Add `EXPOSE_LAN` to `.env.example` and to `setup.py`'s prompts. Correct the root `AGENTS.md`
      claims about network binding.
- [ ] **MEASURE** every published port's bind address and list them in the PR. A port other than
      the frontend's that is published on `0.0.0.0` is a **RULING**.
- [ ] Commit a test that renders the compose port bindings with `EXPOSE_LAN` unset and set, and
      asserts the frontend's bind address in each.

**Done when:** that test runs in CI and passes. If `F1.3` has already landed, this PR marks
ISS-029 done in the register.

### O1.7 Audit measurement scripts

**Files:** `scripts/audit/`, one script per count, each with a test.

The audit's **[A]** figures came from scans nobody committed, which breaks contract rule 3 — and
later packages compare before/after counts against them.

- [ ] Commit one script per count a later package measures:
  - retired-name hits (`florence`, `nemotron`, `enrichment`, `pose`, `demographic`) per directory,
    split into code, living docs and `AGENTS.md` files — for `B3.3`, `W1.1` and `W3.3`;
  - settings fields read nowhere outside `backend/core/config.py` — for `B3.3`;
  - `.env.example` variables read by neither `config.py`, compose nor `setup.py` — for `O3.3`;
  - the battery census: each `test_*_batchNN*.py` with its lines, test count and target module —
    for Phase 4 consolidation;
  - test groups that differ only in literals — for `BB.1`; reuse `scripts/parametrize-guard.py`
    where it fits.
- [ ] Each script prints JSON plus a one-line summary, and has a test on a fixture tree.
- [ ] **MEASURE:** run each at HEAD. Put the baselines in the PR, and replace the matching **[A]**
      figures in `00-audit.md` with the measured values tagged **[C]**.

**Done when:** every script's test runs in CI, and `00-audit.md` carries the measured baselines.

### O1.8 Dependabot alerts

**Files:** `uv.lock`, `pyproject.toml`, `.github/dependabot.yml`, the dependency-audit workflow;
`frontend/package.json` and `frontend/package-lock.json` as cross-lane parts.

21 alerts are open on `main`: 2 critical, 10 high, 9 moderate (`00 §7`). Most close by deletion or
by work already planned; this package closes the rest and keeps the count from climbing again.

| alerts                                 | where                        | how they close                                                       |
| -------------------------------------- | ---------------------------- | -------------------------------------------------------------------- |
| 16, including critical `vitest`        | `archive/package-lock.json`  | `O1.5` deletes the tree; confirm GitHub marks them fixed             |
| critical `python-jose`, high `ecdsa`   | `uv.lock`                    | `B1.5` replaces the JWT library; `ecdsa` leaves with it              |
| medium `Mako`                          | `uv.lock`, via `alembic`     | upgrade to 1.4.2 here; `B3.3` decides whether `alembic` stays at all |
| medium `postcss-selector-parser` 6.1.4 | `frontend/package-lock.json` | upgrade to 7.1.6, or an `overrides` entry if its parent pins 6.x     |
| high `braces` 3.0.3                    | `frontend/package-lock.json` | no patched release; see below                                        |

- [ ] Upgrade `Mako` and `postcss-selector-parser`. Run the backend unit suite, the frontend suite
      and the frontend build, and put the results in the PR.
- [ ] `braces`: **MEASURE** whether it reaches the shipped bundle or only build tooling (trace who
      requires it, and search the built `dist/`). If it is build-only, propose dismissing the alert
      as "vulnerable code not used"; the dismissal is a **RULING** for the owner's batch, since it
      accepts a risk. If it ships, stop and report.
- [ ] **RULING** (OD-11): which fix the owner picks for the `dependabot.yml` defects found on
      2026-09-21. Apply it here once ruled.
- [ ] Make the dependency audit bite: a new critical or high advisory in `uv.lock` or
      `frontend/package-lock.json` fails CI unless it sits on a committed dismissal list with a
      reason and an expiry date. `OB.2` keeps this gate when it merges the audit workflows.

**Done when:** after `O1.5` and `B1.5` land, GitHub shows no open critical or high alert except
those dismissed on the owner's ruling, and the CI audit fails on a fixture advisory that is not on
the dismissal list.

### O1.9 Deploy green on `main` (D12)

**Files:** `.github/workflows/deploy.yml`, `.github/workflows/rollback.yml`,
`scripts/ci-smoke-test.sh`. `O1.2` and `O1.4` also change `deploy.yml`; the coordinator merges the
three one at a time.

`Deploy` has failed on every push to `main` since 2026-01-05 (`00 §3` D12), so it reports nothing,
and each failure opens an incident issue for a rollback that never happens.

- [ ] Make the smoke test state the CI stack's contract. Keep `/api/system/health/full` in it, and
      require every critical service healthy except the AI services `docker-compose.ci.yml` does
      not start, which must be reported unreachable. Commit that list beside the check with the
      reason; it goes when `O2.1`'s fake stack runs in the smoke test instead.
- [ ] Publish `:latest` only after the smoke test passes, testing the per-commit tag instead. If
      `O1.2` has already removed the publishing, this step is done.
- [ ] **MEASURE** each of "Deploy to Staging" and "Post-Deployment Validation": a job that deploys
      or validates nothing and only prints a checklist goes.
- [ ] Delete `rollback.yml` (owner ruling, 2026-10-08): a red `Deploy` run is the signal, and the
      coordinator's daily batch on the pinned issue reports it (its Status line). Build no digest
      workflow, and leave `linear-ci-status.yml` as it is.
- [ ] Once `Deploy` is green, close each open "Automated Rollback" issue with a comment linking this
      PR.

**Done when:** `Deploy` passes on this PR's merge commit and on the next push to `main`, and no
"Automated Rollback" issue is open.

### O1.10 The operator sandbox (UR-30)

**Files:** `scripts/uplevel/sandboxes.toml`, `scripts/uplevel/launch.py`, their tests.

The owner starts `uplevel-operator` by hand for Phase 1
(`agent-dgx run uplevel-operator --agent claude --endpoint dgx --gpu --split`). This package puts it
in the roster, so the launcher creates it from the Phase 2 boundary on.

- [ ] A session may declare `gpu = true`; `up` then adds `--gpu` to its `agent-dgx run`
      arguments. In the draft PR, ask the owner to confirm the flag's exact form, as `O0.1` did for
      the strongest model's arguments.
- [ ] Add `uplevel-operator` to phase 1, model `fast`, kickoff line "Follow the kickoff prompt in
      docs/uplevel/operator.md. It is the section named "Kickoff prompt" in that file."
- [ ] `up` refuses to create a `gpu` session when the launching shell lacks
      `AGENT_GPU_RUNNER_URL`, and adds no `--mount` for the model library: `agent-dgx --gpu` mounts
      `/srv/agent-models` itself and refuses any mount at or under it.
- [ ] A test pins that `uplevel-operator` is the only session declaring `gpu`, in every phase.

**Done when:** the tests pass, including one that runs `up --phase 1 --dry-run` against a fake host
and finds `--gpu` on `uplevel-operator`'s `agent-dgx run` line and on no other.

### O1.12 The hooks run in the gate (UR-37)

**Files:** a new job in `.github/workflows/ci.yml` and its place in `CI Gate (Required Checks)`;
`.pre-commit-config.yaml` only where a hook needs a CI mode.

Agents commit and push through `.pre-commit-config.yaml`'s hooks (semgrep, detect-secrets,
prettier, the slow-test guard and more), but the required gate runs only part of them: the `lint`
job runs ruff and radon. A PR can pass every required check and still block every later push that
touches its files. On 2026-10-08 that took four fix PRs: B1.3's webhook fixture tripped semgrep
(#6888), the slow-test hook (#6890), and #6891 and #6892.

- [ ] Write the failing check first: a fixture change that trips a hook but passes today's CI (the
      B1.3 fixture class) fails the new job.
- [ ] Add a job, as its own job (the hot-file rule for `ci.yml`), that runs the repository's pinned
      hooks on the PR's changed files (`pre-commit run --from-ref <base> --to-ref HEAD`), and add it
      to the `CI Gate (Required Checks)` closure. `scripts/test_ci_job_graph.py` enforces the
      wiring.
- [ ] **MEASURE** the job's wall-clock on a typical PR and on a large one.
- [ ] A hook the CI runner cannot run (missing tooling): give the job the tooling, or list the hook
      in the PR with the reason it stays local-only. That list is a **RULING** for the owner's
      batch: a hook left out of the gate is a known gap, never a silent one.

**Done when:** the job runs in the required gate on every PR, fails on the fixture and passes on the
current tree, and the PR reports its wall-clock and any local-only hooks with the owner's ruling.

### O2.1 Fake AI stack

**Files:** a container build for `backend/ai_contract/fake/app.py`, `docker-compose.fake-ai.yml`,
scenario fixtures. Changes to the fake app itself ride in the same PR under the cross-lane rule.

The fake already exists: a deterministic FastAPI app mounting one route per AI-contract operation,
with conformance tests and golden payloads (`00 §6`). Nothing runs it as a service.

- [ ] Build an image for it, and serve it at both the VLM URL and the gateway URL. **DECIDE** one
      container or two.
- [ ] Pass the backend's startup gates. `/props` returns a `build_info` that contains the pinned
      `VLM_REQUIRED_BUILD` (`vlm_client.py:326-341`), and the constrained-decoding startup probe
      passes (`main.py:732`, `constrained_decoding.py`). Prove both by booting the backend
      against it.
- [ ] Make outcomes scenario-driven: the fixture image chooses the detections and the verdict, so
      a golden path asserts exact results. Commit the scenarios.
- [ ] Support the two failure modes Phase 1 needs: the engine down (the container stops) and a
      slow reply. **DECIDE** the switch for the slow reply.
- [ ] Run the conformance suite in `backend/tests/contracts/ai_providers/` against the running
      container.
- [ ] Make `docker-compose.fake-ai.yml` an overlay that has to be named on the command line; it is
      never a default (UR-18).

**Done when:** the CI stack with the overlay boots a backend that passes its startup gates; an image
dropped into a camera folder yields an event carrying the scenario's verdict (the PR shows the
commands and output); the conformance suite passes against the container.

### O2.3 Reachability check (`01` M1)

Specified in [`01-mutation-policy.md`](../01-mutation-policy.md) §M1. Its output feeds `F2.2`'s list
of modules serving no feature.

### O2.3b Reachability: ancestor packages ship

Cell A; depends on `O2.3` (owner ruling 73). `O2.3`'s tool listed 19 parent `__init__.py` files
(1,099 lines) of shipping modules as non-shipping, though importing a module runs its parent
packages.

- [ ] The tool counts every ancestor package of a shipping module as shipping.

**Done when:** a test pins that a shipping module's ancestor packages are shipping, the real-tree
count drops by those 19 files (re-measured at the PR's head), and `R2`'s "modules serving no
feature" input is regenerated from the fixed tool. It lands before the `R2` sheet's §3 is
finalised (`F2.3`).

### OB.2 CI dedupe

- [ ] One dependency-audit workflow (pip-audit and npm audit each run in four today).
- [ ] One release mechanism (three today). **DECIDE** which survives.
- [ ] Every `continue-on-error: true` (40 today) carries a comment with its reason, or goes.

**Done when:** each concern runs in exactly one workflow and every `continue-on-error` has a
reason.

## Docs

### W1.1 The validator with teeth

**Files:** `scripts/agents_md_validator.py`, `.agents-md-validator.yml`,
`.github/workflows/agents-md.yml`, the validator's tests.

Today's tree already holds dead references, so a gate that failed on any of them would turn every
PR red until `W1.3` lands. This package installs ratchets instead: nothing new gets in, and what
exists drains.

- [ ] Write the failing test: an `AGENTS.md` that adds a reference to a file existing nowhere makes
      the validator exit non-zero, while the dead references already in the committed baseline
      do not.
- [ ] Commit two baselines in `.agents-md-validator.yml`: the dead file references that exist today
      (as an allowlist of `file → reference` pairs), and the count of retired-name mentions
      (`florence`, `nemotron`, `enrichment`, `xclip`, `pose`, `demographics`). The run fails on a
      dead reference outside the allowlist, on a broken link, or on a retired-name count above the
      baseline. Today `main()` always returns 0.
- [ ] **MEASURE** both baselines at HEAD and put them in the PR.

**Done when:** CI passes on the current tree, and fails on a fixture `AGENTS.md` that adds a new
dead reference or a retired-name mention above the baseline.

### W1.2 Root truth

**Files:** the root `AGENTS.md`, `llms.txt`, the root `README.md`.

- [ ] Check every claim in the root `AGENTS.md` sections "Directory Structure", "Key Design
      Decisions", "Data Flow" and "Service Ports" against the code; correct each one that is false.
      Known: `data/` is called gitignored but holds 1,409 tracked fixture files; `archive/` leaves
      with `O1.5`. The auth-model and network-binding lines belong to `B1.5` and `O1.6`, which
      rewrite them when they land.
- [ ] Same for `llms.txt` and the root `README.md`.

**Done when:** the PR lists every claim checked, with the file or command that confirms or
corrects it.

### W1.3 Remove dead references now

- [ ] Delete every line in an `AGENTS.md` that cites a file existing nowhere in the repo (213 at
      `d6ba78d5`), keeping any non-discoverable knowledge the line carried.
- [ ] At the top of the six largest inventory files (`backend/services`, `backend/core`,
      `frontend/src/hooks`, `backend/api/schemas`, `backend/api/routes`, `backend/models`), add a
      banner: their inventories are unmaintained until `W3.2`; the code is the source of truth.

- [ ] Empty the dead-reference allowlist and remove it, so any dead reference fails from then on.

**Done when:** the validator reports zero dead file references with the allowlist removed, and CI
passes.

### W2.1 The boundary list and the line caps

- [ ] Write the boundary list into `.agents-md-validator.yml`: every directory that keeps an
      `AGENTS.md`, each with a one-line reason. Expect 30 to 50 entries.
- [ ] **DECIDE** a line cap per tier (root, lane root, package) and add it to the validator,
      reporting only until `W3.2` switches it to failing.
- [ ] Put the standard above into `docs/developer/` as its single home, and point here to it.

**Done when:** the validator config carries the boundary list and the caps, and the standard has
one home.

### W2.2 Docs rulings for `R2`

Collect this lane's owner decisions so they are ruled in the same session (contract rule 4):

- **RULING:** one home for future plans and specs. VSS material is split across `docs/plans/`,
  `docs/superpowers/` and `docs/vss-integration/` today.
- **RULING:** the register `docs/vss-integration/17-action-plan.md` (8,145 lines). Proposal: its
  OD table gains a ruling column — rulings are written inline in the options column today, which
  is how three rulings were misread during the audit — and closed issues move to a history file.
- **RULING:** whether the 28 near-identical `docs/plans/image-(re)validation-*` plans stay as
  history or go.

**Done when:** the three items are on the `R2` sheet with the facts and a recommendation each.
