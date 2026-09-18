# WP4.4 Triage Dossier — backend/services/batch_coalescer.py

UNVERIFIED — read-only triage wave; no tests were run. Drafted tests below are marked UNVERIFIED.

## Run state

- `mutants/backend/services/batch_coalescer.py.meta`: 372 tracked keys, 191 still unchecked (exit_code null — live run), 69 killed, **112 SURVIVED** (this dossier).
- All 112 diffs extracted by ast-diffing each `xǁ…__mutmut_N` variant body in `mutants/backend/services/batch_coalescer.py` against `backend/services/batch_coalescer.py` (exactly one hunk per key; `mutmut show` spot-check agrees — note the copy dedents bodies, so `mutmut show` context lines look shifted but mutations are unambiguous).
- Covering tests (from `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`): **all six survivor functions are covered only by `backend/tests/unit/services/test_batch_coalescer.py`** (get_metrics/from_json/to_json also co-name unrelated CircuitBreaker/Mqtt/PgNotify/file_service `get_metrics`/`from_json` methods — different classes, not coverage of this module).

## Why so many survive (test-file forensics)

`backend/tests/unit/services/test_batch_coalescer.py`:

| Line | Test | Weakness |
|------|------|----------|
| 486 | `TestCandidateTracking::test_find_compatible_candidates` | `assert len(compatible) >= 0` — **tautology**; mock returns bytes that are raw JSON *without* `created_at`, so `from_json` throws inside the try and every path funnels to the except — the loop body is never really asserted. |
| 464 | `test_register_candidate` | `zadd.assert_called_once()` only — zero argument checks; `set`/`expire` never touched. |
| 512 | `test_remove_merged_candidates_with_camera_id` | `delete.call_count == 3` + zrem args — wrong-key mutants keep the count. |
| 527 | `test_remove_merged_candidates_reads_camera_from_redis` | `get.return_value` ignores the key; asserts only camera from zrem — round-trip runs but fields unasserted. |
| 624 | `TestMetricsCollection::test_tracks_merge_statistics` | asserts membership of 2 of 6 keys; no values. |

Prometheus helpers (`record_batch_coalesce_candidates` etc., `backend/core/metrics.py:5111-5146`): grep over `backend/tests/` finds **zero references** — the NEM-5530 counters are entirely unasserted.

## Cluster table (verified partition: each of the 112 keys appears exactly once; sum = 112)

TEST-GAP 78, EQUIVALENT 33, LOW-VALUE 1.

### TEST-GAP (16 clusters, 78 mutants)

