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
--real` runs these steps itself; until then, follow them by hand. The source for `agent-gpu` is the
stack repository's `docs/operations/agent-gpu-runner.md`; `agent-gpu <verb> --help` contacts
nothing, so it is safe to read.

**How it works.** The GPU never enters the sandbox. The `agent-gpu` CLI sends typed requests to
`agent-gpu-runner`, a host daemon that runs rootless podman as the user `agent-gpu` and accepts no
raw podman flags. `agent-dgx --gpu` gives the sandbox:

- `agent-gpu` on the `PATH` (`status`, `pull`, `build`, `job`, `run`, `ps`, `logs`, `stop`, `rm`,
  `renew`, `images`, `rmi`);
- `$AGENT_GPU_DIR`, with `models/` and `out/`;
- `$AGENT_GPU_LIBRARY` (`/srv/agent-models`), the shared model library: read-only, indexed by its
  `MANIFEST.json`.

A GPU container sees only the roots you pass as `--mount ROOT:TARGET`, where ROOT is `workspace`
(read-only), `models` (read-only), `out` (writable) or `library` (read-only). The sandbox's own
Docker runs everything that needs no GPU. Nothing you start can see or restart the live stack's
containers. The one way out is the network: `host.docker.internal` reaches the host's loopback
ports, where the live stack's API, database and engine listen. Step 4 closes it.

**Admission is the runner's.** `--vram <GiB>` is required. The runner admits a run only if the VRAM
declared by every GPU session plus this request stays within the 40 GiB cap, and free VRAM stays
above the 4 GiB floor. Its watchdog kills a container that uses more than it declared.

1. **Check the weights.** Real-tier numbers are about the production pin
   (`docker-compose.prod.yml:179-180`) and nothing else. Run
   `(cd $AGENT_GPU_LIBRARY/qwen3vl-8b-instruct-q4km && sha256sum *.gguf)` and stop unless it prints
   exactly:

   ```text
   67d1659bfe71b89d50b45a4ad1a9e5b997e5bb16ce5da66a6a6167abd569e9e2  Qwen3VL-8B-Instruct-Q4_K_M.gguf
   c6ba85508d82f42590e6eb77d5340369ab6fecf107a7561d809523d8aa5f3bfd  mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf
   ```

   The library also holds `qwen3vl-8b-instruct-q8_0/`, a Q8_0 build of the model itself. It is
   not the pin; serve only `qwen3vl-8b-instruct-q4km/`.

2. **Build the image.** Check out the commit the PR names. Builds never pull, so first
   `agent-gpu pull` each `FROM` image in `ai/vlm/Dockerfile`. Build once per state of `ai/vlm/`,
   tagged with its tree hash (`git rev-parse --short HEAD:ai/vlm`):
   `agent-gpu build --context workspace:ai/vlm --tag ai-vlm:<tree> --build-arg CUDA_ARCHITECTURES=103`.
   An image name without a registry is this session's own build.
3. **Serve the model from the library:**

   ```bash
   agent-gpu status   # record the budget
   agent-gpu run --name vlm --image ai-vlm:<tree> --vram 14 --port 8098 --ttl 12 \
     --mount library:/library \
     --env MODEL_PATH=/library/qwen3vl-8b-instruct-q4km/Qwen3VL-8B-Instruct-Q4_K_M.gguf \
     --env MMPROJ_PATH=/library/qwen3vl-8b-instruct-q4km/mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf \
     --env <each other ai-vlm variable from docker-compose.prod.yml, verbatim>
   ```

   The runner publishes the port on the host from the pool 18100–18199. Read it from the line
   `run` prints, `port 8098 -> http://host.docker.internal:<hostport>`, and set `VLM_URL` to that
   URL. Wait for `$VLM_URL/health` to return 200, then record `/props`' `build_info` and
   `model_path`; stop unless `model_path` names the Q4_K_M file above. If the runner refuses
   admission, the run waits: report it in the daily batch with the `status` output. Library files
   are readable by any container user, so add `--user 0` only for a container that writes to
   `out/`. This config measured 9,056 MiB actual against 14 GiB declared.

4. **Bring up the test deployment in the sandbox's Docker,** with its own project
   (`docker compose -p <run project>`), its own env file, `ORCHESTRATOR_ENABLED=false` and no
   engine socket, and the backend's VLM URL set to `$VLM_URL`. Render the configuration first
   (`docker compose -p <run project> … config`) and refuse to start when any value points at
   `host.docker.internal` or another host address on any port but the one `agent-gpu run` printed.
5. **Run the PR's command** as written, with `VLM_URL` set.
6. **Tear down, also after a failure:** `docker compose -p <run project> down -v`, then
   `agent-gpu stop vlm` and `agent-gpu rm vlm`. `agent-gpu ps` must list none of your containers.

**Runs the owner keeps,** following "The owner on the host" below: a run that must exercise the
deployed compose `ai-vlm` service itself; a run the runner will not admit; and latency claims for
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
   `model_path`, the weights' `sha256sum` output, and VRAM declared and actual; on the host, the GPU and host (GB300 or A5500). Latency numbers
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
