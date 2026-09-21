# WP4.4 Triage Dossier — backend/services/container_orchestrator.py

- **Source**: `backend/services/container_orchestrator.py` (589 lines)
- **Meta**: `mutants/backend/services/container_orchestrator.py.meta` — 344 keys total, **0 null**, **248 killed**, **96 SURVIVED**
- **Diffs**: all 96 collected via `uv run mutmut show <key>` (no fallback needed)
- **Covering tests** (from `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`):
  - `backend/tests/unit/services/test_container_orchestrator.py` (1889 lines) — primary
  - `backend/tests/unit/services/test_service_status_events.py` (737 lines) — secondary (WS event contract)

## Semantic checks performed (read-only)

| Fact | Evidence | Consequence |
|---|---|---|
| `ServiceStatusEvent.type` has `Field(default="service_status")` | `backend/api/schemas/services.py:278-281` | dropping `type=` kwarg in `create_service_status_event` is semantically identical → EQUIVALENT |
| `ServiceRegistry.update_status/reset_failures/set_enabled/record_restart/persist_state` all `_services.get(name)` → silent no-op for unknown/None names | `backend/services/orchestrator/registry.py:172-267, 322-340` | `None`-arg mutants never crash; they silently skip real state mutation → survive unless call *args* or resulting state is asserted → TEST-GAP |
| `LifecycleManager.__init__` stores `self.registry/docker_client/on_restart/on_disabled` | `backend/services/lifecycle_manager.py:97-115` | start() wiring is inspectable on the live object |
| `HealthMonitor.__init__` stores `self._registry/_docker_client/_settings/_on_health_change/_on_network_isolation` | `backend/services/health_monitor_orchestrator.py:201-229` | same |
| `ServiceRegistry.__init__(redis_client)` stores `self._redis`; None disables all persistence | `backend/services/orchestrator/registry.py:66-75` | `ServiceRegistry(None)` mutant silently breaks cross-restart state persistence |
| `ContainerDiscoveryService.__init__(docker_client, settings=None, compose_file=None)` | `backend/services/container_discovery.py:671-696` | arg-drop mutants shift/reduce positional args; settings=None path guarded by `if settings else None` |
| WS-message mutants survive because `test_container_orchestrator.py` asserts LM-path messages via `.lower()` **substring** (lines 1115, 1145, 1231), while `test_service_status_events.py` exact-equality asserts (lines 507/536/568/572/602/631) only exercise the **fallback** path (`_lifecycle_manager = None` via `__new__` bypass) | both test files | "XXRestart succeededXX".lower() contains "succeeded" → survives; exact-equality on LM path kills |
| Component sentinel `""` is falsy → every `if self._lifecycle_manager:` / `if self._health_monitor:` guard behaves identically to `None` | source lines 252, 295, 336, 369, 412, 457, 569 | observable only via `is None` identity on fresh instance → LOW-VALUE |

## Cluster table (96 = 58+9+9+11+5+1+2+1)

