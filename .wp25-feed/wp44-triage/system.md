# WP4.4 Triage Dossier — `backend/api/routes/system.py` (generation 2)

Module: `backend/api/routes/system.py` (original, 5,624 ln). Mutant source: `mutants/backend/api/routes/system.py`
(121,016 ln span-copy). Meta: `mutants/backend/api/routes/system.py.meta` — 1,899 keys tracked, **638 survivors**
(exit_code 0), 1,261 killed. Gen-1 dossier (187-survivor, pre-final-cache) superseded by this document.

Totals: **638 = 515 TEST-GAP + 65 EQUIVALENT + 58 LOW-VALUE** across 66 clusters (verified: every survivor key
appears in exactly one cluster; per-function survivor counts reproduce the meta fold exactly).

## Covering test files (via `mutmut-stats.json` `tests_by_mangled_function_name`)

| File | Covers |
|---|---|
| `backend/tests/unit/api/routes/test_system.py` (:165 CB, :241 api-key, :290 workers, :684 degradation, :892 gpu, :1812 db health, :1832 redis health, :1858 AI batch, :1927 monitoring helpers) | worker/degradation/monitoring/register/verify_api_key |
| `backend/tests/unit/routes/test_system_routes.py` (:75 db/redis health, :106 runtime-env, :316 register, :352-:712 workers/pipeline, :950+ timeouts) | routes-side |
| `backend/tests/unit/api/routes/test_system_models.py` | `_get_model_display_name/_get_model_category` (presence-only asserts) |
| `backend/tests/unit/api/routes/test_health_full.py` (:41-:125 pg/redis-full, :133-:295 `_check_ai_service_health`, :303 CB summary, :359 `_get_worker_status`) | full-health helpers |
| `backend/tests/unit/api/routes/test_telemetry_api.py` (:204, :257) | `get_latency_stats` (patched out), register |
| `backend/tests/unit/api/routes/test_metrics.py` | `_stats_to_schema` |
| `backend/tests/unit/routes/test_system_performance_cache.py` | cache-entry `is_valid` TTL |

## Assertion-strength findings (the gaps)

- `test_system.py::test_get_worker_statuses_with_running_workers` (:310) asserts `running is True` for gpu_monitor
  only; the pipeline/detection/analysis/timeout/metrics blocks' `.get` defaults, key names and message texts are
  never exercised with **partial** dicts — C35/C39/C40 are pure gap.
- `test_get_degradation_status_success` (:707) feeds a manager dict that supplies **every** key, then asserts only
  mode/is_degraded/redis_healthy/`len(services)==1` — every `.get(k, default)` slot in the payload (C09, 56 keys)
  is invisible to it; a `fallback_queues=None` mutant (whole response -> None) survives.
- Monitoring tests (:1927+:) assert lowercase substrings and `status.value == "up"` only — XX-wrap/CASE payload
  mutants and the always-taken `down >= 0` issue branch survive (C51/C53/C55).
- AI health tests assert lowercase-substring errors and never the call args of `httpx.AsyncClient`, `record_failure`
  or `observe_health_check_component_latency`, nor `last_check`/`response_time_ms`/`circuit_state` values (C01-C03,
  C17-C20, C73, C74).
- `check_database_health` test asserts only 2 of 5 pool keys and never the executed statement (C12/C15).
- GPU endpoint test asserts 6 of 26 response keys and never `db.execute` args (C33/C34).
- `test_system_models.py` asserts `"category" in model` / display-name presence only — all value mutants survive (C60).

## Cluster table (66 clusters, n sums to 638)

