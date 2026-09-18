# WP4.4 triage dossier — backend/services/gpu_config_service.py

- Survivors: **140** (exit_code 0 in `mutants/backend/services/gpu_config_service.py.meta`, read 2026-09-17 14:1x)
- Diffs reconstructed read-only: `uv run mutmut show` raced the live run (`FileNotFoundError: Could not find original function`), and the generated mutant copy reappeared mid-triage (mtime 14:25, 33 530 lines). Frozen copies + the `.spans` line index were snapshotted to `/tmp/wp25/wp44-triage/gpu-copy.py`, `gpu-spans.json`, `gpu-meta.json`; per-key diffs in `/tmp/wp25/wp44-triage/gpu_diffs.json`, signature groups in `gpu_sigs.json` / `gpu_sig_summary.txt`.
- Covering tests (mutmut-stats `tests_by_mangled_function_name`): everything in the survivor set is covered by **`backend/tests/unit/services/test_gpu_config_restart.py`** (single file, 908 lines). `test_gpu_config_service.py` and `test_gpu_config.py` only cover non-survivor members (`__post_init__`, `__init__`, the simple-API generators).
- Shape of the survivor set: heavy logger-payload noise + two real holes — (a) every subprocess call is mocked with `assert_called_once()` / no-arg mocks, so argv/cwd/kwargs/timeouts are never asserted; (b) Redis round-trip deserialization is only ever checked with *minimal or empty* payloads, so dropped keys/defaults are invisible.

## Cluster table

