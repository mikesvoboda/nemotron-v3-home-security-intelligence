# Handoff: power-cycle pause, 2026-09-14 ~14:20 (gate 18 halted pre-verdict)

For whoever picks this up next (including a future me). Goal:
`docs/goal-prompt-m1-m2-m3-2026-09-14.md`. Ground truth: the LEDGER
`docs/plans/2026-09-12-context-map-doc-updates.md` — every gate row, ruling, and
finding is transcribed there; this doc only adds the boot-adjacent mechanics.

## Repo state (all pushed, clean tree)

- Branch `feat/context-map-2026-09-12`, tip `c6b7211d`. Do not re-derive from
  older summaries; `git log --oneline -25` is current.
- New since the last goal-doc write: gate-16 RED row + fix `126bf536`;
  prettier fix `973b0ce0`; gate-17 RED row `a756d6fa`; hooks process-finding
  `c6b7211d`; ledger reformat `71c3c1bb`; staged chaos patch `3f93ae3b`.

## Why the halt

Owner is power-cycling the workstation. Gate 18 was killed mid integration tier
(14:16, unit tier already `[OK]`) — **pre-verdict, aborts don't count**. rc file
never written. No summary was ever printed, so nothing was voided.

## Gate scoreboard (from summary lines only — protocol)

| Gate | Tip      | Verdict                                                                                                                                                                                             |
| ---- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 14   | 9eb02b3e | GREEN (recorded; frontend anchor 2990.68s)                                                                                                                                                          |
| 16   | 5cd37663 | RED — App.lazy FAST_TIMEOUT flake, fixed `126bf536`                                                                                                                                                 |
| 17   | 3f93ae3b | RED — Prettier on `126bf536`'s lines, vitest never ran. **Backend fully green under T5 config**: unit `27524 passed/84.34s`, integration `4165 passed/588.94s` ZERO node-downs = T5 step-4 gate 1/2 |
| 18   | a756d6fa | ABORTED pre-verdict (power cycle)                                                                                                                                                                   |

**Needed next: one clean green gate from tip `c6b7211d` (= gate 19) → record
M1 §6 → the next green gate after §6 counts as gate 2/2 for T5 step-4.**

## Post-boot recovery, in order

1. `grep MemTotal /proc/meminfo` — if the owner's bump landed, note it (T3's
   8x8192 vitest heap arm needs ~96 GiB; 62 GiB runs all gate tiers fine —
   gate 14/17 prove it).
2. `env | grep -E 'TEST_DATABASE_URL|TEST_REDIS_URL'` — persistent via
   `/etc/sandbox-persistent.sh`. **NEVER unset them** (DiskFull cascade). If
   lost: restore values from `/home/agent/env-backup-gb300.env`.
