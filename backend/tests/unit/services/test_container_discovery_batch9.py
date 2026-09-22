"""Batch-9 mutation-kill battery: container_discovery config-builders (WP4.4 feed re-derivation).

The frozen wp44 feed has no per-mutant diff file for this module, so the 746
single-hunk shapes below were re-extracted mechanically from the fresh
generate (variant block vs ``__mutmut_orig`` block, def-name normalized).
The 137 class-mangled survivors (``xǁContainerDiscoveryServiceǁ*``) have no
orig blocks in the mutant copy and are NOT covered here — deferred, stated in
the ledger.

``build_service_configs`` is a pure data function: ONE full-table readback of
all 25 services (display_name, category, port, health endpoint/cmd,
grace/max_failures/backoff) kills every kwarg-None / kwarg-deleted / off-by-
one / XX-wrap / case-flip shape, and the settings-ports readback kills both
ternary directions (`and False` falls to defaults; `or True` crashes on None).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.services import container_discovery as cd_module
from backend.services.container_discovery import (
    build_configs_from_compose,
    build_service_configs,
)
from backend.services.orchestrator import ServiceCategory, ServiceConfig

# (display_name, category, port, health_endpoint, health_cmd,
#  startup_grace_period, max_failures, restart_backoff_base, restart_backoff_max)
EXPECTED_DEFAULTS: dict[str, tuple] = {
    "postgres": (
        "PostgreSQL",
        ServiceCategory.INFRASTRUCTURE,
        5432,
        None,
        "pg_isready -U security",
        10,
        10,
        2.0,
        60.0,
    ),
    "redis": (
        "Redis",
        ServiceCategory.INFRASTRUCTURE,
        6379,
        None,
        "redis-cli ping",
        10,
        10,
        2.0,
        60.0,
    ),
    "backend": (
        "Backend API",
        ServiceCategory.INFRASTRUCTURE,
        8000,
        "/api/system/health/ready",
        None,
        30,
        10,
        2.0,
        60.0,
    ),
    "go2rtc": ("go2rtc", ServiceCategory.INFRASTRUCTURE, 1984, "/api", None, 15, 10, 2.0, 60.0),
    "frontend": (
        "Frontend",
        ServiceCategory.INFRASTRUCTURE,
        8080,
        "/health",
        None,
        30,
        10,
        2.0,
        60.0,
    ),
    "ai-yolo26": ("YOLO26", ServiceCategory.AI, 8095, "/health", None, 60, 5, 5.0, 300.0),
    "ai-llm": ("Nemotron", ServiceCategory.AI, 8091, "/health", None, 120, 5, 5.0, 300.0),
    "ai-florence": ("Florence-2", ServiceCategory.AI, 8092, "/health", None, 60, 5, 5.0, 300.0),
    "ai-clip": ("CLIP", ServiceCategory.AI, 8093, "/health", None, 60, 5, 5.0, 300.0),
    "ai-enrichment": ("Enrichment", ServiceCategory.AI, 8094, "/health", None, 180, 5, 5.0, 300.0),
    "ai-enrichment-light": (
        "Enrichment Light",
        ServiceCategory.AI,
        8096,
        "/health",
        None,
        120,
        5,
        5.0,
        300.0,
    ),
    "prometheus": (
        "Prometheus",
        ServiceCategory.MONITORING,
        9090,
        "/-/healthy",
        None,
        30,
        5,
        10.0,
        120.0,
    ),
    "grafana": (
        "Grafana",
        ServiceCategory.MONITORING,
        3002,
        "/api/health",
        None,
        30,
        5,
        10.0,
        120.0,
    ),
    "alertmanager": (
        "Alertmanager",
        ServiceCategory.MONITORING,
        9093,
        "/-/healthy",
        None,
        15,
        5,
        10.0,
        120.0,
    ),
    "loki": ("Loki", ServiceCategory.MONITORING, 3100, "/ready", None, 30, 5, 10.0, 120.0),
    "pyroscope": (
        "Pyroscope",
        ServiceCategory.MONITORING,
        4040,
        "/ready",
        None,
        30,
        5,
        10.0,
        120.0,
    ),
    "alloy": (
        "Grafana Alloy",
        ServiceCategory.MONITORING,
        12345,
        "/-/ready",
        None,
        30,
        5,
        10.0,
        120.0,
    ),
    "elasticsearch": (
        "Elasticsearch",
        ServiceCategory.MONITORING,
        9200,
        "/_cluster/health",
        None,
        60,
        5,
        10.0,
        120.0,
    ),
    "jaeger": ("Jaeger", ServiceCategory.MONITORING, 16686, "/", None, 15, 5, 10.0, 120.0),
    "redis-exporter": (
        "Redis Exporter",
        ServiceCategory.MONITORING,
        9121,
        "/metrics",
        None,
        15,
        5,
        10.0,
        120.0,
    ),
    "json-exporter": (
        "JSON Exporter",
        ServiceCategory.MONITORING,
        7979,
        "/metrics",
        None,
        15,
        5,
        10.0,
        120.0,
    ),
    "blackbox-exporter": (
        "Blackbox Exporter",
        ServiceCategory.MONITORING,
        9115,
        "/metrics",
        None,
        15,
        5,
        10.0,
        120.0,
    ),
    "node-exporter": (
        "Node Exporter",
        ServiceCategory.MONITORING,
        9100,
        "/metrics",
        None,
        15,
        5,
        10.0,
        120.0,
    ),
    "cadvisor": (
        "cAdvisor",
        ServiceCategory.MONITORING,
        8082,
        "/healthz",
        None,
        15,
        5,
        10.0,
        120.0,
    ),
    "dcgm-exporter": (
        "DCGM Exporter",
        ServiceCategory.MONITORING,
        9400,
        "/metrics",
        None,
        30,
        5,
        10.0,
        120.0,
    ),
}

_SETTINGS_PORTS = {
    "postgres_port": 15432,
    "redis_port": 16379,
    "backend_port": 18000,
    "go2rtc_port": 11984,
    "yolo26_port": 18095,
    "nemotron_port": 18091,
    "florence_port": 18092,
    "clip_port": 18093,
    "enrichment_port": 18094,
    "enrichment_light_port": 18096,
    "prometheus_port": 19090,
    "grafana_port": 13002,
    "redis_exporter_port": 19121,
    "json_exporter_port": 17979,
    "alertmanager_port": 19093,
    "blackbox_exporter_port": 19115,
    "jaeger_port": 16687,
    "loki_port": 13100,
    "pyroscope_port": 14040,
    "alloy_port": 12346,
    "node_exporter_port": 19100,
    "cadvisor_port": 18082,
    "dcgm_exporter_port": 19400,
    "elasticsearch_port": 19200,
    "frontend_port": 18080,
}

# service key -> which settings attr feeds its port
_PORT_ATTR = {
    "postgres": "postgres_port",
    "redis": "redis_port",
    "backend": "backend_port",
    "go2rtc": "go2rtc_port",
    "frontend": "frontend_port",
    "ai-yolo26": "yolo26_port",
    "ai-llm": "nemotron_port",
    "ai-florence": "florence_port",
    "ai-clip": "clip_port",
    "ai-enrichment": "enrichment_port",
    "ai-enrichment-light": "enrichment_light_port",
    "prometheus": "prometheus_port",
    "grafana": "grafana_port",
    "alertmanager": "alertmanager_port",
    "loki": "loki_port",
    "pyroscope": "pyroscope_port",
    "alloy": "alloy_port",
    "elasticsearch": "elasticsearch_port",
    "jaeger": "jaeger_port",
    "redis-exporter": "redis_exporter_port",
    "json-exporter": "json_exporter_port",
    "blackbox-exporter": "blackbox_exporter_port",
    "node-exporter": "node_exporter_port",
    "cadvisor": "cadvisor_port",
    "dcgm-exporter": "dcgm_exporter_port",
}


def _facts(cfg: ServiceConfig) -> tuple:
    return (
        cfg.display_name,
        cfg.category,
        cfg.port,
        cfg.health_endpoint,
        cfg.health_cmd,
        cfg.startup_grace_period,
        cfg.max_failures,
        cfg.restart_backoff_base,
        cfg.restart_backoff_max,
    )


class TestBuildServiceConfigsFullTable:
    def test_default_table_exact_readback(self):
        # whole-table readback kills kwarg->None, kwarg-deleted (default leak),
        # off-by-one numeric flips, string XX-wrap and case flips on every field
        configs = build_service_configs()
        assert set(configs) == set(EXPECTED_DEFAULTS)
        assert {name: _facts(cfg) for name, cfg in configs.items()} == EXPECTED_DEFAULTS

    def test_settings_ports_are_read_from_every_service(self):
        # settings-given readback kills `and False` (falls to defaults); the
        # None-settings table above kills `or True` (crashes reading None ports)
        settings = SimpleNamespace(**_SETTINGS_PORTS)
        configs = build_service_configs(settings)
        assert set(configs) == set(EXPECTED_DEFAULTS)
        for name, attr in _PORT_ATTR.items():
            assert configs[name].port == _SETTINGS_PORTS[attr], name

    @pytest.mark.parametrize(
        "include",
        [True, False],
    )
    def test_include_monitoring_membership(self, include: bool):
        configs = build_service_configs(include_monitoring=include)
        non_monitoring = {
            n for n, f in EXPECTED_DEFAULTS.items() if f[1] is not ServiceCategory.MONITORING
        }
        if include:
            assert set(configs) == set(EXPECTED_DEFAULTS)
        else:
            assert set(configs) == non_monitoring

    def test_ai_configs_keep_serviceconfig_defaults_for_backoff(self):
        # AI configs pass NO max_failures/backoff — ServiceConfig defaults are
        # contractual: 5 / 5.0 / 300.0 (a default-deleted mutant would TypeError)
        cfg = build_service_configs()["ai-enrichment"]
        assert (
            cfg.startup_grace_period,
            cfg.max_failures,
            cfg.restart_backoff_base,
            cfg.restart_backoff_max,
        ) == (
            180,
            5,
            5.0,
            300.0,
        )


class TestBuildConfigsFromCompose:
    def _infra(self) -> ServiceConfig:
        return ServiceConfig(
            display_name="PostgreSQL",
            category=ServiceCategory.INFRASTRUCTURE,
            port=5432,
        )

    def _monitoring(self) -> ServiceConfig:
        return ServiceConfig(
            display_name="Prometheus",
            category=ServiceCategory.MONITORING,
            port=9090,
        )

    @pytest.fixture()
    def log_spy(self, monkeypatch):
        calls: list[tuple] = []

        class Spy:
            def info(self, msg, **kw):
                calls.append(("info", msg, kw))

            def warning(self, msg, **kw):
                calls.append(("warning", msg, kw))

        monkeypatch.setattr(cd_module, "logger", Spy())
        return calls

    def test_success_path_filters_and_logs(self, monkeypatch, log_spy):
        parsed = {"postgres": self._infra(), "prometheus": self._monitoring()}
        seen_args: list = []

        def fake_parse(self, compose_file):
            seen_args.append(compose_file)
            return parsed

        monkeypatch.setattr("backend.services.compose_parser.ComposeParser.parse_file", fake_parse)
        result = build_configs_from_compose("docker-compose.yml")
        assert result is parsed
        assert seen_args == ["docker-compose.yml"]  # arg->None crash/miss killed here
        assert log_spy == [
            (
                "info",
                "Loaded 2 service configs from docker-compose.yml",
                {"extra": {"compose_file": "docker-compose.yml", "count": 2}},
            )
        ]

    def test_monitoring_filter_both_directions(self, monkeypatch, log_spy):
        parsed = {"postgres": self._infra(), "prometheus": self._monitoring()}
        monkeypatch.setattr(
            "backend.services.compose_parser.ComposeParser.parse_file",
            lambda _self, _cf: parsed,
        )
        kept = build_configs_from_compose("c.yml", include_monitoring=False)
        assert set(kept) == {"postgres"}
        alls = build_configs_from_compose("c.yml", include_monitoring=True)
        assert set(alls) == {"postgres", "prometheus"}

    @pytest.mark.parametrize("exc", [FileNotFoundError("gone"), RuntimeError("bad yaml")])
    def test_fallbacks_forward_args_positionally(self, monkeypatch, log_spy, exc):
        monkeypatch.setattr(
            "backend.services.compose_parser.ComposeParser.parse_file",
            lambda _self, _cf: (_ for _ in ()).throw(exc),
        )
        sentinel = {"svc": self._infra()}
        forwarded: list[tuple] = []

        def fake_hardcoded(settings=None, include_monitoring=True):
            forwarded.append((settings, include_monitoring))
            return sentinel

        monkeypatch.setattr(cd_module, "build_service_configs", fake_hardcoded)
        settings = SimpleNamespace(**_SETTINGS_PORTS)
        result = build_configs_from_compose(
            "missing.yml", settings=settings, include_monitoring=False
        )
        assert result is sentinel
        assert forwarded == [(settings, False)]
        warnings = [c for c in log_spy if c[0] == "warning"]
        assert len(warnings) == 1
        text = warnings[0][1]
        if isinstance(exc, FileNotFoundError):
            assert text == "Compose file not found: missing.yml, falling back to hardcoded configs"
        else:
            assert (
                text == "Failed to parse compose file: bad yaml, falling back to hardcoded configs"
            )

    def test_compose_path_accepts_path_object(self, monkeypatch, log_spy):
        parsed = {"postgres": self._infra()}
        monkeypatch.setattr(
            "backend.services.compose_parser.ComposeParser.parse_file",
            lambda _self, _cf: parsed,
        )
        p = Path("deploy/docker-compose.yml")
        assert build_configs_from_compose(p) is parsed
        assert log_spy[0][1] == f"Loaded 1 service configs from {p}"