| # | Cluster | n | Class | Example keys | Kill / note |
|---|---------|---|-------|--------------|-------------|
| 1 | `_recreate_service` — log message text, `extra` dict key casing (`service_name`→`SERVICE_NAME`/`XX…XX`), msg→None, `returncode:0→1` inside log payload, `[:500]→[:501]` truncation of logged stdout/stderr | 30 | EQUIVALENT | `_recreate_service__mutmut_48`, `_59`, `_72` | Log payload only; no caller-observable behavior. Test file never asserts caplog. |
| 2 | `_recreate_service` — compose **subprocess invocation** mutated: argv flags (`"-f"`→`"-F"`, `"up"`→`"UP"`, `"-d"`, `"--force-recreate"`, `"--no-deps"` casing/removal), `str(self._compose_file/_override_file)`→`str(None)`, `cwd=None`/`str(None)`/removed, `stdout/stderr=PIPE`→None/removed, `timeout=None` | 22 | **TEST-GAP** | `_recreate_service__mutmut_15`, `_21`, `_40` | `TestRecreateService` (restart test file **L463–554**) mocks `create_subprocess_exec` and only asserts `assert_called_once()` / `result is True/False`. Timeout test patches `wait_for` with a blanket `side_effect`. Drafted: **T3**. |
| 3 | `_get_compose_command` — **probe exec args/kwargs** mutated: `"--version"` arg removed/`None`/casing (both single-cmd and split-cmd branches), `cmd`→`None`, `*parts`/`cmd` removed, `stdout/stderr=DEVNULL`→None/removed | 19 | **TEST-GAP** | `_get_compose_command__mutmut_11`, `_15`, `_21` | `TestGetComposeCommand` (**L562–614**) mocks exec, never inspects args (the "fallback" test even asserts `result in [...4 options incl. None]` — vacuous). Drafted: **T2**. |
| 4 | `_get_compose_command` — candidate-list constants (`"docker compose"`→`"DOCKER COMPOSE"`/`XX…XX`) + `" " in cmd` → `not in` / `"XX XX" in` (space-split branch for `docker compose`) | 4 | **TEST-GAP** | `_get_compose_command__mutmut_5`, `_7`, `_8` | No test ever drives the third candidate or the split path. Killed by T2's per-candidate argv asserts. |
| 5 | `_get_compose_command` — `continue`→`break` on `FileNotFoundError`: first missing candidate (podman-compose) aborts the whole probe | 1 | **TEST-GAP** (highest severity) | `_get_compose_command__mutmut_34` | On any docker-only host this breaks every GPU restart. `test_no_compose_available` uses FileNotFoundError for *all* candidates, `test_docker_compose_fallback` never raises. Drafted: **T1**. |
| 6 | `_get_compose_command` — `logger.debug(f"Using compose command: {cmd}")` → `logger.debug(None)` | 1 | EQUIVALENT | `_get_compose_command__mutmut_33` | Log text. |
| 7 | `_result_from_dict` — every field/key/default mutated: `started_at` parse→None, `completed_at` guard-key renames→never parsed, `completed_at=completed_at`→None/removed, `service_statuses` loop-key renames + `{}`→None init, dict kwargs→None/removed, `changed_services`/`error` key renames and `[]`/default removal | 28 | **TEST-GAP** | `_result_from_dict__mutmut_9`, `_18`, `_39` | Sole covering test `test_get_existing_operation` (**L807–831**) feeds `service_statuses:{}`, `error:None`, and asserts only `operation_id` + `success`. Drafted: **T4** (full-payload round-trip + missing-keys defaults). |
| 8 | `_result_from_dict` — pre-branch default `completed_at = None` → `""` | 1 | EQUIVALENT | `_result_from_dict__mutmut_5` | `""` is falsy; `to_dict()` maps it back to `None`; not observably different. |
| 9 | `ServiceRestartStatus.from_dict` — `data.get("completed_at")` key renames→never parsed, `completed_at=`→None/removed, `error=data.get("error")`→None/removed/key-renamed | 10 | **TEST-GAP** | `from_dict__mutmut_10`, `_16`, `_28` | Both covering tests (**L139–170**) feed `completed_at=None, error=None` — the parse branches run but never with real values; nothing asserts `from_dict(to_dict(x)) == x` on optionals. Drafted: **T5**. |
| 10 | `get_container_status` — lookup args mutated: `get_container_by_name(service_name)`→`(None)`, `get_container_status(container.id)`→`(None)` | 2 | **TEST-GAP** | `get_container_status__mutmut_11`, `_13` | Mocks return canned values for *any* args (**L732–747**). Kill: `assert_awaited_once_with("ai-yolo26")` / `(container.id)` (same pattern as T6; not separately drafted). |
| 11 | `get_container_status` — warning-log text mutations + `dict.fromkeys(service_names, None)`→`dict.fromkeys(service_names)` (identical default) + except-branch msg text | 8 | EQUIVALENT | `get_container_status__mutmut_2`, `_8`, `_15` | Pure log text; `fromkeys` default arg removal is a true no-op. |
| 12 | `get_operation_status` — Redis key f-string→`None` and `redis.get(key)`→`get(None)` | 2 | **TEST-GAP** | `get_operation_status__mutmut_2`, `_4` | `mock_redis_client.get` ignores args (**L807–831**). Drafted: **T6**. |
| 13 | `GpuAssignment.to_dict` — output key `"vram_budget_override"` renamed (`XX…XX`, `VRAM_BUDGET_OVERRIDE`) | 2 | **TEST-GAP** | `to_dict__mutmut_7`, `_8` | `TestGpuAssignment.test_to_dict` (**L259–271**) asserts 3 of the 4 keys — add `assert data["vram_budget_override"] == 8.0` (kills both). |
| 14 | Structured-log **field loss**: `extra={…}`→`extra=None` / `extra` kwarg removed in `_recreate_service` entry/exit/timeout logs and `get_container_status` except-branch log | 10 | LOW-VALUE | `_recreate_service__mutmut_44`, `_55`, `get_container_status__mutmut_16` | Real change to log records (dropped structured fields) but nothing in the product or tests reads these; not worth an assertion budget. |

Totals: 30+22+19+4+1+1+28+1+10+2+8+10+2+2 = **140** (TEST-GAP 90, EQUIVALENT 40, LOW-VALUE 10).

## Drafted tests (target: `backend/tests/unit/services/test_gpu_config_restart.py`)

TDD procedure (applies to every draft): run the test against the mutant copy's change → the new assert must FAIL (red); apply it to the original source → must PASS (green). Only then does the test earn its keep. All drafts are **UNVERIFIED — not yet run red/green** (no test execution permitted in this triage lane).

Imports to add to the file: `import asyncio` and extend `from datetime import UTC, datetime, timedelta`.

### T1 — kills cluster 5 (`continue`→`break`)

```python
    @pytest.mark.asyncio
    async def test_get_compose_command_falls_back_when_podman_compose_missing(
        self,
        gpu_config_service: GpuConfigService,
    ) -> None:
        """A missing podman-compose binary must not abort the probe for docker-compose.

        The mutant that flips `continue` to `break` in the FileNotFoundError handler
        would return None here and silently break every GPU restart on docker-only hosts.
        """

        async def mock_exec(*args: Any, **kwargs: Any) -> AsyncMock:
            if args[0] == "podman-compose":
                raise FileNotFoundError("podman-compose")
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.wait = AsyncMock()
            return mock_process

        with patch("asyncio.create_subprocess_exec", side_effect=mock_exec, autospec=True):
            result = await gpu_config_service._get_compose_command()

        assert result == "docker-compose"
```

