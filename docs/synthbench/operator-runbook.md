# Synthbench generation: operator runbook

For the owner. It covers the host side of agent-driven Tier B generation
(`docs/superpowers/specs/2026-09-28-synthbench-agent-driven-generation-design.md`): the host
units, the renderer, snapshot holds, the agent's sandbox, and reviewing a batch. The agent's
own document is `agent-handoff.md`.

## The pieces

| Piece                         | What it does                                                                                                                                               | How it runs                |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------- |
| `synthbench-guard.service`    | Every 5 s writes `status/flagship.json`. After 3 failed flagship health checks in a row it stops the renderer. It never stops or starts the flagship.      | user unit, enabled at boot |
| `synthbench-renderer.service` | ComfyUI with FLUX.2 [dev] on `127.0.0.1:8188`, `--reserve-vram 4`, bound to the guard. The pre-start check is listed below. One warm-up image after start. | user unit, started by hand |
| `synthbench-snapshot.timer`   | Every 6 h (UTC): snapshot `primary/export/synthbench/corpus`, prune by design §6, write `status/snapshots.json`.                                           | user unit, enabled at boot |
| `/synthbench/host-checkout`   | a detached worktree with its own `.venv`; the units run its code                                                                                           | updated by the owner       |

The renderer's pre-start check requires:

- a fresh guard status file and a healthy flagship;
- a flagship util gate at most 0.76;
- at least 60 GiB free on the GPU.

## Install or update the host checkout and units

```bash
cd ~/github/nemotron-v3-home-security-intelligence && git fetch origin
git worktree add --detach /synthbench/host-checkout origin/main     # the first time
git -C /synthbench/host-checkout checkout --detach origin/main      # to update
cd /synthbench/host-checkout && uv sync --frozen
mkdir -p /synthbench/status
.venv/bin/python -m synthbench.host.units install
systemctl --user enable --now synthbench-guard.service synthbench-snapshot.timer
systemctl --user restart synthbench-guard.service       # after an update, renderer stopped
```

`units install` writes `~/.config/systemd/user/synthbench-*` for the checkout it runs from, and
reloads systemd when a file changed. `units show` prints them.

The renderer unit is bound to the guard (`BindsTo=`), so restarting the guard also restarts a
running renderer: an in-flight render fails, and a new warm-up runs. Update the checkout and
restart the guard only while the renderer is stopped.

## The renderer

- **Start:** `systemctl --user start synthbench-renderer.service`. It returns after the warm-up
  image, a few minutes the first time.
- **Stop:** `systemctl --user stop synthbench-renderer.service`. The agent's next `render`
  exits 2, and it asks you.
- **Why it refused to start:** `journalctl --user -u synthbench-renderer -n 50` names every
  reason.
- **"A synthbench-comfyui container is already running" but
  `systemctl --user is-active synthbench-renderer` prints anything but `active`** (a pre-check
  failure leaves the unit `failed`, not `inactive`): the container is probably stuck in podman's
  `Removing` state. Before the unit set `KillMode=mixed`, systemd's default sent SIGTERM to
  podman run's own `--rm` cleanup partway through, not just its main process, and could leave it
  stuck there. The unit's `ExecStopPost` runs `serve cleanup` after every stop, and after a
  failed start too: it force-removes a stopped leftover, but leaves a running container alone —
  for example, one started by hand (`serve up`) or by an owner GPU window reusing the same
  container name, which is also the usual reason the pre-check itself refuses. The guard is
  different: after it stops the unit, it stops a container that is still running. For whatever
  gets past both, look at the container's state first:

  ```bash
  podman --root /export/models/containers/storage --runroot /run/user/1000/synthbench-containers \
    ps -a --filter name=synthbench-comfyui --format '{{.Status}}'
  ```

  A running container is deliberate until you know otherwise: stop it with
  `.venv/bin/python -m synthbench.generate.comfy.serve down` from the host checkout. Force-remove
  only one that is not running:

  ```bash
  podman --root /export/models/containers/storage --runroot /run/user/1000/synthbench-containers \
    rm -f synthbench-comfyui
  ```

  `--root`/`--runroot` must match `serve.podman_argv()` on this host; confirm with
  `.venv/bin/python -m synthbench.generate.podman` from the host checkout.