| # | Cluster | N | Class | Example keys (≤3) | Mutated line(s) | Note |
|---|---|---|---|---|---|---|
| C1 | **Log message text** — `logger.*(...)` message arg → `None` / `"XX…XX"` / lower / UPPER, across `__init__`, `_broadcast_status`, `enable/disable/restart/start_service`, `start`, `stop` | 58 | EQUIVALENT | `…__init____mutmut_20`, `…start__mutmut_16`, `…stop__mutmut_5` | 177, 219, 225-231, 332, 365, 398, 402, 449, 453, 494-552, 563-582 | Pure log-text per WP4.4 rubric. Log shape (`level`, exception flow) unchanged; no test asserts log content (none caplog-wrapped). |
| C2 | **WS payload text on lifecycle-manager paths** — `_broadcast_status(..., "Restart succeeded"/"Restart failed"/"Service started")` → XX/lower/UPPER variants | 9 | TEST-GAP | `…restart_service__mutmut_26`, `…restart_service__mutmut_33`, `…start_service__mutmut_17` | 417, 419, 462 | Message is part of the WebSocket event contract. `test_service_status_events.py` asserts the *same strings* exactly — but only on the fallback path; LM-path tests in `test_container_orchestrator.py:1115,1145,1231` use `.lower()` substring, so case/decoration variants slip through. |
| C3 | **`__init__` component wiring** — `ServiceRegistry(redis_client)` → `(None)`; `ContainerDiscoveryService(docker_client, settings, compose_file=settings.compose_file if settings else None)` → arg→None / arg-removed / guard-flip `and False`, `or True` | 9 | TEST-GAP | `…__init____mutmut_8`, `…__init____mutmut_10`, `…__init____mutmut_12` | 165-171 | Tests construct these for real but `discover_all` is always `patch.object`'d on the instance and `test_init_creates_registry` only checks `is not None` (`test_container_orchestrator.py:244`). Real breakage: `ServiceRegistry(None)` silently disables Redis persistence; `compose_file=None` switches discovery config source. `mutmut_17` (`or True`) additionally crashes when `settings=None` (untested edge the guard exists for). |
| C4 | **`start()` callback wiring** — `LifecycleManager(...)`/`HealthMonitor(...)` kwargs → `None` or removed (`registry`, `docker_client`, `on_restart`, `on_disabled`, `on_health_change`, `on_network_isolation`) | 11 | TEST-GAP | `…start__mutmut_36`, `…start__mutmut_40`, `…start__mutmut_46` | 532-546 | Real behavior loss: with `on_restart=None` the "Restart completed" broadcast never fires from the LM, with `on_health_change=None` the entire heal+broadcast loop is dead — yet tests only assert `_health_monitor is not None` (`:363`) and drive callbacks *directly* (`orchestrator._on_restart(...)`, `:1371-1387`), never through the components. Killable by inspecting live attributes post-`start()` (both classes store the kwargs). |
| C5 | **None-substituted call args on control paths** — `_lifecycle_manager.restart_service(None)` / `start_service(None)`, `_registry.update_status(None, …)`, `_registry.persist_state(None)` | 5 | TEST-GAP | `…restart_service__mutmut_19`, `…restart_service__mutmut_39`, `…start_service__mutmut_26` | 413, 423(via 426), 426, 427, 458, 469 | Registry methods no-op silently on `None` key (verified), LM call is behind `autospec` patches that don't type-check. `test_restart_service_fallback_success` (`:1148-1174`) asserts `restart_count>0` and message substring but NOT resulting status (`STARTING`) nor `persist_state` args; LM tests never check call args. |
| C6 | **`restart_service(reset_failures=False)` default flipped to True** | 1 | TEST-GAP | `…restart_service__mutmut_1` | 383 | Every caller that omits the arg now silently wipes failure history on a manual restart, defeating max-failure auto-disable. Only test uses explicit `reset_failures=True` (`:1068-1085`) — passes identically on mutant. |
| C7 | **Sentinel `None` → `""`** for `_health_monitor` / `_lifecycle_manager` in `__init__` | 2 | LOW-VALUE | `…__init____mutmut_18`, `…__init____mutmut_19` | 174-175 | `""` is falsy, so all seven truthiness guards behave identically; observable only via `is None` identity on a never-started instance. Nobody should assert that. |
| C8 | **Dropped `type="service_status"` kwarg** in `create_service_status_event` | 1 | EQUIVALENT | `x_create_service_status_event__mutmut_40` | 98 | Pydantic field carries `default="service_status"` (`backend/api/schemas/services.py:278-281`) → `model_dump(mode="json")` byte-identical; `test_event_type_is_service_status` (`:951-955`) already asserts the surviving value. |

## Drafted kill-tests (5 tests → kill C2, C3, C4, C5, C6 = 35/36 TEST-GAP mutants)

All UNVERIFIED — not yet run red/green. TDD procedure for each: apply the cluster's mutant diff → new assert FAILS; revert to original → PASSES. Target file: `backend/tests/unit/services/test_container_orchestrator.py` (append; reuses existing module fixtures `orchestrator`, `managed_service`, `mock_docker_client`, `mock_broadcast_fn`).