// UNVERIFIED - not yet run red/green

### T2 — kills clusters 3 + 4 (probe argv/kwargs, candidate strings, split branch)

```python
    @pytest.mark.asyncio
    async def test_get_compose_command_probes_candidates_with_expected_args(
        self,
        gpu_config_service: GpuConfigService,
    ) -> None:
        """Each candidate must be probed as `<argv...> --version` with output silenced.

        Asserts the exact call (split path for "docker compose" included) and the
        exact success order, killing constant casing/removal and kwarg mutations.
        """
        exec_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

        async def mock_exec(*args: Any, **kwargs: Any) -> AsyncMock:
            exec_calls.append((args, kwargs))
            mock_process = AsyncMock()
            # Only the space-split 'docker compose' invocation succeeds.
            mock_process.returncode = 0 if args[0] == "docker" else 1
            mock_process.wait = AsyncMock()
            return mock_process

        with patch("asyncio.create_subprocess_exec", side_effect=mock_exec, autospec=True):
            result = await gpu_config_service._get_compose_command()

        assert result == "docker compose"
        assert exec_calls[0] == (
            ("podman-compose", "--version"),
            {"stdout": asyncio.subprocess.DEVNULL, "stderr": asyncio.subprocess.DEVNULL},
        )
        assert exec_calls[1] == (
            ("docker-compose", "--version"),
            {"stdout": asyncio.subprocess.DEVNULL, "stderr": asyncio.subprocess.DEVNULL},
        )
        assert exec_calls[2] == (
            ("docker", "compose", "--version"),
            {"stdout": asyncio.subprocess.DEVNULL, "stderr": asyncio.subprocess.DEVNULL},
        )
```

// UNVERIFIED - not yet run red/green

### T3 — kills cluster 2 (`_recreate_service` compose invocation)

Module-level helper (place near the fixtures):

```python
_wait_for_kwargs_seen: dict[str, Any] = {}


async def _spy_wait_for(awaitable: Any, **kwargs: Any) -> Any:
    """Stand in for asyncio.wait_for and record the timeout kwarg it was given."""
    _wait_for_kwargs_seen.clear()
    _wait_for_kwargs_seen.update(kwargs)
    return await awaitable
```

```python
    @pytest.mark.asyncio
    async def test_recreate_service_builds_expected_compose_invocation(
        self,
        gpu_config_service: GpuConfigService,
        tmp_path: Path,
    ) -> None:
        """The compose restart command, cwd, pipe setup and timeout are load-bearing."""
        with (
            patch.object(
                gpu_config_service,
                "_get_compose_command",
                return_value="podman-compose",
                autospec=True,
            ),
            patch("asyncio.create_subprocess_exec", autospec=True) as mock_exec,
            patch("asyncio.wait_for", autospec=True, side_effect=_spy_wait_for),
        ):
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(return_value=(b"recreated", b""))
            mock_exec.return_value = mock_process

            result = await gpu_config_service._recreate_service("ai-yolo26")

        assert result is True
        mock_exec.assert_called_once_with(
            "podman-compose",
            "-f",
            str(gpu_config_service._compose_file),
            "-f",
            str(gpu_config_service._override_file),
            "up",
            "-d",
            "--force-recreate",
            "--no-deps",
            "ai-yolo26",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(tmp_path),
        )
        assert _wait_for_kwargs_seen == {"timeout": GpuConfigService.COMPOSE_TIMEOUT}
```

// UNVERIFIED - not yet run red/green

### T4 — kills cluster 7 (`_result_from_dict` fields)

