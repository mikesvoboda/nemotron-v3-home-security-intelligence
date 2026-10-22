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
(UR-52); the owner runs both runs from the maui login (rulings 256, 280).
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
      from ruling 143, on a test deployment (UR-133). Since ruling 280 the owner runs both from the
      maui login, item 2 first and then item 1, from the commands ops-a posts on #7037 (UR-140);
      the operator reads their output (ruling 185 item 3).
  - **Item 1, the `--real` run (the owner's on maui, after item 2; ruling 280).** `--real --prod-shape`, with no
    GPU consumer in the stack but the VLM: `ai-vlm` served by `agent-gpu`, the fake `ai-gateway`, no
    `dcgm-exporter`, and `backend`'s GPU reservation stripped. These are runtime transforms in
    `as_prod_shape_deployment`, not edits to the authored override (ruling 162 item 3), and the run
    record names each removed or stripped device. It witnesses F-102, F-115, F-117, F-164 to F-167,
    F-169, F-174, F-295 and F-296.
  - **Item 2, the fake-VLM run (owner, first; ruling 280).** `--prod-shape` with the fake VLM, from a host login on maui,
    keeping production's CDI devices for `ai-gateway`, `dcgm-exporter` and `backend`. It witnesses
    F-176, F-178 and F-182 and the CDI wiring (the stack boots with every device resolved), and its
    stop-test states the GPU memory the run takes beside production. `ai-vlm`'s own CDI line is the
    one GPU line neither run boots.
  - **Venue (ruling 280).** Both runs go from the owner's maui login, where a systemd user session
    delegates cgroups and runs Podman's health-check timers. The sandbox venue is closed for `O2.5`:
    rootless Podman there could not create a container cgroup through the Docker API, and with
    `cgroups = "disabled"` it refused runc. The owner runs item 2, then item 1 from ops-a's
    host-login command on #7037, which states how the VLM is served from the host (the `agent-gpu`
    lease and its `AGENT_GPU_TOKEN_FILE`), which of item 1's device strips still apply there, and
    the stop-test GPU reads.
  - **Item 2's pass (ruling 287).** One owner run on maui at a merged `main` pin that carries the
    venue fixes below, whose run record shows: smoke and `in_run` (isolation) `ok`; the
    F-176/F-178/F-182 browser test passed; `device_changes` naming only `ai-vlm`; `postflight` and
    `teardown` `ok` with `images_leaked: []`; and GPU memory before, at peak and after. Other golden
    legs may run, and their results are reported but do not gate item 2 (`[r287b]` makes them
    pass). The run records the venue requirements: minimal model assets (YOLO26m and OSNet-AIN
    weights, by sha256) in place of production's model zoo; the Triton 26.09 arm64 base by digest,
    because 26.01's CUDA code fails on the GB300; FP32 re-ID, because TensorRT 11 has no `--fp16`;
    the user-level `crun` and NVIDIA CDI runtime; `keep-id` for `foscam-init`; and the busybox HTTP
    health checks for the two exporters. `dcgm-exporter` runs rootful outside this stack in
    production (the `gpu-rootful` profile), so a rootless run cannot witness its device line.
  - **F-182's rows (ruling 285).** No API path writes a GPU config version since #7309, so item 2's
    F-182 step seeds two rows in `gpu_configuration_versions` directly in the run's database,
    exercises list, compare and the JSON and YAML export, and restores the table. The F-176 and
    F-178 steps are read-only, and no step calls a write endpoint.
- [ ] **Ruling 162's three answers.** Resource limits stay where cgroup controllers are delegated
      and are stripped otherwise, with `limits: not applied (no cgroup delegation)` in the run
      record. The engine socket, the 7 pinned `container_name`s and the host ports and paths are
      handled by the runner's own test override, never by editing `docker-compose.prod.yml`; a
      CPU-only CI test renders `docker compose config` for both and fails on any difference not
      listed.
- [ ] **Unchanged:** the fake tier, the CI compose and the per-batch real tier (ruling 103) stay as
      they are.
- [ ] **The venue fixes (ruling 287 item 3), ops-a's, ahead of `[r282]`.** From the owner's maui
      handoff (`scratch-patch.diff`, its text `code-review.diff`, cut against `91bf685eb`), only
      what item 2's pass needs: the harness and venue settings, opt-in under `--prod-shape` (the
      handoff's items 1-7, 11, 12, 15, and whichever of 8 or 14 smoke needs); the GPU spec (item
      10); and a harness option that limits the Playwright leg to named specs under
      `--prod-shape`. Defaults, `docker-compose.prod.yml` and CI's behaviour stay unchanged, and a
      test shows the non-prod-shape commands are unchanged. The review includes a security pass
      over item 12 (the isolation check under `--prod-shape`) and item 15 (`ADMIN_ENABLED` in the
      venue's allow-list). If item 8 changes CI's fake-tier inputs, the PR says how the
      **Unchanged** box above still holds, or keeps the photographs to prod-shape only. Not in
      it: items 9 and 13 and item 19 and the null `risk_score` (`[r285]`, backend), and items
      16-18 (`[r287b]`). Two or three PRs if the diff calls for it, one at a time (UR-52).
- [ ] Ruling 127's 12 real-tier rows (F-102, F-115, F-117, F-164–F-167, F-169, F-174; F-176, F-178,
      F-182), F-295 (ruling 219) and F-296 (ruling 222) get their witness from `O2.5`'s two runs. If
      the spike says no, they fall back to ruling 127's original route: ops adds what they need to
      the test deployment's compose.

**Done when:** the spike's answer (yes or no, the minimal override file, every blocker) is posted;
on yes, both Step 2 runs have posted: item 1 witnesses its 11 rows and item 2 its 3 rows and the
CDI wiring, as item 2's pass above sets it, together ruling 127's 12 rows, F-295 and F-296
(rulings 185, 188, 219, 222, 256, 280, 287); on no, the owner has ruled on the
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
**PR:** #7324. (rulings 241, 289)

- [x] A CI job fails when a new non-shipping Python module appears without a `keep.toml` entry
      (`O2.3`), and when `knip --production` finds a new unused frontend file or export (`F3.2`'s
      config). New means not in the baseline `F3.2`'s PR records at its merge (ruling 257).

