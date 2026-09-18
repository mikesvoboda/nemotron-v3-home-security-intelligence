# WP4.4 Triage Dossier — backend/services/redis_memory_service.py

- Source: `backend/services/redis_memory_service.py` (379 lines)
- Meta: `mutants/backend/services/redis_memory_service.py.meta` — 326 keys, **113 survived** (exit_code 0)
- Diffs collected via `uv run mutmut show <key>` (113/113 clean, no fallback needed); raw dumps in `/tmp/wp25/wp44-triage/diffs/`
- Sole covering test file (from `mutants/mutmut-stats.json` `tests_by_mangled_function_name`, all 5 mutated functions):
  **`backend/tests/unit/services/test_redis_memory_service.py`** — async unit tests, `AsyncMock` redis client fixture (`mock_redis_client` L22-40), service fixture (`memory_service` L53-62).

## Why so many survive — root causes in the test file

1. **Stub-shaped mocks.** `mock_client.info` is a single `return_value`/positional `side_effect` list, so the _section argument_ (`info("memory")` vs `info("XXmemoryXX")`) is invisible; `config_get` returns a fixed dict so the _pattern argument_ is invisible; `memory_usage`/`scan_keys` are `return_value` stubs so _call arguments_ are never asserted.
2. **Missing fields never exercised.** Every fixture info-dict is fully populated, so every `.get(key, default)` default mutation survives.
3. **Unasserted dataclass fields.** `test_get_memory_stats` (L134-156) asserts only 5 of 13 `MemoryStats` fields — `used_memory_peak_bytes/mb`, `maxmemory_mb`, `memory_fragmentation_ratio`, `total_keys`, `keys_with_ttl`, `evicted_keys`, `memory_usage_percent` (unlimited case) are never checked; `used_memory_mb` uses `rel=0.1` tolerance that swallows ~0.1 % divisor mutants and the ×101 percent mutant (50.5 vs 50 passes `approx(50, rel=0.1)`).
4. **Weak substring asserts in recommendations.** Tests assert `any("critically high" in r.lower() or "elevated" in r.lower())` (L344) or count-only (`len >= 1` L536), so threshold off-by-ones, inclusive/exclusive flips, and even None-injection survive. No test asserts the volatile-TTL heuristic branch at all (it _runs_ in several tests with ttl_percent=0 — unasserted).
5. **Boundary-only mutants** (`>90→>=90`, `>1.5→>=1.5`, `>0→>1`): fixtures sit far from boundaries (2.0 frag, 92 %, 500 evicted).

## Cluster table (sums to 113)

Legend: GMS = `RedisMemoryService.get_memory_stats`, GEC = `get_current_config`, FLK = `find_large_keys`, GKM = `get_key_memory_usage`, GMR = `get_memory_recommendations`. Example keys abbreviated `<fn>__mutmut_N`; full keys are `backend.services.redis_memory_service.xǁRedisMemoryServiceǁ<fn>__mutmut_N`.

