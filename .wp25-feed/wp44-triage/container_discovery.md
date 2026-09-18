# WP4.4 Triage Dossier — backend/services/container_discovery.py

**UNVERIFIED — read-only triage wave; no tests were run.** Produced for WP4.3 finding feed → WP4.4.

- Surviving mutants: **696** of 858 keys (frozen snapshot `/tmp/wp25/wp44-triage/cd-meta-frozen.json`, copy of `mutants/backend/services/container_discovery.py.meta` at ~Sep 18, during the live run). NOTE: the live run is re-verifying verdicts — an earlier read showed 686 survivors; the frozen snapshot adds 10 newly-surviving `ContainerDiscoveryService.__init__` mutants. All counts below are from the frozen snapshot and sum to 696.
- Per-function: `build_service_configs` 643 surv / 80 killed (723 total) — the epicenter; `build_configs_from_compose` 8/8 surv (0% kill); `__init__` 10 surv (new); `_create_managed_service` 17 surv; `discover_all` 16 surv; `match_container_name` 2 surv. `get_config`, `discover_by_category`: fully killed.
- Method: mutant copy stores each variant as a full function (`__mutmut_orig` vs `__mutmut_N`); diffs derived by AST-region diff (`/tmp/wp25/wp44-triage/cd_classify.py`, assignments in `cd_clusters_frozen.json`). No `mutmut run`, no pytest.

## Why this module survives

`ServiceConfig` (`backend/services/orchestrator/models.py`, dataclass) has field defaults `startup_grace_period=60, max_failures=5, restart_backoff_base=5.0, restart_backoff_max=300.0`. The tests (all in `backend/tests/unit/services/test_container_discovery.py`) only ever exercise the **no-settings path**: `ContainerDiscoveryService(mock_docker_client)` with `settings=None` binds `self._configs = ALL_CONFIGS` (the static dicts), and the static dicts ARE asserted (TestPreConfiguredServices lines 113-200, TestCategoryPriorityOrdering lines 620-700). But `build_service_configs()`/`build_configs_from_compose()` — the parallel hand-duplicated config builders — are executed only incidentally via the ContainerOrchestrator fixture (`test_container_orchestrator.py:125-140`, MagicMock settings) with **no assertions on the produced configs**. So:

1. No test ever calls `build_service_configs(settings)` or `ContainerDiscoveryService(client, settings=...)` and asserts port/tuning → 25 port ternaries × 4 mutants + all tuning mutants survive.
2. No test ever passes `compose_file=` → the entire compose branch survives.
3. `include_monitoring` / `settings.monitoring_enabled` is never toggled → survives.
4. `display_name` / dict keys of the *settings-built* configs are never compared to the static ones (dual-implementation equality is untested).
5. Dropped-kwarg mutants on monitoring entries are true EQUIVALENTs (explicit value == dataclass default) — unkillable, candidate for mutmut exclude.

## Cluster table (696 survivors, sums exact)

