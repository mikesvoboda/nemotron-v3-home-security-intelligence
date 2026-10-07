# Operator Runbook — the Real Tier

> For the **operator** (README vocabulary): the owner, or an agent the owner has given GB300 access.
> Lane agents work in a sandbox without the GPU; when a package needs real-model numbers, its PR
> carries a command and you run it. This file is everything that role needs.

## What you are asked to run

| when    | what                                                     | from                         |
| ------- | -------------------------------------------------------- | ---------------------------- |
| Phase 1 | hand-written commands in the PRs for `B1.1` and `B1.2`   | the PR's "Real tier" section |
| Phase 2 | the first `scripts/feature-check.sh --real` run (`O2.2`) | `O2.2`'s PR                  |
| Phase 2 | the real-tier date for every inventory row (`F2.3`)      | `F2.3`'s PR                  |
| Phase 4 | each completed feature's real-tier check                 | that feature's build PR      |

A PR waiting on you shows `awaiting real tier` in the README status table.

## The one rule: a test deployment, never the live stack

Every real-tier command runs on a **test deployment** — a disposable stack with its own compose
project, env file, host ports, volumes and camera directory. The prod compose file is built to be
the only stack on a machine (no project name, seven fixed container names, the live camera folder
`/export/foscam`, Postgres in a named volume), so a command that skips any of these lands on
production.

Once `O2.2` lands, `scripts/feature-check.sh --real` enforces this with a preflight and postflight
check, and you run the script as is. **Before `O2.2` lands** (Phase 1), vet every hand-written
command yourself:

1. **Read the command before running it.** Send it back to the PR if it lacks a `-p <project>`
   flag, uses the checkout's `.env`, leaves any published port at its default, mounts
   `FOSCAM_BASE_PATH` anywhere but a fresh empty directory, or points at the live `ai-vlm` URL.
2. **Render what it would start, and read the mounts.** Run the command's compose invocation with
   `config` in place of `up`. Send it back if any writable bind mount points outside a directory
   made for this run — the prod file bind-mounts the checkout's `./backend/data` with `U`, which
   re-owns live files (`docker-compose.prod.yml:454`) — or if any service mounts the Podman socket
   (`:468`). The backend's orchestrator is on by default and restarts any container whose name
   matches, in every project; a test stack must run with `ORCHESTRATOR_ENABLED=false` and no
   socket.
3. **Check GPU headroom.** Run `nvidia-smi --query-gpu=index,memory.used,memory.total --format=csv`.
   If a live `ai-vlm` runs on the GPU the command would use and a second engine would not fit
   beside it, stop: running anyway is a **RULING** for the owner (another GPU, a maintenance
   window, or calling the live engine read-only).
4. **Snapshot before:** `podman ps -a --format '{{.Names}} {{.Status}} {{.StartedAt}}'` and
   `podman volume ls -q`, each into a file.
5. **Run the command.** Tear down only with `podman compose -p <project> down -v`, never a bare
   `down`.
6. **Snapshot after and diff.** Every container and volume from the first snapshot must still
   exist, and every container that was running must still be running with the same start time.
   Live data is protected by step 2, not by this diff: live files change all the time (camera
   uploads, thumbnails, logs), so a changed file is not on its own a sign of interference.

## Posting results

1. Paste the command's output as a comment on the PR, headed with the date, the commit, the GPU and
   host it ran on (GB300 or A5500 — latency numbers such as S4's p95 belong to the hardware that
   produced them), and the before/after snapshot diff.
2. Set the package's README status row from `awaiting real tier` to `done` in a one-line follow-up
   commit, or ask the lane agent to.

## When something goes wrong

- **A live container stopped or restarted (its start time changed), or a volume vanished:** start
  what stopped (`podman start <name>`), say so on the PR, raise it with the owner on the urgent
  path, and leave the row at `awaiting real tier`. The package is not done until a clean run.
- **Live data looks wrong after a run:** report it on the urgent path and investigate with the
  owner. Restore nothing on your own — live data changes during every run for ordinary reasons,
  and a restore would discard real footage.
- **The command fails for reasons the PR did not anticipate:** post the output and the exit code.
  Do not adapt the command yourself; the lane agent revises it.