**Done when:** a throwaway branch adding an unimported module fails the gate, and the PR shows that
run.

### O3.5 Weekly mutation scorer and history (`01` M2)

**Flags:** none. **Depends on:** `R2`, `O2.3`, `B2.1`.
**PR:** #7317. (rulings 241, 289)

Specified in [`01-mutation-policy.md`](../01-mutation-policy.md) §M2. Needs `O2.3` and `B2.1`.

### O3.6 PR mutation evidence tool (`01` M4)

**Flags:** `heavy`. **Assigned:** heavy-b (ruling 258). **Depends on:** `R2`.
**PR:** #7251

Specified in [`01-mutation-policy.md`](../01-mutation-policy.md) §M4. Phase 4's just-in-time
consolidation depends on it.

### O3.7 `scripts/` truth

**Flags:** none. **Depends on:** `R2`. **Assigned:** heavy-b, ahead of `O3.2` and `B2.3`; it moved
from ops-b's queue (ruling 298, record 6321095724).
**PR:** #7329. (rulings 241, 298)

Where it meets open PRs (ruling 298 item 2): box 2's ruff and mypy fixes leave alone any file an
open PR edits under `scripts/` and fix it after that PR merges; box 1's deletions do not touch such
a file; and the PR body names each file it defers, so the Done when is met at the ready head.
Box 1's **DECIDE** for `scripts/ai-quality-analysis.py` is answered: keep it, a documented operator
tool (`docs/reference/backend-entry-points.md:1471`) whose import #7319's `keep.toml` entry keeps
(ruling 298 item 3).

- [x] Delete the scripts nothing references (~14 at `d6ba78d5`, `00 §7`) and the one-off
      investigation scripts. Scripts referenced only by `scripts/AGENTS.md`: **DECIDE** keep (a
      documented operator tool) or delete, one line each in the PR.
- [x] Extend the ruff and mypy pre-commit scope to `scripts/`. **MEASURE** the violations; fix them.
- [x] Wire into CI or delete the script tests no workflow runs (`test_gen_ai_contract.py`,
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

**Flags:** none. **Depends on:** Phase 1 done. **PR:** #7307.

- [x] Delete the 28 PNGs nothing references (15.4 MB).
- [x] **MEASURE** re-encoding the 1408×768 renders (WebP or JPEG) on a sample. If the owner accepts
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
none. **PR:** #7231. (ruling 195)

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
**Depends on:** none. **PR:** #7268. (ruling 239, record 6217014151; ruling 245, record 6223117374)

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
      verbatim on the PR. Ruling 306 (record 6323748868) has the operator run it now on its
      agent-gpu venue, as run 188.17 did, at `main`'s head (which carries #7238), on the same 36
      crops; it posts the table and then the parity mode's `RESULT:` line on #7238, and links both
      from #7002.
- [x] If a plan stage still reads under 0.999, post the measured table and its reading on the PR;
      the next step goes to the owner through the coordinator's status comment before any further
      spend. Run 188.18 read 0.346321 at its FP32 plan stage, against 1.000000 under ONNX Runtime
      on CPU (`6327606735`), and ruling 312 (record 6329693164) took the next step: `[r312a]`.
- [ ] The change ships with a CPU-only CI test that pins it.

**Done when:** `[r157]`'s Done when, read at this package's head: O2.4's command (#6970's) prints
`RESULT: PASS`, posted on the PR, and the CPU-only test above is green in CI. The 0.999 gate stays
(ruling 68), `REID_BACKEND` stays `local` in this package (`[r306a]` flips it on `RESULT: PASS`,
ruling 306), and serving re-ID through ONNX Runtime instead of TensorRT plans is not authorised.

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
**PR:** #7305. (ruling 172; issue #7102)

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
**PR:** #7295. (rulings 184 and 201, records 6177514438 and 6198825479; the owner's answer,
comment 6282692806, 2026-10-20T03:32Z)

Ruling 184's commit renamed the heavy rows in `scripts/uplevel/sandboxes.toml`. The owner starts
both under the pi harness; asked for the exact line (ruling 201 item 1), the owner confirmed
`agent-dgx <name> pi --split` word for word on the PR. The form is not `agent-dgx run`-shaped
(session name before the harness, no `--agent` flag), so the launcher refuses the rows and names
the hand-start line - the refusal is the settled state, not a waiting one.

- [x] The launcher's line for `uplevel-heavy-a` and `uplevel-heavy-b` is the owner's pi start line.
      Take its exact form from `agent-dgx help` output the owner posts from maui, or from a line
      the owner pastes on the PR; the launcher never invents a flag (`history/packages-done.md`
      §O0.1). - the owner answered (`agent-dgx <name> pi --split`, word for word, comment
      6282692806): the form is the hand-start line each row now carries; the launcher names it in
      the refusal and never prints a run line for the rows, per the box below (ops-a's call, PR
      comment 6282901290).
- [x] If that form cannot be written as `agent-dgx run` arguments, the launcher refuses the two
      rows, naming the hand-start line, and prints no wrong line. - it cannot (the session name
      precedes the harness, no `--agent` flag); `hand_start` on each row, `run_args_for` raises
      naming `agent-dgx <name> pi --split`, and `up` refuses the phase before any change while
      such a row is MISSING (commit `efeaf55ff`).
- [x] `backend/tests/unit/scripts/test_uplevel_launch.py`: the heavy rows give the pi line or the
      refusal, and no other row's line changes. -
      `test_the_rosters_heavy_rows_refuse_naming_the_hand_start_line`,
      `test_a_hand_start_row_refuses_before_any_change`,
      `test_no_other_rows_line_changes_for_hand_start` (108 passed).

