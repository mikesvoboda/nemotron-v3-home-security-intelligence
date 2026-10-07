# Scripts - Uplevel Module

## Purpose

The uplevel programme's host-side tooling. Today one tool: `launch.py`, the sandbox
launcher (package `O0.1`, rulings UR-26 and UR-28 in `docs/uplevel/`). It is a **host tool
for the owner** - no agent runs it. The programme itself is planned in `docs/uplevel/`
(start at its `README.md`); this module only automates what `docs/uplevel/50-coordination.md`
("Where agents run") describes the owner doing by hand at a phase boundary.

## Files

### launch.py

Brings a phase's agent sandboxes up and retires one down without losing work. Two
commands (`--dry-run` on both prints every step and changes nothing):

- `launch.py up --phase <n>` - from a clean host checkout of `main` inside a herdr pane,
  creates each missing session with `agent-dgx run <name> … --split` (one sandbox and one
  clone per agent), checks `agent-dgx inspect --json` reports the cloned commit, and
  prints each agent's kickoff line. Re-running creates only what is missing.
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

### sandboxes.toml

The roster: per phase, each session's name, model (a `[models]` key) and kickoff line,
mirroring `docs/uplevel/50-coordination.md`'s roster - when the coordinator changes the
plan, that PR updates this file too. Network profiles and secrets are deliberately absent
(no shown `agent-dgx` flag takes them); provisioning stays the owner's.
