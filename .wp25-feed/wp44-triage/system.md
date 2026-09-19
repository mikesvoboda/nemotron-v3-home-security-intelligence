# WP4.4 triage dossier — backend/api/routes/system.py surviving mutants

**Generated:** 2026-09-19 (triage wave; a live mutation run owns the machine — nothing executed, nothing in the repo modified)
**Verdict source:** `mutants/backend/api/routes/system.py.meta` — 638 keys with exit_code==0 of 1899 total (1261 killed, 0 unchecked). **survivors_total = 638.**
**Overlap note:** commit `cdf32a4f` (routes/system kill-test batch) already probed 135 of these 638 — the post-batch ledger `.wp25-feed/wp44-kills/system-survivors.md` lists 503 still-open. The `open` column below marks per-cluster how many keys are still in that ledger; drafting priority follows it. Already-killed clusters are retained so counts sum to 638 exactly (partition machine-verified: 638/638, 0 dup, 0 missing).

## Diff extraction method
Mutant copy `mutants/backend/api/routes/system.py` holds one trampoline block per mutant (`def <name>__mutmut_orig/_N`). Every survivor was mechanically diffed against its `__mutmut_orig` body (unified diff, def-line and bare-paren noise stripped, paren-balanced multi-line signatures) — cross-verified against `uv run mutmut show` for `_check_ai_service_health__mutmut_10` and the `CircuitBreaker` keys. `XX…XX` in a string = mutmut's clobber convention. Cluster = same mutated function + same statement/field/arg concern; ≤3 example keys each.

## Tallies
| class | clusters | survivors | still-open (post-cdf32a4f) |
|---|---|---|---|
| TEST-GAP | 70 | 492 | 363 |
| LOW-VALUE | 27 | 92 | 89 |
| EQUIVALENT | 16 | 54 | 51 |
| **total** | **113** | **638** | **503** |

## Notable classification judgments
- **`_parse_prometheus_timestamp` ns-truncation branch (13, EQUIVALENT):** every survivor mutates only the `if "." in ts_str` nanosecond-truncation path (`split(None)`, `len(parts)==3`, `rstrip("z")`, slice `[:7]` …), but Python ≥3.11 `datetime.fromisoformat` accepts arbitrary-precision fractions natively — both the branch and the pass-through parse to the identical datetime, so all 13 are output-equivalent in this environment (CI 3.14.2 / sandbox 3.14.4). Truly unkillable here.
- **Kwarg-removal mutants matching a schema default (EQUIVALENT):** dropping `details=None`, `batches=[]`, or `circuit_state=CircuitState.CLOSED` is bit-equivalent because pydantic supplies the same value (`AIServiceHealthStatus.circuit_state` default=CLOSED, `BatchAggregatorStatusResponse.batches` default_factory=list, `details` default None). Same for `_check_postgres_health_full` `_ = result.scalar()` → `_ = None` (result unused; the awaited execute() already performed the probe) and `_write_runtime_env` `encoding="utf-8"`→`"UTF-8"` (alias).
- **Falsy-default swaps (mixed):** `manager_status.get("running", False)`→None/omitted is EQUIVALENT (consumer re-defaults via `if not …`), but `getattr(_gpu_monitor, "running", False)`→None/omitted is **TEST-GAP** because the value lands in the `bool`-typed `WorkerStatus.running` field → ValidationError on the whole `/system/health` payload — asserted nowhere.
- **httpx `timeout=None` + `duration = time.time() + start_time` + `observe_health_check_component_latency("database"→"DATABASE")` (LOW-VALUE):** real behavior changes (no client timeout, garbage durations, wrong Prometheus label), but the duration/labels are only observable in the metrics registry; not worth asserting at route-test level.
- **message/error-text case & clobber mutants (LOW-VALUE):** substring asserts exist (`test_system_routes.py:99-100` `"unavailable" in message.lower()`); exact prose equality is low value. Note the *value-changing* string flips (`"unknown"`→`"UNKNOWN"` in `redis_version` details) are TEST-GAP — that string ships in the API payload.
- **`x__are_critical_pipeline_workers_healthy__mutmut_20`** (default→True): the existing `test_critical_workers_partial_manager_status` kills it (absent from the post-batch ledger); it remains TEST-GAP in this verdict snapshot.
## Per-cluster table

