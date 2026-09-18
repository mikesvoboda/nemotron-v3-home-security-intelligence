# WP4.4 Triage Dossier — backend/services/scene_baseline.py

- **Survivors:** 101 of 224 keyed mutants (exit_code 0 in `mutants/backend/services/scene_baseline.py.meta`)
- **Diff provenance:** each survivor's variant body in `mutants/backend/services/scene_baseline.py`
  diffed against its `__mutmut_orig` sibling in the same copy (ground truth — the local
  libcst reproduction misaligned numbering in `get_baseline`, so the copy was used; derived
  per-survivor diffs saved to `/tmp/wp25/wp44-triage/scene_baseline_surv_diffs.json`).
- **Covering test file (only one):** `backend/tests/unit/services/test_scene_baseline.py`
  (from `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`).
- **Cluster totals:** TEST-GAP 89, LOW-VALUE 6, EQUIVALENT 6 → 101.

## Why so many survive (root cause)

The existing suite exercises every method but asserts only *shapes*, not *values*:

| What the tests assert | What they never assert | Where |
|---|---|---|
| `pipeline.setex.call_count == 3` | the (key, ttl, value) args of each setex | `TestRedisPipelining.test_set_baseline_uses_pipeline` :593-612, `test_update_baseline_uses_pipeline_for_set` :555-590 |
| `_, count = await update_baseline(...)` — the blended baseline is **discarded** | the EMA/normalized embedding values | `test_update_baseline_ema_update` :291-313 |
| `len(result) == EMBEDDING_DIMENSION` | direction/norm of returned vectors | `test_update_baseline_first_sample` :269-288 |
| `mock_redis.delete.assert_called_once()` | which keys were deleted; delete()==1 boundary | `test_delete_baseline_success` :351-360 (mock returns 3, never 1) |
| `mock_clip.anomaly_score.assert_called_once()` | forwarded image + baseline args | `test_get_anomaly_score_success` :385-408 |
| `service1 is service2` (singleton identity) | that redis/clip deps were wired in | `TestGlobalServiceFunctions` :465-488 |
| `info["exists"], info["sample_count"], info["is_reliable"]` | `info["last_updated"]` (never read!) | `test_get_baseline_info_*` :212-266 |
| key-independent pipeline mocks (same execute result for any key) | that camera_id propagates into the keys actually queried | everywhere the helper `create_mock_redis_with_pipeline` :31-96 is used |

## Source oddity worth flagging (not a mutant)

`backend/services/scene_baseline.py:189` — `except TypeError, ValueError:` is legal only under
PEP 758 (Python ≥3.14; parses on sandbox 3.14.4). Any py<3.14 tooling chokes on this line. It
appears identically in the mutant copy's `__mutmut_orig` bodies, so it is source, not a clobber.

## Cluster table (counts sum to 101)

