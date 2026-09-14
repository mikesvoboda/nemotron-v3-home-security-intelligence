# W0 — M1 §6 Close-Out RUNBOOK (gate-14-green → ledger record → push)

STATUS: **DRAFT ONLY.** Nothing here has been executed (box lease held through gate 14).
Every command below is for the executor to run AFTER the orchestrator calls W0, in ORDER,
single-tenant (nothing else on the box: `ps -eo args | grep -E 'python -m pytest|uv run pytest|vitest'` census clear first — binding rule, ledger:2094).

Sources of truth (read these first, cited inline by file:line):
- Spec §6 (exit criteria): `docs/superpowers/specs/2026-09-12-arm64-gb300-milestone1-design.md:169-181`
- Plan Task 8: `docs/superpowers/plans/2026-09-12-arm64-gb300-milestone1.md:521-551`
- Ledger M1 sections: `docs/plans/2026-09-12-context-map-doc-updates.md` (Phase A :103-181; gate-DB/env-protocol :280-310, :696-733; chain state :2176)
- Codified gate: `scripts/bootstrap-gb300.sh` (tracked; COMPOSE string :42, phases/gate functions, TARGETS allowlist :59)
- Health skill: `.claude/skills/platform-healthcheck/SKILL.md`

Template for the ledger entry (fill every [PLACEHOLDER]): `/tmp/wave3-drafts/w0-runbook/ledger-entry-template.md`

---

## STEP 0 — Wait for the verdict (do NOT poll by tailing; read files)

Gate 14: pid in `/tmp/gate14.pid` (currently 941436, launched as `/bin/sh ./scripts/validate.sh`), log `/tmp/validate-full-14.log`.
There is NO exit-code file on disk (verified 2026-09-14: no `/tmp/gate14.rc`; the nohup launch did not record `$?`). Therefore:
**the verdict is the banner + the process having exited. Never call it green while pid 941436 is still alive** — the banner is the LAST bytes the script writes (validate.sh:527-530).

```bash
# alive? keep waiting (use Monitor or an until-loop, not sleep-spam):
kill -0 "$(cat /tmp/gate14.pid)" 2>/dev/null && echo STILL-RUNNING || echo EXITED
```

## STEP 1 — Verdict proof: ONLY real summary lines from /tmp/validate-full-14.log

How success is signaled (verified by reading the script): `#!/bin/sh` + `set -e` (validate.sh:1,17); every failure path prints `[ERROR] <stage> failed` to **stderr** and `exit 1` (exit sites :197,219,230,241,252,262,338,352,364,396,404,414,428,451,461,474,484,492,501); the ONLY success marker is the final block:

```
============================================
  VALIDATION SUCCESSFUL: codebase is healthy!
============================================
```

(portable printf, validate.sh:527-530; exact string `  VALIDATION SUCCESSFUL: codebase is healthy!` — two leading spaces. No color codes: stdout was a file → `[ -t 1 ]` false → GREEN='' at :33-41, so the log is plain ASCII.)

**The exact grep (run as-is; requires EXACTLY one whole-line match):**

```bash
grep -FxC 1 '  VALIDATION SUCCESSFUL: codebase is healthy!' /tmp/validate-full-14.log
#   -F fixed-string, -x whole-line, -C 1 → shows the two '=' rules; that 3-line block
#   is the proof to PASTE VERBATIM into the ledger (with 'log line N of M' context:
#   run  grep -Fxn '  VALIDATION SUCCESSFUL: codebase is healthy!' /tmp/validate-full-14.log  to cite the line number)
grep -cF '  VALIDATION SUCCESSFUL: codebase is healthy!' /tmp/validate-full-14.log   # must print 1
grep -cE '^\[ERROR\] ' /tmp/validate-full-14.log                                     # must print 0
#   ^ anchored: only validate.sh stage failures start a line with "[ERROR] "
#   (print_error writes >&2; merged into the log via the nohup 2>&1 redirect).
#   Frontend tests print '[ERROR] frontend: WebSocket error' INSIDE vitest output —
#   those are indented/ANSI-prefixed test noise, NOT stage failures; do NOT grep bare 'ERROR'.
```

**Negative control (proves the grep discriminates):** gate 12 died WITHOUT the banner — run the same `grep -cF` on `/tmp/validate-full-12.log` → expect `0` [UNVERIFIED: file exists/absent as of draft time; executor records].

**Stage summary lines to transcribe (all real, none inferred):**