| # | Mutation pattern (cluster) | Fn @ system.py | n | Example keys | Class | Kill path |
|---|---|---|---|---|---|---|
| 1 | timestamp parse internals: "." in/split/len==2 branch flips + rstrip charset variants | `1759` | 13 | `x__parse_prometheus_timestamp__mutmut_10`, `x__parse_prometheus_timestamp__mutmut_11`, `x__parse_prometheus_timestamp__mutmut_13` | EQUIVALENT | py>=3.11 fromisoformat natively parses arbitrary fractional digits + trailing Z; branch-skip mutants fall through to identical parse (verified py3.14) |
| 2 | `details=None,` kwarg drop on healthy/error returns (schema default None) | `multiple` | 8 | `x__check_ai_health_with_timeout__mutmut_27`, `x__check_db_health_with_timeout__mutmut_28`, `x__check_postgres_health_full__mutmut_11` | EQUIVALENT | schema default None == explicit |
| 3 | degradation logger.debug/error text + exc_info mutants | `4116` | 5 | `x__get_degradation_status__mutmut_102`, `x__get_degradation_status__mutmut_103`, `x__get_degradation_status__mutmut_105` | EQUIVALENT | log-only |
| 4 | encoding utf-8->UTF-8/None (platform same); `split("=", 2)` -> split once (single-kv file, no second =); `open(path, "w")` (same default) | `2534` | 5 | `x__write_runtime_env__mutmut_11`, `x__write_runtime_env__mutmut_39`, `x__write_runtime_env__mutmut_42` | EQUIVALENT | semantic no-op in-container |
| 5 | `cb_status.get("state", "closed")` default XX/CASE mutants | `5402` | 4 | `x__get_circuit_breaker_summary__mutmut_12`, `x__get_circuit_breaker_summary__mutmut_14`, `x__get_circuit_breaker_summary__mutmut_17` | EQUIVALENT | unreachable: mutated default never equals "open"/"half_open" literals -> same CLOSED branch |
| 6 | details ternary fallback `or "unhealthy"` XX/CASE mutants | `1047` | 4 | `x_check_ai_services_health__mutmut_31`, `x_check_ai_services_health__mutmut_32`, `x_check_ai_services_health__mutmut_40` | EQUIVALENT | error is always non-empty in every failing branch -> sentinel never selected |
| 7 | `logger.warning("Pipeline manager not registered...")` CASE/XX/None mutants | `671` | 4 | `x__are_critical_pipeline_workers_healthy__mutmut_10`, `x__are_critical_pipeline_workers_healthy__mutmut_7`, `x__are_critical_pipeline_workers_healthy__mutmut_8` | EQUIVALENT | log-only |
| 8 | `.get("state", "stopped")` default XX/CASE mutants | `650` | 4 | `x__is_worker_group_operational__mutmut_10`, `x__is_worker_group_operational__mutmut_11`, `x__is_worker_group_operational__mutmut_5` | EQUIVALENT | "XXstoppedXX"/"STOPPED" never in operational_states -> same False |
| 9 | `health = target.get("health", "UNKNOWN"/"XXunknownXX").lower()` + `last_scrape=None` drop | `1821` | 3 | `x__build_exporter_status__mutmut_102`, `x__build_exporter_status__mutmut_54`, `x__build_exporter_status__mutmut_55` | EQUIVALENT | post-.lower() normalization == original default; kwarg drop == schema default |
| 10 | mutants that only delete an already-defaulted get() third arg (getattr(...,None)/.get(k,False)/.get(k,{})) | `multiple` | 3 | `x__are_critical_pipeline_workers_healthy__mutmut_15`, `x__are_critical_pipeline_workers_healthy__mutmut_17`, `x__check_ai_service_health__mutmut_22` | EQUIVALENT | dropping explicit default == implicit same default |
| 11 | kwarg `sample_count=stats.get("sample_count", 0)` default mutants | `3136` | 3 | `x__stats_to_schema__mutmut_43`, `x__stats_to_schema__mutmut_45`, `x__stats_to_schema__mutmut_48` | EQUIVALENT | guard early-returns whenever key absent -> kwarg default unreachable |
| 12 | `logger.info(...sanitize_log_value(overrides))` -> None / sanitize(None) | `2534` | 2 | `x__write_runtime_env__mutmut_49`, `x__write_runtime_env__mutmut_50` | EQUIVALENT | log-only |
| 13 | targets summary `get("health", "unknown")` XX/CASE default | `1784` | 2 | `x__build_targets_summary__mutmut_38`, `x__build_targets_summary__mutmut_39` | EQUIVALENT | post-.lower() normalization |
| 14 | `circuit_state=CircuitState.CLOSED,` kwarg drop (schema default == CLOSED) | `5241` | 1 | `x__check_ai_service_health__mutmut_36` | EQUIVALENT | unreachable: schema default CircuitState.CLOSED |
| 15 | `_ = result.scalar()` -> `_ = None` (dead assignment) | `~5351` | 1 | `x__check_postgres_health_full__mutmut_4` | EQUIVALENT | value bound to throwaway `_` |
| 16 | `batches=[],` kwarg drop in `_build_empty_batch_response` | `3997` | 1 | `x__build_empty_batch_response__mutmut_6` | EQUIVALENT | schema default_factory=list |
| 17 | percentile 99 -> 100 on <=100 samples | `2999` | 1 | `x__calculate_stage_latency__mutmut_59` | EQUIVALENT | index min(...,len-1) clamp returns samples[99] either way |
| 18 | CircuitBreaker record_failure `logger.warning(...)` -> None | `224` | 1 | `xǁCircuitBreakerǁrecord_failure__mutmut_14` | EQUIVALENT | log-only |
| 19 | 11-entry display table + title() fallback CASE/XX mutants | `4706` | 44 | `x__get_model_display_name__mutmut_10`, `x__get_model_display_name__mutmut_11`, `x__get_model_display_name__mutmut_12` | LOW-VALUE | cosmetic display strings; gen-1 precedent LOW-VALUE |
| 20 | `Path("./data")`/`Path("/data")` literal CASE/XX mutants | `2508` | 4 | `x__runtime_env_path__mutmut_14`, `x__runtime_env_path__mutmut_15`, `x__runtime_env_path__mutmut_17` | LOW-VALUE | tests always monkeypatch HSI_RUNTIME_ENV_PATH -> default fallback untested-by-design; case variants resolve same on case-insensitive CI only -> LOW |
| 21 | `_batch_aggregator = batch_aggregator` etc global assignment -> None (degenerate: param default None already) | `463` | 4 | `x_register_workers__mutmut_6`, `x_register_workers__mutmut_7`, `x_register_workers__mutmut_8` | LOW-VALUE | register then read-back via getters: currently unasserted but degenerate value |
| 22 | `round(response_time_ms, 2)` -> round(x, 3)/(x, None) precision mutants | `5241` | 2 | `x__check_ai_service_health__mutmut_100`, `x__check_ai_service_health__mutmut_122` | LOW-VALUE | Killable only by mocking clock delta to a 3+ decimal value; measure-zero otherwise |
| 23 | cache `is_valid` `<` TTL -> `<=` | `358-426` | 2 | `xǁGPUStatsCacheEntryǁis_valid__mutmut_2`, `xǁPerformanceMetricsCacheEntryǁis_valid__mutmut_2` | LOW-VALUE | measure-zero boundary age == TTL |
| 24 | `timeout_seconds: float = 30.0` -> 31.0 | `1018` | 1 | `x__bounded_health_check__mutmut_1` | LOW-VALUE | every call site passes explicit timeout -> default unreachable |
| 25 | CircuitBreaker.is_open `now < open_until` -> `<=` | `195` | 1 | `xǁCircuitBreakerǁis_open__mutmut_3` | LOW-VALUE | measure-zero boundary |
| 26 | `_get_worker_statuses`: getattr running default flips (True/None), `.get("workers", {})`->None, `.get("workers")` key CASE/XX, state-default XX/CASE, message kwarg/text mutants ("Not running" XX/case, message=None/drop, `or True` ternary flip), name= XX/CASE, metrics running default flips | `505` | 63 | `x__get_worker_statuses__mutmut_100`, `x__get_worker_statuses__mutmut_101`, `x__get_worker_statuses__mutmut_106` | TEST-GAP | Mock manager_status with workers WITHOUT some keys: assert per-worker running/message exact values + name equality |
| 27 | target matcher: replace("-","_") XX/`in`->`not in`/.upper(); job/instance .get key-default mutants; endpoint/last_scrape/error extraction + fallback error text XX/CASE | `1821` | 59 | `x__build_exporter_status__mutmut_10`, `x__build_exporter_status__mutmut_101`, `x__build_exporter_status__mutmut_104` | TEST-GAP | Matched target -> assert exact endpoint/last_scrape/error; unmatched -> assert exact endpoint default + exact error text (==) |
| 28 | `_get_degradation_status` response payload: services_dict/status/last_check/consecutive_failures/error_message/memory_queue_size/fallback_queues/available_features/is_degraded/redis_healthy .get key/default mutants + kwarg drops (fallback_queues=None -> ValidationError -> whole response None) | `4116` | 54 | `x__get_degradation_status__mutmut_100`, `x__get_degradation_status__mutmut_101`, `x__get_degradation_status__mutmut_17` | TEST-GAP | Feed manager dict WITHOUT some keys and assert defaults; feed full dict and assert every field equals input |
| 29 | 19 extended response dict keys fan_speed..bar1_used XX/CASE mutants | `754` | 38 | `x_get_latest_gpu_stats__mutmut_26`, `x_get_latest_gpu_stats__mutmut_27`, `x_get_latest_gpu_stats__mutmut_28` | TEST-GAP | Assert set(result.keys()) == exact 26-key set (or exact fan_speed/sm_clock keys present) |
| 30 | check_redis_health details/message payload: `{"error": ...}` key XX/CASE, value XX/CASE, `health.get("error", "Redis connection error")` key-default mutants | `847` | 34 | `x_check_redis_health__mutmut_13`, `x_check_redis_health__mutmut_14`, `x_check_redis_health__mutmut_15` | TEST-GAP | Assert exact message string equality + exact details dict in none/error-payload/exception branches |
| 31 | `details["pool"]` dict: size/overflow/checkedin/checkedout/total_connections `pool_status.get(k, 0)` key CASE/XX/None-default mutants | `806` | 33 | `x_check_database_health__mutmut_22`, `x_check_database_health__mutmut_24`, `x_check_database_health__mutmut_27` | TEST-GAP | Full pool dict -> assert exact details dict; partial dict -> assert 0 defaults |
| 32 | `url=`/`response_time_ms=` kwargs -> None/dropped/round-mutants; `url=""` and error-text CASE/XX on observed fields | `5241` | 25 | `x__check_ai_service_health__mutmut_105`, `x__check_ai_service_health__mutmut_106`, `x__check_ai_service_health__mutmut_113` | TEST-GAP | Exact asserts: result.url == configured url, result.response_time_ms == expected, result.error == exact text |
| 33 | `update_all_components(statuses={...},details={...})` dict keys XX/CASE, `health_emitter=None`, emitter wiring mutants | `1114` | 24 | `x__emit_health_status_changes__mutmut_1`, `x__emit_health_status_changes__mutmut_10`, `x__emit_health_status_changes__mutmut_11` | TEST-GAP | Assert AsyncMock called with statuses=={"database":...,"redis":...,"ai_service":...} exact dicts |
| 34 | observed message/error texts XX/CASE ("Redis client not available", "Redis unavailable: connection failed", "YOLO26/Nemotron service connection refused/timed out/(circuit open)", "Not running") | `847/5369/887/913/948/983` | 24 | `x__check_nemotron_health__mutmut_10`, `x__check_nemotron_health__mutmut_11`, `x__check_nemotron_health__mutmut_12` | TEST-GAP | exact `==` asserts on message/return text (existing lowercase-substring asserts are the gap) |
| 35 | `last_check=datetime.now(UTC)` -> None/now(None)/dropped on all 8 `_check_ai_service_health` returns | `5241` | 18 | `x__check_ai_service_health__mutmut_101`, `x__check_ai_service_health__mutmut_109`, `x__check_ai_service_health__mutmut_117` | TEST-GAP | Assert result.last_check is not None and tz-aware on healthy/open/error returns |
| 36 | `observe_health_check_component_latency("database"\|"redis"\|"ai_services", duration)` label XX/CASE/None mutants | `1169/1201/1233` | 18 | `x__check_ai_health_with_timeout__mutmut_13`, `x__check_ai_health_with_timeout__mutmut_14`, `x__check_ai_health_with_timeout__mutmut_17` | TEST-GAP | Patch metrics fn, assert call arg == exact component label |
| 37 | issue strings XX-wrapped; `down > 0` -> >= 0 (always-takes branch emits "0/N targets down") / > 1; `== UNKNOWN` -> !=; `error or fallback` -> `and` | `1878` | 12 | `x__identify_monitoring_issues__mutmut_12`, `x__identify_monitoring_issues__mutmut_13`, `x__identify_monitoring_issues__mutmut_16` | TEST-GAP | Clean scenario -> assert issues == []; partial-down -> assert exact "1/3 targets..." string; unknown exporter -> exact string |
| 38 | `duration = time.time() - start_time` -> + start_time; `response_time_ms = (time.time()-start)*1000` -> /1000, +start | `1169/5241` | 9 | `x__check_ai_health_with_timeout__mutmut_16`, `x__check_ai_health_with_timeout__mutmut_8`, `x__check_ai_service_health__mutmut_77` | TEST-GAP | Patch time.time sequence, assert observed duration > 0 / equals expected ms |
| 39 | job default None/XX; job_stats counter seed "unknown":0->1; health default None -> .lower() AttributeError | `1784` | 9 | `x__build_targets_summary__mutmut_10`, `x__build_targets_summary__mutmut_24`, `x__build_targets_summary__mutmut_33` | TEST-GAP | Key-less target -> assert summary counts incl. unknown==1 |
| 40 | `circuit_breaker_name = service_config.get("circuit_breaker_name", name)` key/default mutants + `registry.get(breaker_name)` arg mutants | `5241` | 8 | `x__check_ai_service_health__mutmut_10`, `x__check_ai_service_health__mutmut_11`, `x__check_ai_service_health__mutmut_12` | TEST-GAP | Assert registry.get called with the config circuit_breaker_name (call-args assert) |
| 41 | `_health_circuit_breaker.record_failure(service_name, error_msg)` arg drop/None mutants | `948/983` | 6 | `x__check_nemotron_health_with_circuit_breaker__mutmut_17`, `x__check_nemotron_health_with_circuit_breaker__mutmut_18`, `x__check_nemotron_health_with_circuit_breaker__mutmut_19` | TEST-GAP | Patch breaker, assert record_failure called with ("yolo26", error_text) |
| 42 | `select(GPUStats).order_by(GPUStats.recorded_at.desc()).limit(1)` + `db.execute(stmt)` mutants | `754` | 6 | `x_get_latest_gpu_stats__mutmut_1`, `x_get_latest_gpu_stats__mutmut_2`, `x_get_latest_gpu_stats__mutmut_3` | TEST-GAP | Assert executed statement string contains gpu_stats / DESC / LIMIT |
| 43 | `_get_worker_status`: file_watcher `running=True/False` flips, cleanup `stats.get("running", default)` mutants | `5435` | 5 | `x__get_worker_status__mutmut_11`, `x__get_worker_status__mutmut_25`, `x__get_worker_status__mutmut_27` | TEST-GAP | Assert file_watcher entry running is True (import-success branch) and cleanup False when stats dict lacks key |
| 44 | comment/blank skip-condition flips; `split("=", 1)` -> rsplit/split(2)/drop-maxsplit -> ValueError on "KEY=A=B"; open mode kwarg drop | `2534` | 5 | `x__write_runtime_env__mutmut_14`, `x__write_runtime_env__mutmut_17`, `x__write_runtime_env__mutmut_25` | TEST-GAP | Pre-write "#BAD=1" and "A=B" lines; assert merge result / raised behavior |
| 45 | `_stats_to_schema` guard `stats.get("sample_count", 0) == 0` -> key None/0/drop-default -> guard false on empty stats -> returns object instead of None | `3136` | 5 | `x__stats_to_schema__mutmut_2`, `x__stats_to_schema__mutmut_3`, `x__stats_to_schema__mutmut_4` | TEST-GAP | _stats_to_schema({}) -> assert None |
| 46 | `peek_queue(key, 0, MAX_LATENCY_SAMPLES - 1)` window args 0->1/None, -1 drop | `3039` | 5 | `x_get_latency_stats__mutmut_10`, `x_get_latency_stats__mutmut_11`, `x_get_latency_stats__mutmut_12` | TEST-GAP | Assert peek_queue awaited with (key, 0, MAX_LATENCY_SAMPLES-1) |
| 47 | db error branch `details={"error": str(e)}` key CASE/XX, `str(e)`->`str(None)`, kwarg drop | `806` | 5 | `x_check_database_health__mutmut_66`, `x_check_database_health__mutmut_69`, `x_check_database_health__mutmut_72` | TEST-GAP | Force RuntimeError -> assert details == {"error": "msg"} |
| 48 | `httpx.AsyncClient(timeout=timeout)` -> timeout=None; inner `_check_*(url, timeout)` -> (url, None) | `887/913/948/983` | 4 | `x__check_nemotron_health__mutmut_1`, `x__check_nemotron_health_with_circuit_breaker__mutmut_14`, `x__check_yolo26_health__mutmut_1` | TEST-GAP | Patch httpx.AsyncClient / inner checker, assert timeout kwarg == passed value |
| 49 | degraded message `working_service`/`failed_service` ternary strings XX-wrapped | `1047` | 4 | `x_check_ai_services_health__mutmut_58`, `x_check_ai_services_health__mutmut_60`, `x_check_ai_services_health__mutmut_66` | TEST-GAP | Assert exact message "Nemotron service unavailable, YOLO26 operational" (case-sensitive equality) |
| 50 | `details={"redis_version": info.get("redis_version", "unknown")}` default/None mutants | `5369` | 4 | `x__check_redis_health_full__mutmut_46`, `x__check_redis_health_full__mutmut_48`, `x__check_redis_health_full__mutmut_51` | TEST-GAP | health_check dict lacking redis_version -> assert details == {"redis_version": "unknown"} |
| 51 | `if model_name in models` -> not in; `return "Other"` XX/CASE | `4974` | 4 | `x__get_model_category__mutmut_1`, `x__get_model_category__mutmut_2`, `x__get_model_category__mutmut_3` | TEST-GAP | Exact asserts: _get_model_category("yolo26") == known category; unknown -> == "Other" |
| 52 | `hasattr(k, "get_secret_value")` mutants -> str(SecretStr) hashes -> valid key rejected | `272` | 4 | `x_verify_api_key__mutmut_15`, `x_verify_api_key__mutmut_17`, `x_verify_api_key__mutmut_21` | TEST-GAP | api_keys=[SecretStr("s3cret")]; verify with "s3cret" -> no raise |
| 53 | `circuit_state=circuit_state` kwarg drop on dynamic-state returns | `5241` | 4 | `x__check_ai_service_health__mutmut_116`, `x__check_ai_service_health__mutmut_136`, `x__check_ai_service_health__mutmut_154` | TEST-GAP | half-open breaker -> assert result.circuit_state == HALF_OPEN (drop falls back to CLOSED) |
| 54 | `manager_status.get("running", False)` -> True; `.get("workers", {})` -> None (AttributeError uncaught -> 500) | `671` | 3 | `x__are_critical_pipeline_workers_healthy__mutmut_20`, `x__are_critical_pipeline_workers_healthy__mutmut_24`, `x__are_critical_pipeline_workers_healthy__mutmut_26` | TEST-GAP | get_status() dict lacking "running" -> expect False; lacking "workers" -> expect not to raise |
| 55 | `worker_info.get("workers")` key XX/CASE/None -> legacy fallback taken | `650` | 3 | `x__is_worker_group_operational__mutmut_1`, `x__is_worker_group_operational__mutmut_2`, `x__is_worker_group_operational__mutmut_3` | TEST-GAP | Multi-worker dict {"workers":[{"state":"running"}]} -> assert True (fallback would return False) |
| 56 | `httpx.AsyncClient(timeout=timeout)` -> timeout=None; `client.get(f"{url}/health")` -> get(None) | `5241` | 2 | `x__check_ai_service_health__mutmut_73`, `x__check_ai_service_health__mutmut_75` | TEST-GAP | Assert AsyncClient ctor kwargs timeout==passed timeout and get URL == url+"/health" |
| 57 | `status.get("services", {})` -> None -> .items() raises -> swallowed -> response None | `4116` | 2 | `x__get_degradation_status__mutmut_11`, `x__get_degradation_status__mutmut_9` | TEST-GAP | Assert result is not None when manager status lacks "services" |
| 58 | `open_count += 1`/`half_open_count += 1` -> `= 1` | `5402` | 2 | `x__get_circuit_breaker_summary__mutmut_23`, `x__get_circuit_breaker_summary__mutmut_30` | TEST-GAP | Register 2 open + 2 half_open breakers, assert summary.open==2 and half_open==2 |
| 59 | `db.execute(select(func.count()).select_from(Camera))` -> execute(None)/select(None) | `806` | 2 | `x_check_database_health__mutmut_2`, `x_check_database_health__mutmut_4` | TEST-GAP | Assert db.execute called with compiled SQL "cameras" (statement string) |
| 60 | `db.execute(select(func.now()))` -> execute(None)/select(None) | `~5351` | 2 | `x__check_postgres_health_full__mutmut_2`, `x__check_postgres_health_full__mutmut_3` | TEST-GAP | Assert executed statement string contains "now()" |
| 61 | `_calculate_percentile(sorted_samples, 50/95)` -> 51/96 | `2999` | 2 | `x__calculate_stage_latency__mutmut_49`, `x__calculate_stage_latency__mutmut_54` | TEST-GAP | 100 distinct samples: assert p50_ms==samples[50], p95_ms==samples[95] |
| 62 | `_bounded_health_check(..., AI_HEALTH_CHECK_TIMEOUT_SECONDS)` -> None | `1047` | 2 | `x_check_ai_services_health__mutmut_11`, `x_check_ai_services_health__mutmut_17` | TEST-GAP | Patch _bounded_health_check, assert positional 3rd arg == 3.0 |
| 63 | is_open reset path `self._failures[service] = 0` -> 1/None | `195` | 2 | `xǁCircuitBreakerǁis_open__mutmut_5`, `xǁCircuitBreakerǁis_open__mutmut_6` | TEST-GAP | After expiry, record_threshold-1 fresh failures -> assert stays closed |
| 64 | 401 detail texts XX-wrapped ("API key required...", "Invalid API key") | `272` | 2 | `x_verify_api_key__mutmut_31`, `x_verify_api_key__mutmut_8` | TEST-GAP | Assert exc.value.detail == exact string |
| 65 | `_get_supervisor_health` final `return True` -> False (healthy-supervisor path) | `719` | 1 | `x__get_supervisor_health__mutmut_2` | TEST-GAP | Mock running supervisor with healthy workers -> assert True |
| 66 | `manager = get_degradation_manager()` -> None -> AttributeError swallowed -> response None | `4116` | 1 | `x__get_degradation_status__mutmut_2` | TEST-GAP | Patch global getter to return mock -> assert response not None |

