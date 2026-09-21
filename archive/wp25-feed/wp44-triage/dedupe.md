# WP4.4 Triage Dossier — backend/services/dedupe.py

- **Survivors:** 120 of 284 keys (`exit_code_by_key == 0`)
- **Module:** `backend/services/dedupe.py` (618 lines) — SHA256 file-hash idempotency + Redis dedupe service
- **Method:** diffs extracted manually from `mutants/backend/services/dedupe.py` (variants diffed against `__mutmut_orig`; mutmut cache under concurrent write). Per-key diffs: `/tmp/wp25/wp44-triage/diffs.txt`. No tests run — everything UNVERIFIED.
- **Per-function survivors:** compute_file_hash 36, is_duplicate 10, _check_redis 7, mark_processed 19, is_duplicate_and_mark 14, clear_hash 4, cleanup_orphaned_keys 24, ensure_key_has_ttl 6 = **120** ✓
- **Primary covering test file:** `backend/tests/unit/services/test_dedupe.py` (1540 lines; `asyncio_mode = "auto"` per pyproject:492)
- **Secondary (execution-only, no Redis-arg asserts):** `backend/tests/unit/services/test_file_watcher.py` (13 tests drive is_duplicate/_check_redis/mark_processed/is_duplicate_and_mark), `backend/tests/unit/services/test_redis_streams_integration.py` (1)

## Headline finding

**95/120 (79%) are log-shape mutants** (EQUIVALENT): structlog `extra={...}` payload key-casing/clobbering (`XXstatusXX`/`STATUS`/`FILE_NOT_FOUND`), message→None, `exc_info` True→None/False/removed. No test asserts log records; none should.

**19/120 are real TEST-GAPs**, and they share one root cause: tests mock the Redis clients and assert *that* `exists`/`delete`/`set`/`expire`/`ttl` were awaited — almost never **with which key/ttl argument**. Mutants that pass `None` instead of `self._get_redis_key(file_hash)`, or drop the delegation arguments, sail through. Notably `cleanup_orphaned_keys` is the one method where the behavior IS asserted (`expire.assert_awaited_with`, test_dedupe.py:985) — and its ttl/expire mutants did not survive.

**6/120 are LOW-VALUE** (scan-hint kwargs). 0 EQUIVALENT miscounts: per-key cluster assignments below sum exactly.

## Cluster table (exhaustive, mutually exclusive)