- **ComfyUI's own log:** `/synthbench/logs/comfyui.log`.
- **Never enable it at boot.** It holds about 50 GiB beside the flagship, and each render slows
  the flagship's decode by about 59%.
- **Before an owner-only GPU window** (parent spec §3.6), stop the renderer unit. The window
  stops every container labelled `synthbench.gpu=1` anyway. The guard stands down while the
  window's marker file (`/synthbench/state/window.open`) exists: it keeps writing the status
  file, but it stops neither the renderer nor the window's own ComfyUI container, so stopping
  the renderer unit first is still required — the window's ComfyUI reuses the renderer's
  container name. Start the unit again after the window has restored the flagship.

## Read the guard

- `cat /synthbench/status/flagship.json` shows the time (UTC), `healthy`, `running`,
  `waiting` and consecutive `failures`.
- `journalctl --user -u synthbench-guard -n 50` shows "stopping the renderer" when it acted.
- After the guard stops the renderer, the renderer stays stopped. Check the flagship first
  (`curl -s 127.0.0.1:8000/health`, `docker ps --filter name=dgx-inference-vllm-1`), then start
  the renderer again.

## Resolve a snapshot hold

A hold means the oldest snapshot holds the only copy of a removed or changed file. The batch
report shows it, `status/snapshots.json` names it, and the timer's last run exited 2
(`systemctl --user status synthbench-snapshot.service`).

1. List the snapshots, oldest first, and look at what changed after the held one:

   ```bash
   zfs list -H -t snapshot -o name -s createtxg -d 1 primary/export/synthbench/corpus
   zfs diff -FH <held snapshot> <the next snapshot>
   ```

2. Destroy the held snapshot. The prune rule diffs two snapshots that never change, so a hold
   clears only when the held snapshot is destroyed; copying files back alone never clears it.
   - **To keep the files:** first copy them back from
     `/synthbench/corpus/.zfs/snapshot/<held>/…` (`<held>` is the snapshot's name after the
     `@`) to the same paths in the live corpus. Then `zfs destroy <held snapshot>`. The live
     corpus holds the files again, and the next snapshot keeps them.
   - **To accept the loss:** just `zfs destroy <held snapshot>`.
3. Run `systemctl --user start synthbench-snapshot.service`. `status/snapshots.json` shows
   `"hold": null` once pruning gets through.
4. If you restored a modified image, expect one more hold. The restore is itself a
   modification, so the next snapshot now holds the only copy of the modified version. Check it
   with `zfs diff -FH` as in step 1, then destroy it the same way.

Snapshots accumulate past 5 until you resolve the hold. A file created and deleted within the
same 6 h is in no snapshot. ComfyUI keeps its own copy of every render under
`/synthbench/comfy-out/synthbench/<version>/<event id>/`.

## Create the agent's sandbox

One command retires the old agent and creates a ready one. Run it from your checkout at the
commit the agent should use, inside a herdr pane, with the renderer stopped:

```bash
cd ~/github/nemotron-v3-home-security-intelligence
uv run python -m synthbench.host.agent up --dry-run   # the checks, and the steps it would run
uv run python -m synthbench.host.agent up
```