| #   | Pattern (function / source line)                                                                                                                                 | Count | Class      | Example keys             | Notes / weak-assert location                                                                                                                                                                                                          |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----- | ---------- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `info()` section arg → None/garbage/uppercase (GMS L158-160: "memory","stats","keyspace" × 3 variants)                                                           | 9     | TEST-GAP   | GMS_2, GMS_3, GMS_10     | `test_get_memory_stats` test_redis_memory_service.py:134 — side_effect list ignores section args; real Redis: wrong section → used_memory missing → defaults                                                                          |
| 2   | `config_get()` pattern arg → None/garbage/uppercase (GEC L212-213 + GMS L169)                                                                                    | 9     | TEST-GAP   | GEC_2, GEC_6, GMS_46     | :203, :146 — pattern never asserted; real Redis CONFIG GET is pattern-sensitive → empty dict → silent "noeviction"/0                                                                                                                  |
| 3   | `scan_keys()` call args mutated: `pattern=None`/dropped, `max_keys=None`/dropped, `max_keys*10 → /10, *11` (FLK L246)                                            | 6     | TEST-GAP   | FLK_3, FLK_4, FLK_7      | :236-248 — scan_keys fully stubbed; pattern=None ignores caller's glob filter on a real server                                                                                                                                        |
| 4   | `memory_usage(key)` → `memory_usage(None)` (GKM L279 + FLK L250)                                                                                                 | 2     | TEST-GAP   | GKM_1, FLK_10            | :290-306 — return_value stub; returned value asserted, key argument never. One-line `assert_awaited_once_with` kills both                                                                                                             |
| 5   | `info.get("used_memory_peak", 0)` key/default mutated → peak always defaults to 0/None/1 (GMS L164)                                                              | 6     | TEST-GAP   | GMS_22, GMS_26, GMS_27   | peak_bytes/peak_mb asserted nowhere; key-mutation variants (22/26/27) return 0 for ALL inputs — die to a strict peak assert on the existing fixture                                                                                   |
| 6   | Missing-key `.get()` default mutations on INFO/config dicts: default 0→None/dropped/1, 1.0→2.0 (GMS used_memory/maxmemory/frag/evicted L163-183 + GEC L215)      | 13    | TEST-GAP   | GMS_15, GMS_31, GMS_76   | No fixture omits a field anywhere in the file; None-defaults crash arithmetic (TypeError) — still "survived" only because fallback never runs. Also covers GEC_12/14/17                                                               |
| 7   | `config.get("maxmemory-policy", "noeviction")` fallback → None/dropped/"XXnoevictionXX"/"NOEVICTION" (GMS L170 + GEC L221)                                       | 8     | TEST-GAP   | GMS_51, GMS_56, GEC_36   | config_get mock always contains the key → fallback never exercised; real Redis: pattern miss → wrong policy reported                                                                                                                  |
| 8   | keys_with_ttl accumulation block: init 0→1, `+=`→`=`, expires default None/dropped/1 (GMS L177-180)                                                              | 5     | TEST-GAP   | GMS_60, GMS_65, GMS_68   | `stats.keys_with_ttl` is **never asserted in any test** though :144 fixture carries expires=3000; +=→= survives single-db fixtures (multi-db in T1 kills it)                                                                          |
| 8b  | keyspace guard `and`→`or` (GMS L179)                                                                                                                             | 1     | EQUIVALENT | GMS_61                   | `"expires" in db_info` is redundant with the `.get(...,0)` default, so for dict-valued keyspace (the only shape redis-py returns) both operands paths agree; divergence needs non-dict db_info (crash) — not a realistic client shape |
| 9   | used/peak bytes+MB field construction: divisor 1024→1025, `/`→`*`, `/ (1024/1024)`, swap→None (GMS L190-194)                                                     | 8     | TEST-GAP   | GMS_118, GMS_120, GMS_93 | `used_memory_mb == approx(50.0, rel=0.1)` at :153 swallows ~0.1 % divisor shifts; peak fields unasserted                                                                                                                              |
| 10  | maxmemory_mb expression: swap→None, guard `and False`, `/`→`*`, `/ (1024/1024)`, divisor tweaks, `else 0→1` (GMS L196)                                           | 7     | TEST-GAP   | GMS_95, GMS_124, GMS_132 | `maxmemory_mb` never asserted in stats tests (only string variant in get_current_config); `else 1` killed by strict 0.0 in unlimited case :160                                                                                        |
| 11  | KeyMemoryInfo construction: `key=None`, `memory_kb=None / *1024 / /1025` (FLK L253-257)                                                                          | 4     | TEST-GAP   | FLK_15, FLK_17, FLK_21   | :243-247 asserts memory_bytes only — never `.key` or `.memory_kb` of results                                                                                                                                                          |
| 12  | Recommendation usage thresholds off-by-one/inclusive: `>90 → >=90 / >91`, `>75 → >=75 / >76` (GMR L299, L304)                                                    | 4     | TEST-GAP   | GMR_8, GMR_9, GMR_11     | :344 asserts `"critically high" OR "elevated"` — can't tell which branch fired; no fixture near 90/75 boundaries                                                                                                                      |
| 13  | Volatile-TTL heuristic: `ttl_percent = keys/total` → `*`, `*100 → *101`, `<50 → <=50 / <51`, `startswith("volatile") → "XXvolatileXX"/"VOLATILE"` (GMR L333-334) | 6     | TEST-GAP   | GMR_31, GMR_34, GMR_37   | Branch RUNS unasserted in several tests (keyspace `{}` → ttl 0 %); VOLATILE-case flip suppresses a real recommendation on every real policy                                                                                           |
| 14  | `memory_usage_percent = (used/max)*100 → *101` (GMS L188)                                                                                                        | 1     | TEST-GAP   | GMS_89                   | :196 asserts `approx(50.0, rel=0.1)`; mutant yields 50.5 → inside tolerance. Exact-approx kill                                                                                                                                        |
| 15  | Fragmentation threshold `>1.5 → >=1.5` (GMR L318)                                                                                                                | 1     | TEST-GAP   | GMR_21                   | :368 uses ratio 2.0; exact-1.5 boundary untested                                                                                                                                                                                      |
| 16  | Evicted threshold `>0 → >1` (GMR L325)                                                                                                                           | 1     | TEST-GAP   | GMR_25                   | :397 uses 500; evicted==1 untested                                                                                                                                                                                                    |
| 17  | TTL block gate `total_keys >0 → >=0` (introduces div-by-zero crash) / `>1` (GMR L332)                                                                            | 2     | TEST-GAP   | GMR_27, GMR_28           | `>=0` turns an empty DB (dbsize 0) into a ZeroDivisionError — a real startup-path crash nobody covers                                                                                                                                 |
| 18  | Recommendation string element replaced with `None` (GMR L335-338)                                                                                                | 1     | TEST-GAP   | GMR_39                   | List gains a `None` entry; substring asserts use `in r.lower()` on other elements — type change invisible                                                                                                                             |
| 19  | maxmemory_mb ternary guard relaxed: `>=0`, `or True` — 0/1048576 = 0.0 == 0 (GMS L196 + GEC L216)                                                                | 4     | EQUIVALENT | GMS_130, GMS_125, GEC_20 | maxmemory is a non-negative int; float 0.0 == int 0 under `==`. GEC_25 included                                                                                                                                                       |
| 20  | Recommendation display-text case / XX-wrap mutations on first string fragment (GMR L293, L313, L341)                                                             | 9     | EQUIVALENT | GMR_5, GMR_18, GMR_42    | Pure message text; existing asserts are case-folded substrings → semantically identical observable behavior. Strict full-string assert would kill but that's brittle; skip                                                            |
| 21  | 1-byte / 1-MB limit edge thresholds: `maxmemory>0 → >1`, `maxmemory_bytes>0 → >1`, human `MB>0 → >1` (GMS L196/L202, GEC L216/L222)                              | 3     | LOW-VALUE  | GMS_131, GMS_134, GEC_26 | Differs only when maxmemory == 1 byte — physically absurd config; not worth pinning                                                                                                                                                   |
| 22  | `if len(large_keys) >= max_keys: break → >` (FLK L263)                                                                                                           | 1     | LOW-VALUE  | FLK_23                   | Break-point shifts one iteration; final `[:max_keys]` slice (L268) makes results identical — observable only via memory_usage call-count, not worth asserting                                                                         |
| 23  | `if maxmemory > 1` guard on usage-percent calc (GMS L187)                                                                                                        | 1     | LOW-VALUE  | GMS_85                   | Same 1-byte edge as #21                                                                                                                                                                                                               |
| 24  | maxmemory_human `"%.0fMB" if maxmemory_mb > 1 else "unlimited"` (GEC L222)                                                                                       | 1     | LOW-VALUE  | GEC_48                   | Differs only for sub-1-MB limits (0, 1 MB]; "unlimited" for a 0.5 MB cap is odd but nobody configures that                                                                                                                            |

