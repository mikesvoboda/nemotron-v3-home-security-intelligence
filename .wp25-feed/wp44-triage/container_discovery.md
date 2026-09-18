# WP4.4 Triage Dossier — backend/services/container_discovery.py

**Generation-2 tally (FINAL cache).** Meta: `mutants/backend/services/container_discovery.py.meta` — 858 keys total, 696 SURVIVED (exit_code 0), 162 killed, 0 untested.
Method: diffs extracted by AST diffing the mutant copies (`mutants/backend/services/container_discovery.py`, 223k lines of clobbered variants) against `backend/services/container_discovery.py`; no test execution, no repo writes. Extraction script: `/tmp/wp25/wp44-triage/_cd_final.py`, raw bucket data `/tmp/wp25/wp44-triage/_cd_final.json`.

## THE ROOT CAUSE (read this first)

**No test in the entire suite ever executes `build_service_configs` or `build_configs_from_compose`.**
`grep -rn "build_service_configs(" backend/tests/` → 0 hits (rc=1). `mutmut-stats.json` lists 66 covering tests for `build_service_configs`, all in `backend/tests/unit/services/test_container_orchestrator.py` — those are *import-time/transitive* coverage (the orchestrator module imports the discovery module), not invocations: no orchestrator test passes port settings into `ContainerDiscoveryService`, and `backend/services/container_orchestrator.py:167` constructs it without settings. Same for `build_configs_from_compose` (0 direct test references) and for `ContainerDiscoveryService.__init__`'s `settings`/`compose_file` branches — every test builds `ContainerDiscoveryService(mock_docker_client)` with no settings (all fall into the `ALL_CONFIGS` static-dict branch, lines 697-699).

So the function that contains 643 of 696 survivors (the 25-service hardcoded config table in `build_service_configs`, lines 87-384) is a fully dead-to-tests configuration source, while its *static mirror* (`INFRASTRUCTURE_CONFIGS`/`AI_CONFIGS`/`MONITORING_CONFIGS`, lines 389-630 — the same values with constants instead of `settings.X if settings else const`) **is** heavily asserted in `backend/tests/unit/services/test_container_discovery.py`. The fix is one parameterized table test that calls the builder and asserts the same values the static tests already pin.

## Cluster table (696 survivors, sums exactly: 643 + 10 + 17 + 16 + 8 + 2)

