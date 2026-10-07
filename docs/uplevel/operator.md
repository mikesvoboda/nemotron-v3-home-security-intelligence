# Operator Runbook — the Real Tier

> For the **operator** (README vocabulary): the `uplevel-operator` agent, whose sandbox reaches the
> GB300 through the `agent-gpu` broker (UR-30), and the owner for the runs that path cannot make.
> Lane agents have no GPU; when a package needs real-model numbers, its PR carries a command and the
> operator runs it. This file is everything that role needs.

## What you are asked to run

| when    | what                                                     | from                         |
| ------- | -------------------------------------------------------- | ---------------------------- |
| Phase 1 | hand-written commands in the PRs for `B1.1` and `B1.2`   | the PR's "Real tier" section |
| Phase 2 | the first `scripts/feature-check.sh --real` run (`O2.2`) | `O2.2`'s PR                  |
| Phase 2 | the real-tier date for every inventory row (`F2.3`)      | `F2.3`'s PR                  |
| Phase 4 | each completed feature's real-tier check                 | that feature's build PR      |

A package waiting on you shows `awaiting real tier` in the README status table on `main`. Work
those rows oldest first; each names the PR whose "Real tier" section holds the command.

## The one rule: a test deployment, never the live stack

Every real-tier command runs on a **test deployment** — a disposable stack with its own compose
project, env file, host ports, volumes and camera directory. The prod compose file is built to be
the only stack on a machine (no project name, seven fixed container names, the live camera folder
`/export/foscam`, Postgres in a named volume), so a command that skips any of these lands on
production.

## The agent-gpu path

The default path, and the operator agent's only one. Once `O2.2` lands, `scripts/feature-check.sh
--real` runs these steps itself; until then, follow them by hand.

**What the sandbox gives you.** `agent-gpu` (`status`, `pull`, `build`, `run`, `ps`, `logs`,
`stop`, `rm`); `$AGENT_GPU_DIR` with `models/` (weights, read-only in a container) and `out/`
(writable); and the sandbox's own Docker for everything that needs no GPU. There is no `podman`, no
`nvidia-smi` and no engine socket, and the broker runs your containers in a namespace fenced to
this session, so nothing you start can see or restart the live stack's containers. The one way
out is the network: `host.docker.internal` reaches the host's loopback ports, where the live
stack's API, database and engine listen. Step 3 closes it.

**Once, by the owner:** stage the VLM weights in `$AGENT_GPU_DIR/models/vlm/`, sha256-matched to
the compose pin, and readable by the container's user: files `644`, a traversal bit on `models/`
(both have hidden the weights before: finding E in `docs/plans/2026-09-23-vss-gaming-gpu-ledger.md`).

1. **Check headroom.** `agent-gpu status` must show `fence: true` and a `free_mib` that covers your
   declaration plus `floor_mib`. If it does not, stop: the run goes to the owner's batch (another
   time, or a smaller model). **MEASURE** once, with the owner, whether `agent-gpu run` refuses a
   declaration above `free_mib`, using a probe that allocates nothing
   (`agent-gpu run --name probe --vram <free GiB + 2> --wait --image <a CUDA image> --entrypoint nvidia-smi -- -L`,
   then `agent-gpu rm probe`), and record the answer here; until then this check is the only
   guard for the live services sharing the GPU.
2. **Serve the model.** Check out the commit the PR names. Build the image once per state of
   `ai/vlm/`, tagged with its tree hash (`git rev-parse --short HEAD:ai/vlm`):
   `agent-gpu build --context workspace:ai/vlm --tag ai-vlm:<tree> --build-arg CUDA_ARCHITECTURES=103`.
   Then:

   ```bash
   agent-gpu run --name vlm --image ai-vlm:<tree> --vram 14 --port 8098 \
     --mount models:/models --user 0 --ttl 12 \
     --env MODEL_PATH=/models/vlm/<gguf> --env MMPROJ_PATH=/models/vlm/<mmproj> \
     --env <each other ai-vlm variable from docker-compose.prod.yml, verbatim>
   ```

   The broker remaps the port: read it from the JSON that `run` prints (`ports."8098"`), and set
   `VLM_URL=http://host.docker.internal:<that port>`. Wait for `$VLM_URL/health` to return 200,
   and record `/props`' `build_info` and `model_path`. Known traps: `--image` is required;
   `--wait` goes before `--`; `--user 0` is needed to read the weights; declare honestly, since the
   watchdog kills a container over its budget in about 15 s (this config measured 9,056 MiB
   actual against 14 GiB declared).

