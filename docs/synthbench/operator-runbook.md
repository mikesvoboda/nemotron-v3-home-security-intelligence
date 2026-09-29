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
systemctl --user restart synthbench-guard.service                          # after an update
```

`units install` writes `~/.config/systemd/user/synthbench-*` for the checkout it runs from, and
reloads systemd when a file changed. `units show` prints them.

## The renderer

- **Start:** `systemctl --user start synthbench-renderer.service`. It returns after the warm-up
  image, a few minutes the first time.
- **Stop:** `systemctl --user stop synthbench-renderer.service`. The agent's next `render`
  exits 2, and it asks you.
- **Why it refused to start:** `journalctl --user -u synthbench-renderer -n 50` names every
  reason.
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

2. Either copy the files back from `/synthbench/corpus/.zfs/snapshot/<name>/…` to the
   same paths, or accept the loss with `zfs destroy <held snapshot>`.
3. Run `systemctl --user start synthbench-snapshot.service`. `status/snapshots.json` shows
   `"hold": null` once pruning gets through.

Snapshots accumulate past 5 until you resolve the hold. A file created and deleted within the
same 6 h is in no snapshot. ComfyUI keeps its own copy of every render under
`/synthbench/comfy-out/synthbench/<version>/<event id>/`.

## Create the agent's sandbox

Run this from the repository checkout at the commit the agent should use. Its workspace is a
clone of that checkout.

```bash
cd ~/github/nemotron-v3-home-security-intelligence
agent-dgx run synthbench-gen --agent claude --endpoint dgx \
  --mount /synthbench/corpus:rw --mount /synthbench/status:ro
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
- To remove the sandbox: `agent-dgx stop synthbench-gen && agent-dgx session rm synthbench-gen --force`.
- Never run `agent-dgx help` or `agent-dgx ls`: an unknown word starts a real session.

## Review a batch

1. Read the agent's report and `<corpus>/batches/<b>/report.md`.
2. Open `<corpus>/batches/<b>/sheet.html` in a browser on the host.
3. Confirm the batch from the host checkout: `cd /synthbench/host-checkout &&
.venv/bin/python -m synthbench check --batch <b>` must exit 0. It re-checks every fact
   against the sampler, every frozen prompt against the rules, and every image against its
   sha256. The agent's own clone could have been edited; this checkout was not.

## The agent's stop-and-ask questions

| The agent reports                          | You                                                                                    |
| ------------------------------------------ | -------------------------------------------------------------------------------------- |
| the renderer is unreachable or stopped     | read the guard's journal; start the renderer once the flagship is healthy              |
| the status file is stale or missing        | `systemctl --user restart synthbench-guard.service`                                    |
| the reroll cap                             | look at the failed stills; sample a replacement batch if the scenario needs the events |
| an attempt failed to render 3 times        | read its `render_failures` in `provenance.json` and ComfyUI's log                      |
| the taxonomy changed                       | a changed taxonomy needs a new corpus version: edit `version:` in the YAML             |
| a spec, prompt or image is not as expected | find out who changed it (`zfs diff` against the last snapshot) before going on         |
