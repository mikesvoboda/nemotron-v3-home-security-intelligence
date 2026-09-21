# WP4.4 Triage Dossier — backend/services/service_managers.py

**Gen-2 triage, 2026-09-18.** Survivors extracted from
`mutants/backend/services/service_managers.py.meta` (`exit_code_by_key == 0`); all 94 diffs
pulled read-only via `uv run mutmut show <key>` (0 failures, no manual-diff fallback). No tests
executed; nothing in the repo modified. **UNVERIFIED — no red/green run performed.**

## Totals

| Metric | Count |
|---|---|
| Mutants generated | 152 |
| Killed | 58 |
| **Survived (this dossier)** | **94** |
| TEST-GAP | 13 |
| EQUIVALENT | 29 |
| LOW-VALUE | 52 |

Survivors sit in 4 concerns: `validate_container_name` (2), the two `__init__`s (5),
`ShellServiceManager._check_http_health` (44), `ShellServiceManager._check_redis_health` (43).
`validate_restart_command` and `DockerServiceManager._extract_container_name` are 100% killed —
the security allowlist core is genuinely covered; the residue is health-check plumbing plus a
wall of structured-log payload mutants.

## Why the module looks worse than it is

87 of 94 survivors mutate arguments of `logger.*(...)` calls: message text, `extra=` payload
keys/values, `exc_info`. These change only what is *emitted* to stdlib logging — no return
value, no control flow. (Message-*removal* variants raise `TypeError` inside the logging call,
but the crash is caught by the module's own `except Exception` handler on a path that already
returns the same `False` — net observable outcome unchanged, hence EQUIVALENT, not TEST-GAP.)
The file's tests assert return values and, in two places, log *level*
(NEM-1241 tests, test_service_managers.py:676-714) — never log payload. 7 mutants are real
behavior gaps; 6 more are timeout-constant plumbing gaps.

## Cluster table (counts sum to 94)

Keys are suffixes of `backend.services.service_managers.<key>`; `http` =
`xǁShellServiceManagerǁ_check_http_health`, `redis` =
`xǁShellServiceManagerǁ_check_redis_health`.

