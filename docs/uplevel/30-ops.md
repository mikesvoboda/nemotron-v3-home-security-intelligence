# 30 — Ops Lane

> Owns `ai/`, the compose files, `scripts/` (except the AGENTS.md validator, which the docs lane
> owns), `.github/`, `setup.py`, `setup_lib/` and its tests (`backend/tests/unit/setup_lib/`), root
> config files, `archive/`, and the root `tests/`, `monitoring/`, `docker/`, `config/`,
> `env-templates/`, `data/` and `certs/`. Docs this lane's PRs change follow the cross-lane rule. Read [`README.md`](README.md) first: its vocabulary, contract and rulings (`UR-n`)
> bind every package here. Evidence: [`00-audit.md`](00-audit.md).

Work the phases in order. Inside a phase, packages are independent unless a package names a
dependency. One package per PR. The background packages (`OB.n`) may run in any phase after
Phase 1.

---

## Phase 0 — Bootstrap

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

---

## Phase 1 — Stop the bleeding

### O1.1 Mutation hold and supersede (`01` M5)

Specified in [`01-mutation-policy.md`](01-mutation-policy.md) §M5.

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

---

## Phase 2 — Feature truth

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

### O2.2 Feature-check harness

**Depends on:** `O2.1`.

**Files:** `scripts/feature-check.sh`, a CI job, a section in `docs/developer/testing.md`.