**Done when:** the launcher test passes in CI at a ready head, and `sandboxes.toml`'s comment no
longer says the launcher does not print the form. - the comment now says why the launcher does
not print the form (the form is not `run`-shaped), and the CI half needs the PR marked ready.

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
  - Build fix (af50878ec, from the first ready run's two failures, run 39209710736): the shard
    jobs' setup-uv carries `ignore-nothing-to-cache: true` — shards 2–4 never invoke uv after the
    backend-once change, so the action's post step errored on a cache dir that never materialized;
    and the fan-in's `--list` derivation exports an absolute `FEATURE_CHECK_SCENARIOS` — the
    repo-relative value died as `frontend/backend/...` under `cd frontend` and
    event-detail-modal's module-scope constants crashed collection past their own test.skip guard.
    Both pins carry teeth (test_check_gate_reachability.py).
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
check finishes, fan-in included, in at most 25 minutes, measured from the CI run's start to the
fan-in job's end (owner answer 6266229360, Q1); the fan-in's code checks set equality both ways —
it fails on a reference leg missing from the union, a leg of the union not in the reference set,
and one leg running in two shards, any outcome (owner answer 6266229360, Q2); and the measured
runs show no flaky leg the unsharded runs did not.

### [r269] `lane_tick` offers the next package while a PR waits its merge turn

**Flags:** none. **Assigned:** `uplevel-ops-b`, first on its queue (ruling 269).
**Depends on:** none. **PR:** #7290. (ruling 269, record 6275028285)

UR-52 lets an agent whose open PR is waiting its merge turn claim its next package, up to two open
packages (ruling 269). `scripts/uplevel/lane_tick.py` still prints no claimable package while the
lane holds any open PR, so agents read their queues by hand.

- [ ] `lane_tick.py` offers the next claimable package in the lane's own queue when every open PR
      the lane holds waits its turn by UR-52's test and the lane holds fewer than two. The test:
      approving review at the head or a UR-106 carry, owner approval for an owner-tier PR,
      `CI Gate` passed or last run cancelled, not a draft, and nothing the author's to do (no open
      review finding, no conflict, no unanswered owner question).
- [ ] Tests pin each condition and the two-package cap.

**Done when:** the tests pass in CI at a ready head.

### [r270] `coordinator_snapshot.py`'s merge legs read for strict mode

**Flags:** none. **Assigned:** `uplevel-ops-b`, after `[r269]` (ruling 270).
**Depends on:** #7268 (`[r239]`) merged. **PR:** #7323. (ruling 270, record 6276943371)