**Totals: 93 TEST-GAP + 14 EQUIVALENT + 6 LOW-VALUE = 113.**

## Drafted tests (highest-value clusters)

All target `backend/tests/unit/services/test_redis_memory_service.py`, same fixtures/style.
Every draft is **UNVERIFIED — not yet run red/green** (test-execution forbidden in this run). TDD procedure for each: apply the mutant copy for one representative key of the cluster → the named assert fails (or errors); on original source → passes.

### T1 — kills clusters 5, 9, 10, 14 (partial 6/8) — strict-equality stats test

```python
# UNVERIFIED - not yet run red/green
# TDD: fails on GMS__mutmut_118 (divisor 1025 → 49.95 != approx 50.0) etc.; passes on original.
@pytest.mark.asyncio
async def test_get_memory_stats_reports_every_field_exactly(memory_service, mock_redis_client):
    """Every MemoryStats field must match the mocked INFO payloads exactly.

    Kills divisor/operator/None-swap mutants that hide behind rel=0.1 tolerance
    and fields the current test never asserts (peak, maxmemory_mb, keys_with_ttl,
    evicted, percent).
    """
    mock_redis_client.info.side_effect = [
        {
            "used_memory": 52428800,           # 50 MB
            "used_memory_peak": 104857600,     # 100 MB
            "maxmemory": 268435456,            # 256 MB
            "mem_fragmentation_ratio": 1.15,
        },
        {"evicted_keys": 100},
        {
            "db0": {"keys": 4000, "expires": 3000, "avg_ttl": 3600},
            "db1": {"keys": 1000, "expires": 200},
        },
    ]
    mock_redis_client.config_get.return_value = {"maxmemory-policy": "volatile-lru"}
    mock_redis_client.dbsize.return_value = 5000

    stats = await memory_service.get_memory_stats()

    assert stats.used_memory_bytes == 52428800
    assert stats.used_memory_mb == pytest.approx(50.0)          # no rel= → kills 1025 divisor
    assert stats.used_memory_peak_bytes == 104857600            # kills key-mutation → 0 and None swap
    assert stats.used_memory_peak_mb == pytest.approx(100.0)    # kills *divisor, /->* , None swap
    assert stats.maxmemory_bytes == 268435456
    assert stats.maxmemory_mb == pytest.approx(256.0)           # kills and-False, *, /1024/1024, 1025s, None
    assert stats.maxmemory_policy == "volatile-lru"
    assert stats.memory_fragmentation_ratio == 1.15
    assert stats.total_keys == 5000
    assert stats.keys_with_ttl == 3200                          # 3000 + 200; kills init=1, +=→= (multi-db)
    assert stats.evicted_keys == 100
    assert stats.is_memory_limited is True
    # 52428800 / 268435456 * 100 == 19.53125 exactly; kills *101 (→ 19.7265...)
    assert stats.memory_usage_percent == pytest.approx(19.53125)
```

