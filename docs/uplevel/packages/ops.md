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
(UR-52); the operator runs its real-tier check.
It gates only ruling 127's 12 real-tier rows, not Phase 2's exit (UR-10, contract rule 5).

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
- [ ] **Step 2, if yes.** `feature_check.py --real --prod-shape` (the flag's name is the package's
      call) brings up that stack and runs the golden suite against it, using the Playwright
      container from ruling 143. The operator runs it nightly or on demand, not for every batch,
      on a test deployment (UR-133).
- [ ] **Unchanged:** the fake tier, the CI compose and the per-batch real tier (ruling 103) stay as
      they are.
- [ ] Ruling 127's 12 real-tier rows (F-102, F-115, F-117, F-164–F-167, F-169, F-174; F-176, F-178,
      F-182) get their witness from the `O2.5` run. If the spike says no, they fall back to ruling
      127's original route: ops adds what they need to the test deployment's compose.

**Done when:** the spike's answer (yes or no, the minimal override file, every blocker) is posted;
on yes, `feature_check.py --real --prod-shape` runs the golden suite on a production-shape test
deployment and the operator's run witnesses ruling 127's 12 rows; on no, the owner has ruled on the
blocker (ruling 144).

## Phase 3 — The tree matches the rulings

### O3.1 Prune `ai/` to what ships

**Flags:** none. **Depends on:** `R2`, `O2.3`.

- [ ] Declare the `ai/` entry points in `O2.3`'s file: the gateway's `main.py`, `export_all.sh`, and
      every build script a Dockerfile or workflow runs. Delete what does not ship (~27K of 35K
      lines at `d6ba78d5`, `00 §4.2`), with the tests that test only it.
- [ ] Strip the gateway image's unused dependencies (torch, transformers, ultralytics, open_clip,
      timm, onnxruntime). Confirm each by import trace; a build-time-only need moves to a build
      stage. **MEASURE** the image size before and after.
- [ ] Apply the `R2` ruling on OD-17: the Triton `reid`/`threat` models, `/enrich-lt`, and
      `ai-llm-vllm`. `R2a` ruled it (ruling 89): `ai-llm-vllm` is removed — the service, its `vllm`
      profile and every setting that names it; the re-ID half is `B2.2` (ruling 68); and Triton's
      role is UR-86.

**Done when:** `O2.3` reports no non-shipping module under `ai/` outside `keep.toml`, the gateway
image builds, and the golden paths stay green.

### O3.2 Compose base and overlays

**Flags:** none. **Depends on:** `R2`.

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

**Flags:** none. **Depends on:** `R2`.

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

**Flags:** none. **Depends on:** `R2`, `O2.3`, `F3.2`.

- [ ] A CI job fails when a new non-shipping Python module appears without a `keep.toml` entry
      (`O2.3`), and when `knip --production` finds a new unused frontend file or export (`F3.2`'s
      config).

**Done when:** a throwaway branch adding an unimported module fails the gate, and the PR shows that
run.

### O3.5 Weekly mutation scorer and history (`01` M2)

**Flags:** none. **Depends on:** `R2`, `O2.3`, `B2.1`.

Specified in [`01-mutation-policy.md`](../01-mutation-policy.md) §M2. Needs `O2.3` and `B2.1`.

### O3.6 PR mutation evidence tool (`01` M4)

**Flags:** `heavy`. **Depends on:** `R2`.

Specified in [`01-mutation-policy.md`](../01-mutation-policy.md) §M4. Phase 4's just-in-time
consolidation depends on it.

### O3.7 `scripts/` truth

**Flags:** none. **Depends on:** `R2`.

- [ ] Delete the scripts nothing references (~14 at `d6ba78d5`, `00 §7`) and the one-off
      investigation scripts. Scripts referenced only by `scripts/AGENTS.md`: **DECIDE** keep (a
      documented operator tool) or delete, one line each in the PR.
- [ ] Extend the ruff and mypy pre-commit scope to `scripts/`. **MEASURE** the violations; fix them.
- [ ] Wire into CI or delete the script tests no workflow runs (`test_gen_ai_contract.py`,
      `test_synthetic_media.py`, `test_vlm_probes.py`) and `tests/benchmark/`.

**Done when:** every file in `scripts/` is referenced by CI, a hook, `setup.py`, another script, or
the operator docs, and `scripts/` passes ruff in pre-commit.

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
#7052 (open, draft); item 8 of the same ruling merged as #6993.

- [ ] `backend/ai_contract/fake/app.py:115` becomes `except (binascii.Error, ValueError):`,
      behaviour-identical on 3.14 and parseable on older Pythons, so the reachability toolchain is
      no longer coupled to 3.14 by one line.

**Done when:** the line reads `except (binascii.Error, ValueError):` on `main` and the fake VLM's
tests pass (ruling 96).

### [r143] The golden stage runs inside the Playwright container

**Flags:** none. **Assigned:** `uplevel-ops-b`. **Depends on:** none named. **PR:** #7034 (open,
draft). The rule it builds is UR-131.

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

**Flags:** none. **Assigned:** `uplevel-ops-b`. **Depends on:** none named. **PR:** none yet. #7023
(O3.8) merged before ruling 141's changes were made (ruling 145).

- [ ] Remove `--durations=20` from the shared anti-rot pytest command in `.github/workflows/ci.yml`
      (the `collection-sanity` step).
- [ ] Set `@pytest.mark.timeout(30)` on both retired-paths tests in `scripts/test_retired_paths.py`
      (today `timeout(120)`), with their comment updated to the measured CI time.

**Done when** (rulings 141, 145): the shared step's argument list matches its shape before #7023,
both tests carry `timeout(30)`, and `Collection Sanity` passes at the PR's head.

### [r147] The real-sleep gate re-runs a breach before failing

**Flags:** none. **Assigned:** `uplevel-ops-b`. **Depends on:** none named. **PR:** none yet.
Builds UR-125 as the owner amended it (owner design session 2026-10-12, pass 2 Q9).

- [ ] When the Test Performance Audit finds a unit test over 4.0 s, it re-runs only that test, once,
      in the same job, and fails the run only if the re-run also breaches.
- [ ] A test that passes on its re-run is listed as a warning carrying both timings.
- [ ] No baseline file and no cross-run allowance are added; `SLOW_TEST_PATTERNS` stays the only
      exemption.

**Done when:** a unit test pins each case (breach then pass on re-run is a warning; breach twice
is red; a 1.5–4.0 s test is a warning only), and the audit passes on `main`'s current tests in CI.