`main` keeps `strict: true` and the coordinator updates one PR at a time (UR-102, ruling 268), and
"Merging a PR" reads "behind" from §3's `base=`. `scripts/uplevel/coordinator_snapshot.py`'s §4
still prints UR-102's three no-update-branch legs and a "merge without update-branch" verdict, a
path strict mode does not have (#7285's round-1 review, note 6).

- [ ] Drop the "merge without update-branch" verdict and the labels naming UR-102's three legs (the
      docstring, `MAX_MERGES_BEHIND`, §4's header and lines).
- [ ] For each non-draft PR, print whether it is behind `main` (its `base=` is not `main`'s tip)
      and whether it shows the in-flight sign of `roles/coordinator.md` "Merging a PR" step 1
      (`base=` at the tip, gate `absent`, `QUEUED` or `IN_PROGRESS`, and `carry=yes`).
- [ ] `scripts/test_coordinator_snapshot.py` pins both reads; other sections are unchanged.

**Done when:** the tests pass in CI at a ready head, and a live snapshot run posted on the PR shows
the behind and in-flight reads for the open PRs then.

### [r272] The queue-update workflow updates the next queued PR when `main` moves

**Flags:** `owner`. **Assigned:** `uplevel-ops-b`, after `[r269]` (ruling 272).
**Depends on:** none. **PR:** #7301. (ruling 272, record 6282551725; items 3 and 5 amended by the
owner's approval 6290019383; ruling 288 item 1, record 6303093964)

Under ruling 268 each merge waited for the coordinator's 30-minute tick to update the next PR. A
workflow updates the head of the coordinator's queue line within minutes of `main` moving. It uses
the owner's token, because an update made with the built-in `GITHUB_TOKEN` starts no CI on the PR
(UR-104: GitHub's merge queue is unavailable on this repository).

- [x] `.github/workflows/queue-update.yml`, `scripts/uplevel/queue_update.py` and its tests.
      Triggers: a push to `main`, `workflow_run` for `CI` (completed), every 15 minutes, and
      `workflow_dispatch`; a concurrency group runs one fire at a time. One fire, in ruling 272 item
      3's steps: (1) reads the queue line, `main`'s tip and the newest completed `CI` run on
      `main`; (2) does nothing while a listed PR is open, not behind `main` and its `CI Gate` has not
      failed; (3) acts only on a `!` entry while that `CI` run failed; (4) skips an entry that is
      merged, closed or a draft, or whose UR-106 own-diff hash moved; (5) updates the first
      remaining entry that is behind `main`, and only that one, with `expected_head_sha`, then arms
      auto-merge; (6) disarms auto-merge if the own-diff hash changed across its update; (7)
      comments once on the PR it updated with both heads, `main`'s tip, both hashes and the run
      link. Every fire writes a job summary.
- [x] Credentials, as approval 6290019383 amended item 3: the job's `GITHUB_TOKEN` has
      `contents: read` and `issues: write`, the write for the PR comment only. `QUEUE_UPDATE_TOKEN`
      (a fine-grained token for this repository, Contents and Pull requests read and write, set by
      the owner) is used only for `update-branch` and arming and disarming auto-merge, which uses
      `MERGE` (UR-23). No PR code is checked out or run while the token is in scope.
- [ ] The red-`main` read works: the fire reads the `CI` workflow's own runs
      (`actions/workflows/ci.yml/runs`), not `actions/runs?workflow=CI`, which the API does not
      filter, so it read another workflow's run and the filter above never fired. A red-first test
      makes another workflow's run the newest on `main` (ruling 288 item 1; #7312 carries it).
- [ ] Switch-over (item 5 as amended): the merge's own push fired the workflow live. The owner
      partner posts the switch-over pointer once a fire has made a correct update, and not before
      #7312 merges (ruling 288 item 1). From that pointer, UR-102's update clause and
      `roles/coordinator.md` "Merging a PR" step 2 apply.

**Done when:** tests over recorded API payloads cover each step, an empty or missing queue line and
a conflict; `actionlint` is clean; a dry run against the live repo, reading the real queue line, is
quoted in the PR; and the UR-89 review includes a security pass over the workflow (where the token
is exposed, the triggers, and that no PR code runs while the secret is in scope).
(ticked under ruling 283: #7301 merged 2026-10-20T19:47:02Z as `91bf685eb`; review `6296041784`
approved `1dd233b5a`, its item 4 the security pass; audit `6301271763`)

### [r273] One PR for every open Dependabot PR

**Flags:** none. **Assigned:** `uplevel-heavy-b`, first on its queue (ruling 273).
**Depends on:** none. **PR:** #7297. (ruling 273, record 6282749517)

Five grouped Dependabot PRs would have cost five merge cycles under ruling 268, and the three npm
groups rewrite the same lockfile. Ruling 284 repeats the method every Monday
(`roles/coordinator.md`, "Assigning a package").

- [x] One branch and one PR carrying every Dependabot PR open at the start. npm: apply the
      `frontend/package.json` changes and regenerate `frontend/package-lock.json` once. Python:
      take `requirements-base.txt` and `uv.lock`, re-locking at the same versions if `main` moved.
      Actions: take the pin bumps as they are and compare `actionlint` with `main`'s; a Dependabot
      pin bump in `ci.yml`'s shared jobs is outside UR-121.
- [x] Majors that `.github/dependabot.yml` ignores stay held (ruling 160). Only what a bump strictly
      needs is fixed, named per group; anything bigger drops that group, and a group that breaks CI
      is dropped with its failing job and log lines on its own PR, which stays open.
- [x] When the combined `CI Gate` first passes, each folded PR is closed with "Superseded by #N,
      which carries this group's updates (ruling 273)", and no `@dependabot` command.

**Done when:** `CI Gate` is green at a ready head, `build-base-image.yml` is green on the PR, the
body lists each folded PR and each dropped group with the reason, and the UR-89 review approves.
(ticked under ruling 283: #7297 merged 2026-10-20T04:40:01Z as `25f556ae4`; review `6283266920`
approved `9c0e35136`; "Build and Publish Base Image" and `CI` passed at that head; #7274, #7275,
#7276, #7278 and #7284 closed at 04:39:56Z)

### [r274] The harness boots with `up --no-build` after a prebuild

**Flags:** none. **Assigned:** `uplevel-ops-a`, beside #7295, a one-off UR-52 exception counted
toward ruling 269's two (ruling 274). **Depends on:** none. **PR:** #7298. (ruling 274, record
6282871050; item 1 amended by record 6290084892)

`docker-compose.fake-ai.yml:34` sets `pull_policy: build`, so `up` rebuilt the fake gateway after
`prebuild_images` had built it, through compose's BuildKit path, which the rootless sandbox engine
cannot run.

- [x] `Run.up` passes `--no-build` exactly when `prebuild_images` ran in this run (the prod-shape
      modes); fake mode's `up` is unchanged. A test in
      `backend/tests/unit/scripts/test_feature_check.py` pins each branch (amendment 6290084892).
- [x] `prebuild_images`' docstring says why: `pull_policy: build` would otherwise rebuild at `up`.
      `docker-compose.fake-ai.yml` is unchanged.
- [x] The PR says whether CI's fake-AI feature-check legs go through `Run.up`, and whether they
      rebuilt `hsi-fake-ai` at `up` before this change, quoting a job log line.

**Done when:** `CI Gate` is green at a ready head and the UR-89 review approves.
(ticked under ruling 283: #7298 merged 2026-10-20T13:03:38Z as `3f85774e1`; review `6290671826`;
audit `6291719540`)

### [r278] One subset-carry decision for the snapshot and the queue workflow

**Flags:** none. **Assigned:** `uplevel-ops-b`, after `[r270]` (ruling 278).
**Depends on:** none. **PR:** #7327. (ruling 278, record 6293203635)

UR-106's carry also holds when an update only drops lines that `main` now holds identically (a
subset carry, ruling 278). The snapshot and `queue_update.py` still compare hashes, so a shared
table row that `main` absorbs resets an approval (#7301 lost one this way, `6290679665`).

- [ ] `coordinator_snapshot.py` has one function that decides a carry by UR-106's subset rule and
      returns yes, no or unknown. §3's `carry=` and the §7 and §8 verdicts use it, and §3 prints
      `carry=yes (subset: <n> lines main holds)` in the subset case.
- [ ] `queue_update.py`'s skip and disarm steps use the same function instead of hash equality.
- [ ] Tests cover an exact carry; a subset carry where `main` holds the dropped pair; a dropped
      line `main` does not hold (no carry); a line in the new diff that is not in the approved one
      (no carry); an author commit (no carry); and a failed read (unknown, never yes).

**Done when:** the tests pass in CI at a ready head and the UR-89 review approves.

### [r290] The snapshot reads package balance, and `lane_tick` offers a multi-PR package's open box

**Flags:** none. **Assigned:** `uplevel-ops-b`, after `[r278]` (both edit
`coordinator_snapshot.py`), ahead of `O3.7` (ruling 290). **Depends on:** none. **PR:** #7330.
(ruling 290, record 6303479997)

On 2026-10-20 three agents sat idle while ops-b held three Phase 3 packages with dependencies met,
until the owner asked for ruling 289's rebalance. One idle queue was a parser gap: `next_claimable`
offers only a `none yet` block, so B3.3's open fourth box (ruling 254) was never offered because
its block names the merged #7244. The coordinator detects and proposes; it never moves a package
(`roles/coordinator.md`, "The status comment").

- [ ] **The balance section.** `coordinator_snapshot.py` gains a section. For each roster agent
      that is not paused, it prints the agent's open package PRs; its claimable queue entries (the
      blocks `next_claimable` would offer in queue order, plus the open multi-PR packages below),
      each with its **Depends on:** read as met, unmet or unread, where a free-text dependency it
      cannot resolve reads unread, never met; and whether it is idle (no open package PR, and a
      heartbeat state of idle). It flags an imbalance when an idle agent has nothing claimable and
      another holds two or more claimable entries whose dependencies read met, and prints one
      candidate move that keeps UR-24 (no `heavy` package to a fast agent) and the cells' file areas
      (`roles/lane.md`), or names a heavy agent as the receiver.
- [ ] **The multi-PR offer.** `lane_tick.py`'s `next_claimable` also offers a package on my queue
      whose README status row reads `in progress` (UR-144), whose block has an unticked box, and
      which no open PR of mine titles; the digest names the box (UR-47, ruling 290).
- [ ] **Tests:** an idle agent with nothing claimable beside a backlogged one (flags); two busy
      agents (no flag); an unread dependency (never met); a `heavy` package never proposed to a fast
      agent; B3.3's shape (merged PR, `in progress`, an open box) is offered; a merged single-PR block
      with an unticked post-merge box is not (ruling 283).

**Done when:** the tests pass in CI at a ready head, and a live snapshot run posted on the PR shows
the balance section for the agents then.

### [r279] Three flaky CI checks made deterministic

**Flags:** none. **Assigned:** `uplevel-heavy-b`, first on its queue (ruling 279).
**Depends on:** none. **PR:** #7308. (ruling 279, record 6293490330)

Under ruling 268 a flaky failure at the head of the queue costs a whole merge cycle. Test
Performance Audit, Merge Integration Coverage and Feature check (fake AI) are the three ruling 279
named; two of them cost #7281 about 75 minutes on 10-19.

- [x] Every failure of the three checks since 2026-10-18 14:00Z is classified in the PR body as
      flaky (the same head, or the same bytes of every file the job reads, passed elsewhere) or real,
      with its run, job and verdict, and for each flaky one the test or step that varied.
- [x] The flaky causes are fixed at the root. Nothing is deleted, skipped, `xfail`ed, retried to
      green or loosened by raising a threshold or baseline (UR-112);
      `scripts/check-test-duration-budget.py` was not edited while `[r172]` (#7305) was open; edits
      to `ci.yml`'s shared jobs stay within UR-121.
- [x] Any other job found flaky is reported, not fixed, for a later ruling.

**Done when:** `CI Gate` is green at a ready head; each fixed flake shows evidence that it no longer
varies (the test repeated at least 20 times with counts, or a before-and-after comparison on the
same tree); and the UR-89 review approves.
(ticked under ruling 283: #7308 merged 2026-10-20T17:07:38Z as `3dff11402`; review `6295908274`
approved `a1cbf6986`; audit `6297441697`)

### [r282] The golden-test shards balanced by measured duration

**Flags:** none. **Assigned:** `uplevel-ops-a`, after `O2.5`'s venue fixes (rulings 282 and 287).
**Depends on:** none. **PR:** #7310. (ruling 282, record 6294042743)

In median run 39419991445 (19.4 min), `Feature check (fake AI) (4-of-4)` ran 18.1 min while
shards 1 and 3 took 13.9 and 14.8: `[r264]` splits with Playwright's `--shard=i/N`, which balances
test counts, not durations, and shard 1 also runs the backend golden leg.

- [x] **Measure:** per-test durations from the golden junit files of at least five recent green
      runs, plus each shard's fixed cost (stack boot and teardown) and shard 1's backend leg,
      tabulated in the PR body with each shard's time and the long pole.
- [x] **Rebalance:** assign tests to shards by measured duration (for example, per-shard lists
      generated from the junit data and checked in with the script that regenerates them),
      counting shard 1's backend leg, or change the shard count if the measured fixed cost shows a
      5th or 6th shard lowers the slowest one. No test is dropped, skipped or deduplicated across
      shards, and a test pins that the shards' union is exactly the suite. Edits stay inside the
      Feature check job and the harness (UR-121), and `[r264]`'s backend-on-shard-1 rule stays
      unless the measurements argue otherwise, which the PR then says.
- [x] `[r279]` changed tests in the same suite. `[r282]` changes how tests are assigned to shards,
      not the tests themselves, and where the two PRs' files meet, this PR says so.

**Done when:** `CI Gate` is green at a ready head; the regeneration script runs in CI or the docs
say when to rerun it; and the UR-89 review approves. Ruling 297 (record 6315692389) amended the two
measurement clauses, which asked the median of at least three full runs at the PR's head for a
critical path of 15 min or less and a spread of 2 min or less between the slowest and fastest shard.
They close on #7310's measured gain (`6312968792`, at `a4cb3784a`), and the 15-minute target moved
to `[r297]`:

- [x] The median critical path fell from 18.92 to 17.63 min (ruling 297).
- [x] The shard spread fell from about 6.0 to 2.78 min (ruling 297).

### [r291] The gate's dependency audit fails a change only on a finding it adds

**Flags:** `owner` (it changes what `CI Gate (Required Checks)` runs, UR-119, and a security check,
UR-98). **Assigned:** `uplevel-ops-a`, after `[r282]`, behind `O2.5`'s venue fixes (rulings 287 and
291). **Depends on:** none. **PR:** #7328. (ruling 291, record 6304527940)

On 2026-10-20 three advisories published against unchanged code (certifi, Pillow, markdown-it) kept
`main` red from 19:47Z until #7314 merged at 23:54Z. Each fix was a plain lockfile bump, yet the
fixes blocked each other, because one audit job covers both ecosystems, and 11 `CI` runs failed on
the audit alone. UR-185 treats such an advisory as UR-116 treats a red nightly: raised and routed,
without freezing the queue.

- [x] **The gate mode.** On a PR, the gate's audit leg audits both the tree CI tests and the PR's
      base commit in the same job, and fails only on an unexempted finding at the head that is not
      an unexempted finding at the base, keyed by advisory id (with aliases) and package. On a push
      to `main` the base is the previous `main` commit. The two registries
      (`.pip-audit-exemptions.json`, `frontend/.npm-audit-exemptions.json`) stay the one allowlist;
      an entry the change adds or edits must pass today's registry rules; removing an exemption
      whose finding remains counts as adding that finding; an audit error on either side fails
      closed. A change that touches none of `pyproject.toml`, `uv.lock`, `frontend/package.json`,
      `frontend/package-lock.json` and the two registries may skip both audits.
- [x] **The full-lockfile mode** runs today's checks unchanged on every push to `main`, daily (the
      Monday cron becomes daily) and on `workflow_dispatch`, as a check `CI Gate (Required Checks)`
      does not read (UR-119). Both modes live in `dependency-audit.yml` and the two checkers
      (OB.2), and `ci.yml`'s call job selects the gate mode (UR-122).
- [x] **Tests, red first (UR-69),** on recorded audit JSON for each checker: a finding shared by
      base and head passes the gate; a head that adds a vulnerable package fails; a head that
      removes an exemption whose finding remains fails; a head that adds an exemption with a past or
      missing REVIEW BY fails; a base exemption past its REVIEW BY that the change does not touch
      passes the gate and fails the full-lockfile mode; an audit error on either side fails; and the
      full-lockfile mode gives today's results (today's checker tests pass unchanged).