| # | Pattern | Count | Class | Example keys | Note |
|---|---|---|---|---|---|
| C1 | `set_baseline`: setex arg mutants — key/ttl/value replaced by `None`, `json.dumps(None)`, `str(None)`, arg drops | 11 | TEST-GAP | set_baseline__mutmut_22, set_baseline__mutmut_23, set_baseline__mutmut_28 | pipelining test asserts `setex.call_count == 3` but never the call args (test :593-612) |
| C2 | `update_baseline`: same setex arg mutants on the write path | 11 | TEST-GAP | update_baseline__mutmut_43, update_baseline__mutmut_44, update_baseline__mutmut_49 | test :555-590 counts calls only |
| C3 | `set_baseline`: derived Redis keys become `None`/`camera_id`→`None` | 6 | TEST-GAP | set_baseline__mutmut_3, set_baseline__mutmut_4, set_baseline__mutmut_5 | killed by same arg assertion that kills C1 |
| C4 | `update_baseline`: derived Redis keys become `None`/camera→None | 6 | TEST-GAP | update_baseline__mutmut_3, update_baseline__mutmut_5, update_baseline__mutmut_7 | same fix as C2's arg assertion |
| C5 | `delete_baseline`: `redis.delete(...)` arg/key mutants (drops, None args) | 12 | TEST-GAP | delete_baseline__mutmut_1, delete_baseline__mutmut_11, delete_baseline__mutmut_12 | `assert_called_once()` with no args (test :360) |
| C6 | camera_id→None propagated into internal `get_baseline`/`update_baseline` calls | 4 | TEST-GAP | update_baseline__mutmut_10, get_anomaly_score__mutmut_7, get_baseline_info__mutmut_2 | (+update_baseline_from_image__mutmut_8) every mock pipeline returns the same execute result for any key — TDA-fakes must be key-dependent |
| C7 | EMA blend arithmetic: `+`→`-`, `*`→`/`, `(1-decay)`→`(1+decay)`/`(2-decay)` | 4 | TEST-GAP | update_baseline__mutmut_12, update_baseline__mutmut_13, update_baseline__mutmut_15 | test :291-313 comments the expected 0.9 but discards the returned baseline; uniform test vectors also cancel magnitude under normalization — non-uniform vectors required |
| C8 | L2 normalization math: `**0.5`→`*0.5`/`**1.5`, `x*x`→`x/x`, `x/norm`→`x*norm`, list→`None` (set+update) | 9 | TEST-GAP | set_baseline__mutmut_10, set_baseline__mutmut_17, update_baseline__mutmut_33 | stored/returned values never compared; set_baseline's is doubly invisible (returns None) |
| C9 | normalization guard flips: `if norm > 0`→`>= 0` (zero-vector → ZeroDivisionError) / `> 1` (sub-unit vectors skip normalize) | 4 | TEST-GAP | set_baseline__mutmut_14, set_baseline__mutmut_15, update_baseline__mutmut_35 | (+update_baseline__mutmut_36) no test feeds a zero or sub-unit-norm embedding |
| C10 | `datetime.now(UTC)`→`datetime.now(None)` — naive local timestamp stored | 2 | TEST-GAP | set_baseline__mutmut_20, update_baseline__mutmut_41 | stored updated-key value never read back; killable by tz-aware assert |
| C11 | `get_baseline` fallback branches: count default (`or True` makes else unreachable; default `1`→`2`); `last_updated` default `None`→`""` | 3 | TEST-GAP | get_baseline__mutmut_20, get_baseline__mutmut_22, get_baseline__mutmut_23 | no test calls get_baseline with a missing count/updated key |
| C12 | `get_baseline_info` `last_updated` field: value suppressed (`and False`), always-format (`or True`), key clobbered (`XXlast_updatedXX`/`LAST_UPDATED`) in both dict branches | 6 | TEST-GAP | get_baseline_info__mutmut_8, get_baseline_info__mutmut_10, get_baseline_info__mutmut_21 | `info["last_updated"]` is never asserted anywhere (tests :212-266) |
| C13 | `get_baseline_info` reliability boundary `>= MIN`→`> MIN` | 1 | TEST-GAP | get_baseline_info__mutmut_14 | tests use 10 (reliable) and 2 (not); never exactly 5 |
| C14 | `__init__` decay guard boundary `0 < d <= 1`→`0 < d < 1` (decay=1.0 wrongly rejected) | 1 | TEST-GAP | __init____mutmut_4 | tests cover 0, -0.1, 1.5 (:128-144) but never the valid upper bound 1.0 |
| C15 | `get_scene_baseline_service`: constructor arg mutants (redis→None, clip→None, positional shift, clip dropped) | 4 | TEST-GAP | x_get_scene_baseline_service__mutmut_3, _4, _5 | singleton test asserts identity only (:465-488), never `_redis`/`_clip` wiring, and never passes a clip client at all |
| C16 | `get_anomaly_score`: `clip.anomaly_score(image, baseline)` arg mutants (image→None, baseline→None, args swapped, args dropped) | 4 | TEST-GAP | get_anomaly_score__mutmut_10, _11, _12 | `assert_called_once()` without args (:408) |
| C17 | `delete_baseline` return boundary `deleted > 0`→`> 1` (delete()==1 wrongly returns False) | 1 | TEST-GAP | delete_baseline__mutmut_15 | success test mocks delete()==3 (:354); partial-expiry case (1 key left) returns False on mutant |
| C18 | logging calls clobbered to `logger.info(None)`/`logger.debug(None)` | 5 | LOW-VALUE | __init____mutmut_13, delete_baseline__mutmut_16, set_baseline__mutmut_42 | (+update_baseline__mutmut_63, get_anomaly_score__mutmut_14) pure logging, no control flow |
| C19 | `get_anomaly_score` warning threshold `sample_count < MIN`→`<= MIN` | 1 | LOW-VALUE | get_anomaly_score__mutmut_8 | changes only whether a logger.warning fires at exactly 5 samples; killable via caplog if ever wanted |
| C20 | exception message-text clobbers (`"XX...XX"`) | 3 | EQUIVALENT | __init____mutmut_7, get_anomaly_score__mutmut_3, update_baseline_from_image__mutmut_3 | tests' `pytest.raises(match=...)` substrings survive inside the XX-wrapped text; message-only change |
| C21 | `zip(..., strict=True)`→`False`/`None`/dropped | 3 | EQUIVALENT | update_baseline__mutmut_19, _22, _23 | both operands are length-validated 768 on every reachable path; strict flag can only diverge on corrupt Redis data |