```bash
grep -n '^TOTAL' /tmp/validate-full-14.log | tail -1        # combined coverage vs gate 80 (validate.sh:354-358)
ls -l --time-style=full-iso /tmp/validate-backend-unit.log /tmp/validate-backend-integration.log \
    /tmp/validate-coverage-report.log                        # mtimes bind them to run 14 (script truncates all three, :333/:346/:356)
tail -2 /tmp/validate-coverage-report.log                    # the report validate.sh actually gated at 80
tail -30 /tmp/validate-backend-unit.log | grep -E 'passed|failed|error' | tail -3   # pytest summary line
tail -30 /tmp/validate-backend-integration.log | grep -E 'passed|failed|error' | tail -3
```

Vitest lives in the ANSI-colored log (vitest writes to stderr → merged in, keeps escape codes even when validate.sh itself is colorless; gate-10/13 ledger entries already record ANSI'd vitest content in these logs — [UNVERIFIED for run 14's exact bytes until read]). Extract summaries color-safe:

```bash
sed -r 's/\x1b\[[0-9;]*m//g' /tmp/validate-full-14.log > /tmp/validate-full-14.clean.log
grep -E 'Test Files|Tests  |Duration' /tmp/validate-full-14.clean.log | tail -5
```

**If the banner is absent → STOP.** W0 is dead for this gate; record the failure shape (last `[ERROR] ` line + the named side log's `tail -60`, which validate.sh itself prints on failure) and hand back to the chain. Do NOT proceed to Step 2.

## STEP 2 — Env restore (`.env` must NOT have existed during the run; restore only now — R-T8-ENVLEAK, ledger:696-733)

```bash
test -f .env && { echo "UNEXPECTED: .env present during gate — investigate before restoring"; }
cp /tmp/env-backup-gb300.env .env && chmod 600 .env
```

Sanity (a generated file vs a template — expect a LARGE diff; rc=1 is the PASS condition; do not commit secrets):

```bash
diff .env .env.example > /tmp/w0-env-vs-example.diff; echo "diff-rc=$?"   # expect 1 (different files)
grep -E '^(POSTGRES_PORT|REDIS_PORT|API_PORT|FRONTEND_HTTP_PORT|LOG_LEVEL)=' .env
```

Expected (from the backup itself, verified at draft time): `POSTGRES_PORT=5433`, `REDIS_PORT=6380` (host-form dodge — GB300 co-resident dgx holds standard ports), `API_PORT=8000` (setup.py resolved 8001 on THIS sandbox, bootstrap header :17-18 — trust what grep shows), `FRONTEND_HTTP_PORT=8080` (backup:34), `LOG_LEVEL=INFO` (backup:102 — the pipeline-worker-evidence prerequisite).
If restore-from-backup is refused (host drift), regeneration route: `bash scripts/bootstrap-gb300.sh env` is an **idempotent no-op once `.env` exists** (bootstrap:146-150) — it will NOT overwrite; only if `.env` is gone does it regenerate via setup.py machinery + `env-templates/gb300.env.template`.

## STEP 3 — SINGLE-TENANT RECONCILIATION (critic GAP: compose wants 5432/6379; docker gate DBs hold them)

The collision, grounded:
- prod compose publishes **host 5432**: `127.0.0.1:${POSTGRES_PORT:-5432}:5432` (docker-compose.prod.yml:61) and **host 6379**: `127.0.0.1:${REDIS_PORT:-6379}:6379` (:565).
- gate-postgres/gate-redis run in **rootful docker** holding host :5432/:6379 (ledger :300-303, :1710); rootless podman's rootlessport and dockerd **share host ports** (Phase A provider note, ledger :107-110 — a :9100 clash already burned us there).
- The restored `.env` says 5433/6380, BUT that variable only sets the HOST side of the mapping; the backend's own URL is hardcoded by the compose file to in-network `postgres:5432`/`redis:6379` (docker-compose.prod.yml:436-437) → **compose is functionally port-agnostic; only the host publish matters for the clash.**

**Collision check FIRST (read-only):**

```bash
ss -ltnp | grep -E ':(5432|5433|6379|6380)\b'
```

Decision (owner-sanctioned order — pick one, record which in the ledger):

1. **OPTION 1 (PREFERRED — ledger:2176 literally orders "reconcile … with the single-tenant gate DB first"):** after the GREEN record's summary lines are transcribed (Step 1 output pasted), the gate's job is over → stop the gate DBs *in docker* (their own namespace): `docker stop gate-redis gate-postgres` (names per ledger:302 — `docker ps --format '{{.Names}}' | grep gate-` to confirm). Re-run `ss -ltnp` → 5432/6379 free → `bootstrap-gb300.sh phase-a` publishes 5433→5432 / 6380→6379 per .env without clashing. W4/W8 heavy reruns later **restart** gate-postgres/gate-redis + re-export TEST_DATABASE_URL/TEST_REDIS_URL (bootstrap's gate-DB env protocol, ledger:298-303).
2. **OPTION 2 (fallback, zero-stop):** leave gate DBs on 5432/6379; compose publishes dodge to 5433/6380 (exactly what `.env` says — already proven working in Phase A, ledger:103+). Cost: §6 "API health endpoints 200" still passes (API/frontend ports unaffected); record the dodge as the M1 steady state.
3. **NEVER:** touch anything named `dgx-inference-*` (rootful dockerd — two-daemon rule); never run bare `docker` against the project stack (it targets the wrong daemon); gate containers stay in **docker**, project stack stays in **podman** — `podman compose` is the only compose spelling (project CLAUDE.md + bootstrap COMPOSE :42).

## STEP 4 — Bring-up + §6 evidence capture (all via the proven podman spellings)

```bash
cd /agents/agent-nemo2/workspace
COMPOSE="podman compose -f docker-compose.prod.yml -f config/docker-compose.gb300.yml"   # bootstrap-gb300.sh:42 verbatim
podman ps -aq --filter label=com.docker.compose.project=nemotron-v3-home-security-intelligence | sort   # churn "before"

bash scripts/bootstrap-gb300.sh phase-a    # idempotent; prints churn check (cmd_phase_a)
bash scripts/bootstrap-gb300.sh phase-b    # build_images + up -d --no-deps backend frontend (cmd_phase_b)
bash scripts/bootstrap-gb300.sh gate       # Task 8 Step 2a: current state → PASS expected; capture full output
bash scripts/bootstrap-gb300.sh phase-a    # Step 2b: already-up → no-op clean ("no container churn" line)
bash -n scripts/bootstrap-gb300.sh; echo "syntax-rc=$?"
```

§6 evidence lines (paste each command's real output next to its ledger bullet — template §6 block):

```bash
# (a) services Up+healthy (spec §6 core list + foscam-init one-shot):
$COMPOSE ps --format "table {{.Name}}\t{{.Status}}\t{{.Health}}"
#   expect 16 Up (+ foscam-init Exited(0)); redis-exporter & json-exporter plain-Up BY DESIGN (bootstrap:49-50)

# (b) foscam-init exited 0 explicitly:
podman inspect nemotron-v3-home-security-intelligence-foscam-init-1 --format '{{.State.ExitCode}}'   # 0

# (c) ai-*/dcgm ABSENT (proof of exclusion; anchored patterns can't match dgx-inference-*):
podman ps -a --format '{{.Names}}' | grep -E '(^|[-_])(ai-[a-z0-9-]+|dcgm-exporter)([-_]|$)'; echo "absent-rc=$?"   # expect 1 = no match

# (d) health endpoints (API_PORT/FRONTEND_HTTP_PORT from .env — read, never hardcode):
curl -s -o /dev/null -w '%{http_code}\n' localhost:$(awk -F= '/^API_PORT=/{print $2; exit}' .env)/api/system/health/ready
curl -s -o /dev/null -w '%{http_code}\n' localhost:$(awk -F= '/^FRONTEND_HTTP_PORT=/{print $2; exit}' .env)/api/system/health/ready
curl -s -o /dev/null -w '%{http_code}\n' localhost:$(awk -F= '/^API_PORT=/{print $2; exit}' .env)/api/system/health
#   ready=200 BOTH direct+proxied (that's the §6 "200"); aggregate /health = 503-degraded is M1 DESIGN
#   (bootstrap:407-408 addendum + spec §8 — do NOT chase a 200 there; 200 would mean AI unexpectedly up).

# (e) pipeline-worker startup in backend logs (LOG_LEVEL=INFO prerequisite):
podman logs nemotron-v3-home-security-intelligence-backend-1 2>&1 | grep -n 'Pipeline workers started'
#   line from backend/main.py:794-796; if absent, check LOG_LEVEL=INFO in .env and recreate backend
#   (grep -c/-n, never grep -q through a pipe on big output — R-PIPEFAIL-GREPQ note, bootstrap:419-423).

# (f) compose logs --tail=50 error scan (spec §6 last-log bullet):
$COMPOSE logs --tail=50 > /tmp/w0-compose-logs-tail50.log 2>&1
grep -niE 'error|fatal|panic|exception|traceback' /tmp/w0-compose-logs-tail50.log
#   triage every hit in one line each in the ledger (Phase A precedent table style).
```

## STEP 5 — shellcheck (Task 8 Step 2c)

Check for the binary — `which`/`command -v` is a read-only PATH lookup, **allowed**:

```bash
command -v shellcheck && shellcheck --version || echo "shellcheck: NOT on PATH"
```

Draft-time fact: **not on PATH in this sandbox** (verified `which shellcheck` → rc=1). The script header already records the sanctioned zero-install route (bootstrap-gb300.sh:29-33):

```bash
uvx --from shellcheck-py shellcheck scripts/bootstrap-gb300.sh     # --from form REQUIRED
```

If `uvx` is disallowed by the active lease at W0 time, install line (owner/host prep, apt is the only other route — script itself never apt-installs):
`sudo apt install shellcheck` (Ubuntu 24.04 arm64 ships 0.9.x — [UNVERIFIED exact version]).

Fallback wording the ledger MUST use if neither route runs (matches the script's own host note verbatim in spirit):
> "shellcheck binary host-side: ABSENT; uvx shellcheck-py route [used / also blocked by lease]. No shellcheck pre-commit hook exists (bootstrap header:29-31). Syntax gate satisfied via `bash -n scripts/bootstrap-gb300.sh` exit 0; full shellcheck deferred to [owner/host action]. **This is a recorded deviation, not a silent skip.**"

## STEP 6 — /platform-healthcheck (AFTER the gate + bring-up — skill invocation at W0 time, Task 8 Step 5)

Invoke the `platform-healthcheck` skill (`.claude/skills/platform-healthcheck/SKILL.md`), but with the project's podman adaptations — the skill's stock commands use bare `docker compose` (SKILL.md Quick Health Check block) which targets the WRONG daemon here:

| skill check | run as |
|---|---|
| `docker compose … ps` | `$COMPOSE ps --format "table {{.Name}}\t{{.Status}}\t{{.Health}}"` |
| prometheus targets | `curl -s localhost:9090/api/v1/targets \| jq -r '.data.activeTargets[] | "\(.labels.job): \(.health)"' \| sort` |
| `curl :8000/api/health` | `localhost:$API_PORT/api/system/health/ready` (the skill's `/api/health` path does not exist; real router is `/api/system/health*`, backend/api/routes/system.py:1260+1283-1284) |
| redis ping / pg_isready | `$COMPOSE exec -T redis redis-cli ping` / `$COMPOSE exec -T postgres pg_isready` (add `AUTH` if REDIS_PASSWORD set — compose redis has a password in .env; use `redis-cli -a "$REDIS_PASSWORD"`) |

**PASS looks like** (skill Completion Criteria, M1-deviated — record each row):
1. compose ps: ALL services `Up` + `healthy` (or `running` for the two by-design healthcheck-less exporters; foscam-init `Exited (0)`).
2. Prometheus: every target `health: "up"` EXCEPT exactly the M1 allowlist {ai-llm-metrics, triton-metrics, cadvisor, dcgm-exporter, hsi-health} (bootstrap:59) — a down job OUTSIDE that set is FAIL (same rule bootstrap gate §3 enforces, :370).
3. API: `/api/system/health/ready` → 200 (the skill's "API health endpoint returns success" row, M1-deviated per bootstrap:22-23); aggregate `/health` = 503-degraded recorded, not failed.
4. Redis `PONG`; PostgreSQL `accepting connections`.
5. No ERROR-level logs (already scanned in Step 4f).
6. GPU rows: N/A — spec §8 M1 scope.
Any FAIL → fix + RE-VERIFY per skill's verification loop; if not achievable, document per skill's fallback (failing checks / messages / what was tried / next steps) and do NOT mark W0 complete.

## STEP 7 — Ledger entry + commit (the ONLY repo writes W0 performs)

1. Fill `/tmp/wave3-drafts/w0-runbook/ledger-entry-template.md` → append as new `## M1 §6 CLOSE-OUT — gate 14 GREEN record (…)` section at END of `docs/plans/2026-09-12-context-map-doc-updates.md` (additive-only file; anchor = current last line "- **owner-memo-2026-09-14.md** … Hand to owner next touchpoint.").
2. Task 8 Step 4 commit (plan :543-549) — `.env` is gitignored, keep it that way: `git add scripts/bootstrap-gb300.sh docs/plans/2026-09-12-context-map-doc-updates.md && git commit` (script already tracked; include it only if Step 5 forced an edit).
3. Push `feat/context-map-2026-09-12` (direct-mode workspace; `origin` mirrored — `git remote -v` first).
4. Announce §9 release → W1 (T3 apply: /tmp/t3-draft/t3.patch) is unblocked; T4 gate "M1 record" satisfied.

## Collision notes vs queued drafts (checked at draft time)

- t3.patch touches `frontend/vite.config.ts`, `frontend/package.json`, `scripts/validate.sh`; t4/ci-frontend-honesty.patch touches `.github/workflows/ci.yml`; m3-static/ = drafts-only (no patch). **W0 writes exactly one repo file: `docs/plans/2026-09-12-context-map-doc-updates.md`** → zero file overlap with all three.
- Stacked `git apply --check` proofs (from repo root, at fa6521ea): see `patch-verify.md` next to this runbook. `ledger-addition.patch` is clean alone AND after t3+t4 are applied (disjoint files); the t3/t4 patches themselves are already known-clean at 6c0329b7 (ledger:2170) and unmodified by W0.