| ID | Pattern | N | Keys (all) | Why the suite misses it |
|----|---------|---|-----------|------------------------|
| C1 | `find_compatible_candidates`: coalesce **time-window query args** broken — sign flip to empty range (`min=ts+W` / `max=ts−W`), bound→None (unbounded −inf/+inf), whole `zrangebyscore` call elided/args deleted, candidates key→None | 11 | fc_4, fc_5, fc_6, fc_7, fc_8, fc_9, fc_10, fc_11, fc_12, fc_13, fc_14 | Tautological assert (line 509) passes on empty; mock redis never inspected for key/scores. Window is the core "±coalesce_window_seconds" contract. |
| C2 | `find_compatible_candidates`: **self-match filter inverted** (`==`→`!=`) — candidate coalesces with itself | 1 | fc_23 | Existing test's self-batch never reaches the check. |
| C3 | `find_compatible_candidates`: **empty-result guard inverted** (`if not batch_ids`→`if batch_ids`) | 1 | fc_15 | Empty path now iterates None (TypeError) — mock path never feeds it. |
| C4 | `find_compatible_candidates`: **redis acquisition/guard broken** (`redis = None`, `is None`→`is not None`) | 2 | fc_1, fc_2 | Only happy path exercised. |
| C5 | `find_compatible_candidates`: **per-candidate lookup broken** — data-key f-string→None, `get(None)`, result forced None, data-None guard inverted, bytes decode→None, `from_json(None)` | 7 | fc_3, fc_19, fc_24, fc_25, fc_26, fc_27, fc_32 | No assertion on `redis.get` keys; missing-key and found-key paths indistinguishable under the malformed-payload mock. |
| C6 | `find_compatible_candidates`: **`candidates_evaluated` counter + `>0` guard** mutated (init 1, `=1`, `-=1`, `+=2`, `>=0`, `>1`) feeding `record_batch_coalesce_candidates` | 6 | fc_18, fc_28, fc_29, fc_30, fc_45, fc_46 | NEM-5530 Prometheus counter; no test patches or asserts it anywhere. |
| C7 | `register_candidate`: **TTL params broken** (`set(..., expire=None)`, expire kwarg deleted; `expire(None,…)`, `expire(key, None)`, `expire(600)`, `expire(key)`) | 6 | reg_8, reg_11, reg_16, reg_17, reg_18, reg_19 | Candidate data keys + sorted set leak forever (Redis TTL is the cleanup design); neither `set` nor `expire` is asserted. |
| C8 | `register_candidate`: **stored payload removed** (`to_json()`→None / deleted) | 2 | reg_7, reg_10 | Redis would store `None`; every later read fails — unasserted payload. |
| C9 | `register_candidate`: **redis key/member/timestamp args** →None or deleted (key locals, `set`/`zadd` first args, members dict, `timestamp()`) | 9 | reg_3, reg_4, reg_5, reg_6, reg_9, reg_12, reg_13, reg_14, reg_15 | `assert_called_once` can't see wrong key `None`, wrong member dict, or `None` score. |
| C10 | `remove_candidates`: **wrong-key get/delete** (data-key f-string→None, `get(None)`, `delete(None)`) | 3 | rm_4, rm_8, rm_13 | Existing tests assert `delete.call_count`, and `get.return_value` ignores the requested key. |
| C11 | `to_json`: **priority serialization broken** — value key renamed (`XXpriorityXX`, `PRIORITY`) or truthiness `and False` → always null | 3 | to_14, to_15, to_16 | Round-trip never asserted for a candidate with priority set. |
| C12 | `from_json`: **required fields → None** (`batch_id`, `detection_ids`, `object_types`, `avg_confidence`, `created_at`) | 5 | fj_3, fj_5, fj_6, fj_7, fj_8 | Silent corruption; round-trip test asserts only camera_id. |
| C13 | `from_json`: **priority silently lost** (branch deleted→None; `priority=None`; key-arg None; `and False`; `get` key renamed ×2) | 6 | fj_9, fj_16, fj_30, fj_35, fj_36, fj_37 | Persisted P0/P3 priority drives scheduling safety; zero assertions on deserialized priority. |
| C14 | `from_json`: **priority lookup mangled to raise** (`Priority(None)`, `parsed["XXpriorityXX"]`, `parsed["PRIORITY"]`) | 3 | fj_32, fj_33, fj_34 | Inside `find_compatible_candidates` these raise → caught → candidate **silently dropped** from coalescing; outside, uncaught ValueError/KeyError. |
| C15 | `get_metrics`: **result-dict key names clobbered/uppercased** (5 of 6 fields) | 8 | gm_5, gm_6, gm_7, gm_8, gm_9, gm_10, gm_11, gm_12 | Monitoring contract; test checks only 2 keys' membership. |
| C16 | `get_metrics`: **avg-reduction math/zero-guard** (`/`→`*`; guard `and False`, `or True`, `>=0` → ZeroDivisionError on fresh coalescer, `>1` → wrong result at exactly 1 merge) | 5 | gm_13, gm_14, gm_15, gm_16, gm_17 | Value never asserted; fresh-state path never called. |

### EQUIVALENT (4 clusters, 33 mutants)

| ID | Pattern | N | Keys | Note |
|----|---------|---|------|------|
| C17 | Log **message strings** mutated (clobber/lower/UPPER/None) in fc warning, reg debug, rm debug | 12 | fc_33, fc_37, fc_38, fc_39, reg_20, reg_24, reg_25, reg_26, rm_21, rm_25, rm_26, rm_27 | Pure message text; no consumer asserts log copy. (First-positional `None` keeps a valid `warning(None)` call.) |
| C18 | Log `extra=` dict deleted or →None | 6 | fc_34, fc_36, reg_21, reg_23, rm_22, rm_24 | Structured-log extras only; no test inspects `record.extra`. |
| C19 | Log `extra` **inner key names** clobbered/uppercased (batch_id/camera_id/detection_count/error/batch_count/camera_count) | 14 | fc_40, fc_41, fc_42, fc_43, reg_27, reg_28, reg_29, reg_30, reg_31, reg_32, rm_28, rm_29, rm_30, rm_31 | Log-payload naming only. If a log-parsing dashboard consumes these keys, reclassify — no test in-repo does. |
| C21 | Codec alias `"utf-8"`→`"UTF-8"` | 1 | fc_22 | Identical codec semantics. |

### LOW-VALUE (1 cluster, 1 mutant)