## Drafted tests (6) — UNVERIFIED, not yet run red/green

Add `import math` to the file's imports. TDD procedure per test: apply the cluster's mutant →
new assert fails; original code → passes. Run only in the serial pytest lane (live mutation
run owns this machine — nothing was executed here).

### T1 — kills C1 + C3 + C8(set) + C9 + C10(set) — into `TestRedisPipelining`

```python
@pytest.mark.asyncio
async def test_set_baseline_writes_exact_keys_ttl_and_unit_embedding(self) -> None:
    """set_baseline must write unit-normalized embedding with exact keys, TTL, count, tz-aware ts."""
    mock_redis = AsyncMock()
    mock_pipeline = MagicMock()
    mock_pipeline.setex = MagicMock(return_value=mock_pipeline)
    mock_pipeline.execute = AsyncMock(return_value=[True, True, True])
    mock_redis._client = MagicMock()
    mock_redis._client.pipeline = MagicMock(return_value=mock_pipeline)

    service = SceneBaselineService(mock_redis, baseline_ttl=3600)
    raw = [0.1] * EMBEDDING_DIMENSION
    await service.set_baseline("camera_1", raw, sample_count=100)

    assert mock_pipeline.setex.call_count == 3
    (e_key, e_ttl, e_val), (c_key, c_ttl, c_val), (u_key, u_ttl, u_val) = [
        call.args for call in mock_pipeline.setex.call_args_list
    ]
    assert e_key == "scene_baseline:camera_1:embedding"
    assert c_key == "scene_baseline:camera_1:count"
    assert u_key == "scene_baseline:camera_1:updated"
    assert (e_ttl, c_ttl, u_ttl) == (3600, 3600, 3600)
    scale = math.sqrt(sum(x * x for x in raw))
    assert json.loads(e_val) == pytest.approx([x / scale for x in raw])
    assert c_val == "100"
    assert datetime.fromisoformat(u_val).tzinfo is not None

    # Sub-unit norm vector must STILL be rescaled (kills `norm > 1` guard flip).
    mock_pipeline.setex.reset_mock()
    small = [0.01] * EMBEDDING_DIMENSION
    await service.set_baseline("camera_2", small, sample_count=1)
    small_stored = json.loads(mock_pipeline.setex.call_args_list[0].args[2])
    assert math.isclose(sum(x * x for x in small_stored), 1.0)

    # All-zero embedding must pass through unnormalized (kills `norm >= 0` → ZeroDivisionError).
    mock_pipeline.setex.reset_mock()
    await service.set_baseline("camera_3", [0.0] * EMBEDDING_DIMENSION)
    assert json.loads(mock_pipeline.setex.call_args_list[0].args[2]) == [0.0] * EMBEDDING_DIMENSION
```

### T2 — kills C2 + C4 + C6(update) + C7 + C8(update) + C9(update) + C10(update) — into `TestRedisPipelining`

