#!/usr/bin/env python3
"""Audit Grafana dashboard PromQL queries and identify broken queries.

This script analyzes all Grafana dashboards in the monitoring/grafana/dashboards
directory and identifies PromQL queries that reference metrics that don't exist
or have label mismatches.

Usage:
    uv run python scripts/audit_grafana_queries.py

NEM-4153: Audit and fix broken Grafana PromQL queries.

See also: docs/development/metrics-implementation-status.md for the full
implementation status of all metrics referenced in dashboards.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# =============================================================================
# Known metrics by source
# =============================================================================

# Metrics exported by backend /api/metrics endpoint (from metrics.py)
BACKEND_HSI_METRICS = {
    # Queue depth gauges
    "hsi_detection_queue_depth",
    "hsi_analysis_queue_depth",
    "hsi_dlq_depth",
    # Worker supervisor metrics
    "hsi_worker_restarts_total",
    "hsi_worker_crashes_total",
    "hsi_worker_heartbeat_missed_total",
    "hsi_worker_max_restarts_exceeded_total",
    "hsi_worker_status",
    "hsi_pipeline_worker_restarts_total",
    "hsi_pipeline_worker_restart_duration_seconds",
    "hsi_pipeline_worker_state",
    "hsi_pipeline_worker_consecutive_failures",
    "hsi_pipeline_worker_uptime_seconds",
    "hsi_worker_active_count",
    "hsi_worker_busy_count",
    "hsi_worker_idle_count",
    # Stage duration histograms
    "hsi_stage_duration_seconds",
    # Event/detection counters
    "hsi_events_created_total",
    "hsi_detections_processed_total",
    "hsi_detections_by_class_total",
    "hsi_detection_confidence",
    "hsi_detections_filtered_low_confidence_total",
    # AI service histograms
    "hsi_ai_request_duration_seconds",
    "hsi_yolo26_inference_seconds",
    "hsi_nemotron_inference_seconds",
    "hsi_florence_inference_seconds",
    # Pipeline errors
    "hsi_pipeline_errors_total",
    # Risk analysis
    "hsi_risk_score",
    "hsi_events_by_risk_level_total",
    "hsi_prompt_template_used_total",
    # LLM context utilization
    "hsi_llm_context_utilization",
    "hsi_llm_context_utilization_ratio",
    "hsi_prompts_truncated_total",
    "hsi_prompts_high_utilization_total",
    # Business metrics
    "hsi_florence_task_total",
    "hsi_enrichment_model_calls_total",
    "hsi_enrichment_retry_total",
    "hsi_enrichment_success_rate",
    "hsi_enrichment_partial_batches_total",
    "hsi_enrichment_failures_total",
    "hsi_enrichment_batch_status_total",
    "hsi_enrichment_model_duration_seconds",
    "hsi_enrichment_model_errors_total",
    "hsi_events_by_camera_total",
    "hsi_events_reviewed_total",
    "hsi_events_acknowledged_total",
    # Queue overflow metrics
    "hsi_queue_overflow_total",
    "hsi_queue_items_moved_to_dlq_total",
    "hsi_queue_items_dropped_total",
    "hsi_queue_items_rejected_total",
    # Cache metrics
    "hsi_cache_hits_total",
    "hsi_cache_misses_total",
    "hsi_cache_invalidations_total",
    "hsi_cache_stale_hits_total",
    "hsi_cache_background_refresh_total",
    "hsi_redis_pool_size",
    "hsi_redis_pool_available",
    "hsi_redis_pool_in_use",
    # Token usage
    "hsi_nemotron_tokens_input_total",
    "hsi_nemotron_tokens_output_total",
    "hsi_nemotron_tokens_per_second",
    "hsi_nemotron_token_cost_usd_total",
    # Cost tracking
    "hsi_gpu_seconds_total",
    "hsi_estimated_cost_usd_total",
    "hsi_event_analysis_cost_usd_total",
    "hsi_daily_cost_usd",
    "hsi_monthly_cost_usd",
    "hsi_budget_utilization_ratio",
    "hsi_budget_exceeded_total",
    "hsi_cost_per_detection_usd",
    "hsi_cost_per_event_usd",
    # Video analytics metrics
    "hsi_tracks_created_total",
    "hsi_tracks_lost_total",
    "hsi_tracks_reidentified_total",
    "hsi_track_duration_seconds",
    "hsi_track_active_count",
    "hsi_zone_crossings_total",
    "hsi_zone_intrusions_total",
    "hsi_zone_occupancy",
    "hsi_zone_dwell_time_seconds",
    "hsi_loitering_alerts_total",
    "hsi_loitering_dwell_time_seconds",
    "hsi_loitering_events_total",
    "hsi_action_recognition_total",
    "hsi_action_recognition_confidence",
    "hsi_action_recognition_duration_seconds",
    "hsi_face_detections_total",
    "hsi_face_quality_score",
    "hsi_face_embeddings_generated_total",
    "hsi_face_recognition_confidence",
    "hsi_face_matches_total",
    "hsi_face_embedding_duration_seconds",
    "hsi_known_faces_database_size",
    "hsi_reid_matches_total",
    "hsi_reid_attempts_total",
    "hsi_reid_match_duration_seconds",
    "hsi_cross_camera_handoffs_total",
    "hsi_active_tracks_count",
    # Circuit breaker metrics
    "hsi_circuit_breaker_state",
    "hsi_circuit_breaker_trips_total",
}

# Metrics from JSON exporter (gpu, stats, telemetry modules)
JSON_EXPORTER_METRICS = {
    # Health module
    "hsi_system_healthy",
    "hsi_database_healthy",
    "hsi_redis_healthy",
    "hsi_ai_healthy",
    # Telemetry module
    "hsi_detect_latency_avg_ms",
    "hsi_detect_latency_p95_ms",
    "hsi_detect_latency_p99_ms",
    "hsi_batch_latency_avg_ms",
    "hsi_batch_latency_p95_ms",
    "hsi_batch_latency_p99_ms",
    "hsi_analyze_latency_avg_ms",
    "hsi_analyze_latency_p95_ms",
    "hsi_analyze_latency_p99_ms",
    # Stats module
    "hsi_total_cameras",
    "hsi_total_events",
    "hsi_total_detections",
    "hsi_uptime_seconds",
    # GPU module
    "hsi_gpu_utilization",
    "hsi_gpu_memory_used_mb",
    "hsi_gpu_memory_total_mb",
    "hsi_gpu_temperature",
    "hsi_inference_fps",
    "hsi_gpu_fan_speed",
    "hsi_gpu_sm_clock_mhz",
    "hsi_gpu_memory_bandwidth_utilization",
    "hsi_gpu_pstate",
    "hsi_gpu_throttle_reasons",
    "hsi_gpu_power_limit_watts",
    "hsi_gpu_sm_clock_max_mhz",
    "hsi_gpu_compute_processes",
    "hsi_gpu_pcie_replay_counter",
    "hsi_gpu_temp_slowdown_threshold",
    "hsi_gpu_memory_clock_mhz",
    "hsi_gpu_memory_clock_max_mhz",
    "hsi_gpu_pcie_link_gen",
    "hsi_gpu_pcie_link_width",
    "hsi_gpu_pcie_tx_throughput_kbs",
    "hsi_gpu_pcie_rx_throughput_kbs",
    "hsi_gpu_encoder_utilization",
    "hsi_gpu_decoder_utilization",
    "hsi_gpu_bar1_used_mb",
}

# Metrics from AI services
YOLO26_METRICS = {
    "yolo26_inference_duration_seconds",
    "yolo26_requests_total",
    "yolo26_detections_total",
    "yolo26_vram_bytes",
    "yolo26_errors_total",
    "yolo26_batch_size",
    "yolo26_inference_requests_total",
    "yolo26_inference_latency_seconds",
    "yolo26_detections_per_image",
    "yolo26_model_loaded",
    "yolo26_model_inference_healthy",
    "yolo26_gpu_utilization_percent",
    "yolo26_gpu_memory_used_gb",
    "yolo26_gpu_temperature_celsius",
    "yolo26_gpu_power_watts",
}

FLORENCE_METRICS = {
    "florence_inference_requests_total",
    "florence_inference_latency_seconds",
    "florence_model_loaded",
    "florence_gpu_memory_used_gb",
}

CLIP_METRICS = {
    "clip_inference_requests_total",
    "clip_inference_latency_seconds",
    "clip_model_loaded",
    "clip_gpu_memory_used_gb",
    "clip_backend_type",
}

ENRICHMENT_METRICS = {
    "enrichment_action_recognition_inferences_total",
    "enrichment_action_recognition_inference_latency_seconds",
    "enrichment_action_recognition_confidence",
    "enrichment_action_recognition_frames_processed_total",
    "enrichment_pose_estimation_inferences_total",
    "enrichment_pose_estimation_inference_latency_seconds",
    "enrichment_pose_keypoints_detected",
    "enrichment_pose_suspicious_alerts_total",
    "enrichment_reid_embeddings_generated_total",
    "enrichment_reid_embedding_latency_seconds",
    "enrichment_reid_matches_total",
    "enrichment_reid_match_similarity",
    "enrichment_threat_detection_inferences_total",
    "enrichment_threat_detection_inference_latency_seconds",
    "enrichment_threat_alerts_total",
    "enrichment_demographics_inferences_total",
    "enrichment_demographics_inference_latency_seconds",
    "enrichment_face_quality_assessments_total",
    "enrichment_face_quality_scores",
    "enrichment_inference_requests_total",
    "enrichment_inference_latency_seconds",
    "enrichment_vehicle_model_loaded",
    "enrichment_pet_model_loaded",
    "enrichment_clothing_model_loaded",
    "enrichment_depth_model_loaded",
    "enrichment_model_load_time_seconds",
    "enrichment_gpu_memory_used_gb",
}

# Recording rules from prometheus-rules.yml
RECORDING_RULES = {
    "hsi:api_requests:success_rate_5m",
    "hsi:api_availability:ratio_rate1h",
    "hsi:api_availability:ratio_rate6h",
    "hsi:api_availability:ratio_rate1d",
    "hsi:api_availability:ratio_rate30d",
    "hsi:detection_latency:p95_5m",
    "hsi:detection_latency:p99_5m",
    "hsi:detection:success_rate_5m",
    "hsi:detection_latency:within_slo_rate5m",
    "hsi:analysis_latency:p95_5m",
    "hsi:analysis_latency:p99_5m",
    "hsi:analysis:success_rate_5m",
    "hsi:analysis_latency:within_slo_rate5m",
    "hsi:backend:healthy",
    "hsi:redis:healthy",
    "hsi:gpu:memory_utilization",
    "hsi:gpu:utilization",
    "hsi:error_budget:api_availability_remaining",
    "hsi:error_budget:detection_latency_remaining",
    "hsi:error_budget:analysis_latency_remaining",
    "hsi:burn_rate:api_availability_1h",
    "hsi:burn_rate:api_availability_6h",
    "hsi:burn_rate:api_availability_1d",
    "hsi:burn_rate:detection_latency_1h",
    "hsi:burn_rate:detection_latency_6h",
    "hsi:burn_rate:analysis_latency_1h",
    "hsi:burn_rate:analysis_latency_6h",
}

# External metrics (from exporters like node_exporter, redis_exporter, etc.)
EXTERNAL_METRICS = {
    # Node exporter
    "node_cpu_seconds_total",
    "node_memory_MemTotal_bytes",
    "node_memory_MemAvailable_bytes",
    "node_filesystem_avail_bytes",
    "node_filesystem_size_bytes",
    "node_load1",
    "node_load5",
    "node_load15",
    # Redis exporter
    "redis_up",
    "redis_memory_used_bytes",
    "redis_commands_processed_total",
    "redis_connected_clients",
    "redis_keyspace_hits_total",
    "redis_keyspace_misses_total",
    "redis_slowlog_length",
    "redis_slowlog_last_id",
    # Alertmanager
    "alertmanager_alerts",
    "alertmanager_config_last_reload_successful",
    "alertmanager_notification_requests_total",
    "alertmanager_notification_requests_failed_total",
    "alertmanager_alerts_received_total",
    "alertmanager_receivers",
    # Prometheus
    "up",
    "ALERTS",
    # Blackbox exporter
    "probe_success",
    "probe_duration_seconds",
    "probe_dns_lookup_time_seconds",
    "probe_http_duration_seconds",
    # cAdvisor
    "container_cpu_usage_seconds_total",
    "container_memory_usage_bytes",
    "container_network_receive_bytes_total",
    "container_network_transmit_bytes_total",
    "container_fs_usage_bytes",
    # DCGM exporter
    "DCGM_FI_DEV_GPU_UTIL",
    "DCGM_FI_DEV_MEM_COPY_UTIL",
    "DCGM_FI_DEV_FB_USED",
    "DCGM_FI_DEV_FB_FREE",
    "DCGM_FI_DEV_GPU_TEMP",
    "DCGM_FI_DEV_POWER_USAGE",
    "DCGM_FI_DEV_SM_CLOCK",
    "DCGM_FI_DEV_MEM_CLOCK",
    "DCGM_FI_PROF_PCIE_TX_BYTES",
    "DCGM_FI_PROF_PCIE_RX_BYTES",
    # llama.cpp metrics
    "llamacpp:predicted_tokens_seconds",
    "llamacpp:prompt_seconds_total",
    "llamacpp:tokens_predicted_seconds_total",
    "llamacpp:prompt_tokens_seconds",
    "llamacpp:requests_processing",
    "llamacpp:requests_deferred",
    "llamacpp:n_busy_slots_per_decode",
    "llamacpp:n_decode_total",
    "llamacpp:tokens_predicted_total",
    "llamacpp:prompt_tokens_total",
    # Pyroscope
    "pyroscope_distributor_received_samples_total",
    "pyroscope_ingester_profiles_received_total",
    "pyroscope_distributor_bytes_received_total",
}

# All known metrics
ALL_KNOWN_METRICS = (
    BACKEND_HSI_METRICS
    | JSON_EXPORTER_METRICS
    | YOLO26_METRICS
    | FLORENCE_METRICS
    | CLIP_METRICS
    | ENRICHMENT_METRICS
    | RECORDING_RULES
    | EXTERNAL_METRICS
)

# Metrics that are NOT IMPLEMENTED (need to be added or dashboard panels updated)
NOT_IMPLEMENTED_METRICS = {
    # RUM (Real User Monitoring) - Not implemented
    "hsi_rum_page_load_time_seconds",
    "hsi_rum_fcp_seconds",
    "hsi_rum_lcp_seconds",
    "hsi_rum_cls",
    "hsi_rum_inp_seconds",
    "hsi_rum_js_errors_total",
    "hsi_rum_active_sessions",
    # Database connection pool - Not implemented (need postgres exporter)
    "hsi_db_query_duration_seconds",
    "hsi_db_pool_connections_active",
    "hsi_db_pool_connections_idle",
    "hsi_slow_queries_total",
    "hsi_db_transactions_total",
    # A/B testing metrics - Not implemented
    "hsi_ab_variant_traffic_total",
    "hsi_ab_conversions_total",
    "hsi_prompt_accuracy",
    "hsi_prompt_latency_seconds",
    "hsi_prompt_agreement_total",
    "hsi_prompt_comparisons_total",
    "hsi_prompt_context_used_tokens",
    "hsi_prompt_context_max_tokens",
    "hsi_prompt_input_tokens",
    "hsi_prompt_output_tokens",
    "hsi_prompt_context_overflow_total",
    "hsi_prompt_ab_traffic_total",
    "hsi_shadow_avg_risk_score",
    "hsi_ab_rollout_analysis_total",
    # LLM cost tracking - Not implemented
    "hsi_llm_cost_dollars_total",
    "hsi_llm_monthly_budget_dollars",
    # Redis pool metrics - Different naming
    "hsi_redis_pool_connections_active",
    "hsi_redis_pool_wait_seconds",
    "hsi_redis_pool_exhaustion_total",
    # Action recognition metrics - Different naming
    "hsi_action_confidence",
    "hsi_action_corrections_total",
    "hsi_action_detections_total",
    # Model management - Not implemented
    "hsi_model_cold_start_latency_seconds",
    "hsi_model_restarts_total",
    # Profiling regression rules - Not implemented yet
    "job:service_cpu_regression_ratio:5m_vs_24h",
    "job:service_memory_regression_ratio:current_vs_6h",
}


# =============================================================================
# PromQL extraction
# =============================================================================


def extract_metric_names_from_promql(expr: str) -> set[str]:
    """Extract base metric names from a PromQL expression."""
    metric_names: set[str] = set()

    # Pattern to match metric names (including recording rules with colons)
    metric_pattern = re.compile(r"([a-zA-Z_:][a-zA-Z0-9_:]*)")

    promql_keywords = {
        "sum",
        "avg",
        "min",
        "max",
        "count",
        "stddev",
        "stdvar",
        "topk",
        "bottomk",
        "count_values",
        "group",
        "rate",
        "irate",
        "increase",
        "delta",
        "idelta",
        "histogram_quantile",
        "time",
        "absent",
        "absent_over_time",
        "ceil",
        "floor",
        "round",
        "clamp",
        "clamp_min",
        "clamp_max",
        "day_of_month",
        "day_of_week",
        "day_of_year",
        "days_in_month",
        "hour",
        "minute",
        "month",
        "year",
        "exp",
        "ln",
        "log2",
        "log10",
        "sqrt",
        "abs",
        "sgn",
        "changes",
        "deriv",
        "predict_linear",
        "resets",
        "sort",
        "sort_desc",
        "timestamp",
        "vector",
        "label_replace",
        "label_join",
        "quantile",
        "quantile_over_time",
        "avg_over_time",
        "min_over_time",
        "max_over_time",
        "sum_over_time",
        "count_over_time",
        "last_over_time",
        "present_over_time",
        "stddev_over_time",
        "stdvar_over_time",
        "and",
        "or",
        "unless",
        "on",
        "ignoring",
        "group_left",
        "group_right",
        "by",
        "without",
        "offset",
        "bool",
        "le",
        "job",
        "instance",
        "workflow",
        "type",
        "stage",
        "service",
        "error_type",
        "phase",
        "service_type",
        "ai_service",
        "__range",
        "__rate_interval",
    }

    for match in metric_pattern.finditer(expr):
        candidate = match.group(1)
        if candidate.lower() in promql_keywords:
            continue
        if candidate.isdigit():
            continue
        if len(candidate) < 3:
            continue
        if candidate in (
            "healthy",
            "unhealthy",
            "ready",
            "degraded",
            "not_ready",
            "success",
            "error",
            "firing",
            "resolved",
            "active",
            "suppressed",
        ):
            continue
        metric_names.add(candidate)

    return metric_names


def extract_queries_from_dashboard(dashboard_path: Path) -> dict[str, list[tuple[str, str]]]:
    """Extract PromQL queries from a dashboard.

    Returns:
        Dict mapping panel title to list of (query, refId) tuples.
    """
    dashboard = json.loads(dashboard_path.read_text())
    panel_queries: dict[str, list[tuple[str, str]]] = {}

    def process_panels(panels: list[dict]) -> None:
        for panel in panels:
            panel_title = panel.get("title", f"Panel {panel.get('id', 'unknown')}")
            queries = []

            for target in panel.get("targets", []):
                expr = target.get("expr")
                if expr:
                    ref_id = target.get("refId", "?")
                    queries.append((expr, ref_id))

            if queries:
                panel_queries[panel_title] = queries

            # Process nested panels (collapsed rows)
            nested_panels = panel.get("panels", [])
            if nested_panels:
                process_panels(nested_panels)

    process_panels(dashboard.get("panels", []))
    return panel_queries


def analyze_query(expr: str) -> tuple[set[str], set[str], set[str]]:
    """Analyze a query and categorize metrics.

    Returns:
        Tuple of (known_metrics, unknown_metrics, not_implemented_metrics)
    """
    metrics = extract_metric_names_from_promql(expr)

    known = set()
    unknown = set()
    not_impl = set()

    for metric in metrics:
        if metric in ALL_KNOWN_METRICS:
            known.add(metric)
        elif metric in NOT_IMPLEMENTED_METRICS:
            not_impl.add(metric)
        else:
            unknown.add(metric)

    return known, unknown, not_impl


def main():
    """Main entry point."""
    dashboards_dir = Path(__file__).parent.parent / "monitoring" / "grafana" / "dashboards"

    if not dashboards_dir.exists():
        print(f"ERROR: Dashboards directory not found: {dashboards_dir}")
        return

    print("=" * 80)
    print("Grafana Dashboard PromQL Query Audit")
    print("=" * 80)
    print()

    total_queries = 0
    total_broken = 0
    total_not_impl = 0
    all_unknown: set[str] = set()
    all_not_impl: set[str] = set()

    dashboard_stats = []

    for dashboard_path in sorted(dashboards_dir.glob("*.json")):
        print(f"\n{'-' * 60}")
        print(f"Dashboard: {dashboard_path.name}")
        print(f"{'-' * 60}")

        panel_queries = extract_queries_from_dashboard(dashboard_path)

        broken_queries = []
        not_impl_queries = []
        dashboard_broken = 0
        dashboard_not_impl = 0
        dashboard_total = 0

        for panel_title, queries in panel_queries.items():
            for expr, ref_id in queries:
                dashboard_total += 1
                total_queries += 1

                known, unknown, not_impl = analyze_query(expr)

                if unknown:
                    broken_queries.append((panel_title, ref_id, expr, unknown))
                    dashboard_broken += 1
                    total_broken += 1
                    all_unknown.update(unknown)

                if not_impl:
                    not_impl_queries.append((panel_title, ref_id, expr, not_impl))
                    dashboard_not_impl += 1
                    total_not_impl += 1
                    all_not_impl.update(not_impl)

        if broken_queries:
            print("\n  BROKEN QUERIES (unknown metrics):")
            for panel_title, ref_id, expr, unknown in broken_queries:
                print(f"    Panel: {panel_title}")
                print(f"    RefID: {ref_id}")
                print(f"    Query: {expr[:80]}...")
                print(f"    Unknown: {unknown}")
                print()

        if not_impl_queries:
            print("\n  NOT IMPLEMENTED (metrics pending):")
            for panel_title, ref_id, expr, not_impl in not_impl_queries:
                print(f"    Panel: {panel_title}")
                print(f"    RefID: {ref_id}")
                print(f"    Query: {expr[:80]}...")
                print(f"    Not Implemented: {not_impl}")
                print()

        dashboard_stats.append(
            {
                "name": dashboard_path.name,
                "total": dashboard_total,
                "broken": dashboard_broken,
                "not_impl": dashboard_not_impl,
                "health": (
                    (dashboard_total - dashboard_broken - dashboard_not_impl)
                    / dashboard_total
                    * 100
                )
                if dashboard_total > 0
                else 100,
            }
        )

        print(
            f"\n  Summary: {dashboard_total} queries, "
            f"{dashboard_broken} broken, {dashboard_not_impl} not implemented"
        )
        if dashboard_total > 0:
            health = (
                (dashboard_total - dashboard_broken - dashboard_not_impl) / dashboard_total * 100
            )
            print(f"  Health: {health:.1f}%")

    print("\n" + "=" * 80)
    print("OVERALL SUMMARY")
    print("=" * 80)
    print(f"\nTotal queries: {total_queries}")
    print(f"Broken queries: {total_broken}")
    print(f"Not implemented: {total_not_impl}")
    if total_queries > 0:
        health = (total_queries - total_broken - total_not_impl) / total_queries * 100
        print(f"Overall health: {health:.1f}%")

    print("\n" + "-" * 40)
    print("Dashboard Summary Table")
    print("-" * 40)
    print(f"{'Dashboard':<35} {'Total':>6} {'Broken':>7} {'NotImpl':>8} {'Health':>7}")
    print("-" * 65)
    for stats in dashboard_stats:
        print(
            f"{stats['name']:<35} {stats['total']:>6} {stats['broken']:>7} "
            f"{stats['not_impl']:>8} {stats['health']:>6.1f}%"
        )

    if all_unknown:
        print("\n" + "-" * 40)
        print("All unknown metrics (need investigation):")
        print("-" * 40)
        for metric in sorted(all_unknown):
            print(f"  - {metric}")

    if all_not_impl:
        print("\n" + "-" * 40)
        print("All not implemented metrics:")
        print("-" * 40)
        for metric in sorted(all_not_impl):
            print(f"  - {metric}")


if __name__ == "__main__":
    main()