| # | Cluster / pattern | n | Class | Example keys (suffix) |
|---|---|---|---|---|
| B1 | `build_service_configs`: port ternary `settings.X if settings else D` → whole-line `None` / `if (settings) and False` (always default) / `if (settings) or True` (always attribute) / default `+1`, ×25 ports | 100 | TEST-GAP | `x_build_service_configs__mutmut_1,2,3` |
| B2 | `build_service_configs`: `port=<x>` → `port=None` ×25 entries | 25 | TEST-GAP | `x_build_service_configs__mutmut_106,134,161` |
| B3 | `build_service_configs`: dict key case-flip / `XX`-wrap (`"postgres"`→`"POSTGRES"`/`"XXpostgresXX"`) ×25 entries — breaks `match_container_name` substring matching | 50 | TEST-GAP | `x_build_service_configs__mutmut_102,103,130` |
| B4 | `build_service_configs`: `display_name` case/XX/None | 97 | TEST-GAP | `x_build_service_configs__mutmut_104,120,121` |
| B5 | `build_service_configs`: `category=ServiceCategory.X` → `category=None` | 25 | TEST-GAP | `x_build_service_configs__mutmut_105,133,160` |
| B6 | `build_service_configs`: `health_endpoint` value case/XX-wrap | 45 | TEST-GAP | `x_build_service_configs__mutmut_178,179,204` |
| B7 | `build_service_configs`: `health_endpoint` → `None` / kwarg dropped (default None wins) | 46 | TEST-GAP | `x_build_service_configs__mutmut_162,170,189` |
| B8 | `build_service_configs`: `health_cmd` (postgres/redis) case/XX/None/dropped | 9 | TEST-GAP | `x_build_service_configs__mutmut_107,115,123` |
| B10 | `build_service_configs`: `max_failures` → `None` | 19 | TEST-GAP | `x_build_service_configs__mutmut_109,137,164` |
| B11 | `build_service_configs`: `max_failures` +1 (5→6, 10→11) | 19 | TEST-GAP | `x_build_service_configs__mutmut_127,154,181` |
| B12a | `build_service_configs`: `max_failures=10` kwarg dropped → dataclass default 5 (INFRA 10→5) | 5 | TEST-GAP | `x_build_service_configs__mutmut_117,145,172` |
| B12b | `build_service_configs`: `max_failures=5` kwarg dropped on MONITORING — **equals default, semantically identical** | 14 | EQUIVALENT | `x_build_service_configs__mutmut_360,387,414` |
| B13 | `build_service_configs`: `restart_backoff_base` → None / +1 / dropped (base: 2.0→5.0 INFRA, 10.0→5.0 MON) | 57 | TEST-GAP | `x_build_service_configs__mutmut_110,118,128` |
| B14 | `build_service_configs`: `restart_backoff_max` → None / +1 / dropped (60.0→300.0 INFRA, 120.0→300.0 MON) | 57 | TEST-GAP | `x_build_service_configs__mutmut_111,119,129` |
| B15 | `build_service_configs`: `startup_grace_period` → None / +1 | 50 | TEST-GAP | `x_build_service_configs__mutmut_108,126,136` |
| B16a | `build_service_configs`: `startup_grace_period=60` kwarg dropped (AI florence/clip etc.) — **equals default** | 4 | EQUIVALENT | `x_build_service_configs__mutmut_249,284,302` |
| B16b | `build_service_configs`: `startup_grace_period` kwarg dropped, default 60 silently wins (10/15/30/120/180→60) | 21 | TEST-GAP | `x_build_service_configs__mutmut_116,144,171` |
| D1 | `_create_managed_service`: `getattr` default tweaks `[]→None`/arg-drop at paths that never hit the default in any test — **no observable change on any input that reaches them** (see note) | 3 | EQUIVALENT | `..._create_managed_service__mutmut_6,13,16` |
| D2a | `_create_managed_service`: untagged-image f-string `<untagged:{id[:12]}>` → `getattr(None,...)` / default `'unknown'` / `[:13]`-w-12-char-id / `getattr(container,'id',)` arg-drop | 6 | TEST-GAP | `..._create_managed_service__mutmut_23,25,27` (also 28,29,30) |
| D2b | Same string tweaks but default never used (container always has `.id`) or slice no-op on the test's 12-char id | 3 | EQUIVALENT | `..._create_managed_service__mutmut_31,32,33` |
| D3 | `_create_managed_service`: `container_id=getattr(container,"id",…)` default tweaks (`None`/arg-drop/`"XXXX"`) — only fires when container object lacks `.id`; tests always provide it | 3 | LOW-VALUE | `..._create_managed_service__mutmut_60,63,66` |
| D4 | `_create_managed_service`: `health_cmd=config.health_cmd` → `None` / kwarg dropped | 2 | TEST-GAP | `..._create_managed_service__mutmut_40,52` |
| E1 | `discover_all`: log message → `None`, `extra=` dict → None/dropped, extra key case/XX-wrap — pure observability, no functional change | 16 | EQUIVALENT | `..._discover_all__mutmut_18,19,21` |
| F1 | `match_container_name`: `matches.sort(key=len, reverse=True)` → `sort(key=None)` / `sort(reverse=True)` — only changes winner among **equal-length** patterns; no such pattern pair exists in configs | 2 | EQUIVALENT | `..._match_container_name__mutmut_5,7` |
| G1 | `build_configs_from_compose`: `logger.warning(f"Compose file not found...")` → `logger.warning(None)` — message text only | 1 | EQUIVALENT | `x_build_configs_from_compose__mutmut_4` |
| G2 | `build_configs_from_compose`: `ComposeParser()`→None, `configs=None`, `parse_file(None)`, fallback `build_service_configs(None, flag)` / `(settings, None)` / `(include_monitoring)` / `(settings,)` | 7 | TEST-GAP | `x_build_configs_from_compose__mutmut_1,2,3` (also 5,6,7,8) |
| H1a | `__init__`: `include_monitoring = settings.monitoring_enabled if settings else True` → `None` / `and False` (always True) / `else False` | 3 | TEST-GAP | `..._init____mutmut_2,3,5` |
| H1b | `__init__`: compose branch — `self._configs = None`, `build_configs_from_compose(None, …)`, arg drops/swaps (`(settings, include_monitoring)`, trailing-comma drops) | 7 | TEST-GAP | `..._init____mutmut_6,7,8` (also 9,10,11,12) |