| # | Cluster (function / pattern) | n | Class | Killed by |
|---|---|---|---|---|
| G1 | `build_service_configs`: ternary mutations on the 25 `x_port = settings.x_port if settings else CONST` lines — fallback literal tweaked (`else 8080`→`8081`, 25, e.g. mutmut_100), whole ternary replaced (`postgres_port = None`, 25, mutmut_1), `if (settings) and False` (25, mutmut_10 — settings supplied but .env-default silently used), `if (settings) or True` (25, mutmut_11 — AttributeError crash when settings=None) | 100 | TEST-GAP | T1, T2 |
| G2 | `build_service_configs`: dict entry key clobbered (`"postgres"` → `"XXpostgresXX"` / `"POSTGRES"`, 25×2, mutmut_102/103) — breaks `match_container_name`/`get_config` lookups for that service | 50 | TEST-GAP | T1 |
| G3 | `build_service_configs`: `display_name` clobbered (→ None / XX-wrapped / case-flipped / tweaked), 25 entries × ~4 variants (mutmut_104/120/121) | 97 | TEST-GAP | T1 |
| G4 | `build_service_configs`: `port=<x>_port` → `port=None` (25 entries, mutmut_106) | 25 | TEST-GAP | T1 |
| G5 | `build_service_configs`: `category=ServiceCategory.X` → `category=None` (25 entries, mutmut_105) — silently corrupts `discover_by_category` | 25 | TEST-GAP | T1 |
| G6 | `build_service_configs`: health target mutated — `health_endpoint`/`health_cmd` → None (25) + string clobbers XX/case/tweak (50) — breaks health checks (wrong URL / lost exec probe) | 75 | TEST-GAP | T1 |
| G7 | `build_service_configs`: `health_endpoint=`/`health_cmd=` kwarg **deleted** → falls to dataclass default None (25 entries, mutmut_115) | 25 | TEST-GAP | T1 |
| G8 | `build_service_configs`: self-heal params mutated — `startup_grace_period`/`max_failures`/`restart_backoff_base`/`restart_backoff_max` → None (82, mutmut_108-110) or numeric tweak (82, mutmut_126-128) | 164 | TEST-GAP | T1 |
| G9 | `build_service_configs`: self-heal kwargs **deleted** where value ≠ ServiceConfig default (infra `max_failures=10`→5, `restart_backoff_base=2.0`→5.0, monitoring grace 15/30→60, etc.) | 64 | TEST-GAP | T1 |
| E1 | `build_service_configs`: kwargs deleted where the value **equals the ServiceConfig dataclass default** (`max_failures=5` ×14, `startup_grace_period=60` ×4, mutmut_249/284/302) — semantically identical | 18 | EQUIVALENT | — (defaults at `backend/services/orchestrator/models.py:66-71`, pinned by existing `test_service_config_defaults`) |
| G10 | `__init__`: compose-branch call mutations — `self._configs=None`, dropped/Nulled args to `build_configs_from_compose` (mutmut_6-12, 7) plus `include_monitoring` ternary → None / `and False` (mutmut_2/3, 2). The `compose_file` branch and the settings branch are executed by **zero** tests | 9 | TEST-GAP | T3, T4 |
| E2 | `__init__`: `include_monitoring ... else True` → `else False` (mutmut_5) — dead branch: the else-value is only consumed when settings exist, where `if settings` is True; the settings=None path uses `ALL_CONFIGS` and ignores the flag | 1 | EQUIVALENT | — |
| G11 | `_create_managed_service`: untagged-image string content mutations — `getattr(container,'XXidXX'/'ID'...)`, `getattr(None,'id','unknown')`, `[:12]`→`[:13]` (mutmut_23/29/30/33). The existing `test_discover_handles_container_without_image_tags` only asserts `image is not None` | 4 | TEST-GAP | T5 |
| G12 | `_create_managed_service`: `health_cmd=config.health_cmd` → None / kwarg deleted (mutmut_40/52) — postgres/redis exec health command lost on the ManagedService | 2 | TEST-GAP | T5 |
| L1 | `_create_managed_service`: defensive-default mutants on never-executed paths — `getattr(container,"image",…)` default tweaks (6/13/16), missing-`id` fallbacks (`'unknown'`/None/case variants, 25/27/28/31/32), `container_id` getattr default tweaks (60/63/66). All fire only when a container lacks `image`/`tags`/`id`, which real docker-py objects and every test mock always provide | 11 | LOW-VALUE | — |
| E3 | `discover_all`: log-only mutations — debug/info message text → None, `extra={...}` → None/removed/key-clobbered (mutmut_18-35). Return value unaffected | 16 | EQUIVALENT | — |
| G13 | `build_configs_from_compose`: `parser=None` (mutmut_1) and `configs=None` (mutmut_2) both crash → caught by `except Exception` → silent fallback (parse pass-through never verified); `parse_file(None)` (mutmut_3); fallback-call arg mutations incl. `settings` swallowed positionally `build_service_configs(include_monitoring)` (mutmut_5-8) | 7 | TEST-GAP | T4 |
| E4 | `build_configs_from_compose`: warning message → None (mutmut_4) | 1 | EQUIVALENT | — |
| E5 | `match_container_name`: `matches.sort(key=len, reverse=True)` → `sort(reverse=True)` / `sort(key=None, reverse=True)` (mutmut_5/7). The shipped config has exactly two prefix-collision pairs (`redis`/`redis-exporter`, `ai-enrichment`/`ai-enrichment-light`) and the lexicographic-reverse winner equals the longest winner for both — indistinguishable on every reachable input | 2 | EQUIVALENT | — |