It checks everything before it changes anything. It refuses with exit 2, changing nothing,
outside herdr, while the renderer runs, when the host checkout has uncommitted changes
(agent-dgx would copy them into the agent's clone), and while the old agent holds notes the
commit lacks (see `down` below). Then it:

1. Retires the old agent, as `down` does.
2. Puts the host checkout on the commit (`--ref`, default `HEAD`), syncs it, reinstalls the units
   and restarts the guard ("Install or update the host checkout and units").
3. Creates the agent from the host checkout, so its clone is the host's commit, and checks the
   new manifest's source commit. The agent opens in a new herdr pane and waits.
4. Prepares the sandbox with `sbx exec`: the libraries OpenCV needs (the sandbox image lacks
   them, and `import cv2` fails with `libxcb.so.1` missing, verified 2026-09-28;
   `docs/benchmarks/synthbench/p3-probes.md`), `uv sync --frozen`, and an import check.
5. Starts the renderer (`--no-renderer` leaves it stopped), then runs `doctor` in the sandbox:
   every line ok.

A failed step stops it with exit 2 and names the step; fix the cause and run `up` again, which
starts over. It ends by printing the line to give the agent.

The two commits must match because the owner's host `check` re-applies the host's own
`synthbench/prompt/` (the rules, the blocklist, the camera suffix) and `synthbench/taxonomy/`
(the taxonomy and the sampler) to the batch. If they differ from the agent's, the host `check`
exits 2 on every frozen prompt.

**Retire the agent only:** `uv run python -m synthbench.host.agent down`. It first copies the old
workspace's `docs/synthbench/` to `~/synthbench-gen-backups/<UTC time>/`. It then refuses while
the agent holds notes the commit lacks: a file the agent changed since it was created, whose
content the commit does not already have, such as its additions to `flux-prompt-notes.md` or
`h3-prompt-notes.md`. Commit them and run it again, or pass `--discard-notes`. It reads the
workspace's files but never runs git there.

By hand, `up` is these commands (the sandbox is `agent-synthbench-gen`, its workspace
`/agents/agent-synthbench-gen/workspace`):

```bash
agent-dgx stop synthbench-gen && agent-dgx session rm synthbench-gen --force
git -C /synthbench/host-checkout checkout --detach <commit>
cd /synthbench/host-checkout && uv sync --frozen
.venv/bin/python -m synthbench.host.units install
systemctl --user restart synthbench-guard.service
agent-dgx run synthbench-gen --agent claude --endpoint dgx \
  --mount /synthbench/corpus:rw --mount /synthbench/status:ro --split
sbx exec agent-synthbench-gen sudo apt-get install -y libxcb1 libgl1 libglib2.0-0
sbx exec agent-synthbench-gen bash -lc \
  'cd /agents/agent-synthbench-gen/workspace && uv sync --frozen'
sbx exec agent-synthbench-gen bash -lc \
  'cd /agents/agent-synthbench-gen/workspace && uv run python -c "import synthbench.cli, av"'
systemctl --user start synthbench-renderer.service
sbx exec agent-synthbench-gen bash -lc \
  'cd /agents/agent-synthbench-gen/workspace && uv run python -m synthbench doctor'
```

Then tell the agent: "Read docs/synthbench/agent-handoff.md and follow it", with the batches you
want (for example: a 10-event pilot `pilot-1`, then a 50-event `batch-1`).

- Do not mount any path under `/export`: sbx sandboxes cannot bind them (see
  `docs/benchmarks/synthbench/p3-probes.md`). `/synthbench` is its own ZFS dataset and mounts
  fine; the sandbox needs no extra env var, since the code's default `SYNTHBENCH_ROOT` is
  already `/synthbench`.
- The sandbox reaches the renderer through the host's loopback (P3 probe,
  `docs/benchmarks/synthbench/p3-probes.md`).
- The agent sometimes ends a turn mid-task after a line such as "Now rendering:". If its
  transcript goes quiet mid-batch, type "continue"; every command resumes.
- Never run `agent-dgx help` or `agent-dgx ls`: an unknown word starts a real session.

## Review a batch

1. Read the agent's report and `<corpus>/batches/<b>/report.md`.
2. Open `<corpus>/batches/<b>/sheet.html` in a browser on the host.
3. Confirm the batch from the host checkout: `cd /synthbench/host-checkout &&
.venv/bin/python -m synthbench check --batch <b>` must exit 0. It re-checks every fact
   against the sampler, every frozen prompt against the rules, every image against its
   sha256, and the triage limits (one reroll per event, the batch's 10% cap, each verdict
   equal to its `triage.jsonl` row). The agent's own clone could have been edited; this
   checkout was not.
