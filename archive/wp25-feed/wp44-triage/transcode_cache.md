# WP4.4 Triage Dossier — backend/services/transcode_cache.py

- **Module:** `backend/services/transcode_cache.py`
- **Survivors:** 77 of 253 keys (exit_code_by_key == 0; 0 nulls — module fully checked)
- **Covering test file (all clusters):** `backend/tests/unit/services/test_transcode_cache.py` (828 lines; fixtures `temp_dir`, `mock_config` @L37, `disabled_config` @L51, `source_video` @L72, `transcoded_video` @L81)
- **Diff source:** `uv run mutmut show <key>` (worked for all 77 keys; no fallback needed)
- **Key prefix:** all keys are `backend.services.transcode_cache.xǁTranscodeCacheǁ<method>__mutmut_<N>`; shortened below.

**Cluster totals: TEST-GAP 39 + LOW-VALUE 9 + EQUIVALENT 29 = 77 (sums to survivors_total exactly).**

## Per-cluster table

| # | Pattern (cluster) | Count | Keys (≤3 examples) | Src line(s) | Classification | Why / test gap |
|---|---|---|---|---|---|---|
| C1 | `__init__` metadata filename string tweaks (`"metadata.json"` → `"XX..XX"`/`"METADATA.JSON"`) | 2 | `__init___8`, `__init___9` | :98 | LOW-VALUE | Real filename change, but no caller asserts the metadata filename; persistence round-trip (test:543) works under any consistent name — would only surface cross-instance |
| C2 | `_get_cache_key` missing-file sentinel `mtime = 0` → `None`/`1` | 2 | `_get_cache_key__2`, `_get_cache_key__3` | :145 | TEST-GAP | `test_get_cache_key_handles_missing_file` (:170) only asserts len==16; comment says "with mtime=0" but never pins the value → key for an OSError source shifts under mutant |
| C3 | `initialize` `mkdir` kwargs dropped/`parents` True→False/None | 3 | `initialize__2`, `initialize__5`, `initialize__7` | :119 | TEST-GAP | `test_cache_initialize_creates_directory` (:117) makes only ONE missing level → parents flag unobservable; nested cache_dir never tested |
| C4 | `get` `_misses += 1` → `= 1`/`-= 1`/`+= 2` at 5 miss sites | 5 | `get__6`, `get__22`, `get__24` (+29, 23) | :164,:175,:186,:195 | TEST-GAP | Every miss test asserts `_misses == 1` on the FIRST miss only (`=1` and `+=2`/first-site `-=1` indistinguishable at 1); no cumulative-miss test |
| C5 | `get` hit counter `self._hits += 1` → `= 1` | 1 | `get__33` | :204 | TEST-GAP | `test_cache_get_returns_cached_path_on_hit` (:220) asserts `_hits == 1` after one hit; no multi-hit accumulation test |
| C6 | `get` hit path `entry.last_accessed = time.time()` → `None` | 1 | `get__32` | :201 | TEST-GAP | No test asserts `last_accessed` is updated on hit — this is THE LRU-recency-refresh behavior; mutant also poisons on-disk metadata (breaks reload) |
| C7 | `get` mtime-invalidation `self._remove_entry(cache_key)` → `_remove_entry(None)` | 1 | `get__28` | :194 | TEST-GAP | `test_cache_get_invalidates_on_source_change` (:244-247) asserts only `result is None` + `_misses == 1` — never that stale entry/files were actually deleted |
| C8 | `put` `CacheEntry(cached_at=time.time(), ...)` → `cached_at=None` | 1 | `put__26` | :257 | TEST-GAP | No put test asserts `cached_at` is a real timestamp; metadata written with null → reload TypeError silently swallowed by `_load_metadata` (:361 catch) |
| C9 | `get_stats` guard `hit_rate = ... if total_requests > 0 else 0.0` → `> 1` | 1 | `get_stats__18` | :394 | TEST-GAP | With exactly 1 request (`hits=1,misses=0`): original hit_rate 1.0, mutant 0.0 — untested boundary |
| C10 | `_maybe_cleanup` threshold `stats.total_size_gb > threshold_gb` → `>=` | 1 | `_maybe_cleanup__4` | :279 | TEST-GAP | Both cleanup tests use 0.95 and 0.5 vs 0.9 — never exactly AT threshold (0.9): original skips, mutant triggers |
| C11 | `cleanup` LRU sort `key=lambda x: x[1].last_accessed` removed / `key=None` | 2 | `cleanup__3`, `cleanup__5` | :299 | TEST-GAP | `test_cache_cleanup_removes_lru_entries` (:332) writes 400 MB×3 real files = **1.2 GB on disk** (sparsely-allocated; `sum(size_bytes)` = 1.2 GB > target even after ONE deletion) and asserts only `removed >= 1` → eviction ORDER never asserted. `key=None` even crashes sort in py3 |
| C12 | `cleanup` target-size arithmetic (`*1024`↔`/1024`, `1024`→`1025`) | 6 | `cleanup__12`, `cleanup__13`, `cleanup__14` (+16,17,18) | :303-310 | TEST-GAP | Tests only ever assert `removed >= 1`; no test pins the exact eviction count for a known size/target. `1025` variants are ~0.1% real drift |
| C13 | `cleanup` loop guard `if current_size <= target: break` → `<` | 1 | `cleanup__21` | :313 | TEST-GAP | Untested boundary: when size lands EXACTLY on target, original stops, mutant deletes one more entry |
| C14 | `cleanup` running total `current_size -= e.size` → `= e.size` / `+= e.size` | 2 | `cleanup__29`, `cleanup__30` | :322 | TEST-GAP | Same root gap as C12/C13 — no exact-count/kept-set assertion; `+=` deletes everything, `=` deletes until bogus total ≤ target |
| C15 | `cleanup` counter `removed` init/increment (`=0→1`, `+=1→=1`, `+=1→+=2`) | 3 | `cleanup__20`, `cleanup__31`, `cleanup__33` | :311,:324 | TEST-GAP | `cleanup()`'s return value is the documented contract ("Returns: number removed") but only `>= 1` was ever checked; `removed=1` init also kills C16's guard (always-saves) |
| C16 | `cleanup` `if removed > 0:` → `>= 0` / `> 1` | 2 | `cleanup__34`, `cleanup__35` | :326 | LOW-VALUE | `>=0`: empty-cache cleanup would pointlessly re-save metadata (benign); `>1`: cleanup of exactly one entry skips the save → persisted metadata stale. Real but marginal — absorbed by C12/C15 kill-tests as a side-effect |
| C17 | `unlink(missing_ok=True)` → `None`/dropped/`False` on removal paths (`cleanup` ×3, `_remove_entry` ×3, `clear` ×3) | 9 | `cleanup__24`, `_remove_entry__4`, `clear__2` (+6,8,26,28,4,6) | :318,:341,:413 | TEST-GAP | NOT equivalent: `missing_ok=None` == False → unlinking an already-deleted cached file raises `FileNotFoundError`. Tests cover only the file-present happy path; the missing-file invalidation/cleanup path is exactly the resilience contract |
| C18 | `initialize`/`cleanup` `logger.info(f-string)` → `None` (format-arg swap only) | 2 | `initialize__11`, `cleanup__36` | :121,:328 | EQUIVALENT | f-string evaluated before the call → `logger.info(None)` runs identically (module uses no log-capture assertions anywhere) |
| C19 | `_load_metadata` `logger.warning(f"Failed to load cache metadata: {e}")` → `None` | 1 | `_load_metadata__7` | :361 | EQUIVALENT | same f-string pre-evaluation argument |
| C20 | `_maybe_cleanup` `logger.info(f-string)` → `None` | 1 | `_maybe_cleanup__5` | :280-282 | EQUIVALENT | same argument |
| C21 | `invalidate` `logger.info(f-string)` → `None` | 1 | `invalidate__5` | :437 | EQUIVALENT | same argument |
| C22 | `get` debug/info/warning log text or `None` (6 call sites) | 8 | `get__2`, `get__17`, `get__21` (+3,4,5,27,36) | :163,:176,:183,:193,:205 | EQUIVALENT | pure log text (case/XX/None variants), no assertion on messages |
| C23 | `clear` log text variants + `None` | 4 | `clear__8`, `clear__9`, `clear__10` (+11) | :419 | EQUIVALENT | pure log text |
| C24 | `put` disabled-path log text variants + `None` | 4 | `put__2`, `put__3`, `put__4` (+5) | :228 | EQUIVALENT | pure log text |
| C25 | `put` log-only `size_mb` arithmetic (`size_mb` is ONLY consumed by the info log) + info `None` | 5 | `put__41`, `put__42`, `put__43` (+44,45) | :266-267 | EQUIVALENT | `size_mb` feeds nothing else; log text never asserted |
| C26 | `get_stats` display precision: `/3600→3601`, `/1024→1025` (GB), `hit_rate` divisor | 4 | `get_stats__10`, `get_stats__37`, `get_stats__38` (+39) | :391,:399 | LOW-VALUE | 0.03-0.1% drift in reported-only fields; existing assertion `pytest.approx(rel=0.01)` (:443,444) deliberately tolerates it; nobody should assert to 5 digits on a display stat |
| C27 | `_save_metadata` `json.dump(..., indent=2)` → `None`/dropped/`3` | 3 | `_save_metadata__15`, `_save_metadata__18`, `_save_metadata__19` | :373 | EQUIVALENT | JSON semantics identical; reload passes; indent is formatting only |
| C28 | `_save_metadata` atomic-temp suffix `".tmp"` → `".TMP"` | 1 | `_save_metadata__6` | :370 | LOW-VALUE | rename still atomic, round-trip fine; only a concurrent crash could orphan a `.TMP` nobody cleans — nobody should assert the temp filename |