| # | Pattern | Fn | Keys | Cls | Example keys |
|---|---|---|---|---|---|
| C1 | `httpx.AsyncClient(timeout=config.health_timeout)` → `timeout=None` — HTTP health timeout unenforced; hung endpoint blocks forever | http | 1 | TEST-GAP | `http__mutmut_1` |
| C2 | redis-cli `create_subprocess_shell(stdout/stderr=asyncio.subprocess.PIPE)` → `None`/removed — output never captured, PONG check can never pass on the real path | redis | 4 | TEST-GAP | `redis__mutmut_3, _4, _6` |
| C3 | command `"redis-cli ping"` → `"XXredis-cli pingXX"` — spawns nonexistent command; existing substring-`in` assert can't see it | redis | 1 | TEST-GAP | `redis__mutmut_8` |
| C4 | `asyncio.wait_for(communicate(), timeout=config.health_timeout)` → `timeout=None` — redis health timeout unenforced | redis | 1 | TEST-GAP | `redis__mutmut_12` |
| C5 | PONG gate `returncode == 0 and b"PONG" in stdout` → `or` — healthy verdict from rc≠0 alone or garbage stdout alone | redis | 1 | TEST-GAP | `redis__mutmut_24` |
| C6 | container-name gate `len(name) > 128` → `>= 128` / `> 129` — Docker 128-char boundary off-by-one | validate_container_name | 2 | TEST-GAP | `x_validate_container_name__mutmut_3, _4` |
| C7 | ctor default `subprocess_timeout=60.0` → `61.0` — default timeout constant tweak | both `__init__`s | 2 | LOW-VALUE | `…ShellServiceManager…__init____mutmut_1`, `…DockerServiceManager…__init____mutmut_1` |
| C8-attr | ctor body `self._subprocess_timeout = subprocess_timeout` → `None`; `ShellServiceManager(subprocess_timeout)` → `(None)` — timeout plumbing severed, real restart/health would use None | both `__init__`s | 3 | TEST-GAP | `…Shell…__init____mutmut_2`, `…Docker…__init____mutmut_2, _4` |
| C9 | log msg f-string → `None` or arg removed (stdlib logs "None" / the removal crash is absorbed by the module's own except → same return) | http, redis | 12 | EQUIVALENT | `http__mutmut_4, _13`, `redis__mutmut_15` |
| C10 | `extra={…}` → `extra=None` (stdlib `_log` treats falsy extra as absent — semantically identical) | http, redis | 9 | EQUIVALENT | `http__mutmut_5, _14`, `redis__mutmut_16` |
| C11 | `extra={…}` kwarg removed entirely (same no-extra outcome as C10) | http, redis | 8 | EQUIVALENT | `http__mutmut_7, _16, _48`, `redis__mutmut_18` |
| C12 | structured-log key mangled: `"service"`→`"XXserviceXX"`/`"SERVICE"`, same for `url`, `error`, `timeout`, `status_code`, `returncode`, `stdout`, `stderr` | http, redis | 40 | LOW-VALUE | `http__mutmut_8, _9`, `redis__mutmut_41` |
| C13 | `exc_info=True` → `None`/`False`/removed on the unexpected-error `logger.error` — traceback dropped from the ERROR record | http, redis | 6 | LOW-VALUE | `http__mutmut_46, _49, _55` |
| C14 | logged exception detail `str(e)` → `str(None)` — `error` field becomes `"None"` | http, redis | 4 | LOW-VALUE | `http__mutmut_21, _33, _54` |

Class sums: TEST-GAP = 1+4+1+1+1+2+3 = **13**; EQUIVALENT = 12+9+8 = **29**; LOW-VALUE =
2+40+6+4 = **52**. Grand total **94**.

## Covering tests

`mutmut-stats.json` → `tests_by_mangled_function_name` maps every surviving function to
**`backend/tests/unit/services/test_service_managers.py`** only (34 tests; the file cited below
is this one). The gap is structural: health-check tests mock `httpx.AsyncClient` and
`asyncio.create_subprocess_shell` wholesale and assert only `result is True/False` — mock
substitution hides every kwargs mutation, and no test asserts log payload.

| Cluster | Test that executes the line | What it misses (file:line) |
|---|---|---|
| C1 | `test_shell_health_check_success` | builds the AsyncClient mock but never asserts the constructor `timeout=` kwarg (test_service_managers.py:88-105) |
| C2, C3 | `test_shell_health_check_redis_ping_success` | asserts `"redis-cli ping" in call_args[0][0]` — substring survives the mangling; never inspects `stdout=`/`stderr=` kwargs (:189-203, weak assert at :203) |
| C4 | `test_shell_health_check_redis_ping_timeout` | fakes the timeout by making the mocked `communicate` raise `TimeoutError`, so `wait_for`'s `timeout=` value is never checked (:221-233) |
| C5 | `test_shell_health_check_redis_ping_failure` | tests only rc=1 **and** empty stdout together; never rc=0/no-PONG nor rc=1/PONG — the `and`→`or` distinction (:207-217) |
| C6 | `test_validate_container_name_invalid` | length boundary only at `"a"*200`; nothing at 128/129 (:389-401, assert at :401) |
| C7, C8-attr | fixtures `shell_manager`/`docker_manager` pass `subprocess_timeout=5.0`, but no test ever reads `_subprocess_timeout` (:47-55). `test_service_config_defaults` (:567-576) shows the repo already accepts defaults-assertion tests |
| C9–C14 | NEM-1241 tests assert `mock_logger.warning.assert_called_once()` — level only, zero message/payload assertions (:676-714) |

Source anchors (`backend/services/service_managers.py`): `:96` length gate; `:167-174`,
`:423-432` ctors; `:190` redis dispatch; `:205` AsyncClient; `:253-257` subprocess PIPE;
`:260-263` wait_for; `:273` PONG gate; `:208-241`/`:267-297` the log-call clusters.

## Drafted kill-tests

All targets append to `backend/tests/unit/services/test_service_managers.py`; add `import
asyncio` to its header (currently absent — file imports only mocks/httpx/pytest/module names).
**// UNVERIFIED — not yet run red/green.** TDD procedure (same for each): apply the cluster's
mutant → the new assertion fails (red); original source → passes (green); re-run mutmut on those
keys → flip to killed.

### D1 — kills C1 (health_timeout reaches the httpx client)

```python
@pytest.mark.asyncio
async def test_shell_health_http_check_enforces_health_timeout(shell_manager, sample_config):
    """WP4.4: HTTP health checks must pass config.health_timeout to httpx.

    Mutation kill: httpx.AsyncClient(timeout=config.health_timeout) -> timeout=None
    leaves a hung endpoint blocking the health monitor indefinitely.
    """
    with patch(
        "backend.services.service_managers.httpx.AsyncClient", autospec=True
    ) as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await shell_manager.check_health(sample_config)

        assert result is True
        # sample_config.health_timeout == 1.0; the mutant passes timeout=None.
        assert mock_client_class.call_args.kwargs["timeout"] == sample_config.health_timeout
```

### D2 — kills C2 + C3 (exact command string, output actually captured)

```python
@pytest.mark.asyncio
async def test_shell_redis_health_check_exact_command_with_pipes(shell_manager, redis_config):
    """WP4.4: redis-cli ping must be invoked verbatim with stdout/stderr piped.

    Mutation kill: "redis-cli ping" -> "XXredis-cli pingXX" (the existing substring
    `in` assert cannot see it) and stdout/stderr PIPE -> None (communicate() would
    then yield (None, None) and the PONG check can never pass on the real path).
    """
    with patch("asyncio.create_subprocess_shell", autospec=True) as mock_proc:
        process = AsyncMock()
        process.returncode = 0
        process.communicate = AsyncMock(return_value=(b"PONG\n", b""))
        mock_proc.return_value = process

        result = await shell_manager.check_health(redis_config)

        assert result is True
        call_args = mock_proc.call_args
        assert call_args[0][0] == "redis-cli ping"  # exact, not substring
        assert call_args.kwargs["stdout"] is asyncio.subprocess.PIPE
        assert call_args.kwargs["stderr"] is asyncio.subprocess.PIPE
```

### D3 — kills C4 (config timeout reaches asyncio.wait_for)

```python
@pytest.mark.asyncio
async def test_shell_redis_health_check_timeout_reaches_wait_for(shell_manager, redis_config):
    """WP4.4: redis health must enforce config.health_timeout via asyncio.wait_for.

    Mutation kill: wait_for(..., timeout=config.health_timeout) -> timeout=None
    (a hung redis-cli would never be killed).
    """
    with (
        patch("asyncio.create_subprocess_shell", autospec=True) as mock_proc,
        patch("asyncio.wait_for", autospec=True) as mock_wait_for,
    ):
        process = AsyncMock()
        process.returncode = 0
        mock_wait_for.return_value = (b"PONG\n", b"")
        mock_proc.return_value = process

        result = await shell_manager.check_health(redis_config)

        assert result is True
        # redis_config uses the ServiceConfig default health_timeout == 5.0.
        assert mock_wait_for.call_args.kwargs["timeout"] == redis_config.health_timeout
```

### D4 — kills C5 (healthy Redis needs BOTH rc==0 and PONG)

```python
@pytest.mark.asyncio
async def test_shell_redis_health_requires_returncode_and_pong(shell_manager, redis_config):
    """WP4.4: healthy Redis requires exit code 0 AND PONG, never either alone.

    Mutation kill: `returncode == 0 and b"PONG" in stdout` -> `or`.
    """
    # Exit code 0 but no PONG: healthy? No.
    with patch("asyncio.create_subprocess_shell", autospec=True) as mock_proc:
        process = AsyncMock()
        process.returncode = 0
        process.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.return_value = process

        assert await shell_manager.check_health(redis_config) is False

    # PONG on stdout but non-zero exit: healthy? No.
    with patch("asyncio.create_subprocess_shell", autospec=True) as mock_proc:
        process = AsyncMock()
        process.returncode = 1
        process.communicate = AsyncMock(return_value=(b"PONG\n", b""))
        mock_proc.return_value = process

        assert await shell_manager.check_health(redis_config) is False
```

### D5 — kills C6 (Docker 128-char name boundary)

```python
def test_validate_container_name_length_boundary():
    """WP4.4: Docker's limit is *exactly* 128 chars (service_managers.py:96).

    Mutation kill: `len(name) > 128` -> `>= 128` (rejects a valid 128-char name)
    or `> 129` (accepts an invalid 129-char one). Existing test only tries 200.
    """
    assert validate_container_name("a" * 128) is True   # at the limit: valid
    assert validate_container_name("a" * 129) is False  # one over: invalid
```

### D6 — kills C8-attr (ctor timeout plumbing); kills C7 as a side effect

```python
def test_service_managers_store_subprocess_timeout():
    """WP4.4: ctors must store the timeout and forward it to the delegate.

    Mutation kill: `self._subprocess_timeout = None`,
    `ShellServiceManager(subprocess_timeout)` -> `ShellServiceManager(None)`,
    and (bonus, C7) default `60.0` -> `61.0`.
    """
    assert ShellServiceManager()._subprocess_timeout == 60.0
    assert DockerServiceManager()._subprocess_timeout == 60.0
    assert DockerServiceManager()._shell_manager._subprocess_timeout == 60.0

    shell_mgr = ShellServiceManager(subprocess_timeout=7.5)
    assert shell_mgr._subprocess_timeout == 7.5

    docker_mgr = DockerServiceManager(subprocess_timeout=7.5)
    assert docker_mgr._subprocess_timeout == 7.5
    assert docker_mgr._shell_manager._subprocess_timeout == 7.5
```

## Recommendation for WP4.4

- Land D1-D6: 6 tests kill all 13 TEST-GAP survivors + both C7 LOW-VALUE constants = 15 keys.
- C9/C10/C11 (29 EQUIVALENT): record as equivalent, no tests.
- C12/C13/C14 (50 LOW-VALUE): recommend an equivalent-by-policy ruling (structured-log payload
  is asserted nowhere in this repo; the NEM-1241 precedent deliberately asserts level only). A
  `caplog.set_level(logging.DEBUG)` + `record.<key>` helper could kill them if the harness
  insists on numeric score, but that pins log schema into the test suite — flag for the WP4.4
  ruling rather than drafting.

---

## Appendix — full survivor assignment (94; machine-readable copy in clusters.json path below)

- **C1 (1):** http _1
- **C2 (4):** redis _3, _4, _6, _7
- **C3 (1):** redis _8
- **C4 (1):** redis _12
- **C5 (1):** redis _24
- **C6 (2):** x_validate_container_name _3, _4
- **C7 (2):** Shell __init__ _1; Docker __init__ _1
- **C8-attr (3):** Shell __init__ _2; Docker __init__ _2, _4
- **C9 (12):** http _4, _13, _23, _35, _44; redis _15, _17, _30, _37, _39, _50, _54
- **C10 (9):** http _5, _14, _24, _36, _45; redis _16, _31, _38, _51
- **C11 (8):** http _7, _16, _26, _38, _48; redis _18, _33, _40
- **C12 (40):** http _8, _9, _10, _11, _17, _18, _19, _20, _27, _28, _29, _30, _31, _32, _39, _40, _41, _42, _50, _51, _52, _53; redis _19, _20, _21, _22, _34, _35, _41, _42, _43, _44, _45, _46, _47, _48, _56, _57, _58, _59
- **C13 (6):** http _46, _49, _55; redis _52, _55, _61
- **C14 (4):** http _21, _33, _54; redis _60

Sum: 1+4+1+1+1+2+2+3+12+9+8+40+6+4 = 94.
Machine-readable per-key assignment:
`/tmp/claude-1000/-agents-agent-nemo2-workspace/79a1f342-0c47-43c3-bc69-b513f06e89fc/scratchpad/sm/clusters.json`
(there `C8`=msg-removal set incl. http _48; move that one key from its C8 list to C11 per the
reclassification noted above), raw diffs: `.../scratchpad/sm/diffs.txt`.