```python
@pytest.mark.asyncio
async def test_update_baseline_blends_ema_and_stores_all_three_keys(self) -> None:
    """EMA blend values and all three SETEX args must be observable; camera_id must be honoured."""
    old = [1.0] + [0.0] * (EMBEDDING_DIMENSION - 1)  # non-uniform: normalization cannot mask sign/coeff flips
    ts = datetime.now(UTC).isoformat()

    fetched: list[str] = []

    def track_get(key: str) -> MagicMock:
        fetched.append(key)
        return get_pipe

    def exec_get() -> list:
        # Key-dependent fake: a lookup built from a clobbered camera_id sees no baseline.
        if "scene_baseline:None:embedding" in fetched:
            return [None, None, None]
        return [json.dumps(old), "5", ts]

    mock_redis = AsyncMock()
    get_pipe = MagicMock()
    get_pipe.get = MagicMock(side_effect=track_get)
    get_pipe.execute = AsyncMock(side_effect=exec_get)
    set_pipe = MagicMock()
    set_pipe.setex = MagicMock(return_value=set_pipe)
    set_pipe.execute = AsyncMock(return_value=[True, True, True])
    mock_redis._client = MagicMock()
    mock_redis._client.pipeline = MagicMock(side_effect=[get_pipe, set_pipe])

    service = SceneBaselineService(mock_redis, decay_factor=0.9, baseline_ttl=3600)
    new = [0.0, 1.0] + [0.0] * (EMBEDDING_DIMENSION - 2)
    result, count = await service.update_baseline("camera_1", new)

    assert count == 6
    blended = [0.9 * o + 0.1 * n for o, n in zip(old, new, strict=True)]
    scale = math.sqrt(sum(x * x for x in blended))
    assert result == pytest.approx([x / scale for x in blended])
    # blended norm (0.905) is < 1 → kills the `norm > 1` skip-normalization mutant too
    assert set_pipe.setex.call_count == 3
    (e_key, e_ttl, e_val), (c_key, c_ttl, c_val), (u_key, u_ttl, u_val) = [
        call.args for call in set_pipe.setex.call_args_list
    ]
    assert e_key == "scene_baseline:camera_1:embedding"
    assert c_key == "scene_baseline:camera_1:count"
    assert u_key == "scene_baseline:camera_1:updated"
    assert (e_ttl, c_ttl, u_ttl) == (3600, 3600, 3600)
    assert json.loads(e_val) == pytest.approx(result)
    assert c_val == "6"
    assert datetime.fromisoformat(u_val).tzinfo is not None
```

### T3 — kills C9 zero-vector half on the update path — into `TestSceneBaselineService`

```python
@pytest.mark.asyncio
async def test_update_baseline_zero_vector_first_sample_stays_zero(self) -> None:
    """A zero embedding on a fresh camera must pass through, not hit a zero division."""
    mock_redis = create_mock_redis_with_pipeline(
        pipeline_results_sequence=[
            [None, None, None],
            [True, True, True],
        ]
    )
    service = SceneBaselineService(mock_redis)
    result, count = await service.update_baseline("camera_1", [0.0] * EMBEDDING_DIMENSION)
    assert count == 1
    assert result == [0.0] * EMBEDDING_DIMENSION  # norm>=0 mutant raises ZeroDivisionError
```

### T4 — kills C5 + C17 — into `TestSceneBaselineService`

```python
@pytest.mark.asyncio
async def test_delete_baseline_deletes_all_three_keys_and_counts_single(self) -> None:
    """delete()==1 (partial expiry) still means True, and all three keys must be requested."""
    mock_redis = AsyncMock()
    mock_redis.delete = AsyncMock(return_value=1)  # boundary: exactly one key removed
    service = SceneBaselineService(mock_redis)

    assert await service.delete_baseline("camera_1") is True  # `deleted > 1` mutant returns False
    mock_redis.delete.assert_called_once_with(
        "scene_baseline:camera_1:embedding",
        "scene_baseline:camera_1:count",
        "scene_baseline:camera_1:updated",
    )
```

### T5 — kills C11 + C12 + C13 (+C6/info with the fetched-keys trick) — into `TestSceneBaselineService`