| cluster (function::concern) | class | n | open | example keys | covering test file(s) |
|---|---|---|---|---|---|
| x__get_degradation_status::response field lookup key/default mutated | TEST-GAP | 54 | 11 | x__get_degradation_status__mutmut_100, x__get_degradation_status__mutmut_101, x__get_degradation_status__mutmut_11 | tests/unit/api/routes/test_system.py |
| x__get_model_display_name::display-name map entry mutated | TEST-GAP | 40 | 40 | x__get_model_display_name__mutmut_10, x__get_model_display_name__mutmut_11, x__get_model_display_name__mutmut_12 | tests/unit/api/routes/test_system_models.py |
| x_get_latest_gpu_stats::gpu payload dict key mutated | TEST-GAP | 38 | 38 | x_get_latest_gpu_stats__mutmut_26, x_get_latest_gpu_stats__mutmut_27, x_get_latest_gpu_stats__mutmut_28 | tests/unit/api/routes/test_system.py; tests/unit/routes/test_system_routes.py |
| x_check_database_health::pool metric key/default mutated | TEST-GAP | 33 | 33 | x_check_database_health__mutmut_22, x_check_database_health__mutmut_24, x_check_database_health__mutmut_27 | tests/unit/api/routes/test_system.py; tests/unit/routes/test_system_routes.py |
| x_check_redis_health::error/version details payload mutated | TEST-GAP | 25 | 25 | x_check_redis_health__mutmut_13, x_check_redis_health__mutmut_14, x_check_redis_health__mutmut_15 | tests/unit/api/routes/test_system.py; tests/unit/routes/test_system_routes.py |
| x__get_worker_statuses::pipeline worker dict key/default mutated (lookup falls to default) | TEST-GAP | 23 | 13 | x__get_worker_statuses__mutmut_106, x__get_worker_statuses__mutmut_108, x__get_worker_statuses__mutmut_117 | tests/unit/api/routes/test_system.py; tests/unit/routes/test_system_routes.py |
| x__emit_health_status_changes::update_all_components statuses/details payload mutated | TEST-GAP | 19 | 19 | x__emit_health_status_changes__mutmut_10, x__emit_health_status_changes__mutmut_11, x__emit_health_status_changes__mutmut_12 | tests/unit/routes/test_system_routes.py |
| x__check_ai_service_health::last_check kwarg removed/forced None | TEST-GAP | 18 | 18 | x__check_ai_service_health__mutmut_101, x__check_ai_service_health__mutmut_109, x__check_ai_service_health__mutmut_117 | tests/unit/api/routes/test_health_full.py |
| x__get_worker_statuses::message kwarg dropped/forced None | TEST-GAP | 17 | 4 | x__get_worker_statuses__mutmut_100, x__get_worker_statuses__mutmut_101, x__get_worker_statuses__mutmut_195 | tests/unit/api/routes/test_system.py; tests/unit/routes/test_system_routes.py |
| x__build_exporter_status::exporter match target key/default mutated | TEST-GAP | 13 | 7 | x__build_exporter_status__mutmut_11, x__build_exporter_status__mutmut_12, x__build_exporter_status__mutmut_13 | tests/unit/api/routes/test_system.py |
| x__parse_prometheus_timestamp::nanosecond-truncation branch mutated — dead under py>=3.11 fromisoformat | EQUIVALENT | 13 | 13 | x__parse_prometheus_timestamp__mutmut_10, x__parse_prometheus_timestamp__mutmut_11, x__parse_prometheus_timestamp__mutmut_13 | tests/unit/api/routes/test_system.py |
| x__check_ai_service_health::response_time_ms kwarg mutated | TEST-GAP | 12 | 12 | x__check_ai_service_health__mutmut_100, x__check_ai_service_health__mutmut_106, x__check_ai_service_health__mutmut_114 | tests/unit/api/routes/test_health_full.py |
| x__get_worker_statuses::getattr running default False->None/omitted (WorkerStatus.running=None) | TEST-GAP | 12 | 3 | x__get_worker_statuses__mutmut_12, x__get_worker_statuses__mutmut_31, x__get_worker_statuses__mutmut_34 | tests/unit/api/routes/test_system.py; tests/unit/routes/test_system_routes.py |
| x__build_exporter_status::lastError lookup key mutated (error field lost) | TEST-GAP | 11 | 0 | x__build_exporter_status__mutmut_68, x__build_exporter_status__mutmut_69, x__build_exporter_status__mutmut_70 | tests/unit/api/routes/test_system.py |
| x__check_ai_service_health::url kwarg removed/forced None | TEST-GAP | 11 | 11 | x__check_ai_service_health__mutmut_105, x__check_ai_service_health__mutmut_113, x__check_ai_service_health__mutmut_127 | tests/unit/api/routes/test_health_full.py |
| x__build_exporter_status::endpoint kwarg forced None/removed | TEST-GAP | 8 | 0 | x__build_exporter_status__mutmut_101, x__build_exporter_status__mutmut_82, x__build_exporter_status__mutmut_87 | tests/unit/api/routes/test_system.py |
| x__build_exporter_status::exporter match key/needle clobbered (breaks dash/underscore fold) | TEST-GAP | 8 | 5 | x__build_exporter_status__mutmut_10, x__build_exporter_status__mutmut_17, x__build_exporter_status__mutmut_19 | tests/unit/api/routes/test_system.py |
| x__build_exporter_status::last_scrape kwarg forced None/removed | TEST-GAP | 8 | 1 | x__build_exporter_status__mutmut_102, x__build_exporter_status__mutmut_62, x__build_exporter_status__mutmut_63 | tests/unit/api/routes/test_system.py |
| x__check_ai_service_health::circuit breaker name lookup mutated | TEST-GAP | 8 | 8 | x__check_ai_service_health__mutmut_10, x__check_ai_service_health__mutmut_11, x__check_ai_service_health__mutmut_12 | tests/unit/api/routes/test_health_full.py |
| x__check_ai_health_with_timeout::prometheus component label mutated | LOW-VALUE | 6 | 6 | x__check_ai_health_with_timeout__mutmut_13, x__check_ai_health_with_timeout__mutmut_14, x__check_ai_health_with_timeout__mutmut_17 | tests/unit/routes/test_system_routes.py |
| x__check_db_health_with_timeout::prometheus component label mutated | LOW-VALUE | 6 | 6 | x__check_db_health_with_timeout__mutmut_10, x__check_db_health_with_timeout__mutmut_14, x__check_db_health_with_timeout__mutmut_15 | tests/unit/routes/test_system_routes.py |
| x__check_nemotron_health::error return text cosmetic | LOW-VALUE | 6 | 6 | x__check_nemotron_health__mutmut_10, x__check_nemotron_health__mutmut_11, x__check_nemotron_health__mutmut_12 | tests/unit/routes/test_system_routes.py |
| x__check_redis_health_with_timeout::prometheus component label mutated | LOW-VALUE | 6 | 6 | x__check_redis_health_with_timeout__mutmut_10, x__check_redis_health_with_timeout__mutmut_14, x__check_redis_health_with_timeout__mutmut_15 | tests/unit/routes/test_system_routes.py |
| x__check_yolo26_health::error return text cosmetic | LOW-VALUE | 6 | 6 | x__check_yolo26_health__mutmut_10, x__check_yolo26_health__mutmut_11, x__check_yolo26_health__mutmut_12 | tests/unit/routes/test_system_routes.py |
| x__identify_monitoring_issues::issue message text cosmetic | LOW-VALUE | 6 | 6 | x__identify_monitoring_issues__mutmut_16, x__identify_monitoring_issues__mutmut_17, x__identify_monitoring_issues__mutmut_18 | tests/unit/api/routes/test_system.py |
| x_get_latest_gpu_stats::latest-row query mutated | TEST-GAP | 6 | 6 | x_get_latest_gpu_stats__mutmut_1, x_get_latest_gpu_stats__mutmut_2, x_get_latest_gpu_stats__mutmut_3 | tests/unit/api/routes/test_system.py; tests/unit/routes/test_system_routes.py |
| x__are_critical_pipeline_workers_healthy::falsy default swaps on manager_status.get (None/omitted) | EQUIVALENT | 5 | 2 | x__are_critical_pipeline_workers_healthy__mutmut_15, x__are_critical_pipeline_workers_healthy__mutmut_17, x__are_critical_pipeline_workers_healthy__mutmut_20 | tests/unit/api/routes/test_system.py; tests/unit/routes/test_system_routes.py |
| x__build_exporter_status::exporter status mutated | TEST-GAP | 5 | 3 | x__build_exporter_status__mutmut_105, x__build_exporter_status__mutmut_106, x__build_exporter_status__mutmut_38 | tests/unit/api/routes/test_system.py |
| x__check_ai_service_health::circuit_state kwarg removed (default==CLOSED) | EQUIVALENT | 5 | 5 | x__check_ai_service_health__mutmut_116, x__check_ai_service_health__mutmut_136, x__check_ai_service_health__mutmut_154 | tests/unit/api/routes/test_health_full.py |
| x__emit_health_status_changes::emitter wiring branches mutated | TEST-GAP | 5 | 5 | x__emit_health_status_changes__mutmut_1, x__emit_health_status_changes__mutmut_2, x__emit_health_status_changes__mutmut_3 | tests/unit/routes/test_system_routes.py |
| x__get_degradation_status::log-call text arg mutated | LOW-VALUE | 5 | 5 | x__get_degradation_status__mutmut_102, x__get_degradation_status__mutmut_103, x__get_degradation_status__mutmut_105 | tests/unit/api/routes/test_system.py |
| x__identify_monitoring_issues::all-down/partial-down threshold mutated | TEST-GAP | 5 | 5 | x__identify_monitoring_issues__mutmut_12, x__identify_monitoring_issues__mutmut_13, x__identify_monitoring_issues__mutmut_7 | tests/unit/api/routes/test_system.py |
| x__stats_to_schema::empty-samples guard mutated | TEST-GAP | 5 | 5 | x__stats_to_schema__mutmut_2, x__stats_to_schema__mutmut_3, x__stats_to_schema__mutmut_4 | tests/unit/core/test_metrics.py |
| x_check_database_health::error details payload mutated | TEST-GAP | 5 | 5 | x_check_database_health__mutmut_66, x_check_database_health__mutmut_69, x_check_database_health__mutmut_72 | tests/unit/api/routes/test_system.py; tests/unit/routes/test_system_routes.py |
| x_check_redis_health::message pass-through default text mutated | LOW-VALUE | 5 | 5 | x_check_redis_health__mutmut_55, x_check_redis_health__mutmut_57, x_check_redis_health__mutmut_60 | tests/unit/api/routes/test_system.py; tests/unit/routes/test_system_routes.py |
| x_get_latency_stats::peek_queue window args mutated | TEST-GAP | 5 | 5 | x_get_latency_stats__mutmut_10, x_get_latency_stats__mutmut_11, x_get_latency_stats__mutmut_12 | tests/unit/api/routes/test_telemetry_api.py; tests/unit/routes/test_system_routes.py |
| x__are_critical_pipeline_workers_healthy::log-call text arg mutated | LOW-VALUE | 4 | 4 | x__are_critical_pipeline_workers_healthy__mutmut_10, x__are_critical_pipeline_workers_healthy__mutmut_7, x__are_critical_pipeline_workers_healthy__mutmut_8 | tests/unit/api/routes/test_system.py; tests/unit/routes/test_system_routes.py |
| x__check_ai_service_health::error text mutated | LOW-VALUE | 4 | 4 | x__check_ai_service_health__mutmut_39, x__check_ai_service_health__mutmut_40, x__check_ai_service_health__mutmut_41 | tests/unit/api/routes/test_health_full.py |
| x__check_nemotron_health_with_circuit_breaker::circuit record_failure args mutated | TEST-GAP | 4 | 4 | x__check_nemotron_health_with_circuit_breaker__mutmut_17, x__check_nemotron_health_with_circuit_breaker__mutmut_18, x__check_nemotron_health_with_circuit_breaker__mutmut_19 | tests/unit/routes/test_system_routes.py |
| x__check_redis_health_full::redis_version default mutated (surfaces in details) | TEST-GAP | 4 | 4 | x__check_redis_health_full__mutmut_46, x__check_redis_health_full__mutmut_48, x__check_redis_health_full__mutmut_51 | tests/unit/api/routes/test_health_full.py |
| x__get_circuit_breaker_summary::state default mutated (still maps CLOSED) | EQUIVALENT | 4 | 4 | x__get_circuit_breaker_summary__mutmut_12, x__get_circuit_breaker_summary__mutmut_14, x__get_circuit_breaker_summary__mutmut_17 | tests/unit/api/routes/test_health_full.py |
| x__get_model_display_name::title-case fallback separators mutated | TEST-GAP | 4 | 4 | x__get_model_display_name__mutmut_51, x__get_model_display_name__mutmut_52, x__get_model_display_name__mutmut_53 | tests/unit/api/routes/test_system_models.py |
| x__get_worker_statuses::WorkerStatus name literal mutated | TEST-GAP | 4 | 0 | x__get_worker_statuses__mutmut_70, x__get_worker_statuses__mutmut_71, x__get_worker_statuses__mutmut_95 | tests/unit/api/routes/test_system.py; tests/unit/routes/test_system_routes.py |
| x__get_worker_statuses::message ternary condition forced | TEST-GAP | 4 | 1 | x__get_worker_statuses__mutmut_197, x__get_worker_statuses__mutmut_239, x__get_worker_statuses__mutmut_73 | tests/unit/api/routes/test_system.py; tests/unit/routes/test_system_routes.py |
| x__is_worker_group_operational::state default "stopped" cosmetic/falsy (both non-operational) | EQUIVALENT | 4 | 4 | x__is_worker_group_operational__mutmut_10, x__is_worker_group_operational__mutmut_11, x__is_worker_group_operational__mutmut_5 | tests/unit/api/routes/test_system.py; tests/unit/routes/test_system_routes.py |
| x__runtime_env_path::candidate data dir case mutated | TEST-GAP | 4 | 4 | x__runtime_env_path__mutmut_14, x__runtime_env_path__mutmut_15, x__runtime_env_path__mutmut_17 | tests/unit/api/routes/test_system.py; tests/unit/routes/test_system_routes.py |
| x__write_runtime_env::encoding arg aliased | EQUIVALENT | 4 | 4 | x__write_runtime_env__mutmut_11, x__write_runtime_env__mutmut_39, x__write_runtime_env__mutmut_46 | tests/unit/api/routes/test_system.py; tests/unit/api/routes/test_system_config_deprecation.py; tests/unit/routes/test_system_routes.py |
| x_check_ai_services_health::details service-status default "unhealthy" mutated | TEST-GAP | 4 | 4 | x_check_ai_services_health__mutmut_31, x_check_ai_services_health__mutmut_32, x_check_ai_services_health__mutmut_40 | tests/unit/api/routes/test_system.py; tests/unit/routes/test_system_routes.py |
| x_check_ai_services_health::failed/working service name text mutated | LOW-VALUE | 4 | 4 | x_check_ai_services_health__mutmut_58, x_check_ai_services_health__mutmut_60, x_check_ai_services_health__mutmut_66 | tests/unit/api/routes/test_system.py; tests/unit/routes/test_system_routes.py |
| x_check_redis_health::redis_version default mutated | TEST-GAP | 4 | 4 | x_check_redis_health__mutmut_39, x_check_redis_health__mutmut_41, x_check_redis_health__mutmut_44 | tests/unit/api/routes/test_system.py; tests/unit/routes/test_system_routes.py |
| x_register_workers::module global not stored | TEST-GAP | 4 | 4 | x_register_workers__mutmut_6, x_register_workers__mutmut_7, x_register_workers__mutmut_8 | tests/unit/api/routes/test_system.py; tests/unit/api/routes/test_system_supervisor.py; tests/unit/api/routes/test_telemetry_api.py; tests/unit/routes/test_system_routes.py |
| x_verify_api_key::SecretStr api-key handling mutated | TEST-GAP | 4 | 4 | x_verify_api_key__mutmut_15, x_verify_api_key__mutmut_17, x_verify_api_key__mutmut_21 | tests/unit/api/routes/test_system.py; tests/unit/routes/test_system_routes.py |
| CircuitBreaker::failure-count reset after expiry mutated | TEST-GAP | 3 | 3 | xǁCircuitBreakerǁis_open__mutmut_3, xǁCircuitBreakerǁis_open__mutmut_5, xǁCircuitBreakerǁis_open__mutmut_6 | — |
| x__build_exporter_status::health default cosmetic (maps to UNKNOWN enum anyway) | EQUIVALENT | 3 | 3 | x__build_exporter_status__mutmut_51, x__build_exporter_status__mutmut_54, x__build_exporter_status__mutmut_55 | tests/unit/api/routes/test_system.py |
| x__build_targets_summary::health default cosmetic (counts fall to unknown) | EQUIVALENT | 3 | 3 | x__build_targets_summary__mutmut_35, x__build_targets_summary__mutmut_38, x__build_targets_summary__mutmut_39 | tests/unit/api/routes/test_system.py |
| x__build_targets_summary::job default text mutated (surfaces in API job name) | TEST-GAP | 3 | 3 | x__build_targets_summary__mutmut_10, x__build_targets_summary__mutmut_6, x__build_targets_summary__mutmut_9 | tests/unit/api/routes/test_system.py |
| x__calculate_stage_latency::percentile arg off-by-one (p50/p95/p99) | TEST-GAP | 3 | 3 | x__calculate_stage_latency__mutmut_49, x__calculate_stage_latency__mutmut_54, x__calculate_stage_latency__mutmut_59 | tests/unit/api/routes/test_telemetry_api.py; tests/unit/routes/test_system_routes.py |
| x__check_ai_service_health::response time math mutated | TEST-GAP | 3 | 3 | x__check_ai_service_health__mutmut_77, x__check_ai_service_health__mutmut_78, x__check_ai_service_health__mutmut_79 | tests/unit/api/routes/test_health_full.py |
| x__check_nemotron_health_with_circuit_breaker::circuit-open fallback error text cosmetic | LOW-VALUE | 3 | 3 | x__check_nemotron_health_with_circuit_breaker__mutmut_10, x__check_nemotron_health_with_circuit_breaker__mutmut_11, x__check_nemotron_health_with_circuit_breaker__mutmut_9 | tests/unit/routes/test_system_routes.py |
| x__check_redis_health_full::details=None kwarg removed (schema default None) | EQUIVALENT | 3 | 3 | x__check_redis_health_full__mutmut_24, x__check_redis_health_full__mutmut_59, x__check_redis_health_full__mutmut_8 | tests/unit/api/routes/test_health_full.py |
| x__check_redis_health_full::not-available message text cosmetic | LOW-VALUE | 3 | 3 | x__check_redis_health_full__mutmut_11, x__check_redis_health_full__mutmut_12, x__check_redis_health_full__mutmut_13 | tests/unit/api/routes/test_health_full.py |
| x__check_yolo26_health_with_circuit_breaker::circuit-open fallback error text cosmetic | LOW-VALUE | 3 | 3 | x__check_yolo26_health_with_circuit_breaker__mutmut_10, x__check_yolo26_health_with_circuit_breaker__mutmut_11, x__check_yolo26_health_with_circuit_breaker__mutmut_9 | tests/unit/routes/test_system_routes.py |
| x__get_model_category::"Other" category literal mutated | TEST-GAP | 3 | 3 | x__get_model_category__mutmut_2, x__get_model_category__mutmut_3, x__get_model_category__mutmut_4 | tests/unit/api/routes/test_system_models.py |
| x__get_worker_status::cleanup running default mutated | TEST-GAP | 3 | 3 | x__get_worker_status__mutmut_25, x__get_worker_status__mutmut_27, x__get_worker_status__mutmut_30 | tests/unit/api/routes/test_health_full.py |
| x__get_worker_statuses::message text cosmetic | LOW-VALUE | 3 | 1 | x__get_worker_statuses__mutmut_240, x__get_worker_statuses__mutmut_74, x__get_worker_statuses__mutmut_99 | tests/unit/api/routes/test_system.py; tests/unit/routes/test_system_routes.py |
| x__is_worker_group_operational::"workers" key mutated (multi-worker branch) | TEST-GAP | 3 | 0 | x__is_worker_group_operational__mutmut_1, x__is_worker_group_operational__mutmut_2, x__is_worker_group_operational__mutmut_3 | tests/unit/api/routes/test_system.py; tests/unit/routes/test_system_routes.py |
| x__stats_to_schema::sample_count kwarg default mutated (unreachable past guard) | EQUIVALENT | 3 | 3 | x__stats_to_schema__mutmut_43, x__stats_to_schema__mutmut_45, x__stats_to_schema__mutmut_48 | tests/unit/core/test_metrics.py |
| x__write_runtime_env::KEY=VALUE split semantics mutated | TEST-GAP | 3 | 3 | x__write_runtime_env__mutmut_25, x__write_runtime_env__mutmut_26, x__write_runtime_env__mutmut_28 | tests/unit/api/routes/test_system.py; tests/unit/api/routes/test_system_config_deprecation.py; tests/unit/routes/test_system_routes.py |
| x_check_redis_health::message text cosmetic | LOW-VALUE | 3 | 3 | x_check_redis_health__mutmut_10, x_check_redis_health__mutmut_11, x_check_redis_health__mutmut_12 | tests/unit/api/routes/test_system.py; tests/unit/routes/test_system_routes.py |
| CacheEntry.is_valid::TTL boundary < -> <= | LOW-VALUE | 2 | 2 | xǁGPUStatsCacheEntryǁis_valid__mutmut_2, xǁPerformanceMetricsCacheEntryǁis_valid__mutmut_2 | — |
| x__build_exporter_status::error kwarg forced None/removed | TEST-GAP | 2 | 0 | x__build_exporter_status__mutmut_84, x__build_exporter_status__mutmut_89 | tests/unit/api/routes/test_system.py |
| x__check_ai_health_with_timeout::latency duration arithmetic (observe only) | LOW-VALUE | 2 | 2 | x__check_ai_health_with_timeout__mutmut_16, x__check_ai_health_with_timeout__mutmut_8 | tests/unit/routes/test_system_routes.py |
| x__check_db_health_with_timeout::latency duration arithmetic (observe only) | LOW-VALUE | 2 | 2 | x__check_db_health_with_timeout__mutmut_17, x__check_db_health_with_timeout__mutmut_9 | tests/unit/routes/test_system_routes.py |
| x__check_postgres_health_full::SELECT now() query shape mutated (opaque under mocked db) | LOW-VALUE | 2 | 2 | x__check_postgres_health_full__mutmut_2, x__check_postgres_health_full__mutmut_3 | tests/unit/api/routes/test_health_full.py |
| x__check_postgres_health_full::details=None kwarg removed (schema default None) | EQUIVALENT | 2 | 2 | x__check_postgres_health_full__mutmut_11, x__check_postgres_health_full__mutmut_23 | tests/unit/api/routes/test_health_full.py |
| x__check_redis_health_with_timeout::latency duration arithmetic (observe only) | LOW-VALUE | 2 | 2 | x__check_redis_health_with_timeout__mutmut_17, x__check_redis_health_with_timeout__mutmut_9 | tests/unit/routes/test_system_routes.py |
| x__check_yolo26_health_with_circuit_breaker::circuit record_failure args mutated | TEST-GAP | 2 | 2 | x__check_yolo26_health_with_circuit_breaker__mutmut_19, x__check_yolo26_health_with_circuit_breaker__mutmut_21 | tests/unit/routes/test_system_routes.py |
| x__get_circuit_breaker_summary::open/half_open counter =1 instead of += | TEST-GAP | 2 | 2 | x__get_circuit_breaker_summary__mutmut_23, x__get_circuit_breaker_summary__mutmut_30 | tests/unit/api/routes/test_health_full.py |
| x__get_degradation_status::response kwarg removed/forced None | TEST-GAP | 2 | 0 | x__get_degradation_status__mutmut_17, x__get_degradation_status__mutmut_19 | tests/unit/api/routes/test_system.py |
| x__get_worker_status::file_watcher/cleanup running literal flipped | TEST-GAP | 2 | 2 | x__get_worker_status__mutmut_11, x__get_worker_status__mutmut_41 | tests/unit/api/routes/test_health_full.py |
| x__write_runtime_env::comment/skip predicate mutated | TEST-GAP | 2 | 2 | x__write_runtime_env__mutmut_14, x__write_runtime_env__mutmut_17 | tests/unit/api/routes/test_system.py; tests/unit/api/routes/test_system_config_deprecation.py; tests/unit/routes/test_system_routes.py |
| x__write_runtime_env::log-call text arg mutated | LOW-VALUE | 2 | 2 | x__write_runtime_env__mutmut_49, x__write_runtime_env__mutmut_50 | tests/unit/api/routes/test_system.py; tests/unit/api/routes/test_system_config_deprecation.py; tests/unit/routes/test_system_routes.py |
| x_check_ai_services_health::gather timeout arg dropped (None) | TEST-GAP | 2 | 2 | x_check_ai_services_health__mutmut_11, x_check_ai_services_health__mutmut_17 | tests/unit/api/routes/test_system.py; tests/unit/routes/test_system_routes.py |
| x_check_database_health::connectivity query shape mutated (opaque under mocked db) | LOW-VALUE | 2 | 2 | x_check_database_health__mutmut_2, x_check_database_health__mutmut_4 | tests/unit/api/routes/test_system.py; tests/unit/routes/test_system_routes.py |
| x_verify_api_key::401 detail text mutated | LOW-VALUE | 2 | 2 | x_verify_api_key__mutmut_31, x_verify_api_key__mutmut_8 | tests/unit/api/routes/test_system.py; tests/unit/routes/test_system_routes.py |
| CircuitBreaker::warning log message mutated | LOW-VALUE | 1 | 1 | xǁCircuitBreakerǁrecord_failure__mutmut_14 | — |
| x__bounded_health_check::default timeout 30.0->31.0 | LOW-VALUE | 1 | 1 | x__bounded_health_check__mutmut_1 | tests/unit/api/routes/test_system.py; tests/unit/routes/test_system_routes.py |
| x__build_empty_batch_response::batches=[] kwarg removed (schema default) | EQUIVALENT | 1 | 1 | x__build_empty_batch_response__mutmut_6 | tests/unit/api/routes/test_system.py |
| x__build_exporter_status::health always reported up | TEST-GAP | 1 | 0 | x__build_exporter_status__mutmut_58 | tests/unit/api/routes/test_system.py |
| x__build_exporter_status::health default None -> AttributeError on missing health | TEST-GAP | 1 | 1 | x__build_exporter_status__mutmut_49 | tests/unit/api/routes/test_system.py |
| x__build_exporter_status::lastScrape lookup key mutated (last_scrape lost) | TEST-GAP | 1 | 0 | x__build_exporter_status__mutmut_65 | tests/unit/api/routes/test_system.py |
| x__build_exporter_status::not-found error text cosmetic | LOW-VALUE | 1 | 0 | x__build_exporter_status__mutmut_104 | tests/unit/api/routes/test_system.py |
| x__build_targets_summary::down counter =1 instead of += (multi-down jobs) | TEST-GAP | 1 | 1 | x__build_targets_summary__mutmut_51 | tests/unit/api/routes/test_system.py |
| x__build_targets_summary::health default None -> AttributeError (crash on missing health) | TEST-GAP | 1 | 1 | x__build_targets_summary__mutmut_33 | tests/unit/api/routes/test_system.py |
| x__build_targets_summary::job default None -> None key in summary | TEST-GAP | 1 | 1 | x__build_targets_summary__mutmut_4 | tests/unit/api/routes/test_system.py |
| x__build_targets_summary::job seed unknown:1 (miscounts clean jobs) | TEST-GAP | 1 | 1 | x__build_targets_summary__mutmut_24 | tests/unit/api/routes/test_system.py |
| x__build_targets_summary::unknown kwarg removed (schema default 0) | TEST-GAP | 1 | 1 | x__build_targets_summary__mutmut_65 | tests/unit/api/routes/test_system.py |
| x__check_ai_health_with_timeout::details=None kwarg removed (schema default None) | EQUIVALENT | 1 | 1 | x__check_ai_health_with_timeout__mutmut_27 | tests/unit/routes/test_system_routes.py |
| x__check_ai_service_health::health URL mutated | TEST-GAP | 1 | 1 | x__check_ai_service_health__mutmut_75 | tests/unit/api/routes/test_health_full.py |
| x__check_ai_service_health::httpx client timeout dropped | TEST-GAP | 1 | 1 | x__check_ai_service_health__mutmut_73 | tests/unit/api/routes/test_health_full.py |
| x__check_ai_service_health::settings url attr lookup mutated | TEST-GAP | 1 | 1 | x__check_ai_service_health__mutmut_22 | tests/unit/api/routes/test_health_full.py |
| x__check_db_health_with_timeout::details=None kwarg removed (schema default None) | EQUIVALENT | 1 | 1 | x__check_db_health_with_timeout__mutmut_28 | tests/unit/routes/test_system_routes.py |
| x__check_nemotron_health::httpx client timeout dropped | TEST-GAP | 1 | 1 | x__check_nemotron_health__mutmut_1 | tests/unit/routes/test_system_routes.py |
| x__check_nemotron_health_with_circuit_breaker::inner check timeout passed as None | TEST-GAP | 1 | 1 | x__check_nemotron_health_with_circuit_breaker__mutmut_14 | tests/unit/routes/test_system_routes.py |
| x__check_postgres_health_full::scalar() verification call skipped | EQUIVALENT | 1 | 1 | x__check_postgres_health_full__mutmut_4 | tests/unit/api/routes/test_health_full.py |
| x__check_redis_health_with_timeout::details=None kwarg removed (schema default None) | EQUIVALENT | 1 | 1 | x__check_redis_health_with_timeout__mutmut_28 | tests/unit/routes/test_system_routes.py |
| x__check_yolo26_health::httpx client timeout dropped | TEST-GAP | 1 | 1 | x__check_yolo26_health__mutmut_1 | tests/unit/routes/test_system_routes.py |
| x__check_yolo26_health_with_circuit_breaker::inner check timeout passed as None | TEST-GAP | 1 | 1 | x__check_yolo26_health_with_circuit_breaker__mutmut_14 | tests/unit/routes/test_system_routes.py |
| x__get_degradation_status::manager=None (degradation status lost) | TEST-GAP | 1 | 0 | x__get_degradation_status__mutmut_2 | tests/unit/api/routes/test_system.py |
| x__get_model_category::membership check flipped | TEST-GAP | 1 | 1 | x__get_model_category__mutmut_1 | tests/unit/api/routes/test_system_models.py |
| x__get_supervisor_health::healthy path return True->False | TEST-GAP | 1 | 1 | x__get_supervisor_health__mutmut_2 | tests/unit/routes/test_system_routes.py |
| x__identify_monitoring_issues::UNKNOWN-exporter branch flipped | TEST-GAP | 1 | 1 | x__identify_monitoring_issues__mutmut_19 | tests/unit/api/routes/test_system.py |
| x__write_runtime_env::write_runtime_env mutated | TEST-GAP | 1 | 1 | x__write_runtime_env__mutmut_42 | tests/unit/api/routes/test_system.py; tests/unit/api/routes/test_system_config_deprecation.py; tests/unit/routes/test_system_routes.py |