```python
    def test_result_from_dict_round_trips_full_payload(
        self, gpu_config_service: GpuConfigService
    ) -> None:
        """Redis -> ApplyResult must carry every field through the serializer contract."""
        now = datetime.now(UTC)
        done = now + timedelta(seconds=5)
        payload = {
            "success": False,
            "operation_id": "op-777",
            "started_at": now.isoformat(),
            "completed_at": done.isoformat(),
            "changed_services": ["ai-llm"],
            "service_statuses": {
                "ai-llm": ServiceRestartStatus(
                    service_name="ai-llm",
                    status=RestartStatus.FAILED,
                    started_at=now,
                    completed_at=done,
                    error="boom",
                ).to_dict()
            },
            "error": "partial failure",
        }

        result = gpu_config_service._result_from_dict(payload)

        assert result.success is False
        assert result.operation_id == "op-777"
        assert result.started_at == now
        assert result.completed_at == done
        assert result.changed_services == ["ai-llm"]
        assert result.error == "partial failure"
        assert "ai-llm" in result.service_statuses
        assert result.service_statuses["ai-llm"].status == RestartStatus.FAILED
        assert result.service_statuses["ai-llm"].error == "boom"

    def test_result_from_dict_defaults_for_missing_optional_keys(
        self, gpu_config_service: GpuConfigService
    ) -> None:
        """Missing optional keys must fall back to None/[]/{}/None, never crash."""
        now = datetime.now(UTC)
        payload = {
            "success": True,
            "operation_id": "op-min",
            "started_at": now.isoformat(),
        }

        result = gpu_config_service._result_from_dict(payload)

        assert result.completed_at is None
        assert result.changed_services == []
        assert result.service_statuses == {}
        assert result.error is None
```

// UNVERIFIED - not yet run red/green

### T5 — kills cluster 9 (`ServiceRestartStatus.from_dict` optionals)

```python
    def test_from_dict_round_trips_completed_at_and_error(self) -> None:
        """from_dict(to_dict(x)) must preserve completed_at and error, not just started_at."""
        now = datetime.now(UTC)
        original = ServiceRestartStatus(
            service_name="ai-llm",
            status=RestartStatus.FAILED,
            started_at=now,
            completed_at=now,
            error="boom",
        )

        status = ServiceRestartStatus.from_dict(original.to_dict())

        assert status.service_name == "ai-llm"
        assert status.status == RestartStatus.FAILED
        assert status.started_at == now
        assert status.completed_at == now
        assert status.error == "boom"
```

// UNVERIFIED - not yet run red/green

### T6 — kills cluster 12 (`get_operation_status` Redis key)

```python
    @pytest.mark.asyncio
    async def test_get_operation_status_reads_the_prefixed_redis_key(
        self,
        gpu_config_service: GpuConfigService,
        mock_redis_client: AsyncMock,
    ) -> None:
        """The lookup key must be 'gpu_config:operation:<id>' — a mutated key silently
        turns every status poll into a miss."""
        mock_redis_client.get = AsyncMock(return_value=None)

        result = await gpu_config_service.get_operation_status("op-123")

        assert result is None
        mock_redis_client.get.assert_awaited_once_with("gpu_config:operation:op-123")
```

// UNVERIFIED - not yet run red/green

### Not drafted (one-line kills, noted for the fix lane)

- **Cluster 10**: in `test_get_status_with_containers` add
  `mock_docker_client.get_container_by_name.assert_awaited_with("ai-yolo26")` and
  `mock_docker_client.get_container_status.assert_awaited_with("container123")`.
- **Cluster 13**: in `TestGpuAssignment.test_to_dict` (restart test file L259–271) add
  `assert data["vram_budget_override"] == 8.0` (fixture sets `vram_limit_mb=8192` → 8.0 GB).

## Covering test file line map (backend/tests/unit/services/test_gpu_config_restart.py)

- `TestServiceRestartStatus` L91–170 (`from_dict` tests L139–170 — null-timestamp-only)
- `TestGpuAssignment` L233–271 (`test_to_dict` L259–271 — misses one key)
- `TestRecreateService` L463–554 (subprocess fully mocked; `assert_called_once()` only; timeout test L530–554 patches `wait_for` with blanket side_effect)
- `TestGetComposeCommand` L562–614 (fallback test L582–603 asserts `result in [all options + None]` — vacuous)
- `TestGetContainerStatus` L729–796 (mocks ignore call args)
- `TestGetOperationStatus` L804–863 (`test_get_existing_operation` L807–831 — minimal payload, asserts 2 fields; sole coverer of `_result_from_dict`)

## Verdict summary

- 90 of 140 survivors are TEST-GAP and 78 of those fall to the six drafted tests + two one-line assert additions — this module is cheap to fix.
- Priority: T1 (continue→break) is a genuine latent production bug on docker-only hosts; T3/T2 next (silent broken compose invocations); T4/T5 then (partial-result corruption surfaced to the UI via `get_operation_status`).
- 40 EQUIVALENT + 10 LOW-VALUE (log payload) can go to the ignore/waiver list; if the repo ever adds a `caplog` convention, revisit cluster 1/14.
