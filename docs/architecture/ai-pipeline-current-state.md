# AI pipeline: current state (2026-10-02)

Status: **measured against the working tree at `3054e312`**, whose code is identical to
`github/main` at `cfaee6b1` (`git diff HEAD github/main -- ai/ backend/ docker-compose.prod.yml`
returns only added test files). This page describes **what runs today**. It is not a redesign
proposal and it is not the research record.

Why this page exists: the shipped pipeline gets one current description, in this page, so the
running system is stated once instead of spread across operator pages. The decisions, the ordering
of the work and the protection mechanism live in the companion plan at
`docs/superpowers/plans/2026-10-02-vlm-bringup-and-residue-sweep.md`.

What is decided, measured, open and next for the stack, and the guardrails, live in
[the State of the stack](../vss-integration/README.md); this page does not restate them, and that
page does not restate what runs today.

Epistemic markers follow the repo convention from
`docs/plans/2026-09-28-r8-legacy-retirement-scope.md`: **[V]** verified by direct read in this
pass, file:line cited; **[A]** asserted from a source I did not re-measure.

## 0. Correct the framing before anything else

The retired engine **is** Nemotron. Nothing was migrated _to_ it. **[V]**

|                   | Retired by R8 (2026-09-29)                                                | Shipping today                                                                                        |
| ----------------- | ------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| Serving container | `ai-llm` (absent from `docker-compose.prod.yml` outright)                 | `ai-vlm` (`prod.yml:141`)                                                                             |
| Engine            | llama.cpp + Nemotron-3-Nano-30B-A3B Q4_K_M                                | llama.cpp `llama-server` + **Qwen3VL-8B**-Instruct-Q4_K_M + mmproj Q8_0                               |
| Analyzer          | `nemotron_analyzer.py` (deleted)                                          | `backend/services/vlm_analyzer.py`                                                                    |
| Selection         | `PIPELINE_MODE=legacy`                                                    | `PIPELINE_MODE=vlm` — **the only accepted value**; legacy hard-raises at boot (`config.py:1079-1083`) |
| Per-model zoo     | `ai/{florence,clip,enrichment,enrichment-light,nemotron}` (deleted trees) | gateway serves **only** `/yolo26` + `/enrich-lt`                                                      |

So "we should still have a specialist pipeline with a VLM" is satisfied by design: the VLM path is
not a survivor of the refactor, it is the **only** path. What was removed is the thing you are
worried about being left without.

## 1. The live path, hop by hop

```
camera / FTP / seed-events.py  ->  file drop under FOSCAM_BASE_PATH (host /export/foscam,
                                   mounted /cameras; prod.yml:466)
  -> FileWatcher (watchdog inotify, recursive)          file_watcher.py:379
     debounce 0.5s -> 2.0s size-stability wait -> media validation -> content-hash dedupe
  -> XADD detections:stream                            redis_streams.py:389
  -> DetectionQueueWorker (XREADGROUP, 2 workers)      pipeline_workers.py:222
  -> DetectorClient.detect_objects                     detector_client.py:993
     URL = {AI_GATEWAY_URL}/yolo26 when USE_AI_GATEWAY=true  (detector_client.py:283-287)
  -> POST ai-gateway:8090/yolo26/detect  -> Triton YOLO26 TensorRT   adapters/yolo26.py:332
  -> Detection rows -> BatchAggregator.add_detection   batch_aggregator.py:446
     closes on 90s window | 30s idle | 500 detections   (config.py:925,930,964)
  -> XADD analysis:stream                             batch_aggregator.py:948
  -> AnalysisQueueWorker (2 workers)                  pipeline_workers.py:765
  -> build_pipeline_analyzer()                        pipeline_factory.py:28   (no mode branch)
  -> VlmAnalyzer.analyze_batch                        vlm_analyzer.py:380
       |
       +-- select_key_frames(...)                     key_frame_selector.py:73   (1..4 stills)
       +-- collect_specialist_outputs(...)            vlm_analyzer.py:505 -> vlm_specialists.py:884
       |     faces       SCRFD-10G-KPS + w600k_r50, in-process, gallery lookup
       |     plates      FastALPR, in-process, loads on demand
       |     person_reid OSNet-AIN x1.0, in-process, gallery lookup
       |
       +-- vlm_client -> POST ai-vlm:8098/v1/chat/completions   vlm_client.py:85
       |     <=4 base64 images, prompt fitted to the served slot (:437-499)
       |
       +-- apply_verdict_invariants(verdict, SeverityService)   vlm_analyzer.py:255
       |     rejected -> clamp score to <= severity_low_max (29), clamp left VISIBLE in reasoning
       |     verdict=None -> verification_failed, score/level NULL, Event row STILL written
       |
       +-- session 2: INSERT events + event_verifications + event_detections   vlm_analyzer.py:573-633
       +-- SET batch_event:<batch_id> (idempotency, AFTER the write)          vlm_analyzer.py:635
       +-- broadcast LAST, best-effort (a failed broadcast never un-does the commit)
  -> WS /ws/events + GET /api/events
```