3. **Bring up the test deployment in the sandbox's Docker,** with its own project
   (`docker compose -p <run project>`), its own env file, `ORCHESTRATOR_ENABLED=false` and no
   engine socket, and the backend's VLM URL set to `$VLM_URL`. Render the configuration first
   (`docker compose -p <run project> … config`) and refuse to start when any value points at
   `host.docker.internal` or another host address on any port but the one `agent-gpu run` printed.
4. **Run the PR's command** as written, with `VLM_URL` set.
5. **Tear down, also after a failure:** `docker compose -p <run project> down -v`, then
   `agent-gpu stop vlm` and `agent-gpu rm vlm`. `agent-gpu ps` must list none of your containers.

**Runs the owner keeps,** following "The owner on the host" below: a run that must exercise the
deployed compose `ai-vlm` service itself; a run whose headroom check fails; and latency claims for
S1 and S4, which are defined on 24 GB-class hardware (`docs/vss-integration/README.md`), so GB300
numbers do not make them.

## The owner on the host

For the runs the owner keeps. Once `O2.2` lands, `scripts/feature-check.sh --real` enforces this
with a preflight and postflight check, and you run the script as is. Before then, vet every
hand-written command yourself:

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

1. Paste the command's output, verbatim, as a comment on the PR, headed with the date, the commit,
   and the hardware: for the agent-gpu path, "GB300 through agent-gpu", the image tag, `build_info`,
   and VRAM declared and actual; on the host, the GPU and host (GB300 or A5500). Latency numbers
   such as S4's p95 belong to the hardware that produced them. Every number in the comment comes
   from output in the comment (UR-29).
2. Add the teardown evidence: on the agent-gpu path, the empty `agent-gpu ps`; on the host, the
   before/after snapshot diff.
3. Set the package's README status row from `awaiting real tier` to `done` in a one-line follow-up
   PR, or ask the lane agent to.

## When something goes wrong

- **A container of yours outlived the run:** `agent-gpu rm` it, and say so on the PR.
- **A live container stopped or restarted (its start time changed), or a volume vanished:** start
  what stopped (`podman start <name>`), say so on the PR, raise it with the owner on the urgent
  path, and leave the row at `awaiting real tier`. The package is not done until a clean run.
- **Live data looks wrong after a run:** report it on the urgent path and investigate with the
  owner. Restore nothing on your own — live data changes during every run for ordinary reasons,
  and a restore would discard real footage.
- **The command fails for reasons the PR did not anticipate:** post the output and the exit code.
  Do not adapt the command yourself; the lane agent revises it.

## Kickoff prompt

Paste this to the operator agent, in the `uplevel-operator` sandbox.

```text
You are the operator of the uplevel programme: you run real-tier commands on
the GB300 through agent-gpu. Read docs/uplevel/README.md, then
docs/uplevel/operator.md, which is your whole role.

Work oldest first: the README status rows on main that say "awaiting real
tier", and the PR each row names. For each, follow "The agent-gpu path" step by
step, post the results comment, and set the row to done in a one-line
follow-up PR. Runs the owner keeps go to the daily batch, not to you.

You write no product code and change no command; when a command fails for a
reason its PR did not anticipate, post the output and the exit code and move
on. Every number you post comes from output in the same comment. Always tear
down, also after a failure.
```