| ID | Pattern | N | Keys | Note |
|----|---------|---|------|------|
| C20 | Log payload `str(e)`→`str(None)` | 1 | fc_44 | Diagnostic error text lost; behavior unchanged. |

## Drafted tests (UNVERIFIED — not yet run red/green)

Style follows the existing file: imports inside test, `AsyncMock` redis, `@pytest.mark.asyncio`.
TDD procedure (one line each): apply the cluster mutant to `backend/services/batch_coalescer.py` → run the test → must FAIL (assertion/exception); restore original → must PASS; commit tests first.

### T-A — kills C1, C2, C3, C4, C5 (+ exercises C12/C13 fields) → `TestCandidateTracking`

```python
    @pytest.mark.asyncio
    async def test_find_compatible_candidates_window_and_fidelity(self) -> None:
        """In-window compatible candidate returned with full field fidelity; self and
        missing keys skipped; query uses exact key and ±window scores."""
        from backend.services.batch_coalescer import (
            BatchCoalescer,
            CoalesceCandidate,
            Priority,
        )

        def _payload(batch_id: str, camera: str) -> str:
            return CoalesceCandidate(
                batch_id=batch_id,
                camera_id=camera,
                detection_ids=[2, 3],
                object_types=["person", "person"],
                avg_confidence=0.82,
                created_at=datetime.now(tz=UTC),
                priority=Priority.P2_NORMAL,
            ).to_json()

        # self_id payload IS stored so a flipped self-skip would leak self into results
        stored = {
            "coalesce:candidate:self_id": _payload("self_id", "front"),
            "coalesce:candidate:b2": _payload("b2", "front"),
        }
        mock_redis = AsyncMock()
        mock_redis.zrangebyscore.return_value = ["self_id", b"b2", "b_missing"]
        mock_redis.get.side_effect = lambda key: stored.get(key)

        coalescer = BatchCoalescer(redis_client=mock_redis, coalesce_window_seconds=5.0)
        candidate = CoalesceCandidate(
            batch_id="self_id",
            camera_id="front",
            detection_ids=[1],
            object_types=["person"],
            avg_confidence=0.85,
            created_at=datetime.now(tz=UTC),
        )

        compatible = await coalescer.find_compatible_candidates(candidate)

        args, kwargs = mock_redis.zrangebyscore.call_args
        assert args[0] == "coalesce:candidates:front"          # kills C1 key/None cases
        ts = candidate.created_at.timestamp()
        assert kwargs["min_score"] == pytest.approx(ts - 5.0)  # kills sign flips/None
        assert kwargs["max_score"] == pytest.approx(ts + 5.0)
        assert [c.batch_id for c in compatible] == ["b2"]      # kills C2/C3/C4/C5
        assert compatible[0].detection_ids == [2, 3]           # kills C12 field-None
        assert compatible[0].object_types == ["person", "person"]
        assert compatible[0].avg_confidence == pytest.approx(0.82)
        assert compatible[0].priority is Priority.P2_NORMAL    # kills C13 silent-loss
        assert compatible[0].created_at.tzinfo is not None     # kills fj_8
        mock_redis.get.assert_any_call("coalesce:candidate:b2")
```

Red logic: every C1 mutant yields `[]` (flips→empty range, elided call→None) or wrong
args (None/deleted); inverted guards (`fc_2` `is not None`, `fc_15` truthiness,
`fc_23` `!=`, `fc_27` data-guard) each change the returned list or raise; C5 None-key
lookups return nothing so the hard `== ["b2"]` fails. Original: passes.

### T-B — kills C6 (Prometheus counter, `TestMetricsCollection`)

```python
    @pytest.mark.asyncio
    async def test_find_compatible_records_candidates_evaluated_metric(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """record_batch_coalesce_candidates receives the exact evaluated count."""
        from backend.services import batch_coalescer as bc
        from backend.services.batch_coalescer import BatchCoalescer, CoalesceCandidate

        recorded: list[int] = []
        monkeypatch.setattr(
            bc, "record_batch_coalesce_candidates", lambda n: recorded.append(n)
        )

        def _payload(batch_id: str) -> str:
            return CoalesceCandidate(
                batch_id=batch_id,
                camera_id="front",
                detection_ids=[2],
                object_types=["person"],
                avg_confidence=0.85,
                created_at=datetime.now(tz=UTC),
            ).to_json()

        stored = {
            "coalesce:candidate:b2": _payload("b2"),
            "coalesce:candidate:b3": _payload("b3"),
        }
        mock_redis = AsyncMock()
        mock_redis.zrangebyscore.return_value = ["b2"]
        mock_redis.get.side_effect = lambda key: stored.get(key)
        coalescer = BatchCoalescer(redis_client=mock_redis)
        candidate = CoalesceCandidate(
            batch_id="b1",
            camera_id="front",
            detection_ids=[1],
            object_types=["person"],
            avg_confidence=0.85,
            created_at=datetime.now(tz=UTC),
        )

        await coalescer.find_compatible_candidates(candidate)
        assert recorded == [1]                       # kills fc_18, fc_29, fc_30, fc_46

        mock_redis.zrangebyscore.return_value = ["b2", "b3"]
        await coalescer.find_compatible_candidates(candidate)
        assert recorded == [1, 2]                    # kills fc_28 (=1 assignment)

        mock_redis.zrangebyscore.return_value = ["gone"]
        await coalescer.find_compatible_candidates(candidate)
        assert recorded == [1, 2]                    # zero evals must NOT record: kills fc_45
```