- [ ] `--fake` brings up the CI stack with the fake-AI overlay, seeds cameras and the watched
      folder, waits for readiness, runs the golden paths, collects artifacts and tears down. The
      golden paths are the `golden` Playwright project (`frontend/tests/golden/`, `F2.1`) and the
      external-interface pytest specs in `backend/tests/golden/` (outside the default test paths;
      the harness passes them the stack's base URL).
- [ ] Ship a **harness smoke check** with the script: one fixture image in, one event out with the
      scenario's verdict, asserted through the API. It proves the harness before any golden path
      exists.
- [ ] **Isolate every run, in both modes.** Each run creates a **test deployment** and touches
      nothing else on the machine. The prod compose file names no project, so `up` from the
      deployed checkout reuses the live project. It mounts the live camera directory
      (`${FOSCAM_BASE_PATH:-/export/foscam}`, `docker-compose.prod.yml:427,458`), keeps Postgres
      in the `postgres_data` volume, publishes 21 host ports, and pins seven fixed
      `container_name`s (`hsi-go2rtc`, `tempo`, `loki`, `pyroscope`, `node-exporter`,
      `dcgm-exporter`, `alloy`). So every run:
  - uses its own compose project (`-p hsi-check-<run-id>`) and its own generated env file, never
    the checkout's `.env`;
  - starts only the services its golden paths need, and refuses any that carries a fixed
    `container_name`;
  - remaps every published host port, and points `FOSCAM_BASE_PATH` at a fresh per-run directory;
  - shares nothing writable with another stack. Model weights mount read-only. The checkout's
    `./backend/data` is bind-mounted with `U`, which recursively changes ownership of live files
    (`docker-compose.prod.yml:454`); the run points it at a per-run directory. The Triton cache
    mount (`:369`) is read-write: **MEASURE** a cold start with a per-run cache, then **DECIDE**
    per-run copy or a read-only share;
  - has no control over other containers. The backend mounts the host Podman socket (`:468`) and
    its orchestrator — on by default — restarts containers it matches by name substring across
    every compose project (`container_discovery.py:647-656,713-715`). A test deployment **always**
    runs with `ORCHESTRATOR_ENABLED=false` and no container-engine socket in any container, before
    and after `B1.6`: scoping discovery hardens production, but any process holding the socket can
    still drive the raw engine API.
- [ ] **Preflight.** Render the run's effective configuration
      (`podman compose -p <run project> ... config`) and refuse to start when any writable bind
      mount points outside the run's own directory, or when any service mounts a container-engine
      socket. This is what proves the run cannot write live data: isolation rests on what the run
      can reach, not on watching live files, which change all the time (camera uploads,
      thumbnails, logs). Then snapshot the machine — containers (running and stopped) with their
      start times, volumes, published ports, the bind-mount host paths of any running stack — and
      abort if the run's project name, a container name, a host port, a volume, or a writable host
      path overlaps.
- [ ] On the real tier, also **MEASURE** free memory on the chosen GPU (`GPU_LLM`) and abort if a
      second engine would leave a running `ai-vlm` short. Sharing a GPU with a live engine is a
      **RULING**: another GPU, a maintenance window, or calling the live engine read-only.
- [ ] **In-run check.** Once the stack is up, assert that no container in it holds an engine socket
      and that its orchestrator reports disabled.
- [ ] **Teardown and postflight.** Tear down with `podman compose -p <run project> down -v` only,
      never a bare `down`. Then assert that every container and volume in the preflight snapshot
      still exists, and that every container that was running still is, with the **same start
      time** (a restart that already finished leaves a container running but changes its start
      time). An unexplained change in live data is reported on the urgent path and investigated;
      the harness never restores files on its own.
- [ ] Commit tests for the preflight and postflight logic, run against fixture snapshots and
      fixture rendered configs: an overlapping port, container name, volume or camera path, a
      writable bind mount outside the run directory, and a mounted engine socket each make the run
      refuse; an in-run container exposing an engine socket fails the run; a postflight that finds
      a live container missing, stopped or restarted (new start time) fails loudly.
- [ ] `--real` does the same against the prod compose file with real models on the GB300, as a
      test deployment beside whatever already runs there, and prints a summary (date, commit,
      per-spec result, the preflight snapshot, the postflight result) for the operator to paste
      into the PR or the inventory. It never runs from GitHub (UR-15).
- [ ] Add the CI job for `--fake`. **MEASURE** its wall-clock and **DECIDE** the trigger from it:
      every PR, a paths filter, or `main` plus a label.

**Done when:** CI runs `--fake` green with the harness smoke check; the preflight and postflight
tests pass; and the operator has run `--real` once on the GB300, with its summary posted on the PR,
including a postflight result showing every pre-existing container and volume untouched
(`awaiting real tier` until then). `F2.1` then adds its golden project to the same job.

### O2.3 Reachability check (`01` M1)

Specified in [`01-mutation-policy.md`](01-mutation-policy.md) §M1. Its output feeds `F2.2`'s list
of modules serving no feature.

---

## Phase 3 — The tree matches the rulings

Starts after `R2`.

### O3.1 Prune `ai/` to what ships

- [ ] Declare the `ai/` entry points in `O2.3`'s file: the gateway's `main.py`, `export_all.sh`, and
      every build script a Dockerfile or workflow runs. Delete what does not ship (~27K of 35K
      lines at `d6ba78d5`, `00 §4.2`), with the tests that test only it.
- [ ] Strip the gateway image's unused dependencies (torch, transformers, ultralytics, open_clip,
      timm, onnxruntime). Confirm each by import trace; a build-time-only need moves to a build
      stage. **MEASURE** the image size before and after.
- [ ] Apply the `R2` ruling on OD-17: the Triton `reid`/`threat` models, `/enrich-lt`, and
      `ai-llm-vllm`.

**Done when:** `O2.3` reports no non-shipping module under `ai/` outside `keep.toml`, the gateway
image builds, and the golden paths stay green.

### O3.2 Compose base and overlays

- [ ] The prod file is the base; the CI stack and the fake AI are overlays. No service is defined in
      two files.
- [ ] Settle image-version drift: one version per image.
- [ ] Drop the seven fixed `container_name`s, so a test deployment can run every service beside a
      live stack (`O2.2` excludes them until then). Find and update every reference to those names
      first: scripts, dashboards, docs.
- [ ] Cut comments to what an operator needs (42% of the prod file is comments today).

**Done when:** every supported combination renders with `podman compose ... config`, the deploy
tool's tests pass, and the golden paths stay green.

### O3.3 `models.yml` and env truth