4. Diff the agent's workspace against the commit the sandbox was created from, which is the
   host checkout's commit:

   ```bash
   diff -rq -x __pycache__ /synthbench/host-checkout/synthbench \
     /agents/agent-synthbench-gen/workspace/synthbench
   diff -rq /synthbench/host-checkout/docs/synthbench \
     /agents/agent-synthbench-gen/workspace/docs/synthbench
   ```

   Any difference under `synthbench/` or `docs/synthbench/` is a stop: review it before you
   accept the batch. `diff` compares the files themselves, committed or not. Do not run `git`
   in the agent's workspace on the host: its `.git/config` is the agent's to write, and some
   settings there (`core.fsmonitor`) run commands.

## Serve a model for replay (P5a)

`python -m synthbench replay` scores one model that is already served
(`docs/superpowers/specs/2026-09-29-synthbench-p5a-vlm-replay-design.md` §3). Serve one model at a
time, only while the renderer is stopped (`systemctl --user is-active synthbench-renderer` prints
`inactive`), and keep each well under 50 GiB so a flagship restart still passes its util gate.
Commands run from the repo checkout. The evidence behind them is
`docs/benchmarks/synthbench/p5a-probes.md`.

**Once: the weights and the images.**

```bash
SRC=/agents/agent-vss1/gpu/models/vlm DST=/export/models/ai_models/vlm
mkdir -p "$DST"
for f in Qwen3VL-8B-Instruct-Q4_K_M.gguf mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf \
         Qwen3VL-4B-Instruct-Q4_K_M.gguf mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf \
         NVIDIA-Nemotron-Nano-12B-v2-VL-Q4_K_M.gguf NVIDIA-Nemotron-Nano-12B-v2-VL-BF16-mmproj.gguf; do
  cp "$SRC/$f" "$DST/"
done
chmod 0755 /export/models/ai_models "$DST"; chmod 0644 "$DST"/*.gguf
(cd "$DST" && sha256sum *.gguf > SHA256SUMS)      # `score` reads it for the run identity

as_gpu() { (cd / && sudo -u agent-gpu env XDG_RUNTIME_DIR=/run/user/1001 \
  DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1001/bus podman "$@"); }
for tag in sm103-v12 sm103-b11090; do as_gpu save "localhost/agent-vss1/ai-vlm:$tag" | podman load; done
podman tag localhost/agent-vss1/ai-vlm:sm103-v12 localhost/nemotron-v3-home-security-intelligence_ai-vlm:latest
```

`sm103-v12` (llama.cpp `b7972-e06088da0`) is the product's build; `sm103-b11090` is the one
Nemotron-12B-VL needs. The copy only reads the VSS agent's folder.

**`ai-vlm` (the three llama.cpp models).** `.env.bench` holds this host's values. Start the
service with `podman-compose`, not `podman compose`: the latter goes through the docker-compose
plugin and podman's Docker API, which drops the CDI GPU device, so `llama-server` exits 127 on
`libcuda.so.1`. Compose also demands `POSTGRES_PASSWORD` for the backend service; `ai-vlm` never
reads it, so pass a placeholder on the command line and never write one into `.env.bench`.

```bash
export POSTGRES_PASSWORD=not-used-by-ai-vlm
podman-compose --env-file .env.bench -f docker-compose.prod.yml up -d --no-deps --no-build ai-vlm
curl -s 127.0.0.1:8098/props | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['build_info'], d['model_path'])"
podman-compose --env-file .env.bench -f docker-compose.prod.yml stop ai-vlm      # when done
```