### T-C — kills C7, C8, C9 (+round-trips C11) → `TestCandidateTracking`

```python
    @pytest.mark.asyncio
    async def test_register_candidate_writes_expected_keys_payload_and_ttl(self) -> None:
        """Registration stores round-trippable JSON under both keys with the TTL."""
        from backend.services.batch_coalescer import (
            BatchCoalescer,
            CoalesceCandidate,
            Priority,
        )

        mock_redis = AsyncMock()
        coalescer = BatchCoalescer(redis_client=mock_redis)
        created = datetime.now(tz=UTC)
        candidate = CoalesceCandidate(
            batch_id="b1",
            camera_id="front",
            detection_ids=[1, 2],
            object_types=["person", "person"],
            avg_confidence=0.85,
            created_at=created,
            priority=Priority.P2_NORMAL,
        )

        await coalescer.register_candidate(candidate)

        mock_redis.set.assert_awaited_once_with(
            "coalesce:candidate:b1",
            candidate.to_json(),
            expire=BatchCoalescer.CANDIDATE_TTL_SECONDS,
        )
        # payload must survive the Redis round trip (kills C11 to_json key/forced-null)
        restored = CoalesceCandidate.from_json(mock_redis.set.await_args.args[1])
        assert restored == candidate

        mock_redis.zadd.assert_awaited_once_with(
            "coalesce:candidates:front", {"b1": created.timestamp()}
        )
        mock_redis.expire.assert_awaited_once_with(
            "coalesce:candidates:front", BatchCoalescer.CANDIDATE_TTL_SECONDS
        )
```

### T-D — kills C15, C16 → `TestMetricsCollection`

```python
    @pytest.mark.asyncio
    async def test_get_metrics_full_contract_and_average(self) -> None:
        """get_metrics exposes all six keys and the correct average reduction."""
        from backend.services.batch_coalescer import BatchCoalescer, CoalesceCandidate

        mock_redis = AsyncMock()
        coalescer = BatchCoalescer(redis_client=mock_redis)

        fresh = coalescer.get_metrics()   # before any merge: kills gm_14/gm_16 (ZeroDivisionError)
        assert set(fresh) == {
            "merges_attempted",
            "merges_successful",
            "total_batches_processed",
            "total_batches_merged",
            "total_inference_reduction",
            "avg_inference_reduction_pct",
        }                              # kills all of C15
        assert fresh["avg_inference_reduction_pct"] == 0.0

        def _cand(bid: str) -> CoalesceCandidate:
            return CoalesceCandidate(
                batch_id=bid,
                camera_id="front",
                detection_ids=[len(bid)],
                object_types=["person"],
                avg_confidence=0.8,
                created_at=datetime.now(tz=UTC),
            )

        await coalescer.merge_batches([_cand("b1"), _cand("b2")])
        one = coalescer.get_metrics()
        assert one["avg_inference_reduction_pct"] == pytest.approx(
            50.0
        )                            # exactly 1 success: kills gm_17 (>1 guard) and gm_15 (* -> 5000)

        await coalescer.merge_batches([_cand("b3"), _cand("b4"), _cand("b5")])
        m = coalescer.get_metrics()
        assert m["merges_attempted"] == 2
        assert m["merges_successful"] == 2
        assert m["total_batches_processed"] == 5
        assert m["total_batches_merged"] == 5
        assert m["total_inference_reduction"] == pytest.approx(
            50.0 + (2 / 3) * 100.0
        )
        assert m["avg_inference_reduction_pct"] == pytest.approx(
            (50.0 + (2 / 3) * 100.0) / 2
        )
```

### T-E — kills C11–C14 (round-trip with priority) → `TestCoalesceCandidate`