- [x] **Proof in the PR body,** with commands and output against live advisory data: the gate mode
      with base `fadeb1992` (red on markdown-it before #7314) and a head of `fadeb1992` plus a
      doc-only commit passes; the full-lockfile mode at `fadeb1992` fails on markdown-it; and a
      `workflow_dispatch` run of the full-lockfile mode on the PR branch is green.

**Done when:** the tests pass in CI at a ready head, the PR body shows the three proofs, and the
gate reads only the gate mode (`ci-gate`'s needs and `check_job` lines). The owner partner approves
it under ruling 281 once its UR-89 review, with a security pass, approves and its gate is green.

Notes for the lane, from the plan PR's round-4 and round-5 reviews (#7316):

- **The full-lockfile run is `dependency-audit.yml`'s own run,** on its own `push` trigger for
  `main`, not a job in `CI`. A red job in `CI` fails the whole `CI` run, which
  `coordinator_snapshot.py` and, since #7312, `queue_update.py` read as red `main`: the queue freeze
  UR-185 rules out. Update the workflow's header comment that says it has no standalone push
  trigger.
- **The skip still runs both audits** when the change edits `dependency-audit.yml`, `ci.yml` or
  either checker, so this package's own PR, and later edits to the audit, are audited.
- **The gate mode's base** is the tested merge tree's first parent; `pull_request.base.sha` can lag
  it.
- **The npm checker runs `npm audit` itself,** so its tests feed it recorded JSON through a fake
  `npm` on `PATH`, as today's tests already do (`scripts/test_check_npm_audit_exemptions.py:79-83`,
  `:100-101`).
- **The doc-only proof would take the skip,** so run the gate-mode checker directly on both trees
  for it.

### [r294] Trivy's vulnerability scans fail a change only on a finding it adds

**Flags:** `owner` (it changes what `CI Gate (Required Checks)` runs, UR-119, and a security check,
UR-98). **Assigned:** `uplevel-ops-a`, after `[r291]` (ruling 294). **Depends on:** none.
**PR:** none yet. (ruling 294, record 6307203645)

`main` went red at 01:36Z on 2026-10-21 on `Security - Trivy / Scan Backend Image`: `certifi`
2026.6.17 with GHSA-6q48-6c7w-9gw2 (CRITICAL), in pip's own bundle in the base image (raise
`6306177116`; rulings 293 and 295). The same scan passed at `ffeb90f36` (00:35Z), so the advisory
data changed, not the code: `[r291]`'s failure class. `trivy.yml` runs inside
`CI Gate (Required Checks)` (`ci.yml`'s `security-trivy` job) with two vulnerability scans that fail
on any CRITICAL or HIGH finding not in `.trivyignore`: `Filesystem Vulnerability Scan`, over the
repository's lockfiles and manifests, and `Scan Backend Image`, over the image CI builds. This
package gives them `[r291]`'s design, and follows it where the two meet: the coordinator's read and
the routing (UR-185). Until it merges, Trivy stays in the gate as it is, and a Trivy finding turns
`main` red.

- [ ] **The gate mode** for both vulnerability scans in `trivy.yml`, with `ci.yml`'s
      `security-trivy` call job selecting it (UR-122: ruling 294 orders the edit). The head and the
      base are scanned in the same job, against the same Trivy database; for the image, the base
      side is the base commit's backend image (built in the job, or taken from where `main`
      publishes it) or its SBOM. A finding is keyed by its vulnerability id and package.
      `.trivyignore` stays the one allowlist: an entry a change adds or edits must pass today's
      rules (`scripts/check-trivyignore-expiry.sh`), and removing an entry whose finding remains
      counts as adding that finding. A scan error on either side fails closed. The filesystem scan
      may skip when `[r291]`'s skip applies and the change does not touch `.trivyignore`; the image
      scan always runs.