3. `docker ps` — the three gate containers have **restart=no** and will be DOWN.
   Start all three: `docker start gate-postgres gate-redis laughing_albattani`
   (the last is eclipse-mosquitto:2.0, needed by MQTT-touching integration
   tests). Then verify: `pgrep -fc postgres` > 1, `redis-cli ping`. Never touch
   `dgx-inference-*` (they aren't here, but the rule stands).
4. Leftover `security_test_gw0..7` worker DBs from the killed run are EXPECTED
   — conftest drops/recreates per run. Do not hand-drop anything.
5. `.env` must be ABSENT for gates. It lives in the repo dir and survives
   reboots; the backup is `/home/agent/env-backup-gb300.env` if it ever needs
   restoring OUTSIDE a gate window. `/tmp` is wiped by the reboot — the old
   `/tmp/validate-full-1*.log` gate logs are gone; their verdicts already live
   in the ledger rows.
6. Durations tooling: in-tree `docs/superpowers/staged/2026-09-14/dur/`
   (+ `/home/agent/dur-runs-backup`) — unaffected by the /tmp wipe.

## NEW since last session: git hooks are live — two consequences

- Commit-stage pre-commit now runs in this sandbox (prettier x2/eslint/tsc/
  ruff/mypy/semgrep/cmsg/secrets; python3.12 installed at `~/.local/bin` for
  the semgrep env). **Before committing any `.md`/`.json` in docs/, run
  `npx --prefix frontend prettier --write <file>`** — 196 docs markdown files
  are legacy-dirty; the hook rewrites them and refuses the commit. The ledger
  file itself is already clean.
- The **pre-push hook is deliberately NOT installed** (its parallel-tests entry
  would fan out pytest+vitest onto a box a gate owns — run-9 collision class).
  Pushes run bare. Reinstall only between gates if wanted.

## Launch the next gate (19) — exact form

Census first (`ps aux | grep -E 'pytest|vitest|validate'` empty), `.env` absent,
containers up. From repo root, NOTHING else on the box:

```bash
rm -f /tmp/validate-full-19.log /tmp/gate19.rc && \
nohup sh -c './scripts/validate.sh > /tmp/validate-full-19.log 2>&1; echo $? > /tmp/gate19.rc' >/dev/null 2>&1 &
```

~55 min (unit ~15, integration ~10, frontend ~35+lint stages). Monitor the rc
file + `[ERROR]` banners; verdict ONLY from summary lines. Frontend anchor for
comparison: 2990.68s (gate 14); gate 17 never reached vitest.

## On gate 19 GREEN — the M1 §6 close-out (the thing everything is waiting on)

1. Fill `docs/superpowers/staged/2026-09-14/wave3-drafts/w0-runbook/ledger-addition-append.md`
   (APPEND at ledger EOF; retarget its "gate 16" wording to gate 19; replace
   every `[PLACEHOLDER]`/`[RUN:]` with real lines from the logs — capture the
   log lines BEFORE anything wipes /tmp again; side logs land in
   `/tmp/validate-backend-unit.log` / `-integration.log`, coverage TOTAL row
   from validate.sh output, vitest rows ANSI-stripped).
2. Commit the §6 record, push. That un-arms the FCL §9 M1-constraint (
   validate.sh/addopts/vite.config freeze).
3. AFTER the gate (never alongside): compose/healthcheck per M1 T8 —
   `/platform-healthcheck` skill, `podman compose -f docker-compose.prod.yml`
   (podman for compose, docker for gate containers), API health curl.
4. Tick M1 T7 steps 5/7 + T8 in the plan file.

## After §6: M2 then M3, in the wave-3 critic order (in the ledger)

M2: **T3 apply + MEASURE** (needs the 96 GiB box for the 8x8192 heap arm;
anchor 2981.18s; RSS-sample per plan) → t4 → t5→t6→t7 (commit msg:
"reconciliation of shipped M1 substrate") → T10 already landed `2d5fe924` →
T13 → **T14 variant A** (owner-ruled; delete the schedule-only variant at
landing) → T15 playbook. Patches: `docs/superpowers/staged/2026-09-14/
wave3-drafts/` — see its `MERGE-NOTES.md` for per-file apply commands
(t3.patch needs `git apply -3` at the old slot; re-verify hunks against the
current conftest before applying).
M3 (waits M2-green, plan rule 1): slots [10] t1.patch, [11] t3.patch
(`git apply -3`), [12] t2-dead-fixtures.patch + m3-t2-chaos-delete.patch
(both owner-ruled 2026-09-14, rulings in ledger) → T6–T11 with measurement
rows → final gate x2 green, zero node-downs completes T5 DoD.
Then push + close Linear via `/linear-python`.

## Standing hazards that bit this session (all in ledger, listed for speed)

- Gate 16 class: React-19 lazy renders need STANDARD_TIMEOUT under suite
  contention — do NOT reintroduce FAST_TIMEOUT in waitFor around real lazy().
- Frontend edits must pass `npm run format:check` (and now the hook enforces).
- Standalone pytest: pass `--randomly-seed=N` (unset seed crashes faker_seed);
  `-p no:randomly` loses to addopts.
- T5 known caveat: signal timeout does not re-arm during fixture SETUP on a
  rerun attempt — recorded, owner-visible, not a blocker.
- Never bend production to pass tests; never widen quarantines/allowlists
  (16-file R-T7-VITEST list); never scope a tree out of the gate.