Extend the _unlimited_ test with `assert stats.maxmemory_mb == 0.0` (kills the `else 0 → 1` mutant GMS_132) — one added line to `test_get_memory_stats_unlimited` (:160).

### T2 — kills clusters 6, 7 (the 21-key missing-key/default family, incl. partial 8)

```python
# UNVERIFIED - not yet run red/green
# TDD: fails on GMS__mutmut_44 (frag default 1.0→2.0) — assert expects 1.0; errors on GMS__mutmut_31 (None>0 TypeError).
@pytest.mark.asyncio
async def test_get_memory_stats_applies_defaults_when_fields_missing(memory_service, mock_redis_client):
    """Fields absent from Redis INFO/CONFIG responses must fall back to documented defaults.

    Every fixture in this file supplies every key, so all .get(key, default) default
    mutants (None/1/dropped/2.0 and wrong dict keys) survive. This test makes the
    fallback path observable.
    """
    mock_redis_client.info.side_effect = [
        {},                       # INFO memory: nothing present
        {},                       # INFO stats: no evicted_keys
        {"db0": {"keys": 10}},    # INFO keyspace: dict without 'expires'
    ]
    mock_redis_client.config_get.return_value = {}   # CONFIG GET returns no policy
    mock_redis_client.dbsize.return_value = 10

    stats = await memory_service.get_memory_stats()

    assert stats.used_memory_bytes == 0               # kills default None (TypeError) / 1
    assert stats.used_memory_peak_bytes == 0          # kills default None / 1
    assert stats.maxmemory_bytes == 0
    assert stats.maxmemory_mb == 0.0                  # kills else-branch 1 (with is_limited False)
    assert stats.maxmemory_policy == "noeviction"     # kills None / XXnoevictionXX / NOEVICTION
    assert stats.memory_fragmentation_ratio == 1.0    # kills default 2.0
    assert stats.keys_with_ttl == 0                   # kills init 1, expires default None (TypeError) / 1
    assert stats.evicted_keys == 0                    # kills default None / 1
    assert stats.is_memory_limited is False           # kills maxmemory default 1
    assert stats.memory_usage_percent == 0.0


@pytest.mark.asyncio
async def test_get_current_config_applies_defaults_when_fields_missing(memory_service, mock_redis_client):
    """CONFIG GET without maxmemory/policy keys must yield 0 / noeviction defaults."""
    mock_redis_client.config_get.side_effect = [{}, {}]

    config = await memory_service.get_current_config()

    assert config["maxmemory_bytes"] == "0"           # kills int(None) TypeError / int(1)
    assert config["maxmemory_mb"] == "0.00"
    assert config["maxmemory_policy"] == "noeviction" # kills None / XXnoevictionXX / NOEVICTION
    assert config["maxmemory_human"] == "unlimited"
```