Shipped defaults all agree, which is the point of `test_gateway_model_set_compose.py`:
`PIPELINE_MODE=vlm`, `GATEWAY_MODEL_SET=vlm`, `GATEWAY_ENABLE_THREAT=false`,
`USE_AI_GATEWAY=true`, `BACKEND_MODEL_PRELOAD=false` (`.env.example:203-231`,
`prod.yml:392,388,484,489`).

Baseline for the guard tests covering this path, measured before any change:
**206 passed in 4.55s** (`.venv/bin/python -m pytest` over `test_vlm_specialists.py`,
`test_vlm_analyzer.py`, `test_config_pipeline_mode_hard_raise.py`,
`test_gateway_model_set_compose.py`, `test_ai_vlm_compose_service.py`,
`test_no_legacy_pipeline_branches.py`, `test_r8_s3_florence_provider_retirement.py`).

## 2. The four silent-failure surfaces

These are the ones that make a healthy pipeline and a stalled one look identical from the console.
Each is [V].

### 2.1 A text-only VLM passes every health check

`ai/vlm/Dockerfile:144` builds the projector argument conditionally:

```sh
if [ -n "${MMPROJ_PATH}" ]; then MM_ARGS="--mmproj ${MMPROJ_PATH}"; fi
```

An empty or absent `MMPROJ_PATH` starts `llama-server` **without** the projector. The container
then answers `200` on `/health`, so both health checks pass:

- compose healthcheck `prod.yml:243` — `curl -f http://localhost:8098/health`
- the Dockerfile's own `HEALTHCHECK` at `:139`