- [ ] **The full scans:** today's two scans run unchanged, with `check-trivyignore-expiry.sh`'s
      dates, as `trivy.yml`'s own run on every push to `main`, daily (the Monday cron becomes daily)
      and on `workflow_dispatch`. They are not a job in `CI`, because a red job in `CI` reads as red
      `main` (`[r291]`'s notes), and `CI Gate (Required Checks)` does not read them (UR-119).
      `Config/IaC Security Scan` is unchanged: it checks the repository's own configuration.
- [ ] **Tests, red first (UR-69),** on recorded Trivy JSON: a finding in both base and head passes
      the gate (one case built from run `39528289094`'s `certifi` finding); a head-only finding
      fails; removing a `.trivyignore` entry whose finding remains fails; an added entry with a past
      or missing review date fails; a scan error on either side fails; and the full mode gives
      today's results.
- [ ] **Proof in the PR body:** one CI run of the gate mode on this PR and one `workflow_dispatch`
      run of the full scans on its branch, both green, with the run links.

**Done when:** the tests pass in CI at a ready head, the PR body shows the proof, and the gate reads
only the gate mode (`ci-gate`'s needs and `check_job` lines). The owner partner approves it under
ruling 281 once its UR-89 review, with a security pass, approves and its gate is green.

Notes for the lane:

- **The full scans bring back a standalone `trivy.yml` run.** Its header (`trivy.yml:3-34`) says
  the push and PR triggers were replaced by the call from `ci.yml`, that the weekly Monday scan
  catches drift, that the standalone triggers were deleted, and it bans a root `concurrency:` block,
  because the called run would take the caller's group. Schedule and dispatch already run
  standalone, so what comes back is the `push` trigger. Update the whole header, and keep the called
  path free of a root `concurrency:` block.
- **The skip still scans edits to the scan itself:** a change that edits `trivy.yml`, or the
  gate-mode script if the gate mode lives in one, still runs the filesystem scan, as `[r291]`'s skip
  still audits edits to the audit, so this package's own PR is scanned.

### [r297] The per-shard fixed cost cut toward a 15-minute CI

**Flags:** none: it changes how fast the Feature check runs, not what `CI Gate` runs (UR-119).
**Assigned:** `uplevel-ops-a`, after `[r294]` (ruling 297). **Depends on:** #7310 (`[r282]`) merged:
it builds on its manifest. **PR:** none yet. (ruling 297, record 6315692389)

At `a4cb3784a`, #7310's three full green runs gave a median critical path of 17.63 min (18.92 before
`[r282]`) and a shard spread of 2.78 min (about 6 on the count split). Per-shard Playwright time
agrees within 0.20 s, so the pack is balanced; about 626 s of a ~1,027 s shard wall is each shard's
fixed cost, mainly booting its own stack. Rebalancing cannot reduce that, and a 5th shard adds about
400 s of fixed cost to save about 124 s of tests. Ruling 297 closed `[r282]` on that gain and moved
the 15-minute target here.

- [ ] **Measure:** for at least three recent green runs, split each shard's fixed cost into image
      pull or build, stack boot and health waits, seed, and teardown. Tabulate the shares in the PR
      body.
- [ ] **Cut:** take the largest shares down. For example, build or pull the images once for all
      shards, boot services in parallel, shorten health-check waits that only idle, or share what
      one shard's start already paid for. No test is dropped, skipped or deduplicated, and each
      shard keeps its own isolated stack unless the PR shows a shared one keeps isolation (UR-134).
      Edits stay inside the Feature check jobs and the harness (UR-121).

**Done when:** the median critical path of at least three full green runs at the ready head is 15
min or less, the table shows each share before and after, and the UR-89 review approves.

### [r287b] The whole golden suite passes in the production-shaped run

**Flags:** none. **Assigned:** none; the owner assigns it when Phase 3's queue allows, and the
coordinator does not (ruling 287). **Depends on:** none named. **PR:** none yet. (ruling 287, record 6302941592)

The owner's maui discovery for `O2.5` item 2 (attempt 8, `hsi-check-20261020205509-0c0734`, on
`main` `91bf685eb` plus local fixes) passed the backend golden leg 27 of 27, and Playwright passed
210, failed 19 and skipped 16 in production's compose shape. Item 2 passes on its own three rows
(ruling 287); the rest of the suite is this package.

- [ ] The whole golden suite passes in a `--prod-shape` run on maui. It starts from attempts 8 and 9
      of that discovery (the handoff's `ATTEMPT9-PARTIAL-FAILURES.md` and `report-changes.md` items
      16-18), and from its finding that some CI golden specs pin behaviour that only CI's read-only
      directories cause, such as a thumbnail that cannot be written.

**Done when:** a `--prod-shape` run on maui at a merged pin has every golden leg passed.

### [r307a] Face models in Triton

**Flags:** `heavy`; label `cell:heavy-b`. **Assigned:** heavy-b, after `O3.7`, ahead of `B2.3` and
`O3.2` (ruling 307). Where it edits `ai/gateway/`, UR-9 applies. **Depends on:** O2.4's pass (ruling
306 item 1), which proves the TensorRT parity path: `[r252]`'s run was spent without one, and
`[r312a]`'s second run, reading every plan stage at or above 0.999 on all 36 crops on the image
`main` serves, is O2.4's evidence (ruling 312 point 4).
**PR:** none yet. (ruling 307, record 6323846997)

