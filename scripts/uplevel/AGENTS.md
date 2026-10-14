# Scripts - Uplevel Module

## Purpose

The uplevel programme's tooling. `launch.py` is the sandbox launcher (package `O0.1`, rulings
UR-26 and UR-28 in `docs/uplevel/`) and is a **host tool for the owner** - no agent runs it.
`prod-shape-probe.sh` and its override file are different: an agent runs those, inside a
sandbox, as the `O2.5` Step 1 spike (ruling 144), and `docker-compose.prodshape.yml` is the same
package's Step 2 artifact (ruling 162) - an override plus the CPU-only CI test that pins what it
covers. The programme itself is planned in
`docs/uplevel/` (start at its `README.md`); this module only automates what
`docs/uplevel/rules.md` ("Agents, sandboxes and models") describes the owner doing by hand at a
phase boundary.

## Files

### launch.py

Brings a phase's agent sandboxes up and retires one down without losing work. Two
commands (`--dry-run` on both prints every step and changes nothing):

- `launch.py up --phase <n>` - from a clean host checkout of `main` inside a herdr pane,
  creates each missing session with `agent-dgx run <name> … --split` (one sandbox and one
  clone per agent), checks `agent-dgx inspect --json` reports the cloned commit, and
  prints each agent's kickoff line. Re-running creates only what is missing. A session
  declaring `gpu = true` gets `--gpu` after its model arguments, and the whole phase
  refuses first when the launching shell has no `AGENT_GPU_RUNNER_URL` (UR-30: one GPU
  holder, reached through agent-gpu's runner).
- `launch.py retire <name>` - the owner ends the agent's session first. Git runs inside
  the sandbox via `sbx exec` and **never** on the host against `/agents/agent-<name>/workspace`:
  that workspace's `.git/config` is the agent's to write, and settings such as
  `core.fsmonitor` execute commands when host git opens the repo
  (`docs/synthbench/operator-runbook.md`). Any uncommitted, untracked, stashed or
  unpushed work - or a failed inspection - refuses retirement (the owner's manual call).
  Only a clean workspace exports (`git bundle create --all` + a working-tree archive, made
  inside the sandbox), verified on the host from the owner's checkout, and only then
  `agent-dgx stop` and `agent-dgx session rm --force`.

Exit codes: 0 done; 2 refused or a step failed, always naming the next step. It follows
`synthbench/host/agent.py`: every command goes through one `Host` seam, all checks run
before any change. Tests: `backend/tests/unit/scripts/test_uplevel_launch.py` (a fake
host, plus the inspection script executed against throwaway real git repos).

**Command vocabulary:** only `agent-dgx`/`sbx` forms the repo already shows
(`synthbench/host/agent.py`, `docs/synthbench/operator-runbook.md`) - `agent-dgx` reads an
unknown word as a new session's name, so never run `agent-dgx help` or `agent-dgx ls`, and
never invent a flag; the strongest model's run arguments come from the owner into
`sandboxes.toml`'s `[models]`.

### prod-shape-probe.sh + prod-shape-override.yml

The `O2.5` Step 1 spike (ruling 144): does `docker-compose.prod.yml` come up as a disposable
test deployment under **rootless** Podman inside an uplevel sandbox? `prod-shape-probe.sh`
prints `OBSERVED` for each claim its answer rests on - the four sandbox mechanisms that decide
rootless storage and limits, the differential control that isolates resource limits as the
blocker (same image, `--entrypoint` overridden, limits off vs `--memory` vs `--cpus`), then the
bring-up of the image services the override covers, each checked (`redis-cli ping`,
`pg_isready`). Exit 0 both services answered; 2 a prerequisite is missing; 3 the bring-up
failed.

`prod-shape-override.yml` is the spike's answer to "the minimal override file it needed":
`deploy: !reset null` (a rootless container that asks for limits cannot start where no cgroup
controllers are delegated) and `ports: !override` (UR-133 remaps). Both tags are moby
docker-compose syntax - `podman-compose` cannot express the empty mapping - so the probe drives
the moby CLI against podman's Docker-compatible API socket. Storage is the other half of the
answer and cannot live in that file: this sandbox cannot mount overlayfs even as root and
`/dev/fuse` is `EPERM`, so the only working driver is `vfs`, set through
`CONTAINERS_STORAGE_CONF` rather than `--storage-driver` (the flag is refused on an existing
database). The probe is a test deployment in every sense UR-133/134 require and tears itself
down with `down -v` only (UR-135).

### docker-compose.prodshape.yml + test_prodshape_override.py

`docker-compose.prodshape.yml` is Step 2's real artifact (ruling 162 item 3): the override the
prod-shape runner applies on top of `docker-compose.prod.yml`. The production file is **not**
edited - this file is the only carrier - and it changes exactly three kinds of thing: drops the
container-engine socket on `backend` and `alloy` (UR-134), prefixes `hsi-test-` onto every
`container_name` **prod pins** (UR-133; a service prod leaves unpinned gets no `container_name`,
because adding one where prod has none is a key change, not a prefix), and remaps every published
port by +15000 and every writable host bind under `${PROD_SHAPE_RUN_ROOT}`. Read-only binds and
named volumes are kept verbatim. `limits` are absent on purpose: ruling 162 item 2 makes them a
runtime decision the runner records, so keeping them out of the committed file is what makes the
delta the static, assertable part.

That variable is interpolated **required** (`${VAR:?…}`), and that is a safety property, not
tidiness: a bare `${VAR}/cameras` with the variable unset interpolates to `/cameras` and compose
only _warns_ ("variable is not set. Defaulting to a blank string"). Measured on the first version
of this file: a forgotten `PROD_SHAPE_RUN_ROOT` rendered writable binds at the filesystem root
(`/cameras`, `/backend-data`, `/triton-cache`, `/hf-cache`) — a UR-133/134 breach that writes
outside the run directory on a host that may run the live stack, silently. `test_override_refuses_
to_render_without_the_run_root` pins the refusal.

Two compose/YAML traps in the same file, both measured: a `:?` message must not contain a colon
followed by a space, because YAML reads `key: value` inside an otherwise-plain scalar and each
volume entry silently becomes a one-key mapping; and a comment inside a folded YAML scalar is
literal text (see `test_check_gate_reachability`). `test_prodshape_override.py` renders the file
through the compose CLI, so it is the oracle that catches either corruption — a bare `yaml.safe_load`
cannot even parse it (the `!override`/`!reset` tags are compose's).

The override is **hand-authored, never generated.** A generator would derive it from the prod
render, the override would always match prod, and the CI test could never fail - which is precisely
the failure ruling 162 asks to be possible. `scripts/test_prodshape_override.py` is that test: it
renders prod and prod+override with `docker compose config` (CPU-only, daemon-free - client-side
interpolation and schema validation, nothing starts, so UR-133/134/135 are respected by
construction) and asserts the _observed_ delta equals an _expected_ delta derived from a policy
that never reads the override file. It is wired into `collection-sanity`'s pytest list, where it
costs 0.31 s.

Three measured compose facts the file depends on, each re-checked before it was relied on:
`volumes` merge **by target** (an entry at an existing target replaces it and can never delete
one, so dropping or redirecting a mount requires restating the whole list under `!override`);
`ports` **append** (same reason); and a relative `./x` source resolves against the **compose
project directory** - the first `-f` file's dir, the repo root - not the override's own
`scripts/uplevel/`, which is what lets a relative path byte-reproduce prod's absolute source and
keeps the CI comparison machine-independent. The socket mounts are only findable by rendering with
a sentinel `PODMAN_SOCKET`, because `prod.yml` interpolates that variable into **both** fields on
`alloy` and into only the source on `backend`.

### sandboxes.toml

The roster: per phase, each session's name, model (a `[models]` key) and kickoff line,
plus optional `mount` and `gpu` (a plain TOML boolean; only `uplevel-operator` sets it).
The loader refuses the hand-edit shapes a growing roster can produce: a non-boolean
`gpu`, a `gpu` row mounting at or under `/srv/agent-models` (which `agent-dgx --gpu`
owns), and a name repeated within one phase. It mirrors the roster in
`docs/uplevel/roles/lane.md` ("Who takes what") - when the coordinator changes the plan, that PR
updates this file too. A kickoff line names
the prompt's **section**, never a position (`up` prints it verbatim, and a position rots
when the file grows); #6864 established that rule, and both the heavy row and the
operator row on main now carry the section form. Network
profiles and secrets are deliberately absent (no shown `agent-dgx` flag takes them);
provisioning stays the owner's.