```python
# =============================================================================
# WP4.4 kill tests — surviving-mutant clusters (UNVERIFIED - not yet run red/green)
# =============================================================================


class TestWp44ComponentWiring:
    """Kill cluster C3/C4: collaborators constructed with None/missing args."""

    def test_init_forwards_dependencies_to_registry_and_discovery(
        self,
        mock_docker_client: AsyncMock,
        mock_redis_client: AsyncMock,
        mock_settings: MagicMock,
    ) -> None:
        """Registry gets the Redis client; discovery gets client/settings/compose_file.

        UNVERIFIED - not yet run red/green. Kills __init__ mutmut_8 (ServiceRegistry(None)),
        _10/_13 (docker_client -> None / removed), _11/_14 (settings -> None / removed),
        _12/_16 (compose_file forced None), _15 (compose_file kwarg removed).
        """
        with patch(
            "backend.services.container_orchestrator.ContainerDiscoveryService", autospec=True
        ) as mock_discovery_cls:
            orchestrator = ContainerOrchestrator(
                docker_client=mock_docker_client,
                redis_client=mock_redis_client,
                settings=mock_settings,
            )

        assert orchestrator._registry._redis is mock_redis_client

        call = mock_discovery_cls.call_args
        assert call.args == (mock_docker_client, mock_settings)
        assert "compose_file" in call.kwargs
        assert call.kwargs["compose_file"] == mock_settings.compose_file

    def test_init_with_none_settings_does_not_crash(
        self, mock_docker_client: AsyncMock, mock_redis_client: AsyncMock
    ) -> None:
        """settings=None must take the guarded None-compose path, not AttributeError.

        UNVERIFIED - not yet run red/green. Kills __init__ mutmut_17 (`if (settings) or True`).
        """
        orchestrator = ContainerOrchestrator(
            docker_client=mock_docker_client,
            redis_client=mock_redis_client,
            settings=None,
        )

        assert orchestrator._discovery_service._docker_client is mock_docker_client

    @pytest.mark.asyncio
    async def test_start_wires_lifecycle_manager_and_health_monitor(
        self,
        orchestrator: ContainerOrchestrator,
        mock_docker_client: AsyncMock,
        mock_settings: MagicMock,
    ) -> None:
        """Components created by start() must be bound to the shared registry and callbacks.

        UNVERIFIED - not yet run red/green. Kills start() mutmut_35/44 (docker_client=None),
        _36/_40 (on_restart), _37/_41 (on_disabled), _43 (registry=None),
        _46/_51 (on_health_change), _47/_52 (on_network_isolation).
        """
        with patch.object(
            orchestrator._discovery_service, "discover_all", return_value=[], autospec=True
        ):
            await orchestrator.start()

        lm = orchestrator._lifecycle_manager
        hm = orchestrator._health_monitor
        assert lm is not None
        assert hm is not None

        # LifecycleManager stores its kwargs as public attrs
        assert lm.registry is orchestrator._registry
        assert lm.docker_client is mock_docker_client
        assert lm.on_restart == orchestrator._on_restart
        assert lm.on_disabled == orchestrator._on_disabled

        # HealthMonitor stores its kwargs as private attrs
        assert hm._registry is orchestrator._registry
        assert hm._docker_client is mock_docker_client
        assert hm._settings is mock_settings
        assert hm._on_health_change == orchestrator._on_health_change
        assert hm._on_network_isolation == orchestrator._on_network_isolation


class TestWp44ControlPathArgsAndMessages:
    """Kill clusters C2/C5/C6: None call args, exact LM-path messages, param default."""

    @pytest.mark.asyncio
    async def test_restart_service_delegates_real_service_to_lifecycle_manager(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_docker_client: AsyncMock,
    ) -> None:
        """UNVERIFIED - not yet run red/green. Kills restart_service mutmut_19 (`restart_service(None)`)."""
        orchestrator._registry.register(managed_service)
        mock_docker_client.connect.return_value = True
        with patch.object(
            orchestrator._discovery_service, "discover_all", return_value=[], autospec=True
        ):
            await orchestrator.start()

        with patch.object(
            orchestrator._lifecycle_manager, "restart_service", return_value=True, autospec=True
        ) as mock_restart:
            assert await orchestrator.restart_service("ai-yolo26") is True

        mock_restart.assert_called_once_with(managed_service)

    @pytest.mark.asyncio
    async def test_start_service_delegates_real_service_to_lifecycle_manager(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_docker_client: AsyncMock,
    ) -> None:
        """UNVERIFIED - not yet run red/green. Kills start_service mutmut_10 (`start_service(None)`)."""
        orchestrator._registry.register(managed_service)
        mock_docker_client.connect.return_value = True
        with patch.object(
            orchestrator._discovery_service, "discover_all", return_value=[], autospec=True
        ):
            await orchestrator.start()

        with patch.object(
            orchestrator._lifecycle_manager, "start_service", return_value=True, autospec=True
        ) as mock_start:
            assert await orchestrator.start_service("ai-yolo26") is True

        mock_start.assert_called_once_with(managed_service)

    @pytest.mark.asyncio
    async def test_restart_service_fallback_updates_status_and_persists_by_name(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_docker_client: AsyncMock,
    ) -> None:
        """Fallback path must update status STARTING and persist under the real name.

        UNVERIFIED - not yet run red/green. Kills restart_service mutmut_39
        (`update_status(None, STARTING)` — silently no-ops, status stays RUNNING)
        and mutmut_43 (`persist_state(None)`).
        """
        mock_docker_client.restart_container.return_value = True
        orchestrator._registry.register(managed_service)
        orchestrator._lifecycle_manager = None

        with patch.object(
            orchestrator._registry, "persist_state", new_callable=AsyncMock
        ) as mock_persist:
            assert await orchestrator.restart_service("ai-yolo26") is True

        mock_persist.assert_called_once_with("ai-yolo26")
        service = orchestrator.get_service("ai-yolo26")
        assert service is not None
        assert service.status == ContainerServiceStatus.STARTING

    @pytest.mark.asyncio
    async def test_start_service_fallback_persists_by_name(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_docker_client: AsyncMock,
    ) -> None:
        """UNVERIFIED - not yet run red/green. Kills start_service mutmut_26 (`persist_state(None)`)."""
        mock_docker_client.start_container.return_value = True
        orchestrator._registry.register(managed_service)
        orchestrator._lifecycle_manager = None

        with patch.object(
            orchestrator._registry, "persist_state", new_callable=AsyncMock
        ) as mock_persist:
            assert await orchestrator.start_service("ai-yolo26") is True

        mock_persist.assert_called_once_with("ai-yolo26")

    @pytest.mark.asyncio
    async def test_restart_and_start_service_lm_paths_broadcast_exact_messages(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_docker_client: AsyncMock,
        mock_broadcast_fn: AsyncMock,
    ) -> None:
        """LM-path broadcasts must carry the exact contract strings (not lowercased/decorated).

        UNVERIFIED - not yet run red/green. Kills restart_service mutmut_26/27/28
        ("Restart succeeded"), _33/_34/_35 ("Restart failed") and start_service
        mutmut_17/18/19 ("Service started") — the existing LM-path assertions in
        this file (lines 1115/1145/1231) use .lower() substring and let all variants pass.
        """
        orchestrator._registry.register(managed_service)
        mock_docker_client.connect.return_value = True
        with patch.object(
            orchestrator._discovery_service, "discover_all", return_value=[], autospec=True
        ):
            await orchestrator.start()

        with patch.object(
            orchestrator._lifecycle_manager, "restart_service", return_value=True, autospec=True
        ):
            mock_broadcast_fn.reset_mock()
            assert await orchestrator.restart_service("ai-yolo26") is True
        messages = [c.args[0]["message"] for c in mock_broadcast_fn.call_args_list]
        assert "Restart succeeded" in messages

        with patch.object(
            orchestrator._lifecycle_manager, "restart_service", return_value=False, autospec=True
        ):
            mock_broadcast_fn.reset_mock()
            assert await orchestrator.restart_service("ai-yolo26") is False
        messages = [c.args[0]["message"] for c in mock_broadcast_fn.call_args_list]
        assert "Restart failed" in messages

        with patch.object(
            orchestrator._lifecycle_manager, "start_service", return_value=True, autospec=True
        ):
            mock_broadcast_fn.reset_mock()
            assert await orchestrator.start_service("ai-yolo26") is True
        messages = [c.args[0]["message"] for c in mock_broadcast_fn.call_args_list]
        assert "Service started" in messages

    @pytest.mark.asyncio
    async def test_restart_service_default_preserves_failure_count(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_docker_client: AsyncMock,
    ) -> None:
        """UNVERIFIED - not yet run red/green. Kills restart_service mutmut_1
        (reset_failures default False -> True: a plain manual restart would wipe
        the max-failure history that gates auto-disable)."""
        managed_service.failure_count = 4
        orchestrator._registry.register(managed_service)
        orchestrator._lifecycle_manager = None
        mock_docker_client.restart_container.return_value = True

        assert await orchestrator.restart_service("ai-yolo26") is True

        service = orchestrator.get_service("ai-yolo26")
        assert service is not None
        assert service.failure_count == 4
```

## Kill accounting

| Cluster | Killed by | Drafted? |
|---|---|---|
| C2 (9) | `test_restart_and_start_service_lm_paths_broadcast_exact_messages` | yes |
| C3 (9) | `test_init_forwards_dependencies_to_registry_and_discovery` (8) + `test_init_with_none_settings_does_not_crash` (1: mutmut_17) | yes |
| C4 (11) | `test_start_wires_lifecycle_manager_and_health_monitor` | yes |
| C5 (5) | `test_restart_service_delegates_real_service_to_lifecycle_manager`, `test_start_service_delegates_real_service_to_lifecycle_manager`, `test_restart_service_fallback_updates_status_and_persists_by_name`, `test_start_service_fallback_persists_by_name` | yes |
| C6 (1) | `test_restart_service_default_preserves_failure_count` | yes |
| C1 (58) | not drafted — EQUIVALENT log text; killing would require caplog assertions nobody should maintain | no |
| C7 (2) | not drafted — LOW-VALUE sentinel identity | no |
| C8 (1) | not drafted — EQUIVALENT (pydantic default) | no |

Drafts cover 35 of 36 TEST-GAP survivors; no drafted test targets C1/C7/C8.