### T3 — kills clusters 1, 2 (18 args-forwarding mutants)

```python
# UNVERIFIED - not yet run red/green
# TDD: fails on GMS__mutmut_2 (info(None) not in awaited calls) and GEC__mutmut_2 (config_get(None));
# passes on original.
@pytest.mark.asyncio
async def test_stats_and_config_calls_use_documented_sections_and_keys(memory_service, mock_redis_client):
    """The service must request the exact INFO sections and CONFIG patterns.

    Mocks keyed by call order (side_effect lists / fixed return_value) currently make
    every section- and pattern-argument mutant invisible; on real Redis the wrong
    section/pattern silently returns an empty dict.
    """
    section_data = {
        "memory": {
            "used_memory": 52428800,
            "used_memory_peak": 104857600,
            "maxmemory": 268435456,
            "mem_fragmentation_ratio": 1.15,
        },
        "stats": {"evicted_keys": 0},
        "keyspace": {},
    }

    async def fake_info(section=None):
        return section_data.get(section, {})

    mock_redis_client.info.side_effect = fake_info
    mock_redis_client.config_get.return_value = {"maxmemory-policy": "volatile-lru"}

    stats = await memory_service.get_memory_stats()

    mock_redis_client.info.assert_any_await("memory")
    mock_redis_client.info.assert_any_await("stats")
    mock_redis_client.info.assert_any_await("keyspace")
    mock_redis_client.config_get.assert_any_await("maxmemory-policy")
    assert stats.used_memory_bytes == 52428800   # belt-and-braces: wrong section would default to 0

    mock_redis_client.config_get.reset_mock()
    mock_redis_client.config_get.side_effect = [
        {"maxmemory": "268435456"},
        {"maxmemory-policy": "volatile-lru"},
    ]
    await memory_service.get_current_config()
    mock_redis_client.config_get.assert_any_await("maxmemory")
    mock_redis_client.config_get.assert_any_await("maxmemory-policy")
```

### T4 — kills clusters 3, 4, 11 (12 mutants: scan args, memory_usage key, KeyMemoryInfo fields)

```python
# UNVERIFIED - not yet run red/green
# TDD: fails on FLK__mutmut_3 (scan_keys(pattern=None) breaks assert_called_once_with) and
# FLK__mutmut_15 (key=None breaks the identity tuple); passes on original.
@pytest.mark.asyncio
async def test_find_large_keys_scans_pattern_and_reports_key_identity(memory_service, mock_redis_client):
    """find_large_keys must forward pattern/scan budget and preserve key + memory_kb per result."""
    mock_redis_client.scan_keys.return_value = ["k1", "k2", "k3"]
    mock_redis_client.memory_usage.side_effect = [2048, 1024, 4096]

    result = await memory_service.find_large_keys(pattern="cache:*", min_size_bytes=1024, max_keys=3)

    # 10x scan budget over max_keys; kills pattern drop/None and *10 → /10, *11, None mutants
    mock_redis_client.scan_keys.assert_called_once_with(pattern="cache:*", max_keys=30)
    # kills memory_usage(key) → memory_usage(None)
    mock_redis_client.memory_usage.assert_any_await("k1")
    # kills key=None, memory_kb None / *1024 / /1025 mutants
    assert [(info.key, info.memory_bytes, info.memory_kb) for info in result] == [
        ("k3", 4096, pytest.approx(4.0)),
        ("k1", 2048, pytest.approx(2.0)),
        ("k2", 1024, pytest.approx(1.0)),
    ]


@pytest.mark.asyncio
async def test_get_key_memory_usage_queries_the_requested_key(memory_service, mock_redis_client):
    """The wrapper must query the caller's key, not a mutated argument."""
    mock_redis_client.memory_usage.return_value = 4096

    usage = await memory_service.get_key_memory_usage("cache:events:list")

    assert usage == 4096
    mock_redis_client.memory_usage.assert_awaited_once_with("cache:events:list")
```