```python
@pytest.mark.asyncio
async def test_get_baseline_fallbacks_and_info_exposes_last_updated(self) -> None:
    """Missing count/updated keys fall back correctly; info must surface last_updated + boundary."""
    embedding = [0.1] * EMBEDDING_DIMENSION
    ts = datetime.now(UTC).isoformat()

    # Missing count key → default 1 (or-True mutant dies on int(None); default-2 mutant miscounts).
    mock_redis = create_mock_redis_with_pipeline(get_results=[json.dumps(embedding), None, ts])
    service = SceneBaselineService(mock_redis)
    _, count, updated = await service.get_baseline("camera_1")
    assert count == 1
    assert updated is not None and updated.year >= 2020

    # Missing updated key → None, never "".
    mock_redis = create_mock_redis_with_pipeline(get_results=[json.dumps(embedding), "10", None])
    service = SceneBaselineService(mock_redis)
    _, _, updated = await service.get_baseline("camera_1")
    assert updated is None

    # Exactly MIN samples is reliable, and last_updated must be present in the dict.
    mock_redis = create_mock_redis_with_pipeline(
        get_results=[json.dumps(embedding), str(MIN_SAMPLES_FOR_RELIABLE_BASELINE), ts]
    )
    service = SceneBaselineService(mock_redis)
    info = await service.get_baseline_info("camera_1")
    assert info["last_updated"] == ts
    assert info["is_reliable"] is True  # `> MIN` mutant reports False here

    mock_redis = create_mock_redis_with_pipeline(get_results=[None, None, None])
    service = SceneBaselineService(mock_redis)
    info = await service.get_baseline_info("camera_1")
    assert info["last_updated"] is None  # key-clobber mutants raise KeyError
```

### T6 — kills C16 + C6(anomaly) — into `TestSceneBaselineService`

```python
@pytest.mark.asyncio
async def test_get_anomaly_score_forwards_image_and_stored_baseline(self) -> None:
    """CLIP must receive (image, stored-baseline-embedding) and the camera's own keys."""
    embedding = [0.1] * EMBEDDING_DIMENSION
    ts = datetime.now(UTC).isoformat()

    mock_redis = AsyncMock()
    mock_pipeline = MagicMock()
    mock_pipeline.get = MagicMock(return_value=mock_pipeline)
    mock_pipeline.execute = AsyncMock(
        return_value=[json.dumps(embedding), str(MIN_SAMPLES_FOR_RELIABLE_BASELINE + 1), ts]
    )
    mock_redis._client = MagicMock()
    mock_redis._client.pipeline = MagicMock(return_value=mock_pipeline)

    mock_clip = AsyncMock()
    mock_clip.anomaly_score = AsyncMock(return_value=(0.2, 0.8))

    service = SceneBaselineService(mock_redis, clip_client=mock_clip)
    image = Image.new("RGB", (224, 224))
    score, similarity = await service.get_anomaly_score("camera_1", image)

    assert (score, similarity) == (0.2, 0.8)
    mock_clip.anomaly_score.assert_called_once_with(image, embedding)
    mock_pipeline.get.assert_any_call("scene_baseline:camera_1:embedding")  # camera_id→None dies
```

### Not drafted (fold into existing tests as one-line asserts)

- **C15 (singleton wiring, 4 mutants):** in `test_get_scene_baseline_service_singleton` (:465) pass
  a `mock_clip` and assert `service1._redis is mock_redis and service1._clip is mock_clip`.
- **C14 (decay=1.0 boundary, 1 mutant):** add `SceneBaselineService(mock_redis, decay_factor=1.0)`
  succeeding to the init tests (:102-144).
- **C6 remainder** (`get_baseline_info__mutmut_2`, `update_baseline_from_image__mutmut_8`): reuse
  T2's key-dependent `exec_get` fake.
- **C18/C19/C20/C21:** no tests recommended (LOW-VALUE/EQUIVALENT); if the baseline wants them
  killed, caplog assertions suffice for C19.

## Mutation-killing math notes

- **Non-uniform vectors are mandatory** for the EMA cluster (C7): every entry of a uniform vector
  scales identically through L2 normalization, so `[0.9]*768` vs `-/+`-blends collapse to the
  same normalized vector up to per-entry sign only when entries differ — `[1,0,...]` ⊕ `[0,1,...]`
  with decay 0.9 gives expected `[0.994, +0.110, 0...]`, distinguishing `-`, `/`, `1+d`, `2-d`.
- **Sub-unit norms kill the guard flips the zero vector can't:** `[0.01]*768` (norm≈0.28) still
  normalizes under the original but skips normalization under `norm > 1`; the zero vector only
  distinguishes `>= 0` (ZeroDivisionError).
- **TTL/arg asserts must be positional** (`call.args`) since `setex` is called positionally.
