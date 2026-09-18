# WP4.4 verification queue — triage dossiers, ordered

Source: read-only survivor triage during run5 (baseline in progress, 2026-09-17).
Each dossier = `/tmp/wp25/wp44-triage/<module>.md`: cluster table (TEST-GAP /
EQUIVALENT / LOW-VALUE with example mutant keys) + drafted pytest tests marked
UNVERIFIED. Verification lane (serial, after run5 exits): for each draft —
red on the mutant diff → green on original → commit into that WP's tests.
EQUIVALENT/LOW-VALUE cluster notes are the no-deletion-without-record receipts.

Aggregate at 114 modules / 16587 survivors: TEST-GAP 10479 survivors (63%),
EQUIVALENT 3634 (22%), LOW-VALUE 2419 (15%); 747 drafted tests.
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
|       79 |  135 |    59% | `insight_generator`              |      7 |
|       78 |  107 |    73% | `debug`                          |      5 |
|       78 |  112 |    70% | `batch_coalescer`                |      6 |
|       78 |  185 |    42% | `model_zoo`                      |     13 |
|       77 |  116 |    66% | `vehicle_classifier_loader`      |      6 |
|       77 |  141 |    55% | `notification`                   |      6 |
|       74 |  167 |    44% | `detector_client`                |      7 |
|       74 |  203 |    36% | `batch_aggregator`               |      6 |
|       73 |  101 |    72% | `websocket_emitter`              |      6 |
|       71 |  108 |    66% | `transcoding_service`            |      6 |
|       71 |  139 |    51% | `vehicle_damage_loader`          |      7 |
|       71 |  152 |    47% | `transcoding`                    |      6 |
|       70 |  107 |    65% | `performance_collector`          |      6 |
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
|       28 |  101 |    28% | `alert_service`                  |      6 |
|       28 |  105 |    27% | `cleanup_service`                |      6 |
|       27 |  111 |    24% | `calibration_service`            |      4 |
|       25 |  104 |    24% | `file_watcher`                   |      6 |
|       14 |  134 |    10% | `household_matcher`              |      6 |
|       13 |  104 |    12% | `event_broadcaster`              |      7 |
|       13 |  125 |    10% | `registry`                       |      3 |

Wave-23 tail — system.py folded separately (the giant-module fix): 5,624
lines / 1,899 mutants is why the first-slot agent died twice WITHOUT a dossier
— one agent, one file, too much. Resume re-ran it solo -> 166/187 TEST-GAP
(89%, row 7 of 114, top routes/ module, behind four services): the /system/health
exporter-status builder matches Prometheus targets by `job/instance in`
(56 mutants) under a test that asserts only status.value=='up'; degradation
payload keys/defaults 52 mutants (`mode` default -> response becomes None via
a swallowed ValueError); monitoring-issue messages any().lower()-substring
only. Health-endpoint contract = pattern 6 on the dashboard's OWN status page.
Lane note: dispatch >1,200-mutant files as single-module waves.

Wave-40 anchor (04:02-04:15 UTC, 1 module): exports (54 gap/100, 54%,
row 93) is the EXPORT-JOB ROUTE contract: the whole job_tracker call
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
row 88) — the NEM-4474 atomic-Lua store path is ENTIRELY unexercised (all
tests pass a bare AsyncMock so use_atomic is always False — mock-absorption again,
7 mutants) and get_entity_history's today/yesterday Redis date-keys are built
under call-count side_effects that ignore the key (13 mutants; wrong keys
silently return [] in prod). reset_reid_service's None->"" mutant slips past an
identity test; format_full_reid_context's "No "-section suppression is never
fed an empty-match dict (14 header-leak mutants). 7 drafts (T1-T7). Cluster-
sum check regenerated mechanically: 109 = 58+12+39, matches live meta exactly.

Wave-42 anchor (05:02-05:14 UTC, 1 module): summary_generator (89 gap/131, 68%,
row 52) — call-arg forwarding at scale: window_start/window_end/period_type/
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
43%, row 85) — shipped-behavior headliner: _handle_stopped_container's
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
row 47) — the endpoint-with-status-only-assertion shape at gpu_config scale but
smaller: payload/degradation fields flow unobserved. retry_handler (54 gap/151,
36%, row 94) — 62% LOW-VALUE (94): the module's own retry-log prose; the real
work is the backoff/budget arithmetic. cameras (44 gap/130, 34%, row 99) —
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
TEST-GAP, not LOW-VALUE). model_zoo (78 gap/185, 42%, row 64) — 56%
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
118, 49%, row 89) — the most telemetry-saturated module triaged yet: 47%
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
24%, row 111) — 73% EQUIVALENT, the purest log-prose module triaged (start/
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
gap/170, 40%, row 77) is the DELETIVE-FILE-SERVICE risk class: age-unit
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
47%, row 72) is the ffmpeg-plumbing gap — argv construction, availability
probe, stderr-tail failure message (boundary >5 vs >6 lines) and
get_video_info defaults all unobserved; dossier adds a PRODUCT NOTE:
\_validate_input_path's dash check is unreachable after resolve() (dead
code, same family as florence's \_parse_list_response). smoke_fire_loader
(66 gap/135, 49%, row 81) is the MOCK-ABSORPTION textbook: YOLO patched
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
69%, row 74) is UNOBSERVED-REPORT-FIELD gap: the WarmingReport/WarmingResult
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
(43 gap/111, 39%, row 100) is log-noise-dominant (42 LOW-VALUE — extra=
payloads + message renames) with real gaps under it: the progress message
and processed/failed counters ride GET /batch/{job_id} while tests assert
only the percentage, an == -> != query flip survives on a call-order mock
session, and three nullable response fields are never asserted. Cluster
table, journal AND Totals line agreed for both modules (first full
three-channel agreement — recorded, not assumed).

