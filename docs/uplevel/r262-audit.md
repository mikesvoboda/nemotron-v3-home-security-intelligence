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

(batch 1 pending — filled when the census has run)

## Batches

Production first, then test, then tooling; within a class in PR-number order. Batch 1 is the
first ten production PRs; later batches are about fifteen PRs, one comment each. Each batch
records how many items a fresh unnamed refutation subagent (ruling 232) dropped.

| Batch | PRs | Items | Refuted | Comment |
| ----- | --- | ----- | ------- | ------- |
| 1 | 6862, 6868, 6869, 6880, 6886, 6907, 6909, 6913, 6922, 6925 | 15 | 0 so far (q001–q005 survived; q006, q007 running; Q-008–Q-015 pending refuters) | batch-1 comment on #7265 |

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
| #6922 | production | 8 items (Q-008–Q-015, all claim/low) |
| #6925 | production | no items |

## Items

Batch 1. Every item below was verified at the pinned SHA before entering the sheet; the
refutation pass (ruling 232) runs next and the batch records how many it dropped.

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
- Refutation: pending.

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
- Refutation: pending.

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
- Refutation: pending.

### Q-012 · claim · low · frontend/src/__tests__/api-endpoint-contract.test.ts:241 · #6922
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
- Fix: correct :241-242 to "23 entries over 23 distinct positions", or make the count a
  computed interpolation from audit.scan.dynamic so it cannot drift again.
  Size S; owner: frontend.
- Owner: (pending)
- Refutation: pending.

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
- Refutation: pending.

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
- Refutation: pending.

### Q-015 · claim · low · frontend/src/hooks/webSocketManager.auth.test.ts:10 · #6922
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
- Refutation: pending.

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