```python
    def test_roundtrip_preserves_every_field_including_priority(self) -> None:
        """to_json -> from_json preserves all fields, both str and bytes input."""
        from backend.services.batch_coalescer import CoalesceCandidate, Priority

        original = CoalesceCandidate(
            batch_id="b1",
            camera_id="front",
            detection_ids=[1, 2, 3],
            object_types=["person", "vehicle"],
            avg_confidence=0.77,
            created_at=datetime.now(tz=UTC),
            priority=Priority.P0_CRITICAL,
        )
        restored = CoalesceCandidate.from_json(original.to_json())
        assert restored == original                      # field-wise dataclass eq
        assert restored.priority is Priority.P0_CRITICAL

        restored_bytes = CoalesceCandidate.from_json(original.to_json().encode("utf-8"))
        assert restored_bytes == original                # real redis decode_responses=False

        noprio = CoalesceCandidate(
            batch_id="b2",
            camera_id="front",
            detection_ids=[4],
            object_types=["person"],
            avg_confidence=0.5,
            created_at=datetime.now(tz=UTC),
        )
        assert CoalesceCandidate.from_json(noprio.to_json()).priority is None
```

Red logic: C12 field-None breaks dataclass eq; C13 silent priority loss breaks the
`is Priority.P0_CRITICAL`/eq asserts; C14 variants raise (ValueError/KeyError) — red by
exception; C11 renames/forced-null break eq on the payload side.

### T-F — kills C10 → `TestCandidateTracking`

```python
    @pytest.mark.asyncio
    async def test_remove_candidates_uses_exact_redis_keys(self) -> None:
        """Data keys deleted per batch id; camera set zrem'd; None-camera path
        resolves camera by reading the exact data key."""
        from backend.services.batch_coalescer import BatchCoalescer, CoalesceCandidate

        mock_redis = AsyncMock()
        coalescer = BatchCoalescer(redis_client=mock_redis)
        await coalescer.remove_candidates(["b1", "b2"], camera_id="front")
        mock_redis.delete.assert_any_await("coalesce:candidate:b1")
        mock_redis.delete.assert_any_await("coalesce:candidate:b2")
        mock_redis.zrem.assert_awaited_once_with("coalesce:candidates:front", "b1", "b2")

        # camera-less path: side_effect keyed by the *exact* requested key
        payload = CoalesceCandidate(
            batch_id="b1",
            camera_id="front",
            detection_ids=[1],
            object_types=["person"],
            avg_confidence=0.85,
            created_at=datetime.now(tz=UTC),
        ).to_json()
        mock_redis2 = AsyncMock()
        mock_redis2.get.side_effect = lambda key: (
            payload if key == "coalesce:candidate:b1" else None
        )
        coalescer2 = BatchCoalescer(redis_client=mock_redis2)
        await coalescer2.remove_candidates(["b1"])
        mock_redis2.get.assert_awaited_once_with("coalesce:candidate:b1")   # kills rm_8
        mock_redis2.delete.assert_awaited_once_with("coalesce:candidate:b1")  # kills rm_4/rm_13
        mock_redis2.zrem.assert_awaited_once_with("coalesce:candidates:front", "b1")
```

(The file's top-level import grows to `from unittest.mock import AsyncMock, MagicMock` — already present; no `call` needed with `assert_any_await`.)

## Priority ranking of drafted tests (highest kill-yield per line first)

1. T-C — 20 mutants (C7+C8+C9) + round-trip pressure on C11.
2. T-A — 22 mutants (C1–C5) — replaces the tautological assert at line 509.
3. T-E — 17 mutants (C11–C14) — one round-trip test.
4. T-D — 13 mutants (C15, C16).
5. T-B — 6 mutants (C6).
6. T-F — 3 mutants (C10).

Not drafted (no test warranted): C17/C18/C19/C21 (EQUIVALENT — log text/extra naming,
no consumer), C20 (LOW-VALUE).

## File references

- Original: `/agents/agent-nemo2/workspace/backend/services/batch_coalescer.py` (survivor lines: fc 429-499, reg 384-427, rm 501-552, get_metrics 648-665, to_json 123-135, from_json 137-151)
- Covering tests: `/agents/agent-nemo2/workspace/backend/tests/unit/services/test_batch_coalescer.py:464,486,512,527,624`
- Unasserted metric helpers: `/agents/agent-nemo2/workspace/backend/core/metrics.py:5111-5146`
- Raw per-mutant hunks: `/tmp/wp25/bc_survivor_deltas.txt` (key \t tag \t orig \t mutant)