| # | Pattern | N | Example keys | Class | Evidence |
|---|---------|---|--------------|-------|----------|
| 1 | compute_file_hash: file_not-found log-site `extra`/message mutations | 9 | `_4, _5, _7` | EQUIVALENT | warning message→None, `extra` None/removed, key clobbers. Return unchanged; test :111-118 asserts HashResult only. |
| 2 | compute_file_hash: empty_file log-site mutations | 8 | `_17, _18, _20` | EQUIVALENT | same shape on empty-file branch; test :120-127. |
| 3 | compute_file_hash: permission-denied log-site + `exc_info` mutations | 13 | `_45, _46, _47` | EQUIVALENT | test :140-159 asserts result only. |
| 4 | compute_file_hash: `f.read(8192)` → None/8193 chunk-size | 2 | `_40, _41` | EQUIVALENT | SHA256 is chunk-size-invariant; 32KB-file test :129-138 still exact. |
| 5 | compute_file_hash: result-factory arg `file_path` → None (error_message text only) | 4 | `_14, _27, _58, _59` | EQUIVALENT | `status`/`hash` unchanged; tests assert `in`-substrings of the file path only in factory tests (:308-348), which call factories directly, not via compute_file_hash. `_59` (error→None) → f-string embeds "None"; substring assertions still hold. |
| 6 | `_check_redis`: computed key dropped before `exists()` (`key = None` / `_get_redis_key(None)`) | 2 | `_2, _3` | **TEST-GAP** | `exists.assert_awaited_once()` (:561) — no arg check. Mocks accept None. |
| 7 | `_check_redis`: `exists(key)` → `exists(None)` | 1 | `_5` | **TEST-GAP** | same arg-blind spot; drafted test 1 also closes this (its `assert_awaited_with` covers both key-computation and call-site mutants). |
| 8 | `_check_redis`: orphan-TTL delegation with wrong hash (`ensure_key_has_ttl(None)`) | 1 | `_8` | **TEST-GAP** | mutant sets TTL on `dedupe:None`, leaving the real key orphaned. No test asserts `expire` in the check-duplicate flow. Killed by drafted test 1 (ttl=-1 + expire assert). |
| 9 | `_check_redis` log mutations (info duplicate-detected, warning on Redis failure) | 3 | `_9, _10, _13` | EQUIVALENT | message/None/[:17] slice tweaks. |
| 10 | `mark_processed`: `set()` key arg → None / `_get_redis_key(None)` | 3 | `_17, _18, _19` | **TEST-GAP** | tests assert only `call_kwargs[1]["expire"]` (:618-621, :684-685); the key — the dedupe entry's entire identity — unasserted. Wrong key = dedupe silently off. |
| 11 | `mark_processed` log mutations (warning/debug payloads, `[:17]` slice) | 16 | `_4, _5, _25, +13` | EQUIVALENT | hash-failure warning + debug-mark lines; return paths unchanged. |
| 12 | `is_duplicate_and_mark`: delegation drops the precomputed hash (`is_duplicate(fp, None)` / `(fp,)`, `mark_processed(fp, None)` / `(fp,)`) | 4 | `_18, _20, _23, _25` | **TEST-GAP** | dropped hash gets **recomputed** inside callee → output invisible, but atomic path silently re-reads/re-hashes. Existing test :714-742 asserts stored *value*, never the *key*/hash args. Killed by drafted test 4 (spy delegation). |
| 13 | `is_duplicate_and_mark`: `is_duplicate(None, file_hash)` (file_path arg) | 1 | `_17` | EQUIVALENT | hash is precomputed here, so file_path only feeds callee logging. (Note: under the hash-failure flow `Path(None)` would raise TypeError — unreachable in this function since its hash can't be failure-but-None.) |
| 14 | `is_duplicate_and_mark` log mutations | 9 | `_3, _4, _6` | EQUIVALENT | |
| 15 | `is_duplicate` log mutations (hash-failure warning extra, debug fail-open line) | 10 | `_4, _5, _7` | EQUIVALENT | |
| 16 | `clear_hash`: computed key dropped / `delete(None)` | 3 | `_3, _4, _6` | **TEST-GAP** | `delete.assert_awaited_once()` (:793) no args; "not found" test stubs delete→0 so a None-key still "passes". |
| 17 | `clear_hash` log mutation | 1 | `_9` | EQUIVALENT | |
| 18 | `ensure_key_has_ttl`: key dropped (`key=None` / `(None)` / `ttl(None)` / `expire(None, ttl)`) | 4 | `_5, _6, _9, _13` | **TEST-GAP** | existing test asserts `call_args[0][1] == 600` (the TTL) but never `call_args[0][0]` (the key) — test_dedupe.py:1045-1046. Orphaned real key keeps no TTL. |
| 19 | `ensure_key_has_ttl` log mutations | 2 | `_17, _19` | EQUIVALENT | |
| 20 | `cleanup_orphaned_keys`: `ttl(key)` → `ttl(None)` | 1 | `_15` | **TEST-GAP** | the per-key `ttl` call arg is unasserted (:985 asserts only `expire`). Killed by drafted test 5. |
| 21 | `cleanup_orphaned_keys` log mutations (debug/warning/error payloads, exc_info) | 15 | `_26, _27, _37, +12` | EQUIVALENT | |
| 22 | `cleanup_orphaned_keys`: info-log guard `cleaned_count > 0` → `>= 0` / `> 1` | 2 | `_29, _30` | EQUIVALENT | guard wraps only the summary log; return value untouched. |
| 23 | `cleanup_orphaned_keys`: `scan_iter(match=pattern, count=100)` hint mutations (pattern None, `count=None/101`, kwargs removed) | 6 | `_8, _9, _10` | LOW-VALUE | real Redis scans differently, but count is a hint and the existing tests replace `scan_iter` with a custom generator (:863-867) so args are invisible; a 2-line spy assert could kill if the gap list has room. |

**Classification totals:** EQUIVALENT 95 + TEST-GAP 19 + LOW-VALUE 6 = **120** ✓
(TEST-GAP keys: `_check_redis` 2,3,5,8; `mark_processed` 17,18,19; `is_duplicate_and_mark` 18,20,23,25; `clear_hash` 3,4,6; `ensure_key_has_ttl` 5,6,9,13; `cleanup_orphaned_keys` 15)

## Drafted tests — 6 highest-value TEST-GAP clusters (UNVERIFIED — not yet run red/green)

Style follows the existing file exactly: fixtures `mock_redis_client` / `temp_file` / autouse `reset_singleton`, `patch("backend.services.dedupe.get_settings", autospec=True)` with `MagicMock(spec=[])`, `@pytest.mark.asyncio`. **TDD procedure (same for all):** check out the mutant variant for the cluster → run the new test → assertion FAILS; on original `backend/services/dedupe.py` → PASSES.

### 1. `test_check_redis_queries_correct_dedupe_key_and_repairs_orphan_ttl` — kills clusters 6, 7, 8 (append to `TestCheckRedis` @ :546)

```python
    @pytest.mark.asyncio
    async def test_check_redis_queries_correct_dedupe_key_and_repairs_orphan_ttl(
        self, mock_redis_client: AsyncMock
    ) -> None:
        """_check_redis must query exists() with the exact dedupe:{hash} key and,
        when the found key has no TTL, repair it via expire() on that exact key.

        Kills mutants that compute the key then pass None to exists()/
        ensure_key_has_ttl (check_redis _2/_3/_5/_8).
        """
        mock_redis_client.exists.return_value = 1
        mock_redis_client._client.ttl = AsyncMock(return_value=-1)  # orphan -> triggers expire
        mock_redis_client._client.expire = AsyncMock(return_value=True)

        with patch("backend.services.dedupe.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            result = await service._check_redis("abc123")

            expected_key = f"{DEDUPE_KEY_PREFIX}abc123"
            assert result is True
            mock_redis_client.exists.assert_awaited_with(expected_key)
            mock_redis_client._client.ttl.assert_awaited_with(expected_key)
            mock_redis_client._client.expire.assert_awaited_once_with(
                expected_key, DEFAULT_DEDUPE_TTL_SECONDS
            )
```

Red: `exists(None)` / `ttl("dedupe:None")` / `expire("dedupe:None", …)` → fail. Green on original.

### 2. `test_clear_hash_deletes_exact_dedupe_key` — kills cluster 16 (append to `TestClearHash` @ :779)

```python
    @pytest.mark.asyncio
    async def test_clear_hash_deletes_exact_dedupe_key(self, mock_redis_client: AsyncMock) -> None:
        """clear_hash must delete the exact dedupe:{hash} key, not None.

        Kills clear_hash _3/_4/_6 (key = None / _get_redis_key(None) / delete(None)).
        """
        mock_redis_client.delete.return_value = 1

        with patch("backend.services.dedupe.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            result = await service.clear_hash("abc123")

            assert result is True
            mock_redis_client.delete.assert_awaited_with(f"{DEDUPE_KEY_PREFIX}abc123")
```

### 3. `test_ensure_key_has_ttl_sets_expire_on_exact_key` — kills cluster 18 (append to `TestEnsureKeyHasTtl` @ :995)

```python
    @pytest.mark.asyncio
    async def test_ensure_key_has_ttl_sets_expire_on_exact_key(
        self, mock_redis_client: AsyncMock
    ) -> None:
        """ensure_key_has_ttl must call ttl()/expire() with the exact dedupe:{hash} key.

        Existing test checks only expire's TTL arg ([0][1]); the KEY arg was
        unasserted (ensure_key_has_ttl _5/_6/_9/_13).
        """
        mock_redis_client._client.ttl = AsyncMock(return_value=-1)
        mock_redis_client._client.expire = AsyncMock(return_value=True)

        with patch("backend.services.dedupe.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            result = await service.ensure_key_has_ttl("abc123")

            expected_key = f"{DEDUPE_KEY_PREFIX}abc123"
            assert result is True
            mock_redis_client._client.ttl.assert_awaited_with(expected_key)
            mock_redis_client._client.expire.assert_awaited_once_with(
                expected_key, DEFAULT_DEDUPE_TTL_SECONDS
            )
```

### 4. `test_is_duplicate_and_mark_delegates_precomputed_hash` — kills cluster 12 (append to `TestIsDuplicateAndMark` @ :693)

```python
    @pytest.mark.asyncio
    async def test_is_duplicate_and_mark_delegates_precomputed_hash(
        self, mock_redis_client: AsyncMock, temp_file: str
    ) -> None:
        """is_duplicate_and_mark must pass the precomputed hash to BOTH
        is_duplicate() and mark_processed() — not None, not omitted.

        Kills idm _18/_20/_23/_25: dropped hashes get silently RECOMPUTED
        inside the callees, so return values hide the bug while the atomic
        path re-reads and re-hashes the file (losing atomicity guarantees).
        """
        mock_redis_client.exists.return_value = 0

        with patch("backend.services.dedupe.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)

            expected_hash = hashlib.sha256(b"test content for hashing").hexdigest()
            with patch.object(
                service, "is_duplicate", wraps=service.is_duplicate
            ) as spy_dup, patch.object(
                service, "mark_processed", wraps=service.mark_processed
            ) as spy_mark:
                is_dup, file_hash = await service.is_duplicate_and_mark(temp_file)

            assert is_dup is False
            assert file_hash == expected_hash
            spy_dup.assert_awaited_once_with(temp_file, expected_hash)
            spy_mark.assert_awaited_once_with(temp_file, expected_hash)
```

### 5. `test_cleanup_orphaned_keys_checks_ttl_on_exact_key` — kills cluster 20 (append to `TestCleanupOrphanedKeys` @ :835)

```python
    @pytest.mark.asyncio
    async def test_cleanup_orphaned_keys_checks_ttl_on_exact_key(
        self, mock_redis_client: AsyncMock
    ) -> None:
        """cleanup_orphaned_keys must check ttl() on each scanned key itself.

        Kills cleanup_orphaned_keys _15 (ttl(None)); existing tests assert only
        the expire() args, so the ttl() target key was unasserted.
        """

        async def mock_scan_iter(*args: Any, **kwargs: Any) -> Any:
            yield "dedupe:hash1"

        mock_redis_client._client.scan_iter = mock_scan_iter
        mock_redis_client._client.ttl = AsyncMock(return_value=-1)
        mock_redis_client._client.expire = AsyncMock(return_value=True)

        with patch("backend.services.dedupe.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            count = await service.cleanup_orphaned_keys()

            assert count == 1
            mock_redis_client._client.ttl.assert_awaited_with("dedupe:hash1")
```

### 6. `test_mark_processed_stores_under_exact_dedupe_key` — kills cluster 10 (append to `TestMarkProcessed` @ :604)

```python
    @pytest.mark.asyncio
    async def test_mark_processed_stores_under_exact_dedupe_key(
        self, mock_redis_client: AsyncMock, temp_file: str
    ) -> None:
        """mark_processed must store the marker under the exact dedupe:{hash} key.

        Existing tests assert only set()'s expire kwarg; the KEY argument —
        the entire identity of the dedupe entry — was unasserted (mp _17/_18/_19).
        """
        with patch("backend.services.dedupe.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            result = await service.mark_processed(temp_file, "abc123")

            call_args = mock_redis_client.set.call_args
            assert call_args is not None
            assert call_args[0][0] == f"{DEDUPE_KEY_PREFIX}abc123"
            assert call_args[0][1] == temp_file  # value = file_path, for debugging
            assert result is True
```

## Notes for the fix lane

1. **Do not chase clusters 1-5, 9, 11, 13-15, 17, 19, 21-22** — log-text/`exc_info`/chunk-size mutants; killing them would mean asserting structlog record contents, which this codebase deliberately never does.
2. **Cluster 23** (scan hints) if wanted: capture `**kwargs` in `test_cleanup_orphans_finds_orphaned_keys`'s `mock_scan_iter` and assert `kwargs["match"] == f"{DEDUPE_KEY_PREFIX}*"` and `kwargs["count"] == 100` — 2 lines.
3. `cleanup_orphaned_keys` behavioral core (`ttl == -1` branch, `expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)`) is already pinned (:985) — hence none of its ttl-value/expire-value mutants survived; only its ttl-target mutant did.
4. The existing `test_is_duplicate_and_mark_passes_file_path_to_mark_processed` (:714) proves this file's mock style accepts call-arg assertions — the drafted tests extend exactly that pattern from the *value* to the *key*.