`ai/download_models.sh:493-497` says the weights are **not fetched** by the script and that "the
mmproj projector is required, without it the serve is text-only and every `vlm_assess` call
degrades silently". Compounding it, `backend`'s `depends_on` names `postgres`, `redis`,
`ai-gateway` and `go2rtc` — **not** `ai-vlm` (`prod.yml:639-651`), on purpose: `ai-vlm` failing
must never take the rest of the stack down, so degradation is left to the `vlm_analyzer` ladder
rather than a compose edge (`prod.yml:127-130`, the service's header comment).

**Signature to grep for:** a run of events with `risk_score`/`risk_level` NULL and
`verdict = 'verification_failed'`. That is the VLM unreachable or blind, not an empty camera.

### 2.2 `restart-all.sh` restarts the VLM without its profile — closed by UR-18

> **Closed (O1.3, UR-18).** `ai-vlm` now ships in the default compose set, so the profile-less
> AI-group call below starts it like any other service. What follows is the surface as measured
> 2026-10-02, when the service did sit behind a compose profile.

`ai-vlm` was the only shipped AI service behind a compose profile, so `up -d` without the profile
flag did not start it. The script knew this — `start_services` takes an optional profile argument
(`scripts/restart-all.sh:83-89`) and the monitoring group passes one (`:222`). The AI group did not:

```sh
AI_SERVICES="ai-gateway ai-vlm"                      # :39
start_services "$AI_SERVICES" "AI"                   # :220  <- no profile
start_services "$MONITORING_SERVICES" "Monitoring" "monitoring"   # :222  <- profile passed
```

`setup_lib/deploy_phases.py:72-76` records the retired trap in its own words ("podman-compose drops a
service whose profile is inactive before it resolves command-line targets") and names services
with no profile flag now. With `ai-vlm` in the default set, the AI group's profile-less
`start_services`/`stop_services` pair (`scripts/restart-all.sh:220`, `:242`) starts and stops it
with the rest — **the place that could silently drop the VLM and report success is gone.** (The
`monitoring` argument at `:222` names no profile any service declares; compose ignores a flag
nothing declares rather than rejecting it.)

### 2.3 The face and re-ID legs are residency-gated, and residency ships off

`osnet_loader.get_reid_handle()` (`:182-203`) and `face_recognizer_loader.get_face_leg_handles()`
(`:466-490`) are **membership reads that never trigger a load** — by design, mirroring each other.
The handle exists only if the boot preload sweep put it there, and that sweep is gated on
`settings.backend_model_preload` (`backend/main.py:1215`). Shipped default: **false**
(`.env.example:231`, `prod.yml:494`). `setup.py:461-464` auto-sets it **only** when detected VRAM
is >= 24 GB (inclusive).

So on a sub-24 GB host, or a host where the operator answered no, the `faces` and `person_reid`
lines read `unavailable` on **every event, forever**, and nothing fails. The plate leg is the
exception: `fast_alpr_loader.load_fast_alpr` loads on demand.

The degradation is honest, which is the good news and the reason this is a residency question
rather than a correctness bug. `_unavailable_line` (`vlm_specialists.py:105-114`) returns
`"unavailable: specialist did not run"`, increments `hsi_specialist_unavailable_total` with a
bounded code (`weights_absent`, `package_absent`, `space_mismatch`, …), logs with `exc_info`, and
the F11 ruling-3 doctrine keeps `not_identifiable` distinct from `unknown` so a degraded leg can
never masquerade as an empty result. The counter is the query that answers "has this ever run".

### 2.4 No event ever auto-creates an Alert

`[V]` Nothing on the live path calls `AlertRuleEngine.evaluate_event` or
`create_alerts_for_event`. Grepping non-test, non-`alert_engine.py` call sites returns exactly
one name, and it is an unrelated route function (`backend/api/routes/ai_audit.py:193`). The engine
is reachable only through `Depends(get_alert_rule_engine_dep)` at `backend/api/routes/alerts.py:434`
— the rule-test endpoint.

The gate logic itself is fully written and encodes the intended contract: newest-verification
`rejected` never pages (`alert_engine.py:465-470`), `TRUSTED` entity skips all alerts
(`:199-207`), `rule.risk_threshold` vs `event.risk_score` with a NULL score failing
(`:472-476`), `UNTRUSTED` escalating one band (`:78-83`), cooldown per
`{camera_id}:{rule_id}` at 300s default (`:1005-1037`). It runs only when someone calls it.

The one wired "immediate alert" hook is dead on arrival **[V]**:
`batch_aggregator.py:1389-1391` calls
`service.process_threat_detection(threat_detection=None, event=None)` and that method raises
`ValueError("threat_detection is required")` by design (`threat_monitor_service.py:203-207`),
into a broad catch that only logs. So the threat fast path bypasses the batch window and then
produces nothing.

`AlertDeduplicationService.create_alert_if_not_duplicate` (`alert_dedup.py:229`) has **zero**
non-test consumers. Repeat-suppression on the live path is only event idempotency
(`batch_event:<batch_id>` + the unique `events.batch_id`).

Alert rows are created via `POST /api/alert-service/alerts`, which bypasses rules by design
(`alert_service.py:126-148`); that route builds `AlertService(db)` with `emitter=None`, so even
the `alert.created` WS emission is skipped there. Outbound `ALERT_FIRED` webhooks do fire.

**Consequence for triage: diagnose from `events`, never from `alerts`.** A stalled pipeline and a
fully healthy one both produce zero notifications.

## 3. What the VLM verdict actually fills, and what nobody fills any more

Per event the live path writes **[V]** `risk_score`, `risk_level`, `summary`, `reasoning`,
`llm_prompt`, `reviewed=False`, plus the `event_verifications` row (`verdict`,
`scene_description`, `criteria`, `key_frame_detection_ids`, `engine`, `model_id`, `latency_ms`)
and `event_detections`. The API view is good: `GET /api/events` (with `?verdict=` as an `EXISTS`
on `event_verifications`) and `GET /api/events/{id}` carry the same `verification` object the WS
payload carries, both rendered by `api/schemas/event_verification.py`.

The enrichment era's `Event.entities`, `.flags`, `.confidence_factors`, `.recommended_action` and
`.object_types` have **no shipped writer**, yet `EventResponse` still exposes them (always
empty/None) and search/export still read `object_types`/`search_vector`. Permanently
NULL-shaped residue.

Severity bands ship as 0-29 / 30-59 / 60-84 / 85-100 (`config.py:2423-2436`; not set in
`.env.example` or compose) and are **runtime-mutable** via `api/routes/system.py:3483` and the
update route near `:3548`. `api/schemas/events.py:21-23` keeps a **second, hardcoded copy**
(`_DEFAULT_LOW_MAX=29`/`_MEDIUM_MAX=59`/`_HIGH_MAX=84`) for the REST-computed `risk_level`, which
silently disagrees with the DB-stored `risk_level` after any runtime threshold update.

## 4. The orphaned Triton specialists

`ai/gateway/main.py:273-277` mounts exactly two routers: `/yolo26` and `/enrich-lt`. The light
router serves two Triton models (`adapters/enrichment_light.py:6-7`): `/threat-detect` (TensorRT
`threat`) and `/person-reid` (ONNX Runtime `reid`).

**No backend module calls either for inference.** `[V]` Grepping `enrichment_light_url` outside
tests returns only its own `config.py` definition/validator and one consumer —
`api/routes/model_management.py:172`, which uses it as a **readiness probe target**, not an
inference client. The live re-ID leg is `osnet_loader` in-process.

Meanwhile `ai/gateway/residency.py:60-84` keeps `reid` in the shipped `vlm` set (plus `threat`
when `GATEWAY_ENABLE_THREAT=true`, which ships false), and `ai/triton/model_repository/` holds
exactly `{yolo26, reid, threat}`. So the shipped config **pays Triton residency for a model with
no inference consumer**, and a gate test reddens if the flag is flipped. Either residency drops
`reid` or a consumer returns — that is an owner decision, recorded in the plan, not a bug to fix
unilaterally.

Threat detection is off **by ruling, not by accident**: `SPECIALIST_KEYS` is
`{faces, plates, person_reid}` and the comment at `vlm_specialists.py:874-879` records the F12
reason — the threat card reports an identical 83.0% recall for every class on an unnamed dataset,
and published CCTV weapon AP50 is 57.4, collapsing to 3.7 across datasets. Weapon hints are
scheduled to return as a rev-7 YOLOE-26 feature gated on hand/arm overlap.

**One precision the record should keep:** `run_threat` is a **live parameter**
(`vlm_specialists.py:891,926-927`) that adds a fourth prompt key when true, not a deleted
function. `[V]` It has exactly one non-definition caller, in a test
(`test_vlm_specialists.py:661`). So `SPECIALIST_KEYS` is a **call-site default, not a structural
invariant** — the exclusion test observes only a default-false call and cannot catch a caller
flipping the flag.

## 5. Evaluation: today's harness cannot score a specialist change

The runnable chain is `synthbench export` / `replay` / `score` (`synthbench/cli.py:21-26,53-56`):
export writes `<category>/<set>/{expected_labels.json,still.jpg,still.json}`; replay imports into
`$SYNTHBENCH_ROOT/eval/<version>/eval.sqlite` and calls
`backend.evaluation.vlm_replay.run_replay` with **one** `VlmClient` per run against **one** served
endpoint; score emits `runs/scores/<score_id>/{results.jsonl,metrics.json,report.md,report.html}`.
Metrics are S2 (benign scored >= medium), S3 (incidents at/above declared floor), S5 refusals and
`uncertain` rate, from `backend/evaluation/s_metrics.py`, reported with n and a Wilson interval.

Published baseline — `docs/benchmarks/synthbench/p5a-2026-09-30.md`: qwen3-vl-8b **S3 36.5%
[30.7-42.8]** (n=241), **S2 6.7% [4.0-10.9]** (n=209) over 450 tierb-v0 items; the flagship at
S3 58.9% / S2 8.6%. **[A]** transcribed, not re-run — `/synthbench` does not exist in this
sandbox.

**The blocking limitation** [V]: replay reads each item's **stored** `specialist_outputs` as a
given (`vlm_analyzer.py:500-504` — "replay NEVER re-runs the specialists", F11 ruling 4) and the
tierb-v0 export declares no specialist context at all; the report's own Conditions line says "no
specialist context". So **no currently runnable harness can measure a specialist-prompt or
specialist-leg change.** The corpus gap is recorded: media-bearing sets and specialist-context sets
are disjoint, and the only set that ever joined them (38 items, ledger item 40) was built by hand
on the A5500, off-repo, and is not reproducible from the repo.

Two more limits worth stating plainly: CI scores nothing (`addopts` excludes `-m gpu` per
`pyproject.toml:584`, and the A5500 `gpu/rtx-a5500` job was **removed 2026-09-15** per
`.github/workflows/nightly.yml:12`), and the nightly prompt-evaluation workflow that scored the **retired
Nemotron harness in `--mock` mode** (green whether or not the shipped VLM worked) was **deleted
with that harness**. The F14
bars (`S2_MAX 5%`, `S3_MIN 90%`, `s_metrics.py:32-33`) are printed as "bars" and enforced by
nothing; the file says so.

## 6. `ai_contract` is a CI artifact, not a dispatch point

`backend/ai_contract` is a generated registry of **9 operations** (was ~37-38 pre-S3) plus a
provider-registration layer whose import re-verifies every callable against the availability
matrix and raises `ProviderContractError` on a hole. Only **two** ops bind to a live client method:
`yolo26_detect` -> `DetectorClient.detect_objects` and `vlm_assess` -> `VlmClient.assess`. The
other seven are the not-wired sentinel.

**No runtime backend module imports the package.** `[V]` `detector_client` and `vlm_client` dial
their URLs with plain httpx. The single runtime touchpoint is `vlm_client` reading the generated
`schemas/vlm_assess.response.json` as data. Two gates wrap it: `gen-ai-contract.py --check`
(drift; `ci.yml:1589`) and `check-ai-provider-parity.py --expect .github/ai-parity-baseline.json`
(`ci.yml:142`) — and the shipped baseline is **empty** (`[]`), while the checker header and the
`ci.yml` comment still advertise a 21-id D1-D6 golden set.

Most misleading for a deleting agent: `operations.py` rows for `llm_completion` /
`llm_chat_completion` declare `per_model_server: True` with evidence pointing at
`ai/nemotron/model_hf.py` and `backend/services/nemotron_analyzer.py` — **both deleted**. The rows
survive legitimately (llama.cpp re-home: `ai-vlm` serves `/completion`), but the provider's op-set
derivation greps the evidence **string**, so it passes on stale text. The generator's own header
(`gen-ai-contract.py:25-30`) names exactly this hazard as why `PHANTOM_OPS` was retired — the
doctrine was applied to Tier-A and not to `LLM_OPS`.

Also stale: `backend/ai_contract/AGENTS.md` still says "38 operations" and "45 generated JSON
schemas" (disk has 15), and `providers.py:27-29` calls the fake a non-existent spec when
`fake/app.py` exists at 169 lines.

## 7. Gates that lock the shape — and two that do not run

Branch protection requires exactly one context, `CI Gate (Required Checks)` (`strict=true`), and
`ci-gate`'s `needs` + `check_job` lines carry a red; that wiring is itself pinned by
`scripts/test_ci_job_graph.py`. Enforced invariants worth knowing before touching the path:

- no shipped file may AST-compare against `"legacy"` (`test_no_legacy_pipeline_branches.py`)
- `PIPELINE_MODE` and `GATEWAY_MODEL_SET` both hard-raise off `vlm`, and their compose and
  `.env.example` defaults are pinned to **agree** (`test_gateway_model_set_compose.py:75-93`)
- `GATEWAY_ENABLE_THREAT` is pinned to `${GATEWAY_ENABLE_THREAT:-false}` (`:96`)
- the Triton `model_repository` directory set must equal exactly `{yolo26, reid, threat}`
- `ai-llm` must **not** exist in `docker-compose.prod.yml`; `ai-llm-vllm` profiles stay exactly
  `[vllm]`; `backend.depends_on` names no `ai-llm*` (`test_ai_vlm_compose_service.py:327-363`)
- `VLM_MODEL_ID`/`VLM_MODEL_PATH`/`VLM_MMPROJ_PATH`/`MODEL_ALIAS` are the "one fact, five
  spellings" pin, shipped `Qwen3VL-8B-Instruct-Q4_K_M` (`:436,523-533`)
- `BACKEND_MODEL_PRELOAD` is pinned to `Settings.model_fields` — **changing that default is a
  gate edit**, not a config edit (`:402-409`)
- the contract registry equals the schemas/ artifact count, plus a `DELETED_REGISTRY_OPS`
  ratchet of 28 ids that stay absent

Two of the sharpest absence-pins in the repo are **not wired to any workflow** [V]:
`scripts/test_ai_surface_census.py` — which pins the surviving-loads set to exactly the three
lookup loaders, i.e. the guard against a specialist leg being quietly added or deleted — and
`ai/tests/test_module_hygiene.py` (the `ai-tests` job runs only `pytest ai/ --collect-only` and
`pytest ai/gateway`). Both are outside `testpaths` (`pyproject.toml:578`). This contradicts the
repo's own doctrine quoted at `ci.yml:200`: "a gate with no CI is a gate that rots".

And `scripts/validate_docs` — the tool that catches dead `source_refs` — runs in **no** workflow
either (`grep -rn validate_docs .github/workflows/` returns nothing). It is what found the 3 dead
citations in `ai-pipeline.md`.

## 8. What monitoring can and cannot see today

The live blackbox job (`monitoring/prometheus.yml`) probes exactly the four
endpoints the shipped stack answers:

| target                                    | line | note                                 |
| ----------------------------------------- | ---- | ------------------------------------ |
| `http://ai-vlm:8098/health`               | :412 | cannot distinguish multimodal — §2.1 |
| `http://ai-gateway:8090/health`           | :418 |                                      |
| `http://ai-gateway:8090/yolo26/health`    | :424 |                                      |
| `http://ai-gateway:8090/enrich-lt/health` | :430 | readiness only — §4                  |

The owner-visible degradation signal today is therefore weak on purpose: the
only strong one is `verification_failed` with NULL score, and **specialist
degradation never triggers it** — that leg degrades into prompt text by design.
`hsi_specialist_unavailable_total` is the metric for it and nothing in
`monitoring/` surfaces it in a dashboard.

## 9. Where this is NOT settled

- **Runtime state is unmeasured from here.** This sandbox has no GPU (`nvidia-smi` absent) and no
  `/export/ai_models`, so I can read what _ships_, not what is _loaded_. §2.1-2.3 are one
  container-status call and one event query away from being settled on the real box.
- **`deploy_phases.py:649` runs `cd /app/gateway/export && bash export_all.sh` during deploy**, and
  `export_all.sh:113-135` still exports clip/clip_text/fashion_clip/pose engines for Triton models
  pruned in S3, into a cache dir the repository (`{yolo26,reid,threat}`) never loads. Whether that
  currently fails, warns, or wastes GPU-minutes at deploy is **not** established — it gates the
  safety of the export-directory sweep (§plan S3).
- **A latent boot failure, confirmed unreachable.** `backend/evaluation/__init__.py:39-46`
  re-exports `ab_experiment_runner` **eagerly**, which does `from scipy import stats`, and
  `s_metrics.py:11-13` documents scipy as transitive-and-undeclared. I grepped the reachability
  the finding needed: nothing under `backend/` outside `backend/evaluation/` and tests imports
  `backend.evaluation`, so the backend does not fail at boot. Unreachable, but load-bearing if
  anyone wires it up.
