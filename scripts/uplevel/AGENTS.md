# Scripts - Uplevel Module

## Purpose

The uplevel programme's tooling. `launch.py`, the sandbox launcher (package `O0.1`, rulings
UR-26 and UR-28 in `docs/uplevel/`), and `reid_real_tier.sh`, the O2.4 re-ID real-tier runner
(package `[r157]`, rulings 157 and 159), are **host tools for the owner** - no agent runs them.
`prod-shape-probe.sh` and its override file are different: an agent runs those, inside a
sandbox, as the `O2.5` Step 1 spike (ruling 144), and `docker-compose.prodshape.yml` is the same
package's Step 2 artifact (ruling 162) - an override plus the CPU-only CI test that pins what it
covers. The programme itself is planned in
`docs/uplevel/` (start at its `README.md`); this module only automates what
`docs/uplevel/rules.md` ("Agents, sandboxes and models") describes the owner doing by hand at a
phase boundary, and what rulings 157/159 require repeated verbatim on the GPU host.

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
costs about 1 s of test time and about 2 s of wall time standalone (each number names its
instrument, measured 2026-10-14 on an unloaded sandbox: pytest's `--durations` sums this file's own
calls + setups at 0.99 s under `-n0`; full-process wall time is 2.04-2.17 s, and a `--collect-only`
run of the same file is 1.03-1.10 s, so about half the wall is interpreter/report startup the leg
already pays once for all its files). What the shared process actually charges is nearer the 0.99 s
of own-duration than the standalone wall. The original `0.31 s` here was a single pytest-reported
duration written in `12a4f6edc`, when the file had ten tests and rendered no profiles at all; it has
seventeen now and four module-scope renders (prod, prod+override, each twice - once with no profile
and once with both), so the file has about 1.7x the tests and 2x the compose work it had when that
number was written.

Three measured compose facts the file depends on, each re-checked before it was relied on:
`volumes` merge **by target** (an entry at an existing target replaces it and can never delete
one, so dropping or redirecting a mount requires restating the whole list under `!override`);
`ports` **append** (same reason); and a relative `./x` source resolves against the **compose
project directory** - the first `-f` file's dir, the repo root - not the override's own
`scripts/uplevel/`, which is what lets a relative path byte-reproduce prod's absolute source and
keeps the CI comparison machine-independent. The socket mounts are only findable by rendering with
a sentinel `PODMAN_SOCKET`, because `prod.yml` interpolates that variable into **both** fields on
`alloy` and into only the source on `backend`.

### pr_watch.py + test_pr_watch.py + r193-mutation-campaign.py