TEST-GAP total **650**, EQUIVALENT **43**, LOW-VALUE **3**.

## Covering test files

- `backend/tests/unit/services/test_container_discovery.py` — the module's only dedicated test file. Key regions: `TestServiceConfig` (L64-107, dataclass defaults only), `TestPreConfiguredServices` (L113-200, asserts the **static** dicts, not `build_service_configs`), `TestContainerDiscoveryService` (L264-549, all constructions use `ContainerDiscoveryService(mock_docker_client)` — settings=None path), weak untagged-image test `test_discover_handles_container_without_image_tags` (L502-519, asserts only `image is not None`), `TestCategoryPriorityOrdering` (L612-733, static dicts again).
- `backend/tests/unit/services/test_container_orchestrator.py` — L125-140 `orchestrator` fixture passes MagicMock settings; this is what "covers" `__init__`/`build_service_configs` for mutmut (line execution, zero assertions on config content).
- mutmut-stats `tests_by_mangled_function_name`: `x_build_service_configs` / `x_build_configs_from_compose` map only to orchestrator-fixture tests (grep confirms **no test file imports or calls either function directly**).

## Drafted tests (5) — UNVERIFIED, not yet run red/green

TDD procedure (same for all): apply the cluster's mutant diff to `backend/services/container_discovery.py` → run the drafted test → it must FAIL (assert/crash on the mutated value); restore original → PASS. Target file: `backend/tests/unit/services/test_container_discovery.py` (add the import `build_service_configs, build_configs_from_compose` to the existing import block L14-22).

### T1 — settings-threaded ports (kills B1, B2; also kills G2-5 partially)

```python
class TestBuildServiceConfigsWithSettings:
    """build_service_configs must thread OrchestratorSettings ports (.env source of truth)."""

    PORT_ATTRS = [  # (settings attr, config key, default from .env.example)
        ("postgres_port", "postgres", 5432), ("redis_port", "redis", 6379),
        ("backend_port", "backend", 8000), ("go2rtc_port", "go2rtc", 1984),
        ("frontend_port", "frontend", 8080), ("yolo26_port", "ai-yolo26", 8095),
        ("nemotron_port", "ai-llm", 8091), ("florence_port", "ai-florence", 8092),
        ("clip_port", "ai-clip", 8093), ("enrichment_port", "ai-enrichment", 8094),
        ("enrichment_light_port", "ai-enrichment-light", 8096),
        ("prometheus_port", "prometheus", 9090), ("grafana_port", "grafana", 3002),
        ("alertmanager_port", "alertmanager", 9093), ("loki_port", "loki", 3100),
        ("pyroscope_port", "pyroscope", 4040), ("alloy_port", "alloy", 12345),
        ("elasticsearch_port", "elasticsearch", 9200), ("jaeger_port", "jaeger", 16686),
        ("redis_exporter_port", "redis-exporter", 9121), ("json_exporter_port", "json-exporter", 7979),
        ("blackbox_exporter_port", "blackbox-exporter", 9115),
        ("node_exporter_port", "node-exporter", 9100), ("cadvisor_port", "cadvisor", 8082),
        ("dcgm_exporter_port", "dcgm-exporter", 9400),
    ]

    def test_settings_ports_override_defaults(self) -> None:
        settings = MagicMock()  # truthy; each attr set to a distinctive value
        for attr, _key, default in self.PORT_ATTRS:
            setattr(settings, attr, default + 10000)
        configs = build_service_configs(settings, include_monitoring=True)
        for attr, key, default in self.PORT_ATTRS:
            assert configs[key].port == default + 10000, f"{key}: {attr} not threaded"

    def test_no_settings_uses_default_ports(self) -> None:
        configs = build_service_configs(None, include_monitoring=True)
        for attr, key, default in self.PORT_ATTRS:
            assert configs[key].port == default, f"{key}: default port mismatch for {attr}"
```

