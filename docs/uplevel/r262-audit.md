# Qwen-era merge audit (ruling 262)

The to-do sheet for ruling 262 (record 6257468143): the code the Qwen-era merges left on main,
read as it stands at the pinned SHA below, one entry per PR the census keeps. Each fix is the
owner's call (`fix`, `skip`, `later`), made later by the lane that owns the path. The cites stay
at the pinned SHA as main moves; the package that later fixes an item re-reads it on its own base.

- **Pinned SHA:** `41bc0fce71f85ddd2795b67b1e7597990d3a5603` (main at this claim; the merge of #7262)
- **Census window:** merged 2026-10-07T00:00Z to 2026-10-18T07:36Z
- **Census:** every PR merged to main in the window carrying a `lane:` label and no label
  containing `heavy`, plus the `[red-main]` PRs with no label at all; excluding the owner
  session's PRs (head branch starting `uplevel/owner-`, or a `Co-Authored-By: Claude Opus`
  commit trailer in the merge). A PR's files are its merge commit's diff against its first
  parent, kept if the same path exists at the pinned SHA. One class per PR, first match in the
  order production, test, tooling; Markdown skipped; everything else skipped.
- **Census command:** the `python3 - "$PIN" <<'PY'` script in `[r262]`'s block in
  `docs/uplevel/packages/docs.md` (run with `$PIN` = the pinned SHA).
- **Census control:** at `a3b1bd336` the owner session's run gave 228 PRs — 52 production, 110
  test, 6 tooling, 60 none.

## Census counts at the pinned SHA