**Sum check:** 515 TEST-GAP (515 keys) + 65 EQUIVALENT (65) + 58 LOW-VALUE (58) = **638** = survivors.

## Residual EQUIVALENT / LOW-VALUE justification (why these are not drafted against)

- **Schema-default kwarg drops** (C06-CLOSED, C21 `batches=[]`, C27 `details=None`, C52 `last_scrape=None`): the
  drop lands on the Pydantic `Field` default (`circuit_state: CircuitState = Field(default=CircuitState.CLOSED)`,
  `batches: list = Field(default_factory=list)`, `details/message: ... = None`) — byte-identical serialized output.
- **Post-`.lower()` normalization** (C52/C54 health-default XX/CASE, C10 CB `get("state","closed")`, C41
  `get("state","stopped")`): the mutated default never equals the compared literals (or lowercases to the original)
  — the branch result is unchanged for every input.
- **Timestamp branch/rstrip equivalences** (C42, 10 keys): verified against Python 3.14 `datetime.fromisoformat`:
  it natively parses arbitrary fractional-digit counts and trailing `Z`, so skip-the-truncation mutants, the
  `len(parts)!=2/==3` branch flips and `rstrip("z"/"Z"[:7])` variants all return the identical datetime.
- **Unreachable defaults** (C72 s2s kwarg default, C30 `or "unhealthy"` sentinel, C36 bounded-check default,
  C14 dead scalar): guarded earlier or value never read.