Wave-33 anchors (02:23-03:00 UTC, 2 modules): osnet_loader (88 gap/136,
65%, row 53) — the segformer wide-except-crash-swallow pattern lands on the
embedding model's loader (blanket except -> degraded/empty result turns
mutation breakage into silent model degradation); dossier Totals line again
contradicted its own table (86/13 vs table+journal 88/11 — table folded).
mqtt_publisher (37 gap/100, 37%, row 104) is the MQTT WIRE-CONTRACT gap: the
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
72%, row 69) is pattern 6 at the LAST dispatch hop: every
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
reid_matcher (58/100, 58%, row 87) is the SQLAlchemy statement-inspection
hole — find_matches WHERE/ORDER BY/cutoff bind params invisible under
execute.called-only tests (same family as w25 search's bind-params, but the
predicates DO render: kill by compiling the executed stmt).

Wave-28 anchor (00:22-00:40 UTC, 1 module): detections (60 gap/157,
38%, row 86) — highest EQUIVALENT share of any routes/ module (78/157, 50%):
falsy-default swaps (get(k,{})→None), key-rename reads whose canonical
lowercase consumer never sees them, and header-case variants starlette
normalizes away. The 60 gap rows cluster in the ENRICHMENT-PAYLOAD contract:
has_damage/is_commercial/is_suspicious/violence/face/image_quality defaults
flip False→True silently or →None (pydantic 500) whenever a fixture omits the
key — and every existing fixture omits exactly those keys; vehicle_damage
flag flip rides the same hole.

Wave-27 anchor (00:10-00:40 UTC, 1 module): transcoding_service (71 gap/
108, 66%, row 70) is the ffmpeg-ARGV family — both subprocess call sites are
mocked with call-count-only asserts, so 42 argv-token + stdout/stderr=PIPE
mutations survive (no stderr pipe destroys the TranscodingError diagnostic);
boundary + age-window arithmetic (1000-byte cache validity, max_age_days
factor chain) never probed because fixtures avoid every boundary; the
option-injection guard in \_validate_video_path (startswith("-")) becomes dead
code under 2 mutants — security check with zero teeth-tests.

Wave-26 anchors (23:45-00:10 UTC, 2 modules — endpoint + client noise
shape): gpu_config (81 gap/111, 73%, row 56) is the status-code-only-asserted
endpoint at scale — every \_calculate_auto_assignments strategy (MANUAL/
VRAM_BASED/BALANCED/ISOLATION_FIRST/LATENCY) survives full placement clobbers
because tests assert len>=3, never the map; its SYMMETRIC-FIXTURE ABSORPTION
family = mock-absorption's twin — LATENCY sort flips are test-no-ops while
every fixture GPU shares compute_capability '8.6' (a tie swallows the
mutation before any assert); \_update_gpu_devices_in_db survives on
commit.called-once alone. clip_client (69/220, 31%, row 75) is the wave's
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
75%, row 5 of 114, behind container_discovery, llm_reasoning and nemotron_streaming — 244 survivors, the wave's biggest) is the canned-DB-mock shape at scale:
`session.execute` returns AsyncMock whatever statement it's handed, so the
cooldown cutoff arithmetic / dedup `==` / `>=` / LIMIT all ride; the
alert.created WEBSOCKET payload (36 mutants, 24 key renames) and the webhook
payload (22 key renames) are NEVER OBSERVED by any test — pattern 6 again, on
the two wires out of the alert pipeline; T1 kills the cooldown family with a
REAL DB, no mocks. debug (78/107, 73%) is second routes/ module:
redis-info dict + pubsub payload only membership-asserted; the ltrim
off-by-one `start 0->1` DISCARDS every recorded pipeline error while
returning True. scene_baseline (89/101, 88%, row 51) sharp gap. prompt_storage
(93/104, 89%, row 45, 13 drafts — program record) is the cleanest module shape:
ZERO log surface means zero LOW-VALUE noise, every mutant caller-observable;
naive-`now()` timestamp leak (T2) is the shipped-behavior note. batch_aggregator
(row 68; 74 gap/203) is the wave's noise anchor: 125 EQUIVALENT (62%) — a
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