## Drafted tests (highest-value TEST-GAP clusters) — **// UNVERIFIED — not yet run red/green**

TDD procedure (one line): run each new test against the mutant region first — the assertion must FAIL (red) on every clustered mutant and PASS (green) on unmutated `backend/api/routes/system.py` — and only then census-probe the cluster keys (WP4.4 rule: green-under-original proven first; see the `[:12]`-off-by-one incident recorded in `f06eea77`).

### D1 — GPU stats payload full-key contract + latest-row query
Kills: `x_get_latest_gpu_stats::gpu payload dict key mutated` (38) + `x_get_latest_gpu_stats::latest-row query mutated` (6) = 44
Target file: `backend/tests/unit/routes/test_system_routes.py` (style: `test_get_latest_gpu_stats_returns_data`, line 1120 — direct helper call, `AsyncMock(spec=AsyncSession)`)

```python
# UNVERIFIED - not yet run red/green
@pytest.mark.asyncio
async def test_get_latest_gpu_stats_full_payload_contract() -> None:
    """Latest-row query (DESC, LIMIT 1) + every payload key, exact (WP4.4 gpu-dict cluster)."""
    db = AsyncMock(spec=AsyncSession)
    mock_gpu_stat = MagicMock()
    expected = {
        "recorded_at": datetime(2025, 12, 27, 10, 0, 0),
        "gpu_name": "NVIDIA RTX A5500",
        "utilization": 75.5,
        "memory_used": 12000,
        "memory_total": 24000,
        "temperature": 65.0,
        "power_usage": 120,
        "inference_fps": 30.5,
        "fan_speed": 55,
        "sm_clock": 1400,
        "memory_bandwidth_utilization": 42,
        "pstate": "P0",
        "throttle_reasons": "0x0",
        "power_limit": 250,
        "sm_clock_max": 1500,
        "compute_processes_count": 3,
        "pcie_replay_counter": 0,
        "temp_slowdown_threshold": 95,
        "memory_clock": 7000,
        "memory_clock_max": 7000,
        "pcie_link_gen": 4,
        "pcie_link_width": 16,
        "pcie_tx_throughput": 12.5,
        "pcie_rx_throughput": 9.5,
        "encoder_utilization": 10,
        "decoder_utilization": 20,
        "bar1_used": 1024,
    }
    for key, value in expected.items():
        # payload key "utilization" is sourced from the gpu_utilization column
        setattr(mock_gpu_stat, "gpu_utilization" if key == "utilization" else key, value)

    mock_result = MagicMock(spec=Result)
    mock_result.scalar_one_or_none.return_value = mock_gpu_stat
    db.execute = AsyncMock(return_value=mock_result)

    stats = await get_latest_gpu_stats(db)  # type: ignore[arg-type]

    # payload key contract — exact dict kills every key clobber/case mutation
    assert stats == expected

    # latest-row query: ORDER BY recorded_at DESC + LIMIT 1
    sql = str(db.execute.call_args[0][0])
    assert "recorded_at DESC" in sql
    assert "LIMIT 1" in sql
```