Census re-run at the pin `41bc0fce7` with the `[r262]` command: **227 kept — 52
production, 109 test, 6 tooling, 60 none.** The owner's control at `a3b1bd336` gave 228
kept (52/110/6/60): re-running the census at the control SHA with the same script
reproduces 227/52/109/6/60 exactly, and a per-PR membership diff control→pin is empty —
the 110-vs-109 delta is in the classification of a PR both counts include, not a PR that
left the census. Batch placement (production order): batch 1 = positions 0-9
(#6862…#6925), batch 2 = 10-24, batch 3 = 25-39, batch 4 = 40-51 (12 PRs).

## Batches

Production first, then test, then tooling; within a class in PR-number order. Batch 1 is the
first ten production PRs; later batches are about fifteen PRs, one comment each. Each batch
records how many items a fresh unnamed refutation subagent (ruling 232) dropped.

| Batch | PRs                                                                                      | Items                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | Refuted                                                                                                                                                                  | Comment                                                                                                                                                                                                                 |
| ----- | ---------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1     | 6862, 6868, 6869, 6880, 6886, 6907, 6909, 6913, 6922, 6925                               | 12 (+ owner-seeded Q-000, outside the census window; see its section) (3 items re-attributed by mover-owns: Q-012 → #7230 batch 4; Q-014 + Q-015 → #6936 batch 2 — see below)                                                                                                                                                                                                                                                                                                                                                                                                                      | 0 (16/16 survived incl. Q-000)                                                                                                                                           | batch-1 comment on #7265; low items + Q-000 in compact table per owner continue (6266204180); ruled by 267 (r267a/r267b now, 11 lows later)                                                                             |
| 2     | 6927, 6930, 6931, 6936, 6943, 6950, 6959, 7002, 7015, 7019, 7031, 7038, 7039, 7041, 7044 | 45 (41 auditor candidates − 1 dedup (6927_c1 = Q-012's same defect) + 5 probe items from the two empty verdicts re-looked per ruling 232) + 1 supplementary outside the diff (7015 probe, DashboardPage.test.tsx:1091 — scope call for the coordinator, not in the count)                                                                                                                                                                                                                                                                                                                          | 1 (7002_c2, provenance mover-leg only — re-issued as Q-037 with corrected provenance; staleness and fix stand)                                                           | batch-2 comment on #7265; lows in the compact table per owner continue (6266204180); the seven mediums + re-issued Q-037 keep full templates                                                                            |
| 3     | 7052, 7070, 7074, 7077, 7086, 7088, 7103, 7114, 7125, 7135, 7139, 7145, 7146, 7156, 7157 | 62 rows from 69 auditor candidates + 5 deferred items Q-062..Q-066 (− 1 refuted genre-kill 7135_c4, − 1 dedup merge 7086-C1+C2, − 2 dedup twins 7157-C1/C5 resolved onto 7135-C1's verdict, − 1 batch-4 certification 7070-C2, − 2 record-only 7070-C7/C10, − 2 record-only 7114-C2/C3, − 1 re-assigned to #7222 7114-C4; Q-075 stays as a pointer row onto Q-093's fix; the phantom q067 was REFUTED and dies unnumbered — it was never a candidate row) + ~20 rows' dead coordinate cites across feature-inventory.md consolidate into the #7135-family and #7146-family items; enumerated there | 2 (phantom coordinate q067 — a `prod.yml:160` cite that exists nowhere at the pin, dies unnumbered; 7135_c4 genre-kill — ticked Done-when boxes are task specifications) | batch-3 comment on #7265; lows in the compact table per owner continue (6266204180); the two mediums (Q-093, Q-114) keep full templates; ruled 277 (record 6291992942): 62 rows, Q-094 dropped, targets/paths corrected |

## Batch 1 — per-PR verdicts

| PR    | Class      | Verdict                                                                                                                                                                       |
| ----- | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| #6862 | production | 2 items (Q-002, Q-005); 5 more stale cites first-moved by #7114, recorded on its batch; retirement-gate timeout = sandbox environment, no item                                |
| #6868 | production | 2 items (Q-003, Q-006 — Q-006 mover-owns)                                                                                                                                     |
| #6869 | production | no items                                                                                                                                                                      |
| #6880 | production | no items                                                                                                                                                                      |
| #6886 | production | 1 item (Q-004)                                                                                                                                                                |
| #6907 | production | no items (docstring cite drift attaches to #7114's batch)                                                                                                                     |
| #6909 | production | 1 item (Q-007)                                                                                                                                                                |
| #6913 | production | 1 item (Q-001 — pre-existing bug on a kept file)                                                                                                                              |
| #6922 | production | 5 items kept here (Q-008, Q-009, Q-010, Q-011, Q-013, all claim/low) + 3 found here but re-attributed by mover-owns: Q-012 → #7230 (batch 4), Q-014 + Q-015 → #6936 (batch 2) |
| #6925 | production | no items                                                                                                                                                                      |

## Items

Batch 1. Every item was verified at the pinned SHA before entering the sheet, and the refutation
pass (ruling 232) is complete: 16/16 verdicts in, none refuted; three items found while auditing
batch 1 were re-attributed by mover-owns to their first movers (Q-012 → #7230 batch 4; Q-014 +
Q-015 → #6936 batch 2 — full sections below, they rule with those batches). Per the owner's
continue (comment 6266204180): the low items and Q-000 rule from the compact table, with their
quoted lines and proof in the collapsed block under it; Q-001 (high) keeps the full template.
Owner decisions may arrive in bulk and are written into the rows. Ruling 267
(record 6266846674) ruled batch 1: Q-001 fix now as `[r267a]`, Q-004 fix now as
`[r267b]`, the 11 lows `later` (one cleanup PR per lane at the audit's end).

Batch 2. Every item was verified at the pinned SHA before entering the sheet, and the refutation
pass (ruling 232) is complete: 41 auditor candidates + 2 probes of empty verdicts = 43 verdicts,
1 refuted (7002_c2 — provenance mover-leg only; the staleness and fix stand and the item is
re-issued as Q-037 with corrected provenance), 1 deduped (6927_c1 is batch 1 Q-012's same
defect), 5 probe items found by the two ruling-232 probe re-looks (#6943 and #7015 — both
PROBE: CANDIDATES FOUND). Net items: 45, plus 1 supplementary outside the diff (7015 probe,
DashboardPage.test.tsx:1091 — a scope call for the coordinator, not in the count). Two
re-attributions landed INSIDE the batch by mover-owns and rule with their new owners' rows
(Q-016 → #6950, Q-031's block later moved by #6970 + B3.3 while #6959's own re-aim authored
the defect; Q-032 → r95 outside the census so it rules with #6959; Q-033's movers are
#7205/B3.1/r223, also outside). Per the owner's continue (comment 6266204180): the low items
rule from the compact table with their evidence in the collapsed block under it; the seven
mediums (Q-024, Q-032, Q-040, Q-052, Q-053, Q-054, Q-055) and the re-issued Q-037 keep full
templates after the details block. Owner decisions are pending and may arrive in bulk, written
into the rows.

| id    | class | path:line                                                                                                                                    | PR                      | wrong (one line)                                                                                                                                                                                                                                                    | fix (size, lane)                                                                                                                                                                                                               | owner                                                                                                                     |
| ----- | ----- | -------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------- |
| Q-000 | drift | docs/architecture/system-overview/configuration.md:281, docs/deployment/container-orchestration.md:526, docs/operator/service-control.md:464 | owner note (6266183856) | `ORCHESTRATOR_MAX_CONSECUTIVE_FAILURES` still documented in three env-var tables, but #7244 (merge 09e67114c) deleted `OrchestratorSettings.max_consecutive_failures` and `.env.example` lost its line (e630d4784)                                                  | delete the three rows. Size S; docs                                                                                                                                                                                            | ruled later (one cleanup PR per lane at the audit's end) — ruling 267, record 6266846674                                  |
| Q-002 | drift | docker-compose.ci.yml:190                                                                                                                    | #6862                   | the ci.yml comment cites `docker-compose.prod.yml:902` for the read-only-rootfs NOTE, but the NOTE sits at `:950-951` at the pin (`:902` is a disabled `cpus: '0.25'` line)                                                                                         | update the cite to `docker-compose.prod.yml:950`. Size S; ops                                                                                                                                                                  | ruled later (one cleanup PR per lane at the audit's end) — ruling 267, record 6266846674                                  |
| Q-003 | claim | monitoring/ai-pipeline-alerts.yml:20                                                                                                         | #6868                   | the rewritten header says "the five this file alerts on" but the file alerts on only four — no expression matches `vlm_circuit_open` (recorded at vlm_client.py:927, never alerted on)                                                                              | drop `vlm_circuit_open` from the list, or reword to say the file covers circuit-open only through the degraded-gauge proxy. Size S; ops                                                                                        | ruled later (one cleanup PR per lane at the audit's end) — ruling 267, record 6266846674                                  |
| Q-004 | test  | backend/tests/unit/services/test_verdict_engine_status.py:159                                                                                | #6886                   | the only test named for emit-failure containment cannot fail against removal of the swallowing `try/except` — the mocked RuntimeError surfaces only in an orphan task, so the docstring's "swallowed by design" clause is unpinned (mutation-proven by the refuter) | make the swallow observable — capture/gather the scheduled task and assert it completes without exception, or assert the structured "Failed to emit verdict-engine status event" log record. Size S; backend                   | ruled fix now as [r267b] (backend; first on backend's queue after the PR it holds; UR-52) — ruling 267, record 6266846674 |
| Q-005 | drift | docker-compose.prod.yml:573                                                                                                                  | #6862                   | the backend's vlm_assess comment still calls ai-vlm "the profiled ai-vlm service", but the same PR deleted the `vlm` profile from ai-vlm — no ai-vlm profile exists at the pin and the default `up` starts it                                                       | drop "profiled" from the comment ("the default ai-vlm service"). Size S; ops                                                                                                                                                   | ruled later (one cleanup PR per lane at the audit's end) — ruling 267, record 6266846674                                  |
| Q-006 | drift | monitoring/prometheus_rules.yml:4                                                                                                            | #6868 (mover-owns)      | the prometheus-rules header cites `docker-compose.prod.yml:1017` for the bind-mount line, but at the pin the mount sits at `:1098` (`:1017` is a frontend healthcheck URL); cite true at #6862's merge, first broken by #6868                                       | update the cite to `docker-compose.prod.yml:1098`. Size S; ops                                                                                                                                                                 | ruled later (one cleanup PR per lane at the audit's end) — ruling 267, record 6266846674                                  |
| Q-007 | claim | frontend/src/hooks/useVerdictEngineStatus.ts:44                                                                                              | #6909                   | the `enabled` option's docstring claims it controls the WebSocket connection, but `enabled=false` still opens the /ws/system socket — only the reconnect flag and the readiness poll are gated                                                                      | skip the useWebSocket subscription when enabled is false, or reword the docstring to say enabled gates reconnection and polling. Size S; frontend                                                                              | ruled later (one cleanup PR per lane at the audit's end) — ruling 267, record 6266846674                                  |
| Q-008 | claim | backend/tests/unit/core/test_nginx_credential_forwarding.py:3                                                                                | #6922                   | the docstring asserts B1.5's gate "reads exactly two client credentials on the proxied path", but at the pin the gate reads five credential kinds, all arriving on the proxied path (false even at its own cited baseline e9ec74ef)                                 | rewrite :3-4 to the pin's credential set, or scope the sentence to the credential nginx forwarding is pinned for and state the gate reads others (the :87 message may stay, scoped to its HTTP test). Size S; backend          | ruled later (one cleanup PR per lane at the audit's end) — ruling 267, record 6266846674                                  |
| Q-009 | claim | backend/tests/security/test_docker_compose_security.py:401                                                                                   | #6922                   | three present-tense ai-llm census prose claims are false at the pin: the tracked set greps 7 matching lines (not "two"), the live key sits at `prod.yml:305` (not `:283`), and `prodshape.yml:164` also carries the exact key                                       | update :400-403, :559-566 and :580 to the pin counts and coordinates, or reword to state the parsed-key rule without pinning a volatile count and line number. Size S; backend                                                 | ruled later (one cleanup PR per lane at the audit's end) — ruling 267, record 6266846674                                  |
| Q-010 | claim | frontend/src/services/api.auth-seam.test.ts:20                                                                                               | #6922                   | the fixture comment cites the gate's 401 body as `backend/api/middleware/auth.py:405-408` with no dating frame, but at the pin that span is the WebSocket subprotocol extraction and the JSON refusal body sits at `:692-696` (body text itself still exact)        | repoint the cite to auth.py:692-696, or drop the line numbers and name the refusal body. Size S; frontend                                                                                                                      | ruled later (one cleanup PR per lane at the audit's end) — ruling 267, record 6266846674                                  |
| Q-011 | claim | frontend/src/services/api.ts:2928                                                                                                            | #6922                   | nine comment blocks assert media/snapshot/detection endpoints are "exempt from API key authentication in the backend middleware", but OPEN_PATHS holds none of those paths — under EXPOSE_LAN they are gated and work via the same-origin session cookie            | rewrite the nine sites to the pin behaviour, plus the six backend route-docstring sites carrying the same claim (detections.py :170/:644/:1221/:1399/:1546, cameras.py :1075) found by the refuter. Size S; frontend + backend | ruled later (one cleanup PR per lane at the audit's end) — ruling 267, record 6266846674                                  |
| Q-013 | claim | frontend/src/contexts/AuthContext.test.tsx:356                                                                                               | #6922                   | two inline cites give pin-stale coordinates for claims whose substance is still true — logout cited at AuthContext.tsx:175-178 (pin: :217-221) and the assignment at :152 (pin: :194, now the setupRequired-guarded form)                                           | repoint :356 to AuthContext.tsx:217-221 and :361 to AuthContext.tsx:194, and update the :361 quote to the guarded form the pin ships. Size S; frontend                                                                         | ruled later (one cleanup PR per lane at the audit's end) — ruling 267, record 6266846674                                  |

### Q-001 · bug · high · frontend/src/hooks/useServiceStatus.ts:80 · #6913

- Wrong: the hook's service-name allowlist drops every `service_status` broadcast except
  `redis`/`rtdetr`/`nemotron`, but at this pin the monitor broadcasts `yolo26` (the only
  probe it runs) and orchestrator container names (`ai-vlm`, `ai-gateway`, `go2rtc`, …) —
  so the UI never sees the detector's health, and the `rtdetr`/`nemotron` slots can never
  populate.
- Evidence: `frontend/src/hooks/useServiceStatus.ts:80` at the pin reads
  `const SERVICE_NAMES: ServiceName[] = ['redis', 'rtdetr', 'nemotron'];` and
  `:91-93` `function isServiceName(value: unknown): value is ServiceName { return typeof
value === 'string' && SERVICE_NAMES.includes(value as ServiceName); }`. The only
  monitor probe is `backend/main.py:727-735` `return [ ServiceConfig( name="yolo26", …`
  (block spans :727-735; refuter's precision correction), plus two emitters the
  original read missed — `backend/services/worker_supervisor.py:750` broadcasts
  `service="worker:<name>"` and `backend/services/websocket_emitter.py:461`
  forwards SERVICE_STATUS_CHANGED payloads through the same guard — and the
  container broadcasts' status values (running/stopped/disabled) are also
  rejected by the hook's `isServiceStatusType` (`:98-107`), so a scope fix
  touches both lists. Refuted=false; refuter found no escape path (zero
  backend-wide `rtdetr` occurrences at the pin; no emitter ever satisfies the
  allowlist).
  (one probe; the R8 comment at `:724-726` records nemotron's retirement). The monitor
  broadcasts `{"service": service.name}` (`backend/services/health_monitor.py:353-361`);
  `backend/services/event_broadcaster.py:841` `broadcast_service_status` publishes it
  (schema `backend/api/schemas/websocket.py:402-412` accepts any `service: str`).
  `backend/services/container_orchestrator.py:222-241` `_broadcast_status` broadcasts
  container names. Consumers: `frontend/src/components/layout/Layout.tsx:37,157`
  (`useServiceStatus` → `ServiceStatusAlert`), `frontend/src/components/system/
ServicesPanel.tsx:363,662` (`hasUnhealthy` → panel badge). Provenance: the guard was
  born 2025-12-26 (c790a3781); rtdetr→yolo26 renamed 2026-01-26 (ed218ca76, #4442);
  nemotron monitoring retired 2026-09-28 (b3fe4dad4) — all pre-window. #6913 is the only
  census PR whose kept files include the hook; its own edit to the file is formatting
  (prettier reflow), not the guard. Item attaches as a pre-existing bug on a kept file.
- Fix: update `SERVICE_NAMES` (or widen the guard) to the broadcast population — replace
  `rtdetr` with `yolo26`, drop `nemotron`, and decide whether container-name statuses are
  in scope; sync the alert's label map. Size M; owner: frontend.
- Ruling 267 (record 6266846674): ruled fix now as `[r267a]` (frontend).
  The fix: the hook accepts the names and status values the backend actually broadcasts, and
  drops the retired names. The health monitor's probes (`backend/main.py`, today `yolo26`) are
  in scope. The container orchestrator's names and the worker supervisor's `worker:<name>`:
  frontend measures where else each is shown, and the PR states whether it is in scope and
  why. Both broadcast through the same guard. Done when: a test feeds each in-scope emitter's
  real payload shape through the hook, and an unhealthy `yolo26` lights `ServiceStatusAlert`.
  The backend's payloads do not change. Flags: none. First on frontend's queue, after the PR
  it holds (UR-52).
- Owner: [r267a] — fix now (ruling 267).

<details>
<summary>Batch-1 low-item evidence — quoted lines, proof, refutation verdicts (Q-000, Q-002…Q-011, Q-013)</summary>

### Q-000 · drift · low · three docs paths (owner-seeded) · owner note, not a census PR

- Provenance: seeded by the owner (comment 6266183856 on #7265, 2026-10-19T11:30Z) with the
  ruling-262 pointer footer; it is from OUTSIDE the census window (#7244 / B3.3 merged
  2026-10-18T23:06Z) and rides this batch's pass so the owner rules it with the others.
  Lane: docs (the owner's fix text says so).
- Wrong: `ORCHESTRATOR_MAX_CONSECUTIVE_FAILURES` is still documented in three places, but
  the setting no longer exists — B3.3 (#7244, merge 09e67114c) deleted
  `OrchestratorSettings.max_consecutive_failures` from `backend/core/config.py` (the
  "Self-healing limits" field, 5, ge=1 le=50), and `.env.example` lost its line at
  e630d4784 ("[B3.3] UR-89 fixes: drop the dead ORCHESTRATOR_MAX_CONSECUTIVE_FAILURES doc
  block").
- Where (at the pins `41bc0fce7` and `a3b1bd336`, grep-identical):
  - `docs/architecture/system-overview/configuration.md:281`
  - `docs/deployment/container-orchestration.md:526`
  - `docs/operator/service-control.md:464`
- Evidence (lane-verified at the claim pin): `git grep -n ORCHESTRATOR_MAX_CONSECUTIVE_FAILURES
41bc0fce7` lists only those three doc lines; no `consecutive_failures` field in
  `backend/core/config.py` at the pin; the #7244 diff deletes the field verbatim; the
  sibling rows in all three tables (`ORCHESTRATOR_HEALTH_CHECK_INTERVAL`,
  `ORCHESTRATOR_STARTUP_GRACE_PERIOD`, `ORCHESTRATOR_RESTART_BACKOFF_BASE`, …) map to live
  fields at config.py:141-166 — only this row is dead.
- Fix: delete the three rows. Size S. Owning lane: docs.
- Owner: ruled later (ruling 267): one cleanup PR per lane at the audit's end.
- Refuted=false. Refuter verified every leg at both pins: the needle census at 41bc0fce7 AND
  a3b1bd336 returns exactly the three named doc rows, byte-identical at both SHAs;
  `consecutive` is absent from config.py at both pins and `max_consecutive` repo-wide hits
  only the three doc rows (plus an unrelated synthbench MAX_CONSECUTIVE_TIMEOUTS constant) —
  zero in backend/, test or non-test; the deletion provenance is exact (merge 09e67114c =
  PR #7244 removes `max_consecutive_failures: int = Field(5, ge=1, le=50, …)` under
  "# Self-healing limits" verbatim; e630d4784 removes the 4-line .env.example block and
  touches nothing else doc-wise), and 09e67114c is an ancestor of both pins (the deletion
  is already in both pin trees, which is what makes the rows stale there); the sibling
  control holds — all seven named siblings are real Fields in OrchestratorSettings
  (env_prefix ORCHESTRATOR_, config.py ~115-166), so this is drift, not a whole-stale-table;
  nothing at the pin reads ORCHESTRATOR_MAX_CONSECUTIVE_FAILURES from the environment (no
  os.environ/getenv hit, no compose passthrough, no test); no dating qualifier near any row;
  no later PR fixed the rows (all three doc blobs byte-identical from the merge through both
  pins). The Markdown exclusion does not apply: "Markdown is skipped" in the census command
  is a PR-file classification rule for which PRs enter the census, not an item exclusion —
  the drift class explicitly covers "docs or config naming a setting … that no longer
  exists", and the real exclusions are taste/cite-density/line-length/lint-enforced only.
  Corrections: (1) the rows' described BEHAVIOR is not entirely fictional —
  failure-before-disable with per-category defaults (AI 5, infrastructure 10) is still real
  via CATEGORY_DEFAULTS at backend/services/orchestrator/models.py:22 and the
  `orchestrator.max_failures` compose label/healthcheck-retries path at
  compose_parser.py:236-239; what is dead is the env-var knob the Variable column names —
  the rows sit in env-var tables and promise a tunable that no longer exists (previously
  ge=1 le=50 via the deleted Field). Drift per the sheet's own definition stands.
  (2) The refutation prompt's date question read backwards — the #7244 merge (23:06Z) is
  before, not after, both pins were cut; that ancestry is exactly what the item requires
  (my sheet entry said "after both pins", which is wrong — the refuter's framing is the
  correct one). (3) Deleting the service-control row removes that file's only
  CATEGORY_DEFAULTS mention; acceptable as written since container-orchestration.md
  documents the same defaults in a dedicated section. Fix stands as written.

### Q-002 · drift · low · docker-compose.ci.yml:190 · #6862

- Wrong: the ci.yml comment cites `docker-compose.prod.yml:902` for the read-only-rootfs
  NOTE, but at the pin the NOTE sits at `prod.yml:950-951` and `:902` is a commented-out
  `cpus: '0.25'` line inside a disabled `deploy.resources` block.
- Evidence: `docker-compose.ci.yml:190-193` at the pin:
  `# read_only NOT used — same NOTE as docker-compose.prod.yml:902: the / # image's
entrypoint sed -i's /etc/nginx/conf.d/default.conf at startup / # and dies on a
read-only rootfs (...)`. The NOTE at the pin is `docker-compose.prod.yml:950` `#
NOTE: read_only not used — nginx entrypoint uses sed -i on /etc/nginx/conf.d/default.conf`
  and `:951` `# and generates SSL certificates at runtime. These require a writable root
filesystem.`; `prod.yml:902` at the pin is `#         cpus: '0.25'`. History: at
  #6862's first parent the cite already read `:897` while the NOTE sat at `:894` (3 lines
  stale pre-window); #6862's own diff renumbered both by +5 (cite :897→:902, NOTE
  :894→:899), preserving the offset — so this is pre-existing drift the PR touched but
  did not create. Later merges moved the NOTE 899→901→904→906→921→937 (#7114's merge;
  the :921→:937 shift authored in r162 branch commit ac84fd7d9) then :950 (#7222's
  merge, r243's 51a2738f0); the cite text never changed again. Refuted=false;
  refuter verified digit-for-digit including a repo-wide pickaxe (the ':902' cite
  string was never edited after #6862).
- Fix: update the cite to `docker-compose.prod.yml:950`. Size S; owner: ops.
- Owner: ruled later (ruling 267): one cleanup PR per lane at the audit's end.

### Q-003 · claim · low · monitoring/ai-pipeline-alerts.yml:20 · #6868

- Wrong: the rewritten header says "The VLM-path values that survive are the five this
  file alerts on", but the file alerts on only four of them — no expression anywhere in
  the file matches `vlm_circuit_open`, which is recorded (`vlm_client.py:927`) and
  described but never alerted on.
- Evidence: `monitoring/ai-pipeline-alerts.yml:20-22` at the pin: `# to "other". The
VLM-path values that survive are the five this file alerts on / # (vlm_transport_error,
vlm_http_error, vlm_schema_invalid, vlm_circuit_open, / # vlm_verification_failed)
PLUS the reason codes B1.1 added to the allowlist:`. The file's only `error_type`
  expressions are `:150` `sum(rate(hsi_pipeline_errors_total{error_type="vlm_verification_failed"}[30m]))`
  and `:173` `sum(increase(hsi_pipeline_errors_total{error_type=~"vlm_transport_error|vlm_http_error|vlm_schema_invalid"}[10m])) > 30`;
  the circuit-open condition is alerted only via the proxy gauge `:195` `hsi_ai_service_degraded{service="ai-vlm"} == 1`
  (under the comment `:190-191` "counted as / # error_type=\"vlm_circuit_open\"").
  `grep -n circuit` in the file at the pin matches only :21, :191, :203 (all comments).
  The value is recorded at `backend/services/vlm_client.py:927`
  `record_pipeline_error("vlm_circuit_open")`. Corroboration: found independently by a
  fresh subagent auditing #6868 (ruling 232) and by my own read. 6868's diff rewrote
  exactly this sentence (its base wording said "so these alerts match on the five").
  Refuted=false: refuter swept all 8 `expr` blocks in the 230-line file (:52, :70, :83,
  :111, :150, :173, :195, :216) — only four of the five values appear; repo-wide git
  grep at the pin finds no monitoring file matching `vlm_circuit_open`; the :195 gauge
  (VlmServiceUnhealthy) is a different metric and the file's own comments (:190-191)
  distinguish the gauge projection from the error_type count. Attribution: the quoted
  sentence is #6868's authored rewrite (6d2536ad0, branch side); the same falsehood
  predates it in different words (dcaf21a74, PR #6773, "so these alerts match on the
  five"), so #6868 owns the wording it restated. Sentence byte-identical from #6868
  through the pin (#7205 left it unchanged). Refuter precision: :203 is the alert's
  description annotation (a YAML value, not a comment; :21/:191 are comments — all
  non-executable prose).
- Fix: drop `vlm_circuit_open` from the "five this file alerts on" list, or reword to say
  the file covers circuit-open only through the degraded-gauge proxy. Size S; owner: ops.
- Owner: ruled later (ruling 267): one cleanup PR per lane at the audit's end.

### Q-004 · test · low · backend/tests/unit/services/test_verdict_engine_status.py:159 · #6886

- Wrong: the only test named for emit-failure containment cannot fail against removal of
  the `try/except` that swallows the emit exception — `observe()` schedules
  `_emit_transition` via `asyncio.create_task` and returns first, so the mocked
  RuntimeError surfaces only in an orphan task, never in the test frame, leaving the
  docstring's "its exception is swallowed by design" clause unpinned.
- Evidence: test at the pin `:159-169` `test_emit_failure_does_not_break_the_probe`:
  `:164` `ws_emitter.emit = AsyncMock(side_effect=RuntimeError("ws down"))`, `:167-169`
  `snap = tracker.observe(_DOWN_DETAILS)` / `await asyncio.sleep(0)  # the task raises
inside; must not surface` / `assert snap.state == VerdictEngineState.UNAVAILABLE`. The
  guarded block it names: `backend/services/verdict_engine_status.py:285-291` `try: await
self._emitter.emit(WebSocketEventType.SYSTEM_VERDICT_ENGINE_STATUS_CHANGED, payload) /
except Exception as e: logger.error(f"Failed to emit verdict-engine status event: {e}",
exc_info=True)`. Proof the test cannot fail: `observe()` → `_schedule_transition_event`
  → `asyncio.get_running_loop().create_task(...)` returns before the coroutine runs
  (`verdict_engine_status.py:245-255`), so removing the `except` lets the RuntimeError
  kill only the background task — asyncio's default handler logs "Task exception was
  never retrieved" at GC and does not raise into the awaiting test (no loop exception
  handler in `backend/tests/conftest.py`; pytest config plain `asyncio_mode = "auto"`,
  `pyproject.toml:570`). Both files blob-identical 6886-merge → pin (service
  `29308c6b04…`, test `810b438b78…`), so no later PR fixed it. Refuted=false, proven
  empirically: the refuter deleted the try/except in a scratch worktree at the pin and ran
  the named test and its file green against the mutation (1 and 12 passed), and the other
  file touching the tracker (`backend/tests/integration/
test_websocket_system_channel_delivery.py`) passes both mutated and pristine, so nothing
  else pins the swallow; docstring clause sits at :162-163, the schedule call at :225 with
  create_task :246-253.
- Fix: make the swallow observable — capture the scheduled task (or gather it) and assert
  it completes without exception, or assert the structured "Failed to emit verdict-engine
  status event" log record — so removing the `except` turns this test red. Size S;
  owner: backend.
- Ruling 267 (record 6266846674): ruled fix now as `[r267b]` (backend). The test
  becomes able to fail: it can capture the scheduled emit task and assert that it finishes
  without an exception, or assert the "Failed to emit verdict-engine status event" log
  record. Done when: the PR shows that deleting the `try/except` at
  `backend/services/verdict_engine_status.py:285-291` turns the test red. Flags: none.
  First on backend's queue, after the PR it holds (UR-52).
- Owner: [r267b] — fix now (ruling 267).

### Q-005 · drift · low · docker-compose.prod.yml:573 · #6862

- Wrong: the backend's vlm_assess client-wire comment still calls ai-vlm "the profiled
  ai-vlm service", but #6862 deleted the `vlm` profile from the ai-vlm service in the
  same PR — no ai-vlm profile exists at the pin and the default `up` starts it.
- Evidence: `docker-compose.prod.yml:573` at the pin: `# PIPELINE_MODE=vlm (above) makes
the backend dial the profiled ai-vlm / # service, ...`. 6862's own diff deleted
  `-    profiles: / -      - vlm` from the ai-vlm block (the hunk sits directly under the
  `CUDA_ARCHITECTURES` line); the ai-vlm block at the pin (`:163` `ai-vlm:`) has no
  `profiles:` key, and the only remaining `profiles:` keys (`:306`, `:1564`) belong to
  `ai-llm-vllm` and `dcgm-exporter`. The same PR's rewritten header at `:148-149` says
  "It ships in the default `up` (O1.3, UR-18): the verdict engine starts with the rest of
  the stack." `grep -n profiled` in the file at the pin matches only :573. At 6862's first
  parent the comment (then at :539) was true: ai-vlm carried `profiles: [vlm]` (:154-155).
- Fix: drop "profiled" from the comment ("the default ai-vlm service") to match the O1.3
  state the same file documents. Size S; owner: ops.
- Owner: ruled later (ruling 267): one cleanup PR per lane at the audit's end.
- Refuted=false. Refuter verified all cites at the pin; the whole ai-vlm block (:163-302)
  carries no `profiles:` key, the only two are :306 (ai-llm-vllm) and :1564
  (dcgm-exporter), and no `- vlm` value exists anywhere in the file; no other mechanism
  gates ai-vlm (the marker include declares no services; fake-ai/ci/test/engine composes
  name no profiles). The comment is byte-identical pre/post merge (md5 aebb5101c99f…) —
  6862 did NOT rewrite this line, so the drift is a stale leftover the PR failed to
  update while actively rewording sibling profile language in the same header; its own
  sweep test scopes to living docs and never covers compose comments. Alternative
  reading tested and rejected: `profiled` ≠ Pyroscope-profiled (the file's own
  vocabulary and the connection-refused narrative only fit the profile-gate reading).

### Q-006 · drift · low · monitoring/prometheus_rules.yml:4 · #6868 (mover-owns; cite true at #6862's merge)

- Wrong: the prometheus-rules header cites `docker-compose.prod.yml:1017` as the
  bind-mount line, but at the pin the mount sits at `prod.yml:1098` and `:1017` is a
  frontend healthcheck URL.
- Evidence: `monitoring/prometheus_rules.yml:4` at the pin: `# as
/etc/prometheus/prometheus_rules.yml (docker-compose.prod.yml:1017) and it`. The mount
  at the pin is `prod.yml:1098` `./monitoring/prometheus_rules.yml:/etc/prometheus/prometheus_rules.yml:ro,z`;
  `prod.yml:1017` at the pin is `'http://localhost:${FRONTEND_INTERNAL_PORT:-8080}/health',`
  (frontend healthcheck). Mover trace across the census production PRs keeping
  `docker-compose.prod.yml`: mount 1017 (#6862 merge, cite true) → 1022 (#6868, **first
  mover**) → 1024 (#6907) → 1031 (#6925) → 1063 (#6930) → 1069 (#6950) → 1085 (#7114) →
  1098 (#7222). #6868 is batch 1, so the item is batch 1's (mover-owns; cite true at the
  keeping PR's merge, first broken by a batch-1 PR). The citing file itself was last
  touched by #6862 (its own diff renumbered the cite 1012→1017, true at its merge).
- Fix: update the cite to `docker-compose.prod.yml:1098`. Size S; owner: ops.
- Owner: ruled later (ruling 267): one cleanup PR per lane at the audit's end.
- Refuted=false. Refuter re-measured the whole chain and confirmed every number:
  pre-#6862 1012 → #6862 (1e959ccce) 1017, cite true at its merge → #6868 (8169d5c0b)
  1022, **first mover proven by blob identity** (prod.yml blob 99351e71f identical at
  #6862 and #6868^1; the merge's first-parent diff adds 5 lines to the AI_VLM comment
  block near :552 — branch commits 3dedfb812/16060cb6f expanding the read-budget
  comment) → 1024 (#6907) → 1031 (#6925) → 1063 (#6930) → 1069 (#6950) → 1085 (#7114)
  → 1098 (#7222) → pin 1098. Cite text unedited since #6862 (blob 20f33d9c7 identical
  at every chain merge, at #7205, and at the pin). :1017 at the pin is the frontend
  healthcheck URL, nothing prometheus-adjacent; prodshape.yml has no prometheus_rules
  mount, so the cite can only mean the 1098 mount. Annotations: the repo is shallow
  with boundary at d6344e031 (#7205), which is why #7205 appears in the file's log
  without an edit; and `monitoring/prometheus-rules.yml` (hyphenated, a different
  file) is mounted at prod.yml:1099 — the underscore form in the cite unambiguously
  refers to the 1098 mount.

### Q-007 · claim · low · frontend/src/hooks/useVerdictEngineStatus.ts:44 · #6909

- Wrong: the `enabled` option's docstring claims it controls the WebSocket connection, but
  `enabled=false` still opens the /ws/system socket — only the reconnect flag and the
  readiness poll are gated.
- Evidence: at the pin `:43-47` `Whether to enable the WebSocket connection and readiness
polling. / @default true / enabled?: boolean;`; `:254-272` both the enabled and disabled
  branches pass the same url/protocols/onMessage to useWebSocket and differ only in
  `reconnect: true` vs `reconnect: false`; `useWebSocket.ts:200-206` runs `connect()` on
  mount unconditionally, and `webSocketManager.ts:282-290` opens the connection on every
  subscribe with no OPEN/CONNECTING socket. The hook's only production caller is
  `Layout.tsx:40`, which never passes `enabled:false`, so no behaviour changes today —
  the defect is the docstring's claim. Found by the fresh #6909 audit subagent (ruling 232);
  all six kept test files read, the four merge-to-pin test diffs attributed to later PRs.
- Fix: either skip the useWebSocket subscription when enabled is false, or reword the
  docstring to say enabled gates reconnection and polling rather than the connection itself.
  Size S; owner: frontend.
- Owner: ruled later (ruling 267): one cleanup PR per lane at the audit's end.
- Refuted=false. Refuter verified every cite at the pin: the ternary only selects options
  (both branches pass the same url/protocols/onMessage; disabled adds reconnect:false and
  defaults the rest), `useWebSocket.ts:200-206` runs connect() on mount with no gate, and
  `webSocketManager.ts:282-290` opens on subscribe whenever none is OPEN/CONNECTING — its
  connect() never consults config.reconnect (reconnect is read only in the onclose handler
  at :594/:630). Only production caller `Layout.tsx:40` calls useVerdictEngineStatus() with
  no options; repo-wide grep at the pin finds no other caller (banner/provider hits are
  comments, index.ts a re-export). Born in #6909: the hook file is new in merge 34f66b38's
  diff and byte-identical at the pin, so no later PR fixed it. Escapes rejected: reading
  "enable the connection" as "enable the feature" doesn't rescue the false half (the
  interface documents isConnected as "Whether the /ws/system socket is connected"); the
  readiness-poll half being true does not rescue the false main clause. Path corrections:
  webSocketManager.ts lives at frontend/src/hooks/, Layout.tsx at
  frontend/src/components/layout/; the `enabled:` at Layout.tsx:60 belongs to the shortcuts
  hook, not useVerdictEngineStatus.

### Q-008 · claim · low · backend/tests/unit/core/test_nginx_credential_forwarding.py:3 · #6922

- Wrong: the docstring asserts B1.5's gate "reads exactly two client credentials on the
  proxied path: the session_id cookie and the api-key.<key> WebSocket subprotocol", and the
  `:87` assert message repeats "reads only the session_id cookie and the API key". At the pin
  the gate reads five credential kinds — session cookie, ?token= JWT, ?api_key= query param,
  api-key.* subprotocol, and x-api-key header on HTTP — and all five arrive on the proxied
  path. False even at its own cited baseline e9ec74ef, where the ?token= read already exists.
- Evidence: pin `:3-4` and `:87` as quoted. Pin gate reads: `backend/api/middleware/auth.py:501`
  cookie, `:502` token, `:396` api_key, `:405` subprotocol, `:576` x-api-key. At e9ec74ef the
  token read also exists (`auth.py:258`). Test file blob-identical merge→pin
  (2ac74aaf143d…), so the false claim shipped in the PR's own content.
- Fix: rewrite :3-4 and the :87 message to the pin's credential set, or scope the sentence to
  the credential nginx forwarding is pinned for and state the gate reads others.
  Size S; owner: backend.
- Owner: ruled later (ruling 267): one cleanup PR per lane at the audit's end.
- Refuted=false. Refuter verified all five reads as live code at the pin (cookie :501,
  ?token= :502 in authenticate_websocket called from websocket.py:501/:729 on proxied
  /ws/events and /ws/system, ?api_key= :396, subprotocol :402-405, x-api-key :576),
  OPEN_PATHS :56-69 exempting only health/auth, and the false count holding at the cited
  baseline e9ec74ef too (cookie :257, token :258, api_key :175, subprotocol :181-185,
  x-api-key :296). The file was introduced by #6922 itself (absent at 3dab5c557^1,
  present at blob 2ac74aaf at 3dab5c557^2), so the falsehood shipped in the PR's own
  content. Precision corrections: the :87 assert message annotates the /api (HTTP) test,
  and on HTTP the gate reads exactly two kinds (session cookie :609 + x-api-key :576 via
  _presented_api_key's early-return) — that message is defensible in its own scope; the
  standing falsehood is the module docstring :3-4, whose "proxied path" covers /api and
  /ws (the file's own _proxied_credential_blocks includes /ws). Also: the ?token= read
  belongs to authenticate_websocket (called by the /ws routes), so the middleware gate
  alone reads four kinds — either count still refutes "exactly two". Method caveat:
  the history graph is grafted (d6344e031's parents resolve via cat-file but not ^1;
  `git show --stat` displays the whole tree as insertions), so the blob-identity claim
  rests on endpoint content hashes, which are graft-proof. Fix amended: correct :3-4;
  the :87 message may stay or be clarified to name its HTTP scope.

### Q-009 · claim · low · backend/tests/security/test_docker_compose_security.py:401 · #6922

- Wrong: three prose claims about the ai-llm census are false at the pin. (1) `:400-403`
  "`grep -c ai-llm` over this file set returns two hits -- one sentence of retirement prose
  (config/docker-compose.gb300.yml:43) and the live prefixed key ai-llm-vllm:
  (docker-compose.prod.yml:283)" — the tracked set at the pin yields 7 matching lines, and
  `prod.yml:283` is deploy.resources content (`memory: 10G`), the key having moved to
  `prod.yml:305`. (2) `:559-560`/`:566` "`ai-llm` is still WRITTEN in this file set, twice"
  and "prod:283 is the live `ai-llm-vllm:` key" — 7 sites, key at `:305`. (3) `:580` the
  scan's skip comment "the live prefixed key (prod only, today)" —
  `scripts/uplevel/docker-compose.prodshape.yml:164` also carries the exact key. The
  executable scans still pass (parsed keys, not greps, decide); this is prose staleness.
- Evidence: pin counts — gb300.yml:43 (1), prod.yml:305 (1), b14-real.yml:65 comment (1),
  prodshape.yml :37/:161/:162 comments + :164 key (4) = 7. At the merge tree prod.yml:283
  was `ai-llm-vllm:` (`git show 3dab5c557:docker-compose.prod.yml` line 283) — the docstring
  was written against that layout. Test blob differs merge→pin (the [r243] marker-content
  additions grew the tracked set and moved the key but left the two/three-hit prose).
- Fix: update :400-403, :559-566 and :580 to the pin counts and coordinates, or reword to
  state the parsed-key rule without pinning a volatile count and line number.
  Size S; owner: backend.
- Owner: ruled later (ruling 267): one cleanup PR per lane at the audit's end.
- Refuted=false. Refuter verified all three claims false at the pin: the grep over the
  12-file `TRACKED_COMPOSE_FILES` tuple (:264-294) yields exactly 7 lines (gb300.yml:43,
  prod.yml:305 key, b14-real.yml:65, prodshape.yml :37/:161/:162 comments + :164 key);
  prod.yml:283 at the pin is deploy.resources content with the key at :305, and was the
  key at :283 in merge tree 3dab5c557; prodshape.yml:164 carries the exact key and
  prodshape is enrolled in the tuple (:293). Escapes all fail: the prose is present
  tense ("returns", "is still WRITTEN", "today") with no as-of frame; "this file set"
  contextually means the tuple (class docstring :391 "every tracked compose file", both
  loops iterate it), and even under a narrower gb300+prod reading the prod:283 cite is
  stale at the pin; the executable tests parse service keys and still pass (comments
  and exact key lines are skipped). Freshness: merge→pin blob diff (e330139e→06ece40d)
  contains only [r243] marker additions; the prose lines are byte-identical between the
  two trees — no later PR fixed them. Corrections: prod.yml:283 at the pin is `limits:`
  ("memory: 10G" sits at :285) — both deploy.resources content, substance unchanged.
  Sharper still: at the merge tree the grep over its own tuple already yielded 3 hits
  (b14-real was enrolled at merge), so "two hits" was inconsistent with the file set
  even at write time.

### Q-010 · claim · low · frontend/src/services/api.auth-seam.test.ts:20 · #6922

- Wrong: the fixture comment cites the gate's 401 body as
  `backend/api/middleware/auth.py:405-408: 401 {"detail": "Authentication required"}` with no
  dating frame, but at the pin `:405-407` is the WebSocket subprotocol extraction and the
  JSON refusal body sits at `:692-696`. The body text is still exactly what the fixture
  builds; only the coordinate pointer lands far from its object.
- Evidence: pin `:19-20` as quoted; pin `auth.py:405` = `if stripped_protocol.startswith("api-key."):`,
  refusal body at `:692-694`. At e9ec74ef the body was exactly at `:405-408` — the cite was
  written against the pre-PR layout. File blob-identical merge→pin (0b759dcbdcff…).
- Fix: repoint the cite to auth.py:692-696, or drop the line numbers and name the refusal
  body/constant. Size S; owner: frontend.
- Owner: ruled later (ruling 267): one cleanup PR per lane at the audit's end.
- Refuted=false. Refuter verified: the comment (:18-21) is verbatim with no dating frame —
  the file's own :4 dates its sibling api.ts cite ("at origin/main e9ec74ef"), so the
  author's dating convention exists and this cite lacks it; at the pin auth.py:405 is the
  subprotocol extraction and the JSONResponse spans :692-695 (content at :694, await at
  :696); at e9ec74ef the body sat exactly at :405-408, and the authoring commit aa1e50734
  has an empty auth.py diff vs e9ec74ef. Escapes fail: no qualifier or past-tense framing
  (unlike the sibling cite), and the comment reads as current-state documentation, not
  fixture provenance — the fixture builds the same body text, so nothing anchors the
  pointer to a snapshot. Provenance sharpened, not refuted: the body was still at
  :405-407 at #6922's merge too, so the cite was accurate when merged; the displacement
  to :692 came from the r213 wave (shallow-boundary d6344e031, #7205 — labeled `heavy`,
  excluded from the census) between merge and pin. The defect is therefore stale-by-
  later-non-census-drift, not wrong-when-merged — the comment was never corrected as the
  code moved under it — and since the mover is outside the census, the item stays with
  #6922 as the census PR keeping the citing file. auth.py itself changed 329/42 between
  merge and pin.

### Q-011 · claim · low · frontend/src/services/api.ts:2928 · #6922

- Wrong: nine comment blocks assert media/snapshot/detection endpoints are "exempt from API
  key authentication in the backend middleware" (listing /api/media/{path},
  /api/detections/{id}/image, /api/detections/{id}/video, /api/cameras/{id}/snapshot). At the
  pin the middleware exemption set OPEN_PATHS contains none of those paths, so under
  EXPOSE_LAN=true those endpoints are gated and work only via the same-origin session cookie
  (which does work for img/video tags — stale wording, not a broken feature). Pre-existing
  before this PR but attaching to kept files; the PR body itself disclosed the staleness in
  "Questions for the owner".
- Evidence: pin `:2928-2940` as quoted; same claim at :1417, :1510, :3138, :3151, :3165,
  :3178, :3193, :6145. Backend: `backend/api/middleware/auth.py:56-67` OPEN_PATHS holds no
  media paths; `__call__` refuses every other request with 401 when expose_lan is set. The
  same wording is present at the merge's first parent.
- Fix: rewrite the nine sites to state the pin behaviour — media endpoints are not exempt;
  the middleware gates them under EXPOSE_LAN and the browser's same-origin session cookie
  authenticates img/video tag loads. Size S; owner: frontend.
- Owner: ruled later (ruling 267): one cleanup PR per lane at the audit's end.
- Refuted=false. Refuter verified every leg at the pin: the nine sites sit at exactly the
  cited lines with :2928-2940 verbatim; `auth.py:56-68` OPEN_PATHS holds only
  health/auth paths; `__call__` (:660-670) refuses any non-OPEN, non-preflight request
  without a valid credential (HTTP refusal 401 at :693); no alternative exemption exists
  (no decorator, per-route guard, router dependencies, or dependency_overrides). The
  "stale wording, not a broken feature" judgment holds: `authenticated_principal`
  (:607-611) is transport-agnostic and accepts the session cookie on HTTP GET
  (httponly/SameSite=lax rides same-origin img/video loads), and #6922's own run-1
  evidence confirms media rendered after login. Escape (b) rejected decisively: the
  comment enumerates the paths as the middleware's exempt set, and unscoped API keys are
  in fact accepted on gated paths by the middleware — false under both readings. The PR
  body's disclosure confirms rather than refutes (not in ruling 262's exclusion list).
  Freshness: 5 commits touch api.ts merge→pin, none touch an `exempt` line; the comments
  pre-date the PR (present in both merge parents). Corrections: OPEN_PATHS spans :56-68
  (not :56-67); and the same stale claim also lives in backend route docstrings the
  item's fix must cover — `backend/api/routes/detections.py` (:170, :644, :1221, :1399,
  :1546) and `backend/api/routes/cameras.py` (:1075) — so the fix spans frontend and
  backend (owners: frontend + backend).

### Q-013 · claim · low · frontend/src/contexts/AuthContext.test.tsx:356 · #6922

- Wrong: two inline cites give pin-stale coordinates for claims whose substance is still
  true. `:356` "Shipped logout (AuthContext.tsx:175-178) POSTs /api/auth/logout and then only
  invalidateQueries(CURRENT_USER_KEY)" — at the pin `:175-178` is the tail of the 401-seam
  useEffect and a loading-state comment; the logout callback lives at `:217-221`. `:361`
  "user = currentUser ?? null (AuthContext.tsx:152)" — at the pin `:152` is an "F1.3 Done
  when" comment line; the assignment is at `:194` and now reads
  `setupRequired ? null : (currentUser ?? null)`. The present-tense framing tells the reader
  these lines hold the code, and they don't.
- Evidence: pin cites match the pre-PR layout: at e9ec74ef, AuthContext.tsx:175-178 IS the
  logout block and :152 IS the assignment. Pin AuthContext.tsx: `:173-175` seam useEffect
  tail, `:194` the guarded assignment, `:217-221` the logout callback. Both files
  blob-identical merge→pin (7eaa705632d0… / b0c32aa52d97…), and AuthContext.tsx already had
  logout at :217 at e0cd9333 — the cites were stale in the PR's own content.
- Fix: repoint :356 to AuthContext.tsx:217-221 and :361 to AuthContext.tsx:194, and update
  the :361 quote to the setupRequired-guarded form the pin ships. Size S; owner: frontend.
- Owner: ruled later (ruling 267): one cleanup PR per lane at the audit's end.
- Refuted=false. Refuter verified both cites verbatim with present-tense framing; the pin
  coordinates exactly as itemized (:175-178 seam tail + comment, :152 "F1.3 Done when",
  logout callback :217-221, guarded assignment :194); and substance still true (logoutApi
  at services/authApi.ts:243-249 POSTs /api/auth/logout, only cache action is
  invalidateQueries(CURRENT_USER_KEY); the quoted "user = currentUser ?? null" holds in
  the operative branch, where the guarded line reduces exactly to that form). Mechanism
  sharpened: the test blob was unchanged e9ec74ef→e0cd9333 (9b602fa6) and only became
  7eaa7056 at merge, while AuthContext.tsx moved (7bfedf84→b0c32aa5) already in PR-branch
  commits — the PR relocated the code without touching the test comment, so the cites
  were stale in the PR's own content at merge, not drifted later. Nuance: the
  setupRequired guard predates #6922 (:152 at e9ec74ef already reads the guarded form),
  so the comment's quote was never a verbatim match of the cited line — a branch-local
  simplification — and the item's fix (repoint + update the quote) already covers it.

</details>

### Found in batch 1, re-attributed by mover-owns (rule with the re-attributed batch)

### Q-012 · claim · low · frontend/src/**tests**/api-endpoint-contract.test.ts:241 · re-attributed #6922 → **#7230 (batch 4)**

- Wrong: the comment's present-tense measurement is false against the file's own adjacent
  snapshot: "Measured now: 24 entries over 24 distinct positions, i.e. no position is
  doubled" — the pinned dynamic snapshot immediately below (:252-274) holds 23 entries over
  23 distinct file:line tokens. The snapshot was refreshed post-merge and the recount that
  accompanied the refresh landed one short of the comment; a reader cross-checking list
  length against the stated count — the exact check the comment says it exists for — gets
  23 vs 24.
- Evidence: pin `:241-242` as quoted; snapshot `:252-274` = 23 entry lines, 23 distinct
  tokens (first-token sort -u = 23; webSocketManager.ts:503 and :504 both present, so the
  "distinct lines" claim at :241 is true and only the count is wrong). File blob differs
  merge→pin (the post-merge snapshot refresh); the pin snapshot is what binds.
- **Re-attribution (refutation pass, 2026-10-19):** the current "24 entries" wording was
  authored by [r204] commit 70c5d96ae (PR #7230), whose own branch snapshot was genuinely
  24/24 — the count was correct when written. Concurrent detector-retire PR #7228
  (`heavy`, 3h earlier) had already deleted the detectorApi.ts:144 entry, and #7230's
  merge resolution (9e71bfde8) carried that removal in, so the tree read 23/23 under the
  24-claiming comment from the moment #7230 landed — merge-resolution drift, the
  mover-owns doctrine. #7230 is a census production PR (position 50, batch 4), so the
  item attaches to #7230's batch, not batch 1. (The item was first found while auditing
  #6922's kept files, hence its original attribution; #6922's merge version said
  "25/24" against a 26/25 snapshot — already inconsistent — but the wording the pin
  carries is #7230's.)
- Fix: correct :241-242 to "23 entries over 23 distinct positions", or make the count a
  computed interpolation from audit.scan.dynamic so it cannot drift again.
  Size S; owner: frontend.
- Owner: (pending)
- Refuted=false (verified against the re-attributed owner): no reading of "entries" yields
  24 (23 array lines, 23 tokens, 14 distinct files, nonApi empty); the merge blob said
  "25/24" against an actual 26/25 (useWebSocketStatus.ts:145 doubled), so the comment was
  already inconsistent at merge too; no later PR fixed it (pickaxe -S 'Measured now' over
  70c5d96ae..pin empty); the executable assertion derives the length at runtime and the
  inline snapshot pins 23 entries, so the test is green — prose-only.

### Q-014 · claim · low · frontend/src/hooks/useSummaries.ts:150 · #6922

- Wrong: the comment claims buildWebSocketOptions "attaches the optional api-key subprotocol",
  but at the pin the builder attaches no credential and never returns protocols — the WS
  connection rides the session cookie. The five sibling hooks (useAlertWebSocket,
  useEventLifecycleWebSocket, usePlateReadWebSocket, useUnknownStrangerAlerts,
  useRecentThreats) had this exact comment rewritten to ruling-44 wording by the post-merge
  sweep; this file was missed, so the comment describes code that no longer exists at the pin.
- Evidence: pin `:148-152` as quoted, then `const { url: wsUrl, protocols } =
buildWebSocketOptions('/ws/events');` — protocols is always undefined. The builder at
  `frontend/src/services/api.ts:986-987` reads `// No credential is attached: the cookie
authenticates the browser.` / `return { url: wsUrl };` — no protocols field is ever
  returned. Blob identity: merge tree = pin = 944d6659acd2…, so the file was untouched
  between merge and pin. Contrast: sibling hooks at the pin say "buildWebSocketOptions
  attaches no protocols" (useRecentThreats.ts:194-195 "rides the session cookie").
- Fix: rewrite the comment to the ruling-44 wording used by the five sibling hooks — the
  builder resolves the origin and attaches no credential — and drop the destructured
  protocols. Size S; owner: frontend.
- Owner: (pending)
- Refuted=false. Refuter verified all claims at the pin: the comment (:148-151) and the
  call verbatim (`protocols` destructured at :152, threaded into wsOptions at :155, always
  undefined since the builder at api.ts:969-1005 returns only `{ url: wsUrl }` — harmless
  because webSocketManager.ts:502-503 guards with `config.protocols?.length`); all five
  siblings carry the ruling-44 wording at the pin; the sweep commit is 4447c7cc4 ("fix
  (ruling 44): browsers authenticate only through the cookie login", Oct 9 15:35 — after
  #6922's merge, before the pin, ancestor confirmed), which rewrote the five siblings'
  comments across a 19-file stat that does NOT include useSummaries.ts, which existed at
  sweep time (stale comment added by e0cd93333 "fix(F1.3)", Oct 8 23:41) — "missed by the
  sweep" is accurate. Blob 944d6659 identical merge→boundary→pin, so no later PR fixed it.
  Escapes fail: nothing mints an api-key subprotocol in the browser bundle at the pin; no
  dating qualifier; the sentence's subject for both verbs is buildWebSocketOptions itself.
  Repo-wide grep: the stale claim wording hits only useSummaries.ts:150. Corrections:
  (1) "this exact comment" is loose — only useRecentThreats carried near-identical wording;
  the four hook-clone siblings read "and pick up its api-key subprotocol" pre-sweep (same
  false claim, different phrasing). (2) The fix's "drop the destructured protocols"
  exceeds sibling parity — useRecentThreats.ts:198 still destructures it at the pin; drop
  it only as optional cleanup, not as part of the comment fix.
- Re-attribution (mover-owns, applied after Q-015's refuter identified the sweep's PR):
  the comment was TRUE at #6922's merge — the builder at 3dab5c557 api.ts:974-1017 still
  carried `if (apiKey) { options.protocols = [`api-key.${apiKey}`]; }`. The comment became
  false when the sweep commit 4447c7cc4 rewrote the builder to `return { url: wsUrl };` —
  and the same commit's 49-file stat rewrites the five siblings while missing
  useSummaries.ts. 4447c7cc4 is PR #6936's content (merged as c382693bf, 2026-10-09
  22:23, after #6922's merge, not an ancestor of it). The first mover of the falsehood is
  #6936, not #6922: the item re-attributes to **#6936 (batch 2, mover-owns)**. #6922's
  only relation is that it merged a hook (from #7228's e0cd93333 content) whose comment
  was still accurate at its merge.

### Q-015 · claim · low · frontend/src/hooks/webSocketManager.auth.test.ts:10 · re-attributed #6922 → **#6936 (batch 2)**

- Wrong: the header's defect-1 paragraph is a botched splice that no longer parses:
  "the plumbing below / still pins that any protocols a caller sets are not dropped /
  through `useWebSocket` is dropped on the floor (useWebSocket.ts:19 admits it: …)" carries
  two predicates for one clause ("are not dropped" and "is dropped on the floor"), so as
  written the sentence asserts the plumbing both preserves and drops the protocols. At the
  merge the same sentence was coherent; the rewrite that adapted it to ruling 44 replaced
  the front of the sentence and left the old tail behind. A reader cannot extract a claim
  from the pin text.
- Evidence: pin `:9-13` byte-verified as quoted. Merge blob 49a64d414bda…: "…the
  `api-key.{key}` subprotocol that `buildWebSocketOptions` mints (api.ts:995-999) and 18
  hooks pass down through `useWebSocket` is dropped on the floor…" — coherent. The [r204]
  repair e2843aa1d (between merge and pin) changed only the final two lines and its message
  describes a clean 2-in/2-out, while the broken front half is already present in its parent
  blob d0986216cce5…. The test body itself is fine: all six executables verify against the
  pin manager (constructor ternary webSocketManager.ts:503-504, terminal 4001, close-code
  pass-through, rerender identity stability).
- Fix: rewrite :9-13 as two clean sentences: the plumbing below still pins that any
  protocols a caller sets are forwarded to the WebSocket constructor
  (webSocketManager.ts:503-504); before F1.3 they were dropped on the floor, as
  useWebSocket.ts:19 admitted at e9ec74ef. Size S; owner: frontend.
- Owner: (pending)
- Refuted=false. Refuter verified every leg at the pin: :9-13 byte-exact as quoted; one
  subject ("any protocols a caller sets") carries two conflicting predicates ("are not
  dropped" / "is dropped on the floor") with no punctuation or relative structure between
  them — the charitable two-claim reading requires inserting a subject ("the subprotocol")
  absent from the text, so no coherent claim is extractable; not taste (a
  self-contradicting comment destroying its own claim, not a style preference), not a
  Markdown file. At #6922's merge (blob 49a64d414) the same tail was coherent because the
  front carried the relative clause ("the `api-key.{key}` subprotocol that
  `buildWebSocketOptions` mints (api.ts:995-999) and 18 hooks pass down"); a rewrite
  replaced that front and left the old tail. Test body verified: all six executables hold
  at the pin (constructor ternary webSocketManager.ts:503-504,
  AUTH_TERMINAL_CLOSE_CODES [4001,4002] at :155 used at :586 — terminal 4001, no retry
  storm; close-code pass-through to subscriber onClose; rerender identity via
  content-keyed protocolsKey, useWebSocket.ts:95); the quoted "protocols are not yet
  supported by the manager" is verbatim at e9ec74ef useWebSocket.ts:19.
- Re-attribution (mover-owns): the defect does not belong to #6922. The blob at #6922's
  branch tip (a6b07d74) and merge (3dab5c557) is the coherent 49a64d414 — the test file
  was authored by #6922 with a well-formed sentence. The broken front half was written by
  commit 4447c7cc4 ("fix(ruling 44): browsers authenticate only through the cookie
  login"), part of PR #6936 (merged as c382693bf, 2026-10-09 22:23, after #6922's merge):
  diff-tree shows 49a64d414 → d0986216 at 4447c7cc4, and the tag pair v0.38.3 (last
  coherent; #6943 merge) → v0.38.4 (first broken; #6936 merge) brackets it with
  4447c7cc4 as the only commit in the range touching the file. The r204/#7230 branch only
  inherited the broken blob from main (every r204 commit from bc9769473 back carries
  d0986216; deletion commit 70c5d96ae did not touch this file), so this is NOT the
  Q-012-style re-attribution to #7230 the refutation prompt's hypothesis anticipated —
  re-attribute to **#6936 (batch 2, mover-owns)**, the PR whose sweep adapted the header
  to ruling 44 and botched the splice. Severity low / class claim unchanged.
  (Refuter's check that no later PR fixed it: no commit between e2843aa1d and the pin
  touched the file — path log empty.)

### Deferred out of batch 1 (recorded here so they are not lost)

- `monitoring/alerting-rules.yml:960` cites `docker-compose.prod.yml:151-152` for the
  pyroscope labels (pin: labels at `:173-174`, `:151-152` is part of the rewritten
  ai-vlm header). True at #6862's merge (:151-152). First moved by #7114 (151→166),
  then #7222 (166→173). Mover #7114 is a later batch — attaches there.
- `backend/api/routes/model_management.py:253` cites `docker-compose.prod.yml:398` for
  the CUDA line (pin: at `:420`). True at #6862's merge and again at #6907's merge
  (#6907 rewrote the comment to `:398`, true at its merge). First moved by #7114
  (398→413), then #7222 (413→420). Mover #7114 is a later batch — attaches there.
- `backend/tests/unit/scripts/test_ci_compose_cap_drop_bootable.py:149` cites
  `docker-compose.prod.yml:479` for the ENVIRONMENT line (pin: `:508`). True at
  #6907's merge (the PR carrying the test) and still `:479` at #6950's merge.
  First moved by #7114 (479→495), then #7222 (495→508). Attaches to #7114's batch.
- `scripts/a5500_precheck.py` AMENDMENTS rows (renumbered by #6862):
  `docker-compose.prod.yml:160` for the CUDA_ARCHITECTURES thread line (pin: `:182`)
  and `:188` for the GPU_LAYERS line (pin: `:210`). Both true at #6862's merge and
  unchanged through #6950; first moved by #7114 (→175/203), then #7222 (→182/210).
  Attaches to #7114's batch.
- [#6862 test/tooling verdict note, NOT an item] the retirement gate's
  `test_no_living_surface_gives_the_retired_profile_instruction` times out under
  pyproject's repo-wide `timeout = 5` in THIS sandbox (25s: the walk descends into
  untracked `.pytest_cache/golden-run` ~20k files + `.hypothesis`; simulated
  clean tree: 1739 surfaces, walk 0.1s, scan 0.8s). The repo already ruled this
  failure class environment-not-pin (`4668c589e`, 2026-10-17, in main at the pin:
  ".tickscratch" prune with "a walk's speed is an environment property... a green
  that depends on whose scratch tree is under REPO_ROOT is not a pin"). CI passed
  #6862's unit shards and passes at the pin's head (e0bf44c runs all success).
  No item; the gate is green in its enforcement context.
- `scripts/validate_docs/config.py:205` docstring example cites
  `docker-compose.prod.yml:284` as the profiles-line citation the host-rule
  deliberately allows (pin: `:284` is `cpus: '4'`; the example's referent — a
  `profiles:` line — is gone, and no doc cites `:284` at the pin). True at
  #6862's own merge (its diff renumbered the example `:154`→`:284` to stay
  true) and unchanged through #6950; first moved by #7114 (`:284` →
  `device_ids:`), then #7222. Attaches to #7114's batch.

## Batch 2 — per-PR verdicts

Production positions 10-24, audited under the same ruling-232 protocol as batch 1: a fresh
unnamed refutation subagent per item, verdicts in /tmp/r262_b2_refutations/, nothing dropped
by refutation. Two PRs returned empty auditor verdicts and were re-looked per ruling 232's
probe rule (#6943 and #7015 — both probes found candidates, listed below under their own PRs).
Per the owner's continue (comment 6266204180): the low items rule from the compact table with
their evidence in the collapsed block under it; the mediums keep the full templates after the
table. Owner decisions are pending and may arrive in bulk, written into the rows.

| PR    | Class      | Verdict                                                                                                                                                                                             |
| ----- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| #6927 | production | 1 item kept here (Q-016, claim/low) + 1 auditor candidate that is batch 1 Q-012's same-file duplicate (api-endpoint-contract.test.ts:241 — re-attributed to #7230 batch 4, counted there, not here) |
| #6930 | production | 2 items (Q-018, Q-019, claim/low)                                                                                                                                                                   |
| #6931 | production | 2 items (Q-020, Q-021, claim/low)                                                                                                                                                                   |
| #6936 | production | 2 items (Q-022, Q-023, claim/low); also rules over Q-014 and Q-015, re-attributed here from batch 1 by mover-owns (their sections sit in batch 1's block)                                           |
| #6943 | production | no auditor items — empty verdict probed per ruling 232: PROBE: CANDIDATES FOUND — 3 probe items (Q-024 medium, Q-025, Q-026)                                                                        |
| #6950 | production | 3 items (Q-027, Q-028, Q-029, all low; Q-027 owns websocket_auth.py kept by #6927's batch — the file's mover facts live here)                                                                       |
| #6959 | production | 5 items (Q-030–Q-034; Q-032 medium) + 3 re-attributed by mover-owns: Q-031 → #6970/B3.3, Q-032 → r95 (75ea5ee10), Q-033 → events.py movers (#7205/B3.1/r223)                                        |
| #7002 | production | 4 items (Q-035, Q-036, Q-037, Q-038) — Q-036 re-issued with corrected provenance (refuter verdict REFUTED on the mover leg only; staleness and fix stand)                                           |
| #7015 | production | no auditor items — empty verdict probed per ruling 232: PROBE: CANDIDATES FOUND — 2 probe items (Q-058, Q-059) + 1 supplementary outside the diff (scope call for the coordinator)                  |
| #7019 | production | 1 item (Q-039, test/low)                                                                                                                                                                            |
| #7031 | production | 5 items (Q-040 medium, Q-041–Q-044 low)                                                                                                                                                             |
| #7038 | production | 2 items (Q-045, Q-046) — both attach to the #7044 lineage by mover-owns (this PR is the r94 harness PR that created the files; see rows)                                                            |
| #7039 | production | 5 items (Q-047–Q-051, all claim/low)                                                                                                                                                                |
| #7041 | production | 6 items (Q-052, Q-053, Q-054, Q-055 mediums; Q-056, Q-057 low)                                                                                                                                      |
| #7044 | production | 2 items (Q-060, Q-061 low) — Q-061 corrects the batch-1-era attribution: #7044 DELIVERED the security.md paragraph (PR-side commits), not a keeper-miscast                                          |

| id    | class        | path:line                                                                                                           | PR                                                        | wrong (one line)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | fix (size, lane)                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | owner                                                                                                                                 |
| ----- | ------------ | ------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Q-016 | claim        | backend/api/middleware/websocket_auth.py:159-160                                                                    | #6927 (mover-owns → #6950, batch 2)                       | the R55 docstring cites `middleware/auth.py::_session_username, used by authenticated_principal at :329` — pin truth is def :585 / caller :600 / call :610; pin :329 is a blank line in require_api_key's docstring ~270 lines from the object; born-wrong at its authoring commit 49dd54a90 (#6950)                                                                                                                                                                                                                                                                                                                                                     | repoint to `auth.py::_session_username (def :585), called by authenticated_principal (:600) at :610`, or drop the bare line number. Size S; backend                                                                                                                                                                                                                                                                                                                                    | ruled later (one cleanup PR per lane at the audit's end) — ruling 271, record 6277412644                                              |
| Q-017 | dedup        | (batch 1 Q-012's same defect — see that row)                                                                        | #6927 candidate, not counted here                         | 6927_c1 is the same-file twin of Q-012 (same comment, same 23/24 mismatch, same mover #7230) — one defect, counted once at Q-012                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | cross-reference only. — rules with batch 4                                                                                                                                                                                                                                                                                                                                                                                                                                             | ruled with batch 4 (a duplicate of Q-012; decided there) — ruling 271, record 6277412644                                              |
| Q-018 | claim        | docs/operations/profiling-runbook.md:12, :30, :811                                                                  | #6930                                                     | three present-tense compose cites point far from their objects at the pin: pyroscope.profile labels :151-152→:173, GF_SERVER_ROOT_URL/SERVE_FROM_SUB_PATH :1095-1096→:1215-1216, provisioning mount :1074→:1165; runbook blob byte-identical merge→pin                                                                                                                                                                                                                                                                                                                                                                                                   | re-point the three cites (173 / 1215-1216 / 1165) or drop the numbers and keep the substance. Size S; docs                                                                                                                                                                                                                                                                                                                                                                             | ruled later (one cleanup PR per lane at the audit's end) — ruling 271, record 6277412644                                              |
| Q-019 | claim        | docs/operations/profiling-runbook.md:804-808                                                                        | #6930                                                     | the PR's own UR-9 sentence says under EXPOSE_LAN "these API calls need the machine key or a login session", but the machine key is not a Grafana credential — nothing wires it to Grafana's API; the runbook's own procedures use `-u admin:admin`                                                                                                                                                                                                                                                                                                                                                                                                       | rewrite to pin truth: under EXPOSE_LAN the Grafana API needs basic auth (GF_ADMIN pair) or a login session; the machine key is for the backend gate (Prometheus/Alertmanager/json-exporter). Size S; docs                                                                                                                                                                                                                                                                              | ruled later (one cleanup PR per lane at the audit's end) — ruling 271, record 6277412644                                              |
| Q-020 | claim        | .trivyignore:264                                                                                                    | #6931                                                     | the AVD-DS-0002 rationale cites `ci.yml:1889-1901` for deploy.yml's backend+frontend matrix, but that pin range is the Linear issue-creation shell; the matrix lives at deploy.yml:44-66 — wrong file, false at authorship (22ccdde31, PR #6792)                                                                                                                                                                                                                                                                                                                                                                                                         | point the cite at deploy.yml:44-66 or drop the coordinate and keep the prose claim. Size S; backend                                                                                                                                                                                                                                                                                                                                                                                    | ruled later (one cleanup PR per lane at the audit's end) — ruling 271, record 6277412644                                              |
| Q-021 | claim        | .github/workflows/ci.yml:2224                                                                                       | #6931                                                     | the vitest rerun comment cites `ci.yml:455-463` as "the pytest jobs' rerun block", but that pin range is the WP0.1 pre-push gate; the pytest rerun blocks sit at :1287/:1432/:1556                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | update to :1287/:1432/:1556 or name the steps without line numbers. Size S; ops                                                                                                                                                                                                                                                                                                                                                                                                        | ruled later (one cleanup PR per lane at the audit's end) — ruling 271, record 6277412644                                              |
| Q-022 | claim        | docs/architecture/frontend-hooks.md:9 + :364                                                                        | #6936                                                     | both headline cites into useConnectionStatus.ts name :117, past EOF of the 111-line pin file; the export sits at :105 (the doc's own body at :206 correctly cites :108) — cites authored true by 8352c1e07, broken by 70c5d96ae (r204 hook rewrite)                                                                                                                                                                                                                                                                                                                                                                                                      | re-aim both to `useConnectionStatus.ts:useConnectionStatus:105` (frontmatter) and `useConnectionStatus.ts:105` (Source line). Size S; docs                                                                                                                                                                                                                                                                                                                                             | ruled later (one cleanup PR per lane at the audit's end) — ruling 271, record 6277412644                                              |
| Q-023 | claim        | frontend/src/hooks/useWebSocket.ts:87                                                                               | #6936                                                     | the F1.3 dependency comment still says "Callers rebuild this list every render — buildWebSocketOptions returns a fresh array", but the pin builder returns only `{ url: wsUrl }` — no array, no protocols key at all; the PR's own test pins `expect('protocols' in options).toBe(false)`                                                                                                                                                                                                                                                                                                                                                                | rewrite the stale clause for the shipped contract (builder attaches no protocols; mechanism inert) or trim the fresh-array rationale. Size S; frontend                                                                                                                                                                                                                                                                                                                                 | ruled later (one cleanup PR per lane at the audit's end) — ruling 271, record 6277412644                                              |
| Q-024 | claim/medium | docs/reference/backend-entry-points.md:1530 (+ :1349)                                                               | #6943 (probe)                                             | two dead-code-register entries assert WebSocketEmitterService unwired wholesale — every clause false at pin (main.py:147/:1032 wire it with the system broadcaster; :377-378 fires)                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | rewrite :1530 to residual truth (system broadcaster only wired; four call sites bare) + re-aim :1349's publisher sentence to main.py:1032. Size M; docs                                                                                                                                                                                                                                                                                                                                | ruled fix now as `[r271c]` (docs; this lane's, one-off UR-52 exception, worked between audit batches) — ruling 271, record 6277412644 |
| Q-025 | claim        | docs/reference/backend-entry-points.md:1349                                                                         | #6943 (probe)                                             | the same /ws/system Feed-chain bullet's three internal main.py cites drifted — :1025-1026→:1017-1018, :1031→:1037, :1036-1037→:1042-1043 — made stale by #6943's own 15-line insertion                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | re-aim the three cites to :1017-1018, :1037, :1042-1043. Size S; docs                                                                                                                                                                                                                                                                                                                                                                                                                  | ruled fix now as `[r271c]` (docs; this lane's, one-off UR-52 exception, worked between audit batches) — ruling 271, record 6277412644 |
| Q-026 | claim        | docs/reference/feature-inventory.md:1207, :344 (F-008), :352 (F-016)                                                | #6943 (probe)                                             | three wiring-line cites miss the wiring at main.py:1032 — :1041 born-true made stale by d6344e031 (edited the row without re-aiming); the two :1038 cites born-stale, never true in any of 169 reachable main.py blobs                                                                                                                                                                                                                                                                                                                                                                                                                                   | re-aim all three to backend/main.py:1032. Size S; docs                                                                                                                                                                                                                                                                                                                                                                                                                                 | ruled fix now as `[r271c]` (docs; this lane's, one-off UR-52 exception, worked between audit batches) — ruling 271, record 6277412644 |
| Q-027 | bug          | backend/api/middleware/websocket_auth.py:193                                                                        | #6950                                                     | validate_websocket_jwt gates success on `hmac.compare_digest(token, token)` — always true — so the docstring/comment/module-bullet "constant-time comparison" claims are unexercised and `return None` :195 is dead code; #6950 deleted the cookie twin but left this line and its pinning test                                                                                                                                                                                                                                                                                                                                                          | delete the comparison and dead branch; correct the three prose sites (:12 can stay only scoped to validate_websocket_token; :179, :192 must go); rewrite or drop test_validate_websocket_jwt_constant_time_comparison. Size S; backend                                                                                                                                                                                                                                                 | ruled later (one cleanup PR per lane at the audit's end) — ruling 271, record 6277412644                                              |
| Q-028 | bug          | backend/api/middleware/websocket_auth.py:196                                                                        | #6950                                                     | validate_websocket_jwt catches only InvalidTokenError/TokenExpiredError, but _get_jwt_secret raises ValueError when settings.jwt_secret is None — the shipped default (production env, no JWT_SECRET in compose or .env.example) — so a client presenting ?token= kills the handshake with an unhandled exception instead of the designed no-vote refusal                                                                                                                                                                                                                                                                                                | add ValueError to the caught set: `except (InvalidTokenError, TokenExpiredError, ValueError):`. Size S; backend                                                                                                                                                                                                                                                                                                                                                                        | ruled later (one cleanup PR per lane at the audit's end) — ruling 271, record 6277412644                                              |
| Q-029 | claim        | docs/reference/config/env-reference.md:377                                                                          | #6950                                                     | the SESSION_COOKIE_SECURE warning parenthetical states the no-bind state as "TLS_MODE set with BOTH paths" — the inverse of the code: the warning fires when NOT (mode != disabled and both set), so TLS_MODE=disabled with both paths still warns and TLS_MODE=provided with both paths DOES bind                                                                                                                                                                                                                                                                                                                                                       | reword the parenthetical to the actual no-bind condition ("TLS_MODE is disabled, or TLS_CERT_PATH/TLS_KEY_PATH are not both set"), keeping the link to the precise :387-437 section. Size S; docs                                                                                                                                                                                                                                                                                      | ruled later (one cleanup PR per lane at the audit's end) — ruling 271, record 6277412644                                              |
| Q-030 | drift        | backend/api/middleware/README.md:66                                                                                 | #6959                                                     | the tail still offers "Key permissions/scopes" under Future Enhancements although R60 shipped API-key scopes and the same file's Configuration table documents the scoped object entry — the list contradicts the table in the same file                                                                                                                                                                                                                                                                                                                                                                                                                 | delete the bullet or replace with a pointer to the Configuration table's R60 row. Size S; docs                                                                                                                                                                                                                                                                                                                                                                                         | ruled later (one cleanup PR per lane at the audit's end) — ruling 271, record 6277412644                                              |
| Q-031 | claim        | docs/architecture/security/authentication-roadmap.md:9 + :34                                                        | #6959 (its own re-aim; block later moved by #6970 + B3.3) | config.py:1999-2012 cite dead (block now at :1794-1874)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | re-aim to :1794-1874 or def-anchor on setting names api_key_enabled/api_keys/parse_api_key_scopes — the only anchor formulation that has survived this file (S, docs)                                                                                                                                                                                                                                                                                                                  | ruled later (one cleanup PR per lane at the audit's end) — ruling 271, record 6277412644                                              |
| Q-032 | claim/medium | docs/reference/config/env-reference.md:372                                                                          | #6959 (mover-owns → r95, 75ea5ee10)                       | the row's verify_api_key clause is false for scoped entries — both verify_api_key defs (dlq.py:42, system.py:272) skip scoped keys and 401                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | scope the assertion: plain entries accepted, scoped entries honored only by the middleware gate and refused by legacy verify_api_key (dlq.py, system.py). Size M; docs                                                                                                                                                                                                                                                                                                                 | ruled fix now as `[r271c]` (docs; this lane's, one-off UR-52 exception, worked between audit batches) — ruling 271, record 6277412644 |
| Q-033 | claim        | backend/core/constants.py:273                                                                                       | #6959 (mover-owns → #7205/B3.1/r223)                      | the R60 rationale cites events.py's bulk write verbs at :1493/:1617/:1733; at the pin those hold a read signature, an enumerate loop, and `failed = 0` — the verbs sit at :1575/:1699/:1815; drift chain #7205 +48, B3.1 −1, r223 +22, r223-round-1 +13                                                                                                                                                                                                                                                                                                                                                                                                  | re-point to :1575/:1699/:1815 — or, durably, drop coordinates for handler names (bulk_create_events, bulk_update_events, bulk_delete_events, …); note the trio covers only the bulk verbs of the file's seven write verbs. Size S; backend — movers outside the census; rules here                                                                                                                                                                                                     | ruled later (one cleanup PR per lane at the audit's end) — ruling 271, record 6277412644                                              |
| Q-034 | claim        | setup_lib/core.py:254                                                                                               | #6959                                                     | merge_api_keys' docstring cites `docker-compose.prod.yml:636` for the API_KEYS interpolation; at the pin :636 is a reid comment and the interpolation sits at :665                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | retarget to docker-compose.prod.yml:665 or drop the coordinate. Size S; backend                                                                                                                                                                                                                                                                                                                                                                                                        | ruled later (one cleanup PR per lane at the audit's end) — ruling 271, record 6277412644                                              |
| Q-035 | drift        | docs/reference/nvidia-technology-inventory.md:328-329                                                               | #7002                                                     | the TensorRT Version-and-status section still says "TensorRT is **not active in Triton** — all three repository models use the ONNX Runtime backend", contradicting reid/config.pbtxt:24 (`backend: "tensorrt"`) and the same file's Model Repository section (:282) — adjacent ## sections, 48 lines apart                                                                                                                                                                                                                                                                                                                                              | rewrite the paragraph: TensorRT is active for exactly one model — reid serves a trtexec-compiled 1/model.plan since O2.4 (ruling 107; compiled at deploy time on the serving GPU — the repo ships no plan binary), ONNX Runtime's CUDA EP fails on the GB300 (ruling 106); yolo26/threat remain onnxruntime; cross-reference the Model Repository section. Size S; docs                                                                                                                | ruled later (one cleanup PR per lane at the audit's end) — ruling 271, record 6277412644                                              |
| Q-036 | claim        | docs/reference/nvidia-technology-inventory.md:395-397                                                               | #7002                                                     | the providers paragraph says "Six scripts under ai/gateway/export/ do this" with the CUDA-first list, but O2.4 made export_reid.py CPU-only (export_reid.py:623) — exactly five scripts carry the CUDA-first list; the one script whose provider choice is the PR's whole point is counted in the wrong list                                                                                                                                                                                                                                                                                                                                             | change to five scripts; add the clause: export_reid.py pins CPUExecutionProvider for its ONNX validation pass (ruling 106) — its GPU path is the trtexec plan, not an execution provider; keep the "only export_reid.py corresponds to a model in the repository" clause intact. Size S; docs                                                                                                                                                                                          | ruled later (one cleanup PR per lane at the audit's end) — ruling 271, record 6277412644                                              |
| Q-037 | drift        | ai/triton/AGENTS.md:168 (+ :46-59, :160, :171-175, :177-191)                                                        | #7002 (re-issued; refuter REFUTED the mover leg only)     | the Model Repository section says "model_repository/ ships 14 model directories. 12 are loadable at startup" against a 3-dir tree (yolo26, reid, threat) — 14 tree rows :46-59, 13-row table :177-191, stale healthcheck comment :160; O2.4 flipped the reid table row (:186) and added the reid paragraph inside the stale-14-count section                                                                                                                                                                                                                                                                                                             | rewrite the section to the shipped reality: three directories, loadable at startup once the entrypoint symlinks version dirs from the model cache; replace the 13-row table or point at nvidia-technology-inventory.md's Model Repository section (corrected by this same PR); fix the tree block, the healthcheck comment, and the follow-up-count paragraph. Size M; docs                                                                                                            | ruled later (one cleanup PR per lane at the audit's end) — ruling 271, record 6277412644                                              |
| Q-038 | drift        | ai/gateway/tests/AGENTS.md:5 (+ :17-23)                                                                             | #7002                                                     | the purpose line says the suite covers "all five adapter modules" but adapters/ holds exactly two (enrichment_light, yolo26); the tree names three phantom test_adapters_* files and omits six real ones (test_residency, test_entrypoint_residency, test_dockerfile_agent_gpu_buildable, test_export_reid_onnx_fidelity, test_export_yolo26, test_py312_compat) — pin-frame count; merge-frame would be four                                                                                                                                                                                                                                            | correct :5 to two adapter modules; delete the three phantom rows; add the six named rows (plus conftest.py for a full reconstruction). Size S; docs                                                                                                                                                                                                                                                                                                                                    | ruled later (one cleanup PR per lane at the audit's end) — ruling 271, record 6277412644                                              |
| Q-039 | test         | frontend/src/hooks/**tests**/useFaceRecognitionApi.test.ts:65 (+ :76, useKnownPersonsApi.test.ts:63)                | #7019                                                     | the wire-mock fixtures still carry `household_member_id` on person items — a field the pin's backend KnownPersonResponse (7 fields) never sends; the PR corrected the envelope shape of the same fixtures but left the item-field shape overstating the contract (contract-mock overstatement, not mock-seam)                                                                                                                                                                                                                                                                                                                                            | drop household_member_id from the three fixture literals and from hand-maintained KnownPerson (faceRecognition.ts:192; also :206/:220 per F-280's three type sites); the field is NOT fictional — it is writable and readable on HouseholdMember responses, so fix says "drop from the person fixtures/type", not "the field never exists". Size S; frontend                                                                                                                           | ruled later (one cleanup PR per lane at the audit's end) — ruling 271, record 6277412644                                              |
| Q-040 | bug/medium   | backend/services/backup_service.py:361                                                                              | #7031                                                     | the getattr walk stringifies Alert's reserved metadata (MetaData) to "metadata": "MetaData()" and drops the alert_metadata payload; restore side swallows the key (Alert(**processed)) so alert_metadata stays NULL                                                                                                                                                                                                                                                                                                                                                                                                                                      | special-case the collision in the walk — read alert_metadata for the "metadata" key; do not generalize (Alert is the only walked model with it). Size M; backend                                                                                                                                                                                                                                                                                                                       | ruled fix now as `[r271b]` (backend backups package) — ruling 271, record 6277412644                                                  |
| Q-041 | claim        | backend/tests/golden/external/test_backup.py:39 + :43                                                               | #7031                                                     | the module docstring cites backup_service.py:324/:354 for the getattr walk (pin: walk at :361-362; :354 is the "type unresolved" comment) and :338-341 for the undefer loop (pin: :346-349) — both true at PR head b763116b7, broken by the PR's own commit 13a0ff66e (+10/-2 in backup_service.py) without re-anchoring the docstring it documents                                                                                                                                                                                                                                                                                                      | re-anchor to :361-362 (walk) and :346-349 (undefer). Size S; backend                                                                                                                                                                                                                                                                                                                                                                                                                   | ruled fix now as `[r271b]` (backend backups package) — ruling 271, record 6277412644                                                  |
| Q-042 | claim        | backend/tests/integration/test_backup_service.py:142                                                                | #7031                                                     | the class docstring cites backup_service.py:353-354 for the getattr walk; at the pin that span is the unresolved-scalar-type comment; the walk is at :361-362 — same mover (13a0ff66e) as Q-041                                                                                                                                                                                                                                                                                                                                                                                                                                                          | re-anchor to backup_service.py:361-362 (land together with Q-041's edit). Size S; backend                                                                                                                                                                                                                                                                                                                                                                                              | ruled fix now as `[r271b]` (backend backups package) — ruling 271, record 6277412644                                                  |
| Q-043 | claim        | backend/tests/integration/test_ai_audit_api.py:1530 (+ :1525, :1539, :1620, :1653, :1703)                           | #7031                                                     | six present-tense ai_audit.py cites in the new test class are all shifted off their objects at the pin (:433-437→undefer :450-454, :458→read :475, :475-480→except :492-497, :440-446→None-guard :457-463, :576→create_job :593) — all true at the merge, broken by eb7ce4431 ([r244], +17 lines earlier in ai_audit.py)                                                                                                                                                                                                                                                                                                                                 | re-anchor the six cites to the pin coordinates. Size S; backend                                                                                                                                                                                                                                                                                                                                                                                                                        | ruled later (one cleanup PR per lane at the audit's end) — ruling 271, record 6277412644                                              |
| Q-044 | claim        | backend/api/routes/ai_audit.py:443                                                                                  | #7031                                                     | the PR's undefer comment self-cites its own fatal read as "event.llm_prompt is read below (:445)" — never true at any reachable revision: born-false (read at :458 at authoring 702198999, at :475 at pin); the same self-review that re-anchored the test-docstring cites left this stale ':445' in the source comment                                                                                                                                                                                                                                                                                                                                  | drop the line-precise form ("in create_partial_audit below") — born-false and drifted twice, the coordinate is the defect; changing ':445'→':475' also works. TRAP: the sibling escape claim in _get_queue_stats (:988-992) is TRUE there — do not reword it. Size S; backend                                                                                                                                                                                                          | ruled later (one cleanup PR per lane at the audit's end) — ruling 271, record 6277412644                                              |
| Q-045 | drift        | scripts/uplevel-r94-mutation/README.md:19 (+ :34, :45, M-table :51-68)                                              | #7038 (mover-owns → #7044 lineage)                        | the README documents a 16-mutant battery; battery.py at the pin holds 20 (M1-M20) — four dead count claims, the M16 row describes a superseded mutation ("keep no quote as found" vs the pin's "only a single-quoted line is recognized as quoted"), M17-M20 have no rows, and battery.py:10's own docstring still says "16/16"                                                                                                                                                                                                                                                                                                                          | widen: 16→20 (or count-free "every mutant in MUTANTS" — the count has drifted once already; battery.py:272 prints it dynamically), add M17-M20 rows, rewrite the M16 row, fix battery.py:10's "16/16" in the same commit. Size S; ops — rules with #7044's batch                                                                                                                                                                                                                       | ruled later (one cleanup PR per lane at the audit's end) — ruling 271, record 6277412644                                              |
| Q-046 | claim        | backend/tests/unit/setup_lib/AGENTS.md:31                                                                           | #7038 (mover-owns → #7044 lineage)                        | the gotcha bullet says "four are not" 1:1 with a setup_lib module and enumerates four files, but 967f8476d added a fifth (test_r94_crlf_env_flag.py, named after the r94 ruling like its sibling) — false from #7044's merge onward                                                                                                                                                                                                                                                                                                                                                                                                                      | change to "five are not" and add test_r94_crlf_env_flag.py with ruling-named rationale; preserve the bullet's accurate tail (credentials/models_config/rootful_services untested). Size S; backend — rules with #7044's batch                                                                                                                                                                                                                                                          | ruled later (one cleanup PR per lane at the audit's end) — ruling 271, record 6277412644                                              |
| Q-047 | claim        | frontend/src/components/ai-performance/AGENTS.md:61 (+ :34/:75, :56, :25, :27, :92)                                 | #7039                                                     | the AGENTS.md contradicts the component in six claim-groups: IndicatorType union omits dlq and says yolo26 (code: rtdetr + dlq at AIPerformanceSummaryRow.tsx:36); props/usage name a yolo26 prop the component does not have (:58 takes rtdetr); "5 columns desktop" vs lg:grid-cols-6 (:366); Queues band "Green <5 / Yellow 5-20 / Red >20" vs getQueueStatus 0-10/11-50/51+; Errors band "Green 0 / Yellow 1-5 / Red >5" vs getErrorStatus yellow 1-49 / red >=50; icon list omits Archive. The DLQ row :28 and the 5→6 counts :11/:19 are correct; the props block :33-47 + usage :74-86 also omit dlqCounts (eighth staleness, added by a24d095bd) | update the union to 'rtdetr' \| 'nemotron' \| 'queues' \| 'throughput' \| 'errors' \| 'dlq', rename yolo26→rtdetr in props/usage, 6 columns, restate both bands, add Archive + dlqCounts to the props/usage blocks. Size S; frontend                                                                                                                                                                                                                                                   | ruled later (one cleanup PR per lane at the audit's end) — ruling 271, record 6277412644                                              |
| Q-048 | claim        | frontend/src/components/ai-performance/AIPerformanceSummaryRow.test.tsx:76                                          | #7039                                                     | the test titled "renders all 5 indicator cards" mounts six — the DLQ card renders even when dlqCounts is omitted (:688 sibling pins that), and the PR's own golden witness counts six (ai-summary-row.spec.ts:290 "the row now carries six indicators"); the body asserts only the five original testids                                                                                                                                                                                                                                                                                                                                                 | retitle to 6 AND add expect(screen.getByTestId('dlq-indicator')).toBeInTheDocument() — without the added assertion the retitled test inverts the mismatch (title-claims-6/body-proves-5). Grid-invariant corroboration: :97-130 requires cardCount % lg-cols === 0. Size S; frontend                                                                                                                                                                                                   | ruled later (one cleanup PR per lane at the audit's end) — ruling 271, record 6277412644                                              |
| Q-049 | claim        | frontend/src/components/settings/ModelManagementPanel.tsx:38 (+ hooks/AGENTS.md:1360)                               | #7039                                                     | the router-mount comment cites main.py:1648/:1663 — dead (pin: :1603/:1618); the order claim (model_management before system, so list_models answers GET /api/system/models) stays true; same drifted pair in hooks/AGENTS.md:1360                                                                                                                                                                                                                                                                                                                                                                                                                       | re-point both carriers to main.py:1603/:1618 in the same edit, or count-free ("mounted before system.router") for durability — drift = 3d8418fec then 9fcb5f453, both failed to re-point either carrier. Size S; frontend                                                                                                                                                                                                                                                              | ruled later (one cleanup PR per lane at the audit's end) — ruling 271, record 6277412644                                              |
| Q-050 | claim        | frontend/tests/golden/shell/tour.spec.ts:55 + :303 (+ feature-inventory.md:357)                                     | #7039                                                     | three carriers cite the ProductTour mount as App.tsx:342; the pin mount is :361 (:342 is a /heatmaps route line) — spec cites born true 8f87050d7, made off-by-one by 62c72165e BEFORE #7039 existed (inventory coordinate predates the PR, transcribed), born-false-in-place in the spec rewrite 4238c6260, off-by-ten from 453bec830 (inside the PR)                                                                                                                                                                                                                                                                                                   | re-point all three carriers to App.tsx:361, or use the stable anchor ("the <ProductTour /> line just inside </BrowserRouter>") — the mount has drifted three times post-qualification and survived one re-anchoring pass that fixed neighbors (bc43387c8 missed this row). Size S; frontend                                                                                                                                                                                            | ruled later (one cleanup PR per lane at the audit's end) — ruling 271, record 6277412644                                              |
| Q-051 | claim        | frontend/tests/golden/operations/config-inspector.spec.ts:94                                                        | #7039                                                     | of three coordinates in the testid-drop explanation, one stale (SystemMonitoringPage.tsx:738 → pin :709 pass-site) and one never-true (panel root div ":135" → pin :138; panel blob byte-stable since January); ":73 _props" is exact; the substantive testid-drop claim is true                                                                                                                                                                                                                                                                                                                                                                         | re-point to SystemMonitoringPage.tsx:709 and ConfigInspectorPanel.tsx:138 (panel lives in components/developer-tools/, NOT system/), or anchor on the _props signature :73. Size S; frontend                                                                                                                                                                                                                                                                                           | ruled later (one cleanup PR per lane at the audit's end) — ruling 271, record 6277412644                                              |
| Q-052 | bug/medium   | backend/services/system_broadcaster.py:1008-1014                                                                    | #7041                                                     | the RedisError arm discards the wrapper's unhealthy dict and the success path returns True unconditionally — the production failure signal is read as healthy                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | capture the dict, branch on healthiness, keep the RedisError arm as defense-in-depth, log the payload. Size M; backend                                                                                                                                                                                                                                                                                                                                                                 | ruled fix now as `[r271a]` (backend broadcaster package; UR-52, ruling 269) — ruling 271, record 6277412644                           |
| Q-053 | bug/medium   | backend/services/system_broadcaster.py:1008 companion :1320                                                         | #7041                                                     | twin test :1320's bare AsyncMock breaks the Q-052 fix (Mock return is not a dict → AttributeError) — the fix ships RED without the companion edit (:1321 then sets `health_check.return_value=True`)                                                                                                                                                                                                                                                                                                                                                                                                                                                     | same edit as Q-052: twin stub becomes return_value={"status": "healthy"} (house style system.py:893-894/:5346-5347); two callers keep the boolean contract. Size M; backend                                                                                                                                                                                                                                                                                                            | ruled fix now as `[r271a]` (backend broadcaster package; UR-52, ruling 269) — ruling 271, record 6277412644                           |
| Q-054 | bug/medium   | backend/services/system_broadcaster.py — REFUTED AS WRITTEN; re-issued as Q-054R below (nine builtin-only handlers) | #7041                                                     | as-written (Retry(NoBackoff(), 0) zero-retry wiring) disprovable by one grep at the pin: NoBackoff/Retry( absent from backend/; :564/:631/:693 are listener handlers, not retry sites; refutation-pass note logged (refuter verified lines but never checked the quoted tokens against them); real defect = the NINE builtin-only except handlers (:314/:364/:564/:583/:589/:612/:617/:631/:693) letting redis.exceptions.TimeoutError (a RedisError) escape — full template at Q-054R below                                                                                                                                                             | re-issue ruled fix now as `[r271a]` (backend broadcaster package; UR-52, ruling 269) — ruling 271 + corrections 6281398804/6281511059; re-issue verified at the pin line-by-line (nine tuples, :33 import, :1235 loop absorb)                                                                                                                                                                                                                                                          | ruled fix now as `[r271a]` (backend broadcaster package; UR-52, ruling 269) — ruling 271, record 6277412644                           |
| Q-055 | test/medium  | backend/tests/unit/services/test_system_broadcaster.py:1345 (storm probe)                                           | #7041                                                     | the probe stubs broadcast_status/performance (the exact losing layer) and counts STUB INVOCATIONS (:1424-1428) — real publish handlers catch only builtins (:307-316/:357-366), so loss is per-tick indefinite and the probe passes on a starvation; cross-refs updated to Q-054R (the zero-retry cross-ref died with as-written Q-054)                                                                                                                                                                                                                                                                                                                  | run against the real broadcast methods with publish raising redis.exceptions.TimeoutError, asserting per-message-type delivery every tick — sequence behind Q-054R's handler fix. Size M; backend                                                                                                                                                                                                                                                                                      | ruled fix now as `[r271a]` (backend broadcaster package; UR-52, ruling 269) — ruling 271, record 6277412644                           |
| Q-056 | test         | backend/tests/unit/services/test_system_broadcaster.py:1432                                                         | #7041                                                     | the timeout test drives _check_redis_health's except-branch through an AsyncMock seam only — production wiring cannot deliver a raised TimeoutError (RedisClient.health_check absorbs every Exception), so the test pins a branch shipped wiring never reaches; the seam is shared by THREE sibling sites (:1332/:1361/:1432); docstring :1436-1437 implies production raises                                                                                                                                                                                                                                                                            | document the seam's synthetic nature (all three docstrings), or re-seam through the production path — which goes RED until Q-053's fix lands, so sequence it behind c1. Size S; backend                                                                                                                                                                                                                                                                                                | ruled fix now as `[r271a]` (backend broadcaster package; UR-52, ruling 269) — ruling 271, record 6277412644                           |
| Q-057 | claim        | backend/services/system_broadcaster.py:1011 (+ test docstring :1434-1440)                                           | #7041                                                     | the PR's comment on the new RedisError arm asserts "without it a timeout under load escapes this helper" — false: the only production client type (RedisClient) absorbs every Exception into a returned dict, so the arm is dead in production; born-false at authoring (88e0d3457), zero drift, never true at any reachable milestone                                                                                                                                                                                                                                                                                                                   | reword ONLY :1011-1013 with the real rationale (defense-in-depth for non-wrapper clients / wrapper absorbs Exception) + the twin test docstring :1434-1440. TRAP: the near-identical escape claim in _get_queue_stats (:988-992) is TRUE there (raw client.llen) — mechanical "reword the #7041 comments" damage; keep the hierarchy clause (RedisError covers redis.exceptions.TimeoutError) and the outside-guard parenthetical (:807 outside guarded try :785-801). Size S; backend | ruled fix now as `[r271a]` (backend broadcaster package; UR-52, ruling 269) — ruling 271, record 6277412644                           |
| Q-058 | claim        | docs/reference/feature-inventory.md F-031 row (5 cites)                                                             | #7015 (probe)                                             | events.py :282/:468 and vlm_analyzer.py :671/:692/:980 cite stale lines — targets moved to :317/:513/:677/:698/:1077 by later commits the row never re-measured                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | re-point the five cites or def-anchor each target (S, docs)                                                                                                                                                                                                                                                                                                                                                                                                                            | ruled later (one cleanup PR per lane at the audit's end) — ruling 271, record 6277412644                                              |
| Q-059 | claim        | docs/reference/feature-inventory.md F-031 row (bug sentence)                                                        | #7015 (probe)                                             | present-tense "mapper DROPS verification/verdict" sentence is false at pin (mapper maps both fields — the PR's own fix) and its span drifted :206-221→:206-235                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | mark the sentence history per F-021 convention or re-tense past; re-bound span to :206-235 (S, docs)                                                                                                                                                                                                                                                                                                                                                                                   | ruled later (one cleanup PR per lane at the audit's end) — ruling 271, record 6277412644                                              |
| Q-060 | drift        | docs/uplevel/packages/backend.md:294-296                                                                            | #7044                                                     | the r94 record's defect bullet still reads present tense ("on a re-run, the LAN-exposure prompt defaults to n") with six dead coordinates (setup.py:685/:900/:447/:449/:482/:491 all unrelated at pin) — but the behavior was fixed INTRA-PR by 4430762dd inside #7038's own chain, NOT by a post-merge fixer; #7044's only touch = register update 888974d16                                                                                                                                                                                                                                                                                            | mark fixed-at-pin naming 4430762dd in #7038 (not a post-merge commit); convert to past tense; if re-anchoring, pin coordinates: prompts :784/:1011, derives :533/:535/:567-577; or drop the bullet. Size S; docs                                                                                                                                                                                                                                                                       | ruled later (one cleanup PR per lane at the audit's end) — ruling 271, record 6277412644                                              |
| Q-061 | claim        | docs/operator/admin/security.md:33-36                                                                               | #7044                                                     | the cure sentence "for every other one a full interactive python setup.py still works and converts it as a side effect" is false for exactly one of seven refusal cases — no-monitoring-key mints a FRESH key (setup.py:722/:921 `existing_env.get(...) or generate_api_key()`); merge_api_keys dedupes on VALUE, so the old plain entry stays live — the exact failure the sentence's own parenthetical attributes only to --yes/--defaults                                                                                                                                                                                                             | narrow to the key-known cases ("for every other one that still names the key in MONITORING_API_KEY …") or add no-monitoring-key to the exceptions with its actual remedy (the re-run mints a fresh key; remove or manually re-scope the stale plain entry). Do NOT touch the other six cases (verified true). The paragraph was DELIVERED by #7044 (PR-side commits 2571a8846 + 593dc4d8e via merge d393ff9ce); false advice reachable only in a hand-mangled .env state. Size S; docs | ruled later (one cleanup PR per lane at the audit's end) — ruling 271, record 6277412644                                              |

<details>
<summary>Batch-2 low-item evidence — quoted lines, proof, refutation verdicts (all batch-2 rows except the seven full-template mediums Q-024, Q-032, Q-040, Q-052, Q-053, Q-054, Q-055, and the re-issued Q-037, which also carries a full template below)</summary>

### Q-016 · claim · low · backend/api/middleware/websocket_auth.py:159-160 · #6927 (mover-owns → #6950, batch 2)

- Wrong: the validate_session_cookie docstring (the R55 rewrite) cites
  `middleware/auth.py::_session_username, used by authenticated_principal at :329` — at the
  pin that coordinate misdirects: authenticated_principal is defined at auth.py:600 and calls
  _session_username (def at :585) at :610, while pin auth.py:329 is a blank line inside
  `require_api_key`'s docstring (def :315 — refuter's precision correction; the item first
  named `_api_key_principal`'s docstring, def :275), roughly 270 lines from the object cited.
- Evidence: cite at pin :159-160 (row header previously said :158-160 — pointer P2 sweep
  correction, the cite text sits on :159-160); pin auth.py:585/600/610 confirmed; auth.py:329 blank inside
  the D3/R60 fail-closed prose. Born-wrong at authoring: at 49dd54a90 auth.py held
  _session_username at :348, authenticated_principal at :363, call at :369 — :329 there is
  `await websocket.close(code=close_code)`. No alternative reading rescues it.
- Provenance: authored post-merge by 49dd54a90 (#6950, R55 session-cookie round 2; not an
  ancestor of #6927's merge 5689e80ef); #6927 did not author the text but keeps the file
  (blob differs merge→pin). Mover-owns attaches the defect to #6950 — which is in THIS batch,
  so the item rules here with #6950's rows. Refuted=false; "already stale at its own authoring
  commit" is exact — born-wrong, never drifted (line written once, never touched).
- Fix: repoint to `auth.py::_session_username (def :585), called by authenticated_principal
(:600) at :610`, or name the functions without a line number. Size S; backend.
- Owner: ruled later (ruling 271): one cleanup PR per lane at the audit's end.

### Q-017 · dedup pointer — same defect as batch 1's Q-012 · #6927 candidate, not counted here

Refuter 6927_c1 verified the #6927 candidate NOT-REFUTED on its own legs (:241-242 prose
24/24 vs a 23/23 snapshot; authored true by 70c5d96ae [r204]; made false by merge 9e71bfde8
#7230), but it is the SAME defect as batch 1's Q-012 — same file
frontend/src/**tests**/api-endpoint-contract.test.ts, same ":241-242" comment, same
23-vs-24 mismatch, same mover #7230 (batch 4), same fix. One defect, counted once: see
Q-012's re-attributed section in the batch-1 block above. The 45-item arithmetic therefore
debits this candidate from the 41 auditor verdicts.

### Q-018 · claim · low · docs/operations/profiling-runbook.md:12, :30, :811 · #6930

- Wrong: three present-tense coordinate cites into docker-compose.prod.yml point far from
  their objects at the pin: :12 cites `:151-152` for the `pyroscope.profile: 'true'` labels
  (pin :173); :30 cites `:1095-1096` for GF_SERVER_ROOT_URL=/grafana/ +
  GF_SERVER_SERVE_FROM_SUB_PATH=true (pin :1215-1216); :811 cites `:1074` for the provisioning
  read-only bind-mount (pin :1165). A reader following the numbers lands on unrelated compose
  keys. Runbook blob byte-identical merge→pin — no later PR fixed it.
- Evidence: pin compose truth — each object occurs exactly once (173 / 1215-1216 / 1165), no
  duplicate rescues the cites; what sits AT the cited lines: :151-152 = "degradation …
  ladder in vlm_analyzer" prose, :1095-1096 = security-hardening comment + Prometheus port
  mapping, :1074 = `volumes:`.
- Provenance: at merge c4d1528c6 the objects sat at 151/1180-1181/1130 — so :151-152 was true
  at the merge and broke when later census PRs inserted compose lines; :1095-1096 and :1074
  were already false at the merge (~85 and ~56 lines off; at diff base c4d1528c6^1 they sat
  at 151/1105/1084). Mover-owns: earlier census PRs that inserted compose lines made the
  cites false; #6930's own compose edits deepened the drift for two of the three. Kept
  pre-existing/false at the merge; #6930 keeps the citing file. Refuted=false.
- Fix: re-point the three cites (173 / 1215-1216 / 1165) or drop the numbers and keep the
  substance-only mention, matching how the rest of the runbook anchors compose facts.
  Size S; docs.
- Owner: ruled later (ruling 271): one cleanup PR per lane at the audit's end.

### Q-019 · claim · low · docs/operations/profiling-runbook.md:804-808 · #6930

- Wrong: PR #6930's own UR-9 edit says that when EXPOSE_LAN=true "these API calls need the
  machine key or a login session", where "these API calls" are Grafana's own API calls at
  http://localhost:3002/grafana/api/.... The backend's machine key (MONITORING_API_KEY,
  checked by the auth.py gate) is not a Grafana credential: nothing at the pin wires an
  X-API-Key into Grafana's API (the O1.11 injections serve Prometheus scrape, json-exporter,
  and the Alertmanager→backend webhook path only), and Grafana accepts anonymous access,
  basic auth from GF_SECURITY_ADMIN_USER/GF_SECURITY_ADMIN_PASSWORD, sessions, or auth.proxy
  — the runbook's own procedures two paragraphs later use `-u admin:admin`, not the machine
  key. A reader taking the sentence at face value would authenticate to Grafana's API with
  the monitoring key and fail.
- Evidence: sentence spanning :804-808 at the pin; runbook blob c4d1528c6→pin identical.
- Provenance: authored by PR #6930's own docs edit (UR-9 follow-up text in the same commit
  family); false at its own merge, unchanged at the pin. Refuted=false.
- Fix: rewrite the clause to the pin truth: under EXPOSE_LAN=true the Grafana API needs
  basic auth (the GF_ADMIN pair, default admin:admin) or a login session — the machine key
  is for the backend gate (Prometheus/Alertmanager/json-exporter paths), not Grafana's API.
  Size S; docs.
- Owner: ruled later (ruling 271): one cleanup PR per lane at the audit's end.

### Q-020 · claim · low · .trivyignore:264 · #6931

- Wrong: the AVD-DS-0002 rationale's parenthetical proof reads "(deploy.yml's matrix is
  backend+frontend only, ci.yml:1889-1901)", but the cited ci.yml coordinate has never held
  deploy.yml's matrix: at the pin ci.yml:1889-1901 is the Linear issue-creation shell
  (curl -X POST https://api.linear.app/graphql ... CreateIssue) inside a different job,
  while the matrix lives at .github/workflows/deploy.yml:44-66. Wrong file, present tense.
- Evidence: pin ci.yml:1889-1901 = Linear CreateIssue shell; deploy.yml:44-66 = the
  backend+frontend build matrix.
- Provenance: authored by commit 22ccdde31 (PR #6792, security/dockerfile-misconfig-register,
  2026-10-04) — false at authorship (wrong file named); pre-existing at #6931's merge
  (blob-identical through the merge), still present at the pin; not fixed by any later PR.
  Refuted=false.
- Fix: point the coordinate at the matrix's real home — "(deploy.yml's matrix is
  backend+frontend only, deploy.yml:44-66)" — or drop the coordinate and keep the prose
  claim, which is still true. Size S; backend.
- Owner: ruled later (ruling 271): one cleanup PR per lane at the audit's end.

### Q-021 · claim · low · .github/workflows/ci.yml:2224 · #6931

- Wrong: the vitest rerun step's comment says "Mirrors the pytest jobs' rerun block
  (ci.yml:455-463 et al.)", but at the pin ci.yml:455-463 holds the pre-push hook gate test
  (WP0.1) and the O1.12 pre-commit gate comment — the pytest flake-rerun blocks it names sit
  at ci.yml:1287, 1432 and 1556, 800+ lines away.
- Evidence: pin :455-463 = WP0.1 gate + O1.12 comment; :1287/:1432/:1556 = the three pytest
  rerun blocks.
- Provenance: authored as a true coordinate by 978bb04c1 (PR #6538, 2026-09-12); made false
  by later ci.yml restructuring before #6931's merge (false at merge 80571a602, verified),
  not fixed through the pin; pre-existing on a kept file. Refuted=false.
- Fix: update the coordinate to :1287/:1432/:1556, or replace the line numbers with the step
  name ("the pytest jobs' registered-flakes rerun steps"). Size S; ops.
- Owner: ruled later (ruling 271): one cleanup PR per lane at the audit's end.

### Q-022 · claim · low · docs/architecture/frontend-hooks.md:9 + :364 · #6936

- Wrong: two present-tense coordinate cites into useConnectionStatus.ts point past EOF: the
  frontmatter source_refs entry `useConnectionStatus.ts:useConnectionStatus:117` (:9) and the
  module section's **Source** line citing `useConnectionStatus.ts:117` (:364). At the pin the
  file is 111 lines and `export function useConnectionStatus` sits at :105 — both cites name
  a line that does not exist. The doc's own prose at :206 correctly cites
  `useConnectionStatus.ts:108` (the context throw), so the module's two headline cites
  misdirect while its body is right.
- Evidence: pin hook = 111 lines, export at :105; frontmatter :9 and Source :364 both say 117.
- Provenance: the :117 cite was authored true by 8352c1e07 (docs truth pass inside the merge
  chain) when the export sat at :117 of a 394-line file; made false at the pin by 70c5d96ae
  (r204 hook rewrite, post-merge, non-census mover candidate). Mover-owns attaches the defect
  to the census PR keeping the citing doc — #6936's merge itself carried the cite true.
  Refuted=false.
- Fix: re-aim both cites to the symbol's true pin location:
  `useConnectionStatus.ts:useConnectionStatus:105` (frontmatter) and
  `useConnectionStatus.ts:105` (body Source). Size S; docs.
- Owner: ruled later (ruling 271): one cleanup PR per lane at the audit's end.

### Q-023 · claim · low · frontend/src/hooks/useWebSocket.ts:87 · #6936

- Wrong: the F1.3 dependency-rationale comment still asserts "Callers rebuild this list every
  render — buildWebSocketOptions returns a fresh array". At the pin buildWebSocketOptions
  returns only `{ url: wsUrl }` — never an array and no protocols key at all ("No credential
  is attached: the cookie authenticates the browser.") — so the fresh-array identity hazard
  the comment exists to explain cannot arise, and callers no longer rebuild any list every
  render. The operative claim is false in the very contract the PR's own test pins
  (`expect('protocols' in options).toBe(false)`, api.test.ts:361). The joined-string
  mechanism itself stays harmless (protocols is always undefined) — behaviour unchanged, the
  comment alone is wrong. This is the same defect as batch 1's Q-014 (the missed-by-the-sweep
  useSummaries.ts twin), found here in the hook the sweep did edit.
- Evidence: pin :87 comment; builder api.ts:969-1005 returns `{ url: wsUrl }` only; the PR's
  own test pins the no-protocols contract.
- Provenance: comment authored true by e0cd93333 (pre-merge F1.3 fix); made false by PR
  #6936's builder change (merge c382693bf; the same sweep commit 4447c7cc4 that Q-014/Q-015
  name); still false at the pin (blob unchanged merge→pin). Defect attaches to #6936's chain
  as the first PR that made the text false — consistent with Q-014/Q-015 ruling here.
  Refuted=false.
- Fix: rewrite the stale clause for the shipped contract — "buildWebSocketOptions attaches
  no protocols at all; the joined-string dependency keeps the mechanism inert and correct for
  any future caller that passes protocols" — or trim the fresh-array rationale. Size S;
  frontend.
- Owner: ruled later (ruling 271): one cleanup PR per lane at the audit's end.

### Q-025 · claim · low · docs/reference/backend-entry-points.md:1349 · #6943 (probe)

- Wrong: within the /ws/system Feed-chain bullet (whose publisher-list sentence is fixed by
  Q-024 below), three internal main.py cites drifted: "created and started at
  backend/main.py:1025-1026" → pin :1017-1018; "job_tracker ... (wired at
  backend/main.py:1031)" → pin :1037; "PerformanceCollector is wired
  (backend/main.py:1036-1037)" → pin :1042-1043.
- Evidence: all three born-true at 5f3104335; the #6943 merge's own 15-line insertion shifted
  them (:1026-1027, :1046, :1052 at the merge tree) — the PR made the cites stale in the same
  commit that added the wiring; no re-aim followed (the same-day re-aim commit c76a5f301
  touched only feature-inventory.md and r2-sheet.md).
- Provenance: probe item (empty auditor verdict re-looked per ruling 232). Refuted=false.
- Fix: re-aim the three cites to :1017-1018, :1037, :1042-1043. Size S; docs.
- Owner: `[r271c]` — fix now (ruling 271). Docs' own package beside the audit (one-off UR-52 exception).

### Q-026 · claim · low · docs/reference/feature-inventory.md:1207, :344 (F-008), :352 (F-016) · #6943 (probe)

- Wrong: three rows cite the wiring line by number; no cite points where the wiring is.
  (a) Row :1207 ("the emitter's event broadcaster is never attached (R47, #6943, attached
  only the system one)") cites backend/main.py:1041 — pin :1041 is the PerformanceCollector
  comment; wiring is at :1032. (b) F-008 (:344) and F-016 (:352) cite backend/main.py:1038 —
  pin :1038 is `lifespan_logger.info("Job tracker initialized with WebSocket broadcasting")`.
  Substantive claims in all three rows TRUE (only the system broadcaster attached; event
  broadcaster stays None) — only the line cites are wrong.
- Evidence: distinct provenance per carrier: :1041 born-true (c76a5f301's tree held the
  wiring at :1041), made stale by d6344e031 which edited this very row 2026-10-16 (added
  F-091/F-136/F-144 to its feature list, blob diff 4b79a475c→d752c9391) without re-aiming;
  :1038 cites born 9fcb5f453 whose own tree held the wiring at :1032 (parent blob 0c047031 at
  :1035, own blob 332cfda1 at :1032) — and a full sweep of every unique main.py blob in
  reachable history (169 blobs) finds the wiring only at 1031, 1032, 1035, 1036, 1041, 1048,
  1056, never 1038: born-stale, never true in any tree.
- Provenance: probe item. Refuted=false.
- Fix: re-aim all three cites to backend/main.py:1032 (the wiring line in every tree from
  9fcb5f453 forward, including the pin). Size S; docs.
- Owner: `[r271c]` — fix now (ruling 271). Docs' own package beside the audit (one-off UR-52 exception).

### Q-027 · bug · low · backend/api/middleware/websocket_auth.py:193 · #6950

- Wrong: validate_websocket_jwt gates its success return on
  `hmac.compare_digest(token, token)` — a self-comparison that is always true — so the
  "constant-time comparison" claimed by the function docstring (:179 "Uses constant-time
  comparison for security."), the inline comment (:192), and the module docstring's
  Security-features bullet (:12) is not actually exercised on this path, and the
  `return None` at :195 is dead code. Inert at runtime (decode_token already decided
  validity) but it asserts a security property the code does not have, and a pin-state unit
  test enshrines the tautology.
- Evidence: :193 comparison, :195 dead return, :179/:192/:12 prose; the test
  test_validate_websocket_jwt_constant_time_comparison pins the tautology. #6950 deleted the
  validate_session_cookie twin (its own non-blocking item (b)) but left this line and its
  pinning test — asymmetric cleanup.
- Provenance: pre-existing at base f7a743b6d^1:194 (byte-identical); authored before #6950;
  recorded as non-blocking item (b) in the PR body; attaches to #6950 as the census PR
  keeping the file. Refuted=false.
- Fix: delete the comparison and dead branch (return `claims` directly after decode_token);
  correct the three prose sites (:12 module bullet can stay only if scoped to
  validate_websocket_token, :179 and :192 must go); rewrite or drop the pinning test the way
  its cookie-leg twin was dropped in this PR. Size S; backend.
- Owner: ruled later (ruling 271): one cleanup PR per lane at the audit's end.

### Q-028 · bug · low · backend/api/middleware/websocket_auth.py:196 · #6950

- Wrong: validate_websocket_jwt catches only InvalidTokenError and TokenExpiredError, but
  decode_token calls `jwt.decode(token, _get_jwt_secret(), ...)` and _get_jwt_secret raises
  ValueError("JWT_SECRET is not configured") when settings.jwt_secret is None outside
  test/development environments — the shipped default state (jwt_secret default None;
  environment defaults to "production"; JWT_SECRET appears nowhere in
  docker-compose.prod.yml or .env.example). The ValueError propagates out of
  validate_websocket_jwt and out of the live token leg (auth.py calls it bare inside
  authenticate_websocket; that function's only try/except is around _session_username), so a
  client presenting ?token= kills the handshake with an unhandled exception instead of the
  designed refusal path (no-vote semantics handing the decision to the key leg's
  accept-then-close with 4001/1008).
- Evidence: except clause :196 (base :197); _get_jwt_secret raise at auth_service.py:84-85;
  compose/.env.example absence verified at the pin.
- Provenance: pre-existing at base f7a743b6d^1; #6950's round-2 rework kept this function as
  the live token-leg validator; recorded as non-blocking item (a) in the PR body; attaches
  to #6950 as the census PR keeping the file. Refuted=false.
- Fix: add ValueError to the caught set —
  `except (InvalidTokenError, TokenExpiredError, ValueError):` — so an unconfigured secret
  makes the ?token= credential cast no vote and the key leg decides, matching the PR's own
  no-vote semantics. Size S; backend.
- Owner: ruled later (ruling 271): one cleanup PR per lane at the audit's end.

### Q-029 · claim · low · docs/reference/config/env-reference.md:377 · #6950

- Wrong: the SESSION_COOKIE_SECURE table row's warning condition ends: "The backend warns at
  startup when `EXPOSE_LAN=true`, this is `true`, and this process will not bind TLS
  (`TLS_MODE` set with BOTH `TLS_CERT_PATH` and `TLS_KEY_PATH`)." On its direct parse the
  parenthetical states the no-bind state as one where TLS_MODE IS set with both paths — the
  inverse of the code: the warning fires when NOT (tls_mode != "disabled" and both paths
  set), so TLS_MODE=disabled with both paths set still warns, and TLS_MODE=provided with
  both paths DOES bind under `python -m backend.main`. Read as a fire condition the
  parenthetical is false; read as a suppression condition it silently omits the
  mode-not-disabled requirement. The linked section below the row (:387-437, "The login
  cookie over http and TLS") states the mechanics precisely — including the compose-specific
  truth that the backend's CMD never reads TLS_MODE and the real TLS switch is the
  frontend's SSL_ENABLED — which bounds the harm, but the table row is what a reader lands
  on first.
- Evidence: row :377 at the pin; the code's condition is the negation as stated.
- Provenance: authored by #6950 itself (zero SESSION_COOKIE_SECURE occurrences at base
  f7a743b6d^1; row added in the merged tree); survives to pin unchanged; mover-owns: the
  census PR authored the false-at-pin prose. Refuted=false.
- Fix: reword the parenthetical to the actual no-bind condition — e.g. "(`TLS_MODE` is
  `disabled`, or `TLS_CERT_PATH`/`TLS_KEY_PATH` are not both set)" — keeping the link to the
  precise section. Size S; docs.
- Owner: ruled later (ruling 271): one cleanup PR per lane at the audit's end.

### Q-030 · drift · low · backend/api/middleware/README.md:66 · #6959

- Wrong: the file's tail still offers "Key permissions/scopes" under "Future Enhancements"
  although R60 shipped API-key scopes and the same file's Configuration table documents the
  scoped object entry form — the list contradicts the table in the same file.
- Evidence: tail bullet :66 vs the Configuration table's R60 scoped-object row.
- Provenance: authored by R60 (#6959's own commits) — the self-contradiction was created by
  updating the table while keeping the old list; true at merge and at pin (blob unchanged).
  Refuted=false.
- Fix: delete the bullet or replace it with a pointer to the Configuration table's R60 row
  (scopes shipped; remaining future work is scoping beyond monitoring). Size S; docs.
- Owner: ruled later (ruling 271): one cleanup PR per lane at the audit's end.

### Q-031 · claim · low · docs/architecture/security/authentication-roadmap.md:9 + :34 · #6959 (its own re-aim, born true; block later moved by #6970 + B3.3)

- Wrong: the security roadmap's Phase 0 cites `- `backend/core/config.py:1999-2012` - Current
API key authentication settings` (:9), and the Python block at :33-49 opens with the same
  dead range (`# From backend/core/config.py:1999-2012`). At the pin that range is the
  Logging settings block (:1998-2013 log_file_path/log_file_max_bytes/log_file_backup_count/
  log_db_enabled). The API-key block actually sits at :1794-1874 (section comment :1793;
  api_key_enabled :1794, api_keys :1798 with the R60 scoped-object description,
  @field_validator :1809, parse_api_key_scopes :1811, validator `return out` :1874; :1876
  begins file-dedup, :1884-1885 the OpenTelemetry header). The doc's quoted code body
  (:35-48) still matches the shipped fields verbatim — only the line cites are dead, not
  the quoted code. No rescue reading: the label is explicit ("Current API key
  authentication settings").
- Evidence: pin config.py span above; both dead cites at roadmap :9 and :34.
- Provenance: born TRUE in #6959 — PR-side commit 422b92e9b authored both cites (the
  pre-R60 roadmap said :1093-1101 against a list[str]/hashed-on-startup body); at
  422b92e9b the range was accurate (api_key_enabled :1999, api_keys Field closing :2012).
  Doc blob f8e29df768bbcdf741faa1704f99e8faaf3843b8 identical at 422b92e9b → merge 2f1a82970
  → both parents of the intervening d6344e031 (#7205, content no-op) → pin — the cite died
  untouched. Movers (NOT r-series retirements): 6c5830a67 (merge of #6970, B2.2 reid seam,
  2026-10-10) shifted the block 1999→2006; af7690bfd ([B3.3] delete 43 unread settings
  fields, 2026-10-17) 2006→1802; 8c3c8a7f6 ([B3.3] box 5 upgrade path, 2026-10-17)
  1802→1794. None touched the roadmap. The falseness attaches to #6959's rows: the
  re-aim defect (a re-aim true on its day, dead within days) is #6959's own authorship.
  History deepens the def-anchor case: the original :1090-1098 cite (678c51fc9, #4000,
  2026-01-24) was born-false (block sat at :1189); the re-aim commit 8ddf22b1f (2026-10-09,
  "re-aim 310 drifted core/config.py + main.py cites across 66 docs") re-aimed to
  :1093-1101 while the block sat at :1952 — that re-aim's own re-aim was false for this
  file. Four consecutive line-number anchors in this file false at some point in their
  life. Refuted=false (NOT-REFUTED).
- Fix: re-aim both cites to :1794-1874 (:1794-1807 covers the two quoted fields), or
  better, def-anchor on setting names (api_key_enabled, api_keys, parse_api_key_scopes) —
  the only formulation that has survived this file's history. Size S; docs.
- Owner: ruled later (ruling 271): one cleanup PR per lane at the audit's end.

### Q-033 · claim · low · backend/core/constants.py:273 · #6959 (mover-owns → #7205/B3.1/r223)

- Wrong: the R60 rationale comment cites events.py's write verbs at :1493/:1617/:1733; at
  the pin those lines hold `async def list_deleted_events(` (a READ), an enumerate loop, and
  `failed = 0`. The POST/PATCH/DELETE verbs on the /bulk endpoints now sit at
  :1575/:1699/:1815 — the cite no longer directs a reader to the write endpoints the comment
  argues about.
- Evidence: pin coordinates as stated; replacement coordinates exact (bulk_create_events
  :1587, bulk_update_events :1711, bulk_delete_events :1827, under APIRouter
  prefix="/api/events" :109-110).
- Provenance: born TRUE at authorship — the cite was authored by 422b92e9b ([R60] scoped API
  keys, #6959's own commit; git log -S confirms) and at that commit the three lines held the
  bulk write verbs; accurate on the day, inside the same PR that wrote them. Drift chain
  fully identified: d6344e031 (#7205 merge) 1493→1541 (+48); 834d51097 (B3.1 retire OD-20)
  −1; 361199a99 ([r223]) +22; 6db72093c ([r223] round-1, whose message says "cites
  re-measured" while pushing these cites off target by its +13) →1575. PATCH/DELETE moved in
  lockstep at every stage — one shared upstream insertion, not three independent edits.
  Mover-owns: the movers (#7205, B3.1, r223 ×2) are outside the census — the item rules here
  with #6959's rows. #6959 touched AND kept the file; attachment to #6959 holds for the
  keep, with the drift caused entirely by later PRs. Refuted=false.
- Fix: re-pointing to :1575/:1699/:1815 restores accuracy today but is the fourth
  line-number re-aim in this block's lifetime; the durable form drops coordinates for
  endpoint/handler names (bulk_create_events, bulk_update_events, bulk_delete_events,
  update_event, generate_event_clip, delete_event, restore_event) or scopes the sentence to
  "the bulk write verbs" — the comment's own pin-test caveat (:275-277) already shows
  cite-free derivation is the reliable instrument. Note the trio covers only the bulk verbs
  of the file's seven write verbs, the same under-coverage the original had. Size S; backend.
- Owner: ruled later (ruling 271): one cleanup PR per lane at the audit's end.

### Q-034 · claim · low · setup_lib/core.py:254 · #6959

- Wrong: merge_api_keys' serialization-note docstring cites
  `docker-compose.prod.yml:636 interpolates the same value`; at the pin :636 holds a reid
  comment ("# light lane for the KEPT reid and threat models.") and the
  `- API_KEYS=${API_KEYS:-[]}` interpolation sits at :665.
- Evidence: pin coordinates as stated.
- Provenance: cite authored by R60 (present in the merge blob at setup_lib/core.py:254) and
  true at merge; broken by post-merge docker-compose.prod.yml growth. Refuted=false.
- Fix: retarget the cite to docker-compose.prod.yml:665 or drop the coordinate. Size S;
  backend.
- Owner: ruled later (ruling 271): one cleanup PR per lane at the audit's end.

### Q-035 · drift · low · docs/reference/nvidia-technology-inventory.md:328-329 · #7002

- Wrong: the "NVIDIA TensorRT / Version and status" section still states "TensorRT is
  **not active in Triton** — all three repository models use the ONNX Runtime backend",
  which is false at the pin: reid serves backend: "tensorrt"
  (ai/triton/model_repository/reid/config.pbtxt:24) and the same file's Model Repository
  section (:282) says "reid declares backend: tensorrt since O2.4". The document
  contradicts itself: the two passages sit in adjacent `##` sections, 48 lines apart
  (282 → 328; refuter's stronger exact statement — under the ###-ordinal reading "three
  sections apart" is also defensible, with exactly two ### sections intervening).
- Evidence: :324 `## NVIDIA TensorRT`, :326 `### Version and status`, :328-329 the sentence;
  config.pbtxt:24 the only `backend:` line in that file; :282 the self-contradiction.
- Provenance: authored-false by O2.4 (#7002): the sentence existed true at 1ca36aa03^1
  (then line 326, reid/config.pbtxt then `backend: "onnxruntime"` at :11); O2.4's merge diff
  (exactly two hunks, old 278-290 and 765-773) flipped reid to tensorrt and rewrote the
  Why-ONNX-Runtime section but left this one. Blob 887fce80c identical merge→pin→HEAD —
  still unfixed at HEAD. Refuter's narrowing (good news for the fix): the stale all-three
  claim is exactly one sentence; :108's "all three" refers to NGC-shipped Python packages,
  not backends; "Key limitation" (:371-377) concerns ONNX Runtime's
  TensorrtExecutionProvider, a different mechanism, and remains true. Refuted=false.
- Fix: rewrite the Version-and-status paragraph: TensorRT is active in Triton for exactly
  one model — reid serves a trtexec-compiled 1/model.plan since O2.4 (owner ruling 107),
  compiled at deploy time on the serving GPU (the repo ships no plan binary —
  ai/gateway/export/README.md:147 — say "serves"/"is compiled at deploy time", not "ships"),
  because ONNX Runtime's CUDA EP fails on the GB300 (ruling 106); yolo26 and threat remain
  onnxruntime — and cross-reference the Model Repository section above, which already states
  it correctly. Size S; docs.
- Owner: ruled later (ruling 271): one cleanup PR per lane at the audit's end.

### Q-036 · claim · low · docs/reference/nvidia-technology-inventory.md:395-397 · #7002

- Wrong: the providers paragraph asserts six export scripts select providers directly with
  the CUDA-first list: "Six scripts under `ai/gateway/export/` do this — export_reid.py,
  export_depth.py, export_vehicle.py, export_pet.py, export_fashion_clip.py,
  export_demographics.py — of which only `export_reid.py` corresponds to a model in the
  repository." False at the pin: O2.4 changed export_reid.py's validation providers to
  CPU-only (export_reid.py:623 `providers = ["CPUExecutionProvider"]`), so exactly five
  scripts carry `providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]` — the one
  script whose provider choice is the PR's whole point is counted in the wrong list.
- Evidence: pin census — exactly five CUDA-first scripts (export_depth.py:220,
  export_vehicle.py:185, export_pet.py:175, export_fashion_clip.py:279,
  export_demographics.py:184) plus export_reid.py CPU-only at :623 with the ruling-106
  comment block (:615-624); out-of-scope benchmark hits
  (scripts/benchmark_yolo26_gpu.py:463/:476, benchmark_yolo26_container.py:469) are the
  doc's separately-discussed "measurement arm, not a deployment option" (:371-377) and do
  not change the export-script count. Single-carrier check: "Six scripts" appears at exactly
  one place in the pin tree (:395).
- Provenance: authored-false by O2.4 (this PR): true at 1ca36aa03^1 (export_reid.py:600
  CUDA-first); the PR's own export_reid.py edit made it false and its merge diff left this
  paragraph untouched (the two hunks are the model-repository table and the
  Why-ONNX-Runtime intro). Blob identical merge→pin. Refuted=false; refuter confirms the
  item is accurate as written.
- Fix: change to five scripts (export_depth.py, export_vehicle.py, export_pet.py,
  export_fashion_clip.py, export_demographics.py) and add one clause: export_reid.py instead
  pins CPUExecutionProvider for its ONNX validation pass because ONNX Runtime's CUDA EP
  fails on the GB300 (ruling 106) — its GPU path is the trtexec plan, not an execution
  provider. Keep the "only export_reid.py corresponds to a model in the repository" clause
  intact (independent and still true). Size S; docs.
- Owner: ruled later (ruling 271): one cleanup PR per lane at the audit's end.

### Q-038 · drift · low · ai/gateway/tests/AGENTS.md:5 (+ :17-23) · #7002

- Wrong: two staleness faults in the kept file. (1) The purpose line says the suite covers
  "all five adapter modules" but ai/gateway/adapters/ holds exactly two (enrichment_light.py,
  yolo26.py). (2) The tree at :17-23 names three test files that do not exist at the pin
  (test_adapters_clip.py, test_adapters_florence.py, test_adapters_enrichment.py) and omits
  six that do (test_residency.py, test_entrypoint_residency.py,
  test_dockerfile_agent_gpu_buildable.py, test_export_reid_onnx_fidelity.py,
  test_export_yolo26.py, test_py312_compat.py). PR #7002 inserted its two rows into this
  stale tree (between test_patch_triton_configs.py and test_adapters_yolo26.py, with the
  three phantom rows immediately following as pre-existing context), so its own addition is
  framed by phantom entries while test_residency.py — which O2.4's own docs cite — is
  absent from the map.
- Evidence: byte-identical :5 at the pin (blob 5c81d328f identical merge→pin→boundary→HEAD);
  adapters/ = exactly two modules (no re-exports, no dynamic-import widening — the pin's own
  test_main.py `_ADAPTER_PATCH_TARGETS` pins the two-module set, with
  test_targets_cover_every_shipped_adapter asserting the pkgutil scan's live set equals
  those two); the three phantom rows absent at pin, merge tree, and HEAD; all six omitted
  names present in the pin tests/ (17 entries incl. AGENTS.md/**init**.py/conftest.py).
  O2.4's own added sentence in ai/triton/AGENTS.md cites
  `ai/gateway/tests/test_residency.py` — the same PR that registered rows into a map
  omitting test_residency.py added prose citing it.
- Provenance (refuter corrections folded in): the mover of the five-vs-two fault and of the
  phantom rows is `3b73b9b6b` ("feat(r8-s3): retire the Florence provider and prune the
  gateway to the vlm set", 2026-09-30, PR #6733) — INSIDE the clone's visible merge-line
  history (the merge line is 3106 commits deep; the d6344e031 graft sits on the pin-side
  line, not the merge line). The phantom rows and the "all five" sentence date to the file's
  creation at fdb7d4a5b (#6637, 2026-09-21) where they were TRUE; they went stale at the
  consolidation, not before it. "Omits six" is pin-frame (merge-frame would be four — two of
  the six arrived later via #7205). PR #7002's body acknowledges the surrounding drift as
  reported, not silently repaired (self-review item 11, verbatim: "its pre-existing drift
  reported, not silently repaired") — its precise scope is the AGENTS.md file generally,
  without itemizing the five-vs-two fault or the phantom/omitted rows. Attaches to O2.4
  under pre-existing-on-a-kept-file with the PR registering new rows into the stale tree.
  Refuted=false.
- Fix: correct :5 to "two adapter modules (enrichment_light, yolo26)"; delete the three
  phantom test_adapters_* rows; add rows for test_residency.py,
  test_entrypoint_residency.py, test_dockerfile_agent_gpu_buildable.py,
  test_export_reid_onnx_fidelity.py, test_export_yolo26.py and test_py312_compat.py — and,
  for a full reconstruction, conftest.py (present in the tree, included in the 17-entry
  count). Size S; docs.
- Owner: ruled later (ruling 271): one cleanup PR per lane at the audit's end.
  (Corroborating context, outside this item's path: ai/gateway/adapters/AGENTS.md at the pin
  still carries the five-adapter table including the three deleted modules — the same
  consolidation-staleness pattern, already known to a parallel W3.1 branch whose commit
  8e756e241 deleted this very tests/AGENTS.md on a non-ancestor branch.)

### Q-039 · test · low · frontend/src/hooks/**tests**/useFaceRecognitionApi.test.ts:65 (+ :76, useKnownPersonsApi.test.ts:63) · #7019

- Wrong: the wire-mock fixtures in both kept test files still pin the list endpoint's items
  as carrying household_member_id: mockKnownPerson has household_member_id: 1
  (useFaceRecognitionApi.test.ts:65) and mockKnownPerson2 : null (:76); the fetch-stub person
  fixture has household_member_id: null (useKnownPersonsApi.test.ts:63) — a field the pin's
  backend never sends. The PR's stated standard was that every mock of the LIST path is now
  envelope-shaped, and it corrected the envelope shape of these same fixtures while leaving
  the item-field shape overstating the contract. Same contract-mock error class the PR fixed
  for the envelope, left half-corrected for the items: a reader of the kept tests concludes
  the API returns the member-link field — the exact false success F-280 registers (the chip
  stays blank because the field is writable but never readable on KnownPersonResponse).
- Evidence: pin backend KnownPersonResponse (backend/api/schemas/face_recognition.py:81,
  fields :95-108) declares exactly 7 fields, NO household_member_id; openapi.json parsed
  match, 0 occurrences; KnownPerson model (models/face_identity.py:63) has no such column;
  the LIST endpoint returns KnownPersonListResponse (routes/face_recognition.py:132-135), so
  every wire item is a KnownPersonResponse — the LIST-path mocks (file 1 :175, file 2
  :120/:177/:215/:237) carry a field production never produces. Non-falsifiability: every
  list assertion is fixture round-trip; 0 occurrences of the field outside the fixture
  literals in both files — no assertion ever reads it.
- Classification (refuter correction): contract-mock overstatement, not mock-seam — the
  fixtures assert a wire shape richer than the shipped one; mocks self-consistent, tests
  unable to fail on missing-field behavior.
- Widening (refuter): the phantom field also sits in hand-maintained KnownPersonCreate
  (faceRecognition.ts:206) and KnownPersonUpdate (:220), and the backend's real Create/Update
  schemas likewise lack it — the F-280 cleanup has three type sites, though only :192 is
  load-bearing for these fixtures.
- Field-name distinction the fix must carry (refuter): household_member_id IS writable
  (PATCH /api/household/members/{id}/link-person) and readable on HouseholdMember responses —
  the field is not fictional, only its presence on KnownPersonResponse is.
- Provenance: file 1's field reaches back to ef5e2f57d (NEM-4688, #5622, 2026-02-01,
  byte-identical :65/:76); file 2's to a292ba4c9 (test(F1.3) unit tests for
  useKnownPersonsApi, 2026-10-09, inside #7019's chain). The #7019 diff proper (a51a3aad9,
  merged 4a83b61a1 2026-10-12) touched only envelope shapes — 0 occurrences in either test
  diff. Census PR #7019 kept both tests with fixtures intact (file 2's only later change =
  662fbd575 r214 query-key rename, not the fixture). The PR body itself registers the
  underlying gap as F-280/F-272 (docs/reference/feature-inventory.md:486/:478) and declares
  it out of scope; backend owns the readability gap, the kept test files carry the
  contract-overstating mocks. Refuted=false.
- Fix: drop household_member_id from the three fixture literals (:65, :76, file-2 :63) and
  from hand-maintained KnownPerson (faceRecognition.ts:192) per F-280's plan — test-neutral
  today, converts fixtures from self-consistent overstatement into honest wire shapes; a
  future consumer needs the backend contract change (F-280/F-272) the PR already registered,
  rather than passing on mock charity. Size S; frontend.
- Owner: ruled later (ruling 271): one cleanup PR per lane at the audit's end.

### Q-041 · claim · low · backend/tests/golden/external/test_backup.py:39 + :43 · #7031

- Wrong: two present-tense coordinate cites in the module docstring point far from their
  objects at the pin. Line 39 cites "backup_service.py:324, :354" for the walk that "getattrs
  each one" — at the pin :324 is the column_names line (true) but :354 is the "type
  unresolved" comment; the getattr walk is at :361-362. Line 43 cites
  "backup_service.py:338-341" for "The fix undeferres them at the query site" — at the pin
  :338-341 is the Detection-scope comment; the undefer loop is at :346-349.
- Evidence: pin coordinates as stated.
- Provenance: both cites true at the PR head b763116b7; broken by the PR's own commit
  13a0ff66e, which expanded the undefer comment (+10/-2 in backup_service.py only) without
  re-anchoring the docstring it documents. False at the merge; the test file's post-merge
  blob change is test renames only, which did not touch the docstring. Refuted=false.
- Fix: re-anchor the two cites to :361-362 (walk) and :346-349 (undefer). Land together with
  Q-042's edit (same mover, same PR). Size S; backend.
- Owner: `[r271b]` — fix now (ruling 271). On backend's queue after `[r271a]`.

### Q-042 · claim · low · backend/tests/integration/test_backup_service.py:142 · #7031

- Wrong: the class docstring cites "backend/services/backup_service.py:353-354" for
  "_export_table then walks EVERY mapper column with getattr" — at the pin :353-354 is the
  comment about the unresolved scalar type ("type unresolved -- Any matches how the rows are
  consumed"); the getattr walk it describes is at :361-362.
- Evidence: pin coordinates as stated.
- Provenance: same mover as Q-041 — the PR's own commit 13a0ff66e moved the walk down 8
  lines and did not re-anchor this cite; true at the PR head, false at the merge and pin
  (file blob unchanged merge→pin). Refuted=false.
- Fix: re-anchor to backup_service.py:361-362. Land together with Q-041's edit. Size S;
  backend.
- Owner: `[r271b]` — fix now (ruling 271). On backend's queue after `[r271a]`.

### Q-043 · claim · low · backend/tests/integration/test_ai_audit_api.py:1530 (+ :1525, :1539, :1620, :1653, :1703) · #7031

- Wrong: six present-tense coordinate cites into ai_audit.py in the new test class
  (docstring :1525, :1530-1531, :1539; the _run_job comment :1620 "ai_audit.py:576
  create_job"; the failure message :1653 "ai_audit.py:475-480"; the None-guard cite :1703
  "ai_audit.py:440-446") are all shifted off their objects at the pin: :433-437 is the
  update_progress call (the undefer select is at :450-454), :458 is the not-found
  logger.warning (the deferred read is at :475), :475-480 is the create_partial_audit
  argument list (the per-event except is at :492-497), :440-446 is the undefer comment block
  (the event-is-None guard is at :457-463), and :576 is the zero-path start_job line (the
  main-path create_job is at :593). The docstring's claim "The head line cites below are this
  file's own" is therefore false at the pin.
- Evidence: all six cites true at the merge (b763116b7); broken by eb7ce4431 ([r244]), which
  inserted 17 lines earlier in ai_audit.py (the scoped-key ceiling on get_recommendations)
  without touching this test file.
- Provenance: cites authored by PR 7031 (true at its merge); made false by eb7ce4431 [r244]
  (non-census) between merge and pin; not fixed by any later PR; attaches to 7031 as the
  census PR keeping the citing file. Refuted=false.
- Fix: re-anchor the six cites to the pin coordinates (undefer :450-454, read :475, except
  :492-497, None-guard :457-463, create_job :593). NOTE: a mechanical remap must NOT "fix"
  them by cross-mapping — the five distinct stale values across the six sites are distinct;
  re-point each to its own named object. Size S; backend.
- Owner: ruled later (ruling 271): one cleanup PR per lane at the audit's end.

### Q-044 · claim · low · backend/api/routes/ai_audit.py:443 · #7031

- Wrong: the undefer comment the PR added in the batch-job loop self-cites its own fatal read
  as "event.llm_prompt is read below (:445)" — at the pin the read
  (llm_prompt=event.llm_prompt) is at :475, and :445 is the comment's own line. The cite was
  never true at any reachable revision: at the fix commit 702198999 and at PR head
  b763116b7 the read was at :458 while ":445" pointed at the None-guard's failed_events line;
  the PR's own self-review (b763116b7) re-anchored the test-docstring cites (:445→:458) but
  left this same stale ":445" in the source comment it was fixing. Born-false at authoring,
  zero drift before the post-merge move to :475 (entirely eb7ce4431).
- Evidence: pin :443-446 comment block; :475 the read.
- Provenance: authored by PR 7031 (commit 702198999, kept through b763116b7 despite the
  same-review cite repair); false from creation, false at merge, false at pin. 9fcb5f453
  touched the comment's Precedent line without re-checking the self-cite. Refuted=false.
- Fix: given born-false + drifted twice, dropping the line-precise form is the more durable
  repair ("in create_partial_audit below"); changing ":445"→":475" also works. TRAP: the
  sibling escape claim in _get_queue_stats (:988-992) is TRUE there — do not reword it in the
  same sweep. Size S; backend.
- Owner: ruled later (ruling 271): one cleanup PR per lane at the audit's end.

### Q-045 · drift · low · scripts/uplevel-r94-mutation/README.md:19 (+ :34, :45, M-table :51-68) · #7038 (mover-owns → #7044 lineage)

- Wrong: the README documents a 16-mutant battery, but battery.py at the pin holds 20
  (M1-M20): :19 "For each of the 16 mutants in `battery.py`", :34 "can score 16/16 quiet",
  :45 "Expected output ends with all 16 RED", and the M-table has only 16 rows. battery.py's
  output line (:272) prints caught/len(MUTANTS) dynamically — a real run prints "20/20
  mutants caught", so :45 contradicts the tool's own stdout. Two rows describe superseded
  behaviours: the M14 row says "the quote pair is dropped entirely" while the pin M14 drops
  the single quote (a fair paraphrase — stays); the M16 row says "keep no quote as found
  (the pre-fix policy)" while the pin M16 is "only a single-quoted line is recognized as
  quoted (a double-quoted input stops converting)" — same label, different defect.
  M17-M20 (not-quotable-guard removal, presence-as-yes saved_answer, command-eclipse refusal
  removal, terminator-supplying writer) have no rows at all. Second carrier: battery.py:10's
  docstring itself says "an invented mutant can score 16/16 quiet" — the stale 16 lives
  inside the instrument. (:71's "(13/15 caught at the time)" is explicitly historical and
  stays true.)
- Evidence: all coordinates verified at the pin; battery.py grep count 20 mutants.
- Provenance (item miscast, corrected): #7038 is the ORIGINAL r94 harness PR that CREATED
  the README and battery — the README was TRUE at its merge (f3578d72b, battery = 16, M16
  still original). Killed post-merge by the r94 follow-ups: 2571a8846 (16→17, replaced
  M16's body + added M17; its own message says "17/17 caught", so the author knew the count
  moved) and cf080fb20 (17→20, added M18-M20, updated battery.py's docstring to name M20
  but left docstring :10's "16/16" and the whole README untouched) — both through the #7044
  lineage (merge d393ff9ce, Oct 13 04:15), reached the pin via boundary merge d6344e031
  (PR #7205). Mover-owns attaches to the #7044 lineage, not #7038. Refuted=false.
- Fix (widened): (a) replace the three "16" totals with 20 — or better, drop the literals
  for "every mutant in `MUTANTS`" and let the :272 print carry the number (the count has
  drifted once already); (b) add table rows for M17-M20; (c) rewrite the M16 row + :74-76
  prose for the pin mutant, keeping the dated historical "(13/15 caught at the time)" as-is;
  (d) fix battery.py:10's "16/16" in the same commit, or README and instrument will disagree
  in the opposite direction. Size S; ops — rules with #7044's batch.
- Owner: ruled later (ruling 271): one cleanup PR per lane at the audit's end.

### Q-046 · claim · low · backend/tests/unit/setup_lib/AGENTS.md:31 · #7038 (mover-owns → #7044 lineage)

- Wrong: the gotcha bullet asserts "Most files here are 1:1 with a `setup_lib/` module, but
  four are not - check them before naming a new test file", enumerating exactly
  test_setup.py, test_setup_core.py, test_r94_env_preserving_reruns.py and
  test_download_models_script_vlm_retirement.py. At the pin there are five non-1:1 test
  files: 967f8476d added backend/tests/unit/setup_lib/test_r94_crlf_env_flag.py, named after
  the r94 ruling (like its sibling) and covering the --convert-monitoring-key flag's CRLF
  .env handling in setup.py — there is no setup_lib module named r94_crlf_env_flag. A
  contributor following the bullet checks four examples and can wrongly conclude the
  r94-ruling naming precedent is a single file. False only from #7044's merge onward
  (967f8476d not an ancestor of #7038's merge tip).
- Evidence: five non-1:1 files at the pin (four enumerated + the CRLF test).
- Provenance (item miscast, corrected): true at the merge f3578d72b — the four-file
  enumeration was authored by 1f3ae0729 "[r94] AGENTS.md: name all four non-twin test files"
  (2026-10-12, PR #7038's own branch) and the fifth file did not exist at the merge; made
  false by 967f8476d "[r94 follow-up] the convert flag keeps a CRLF .env's line endings",
  which added the fifth test file without touching AGENTS.md (blob identical merge→pin);
  reached the pin via boundary merge d6344e031 (PR #7205). Mover-owns attaches to the #7044
  lineage, not #7038. Refuted=false.
- Fix: change "four are not" to "five are not" and add test_r94_crlf_env_flag.py to the
  enumeration, described like its sibling: named after the r94 ruling, covering the CRLF
  .env path through setup.py's flag handler. The bullet's tail (credentials /
  models_config / rootful_services untested) is accurate — preserve it. Size S; backend —
  rules with #7044's batch.
- Owner: ruled later (ruling 271): one cleanup PR per lane at the audit's end.

### Q-047 · claim · low · frontend/src/components/ai-performance/AGENTS.md:61 (+ :34/:75, :56, :25, :27, :92) · #7039

- Wrong: the AGENTS.md documenting AIPerformanceSummaryRow contradicts the component at the
  pin in six claim-groups across seven lines: (1) line 61's `export type IndicatorType`
  union omits 'dlq' and says 'yolo26' where the component exports
  'rtdetr' | 'nemotron' | 'queues' | 'throughput' | 'errors' | 'dlq'
  (AIPerformanceSummaryRow.tsx:36); (2) the props block (:34 `yolo26: AIModelStatus;`) and
  usage block (:75 `yolo26={yolo26Status}`) document a prop the component does not have
  (it takes `rtdetr: AIModelStatus;` at :58); (3) :56 says "Responsive: 5 columns desktop"
  while the component's grid is `lg:grid-cols-6` (:366); (4) :25 gives the Queues band
  "Green: <5, Yellow: 5-20, Red: >20" while getQueueStatus (:148-152) renders green for
  0-10, yellow 11-50, red 51+; (5) :27 gives Errors "Green: 0, Yellow: 1-5, Red: >5" while
  getErrorStatus (:173-177) renders yellow for 1-49 and red at >=50; (6) :92's lucide icon
  list omits Archive, which the PR's DLQ card imports. The DLQ row (:28, Green 0 / Yellow
  1-9 / Red >=10) is correct, as are the 5→6 count updates (:11/:19). Eighth staleness
  (refuter widening): the props block :33-47 + usage :74-86 also omit dlqCounts (added by
  a24d095bd).
- Evidence: component coordinates as stated; sixth card unconditional (dlqCounts = {}
  default :325, card :496-503).
- Provenance: PR #7039 edited this same file (counts 5→6 and the DLQ row — both correct) but
  left the exported-types/props/usage/responsive/band blocks stale: the IndicatorType
  omission, the "5 columns" line, the icon-list omission and the dlqCounts omission were
  made false by this PR's own component changes (a24d095bd + d31777c9c); the 'yolo26' naming
  and both threshold bands pre-date the PR (identical at base) and attach as pre-existing
  defects on a kept file. Refuted=false.
- Fix: update the exported-types block to the real union, rename yolo26→rtdetr in the props
  and usage blocks and add dlqCounts, change "5 columns desktop" to 6, restate the Queues
  band as Green 0-10 / Yellow 11-50 / Red >50 and Errors as Green 0 / Yellow 1-49 / Red
  > =50 (or cite the test titles), and add Archive to the icon list. Size S; frontend.
- Owner: ruled later (ruling 271): one cleanup PR per lane at the audit's end.

### Q-048 · claim · low · frontend/src/components/ai-performance/AIPerformanceSummaryRow.test.tsx:76 · #7039

- Wrong: the unit test titled "renders all 5 indicator cards" is false prose at the pin: the
  render call inside it mounts six cards, because the DLQ card renders even when the
  dlqCounts prop is omitted (the sibling test "renders the zero state when the prop is
  omitted entirely" at :688 pins that), and the PR's own golden witness counts six
  (`expect(cards, 'the row now carries six indicators').toBe(6)` in
  ai-summary-row.spec.ts:290). The body asserts only the five original testids so the test
  still passes — only the title states a count the component no longer has.
- Evidence (refuter strengthening): the grid-invariant test :97-130 requires
  cardCount % lg-cols === 0 against grid-cols-6, and :881-885 hardcodes
  `expect(indicators.length).toBe(6)` "6 as of F-038" — two more in-file witnesses that six
  is the current truth. Sixth card unconditional (dlqCounts = {} default :325, card
  :496-503).
- Provenance: title born 8632b8d6b (2026-01-04), true ten months; made false by #7039's
  a24d095bd, which added the card AND updated the sibling aria test 5→6 but left :76.
  Defect authored by #7039's change, false from its merge onward. Refuted=false.
- Fix: retitle to "renders all 6 indicator cards" AND add
  `expect(screen.getByTestId('dlq-indicator')).toBeInTheDocument();` to the body — without
  the added assertion the retitled test inverts the mismatch (title-claims-6/body-proves-5).
  Size S; frontend.
- Owner: ruled later (ruling 271): one cleanup PR per lane at the audit's end.

### Q-049 · claim · low · frontend/src/components/settings/ModelManagementPanel.tsx:38 (+ hooks/AGENTS.md:1360) · #7039

- Wrong: the router-mount comment cites main.py:1648/:1663 — dead at the pin (they hold a
  liveness-endpoint docstring line and an import); the actual mounts are
  `app.include_router(model_management.router)` at :1603 and
  `app.include_router(system.router)` at :1618. The substantive claim — model_management
  mounted BEFORE system so model_management.list_models answers GET /api/system/models —
  remains true (1603 < 1618); only the coordinates misdirect. The same drifted pair is
  carried in frontend/src/hooks/AGENTS.md:1360.
- Evidence: pin main.py:1603/:1618 the two include_router calls; :1648/:1663 unrelated.
- Provenance (refuter correction): TWO authoring commits — the panel comment by 0f0134bac
  and the hooks/AGENTS.md row by ec92ab3ec, the PR's SELF-REVIEW commit about repointing
  dead cites, which wrote two fresh line cites — born-true-then-drifted. The staleness was
  introduced after the merge by retirement commits 3d8418fec (retire F-244) then 9fcb5f453
  (retire F-114); both movers failed to re-point either carrier, so mover-owns routes the
  drift to those PRs — reported because both carriers sit in this audit's kept set at the
  pin. Refuted=false.
- Fix: re-point BOTH carriers to main.py:1603/:1618 in the same edit, or use the count-free
  order-claim form ("mounted before system.router") so the comment survives unrelated
  main.py churn — the second carrier MUST move in the same edit. Size S; frontend.
- Owner: ruled later (ruling 271): one cleanup PR per lane at the audit's end.

### Q-050 · claim · low · frontend/tests/golden/shell/tour.spec.ts:55 + :303 (+ feature-inventory.md:357) · #7039

- Wrong: three carriers cite the ProductTour mount as `App.tsx:342` — the spec's header
  (:55, "The mount (App.tsx:342)") and body (:303, "(App.tsx:342) does not care about
  auth"), and the F-021 inventory row (feature-inventory.md:357). At the pin the mount
  `<ProductTour />` is at App.tsx:361 and :342 is a /heatmaps route line. The substantive
  claim — the mount is app-wide, inside BrowserRouter outside Routes/ProtectedRoute, so the
  tour also boots on /login — is verified true at :361; only the coordinate misdirects.
- Evidence (provenance chain, refuter-corrected chronological): born true 8f87050d7 (F-021
  tour demoted — the mount WAS :342); made off-by-one by 62c72165e ([r132], mount
  :342→:341) BEFORE #7039 existed — the inventory coordinate predates the PR (transcribed,
  not authored); born-false-in-place 4238c6260 rewrote the spec writing pin-phrased cites at
  its tip's stale value; merge-state off-by-ten from 453bec830 (F-034, inside the PR);
  post-merge d6344e031 −1 (real content consumption) and 70c5d96ae [r204] +10 → :361
  (attribution CONFIRMED). Carrier census: exactly three lines.
- Provenance: coordinate inherited from the pre-existing spec and carried through #7039's
  rewrite of the spec (merge blob 109c21dc) without re-verification — false at the PR's own
  merge; the underlying app-wide-mount claim is #7039-verified and true. Refuted=false.
- Fix: re-point all three carriers to the current mount line (App.tsx:361), or replace the
  line number with a stable anchor ("the <ProductTour /> line just inside </BrowserRouter>")
  so the cite survives App.tsx churn — the mount has drifted three times post-qualification
  and survived one re-anchoring pass that fixed neighbors (bc43387c8 missed this row;
  r148a-style re-anchor passes should sweep this coordinate class). Size S; frontend.
- Owner: ruled later (ruling 271): one cleanup PR per lane at the audit's end.

### Q-051 · claim · low · frontend/tests/golden/operations/config-inspector.spec.ts:94 · #7039

- Wrong: of the spec's three coordinates in the testid-drop explanation, one is stale and
  one was never true: "SystemMonitoringPage.tsx:738 passes data-testid=
  \"config-inspector-panel-section\"" points at a line that is now `</div>` — the pass-site
  `<ConfigInspectorPanel data-testid="config-inspector-panel-section" />` is at :709 (the
  B3.1 retirements removed the QueueMetricsPanel/WorkerStatusPanel sections above it; drift
  chain chronological: 17f450687 → 02cca65bf → 82f49c92e — the pass-site moved twice in one
  day); and "its root <div> (:135)" is off by three — the panel's root div is at :138 (:135
  is the closing brace of the error branch; the panel blob is byte-stable since January, so
  :135 was false at authoring). "accepts `_props` (:73)" is exact. The substantive claim —
  the page passes a testid the panel accepts as `_props` and never spreads, so the testid is
  dropped and the spec pins its absence — is verified true. Path precision (refuter): the
  panel is frontend/src/components/developer-tools/ConfigInspectorPanel.tsx, NOT system/.
- Evidence: pin coordinates as stated.
- Provenance: spec authored on #7039's branch (created by 2099deab6, first merged in this
  PR): the :738 cite was true at merge and drifted afterwards via the retirement commits;
  the :135 root-div cite was false when authored. Mixed provenance — half later-PR drift,
  half authored defect. Refuted=false.
- Fix: re-point to SystemMonitoringPage.tsx:709 and ConfigInspectorPanel.tsx:138 (or anchor
  on the `_props` signature :73); re-derive-at-edit-time is well-motivated here since the
  neighboring sections are being retired piecemeal. Size S; frontend.
- Owner: ruled later (ruling 271): one cleanup PR per lane at the audit's end.

### Q-056 · test · low · backend/tests/unit/services/test_system_broadcaster.py:1432 · #7041

- Wrong: the new timeout test drives _check_redis_health's except-branch entirely through an
  AsyncMock seam — `health_check.side_effect = RedisTimeoutError(...)` — but production
  wiring cannot deliver that exception: RedisClient.health_check (core/redis.py:705-725)
  absorbs every Exception into a returned dict, so no production input path raises inside
  the helper. With shipped wiring the helper's except branch is DEAD (only consumer
  system_broadcaster.py:1008; every construction injects a real RedisClient — main.py:1017
  via init_redis building `client = RedisClient()` at core/redis.py:2767-2790;
  websocket.py:733 / job_tracker.py:751 via the get_system_broadcaster() singleton;
  SentinelClient never wired, and it would also absorb). The test pins a branch only a mock
  can reach, and its docstring (:1436-1437, "the failure redis actually raises under load")
  implies the production path raises — the opposite of the seam's synthetic nature.
- Evidence: def :1432 (decorator :1431), body :1441-1449; seam unreachable at the pin
  (the production client absorbs); mirrored siblings
  test_system_broadcaster_check_redis_health_failure (:1332, ConnectionError) and the storm
  probe (:1361, RedisTimeoutError) use the SAME AsyncMock-raising seam — a seam-documentation
  or re-seaming repair has THREE sites, not one.
- Provenance: authored by #7041's own diff (88e0d3457, the sole branch commit); test blob
  860634ba6 identical merge→pin; census PR kept the test (correct framing). Refuted=false
  (NOT-REFUTED with the widening above).
- Fix: document the seam's synthetic nature in all three sibling docstrings (standalone-
  compatible — the docstring currently implies production raises), or re-seam the test
  through the production path — which goes RED at this pin until Q-053's fix lands (the
  helper discards the unhealthy dict and returns True), so the production-seam test must be
  sequenced behind Q-053 or the two items fixed together. Size S; backend.
- Owner: ruled later (ruling 271): one cleanup PR per lane at the audit's end.

### Q-057 · claim · low · backend/services/system_broadcaster.py:1011 (+ test docstring :1434-1440) · #7041

- Wrong: the comment this PR added to the new RedisError arm asserts "without it a timeout
  under load escapes this helper (and the call site in _get_system_status is outside its
  guard)". At the pin that escape cannot happen: the only production client type is
  RedisClient, whose health_check absorbs every Exception — redis.exceptions.TimeoutError
  included — into a returned dict. The arm is dead in production and the documented
  mechanism is false; a reader trusting it will believe the health check correctly reports
  unhealthy under timeouts when it actually returns True (the discarded dict — Q-053's
  defect). The twin docstring in the new test (test_system_broadcaster.py:1434-1440, "the
  failure redis actually raises under load ... an escape there costs the whole broadcast
  tick") repeats the same false mechanism.
- Evidence: RedisClient.health_check (core/redis.py:705-726) absorbs every Exception into a
  dict; no production construction passes a raw client (main.py:1017 / core/redis.py
  init_redis :2767-2790; SentinelClient never wired, and would also absorb).
- Provenance: born-false at authoring (88e0d3457, the sole branch commit); zero drift; the
  comment was never true at any reachable milestone. TRUE halves that must survive the
  reword: the hierarchy clause (RedisError covers redis.exceptions.TimeoutError — MRO
  verified) and the outside-guard parenthetical (:807 sits outside the guarded try
  :785-801). TRAP (refuter): the same commit added a near-identical escape claim to
  _get_queue_stats (:988-992) where it IS true (get_queue_length calls the raw
  client.llen() at :1021-1031) — a mechanical "reword the #7041 comments" fix would damage
  a true comment; reword ONLY :1011-1013. Secondary (out of scope): the deprecated
  _get_health_status :1093 sits inside its own try whose tuple lacks RedisError. Refuted=false.
- Fix: rewrite the comment (and the twin test docstring) to state the wrapper absorbs all
  exceptions and this arm only guards non-wrapper clients — replace with the real rationale
  (defense-in-depth) — or make the arm live by inspecting the returned dict, which also
  fixes the underlying behavior (that is Q-053's fix). Size S; backend.
- Owner: ruled later (ruling 271): one cleanup PR per lane at the audit's end.

### Q-058 · claim · low · docs/reference/feature-inventory.md F-031 row (five stale backend cites) · #7015 (probe)

- Wrong: the F-031 inventory row cites five backend lines that no longer point at the
  constructs the row describes. At the pin: events.py:282 is a blank line inside the
  sanitize_csv_value docstring (the cited `list_events` sits at :317); events.py:468 is
  `if start_date:` (the `order_by` statement sits at :513, its comment at :512);
  vlm_analyzer.py:671 is a blank line (the `event = Event(` construction sits at :677);
  :692 is `await session.flush()` (the `row = EventVerification(` construction sits at
  :698); :980 is the `verdict: str,` parameter of `_notify_decision` in
  vlm_analyzer.py (its def sits at :973 — name correction per pointer P2 sweep: the
  function is `_notify_decision`, not `_should_notify`; the `broadcast_event` call sits at
  :1077). Per-cite provenance: the events.py cites were born 3f614c49e (2026-10-11 18:44,
  FE-2 lane) citing :281/:467 true at authoring, re-anchored to :282/:468 by 1fb9b87d1
  (2026-10-13 12:10, "docs: re-anchor the events.py cites my F-057 insert moved"), and
  broken by the two r223 commits in #7201 (merge cd68cbca6, 2026-10-16 20:40):
  361199a99 (Oct 16 14:06) moved 283→304/478→500 and 6db72093c (Oct 16 18:25)
  →317/:513 — neither re-measured the F-031 row (note 834d51097, Oct 16 14:01, OD-20,
  briefly restored :282 before 361199a99 broke it again). The vlm_analyzer.py cites were
  born 264023fe1 (2026-10-09 19:35, the original 294-row inventory), true at birth and at
  #7015's merge (blob 30fc6c06262a identical 264023fe1→31b3e08ea), then broken post-merge:
  f9a18d028 (2026-10-15 00:19, UR-48 cure, rode #7165's merge ea55d55e0; +2 at ~:490)
  671→673/692→694/980→982, and a8760714f (2026-10-15 14:16, [r199] acknowledge analysis
  stream, #7182's merge 5d990377e; hunks @476 +4 and @792 +91) 673→677/694→698/982→1077
  (the 91-line insert :796-887 lands between the writes and the broadcast). Probe item
  (empty auditor verdict re-looked per ruling 232; the PR's own diff is clean — these
  candidates are the PR's subject matter, the F-031 fix, carrying stale cites in the row
  that records it). Refuted=false.
- Fix: re-point the five cites to :317/:513/:677/:698/:1077, or convert to def-anchored
  cites (`async def list_events`, the order_by statement, `event = Event(`,
  `row = EventVerification(`, `broadcast_event`). One edit, one row. Size S; docs.
- Owner: ruled later (ruling 271): one cleanup PR per lane at the audit's end.

### Q-059 · claim · low · docs/reference/feature-inventory.md F-031 row (bug sentence + drifted span) · #7015 (probe)

- Wrong: the same F-031 row asserts in present tense that the mapper "…SIX-field literal
  … DROPS verification/verdict on the floor" (citing DashboardPage.tsx:206-221) — at the
  pin the mapper does NOT drop either field: :231 `verification: event.verification`,
  :232 `notify: event.notify` (this PR's own fix), and the row's own later narrative
  records the cure twice. The span also drifted: the mapper sits at :206-235 at the pin;
  :206-221 ends inside the F-031 comment. Sibling rows mark bug narrative as history (the
  F-021 convention); this row does not. Born 3f614c49e (Oct 11 18:44) true and
  future-tense-correct; content made false by #7015's own merge (Oct 11 19:29); never
  re-tensed. Classification: born-true-then-drifted at the PR's own merge. Probe item
  (same re-look). Refuted=false.
- Fix: mark the bug sentence as history (F-021 convention) or re-tense it past; re-bound
  the span to :206-235. Size S; docs.
- Owner: ruled later (ruling 271): one cleanup PR per lane at the audit's end.

### Q-060 · drift · low · docs/uplevel/packages/backend.md:294-296 · #7044

- Wrong: the merged r94 package record's defect bullet still reads present tense — "on a
  re-run, the LAN-exposure prompt defaults to `n`" — and cites coordinate lines setup.py:685
  (quick path), :900 (guided), and :447, :449, :482-:491 (the EXPOSE_LAN/FRONTEND_BIND_
  ADDRESS derives per the bullet's own prose). At the pin every cited coordinate holds
  unrelated code: :685 is the closing `)` of the foscam prompt, :900 is a comment inside an
  OSError handler, :447 blank, :449 the secrets-dir docstring, :482 the
  `def generate_env_content` line, :491 its closing `"""`. The described behaviour no
  longer exists either: the re-run default is now `saved_answer(existing_env, "EXPOSE_LAN",
"n")` (setup.py:784-785 quick, :1011-1012 guided), which defaults to the value already in
  .env, not to `n`. The bullet wraps to :298.
- Evidence (provenance CORRECTED by the refuter): the fix was INTRA-PR — 4430762dd ([r94]
  re-runs keep existing config) is INSIDE #7038's own chain (~5 hours after the record
  de661e070 wrote, BEFORE the merge f3578d72b); there is NO post-merge fixer (the only
  later backend.md-adjacent commit, d6344e031, touches only the
  --convert-monitoring-key handler). #7044's only backend.md touch is the register update
  888974d16 (`**PR:** none yet` → `#7038 (merged)`), leaving the checkboxes deliberately
  untouched. Authored by de661e070 (cites true at authorship); made stale by f3578d72b
  reflowing setup.py; pre-existing at #7044's merge d393ff9ce, unchanged merge→pin; #7044
  is the census PR keeping the citing file (pre-existing-on-a-kept-file). Refuted=false.
- Fix: mark the defect fixed-at-pin naming 4430762dd in #7038 (not a post-merge commit);
  convert the bullet to past tense; the file's own stated convention is "Cited by function,
  not line" — cite the mechanism (saved_answer) instead of line numbers; if re-anchoring
  instead, pin coordinates: prompts :784/:1011, derives :533/:535/:567-577; alternatively
  drop the bullet. Size S; docs.
- Owner: ruled later (ruling 271): one cleanup PR per lane at the audit's end.

### Q-061 · claim · low · docs/operator/admin/security.md:33-36 · #7044

- Wrong: the admin security guide asserts a universal cure for REFUSAL_case_mismatch: "add
  the object entry … replacing the plain entry" — false for exactly one of the seven
  refusal cases the same block enumerates: the no-monitoring-key case mints a FRESH key
  (setup.py:722/:921 `existing_env.get("MONITORING_API_KEY") or generate_api_key()`), so
  there is no old plain entry carrying the old value to replace, and merge_api_keys
  dedupes on VALUE (core.py:282-285/:321-327), so the stale plain entry's value — if one
  existed — stays live; replacing the entry by KEY does not retire the old grant. The
  other six refusal cases (plain-key entries naming the key in MONITORING_API_KEY) are
  correctly covered. Provenance: born false TWICE — 4430762dd (#7038) authored the bullet
  over a six-refusal list, and 2571a8846 (#7044 PR-side) rewrote it into the universal
  "any of the seven" form; #7044 DELIVERED the false sentence via merge d393ff9ce plus
  PR-side commits 2571a8846 and 593dc4d8e — this is #7044's own text, not a
  keeper-miscast. Refuted=false.
- Fix: narrow the sentence to "for every other one that still names the key in
  MONITORING_API_KEY …", or add the no-monitoring-key case to the exceptions. Do NOT
  touch the other six cases — they are correct. Size S; docs.
- Owner: ruled later (ruling 271): one cleanup PR per lane at the audit's end.

</details>

### Q-037 · drift · low · ai/triton/AGENTS.md:168 (+ :46-59, :160, :171-175, :177-191) · #7002 (re-issued; refuter REFUTED the mover leg only)

- Wrong: the Model Repository section's lead sentence says "model_repository/ ships 14 model
  directories. 12 are loadable at startup" against a tree that holds exactly three
  (yolo26, reid, threat — `git ls-tree` at the pin; models.yml carries exactly three
  `triton_name:` entries; ai/gateway/Dockerfile:56 copies only model_repository/). The
  supporting blocks share the staleness: 14 tree rows (:46-59), a 13-row model table
  (:177-191), a healthcheck comment sized for 14 (:160), and a follow-up-count paragraph
  (:171-175). O2.4 flipped the reid table row onnxruntime→tensorrt (:186) and added its reid
  paragraph directly under the stale table, inside the section led by the false 14-count
  sentence.
- Evidence (refuter-verified digit-for-digit): every coordinate and quote byte-exact at the
  pin (blob 90c1614be identical 1ca36aa03→d6344e031→both pin parents→pin→HEAD — none of the
  1288 intervening commits repaired the section); 3 dirs at every ref; the O2.4 flip at :186
  real (at merge parent 28467f85d the row read "| reid | onnxruntime | 16 |").
- Provenance (refuter CORRECTION — the one REFUTED leg, re-issued): the staleness was
  pre-existing at the merge (the :168 sentence is byte-identical at merge parent 28467f85d;
  the tree already had 3 dirs), authored TRUE by 610882b47 (#6645, 2026-09-22, when the tree
  held 14). The exact mover of the falseness is `3b73b9b6b` (2026-09-30, "feat(r8-s3): retire
  the Florence provider and prune the gateway to the vlm set", merged as PR #6733 =
  c69add19c): 14 dirs at its parent, 3 at it, deleting exactly the 11 non-shipped dirs'
  files; ancestor of both the merge parent and the pin; PR #6733 touched NO AGENTS.md, so
  pre-existing-on-a-kept-file for O2.4 remains the right attachment. The earlier item text's
  "the exact mover sits outside the shallow window" was the refutation — an instrument
  artifact: a plain `git log <pin> -- <path>` walk collapses to the d6344e031 graft (which
  sits on the pin-side line, NOT an ancestor of the merge parent; the merge line is 3106
  commits deep and fully intact) and hides the mover; `--full-history` shows it. Fix-wording
  guard (refuter): say reid "serves"/the plan "is compiled at deploy time on the serving
  GPU" — the repo ships no plan binary (ai/gateway/export/README.md:147). One wording
  imprecision fixed: the reid paragraph sits under the 13-row TABLE, two blocks below the
  :168 sentence. Refuted=false as re-issued.
- Fix: rewrite the section to the shipped reality — three directories (yolo26, reid,
  threat), loadable at startup once the entrypoint symlinks version dirs from the model
  cache; replace the 13-row/14-dir table or point at nvidia-technology-inventory.md's Model
  Repository section (corrected by this same PR); fix the tree block :46-59, the healthcheck
  comment :160, and the follow-up-count paragraph :171-175. Size M; docs.
- Owner: ruled later (ruling 271): one cleanup PR per lane at the audit's end.

### Q-024 · claim · medium · docs/reference/backend-entry-points.md:1530 (+ :1349) · #6943 (probe)

- Wrong: two entries in the backend's dead-code registry assert the WebSocketEmitterService
  is unwired wholesale: :1530 "WebSocketEmitterService is unwired wholesale (see WebSocket
  chapter /ws/system): backend/main.py never imports it, get_websocket_emitter() callers are
  all no-arg, and the singleton's broadcaster/redis slots stay None
  (backend/services/websocket_emitter.py:636-641) — _dispatch_event can only warn
  (:385-389)", and :1349 (the /ws/system Feed-chain bullet's publisher list) "is wired to
  nothing in prod (see Dead Marks)". Every clause is false at the pin: main.py:147 imports
  get_websocket_emitter (the PR's own import) and main.py:1032 calls
  `await get_websocket_emitter(system_broadcaster=system_broadcaster)` (the PR's own
  one-line fix), so websocket_emitter.py:377-378 — `if channel == "system" and
self._system_broadcaster is not None: await self._dispatch_to_system_broadcaster(...)`
  — now fires, and _dispatch_event returns True rather than only warning (:385-389 /
  :262-263). A false "unwired wholesale" entry in the dead-code registry marks a live
  delivery path (verdict-engine transitions and health changes over /ws/system) as dead —
  it feeds retirement planning on a living surface. Severity rationale: this is the
  register retirement packages act on; a wrong entry here is the highest-harm doc-defect
  class this audit has recorded.
- Evidence: pin main.py:147/:1032; websocket_emitter.py:377-378/:385-389/:262-263; both
  lines byte-identical merge→pin (md5 0917129fca483589 :1530, dc605a46737ff5db :1349).
- Provenance: born TRUE 5f3104335 (2026-10-09 16:23 — `git show 5f3104335:backend/main.py |
grep -c get_websocket_emitter` = 0); made false by #6943's own merge 9eb963ebf hours the
  same day; unrepaired through d6344e031, 3d8418fec, 9fcb5f453, e8e2714ba; false at the
  pin. The same-day re-aim commit c76a5f301 (21:48, "Every main.py cite is re-aimed by
  diff") touched only feature-inventory.md and r2-sheet.md — entry-points.md was never
  re-aimed. Probe item (empty auditor verdict re-looked per ruling 232). Refuted=false.
- Fix: rewrite :1530 to the residual truth — main.py imports and wires the emitter
  (main.py:147, :1032) with the system broadcaster only; the event_broadcaster and
  redis_client slots stay None in production (no call site passes them; four call sites —
  main.py:1032, cameras.py:1798, job_progress_reporter.py:117/:158 — all bare), so only
  the system-channel branch of _dispatch_event delivers and the event-broadcaster branches
  still dead-end. Rewrite :1349's publisher-list sentence to name the main.py:1032 wiring.
  Size M; docs.
- Owner: `[r271c]` — fix now (ruling 271). Docs' own package beside the audit (one-off UR-52 exception).

### Q-032 · claim · medium · docs/reference/config/env-reference.md:372 · #6959 (mover-owns → r95, 75ea5ee10)

- Wrong: the API_KEYS table row asserts entries are "accepted by `verify_api_key`". At the
  pin there are exactly two verify_api_key definitions — dlq.py:42 and system.py:272 — and
  both skip every scoped entry (dlq.py:105-106 `if _key_scope(k) is not None: continue`,
  system.py:328-329) and return 401 "Invalid API key". So the blanket assertion is false
  for the scoped form the very same row documents: a scoped monitoring key is refused on
  the DLQ and system legacy paths. Dangerous read: an operator hitting that 401 may
  conclude the object form is malformed and re-list the value plain — which the absorption
  rule (verbatim in row 372 itself) turns into a full unscoped grant. The middleware gate
  honoring scopes (auth.py _key_entry_for_digest/_key_admits) is a separate conjunct and
  does not rescue the clause.
- Evidence: the two verify_api_key defs and their skip/401 lines; the pinning test lives at
  backend/tests/unit/api/test_api_key_scopes.py:858 (refuter's path correction — not
  backend/tests/test_api_key_scopes.py); row 371 (API_KEY_ENABLED) itself pins
  verify_api_key to the DLQ/some-/api/system routes, so the row's own conjunct structure
  makes the false half precisely the verify_api_key clause.
- Provenance: the row is byte-identical from R60's merge 2f1a82970 through the pin; the
  scoped-entry exclusion in the legacy copies was added by r95 (75ea5ee10 — ancestor of the
  pin but NOT of R60's merge; pre-r95 dlq.py has zero _key_scope) after R60 merged.
  Mover-owns re-attributes the defect to r95, which is outside the census — the item rules
  here with #6959's rows. Refuted=false (NOT-REFUTED, ~76k tokens, 18 tool uses).
- Fix: scope the assertion: plain entries are accepted by verify_api_key and the auth gate;
  scoped entries are honored only by the middleware gate and deliberately refused by the
  legacy verify_api_key consumers (dlq.py, system.py). Size M; docs.
- Owner: `[r271c]` — fix now (ruling 271). Docs' own package beside the audit (one-off UR-52 exception).

### Q-040 · bug · medium · backend/services/backup_service.py:361 · #7031

- Wrong: the getattr-walk that builds backup rows does `getattr(model, col.key)` per column
  and serializes the result; Alert carries a `metadata` reserved-attribute (SQLAlchemy
  MetaData at backend/models/alert.py:121, the comment at :120 names the collision reason)
  that is NOT a mapped column with an alternate attribute name — so the walk's "metadata"
  key is the raw MetaData object. json-safe conversion stringifies it to
  `"metadata": "MetaData()"`, and the real `alert_metadata` payload is absent from the
  backup row. Live repro (refuter) against a real seeded Alert: `getattr(a, "metadata")` IS
  Alert.metadata (MetaData), `getattr(a, "alert_metadata")` is the seeded dict; walk + dumps
  yields `"metadata": "MetaData()"` with the payload absent. Restore side is STRONGER than
  the auditor stated: restore_service.py restores "alerts" via `model_class(**processed_data)`
  — `Alert(**{"metadata": "MetaData()"})` silently succeeds (unmapped attr swallowed), and
  alert_metadata stays NULL — the same silent loss on the way back. Sharpenings: NULL rows
  ALSO get the bogus "MetaData()" string, and restore doesn't write null — the key is
  swallowed to the unmapped attribute. Corroboration: mapped_column("<string>") occurs
  exactly once repo-wide — Alert is the only affected walked model. The module docstring
  (:344-345, F-101-pending framing) saw the divergence and named it pending; the shipped
  walk still loses the payload on both legs.
- Evidence: walk at :361-362 (sole writer _export_table :222-223, no Alert-specific
  fallback); models/alert.py:121 with the collision comment :120; blob 38ad7b64d identical
  merge→pin; f79f066e8 (ancestor) carries the same walk — not new code here.
- Provenance: pre-existing walk kept by #7031 (the PR's own commit 13a0ff66e moved it down 8
  lines without touching the behavior — the same commit that made Q-041/Q-042's cites
  stale); attaches to #7031 as the census PR keeping the file. Refuted=false (NOT-REFUTED,
  ~84k tokens, 56 tool uses; all six refutation directions failed).
- Fix: in the walk, special-case the reserved-attribute collision — read
  `getattr(model, "alert_metadata")` for the "metadata" key (or skip non-column reserved
  attrs and serialize the mapped `alert_metadata` column explicitly); the restore side then
  round-trips. Do not generalize: Alert is the only walked model with the collision.
  Size M; backend.
- Owner: `[r271b]` — fix now (ruling 271). On backend's queue after `[r271a]`.

### Q-052 · bug · medium · backend/services/system_broadcaster.py:1008-1014 · #7041

- Wrong: the new RedisError arm in _check_redis_health discards the wrapper's unhealthy
  dict and the success path returns True unconditionally — the dict the wrapper returns
  (which carries the production failure mode: RedisClient.health_check absorbs every
  Exception into a returned dict, so the only way _check_redis_health learns of trouble
  is that dict) is read as healthy. Concretely: `try: result = await
self._redis.health_check() … except RedisError: return True` — the except arm returns
  True without inspecting anything, and the non-exception path returns True regardless
  of what the dict says (:1008-1014). Net effect: an unhealthy Redis surface never flips
  the broadcaster's health bit; the helper reports healthy on every input it can
  actually receive.
- Evidence: authoring 88e0d3457 (born-false at authoring — zero drift); core/redis.py
  blob 879599cd18 identical authoring→pin (health_check absorbs every Exception into a
  returned dict).
- Refuted=false (NOT-REFUTED).
- Fix: capture the dict, branch on its healthiness (healthy → True; unhealthy → mark
  unhealthy / return False), keep the RedisError arm as defense-in-depth for
  non-wrapper clients, and log the payload. Size M; backend.
- Owner: `[r271a]` — fix now (ruling 271). First on backend's queue, after the packages it holds (UR-52, ruling 269).

### Q-053 · bug · medium · backend/services/system_broadcaster.py:1008 companion :1320 · #7041

- Wrong: companion to Q-052 (one fix covers both) — the twin test at :1320 stubs
  health_check with a bare AsyncMock (the row header previously said :1321 — pointer P2
  sweep correction; :1321 is the line that sets `health_check.return_value=True`), so once
  the dict-inspecting fix (Q-052) ships, that
  test breaks with AttributeError (AsyncMock's return value is a Mock, not a dict) and
  the fix arrives RED. The bare stub must become
  `return_value={"status": "healthy"}` (or the codebase's house-style equivalent —
  system.py:893-894/:5346-5347 show the dict-returning stub idiom) in the SAME edit as
  Q-052's fix. Two callers of _check_redis_health (:807 and :1093) keep the boolean
  contract — the fix must preserve their expectations. The secondary seam at
  dependencies.py:303-312 is OUT OF SCOPE (different helper).
- Evidence: twin test :1320 bare AsyncMock (at :1321 `health_check.return_value=True`);
  house style system.py:893-894/:5346-5347.
- Refuted=false (NOT-REFUTED).
- Fix: as above — the twin-test edit is LOAD-BEARING: without it the dict-inspecting fix
  ships RED. Size M; backend.
- Owner: `[r271a]` — fix now (ruling 271). First on backend's queue, after the packages it holds (UR-52, ruling 269).

### Q-054 · bug · medium · backend/services/system_broadcaster.py · #7041 — REFUTED AS WRITTEN; re-issued below

- **Refuted as written (owner pointer, 2026-10-20 01:46Z).** The as-written claim —
  `retries=10` accepted but never wired, `Retry(NoBackoff(), 0)` at :564/:631/:693,
  loop absorb at :1235 — is disprovable by one line at the pin:
  `git grep -E 'NoBackoff|Retry\(' 41bc0fce7 -- backend/` returns nothing; the pin's
  system_broadcaster.py has no `retries` and no `Retry(` anywhere, and :564/:631/:693
  are pub/sub listener except-handlers, not retry constructions. The death chain,
  the fix, and the PR-body follow-up note were all built on a mechanism that does
  not exist in the code.
- **Refutation-pass note (owner-mandated):** Q-054's refuter returned NOT-REFUTED on
  a claim a one-line `git grep` disproves — the refuter verified the cited lines
  contained text but never checked the quoted tokens against those lines. Rule going
  forward: a refuter must run its own `git show`/`grep` against every load-bearing
  quote before returning a verdict; a verdict asserting text the refuter never
  mechanically checked is worth nothing.

### Q-054R (re-issue, keeps the number) · bug · medium · backend/services/system_broadcaster.py — nine builtin-only except handlers let redis.exceptions.TimeoutError escape · #7041

- Wrong: NINE handlers in system_broadcaster.py guard Redis calls with builtin-only
  except tuples, so `redis.exceptions.TimeoutError` — a `RedisError`, not a builtin
  (import at :33 brings in only `RedisError`; the tuple names resolve to the
  builtins) — escapes every one of them. The census at the pin
  (41bc0fce7, `git show 41bc0fce7:backend/services/system_broadcaster.py | sed -n
'<line>p'` for each): the two publish handlers
  :314 and :364 `except (ConnectionError, TimeoutError, OSError) as e:`;
  the four pub/sub cleanup/reset handlers :583/:589 (unsubscribe/close in
  _stop_pubsub_listener) and :612/:617 (unsubscribe/close in _reset_pubsub_connection),
  all `except (ConnectionError, TimeoutError, OSError) as e:`;
  the three pub/sub listener handlers :564, :631 and :693
  `except (ConnectionError, TimeoutError, OSError, RuntimeError) as e:`.
  A timeout escaping :314/:364 propagates to the loop's `except Exception` (:1235),
  which absorbs it and sleeps — per-tick, indefinite loss; a timeout escaping
  :564/:631/:693 ends the listener region and skips recovery. The events.py layer
  is out of scope: it has NO redis exception handlers at the pin.
- Evidence: the nine except-tuples above, all verified at the pin line-by-line;
  MRO `redis.exceptions.TimeoutError -> RedisError -> Exception` (venv
  redis/exceptions.py:23/:29); loop absorb :1235 `except Exception as e:`.
- Refuted=false (NOT-REFUTED; re-issued per owner pointer with the owner's mechanism;
  refuter re-run recorded as the refutation-pass note above).
- Fix: widen all nine tuples to include `redis.exceptions.RedisError` (one name, one
  import — `RedisError` is already imported at :33), preserving each tuple's other
  members. Plus a reset test: a test shows that a `redis.exceptions.TimeoutError`
  raised by `unsubscribe` or `close` during reset does not stop the re-subscribe or
  kill the listener (the test must inject `redis.exceptions.TimeoutError`
  explicitly — every existing test injects the builtin `ConnectionError`, which the
  current tuples already catch, so a builtin-only test proves nothing about this
  defect). Size M; backend.
- Owner: `[r271a]` — fix now (ruling 271, corrections 6281398804 + 6281511059).
  First on backend's queue, after the packages it holds (UR-52, ruling 269).

### Q-055 · test · medium · backend/tests/unit/services/test_system_broadcaster.py:1345 (storm probe) · #7041

- Wrong: the storm probe (the test that was supposed to prove publish-loss resilience)
  stubs broadcast_status/broadcast_performance with autospec — the exact layer the loss
  lives UNDER, so the real publish handlers are never exercised. The real publish
  handlers catch builtin exceptions only (:307-316, :357-366) and do NOT catch
  redis.exceptions.TimeoutError; production lets the first failed publish propagate,
  so loss is PER-TICK and INDEFINITE — a permanent degradation, not a task death. The
  probe's assertions (:1424-1428) count STUB INVOCATIONS, which succeed regardless of
  Redis state, so the probe passes while production loses every message. Executed at
  the pin NOW: 1 passed, 7.59s — green on a starvation it was built to catch. Blind
  spot singular (only this probe has the shape). [Cross-references to Q-054 updated
  2026-10-20 per owner pointer: the defect in Q-054 as originally written (zero-retry
  wiring) was refuted; the real defect is the nine builtin-only handlers — see
  Q-054R. The publish handlers :314/:364 belong to that census.]
- Evidence: stubs at :1345; assertions :1424-1428; real handlers :307-316/:357-366;
  the builtin-only census (Q-054R, nine handlers).
- Refuted=false (NOT-REFUTED).
- Fix: run the probe against the real broadcast methods with publish raising
  redis.exceptions.TimeoutError, asserting PER MESSAGE TYPE local delivery every tick —
  requires Q-054R's fix scope to include the tick-abort guard (or reorder) so the test
  can pass; otherwise the corrected test documents the starvation RED. Pairs with
  Q-054R's handler fix and Q-052/Q-053's dict fix. Size M; backend.
- Owner: `[r271a]` — fix now (ruling 271). First on backend's queue, after the packages it holds (UR-52, ruling 269).

## Batch 3 — per-PR verdicts

Production positions 25-39, audited under the same ruling-232 protocol as batches 1 and 2: a
fresh unnamed refutation subagent per item, verdicts in /tmp/r262_b3_refutations/, nothing
dropped by refutation. One candidate was refuted as a phantom coordinate (q067: the auditor
attributed a `prod.yml:160` cite to config.py:203-206; `grep -c '160'` on the pin blob is 0 and
the only `prod.yml:160` carrier at the pin is Q-065's own site, a5500_precheck.py:696 — dies
unnumbered) and one was refuted on genre (7135_c4: ticked Done-when boxes are task
specifications — the register's own gloss backend.md:382, "…so this row is met by [r130b] and
the `2.0`/`le=10.0` above describe the base, not the fix", kills the class claim). Coverage: 68
verdict files on disk (66 NOT-REFUTED + 2 REFUTED), plus 2 dedup twins (7157-C1 and 7157-C5
cite 7135-C1's verdict — same defect, same blob, different PR) = 70 candidate-verdicts;
record-only dispositions for 7070-C7, 7070-C10, 7114-C2, 7114-C3 (batch-4 cross-refs, listed
under their PRs). Numbering: Q-067..Q-118 in PR order; the deferred five keep Q-062..Q-066.
Per the owner's continue (comment 6275088190): the low items rule from the compact table with
their evidence in the collapsed block under it; the two mediums keep the full templates after
the table. Owner decisions landed as ruling 277 (owner record 6291992942 on #6854, 2026-10-20
13:28Z; pointer 6291995265 on #7265): HOLD lifted; the batch is ruled with 62 rows — Q-094
dropped (REFUTED by the verification: the timer branch it called removed is live at
rate-limit-store.ts:105-118), Q-063/Q-065/Q-077/Q-105 fix targets corrected, the 13 wrong
paths corrected, Q-089 moved to the backend lane, Q-114's `starte_at` note removed, the
mediums ruled into packages [r277a] (backend: Q-068+Q-114) and [r277b] (docs: Q-093+Q-075,
a one-off UR-52 exception beside [r262]), and every other low ruled later (per-lane cleanup).
Every kept item carries the quote check docs added after Q-054 (6281400786); the owner
partner's verification re-confirmed all 62 quotes at the pin and all 62 still applying on
main (d2f07fd41).

Provenance mechanisms seen in batch 3, named: authored-live-rotted (7088 c1/c2/c3/c5 —
authored against a live tree that moved under the author before merge); drifted-post-merge
(7088 c3 jobs.py leg, c4 config.py get_settings leg); wrong-at-birth (7088 c4 schemas:49 leg;
7077-C2; 7074-C0 spec:3); pre-existing-stale-kept (7088 c6/c7/c8 — the PR edited around the
stale text and left it); last-writer-with-knowledge (7070-C5/C6 — 1fb9b87d1's own commit
message names the defect it re-anchored past); correct-at-remap-born-stale-by-later-drift
(7157-C4); false-witness claim (7145-C4 "comment-only-equal" — the harness fold and describe
tag changed spec bytes); retirement-lag systematic (7070-C4 — the sheet keeps a row for a
retired field through two later passes).

| PR    | Class      | Verdict                                                                                                                                                                                                                                 |
| ----- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| #7052 | production | 1 item (Q-067)                                                                                                                                                                                                                          |
| #7070 | production | 6 items (Q-068, Q-069, Q-070 [C5+C6 one defect two carriers], Q-071, Q-072) + 7070-C2 certified as batch-4 cross-ref (F-057/F-049/F-050/F-056/F-078/F-079 family) + 7070-C7, 7070-C10 record-only → batch-4 + 7070-C3 twin of 7146-C1   |
| #7074 | production | 2 items (Q-073, Q-074)                                                                                                                                                                                                                  |
| #7077 | production | 4 items (Q-075 [dedup twin of 7103-C0, one defect two carriers], Q-076, Q-077, Q-078)                                                                                                                                                   |
| #7086 | production | 6 rows from 7 candidates (Q-079..Q-084; C1+C2 merged — one drifted anchor :268→:276, scope wider than the item: 5 carriers total, one fix sweeps all)                                                                                   |
| #7088 | production | 8 items (Q-085..Q-092; four provenance mechanisms among them)                                                                                                                                                                           |
| #7103 | production | 1 item (Q-093 medium — F-022's five cites, full template below; the batch's Q-094 was REFUTED by the owner's verification — timer branch live at rate-limit-store.ts:105-118 — and dropped per ruling 277)                              |
| #7114 | production | 1 own item (Q-095) + the five deferred items Q-062..Q-066 ride this PR's batch (they cite lines its diffs moved) + 7114-C2/C3 record-only → batch-4 + 7114-C4 re-assigned to #7222 (batch 4): first author 51a2738f0 [r243], born false |
| #7125 | production | 1 item (Q-096 — mechanism-3 flagship, false at birth)                                                                                                                                                                                   |
| #7135 | production | 4 rows from 5 candidates (Q-097..Q-100; c4 REFUTED on genre) + the A-family census joins Q-097's row + 7157-C1/C5 dedup twins ride 7135-C1's verdict                                                                                    |
| #7139 | production | 6 items (Q-101..Q-106)                                                                                                                                                                                                                  |
| #7145 | production | 4 items (Q-107..Q-110; C2 self-authored error, C4 false-witness claim)                                                                                                                                                                  |
| #7146 | production | 3 items (Q-111..Q-113; C1 anchors the B-family census, C3 keeper-deletion)                                                                                                                                                              |
| #7156 | production | 5 items (Q-114 medium — full template below; Q-115..Q-118)                                                                                                                                                                              |
| #7157 | production | 5 own items (Q-119..Q-123 mapping C2/C3/C4/C6/C7) + C1/C5 dedup twins resolved onto 7135-C1's verdict                                                                                                                                   |

Compact table. Owner decisions are pending; the owner column carries write-time wording only.

| id    | class | path:line                                                                            | PR    | wrong (one line)                                                                                                                                                                                                                                                     | fix (size, lane)                                                                                                      | owner                                                                                              |
| ----- | ----- | ------------------------------------------------------------------------------------ | ----- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Q-062 | claim | monitoring/alerting-rules.yml:960                                                    | #7114 | cites prod.yml:151-152 for VLM labels; pin has the ai-vlm header there, real labels at :173-174                                                                                                                                                                      | re-point to :173-174 (S, docs)                                                                                        | ruled 277: later (docs cleanup)                                                                    |
| Q-063 | claim | backend/api/routes/model_management.py:253                                           | #7114 | cites prod.yml:398 for CUDA_VISIBLE_DEVICES (not SERVICE_NAME); pin :398 is a CUDA kernel-cache comment, the fact is at :420 (ruled 277; :405 is ai-gateway's SERVICE_NAME, a different line)                                                                        | re-point to :420 (S, backend)                                                                                         | ruled 277: later (backend cleanup)                                                                 |
| Q-064 | claim | backend/tests/unit/scripts/test_ci_compose_cap_drop_bootable.py:149                  | #7114 | cites prod.yml:479 for ENVIRONMENT; pin :479 is a ":U chown" comment, real at :508                                                                                                                                                                                   | re-point to :508 (S, backend)                                                                                         | ruled 277: later (backend cleanup)                                                                 |
| Q-065 | claim | scripts/a5500_precheck.py:696                                                        | #7114 | cites prod.yml:160 for CUDA_ARCHITECTURES build-arg threading (not label=disable); pin :160 is a comment, the fact is at :182 (ruled 277; :167 is label=disable, a different line)                                                                                   | re-point to :182 (S, scripts)                                                                                         | ruled 277: later (scripts cleanup)                                                                 |
| Q-066 | claim | scripts/a5500_precheck.py:815                                                        | #7114 | cites prod.yml:188 for VLM_GPU_LAYERS; pin :188 is a comment, real at :210                                                                                                                                                                                           | re-point to :210 (S, scripts)                                                                                         | ruled 277: later (scripts cleanup)                                                                 |
| Q-067 | low   | docs/uplevel/packages/ops.md:373-376 + pyproject.toml:345-346                        | #7052 | ticked "no longer coupled to 3.14 by one line" unqualified while 157 bare-except sites in 79 files (AST census at the pin) remain                                                                                                                                    | scope the clause + fix the two named PEP-758 carriers (M, docs+backend)                                               | ruled 277: later (docs+backend cleanup)                                                            |
| Q-068 | low   | backend/api/routes/events.py:340                                                     | #7070 | fields Query description lists detection_ids (not in the allowlist :177-197) and omits notify (:196)                                                                                                                                                                 | align description with the allowlist (S, backend)                                                                     | ruled 277: fix-now in [r277a] (backend)                                                            |
| Q-069 | low   | docs/uplevel/r2-sheet.md:197 (F-058)                                                 | #7070 | row still targets the retired `flagged` field (deleted by e2d65dda3); movers passed it by twice post-retirement                                                                                                                                                      | retire or re-target the F-058 row (S, docs)                                                                           | ruled 277: later (docs cleanup)                                                                    |
| Q-070 | low   | docs/architecture/api-reference/README.md:29 + events-api.md :26/:106/:160/:205/:233 | #7070 | five Source spans stale; 2/5 wrong-spans-not-dead, 3/5 dead; wrong since 910d09f23 (~262 days)                                                                                                                                                                       | re-anchor all five Source cells in both files (S, docs)                                                               | ruled 277: later (docs cleanup)                                                                    |
| Q-071 | low   | docs/architecture/event-lifecycle.md:233                                             | #7070 | PATCH span :2123; fix span is :2004-2200 (decorator to def end); 1fb9b87d1 re-anchored against the base tree                                                                                                                                                         | re-anchor to :2004-2200 (S, docs)                                                                                     | ruled 277: later (docs cleanup)                                                                    |
| Q-072 | low   | docs/uplevel/packages/backend.md:399-401 (register row)                              | #7070 | events.py dict cites :546-601 dead since 6db72093c; box checked while cites still live; post-check drift                                                                                                                                                             | repair the register row (S, docs)                                                                                     | ruled 277: later (docs cleanup)                                                                    |
| Q-073 | low   | frontend/tests/golden/gpu-storage-admin/admin-logging.spec.ts (nine cites)           | #7074 | nine stale cites incl. spec:3's :379 wrong at birth; validated by nothing (no gate reaches tests/golden); path corrected per ruling 277 (:26 was frontend/tests/golden/operations/)                                                                                  | re-derive all nine + api.ts:2102→:2053 (M, frontend)                                                                  | ruled 277: later (frontend cleanup)                                                                |
| Q-074 | low   | backend/tests/unit/scripts/test_ci_compose_cap_drop_bootable.py:247                  | #7074 | cites system.py:2572; guard list at :2554-2559, :2572 is blank inside a docstring; ruled 277: the row also cites the guard at :2545-2556 (real :2554-2560) and the mkdir at :2572 (real :2580), and its fix re-pointed only the guard                                | re-point both cites to :2554-2560 / :2580 (S, backend)                                                                | ruled 277: later (backend cleanup)                                                                 |
| Q-075 | low   | feature-inventory F-022 (5 cites)                                                    | #7077 | one defect, two carriers — same five stale F-022 cites as Q-093; this PR's carrier attribution differs                                                                                                                                                               | resolved with Q-093's fix (—)                                                                                         | see Q-093                                                                                          |
| Q-076 | low   | frontend/tests/golden/shell/rate-limit.spec.ts :31/:33/:147/:570                     | #7077 | four stale cites, one past EOF (SystemMonitoringPage.tsx:751; file is 745 lines); path corrected per ruling 277; carries two F-022 anchors (:31 api.ts:2165, :33 system.py:1626) shared with Q-093                                                                   | re-derive, fix anchor :2116/:2113 (S, frontend)                                                                       | ruled 277: later (frontend cleanup; Q-076 anchors ride Q-093's fix)                                |
| Q-077 | low   | docs/uplevel/packages/frontend.md :149/:410                                          | #7077 | queryClient.ts:249-297 dead range — symbol absent at merge (wrong-at-birth) and at pin; ruled 277: re-pointing to :247-251/:295-299 lands on unrelated queryKeys code                                                                                                | revision-qualify the cite (`8a49ae7ac:frontend/src/services/queryClient.ts:249-297`) or drop the coordinate (S, docs) | ruled 277: later (docs cleanup)                                                                    |
| Q-078 | low   | frontend/src/services/queryClient.ts:123                                             | #7077 | @example 60000ms vs MAX_RETRY_DELAY_MS=30000; the example exercises the capped path                                                                                                                                                                                  | fix the example value (S, frontend)                                                                                   | ruled 277: later (frontend cleanup)                                                                |
| Q-079 | low   | DashboardConfigModal.tsx:110 + DashboardConfigModal.test.tsx:468                     | #7086 | cite DashboardLayout.tsx:268→:276 (ruled 277: :276 is `const config = { widgets, version }`, mainWidgets is declared at :271); scope wider: 5 carriers (gpu-stats.spec.ts:199/:246, pipeline-telemetry.spec.ts:192)                                                  | one fix sweeps all five (S, frontend)                                                                                 | ruled 277: later (frontend cleanup)                                                                |
| Q-080 | low   | frontend/tests/golden/dashboard/pipeline-telemetry.spec.ts:16                        | #7086 | three first-mover stories kept distinct (api.ts 2099deab6, schemas 3a1bc8fdf, layout 4238c6260); spec author 3d14e7da2; path corrected per ruling 277                                                                                                                | re-derive all cites (M, frontend)                                                                                     | ruled 277: later (frontend cleanup)                                                                |
| Q-081 | low   | feature-inventory F-042/F-040 rows :383/:385                                         | #7086 | :268→:276 same drift; mints-sentence author 8f39f6102                                                                                                                                                                                                                | re-anchor both rows (S, docs)                                                                                         | ruled 277: later (docs cleanup)                                                                    |
| Q-082 | low   | feature-inventory F-042 works-cell                                                   | #7086 | '**works** waits on the real tier' — 57 lines in feature-inventory.md + 1 elsewhere = 58 repo-wide at the pin (ruled 277 confirms); systemic pattern                                                                                                                 | sweep the phrase repo-wide (M, docs)                                                                                  | ruled 277: later (docs cleanup)                                                                    |
| Q-083 | low   | feature-inventory F-040 '9 commits behind'                                           | #7086 | authoring-tip miscount: true count 7 (97c602ae9..1132ab8c9)                                                                                                                                                                                                          | correct to 7 (S, docs)                                                                                                | ruled 277: later (docs cleanup)                                                                    |
| Q-084 | low   | frontend/tests/golden/dashboard/config-modal.spec.ts:13                              | #7086 | four stale anchors; PR moved handleSave/handleCancel without re-deriving (Save :152, Cancel :158-161); path corrected per ruling 277                                                                                                                                 | re-derive all four (S, frontend)                                                                                      | ruled 277: later (frontend cleanup)                                                                |
| Q-085 | low   | docs/architecture/decisions.md:188                                                   | #7088 | cites config.py:1942-1982 (real :1739/:1731-1767) + prod.yml:643 (real :672); authored-live-rotted                                                                                                                                                                   | re-point both (S, docs)                                                                                               | ruled 277: later (docs cleanup)                                                                    |
| Q-086 | low   | docs/architecture/system-overview/configuration.md:174                               | #7088 | same root as Q-085; true block 1730-1770, fields-only 1739-1754; path corrected per ruling 277 (:174 was docs/architecture/configuration.md)                                                                                                                         | re-point (S, docs)                                                                                                    | ruled 277: later (docs cleanup)                                                                    |
| Q-087 | low   | docs/uplevel/packages/backend.md :377/:383 (F-187/190/191, F-089)                    | #7088 | config.py:1952→:1740; jobs.py:296-299→:291-295 (one mover 6b691302d)                                                                                                                                                                                                 | re-point all (S, docs)                                                                                                | ruled 277: later (docs cleanup)                                                                    |
| Q-088 | low   | backend/tests/unit/core/test_config_fast_path_flag.py :63-64/:75-76                  | #7088 | schemas settings_api.py:49 wrong-at-birth (:53 threshold, :56 le=1.0); config.py:3497-3500 → real get_settings :3171; path corrected per ruling 277                                                                                                                  | re-derive (S, backend)                                                                                                | ruled 277: later (backend cleanup)                                                                 |
| Q-089 | low   | backend/tests/golden/external/test_settings_save_roundtrip.py :19/:142/:171          | #7088 | three dead cites incl. one past EOF (config.py had 3176 lines at pin); mover af7690bfd first and only content mover; path + lane corrected per ruling 277 — the file is backend's (was listed frontend)                                                              | re-derive to :2098/:2431/:3170-3176 (S, backend)                                                                      | ruled 277: later (backend cleanup)                                                                 |
| Q-090 | low   | docs/architecture/detection-pipeline/critical-paths.md:129                           | #7088 | vlm_analyzer.py:690-705 pre-existing-stale-kept; real fn :898-914 (moved 801→898 by #7182); path corrected per ruling 277; second carrier at detection-pipeline/batch-aggregator.md:352                                                                              | re-point to :898-914, both carriers (S, docs)                                                                         | ruled 277: later (docs cleanup)                                                                    |
| Q-091 | low   | docs/architecture/background-services/batch-aggregator.md:24                         | #7088 | table says BATCH_MAX_DETECTIONS=100; config.py:972-973 default=500; six other docs say 500 — outlier not ambiguity; path corrected per ruling 277                                                                                                                    | fix the row to 500 (S, docs)                                                                                          | ruled 277: later (docs cleanup)                                                                    |
| Q-092 | low   | docs/developer/batching-logic.md :103/:124                                           | #7088 | dead symbol _is_fast_path_eligible; real gate _should_use_fast_path :1186, _process_fast_path :1227; path corrected per ruling 277                                                                                                                                   | replace symbol + re-point (S, docs)                                                                                   | ruled 277: later (docs cleanup)                                                                    |
| Q-093 | med   | feature-inventory F-022 (5 cites)                                                    | #7103 | rate-limit store contract record carries five stale cites; first breaker 834d51097; full template below                                                                                                                                                              | re-derive five + re-anchor (M, docs)                                                                                  | ruled 277: fix-now in [r277b] (docs, with Q-075)                                                   |
| Q-095 | low   | scripts/test_orchestrator_engine_socket.py:3                                         | #7114 | docstring's "451 lines" parenthetical false at own merge (643 lines); mechanisms 1+3+2                                                                                                                                                                               | fix the parenthetical (S, scripts)                                                                                    | ruled 277: later (scripts cleanup)                                                                 |
| Q-096 | claim | scripts/uplevel/reid_real_tier.sh S5 :794-799                                        | #7125 | universal "NO plan" contradicts S3's refusal shape + export_reid.py:1008-1019 + AGENTS.md :257-258 vs :262-263; false at birth                                                                                                                                       | align S5 with S3/export/AGENTS (M, scripts)                                                                           | ruled 277: later (scripts cleanup)                                                                 |
| Q-097 | claim | test_monitoring_key_field_ceiling.py docstring + A-family census                     | #7135 | docstring cites dead at pin (events.py :441/:564/:566/:452-455, conftest :1729, ci.yml :2052-2053/:2058-2059) + A-family dead-coordinate census                                                                                                                      | re-derive + census sweep (M, backend)                                                                                 | ruled 277: later (backend cleanup; census sweep waits for the wired CI drift check per ruling 277) |
| Q-098 | low   | backend/tests/unit/api/test_api_key_scopes.py :27-28 (:702)                          | #7135 | "(2)" is an amendment number misread as instance count; section comment :702 carries the same stale framing                                                                                                                                                          | fix both sites (S, backend)                                                                                           | ruled 277: later (backend cleanup)                                                                 |
| Q-099 | low   | vulture_whitelist.py :37-38/:42 (repo root)                                          | #7135 | 'seven bodies' vs 11 at pin; the 2026-10-15 stamp attached to the wrong sentence; path corrected per ruling 277 (was scripts/)                                                                                                                                       | update count + restamp (S, scripts)                                                                                   | ruled 277: later (scripts cleanup)                                                                 |
| Q-100 | low   | backend/api/routes/events.py :587-588 + ceiling test :93                             | #7135 | "0 hits for verification under monitoring/" — 7 matching lines; needle needs qualification, both sites                                                                                                                                                               | qualify the needle at both (S, backend)                                                                               | ruled 277: later (backend cleanup)                                                                 |
| Q-101 | low   | feature-inventory F-019 :355                                                         | #7139 | App.tsx:275 → real /operations route :293 (18 off); own code commit worsened drift while docs commit re-anchored five other rows                                                                                                                                     | re-anchor (S, frontend)                                                                                               | ruled 277: later (frontend cleanup; in the feature-inventory sweep cluster)                        |
| Q-102 | low   | feature-inventory F-021 :357                                                         | #7139 | App.tsx:342 off-by-one from birth (mount :341); stale by 19 at pin; content true of :361                                                                                                                                                                             | re-anchor to :361 (S, frontend)                                                                                       | ruled 277: later (frontend cleanup; in the feature-inventory sweep cluster)                        |
| Q-103 | low   | feature-inventory F-020 :356                                                         | #7139 | span 251-334 open/close asymmetry; true span 260-353; close never exact in the row's lifetime                                                                                                                                                                        | re-derive span (S, frontend)                                                                                          | ruled 277: later (frontend cleanup; in the feature-inventory sweep cluster)                        |
| Q-104 | low   | feature-inventory F-238 :634                                                         | #7139 | App.tsx:251 correct at own merge, re-staled by 70c5d96ae (+9); shares mover with Q-103                                                                                                                                                                               | re-anchor with Q-103's fix (S, frontend)                                                                              | ruled 277: later (frontend cleanup; in the feature-inventory sweep cluster)                        |
| Q-105 | low   | feature-inventory F-034 :378                                                         | #7139 | both F-034 legs stale (ruled 277): mount App.tsx:263-268 (pin block :272-277) re-staled by 70c5d96ae; catch-all App.tsx:338 (pin :338 = /face-recognition opening, `path="*"` at :347) — the sheet's earlier "catch-all :347 exact" misread the row, which cites 338 | re-anchor both legs (S, frontend)                                                                                     | ruled 277: later (frontend cleanup)                                                                |
| Q-106 | low   | frontend/src/**tests**/pwa-install-prompt-retired.test.tsx:58                        | #7139 | "Devtools +10" bare cite false at pin (:358=</Routes>, :368=Devtools) in the sentence teaching why bare cites can't be trusted                                                                                                                                       | re-word to a revision anchor (S, frontend)                                                                            | ruled 277: later (frontend cleanup)                                                                |
| Q-107 | low   | frontend/tests/golden/operations/batch-statistics.spec.ts:19-94                      | #7145 | ~14 stale cites across 5 files; authored exact at its merge, displaced by 5+ later PRs                                                                                                                                                                               | re-derive all (M, frontend)                                                                                           | ruled 277: later (frontend cleanup)                                                                |
| Q-108 | low   | frontend/tests/golden/operations/batch-statistics.spec.ts :56-57                     | #7145 | "checks every 10 s" self-authored error — settings default is 5.0 (config.py:965-966); false at merge and pin                                                                                                                                                        | fix to 5 s (S, frontend)                                                                                              | ruled 277: later (frontend cleanup)                                                                |
| Q-109 | low   | feature-inventory F-135 :518                                                         | #7145 | get_pipeline_status :4253→:4241 (mover a4916e3ea #7183); no wired gate checks feature-inventory line cites at all                                                                                                                                                    | re-anchor (S, docs)                                                                                                   | ruled 277: later (docs cleanup; in the feature-inventory sweep cluster)                            |
| Q-110 | low   | feature-inventory F-135 witness clause                                               | #7145 | "spec bytes differ by comment only" false — harness fold ('./harness') + describe tag '(F-135)' changed bytes                                                                                                                                                        | correct strength to comment-only-equal (S, docs)                                                                      | ruled 277: later (docs cleanup; wording call kept)                                                 |
| Q-111 | claim | backend/tests/integration/test_soft_delete.py :209/:218/:251                         | #7146 | four dead docstring cites; B-family census anchor (with 7070-C2 siblings and C3)                                                                                                                                                                                     | re-derive + B-family sweep (M, backend)                                                                               | ruled 277: later (backend cleanup; census sweep waits for the wired CI drift check per ruling 277) |
| Q-112 | low   | backend/api/routes/events.py:691                                                     | #7146 | cites ci.yml:692→:772 (mypy backend/); total drift +80 across seven landings; repo-wide exactly one carrier                                                                                                                                                          | re-point to :772 (S, backend)                                                                                         | ruled 277: later (backend cleanup)                                                                 |
| Q-113 | low   | backend/tests/integration/test_soft_delete.py:667                                    | #7146 | vacuous stats leg asserts 200 + membership while the real leg (:204-253) carries three aggregates; keeper = #7146 (deletion of pre-existing rot)                                                                                                                     | delete the 18-line block; re-check internal cites after (S, backend)                                                  | ruled 277: later (backend tests cleanup)                                                           |
| Q-114 | med   | backend/api/routes/system.py:4132-4135                                               | #7156 | "add_detection rewrites these through the set wrapper (batch_aggregator.py:641)" — plural half-false: started_at raw via :427; full template below                                                                                                                   | reword to singular + fix cites (S, backend)                                                                           | ruled 277: fix-now in [r277a] (backend)                                                            |
| Q-115 | low   | docs/superpowers/plans/2026-09-27-a5500-vlm-bringup-checklist.md:58                  | #7156 | first mover 2467cea06 (not 734f5e409); gaps 2/36/4, "broken before this PR" stands                                                                                                                                                                                   | fix cites + gap numbers (S, docs)                                                                                     | ruled 277: later (docs cleanup)                                                                    |
| Q-116 | low   | docs/superpowers/plans/2026-09-25-a5500-bringup-checklist.md:48                      | #7156 | same first mover (one commit, two rows); .env.example:58 stale at row entry (a0105b630 already had :57)                                                                                                                                                              | fix cites + TMPDIR :55 + three test defs (S, docs)                                                                    | ruled 277: later (docs cleanup)                                                                    |
| Q-117 | low   | scripts/a5500_precheck.py :967-975                                                   | #7156 | generator/test expectations diverge from rendered output (:576/:598 vs :577/:599); disposition SHA unresolvable — cite 7ad0fd8fd's message                                                                                                                           | sync expectations + cite the commit (S, scripts)                                                                      | ruled 277: later (scripts cleanup)                                                                 |
| Q-118 | low   | backend/tests/e2e/test_pipeline_integration.py :121-122                              | #7156 | "mock_get refuses GET on these" blanket — pipeline seam (:249-259) unguarded; well-formed detection_count=0 survives                                                                                                                                                 | guard the get-branch or narrow the comment (S, backend)                                                               | ruled 277: later (backend tests cleanup; optional promote)                                         |
| Q-119 | low   | five qualified carriers citing ai_audit.py:194                                       | #7157 | pin :194 = decorator close paren, def :195; blind +1 remap by eb7ce4431                                                                                                                                                                                              | re-point all five to :195 (S, docs)                                                                                   | ruled 277: later (docs cleanup)                                                                    |
| Q-120 | low   | docs/reference/feature-inventory.md F-062 :413                                       | #7157 | F-062's relative :194 contradicts F-061's :195 two rows apart; 62a2d7eea rewrote both and left :194; path corrected per ruling 277 (was backend-entry-points.md)                                                                                                     | fix F-062 to :195 (S, docs)                                                                                           | ruled 277: later (docs cleanup)                                                                    |
| Q-121 | low   | docs/vss-integration/17-action-plan.md:5653                                          | #7157 | :228/:274 correct-at-remap born-stale-by-later-drift; calls at :229/:275; adjacent dead cites (config.py:2707-2708, main.py:1054-1068)                                                                                                                               | fix the whole bullet (S, docs)                                                                                        | ruled 277: later (docs cleanup)                                                                    |
| Q-122 | low   | docs/reference/backend-entry-points.md:158                                           | #7157 | prose `POST /batch` (:504) vs own table :153 citing :534 (decorator :524, "/batch" :525) — same-pass oversight                                                                                                                                                       | re-derive prose (S, docs)                                                                                             | ruled 277: later (docs cleanup)                                                                    |
| Q-123 | low   | feature-inventory F-104 :480 + F-129 :504                                            | #7157 | system.py:4936 dead (get_model_zoo_status :4992); F-104's has_clip :4839 dead → backend/models/event_audit.py:37; disclosure ≠ repair                                                                                                                                | fix both rows (S, docs)                                                                                               | ruled 277: later (docs cleanup; in the feature-inventory sweep cluster)                            |

Census consolidation: ~20 rows' dead coordinate cites across feature-inventory.md consolidate
into the #7135-family and #7146-family items; enumerated there. A-family (first breaker #7135):
:282×7, :569×3, :427, :468, :542 — joins Q-097's row (with 7070-C5/C6/C9). B-family (first
breaker #7146): :1952×5, :2010×2, :719, :2430/:2512, :2139, :1424, :1793, :2703/:2726×3/:2745 —
folds into Q-111's row (with 7070-C2 siblings and 7070-C3). C-family (first breaker #7201) →
batch-4 cross-ref (incl. F-059/F-296/:1919 authored TRUE by 19845d681 [r196a]; F-059's :2174
also dead, first breaker #7146).

Record-only dispositions (no refuter dispatched per prior ruling; batch-4 cross-refs):

- 7070-C7 and 7070-C10: recorded against #7070's batch-4 set.
- 7114-C2 (ci.yml "Pin the compose CLI") and 7114-C3 (feature_check.py docstring): recorded
  against #7222's batch-4 set.
- 7114-C4 (deployment/README.md:904-906 "because alloy precedes backend"): refuted on
  attribution, NOT on defect — first author 51a2738f0 ([r243] #7222 branch commit), born false
  (backend :463 precedes alloy :1592 at that commit; compose reports every service whose
  interpolation fails, in alphabetical service order — file order is irrelevant). Re-assigned
  to #7222, batch 4. The fix wording: "compose reports every service whose interpolation
  fails, in alphabetical service order, so an unset PODMAN_SOCKET fails the render naming
  services.alloy.volumes and services.backend.volumes in BOTH states regardless of file order
  — alloy heads the list only because the names sort that way."

<details>
<summary>Batch 3 evidence — low items (collapsed)</summary>

### Q-062 · claim · monitoring/alerting-rules.yml:960 · #7114

- Wrong: the comment cites `prod.yml:151-152` for the VLM labels; the pin has the ai-vlm
  header comment there and the labels at :173-174.
- Evidence: pin prod.yml :151-152 vs :173-174; blob a9be3a71 byte-identical boundary→pin;
  the move is #7114's branch commit ac84fd7d96 (include insert :43-57 moves labels 151→166),
  then #7222's 51a2738f03 (166→173); 56 first-parent merges to the boundary, not 52.
- Refuted=false (NOT-REFUTED; verdict 7114_q062.md).
- Fix: re-point to :173-174. Size S; docs.
- Owner: ruled 277: later (docs cleanup).

### Q-063 · claim · backend/api/routes/model_management.py:253 · #7114

- Wrong: cites `prod.yml:398` for CUDA_VISIBLE_DEVICES (`${GPU_AI_SERVICES:-1}`); pin :398 is
  a CUDA kernel-cache comment, the fact is at :420 — the sheet's earlier ":405 SERVICE_NAME"
  fix target was a different line (ruled 277).
- Evidence: chain #6862 wrote :397-ish → #6907 renumbered truthfully (193498dac, true at its
  own merge) → #7114 moved the line away (false at its own merge; its own diff never touches
  the cite file) → #7222's :420.
- Refuted=false (NOT-REFUTED; verdict 7114_q063.md).
- Fix: re-point to :420. Size S; backend.
- Owner: ruled 277: later (backend cleanup; target re-pointed to :420 in the table).

### Q-064 · claim · backend/tests/unit/scripts/test_ci_compose_cap_drop_bootable.py:149 · #7114

- Wrong: cites `prod.yml:479` for ENVIRONMENT; pin :479 is a ":U chown" comment, ENVIRONMENT
  is at :508.
- Evidence: chain #6907 :479 (true) → #7114 in-branch ac84fd7d9 :495 → #7222 :508; zero
  corrections; #7074 co-ownership proven irrelevant (its diff grep "479"/"ENVIRONMENT" rc=1);
  graft-truncation check clean.
- Refuted=false (NOT-REFUTED; verdict 7114_q064.md).
- Fix: re-point to :508. Size S; backend.
- Owner: ruled 277: later (backend cleanup).

### Q-065 · claim · scripts/a5500_precheck.py:696 · #7114

- Wrong: cites `prod.yml:160` for the CUDA_ARCHITECTURES build-arg threading ("threads
  ${CUDA_ARCHITECTURES:-} into the ai-vlm build"); pin :160 is the "interim GPU-less path"
  comment, the fact is at :182 — the sheet's earlier ":167 label=disable" fix target was a
  different line (ruled 277; the item's own evidence chain already ended at :182).
- Evidence: walk 254 merges → #7114 :175 → #7222 :182; CUDA_ARCHITECTURES at :182; blob
  transition 3276f3a1→30bc7f47 is #6907's, NOT #7114's.
- Refuted=false (NOT-REFUTED; verdict 7114_q065.md). This is the only `prod.yml:160` carrier
  at the pin — the phantom q067 (REFUTED) had bound the same coordinate to config.py:203-206,
  which actually cites :284.
- Fix: re-point to :182. Size S; scripts.
- Owner: ruled 277: later (scripts cleanup; target re-pointed to :182 in the table).

### Q-066 · claim · scripts/a5500_precheck.py:815 · #7114

- Wrong: cites `prod.yml:188` for VLM_GPU_LAYERS; pin :188 is a comment, the real line is at
  :210.
- Evidence: :188 true exactly at #6862's merge (its own diff moved 183→188) → #7114 :203 →
  #7222 :210; distinct AMENDMENTS blocks confirmed.
- Refuted=false (NOT-REFUTED; verdict 7114_q066.md).
- Fix: re-point to :210. Size S; scripts.
- Owner: ruled 277: later (scripts cleanup).

### Q-067 · low · docs/uplevel/packages/ops.md:373-376 · #7052

- Wrong: the ticked bullet "no longer coupled to 3.14 by one line" carries no scoping clause,
  and the Done-when checks only the literal line — 157 bare-except sites across 79 files
  remain at the pin (AST census; item said ~125/65).
- Evidence: second carrier pyproject.toml:345-346; the two named code carriers
  scripts/reachability.py:126 (`ast.parse(text, filename=self.rel)`, zero handlers) and
  backend/api/middleware/request_recorder.py:281 (bare PEP-758 `except
json.JSONDecodeError, UnicodeDecodeError:`); tick 21411ba33 2026-10-15T00:43:35Z (the item
  had mislabeled local as Z); ruling-map.md:184 ruling-169 acceptance has no scope prose; the
  bullet is pre-existing unticked at base and [x] by the tick. Counter-read DEFEATED — the
  item stands on the second carrier alone.
- Refuted=false (NOT-REFUTED; verdict 7052_c0.md).
- Fix: scope the clause to what ruling 169 actually accepted + fix the two named carriers.
  Size M; docs+backend.
- Owner: ruled 277: later (docs+backend cleanup).

### Q-068 · low · backend/api/routes/events.py:340 · #7070

- Wrong: the fields Query description lists detection_ids (not in the allowlist :177-197) and
  omits notify (:196, not :199).
- Evidence: parse path :407-411 (FieldFilterError field_filter.py:107 → :408-411 HTTP_400);
  pre-existing at base; the PR edited this exact string AND disclosed it in the PR body as
  "finding 7 of my self-review — deliberately NOT in this PR"; the follow-up never landed;
  the body's own cites (:305/:161) are pre-rebase, +35 off at the pin.
- Refuted=false (NOT-REFUTED; verdict 7070_c1.md).
- Fix: align the description with the allowlist; the fix should carry the PR body's
  self-disclosure. Size S; backend.
- Owner: `[r277a]` — fix now (ruling 277), with Q-114: the description names exactly VALID_EVENT_LIST_FIELDS (detection_ids out, notify in) and a test fails on drift.

### Q-069 · low · docs/uplevel/r2-sheet.md:197 (F-058) · #7070

- Wrong: the F-058 row is half-built — it targets the `flagged` field, which e2d65dda3
  deleted (gone at the pin: :312 is snooze_until; present at #7070's merge).
- Evidence: e2d65dda3 deleted the Field but did not touch the sheet; the sheet movers 7f4a40893
  (regeneration) and 351e97001 (prettier) POSTDATE the retirement yet left the row
  byte-identical. Counter-read REJECTED: the row's "S — persist flagged" action would re-add a
  retired field. Siblings F-035 :210, F-114 :221 — a systematic lag, not a one-off. routes
  :2000 is the optimistic-locking comment (reviewed write :2070, notes :2074, snooze :2079).
  Class: substance drift, distinct from cite-rot.
- Refuted=false (NOT-REFUTED; verdict 7070_c4.md).
- Fix: retire or re-target the F-058 row. Size S; docs.
- Owner: ruled 277: later (docs cleanup).

### Q-070 · low · docs/architecture/api-reference/README.md:29 + events-api.md · #7070

- Wrong: five Source spans stale (README carries all five at :29-33; events-api :26 list
  225-469, :106 stats 472-616, :160 timeline 634-792, :205 search 795-905, :233 export
  908-1012 — the sheet's earlier label-to-line mapping was shifted one row; ruled 277
  confirms the corrected mapping).
- Evidence: 2/5 wrong-spans-not-dead (list def@317 ∈ 225-469; timeline def@788 ∈ 634-792
  barely), 3/5 genuinely dead (stats/search/export); the search span now sits inside
  get_timeline_summary's body (795-905 ⊂ 788-945); wrong since 910d09f23 2026-01-25 (~262
  days); #7070 owns as last-writer-with-knowledge — 1fb9b87d1's own commit message names the
  search-span defect ("leaves search_events_endpoint for get_event_clusters") and it
  re-anchored the span anyway; only the list span shifted +1, the others +13 (difflib
  re-alignment, not uniform); def anchors 317/634/788/949/1154/1300; search body ends 1274,
  export body ends ~1476 (decorator 1276-1299, def :1300); movers never touched api-reference
  (0 hits in --stat). No gate reaches docs/architecture.
- Refuted=false (NOT-REFUTED; verdict b3_7070c56.md — one refuter for both carriers, one
  defect, two renderings).
- Fix: re-anchor all five Source cells in both files to freshly-measured pin extents
  (decorator-to-body-end convention). Size S; docs.
- Owner: ruled 277: later (docs cleanup).

### Q-071 · low · docs/architecture/event-lifecycle.md:233 · #7070

- Wrong: the PATCH span cites events.py:2123 as the response build; :2123 is update_event's
  audit-log details dict (:2120-2124), not the response build (:2184).
- Evidence: fix span :2004-2200 (@router.patch :2004, responses :2005-2020, :2021 def, :2200
  def end, :2204 VALID_DETECTION_ORDER_BY, :2207 next decorator); 1fb9b87d1 re-anchored
  against the BASE tree (exact at 841bb53ea, 13/14 early at its own merge); movers worsened
  the start into bulk_delete (361199a99). Coordinator override of the refuter's :2020
  (decorator). No gate reaches docs/architecture.
- Refuted=false (NOT-REFUTED; verdict b3_7070c8.md).
- Fix: re-anchor to :2004-2200. Size S; docs.
- Owner: ruled 277: later (docs cleanup).

### Q-072 · low · docs/uplevel/packages/backend.md:399-401 (register row) · #7070

- Wrong: the register row's events.py dict cites are dead (:546-601 at the pin) and the row's
  box was CHECKED (e0dd810a7, 2026-10-14) while both cites still live — the deadness is
  post-check drift.
- Evidence: 75ea5ee10 contributed +11 dict-start/+31 dict-end/+1 allowlist (NOT "+35" — the
  +35 is the ALLOWLIST net shift); dict 501-536 (merge) → 546-601 (pin); allowlist 142→177;
  full death at 6db72093c 2026-10-16; the row must NOT attribute deadness to #7070 (born-loose
  only at start — a 2-line leading context disclosed in 1fb9b87d1's message; the end was
  AST-exact at merge; damage owned by the post-merge movers 361199a99 + 6db72093c primary,
  834d51097 -1 secondary). Gate: check-uplevel-cites.py SCAN=["rules.md"] — packages/*.md
  file:line cites are outside its grammar AND its scan set; auditor-eyed. Pin truth:
  events.py :142 (r223 docstring), :177 (frozenset def), :198 (close), :546 (event_dict = {),
  :577 ("notes": event.notes,), :601 (}).
- Refuted=false (NOT-REFUTED; verdict b3_7070c9.md).
- Fix: repair the register row (fix attributed to the register repairer, not #7070). Size S;
  docs.
- Owner: ruled 277: later (docs cleanup).

### Q-073 · low · frontend/tests/golden/gpu-storage-admin/admin-logging.spec.ts · #7074

- Wrong (path corrected per ruling 277 — the spec lives in tests/golden/gpu-storage-admin/,
  not operations/): nine stale cites (:3 :16 :25 :101 :119 :147 :168 :171-172 :177-178),
  four badly —
  junit_results :853→:1188 (:853 is `return [value]` in _strings), toast :166→:178 (pin :166
  is toast.error('Failed to change log level'), :178 is toast.success('Log retention
  updated')), loader catch :129-131→:141-143, fetchConfig :86-127→:134-149.
- Evidence: routes/system.py :2668 = detection_confidence_threshold if, :2680 = cache_clear,
  :2710 = AuditService.log_action (TRUE at merge, broke post-merge via #7205); schemas
  log_retention_days Field :559-564 (not :560-565); passed-mapping :1203-1207; spec:3's :379
  cite WRONG AT BIRTH (merge :379 = F-194 row, F-195 at :380); api.ts:2102 leg also stale
  (updateConfig now :2053) — underclaim folded into the row; :172 carries both system.py
  numbers; spec blob 27b719aa2 (merge) → 3b48b5f2b (pin). Gate: guard.ts runtime-only,
  check-uplevel-cites.py scopes docs/uplevel only, no docs-drift rule for tests/golden —
  validated by NOTHING.
- Refuted=false (NOT-REFUTED; verdict 7074_c0.md).
- Fix: re-derive all nine + the api.ts leg. Size M; frontend.
- Owner: ruled 277: later (frontend cleanup).

### Q-074 · low · backend/tests/unit/scripts/test_ci_compose_cap_drop_bootable.py:247 · #7074

- Wrong: the row cites TWO system.py legs — the guard at :2545-2556 (real :2554-2560) and
  the mkdir at :2572 (real :2580; the pin's :2572 is a blank line inside
  _write_runtime_env's docstring, def :2570) — and its fix re-pointed only the guard leg
  (ruled 277).
- Evidence: net regional shift +8 (hunk arithmetic +19-6-5; the "~80 lines" was a whole-file
  diff count); pin :2545-2556 grazes the guard head (docstring :2545-2549 + getenv/resolve
  :2550-2551 + comment/allowed_bases/first two entries :2552-2556), not purely docstring;
  TRUE at merge 5b395461f (:2545 = "# Allowed directories", :2552 startswith if, :2572 =
  mkdir); test blob 8768beb8947… identical merge=pin; aed03e1ae ancestor of merge;
  d6344e031's system.py blob 75fecb572 = the pin blob. Severity low fair (symbols named in
  prose :233/:247-248).
- Refuted=false (NOT-REFUTED; verdict 7074_c1.md).
- Fix: re-point both cites to :2554-2560 / :2580. Size S; backend.
- Owner: ruled 277: later (backend cleanup).

### Q-075 · low · feature-inventory F-022 (5 cites) · #7077

- Wrong: one defect, two carriers — the same five stale F-022 cites as Q-093, attributed here
  under #7077 (its diff touches the same surface).
- Evidence: Depends at :1639 RESOLVED (route 1637-1638, Depends :1639); guard :1040-1041;
  the rowCites gate is existence-only; 6b691302d's blind -8 was wrong at its own tree;
  834d51097 is the first breaker; movers exactly {834d51097, d6344e031, e2d65dda3, 516cffc98};
  the row's own prose admits un-policability.
- Refuted=false (NOT-REFUTED; verdict 7077_c0.md). Dedup twin of Q-093 — resolved with
  Q-093's fix; the full template lives there.
- Fix: see Q-093.
- Owner: see Q-093.

### Q-076 · low · frontend/tests/golden/shell/rate-limit.spec.ts · #7077

- Wrong (path corrected per ruling 277 — the spec lives in tests/golden/shell/): four stale
  cites (:31 :33 :147 :570), one PAST EOF — SystemMonitoringPage.tsx:751; the file is 745
  lines at the pin, so :751 is unresolvable. The :31/:33 anchors carry two of F-022's five
  stale cites (api.ts:2165, system.py:1626) shared with Q-093 — they ride Q-093's [r277b]
  fix, not frontend's cleanup.
- Evidence: fix anchor :2116 or :2113; api.ts:901 = empty line; second past-EOF cite in
  batch 3 (cf. Q-089's config.py:3497-3500).
- Refuted=false (NOT-REFUTED; verdict 7077_c1.md).
- Fix: re-derive the four; anchor the EOF case. Size S; frontend.
- Owner: ruled 277: later (frontend cleanup; Q-076 anchors ride Q-093's fix).

### Q-077 · low · docs/uplevel/packages/frontend.md :149/:410 · #7077

- Wrong: queryClient.ts:249-297 names `updateRateLimitStoreFromError`, a symbol [r132]
  deleted — the symbol is absent at the merge tree (wrong-at-birth) and at the pin; exact
  only at the diff base 8a49ae7ac.
- Evidence: ruled 277: the proposed :247-251/:295-299 re-point lands on the unrelated
  queryKeys docblock and factory; the symbol has no live coordinate to re-point to.
- Refuted=false (NOT-REFUTED; verdict 7077_c2.md).
- Fix: revision-qualify the cite (`8a49ae7ac:frontend/src/services/queryClient.ts:249-297`)
  or drop the coordinate. Size S; docs.
- Owner: ruled 277: later (docs cleanup; fix re-worded to revision-qualify or drop, not :247-251/:295-299).

### Q-078 · low · frontend/src/services/queryClient.ts:123 · #7077

- Wrong: the @example says 60000ms while MAX_RETRY_DELAY_MS=30000 (:75) — and the example
  exercises the capped path.
- Evidence: test asserts 30000; blob 6b57aae6 identical pin=merge.
- Refuted=false (NOT-REFUTED; verdict 7077_c3.md).
- Fix: fix the example value. Size S; frontend.
- Owner: ruled 277: later (frontend cleanup).

### Q-079 · low · DashboardConfigModal.tsx:110 + DashboardConfigModal.test.tsx:468 · #7086

- Wrong: both cite DashboardLayout.tsx:268 for mainWidgets; :268 is topWidgets since
  d6344e031 (:276 is mainWidgets, declared :271).
- Evidence: scope wider than the item — the same drifted :268 anchor also sits in
  gpu-stats.spec.ts:199/:246 (held-as-written; re-check in batch 4) and
  pipeline-telemetry.spec.ts:192 = 5 carriers total; one fix sweeps all five. Merge of
  auditor candidates C1+C2 (one drifted anchor, two test carriers).
- Refuted=false (NOT-REFUTED; verdict 7086_c1.md).
- Fix: one fix sweeps all five carriers. Size S; frontend.
- Owner: ruled 277: later (frontend cleanup).

### Q-080 · low · frontend/tests/golden/dashboard/pipeline-telemetry.spec.ts:16 · #7086

- Wrong (path corrected per ruling 277 — the spec lives in tests/golden/dashboard/): stale
  cites with TWO first-mover stories kept distinct — api.ts 2119→2070-2072
  (first mover 2099deab6 [r130f]), schemas 853→862 / 799→808 / 945-948→951-954 (first mover
  3a1bc8fdf [r130b]; fix-span 862-889 short — runs to ~:932), layout 268→276 / 377→385
  (first mover 4238c6260 [r130f]) — NOT d6344e031 for any leg.
- Evidence: spec author 3d14e7da2.
- Refuted=false (NOT-REFUTED; verdict 7086_c3.md).
- Fix: re-derive all cites. Size M; frontend.
- Owner: ruled 277: later (frontend cleanup).

### Q-081 · low · feature-inventory F-042/F-040 rows :383/:385 · #7086

- Wrong: the :268→:276 drift reaches the inventory rows; the mints-sentence author is
  8f39f6102, not c997b0b7d.
- Refuted=false (NOT-REFUTED; verdict 7086_c4.md).
- Fix: re-anchor both rows. Size S; docs.
- Owner: ruled 277: later (docs cleanup).

### Q-082 · low · feature-inventory F-042 works-cell · #7086

- Wrong: the works-cell flip; '**works** waits on the real tier' = 57 hits repo-wide — a
  systemic pattern, not this PR's coinage.
- Refuted=false (NOT-REFUTED; verdict 7086_c5.md). Owner real-tier batch (5db3c56f7)
  contributed the phrasing.
- Fix: sweep the phrase repo-wide. Size M; docs.
- Owner: ruled 277: later (docs cleanup).

### Q-083 · low · feature-inventory F-040 '9 commits behind' · #7086

- Wrong: authoring-tip miscount — the true count is 7 (97c602ae9..1132ab8c9); exactly one
  9-shaped number exists (97c..8f39f6102 = 9).
- Refuted=false (NOT-REFUTED; verdict 7086_c6.md).
- Fix: correct to 7. Size S; docs.
- Owner: ruled 277: later (docs cleanup).

### Q-084 · low · frontend/tests/golden/dashboard/config-modal.spec.ts:13 · #7086

- Wrong (path corrected per ruling 277 — the spec lives in tests/golden/dashboard/): four
  stale anchors (:297 vs testid :306; :147-150 Save vs :152; :152-155 Cancel vs
  :158-161; :337-342 vs :346) and the PR's own irony — c997b0b7d moved handleSave
  :142→:152 / handleCancel :148→:158 without re-deriving, and 5047db829's spec diff is
  exactly the one-line :268→:278 fix.
- Evidence: corrections folded: the layout-shift mover is 4238c6260 [r130f], NOT
  d6344e031's own merge diff (diff bf82aa0ca→d6344e031 empty); ":154-234 never matched" was
  overbroad (reset/cancel/save WERE in-span at authoring); :297/:337-342 defensible-at-birth
  (testid one line after the cited coord); :147-150/:152-155 wrong at authoring too (Save
  141-145, Cancel 147-151), the PR's +10 shift made them 5 staler; only the Switch cite :278
  was re-derived correctly; authoring 5a3c8bbf1 (2026-10-11); spec blob ca72d0146
  pin=boundary.
- Refuted=false (NOT-REFUTED; verdict 7086_c7.md).
- Fix: re-derive all four. Size S; frontend.
- Owner: ruled 277: later (frontend cleanup).

### Q-085 · low · docs/architecture/decisions.md:188 · #7088

- Wrong: cites config.py:1942-1982 for the fast-path Field (real :1739, banner :1729-1732,
  validator ends :1767) and prod.yml:643 (real :672) — authored-live-rotted: written against
  a live tree that moved under the author before merge.
- Evidence: movers af7690bfd + 8c3c8a7f6 (both [B3.3], 2026-10-18 14:29:48) took 1951→1747→1739
  (intermediate :1748); prod.yml first mover d6344e031, then 51a2738f0 [r243] 2026-10-16
  659→672; merge 81b40861a 2026-10-14; the item was authored on the r130b branch side
  (3a1bc8fdf2); the status claim still holds at the pin.
- Refuted=false (NOT-REFUTED; verdict 7088_c1.md).
- Fix: re-point both. Size S; docs.
- Owner: ruled 277: later (docs cleanup).

### Q-086 · low · docs/architecture/system-overview/configuration.md:174 · #7088

- Wrong (path corrected per ruling 277 — the file lives in docs/architecture/
  system-overview/): same root as Q-085 — the Source line at :174 cites the same stale
  span; the true block is 1730-1770, fields-only 1739-1754.
- Evidence: both 3a1bc8fdf and 3a1bc8fdf2 carry the identical Source line at :174.
- Refuted=false (NOT-REFUTED; verdict 7088_c2.md).
- Fix: re-point. Size S; docs.
- Owner: ruled 277: later (docs cleanup).

### Q-087 · low · docs/uplevel/packages/backend.md :377/:383 · #7088

- Wrong: F-187/190/191 cite config.py:1952→:1740 and F-089 cites jobs.py:296-299→:291-295 —
  drifted-post-merge on the jobs.py leg.
- Evidence: ONE jobs.py mover — 6b691302d (2026-10-18 01:32, ~206 lines deleted);
  af7690bfd touches jobs.py 0 times; pin jobs.py :291 = job_type Query, :296 = queue Query;
  the UR-181 counter-read rejected.
- Refuted=false (NOT-REFUTED; verdict 7088_c3.md).
- Fix: re-point all (one fix PR sweeps Q-085/Q-086/Q-087 + the jobs.py repoint). Size S;
  docs.
- Owner: ruled 277: later (docs cleanup).

### Q-088 · low · backend/tests/unit/core/test_config_fast_path_flag.py :63-64/:75-76 · #7088

- Wrong (path corrected per ruling 277 — the test lives in backend/tests/unit/core/):
  schemas settings_api.py:49 is WRONG-AT-BIRTH (:49 fast_path_enabled bool, :53
  threshold, :56 le=1.0 — at pin AND merge); config.py:3497-3500 for get_settings (real def
  :3171, span 3170-3176 correct; :3495 at merge with no @cache there; 3176 lines pin vs 3500
  merge).
- Evidence: mover chain af7690bfd (3500→3211) → 8c3c8a7f6 (→3199) → 9fcb5f453/a30a502df
  (→3176); test blob 805920c8c identical.
- Refuted=false (NOT-REFUTED; verdict 7088_c4.md).
- Fix: re-derive. Size S; backend.
- Owner: ruled 277: later (backend cleanup).

### Q-089 · low · backend/tests/golden/external/test_settings_save_roundtrip.py :19/:142/:171 · #7088

- Wrong: three dead cites — :3497-3500 is past EOF (config.py had 3176 lines at the pin;
  second past-EOF carrier in the batch), :2370 is blank (was queue_max_size), :2703 is the
  CA-cert description (was clip_generation_enabled).
- Evidence: queue_max now :2098, clip now :2431; authored 9d284659c pre-boundary, carried in
  by d6344e031/#7205; mover af7690bfd first AND only content mover of all three coords;
  misdirection far-field; blob 681449a1bb identical.
- Refuted=false (NOT-REFUTED; verdict 7088_c5.md).
- Fix: re-derive to :2098/:2431/:3170-3176. Size S; backend.
- Owner: ruled 277: later (backend cleanup; lane moved frontend→backend per ruling 277).

### Q-090 · low · docs/architecture/detection-pipeline/critical-paths.md:129 · #7088

- Wrong (path corrected per ruling 277 — the doc lives in docs/architecture/
  detection-pipeline/, and the same cite has a second carrier at
  detection-pipeline/batch-aggregator.md:352): cites vlm_analyzer.py:690-705 for the
  verification fn — pre-existing-stale-kept; the real fn is :898-914 (next def :915);
  :690-705 is session.add(event)/EventVerification code in another method.
- Evidence: at the merge the fn was :801-817; it moved 801→898 between f8a7908fa (:803) and
  5d990377e (#7182 merge, Oct 15 16:25, :898); the PR's doc blob 3bd933962 is identical
  d6344e031→pin; post-7088 doc movers 365ce75d4/427b8ba79/be8627161 keep the stale text.
- Refuted=false (NOT-REFUTED; verdict 7088_c6.md).
- Fix: re-point to :898-914. Size S; docs.
- Owner: ruled 277: later (docs cleanup).

### Q-091 · low · docs/architecture/background-services/batch-aggregator.md:24 · #7088

- Wrong (path corrected per ruling 277 — the doc lives in docs/architecture/
  background-services/): the table row says BATCH_MAX_DETECTIONS=100; config.py:972-973 has
  default=500 ge=1 le=10000 (service binds settings.batch_max_detections :202/:587) — six
  other pin docs say 500, so this is an outlier, not ambiguity.
- Evidence: the default's base/merge location :1028 (pin-relative :973); doc blob 706f0f379
  → 0e2eaedb4 = pin — the PR rewrote the table (added the FAST_PATH_ENABLED row, flipped
  0.95→0.9, object-types) but carried the row through unchanged at line 24.
- Refuted=false (NOT-REFUTED; verdict 7088_c7.md).
- Fix: fix the row to 500. Size S; docs.
- Owner: ruled 277: later (docs cleanup).

### Q-092 · low · docs/developer/batching-logic.md :103/:124 · #7088

- Wrong (path corrected per ruling 277 — the doc lives in docs/developer/): cites the dead
  symbol _is_fast_path_eligible (grep rc=1 — dead at the pin); the real gate is
  _should_use_fast_path :1186 (checks self._fast_path_enabled :1216 first,
  optional args :1219), _process_fast_path def :1227 (not :1218); call sites :557/:567.
- Evidence: the PR edited the snippet body (added the self.fast_path_enabled conjunct as
  context) and the table, but left the dead name; doc blob 92452ea48 (base 60ca6305c) →
  6878d3d77 (merge = d6344e031 = pin); refuter softening folded: the doc uses bare
  `self.fast_path_enabled` vs the backend's `self._fast_path_enabled` (:1216).
- Refuted=false (NOT-REFUTED; verdict 7088_c8.md).
- Fix: replace the symbol + re-point. Size S; docs.
- Owner: ruled 277: later (docs cleanup).

### Q-095 · low · scripts/test_orchestrator_engine_socket.py:3 · #7114

- Wrong: the docstring's "451 lines" parenthetical was false at its OWN merge — added within
  #7114 while ops.md had 643 lines and [r162] sat at :456 (pin: ops.md 993 lines, [r162] at
  :508-522).
- Evidence: mechanisms 1+3+2 (authored-false, live-rotted, and one more); [r151] :452;
  prod.yml :502/:1613; config.py enabled :118 / compose_file :133; feature_check :604-608.
- Refuted=false (NOT-REFUTED; verdict 7114_c1.md).
- Fix: fix the parenthetical. Size S; scripts.
- Owner: ruled 277: later (scripts cleanup).

### Q-096 · claim · scripts/uplevel/reid_real_tier.sh S5 :794-799 · #7125

- Wrong: S5's universal "NO plan" contradicts S3's refusal shape (:769-778),
  export_reid.py:1008-1019 ("Do NOT unlink here"), and scripts/uplevel/AGENTS.md :257-258 vs
  :262-263 — and the refusal still fails via the table's stage-4 unknown exit 2.
- Evidence: start_gateway poll 60×5s (:369-380); authored f99058805 [r157] (not 7b814c4ae);
  blobs pin=merge; false at birth — the mechanism-3 flagship.
- Refuted=false (NOT-REFUTED; verdict 7125_c0.md).
- Fix: align S5 with S3/export/AGENTS. Size M; scripts.
- Owner: ruled 277: later (scripts cleanup).

### Q-097 · claim · test_monitoring_key_field_ceiling.py docstring + A-family census · #7135

- Wrong: the docstring's cites are dead at the pin — events.py :441/:564/:566/:452-455 (from
  :407/:530/:532/:420-421), conftest :1729 (from :1755), ci.yml :2052-2053/:2058-2059 (from
  :2036/:2042) — and the A-family dead-coordinate census rides this row.
- Evidence: authored head cd9c579f5 verified at both 75ea5ee10399 and cd9c579f5; pin blob
  09cf5fc893 vs authoring 69b9dd0604, cite text byte-identical. A-family (first breaker
  #7135): :282×7, :569×3, :427, :468, :542 — joins here with 7070-C5/C6/C9.
- Refuted=false (NOT-REFUTED; verdict 7135_c1.md).
- Fix: re-derive the docstring + sweep the A-family. Size M; backend.
- Owner: ruled 277: later (backend cleanup; census sweep waits for the wired CI drift check per ruling 277).

### Q-098 · low · backend/tests/unit/api/test_api_key_scopes.py :27-28 · #7135

- Wrong: "stayed-unscoped stance (2)" — "(2)" is an AMENDMENT NUMBER misread as an instance
  count; the section comment at :702 carries the same stale framing (second site the
  refuter found).
- Evidence: half-true — "flag-off returns" survives.
- Refuted=false (NOT-REFUTED; verdict 7135_c2.md).
- Fix: fix both sites. Size S; backend.
- Owner: ruled 277: later (backend cleanup).

### Q-099 · low · vulture_whitelist.py :37-38/:42 (repo root) · #7135

- Wrong (path corrected per ruling 277 — the file is at the repo root, not scripts/):
  'seven bodies' vs 11 at the pin (7 in TestScopedKeyFieldCeiling + 4 in
  TestRecommendationsSuggestionCeiling); the :42 stamp "(measured 2026-10-15, run
  38671466660 job 116218984106, 7 sites, 100%)" is attached to the CI-run sentence.
- Evidence: 7 was true at merge 75ea5ee10399; blob 27df4f858d merge=pin.
- Refuted=false (NOT-REFUTED; verdict 7135_c3.md).
- Fix: update the count + restamp. Size S; scripts.
- Owner: ruled 277: later (scripts cleanup).

### Q-100 · low · backend/api/routes/events.py :587-588 + ceiling test :93 · #7135

- Wrong: "0 hits for verification under monitoring/" — there are 7 matching lines (6
  alerts.yml + 1 AGENTS.md:108 tlsSkipVerify); the word-boundary variant leaves 2 lines
  standing; none consumes the events-API verification field, so the substance holds.
- Evidence: mirrored at test_monitoring_key_field_ceiling.py:93; false at merge too
  (identical counts at 75ea5ee10399); comment byte-identical merge→pin.
- Refuted=false (NOT-REFUTED; verdict 7135_c5.md).
- Fix: qualify the needle at both sites. Size S; backend.
- Owner: ruled 277: later (backend cleanup).

### Q-101 · low · feature-inventory F-019 :355 · #7139

- Wrong: App.tsx:275 → the real /operations route is :293 (18 off); #7139's own code commit
  3925f2094 WORSENED the drift while its docs commit ea5fbd923 re-anchored five OTHER rows
  (F-002/F-020/F-024/F-034/F-238) and skipped F-019.
- Evidence: corrected 5-step chain 275→[r132] 62c72165e 274→[r130f] 453bec830 285→[#7139 own
  r133] 284→[r204] 70c5d96ae 293; pin :275 = EventDeepLinkRedirect; drift instrument
  frontend/scripts/feature-inventory-cite-drift.mjs is HAND-RUN (no ci.yml/package.json
  wiring); ci.yml validate_docs excludes docs/reference.
- Refuted=false (NOT-REFUTED; verdict 7139_c1.md).
- Fix: re-anchor. Size S; frontend.
- Owner: ruled 277: later (frontend cleanup; in the feature-inventory sweep cluster).

### Q-102 · low · feature-inventory F-021 :357 · #7139

- Wrong: App.tsx:342 was off-by-one FROM BIRTH (authoring 4238c6260 mount :341, cite :342 =
  the </BrowserRouter> line); stale by 19 at the pin.
- Evidence: pin :342 = heatmaps Route, :361 = <ProductTour />; nesting verified (:348 inner
  </Routes>, :355 </ProtectedRoute>, :358 outer </Routes>) — :342 IS inside both, :361
  outside both, the exact opposite of the contrast; first breaker [r130f] 453bec830 +11 (no
  re-anchor); #7139's 3925f2094 (-3 InstallPrompt) kept it stale (mount :351 at merge); the
  semantic content is TRUE of :361 — a pure re-anchor fix.
- Refuted=false (NOT-REFUTED; verdict 7139_c2.md).
- Fix: re-anchor to :361. Size S; frontend.
- Owner: ruled 277: later (frontend cleanup; in the feature-inventory sweep cluster).

### Q-103 · low · feature-inventory F-020 :356 · #7139

- Wrong: span 251-334 with open/close asymmetry — the open is exact at the merge (#7139's
  re-anchor was a mechanical -1 shift) but the close was NEVER exact in the row's lifetime
  (inherited shortfall); the true span is 260-353 (pin :251 = <ProtectedRoute>, :260 =
  <AmbientStatusProvider>, :353 = </AmbientStatusProvider>).
- Evidence: at the merge 1e1c241ed the provider spans 251-344 (close already 10 short); base
  1ab5d084d cites 252-335; mover 70c5d96ae widened the close drift 10→19; the cited span
  still CONTAINS the provider open (260 ∈ [251,334]) — a misstated extent, not a total miss;
  "landing the reader on the auth-gate region" overstated.
- Refuted=false (NOT-REFUTED; verdict 7139_c3.md).
- Fix: re-derive the span. Size S; frontend.
- Owner: ruled 277: later (frontend cleanup; in the feature-inventory sweep cluster).

### Q-104 · low · feature-inventory F-238 :634 · #7139

- Wrong: App.tsx:251 was correct at its own merge (:251 = <AmbientStatusProvider> at
  1e1c241ed) and was re-staled by [r204] 70c5d96ae (net +9: ConnectionStatusProvider wrapper
  - an 8-line comment), ancestor of the pin; shares its mover with Q-103 — F-020 (:356) and
    F-238 (:634) are the only 25x cites remaining at the pin.
- Evidence: AmbientStatusProvider.tsx:82 not re-checked.
- Refuted=false (NOT-REFUTED; verdict 7139_c4.md).
- Fix: re-anchor both with Q-103's fix. Size S; frontend.
- Owner: ruled 277: later (frontend cleanup; in the feature-inventory sweep cluster).

### Q-105 · low · feature-inventory F-034 :378 · #7139

- Wrong: BOTH F-034 legs are stale (ruled 277) — the mount leg (App.tsx:263-268 Route
  block; the row's element cite lands at the pin's :272-277 after 70c5d96ae's +99/-89
  wrapper + comment above Routes) and the catch-all leg, which the row cites as
  App.tsx:338: the pin's :338 is the /face-recognition `<Route` opening, `path="*"` sits at
  :347. The sheet's earlier "catch-all :347 exact" misread the row, which cites 338.
- Evidence: both exact at the merge 1e1c241ed (block 263-268, catch-all 338); the
  Suspense-wrapper rescue fails — the wrapper is INSIDE the cited span itself; pin :338 =
  /face-recognition opening, :263 = Suspense.
- Refuted=false (NOT-REFUTED; verdict 7139_c5.md).
- Fix: re-anchor both legs. Size S; frontend.
- Owner: ruled 277: later (frontend cleanup; both F-034 legs stale per ruling 277).

### Q-106 · low · frontend/src/**tests**/pwa-install-prompt-retired.test.tsx:58 · #7139

- Wrong: "Devtools +10" (not +9: 358→368) — the clause was true when authored (App.tsx:358 =
  ReactQueryDevtools at the merge 1e1c241ed) and is false at the pin (:358 = </Routes>,
  :368 = Devtools), in the very sentence teaching why bare cites can't be trusted; the
  "Now = as of merge" reading does NOT defuse it.
- Evidence: the revision-qualified cite 1f6405610:App.tsx:358 = <InstallPrompt /> is still
  correct; App.tsx blob 90735aa45 at the pin (70c5d96ae rewrote 2cb89db09→90735aa45); PR
  #7230's number not independently confirmable in the shallow clone but [r204] label +
  timing check out.
- Refuted=false (NOT-REFUTED; verdict 7139_c6.md).
- Fix: re-word to a revision anchor or drop the bare cite. Size S; frontend.
- Owner: ruled 277: later (frontend cleanup).

### Q-107 · low · frontend/tests/golden/operations/batch-statistics.spec.ts:19-94 · #7145

- Wrong: ~14 stale cites across 5 files — system.py 4105→4093, 4127-4133→4115-4121,
  4032→4020, 4130→4118, 4148-4149→4136-4137, 4151→4139-4140, 4164→4152, 4175→4163;
  vlm_analyzer 517→521; pipeline_workers 1204→1174; config 1027→973 (Field at :972, not
  :973); 980-983→925-928; main.py worker registration→pipeline_workers 1583-1598 (main.py
  has 0 register_worker, :997 getattr); stats-row 146→230; harness.ts:17-20→
  tests/golden/harness.ts:60.
- Evidence: authored by #7145, exact at its merge 096ae1bd9, displaced by
  #7183/#7182/#7244/#7258/#7191/[r148a]; the stats-row mover is be8627161 (not [r148a]
  10d00a96e — imports only; [r148a] keeps the harness-fold); the 4-key pipeline span is
  :4116-4120 (the item's :4115-4121 defensible as a statement span); PR-level attributions
  plausible but the in-window carriers are nameable as be8627161, #7243 (134bf412e, pw -30),
  and registration below the shallow boundary.
- Refuted=false (NOT-REFUTED; verdict 7145_c1.md).
- Fix: re-derive all. Size M; frontend.
- Owner: ruled 277: later (frontend cleanup).

### Q-108 · low · frontend/tests/golden/operations/batch-statistics.spec.ts :56-57 · #7145

- Wrong: "checks every 10 s" is a self-authored error — the constructor default is 10.0 but
  the manager passes settings.batch_check_interval_seconds, default 5.0 (config.py:965-966
  `batch_check_interval_seconds: float = Field(default=5.0, ge=1.0, …)`, pw:1585); false at
  BOTH the merge and the pin (merge :1619 = `check_interval =
settings.batch_check_interval_seconds`).
- Evidence: no env/compose override; repo docs say 5 s; #7182's provenance is +41/-14 gross
  +27 net, displacing :1204→:1231 DOWN — "#7182 -30" wrong; the sibling config.py:980-983 is
  also stale (field now :925) — same sentence, not claimed by the item.
- Refuted=false (NOT-REFUTED; verdict 7145_c2.md).
- Fix: fix to 5 s. Size S; frontend.
- Owner: ruled 277: later (frontend cleanup).

### Q-109 · low · feature-inventory F-135 :518 · #7145

- Wrong: get_pipeline_status :4253→:4241 (mover a4916e3ea, #7183 [UR-48], -12); authorship:
  #7145 re-anchored :4185→:4253 itself; NO wired gate checks feature-inventory.md line cites
  at all (ci.yml:391-397 line_bounds tier covers docs/decisions|deployment|getting-started|
  operations|ui only; docs/reference excluded, grounds_sweep.py:33-35; the inventory
  instruments — summary-arith, witness — never read line coords; "cannot catch" true a
  fortiori); "#7183 the census PR" nickname not corroborated in-tree (commits say [UR-48],
  ruling 168 item 3).
- Evidence: severity low honest — the cite lands inside the same function; the def-line
  convention anchor is still 12 off (the row's own convention: "batch_aggregator.py:1031,
  def :266").
- Refuted=false (NOT-REFUTED; verdict 7145_c3.md).
- Fix: re-anchor. Size S; docs.
- Owner: ruled 277: later (docs cleanup; in the feature-inventory sweep cluster).

### Q-110 · low · feature-inventory F-135 witness clause · #7145

- Wrong: "spec bytes differ by comment only" is now false — the harness fold
  ('./harness'→'../harness' at :116 via [r148a] 10d00a96e) and the describe title's
  '(F-135)' tag at :142 via [r218] 08030119d changed bytes; the correct strength is
  "comment-only-equal".
- Evidence: run 38671466660's predecessor run 38664676455 (head 9c71e27639, conclusion=
  failure on uplevel/r134-retire-batch-history-views); run-head spec c5b38a851; 56 comment
  lines differ, 159 non-comment identical each side; the claim was true at the merge
  (code-only diff run-head vs merge = empty); the mover walk is exact (3 movers incl. the
  boundary d6344e031; r218 hidden from the plain walk = the shallow-graft artifact); pin
  :116/:142 byte-confirmed, blobs 12212c335 vs aa0cf8f39.
- Refuted=false (NOT-REFUTED; verdict 7145_c4.md).
- Fix: correct the strength. Size S; docs.
- Owner: ruled 277: later (docs cleanup; wording call kept).

### Q-111 · claim · backend/tests/integration/test_soft_delete.py :209/:218/:251 · #7146

- Wrong: four dead docstring cites — born-TRUE at the merge d57362ff0 (ea4f36209 authored):
  :790 right-endpoint/wrong-line, :941 wrong-endpoint (worst), :606 wrong-function; the
  B-family dead-coordinate census anchors here.
- Evidence: mover arithmetic 606+31-1+22+13 = 671; 790→855; 941→1006; schemas 368-369→366-377
  by e2d65dda3 -2; corrections folded: drop b5c6fea3c (rename-only); "[r95] predates the
  merge" is timestamp-only; d6344e031 is the graft artifact. B-family (first breaker #7146):
  :1952×5, :2010×2, :719, :2430/:2512, :2139, :1424, :1793, :2703/:2726×3/:2745 — folds here
  with 7070-C2 siblings and 7070-C3.
- Refuted=false (NOT-REFUTED; verdict b3_7146c1.md).
- Fix: re-derive the docstring + sweep the B-family. Size M; backend.
- Owner: ruled 277: later (backend cleanup; census sweep waits for the wired CI drift check per ruling 277).

### Q-112 · low · backend/api/routes/events.py:691 · #7146

- Wrong: cites ci.yml:692 for the mypy check; the mypy backend/ run is at :772 at the pin.
- Evidence: total drift +80 across SEVEN landings: +1 (r181/#7164, first mover 1cb31cab2 —
  merged via d62b08eb8 08:43, reached main ~6h earlier) +43 (r162/#7114: ac84fd7d9 +7,
  122365750 +4, 8b764012e +32) +30 (r197/#7186) +3 (r218/#7193) +1 (r193/#7175) +1
  (O3.6/#7251) +1 (B3.3 3513732ef main line); hunk arithmetic independently confirms +80;
  authored 57174acf0 18:25, merged 23:13; #7146 didn't touch ci.yml (blob identical
  468eeee1 vs d57362ff0); the comment block is verbatim at the pin :687-692, merge :622-627
  IDENTICAL; pin ci.yml :691-692 = "Verify installation"/pytest-import check, mypy backend/
  at :772 (unique hit); repo-wide ci.yml:692 = exactly ONE carrier; DISTINCT from 7135-C1's
  ci.yml cites — different region.
- Refuted=false (NOT-REFUTED; verdict b3_7146c2.md).
- Fix: re-point to :772. Size S; backend.
- Owner: ruled 277: later (backend cleanup).

### Q-113 · low · backend/tests/integration/test_soft_delete.py:667 · #7146

- Wrong: the vacuous stats leg asserts 200 + membership (:668 docstring, :673-675 seeding,
  :678 GET, :679 200-assert, :683 conceding comment, :684 membership-assert, next def :686)
  while the real leg (:204-253) carries THREE aggregates (total_count_query ~:701-705,
  risk_level_query ~:711-714, camera_stats_query :730-734 — "for condition in filters" in
  each) + the cross-view /api/events pagination.total (:248-253).
- Evidence: the route filter seed :692 is shared by all three; the response dict :756-761
  carries the literal "total_events" key; the vacuous leg was authored ee5a050fa 2026-01-09
  pre-window (with 1c0ec19a0/92f6451b5 same-message commits); the conceding comment's
  premise is FALSE — the deterministic ==2 assert was available and declined ("didn't
  check", not "couldn't check"); keeper = #7146 — the fix is deletion of pre-existing rot,
  mechanical. No wired gate flags vacuous asserts (ruff select list pyproject.toml:354-371;
  the coverage gate ci.yml:1000-1025 is percentage-based over unit tests only — a vacuous
  test ADDS coverage, can never trip it). The deleting PR must re-check the file's internal
  cites after the 18-line block goes (ea4f36209 precedent); the vacuous leg sits at :775 at
  the boundary, :667 at the pin; conftest.py's client fixture runs _cleanup_test_data()
  (grep hit :27) — deterministic counts supported.
- Refuted=false (NOT-REFUTED; verdict b3_7146c3.md).
- Fix: delete the 18-line block; re-check internal cites after. Size S; backend.
- Owner: ruled 277: later (backend tests cleanup; optional promote per the verification).

### Q-115 · low · docs/superpowers/plans/2026-09-27-a5500-vlm-bringup-checklist.md:58 · #7156

- Wrong: the first mover is 2467cea06 (2026-09-28 15:07, def→2609, test→107), NOT
  734f5e409 (2026-09-29 00:17, second mover →2561/:110); both r8-era, so "broken before this
  PR" stands; the measured gaps are 2/36/4, not "2-400+".
- Evidence: the row in its pinned form was authored by the 09-27 re-render; a7dc48daf's
  original had different cite forms.
- Refuted=false (NOT-REFUTED; verdict 7156_c2.md).
- Fix: fix the cites + the gap numbers. Size S; docs.
- Owner: ruled 277: later (docs cleanup).

### Q-116 · low · docs/superpowers/plans/2026-09-25-a5500-bringup-checklist.md:48 · #7156

- Wrong: same first mover as Q-115 (2467cea06 — one commit, two rows); .env.example:58 was
  already stale AT ROW ENTRY: a0105b630 (#6678 squash) already had TMPDIR at :57 (58→57
  pre-151ccc058), the authoring branch still had 58, then e40d69f56 took 57→55.
- Evidence: TMPDIR at :55; system.py defs :2544/:2570; test_system_routes.py defs
  :110/:2414/:2426 — the fix cites three defs though the row names four tests.
- Refuted=false (NOT-REFUTED; verdict 7156_c3.md).
- Fix: fix the cites + TMPDIR :55 + the three test defs. Size S; docs.
- Owner: ruled 277: later (docs cleanup).

### Q-117 · low · scripts/a5500_precheck.py :967-975 · #7156

- Wrong: the generator's test expectations (:576/:598) diverge from the rendered output
  (:577/:599) — a future render would regress the fixed rows; the disposition SHA
  6186718407 is UNRESOLVABLE (git cat-file fatal) — the substance lives in 7ad0fd8fd's own
  commit message ("scripts/ is ops's cell…"): cite the commit, not the SHA.
- Evidence: system.py:2508 mover attribution WRONG — at e0414f8ca _runtime_env_path was
  already at :2610; walk 2610→2561 (734f5e409)→2496 (e40d69f56)→2537→2544; neither named
  mover produced :2508; "predate the PR" half still true (stale at f9a18d028); generator
  blob 30bc7f473 byte-identical f9a18d028→pin.
- Refuted=false (NOT-REFUTED; verdict 7156_c4.md).
- Fix: sync the expectations + cite the commit. Size S; scripts.
- Owner: ruled 277: later (scripts cleanup).

### Q-118 · low · backend/tests/e2e/test_pipeline_integration.py :121-122 · #7156

- Wrong: the header comment "mock_get refuses GET on these" is a blanket the fake doesn't
  honor — the MockPipeline.execute get-branch (:249-259) is unguarded: it answers
  batch_data.get(key) with no list_keys check; mock_rpush writes list_data only, so a
  pipelined GET of an rpushed key returns None → _parse_detections(None) = [] → a
  well-formed detection_count=0.
- Evidence: the guard covers only the wrapper-level GET seam (mock_get :144-147 WRONGTYPE
  raise); the author consciously scoped the raise (:141-143 wrapper-level note) but the
  header attributes can't-hide to "this fake" as a whole; the pre-hardening parent
  (cd00c7261) had BOTH seams unguarded — the pipeline seam was never hardened; the comment
  sits at :121-122, not :118-121 (:118-119 are the batch_data/list_data dict declarations);
  blob 84faf71ba f9a18d028=pin.
- Refuted=false (NOT-REFUTED; verdict 7156_c5.md).
- Fix: guard the get-branch or narrow the comment. Size S; backend.
- Owner: ruled 277: later (backend tests cleanup; optional promote per the verification).

### Q-119 · low · five qualified carriers citing ai_audit.py:194 · #7157

- Wrong: docs/architecture/ai-pipeline-current-state.md:163, docs/vss-integration/
  15-progress-since-the-design.md:125, 16-errata-2026-10-03.md:1751,
  18-world-class-target.md:502, docs/vss-integration/history/17-closed-issues.md:15 cite
  ai_audit.py:194 for the def; the pin's :194 is the decorator close paren, the def is
  :195.
- Evidence: chain — 702198999 [r129 undefer] 2026-10-13 shifted the def 193→194 →
  eb7ce4431's blind +1 remap (its own import insert at ai_audit.py:22 landed the cite on
  the parent-tree call lines :228/:274 while eb's own tree has calls at :229/:275) →
  62a2d7eea repaired elsewhere; the errata's "(seven hits)" is separately stale; the grep
  substance is true at :195 (12 hits).
- Refuted=false (NOT-REFUTED; verdict 7157_c2.md).
- Fix: re-point all five to :195. Size S; docs.
- Owner: ruled 277: later (docs cleanup).

### Q-120 · low · docs/reference/feature-inventory.md F-062 :413 · #7157

- Wrong (path corrected per ruling 277 — the row lives in docs/reference/
  feature-inventory.md :413, not backend-entry-points.md): F-062's relative :194 contradicts
  F-061's :195 two rows apart; 62a2d7eea rewrote BOTH rows in the same field edit
  (:157→:158) and still left :194 — exactly F-062's :194 is false (:195 true); the commit
  message names the class verbatim.
- Evidence: no gate scans docs/reference.
- Refuted=false (NOT-REFUTED; verdict 7157_c3.md).
- Fix: fix F-062 to :195. Size S; docs.
- Owner: ruled 277: later (docs cleanup).

### Q-121 · low · docs/vss-integration/17-action-plan.md:5653 · #7157

- Wrong: :228/:274 correct-at-remap, born-stale-by-later-drift — born at 31551704a
  (2026-10-03, [r213-era research refresh]) TRUE at birth (:227/:273); eb7ce4431 is the
  remapper, not the author; the calls are at :229/:275; "one-short even pre-remap" is TRUE
  at the boundary vantage (702198999's shift 227→228 pre-merge) and FALSE at the birth
  vantage; adjacent dead cites ride the fix (config.py:2707-2708 dead —
  background_evaluation_enabled now :2573, default=True :2574; main.py:1054-1068 dead — the
  evaluator boot deleted by 9fcb5f453 B3.1; BackgroundEvaluator retired, only
  test_main.py:663-671 asserts it).
- Evidence: gates skip 17-action-plan.md (check-uplevel-cites.py explicitly skips it;
  check-vss-docs-currency.py doesn't resolve .py:LINE cites) — comment-only severity.
- Refuted=false (NOT-REFUTED; verdict 7157_c4.md).
- Fix: fix the whole bullet. Size S; docs.
- Owner: ruled 277: later (docs cleanup).

### Q-122 · low · docs/reference/backend-entry-points.md:158 · #7157

- Wrong: the prose `POST /batch` (:504) contradicts the file's own table :153 citing :534
  (decorator :524, "/batch" :525, def :534); true only at authoring 5f3104335 2026-10-09,
  stale since 702198999.
- Evidence: the PR repaired the table cell and left the prose byte-identical — a same-pass
  oversight; docs/reference is outside ci.yml validate_docs (:395).
- Refuted=false (NOT-REFUTED; verdict 7157_c6.md).
- Fix: re-derive the prose. Size S; docs.
- Owner: ruled 277: later (docs cleanup).

### Q-123 · low · feature-inventory F-104 :480 + F-129 :504 · #7157

- Wrong: F-104 and F-129 cite system.py:4936 for get_model_zoo_status (real def :4992; :4936
  = a continue); F-104's has_clip cite system.py:4839 is dead — has_clip lives at
  backend/models/event_audit.py:37 (`Mapped[bool] = mapped_column(Boolean, default=False,
nullable=False)`); :4839 is a blank inside get_model's docstring (:4831, GET
  /models/{model_name}).
- Evidence: the pin rows' main.py:1212 cites are TRUE (9fcb5f453 deleted 26 lines above
  preload and remapped the cite); F-104 = exactly two dead cites (system.py:4936, :4839) +
  two true (main.py:1212, ai_audit.py:477); F-129 = one dead (:4936) + one true (:1212);
  the ai_audit.py:447→:477 remap was NOT rot-repair — :447 was dead in every visible tree
  (true :460 at the boundary/merge-base), the remap tracked the PR's own +17 shift;
  "Ruling 250.3" does not exist (ruling-map.md:265 records ruling 250 only; UR-89
  non-blocking class); Side-B adjudication wins (disclosure ≠ repair: the PR rewrote 11
  rows F-026/F-061/F-062/F-104/F-106/F-107/F-108/F-125/F-129/F-164/F-294 as minus/plus
  pairs; the no-guess excuse collapses — the body printed the correct carrier
  backend/models/event_audit.py:37 and didn't apply it; the PR's own practice contradicts
  its carve-out: it grep-repaired backend-entry-points.md:829 :558/:576→:575/:593); the
  body's disclosure coords :291/:359 were true at drafting 62a2d7eea, stale +197/+129 at
  head; body 35,791 chars/35,792 bytes; PR diff instrument 4039c7047→b4164bb7f.
- Refuted=false (NOT-REFUTED; verdict 7157_c7.md).
- Fix: :4936→:4992 in F-104 AND F-129; :4839→backend/models/event_audit.py:37 in F-104.
  Size S; docs.
- Owner: ruled 277: later (docs cleanup; in the feature-inventory sweep cluster).

</details>

## Batch 3 — medium templates

### Q-093 · docs · medium · feature-inventory F-022 (5 cites) · #7103

- Wrong: the feature-inventory's F-022 row — the rate-limit store's contract record —
  carries five stale coordinate cites (api.ts:1045, :1197, :1060-1061, :2165; system.py:1626)
  after the rate-limit route moved to system.py:1637-1638 (Depends at :1639; the guard list
  at :1040-1041). 6b691302d's renumber (-8) was blind — wrong at its own tree; 834d51097 is
  the first breaker. The row's doctrine line says "re-traced, not re-numbered" (:88); the
  movers did the opposite. One defect, two carriers: #7077's Q-075 cites the same F-022 row —
  resolved together, one fix.
- Evidence: fix text — system.py route :1637-1638, Depends :1639, guard :1040-1041, the
  update call at merge :1205; movers exactly {834d51097, d6344e031, e2d65dda3, 516cffc98};
  rowCites gate existence-only (catches absence, not drift).
- Refuted=false (NOT-REFUTED; verdicts 7103_c0.md + 7077_c0.md).
- Fix: re-derive the five cites and re-anchor the row. Size M; docs.
- Owner: `[r277b]` — fix now (ruling 277): F-022's five citations re-derived against main's
  base, each cited line quoted from the PR's base. One-off UR-52 exception beside [r262];
  counts toward ruling 269's two. Q-075 resolves with it.

### Q-114 · backend · medium · backend/api/routes/system.py:4132-4135 · #7156

- Wrong: the comment "add_detection rewrites these through the set wrapper
  (batch_aggregator.py:641), which JSON-quotes them" is plural half-false — only
  last_activity goes through the wrapper (:641); started_at is written raw via
  _create_batch_metadata_atomic (batch_aggregator.py:427, `pipe.set(f"batch:{batch_id}:
started_at", str(current_time), ex=ttl)`). The witness test asserts the split (test :173,
  not :174: `not raw["started_at"].startswith('"')`) and "one call, two serializers" sits at
  :155-157, not :171-172. False the moment it landed — parent 7a2aa8ca8 already had the
  split. The PR body retracted the claim at 93976fd15 but the shipped comment kept it, and
  it is still on main today.
- Evidence: pin system.py:4132-4135 verbatim; batch_aggregator.py :427 and :641 verbatim;
  witness test :173; authoring f9a18d028.
- Refuted=false (NOT-REFUTED; verdict 7156_c1.md).
- Fix: reword to singular ("last_activity goes through the set wrapper and is JSON-quoted;
  started_at is written raw") and correct the internal cites. Size S; backend.
- Owner: `[r277a]` — fix now (ruling 277), after [r271b] #7302: the comment states the
  singular split (wrapper :641 / raw :427) and cites _coerce_scalar for both. Q-068 rides
  the same package.
- Note: the "(Fix-note typo guard: the test's variable is "starte_at".)" sentence removed
  per ruling 277 — the name names nothing in the tree (0 hits at the pin).

## Batch 3 — process notes

- Refutation-pass note (owner P2 item 2): one refuter returned NOT-REFUTED on a claim a
  one-line grep disproves — the lesson from Q-054's re-issue applies to this batch's intake:
  every refuter verdict was self-verified at the pin with the coordinator's own git commands
  (`git show 41bc0fce7:<path> | sed -n '<line>p'`) before entering the sheet, and every
  load-bearing coordinate checked out.
- Concurrency disclosures: the cap "at most two audit subagents at once" (docs.md:450) was
  exceeded three times: (a) 22:15Z — 3 auditors on #7145/#7156/#7157; (b) 02:15-02:44Z — up
  to 4 refuters, one slot lost (7157-C4 died pre-verdict, was re-dispatched, landed
  NOT-REFUTED); (c) 04:41-04:49Z — ~7.5-minute transient at 3 concurrent (no loss — all
  three verdicts landed).
- Shallow-graft hazard governed the whole batch: the repo is shallow at d6344e031
  (parents:[]) — full hashes and pairwise blob diffs throughout, never merge-base walks;
  r218 is hidden from plain walks (the 7145-C4 mover walk needed it).
- HOLD (owner continue 6275088190): no batch-4 sheet work and no new [r262] claims until the
  owner rules on batch 3 — LIFTED by ruling 277 (record 6291992942, 2026-10-20 13:28Z):
  batch 3 is ruled verified with the corrections above folded in.