Every small model the product runs on the GPU is served by Triton (UR-86). The face leg runs on the
CPU today by an earlier choice (`backend/services/face_recognizer_loader.py:19`, `:152`); `[r307b]`
moves the backend to the routes this package adds.

- [ ] Serve SCRFD (`det_10g.onnx`) and ArcFace (`w600k_r50.onnx`), the same pinned files, in Triton
      as TensorRT plans built for the serving GPU, behind gateway routes as `reid` is.
- [ ] Parity against the CPU ONNX path on a fixed face set, stage by stage as `[r157]`'s runner
      does: ArcFace cosine at least 0.999 (ruling 68's gate); SCRFD boxes and the five landmarks
      within a tolerance the PR states and justifies. A CPU-only CI test pins whatever graph change
      the plans need, as `[r252]`'s does.
- [ ] The operator runs it (UR-15) and posts the stage table and `RESULT:` line; the PR records GPU
      memory added and latency per face.

**Done when:** `RESULT: PASS` is posted at the head and the UR-89 review approves. Nothing in
production switches yet.

### [r308a] CI sinks for the alerting golden paths

**Flags:** none. **Assigned:** ops-b, after `[r290]` (ruling 308). **Depends on:** none.
**PR:** #7340. (ruling 308, record 6326364266)

The alerting packages' golden paths deliver to a mail server, a webhook receiver and a push
service; the CI harness admits only `FAKE_SERVICES` today (`scripts/feature_check.py:96`, `:463`).
Split out of `B4.2` so it is ready before `B4.2`'s build PR
([`../4n-alerting.md`](../4n-alerting.md), "What changes", ops).

- [ ] The CI harness admits a mail sink, a webhook sink and a Web Push service fake beside
      `FAKE_SERVICES`, each started by the fake stack and readable by a golden test; the CI
      webhook sink is marked "on this network".

**Done when:** a smoke test sends one message to each sink and reads it back in CI, and the UR-89
review approves.

### [r309] The labelled frame set for `[r303]`

**Flags:** none. **Assigned:** ops-b, after `[r308a]` (ruling 309). **Depends on:** none.
**PR:** none yet. (ruling 309, record 6327202214)

`[r303]`'s detector bake-off scores the candidates on about 400 real stills from the owner's
cameras, stratified into day, night/IR and distant subjects, with at least 100 in each stratum that
contain a person or a vehicle. An open-vocabulary detector from a different family than every
candidate (OWLv2 or Grounding DINO, as synthbench's §4.1 rule requires) pre-boxes them, and the
owner corrects the boxes. Classes: person and vehicle first; any other product class the pre-box
finds is kept. The frames and labels stay on the host: no frame, crop or label file enters the
repo, a PR, a CI artifact or any cloud service.

- [ ] A stratified sampler over the camera upload tree, seeded and repeatable, that writes its
      selection list (paths and strata only) on the host.
- [ ] The independent pre-box pass, writing COCO-format boxes.
- [ ] A locally run labelling tool loaded with the frames and pre-boxes, with a short guide for the
      owner, and an export to the COCO file the bake-off reads.

The PR says where each step runs (the owner's host login or a venue that mounts the camera tree);
it never needs the frames in a sandbox's git tree.

**Done when:** the owner has corrected the set, and the PR posts the counts per stratum and class
(no images) and the labelled file's SHA-256.

### [r311a] An MQTT broker in the CI harness

**Flags:** none. **Assigned:** ops-b, after `[r309]` (ruling 311). **Depends on:** none.
**PR:** none yet. (ruling 311, record 6328311780)

`B4.8`'s golden path sends the arming commands through a real broker, beside `[r308a]`'s sinks
([`../4n-arming.md`](../4n-arming.md), "What changes", ops).

- [ ] The CI harness starts a Mosquitto broker with a password file, an ACL that lets only the
      backend's user read `<prefix>/commands/#` and lets the sender read `<prefix>/results/#` (the
      one the operator README gives with `B4.8`), and a TLS listener with a test CA. A golden test
      can connect as the backend, as a command sender and as an unprivileged user. A second
      listener accepts anonymous logins, for `B4.8`'s refusal step.

**Done when:** `B4.8`'s golden path can run against it (ruling 311): a smoke test in CI publishes a
command as the sender, receives it as the backend, sees nothing as the unprivileged user, connects
over TLS with the test CA, and connects anonymously to the second listener; and the UR-89 review
approves.

### [r312a] Re-ID's plan divergence, layer by layer

**Flags:** none. **Assigned:** ops-b, first on its queue, as `[r252]` was (ruling 312). Where it
edits `ai/gateway/` (cell A's files), UR-9 applies. **Depends on:** none.
**PR:** #7355. (ruling 312, record 6329693164)

Run 188.18 (`6327606735`) read 1.000000 under ONNX Runtime on CPU on the decomposed export, and
0.346321 at its FP32 plan, as 188.17 did on the raw graph. The divergence sits inside the
ONNX→TensorRT build, so the next measurement names the first layer the plan gets wrong. The latest
supported Triton image carries a newer TensorRT and ONNX Runtime, either of which may already fix
its half; `[r312b]` moves the gateway to `26.09-py3`.

- [ ] `[r157]`'s runner (`scripts/uplevel/reid_real_tier.sh`) gains a layer-compare mode: Polygraphy
      runs the decomposed ONNX under ONNX Runtime (CPU) against the TensorRT FP32 plan with every
      layer's output marked, on the same 36 crops, and prints the first layer under 0.999 cosine
      with its op type and name.
- [ ] The runner takes the Triton image as a parameter. On the latest supported release it rebuilds
      the plan with that release's TensorRT and runs the stage table and the layer compare, and it
      adds a stage serving the ONNX through Triton's `onnxruntime` backend on the GPU (CUDA
      execution provider), as a probe only.
- [ ] CPU-only CI tests pin the new modes' parsing and output.

The operator runs it twice (UR-15): on `26.01-py3` and on the latest supported release, on its
agent-gpu venue, with the same 36 crops and production weights. Each run posts its tables verbatim
on #7238 and links them from #7002. Ruling 306 item 3's stop on spend is lifted for these two runs
only. If the latest release's plan reads every stage at or above 0.999 on all 36 crops, that run is
O2.4's evidence once `[r312b]` ships the image; any other outcome goes to the owner through the
coordinator before more spend.

**Done when:** both runs are posted, each naming the first diverging layer or reading every plan
stage at or above 0.999; and the UR-89 review approves.

### [r312b] The AI stack on its latest supported releases, the Triton image first

**Flags:** `heavy`, `owner` (it changes what ships, UR-98); label `cell:heavy-b`. **Assigned:**
heavy-b, after `O3.7`, ahead of `[r307a]` and `B4.6` (ruling 312). **Depends on:** none.
**PR:** #7343. (ruling 312, records 6329693164 and 6331303299)

UR-187 starts here: the gateway built on `nvcr.io/nvidia/tritonserver:26.01-py3`
(`ai/gateway/Dockerfile:1`), on which ONNX Runtime's CUDA execution provider had failed on the GB300
(ruling 106).

- [ ] An inventory of the AI stack's pinned components, each with its pinned version, its latest
      supported release for the GB300 and the host driver, and its source, in the PR body; it is
      the list UR-187 tracks.
- [ ] The gateway's Triton image moves to the latest supported release; every model it serves is
      rebuilt for it (plans and engines on the serving host, as today), and the tests pinning
      `26.01-py3` follow.
- [ ] Any further component the inventory shows behind is upgraded in the PR or named as its own
      follow-up package.
- [x] If the release needs a newer host driver than the owner's host runs, the PR stops there and
      puts the driver step to the owner; changing the host is the owner's act. It needs none: the
      operator's run at `f1e7fa50c` served every model on `26.09-py3` through the image's
      forward-compatibility libraries (run 39702868586, operator `6330800872`, review
      `6330317376`; ruling 312's amendment, record 6331303299).

**Done when:** CI is green; the operator's real-tier run on the GB300 shows every served model
loading and answering; and the UR-89 and UR-95 reviews approve. Re-ID's parity read on the new image
is `[r312a]`'s second run and O2.4's, not this package's (the amendment, record 6331303299).
