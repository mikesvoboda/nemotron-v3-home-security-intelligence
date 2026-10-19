# Ops packages

Open packages of the ops lane: every package whose row in the
[README status table](../README.md#status) is not `done`. How to claim, build, review and merge
one is in [`../rules.md`](../rules.md) and [`../roles/lane.md`](../roles/lane.md). Finished
packages are in [`../history/packages-done.md`](../history/packages-done.md).

## Lane scope

- The lane owns `ai/`, the compose files, `scripts/` (except the AGENTS.md validator, which the
  docs lane owns), `.github/`, `setup.py`, `setup_lib/` and its tests
  (`backend/tests/unit/setup_lib/`), root config files, `archive/`, and the root `tests/`,
  `monitoring/`, `docker/`, `config/`, `env-templates/`, `data/` and `certs/`. Evidence for every
  package is in [`00-audit.md`](../00-audit.md); `00 §n` cites its sections.
- When the background packages (`OB.n`) may run: UR-51.
- On next touch: the comment at `docker-compose.prod.yml:952` says "SSL enabled by default", but
  the default on `:954` is `false`. The PR that next touches those lines fixes the comment
  (ruling 133).

## Phase 1 — Stop the bleeding

### O1.11 Monitoring behind the gate (UR-33)

**Flags:** `owner`. **Depends on:** `B1.5`, `O1.6`.

**Files:** the `grafana` service's environment in `docker-compose.prod.yml`, `monitoring/prometheus.yml`,
`monitoring/alertmanager.yml`, the Grafana datasource provisioning under `monitoring/grafana/`;
`frontend/nginx.conf` as a cross-lane part.

With `EXPOSE_LAN=true`, `B1.5` refuses every unauthenticated request, monitoring included (UR-33).
The UI's own calls to `/api/metrics` and `/api/system/*` carry its session cookie and keep working;
the callers without a session go blank: Prometheus (`monitoring/prometheus.yml:62` scrapes
`/api/metrics`), Alertmanager's webhook, and Grafana's Backend-API datasource. And `/grafana/` is
published with anonymous **Admin** today (`GF_AUTH_ANONYMOUS_ENABLED=true`,
`GF_AUTH_ANONYMOUS_ORG_ROLE=Admin`), which exposure would hand to the LAN.

- [ ] Write the failing tests first, on a stack with `EXPOSE_LAN=true`: Prometheus's backend
      targets are up; Alertmanager's webhook reaches the backend; `/grafana/` without an app
      session is refused, and with one it is served.
- [ ] Give each machine caller a credential in the form `B1.5` chose, read from the env file and
      never committed.
- [ ] `/grafana/` when exposed: no anonymous access. **DECIDE** between nginx checking the app's
      session (`auth_request` to the backend) with Grafana's auth proxy — one login, and the UI's
      three embedded dashboards (Analytics, Video Analytics, Tracing) keep working — and Grafana's
      own login, which asks again inside each embed. Recommendation: the first.
- [ ] Leave the default (`EXPOSE_LAN` unset) unchanged.

**Done when:** on a running stack with `EXPOSE_LAN=true`, Prometheus shows the backend targets up,
the three embedded dashboards render after one login, and `/grafana/` without a session is
refused.

## Phase 2 — Feature truth

### O2.2 Feature-check harness (fake and real)

**Flags:** `heavy · owner`. **Depends on:** `O2.1`.

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
    every compose project (`container_discovery.py:647-656,713-715`). Every run applies UR-134,
    before and after `B1.6`.
- [ ] **Preflight.** Render the run's effective configuration
      (`docker compose -p <run project> ... config`) and refuse to start when any writable bind
      mount points outside the run's own directory, or when any service mounts a container-engine
      socket. This is what proves the run cannot write live data: isolation rests on what the run
      can reach, not on watching live files, which change all the time (camera uploads,
      thumbnails, logs). Then snapshot the machine — containers (running and stopped) with their
      start times, volumes, published ports, the bind-mount host paths of any running stack — and
      abort if the run's project name, a container name, a host port, a volume, or a writable host
      path overlaps.
- [ ] On the real tier, check the weights' sha256 against the pin before serving, and record
      `agent-gpu status`; the runner's admission rule guards VRAM
      ([`roles/operator.md`](../roles/operator.md), "The agent-gpu path").
- [ ] **In-run check.** Once the stack is up, assert that no container in it holds an engine socket
      and that its orchestrator reports disabled.
- [ ] **Teardown and postflight.** Tear down with `docker compose -p <run project> down -v`
      (UR-135). Then assert that every container and volume in the preflight snapshot
      still exists, and that every container that was running still is, with the **same start
      time** (a restart that already finished leaves a container running but changes its start
      time). An unexplained change in live data goes on the urgent path (UR-143); the harness never
      restores files on its own.
- [ ] Commit tests for the preflight and postflight logic, run against fixture snapshots and
      fixture rendered configs: an overlapping port, container name, volume or camera path, a
      writable bind mount outside the run directory, and a mounted engine socket each make the run
      refuse; an in-run container exposing an engine socket fails the run; a postflight that finds
      a live container missing, stopped or restarted (new start time) fails loudly.
- [ ] `--real` runs in the `uplevel-operator` sandbox (UR-30): the same test deployment in the
      sandbox's own Docker, with the VLM served through `agent-gpu` and reached at the port `run`
      prints ([`roles/operator.md`](../roles/operator.md), "The agent-gpu path"); the detector
      stays the fake one (owner ruling 66). **DECIDE** the VLM's image and VRAM declaration,
      within the runner's 40 GiB cap (UR-30). The preflight
      also refuses any configured host address but that port. It prints a summary (date, commit,
      image tags and `build_info`, VRAM declared and actual, per-spec result, the preflight
      snapshot, the postflight result) for the operator to paste into the PR or the inventory, and
      removes its `agent-gpu` containers, also after a failure. It never runs from GitHub (UR-15).
- [ ] Add the CI job for `--fake`. **MEASURE** its wall-clock and **DECIDE** the trigger from it:
      every PR, a paths filter, or `main` plus a label. (Ruling 105 settled it: the fake-stack
      feature check is a `ci.yml` job that `CI Gate` needs, skipped by the `detect-changes` filter
      on PRs that cannot affect it.)
- [ ] The golden stage runs inside the official Playwright container (UR-131).

**Done when:** CI runs `--fake` green with the harness smoke check; the preflight and postflight
tests pass; and the operator has run `--real` once on the GB300, with its summary posted on the PR,
including a postflight result showing every pre-existing container and volume untouched and an
empty `agent-gpu ps` (`awaiting real tier` until then). `F2.1` then adds its golden project to the same job.

### O2.4 Re-ID on the GB300 GPU via TensorRT

**Flags:** none: not heavy; not owner-tier at merge. **Depends on:** none named. Approved by owner
ruling 107 (issue #6854, comment `6109720693`, 2026-10-11). It is on ops-b's roster queue (UR-52);
it edits `ai/gateway/` (cell A's files), so ops-a reviews.
It may stay open past Phase 2's exit (UR-10, contract rule 5).

- [ ] Serve the gateway's `reid` through TensorRT, a plan built for the serving GPU as `yolo26`'s
      is, not ONNX Runtime's CUDA execution provider, which fails on GB300 (owner ruling 106).
- [ ] Keep `B2.2`'s provenance and model-ID behaviour unchanged; `test_reid_path_parity.py` stays
      green in CI.

**Done when:** the owner's host run (`B2.2`'s command, #6970) prints `RESULT: PASS` on the GB300
host with OSNet-AIN at the PR's head, posted on the PR; the row reads `awaiting real tier` until
then. It does not flip `REID_BACKEND`; production stays `local`.

### O2.5 Production-shape real tier

**Flags:** none: not heavy. **Depends on:** none named; it builds on `O2.2`'s
`feature_check.py --real` and ruling 143's Playwright container. It is on ops-a's roster queue
(UR-52); the operator runs its sandbox run and the owner its maui run (ruling 256).
It gates only ruling 127's 12 real-tier rows, F-295 (ruling 219) and F-296 (ruling 222), not
Phase 2's exit (UR-10, contract rule 5).

Both test tiers run `docker-compose.ci.yml` on Docker (`feature_check.py` `--engine` defaults to
`docker`, `:2189`). Production runs `docker-compose.prod.yml` on Podman (root `README.md:279-307`),
and no test runs that file. Its own surface goes unchecked: Grafana and the monitoring stack,
`userns_mode: keep-id`, the `:U` mounts, CDI devices, `PODMAN_SOCKET` for `backend` and `alloy`,
nginx with TLS, and the real `runtime.env` mounts (ruling 144).

- [ ] **Step 1, a spike, time-boxed to one session.** Does rootless Podman run inside an uplevel
      sandbox (`sudo` is available, UR-176)? Can `docker-compose.prod.yml` come up as a
      disposable project, with its own project name, ports, volumes, env file and camera directory
      (the README's **test deployment**), and with GPU services pointed at `agent-gpu`'s `ai-vlm`
      instead of CDI? The spike posts yes or no, the minimal override file it needed, and every
      blocker. **If no, the spike stops, and the owner rules on the blocker before anything is
      built.**
- [ ] **Step 2, if yes: two runs, split by venue (ruling 256).** `feature_check.py --prod-shape`
      brings up that stack and runs the golden suite against it, using the Playwright container
      from ruling 143, on a test deployment (UR-133). The operator runs the sandbox run from the
      command ops-a posts (UR-140); ops-a posts the maui command on #7037 once `[r195]` carries it,
      and the operator reads that run's output (ruling 185 item 3).
  - **The sandbox run, first (operator).** `--real --prod-shape` in the operator's sandbox, with no
    GPU consumer in the stack but the VLM: `ai-vlm` served by `agent-gpu`, the fake `ai-gateway`, no
    `dcgm-exporter`, and `backend`'s GPU reservation stripped. These are runtime transforms in
    `as_prod_shape_deployment`, not edits to the authored override (ruling 162 item 3), and the run
    record names each removed or stripped device. It witnesses F-102, F-115, F-117, F-164 to F-167,
    F-169, F-174, F-295 and F-296.
  - **The maui run, after it (owner).** `--prod-shape` with the fake VLM, from a host login on maui,
    keeping production's CDI devices for `ai-gateway`, `dcgm-exporter` and `backend`. It witnesses
    F-176, F-178 and F-182 and the CDI wiring (the stack boots with every device resolved), and its
    stop-test states the GPU memory the run takes beside production. `ai-vlm`'s own CDI line is the
    one GPU line neither run boots.
- [ ] **Ruling 162's three answers.** Resource limits stay where cgroup controllers are delegated
      and are stripped otherwise, with `limits: not applied (no cgroup delegation)` in the run
      record. The engine socket, the 7 pinned `container_name`s and the host ports and paths are
      handled by the runner's own test override, never by editing `docker-compose.prod.yml`; a
      CPU-only CI test renders `docker compose config` for both and fails on any difference not
      listed.
- [ ] **Unchanged:** the fake tier, the CI compose and the per-batch real tier (ruling 103) stay as
      they are.
- [ ] Ruling 127's 12 real-tier rows (F-102, F-115, F-117, F-164–F-167, F-169, F-174; F-176, F-178,
      F-182), F-295 (ruling 219) and F-296 (ruling 222) get their witness from `O2.5`'s two runs. If
      the spike says no, they fall back to ruling 127's original route: ops adds what they need to
      the test deployment's compose.

**Done when:** the spike's answer (yes or no, the minimal override file, every blocker) is posted;
on yes, both Step 2 runs have posted: the operator's sandbox run witnesses its 11 rows and the
owner's maui run its 3 rows and the CDI wiring, together ruling 127's 12 rows, F-295 and F-296
(rulings 185, 188, 219, 222, 256); on no, the owner has ruled on the
blocker (ruling 144; the spike's blockers are ruled by ruling 162). When it merges, the owning lanes rewrite the real-tier commands of `F1.2`
(#6909, frontend; the owner runs it) and `O1.11` (#6930, ops-a; the operator runs it) onto the
sandbox run's deployment, in a comment on each PR (rulings 154 and 256).

## Phase 3 — The tree matches the rulings

### O3.1 Prune `ai/` to what ships

**Flags:** none. **Depends on:** `R2`, `O2.3`.
**PR:** #7256 (ruling 241)

**Assigned:** heavy-b, first on its queue (ruling 260). It is owner tier as destructive work (UR-98,
ruling 249).

- [x] Declare the `ai/` entry points in `O2.3`'s file: the gateway's `main.py`, `export_all.sh`, and
      every build script a Dockerfile or workflow runs. Delete what does not ship (~27K of 35K
      lines at `d6ba78d5`, `00 §4.2`), with the tests that test only it. The declaration lands
      first, so `ai/gateway/export/` (O2.4, B2.3) is never on the deleted list (ruling 210).
- [x] `synthbench/host`, `synthbench/generate` and `synthbench/contract` go on `keep.toml` as
      "synthbench workstream (UR-82), ruling 210"; delete `synthbench/spikes/` (ruling 210 amends
      UR-82 for it).
- [x] Strip the gateway image's unused dependencies (torch, transformers, ultralytics, open_clip,
      timm, onnxruntime). Confirm each by import trace; a build-time-only need moves to a build
      stage. **MEASURE** the image size before and after.
- [x] Apply the `R2` ruling on OD-17: the Triton `reid`/`threat` models, `/enrich-lt`, and
      `ai-llm-vllm`. `R2a` ruled it (ruling 89): `ai-llm-vllm` is removed — the service, its `vllm`
      profile and every setting that names it; the re-ID half is `B2.2` (ruling 68); and Triton's
      role is UR-86.

**Done when:** `O2.3` reports no non-shipping module under `ai/` outside `keep.toml`, the gateway
image builds, and the golden paths stay green.

### O3.2 Compose base and overlays

**Flags:** none. **Depends on:** `R2`; both `O2.5` runs posted (ruling 260).
**Assigned:** heavy-b, after `O3.3`, once both `O2.5` runs have posted (ruling 260).
**PR:** none yet. (rulings 241 and 260)

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

**Flags:** none. **Depends on:** `R2`; #7244 (`B3.3`) merged (ruling 260).
**Assigned:** heavy-b, after `O3.1`, once #7244 (`B3.3`) has merged (ruling 260). **PR:** #7281
(rulings 241 and 260)

- [x] `models.yml`: delete the dead rows (`yolo11-face`, `yolo11-license-plate`, `paddleocr`,
      `yolo26-general`), correct the `yolo26` row, and add the shipped Qwen3-VL GGUF and mmproj.
      **DECIDE** the one place that names the VLM's identity; today it is spread across compose,
      `.env.example` and `config.py`.
- [x] `.env.example`: delete the variables read by neither `config.py`, compose nor `setup.py`
      (34 at `d6ba78d5`), with `B3.3` covering the settings side. `test_a5500_precheck.py` reads the
      `GPU_*` names; update it in the same PR.
- [x] Add a ratchet test: every `.env.example` variable is read by `config.py`, compose or
      `setup.py`.

**Done when:** the ratchet test passes and every `models.yml` row names something that loads.

### O3.4 Reachability gates in CI

**Flags:** none. **Depends on:** `R2`, `O2.3`, `F3.2`.
**PR:** none yet. (ruling 241)

- [ ] A CI job fails when a new non-shipping Python module appears without a `keep.toml` entry
      (`O2.3`), and when `knip --production` finds a new unused frontend file or export (`F3.2`'s
      config). New means not in the baseline `F3.2`'s PR records at its merge (ruling 257).

**Done when:** a throwaway branch adding an unimported module fails the gate, and the PR shows that
run.

### O3.5 Weekly mutation scorer and history (`01` M2)

**Flags:** none. **Depends on:** `R2`, `O2.3`, `B2.1`.
**PR:** none yet. (ruling 241)

Specified in [`01-mutation-policy.md`](../01-mutation-policy.md) §M2. Needs `O2.3` and `B2.1`.

### O3.6 PR mutation evidence tool (`01` M4)

**Flags:** `heavy`. **Assigned:** heavy-b (ruling 258). **Depends on:** `R2`.
**PR:** #7251

Specified in [`01-mutation-policy.md`](../01-mutation-policy.md) §M4. Phase 4's just-in-time
consolidation depends on it.

### O3.7 `scripts/` truth

**Flags:** none. **Depends on:** `R2`.
**PR:** none yet. (ruling 241)

- [ ] Delete the scripts nothing references (~14 at `d6ba78d5`, `00 §7`) and the one-off
      investigation scripts. Scripts referenced only by `scripts/AGENTS.md`: **DECIDE** keep (a
      documented operator tool) or delete, one line each in the PR.
- [ ] Extend the ruff and mypy pre-commit scope to `scripts/`. **MEASURE** the violations; fix them.
- [ ] Wire into CI or delete the script tests no workflow runs (`test_gen_ai_contract.py`,
      `test_synthetic_media.py`, `test_vlm_probes.py`) and `tests/benchmark/`.

**Done when:** every file in `scripts/` is referenced by CI, a hook, `setup.py`, another script, or
the operator docs, and `scripts/` passes ruff in pre-commit.

## Phase 4 — Complete the product

### O4.1 One-GPU installs

**Flags:** none. **Depends on:** Phase 4's start (ruling 202, record 6198876496).
**PR:** none yet.

`README.md:242` promises a one-card install, but `setup.py` writes `gpu_llm: 0` and
`gpu_ai_services: 1` in all three modes (`:820`, `:1070`, `:1252`) whatever `get_gpu_info()` finds
(`:795`), and `docker-compose.prod.yml` gives the AI services
`CUDA_VISIBLE_DEVICES=${GPU_AI_SERVICES:-1}`. On a one-card machine they see no GPU.

- [ ] A design session chooses: setup derives the split from the detected GPUs (one card puts both
      on GPU 0, keeping a saved answer on re-run as `[r94]` does), or two GPUs become a stated
      requirement that setup enforces and the README's hardware table states.
- [ ] Whether detection, re-ID and the VLM fit one 24GB card is a real-tier run, settled in that
      session.

**Done when:** a one-GPU setup either runs with every service on a visible GPU or is refused with
the requirement named, and unit tests cover one and two detected GPUs.

## Background (any phase after Phase 1)

### OB.3 Image weight

**Flags:** none. **Depends on:** Phase 1 done.

- [ ] Delete the 28 PNGs nothing references (15.4 MB).
- [ ] **MEASURE** re-encoding the 1408×768 renders (WebP or JPEG) on a sample. If the owner accepts
      the quality, re-encode them and drop the large-file exemption for `docs/images/`.

**Done when:** no unreferenced image remains and the PR reports bytes saved.

### OB.4 Lane map and cross-lane check

**Flags:** none. **Depends on:** its trigger.

**Trigger:** a PR found touching another lane's files without listing them as cross-lane parts.
A merge conflict between rows each lane owns in a shared file is not a trigger (owner ruling 115).
Until then, the README's "Lanes and ownership" list is enough.

- [ ] `docs/uplevel/lanes.toml` maps path patterns to lanes, generated from the README's "Lanes and
      ownership" list.
- [ ] A CI check warns — never fails — when a PR changes files outside the lane named in its
      template without a "Cross-lane parts" section.

**Done when:** the check warns on a fixture diff that crosses lanes silently, and stays quiet on
one that declares its cross-lane parts.

## Ruling-ordered fixes

Fixes an owner ruling ordered outside the phase order. Each keeps the ruling's tag as its id, queues
where its ruling says, and takes the normal queue and review (UR-113). None has a README status row;
the PR that finishes one updates its row in [`../history/ruling-map.md`](../history/ruling-map.md).

### [r96i11] The Python 2–shaped `except` in the fake VLM

**Flags:** none. **Assigned:** `uplevel-ops-a` (ruling 96, item 11). **Depends on:** none. **PR:**
#7052 (merged 2026-10-14T12:58:10Z as `00a979c03`, head `67c5e0ac8`); item 8 of the same ruling merged as #6993.

- [x] `backend/ai_contract/fake/app.py:115` becomes `except (binascii.Error, ValueError):`,
      behaviour-identical on 3.14 and parseable on older Pythons, so the reachability toolchain is
      no longer coupled to 3.14 by one line.

**Done when:** the line reads `except (binascii.Error, ValueError):` on `main` and the fake VLM's
tests pass (ruling 96). Both re-verified at `c1b804a82`: `app.py:115` reads the tuple form, and
`backend/tests/unit/test_r96i11_fake_vlm_except_tuple.py` passes 3/3.

### [r143] The golden stage runs inside the Playwright container

**Flags:** none. **Assigned:** `uplevel-ops-b`. **Depends on:** none named. **PR:** #7034 (merged).
The rule it builds is UR-131.

- [ ] `scripts/feature_check.py`'s golden stage runs `npx playwright test --project=golden` inside
      `mcr.microsoft.com/playwright:v<version>-noble`, where `<version>` is read from
      `frontend/package-lock.json`, never hard-coded. The container reaches the test stack over the
      host network, with the repo's `frontend/` mounted, and runs on the same engine
      `feature_check.py` uses (`--engine`, default `docker`).
- [ ] The browser-install step (`feature_check.py:1555-1580`) and its exit-127 failure mode go: the
      image carries the browser builds and their system libraries. A blocked registry fails as
      UR-131 says.

**Done when** (ruling 143):

1. The fake tier's golden stage passes in CI through the container, with the same counts as
   before.
2. One real-tier run by the operator passes its golden stage through the container.
3. A unit test pins that the image tag follows `package-lock.json`.
4. A sandbox with no Chromium libraries installed runs the golden stage green.

### [r141] Retired-paths timing guard

**Flags:** none. **Assigned:** `uplevel-ops-b`. **Depends on:** none named. **PR:** #7032 (merged).
#7023 (O3.8) merged before ruling 141's changes were made (ruling 145).

- [x] Remove `--durations=20` from the shared anti-rot pytest command in `.github/workflows/ci.yml`
      (the `collection-sanity` step).
- [x] Set `@pytest.mark.timeout(30)` on both retired-paths tests in `scripts/test_retired_paths.py`
      (today `timeout(120)`), with their comment updated to the measured CI time.

**Done when** (rulings 141, 145): the shared step's argument list matches its shape before #7023,
both tests carry `timeout(30)`, and `Collection Sanity` passes at the PR's head.

### [r147] The real-sleep gate re-runs a breach before failing

**Flags:** none. **Assigned:** `uplevel-ops-b`. **Depends on:** none named. **PR:** #7042 (merged).
Builds UR-125 as the owner amended it (owner design session 2026-10-12, pass 2 Q9).

- [x] When the Test Performance Audit finds a unit test over 4.0 s, it re-runs only that test, once,
      in the same job, and fails the run only if the re-run also breaches.
- [x] A test that passes on its re-run is listed as a warning carrying both timings.
- [x] No baseline file and no cross-run allowance are added; `SLOW_TEST_PATTERNS` stays the only
      exemption.

**Done when:** a unit test pins each case (breach then pass on re-run is a warning; breach twice
is red; a 1.5–4.0 s test is a warning only), and the audit passes on `main`'s current tests in CI.

### [r149b] Retire `Nightly Analysis`'s Complexity Trends job

**Flags:** none. **Assigned:** `uplevel-ops-b`. **Depends on:** none. **PR:** #7067 (merged). (ruling
149, record 6146380050)

- [x] Delete the `complexity-trends` (`wily`) job from `.github/workflows/nightly.yml`; it has failed
      on every run since at least 10-03 and nothing reads its report. Security Audit stays.

**Done when:** the next `Nightly Analysis` run is green, or `nightly.yml` holds only Security Audit.

### [r149f] Flaky Test Detection reports to its run summary

**Flags:** none. **Assigned:** `uplevel-ops-b`. **Depends on:** none. **PR:** #7090 (merged). (ruling 149)

- [ ] Remove the issue-creation step from `.github/workflows/flaky-test-detection.yml`; the Analyze
      Flaky Tests job writes its flaky list (test id, pass/fail count over the runs) to the run
      summary instead, and goes green when the analysis itself succeeds. The coordinator routes the
      list (UR-116).

**Done when:** a `workflow_dispatch` run's Analyze job is green and its summary lists the flaky
tests.

### [r151] The integration tier re-runs a breach before failing

**Flags:** none. **Assigned:** `uplevel-ops-b`. **Depends on:** none. **PR:** #7084 (merged). (ruling 151,
record 6149020713)

- [x] Extend `[r147]`'s re-run to the integration tier: an integration test over 10.0 s is re-run
      once in the same job, and the run is red only if the re-run also breaches; a test that passes
      on its re-run is listed as a warning with both timings. At most 5 re-runs per job.

**Done when:** a unit test pins each integration case (breach then pass on re-run is a warning;
breach twice is red), and the audit passes on `main`'s current tests in CI.

### [r157] O2.4: find the re-ID parity failure, and gate the model half in CI

**Flags:** none. **Assigned:** `uplevel-ops-b`, first on its queue, ahead of its F2.3 batch; ops-a
reviews. **Depends on:** none. **PR:** #7087, #7125. (rulings 157, 159)

The owner's O2.4 run at `3e0183e9f` (#7002, result `6154659954`) gave cosine min 0.230, mean 0.331,
against the 0.999 gate on 36 real crops, with build, flags, checkpoint SHA and model IDs all
passing: the embeddings are unrelated, not FP16-imprecise. `test_reid_path_parity.py` mocks
Triton, so CI never checks the model half.

- [ ] O2.4's README row goes back from `awaiting real tier` to `in progress` in this claim PR.
- [ ] A diagnostic script feeds the same crops through each stage and prints cosine per crop and
      per stage against the backend's CPU OSNet vector: PyTorch on the production checkpoint; ONNX
      Runtime on CPU on the exported ONNX; the TensorRT plan called directly in FP32 and in FP16,
      printing Triton's bound input and output names, shapes and layout; and the gateway's
      `/enrich-lt/person-reid`. It runs under UR-133/UR-134: a fresh worktree, a loopback port, a
      read-only cache, and teardown on exit.
- [ ] A CPU-only CI test of the model half: exported ONNX against PyTorch, cosine at least 0.999 on
      fixed crops, using a seeded, randomly initialised OSNet-AIN where the checkpoint is not in CI.
- [ ] One committed runner, `scripts/uplevel/reid_real_tier.sh`, built from `o24.sh` and the owner's
      maui adaptations (both posted on #7087): port, checkpoint directory, GPU and crops directory as
      arguments; the parity check as its default mode and the diagnostic as a second mode; UR-133 and
      UR-134 kept (ruling 159).
- [ ] The fix for the first stage under 0.999, here or in a follow-up PR this one names: `[r252]`
      (ruling 252).
- [ ] The runner builds each stage's plan independently: stage 3 probes the FP32 plan straight
      after its build, and a failed build leaves its stage `unknown` instead of ending the run. A
      `--plan-timeout <s>` flag reaches `export_reid.py`'s build, default 600 s, and each build logs
      its wall time and `nvidia-smi` compute apps into the run directory. The owner's 10-14 run
      lost stage 3 when the FP16 build hit 600 s; the same build took 137.7 s on 10-13. The owner
      reruns with `--plan-timeout 1800` (ruling 180).
- [ ] An agent-gpu venue for the runner, so the operator runs it (UR-15): `agent-gpu build` for the
      gateway image; `agent-gpu job` for the export, the `trtexec` compiles and the stage-3/4 probe,
      in an image whose Python imports a `tensorrt` matching the plans' builder; `agent-gpu run`
      for the Triton leg; inputs from the operator's `$AGENT_GPU_DIR/models/`, results in `out/`.
      The owner copies the checkpoint and crops there once; the crops never leave it. Until this
      works, the owner's maui runs stay valid (ruling 188).

**Done when:** a diagnostic run (the operator's, or the owner's on maui) is posted on this PR, and O2.4's command
(#6970's) then prints `RESULT: PASS` at the fix head, posted there; O2.4 goes to `done` and `B2.3`
is unblocked. The 0.999 gate stays (ruling 68) and `REID_BACKEND` stays `local`. Under ruling 252
the fix head is `[r252]`'s, so this PR merges as the instrument and its `RESULT: PASS` clause is
read there.

### [r162] The engine socket follows the orchestrator setting

**Flags:** owner (production safety). **Assigned:** `uplevel-ops-a`. **Depends on:** `O2.5`
merged. **PR:** #7114. (rulings 162, 186)

- [ ] `backend` mounts `${PODMAN_SOCKET}` only when the orchestrator is enabled
      (`docker-compose.prod.yml:473` at ruling 162), not unconditionally. `alloy` keeps its
      unconditional mount and its `:?` (`:1584`): it uses the socket for container discovery, log
      scraping and profiler targets, not orchestration (ruling 186).
- [ ] A migration note for the live deployment's next redeploy.

**Done when:** a production config rendered with the orchestrator off gives `backend` no engine
socket, one with it on mounts it as before, `alloy`'s mount is unchanged in both, and `O2.5`'s
override drift test still passes.

### [r189] The golden Playwright leg's cap follows its measured time

**Flags:** none. **Assigned:** `uplevel-ops-a`, first on its queue; ops-b reviews. **Depends on:**
none. **PR:** #7169. (ruling 189)

- [x] The golden Playwright leg's `timeout=1800` (`scripts/feature_check.py:2341` at ruling 189)
      becomes the slowest golden-leg wall time on the last 10 green `Feature check (fake AI)` runs on
      `main`, plus at least 50%, rounded up to a minute; the PR body lists the 10 times. #7114 died
      at test #199 twice with exit 124, and green legs kept only 66-306 s of margin.
- [x] The job's `timeout-minutes: 60` (`.github/workflows/ci.yml:3596` at ruling 189) rises if boot,
      the backend leg and the new cap would leave it under 10 minutes of margin.
- [x] A test pins the value, so a later change comes with its own measured note. The image pull and
      build timeouts, the seeded job's budget (ruling 187) and per-test timeouts are unchanged.

**Done when:** the new cap is on `main` with its measurement, and #7114's golden leg completes under
it.

### [r193] Lanes wake on GitHub events

**Flags:** `owner` (the role files' tick text). **Assigned:** `uplevel-ops-a`, after `[r189]`;
ops-b reviews. **Depends on:** none. **PR:** #7175. (ruling 193)

Fixed-interval ticks add up to one tick of delay to every handoff, and an agent's view of a PR is
only as fresh as its last tick.

- [x] A watcher script in `scripts/uplevel/` that an agent keeps armed as a background task. It
      polls GitHub about every 60 s with one GraphQL query per poll and never the search API (its
      30-per-minute limit is shared by every agent on the owner's token). It watches the PRs the
      agent owns or must review (its lane, cell and `review:<lane>` labels, plus PR numbers it is
      given) and new `BINDING NOW` records on #6854.
- [x] It exits with one line naming the PR and the change on a new head commit, a check reaching a
      conclusion, a review, a comment, a label change, or a merge or close, and prints no comment
      bodies. Transient API errors do not end it; repeated failures do, with an error line. It
      exits after a bounded lifetime with a "no change" line, so the agent re-arms it.
- [x] Tests pin the change detection and the error exit.
- [x] The tick sections of `roles/lane.md`, `roles/coordinator.md` and `roles/operator.md`: the
      Claude Code lane agents re-arm the watcher at the end of every turn, and their `/loop` tick
      becomes a 30-minute fallback; the coordinator (30 minutes, ruling 239), the operator (30 minutes) and the
      heavy agents under pi (15 minutes) keep their ticks. The PR says whether pi wakes an agent on
      a finished background task, if ops-a can measure it. (The PR says it is unmeasured: `pi` is not
      installed in the lane sandboxes, so #7175 reports "said, not measured"; the box is ticked on
      the same basis as the three above it — the role-file text is in this diff — while the package's
      separate "Done when: the watcher is on `main`" line stays open until the merge.)

**Done when:** the watcher is on `main` with its tests, and the role files' tick sections say how
each agent wakes.

### [r195] O2.5 runs from a host login

**Flags:** none. **Assigned:** `uplevel-ops-a`, after `[r193]`; ops-b reviews. **Depends on:**
none. **PR:** none yet. (ruling 195)

The owner's maui run (`6193951294`) died at VLM readiness: the harness reaches the VLM only at
`host.docker.internal`, which does not resolve from a host login. Ruling 256 split `O2.5` by venue
instead of picking a route to the VLM, so this package carries:

- [ ] The operator's sandbox run's transforms in `as_prod_shape_deployment`: the fake `ai-gateway`,
      no `dcgm-exporter`, and `backend`'s GPU reservation stripped, beside the `ai-vlm` removal; the
      run record names each removed or stripped device (ruling 256 item 1).
- [ ] The maui command: `--prod-shape` with the fake VLM, from a host login, keeping production's
      CDI devices for `ai-gateway`, `dcgm-exporter` and `backend` (ruling 256 item 2).
- [ ] That command's stop-test states the GPU memory the run takes on the GB300 beside production.

Ruling 256 dropped this package's earlier boxes: the harness reaching the VLM on loopback outside a
sandbox, the container-to-host route, the `loki`/VLM-pool collision and `AGENT_GPU_TOKEN_FILE`.

**Done when:** the fixes are on `main` with tests, and ops-a has posted the maui command on its PR
and on #7037 (ruling 185 item 3: the operator reads the output).

### [r196c] The seeded rows F-186, F-196 and F-197

**Flags:** none. **Assigned:** `uplevel-ops-b`, first on its queue, claimed now while `[r157]`
waits on the operator (UR-52 waived, ruling 217). **Depends on:** none.
**PR:** #7189 (merged 2026-10-16T13:02:29Z as `c941d1481`, head `ba4ff9495`). (rulings 127, 187,
196, 217; record 6200901387)

- [ ] Specs for F-186, F-196 and F-197 in ops-b's batch directory
      `frontend/tests/golden/gpu-storage-admin/` (ruling 87) run in `Feature check (seeded)`, the
      job #7155 built under ruling 187. The PR's title carries `[r196c]`; frontend reviews.

**Done when:** none of the three rows says **unverified**; each flipped on a run where its leg
executed and passed, or was demoted for `R2b` with the failure as evidence (rulings 103, 114).

### [r235] Seeded rows on the real tier

**Flags:** none. **Assigned:** `uplevel-ops-b`, first on its queue, claimed now while `[r157]`
waits (UR-52 waived, as ruling 217 did). **Depends on:** none. **PR:** #7214. (ruling 235,
record 6216273821)

About 11 rows are witnessed only by `*.seeded.spec.ts` legs (F-012, F-133, F-138, F-154–F-156,
F-186, F-196, F-197, F-278), and `scripts/feature_check.py` refuses `--seeded` without `--fake`
(`:3193-3194`), so no real-tier run executes them.

- [ ] `--seeded` is accepted with `--real`: the real-tier boot (UR-136) applies the seeded
      overrides (`:500-505`) and fixtures (`:2110-2257`) and runs `golden-seeded` (`:2345`).
      `--seeded --prod-shape` stays refused.
- [ ] Tests pin the flag matrix: `--fake --seeded` unchanged, `--real --seeded` accepted,
      `--prod-shape --seeded` refused.
- [ ] After merge, the operator runs `--real --seeded` (UR-15) and posts the output here. Each
      seeded row whose leg passes moves to **works** with the run's date (ruling 153), except a row
      ruling 207 or 231 lists, which keeps `needs real Triton models`.

**Done when:** the tests pass in CI at a ready head, and the operator's `--real --seeded` run is
posted on the PR.

### [r239] The coordinator's heartbeat goes stale at 90 minutes

**Flags:** none. **Assigned:** `uplevel-ops-b`, after `[r235]` (ruling 239; ruling 266 retired
`[r240]`).
**Depends on:** none. **PR:** none yet. (ruling 239, record 6217014151; ruling 245, record 6223117374)

The coordinator's loop fires every 30 minutes (`roles/coordinator.md`), and a tick may run 60, so a
healthy coordinator's heartbeat can be about 90 minutes old. `scripts/uplevel/coordinator_snapshot.py:66`
sets `STALE_HEARTBEAT_MIN = 20` for every heartbeat, and `scripts/uplevel/lane_tick.py:623` tells a
lane to raise UR-162 from that flag.

- [ ] `coordinator_snapshot.py` flags the coordinator's heartbeat stale past 90 minutes and every
      other heartbeat past 20, in its `stale` flag (`:1094`) and its `STALE` print (`:1358`), so
      `lane_tick.py`'s UR-162 line follows.
- [ ] `scripts/uplevel/status_draft.py:170`'s note names both numbers.
- [ ] Tests pin both thresholds.
- [ ] One per-agent interval table (ruling 245): `coordinator_snapshot.py` flags each agent stalled
      past three of its own intervals (UR-38), beside UR-162's 90-minute coordinator threshold.
      Whichever of `[r193]` and `[r239]` merges second sets the lanes' row to the cadence then in
      force: 15 minutes (stalled at 45) before `[r193]`, 30 (stalled at 90) after. UR-166's
      20-minute listing in the status comment is unchanged.

**Done when:** the tests pass in CI at a ready head, and a coordinator heartbeat between 20 and 90
minutes old prints no UR-162 line in `lane_tick.py`'s digest.

### [r197] The digest's formats are checked where they are written

**Flags:** `owner` (the role files' tick text). **Assigned:** the owner's session, as an owner PR;
ops-b reviews. **Depends on:** none.
**PR:** #7186. (ruling 197, as amended by `6198199744`)

Lanes act on what `scripts/uplevel/lane_tick.py` parses, and nothing checks those fields where they
are written: a wrapped `**PR:** none yet` goes unoffered, owner pointers reach the digest only as a
comment count, and heartbeat markers drift.

- [ ] A CI plan lint that imports `lane_tick.py`'s own parsers and runs them over the plan files in
      the PR's tree. It fails when a roster token has no package block, a block's `**PR:**` field
      reads neither `none yet` nor `#N`, a token sits in two lanes' queues, or a ruling-map row
      lacks its record id. Tests pin each failure, and one runs the lint on the real tree.
- [ ] Owner records and pointers end with one HTML-comment footer:
      `<!-- uplevel: ruling=<n> lanes=<names|all> packages=<tokens|none> -->` for a record and
      `<!-- uplevel: pointer ruling=<n> lane=<name> -->` for a pointer. `lane_tick.py` prints a
      `for you:` line for each live record and each owner pointer since the beat that names the
      lane or `all`; one without a footer prints as today. `scripts/uplevel/post_record.py` posts
      both with the exact footer.
- [ ] A `--beat "<text>"` mode writes the agent's heartbeat itself, marker line first, with
      UR-155's 600-character cap.
- [ ] For ruling 198, the digest drops its `review:<lane>` section and marks the agent's own PRs:
      `needs your review` (ready, CI finished at the head, no review for that head) and
      `arm auto-merge` (approved at the head, `Plan text: none`, `CI Gate` green, not a draft, not
      owner-tier, auto-merge off).
- [ ] The tick sections of the role files name the footer lines and `--beat`. `[r193]` edits the
      same sections, so whichever merges second rebases onto the first.

**Done when:** the lint runs in CI and passes on `main`, `lane_tick.py` prints `for you:` lines
from footers, and `--beat` writes a heartbeat the coordinator's snapshot reads.

### [r242] plan_lint checks every roster row again

**Flags:** none. **Assigned:** the owner's session, as an owner PR; ops-b reviews (ruling 242).
**Depends on:** none. **PR:** #7221. (ruling 242, record 6221764225)

`[r197]`'s lint skipped every roster row whose review label is `none`, and ruling 198 set every
label to `none`. So check 1 (a queue token with no block) and check 3 (a token on two lanes'
queues) checked nothing, and ruling 241's missing `B3.1` slot surfaced only by hand.

- [ ] Checks 1 and 3 run on every roster row, whatever its label. A lane with a package file keeps
      check 1 against that file alone, since its digest reads no other. The lanes with none
      (coordinator, heavy-a, heavy-b, operator; `lane_tick.py`'s `packages` docstring) are named,
      and their tokens are looked up across every package file. The operator's row lists real-tier
      runs (UR-15, ruling 188), so check 3 does not count it. The shared `F2.3` rule is kept.
- [ ] Tests pin a `none`-labelled row with a missing block, a token on two lanes' queues (heavy-a's
      among them), a heavy-a row whose tokens live in other lanes' files, and the real roster: a
      token no block carries, planted on each real row, is caught on every one.
- [ ] Each finding the fixed lint reports on `main` is fixed in the same PR: heavy-a's
      `[r196a]` entry (ruling 226's split) no longer leads with the token frontend's row holds.

**Done when:** the suites pass, the lint reports 0 findings on the PR's tree with no baseline (what
`main`'s own run checks), and putting back the `none`-label skip fails the new tests.

### [r243] prod.yml's engine-socket condition renders on every supported Compose

**Flags:** `owner` (production safety). **Assigned:** `uplevel-ops-a`, first on its queue, and
claimable while #7175 waits on review (UR-52 waived, as rulings 217 and 235 did). **Depends on:**
none. **PR:** #7222. (ruling 243, record 6222454848)

`[r162]` (#7114) gave `docker-compose.prod.yml` a top-level `include:` of
`docker-compose.engine-${ORCHESTRATOR_ENABLED:-true}.yml`, which redeclares `services.backend`. The
Nightly Full Gate's Compose (`/usr/libexec/docker/cli-plugins/docker-compose`, reached through
`podman compose`) refuses that with `services.backend conflicts with imported resource`, and the 8
compose-render tests in `backend/tests/unit/core/` fail (run 38877698644).

- [ ] Ruling 186's socket condition moves to a mechanism every supported Compose renders: a `-f`
      overlay the deploy tooling selects, or another one ops-a measures. The `:-true` default and
      alloy's unconditional mount are unchanged.
- [ ] The PR body names the command the live host runs to check its own render before the next
      redeploy.
- [ ] The routing of the 8 tests to backend is withdrawn: backend owes nothing for raise
      `6216622756`, and the coordinator closes it when this package's nightly run is green.

**Done when:** the Nightly Full Gate, re-run by `workflow_dispatch` at the PR's head or after
merge, is green with the 8 tests passing; and the PR shows `docker-compose.prod.yml` rendering, with
and without `ORCHESTRATOR_ENABLED=false`, on the runner's Compose, on compose v5.5.1 and on
podman-compose 1.6.0.

### [r247] A host-side supervisor runs the coordinator's ticks

**Flags:** `owner` (privileged host tooling; plan text). **Assigned:** `uplevel-ops-b`, after
`[r235]`, ahead of `[r240]` (ruling 247; ruling 266 retired `[r240]`). **Depends on:** none.
**PR:** #7248. (ruling 247, record 6223821495)

On 2026-10-16 the coordinator posted nothing from 03:47Z to 13:30Z: its in-pane `/loop` dispatcher
stopped, and nothing in the swarm can restart a pane. Each tick is already a fresh, unnamed subagent
whose only memory is its heartbeat's `read-through:` cursor (UR-173), so the dispatcher adds only a
process that can die or hang.

- [ ] `scripts/uplevel/launch.py supervise <session>`, which the owner's timer runs (UR-26). One
      fire is one tick: the coordinator's tick prompt, word for word as the `/loop` line quotes it,
      run once as a headless `claude -p` inside `agent-<session>` through `sbx exec`, on the pane
      session's model and permission mode. The PR shows how it established both.
- [ ] A host lock skips a fire while the previous tick runs, and a tick that has run 60 minutes is
      killed.
- [ ] Each fire appends one line to a host log: start, end, exit status, whether it was killed, and
      the tick's five-line summary.
- [ ] `--dry-run`, and exit 2 naming the next step when the sandbox is not running, as `up` and
      `retire` do.
- [ ] The PR documents a 30-minute timer on maui (ruling 239) for the owner to install, and rewrites
      `roles/coordinator.md` "Kickoff prompt" for the supervisor (and `sandboxes.toml` if the
      coordinator's row changes). The owner switches over: first ends the pane's `/loop` session,
      then enables the timer.
- [ ] Two dispatchers never run at once.
- [ ] The coordinator only. Lanes, heavy agents and the operator keep their panes. After 48 hours
      of supervised ticks, the owner decides by a new ruling whether the supervisor extends to
      them.

**Done when:** the PR shows `--dry-run`'s output and one real manual fire: its log line, and the
heartbeat patch that tick made.

### [r248] A ready package PR names itself in its own block

**Flags:** none. **Assigned:** the owner's session, as an owner PR; ops-b reviews (ruling 248).
**Depends on:** none. **PR:** none yet. (ruling 248, record 6223962176)

UR-183 has each package PR write its own number into its block's `**PR:**` field. Of the 130 PRs
merged since 2026-10-14, 17 were register or stamp fixups that rewrote such a field after a merge.

- [ ] `scripts/uplevel/plan_lint.py` reads the pull request from `GITHUB_EVENT_PATH` when CI runs on
      one, so `ci.yml`'s step does not change. On a ready (not draft) PR, for each leading
      `[token]` in the title that has a `### ` block, it reports one finding when the block's
      `**PR:**` field does not name this PR's number.
- [ ] Titles that name no block (`[UR-48]`, `docs(...)`) and `F2.3`'s batches (`SHARED`) are
      skipped, and a push to `main` is unaffected.
- [ ] Tests pin a ready PR whose block says `none yet` (a finding), one that names itself (clean), a
      draft (skipped), a title with no block (skipped), and two tokens in one title.
- [ ] `scripts/uplevel/lane_tick.py`'s `next_claimable` docstring stops calling the field
      "coordinator-owned" (UR-183).

**Done when:** the suites pass, and the check reports this PR's own block until the block names this
PR.

### [r251] The feature inventory's §2 summary is computed, not stored

**Flags:** none. **Assigned:** the owner's session, as an owner PR; ops-b reviews (ruling 251).
**Depends on:** none. **PR:** #7226. (ruling 251, record 6224408012; correction 6224625255)

Two PRs that flipped different rows of `docs/reference/feature-inventory.md` both edited §2's `all`
row, so they conflicted though their real edits did not: about 20 recount and conflict commits
across 11 PRs since 2026-10-14.

- [ ] §2's table becomes one paragraph saying how to print it, and the `## 2. Summary` heading
      stays.
- [ ] `scripts/check-inventory-summary-arith.py` prints the table (and `--json`) from §3's rows,
      with the status vocabulary from §1's `### Statuses` legend, and refuses a table stored under
      §2 again.
- [ ] The row checks keep their exit codes (a status outside the legend 1; a section listed twice
      or an unreadable table 2), and `inventory_witness.py`'s helpers and `check()`'s census stay.
- [ ] `scripts/test_check_inventory_summary_arith.py` pins the computed table on fixtures and the
      real file's rows parsing cleanly. The PR runs the full Feature check once.
- [ ] No PR edits §2's counts: a PR that changes a row's status edits only that row. Until this
      package lands, an open PR drops its §2 hunk at its next push, and may merge with
      `check-inventory-summary-arith.py` failing on §2 alone, if its review names that failure.

**Done when:** the suites pass, and the printed table equals the stored one it replaces.

### [r252] Re-ID: find and fix the ONNX→TensorRT plan-build divergence

**Flags:** none. **Assigned:** `uplevel-ops-b`, first on its queue, ahead of `B2.3`. Where it edits
`ai/gateway/` (cell A's files), UR-9 applies. **Depends on:** none. **PR:** #7238. (ruling 252,
record 6235589555)

Operator run 188.17 (`6235043370`: `[r157]`'s runner at `f99058805`, 36 crops) read `onnx-cpu`
at 1.00000 (min and mean), `plan-fp32` at min 0.35205 / mean 0.45675 and `plan-fp16` at min 0.23046
/ mean 0.33142, against the 0.999 gate. FP32 carries no half-precision rounding, so the divergence
enters at the ONNX→TensorRT plan build, deterministically (ops-b `6235236028`). The exported
OSNet-AIN graph has five `InstanceNormalization` nodes, the one op in it with a TensorRT fidelity
history; rewritten into primitives, it matches the original under ONNX Runtime on CPU to 9.686e-08
(`6235312093`). This is `[r157]`'s box-5 follow-up.

- [ ] 188.18 as `6235312093` proposes: plans rebuilt from the `InstanceNormalization`-decomposed
      ONNX through `[r157]`'s runner, run once by the operator (UR-15), and the stage table posted
      verbatim on the PR.
- [ ] If a plan stage still reads under 0.999, post the measured table and its reading on the PR;
      the next step goes to the owner through the coordinator's status comment before any further
      spend.
- [ ] The change ships with a CPU-only CI test that pins it.

**Done when:** `[r157]`'s Done when, read at this package's head: O2.4's command (#6970's) prints
`RESULT: PASS`, posted on the PR, and the CPU-only test above is green in CI. The 0.999 gate stays
(ruling 68), `REID_BACKEND` stays `local`, and serving re-ID through ONNX Runtime instead of
TensorRT plans is not authorised.

### [r164a] The coordinator's paperwork moves into scripts

**Flags:** none. **Assigned:** `uplevel-ops-a`, next on its queue after `O2.5`; ops-b reviews.
**Depends on:** none. **PR:** #7154. (ruling 164)

The coordinator re-derives by hand what a script can compute, and that is where today's misses came
from: hand-typed UR-106 hashes, ruling 156's auto-merge audit, and #7037's owner questions absent
from the status comment for 25 hours.

- [ ] `coordinator_snapshot.py` also prints, per open PR: the UR-106 own-diff hash at its head and
      at its approved head, with `carry: yes | no`; whether auto-merge is armed on a head that is
      neither approved nor carried (the disable list, UR-108); and, per PR merged since the
      cursor, the audit verdict (merged head is the approved head or a carry; owner comments naming
      it) with a pre-filled UR-29 merge comment.
- [ ] A new `scripts/uplevel/status_draft.py` writes the status comment's body in UR-166's order
      from the snapshot's data, listing every open PR, drafts included, with a non-empty "Questions
      for the owner" section, and warns above about 4,000 characters. The coordinator edits the
      draft's judgement lines (options, recommendations) and posts it.
- [ ] `roles/coordinator.md` shrinks to match: "Merging a PR" step 2's hash pipeline, "Auditing an
      auto-merge" and "The status comment" step 3 become one-line pointers to the scripts.

**Done when:** unit tests pin each new field on recorded fixtures (a carried and an uncarried roll,
an armed unapproved head, a draft with owner questions), and one coordinator tick runs on the new
output with its status comment drafted by `status_draft.py`.

### [r181] The lane-tick digest and the signed-activity snapshot

**Flags:** none. **Assigned:** `uplevel-ops-b`, after its `F2.3` OP-3 rows and before `[r172]`;
ops-a reviews. **Depends on:** none. **PR:** #7164 (merged). (ruling 181)

- [x] `scripts/uplevel/lane_tick.py --sandbox <name>`, read-only, one call, at most 80 lines: the
      agent's heartbeat id and age, the coordinator's heartbeat age (UR-162), and disk use of `/`
      and `/var/lib/docker` with a pointer to UR-180 above 90%; the live `BINDING NOW` records the
      ruling map does not yet carry (ruling 177's filter); PRs labelled `review:<lane>` with head,
      merge state, `CI Gate` at that head (paginated past 100 check runs) and the `Plan text:` line;
      its own open PRs with head, commits behind `origin/main`, merge state (`DIRTY` flagged),
      `CI Gate` at head (in-flight jobs read from the run's jobs), and comments and reviews since
      its heartbeat; and the next claimable roster package (UR-52) when it holds no open claim. A
      failed `gh` or `git` call prints `ERROR <section>`, never an empty section.
- [x] `coordinator_snapshot.py`'s heartbeats section prints, beside each non-paused agent's age, its
      latest signed comment and its latest commit on its open PR branches since its heartbeat
      (ruling 178's signature rule), and any `BLOCKER:` line.
- [x] Red-first unit tests for both, with `gh` stubbed; `roles/lane.md` and `roles/operator.md`
      "The tick" and `roles/coordinator.md` step 5 point at them in the same PR.

**Done when:** a lane tick reads through `lane_tick.py` alone, the snapshot shows each agent's
activity beside its heartbeat age, and the tests pin every section. A disk warning points at
UR-180's order, never at a routine full prune (ruling 176).

### [r172] A per-module import budget for the duration gate

**Flags:** none. **Assigned:** `uplevel-ops-b`, after `[r157]`; ops-a reviews. **Depends on:** none.
**PR:** none yet. (ruling 172; issue #7102)

- [ ] `scripts/check-test-duration-budget.py` computes each module's import cost as
      `<testsuite time>` minus the sum of its `<testcase time>`s and applies UR-125's numbers per
      module, with UR-125's single re-run and shared re-run cap; per-test budgets and
      `worst_durations()` keep their meaning.
- [ ] It ships warning-only; after one scheduled nightly the modules over each threshold are posted,
      and it turns failing once each is fixed or in `SLOW_TEST_PATTERNS` with a measured note.
- [ ] A pin fails when the import stall is left out of the compared number.

**Done when:** the module budget fails CI on a reproduced import breach, the warning-only nightly's
list is posted, and the existing duration pins pass.

### [r215a] F-278: a test-only face vector in the seeded project

**Flags:** `heavy`. **Assigned:** heavy-a, after `[r199]`; heavy-a opens its own draft PR.
**Depends on:** none. **PR:** #7188 (merged 2026-10-15T21:41:12Z as `091ffa623`, head `2572c6ca6`).
(ruling 215, record 6200719567)

- [ ] `Feature check (seeded)`'s setup inserts one known person and one face-embedding row with a
      fixed vector and a `model_id` marked test-only, as F-012's disk seed did (#7178, ruling 192).
      No production route or model changes.

**Done when:** the seeded job's stack holds that person and embedding at a ready head, and
`[r215d]`'s leg can run against it.

### [r218] The inventory's status is checked against the golden run

**Flags:** `owner` (CI and the witness convention). **Assigned:** the owner's session, as an owner
PR. **Depends on:** none. **PR:** #7193. (ruling 218, record 6201875149)

Ruling 208's count (`6200252063`): 106 of 254 record-repair commits mainly edit the inventory, and
status flips, evidence cells and witness ids lead. Each Feature check job already records per-test
results (`summary["results"]["golden"]["playwright_specs"]`, `scripts/feature_check.py`), and the
golden specs carry their rows' `F-NNN` ids in their titles.

- [ ] A script maps each executed golden test to the rows its title names, and lists golden specs
      that name none.
- [ ] Rules (UR-128; rulings 103, 114, 148): a row at **awaiting real tier** or **works** needs at
      least one mapped leg, each executed and passed; a failed or skipped mapped leg fails that row;
      an **unverified** row whose legs all passed prints as ready to flip, with the cell text.
      Real-tier confirmation stays the operator's.
- [ ] CI: the check runs after the golden project in `Feature check (fake AI)` and
      `Feature check (seeded)`, fails on a row claiming more than the run shows, prints rows ready
      to flip, and fails closed on a read error with its reason.
- [ ] Evidence cells name the spec and legs; run and job ids are no longer required there.
- [ ] Disagreements the check finds on `main` are fixed in this PR or listed for the owner, so
      `main` stays green.

**Done when:** the check runs in both Feature check jobs and passes on `main`, with unit tests
for each rule.

### [r184] The launcher prints the heavy sessions' pi start line

**Flags:** none. **Assigned:** ops-a. **Depends on:** none.
**PR:** none yet. (rulings 184 and 201, records 6177514438 and 6198825479)

Ruling 184's commit renamed the heavy rows in `scripts/uplevel/sandboxes.toml`. The owner starts
both with `agent-dgx <name> pi --split`, but `launch.py` still builds
`agent-dgx run <name> --agent claude --split` for them (`[models] strongest`).

- [ ] The launcher's line for `uplevel-heavy-a` and `uplevel-heavy-b` is the owner's pi start line.
      Take its exact form from `agent-dgx help` output the owner posts from maui, or from a line
      the owner pastes on the PR; the launcher never invents a flag (`history/packages-done.md`
      §O0.1).
- [ ] If that form cannot be written as `agent-dgx run` arguments, the launcher refuses the two
      rows, naming the hand-start line, and prints no wrong line.
- [ ] `backend/tests/unit/scripts/test_uplevel_launch.py`: the heavy rows give the pi line or the
      refusal, and no other row's line changes.

**Done when:** the launcher test passes in CI at a ready head, and `sandboxes.toml`'s comment no
longer says the launcher does not print the form.

### [r264] The golden Playwright suite runs in shards, each on its own stack

**Flags:** owner (it changes what `CI Gate (Required Checks)` runs, UR-119). **Assigned:** ops-a,
first on its queue, held beside #7231 under ruling 264 item 2, a one-off exception to UR-52.
`lane_tick` prints no claimable package while #7231 is open, so ops-a claims this one from this
block. Work the O2.5 runs need on #7231 or #7037 comes first whenever it arises: the operator's
sandbox run once its disk grows, the maui command, and the no-flag refusal the owner asked for
(`6257622404`). The exception ends when #7231 or #7264 merges. **Depends on:** none. Its one
review is ops-a's UR-89 subagent (UR-32); an edit to a golden spec follows UR-9.
**PR:** #7264. (ruling 264, record 6257854715)

A full CI run takes 45–50 minutes, and `Feature check (fake AI)` is 42–47 of them; no other job
passes 9, and jobs wait a median 0.3 minutes for a runner (8 runs measured on 2026-10-19). Inside
that job the golden Playwright project takes about 39 minutes, on one worker and in series
(`frontend/playwright.config.ts`:289-290), because every spec shares one stack. Each PR runs CI two
or three times, so CI sets every lane's pace. Shards on separate stacks keep each shard serial and
cut the wall time.

- [ ] **MEASURE** before the gate changes. Run the golden project split across N shards, each in
      its own CI job with its own stack (Playwright's `--shard=i/N`), for N = 2, 3 and 4, at least
      twice each. The measurement jobs live in their own workflow file that the gate does not
      require, because a `ci.yml` job that `ci-gate` does not reach turns the job-graph check red
      (`scripts/test_ci_job_graph.py`); they run on a ready PR or by `workflow_dispatch`, since the
      feature check skips drafts, and the file goes when Build lands. Post a table on the PR: each
      shard's wall time, the slowest shard's, whether the union of the shards' legs equals the
      unsharded run's legs at the same head (names and count), and every failure seen only when
      sharded. Pick the smallest N whose slowest shard, setup included, finishes in about 20
      minutes or less; at most 4. If 4 shards still leave the slowest above that, take 4, name the
      slowest spec files on the PR, and split the longest of them (a golden spec, UR-9).
- [ ] **Build.** `Feature check (fake AI)` becomes N shard jobs and one fan-in job.
  - The shard jobs do not run the inventory witness. The fan-in merges the shards'
    `playwright_specs` and `backend_specs` into one fake-mode summary and runs the witness once over
    it, so a row is judged on the union exactly as the single run judges it today.
  - The reference leg set is `playwright test --list --project=golden` at that head plus the
    backend golden tests. The fan-in fails if any shard failed or was cancelled, or if a leg of the
    reference set is missing from the union.
  - The fan-in runs with `if: always()`: the gate counts a skipped job as passed, so a fan-in
    skipped after a red shard would leave the gate green.
  - `CI Gate (Required Checks)` needs the fan-in in place of the single job, and stays the one
    required check (UR-119). The backend golden tests run once, in one shard.
- [ ] A spec that passed only because of the serial run's order is fixed in its spec (UR-9).
      `GOLDEN_LEG_TIMEOUT_S` (ruling 189) already bounds each Playwright run, so each shard keeps
      it. The tests that pin the single job's name, timeout budget and witness step move with the
      change, and every duration baseline the change moves is re-measured, not raised by hand.
- [ ] **Unchanged:** the real-tier and maui runs of `scripts/feature_check.py` keep the whole suite
      on one stack (sharding is a CI option, off by default); `Feature check (seeded)`; and
      `strict: true` on `main` (record 6244473689).

**Done when:** CI Gate requires the fan-in; on three consecutive green PR runs the sharded feature
check finishes, fan-in included, in about 20 minutes or less; the union of legs equals the reference
set at the same head; and the measured runs show no flaky leg the unsharded runs did not.