Red-proof: B1 `whole_None` → `configs[key].port` is None; `forced_default`/`default_plus1` → port==default ≠ default+10000; `forced_settings` → AttributeError on `None.postgres_port` in the None-side test (kills the else-always mutant). B2 (`port=None`) fails both tests.

### T2 — self-healing tuning values of the settings-built configs (kills B10, B11, B12a, B13, B14, B15, B16b — 221 mutants)

```python
class TestBuildServiceConfigsTuning:
    """build_service_configs (no settings) must reproduce the tuned per-category values,
    NOT ServiceConfig dataclass defaults (60/5/5.0/300.0 silently absorbed by dropped-kwarg mutants)."""

    def test_infrastructure_tuning(self) -> None:
        configs = build_service_configs(None, include_monitoring=False)
        for name, grace in [
            ("postgres", 10), ("redis", 10), ("backend", 30), ("go2rtc", 15), ("frontend", 30),
        ]:
            cfg = configs[name]
            assert cfg.startup_grace_period == grace, f"{name} grace"
            assert cfg.max_failures == 10, f"{name} max_failures"
            assert cfg.restart_backoff_base == 2.0, f"{name} base backoff"
            assert cfg.restart_backoff_max == 60.0, f"{name} max backoff"

    def test_ai_tuning(self) -> None:
        configs = build_service_configs(None, include_monitoring=False)
        for name, grace in [
            ("ai-yolo26", 60), ("ai-llm", 120), ("ai-florence", 60),
            ("ai-clip", 60), ("ai-enrichment", 180), ("ai-enrichment-light", 120),
        ]:
            cfg = configs[name]
            assert cfg.startup_grace_period == grace, f"{name} grace"
            assert cfg.max_failures == 5
            assert cfg.restart_backoff_base == 5.0
            assert cfg.restart_backoff_max == 300.0

    def test_monitoring_tuning(self) -> None:
        configs = build_service_configs(None, include_monitoring=True)
        for name, grace in [
            ("prometheus", 30), ("grafana", 30), ("alertmanager", 15), ("loki", 30),
            ("pyroscope", 30), ("alloy", 30), ("elasticsearch", 60), ("jaeger", 15),
            ("redis-exporter", 15), ("json-exporter", 15), ("blackbox-exporter", 15),
            ("node-exporter", 15), ("cadvisor", 15), ("dcgm-exporter", 30),
        ]:
            cfg = configs[name]
            assert cfg.startup_grace_period == grace, f"{name} grace"
            assert cfg.max_failures == 5
            assert cfg.restart_backoff_base == 10.0
            assert cfg.restart_backoff_max == 120.0
```

### T3 — parity with static dicts (kills B3, B4, B5, B6, B7, B8 — 272 mutants)

The two implementations must agree; every case/XX/None mutation of a display_name/key/category/health string breaks equality with the asserted-correct static dicts.

```python
class TestBuildServiceConfigsStaticParity:
    """build_service_configs(None, True) is the settings-free twin of ALL_CONFIGS; any drift
    (keys, display names, categories, health endpoints/cmds) is a real behavior change because
    match_container_name/discover_all read these dicts directly."""

    def test_matches_static_configs(self) -> None:
        built = build_service_configs(None, include_monitoring=True)
        assert set(built) == set(ALL_CONFIGS), "config key set differs from ALL_CONFIGS"
        for key, expected in ALL_CONFIGS.items():
            cfg = built[key]
            assert cfg.display_name == expected.display_name, f"{key} display_name"
            assert cfg.category == expected.category, f"{key} category"
            assert cfg.health_endpoint == expected.health_endpoint, f"{key} health_endpoint"
            assert cfg.health_cmd == expected.health_cmd, f"{key} health_cmd"
```

### T4 — monitoring_enabled + compose branch in `__init__` (kills H1a, H1b, G2)