- [ ] `models.yml`: delete the dead rows (`yolo11-face`, `yolo11-license-plate`, `paddleocr`,
      `yolo26-general`), correct the `yolo26` row, and add the shipped Qwen3-VL GGUF and mmproj.
      **DECIDE** the one place that names the VLM's identity; today it is spread across compose,
      `.env.example` and `config.py`.
- [ ] `.env.example`: delete the variables read by neither `config.py`, compose nor `setup.py`
      (34 at `d6ba78d5`), with `B3.3` covering the settings side. `test_a5500_precheck.py` reads the
      `GPU_*` names; update it in the same PR.
- [ ] Add a ratchet test: every `.env.example` variable is read by `config.py`, compose or
      `setup.py`.

**Done when:** the ratchet test passes and every `models.yml` row names something that loads.

### O3.4 Reachability gates in CI

- [ ] A CI job fails when a new non-shipping Python module appears without a `keep.toml` entry
      (`O2.3`), and when `knip --production` finds a new unused frontend file or export (`F3.2`'s
      config).

**Done when:** a throwaway branch adding an unimported module fails the gate, and the PR shows that
run.

### O3.5 Weekly mutation scorer and history (`01` M2)

Specified in [`01-mutation-policy.md`](01-mutation-policy.md) §M2. Needs `O2.3` and `B2.1`.

### O3.6 PR mutation evidence tool (`01` M4)

Specified in [`01-mutation-policy.md`](01-mutation-policy.md) §M4. Phase 4's just-in-time
consolidation depends on it.

### O3.7 `scripts/` truth

- [ ] Delete the scripts nothing references (~14 at `d6ba78d5`, `00 §7`) and the one-off
      investigation scripts. Scripts referenced only by `scripts/AGENTS.md`: **DECIDE** keep (a
      documented operator tool) or delete, one line each in the PR.
- [ ] Extend the ruff and mypy pre-commit scope to `scripts/`. **MEASURE** the violations; fix them.
- [ ] Wire into CI or delete the script tests no workflow runs (`test_gen_ai_contract.py`,
      `test_synthetic_media.py`, `test_vlm_probes.py`) and `tests/benchmark/`.

**Done when:** every file in `scripts/` is referenced by CI, a hook, `setup.py`, another script, or
the operator docs, and `scripts/` passes ruff in pre-commit.

---

## Background (any phase after Phase 1)

### OB.2 CI dedupe

- [ ] One dependency-audit workflow (pip-audit and npm audit each run in four today).
- [ ] One release mechanism (three today). **DECIDE** which survives.
- [ ] Every `continue-on-error: true` (40 today) carries a comment with its reason, or goes.

**Done when:** each concern runs in exactly one workflow and every `continue-on-error` has a
reason.

### OB.3 Image weight

- [ ] Delete the 28 PNGs nothing references (15.4 MB).
- [ ] **MEASURE** re-encoding the 1408×768 renders (WebP or JPEG) on a sample. If the owner accepts
      the quality, re-encode them and drop the large-file exemption for `docs/images/`.

**Done when:** no unreferenced image remains and the PR reports bytes saved.

### OB.4 Lane map and cross-lane check

**Trigger:** the first merge conflict between lanes, or a PR found touching another lane's files
without listing them as cross-lane parts. Until then, the README's Lanes table is enough.

- [ ] `docs/uplevel/lanes.toml` maps path patterns to lanes, generated from the README's Lanes
      table.
- [ ] A CI check warns — never fails — when a PR changes files outside the lane named in its
      template without a "Cross-lane parts" section.

**Done when:** the check warns on a fixture diff that crosses lanes silently, and stays quiet on
one that declares its cross-lane parts.

---

## Kickoff prompt

Paste this to the agent taking the ops lane.

```text
You are the ops lane of the uplevel programme. Read docs/uplevel/README.md
(vocabulary, contract, rulings), then docs/uplevel/30-ops.md, then the
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

You own ai/, compose, scripts/, .github/, setup.py, setup_lib/, root config
and archive/. The README's cross-lane rule governs every other file you
touch. Real-model checks run on the GB300 by the operator, never from CI. When
the plan does not answer a question, stop and report the question.
```