Red proof: `"XXfan_speedXX"`/`"FAN_SPEED"`-style key mutations change a payload key → dict equality fails; `limit(2)`/`limit(None)`/`order_by(None)`/`select(None)`/`db.execute(None)` fail the SQL asserts (`stmt=None` → `str(None)` contains neither substring).
Green: original returns exactly `expected` and compiles `... ORDER BY gpu_stats.recorded_at DESC LIMIT 1`.
Risk note: if `str(stmt)` renders the limit differently in this SQLAlchemy version, keep the `recorded_at DESC` assert and drop the `LIMIT 1` one — dict equality alone covers 38/44.

### D2 — DB pool metrics exact payload + error details
Kills: `x_check_database_health::pool metric key/default mutated` (33) + `x_check_database_health::error details payload mutated` (5) = 38
Target file: `backend/tests/unit/routes/test_system_routes.py` (style: `test_check_database_health_healthy`, line 2220)

```python
# UNVERIFIED - not yet run red/green
@pytest.mark.asyncio
async def test_check_database_health_pool_metrics_exact() -> None:
    """Each pool key maps its pool_status source key; missing keys default to 0; error details exact."""
    db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock(spec=Result)
    mock_result.scalar_one.return_value = 5
    db.execute = AsyncMock(return_value=mock_result)

    pool = {"pool_size": 20, "overflow": 5, "checkedin": 15, "checkedout": 10, "total_connections": 25}
    with patch("backend.core.database.get_pool_status", AsyncMock(return_value=pool)):
        status = await check_database_health(db)  # type: ignore[arg-type]
    assert status.details == {
        "pool": {"size": 20, "overflow": 5, "checkedin": 15, "checkedout": 10, "total_connections": 25}
    }

    # missing pool_status entries fall back to 0 (kills default -> None/1 mutations)
    with patch("backend.core.database.get_pool_status", AsyncMock(return_value={})):
        status = await check_database_health(db)  # type: ignore[arg-type]
    assert status.details == {
        "pool": {"size": 0, "overflow": 0, "checkedin": 0, "checkedout": 0, "total_connections": 0}
    }

    # exception path keeps {"error": str(e)} exactly (kills details=None / {"ERROR": ...} mutations)
    db_fail = AsyncMock(spec=AsyncSession)
    db_fail.execute = AsyncMock(side_effect=RuntimeError("db down"))
    status = await check_database_health(db_fail)  # type: ignore[arg-type]
    assert status.details == {"error": "db down"}
```