**Totals: TEST-GAP 647 · EQUIVALENT 38 · LOW-VALUE 11 = 696.**

## Covering test file

`backend/tests/unit/services/test_container_discovery.py` — the module's test file. Style: class-based, `MagicMock` docker client, `create_mock_container` factory, `@pytest.mark.asyncio` for discovery tests. Relevant weak assertions:

- `test_discover_handles_container_without_image_tags` (line ~501): asserts only `discovered[0].image is not None` — G11 gap.
- `test_discover_all_finds_postgres_container` (line ~271): asserts name/display/port/category but **not** `health_cmd`/backoffs — G12 gap.
- `TestPreConfiguredServices` / `TestCategoryPriorityOrdering` (lines ~113-300, ~610-700): assert the *static* dicts thoroughly — the exact table T1 replicates against the builder.
- Settings/compose paths of `__init__`: no test exists (T3/T4 are new).

## Drafted tests — UNVERIFIED, not yet run red/green

Append to `backend/tests/unit/services/test_container_discovery.py`. (The existing file imports `ServiceCategory` from `backend.api.schemas.services` — keep that import so enum identity matches the module's.)

```python
# =============================================================================
# Config Builder Tests  (WP4.4 kill tests — UNVERIFIED, not run red/green)
# =============================================================================

from types import SimpleNamespace

from backend.services.container_discovery import build_configs_from_compose, build_service_configs

# Expected table for build_service_configs(settings=None): .env.example default ports
# + hardcoded probe/grace/backoff policy, exactly as lines 107-384.
# (display_name, category, port, health_endpoint, health_cmd,
#  startup_grace_period, max_failures, restart_backoff_base, restart_backoff_max)
EXPECTED_BUILDER_TABLE: dict[str, tuple] = {
    "postgres": ("PostgreSQL", "INFRASTRUCTURE", 5432, None, "pg_isready -U security", 10, 10, 2.0, 60.0),
    "redis": ("Redis", "INFRASTRUCTURE", 6379, None, "redis-cli ping", 10, 10, 2.0, 60.0),
    "backend": ("Backend API", "INFRASTRUCTURE", 8000, "/api/system/health/ready", None, 30, 10, 2.0, 60.0),
    "go2rtc": ("go2rtc", "INFRASTRUCTURE", 1984, "/api", None, 15, 10, 2.0, 60.0),
    "frontend": ("Frontend", "INFRASTRUCTURE", 8080, "/health", None, 30, 10, 2.0, 60.0),
    "ai-yolo26": ("YOLO26", "AI", 8095, "/health", None, 60, 5, 5.0, 300.0),
    "ai-llm": ("Nemotron", "AI", 8091, "/health", None, 120, 5, 5.0, 300.0),
    "ai-florence": ("Florence-2", "AI", 8092, "/health", None, 60, 5, 5.0, 300.0),
    "ai-clip": ("CLIP", "AI", 8093, "/health", None, 60, 5, 5.0, 300.0),
    "ai-enrichment": ("Enrichment", "AI", 8094, "/health", None, 180, 5, 5.0, 300.0),
    "ai-enrichment-light": ("Enrichment Light", "AI", 8096, "/health", None, 120, 5, 5.0, 300.0),
    "prometheus": ("Prometheus", "MONITORING", 9090, "/-/healthy", None, 30, 5, 10.0, 120.0),
    "grafana": ("Grafana", "MONITORING", 3002, "/api/health", None, 30, 5, 10.0, 120.0),
    "alertmanager": ("Alertmanager", "MONITORING", 9093, "/-/healthy", None, 15, 5, 10.0, 120.0),
    "loki": ("Loki", "MONITORING", 3100, "/ready", None, 30, 5, 10.0, 120.0),
    "pyroscope": ("Pyroscope", "MONITORING", 4040, "/ready", None, 30, 5, 10.0, 120.0),
    "alloy": ("Grafana Alloy", "MONITORING", 12345, "/-/ready", None, 30, 5, 10.0, 120.0),
    "elasticsearch": ("Elasticsearch", "MONITORING", 9200, "/_cluster/health", None, 60, 5, 10.0, 120.0),
    "jaeger": ("Jaeger", "MONITORING", 16686, "/", None, 15, 5, 10.0, 120.0),
    "redis-exporter": ("Redis Exporter", "MONITORING", 9121, "/metrics", None, 15, 5, 10.0, 120.0),
    "json-exporter": ("JSON Exporter", "MONITORING", 7979, "/metrics", None, 15, 5, 10.0, 120.0),
    "blackbox-exporter": ("Blackbox Exporter", "MONITORING", 9115, "/metrics", None, 15, 5, 10.0, 120.0),
    "node-exporter": ("Node Exporter", "MONITORING", 9100, "/metrics", None, 15, 5, 10.0, 120.0),
    "cadvisor": ("cAdvisor", "MONITORING", 8082, "/healthz", None, 15, 5, 10.0, 120.0),
    "dcgm-exporter": ("DCGM Exporter", "MONITORING", 9400, "/metrics", None, 30, 5, 10.0, 120.0),
}

ALL_PORTS = {  # distinct from every default so a swallowed settings object always shows
    "postgres_port": 15432, "redis_port": 16379, "backend_port": 18000, "go2rtc_port": 19841,
    "yolo26_port": 18095, "nemotron_port": 18091, "florence_port": 18092, "clip_port": 18093,
    "enrichment_port": 18094, "enrichment_light_port": 18096, "prometheus_port": 19090,
    "grafana_port": 13002, "redis_exporter_port": 19121, "json_exporter_port": 17979,
    "alertmanager_port": 19093, "blackbox_exporter_port": 19115, "jaeger_port": 16687,
    "loki_port": 13100, "pyroscope_port": 14040, "alloy_port": 12346, "node_exporter_port": 19100,
    "cadvisor_port": 18082, "dcgm_exporter_port": 19400, "elasticsearch_port": 19200,
    "frontend_port": 18080,
}
_KEY_TO_PORT_ATTR = {  # config key -> settings attribute feeding its port
    "postgres": "postgres_port", "redis": "redis_port", "backend": "backend_port",
    "go2rtc": "go2rtc_port", "frontend": "frontend_port", "ai-yolo26": "yolo26_port",
    "ai-llm": "nemotron_port", "ai-florence": "florence_port", "ai-clip": "clip_port",
    "ai-enrichment": "enrichment_port", "ai-enrichment-light": "enrichment_light_port",
    "prometheus": "prometheus_port", "grafana": "grafana_port", "alertmanager": "alertmanager_port",
    "loki": "loki_port", "pyroscope": "pyroscope_port", "alloy": "alloy_port",
    "elasticsearch": "elasticsearch_port", "jaeger": "jaeger_port",
    "redis-exporter": "redis_exporter_port", "json-exporter": "json_exporter_port",
    "blackbox-exporter": "blackbox_exporter_port", "node-exporter": "node_exporter_port",
    "cadvisor": "cadvisor_port", "dcgm-exporter": "dcgm_exporter_port",
}


class TestBuildServiceConfigs:
    """Kill tests for the settings-driven config builder (WP4.4)."""

    def test_build_service_configs_full_table_without_settings(self) -> None:
        """Every service built with settings=None must match the .env-default table."""
        configs = build_service_configs(None)
        assert set(configs) == set(EXPECTED_BUILDER_TABLE)
        for name, exp in EXPECTED_BUILDER_TABLE.items():
            cfg = configs[name]
            display, cat, port, endpoint, cmd, grace, maxf, base, mx = exp
            assert cfg.display_name == display, name
            assert cfg.category.value.upper() == cat, name
            assert cfg.port == port, name
            assert cfg.health_endpoint == endpoint, name
            assert cfg.health_cmd == cmd, name
            assert cfg.startup_grace_period == grace, name
            assert cfg.max_failures == maxf, name
            assert cfg.restart_backoff_base == base, name
            assert cfg.restart_backoff_max == mx, name

    def test_build_service_configs_uses_ports_from_settings(self) -> None:
        """With settings supplied, every port must come from settings, not .env defaults."""
        settings = SimpleNamespace(monitoring_enabled=True, **ALL_PORTS)
        configs = build_service_configs(settings)
        for key, attr in _KEY_TO_PORT_ATTR.items():
            assert configs[key].port == ALL_PORTS[attr], f"{key} must use settings.{attr}"

    def test_build_service_configs_include_monitoring_flag(self) -> None:
        """include_monitoring=False must exclude exactly the MONITORING entries."""
        with_mon = build_service_configs(None, include_monitoring=True)
        without_mon = build_service_configs(None, include_monitoring=False)
        monitoring_keys = {k for k, v in EXPECTED_BUILDER_TABLE.items() if v[1] == "MONITORING"}
        assert monitoring_keys <= set(with_mon)
        assert not (monitoring_keys & set(without_mon))
        assert set(with_mon) - monitoring_keys == set(without_mon)


class TestDiscoverySettingsWiring:
    """__init__ branches no test has ever executed."""

    def test_init_with_settings_uses_configured_ports_and_monitoring_flag(self) -> None:
        """Settings branch: ports flow from settings; monitoring_enabled drives inclusion."""
        client = MagicMock()
        client.list_containers = AsyncMock(return_value=[])
        settings = SimpleNamespace(monitoring_enabled=True, **ALL_PORTS)
        discovery = ContainerDiscoveryService(client, settings)
        assert discovery.get_config("postgres").port == 15432
        assert discovery.get_config("prometheus") is not None

        settings_off = SimpleNamespace(monitoring_enabled=False, **ALL_PORTS)
        discovery_off = ContainerDiscoveryService(client, settings_off)
        assert discovery_off.get_config("prometheus") is None
        assert discovery_off.get_config("postgres").port == 15432

    def test_init_with_compose_file_uses_parsed_configs(self, tmp_path, monkeypatch) -> None:
        """compose_file branch: parsed configs win; mangled call args must fail loudly."""
        from backend.services.compose_parser import ComposeParser

        sentinel = ServiceConfig(
            display_name="Custom Compose Service",
            category=ServiceCategory.AI,
            port=45999,
            health_endpoint="/health",
        )
        monkeypatch.setattr(ComposeParser, "parse_file", lambda self, path: {"custom-svc": sentinel})
        client = MagicMock()
        client.list_containers = AsyncMock(return_value=[])
        discovery = ContainerDiscoveryService(client, None, compose_file=tmp_path / "docker-compose.yml")
        assert discovery.get_config("custom-svc") is sentinel
        assert discovery.get_config("postgres") is None  # parsed set replaces hardcoded table


class TestBuildConfigsFromCompose:
    """Pass-through and fallback semantics of the compose builder."""

    def test_missing_compose_file_falls_back_to_settings_ports(self, tmp_path) -> None:
        """FileNotFoundError must fall back to build_service_configs WITH settings forwarded."""
        missing = tmp_path / "nope-compose.yml"
        settings = SimpleNamespace(monitoring_enabled=True, **ALL_PORTS)
        configs = build_configs_from_compose(missing, settings)
        assert configs["postgres"].port == 15432  # fallback must keep settings, not default ports

    def test_parse_success_passes_configs_through(self, tmp_path, monkeypatch) -> None:
        """A successful parse result must be returned verbatim, not swapped for fallback."""
        from backend.services.compose_parser import ComposeParser

        sentinel = ServiceConfig(display_name="S", category=ServiceCategory.AI, port=1)
        monkeypatch.setattr(ComposeParser, "parse_file", lambda self, path: {"only-svc": sentinel})
        configs = build_configs_from_compose(tmp_path / "any.yml")
        assert configs == {"only-svc": sentinel}

    def test_parse_error_falls_back(self, tmp_path, monkeypatch) -> None:
        """Any parse exception must fall back to hardcoded configs (postgres present, default port)."""
        from backend.services.compose_parser import ComposeParser

        def boom(self, path):
            raise ValueError("bad yaml")

        monkeypatch.setattr(ComposeParser, "parse_file", boom)
        configs = build_configs_from_compose(tmp_path / "broken.yml")
        assert "postgres" in configs and configs["postgres"].port == 5432


class TestDiscoveryImageStringEdgeCases:
    """Exact untagged-image string + health_cmd passthrough."""

    @pytest.mark.asyncio
    async def test_untagged_container_image_string_uses_first_12_id_chars(
        self, mock_docker_client: MagicMock
    ) -> None:
        """Untagged containers must get '<untagged:{id[:12]}>' with the REAL id and health_cmd."""
        long_id = "0123456789abcdef0123456789abcdef"  # 32 hex chars, like a real docker id
        container = create_mock_container("security-postgres-1", container_id=long_id)
        container.image.tags = []
        mock_docker_client.list_containers = AsyncMock(return_value=[container])

        discovery = ContainerDiscoveryService(mock_docker_client)
        discovered = await discovery.discover_all()

        assert len(discovered) == 1
        assert discovered[0].image == f"<untagged:{long_id[:12]}>"
        # postgres uses an exec health command — it must survive the ManagedService mapping
        assert discovered[0].health_cmd == "pg_isready -U security"
```

TDD procedure (per test: run against the mutant → the specific assertion fails; run against original → passes):

- **T1** `test_build_service_configs_full_table_without_settings` — kills G2-G9 (entry key clobber → `set(configs)` mismatch; display/category/port/health/self-heal field mutation → field assertion fails with service name in message). ≈500 survivors. On original it merely restates the values the static-dict tests already pin → green.
- **T2** `test_build_service_configs_uses_ports_from_settings` — kills G1: `and False` mutants give default 5432 ≠ 15432; `port=None`/`assign-None` mutants give None/AttributeError; `or True` mutants crash at import of the ternary with settings=None in T1. (G1's numeric-default-tweak half is killed by T1 since T1 exercises settings=None.)
- **T3** `test_init_with_settings_uses_configured_ports_and_monitoring_flag` + `test_build_service_configs_include_monitoring_flag` — kills the `include_monitoring` ternary mutants (G10's 2 ternary survivors): `and False` forces default-ports/no-monitoring path; monitoring key set diverges.
- **T4** `test_init_with_compose_file_uses_parsed_configs` + the three `TestBuildConfigsFromCompose` tests — kill G10's 7 compose-call mutants (`custom-svc` absent or `_configs=None` TypeError) and G13 (parser=None → silent fallback → sentinel absent; settings swallowed positionally → port 5432 ≠ 15432).
- **T5** `test_untagged_container_image_string_uses_first_12_id_chars` — kills G11/G12: `[:13]` mutant yields `long_id[:13]`; `XXidXX`/`ID` mutants yield `<untagged:unknown>`; health_cmd mutants yield `None`.

## Notes / caveats

- Parallel-triage tier: **all drafted tests are UNVERIFIED** (no pytest run permitted in this lane; a live mutation run owns the machine). Verify red/green in the serial pytest lane before landing.
- E1 (18 removal-eq-default) is EQUIVALENT only because `ServiceConfig` defaults (`backend/services/orchestrator/models.py:66-71`: `max_failures: int = 5`, `startup_grace_period: int = 60`) happen to equal the deleted literals — if dataclass defaults change, these become real mutants.
- `build_service_configs` duplicates the entire table also present in the module-level `*_CONFIGS` dicts (lines 389-630); T1 pins the builder against literals, which simultaneously guards the builder's copy — a future dedup refactor should keep T1 (or repoint it at the shared table).
- The 66 "covering" tests in `mutmut-stats.json` for `build_service_configs`/`build_configs_from_compose` are transitive-import artifacts — treat as zero coverage when scoring the module.
