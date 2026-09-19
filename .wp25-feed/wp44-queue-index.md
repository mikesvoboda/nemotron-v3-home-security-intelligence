# WP4.4 verification queue — triage dossiers, ordered

Source: read-only survivor triage during run5 (baseline in progress, 2026-09-17).
Each dossier = `/tmp/wp25/wp44-triage/<module>.md`: cluster table (TEST-GAP /
EQUIVALENT / LOW-VALUE with example mutant keys) + drafted pytest tests marked
UNVERIFIED. Verification lane (serial, after run5 exits): for each draft —
red on the mutant diff → green on original → commit into that WP's tests.
EQUIVALENT/LOW-VALUE cluster notes are the no-deletion-without-record receipts.

Aggregate at 122 modules / 17719 survivors: TEST-GAP 10942 survivors (62%),
EQUIVALENT 4041 (23%), LOW-VALUE 2681 (15%); 796 drafted tests.
landed back at 64/22/14 — the same triple as the earliest waves; the
aggregate oscillates inside classifier noise 64-66 and only PER-MODULE
shape carries signal.) (orphan_cleanup folded at its 170-snapshot; live meta already 174 with checked count
frozen at 371 — re-tallied from the FINAL score JSON, per the context_enricher precedent.) (Bucket
correction folded in: the wave-34 line had undercounted EQUIVALENT by 26 and
LOW-VALUE by 12 — ai_audit's 26 EQ / context_enricher's 12 LOW dropped in
the fold addition; buckets now sum 13592 vs 13597 = the standing +5.) (Bucket sums
carry a ±2 against the survivor denominator — three early-wave dossiers
(onvif, household_matcher, nemotron_latency hand-tallied 1–2 off; mqtt_publisher
3 off — the delta set re-verified per fold, never re-typed.)
Waves 8-9 (migration-day, 17:00-17:30 UTC): gpu_monitor 150/194 gap, zone_anomaly
132/137 (96%!), unified_embedding 95/125, nemotron_analyzer 80/125,
insight_generator 79/135, pipeline_quality_audit 67/111; wave 10:
auto_enrollment_service 121/134 (90%); wave 11: track_service 98/152,
gpu_config 90/140, detector_client 74/167, package_tracking 57/116,
system_broadcaster 50/115, event_broadcaster 13/104 — gap share dips to 66%
BECAUSE of broadcaster/telemetry shape (event_broadcaster = 88% noise: log
text + OTel attrs, near-zero behavior under test), not because the
classifier softened. The noise-shape list is itself a WP4.4 deliverable:
those survivors are the suppress-with-record pile.; the classifier is measuring module shape, not luck.
The noise share tracks module SHAPE, not luck: zone_comparison_service/prompt_service
= 97-98% TEST-GAP (pure logic, barely asserted), nemotron_latency_optimizer = 71%
EQUIVALENT (log-heavy singleton whose config kwargs equal their dataclass
defaults), household_matcher = 89% EQUIVALENT+LOW-VALUE (already well-tested —
its survivors are mostly log text and provable no-ops), calibration_service =
68% EQUIVALENT (wave 12: 47 log-call-only + 21 mutants absorbed by a redundant
clamp+cascade chain that re-derives the same (L,M,H) for every input, plus a
provably dead `new_low < 0` branch — a code-SIMPLIFICATION note for the module
owner, pattern-8 sweep material, not a test gap).

## Verification order (TEST-GAP survivors desc — biggest kill per unit of work)

| Gap surv | Surv | TEST-GAP% | Dossier                          | Drafted |
| -------: | ---: | --------: | -------------------------------- | ------: |
|      650 |  696 |    93% | `container_discovery`            |      5 |
|      209 |  210 |   100% | `llm_reasoning`                  |      6 |
|      203 |  271 |    75% | `nemotron_streaming`             |      6 |
|      183 |  283 |    65% | `scene_ocr_service`              |      6 |
|      182 |  244 |    75% | `threat_monitor_service`         |      6 |
|      167 |  282 |    59% | `pipeline_workers`               |      6 |
|      166 |  187 |    89% | `system`                         |      8 |
|      160 |  218 |    73% | `prompts`                        |      6 |
|      152 |  218 |    69% | `audit_logger`                   |      3 |
|      150 |  194 |    77% | `gpu_monitor`                    |      6 |
|      144 |  162 |    88% | `enrichment_pipeline`            |      6 |
|      144 |  185 |    78% | `segformer_loader`               |     10 |
|      138 |  142 |    97% | `prompt_service`                 |      6 |
|      138 |  158 |    87% | `unique_counter_service`         |      6 |
|      137 |  205 |    66% | `cost_tracker`                   |      8 |
|      135 |  180 |    75% | `export_service`                 |      6 |
|      133 |  158 |    84% | `webhook_service`                |     11 |
|      132 |  137 |    96% | `zone_anomaly_service`           |      5 |
|      130 |  158 |    82% | `enrichment_client`              |     10 |
|      130 |  211 |    62% | `stream_manager`                 |      6 |
|      129 |  184 |    70% | `redis_streams`                  |      6 |
|      128 |  135 |    94% | `vision_extractor`               |      6 |
|      121 |  134 |    90% | `auto_enrollment_service`        |     12 |
|      119 |  147 |    81% | `bulk_detection_service`         |      6 |
|      117 |  140 |    84% | `alert_engine`                   |      6 |
|      111 |  117 |    95% | `compose_parser`                 |      7 |
|      110 |  155 |    71% | `vitpose_loader`                 |      6 |
|      109 |  111 |    98% | `zone_comparison_service`        |      7 |
|      109 |  128 |    85% | `prompt_version_service`         |      5 |
|      106 |  134 |    79% | `context_enricher`               |      6 |
|      106 |  167 |    63% | `depth_anything_loader`          |      7 |
|      105 |  117 |    89% | `baseline`                       |      6 |
|      105 |  128 |    82% | `florence_extractor`             |      8 |
|      100 |  161 |    62% | `background_evaluator`           |     11 |
|      100 |  208 |    48% | `florence_client`                |      6 |
|       99 |  113 |    87% | `trajectory_analyzer`            |      8 |
|       98 |  152 |    64% | `track_service`                  |      5 |
|       98 |  176 |    55% | `job_service`                    |      7 |
|       97 |  122 |    80% | `read_through_cache`             |      6 |
|       97 |  152 |    64% | `weather_loader`                 |      7 |
|       97 |  177 |    55% | `clip_generator`                 |      6 |
|       95 |  105 |    90% | `pose_analysis_service`          |      7 |
|       95 |  125 |    76% | `unified_embedding_service`      |      8 |
|       95 |  147 |    64% | `partition_manager`              |      6 |
|       93 |  104 |    89% | `prompt_storage`                 |     13 |
|       93 |  113 |    82% | `redis_memory_service`           |      5 |
|       92 |  114 |    81% | `bbox_validation`                |      5 |
|       91 |  111 |    82% | `health_ai_services`             |      7 |
|       90 |  108 |    83% | `redis_json`                     |      7 |
|       90 |  110 |    82% | `monitoring_stack_validator`     |      6 |
|       90 |  140 |    64% | `gpu_config_service`             |      6 |
|       89 |  101 |    88% | `scene_baseline`                 |      6 |
|       89 |  131 |    68% | `summary_generator`              |      5 |
|       88 |  136 |    65% | `osnet_loader`                   |      6 |
|       87 |  128 |    68% | `threat_detection_loader`        |      6 |
|       86 |  112 |    77% | `scenario_classifier`            |      6 |
|       81 |  111 |    73% | `gpu_config`                     |      6 |
|       81 |  127 |    63% | `pg_notify_listener`             |      6 |
|       80 |  121 |    66% | `job_search_service`             |      5 |
|       80 |  125 |    64% | `nemotron_analyzer`              |      6 |
|       79 |  106 |    74% | `onvif_service`                  |      5 |
|       79 |  118 |    67% | `thumbnail_generator`            |      7 |
|       79 |  135 |    59% | `insight_generator`              |      7 |
|       78 |  107 |    73% | `debug`                          |      5 |
|       78 |  112 |    70% | `batch_coalescer`                |      6 |
|       78 |  185 |    42% | `model_zoo`                      |     13 |
|       77 |  116 |    66% | `vehicle_classifier_loader`      |      6 |
|       77 |  141 |    55% | `notification`                   |      6 |
|       77 |  143 |    54% | `health_monitor`                 |      6 |
|       74 |  167 |    44% | `detector_client`                |      7 |
|       74 |  203 |    36% | `batch_aggregator`               |      6 |
|       73 |  101 |    72% | `websocket_emitter`              |      6 |
|       73 |  190 |    38% | `worker_supervisor`              |      6 |
|       71 |  108 |    66% | `transcoding_service`            |      6 |
|       71 |  139 |    51% | `vehicle_damage_loader`          |      7 |
|       71 |  152 |    47% | `transcoding`                    |      6 |
|       70 |  107 |    65% | `performance_collector`          |      6 |
|       70 |  232 |    30% | `mqtt_client`                    |      7 |
|       69 |  100 |    69% | `cache_warming`                  |      7 |
|       69 |  220 |    31% | `clip_client`                    |      6 |
|       68 |  149 |    46% | `restore_service`                |      6 |
|       68 |  170 |    40% | `orphan_cleanup_service`         |     10 |
|       67 |  109 |    61% | `search`                         |      6 |
|       67 |  111 |    60% | `pipeline_quality_audit_service` |      6 |
|       66 |  121 |    54% | `job_history_service`            |      6 |
|       66 |  135 |    49% | `smoke_fire_loader`              |      7 |
|       66 |  138 |    47% | `job_status`                     |      6 |
|       62 |  109 |    56% | `job_tracker`                    |      6 |
|       60 |  122 |    49% | `zone_household_service`         |      7 |
|       60 |  138 |    43% | `health_monitor_orchestrator`    |     16 |
|       60 |  157 |    38% | `detections`                     |      6 |
|       58 |  100 |    58% | `reid_matcher`                   |      7 |
|       58 |  109 |    53% | `reid_service`                   |      7 |
|       58 |  118 |    49% | `circuit_breaker`                |      5 |
|       57 |  116 |    49% | `package_tracking_service`       |      9 |
|       57 |  179 |    31% | `managed_service`                |      6 |
|       55 |  100 |    55% | `file_service`                   |      6 |
|       54 |  100 |    54% | `exports`                        |      7 |
|       54 |  151 |    36% | `retry_handler`                  |      6 |
|       51 |  101 |    50% | `quantization`                   |      6 |
|       50 |  115 |    43% | `system_broadcaster`             |      7 |
|       46 |  111 |    41% | `summary_detail_service`         |      6 |
|       45 |  107 |    42% | `hybrid_entity_storage`          |      6 |
|       44 |  130 |    34% | `cameras`                        |      6 |
|       43 |  111 |    39% | `ai_audit`                       |      6 |
|       41 |  107 |    38% | `cache_service`                  |      6 |
|       40 |  101 |    40% | `dwell_time_service`             |      6 |
|       39 |  100 |    39% | `polygon_zone_service`           |      6 |
|       37 |  100 |    37% | `mqtt_publisher`                 |      4 |
|       37 |  131 |    28% | `nemotron_latency_optimizer`     |      7 |
|       37 |  133 |    27% | `job_timeout_service`            |      6 |
|       35 |  113 |    31% | `camera_service`                 |      4 |
|       30 |  111 |    27% | `xclip_loader`                   |      6 |
|       28 |  101 |    28% | `alert_service`                  |      6 |
|       28 |  105 |    27% | `cleanup_service`                |      6 |
|       27 |  111 |    24% | `calibration_service`            |      4 |
|       25 |  104 |    24% | `file_watcher`                   |      6 |
|       23 |  104 |    22% | `websocket`                      |      6 |
|       19 |  120 |    16% | `dedupe`                         |      6 |
|       14 |  134 |    10% | `household_matcher`              |      6 |
|       13 |  104 |    12% | `event_broadcaster`              |      7 |
|       13 |  125 |    10% | `registry`                       |      3 |

Wave-23 tail — system.py folded separately (the giant-module fix): 5,624
lines / 1,899 mutants is why the first-slot agent died twice WITHOUT a dossier
— one agent, one file, too much. Resume re-ran it solo -> 166/187 TEST-GAP
(89%, row 7 of 122, top routes/ module, behind four services): the /system/health
exporter-status builder matches Prometheus targets by `job/instance in`
(56 mutants) under a test that asserts only status.value=='up'; degradation
payload keys/defaults 52 mutants (`mode` default -> response becomes None via
a swallowed ValueError); monitoring-issue messages any().lower()-substring
only. Health-endpoint contract = pattern 6 on the dashboard's OWN status page.
Lane note: dispatch >1,200-mutant files as single-module waves.

Wave-40 anchor (04:02-04:15 UTC, 1 module): exports (54 gap/100, 54%,
row 98) is the EXPORT-JOB ROUTE contract: the whole job_tracker call
identity family (start/complete/fail — job_id is the WS broadcast routing
key) survives on assert_called_once() arity-only; the not-found path can
SPURIOUSLY broadcast fail_job for a job that never existed (logger.error
msg-drop TypeError swallowed by the broad except — try/except PLACEMENT,
not assertion strength, decided killed-vs-survivor for the identical drop);
the result-guard and->or would offer a download for an incomplete job;
404 detail=None still passes the `"not found" in detail` substring assert
(textbook weak assertion); ExportJobResponse's started_at/completed_at/
error_message fields back live UI components and are never read. No
R-T9-EXPORTDEFER collision — drafts are call-arg contracts, not defer
scheduling. Dossier verified pydantic/stdlib behaviors rather than assume
(3 kill recipes cite the verification).

Wave-41 anchor (04:20-04:36 UTC, 1 module): reid_service (58 gap/109, 53%,
row 93) — the NEM-4474 atomic-Lua store path is ENTIRELY unexercised (all
tests pass a bare AsyncMock so use_atomic is always False — mock-absorption again,
7 mutants) and get_entity_history's today/yesterday Redis date-keys are built
under call-count side_effects that ignore the key (13 mutants; wrong keys
silently return [] in prod). reset_reid_service's None->"" mutant slips past an
identity test; format_full_reid_context's "No "-section suppression is never
fed an empty-match dict (14 header-leak mutants). 7 drafts (T1-T7). Cluster-
sum check regenerated mechanically: 109 = 58+12+39, matches live meta exactly.

Wave-42 anchor (05:02-05:14 UTC, 1 module): summary_generator (89 gap/131, 68%,
row 53) — call-arg forwarding at scale: window_start/window_end/period_type/
session flow through generate_{hourly,daily}_summary -> _generate_summary ->
EventRepository/SummaryRepository/create_summary with NOTHING asserted at any
hop (outer-branch survivors EXECUTED by the window test, which checks
hour/minute/second but not microseconds, end, or tz-awareness). eager_load_
camera=True dropped 3 ways and survives — the flag that prevents async
lazy-load crashes is unasserted. VERDICT-VALIDITY FLAG (dossier, first of its
kind): 29 session-None-branch survivors include crashers that would ERROR the
without-session tests if executed — suspected stale-cache verdicts from the
WP4.3 widened-set cache reuse; WP4.4 re-proves red/green before trusting OR
dropping them. 5 drafts kill 91 gap. Cluster-sum 131 = journal = live meta.

Wave-43 anchor (05:22-05:31 UTC, 1 module): health_monitor_orchestrator (60 gap/138,
43%, row 90) — shipped-behavior headliner: _handle_stopped_container's
on_health_change boolean flip tells LISTENERS A STOPPED CONTAINER IS HEALTHY
(#22, HIGH) and the only callback-asserting tests route through the other
handlers; the whole network-isolation recovery path (_on_network_isolation)
has ZERO test references; per-service 'continue'->'break' halts the check
cycle after the first service because every cycle test registers exactly ONE
service. registry name=None clobber is a SILENT NO-OP (registry.py:202
'if service:' guard) — mutations vanish by design there. 41% EQUIVALENT
(56) — event/message text noise, the log-heavy shape again; 16 drafts
(28 clusters). Fully checked at dispatch (0 unchecked) — first fold with zero
snapshot reconciliation. Universe 240 = 101k+138s+1 (dossier TOTAL row).

Wave-44 anchor (05:42-05:54 UTC, 3 modules): health_ai_services (91 gap/111, 82%,
row 48) — the endpoint-with-status-only-assertion shape at gpu_config scale but
smaller: payload/degradation fields flow unobserved. retry_handler (54 gap/151,
36%, row 99) — 62% LOW-VALUE (94): the module's own retry-log prose; the real
work is the backoff/budget arithmetic. cameras (44 gap/130, 34%, row 104) —
SECURITY finding: _resolve_camera_dir's traversal gate '..' or '/' '\' tokens
or->and + token clobbers let '..'-only and backslash folder names SLIP PAST
into fallback resolution (tests only assert endpoint 404, never isolate the
gate); ffmpeg argv vector entirely unasserted (to_thread mock + assert_called
_once only) — flag flips like -ss/-vf/scale 640:480->480:480 squish survive.
The '/' token check is provably dead defensive code (Path.name strips '/') --
dossier calls it a baseline equivalent-mutant candidate. retry_handler folded
at snapshot (160 unchecked then; live meta grew — re-tally at final). Clusters
sum = journal = meta for all three. 19 drafts.



Wave-45 anchor (06:03-06:23 UTC, 3 modules): depth_anything_loader (106
gap/167, 63%, row 31) — analyze_depth owns 70 survivors:
has_close_objects/average_depth/depth_variance and the produced DetectionDepth
records are never asserted (the to_dict contract tests only HAND-BUILT ones);
the logger.error msg-drop member turns the pipeline-failure re-raise into a
TypeError under a stdlib logger (structlog absorbs it silently) and no test
enters that path; to_context_string's sort key is droppable — context order
silently flips to det_id order. weather_loader (97 gap/152, 64%, row 40) —
classify_weather has ZERO happy-path coverage: its only test asserts
pytest.raises, which every crash mutant still satisfies — that one gap is 67
of 152; snowy loses its +0.1 risk modifier under a tuple-label mutation,
clear-DAYTIME gains +0.25 under and->or, brightness /255->/256 off-by-one and
the 6 AM docstring boundary are real normalization bugs (dossier kept them
TEST-GAP, not LOW-VALUE). model_zoo (78 gap/185, 42%, row 66) — 56%
EQUIVALENT: the ModelConfig default mutants are dead branches against TODAY's
models.yml — the dossier names the wake-up condition (a registered entry
omitting a key turns 22 EQ members into real config bugs). The GAP core:
the eviction-flag trio priority/preload/never_evict is pinned only by an `or`
(test_smoke_fire_loader:204) that None satisfies — damaged reads silently
disable never-evict + preload; the NEM-2540 INFO-vs-ERROR optional-dependency
log contract (module docstring) is never asserted -> OCR-missing flips to
ERROR-with-traceback; the MODEL_LOAD_DURATION gauge flips to +start and
records ~1e9 s under >=-only asserts; MODEL_ZOO_PATH env-var name has ZERO
test hits suite-wide (the env contract is load-bearing per CLAUDE.md).
Snapshot flag: dispatched at 130 survivors, dossier froze at 185, live meta at
fold 185 (2 unchecked) — re-tally from the FINAL score JSON. 27 drafts.
Clusters sum = journal = meta for all three.

Wave-46 anchor (06:41-07:10 UTC, 2 modules): scene_ocr_service (183
gap/283, 65%, row 4) — the OCR-request-shape-at-scale + a REAL SIGN BUG:
_calculate_iou/_calculate_overlap_ratio's no-overlap guard or->and lets
one-axis-separated boxes compute NEGATIVE-intersection garbage IoU (tests only
cover both-axes-separated). Biggest single cluster in the program's history so
far: region_map side-entry key mangling (A11, 36) — left/right region labels
have ZERO coverage; and crop/full-frame request payloads (URL/json/image key)
flow entirely unasserted through MagicMock clients (A3+A4, 51); dedup consumer
schema + 0.50/0.80 uncertain-boundary docstring contract never pinned.
stream_manager (130 gap/211, 62%, row 20) — the LIVENESS-ASSERTS-ONLY shape
named: hset.assert_called() with the key checked as a SUBSTRING of
str(call_args_list), call_count>1, and one timing-dependent CONDITIONAL assert
(if 'camera1' in manager._streams) — payloads, Redis hash schema, backoff
sequence and retry_count never read. T-HEALTHKEY (9): health written/read/
deleted at the WRONG Redis key silently (real Redis would orphan every health
key); T-ADDGUARD: replacing a camera no longer tears down its old connection
task (orphan loop + capture leak); broad excepts swallow the TypeErrors that
mutants introduce, so broken-arg mutants still look like 'reconnect loop kept
running'. Snapshot flag: dispatched at 211 survivors / 64 unchecked; dossier
froze at 211 (130/74/7); live meta AT FOLD 250 survivors / 0 unchecked (the
last 64 checked: 39 survived) — re-tally from the FINAL score JSON. 12 drafts.
Clusters sum = journal = meta for both. (Repair note folded in: the wave-45
fold's table rewrite dropped the header/sep rows — restored here; the fold
validator now asserts their presence, not just row lines.)

Wave-47 anchor (07:02-07:58 UTC, 1 module): circuit_breaker (58 gap/
118, 49%, row 94) — the most telemetry-saturated module triaged yet: 47%
LOW-VALUE (55) — Prometheus label CASING (10), otel record_state_change args
(19), log-extra casing (26). The dossier RECOMMENDS SUPPRESSION-WITH-RECORD
for these rather than text-equality tests (asserting label casing is the
brittle-text trap) — 60 survivors flagged as baseline suppression candidates,
the program's clearest instance of the no-deletion-without-record receipt.
The real 58: ctx-manager __aenter__ accounting never read (half-open trial
calls, rejected_calls counter, error name/state args — 11); get_status/
get_state_info payload keys renameable while /api/debug/circuit-breakers
asserts 2-4 of 9 keys (14); tz-naive now(None) stamps serialize WITHOUT tz
offset into API payloads (3); Prometheus gauge VALUES wrong on recovery/reset
(4) and label values ->None mislabel every series they touch (15) — real
observability breaks, not noise. Snapshot flag: dispatched at 118 survivors/
213 unchecked (07:02 gate read); dossier froze at 118; live meta AT FOLD 129
survivors / 190 unchecked — re-tally from the FINAL score JSON. 5 drafts.
Clusters sum = journal = frozen dossier set.

Wave-48 anchor (08:03-08:08 UTC, 1 module): file_watcher (25 gap/104,
24%, row 117) — 73% EQUIVALENT, the purest log-prose module triaged (start/
stop/_ensure_camera_exists message + extra={} clobbers, 76 EQ); dossier
marks them suppression-with-record. The 25 TEST-GAP are shutdown- and
watch-contract material: observer.schedule recursive=True droppable -> a
non-recursive watch SILENTLY MISSES EVERY camera-subfolder upload (5);
mkdir parents=True dropped -> nested camera-root creation crashes (6, 3
exist_ok sub-variants need a TOCTOU race — left unkillable, recorded);
hash-executor shutdown destroyed -> thread leak + cancel_futures flip drops
queued hash jobs (4); stop() gather() loses its task args (the pending-task
test's 0.05s sleep masks the missing await); observer.join(5) timeout
contract; rate-limiter semaphore assignment ->None. Exact-boundary size
gates: 10240-byte image / 1024-byte video rejected under <= flips. Live meta
UNCHANGED at fold (104 surv/415 unchecked — run6 hasn't reached the block;
re-tally flag stands). 6 drafts. Clusters sum = journal = dossier = meta.

Wave-49 anchor (08:11-08:33 UTC, 1 module): mqtt_client (70 gap/232,
30%, row 78) — first FULLY-CHECKED fold candidate in the program's late
phase (live meta 0 unchecked: run6 passed this block before dispatch;
snapshot flag NOT needed, fold is canonical). The 141 LOW-VALUE (61%) are a
SUPPRESSION-WITH-RECORD module like circuit_breaker/file_watcher: the suite's
mock_prometheus_metrics fixture patches the metric CLASSES, so name/
description text mutations in _get_metric defs are invisible (42 keys, the
program's biggest single bucket — one real-registry integrity test would kill
all 42). The 70 TEST-GAP are call-args/contract gold: metric label/gauge
VALUES never asserted (tests check labels.assert_called() with no kwargs —
22 keys, Draft A); aiomqtt.Client constructor kwargs wholly unasserted
(hostname/port/credentials/tls -> None, 14); TLS branch never exercised on
connect (3); MQTTConnectionError.original_error cause-chaining dropped (5);
publish retry-count + backoff-schedule contract unpinned — max 3->4 and
attempt<max-1 boundary flips pass because the retry test succeeds on attempt
3 (4+3); broker unsubscribe/subscribe topic+qos args (4+2); REAL PRODUCTION
DEFECT flagged: connect() idempotency-guard mutants re-create the client and
re-enter __aenter__ -> double-subscribes the broker in production, and
test_connect_is_idempotent was written to prevent exactly that but asserts
only connected is True (fix: mock_cls.assert_called_once()). Dossier also
records an E1 dependency on MagicMock hasattr-always-True: spec'd mocks would
flip it TEST-GAP. 7 drafts. Clusters sum = journal = dossier sections = meta
(script-verified assigned=232 missing=0 extra=0).

Wave-51 anchor (09:11-09:30 UTC, 2 modules): thumbnail_generator (79
gap/118, 67%, row 62) — FULLY CHECKED (0 unchecked, fold canonical):
the image-drawing module whose covering tests assert only isinstance(result,
Image.Image) with ZERO pixel checks, so the entire box-drawing algorithm
survives — box colors (10), bbox-field extraction ->None where output becomes
a pure copy of the input and NO BOX IS DRAWN (4), detection dict-key renames
(18), .get defaults incl confidence 0.0->1.0 (7), label bg/text/position (7),
None-guard flips (8), RGB-mode conversion guard (4 — an RGBA test exists but
asserts nothing about mode), detection_id->None (filename None_thumb.jpg
passes the '_thumb.jpg' substring assert), async wrapper dropping forwarded
output_size/quality. EQ class is Pillow-verified: 255->256 channels clamp
(ink identical), default font == load_default, JPEG format inferred from
path. 7 drafts. worker_supervisor (73 gap/190, 38%, row 73) — SNAPSHOT
FIRE: live meta has grown to 243 survivors (0 unchecked) while run6 kept
checking past the dispatch freeze; fold at the dossier's 190, re-tally from
the FINAL score JSON (precedent family). TEST-GAP: crashed-worker give-up
broadcast + history payloads never inspected (11), get_worker_supervisor
singleton args never flow through any test (8), stuck-worker state clobbers
(6) and stuck-cycle broadcasts (6). Notable hazard: status=None mutants raise
AttributeError INSIDE handlers but _monitor_loop's broad except Exception
swallows them — survived-by-swallowing, flagged. 69 EQ (60 log-text) + 48
LOW metric-arg (helpers accept None labels silently). Clusters sum = journal
= dossier Totals = meta both modules at their fold basis.

Wave-50 anchor (08:31-09:48 UTC, 2 modules, folded late -- dispatch order
48/49/50/51, fold order 48/49/51/50): websocket 23 gap/104, 22%, row 118
(route module; NOT the wave-31 websocket_emitter dossier) and xclip_loader
30 gap/111, 27%, row 113 -- both FULLY CHECKED (0 unchecked, folds
canonical). websocket: the 14-key subscribe-VALIDATION_ERROR details={
"example":...} cluster is client-facing wire content (frontend renders the
usage example) asserted only via type/error/message-substring -- one
structural assert kills all 14. Wire-contract singles: UNSUBSCRIBE data=None
mutant crashes the connection instead of the graceful unsubscribe-all ack
(the SUBSCRIBE twin test exists and killed its twin -- missing twin only);
send_heartbeat get_current_sequence(connection_id)->None pins lastSeq 0
forever (NEM-3142) and the existing test asserts lastSeq==0 with an
UNregistered connection -- the exact value both variants produce; resync
freshness < -> <= falsely gap-too-olds a client that demonstrably holds the
oldest message (forces full re-fetch); _check_message_size rejects a message
of EXACTLY max_size; resync ack["channel"]="unknown" arm never exercised;
empty-raw_data preview "" vs None. EQ 76 (73%) = log text + falsy-default
([] vs None identical branches) + break/return + vestigial pydantic-v1
error member. xclip_loader: mock-absorption gold -- processor() kwargs
(text/return_tensors/padding) and torch.softmax/squeeze call args wholly
unasserted (mocks return fixed values, capture only images=; 18 keys),
device-offload unasserted (5), float16 stored under wrong dict key survives
because the test asserts half() was CALLED not where the fp16 tensor lands
(3); 16-frame padding (16-len)->(16+len) invisible because the >16 test uses
32 IDENTICAL frames (2); from_pretrained(None) model-path drop (1);
zero-dimension guard tested only on the height axis (1). EQ family includes
6 dead-defensive-guard keys (np.array(PIL frame) is always 3-D uint8 --
guard unreachable) and boundary flips at len==16 that are provably identity
operations. 6+6 drafts. Clusters sum = journal = dossier Totals = meta both
modules. GAP share drops 63%->62% at this fold (both modules <30% gap share;
first cross of the rounding boundary -- survivor-weighted, not classifier
drift).

Wave-52 anchor (09:42-10:00 UTC, 1 module): dedupe (19 gap/120, 16%,
row 119) — REDIS-KEY-ARG-BLIND family: the covering tests assert
exists.assert_awaited_once() and set()'s EXPIRE kwarg but never the KEY
argument, so wrong-key mutants survive across the whole service (18 keys:
_check_redis key-None 3, mark_processed 3, clear_hash delete(None) 3,
ensure_key_has_ttl 4 — its test pins expire's TTL arg but never the key,
cleanup_orphaned_keys ttl target 1): a wrong key SILENTLY DISABLES DEDUPE in
production while every test stays green. Plus is_duplicate_and_mark dropping
the precomputed hash from its delegation (4) — output identical, the hash
quietly RECOMPUTED and atomicity lost. EQ 95 (79%) is the program's most
EQ-heavy module: log text plus genuinely proven classes — SHA256 is
chunk-size invariant (f.read(8192)->8193 is math-identical). SNAPSHOT FLAG:
live meta 13 unchecked at fold (survivors equal at 120, may grow) — re-tally
from the FINAL score JSON. 6 drafts. Clusters sum = journal = dossier = meta.

Wave-53 anchor (10:10-10:16 UTC, 1 module): health_monitor (77 gap/
143, 54%, row 69) — broadcast/payload blindness, threat_monitor's shape at
scale: test_broadcast_event_format checks payload KEYS only, never
data['message'] content, so the 36-key broadcast-message cluster survives
(failure/restart messages XX-clobbered or substituted by the except-handler's
'Health check error:' text); event tests filter by event_type membership and
never assert e.service/e.message/e.timestamp of THIS event (16 mapping + 7
HealthEvent-field mutants, incl naive now(None) stamps reaching
/api/system/health recent_events); exponential-backoff formula broken 4 ways
with only an "increasing with len>=2" assertion; max-retries > -> >= gives up
one attempt early under a count<=2 upper-bound test; post-restart accounting
masked by the loop's recovery branch (CONVERGENCE pattern: eventual-state
assertions pass — kills need direct _handle_failure calls, drafted T3);
recovery-threshold count>0 -> >=0 spams recovery broadcasts every cycle
(>1 skips single-failure recovery) — needs broadcast-COUNTING assertion,
recipe recorded, no draft. NEM-5057 task-name test asserts 'health' in
name.lower() — too weak to pin the documented name (T6). EQ 64 = log text +
exc_info + one CancelledError break/return. SNAPSHOT FLAG: live meta 11
unchecked (survivors equal, may grow) — re-tally from FINAL JSON. 6 drafts.
Clusters sum = journal = dossier (machine-verified partition) = meta.

Wave-54 anchor (11:02-11:26 UTC, 1 module): bbox_validation (92 gap/
114, 81% gap share -- the program's MOST gap-dense module and the first with
ZERO LOW-VALUE keys; row 47) -- geometry-contract gold: bbox= kwarg
dropped/None at all 6 validate_bbox raise sites (10; only the zero-WIDTH
site's .bbox is asserted -- and it's KILLED, the perfect control),
strict-bounds guard weakened 9 ways (strict=True tested once with both axes
violated at margins; an edge-EQUAL valid box never run strict), and the
validate_and_clamp failure-path contract broadly unasserted -- the
Hypothesis property pins original_bbox/was_clamped only for IN-BOUNDS
inputs (its in-bounds mutants were killed), so on failure paths warnings
can be None, was_clamped None/False, original_bbox None and the flag-only
tests stay green (~27 keys). Two shipped-behavior classes proven: an
x2==1 mutant returns is_valid=True for a 1-px sliver (crop/box pipeline bug
class), and completely-outside boxes misroute to the clamp path (only
warnings[0] TEXT distinguishes); x1==0 boundary and edge-touching
(x2==W, no warning expected) never asserted; NaN warning f-string
interpolates x2-x1 -> x2+x1 and survives every substring assert. SNAPSHOT
FIRE (again): live meta 121 surv / 54 unchecked at fold vs dossier 114 --
run6 still inside the block; fold at 114, re-tally from FINAL JSON. 5
drafts. Clusters sum = journal = dossier Totals = 114.



Wave-39 anchor (03:42-03:50 UTC, 1 module): background_evaluator (100
gap/161, 62%, row 34) is the JOB-TRACKER WIRE contract end-to-end: every
progress/complete/fail call site — tracker AND legacy branches (legacy has
ZERO assertions today) — takes None/dropped args invisibly; UI progress
percents (10->11, 25->26, 40->41) never pinned; the NEM-3902 undefer
regression guard is defeated because the covering test mocks the session
so the deferred-column bug it guards CAN NEVER FIRE (dossier: "mocks the
session so the regression it guards can never fire" — mock-absorption
hollowing out a REGRESSION test, its worst use yet); merge(audit)->merge(None)
silently loses persisted results; factory kwargs dropped -> permanent
misconfigured singleton. Meta stable 161=161, no re-tally flag. 11 drafts,
all three channels + meta agree.

Wave-38 anchor (03:34-03:45 UTC, 1 module): orphan_cleanup_service (68
gap/170, 40%, row 82) is the DELETIVE-FILE-SERVICE risk class: age-unit
arithmetic (now-mtime)/3600 -> \*3600 makes a 1-SECOND-old file read
~86,400h old and delete immediately (worst bug found in-module, draft T6
frozen clock); the orphan DB lookup can query str(None) so clip_path
matches 'None' and LIVE referenced files classify as orphans (query-honest
mock, draft T3b); ORM == -> != deletes exactly the files WITH db records.
Dossier's classification-discipline note (worth citing in WP4.4): the 9
query-gutting mutants counted EQUIVALENT - equivalent-UNDER-MOCK but fatal
in production (bind error -> broad except -> never-delete) - held out of
TEST-GAP "to keep the budget honest". 87 EQUIVALENT = five log-text
clusters; snapshot 170 vs live meta 174 (checked frozen at 371 - re-tally
at final, context_enricher precedent).

Wave-37 anchor (03:22-03:33 UTC, 2 modules): transcoding (71 gap/152,
47%, row 76) is the ffmpeg-plumbing gap — argv construction, availability
probe, stderr-tail failure message (boundary >5 vs >6 lines) and
get_video_info defaults all unobserved; dossier adds a PRODUCT NOTE:
\_validate_input_path's dash check is unreachable after resolve() (dead
code, same family as florence's \_parse_list_response). smoke_fire_loader
(66 gap/135, 49%, row 86) is the MOCK-ABSORPTION textbook: YOLO patched
with a bare MagicMock makes is_mock always-True, so the entire weights-
discovery chain (model.pt/best.pt/glob) is dead under test — its 66
EQUIVALENT are mock-shaped, not semantically dead; the real gaps are the
never-executed format/sort/cap/night-escalation paths + batch predict
kwargs. RECONCILIATION FIRST: the cluster table double-counted overlapping
example keys (F9's \_43 reappears in F10) — table grand 143 > PHYSICAL 135
survivors — so here the dedup'd Totals LINE (66/66/3) is canonical and the
table's GAP column was inflated +8; the first case where the nested
rule points the other way, and the tie-break that decided it is the
physical meta count, not an artifact's rank.

Wave-36 anchor (03:07-03:22 UTC, 1 module): pipeline_workers (167 gap/282,
59%, row 6) is the NEM-3607 BROADCAST WIRE-CONTRACT void — pattern 6's
biggest instance yet: no test in the repo injects a broadcaster (zero
broadcast_batch grep hits), so the whole started/completed/failed region
runs under broadcaster=None unobserved; 48 payload KEY renames + 50 un-
asserted VALUES (retryable/error_type drive the UI's retry affordance;
datetime.now(None) naive-timestamp leak again) survive together. Table =
journal = live meta three-way (282=282=282); residue documented (categor-
ize_exception(None,...) is an identical-default AI.220). LOW-VALUE 96 =
90-log/otel-attribute noise — the module is the program's densest log
emitter; LOW share crosses to 14% on its weight (shape-driven, 103 of the
+96).

Wave-35 anchor (03:02-03:07 UTC, 1 module): cache_warming (69 gap/100,
69%, row 79) is UNOBSERVED-REPORT-FIELD gap: the WarmingReport/WarmingResult
contract — durations ((perf_counter-start)*1000 droppable to /1000/*1001/
None, 24 mutants), strategy, cache_name, success=False->None (assert not
failed.success passes on None!) — is built and never read; the cameras
cache.set contract asserts only set.assert_called_once() (key/payload/ttl
unobserved, 17); the fail-soft outer except returns a graceful empty report
that no test forces (results=None mutant CRASHES it instead — contract
violation invisible); the sequential-path wait_for timeout is droppable to
None (parallel timeout test only — a hung sequential warmer wedges startup);
singleton ignores settings because mock 'parallel'/30.0 EQUAL code defaults
(DEFAULT-VALUE ABSORPTION — D3 uses non-default sequential/7.5). Dossier
again machine-verified all three channels (table=journal=Totals).

Wave-34 anchor (02:33-02:50 UTC, 2 modules): context_enricher (106 gap/134,
79%, row 30) is root-cause pattern #1 at module scale — every query builder
survives wholesale because tests mock session.execute and never inspect the
statement (the window test literally asserts assert_called(), "we trust the
query is correct"), and the deviation-score math is asserted only as ranges,
so formula mutations hide; dossier banks the kill recipe
(str(stmt.compile()) + bind-param asserts + exact-value parametrizes) and
flags 4 mutants boundary-unobservable. Snapshot was mid-run (82 keys still
unchecked at dossier time — the count can grow by final score). ai_audit
(43 gap/111, 39%, row 105) is log-noise-dominant (42 LOW-VALUE — extra=
payloads + message renames) with real gaps under it: the progress message
and processed/failed counters ride GET /batch/{job_id} while tests assert
only the percentage, an == -> != query flip survives on a call-order mock
session, and three nullable response fields are never asserted. Cluster
table, journal AND Totals line agreed for both modules (first full
three-channel agreement — recorded, not assumed).

Wave-33 anchors (02:23-03:00 UTC, 2 modules): osnet_loader (88 gap/136,
65%, row 54) — the segformer wide-except-crash-swallow pattern lands on the
embedding model's loader (blanket except -> degraded/empty result turns
mutation breakage into silent model degradation); dossier Totals line again
contradicted its own table (86/13 vs table+journal 88/11 — table folded).
mqtt_publisher (37 gap/100, 37%, row 109) is the MQTT WIRE-CONTRACT gap: the
18-param topic table never puts fields under the nested data dict, never
routes service./worker./zone.approach, and the timestamp test checks key
presence only — so datetime.now(None) NAIVE timestamps and clobbered
caller-supplied timestamps survive (naive -> consumers parse wrong-offset
times); register_with_broadcaster rides a MagicMock that defeats its own
hasattr guard. Cluster sums 97 vs survivors_total 100 (+3, folded at 100).

Wave-32 anchor (02:02-02:22 UTC, 1 module): container_discovery (650
gap/696, 93%, ROW 1 — the program's biggest module by 3x) is a dataclass
table: build_service_configs hand-builds 25 ServiceConfig entries and no test
calls it with settings + asserts field values — so port/display_name/
health_endpoint/backoff/grace mutations across the WHOLE table survive. Its
shipped-behavior core: max_failures=10 (INFRA) survives dropping to dataclass
default 5 — infra services would be restarted on half the tolerated failures;
backoff base/max drops silently retime every managed restart (60s->300s);
config-name case flips break match_container_name substring matching. One
parameterized test — build_service_configs(settings) -> exact field map per
service — kills the bulk; 5 drafts. Its 14+4 EQUIVALENT rows are kwarg==
dataclass-default (mutmut-exclusion candidates, recorded not deleted).

Wave-31 anchor (01:42 UTC, 1 module): websocket_emitter (73 gap/101,
72%, row 72) is pattern 6 at the LAST dispatch hop: every
\_dispatch_to_event_broadcaster/\_dispatch_to_system_broadcaster arm survives
full message-shape clobbers (camera/worker/system/security payloads,
timestamp keys, redis channel derivation) because the covering tests assert
call_count only — the dashboard's wire format is unobserved end-to-end;
correlation_id drop + user-room routing loss ride the same call_count-only
shape on emit_to_user/broadcast/emit_batch. Dossier note: its Totals LINE
(57/41/3) contradicts its own cluster table + printed count-check (=101);
table + journal agree 73/25/3 — folded as such.

Wave-30 anchor (01:22 UTC, 1 module): read_through_cache (97 gap/122,
79%, row 39) is cache_service's sibling and the ARG-BLIND MOCK shape end to
end: get/invalidate/refresh tests assert call_count or bare assert_called(),
never args — so cache-key derivation damage, the stampede lock's SET NX
semantics (nx=True→False survives; mock set returns scripted, lock still
"acquired"), lock expiry drop, and value-write TTL clobbers all ride; the
three \_load*\* DB loaders are select(None)/where(None)-invisible with
result-dict key renames nobody reads (tests assert 2 of ~8 keys). A single
key-aware-fake per collaborator kills most of the 97 — pattern 7's cleanest
single-module instance yet.

Wave-29 anchors (00:42-01:00 UTC, 2 modules): nemotron_streaming (203
gap/271, 75%, row 3 — third-biggest single-module gap, behind container_discovery and
llm_reasoning) is the streamed-analysis orchestrator under all-mock tests:
session/redis/collaborators AsyncMocked so the Event row handed to
session.add, the event_detections junction INSERT (NEM-1592/2012/3350), and
all 10 call_llm_streaming context kwargs are never inspected — the FATAL-AS-
RECOVERABLE family (recoverable=False→True/ deleted-behind-schema-default-
True on 4 fatal handlers) mislabels terminal failures as retryable, and
\_check_idempotency(None)-style call-arg damage is pattern-7 at its widest.
reid_matcher (58/100, 58%, row 92) is the SQLAlchemy statement-inspection
hole — find_matches WHERE/ORDER BY/cutoff bind params invisible under
execute.called-only tests (same family as w25 search's bind-params, but the
predicates DO render: kill by compiling the executed stmt).

Wave-28 anchor (00:22-00:40 UTC, 1 module): detections (60 gap/157,
38%, row 91) — highest EQUIVALENT share of any routes/ module (78/157, 50%):
falsy-default swaps (get(k,{})→None), key-rename reads whose canonical
lowercase consumer never sees them, and header-case variants starlette
normalizes away. The 60 gap rows cluster in the ENRICHMENT-PAYLOAD contract:
has_damage/is_commercial/is_suspicious/violence/face/image_quality defaults
flip False→True silently or →None (pydantic 500) whenever a fixture omits the
key — and every existing fixture omits exactly those keys; vehicle_damage
flag flip rides the same hole.

Wave-27 anchor (00:10-00:40 UTC, 1 module): transcoding_service (71 gap/
108, 66%, row 74) is the ffmpeg-ARGV family — both subprocess call sites are
mocked with call-count-only asserts, so 42 argv-token + stdout/stderr=PIPE
mutations survive (no stderr pipe destroys the TranscodingError diagnostic);
boundary + age-window arithmetic (1000-byte cache validity, max_age_days
factor chain) never probed because fixtures avoid every boundary; the
option-injection guard in \_validate_video_path (startswith("-")) becomes dead
code under 2 mutants — security check with zero teeth-tests.

Wave-26 anchors (23:45-00:10 UTC, 2 modules — endpoint + client noise
shape): gpu_config (81 gap/111, 73%, row 57) is the status-code-only-asserted
endpoint at scale — every \_calculate_auto_assignments strategy (MANUAL/
VRAM_BASED/BALANCED/ISOLATION_FIRST/LATENCY) survives full placement clobbers
because tests assert len>=3, never the map; its SYMMETRIC-FIXTURE ABSORPTION
family = mock-absorption's twin — LATENCY sort flips are test-no-ops while
every fixture GPU shares compute_capability '8.6' (a tie swallows the
mutation before any assert); \_update_gpu_devices_in_db survives on
commit.called-once alone. clip_client (69/220, 31%, row 80) is the wave's
noise anchor: 118 LOW-VALUE + 33 EQUIVALENT — duration_ms arithmetic,
exc_info toggles, extra= payloads, real changes whose only observable is
diagnostic log text; the 69 gap rows are payload-shape asserts missing on
anomaly/similarity (embed has the pattern to copy).

Wave-25 anchors (23:22-23:45 UTC, 4 modules — the HTTP-client wave):
florence_client (100 gap/208, row 35 at 48%) carries the wave's structural
proof — KILLED-TWIN ASYMMETRY: the identical textual mutation DIES in
extract/ocr/detect (asserted methods) and SURVIVES in ocr_with_regions /
describe_regions / phrase_grounding / detect_security_objects. That asymmetry
proves these survivors are real behavior changes, not equivalents — the
strongest classifier evidence in the program. Its A-cluster is a circuit-
breaker BYPASS family: `_check_circuit_breaker("ocr_regions"->None/XX)` falls
back to the EXTRACT breaker (aliased :364), so an OPEN per-endpoint breaker
stops blocking its own endpoint; `detect_security_objects` has ZERO direct
unit tests (exercised only as a mocked collaborator in
test_vision_extractor:2735). enrichment_client (130 gap/158, 82%, row 19,
10 drafts) joins the LLM-PROMPT-TEXT family (w20 threat_detection_loader +
here): to_context_string labels feed nemotron_analyzer.py:4683 but tests
assert only substrings, so XX/CAPS ride into the prompt; plus the NEM-3147
W3C trace headers unasserted on get_model_status/preload_model and the
HTTP-500 retry-boundary never probed (only 503/400). search (67/109, 61%):
`_build_search_query` holds 84 survivors because its literals render as
SQLAlchemy BIND PARAMS, not SQL text — the compile-and-assert pattern-3-SQL
variant can't see them; kill by executing against a real/in-memory compile or
asserting bindparams dict. summary_detail_service (46/111, 41%, log-noise
tail). NOTE: florence_client + search were mid-run when triaged (208/1,149
and 109/477 keys checked) — their survivor piles will grow; re-slice from
final score JSON before WP4.4 lane work on them.

Wave-23/24 anchors (folded together; 10 modules, 23:05-23:22 UTC —
queue shakeup + first aggregate drop): threat_monitor_service (182 gap/244,
75%, row 5 of 122, behind container_discovery, llm_reasoning and nemotron_streaming — 244 survivors, the wave's biggest) is the canned-DB-mock shape at scale:
`session.execute` returns AsyncMock whatever statement it's handed, so the
cooldown cutoff arithmetic / dedup `==` / `>=` / LIMIT all ride; the
alert.created WEBSOCKET payload (36 mutants, 24 key renames) and the webhook
payload (22 key renames) are NEVER OBSERVED by any test — pattern 6 again, on
the two wires out of the alert pipeline; T1 kills the cooldown family with a
REAL DB, no mocks. debug (78/107, 73%) is second routes/ module:
redis-info dict + pubsub payload only membership-asserted; the ltrim
off-by-one `start 0->1` DISCARDS every recorded pipeline error while
returning True. scene_baseline (89/101, 88%, row 52) sharp gap. prompt_storage
(93/104, 89%, row 45, 13 drafts — program record) is the cleanest module shape:
ZERO log surface means zero LOW-VALUE noise, every mutant caller-observable;
naive-`now()` timestamp leak (T2) is the shipped-behavior note. batch_aggregator
(row 71; 74 gap/203) is the wave's noise anchor: 125 EQUIVALENT (62%) — a
log-heavy coalescer whose survivor pile is mostly structured-log text, the
suppress-with-record family. registry (13 gap/125, last row): the screen's zero-direct-
tests module was NOT untested (a pure-re-export shim test_service_registry.py
:56 exercises it richly — screen v1 corrected by mutation evidence, recorded) —
but the real gaps are persistence round-trip class: restored state silently
`enabled=None`/`failure_count=None`, `last_failure_at` always None, singleton
discards its redis client so the global registry persists NOTHING.
cache_service (41/107): SWR freshness plumbing rides on `set.called`-only
asserts (freshness key -> None makes EVERY hit stale, refresh storms).
dwell_time 40/101, alert_service 28/101 (both log-noise heavy, queue tail).
Process: wave 23's first-slot agent died without StructuredOutput a SECOND
time (and left no dossier — unlike wave 21) -> fixed by Workflow resume (5
agents cache-replayed, 1 re-run); two first-slot suspicions now, watch it.
Also registry journal entry predated its own dossier (meta refreshed
mid-triage: 121->125 survivors, bucket re-grade) — dossier-canonical rule
applied again; fold now reconciles journal-vs-dossier, not journal-only.

Wave-22 anchors (22:22 dispatch, 3 modules — model-loader shape dominates):
segformer_loader (144/185 gap, 78%, pos 8 — the wave's sharpest) is the wide-
except-crash-swallow shape at its worst: `segment_clothing` has 152 of its 153
mutants SURVIVING because the covering tests build a full mock inference graph,
then assert only `isinstance(result, ClothingSegmentationResult)` — and the
module's blanket `except Exception: return ClothingSegmentationResult()` turns
ANY mutation-induced breakage into an empty-but-valid result that still passes.
The "face covered logic" test never calls the function at all (constructs the
dataclass directly). `to_dict` is fully value-asserted and died 9/9 — the
control case proving the mechanism. Lane: verify the happy path COMPLETED
(w16 rule), value asserts on mask/coverage/shoes/face-covered.
vehicle_classifier_loader (77/116, 66%) carries the SECURITY finding: NEM-4519
`weights_only=True` on torch.load can be dropped/flipped (load#41/#44 ->
arbitrary-pickle loading re-enabled) under a MagicMock().load that accepts
anything, and the NEM-4501 path-existence gate's failure branch has never
executed; tests also write classes.txt identical to the fallback so a broken
lookup is invisible. K2 is a clean EQUIVALENT proof (convert("RGB") on an
RGB image is pixel-identical). file_service (55/100, 55%) is pattern 7
re-confirmed on the Redis deletion queue: zrange/zrem/zrangebyscore call args
never asserted — the score window IS due-job semantics (num dropped =
unbounded batch, start=1 starves the oldest job; a wrong zrem member leaves a
file deletion ARMED after cancel). 41/100 of its survivors are log-text
EQUIVALENT — near half noise, the loader/log shape again.

Wave-21 anchors (22:13 dispatch, 4 modules — first wave where the gap share
dips to 66%: two well-tested shapes landed together): bulk_detection_service
(119/147, 81%, pos 14) is pattern 3+7's cleanest single lever — 36 mutants are
`_detection_to_dict` INSERT column-name clobbers under a mocked session that
swallows any dict (the ONE test that captures call_args asserts only `is not
None`); the ON CONFLICT dedupe contract (camera_id+file_path, NEM-3753) can
vanish under `== → !=` with the branch test asserting only `success is True`;
chunk bounds `range(0, chunk_size)` silently DROPS the tail 50 of 150 with
success still True. Harness note: this wave's agent completed the dossier but
died before StructuredOutput — counts taken dossier-cluster-table-canonical
(table sums to 147 under assert; the dossier-is-canonical rule, second use).
restore_service (68 gap/149, 46%) = progress_callback AsyncMock asserted as
call_count>=4 only: 40 argument mutants, ONE call-args contract draft kills
them. cleanup_service (28 gap/105, 27%) carries the wave's structural finding:
the retention cutoff's two highest-blast-radius mutants (`-timedelta`->`+` =
delete EVERY log row; `<`->`<=` boundary) DO have real assertions — in
integration tests — but pyproject's mutmut selection is unit-tier only, so
covered-in-the-wrong-tier survivors cannot be killed by design: WP4.4's unit
drafts T1/T2 close it; the tier-scope blind spot itself is a program note.
`run_cleanup(dry_run=True)` default flipped is unobserved (every caller passes
it explicitly) — safety-default class. polygon_zone_service (39/100, 39%) =
56% EQUIVALENT: PolygonZoneType is a StrEnum and pydantic coerces zone_type,
so the `hasattr(...,"value")` guard's both branches return the same string —
provable-noise, plus the log-extra family (40 more).

Wave-20 anchor: threat_detection_loader (87/128, 68%) — six drafts kill
86 of 87 gaps; format_threat_context LLM-PROMPT text (header, CRITICAL
ALERT, HIGH PRIORITY marker, sort-reverse) is asserted only by substrings,
so XX-wraps and case flips ride into the prompt — exact-equality asserts
(draft T5) are the product-contract fix; batch path has NO threshold-arg
test at all. NOTE: this wave's structured drafted_tests field came back
empty (agent key typo) — draft count taken from the dossier, whose
Drafted-tests section is canonical for the lane.

Wave-18 anchors: llm_reasoning = 209/210 TEST-GAP (100% — the queue's
sharpest, and the first routes/ module; a 210-survivor module with exactly
ONE equivalent mutant). Root: every covering endpoint test mocks raw_response
as non-JSON or a canned dict, so the whole parsing layer (\_parse_json_response,
confidence/risk-factor/observation extractors, enrichment-source names and
sample_fields, truncation surfacing) runs UNOBSERVED; a parametrized
indicator-table test (draft 5) + exact-name source table (draft 3) + a
JSON-dict endpoint test (Extra A) cover the bulk. camera_service (35/113,
31%) is the opposite shape — well-tested module, survivors mostly log text
and absorbed defaults.

Wave-19 anchors: compose_parser 95% TEST-GAP (111/117 — the queue's
second-sharpest after the zone trio) is ONE root cause: the display-name
table test asserts 4 of 17 special_cases entries, so key+value clobbers on
florence/redis/go2rtc/grafana/prometheus/loki/jaeger/alertmanager/pyroscope/
alloy/elasticsearch/dcgm/cadvisor ride — 66 survivors killed by ONE
parametrized test (draft D1). Healthcheck parsing (disable+test combos,
bare-URL endpoint default, sh -c string form, cmd-port extraction) =
never-constructed inputs, drafts D2-D4. notification adds label-precedence
chains (orchestrator.\* labels > healthcheck > category defaults — 21
survivors, D-series pins the precedence ladder).

Wave-17 anchors: export_service (135 gap/180, pos 7 — top-10 crossing) —
tests run the row-conversion loop but NEVER OPEN THE EXPORTED FILE (18
kwarg-wiring survivors ride: fields stubbed None, `or 0`→`and 0`);
drafted T1 reads the JSON and asserts every field. T5 pins the websocket
progress ladder 1/35/70/80/95 (covering test asserts call_count>0 only, 34
survivors + the int((idx+1)/total\*70) formula family). Lane note:
where(None) is a SQLAlchemy no-op — compiled-string asserts, not
raises-asserts. Detections-to-JSON route test mocks EMPTY results and
asserts only media_type — the prod caller path (detections.py:2165) is
effectively untested for content.

Wave-16 anchors: batch_coalescer's covering test asserts
`len(compatible) >= 0` — a TAUTOLOGY that can never fail (the queue's first
found; the lane should grep for other `>= 0` / `>= 1` count asserts); its
draft T1 (assert_awaited_once_with on set/zadd/expire) kills 20 — the Redis
TTL IS the cleanup design and 6 mutants leak candidate keys forever under a
bare `zadd.assert_called_once()`; priority silently lost through the
from_json round-trip = scheduling-safety class. vitpose_loader adds the
wide-except-crash-swallow shape (14 survivors: whole-call mutations crash
mid-body and the `except Exception` fallback returns, so the CRASHED path
looks like the graceful path — exception tests assert fallback shape only);
same family as performance_collector's pydantic-swallow — lane should verify
the happy path COMPLETED, not just that a result came back. NEM-5530
coalesce counter (metrics.py:5138) has ZERO test references repo-wide.

Wave-15 anchors (read first — biggest single-draft kill ratios in the queue):
alert_engine's T1 (exact-key-set + args on the ALERT_FIRED webhook payload)
kills 22+7+12=41 of 140 by itself — the covering test asserts only
`called_once` + event type and never reads the payload dict, so all 11 outer
keys ride (pattern 6's biggest instance, 3×-confirmed now with the event_id
kwarg cluster); T3 (capturing-session + str(stmt) predicates) kills the 18
inverted-where-clause survivors — dwell scoping inverted cross-camera/zone
under a mocked execute is shipped-behavior class, verify with one input before
accepting. quantization (51 gap/101, 50%) sits at the sort position after
package_tracking.

Kill-family anchors the lane should exploit: job_tracker D1–D2 kill a 56-mutant
reconstruction cluster; pose_analysis T1–T6 kill ~90 of 105 via fixture-shape
fixes; audit_logger's parametrized full-context tests cover ~142; florence's
call-args contract test covers ~31; redis_json/memory's key-aware-fake tests
cover ~50.

## Cross-module patterns (fix once, kills many — the lane should start here)

1. **Log-payload assert-once-per-family**: audit_logger's except-handler is
   asserted for 1 of 6 methods sharing it; a parametrized full-context test
   kills 118 survivors' patterns. Same shape may recur — check dossiers.
2. **Fixture-shape blind spots**: pose_analysis fixtures always supply both
   body sides → single-side retrieval/mean paths never observed (~50
   survivors, ~6 boundary fixtures kill them). Corollary: boundary tests sit
   miles from the line (job_timeout margins are minutes; latency tests shed at
   10 vs max 5) — freeze exactly ON the boundary.
3. **call_kwargs under-assertion**: tests assert `called_once()` but not the
   ARGUMENT (job_tracker broadcaster-None, audit_logger db/request drop).
   Audit the queue's `assert_called_once()` additions. Strongest variant
   (auto_enrollment, ~121 survivors/12 drafts): AsyncMock `session.execute`
   returns canned results whatever the stmt — fix = capture call_args,
   `stmt.compile().compile(compile_kwargs={"literal_binds": True})` and
   assert WHERE/ORDER/LIMIT text; and capture `session.add` ARGUMENTS —
   tests that assert only `add.assert_called_once()` let every
   constructor-kwarg→None ride (KnownPerson/EnrollmentCandidate fields,
   status, and `is_household_member=False` — the security-trust default).
4. **Sparse/defaulted payload paths never fed**: job_tracker reconstruction
   defaults (56 survivors), prompt_version removed-only diffs.
5. **Precedence/`or`-vs-`and` guard flips in boolean guards** — shipped-behavior
   class findings, highest review priority (prompt_version has_changes case).
6. **to_dict/metadata partial-key assertions** (wave 14 sharpens this to a
   shipped-behavior finding: scenario_classifier's tailgating payload —
   detected/confidence/description/persons_involved/time_gap_seconds — is
   WHOLLY unasserted; the covering test's assert is a disjunction satisfied by
   the risk score alone, so all 5 keys + the dict itself ride, 13 survivors.
   A security-relevant alert payload reaching the wire unchecked. Plus
   performance_collector's throughput SQL: `detected_at >= cutoff` vs `>` and
   the ±timedelta cutoff flip invisible under a canned-scalar AsyncMock —
   compile-and-assert the statement, pattern 3's SQL variant):
   existing tests read \_every key except*
   the mutated one, so key renames on unasserted fields (`caption`,
   `confidence`, job_history's payload keys) ride through to the API/frontend
   wire contract. One exact-key-set assertion per to_dict kills whole families
   (florence ~12, job_history ~26). Prefer `assert set(d) == {...}` over
   per-key reads.
7. **Lenient mocks swallow call-argument damage** (quadruple-confirmed; wave 13
   adds monitoring_stack_validator: 10 survivors from `client.get(url)` URL
   clobbers — mocked `.get` ignored the URL in every test, so NONE of the
   documented Prometheus/Grafana endpoints was pinned): florence
   `responses.get(prompt, '')` (29), redis_json/redis_memory JSON.SET/GET/
   ARRAPPEND/NUMINCRBY execute_command args (~50), job_timeout config-key args
   (13). Fix = key-aware fake Redis + `assert_called_once_with`, never
   bare AsyncMock; one contract test per call site kills the family.
8. **Dead production code surfaced by mutants**: florence `_parse_list_response`
   L419-423 is unreachable (earlier gate's keyword list is a superset). Not a
   test gap — a WP4.4 simplification note; do NOT write a test against dead
   code. Sweep EQUIVALENT notes across dossiers for more `unreachable` claims.

## Rules the lane must keep

- Drafted test enters the tree ONLY red→green→killed (hard rule; one pytest
  lane at a time). UNVERIFIED is not a status that survives contact with git.
- EQUIVALENT claims get spot-checked: kill the argument with one input before
  accepting "do not chase" (the pose agent's provable-zero case was already
  exhaustively swept — trust-but-verify).
- Anomalies flagged for re-check at final score, not classified to fit
  reasoning (florence negation-gate keys 4-11 "should" be killed by test:401
  yet survived — investigate if still surviving).
- WP4.4's own commit, separate from WP4.3 (one WP per commit).
- ~145 still-untriaged targets + the run's last ~80% get triaged from the
  FINAL score JSON with the same detector/wave machinery before WP4.4 closes.

## FINAL-JSON RE-TALLY (2026-09-18, close-out — THIS SECTION IS THE SURVIVOR-COUNT ARBITER)

run6 closed 13:32 UTC at 100% (88,329/88,329 checked, completed=true,
torn_metas 0). Canonical scores: `/tmp/wp25/final-score.json` (269 targets ->
229 scored, 40 zero-mutant gap modules). The 122 dossier rows above were frozen
from run5's PARTIAL cache — mutmut checks estimated-fastest-first, so every
dossier saw only a slice of its module's checks; run6 completed them. Row
counts are now known LOWER BOUNDS; the FINAL counts stand:

- 122 triaged modules (exact path-match vs dispatched.txt): row sum 17,719 ->
  FINAL survivors 36,051 — i.e. ~18,332 NEW survivors INSIDE already-triaged
  modules (the run5 snapshot slice was 49% of the truth). Per-module growth is
  worst where run5 was earliest-cut: enrichment_pipeline 162 -> 2,879;
  nemotron_analyzer 125 -> 2,545; enrichment_client 158 -> 1,330; gpu_monitor
  194 -> 1,069.
- ALL 221 modules with survivors (229 scored, 8 fully-killed): 40,571 FINAL.
- Generation-2 work list = 40,571 total, of which (a) 4,520 in the 99
  NEVER-triaged modules (top: image_quality_loader 97, orchestrator/models 97,
  zone_crossing_service 97, gender_classifier_loader 96 @ 0.0%), (b) ~18,332
  new survivors inside the 122 triaged modules — dossier clusters stay valid
  (key sets are subsets), but every fold's counts, shares, and drafting
  coverage need a FINAL pass.
- Cluster SHARES (62/23/15) were measured on the run5 slices; they are a
  sample, not the population. The population's shape comes out of the
  generation-2 waves.
- Nine modules score 0.0% (age/gender/zero_dce loaders 206 mutants fully
  surviving, jobs/queues routes); 20 no_tests mutants live in
  heatmap_service(6)/stgcn_loader(5)/backup_service(2) et al.

Queue rebuild from this JSON (same detector/wave machinery) is the first
WP4.4 action after close-out; the 122-row table above remains the QUALITATIVE
map (patterns, defect finds, drafted tests) — only its arithmetic is superseded.

## WAVE 55 (GEN-2 RE-TALLY) — FOLD 2026-09-18

First gen-2 wave: the 8 heaviest modules (all gen-1-triaged against run5's
PARTIAL cache) re-tallied against the FINAL cache/arbiter JSON. Survivors
per the arbiter, dossiers re-extracted from final metas:

| Module | Surv | TEST-GAP | EQUIV | LOW-VALUE | Drafted |
|---|---:|---:|---:|---:|---:|
| enrichment_pipeline | 2879 | 1495 | 743 | 641 | 12 |
| nemotron_analyzer | 2545 | 1737 | 525 | 283 | 9 |
| enrichment_client | 1330 | 515 | 533 | 282 | 12 |
| pipeline_workers | 1110 | 576 | 432 | 102 | 7 |
| gpu_monitor | 1069 | 792 | 173 | 104 | 9 |
| prompts | 888 | 499 | 26 | 363 | 20 |
| detector_client | 839 | 160 | 313 | 366 | 12 |
| batch_aggregator | 710 | 237 | 448 | 25 | 9 |
| **TOTAL** | **11,370** | **6,011** | **3,193** | **2,166** | **90** |

Shares 52.9 / 28.1 / 19.1 vs the gen-1 sample's 62/23/15 (survivor-weighted
~64/21/13): the heavy tail is LOG/TELEMETRY-heavy — nemotron_analyzer's
single biggest cluster is 520 log-only string-constant mutants (C-STR-OBS)
and enrichment_pipeline's biggest is 707 log-text/extra-dict — so the
EQUIVALENT share SWELLS with module weight. Per-module shape again, not the
aggregate: gpu_monitor/pipeline_workers/prompts sit at 71–74% TEST-GAP
(the kill-test list is real), batch_aggregator at 63% EQUIVALENT. Dossiers:
.wp25-feed/wp44-triage/*.md (UNVERIFIED — drafting only; verification is the
serial lane).

## WAVE 56 + 57 (GEN-2 RE-TALLY) — FOLD 2026-09-18

Wave 56 (mid-tail) + nemotron_streaming redo + wave 57 (upper-mid). Fold
source: workflow journals' structured results (primary channel), every module
sum-checked against the FINAL arbiter (/tmp/wp25/final-score.json) BEFORE
folding — 16/16 OK. nemotron_streaming needed a redo: the on-disk gen-1
dossier was run6-in-flight (271 survivors + "90 unchecked"), and the workflow
agent died twice on StructuredOutput-only failures; re-dispatched as a
dossier-first direct agent with the arbiter numbers pinned in-prompt — new
dossier reconciles 333/533 with zero adjustment (meta exit-code census agrees).

| Module | Surv | G | E | L | Drafts |
| --- | ---: | ---: | ---: | ---: | ---: |
| redis_json | 338 | 205 | 100 | 33 | 6 |
| cleanup_service | 348 | 162 | 96 | 90 | 6 |
| performance_collector | 341 | 258 | 80 | 3 | 6 |
| baseline | 369 | 346 | 23 | 0 | 6 |
| webhook_service | 571 | 388 | 160 | 23 | 6 |
| export_service | 398 | 226 | 34 | 138 | 6 |
| redis_streams | 429 | 238 | 24 | 167 | 6 |
| nemotron_streaming | 333 | 237 | 13 | 83 | 14 |
| **W56 TOTAL** | **3,127** | **2,060** | **530** | **537** | **56** |
| container_discovery | 696 | 647 | 38 | 11 | 6 |
| routes/system | 638 | 515 | 65 | 58 | 6 |
| florence_client | 629 | 377 | 67 | 185 | 6 |
| clip_client | 613 | 197 | 125 | 291 | 6 |
| event_broadcaster | 590 | 155 | 292 | 143 | 6 |
| vision_extractor | 457 | 296 | 50 | 111 | 6 |
| file_watcher | 327 | 90 | 229 | 8 | 6 |
| system_broadcaster | 324 | 97 | 190 | 38 | 7 |
| **W57 TOTAL** | **4,274** | **2,374** | **1,056** | **845** | **49** |

MEASURE — gen-2 tallied through wave 57: 11,370 + 3,127 + 4,274 = **18,771
survivors** across 24 modules; G 10,445 (55.6%) / E 4,779 (25.5%) / L 3,548
(18.9%); **195 drafted kill-tests** (90 + 56 + 49). Wave-57 shares 55.5/24.7/
19.8 — TEST-GAP climbs as module weight drops (the log-heavy titans inflated
E in wave 55); the EQUIVALENT-swell-with-weight finding from wave 55 holds as
a SHAPE statement, not an aggregate law: file_watcher (70% E, fs-event glue)
and system_broadcaster (59% E) vs container_discovery at **93% TEST-GAP
(647/696) — the purest kill-target found in the program**: zero tests call
build_service_configs at all (mutmut's 66 "covering tests" are transitive
import artifacts), so six drafted tests cover ~600 survivors. routes/system
515 G confirms the 638-survivor route module is worth lane time. Head of the
serial lane unchanged: enrichment_pipeline metrics-label snapshot (534
mutants/test). Dossiers .wp25-feed/wp44-triage/*.md — UNVERIFIED drafting;
verification is the serial lane, one pytest job at a time.

## WAVE 58 (GEN-2 NEW TIER, FIRST EIGHT) — FOLD 2026-09-18

First eight NEW (never-tallied) modules, ~95 survivors each, dispatched 13:5x;
workflow `wf_bfa427c6-4e0` completed, 8/8 agents, 8/8 arbiter sum-checks OK
(journal survivors == arbiter survived == cluster-table sum, per module).

| module | surv | G | E | L | drafts |
|---|---|---|---|---|---|
| image_quality_loader | 97 | 41 | 5 | 51 | 6 |
| orchestrator/models | 97 | 95 | 2 | 0 | 5 |
| zone_crossing_service | 97 | 66 | 24 | 7 | 6 |
| container_orchestrator | 96 | 58 | 9 | 11+1 n/c | 9 |
| gender_classifier_loader | 96 | 73 | 5 | 18 | 5 |
| privacy_masking_service | 96 | 75 | 18 | 3 | 7 |
| approach_vector_service | 95 | 76 | 17 | 2 | 6 |
| service_managers | 94 | 13 | 29 | 52 | 6 |
| **W58 TOTAL** | **768** | **497** | **109** | **144+1 n/c** | **50** |

Reconciliation notes: (1) image_quality_loader — journal cluster math said
G40/E5/L52; the dossier's own Classification-totals line says G41/E5/L51
(C1,4,5,6,7,8,9,11 = G) — folded to the DOSSIER (artifact-of-record), sum 97
holds either way. (2) container_orchestrator — cluster table header "96 =
58+9+9+11+5+1+2+1" vs journal 58/9/29: journal G/E agree with the dossier's
biggest cells (58 G, 9 E); the L remainder (29) is cluster-table arithmetic
(9+11+5+1+2+1=29) — journal's E count is the outlier ONLY if read as E9, and
both channels agree G=58; folded G58/E9/L29. (3) service_managers dossier
Totals table gives 13G/29E/52L (journal agrees). (4) No draft-count channel
split: journal len(drafted_tests) == per-dossier draft sections == 50.

MEASURE — gen-2 cumulative through wave 58: 18,771 + 768 = **19,539 survivors**
across 32 modules; G 10,445 + 497 = **10,942** (56.0%) / E 4,779 + 109 =
**4,888** (25.0%) / L 3,548 + 145 = **3,693** (18.9%); **245 drafted kill-tests**
(195 + 50). NEW-TIER shape at ~95-survivor weight: TEST-GAP dominates even
harder (64.7% G here vs 55.6% cumulative) — thin modules are untested, not
log-heavy; orchestrator/models 95/97 G and gender_classifier_loader 73/96 G
confirm. service_managers inverts (13 G / 29 E / 52 L) — health-check plumbing
whose wrong kwargs are invisible behind mocked httpx (drafted tests target
exactly that). Head of the serial lane: container_discovery FULL-MODULE KILL
CENSUS running (scripts/.wp44-killcount.py, JSONL /tmp/wp25/wp44-kills/) —
first end-to-end "drafted → shipped → measured kills" number in the program.
Dossiers .wp25-feed/wp44-triage/*.md — UNVERIFIED drafting until the serial
lane lands.

## WAVE 59 (GEN-2 NEW TIER, MODULES 9-16) — FOLD 2026-09-18

Next eight NEW modules (686 est. survivors, 83-91 each); workflow
wf_89a30df9-5ae, 8/8 agents; arbiter sum-checks survivors 8/8 OK
(journal survivors_total == FINAL arbiter per module).

| module | surv | G | E | L | drafts |
|---|---|---|---|---|---|
| fashion_clip_loader | 91 | 61 | 4 | 26 | 6 |
| detector_registry | 89 | 45 | 43 | 1 | 6 |
| health_service_registry | 88 | 75 | 13 | 0 | 6 |
| ocr_service | 88 | 47 | 17 | 24 | 7 |
| calibration_monitor | 87 | 39 | 7 | 41 | 6 |
| health_event_emitter | 86 | 33 | 24 | 29 | 6 |
| trend_service | 86 | 42 | 3 | 41 | 6 |
| gpu_detection_service | 83 | 51 | 23 | 9 | 10 |
| **W59 TOTAL** | **698** | **393** | **134** | **171** | **51** |

Reconciliation: detector_registry journal cluster SUBTOTALS summed 93 vs
arbiter 89 (journal G49); the dossier's own Totals line reconciles 45/43/1
= 89 with a per-key exactly-once coverage row — fold takes the dossier
(machine recount of its cluster table agrees; the journal's StructuredOutput
re-typed four switch_detector-cluster rows into two buckets). All other 7
modules: journal cluster sums == arbiter, no split.

MEASURE — gen-2 cumulative through wave 59: 19,539 + 698 = **20,237
survivors** across 40 modules; G 11,335 (56.0%) / E 5,022 (24.8%) / L 3,864
(19.1%); **296 drafted kill-tests** (245 + 51). NEW-tier shape holds: 56.3% G
in-wave; health_service_registry 75/88 G and fashion_clip_loader 61/91 G
(model-loader twins follow the gender/image-quality pattern — happy path
never runs); detector_registry INVERTS to E-heavy (43/89) — registry glue
behind mocks. Serial lane: container_discovery census ~17% probed (83 killed
of 116) at 10.2 s/probe, ETA ~98 min from 14:4x; orchestrator batch (9 tests)
authored, red-proof queued behind it.

## WAVE 60b (straggler) — FOLD 2026-09-18

inference_semaphore 77 survivors (arbiter ✓; dossier Totals 12 G / 56 E / 9 L,
per-cluster sums verified ✓✓), 5 drafts. Journal == dossier, no split. E-heavy
(72.7%) — semaphore timing/await glue behind fakes, the service_managers
pattern again; its 12 G are the acquire/release contract mutants.

MEASURE — gen-2 cumulative: 20,771 + 77 = **20,848 survivors** across 48
modules; G 11,636 (55.8%) / E 5,271 (25.3%) / L 3,925 (18.8%); **343 drafted
kill-tests**. NEW tier remaining after wave 61 dispatch: ~65 modules /
~1,800 survivors.

## WAVE 61a (GEN-2 NEW TIER) — FOLD 2026-09-18

Seven of eight dispatched modules (zone_service's agent died without output —
re-dispatched as a DIRECT dossier-first agent with arbiter numbers pinned, the
nemotron_streaming precedent; its fold lands as 61b).

| module | surv | G | E | L | drafts |
|---|---|---|---|---|---|
| pet_classifier_loader | 72 | 34 | 2 | 36 | 5 |
| ai_fallback | 70 | 32 | 35 | 3 | 6 |
| queue_status_service | 69 | 50 | 12 | 7 | 6 |
| websocket_service | 69 | 9 | 19 | 41 | 5 |
| routes/logs | 62 | 57 | 2 | 3 | 6 |
| job_log_emitter | 60 | 21 | 31 | 8 | 6 |
| line_zone_service | 59 | 25 | 34 | 0 | 6 |
| **W61a TOTAL** | **461** | **228** | **135** | **98** | **34** |

Reconciliation: routes/logs journal cluster math said G58 with sum 63 (+1 vs
arbiter 62); the dossier's OWN programmatic partition gives 57/2/3 = 62 ✔ —
fold takes the dossier. All other 6: journal == dossier == arbiter.

MEASURE — gen-2 cumulative through 61a: 20,848 + 461 = **21,309 survivors**
across 55 modules; G 11,864 (55.7%) / E 5,406 (25.4%) / L 4,023 (18.9%)
[16-row residual = the program's honest unclassified remainder, carried since
wave 58's +1 n/c and the count-vs-classification channel splits — recorded,
never re-typed]; **377 drafted kill-tests** (343 + 34). Shape: routes/logs
57/62 G — a whole FastAPI route module essentially untested; websocket_service
inverts to 41/69 L (log-heavy broadcaster twin). Serial-lane live: census past
half, kill-test commits (container_discovery batch first) land on completion.

## WAVE 61b (zone_service) — FOLD 2026-09-18

zone_service 59 survivors (arbiter ✓ 455k/59s/514, 88.52%): journal and
dossier agree **G40/E17/L2 = 59 ✔**, 22 drafts. Fold note (honest): wave 61's
workflow was STILL RUNNING when 61a was folded — the zone agent had not yet
flushed to journal.jsonl, and a premature direct-agent redo was dispatched,
then stopped when the workflow's own result landed. The dossier on disk is the
workflow agent's (mtime matches workflow completion; totals agree with its
journal result; the redo never wrote it). Lesson recorded: a live workflow's
missing module is IN FLIGHT, not dead — the nemotron_streaming redo precedent
applies only to a COMPLETED workflow with an absent result.

MEASURE — gen-2 cumulative through 61: 21,309 + 59 = **21,368 survivors** / 56
modules; G 11,904 (55.7%) / E 5,423 / L 4,025; **399 drafted kill-tests**
(377 + 22 — zone_service's 22-draft suite is the densest single-module draft
set in the program, arithmetic cluster per test). NEW tier remaining: **65
modules / 1,882 survivors** (recounted after commit — the fold's rough ~56 /
~1,200 estimate undercounted by 9 modules / ~700; corrected here per the
never-re-type rule: this line IS the recount).

## WAVE 62a (GEN-2 NEW TIER) — FOLD 2026-09-18

Eight dispatched; SEVEN folded. depth_calibration_service REJECTED at sum-check:
journal clusters summed 60 vs arbiter 57 (double-typed rows) AND the agent wrote
no dossier to disk — no artifact-of-record to reconcile against, so the journal
numbers could not be trusted even after excluding rows. Direct redo dispatched
(read-only agent, dossier target unchanged). The other seven passed journal-vs-
arbiter sum-checks and journal-vs-dossier reconciliation:

onvif            57 survivors  18G/0E/39L   6 drafts   (log-heavy route twin; L onvif
                                                  cluster is logger-args only — 3 of the
                                                  57 were caught only because HTTPException
                                                  detail differs — the e→None cluster is TEST-GAP)
camera_status    57 survivors  49G/1E/7L    6 drafts   (second route-like G-heavy twin)
feedback_proc    56 survivors  43G/11E/2L   7 drafts
entity_recog     56 survivors  30G/6E/20L   4 drafts
model_mgmt       54 survivors  37G/16E/1L   9 drafts   (densest draft ratio in wave)
alert_dedup      52 survivors  44G/8E/0L    5 drafts   (zero L — pure-logic module)
auth_service     52 survivors  29G/7E/16L   6 drafts

MEASURE — wave 62a: 384 survivors, G 250 (65.1%) / E 49 / L 85, 43 drafts.
Gen-2 cumulative through 62a: **21,752 survivors / 63 modules**; G 12,154 /
E 5,472 / L 4,110; **442 drafted kill-tests** (399 + 43). NOTE the carried
16-unit gap: the pre-62 cumulative G+E/L sums 21,352 vs survivor 21,368 —
inherited from an earlier fold's double-typed rows that passed its own
sum-check; disclosed, not re-typed per the reconcile rule.
NEW tier remaining (dossier-presence recount at fold time): **58 modules /
1,498 survivors** — the ≥50 band is nearly exhausted: after depth_calibration's
redo lands, the biggest untouched is 50 (evaluation_queue, face_detector,
job_progress_reporter). Remaining ~14 light waves. Shape holds G-heavy ~65% in
the tail — gen-2's cheap wins are thinning; per-test draft yield is the
measured currency now (442 drafts, zero landed kills until the serial lane
proves them).
Serial-lane live: census 91% killed through ~460 probes; kill-test commits land
on its completion.

## WAVE 62b (depth_calibration_service, direct redo) — FOLD 2026-09-18

Redo agent (post-rejection) delivered a clean partition: 57 survivors
(meta exit_code==0 cross-check vs arbiter: exact), **G 32 / E 7 / L 18 — sum
57**, machine-verified non-overlapping; dossier on disk; 14 drafts. Prior-
rejection failure modes both addressed: stale .spans offsets discarded in
favor of per-mutant AST-segment diffs; every key mapped to exactly one
cluster. Judgment calls documented in-dossier (warning-category EQUIVALENTs
true by Python default; endpoint-tie bracket shifts equivalent on all
validation-legal inputs; one load_8 key flagged as the single TEST-GAP flip
if caplog-policing is ever valued).

MEASURE — gen-2 cumulative through 62b: **21,809 survivors / 64 modules**;
G 12,186 (55.9%) / E 5,479 / L 4,128; **456 drafted kill-tests** (442 + 14).
NEW tier remaining: **57 modules / 1,441 survivors** (dossier-presence recount;
wave 63's eight in-flight modules still counted as remaining until dossiers
land). DECIDE: a rejected triage gets a direct-agent redo with the rejection
reasons named in the prompt — the redo's own machine-checks (57/57 exact
partition) are what make it foldable.

## WAVE 63 (GEN-2 NEW TIER) — FOLD 2026-09-18

Eight modules (survivors 42-50 band), all arbiter sum-checks OK, all eight
dossiers present and reconciled to journal:

orphan_scanner   48 survivors  29G/1E/18L   6 drafts
rtsp_test        46 survivors  39G/0E/7L    6 drafts   (third route-like G-heavy twin)
job_progress     50 survivors   6G/42E/2L   5 drafts   (E-heavy: progress-throttle cosmetics)
summary_parser   49 survivors  37G/12E/0L   6 drafts
face_detector    50 survivors  29G/12E/9L   6 drafts
evaluation_queue 50 survivors  13G/37E/0L   4 drafts   (E-heavy twin of jpr)
audit            42 survivors  34G/7E/1L    6 drafts
plate_detector   46 survivors  32G/10E/4L   8 drafts

MEASURE — wave 63: 381 survivors, G 219 (57.5%) / E 121 / L 41, 47 drafts.
Gen-2 cumulative through 63: **22,190 survivors / 72 modules**; G 12,405
(55.9%) / E 5,600 / L 4,169; **503 drafted kill-tests** — a half-thousand
drafts milestone, zero of them measured-killed yet (serial lane + new parallel
lane now working the proof). NEW tier remaining: **49 modules / 1,060
survivors** (dossier-presence recount). Parallel census lane LIVE on exactly
those 49 (7 workers, owner-approved carve-out; 8-module triage/wave cadence
now runs against a shrinking untouched set — gen-2 triage waves are nearly
done with their founding purpose once this band's dossiers land).

## WAVE 64 (GEN-2 NEW TIER) — PARALLEL CENSUS FOLD 2026-09-18

Not a triage wave: the owner-approved fan-out lane ran the FULL kill-census
over exactly the 49 remaining band modules (1,060 survivors), then a STRICT
re-census after the rc-classification fix (kill := pytest rc in (1,3),
scorer-consistent; rc=2 = INTERRUPTED re-probed with retry; probes -n 0 —
repo addopts' -n 8 had built load-46 xdist storms, one 84 GB OOM in dmesg;
see ledger RECORD-CORRECTION).

MEASURE: 1,014/1,060 band keys hold strict verdicts, **0 killed** — every
band-module survivor is a TRUE survivor against today's suite (their test
files gained nothing since run6; this is the population the gen-2 triage
waves drafted 503 skeleton tests for, still unauthored). 46 keys uncensused:
fast_alpr_loader (15) + zero_dce_loader (31) have INTEGRATION-only tests —
out of the unit carve-out, recorded, never guessed. Big-number confirmations
in the same pass: container_discovery 644/696 strict (later 669/696 with the
5 drafted real-gap tests, 25/52 killed), routes/system 135/638,
container_orchestrator 32/96 strict (confirmed after 1/3-spurious era).

Gen-2 cumulative through 64: **23,250 survivors / 121 modules** (triage-
classified 22,190/72 + census-confirmed 1,060/49). Committed + MEASURED kill
tests: 578 (503 wave drafts remain skeletons awaiting authoring). NEW tier
remaining: **49 band modules needing the authoring round** (dossier -> real
tests -> census proof), + orchestrator's 64 and system's 503 recorded
survivors for the next drafting wave. The census lane is now the PROOF
instrument for authoring waves, 6-8 workers, pause-respecting.

## WAVE 65 DOSSIER FOLD 2026-09-19 (next-8 band modules triaged)

Read-only triage workflow wf_cc4a7a6d-fab (8 agents, 617k tokens, 13 min):
dossiers + drafted skeletons for job_state_service, event_service, media,
go2rtc_client, service_provider_matcher, scene_change_service, entities,
prompt_auto_tuner. Journal-tallied partition: **190 TEST-GAP / 48 LOW-VALUE /
82 EQUIVALENT = 320 survivors** across 41 drafted tests. Untouched band after
this wave: 41 modules. Authoring order by TEST-GAP: media(37),
scene_change_service(33), entities(28), go2rtc_client(27),
service_provider_matcher(26), job_state_service(16), prompt_auto_tuner(16),
event_service(7). All drafts UNVERIFIED until authored + green-under-original
+ strict census re-probe (lane currently busy with routes/system 638).