```python
class TestContainerDiscoveryInitBranches:
    """__init__ must honor settings.monitoring_enabled and the compose_file branch
    (neither branch is entered by any existing test)."""

    def test_monitoring_enabled_true_includes_monitoring(self, mock_docker_client: MagicMock) -> None:
        settings = MagicMock()
        settings.monitoring_enabled = True
        service = ContainerDiscoveryService(mock_docker_client, settings=settings)
        assert service.get_config("prometheus") is not None
        assert service.get_config("postgres") is not None

    def test_monitoring_enabled_false_excludes_monitoring(self, mock_docker_client: MagicMock) -> None:
        settings = MagicMock()
        settings.monitoring_enabled = False
        service = ContainerDiscoveryService(mock_docker_client, settings=settings)
        assert service.get_config("prometheus") is None
        assert service.get_config("postgres") is not None

    def test_compose_file_success_path(
        self, mock_docker_client: MagicMock, tmp_path
    ) -> None:
        compose = tmp_path / "docker-compose.yml"
        compose.write_text("services: {}\n")
        parsed = {"custom-svc": ServiceConfig(display_name="Custom", category=ServiceCategory.AI, port=1234)}
        with patch("backend.services.compose_parser.ComposeParser") as parser_cls:
            parser_cls.return_value.parse_file.return_value = parsed
            service = ContainerDiscoveryService(mock_docker_client, compose_file=compose)
            parser_cls.return_value.parse_file.assert_called_once_with(compose)
        assert service.get_config("custom-svc") is not None  # not the hardcoded fallback

    def test_compose_fallback_threads_settings_and_flag(
        self, mock_docker_client: MagicMock, tmp_path
    ) -> None:
        missing = tmp_path / "does-not-exist.yml"
        settings = MagicMock()
        settings.monitoring_enabled = False
        settings.postgres_port = 15432
        service = ContainerDiscoveryService(
            mock_docker_client, settings=settings, compose_file=missing
        )
        cfg = service.get_config("postgres")
        assert cfg is not None and cfg.port == 15432  # settings threaded into fallback
        assert service.get_config("prometheus") is None  # monitoring_enabled=False threaded
```

Imports to add: `from unittest.mock import AsyncMock, MagicMock, patch` (patch new). Red-proof sketch: H1a — `include_monitoring=None`/`else False` excludes prometheus in the True test; `and False` (always True) includes it in the False test. H1b — `_configs=None` → AttributeError on `get_config`; `compose_file=None` / arg swaps → `parse_file.assert_called_once_with(compose)` fails or fallback dict (no "custom-svc") returned. G2-5/6/7/8 → fallback test port==15432 and prometheus-excluded asserts; G2-1/2/3 → success-path asserts (`parse_file` call args / no-fallback-onto-hardcoded).

### T5 — untagged image string format (kills D2a; kills the too-weak existing assertion)

```python
@pytest.mark.asyncio
async def test_discover_untagged_image_uses_container_id_prefix(
    self, mock_docker_client: MagicMock
) -> None:
    """Untagged container image must render as '<untagged:{container.id[:12]}>'."""
    container = create_mock_container(
        name="security-postgres-1", container_id="abc123def456"
    )
    container.image.tags = []
    mock_docker_client.list_containers = AsyncMock(return_value=[container])
    service = ContainerDiscoveryService(mock_docker_client)
    discovered = await service.discover_all()
    assert discovered[0].image == "<untagged:abc123def456>"
```

Replaces/strengthens `test_discover_handles_container_without_image_tags` (L502-519, which asserts only `image is not None` — the reason D2 survives). Kills 23/27/29/30 (`'unknown'`/getattr-None paths), 25/28 (TypeError on `None[:12]`), 33's 12-char-id no-op is EQUIVALENT (use a 13+ char id in the mock to also kill `[:13]`: change id to `"abc123def456789"` and expect `"abc123def456"`).

## WP4.4 notes

- Priority order by mutant yield: T2 (221) ≈ T3 (272, overlaps B4/B5 double-count avoided: T3 kills B3-B8=272, T2 kills B10/B11/B12a/B13/B14/B15/B16b=221, T1 kills B1/B2=125, T4 kills H1+G2=17, T5 kills D2a=6). Total killable-by-drafts ≈ 641 of 696.
- Candidate mutmut exclusions (unkillable/never-killable): B12b (14) + B16a (4) + D2b (3) + D1 (3) + G1 (1) + F1 (2) + E1 (16) = 40 — structural: log text + dataclass-default-equivalent kwargs + tie-order sorts. Alternatively a source fix — drop the redundant `max_failures=5` / `startup_grace_period=60` kwargs and the duplicated static dicts (ALL_CONFIGS vs build_service_configs are ~250 lines of hand-maintained duplication; parity test T3 is the interim guard).
- The `ServiceCategory` in tests comes from `backend.api.schemas.services` (StrEnum) while configs use `orchestrator.models.ServiceCategory` — existing tests pass, so they are aliases, but a future divergence would masquerade as a mutation kill.
