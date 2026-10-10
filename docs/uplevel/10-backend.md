# 10 — Backend Lane

> Owns `backend/` except `backend/tests/unit/setup_lib/`. Read [`README.md`](README.md) first:
> its vocabulary, contract and rulings (`UR-n`) bind every package here. Evidence: [`00-audit.md`](00-audit.md).

Work the phases in order. Inside a phase, packages are independent unless a package names a
dependency. One package per PR.

---

## Phase 1 — Stop the bleeding

### B1.1 VLM timeout ladder (D1)

**Files:** `backend/services/vlm_client.py`, `backend/core/config.py`; `.env.example` and the
compose `environment:` line if a default changes.

`_ASSESS_MAX_TOKENS = 2048` is justified by a 180 s read timeout that no longer exists; the real
default is 25 s. A reply past roughly 1,400 tokens times out, is retried identically at
temperature 0, and charges the circuit breaker twice (`00 §3` D1).

- [ ] Write the failing test: a stub transport slower than the read timeout. Assert the target —
      the breaker charged at most once, no identical retry. It fails today, which records a
      transport error, retries identically and charges the breaker twice.
- [ ] **DECIDE** the ladder under spec S4 (p95 ≤ 30 s including cold starts, `config.py:1134`).
      The options: derive the per-attempt timeout from the token budget and measured throughput;
      cap `max_tokens` to what the timeout can hold; classify a read timeout as a budget outcome
      that skips the identical retry and the breaker. Whatever you choose, a slow reply never
      counts as a broken engine.
- [ ] Replace the stale comment with the real arithmetic: tokens, throughput, timeout.
- [ ] **MEASURE** on the real tier: p95 latency and the reply-length tail. The operator agent
      measures the tail on the GB300 (`operator.md`, "The agent-gpu path"); S4's p95 is defined on
      24 GB-class hardware, so the owner measures it on the A5500. Until `O2.2` exists, put both
      commands in the PR, using `$VLM_URL` and written to run against a test deployment (README
      vocabulary), never the live stack.

**Done when:** the test passes; the comment's numbers match `config.py`; the operator's S4 p95
measurement is posted on the PR (the row sits at `awaiting real tier` until then, contract rule 5).

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

---

## Phase 2 — Feature truth

### B2.1 The interface bar and the accepted-survivors file (`01` M3)

Specified in [`01-mutation-policy.md`](01-mutation-policy.md) §M3.

**Supporting the inventory.** `F2.2` traces every feature through `backend/` read-only. Answer its
questions about backend behaviour from the code and from the fake stack; a behaviour you cannot
explain is itself an inventory finding.

---

## Phase 3 — The tree matches the rulings

Starts after the Phase 2 RULING session (`R2`). The feature inventory's ruling column is the
input to every package here.

### B3.1 Retire ruled-out features, backend part

**Files:** whatever each retired feature's inventory row lists under "modules".

- [ ] First, OD-20's already-ruled retirement of the enrichment surface (hook, route, types and
      tombstone in one commit; ISS-073).
- [ ] For each feature ruled **retire**: delete its routes, schemas, services, settings, alert
      conditions and tests (batteries included). The frontend part (`F3.1`) lands in the same PR,
      so the client never calls a route that is gone.
- [ ] Tables leave through a dated DROP runbook in `docs/api/migrations/`, following the R8-S4
      precedent (`cafad910`).
- [ ] Regenerate `docs/openapi.json`.

**Done when:** for every retired feature, a grep for the identifiers its inventory row lists finds
nothing in `backend/` outside the DROP runbook.

### B3.2 Delete the approved module list (OD-28 and `R2`)

- [ ] Delete in OD-28's order — the guided-constraints and trajectory modules first, then the
      scene-change vertical — then the rest of the list the owner approved at `R2`.
- [ ] A non-shipping module that a **complete** feature's inventory row claims stays: add it to
      `keep.toml` with that row's id as the reason. It ships once its feature is built.
- [ ] Cut `backend/services/__init__.py` and `backend/core/__init__.py` down to the names shipping
      code imports.
- [ ] Delete each module's tests, batteries included. These PRs change production code, so the
      kill-loss rule does not apply; each PR discloses the scored-set change instead (`01`).

**Done when:** the reachability check (`O2.3`) reports no non-shipping module under `backend/`
outside `keep.toml`, and the suite is green.

### B3.3 Settings and residue truth

- [ ] **MEASURE** the settings fields read nowhere outside `config.py` (50 at `d6ba78d5`, `00 §4.1`)
      and delete them with their `.env.example` and compose lines.
- [ ] Add a ratchet test: every `Settings` field is read outside `config.py`, or sits on an
      allowlist with a reason.
- [ ] Rename live code still carrying retired names (`get_nemotron_analyzer_dep`,
      `summary_generator._call_nemotron`, Nemotron-named metrics); delete the uncalled metrics and
      unused exception classes `00 §4.1` lists.
- [ ] `AIModelEnum` and the prompt-management schemas follow the prompt page's ruling.
- [ ] **DECIDE** whether the `alembic` dependency stays (`00 §7`: no Alembic directory exists).

**Done when:** the ratchet test passes, and the PR reports the before/after count of `nemotron`,
`florence` and `enrichment` hits in `backend/`.

---

## Phase 4 — Complete the product

### Feature track (`B4.n`)

One package per feature ruled **complete**, in the priority order set at `R2`. Every feature
package runs the same six steps:

1. **Design session.** The owner and the executing agent settle the feature's open questions;
   the result is a design at `docs/uplevel/4n-<feature>.md`, copied from
   [`templates/feature-design.md`](templates/feature-design.md).
2. **Consolidate first, in its own test-only PR.** Consolidate the tests of every module the
   feature will touch, under `01`'s zero kill-loss protocol. This PR changes no production bytes;
   it is the one named exception to "one package per PR" (README, Phase 4).
3. **Build** test-first, in the second PR.
4. **Golden path** green on the fake stack. The frontend lane writes UI golden paths; this lane
   writes external-interface golden paths as pytest specs in `backend/tests/golden/`, which sit
   outside the default test paths and run through `scripts/feature-check.sh` (`O2.2`).
5. **Real-tier check** recorded by the operator.
6. **Inventory row** set to **works**.

**Done when** (every feature package): steps 4–6 hold.

**Arming (UR-12)** is one of these features. Its shape is fixed: one arming module behind the
seam, with the inbound webhooks and the MQTT command handler as two thin adapters, replacing both
stubs. Its design session settles:

- what arming gates — alert creation, notification delivery, or analysis;
- whether a critical tier alerts regardless of arm state, as life-safety alarms do;
- what a mode (home, away, night) is — a named set of armed zones, or something else;
- how arm state relates to `AlertRule.schedule` and notification quiet hours — settle OD-22
  (notification policy) in the same session;
- the persisted state and its audit trail, and the UI control (a frontend part);
- whether the MQTT handler starts with the app, and how it authenticates.

### Background track (`BB.n`)

Modules and seams no feature reaches. Each package opens with a design session against the code
that remains, then consolidates the tests it will touch in a test-only PR (`01`'s zero kill-loss
protocol), then refactors in a second PR. `BB.1` is test-only throughout.

| package | target                                                                                                                                                                                                                                                                                                                                                       | evidence    |
| ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------- |
| BB.1    | Test consolidation for untouched modules: the 2,010 literal-only tests (`scripts/parametrize-guard.py` proves merges safe), ~215 shadowed fixtures, copy-pasted battery helpers into `backend/tests/utils`, `unit/routes/` merged into `unit/api/routes/`, the three permanently skipped `stream_config` files, the "moved" skips in `test_system_models.py` | `00 §6`     |
| BB.2    | Resilience primitives: one circuit breaker (four today), one retry (two), one HTTP client factory (31 construction sites); detection's three-deep retry stack collapses                                                                                                                                                                                      | `00 §5`     |
| BB.3    | Broadcast: `EventBroadcaster`, `WebSocketEmitterService` and `SystemBroadcaster` become one module driven by a typed event table                                                                                                                                                                                                                             | `00 §5`     |
| BB.4    | Service registry: `ServiceConfig` ×3 and `ManagedService`/`ServiceRegistry` ×2 become one                                                                                                                                                                                                                                                                    | `00 §5`     |
| BB.5    | Configuration: `config.py` (3,366 lines, 19 `BaseSettings` classes repo-wide) split by concern                                                                                                                                                                                                                                                               | `00 §2, §5` |
| BB.6    | The VLM seam — build → call → judge: one prompt fit and one key-frame selection per batch, the prompt as a versioned template whose hash is stored on `EventVerification`, the analyzer built once. Unless a VLM feature reaches it first.                                                                                                                   | `00 §5`     |
| BB.7    | Oversized route modules, starting with `api/routes/system.py` (5,515 lines)                                                                                                                                                                                                                                                                                  | `00 §2`     |

**Done when** (every background package): one implementation of the concept remains (a grep proves
it), and the module's tests pass through its interface.

---

## Kickoff prompt

Paste this to the agent taking the backend lane.

```text
You are the backend lane of the uplevel programme. Read docs/uplevel/README.md
(vocabulary, contract, rulings), then docs/uplevel/10-backend.md, then the
docs/uplevel/00-audit.md sections each package cites.

Take the package the coordinator assigns you. Otherwise claim one yourself: the
lowest-numbered package in your current phase that is "not started", not
flagged heavy, unclaimed (no open draft PR titled [<package>]) and whose
dependencies are merged. Claim it by opening that draft PR with
gh pr create --draft --template uplevel.md (docs/uplevel/50-coordination.md).
If every remaining package in your phase waits on another lane, take the next
phase's first ready package; never start Phase 3 before R2 is done.

One package per PR. Write the failing test first. Before marking the PR ready,
dispatch a fresh-context subagent to self-review it against the package's Done
when, and record what it found. Keep commit subjects at 72 characters or fewer.
The PR sets the package's README status row to done, with its number, when it
merges.

Reviews come first (UR-32). Before you start or resume a package, run
gh pr list --state open --label review:backend; review each PR independently against
its package's Done when, the contract and the hot-file rules, post the review
comment in the form 50-coordination.md gives, and remove the label.

Read your own open PRs before resuming a package (UR-35): gh pr view <n>
--comments for each. An owner ruling or a requested change there comes before
new work; nobody tells you about a comment except by writing it.

State only what you have just read (UR-31): every commit, PR, file, test result
and question you cite comes from output you ran in the same turn.

You own backend/. The README's cross-lane rule governs every other file you
touch. When the plan does not answer a question, stop and report the question.

Never wait inside a turn on CI, a check run or a background watcher: read it
once, report what you see and end the turn; your next tick re-reads (UR-38).
```
