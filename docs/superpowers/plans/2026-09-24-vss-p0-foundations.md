# Phase P0 — Foundations (VSS gaming-GPU workstream)

> **For agentic workers:** execute task-by-task, checkbox syntax; every step closes on an executed command + result in the ledger, never on written code. Milestone review is the built-in code review. Ledger rows for this phase are P0.x in `docs/plans/2026-09-23-vss-gaming-gpu-ledger.md`.

**Goal:** land spec §"Phase 0: Foundations" — the control freeze (0.1), the A5500 single-GPU bring-up (0.2, owner-run), NULL-safe consumers before any NULL score exists (0.25), constrained verdict + fail-closed §6 semantics on the LIVE legacy path (0.3, F4-approved), `event_verifications` + the `verification` field (0.4), and the labeling/import loop (0.5) — closing on **M0: A5500 healthy on one GPU, eval store frozen, S5 holds on the legacy path** (spec §8:397).

**Spec/authority:** `docs/superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md` (rev 4) — §6 (semantics/failure ladder), §4 (data model), §5 (eval items), §8 Phase 0 + A5500 checklist. G0 ledger rows E1–E13, S-1…S-5, F1–F8 are the environment-of-record; the G0 close row is the "done before this" evidence.

**Machine split (E10, measured):** repo code + all test tiers run in this sandbox (16 cores, test Postgres:5433/Redis:6380 via `docker compose -f docker-compose.test.yml up -d` — **bring it up + health-check in the same session or don't claim the tier ran**, E11 rule). GPU serving goes through `agent-gpu`. **The home machine (VSS production, feedback UI, retention, the 30B control) is a different box this sandbox cannot reach** — tasks touching it are owner-run with repo-side code proven here; each such row says which machine produced the evidence. The A5500 is the S1/S4 gate hardware and arrives through 0.2/owner; nothing here claims S1.

**Tech stack:** unchanged from G0 (uv/Python venv, FastAPI/SQLAlchemy `create_all`-only schema, React frontend, llama.cpp serving for probe evidence, `ai-vlm:sm103` + Qwen3-VL-4B for probe re-runs).

## Sequencing (binding)

1. **0.1-before-0.2** (spec:376): the control timestamp must precede the Nano-4B placeholder serving new events, or post-switch verdicts masquerade as control. 0.1's _code_ (freeze tool) can land any time; its _execution_ gates 0.2's execution.
2. **0.25-before-0.3** (spec:378): NULL-safety lands before anything can emit NULL.
3. 0.3 → 0.4: the `verification` field carries what 0.3 emits.
4. 0.5 runs any time after 0.1 (labels live inside a 30-day retention window — start early).
5. **Task 0 is a G0 tail, not P0 scope** — the owner-ruled media replacement (F5, "tonight") — but it re-freezes G0.4 items, so P0's eval-store claims quote its outcome.

## Global constraints

- GPU only through `agent-gpu`; honest `--vram`; `agent-gpu rm` when done. `--wait` before `--`.
- Real-camera imagery/labels/snapshots never enter git (D10); the eval store stays off-repo and is wiped at teardown. Aggregate metrics only in docs.
- Legacy path byte-identical EXCEPT the approved 0.25/0.3 diffs (F4 approval is on record — the approval is for the _semantics change_; every line still gets a test). R8: nothing retired, no deletions.
- TDD: failing test first, per site. Gates: `uv run pytest backend/tests/unit/ -n auto`; contracts `-n0 --timeout=30`, never xfail/skip in `contracts/ai_providers`; integration requires the same-session compose-up; `cd frontend && npm ci && npm run typecheck` when frontend changes. `scripts/gen-ai-contract.py --check` if `ai_contract` touched (0.4's Event API field may not touch it — verify, don't assume).
- Doc-vs-repo conflicts → ledger row or dated errata, never a silent spec edit; keep [V]/[C]/[E]/[?]/[O]/[A] markers; run-count claims are [V] only with a same-session run (G0-close lesson: the test DB is ephemeral).
- Every commit: manual pre-commit pass + conventional-pre-commit msg check + `Co-Authored-By` trailer. No pushes/PRs (stop-and-ask; F7 records why push is moot).
- STOP AND ASK unchanged, plus: any 0.25 triage call that would change a live behavior beyond NULL-safety, and any surprise in the events schema NULLability (first step of task 2 checks it — if `events.risk_score` turns out NOT NULL, stop: 0.3's core premise breaks).

## Known environment facts carried from G0 (all [V] in ledger)

- `requires_ack` (`event_broadcaster.py:326-333`) reads `data.get("risk_score", 0)` — a present-but-NULL key defeats the default and `None >= 80` raises TypeError. Baseline behavior pinned 2026-09-24 by reading the function.
- `notification_filter` (`notification_filter.py:55,66`) calls `self._risk_score_to_level(risk_score)` then `risk_score < camera_setting.risk_threshold` — both raise on NULL. §6: the detector-only rule must branch **before** the threshold comparison.
- Default-score sites in `nemotron_analyzer.py` re-counted at plan time: `:2837, :2853, :2884-2885, :2965, :3350, :3365, :3391, :3459, :4392` (spec's fact table says `:4392`/`:2884-2885` — still those lines, plus the `or 50` enqueue sites 2965/3459 the table omits) **[V 2026-09-24]**. nvext payload at `:593`, probe `:434-483`, settings `:382-385`.
- Counting surface for the 0.25 audit: **54 live-path comparison sites + 4 arithmetic sites = 58** (ledger counting-erratum, recipe pinned `[*/+-]`); spec's 61 superseded by errata N1 (written, not queued).
- Enforcement at the serving pin is empirical: native `json_schema` **ENFORCED** (S-1 arm B2, S-2 with images at b7972 and b11090); `nvext` **silently IGNORED** (S-1 arm B1) — this is why 0.3 is a payload switch plus a probe, and why the probe must be runtime, not static.
- Serve recipe + libgomp mount + models perms: G0 rows G0.2/F1. Test-DB creds persist in the sandbox env (E11).

## File structure

| File                                                           | Fate              | Responsibility                                                                                                                     |
| -------------------------------------------------------------- | ----------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `backend/evaluation/control_freeze.py`                         | new (P0.1)        | pre-switch event → eval item: copy images into store, snapshot AssessInput, recorded verdict as control                            |
| `backend/api/schemas/websocket.py`                             | edit (P0.25)      | `WebSocketEventData.risk_score`/`risk_level` → Optional (schema:252-253 today required)                                            |
| `backend/services/event_broadcaster.py`                        | edit (P0.25)      | `requires_ack` NULL-safe: None ⇒ no ack (spec §6 step 3)                                                                           |
| `backend/services/notification_filter.py`                      | edit (P0.25)      | NULL-safe level + detector-only branch BEFORE threshold comparison (spec §6, :185 of §4 table)                                     |
| `backend/services/nemotron_analyzer.py`                        | edit (P0.3)       | `json_schema` payload replaces nvext; endpoint enforcement probe; every default-50 site → fail-closed NULL + `verification_failed` |
| `backend/models/event_verification.py` (+ `create_all` wiring) | new (P0.4)        | `event_verifications` table (event_id FK, verdict enum, criteria/key_frame JSONB, engine, model_id, latency_ms)                    |
| Event REST + WS payload                                        | edit (P0.4)       | `verification` object present on verified events; frontend types regenerate                                                        |
| frontend score rendering + badges                              | edit (P0.25/P0.4) | NULL-safe score display; "unverified" badge is §4/1.6 — 0.25 only needs no-crash/no-lie                                            |
| `backend/evaluation/label_import.py`                           | new (P0.5)        | `EventFeedback` → eval items (§5 mapping table), `source_event_id` provenance, expected_severity                                   |
| `scripts/vlm_probes/enforcement.py`                            | new (P0.3)        | the S-1/S-2 nonce-const probe promoted from research script to runtime check (once per endpoint)                                   |
| probe reports → `$AGENT_GPU_DIR/out/probes/`                   | off-repo          | aggregate verdicts into ledger rows only                                                                                           |

---

### Task 0: G0 tail — owner media replacement (F5 ruling "tonight", owner-gated)

- [ ] When replacement incident media lands: re-run `load_stock_items` against the new corpus (D10 guard already refuses repo/capture-root paths — its behavior on this is the test), re-freeze the 13 stock items, re-run `s3_salience_stock.py`. Bar: incident-half confirmed-rates stop being 1/48 and the ledger S-3 row gets its dated amendment. Owner-ruling evidence (arrival time, what replaced what) goes in the ledger F5 row as [O].
- [ ] If media lands structurally different (new scenario names): loader/mapping fix is TDD here; S-3's per-scenario table is the regression check.

### Task 1: P0.1 control freeze — code here, execution owner-run

- [ ] Read spec §5 item anatomy; verify against `backend/models/` what a pre-switch event actually carries (`Detection.file_path`/`thumbnail_path`, `LLMInteraction` for recorded verdicts) — [V] each.
- [ ] TDD: `control_freeze.py` — given a production-DB fixture (sqlite or the test PG with rows staged by fixture), freeze = copy images INTO the eval store, snapshot `AssessInput`, recorded verdict as control, `source_event_id` provenance-only. D10 guard applies to writes (store path is a required argument). Test on fabricated rows; no real imagery in repo tests.
- [ ] Freeze manifest: one JSON row per item — kind (historical-pre-switch), label source, control source. This is what "frozen" means for M0.
- [ ] **Owner-run on the home box:** record the control timestamp FIRST (ledger [O] row), then run the freeze tool over pre-switch events. Row closes only when that execution + item counts land; until then P0.1 = code-DONE/execution-PENDING, and 0.2 must not serve new events from the placeholder.

### Task 2: P0.25 null-safety — every live consumer before any NULL exists

- [ ] **Premise check first:** `events.risk_score`/`risk_level` column NULLability in `backend/models/event.py` + the REST schema's existing NULL allowance (spec §4 asserts "REST already allows NULL"). If the column is NOT NULL, STOP AND ASK — 0.3's premise breaks.
- [ ] Triage the 58-site ledger surface into live-path / dead / comment (ledger P0.25 row carries the table; only live-path gets tests). Recipe A + `[*/+-]`, tests excluded.
- [ ] TDD per named site, red first, each with a NULL-input test:
  - `WebSocketEventData` — `risk_score=None, risk_level=None` validates (was: required);
  - `requires_ack` — `{"risk_score": None}` ⇒ False (today: TypeError via `.get` default defeated by present-None key) and scored ≥ 80 keeps ack;
  - `notification_filter` — None level-mapping + threshold both survived; detector-only branch placed before the threshold comparison (behavior: NULL + security class ≥ `detection_confidence_threshold` (`config.py:1788`) ⇒ notify; NULL + below ⇒ suppress; **never** a crash and never a silent pass).
  - the 4 arithmetic sites (`analytics.py:418`, `experiment_result.py:117`, `calibration_service.py:407`, `pipeline_quality_audit_service.py:314`) — decide per site: guard (NULL excluded from aggregate/abs-diff) with a test each.
- [ ] Frontend: find score rendering of `risk_score` (grep the WS/Event types), make it NULL-safe; `npm run typecheck` + any touched component tests green.
- [ ] Full gates: unit `-n auto`, contracts tier, integration (same-session compose-up). Legacy byte-identical diff = the approved set + nothing else: `git diff --stat` into the ledger row.

### Task 3: P0.3 constrained verdict on the legacy path (F4-approved semantics)

- [ ] `scripts/vlm_probes/enforcement.py`: promote the S-1 probe (nonce-required-const schema, content-only gate, `/props build_info` pin check) to a runtime check that `nemotron_analyzer` runs once per endpoint at startup; a NOT-ENFORCED result must fail closed (no silent prose mode).
- [ ] Payload switch: `response_format={"type":"json_schema",...}` derived from the same schema the parser expects (single source, spec §3 drift doctrine) replacing `nvext.guided_json` (`:593`, `:1033-1049`); settings/probe plumbing at `:382-385`/`:434-483` retuned or bypassed (R8: keep code paths, add the new default; a settings flip keeps the old route until R8).
- [ ] Fail-closed: every default-50 site (`:2837, :2853, :2884-2885, :2965, :3350, :3365, :3391, :3459, :4392` — ledger carries the [V] line list) becomes `verification_failed` + `risk_score`/`risk_level` NULL, notification via the 0.25 detector-only path. TDD: unparseable response ⇒ NULL-score event exists, notification rule evaluated, no 50/medium anywhere, S5 language holds (unparseable never surfaces as a score).
- [ ] Runtime probe evidence [V]: serve with `agent-gpu` (Qwen3-VL-4B on `ai-vlm:sm103`, or the endpoint the legacy path will actually point at on the home box), run the promoted probe, ledger ENFORCED verdict + build_info. `agent-gpu rm` after. **The home-box 30B/NIM endpoint probe is owner-run (0.2 stack); sandbox evidence covers the mechanism, the home row covers the actual endpoint.**
- [ ] Unit + contracts green; integration re-run with the compose-up in-session.

### Task 4: P0.4 `event_verifications` + `verification` field

- [ ] TDD: model + `create_all` creates the table on an existing DB (spec §4: create_all creates new tables, never alters — test on a staged existing schema). Columns: event_id FK, verdict ∈ {confirmed, rejected, uncertain, verification_failed}, scene_description, criteria JSONB, key_frame_detection_ids JSONB, engine, model_id, latency_ms, created_at.
- [ ] Retention path: verify `cleanup_service` cascade behavior for the new table against `:294` hard-delete (an event delete must not orphan-500; decide cascade vs. FK-less provenance row, ledger the call).
- [ ] Event REST + WS payload gain `verification` (present when a row exists; legacy events: absent, per spec "Legacy events have no verification row"). Frontend types regenerate; typecheck gate. `gen-ai-contract.py --check` if anything touched `ai_contract` (expect: it does not — this is VSS-internal API, not a provider op; ledger the check either way).
- [ ] 0.3's fail-closed path writes the verification row (`verification_failed`, engine/model/latency filled) — wire it and pin with an integration test.

### Task 5: P0.5 labels + imports

- [ ] TDD `label_import.py`: `EventFeedback` mapping per §5 (`false_positive`→benign; `missed_threat` or `accurate`-on-high→incident + `expected_severity`), keyed by `source_event_id`; unlabeled stay excluded from S2/S3.
- [ ] Synthetic incidents: import path for the (post-Task-0) media-bearing scenarios; control = offline-30B-replay placeholder field (the replay harness itself is Phase 2's 2.1 — do NOT build it here).
- [ ] **Owner-run:** label ≥100 benign / ≥20 incidents through the feedback UI, each within its 30-day window (spec §5:50-item coarseness argument is why 100 is a floor, not a goal). Ledger [O] row with counts; import run closes the repo half.
- [ ] Size check lands as a test: import refuses to call a <100-benign or <20-incident set "M0-complete" — bar enforced in code, not vibes.

### Task 6: P0.2 A5500 bring-up (owner-run; repo-side prep only)

- [ ] Repo-side prep review (here): `.env.example` SINGLE-GPU notes vs `GPU_*=0`, `CUDA_ARCHITECTURES=86` check-before-build, `LLM_MODEL_PATH` → Nemotron-3-Nano-4B Q4_K_M + the ai-llm volume-mount line that targets the 30B dir, TMPDIR/pycache traps from the spec checklist — every claim [V] against the current tree (the spec's anchors drift; re-verify each line-number claim first).
- [ ] Hand the owner a dated, copied checklist (spec §"A5500 bring-up") with the [V] amendments from the prep review. Execution + `/platform-healthcheck` result + root AGENTS.md infra checklist completion = owner ledger rows. 30B GGUF stays on disk (control for replay).
- [ ] **Ordering guard:** does not execute until Task 1's control timestamp is recorded (sequencing rule 1).

### Task 7: M0 exit + close

- [ ] Ledger P0 rows: each closed with command+result+commit and the machine that produced it; owner-run rows carry [O], sandbox rows [V]. No unobserved passes anywhere.
- [ ] M0 assertion in three evidence pieces: A5500 healthy (owner row, healthcheck + infra checklist), eval store frozen (Task 1/5 manifest + counts), **S5 holds on the legacy path** (0.3 test suite + first live observation: zero unparseable-as-scored, failures visible as `verification_failed` on dashboard/notification path).
- [ ] Built-in code review across the diff; milestone report (proven / failed & why / next = Phase 1 planning only / decisions owed).

## Definition of done

0.25 green with the 58-site triage table ledgered and every live-path NULL test committed; 0.3 on the legacy path with runtime ENFORCED probe evidence at both the sandbox mechanism level and the home endpoint (owner row); `event_verifications` + `verification` shipped with retention behavior decided and tested; label import with the 100/20 bar in code; control freeze executed on the home box BEFORE any placeholder-served event; A5500 bring-up closed by the owner; M0 closed with its three evidence pieces. Legacy diff = approved 0.25/0.3 only; nothing pushed.

## Out of scope

The replay harness and offline-30B control replay (2.1); bake-off (2.2); any Brev spend (2.3, stop-and-ask); `VlmVerdict`/`VLM_OPS`/FakeProvider contract (1.1); `ai-vlm` compose wiring (1.2); failure ladder beyond the legacy-path bits 0.3 needs, wake-on-open, degradation wiring (1.3); `PIPELINE_MODE` (1.5); full §4 frontend badges/filters (1.6 — 0.25 only requires no-crash/no-lie on NULL); R8 deletions; RT-VLM (Phase 4).