## Highest-value TEST-GAP clusters selected for drafted tests

P1→C11/C12/C13/C14/C15/C16 (cleanup exact-contract, 15 mutants), P2→C4/C5 (counter accumulation, 6), P3→C17 (missing-file resilience on removal paths, 9), P4→C7/C6 (source-change invalidation actually removes + hit refreshes recency, 2), P5→C2 (missing-file key sentinel, 2), P6→C9/C10 (hit_rate and cleanup-threshold exact boundaries, 2). Total drafted-test reach: 35 mutants directly (P1=14, P2=6, P3=9, P4=2, P5=2, P6=2) + 2 C16 mutants killed as a side-effect of P1's reload-save assert.

## Drafted tests

Style follows the existing file (`@pytest.mark.asyncio`, fixtures `cache`/`mock_config`/`temp_dir`/`source_video`/`transcoded_video`, tiny synthetic files instead of the existing test's 1.2 GB allocations). Append to `backend/tests/unit/services/test_transcode_cache.py`.

```python
# =============================================================================
# WP4.4 kill-tests for surviving transcode_cache mutants (UNVERIFIED)
# =============================================================================


# // UNVERIFIED - not yet run red/green
# P1 — kills C11 (key=None / key dropped), C12 (target arithmetic), C13 (`<=`→`<`),
#      C14 (current_size op), C15 (removed counter), C16 (save guard >0), C1 part 2.
# TDD: every mutation above changes the exact set of evicted keys or the return
# count → the exact equality asserts fail on mutant, pass on original.
@pytest.mark.asyncio
async def test_cleanup_evicts_exactly_oldest_entries_to_target(mock_config):
    """Cleanup must evict LRU-first and stop exactly at the byte target."""
    # 1 MB cap, evict down to 0.5 MB, trigger at 90%
    mock_config.max_cache_size_gb = 1e-6          # 1 MB
    mock_config.cleanup_threshold_percent = 0.9
    mock_config.cleanup_target_percent = 0.5      # target = 524288 bytes exactly
    cache = TranscodeCache(config=mock_config)
    await cache.initialize()

    now = time.time()
    for idx, age in enumerate([300, 200, 100]):   # entry0 is least recently used
        cached = cache.cache_dir / f"e{idx}.mp4"
        cached.write_bytes(b"x" * 200_000)
        cache._metadata[f"key{idx}"] = CacheEntry(
            source_path=f"/vid/{idx}.mp4",
            source_mtime=1.0,
            cached_path=str(cached),
            cached_at=now,
            last_accessed=now - age,
            size_bytes=200_000,
        )

    removed = await cache.cleanup()

    assert removed == 1                    # kills C15 (=1, +=2) and C12/C14 (wrong target → 0 or 2+)
    assert "key0" not in cache._metadata   # kills C11: sort key dropped/None → order wrong or TypeError
    assert set(cache._metadata) == {"key1", "key2"}
    assert not (cache.cache_dir / "e0.mp4").exists()
    assert (cache.cache_dir / "e1.mp4").exists() and (cache.cache_dir / "e2.mp4").exists()
    stats = await cache.get_stats()
    assert stats.total_size_bytes == 400_000  # stops at <= target, never below (kills C13 `<`)

    # metadata on disk must match in-memory after eviction (kills C16 `>1`: save skipped at removed==1)
    reloaded = TranscodeCache(config=mock_config)
    await reloaded._load_metadata()
    assert set(reloaded._metadata) == set(cache._metadata)


# // UNVERIFIED - not yet run red/green
# P2 — kills C4 (`_misses += 1` → `=1`, `-=1`, `+=2` at all 4 miss sites, 5 keys)
#      and C5 (`_hits += 1` → `=1`, 1 key).
# TDD: counts 3 misses / 2 hits across DIFFERENT miss sites — any `=1` assignment,
# `-=1` flip or `+=2` bump breaks the exact totals; single-miss tests cannot see it.
@pytest.mark.asyncio
async def test_get_accumulates_hit_and_miss_counters_across_paths(cache, source_video, temp_dir):
    """_hits/_misses must increment by one on every hit/miss, across every miss path."""
    await cache.initialize()

    # site A: cache disabled (line 164)
    disabled = TranscodeCache(config=TranscodeCacheSettings(cache_dir=temp_dir, enabled=False))
    await disabled.get(source_video)
    assert disabled._misses == 1

    # site B: not found (line 175)
    missing = Path(temp_dir) / "never_seen.mp4"
    missing.write_bytes(b"x")
    await cache.get(missing)
    assert cache._misses == 1

    # site C: entry present but cached file gone (line 186)
    key_gone = cache._get_cache_key(source_video)
    cache._metadata[key_gone] = CacheEntry(
        source_path=str(source_video),
        source_mtime=source_video.stat().st_mtime,
        cached_path=str(cache.cache_dir / "ghost.mp4"),
        cached_at=time.time(),
        last_accessed=time.time(),
        size_bytes=10,
    )
    assert await cache.get(source_video) is None
    assert cache._misses == 2  # kills `=1` (resets to 1) and `+=2` (4) and `-=1` (0)

    # sites D + E: stale mtime (line 195), then two hits (line 204)
    stale_key = cache._get_cache_key(source_video)
    cached = cache.cache_dir / f"{stale_key}.mp4"
    cached.write_bytes(b"transcode")
    cache._metadata[stale_key] = CacheEntry(
        source_path=str(source_video),
        source_mtime=source_video.stat().st_mtime - 100,
        cached_path=str(cached),
        cached_at=time.time(),
        last_accessed=time.time(),
        size_bytes=cached.stat().st_size,
    )
    assert await cache.get(source_video) is None
    assert cache._misses == 3

    cache._metadata[stale_key] = CacheEntry(
        source_path=str(source_video),
        source_mtime=source_video.stat().st_mtime,
        cached_path=str(cached),
        cached_at=time.time(),
        last_accessed=time.time(),
        size_bytes=cached.stat().st_size,
    )
    assert await cache.get(source_video) == cached
    assert await cache.get(source_video) == cached
    assert cache._hits == 2    # kills C5 `=1`
    assert cache._misses == 3


# // UNVERIFIED - not yet run red/green
# P3 — kills C17 (unlink missing_ok True→None/False/dropped, 9 keys across
#      _remove_entry / cleanup / clear).
# TDD: removal paths must tolerate an already-deleted cached file; missing_ok
# mutants raise FileNotFoundError (or TypeError for None) instead of proceeding.
@pytest.mark.asyncio
async def test_removal_paths_tolerate_already_deleted_files(cache, source_video, temp_dir):
    """invalidate / get-stale / clear must not raise when the cached file is gone."""
    await cache.initialize()

    key = cache._get_cache_key(source_video)
    ghost = cache.cache_dir / f"{key}.mp4"  # never created: file is already missing
    cache._metadata[key] = CacheEntry(
        source_path=str(source_video),
        source_mtime=source_video.stat().st_mtime,
        cached_path=str(ghost),
        cached_at=time.time(),
        last_accessed=time.time(),
        size_bytes=7,
    )

    assert await cache.invalidate(source_video) is True   # _remove_entry: :341
    assert key not in cache._metadata

    stale_key = cache._get_cache_key(source_video)
    cache._metadata[stale_key] = CacheEntry(
        source_path=str(source_video),
        source_mtime=source_video.stat().st_mtime - 100,  # forces get → _remove_entry
        cached_path=str(cache.cache_dir / "ghost2.mp4"),
        cached_at=time.time(),
        last_accessed=time.time(),
        size_bytes=3,
    )
    assert await cache.get(source_video) is None          # get stale path → :341

    other = Path(temp_dir) / "src2.mp4"
    other.write_bytes(b"y")
    okey = cache._get_cache_key(other)
    cache._metadata[okey] = CacheEntry(
        source_path=str(other),
        source_mtime=other.stat().st_mtime,
        cached_path=str(cache.cache_dir / "ghost3.mp4"),
        cached_at=time.time(),
        last_accessed=time.time(),
        size_bytes=1,
    )
    await cache.clear()                                    # clear loop: :413
    assert cache._metadata == {}


# // UNVERIFIED - not yet run red/green
# P4 — kills C7 (`_remove_entry(cache_key)` → `_remove_entry(None)` in get's
#      mtime-stale branch, :194) and C6 (`entry.last_accessed = time.time()` →
#      None on hit, :201).
# TDD: original removes the stale entry + its file and refreshes last_accessed
# on hit; mutants leave the stale entry live (next get wrongly HITs) / wipe recency.
@pytest.mark.asyncio
async def test_source_change_invalidation_removes_entry_and_hit_refreshes_recency(
    cache, source_video
):
    """A stale-mtime hit must delete the entry; a valid hit must refresh recency."""
    await cache.initialize()

    key = cache._get_cache_key(source_video)
    cached = cache.cache_dir / f"{key}.mp4"
    cached.write_bytes(b"transcode")
    entry = CacheEntry(
        source_path=str(source_video),
        source_mtime=source_video.stat().st_mtime - 100,
        cached_path=str(cached),
        cached_at=time.time() - 500,
        last_accessed=time.time() - 500,
        size_bytes=cached.stat().st_size,
    )
    cache._metadata[key] = entry

    assert await cache.get(source_video) is None
    assert key not in cache._metadata              # kills C7: `_remove_entry(None)` is a no-op
    assert not cached.exists()                     # stale cached file was unlinked too

    # Re-register with current mtime (entry absent again after invalidation)
    cache._metadata[key] = CacheEntry(
        source_path=str(source_video),
        source_mtime=source_video.stat().st_mtime,
        cached_path=str(cached),                   # file gone post-invalidation; recreate
        cached_at=time.time(),
        last_accessed=time.time() - 100,
        size_bytes=0,
    )
    cached.write_bytes(b"transcode")
    before = time.time()
    assert await cache.get(source_video) == cached
    assert cache._metadata[key].last_accessed >= before  # kills C6: `= None`


# // UNVERIFIED - not yet run red/green
# P5 — kills C2 (`mtime = 0` → `None`/`1` in _get_cache_key OSError branch, :145).
# TDD: original key = sha256(f"{path}:0")[:16]; mutants hash ":None"/":1" → differ.
def test_get_cache_key_missing_file_uses_zero_mtime_sentinel(cache, temp_dir):
    """The OSError fallback must be exactly mtime=0, pinning the key for absent sources."""
    import hashlib

    missing = Path(temp_dir) / "gone" / "video.mp4"
    key = cache._get_cache_key(missing)
    expected = hashlib.sha256(f"{missing}:0".encode()).hexdigest()[:16]
    assert key == expected


# // UNVERIFIED - not yet run red/green
# P6 — kills C9 (`total_requests > 0` → `> 1` hit_rate guard, :394) and
#      C10 (`>` → `>=` cleanup threshold, :279).
# TDD: exact boundaries — 1 request with 1 hit must give hit_rate 1.0, and a size
# exactly AT threshold must NOT trigger cleanup (>= would).
@pytest.mark.asyncio
async def test_get_stats_hit_rate_single_request_and_cleanup_threshold_boundary(cache):
    """hit_rate at exactly one request; cleanup not triggered exactly at threshold."""
    await cache.initialize()

    cache._hits = 1
    cache._misses = 0
    stats = await cache.get_stats()
    assert stats.hit_rate == 1.0  # kills C9: `>1` guard returns 0.0 here

    exact = CacheStats(
        total_entries=1,
        total_size_bytes=900_000_000,
        total_size_gb=0.9,  # == max_cache_size_gb(1.0) * 0.9 threshold exactly
        oldest_entry_age_hours=1.0,
        hit_rate=1.0,
        hits=1,
        misses=0,
    )
    with patch.object(cache, "get_stats", new_callable=AsyncMock, return_value=exact):
        with patch.object(cache, "cleanup", new_callable=AsyncMock) as mock_cleanup:
            await cache._maybe_cleanup()
    mock_cleanup.assert_not_called()  # kills C10: `>=` would call cleanup()
```

## Notes / caveats

- **C18-C21 `logger.*(f-string)` → `None` equivalence argument:** the f-string argument is fully evaluated at the call site before `logger` sees it, so the mutated call executes the same f-string then passes `None` as the msg. Identical control flow, no formatting error. If the repo's logging layer were ever to assert on message content (it currently does not), these would flip to LOW-VALUE, not TEST-GAP.
- **C17 classification correction:** initially looked equivalent (`missing_ok=None` is falsy == `False` == dropped kwarg, all four spellings one behavior); it is a real behavioral change on the *missing-file* branch (raises). Reclassified TEST-GAP and covered by P3. This is why C17 shows TEST-GAP in the totals despite being a "kwarg tweak" pattern.
- **C12's `*1024→/1024` (cleanup__12/13/14) shrink target to KB-scale** → cleanup would evict nearly everything on any real cache; the `1024→1025` variants are genuine low-drift twins kept in the same cluster (killed by the exact-count test at 0.03% margin — the P1 test's byte target is exact integer arithmetic, so `1025` variants fail `removed == 1` deterministically).
- **Why the existing cleanup test hid 15 mutants:** `test_cache_cleanup_removes_lru_entries` (:332) allocates 3×400 MB real files and asserts `removed >= 1`; since any single deletion drops 400 MB and target is 800 MB, essentially every wrong sort/target/count behavior still yields "≥1 removed". The P1 rewrite uses tiny files + exact ints and asserts the *set* kept.
- All 77 diffs captured verbatim at `/tmp/wp25/wp44-triage/all_diffs.txt`; survivor key list at `/tmp/wp25/wp44-triage/surv_keys.txt`.