`pr_watch.py` is ruling 193's lane watcher: an agent arms it as a background task at the end of a
turn and the line it prints starts the next one (UR-38 — a backgrounded watcher is not waiting
inside a turn). One `gh api graphql` call per poll, never the search API (its 30/min is shared by
every agent on the owner's token), watching the PRs named by `--pr` plus those a label group
discovers, and the last 100 comments of #6854. It exits with one line per change class and no
comment bodies, survives transient failures, and always ends — an error line after repeated
failures, a "no change" line at its lifetime bound.

Four GraphQL facts decided the shape, all measured against the live API before the query was
written, and each the reason a plausible alternative is wrong: `pullRequests(labels: [...])` is
**OR**, not AND — `lane:ops` (82 PRs) and `lane:docs` (56), which no PR carries together, came back
as one query of 138 with an empty intersection, and AND would have returned 0 — so putting
`lane:ops` and `cell:a` in one connection narrows nothing (the union already holds every ops PR of
either cell) while `discovered` names the labels whose connection matched, which would let the watch
line print a label the PR does not carry. Hence one single-label group per connection alias, and
`discovered` collecting **every** matching label, not the first; the connection's `orderBy.field` is
`UPDATED_AT` (`UPDATED_DESC` is rejected outright); `states: [OPEN]` is load-bearing because an
unfiltered `lane:ops` query matched 82 PRs against 6 open ones (measured 2026-10-15 — the count
drifts, the ratio does not);
and the watched set must stay **monotonic** even though discovery asks for OPEN, or
a merge removes a PR from the set before its state is ever read. Label strings ride as `-f` String
variables — a `-F` JSON array matches nothing **and returns no error**, which is a silently empty
watch. A discovery page at `DISCOVERY_WINDOW` (100, GitHub's page cap) whose `totalCount` is higher
raises instead of reporting a quiet tick.

Two facts the UR-89 review turned up, each a bug a green suite shipped. `seeding` is keyed on
whether the state was ever seeded (`"seeded" not in state`), **not** on emptiness (`not state["prs"]`):
a watcher armed by label alone over a lane with nothing routed to it has an empty `prs` on every poll,
so emptiness kept it "seeding" forever and the seed poll's early `return []` meant its #6854 diff never
ran — a new `BINDING NOW`, the one event ruling 193 names, woke nobody, which is precisely the idle
lane that arms a watcher. And the marker match reads only a comment's **first line**, because UR-40
binds an owner record on its first line; matching the phrase anywhere in the body wakes the lane for a
comment that merely _mentions_ it — the live false-positive is #6854 comment `6180424930`, first line
`URGENT PATH · coordinator stale again`, whose status prose counts "42 BINDING NOW rows in window"
(verified at that id, 2026-10-15: 1 occurrence, 0 on the first line).

A second review round turned up three more ways to be silent, and all three were shapes where
**difference had been mistaken for addition**. An explicitly typed `--pr` that GitHub answers as null
was stored as `None` and then skipped forever, so a head change straddling that window never printed —
and never could, because the next poll's `before` _is_ the null snapshot. `_check_explicit` now
refuses that poll the way `_check_ruling` refuses a null ruling issue: a transient null costs one
error credit (the state keeps the last good snapshot, so the straddling change prints on the next good
poll) and a prolonged one exits rc 2. It guards only the numbers an agent typed, because those are
the ones label discovery can never hand back. A discovered PR answered null has a different cure — the
UNREAD carry-forward, which is what keeps its label group alive until it answers and its merge can
still print. And a comment or review **deleted** between polls used to print `new comment`: the diff
fired on any set difference and then searched the new side for an id missing from the old, which in
the delete direction finds nothing, so the line announced an addition that had not happened and named
no author. Deletion is not one of ruling 193's six change classes either, and the file resolves that
the way `_state_line` does a reopen — name what moved.

`scripts/test_pr_watch.py` (48 tests, in ci.yml's anti-rot-gates list) drives one seam —
`run(query, variables)` plus an injected clock and sleeper, no network, no monkeypatching. Its `Run`
fixture **raises** on an unscripted poll rather than returning an empty response, so a watcher that
starts reading something new fails loudly instead of passing on `{}`.
`scripts/r193-mutation-campaign.py` reverts 36 properties in a throwaway worktree and fails if any
survives; it follows `scripts/r151-mutation-campaign.py` and, like it, is run by hand rather than
registered in ci.yml — the campaign list holds suites, not drivers.

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

### reid_real_tier.sh

The O2.4 re-ID real-tier runner: the owner's throwaway maui run, committed so a repeat is a
command and not a scratchpad (`[r157]`, rulings 157 + 159). Two modes:

- `parity` (default) - the gateway serves this head's TensorRT plan and the runner runs
  `scripts/reid_parity_check.py` (#6970's command): every crop through the CPU OSNet
  reference and the served plan, cosine per crop against ruling 68's 0.999 gate. On a
  near-miss (0.99 <= min < 0.999) it rebuilds the plan once in FP32 and retries, so a
  precision loss is told apart from a fault.
- `stages` - ruling 157's five-stage diagnostic: PyTorch -> ONNX Runtime CPU -> the plan
  called directly FP32 -> FP16 -> the gateway endpoint, cosine per crop against stage 1,
  and the first stage under the gate names where parity breaks. Stages 3/4 bind the plan by
  device pointer using `ai/common/tensorrt_utils.py`'s own idiom, so they exercise the
  same plan the Triton backend loads, and each precision PRINTS the binding the engine
  reports (input/output names, declared shape, dtype, plus what the probe feeds) because
  bullet 2 names that print as a deliverable - a CHW-vs-transposed fault is shape-legal and
  shows up only when the owner can eyeball it. The gateway leg prints Triton's own
  `/v2/models/reid/config` too. A stage that raises just leaves its file absent and the
  table reads `unknown`; a stage plan missing on disk FAILS instead of falling back to the
  cache plan (which is the LAST compiled precision, so a fallback could score FP16 as
  FP32). `unknown` makes the table exit 2 - an incomplete diagnostic must not post as a
  clean run - while a located first failure stays exit 0, because naming the broken stage
  is this mode succeeding.

`--checkout`, `--gpu`, `--port`, `--checkpoint`, `--crops`, `--head`, `--mode` - the host
paths ruling 159 makes arguments. Without `--crops` it stops after build/export/compile and
prints the run directory: real camera crops cannot be synthesised (a synthetic crop passes
the parity check it is meant to test), so it waits for >=30 crops plus a `crops-ready`
touch. UR-133/UR-134 hold unchanged: a fresh detached worktree at a named head (never the
live checkout, never its `.env` - checked, not assumed), loopback-only port, the weights
and model cache read-only, a local image tag never pushed, and teardown on any exit that
re-snapshots both podman and docker and fails the run on any diff. Verified here: bash -n,
shellcheck clean, the three embedded python scripts byte-compile, and the cosine table's
four verdict branches tested against synthetic stage files. **Not run here:** the GPU legs
(1-4) and the gateway leg need the serving host; the owner runs it on maui.

### post_record.py

The owner's side of ruling 197's machine footers. `post_record.py record --ruling N --lanes a,b|all
--packages r1,r2|none --body-file F` posts a record on #6854; `post_record.py pointer --ruling N
--lane x --pr P --body-file F` posts a pointer on PR `P`. Each appends ONE footer line
(`<!-- uplevel: ruling=<n> lanes=<names|all> packages=<tokens|none> -->` or
`<!-- uplevel: pointer ruling=<n> lane=<name> -->`), which `lane_tick.py` turns into a `for you:`
line for the lane it names. The footer is parsed back with `lane_tick.py`'s own reader before
anything is posted, so the writer and the digest cannot drift. Refused (exit 2): a name that is not
a roster sandbox without its `agent-`/`uplevel-` prefixes, a body that already carries a footer, and
a record whose first line does not start `BINDING NOW · ruling N`. `--dry-run` prints the final body
and posts nothing; a failed post exits 1. It posts with `gh api ... -F body=@-` (the body on stdin)
through one injectable runner. Tests: `scripts/test_post_record.py`.

### plan_lint.py

The plan fields `lane_tick.py` acts on, checked where they are written (ruling 197).
`uv run python scripts/uplevel/plan_lint.py [--root DIR]` reads the working tree's roster
(`docs/uplevel/roles/lane.md`), package files and ruling map with `lane_tick.py`'s own parsers
(imported, never copied: `ROW`, `queue_entries`, `BLOCK`, `PKG_FIELD`, `NONE_YET`, `PR_NUMBER`,
`next_claimable`, `held_claims`). It fails when a roster queue token has no `### ` block in its
lane's package file, when a `**PR:**` field is neither `none yet` on one line nor a leading `#N`
(a `none` / `yet.` wrapped across two lines is that case, even when a later `issue #N` follows),
when one token is on two lanes' queues, or when a ruling-map row other than 1-145 and 147 names no
10-digit record id. Rows labelled `none` are skipped, and `F2.3` (one package split across every
lane, rulings 87 and 175) is held to its block in `frontend.md` instead. `--baseline REF` reads the
same files at a git ref (`git show`) and fails only on findings REF lacks, matched by file and
message, never line. Collection-sanity runs it as `python -m scripts.uplevel.plan_lint` with the
PR merge commit's first parent (the `main` it merged into) as the baseline, so a defect already on
`main` reds `main`'s run, not every PR. Exit 0 clean, 1 with one `file:line: message` per (new)
finding, 2 when the baseline ref is unreadable (the CI step also exits 2 when HEAD names no parent);
the last line counts what it read. Tests: `scripts/test_plan_lint.py` (fixtures and one throwaway
git repository; it never lints this checkout, which is the CI step's job).
