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

| Batch | PRs | Items | Refuted | Comment |
| ----- | --- | ----- | ------- | ------- |
| 1 | 6862, 6868, 6869, 6880, 6886, 6907, 6909, 6913, 6922, 6925 | 12 (+ owner-seeded Q-000, outside the census window; see its section) (2 re-attributed by mover-owns: Q-012 → #7230 batch 4; Q-014 + Q-015 → #6936 batch 2 — 3 items moved off this batch, see below) | 0 (16/16 survived incl. Q-000) | batch-1 comment on #7265 |

## Batch 1 — per-PR verdicts

| PR | Class | Verdict |
| -- | ----- | ------- |
| #6862 | production | 2 items (Q-002, Q-005); 5 more stale cites first-moved by #7114, recorded on its batch; retirement-gate timeout = sandbox environment, no item |
| #6868 | production | 2 items (Q-003, Q-006 — Q-006 mover-owns) |
| #6869 | production | no items |
| #6880 | production | no items |
| #6886 | production | 1 item (Q-004) |
| #6907 | production | no items (docstring cite drift attaches to #7114's batch) |
| #6909 | production | 1 item (Q-007) |
| #6913 | production | 1 item (Q-001 — pre-existing bug on a kept file) |
| #6922 | production | 5 items kept here (Q-008, Q-009, Q-010, Q-011, Q-013, all claim/low) + 3 found here but re-attributed by mover-owns: Q-012 → #7230 (batch 4), Q-014 + Q-015 → #6936 (batch 2) |
| #6925 | production | no items |

## Items

Batch 1. Every item below was verified at the pinned SHA before entering the sheet; the
refutation pass (ruling 232) runs next and the batch records how many it dropped.

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
- Owner: (pending)
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
- Owner: (pending)

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
- Owner: (pending)

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
- Owner: (pending)

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
- Owner: (pending)

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
- Owner: (pending)
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
- Owner: (pending)
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
- Owner: (pending)
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
- Owner: (pending)
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
- Owner: (pending)
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
- Owner: (pending)
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
- Owner: (pending)
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

### Q-012 · claim · low · frontend/src/__tests__/api-endpoint-contract.test.ts:241 · re-attributed #6922 → **#7230 (batch 4)**
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
- Owner: (pending)
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