The first command serves `qwen3-vl-8b` (`b7972-e06088da0 /models/Qwen3VL-8B-Instruct-Q4_K_M.gguf`,
about 11 GB). Not yet run in P5a: for `qwen3-vl-4b`, set `VLM_MODEL_PATH`, `VLM_MMPROJ_PATH` and
`VLM_MODEL_ALIAS` to the 4B pair and recreate the container; for `nemotron-12b-vl`, also re-tag
`sm103-b11090` as `localhost/nemotron-v3-home-security-intelligence_ai-vlm:latest` first. `replay`
refuses a served model other than the one named, so a wrong switch cannot score silently.

**Cosmos-Reason2-8B (vLLM, synthbench's podman store).** Stop `ai-vlm` first.

```bash
P="$(uv run python -m synthbench.generate.podman)"
V=docker.io/vllm/vllm-openai@sha256:c2b7c425d4a30d26bc2097ac6b28331fbe1b8aee11b8bfbb02bc3295de6f642d
$P pull "$V"                                     # once; the flagship's image, 22.4 GB
$P run -d --name synthbench-cosmos --device nvidia.com/gpu=all -p 127.0.0.1:8099:8000 \
  -v /export/models:/export/models -e HF_HOME=/export/models -e HF_HUB_OFFLINE=1 "$V" \
  --model nvidia/Cosmos-Reason2-8B --served-model-name nvidia/Cosmos-Reason2-8B \
  --gpu-memory-utilization 0.10 --max-model-len 16384 --limit-mm-per-prompt '{"image": 4}' \
  --reasoning-parser qwen3
for i in $(seq 1 90); do curl -sf 127.0.0.1:8099/v1/models >/dev/null && break; sleep 10; done
$P rm -f synthbench-cosmos                       # when done
```

It is ready in about 3 minutes and holds about 25 GiB. Cosmos is a reasoning model: without room
to reason it loops inside the verdict's first text field. So, for Cosmos only (the owner's
choice), `replay` adds the model card's `<think>` format instruction as a system message and gives
it a 4096-token budget and a 120 s read timeout, and `--reasoning-parser qwen3` keeps its reasoning
out of the JSON. Without that flag the reasoning would land in the answer, which would then
likely fail to parse (not tested). The product
model and the flagship keep the shipped prompt, 1024 tokens and 25 s.