Red proof: `"XXcheckedinXX"`/`"CHECKEDIN"` response-key flips, wrong lookup keys, `default None/1` break assert 1 or 2; `details=None`, `{"ERROR":...}`, `{"error": str(None)}` break assert 3.
Green: original builds exactly those dicts. (Import `check_database_health` — already imported/used in this file via `system_routes.` attribute; use `system_routes.check_database_health` to match the file's existing call style.)

### D3 — Redis health payload contract (details keys, defaults, both branches)
Kills: `x_check_redis_health::error/version details payload mutated` (25) + `x_check_redis_health::redis_version default mutated` (4) + `x__check_redis_health_full::redis_version default mutated` (4) = 33
Target files: `backend/tests/unit/routes/test_system_routes.py` (style: `test_check_redis_health_healthy`, line 2252) + the `_check_redis_health_full` twin added to `backend/tests/unit/api/routes/test_health_full.py`

```python
# UNVERIFIED - not yet run red/green
@pytest.mark.asyncio
async def test_check_redis_health_details_payload_exact() -> None:
    """details redis_version/error keys + defaults are payload contract (WP4.4 redis cluster)."""
    # healthy WITHOUT a version field -> default "unknown"
    redis = AsyncMock(spec=RedisClient)
    redis.health_check = AsyncMock(return_value={"status": "healthy"})
    status = await system_routes.check_redis_health(redis)  # type: ignore[arg-type]
    assert status.details == {"redis_version": "unknown"}

    # unhealthy payload WITHOUT an error field -> default text in message AND details
    redis = AsyncMock(spec=RedisClient)
    redis.health_check = AsyncMock(return_value={"status": "unhealthy"})
    status = await system_routes.check_redis_health(redis)  # type: ignore[arg-type]
    assert status.message == "Redis connection error"
    assert status.details == {"error": "Redis connection error"}

    # exception path keeps {"error": str(e)}
    redis = AsyncMock(spec=RedisClient)
    redis.health_check = AsyncMock(side_effect=ConnectionError("connection refused"))
    status = await system_routes.check_redis_health(redis)  # type: ignore[arg-type]
    assert status.details == {"error": "connection refused"}

    # redis=None DI-failure branch keeps its error detail dict
    status = await system_routes.check_redis_health(None)
    assert status.details == {"error": "Redis client not available"}
```

```python
# UNVERIFIED - not yet run red/green  (append to backend/tests/unit/api/routes/test_health_full.py)
@pytest.mark.asyncio
async def test_check_redis_health_full_defaults_to_unknown_version() -> None:
    """health/full redis details fall back to version 'unknown' (WP4.4 redis-full cluster)."""
    mock_redis = AsyncMock(spec=RedisClient)
    mock_redis.info.return_value = {"status": "healthy"}  # no redis_version key
    result = await _check_redis_health_full(mock_redis)
    assert result.details == {"redis_version": "unknown"}
```

Red: `"XXredis_versionXX"`/lookup-key flips, `default None/""/"UNKNOWN"`, `"XXerrorXX"`/`"ERROR"` keys, `details=None`, and default-text clobbers each break one exact assert.
Green: original matches all five. **Verify before census:** `_check_redis_health_full` reads `redis.info(...)` or `redis.health_check(...)` — read lines 5369-5400 and set the mock's attribute name accordingly.

### D4 — Model display-name map + fallback casing contract
Kills: `x__get_model_display_name::display-name map entry mutated` (40) + `::title-case fallback separators mutated` (4) + `x__get_model_category::"Other" category literal mutated` (3) = 47
Target file: `backend/tests/unit/api/routes/test_system_models.py` (module has no direct helper test yet — add imports `from backend.api.routes.system import _get_model_category, _get_model_display_name`)

```python
# UNVERIFIED - not yet run red/green
@pytest.mark.parametrize(
    ("name", "display"),
    [
        ("yolo11-license-plate", "YOLO11 License Plate"),
        ("yolo11-face", "YOLO11 Face Detection"),
        ("paddleocr", "PaddleOCR"),
        ("yolo26-general", "YOLO26 General Detection"),
        ("clip_embedder", "CLIP ViT-L/14"),
        ("yolo-world-s", "YOLO-World Small"),
        ("depth-anything-v2-tiny", "Depth Anything V2 Tiny"),
        ("vitpose-small", "ViTPose Small"),
        # unmapped names must go through the "-"/"_" -> space, title-cased fallback
        ("foo-bar-baz", "Foo Bar Baz"),
        ("my_model_v2", "My Model V2"),
    ],
)
def test_get_model_display_name_exact_contract(name: str, display: str) -> None:
    """Every map entry exact; unmapped names use the separator-replacement title fallback (WP4.4 map cluster)."""
    assert _get_model_display_name(name) == display


def test_get_model_category_unknown_is_other() -> None:
    assert _get_model_category("totally-unknown-model") == "Other"
```

Red: value clobbers (`"XXPaddleOCRXX"`, `"PADDLEOCR"`) fail their param directly; key clobbers (`"XXpaddleocrXX"`, `"PADDLEOCR"`) miss the dict and fall to the title-cased fallback which differs from the map value (e.g. "Paddleocr" ≠ "PaddleOCR") → that param fails; fallback-separator clobbers break the last two params; `"XXOtherXX"`/`"other"` breaks the category test.
Green: original returns exactly those strings (str.title() renders "v2" as "V2" — re-check the real call before census).

### D5 — Health event emitter payload + lazy wiring
Kills: `x__emit_health_status_changes::update_all_components statuses/details payload mutated` (19) + `::emitter wiring branches mutated` (5) = 24
Target file: `backend/tests/unit/routes/test_system_routes.py` (no direct coverage of `_emit_health_status_changes` exists today — only reached transitively through `get_health`)

```python
# UNVERIFIED - not yet run red/green
@pytest.mark.asyncio
async def test_emit_health_status_changes_payload_and_wiring() -> None:
    """update_all_components gets exact component-keyed statuses/details; ws emitter wired exactly once."""
    emitter = AsyncMock()
    emitter._emitter = None  # force the lazy wiring branch
    ws_emitter = MagicMock()

    with (
        patch.object(system_routes, "get_health_event_emitter", return_value=emitter),
        patch(
            "backend.services.websocket_emitter.get_websocket_emitter_sync",
            return_value=ws_emitter,
        ) as ws_get,
    ):
        await system_routes._emit_health_status_changes(
            "healthy",
            "degraded",
            "unhealthy",
            db_details={"pool": {}},
            redis_details={},
            ai_details=None,
        )

    ws_get.assert_called_once()
    emitter.set_emitter.assert_called_once_with(ws_emitter)
    emitter.update_all_components.assert_awaited_once_with(
        statuses={"database": "healthy", "redis": "degraded", "ai_service": "unhealthy"},
        details={"database": {"pool": {}}, "redis": {}, "ai_service": {}},
    )
```

Red: every `"database"`/`"redis"`/`"ai_service"` key clobber/case flip, `X and {}` conditional (→ `{}`/falsy swap on a non-empty db_details), `statuses=None`, whole-payload removal, `health_emitter = None` (function takes the except path — no call), flipped `is None`/`is not None` branches (set_emitter skipped, or called with None) each break one of the three asserts.
Green: original calls `update_all_components` exactly once with that kwargs pair; `ai_details=None or {}` → `{}`.

### D6 — AI service health payload contract + latency math + breaker lookup
Kills: `x__check_ai_service_health::last_check kwarg removed/forced None` (18) + `::url kwarg removed/forced None` (11) + `::response_time_ms kwarg mutated` (12, minus the round-2→3 twin that survives) + `::response time math mutated` (3) + `::circuit breaker name lookup mutated` (8, default-name leg) ≈ 51/52
Target file: `backend/tests/unit/api/routes/test_health_full.py` (style: `test_check_ai_service_health_healthy`, line 131 — httpx + registry patching already established)

```python
# UNVERIFIED - not yet run red/green
@pytest.mark.asyncio
async def test_check_ai_service_health_healthy_payload_contract() -> None:
    """Healthy branch pins breaker lookup, url, response_time_ms (real ms math, round 2), last_check."""
    mock_settings = MagicMock(spec=Settings)
    mock_settings.yolo26_url = "http://ai-yolo26:8095"

    service_config = {  # NOTE: no "circuit_breaker_name" -> must default to name
        "name": "yolo26",
        "display_name": "YOLO26 Object Detection",
        "url_attr": "yolo26_url",
        "critical": True,
    }

    with (
        patch("backend.services.circuit_breaker._get_registry", autospec=True) as mock_registry,
        patch("httpx.AsyncClient", autospec=True) as mock_client,
        patch("backend.api.routes.system.time.time", side_effect=[1000.0, 1000.123]),
    ):
        mock_registry.return_value.get.return_value = None  # no breaker registered -> CLOSED
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

        result = await _check_ai_service_health(service_config, mock_settings)

    mock_registry.return_value.get.assert_called_once_with("yolo26")
    assert result.status == ServiceHealthState.HEALTHY
    assert result.url == "http://ai-yolo26:8095"
    assert result.response_time_ms == 123.0  # 0.123 s * 1000, round(…, 2)
    assert result.last_check is not None
    assert result.circuit_state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_check_ai_service_health_no_url_payload_contract() -> None:
    """URL-not-configured branch: url == '' (not None) and last_check populated."""
    mock_settings = MagicMock(spec=Settings)
    mock_settings.yolo26_url = None

    service_config = {
        "name": "yolo26",
        "display_name": "YOLO26 Object Detection",
        "url_attr": "yolo26_url",
        "circuit_breaker_name": "yolo26",
    }
    result = await _check_ai_service_health(service_config, mock_settings)

    assert result.status == ServiceHealthState.UNKNOWN
    assert result.url == ""  # explicit '' — kills url=None / kwarg-removed mutations
    assert result.last_check is not None
```

Red: `last_check` removal→None (all branches, including the 6 now-None twins via `datetime.now(None)` — see green-risk note) fails `is not None`; `url=None`/kwarg-removed fails `== "http://ai-yolo26:8095"` / `== ""`; `response_time_ms=None`/removed fails `== 123.0`; `/1000`→0.0, `*1001`→123.123, `time.time() + start_time`→≈2e6 fail `== 123.0`; every `circuit_breaker_name`/`registry.get` key mutation fails `assert_called_once_with("yolo26")` (the omitted-key config exercises the default-name leg).
Green: original produces exactly these values.
**Green-risk (verify before census):** the `datetime.now(None)` twins (12 keys, e.g. mutmut_42) yield a NAIVE datetime while the schema field is `datetime | None` — pydantic does not coerce tz, so the field type check passes and the survivor is NOT killed by `is not None` in its healthy-branch legs unless the test also asserts `result.last_check.tzinfo is not None`. Add that one-liner to D6's first test — with it the kill estimate for the last_check cluster rises to 18/18.
**Known survivor:** the `round(response_time_ms, 3)` twin (2 keys) survives D6 (123.0 is 123.0 at any ndigits) — a fractional-millisecond fixture (e.g. 0.1234 s) would also kill it; noted for a follow-up pass.

## Kill estimate
D1 44, D2 38, D3 33, D4 47, D5 24, D6 ≈51 → **≈237 survivors killable; ≈200 of them still open per the `cdf32a4f` ledger** (projection on top of the batch: (1261+135+200)/1899 ≈ 84.1%).

## Covering test files (where the weak asserts live)
- `backend/tests/unit/routes/test_system_routes.py` — `check_database_health` asserts only 2 of 5 pool keys (lines 2245-2249); redis payload asserted only for the happy version case (line 2262); `_emit_health_status_changes` never directly covered; `_get_worker_statuses` asserts exist for some workers only.
- `backend/tests/unit/api/routes/test_system.py` — `TestWp44WorkerStatusContract` (line 2453) is the model assert style to reuse (it already killed 41 worker mutants); monitoring helper tests assert counts but not missing-key/default crash paths.
- `backend/tests/unit/api/routes/test_health_full.py` — AI-service tests assert status/error only; `last_check`/`response_time_ms`/`url`/breaker-lookup key never asserted.
- `backend/tests/unit/api/routes/test_system_models.py` — no direct `_get_model_display_name`/`_get_model_category` unit test exists; endpoint checks only assert key presence (`display_name in data`, lines 626/753).

## Report clusters (StructuredOutput mirror — 36 clusters, sum 638, 0 dup / 0 missing)

| report cluster | class | n | open |
|---|---|---|---|
| x__get_degradation_status::response field lookup key/default mutated | TEST-GAP | 54 | 11 |
| x__get_model_display_name::display-name map entry mutated | TEST-GAP | 40 | 40 |
| x_get_latest_gpu_stats::gpu payload dict key mutated | TEST-GAP | 38 | 38 |
| x_check_database_health::pool metric key/default mutated | TEST-GAP | 33 | 33 |
| x_check_redis_health::error/version details payload mutated | TEST-GAP | 25 | 25 |
| x__get_worker_statuses::pipeline worker dict key/default mutated (lookup falls to default) | TEST-GAP | 23 | 13 |
| x__emit_health_status_changes::update_all_components statuses/details payload mutated | TEST-GAP | 19 | 19 |
| x__check_ai_service_health::last_check kwarg removed/forced None | TEST-GAP | 18 | 18 |
| x__get_worker_statuses::message kwarg dropped/forced None | TEST-GAP | 17 | 4 |
| x__build_exporter_status::exporter match target key/default mutated | TEST-GAP | 13 | 7 |
| x__parse_prometheus_timestamp::nanosecond-truncation branch mutated — dead under py>=3.11 fromisoformat | EQUIVALENT | 13 | 13 |
| x__check_ai_service_health::response_time_ms kwarg mutated | TEST-GAP | 12 | 12 |
| x__get_worker_statuses::getattr running default False->None/omitted (WorkerStatus.running=None) | TEST-GAP | 12 | 3 |
| x__build_exporter_status::lastError lookup key mutated (error field lost) | TEST-GAP | 11 | 0 |
| x__check_ai_service_health::url kwarg removed/forced None | TEST-GAP | 11 | 11 |
| x__build_exporter_status::other payload mutations (match needle clobber, endpoint/last_scrape/error kwargs forced None, status/health kwarg branches incl. None->AttributeError, lastScrape key) | TEST-GAP | 34 | 10 |
| x__check_ai_service_health::other payload/arg mutations (breaker-name default lookup 8, response-time math 3, health-URL 1, settings url_attr lookup 1, httpx timeout dropped 1) | TEST-GAP | 14 | 14 |
| x__build_targets_summary::job/down/health field mutations (job default text/None, job seed, down counter =1 vs +=, health None crash, unknown kwarg) | TEST-GAP | 8 | 8 |
| x__identify_monitoring_issues::all-down/partial-down thresholds + UNKNOWN-exporter branch flipped | TEST-GAP | 6 | 6 |
| runtime env plumbing (x__runtime_env_path data-dir candidate case; x__write_runtime_env KEY=VALUE split, comment/skip predicate, whole-fn) | TEST-GAP | 10 | 10 |
| worker registry plumbing (x__get_worker_statuses name literal + message ternary; x__is_worker_group_operational "workers" key; x_register_workers global not stored; x__get_worker_status cleanup/running literals) | TEST-GAP | 20 | 10 |
| x_check_ai_services_health::per-service default status mutated + gather timeout dropped | TEST-GAP | 6 | 6 |
| redis_version default mutations (x_check_redis_health + x__check_redis_health_full; value surfaces in details payload) | TEST-GAP | 8 | 8 |
| x__emit_health_status_changes::emitter wiring branches (lazy ws-emitter get/set branches, health_emitter=None) | TEST-GAP | 5 | 5 |
| x_check_database_health::exception path details={"error": str(e)} mutated | TEST-GAP | 5 | 5 |
| latency math (x_get_latency_stats peek_queue window args; x__calculate_stage_latency percentile off-by-one) | TEST-GAP | 8 | 8 |
| x__stats_to_schema::empty-samples guard mutated (crash/empty-payload path) | TEST-GAP | 5 | 5 |
| CircuitBreaker behaviour (failure-count reset after expiry; summary open/half_open counter =1 vs +=) | TEST-GAP | 5 | 5 |
| x_verify_api_key::SecretStr api-key handling mutated (hash/compare path) | TEST-GAP | 4 | 4 |
| model naming (x__get_model_display_name fallback separators 4; x__get_model_category "Other" literal 3 + membership flip 1) | TEST-GAP | 8 | 8 |
| nemotron/yolo health wrappers (record_failure args mutated 6, inner-check timeout passed None 2, httpx client timeout dropped 2) | TEST-GAP | 10 | 10 |
| x__get_degradation_status::residual kwargs (response kwarg removed/forced None; manager=None) | TEST-GAP | 3 | 0 |
| x__get_supervisor_health::healthy path return True->False | TEST-GAP | 1 | 1 |
| x_get_latest_gpu_stats::latest-row query mutated (ORDER BY recorded_at DESC / LIMIT 1) | TEST-GAP | 6 | 6 |
| LOW-VALUE residual: prometheus component labels + latency-duration arithmetic (timeout wrappers 14), cosmetic message/error/log text (ai/yolo/nemotron/redis/monitoring/exporter 34), query shapes opaque under mocked db (4), CacheEntry TTL boundary < -> <= (2), bounded_health_check default timeout (1) | LOW-VALUE | 92 | 89 |
| EQUIVALENT residual: kwarg-removal == pydantic schema default (details=None x5, batches=[], circuit_state=CLOSED, sample_count), falsy-default swaps re-defaulted by consumer, cosmetic defaults mapping to same enum, utf-8/UTF-8 encoding alias, scalar() skip (result unused) | EQUIVALENT | 41 | 38 |
| **total** |  | **638** | **503** |

Every report cluster is a union of machine clusters from the 113-row table above; TEST-GAP 492 / LOW-VALUE 92 / EQUIVALENT 54 exact.