### T5 — kills clusters 12, 13, 15, 16, 17, 18 (15 mutants in the recommendation heuristics)

```python
# UNVERIFIED - not yet run red/green
# TDD: fails on GMR__mutmut_9 (usage 90.5% → mutant drops 'critically high') and GMR__mutmut_27
# (total_keys=0 → ZeroDivisionError); passes on original.
def _wire_stats_mock(
    mock_redis_client,
    *,
    used_memory: int,
    maxmemory: int,
    policy: str,
    total_keys: int,
    expires: int,
    evicted_keys: int = 0,
    frag: float = 1.0,
):
    """Point the service's get_memory_stats at an exact synthetic state."""
    keyspace = {"db0": {"keys": total_keys, "expires": expires}} if total_keys else {}
    mock_redis_client.info.side_effect = [
        {
            "used_memory": used_memory,
            "used_memory_peak": used_memory,
            "maxmemory": maxmemory,
            "mem_fragmentation_ratio": frag,
        },
        {"evicted_keys": evicted_keys},
        keyspace,
    ]
    mock_redis_client.config_get.return_value = {"maxmemory-policy": policy}
    mock_redis_client.dbsize.return_value = total_keys


# Each case: (state kwargs, must_contain substrings, must_not_contain substrings).
# All cases except the empty-db one have a memory limit set, so the "memory limit"
# recommendation is absent; ttl=100% on non-volatile policies keeps the TTL advisory quiet.
RECOMMENDATION_CASES = [
    # exactly 90.0%: elevated band only (>90 strict). Kills >=90 (GMR_8).
    (dict(used_memory=188743680, maxmemory=209715200, policy="noeviction",
          total_keys=100, expires=100),
     ["noeviction'"], ["critically high"]),
    # 90.5%: critical band. Kills >91 (GMR_9).
    (dict(used_memory=189792256, maxmemory=209715200, policy="noeviction",
          total_keys=100, expires=100),
     ["critically high"], ["elevated"]),
    # exactly 75.0%: no usage recommendation at all (>75 strict). Kills >=75 (GMR_11).
    (dict(used_memory=157286400, maxmemory=209715200, policy="noeviction",
          total_keys=100, expires=100),
     ["noeviction'"], ["critically high", "elevated"]),
    # 75.5%: elevated band present. Kills >76 (GMR_12).
    (dict(used_memory=158334976, maxmemory=209715200, policy="noeviction",
          total_keys=100, expires=100),
     ["elevated"], ["critically high"]),
    # exactly 1 evicted key still triggers, with the count interpolated. Kills evicted >1 (GMR_25).
    (dict(used_memory=20971520, maxmemory=209715200, policy="noeviction",
          total_keys=100, expires=100, evicted_keys=1),
     ["1 keys have been evicted"], []),
    # fragmentation exactly at 1.5: NO recommendation (>1.5 strict). Kills >=1.5 (GMR_21).
    (dict(used_memory=20971520, maxmemory=209715200, policy="noeviction",
          total_keys=100, expires=100, frag=1.5),
     ["noeviction'"], ["fragmentation"]),
    # ttl 49.5% + volatile-lru: TTL advisory fires. Kills ttl /→* (31), XXvolatileXX (37), VOLATILE (38),
    # and the None-injection element (39, via the str check in the test body).
    (dict(used_memory=20971520, maxmemory=209715200, policy="volatile-lru",
          total_keys=200, expires=99),
     ["49.5% of keys have ttl"], []),
    # ttl exactly 50%: NO advisory (<50 strict). Kills <=50 (GMR_34).
    (dict(used_memory=20971520, maxmemory=209715200, policy="volatile-lru",
          total_keys=200, expires=100),
     ["healthy"], ["of keys have ttl"]),
    # ttl 50.5%: NO advisory. Kills <51 (GMR_35).
    (dict(used_memory=20971520, maxmemory=209715200, policy="volatile-lru",
          total_keys=200, expires=101),
     ["healthy"], ["of keys have ttl"]),
    # ttl 100/202=49.5049%: advisory fires; *101 variant yields 50.0049% → suppressed. Kills *101 (GMR_32).
    (dict(used_memory=20971520, maxmemory=209715200, policy="volatile-lru",
          total_keys=202, expires=100),
     ["49.5% of keys have ttl"], []),
    # empty db: total_keys=0 must NOT divide by zero; healthy fallback only. Kills >=0 (GMR_27).
    (dict(used_memory=20971520, maxmemory=209715200, policy="volatile-lru",
          total_keys=0, expires=0),
     ["healthy"], []),
    # single key, volatile policy: ttl advisory fires (gate is >0, not >1). Kills >1 (GMR_28).
    (dict(used_memory=20971520, maxmemory=209715200, policy="volatile-lru",
          total_keys=1, expires=0),
     ["0.0% of keys have ttl"], []),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("state, must, must_not", RECOMMENDATION_CASES)
async def test_recommendation_thresholds_and_branches(memory_service, mock_redis_client, must, must_not, state):
    """Pin every recommendation branch at its exact boundary values."""
    _wire_stats_mock(mock_redis_client, **state)

    recommendations = await memory_service.get_memory_recommendations()

    assert all(isinstance(r, str) and r for r in recommendations)  # kills None injection (GMR_39)
    lowered = [r.lower() for r in recommendations]
    for needle in must:
        assert any(needle.lower() in r for r in lowered), f"missing {needle!r} in {recommendations}"
    for needle in must_not:
        assert not any(needle.lower() in r for r in lowered), f"unexpected {needle!r} in {recommendations}"
```