**A rebuilt export needs a fresh eval store.** Items in `eval/<version>/eval.sqlite` are
immutable, so `replay` refuses a store whose items differ from the export (label, score,
timestamp or detections). Move `$SYNTHBENCH_ROOT/eval/<version>/` aside (never delete: other
replays' results live there) and replay again.

**The flagship** is already served on `127.0.0.1:8000`. It is shared with the agents: replay it in
a quiet period. `replay` turns its thinking off, which keeps it inside the product's 1024-token
budget.

## Score the models (P5a)

The full scored run, as it was done on 2026-09-29/30. It needs the owner for the audit and for the
flagship's timing. A model is served as the section above says.

1. **Record the start.** Keep the time for the guard check in step 6.

   ```bash
   date '+%F %T' | tee ~/p5a-start
   docker inspect -f '{{.State.StartedAt}} restarts={{.RestartCount}}' dgx-inference-vllm-1 | tee ~/p5a-flagship
   systemctl --user is-active synthbench-renderer synthbench-guard    # inactive, active
   uv run python -m synthbench export vss                             # 450 unchanged
   ```

2. **The audit (owner, about 20 minutes).** Run `uv run python -m synthbench audit` and answer all
   60 stills at `http://127.0.0.1:8765/`. From another machine, tunnel the same port first:
   `ssh -L 8765:127.0.0.1:8765 <host>`. The page refuses answers from any other origin or port.
3. **The product model:** serve `ai-vlm`, then run
   `uv run python -m synthbench replay --model qwen3-vl-8b`. It takes about 19 minutes.
4. **The comparison models.** Stop `ai-vlm` and start `synthbench-cosmos`, then run
   `replay --model cosmos-reason2-8b` (about 1¾ hours). The flagship replay,
   `replay --model flagship` (about 35 minutes), loads nothing, so it can run alongside Cosmos in
   a quiet period the owner picks. The eval store takes both writers (SQLite, 30 s busy timeout).
   If any replay refuses more than 5% of its items, stop and show the owner its refusal classes.
   (On 2026-09-30 Cosmos refused about 13% and the owner stopped it; the flagship was the
   comparison.)
5. **Score.** Run
   `uv run python -m synthbench score --replay <qwen id> --replay <cosmos id> --replay <flagship id>`.
   To view the gallery, serve the tree:
   `cd /synthbench && python3 -m http.server 8766 --bind 127.0.0.1`, then open
   `runs/scores/<score_id>/report.html`.
6. **Check the flagship stayed healthy.**

   ```bash
   journalctl --user -u synthbench-renderer -u synthbench-guard --since "$(cat ~/p5a-start)" --no-pager
   docker inspect -f '{{.State.StartedAt}} restarts={{.RestartCount}}' dgx-inference-vllm-1 | diff - ~/p5a-flagship
   ```

   Expected: no entries, and no difference.

7. **Stop what you served** (`ai-vlm`, `synthbench-cosmos`). Commit `report.md` as
   `docs/benchmarks/synthbench/p5a-<date>.md`, with the acceptance record.

## Clip rounds (the owner's part)

Clips render beside the flagship through the same renderer. `clip render` switches ComfyUI
from FLUX.2 to H3 (`/free`, then a warm-up clip), and the stills' `render` switches it back.
The guard covers both. Design: `docs/superpowers/specs/2026-09-30-synthbench-h3-clips-design.md`.
There is no pilot gate (spec C13): a round may take every ready still.

1. **Recreate the agent at the commit with the clip commands** ("Create the agent's sandbox"):
   `uv run python -m synthbench.host.agent up`, with the renderer stopped. It retires the old
   agent once its notes are safe, updates the host checkout, creates the agent (its clone brings
   the commands and `.claude/skills/synthbench-generation/` together), and starts the renderer.
2. **Ask for the round:** "Make clips of every ready still, round clips-1; follow 'Clip rounds'
   in docs/synthbench/agent-handoff.md." About 328 s per clip beside the flagship: 459 clips
   take about 42 hours, and flagship users are slower while a clip renders.
3. **Watch it:**

   - `rounds/clips-1/report.md` and `sheet.html` under `/synthbench/corpus/<version>/`;
   - `clip-index.jsonl`;
   - the guard (`journalctl --user -u synthbench-guard`).

   Stop the renderer at any time. The agent's next `clip render` then exits 2, and every
   command resumes later.

4. **Confirm the round on the host:**
   `uv run python -m synthbench clip check --round clips-1`.

## The agent's stop-and-ask questions

| The agent reports                          | You                                                                                     |
| ------------------------------------------ | --------------------------------------------------------------------------------------- |
| the renderer is unreachable or stopped     | read the guard's journal; start the renderer once the flagship is healthy               |
| the status file is stale or missing        | `systemctl --user restart synthbench-guard.service`; it restarts a running renderer too |
| the reroll cap                             | look at the failed stills; sample a replacement batch if the scenario needs the events  |
| an attempt failed to render 3 times        | the event is now failed; see below                                                      |
| the taxonomy changed                       | a changed taxonomy needs a new corpus version: edit `version:` in the YAML              |
| a spec, prompt or image is not as expected | find out who changed it (`zfs diff` against the last snapshot) before going on          |

**An attempt failed to render 3 times.** Its event is now `failed` in `index.jsonl`, a
terminal state: later `render` runs skip it, and the batch finishes without it. Read its
`render_failures` in `provenance.json` and ComfyUI's log (`/synthbench/logs/comfyui.log`), and
fix the cause before the agent renders more. A failure recorded while the renderer was
unreachable is marked `unreachable` and does not count toward the 3. Whether to sample
replacements is your decision.