- **Default-arg no-ops** (C71): deleting an explicit `.get(k, D)` / `getattr(o, a, None)` third argument that
  already equals the implicit default.
- **Log-only text** (C31, C38, C45, C66): logger call arguments; no test asserts log content (and shouldn't).
- **Boundary/measure-zero** (C37 cache `<`->`<=` TTL, C65 CB `now <= open_until`, C05 round(x,3), C48 env-path
  literal case): observable only at an exact wall-clock instant or on a case-insensitive filesystem; gen-1
  precedent keeps these LOW-VALUE.
- **Degenerate value mutants** (C62 `register_workers` `_x = None` where param default is already None; C61 44
  display-name cosmetic strings per gen-1 precedent).

## Drafted tests (7 drafts across 3 files)

### Draft 1 — `_get_degradation_status` full-payload contract
**File:** `backend/tests/unit/api/routes/test_system.py` (append to `class TestDegradationStatus`, ~:767)
**Kills:** C09-deg-payload (54), C09-deg-services-iter (2), C32-deg-manager-tg (1)
**TDD:** add test -> expect RED on current code (mutant `fallback_queues=None` / services key mutants survive) -> implement nothing in prod, confirm the *test* passes on the original -> rerun mutmut subset to see cluster die.

```python
    def test_get_degradation_status_full_payload_contract(self) -> None:
        """Every payload slot of DegradationStatusResponse must mirror manager.get_status().

        Guards the .get(key, default) fan-out in _get_degradation_status: a key-name or
        default mutant must be visible through exact equality, including the
        fallback_queues=None -> ValidationError -> whole-response-None failure mode.
        """
        import backend.api.routes.system as system_module

        mock_manager = MagicMock()
        mock_manager.get_status.return_value = {
            "mode": "degraded",
            "is_degraded": True,
            "redis_healthy": False,
            "memory_queue_size": 7,
            "fallback_queues": {"events": 3, "videos": 4},
            "services": {
                "nemotron": {
                    "status": "unhealthy",
                    "last_check": 1712345678.5,
                    "consecutive_failures": 2,
                    "error_message": "connection refused",
                }
            },
            "available_features": ["detect", "watch"],
        }
        original = system_module._degradation_manager
        try:
            system_module._degradation_manager = mock_manager
            result = _get_degradation_status()
        finally:
            system_module._degradation_manager = original

        assert result is not None
        assert result.mode.value == "degraded"
        assert result.is_degraded is True
        assert result.redis_healthy is False
        assert result.memory_queue_size == 7
        assert result.fallback_queues == {"events": 3, "videos": 4}
        assert result.available_features == ["detect", "watch"]
        (svc,) = result.services
        assert svc.name == "nemotron"
        assert svc.status == "unhealthy"
        assert svc.last_check == 1712345678.5
        assert svc.consecutive_failures == 2
        assert svc.error_message == "connection refused"

    def test_get_degradation_status_defaults_on_partial_status(self) -> None:
        """Manager status missing optional keys must fall back to documented defaults."""
        import backend.api.routes.system as system_module

        mock_manager = MagicMock()
        # Only "mode" is provided: every .get(...) default path is exercised.
        mock_manager.get_status.return_value = {"mode": "normal"}
        original = system_module._degradation_manager
        try:
            system_module._degradation_manager = mock_manager
            result = _get_degradation_status()
        finally:
            system_module._degradation_manager = original

        assert result is not None  # services-iter mutants return None here
        assert result.mode.value == "normal"
        assert result.is_degraded is False
        assert result.redis_healthy is False
        assert result.memory_queue_size == 0
        assert result.fallback_queues == {}
        assert result.services == []
        assert result.available_features == []

    def test_get_degradation_status_falls_back_to_global_getter(self) -> None:
        """When the module global is unset, get_degradation_manager() must still be used."""
        import backend.api.routes.system as system_module
        from unittest.mock import patch

        mock_manager = MagicMock()
        mock_manager.get_status.return_value = {"mode": "minimal", "is_degraded": True}
        original = system_module._degradation_manager
        try:
            system_module._degradation_manager = None
            with patch(
                "backend.services.degradation_manager.get_degradation_manager",
                return_value=mock_manager,
                autospec=True,
            ):
                result = _get_degradation_status()
        finally:
            system_module._degradation_manager = original

        assert result is not None  # manager = None mutant swallows AttributeError -> None
        assert result.mode.value == "minimal"
        assert result.is_degraded is True
```
// UNVERIFIED - not yet run red/green

### Draft 2 — `_get_worker_statuses` partial-dict contract (pipeline workers)
**File:** `backend/tests/unit/api/routes/test_system.py` (append to `class TestWorkerStatus`, ~:485)
**Kills:** C35-wk-contract (63, all sub-slots), C39-acp-defaults (3), C40-iwgo-workers-key (3), plus C73's "Not running" members
**TDD:** add -> RED on mutants via mutmut subset run (WP4.4 lane); should be GREEN on original code.

```python
    def test_worker_statuses_pipeline_partial_dicts(self) -> None:
        """Pipeline worker blocks must honor key names, defaults and messages exactly.

        C35 kill-path: dicts that OMIT workers/state/running keys plus exact
        running/message/name assertions per worker entry.
        """
        mock_manager = MagicMock()
        mock_manager.get_status.return_value = {
            "running": True,
            "workers": {
                # legacy single-worker shape, no "workers" list
                "detection": {"state": "stopped"},
                # multi-worker shape; state aggregation picks "running" from error
                "analysis": {"count": 1, "workers": [{"state": "error"}]},
                # timeout entry WITHOUT a state key -> legacy default "stopped"
                "timeout": {},
                # metrics entry WITHOUT a running key -> default False
                "metrics": {},
            },
        }
        register_workers(
            gpu_monitor=None,
            cleanup_service=None,
            system_broadcaster=None,
            file_watcher=None,
            pipeline_manager=mock_manager,
        )
        try:
            statuses = _get_worker_statuses()
        finally:
            register_workers(pipeline_manager=None)

        status_dict = {s.name: s for s in statuses}
        assert status_dict["detection_worker"].running is False
        assert status_dict["detection_worker"].message == "State: stopped"
        assert status_dict["analysis_worker"].running is True
        assert status_dict["analysis_worker"].message is None
        assert status_dict["batch_timeout_worker"].running is False
        assert status_dict["batch_timeout_worker"].message == "State: stopped"
        assert status_dict["batch_aggregator"].running is False
        assert status_dict["batch_aggregator"].message == "State: stopped"
        assert status_dict["metrics_worker"].running is False
        assert status_dict["metrics_worker"].message == "Not running"

    def test_worker_statuses_defaults_when_attrs_missing(self) -> None:
        """Objects without a running attribute must report running=False, message='Not running'."""
        gpu_obj = object()   # getattr(_gpu_monitor, "running", False) default path
        broadcaster_obj = object()  # getattr(_system_broadcaster, "_running", False)
        file_watcher_obj = object()
        register_workers(
            gpu_monitor=gpu_obj,
            system_broadcaster=broadcaster_obj,
            file_watcher=file_watcher_obj,
            cleanup_service=None,
            pipeline_manager=None,
        )
        try:
            statuses = _get_worker_statuses()
        finally:
            register_workers(
                gpu_monitor=None, system_broadcaster=None, file_watcher=None
            )

        status_dict = {s.name: s for s in statuses}
        assert status_dict["gpu_monitor"].running is False
        assert status_dict["gpu_monitor"].message == "Not running"
        assert status_dict["system_broadcaster"].running is False
        assert status_dict["file_watcher"].running is False
        assert status_dict["file_watcher"].message == "Not running"

    def test_critical_workers_partial_manager_status(self) -> None:
        """_are_critical_pipeline_workers_healthy defaults: missing running -> False,
        missing workers -> empty dict (no crash); multi-worker groups use the
        'workers' list, not the legacy state fallback."""
        stopped_default = MagicMock()
        stopped_default.get_status.return_value = {"workers": {}}
        register_workers(pipeline_manager=stopped_default)
        try:
            assert _are_critical_pipeline_workers_healthy() is False
        finally:
            register_workers(pipeline_manager=None)

        no_workers = MagicMock()
        no_workers.get_status.return_value = {"running": True}
        register_workers(pipeline_manager=no_workers)
        try:
            assert _are_critical_pipeline_workers_healthy() is True  # {} default; None mutant raises
        finally:
            register_workers(pipeline_manager=None)

        multi = MagicMock()
        multi.get_status.return_value = {
            "running": True,
            "workers": {
                "detection": {"count": 1, "workers": [{"state": "error"}]},
                "analysis": {"count": 1, "workers": [{"state": "running"}]},
            },
        }
        register_workers(pipeline_manager=multi)
        try:
            assert _are_critical_pipeline_workers_healthy() is True
        finally:
            register_workers(pipeline_manager=None)
```
// UNVERIFIED - not yet run red/green

### Draft 3 — monitoring helpers exact-contract suite
**File:** `backend/tests/unit/api/routes/test_system.py` (append to `class TestMonitoringHealthHelpers`, ~:2101)
**Kills:** C51 (12), C53 (59), C55 (9), C69 partial, C73 members for exporter error text
**TDD:** add -> run -> GREEN on original; then `uv run mutmut check <subset>` (WP4.4 lane) to confirm cluster death.

```python
    def test_exporter_status_exact_contract_matched_and_unmatched(self) -> None:
        """Matched target must map endpoint/last_scrape/error exactly; unmatched target
        must expose the KNOWN default endpoint + exact fallback error text."""
        from backend.api.routes.system import _build_exporter_status

        targets = [
            {
                "job": "redis_exporter",
                "instance": "prom-redis:9121",
                "health": "UP",
                "lastScrape": "2024-01-15T10:30:00.123456789Z",
                "lastError": "",
            },
            {
                "job": "other",
                "instance": "json-host:7979",
                "health": "down",
                "lastScrape": None,
                "lastError": "connection refused",
            },
        ]
        result = {e.name: e for e in _build_exporter_status(targets)}

        redis = result["redis-exporter"]
        assert redis.status.value == "up"          # .lower() normalization of "UP"
        assert redis.endpoint == "prom-redis:9121"  # target instance wins
        assert redis.last_scrape is not None
        assert redis.last_scrape.microsecond == 123456  # ns truncated to us
        assert redis.last_scrape.utcoffset().total_seconds() == 0
        assert redis.error is None

        js = result["json-exporter"]
        assert js.status.value == "down"
        assert js.error == "connection refused"

        bb = result["blackbox-exporter"]
        assert bb.status.value == "unknown"
        assert bb.endpoint == "http://blackbox-exporter:9115"  # KNOWN default endpoint
        assert bb.error == "Exporter not found in Prometheus targets"  # exact text

    def test_targets_summary_counts_keyless_and_partial_targets(self) -> None:
        """Targets without job/health must count under 'unknown'; 'unknown' seed is 0."""
        from backend.api.routes.system import _build_targets_summary

        targets = [
            {"job": "node", "health": "up"},
            {},                      # no job, no health -> unknown bucket
            {"job": "node"},         # no health -> unknown count for node
        ]
        result = {s.job: s for s in _build_targets_summary(targets)}
        assert result["node"].total == 2
        assert result["node"].up == 1
        assert result["node"].down == 0
        assert result["node"].unknown == 1
        assert result["unknown"].total == 1
        assert result["unknown"].unknown == 1

    def test_identify_issues_exact_strings_and_empty_case(self) -> None:
        """Issue fan-out: exact strings, no issue when all healthy, partial-down ratio text."""
        from backend.api.routes.system import ExporterStatus, ExporterStatusEnum, _identify_monitoring_issues
        from backend.api.schemas.system import JobTargetSummary

        # Fully healthy -> NO issues (kills `down > 0` -> `>= 0` always-taken branch)
        healthy = [JobTargetSummary(job="node", total=3, up=3, down=0)]
        assert _identify_monitoring_issues(True, healthy, []) == []

        partial = [JobTargetSummary(job="node", total=3, up=2, down=1)]
        assert _identify_monitoring_issues(True, partial, []) == [
            "1/3 targets in job 'node' are down"
        ]

        alldown = [JobTargetSummary(job="node", total=2, up=0, down=2)]
        assert _identify_monitoring_issues(True, alldown, []) == [
            "All targets in job 'node' are down"
        ]

        exporters = [
            ExporterStatus(name="redis-exporter", status=ExporterStatusEnum.DOWN,
                           endpoint="http://x:9121", error="connection refused"),
            ExporterStatus(name="json-exporter", status=ExporterStatusEnum.UNKNOWN,
                           endpoint="http://y:7979"),
        ]
        issues = _identify_monitoring_issues(True, [], exporters)
        assert issues == [
            "Exporter 'redis-exporter' is down: connection refused",
            "Exporter 'json-exporter' status unknown (not in Prometheus targets)",
        ]

        assert _identify_monitoring_issues(False, [], []) == [
            "Prometheus server is not reachable"
        ]
```
// UNVERIFIED - not yet run red/green

### Draft 4 — health-check payload + statement exactness (db / redis / postgres)
**File:** `backend/tests/unit/api/routes/test_system.py` (append near `TestCheckDatabaseHealthFunction` :1857) and `test_health_full.py`
**Kills:** C15 (33), C70 (4), C12 (2), C13 (2), C57 (4), C59 (34), C73 (db/redis message members)
**TDD:** add -> GREEN on original; mutmut subset run kills C15/C59/C70/C12/C13/C57.

```python
    @pytest.mark.asyncio
    async def test_check_database_health_exact_pool_contract(self) -> None:
        """Pool details dict must expose all five keys with 0-defaults; statement shape asserted."""
        from unittest.mock import patch
        from sqlalchemy.ext.asyncio import AsyncSession
        from backend.api.routes.system import check_database_health

        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.execute.return_value = MagicMock()

        with patch(
            "backend.core.database.get_pool_status",
            AsyncMock(return_value={"pool_size": 5, "overflow": 2}),
        ):
            result = await check_database_health(mock_db)

        assert result.status == "healthy"
        assert result.message == "Database operational"
        assert result.details == {
            "pool": {
                "size": 5,
                "overflow": 2,
                "checkedin": 0,     # .get(k, 0) default mutants die here
                "checkedout": 0,
                "total_connections": 0,
            }
        }
        stmt_sql = str(mock_db.execute.call_args.args[0])
        assert "cameras" in stmt_sql.lower()   # select(...).select_from(Camera)

    @pytest.mark.asyncio
    async def test_check_database_health_error_details_exact(self) -> None:
        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.execute.side_effect = RuntimeError("boom")
        from backend.api.routes.system import check_database_health

        result = await check_database_health(mock_db)
        assert result.status == "unhealthy"
        assert result.message == "Database error: boom"
        assert result.details == {"error": "boom"}

    @pytest.mark.asyncio
    async def test_check_redis_health_exact_payloads(self) -> None:
        """All three redis branches: exact message + exact details dict."""
        from backend.core.redis import RedisClient
        from backend.api.routes.system import check_redis_health

        none_result = await check_redis_health(None)
        assert none_result.message == "Redis unavailable: connection failed"
        assert none_result.details == {"error": "Redis client not available"}

        mock_redis = AsyncMock(spec=RedisClient)
        mock_redis.health_check.return_value = {"status": "healthy"}  # NO redis_version
        ok = await check_redis_health(mock_redis)
        assert ok.message == "Redis connected"
        assert ok.details == {"redis_version": "unknown"}

        mock_redis.health_check.return_value = {"status": "bad"}
        bad = await check_redis_health(mock_redis)
        assert bad.message == "Redis connection error"
        assert bad.details == {"error": "Redis connection error"}

        mock_redis.health_check.side_effect = ConnectionError("refused")
        exc = await check_redis_health(mock_redis)
        assert exc.message == "Redis error: refused"
        assert exc.details == {"error": "refused"}
```
In `test_health_full.py`:

```python
@pytest.mark.asyncio
async def test_check_redis_health_full_missing_version_default() -> None:
    """details must fall back to redis_version='unknown' (default mutants kill-path)."""
    mock_redis = AsyncMock(spec=RedisClient)
    mock_redis.health_check.return_value = {"status": "healthy"}
    result = await _check_redis_health_full(mock_redis)
    assert result.details == {"redis_version": "unknown"}


@pytest.mark.asyncio
async def test_check_postgres_health_full_executes_now_statement() -> None:
    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.execute.return_value = MagicMock()
    await _check_postgres_health_full(mock_db)
    assert "now" in str(mock_db.execute.call_args.args[0]).lower()
```
// UNVERIFIED - not yet run red/green

### Draft 5 — `_check_ai_service_health` response fields + HTTP/circuit-breaker call args
**File:** `backend/tests/unit/api/routes/test_health_full.py` (append at end) + `test_system.py`
**Kills:** C01 (18), C02 (8), C03 (2), C07 (25), C19 (4), C20 (6), C28 (4), C74 (4), C73 (AI message members)
**TDD:** add -> GREEN; mutmut subset run kills payload/label clusters.

```python
@pytest.mark.asyncio
async def test_check_ai_service_health_healthy_payload_exact() -> None:
    """url / response_time_ms / last_check / breaker lookup key / client timeout kwargs."""
    mock_settings = MagicMock(spec=Settings)
    mock_settings.yolo26_url = "http://ai-yolo26:8095"
    service_config = {
        "name": "yolo26",
        "display_name": "YOLO26 Object Detection",
        "url_attr": "yolo26_url",
        "circuit_breaker_name": "yolo26-breaker",
        "critical": True,
    }

    with patch("backend.services.circuit_breaker._get_registry", autospec=True) as mock_registry:
        mock_registry.return_value.get.return_value = None
        with patch("httpx.AsyncClient", autospec=True) as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            result = await _check_ai_service_health(service_config, mock_settings, timeout=2.5)

    assert result.url == "http://ai-yolo26:8095"        # C07: url=None/drop dies
    assert result.last_check is not None                 # C01: last_check=None/drop dies
    assert result.last_check.tzinfo is not None          # now(None) dies
    assert result.response_time_ms is not None           # C07: ms mutants die
    assert result.response_time_ms >= 0.0                # sign/scale mutants die
    mock_registry.return_value.get.assert_called_once_with("yolo26-breaker")  # C02
    ctor_kwargs = mock_client.call_args.kwargs
    assert ctor_kwargs["timeout"] == 2.5                 # C03/C19: timeout=None dies
    mock_client.return_value.__aenter__.return_value.get.assert_awaited_once_with(
        "http://ai-yolo26:8095/health"
    )


@pytest.mark.asyncio
async def test_check_ai_service_health_half_open_state_survives_kwarg_drop() -> None:
    """circuit_state must carry HALF_OPEN through the healthy-path return (C74)."""
    mock_settings = MagicMock(spec=Settings)
    mock_settings.yolo26_url = "http://ai-yolo26:8095"
    service_config = {
        "name": "yolo26",
        "display_name": "YOLO26 Object Detection",
        "url_attr": "yolo26_url",
        "circuit_breaker_name": "yolo26",
        "critical": True,
    }
    with patch("backend.services.circuit_breaker._get_registry", autospec=True) as mock_registry:
        breaker = MagicMock()
        breaker.state.value = "half_open"
        mock_registry.return_value.get.return_value = breaker
        with patch("httpx.AsyncClient", autospec=True) as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            result = await _check_ai_service_health(service_config, mock_settings)
    assert result.circuit_state == CircuitState.HALF_OPEN


def test_circuit_breaker_summary_multi_count() -> None:
    """open_count += 1 mutants (= 1) die with 2+2 mixed states."""
    with patch("backend.services.circuit_breaker._get_registry", autospec=True) as mock_registry:
        mock_registry.return_value.get_all_status.return_value = {
            "a": {"state": "open"}, "b": {"state": "open"},
            "c": {"state": "half_open"}, "d": {"state": "half_open"},
            "e": {"state": "closed"},
        }
        result = _get_circuit_breaker_summary()
    assert (result.total, result.open, result.half_open, result.closed) == (5, 2, 2, 1)
```
In `test_system.py` (AI batch side): exact degraded message + breaker call args:

```python
    @pytest.mark.asyncio
    async def test_ai_batch_degraded_message_exact(self) -> None:
        """Degraded message must be exactly '<failed> service unavailable, <working> operational'."""
        from unittest.mock import patch
        from backend.api.routes.system import check_ai_services_health

        async def fake_bounded(check_func, url, timeout):
            assert timeout == 3.0  # C29: AI_HEALTH_CHECK_TIMEOUT_SECONDS -> None dies
            name = getattr(check_func, "__name__", "")
            if "yolo26" in name:
                return (True, None)
            return (False, "Nemotron service connection refused")

        mock_settings = MagicMock()
        mock_settings.yolo26_url = "http://y:8095"
        mock_settings.nemotron_url = "http://n:8091"
        with patch("backend.api.routes.system.get_settings", return_value=mock_settings), \
             patch("backend.api.routes.system._bounded_health_check", side_effect=fake_bounded):
            result = await check_ai_services_health()
        assert result.status == "degraded"
        assert result.message == "Nemotron service unavailable, YOLO26 operational"
        assert result.details == {
            "yolo26": "healthy",
            "nemotron": "Nemotron service connection refused",
        }
```
// UNVERIFIED - not yet run red/green

### Draft 6 — kill-path misc bundle (CB reset, percentiles, latency window, GPU, runtime env, supervisor, verify_api_key)
**File:** `test_system.py` (+ `test_telemetry_api.py` for the latency test)
**Kills:** C67 (2), C23 (2), C50 (5), C33 (6), C34 (38), C47 (5), C25 (1), C63 (4), C69 (2), C49/C72 guard members (5), C26 (5)
**TDD:** add -> GREEN; one mutmut subset run closes the bundle.

```python
    def test_circuit_breaker_expiry_resets_failure_counter(self) -> None:
        """After reset expiry the failure counter must be back to 0 (C67: =1/=None die)."""
        from datetime import timedelta
        breaker = CircuitBreaker(failure_threshold=2, reset_timeout=timedelta(milliseconds=1))
        breaker.record_failure("svc", "x")
        breaker.record_failure("svc", "x")          # opens
        assert breaker.is_open("svc") is True
        time.sleep(0.01)                              # expiry
        assert breaker.is_open("svc") is False        # reset path runs: _failures=0
        breaker.record_failure("svc", "x")            # one failure only...
        assert breaker.is_open("svc") is False        # ...must NOT open (a reset-to-1 mutant would)

    def test_calculate_stage_latency_percentiles_100(self) -> None:
        """p50/p95 must index exactly 50/95 on 100 samples (51/96 mutants die)."""
        samples = [float(i) for i in range(1, 101)]  # sorted 1..100
        latency = _calculate_stage_latency(samples)
        assert latency.p50_ms == 51.0   # index int(100*50/100)=50 -> samples[50]
        assert latency.p95_ms == 96.0   # index 95 -> samples[95]
        assert latency.p99_ms == 100.0  # clamped last

    @pytest.mark.asyncio
    async def test_latency_stats_peek_window_args(self) -> None:
        """peek_queue must receive (key, 0, MAX_LATENCY_SAMPLES - 1) per stage."""
        from backend.api.routes.system import get_latency_stats, MAX_LATENCY_SAMPLES

        mock_redis = AsyncMock()
        mock_redis.peek_queue.return_value = []
        await get_latency_stats(mock_redis)
        assert mock_redis.peek_queue.await_count == 4  # PIPELINE_STAGES
        for call in mock_redis.peek_queue.await_args_list:
            key, start, stop = call.args
            assert key.startswith("telemetry:latency:")
            assert start == 0
            assert stop == MAX_LATENCY_SAMPLES - 1

    def test_stats_to_schema_empty_dict_returns_none(self) -> None:
        assert _stats_to_schema({}) is None
        assert _stats_to_schema({"sample_count": 0}) is None

    @pytest.mark.asyncio
    async def test_gpu_stats_statement_and_full_keys(self) -> None:
        """Latest-stat query shape + the 19 extended keys XX/CASE mutants (C33/C34)."""
        mock_db = AsyncMock(spec=AsyncSession)
        gpu_stat = MagicMock()
        gpu_stat.recorded_at = datetime.now(UTC)
        mock_db.execute.return_value.scalar_one_or_none.return_value = gpu_stat
        result = await get_latest_gpu_stats(mock_db)
        stmt_sql = str(mock_db.execute.call_args.args[0])
        assert "gpu_stats" in stmt_sql.lower()
        assert "LIMIT 1" in stmt_sql.upper() and "DESC" in stmt_sql.upper()
        assert set(result) == {
            "recorded_at", "gpu_name", "utilization", "memory_used", "memory_total",
            "temperature", "power_usage", "inference_fps", "fan_speed", "sm_clock",
            "memory_bandwidth_utilization", "pstate", "throttle_reasons", "power_limit",
            "sm_clock_max", "compute_processes_count", "pcie_replay_counter",
            "temp_slowdown_threshold", "memory_clock", "memory_clock_max",
            "pcie_link_gen", "pcie_link_width", "pcie_tx_throughput",
            "pcie_rx_throughput", "encoder_utilization", "decoder_utilization", "bar1_used",
        }

    def test_write_runtime_env_edge_cases(self, tmp_path, monkeypatch) -> None:
        """Comment lines / no-'=' lines are skipped; values may contain '='; legacy
        KEY=A=B line is tolerated (split('=', 2) mutant raises ValueError)."""
        from backend.api.routes.system import _write_runtime_env, _runtime_env_path
        env_file = tmp_path / "runtime.env"
        monkeypatch.setenv("HSI_RUNTIME_ENV_PATH", str(env_file))
        env_file.write_text("# comment=with-equals\nnoequalsline\nA=B\n", encoding="utf-8")
        _write_runtime_env({"NEW": "x=y"})
        lines = dict(
            ln.split("=", 1) for ln in env_file.read_text(encoding="utf-8").splitlines() if "=" in ln
        )
        assert lines == {"A": "B", "NEW": "x=y"}

    def test_supervisor_healthy_returns_true(self) -> None:
        """Healthy running supervisor with no failed workers -> True (C25 final-return flip)."""
        import backend.api.routes.system as system_module
        supervisor = MagicMock()
        supervisor.is_running = True
        w = MagicMock()
        w.status.value = "running"
        supervisor.get_all_workers.return_value = {"w1": w}
        original = system_module._worker_supervisor
        try:
            system_module._worker_supervisor = supervisor
            assert _get_supervisor_health() is True
        finally:
            system_module._worker_supervisor = original

    @pytest.mark.asyncio
    async def test_verify_api_key_accepts_secretstr_keys(self) -> None:
        """hasattr(k,'get_secret_value') mutants hash str(SecretStr) -> valid key rejected (C63)."""
        from pydantic import SecretStr
        from fastapi import HTTPException
        import hashlib
        mock_settings = MagicMock()
        mock_settings.api_key_enabled = True
        mock_settings.api_keys = [SecretStr("s3cret")]
        with patch("backend.api.routes.system.get_settings", return_value=mock_settings):
            await verify_api_key(x_api_key="s3cret")  # must not raise
        with patch("backend.api.routes.system.get_settings", return_value=mock_settings):
            with pytest.raises(HTTPException) as exc:
                await verify_api_key(x_api_key="wrong")
            assert exc.value.status_code == 401
            assert exc.value.detail == "Invalid API key"   # C69 XX text dies
        with patch("backend.api.routes.system.get_settings", return_value=mock_settings):
            with pytest.raises(HTTPException) as exc:
                await verify_api_key(x_api_key=None)
            assert exc.value.detail == "API key required. Provide via X-API-Key header."
```
// UNVERIFIED - not yet run red/green

## Method notes (gen-2)

- Diffs extracted by span-diffing each `def x...__mutmut_N` copy vs its `__mutmut_orig` sibling inside the
  mutant copy; 9 boundary members re-verified with read-only `uv run mutmut show` (all passed <60s; no cache
  contention hit). Bookkeeping lines (`mutants_...: MutantDict`, `['_mutmut_orig'] = ...`) filtered from spans.
- Classification doctrine (this generation): any mutant that alters a string/number observable in an endpoint/
  helper **return value** (incl. response `message`/`error` texts) is a TEST-GAP if an exact-`==` assert can kill
  it — lowercase-substring asserts do not count; CASE/XX mutants of internal comparison constants whose outcome
  cannot change (post-normalization, branch-unreachable) are EQUIVALENT; measure-zero and degenerate value mutants
  are LOW-VALUE. This reclassified ~240 survivors relative to gen-1 (notably all message-text CASE/XX survivors
  in `_check_*_health`, `check_redis_health`, `_get_worker_statuses`, `_emit_health_status_changes`).