(Note: strip the placeholder ternary in the evicted case to plain `"evicted"` before landing; kept explicit to show the exact-count intent `f"{stats.evicted_keys} keys"` — a `startswith("1 keys have been evicted")` check pins GMR_25 harder than a substring. The ttl-50% "must_not" needle should be the literal `"of keys have ttl"`; tidy both when landing.)

### Kill coverage of drafts vs clusters

| Draft                          | Clusters killed                                          |
| ------------------------------ | -------------------------------------------------------- |
| T1 (+1 line in unlimited test) | 5, 9, 10, 14 (+ keys_with_ttl multi-db part of 8)        |
| T2                             | 6, 7 (all 21) + residual 8 (expires-default), 17-partial |
| T3                             | 1, 2 (all 18)                                            |
| T4                             | 3, 4, 11 (all 12)                                        |
| T5                             | 12, 13, 15, 16, 17, 18 (all 15)                          |

Clusters 1-18 minus 8b (93 TEST-GAP survivors) are covered by the five drafts; clusters 8b, 19-24 (14 EQUIVALENT + 6 LOW-VALUE) are deliberately not pursued (cluster 20 optionally killable by a strict first-fragment string assert if the project prefers score over signal).

## Reference coordinates

- Covering test file: `backend/tests/unit/services/test_redis_memory_service.py` (fixtures L22-62; get_memory_stats tests L134-196; get_current_config L203-229; find_large_keys L236-283; get_key_memory_usage L290-306; recommendations L313-425)
- Source functions: `get_memory_stats` L151-204, `get_current_config` L206-223, `find_large_keys` L225-268, `get_key_memory_usage` L270-279, `get_memory_recommendations` L281-343
- RedisClient contracts (`backend/core/redis.py`): `info` L1706, `config_get` L1835, `memory_usage` L1884, `scan_keys` L1907 (defaults `pattern="*"`, `max_keys=10000` — why dropped-arg mutants are silently absorbable by real clients too)
- Raw per-mutant diffs: `/tmp/wp25/wp44-triage/diffs/*redis_memory_service*.diff`
