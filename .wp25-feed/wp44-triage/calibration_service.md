# WP4.4 Triage Dossier — `backend/services/calibration_service.py`

- **Survivors:** 111 of 427 mutants (from `mutants/backend/services/calibration_service.py.meta`, exit_code == 0)
- **Method:** each surviving `*__mutmut_N` variant body was diffed against its `*__mutmut_orig` twin inside
  `mutants/backend/services/calibration_service.py` (manual diff path — `mutmut run` never invoked, cache untouched).
  Every TEST-GAP claim below was validated by hand-tracing a concrete input through original vs mutant;
  every EQUIVALENT claim has a stated absorption argument. **No tests were run (harness constraint) — all kill
  predictions are UNVERIFIED.**
- **Covering tests:** all five survivor functions map to `backend/tests/unit/services/test_calibration_service.py`
  (per `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`). That single file, 1040 lines, is the whole
  test surface. Mock-session style (AsyncMock + scalar_one_or_none) throughout.
- **Tally:** EQUIVALENT 75 · TEST-GAP 27 · LOW-VALUE 9 (= 111)

## The headline finding: `_apply_adjustment`'s constraint chain is self-absorbing

The function clamps every threshold twice and cascades ordering between: early `max(0, min(100, x))` (lines 488–490),
order cascade (494/496), a new_high>100 push-down branch (499–508), a `new_low < 0` push-up branch (511–520), and a
**final** clamp `low≤90 / medium∈[5,95] / high∈[10,100]` (523–525). Hand trace proves the effective function is:

```
L = min(90, clamp(r_low, 0, 100))
M = clamp(max(L_raw + 5, clamp(r_med, 0, 100)), 5, 95)      # cascade
H = clamp(max(M + 5, clamp(r_high, 0, 100)), 10, 100)       # cascade
```

— the two middle branches never change the final output when they run (verified: branch fires ⟺ medium ≥ 96 and
its output ≡ what the final clamps alone would give; the `new_low < 0` branch is **dead code** — the first clamp
makes it unreachable and the only other writer (line 508) floors at min(90,·) ≥ 0). Consequence: **21 of the 26
`_apply_adjustment` survivors are true equivalents** (bound widenings, branch-arithmetic flips, guard off-by-ones)
that no input can distinguish. Only 5 are killable (cluster C7). This over-constraint is itself a WP4.4 signal:
the redundant branches are untestable by construction and candidates for simplification, not for tests.

## Cluster table (authoritative; n sums to 111)

Keys are mutant numbers within the function; full key = `backend.services.calibration_service.xǁCalibrationServiceǁ<fn>__mutmut_<n>`.
"Covering test" line refs are in `backend/tests/unit/services/test_calibration_service.py`.

| id  | fn                   | pattern                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | n   | keys                | class      | judgment                                                                                                                                                                                                                                                                                                                                                           |
| --- | -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --- | ------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| C1  | get_thresholds       | query-construction clobbers: `stmt=None`, `where(None)`, `select(None)`, `==`→`!=`, `execute(None)`                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | 5   | 1, 2, 3, 4, 6       | EQUIVALENT | every variant raises (AttributeError/SQL compile) before any observable return — self-crashing, no behavior to assert; under the mocked-session test style they're unkillable by design                                                                                                                                                                            |
| C2  | get_thresholds       | `is_calibrated = fp>0 or mt>0` → `and`, `fp>1`, `mt>1`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | 3   | 19, 21, 23          | TEST-GAP   | covered at :187 (3+2 → True) and :217 (0+0 → False); **no test with exactly one counter == 1**, so `and`/`>1` survive. Real behavior (any single feedback = calibrated)                                                                                                                                                                                            |
| C3  | calculate_adjustment | no-op guard widenings `base<1`→`<=1`/`<2` (clamp body is the constant 1)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | 2   | 8, 9                | EQUIVALENT | guard body `base_adjustment = 1`: firing at base∈{0,1} yields 1 either way — no input distinguishes                                                                                                                                                                                                                                                                |
| C4  | calculate_adjustment | magnitude & boundary constants: base `10`→`11` (4); min-adjust guard `df>0`→`df>1` (7), clamp body `1`→`2` (11); FP floor `1.0`→`2.0` (32), MT floor `1.0`→`2.0` (54); `/50.0`→`*50.0` (33,55); score consts `50→51`×2, `100→101` (34,57,58); SW `//2`→`//3` (84), SW `//2`→`/2` float leak (83 — real value change: base=5 → delta 2.5 vs 2 at df=0.5); SW zero-decay branch `>0`→`>=0`/`or True`/`else 1` (77,85,87); SW direction boundary `>=50`→`>50`/`>=51` (88,89)                                                                                                   | 17  | 4, 7, 32, 84, 88    | TEST-GAP   | every existing test asserts signs/inequalities (`> 0`, `>= 0`, `abs(sw) <= abs(fp)`) with scores 25/50/75/90 and decay 0/0.01/0.1/0.5/1.0 — a hand-built exact-value table (Draft 1) kills all 17; e.g. FP(30, df=0.1) orig 1 vs floor-mutant 2; SW(50, 0.5) orig +2 vs boundary mutants −2 / float 2.5; SW(75, 0.0) orig 0 vs 1; MT(50, 1.0) orig −10 vs `/51` −9 |
| C5  | calculate_adjustment | `original_risk_score=risk_score` → `None` in all 5 return branches                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | 5   | 17, 42, 66, 94, 104 | LOW-VALUE  | pass-through field only consumed by the log payload (`adjustment.to_dict()`); no caller behavior depends on it; `test_adjustment_to_dict` builds the dataclass directly. A `to_dict`-through-`calculate_adjustment` smoke check is nearly tautological; not drafted as a priority (note: Draft 1's trailing assert kills them for free)                            |
| C6  | \_apply_adjustment   | absorbed by the redundant chain: bound widenings `min(100→101)` early×3 + final (17,28,39,90,103,115), `100−2/G=99.6` (91), early lower clamps `max(0→1)` on medium/high (23,34 — cascade `max(low+5,·)` dominates), overflow-guard `>100→>=100`/`>101` (52,53), overflow arithmetic `+100`→`−101`, sign flips `+overflow`/`+G` (56,64,70), low-cascade sign (76 — final `min(90,·)` absorbs), dead underflow guard `<0→<=0/<1` (77,78), final caps/floors `min(100,low)`/`min(100−3G… no — see C7 for 92` (89,90,91), final medium cap (102), final high floor `2/G` (109) | 21  | 17, 52, 76          | EQUIVALENT | full absorption proofs per key in the "chain" section above; canonical check: (50,75,90)+(+50,+50,+50) → orig (90,95,100) == min(101)-variant; (0,50,60)+0 unaffected by `2/G` floor since high ≥ medium+5 ≥ 10 always                                                                                                                                             |
| C7  | \_apply_adjustment   | reachable boundary values: early low clamp `max(0→1)` (12), final low clamp `max(0→1)` (84), overflow `overflow=new_high+100` (55), final low cap `min(90→85)` (92), final high floor `2G→3G` (110)                                                                                                                                                                                                                                                                                                                                                                         | 5   | 12, 55, 84          | TEST-GAP   | killable rows traced: (10,40,70,−50) → orig (0,5,20) vs 12:(1,6,20), 84:(1,5,20); (95,100,100,+0) → orig (90,95,100) vs 55:(0,5,100); (90,95,100,+0) → orig (90,95,100) vs 92:(85,95,100); (0,5,12,+0) → orig (0,5,12) vs 110:(0,5,15). Existing asserts are all inequality-style (`>= 0`, `<= 100`, `new_low < new_medium < new_high`) which every mutant passes  |
| C8  | reset_calibration    | logger-only edits: message clobbers/None/case, `extra=None`/removal, extra-key renames, `old_thresholds=None` (feeds only the log line)                                                                                                                                                                                                                                                                                                                                                                                                                                     | 15  | 6, 18, 22           | EQUIVALENT | pure log content; no caplog assertions anywhere in the test file; nobody should assert these strings                                                                                                                                                                                                                                                               |
| C9  | adjust_from_feedback | logger-only edits (warning + info message clobbers, extra dict None/remove/rename ×2 dicts), `decay_factor=` kwarg dropped (restored via default when calibration at default decay), `old_thresholds=None`                                                                                                                                                                                                                                                                                                                                                                  | 32  | 12, 51, 57          | EQUIVALENT | same as C8. Kwarg mutant 25 is a corner equivalent: only diverges for calibrations with decay_factor ≠ 0.1 — production never has one (model default + reset both set 0.1), and the default arg re-derives the value for every reachable input                                                                                                                     |
| C10 | adjust_from_feedback | counter updates `+= 1` → `= 1` (false_positive branch, missed_threat branch)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | 2   | 43, 47              | TEST-GAP   | both existing tests (:730, :775) start counts at 0 where `+=1 ≡ =1`; **no accumulation test** — a second feedback with prior count > 0 kills both (Draft 3)                                                                                                                                                                                                        |
| C11 | adjust_from_feedback | `updated_at = datetime.now(UTC)` → `None` / `now(None)` (naive)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | 2   | 40, 41              | LOW-VALUE  | nullable non-deterministic timestamp; behavior contract is "a value is set"; a freezegun smoke test is optional polish, not drafted                                                                                                                                                                                                                                |
| C12 | adjust_from_feedback | `get_or_create_calibration(db, user_id)` → `db, None` / kwarg omitted                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | 2   | 3, 5                | LOW-VALUE  | single-user deployment (CLAUDE.md auth model) always passes `"default"`, so `None`→default default makes them indistinguishable in production; multi-user routing is explicitly future work                                                                                                                                                                        |

Arithmetic: 5+3+2+17+5+21+5+15+32+2+2+2 = **111**. Classes: E = 5+2+21+15+32 = **75** · TG = 3+17+5+2 = **27** · LV = 5+2+2 = **9**.

## Drafted tests (WP4.4 candidates)

All go in `backend/tests/unit/services/test_calibration_service.py`, matching its class/parametrize style.
**UNVERIFIED — not yet run red/green** (execution forbidden this session). TDD procedure, one line: paste the
mutant's one-line diff into `backend/services/calibration_service.py`, run the new test → must FAIL; revert → must PASS.

### Draft 1 — exact-delta table for `calculate_adjustment` (kills C4 = 17; trailing assert also kills C5 = 5)

```python
    @pytest.mark.parametrize(
        ("feedback_type", "risk_score", "decay_factor", "expected_delta"),
        [
            # FALSE_POSITIVE: delta = int(int(10*df) * max(1.0, score/50.0)); floor 1 for 0 < df < 0.1
            (FeedbackType.FALSE_POSITIVE, 30, 0.1, 1),    # kills 32 (max(2.0,...) -> 2)
            (FeedbackType.FALSE_POSITIVE, 30, 0.05, 1),   # kills 7 (df>1 guard -> 0), 11 (clamp body 2 -> 2)
            (FeedbackType.FALSE_POSITIVE, 30, 0.19, 1),   # kills 4 (int(11*0.19)=2 -> 2)
            (FeedbackType.FALSE_POSITIVE, 55, 1.0, 11),   # kills 33 (*50 -> 27500), 34/58 (/51.0 -> 10)
            # MISSED_THREAT: delta = -int(int(10*df) * max(1.0, (100-score)/50.0))
            (FeedbackType.MISSED_THREAT, 45, 1.0, -11),   # kills 54 (floor 2.0 -> -20), 55 (*50)
            (FeedbackType.MISSED_THREAT, 1, 1.0, -19),    # kills 57 ((101-score)/50 -> -20)
            (FeedbackType.MISSED_THREAT, 50, 1.0, -10),   # kills 58 ((100-score)/51.0 -> -9)
            # SEVERITY_WRONG: +/- max(1, base//2) when df > 0, else 0; direction flips at score 50
            (FeedbackType.SEVERITY_WRONG, 75, 1.0, 5),    # kills 84 (//3 -> 3)
            (FeedbackType.SEVERITY_WRONG, 75, 0.5, 2),    # kills 83 (/2 -> 2.5)
            (FeedbackType.SEVERITY_WRONG, 50, 0.5, 2),    # kills 88 (>50 -> -2), 89 (>=51 -> -2)
            (FeedbackType.SEVERITY_WRONG, 75, 0.0, 0),    # kills 77 (or True -> +1), 85 (>=0 -> +1), 87 (else 1 -> +1)
        ],
    )
    def test_calculate_adjustment_exact_values(
        self,
        feedback_type: FeedbackType,
        risk_score: int,
        decay_factor: float,
        expected_delta: int,
    ) -> None:
        """Every magnitude/boundary constant in calculate_adjustment pinned by exact delta."""
        service = CalibrationService()
        adjustment = service.calculate_adjustment(
            feedback_type=feedback_type,
            risk_score=risk_score,
            decay_factor=decay_factor,
        )
        assert adjustment.low_delta == expected_delta
        assert adjustment.medium_delta == expected_delta
        assert adjustment.high_delta == expected_delta
        assert adjustment.original_risk_score == risk_score
```

(Add inside `class TestCalculateAdjustment`, after `test_severity_wrong_smaller_than_false_positive` at ~:453.)

### Draft 2 — `_apply_adjustment` exact outputs at reachable boundaries (kills C7 = 5)

```python
    @pytest.mark.parametrize(
        ("low", "medium", "high", "delta", "expected"),
        [
            # First clamp floors low at exactly 0 — mutants raising the floor shift the whole tuple.
            (10, 40, 70, -50, (0, 5, 20)),   # kills 12 (early max(1,..) -> (1,6,20)), 84 (final max(1,..) -> (1,5,20))
            # Overflow branch fires (medium hits 100): push-down must land on (90, 95, 100).
            (95, 100, 100, 0, (90, 95, 100)),  # kills 55 (overflow=new_high+100 -> (0,5,100))
            # Low at its final cap exactly: min(100-2*GAP) must leave 90.
            (90, 95, 100, 0, (90, 95, 100)),  # kills 92 (min(100-3*GAP,..) -> 85)
            # High between floors: 2*GAP floor must not lift 12.
            (0, 5, 12, 0, (0, 5, 12)),  # kills 110 (3*GAP floor -> 15)
        ],
    )
    def test_apply_adjustment_exact_boundaries(
        self,
        low: int,
        medium: int,
        high: int,
        delta: int,
        expected: tuple[int, int, int],
    ) -> None:
        """Constraint outputs pinned exactly at the clamp/cascade boundaries inequality tests miss."""
        service = CalibrationService()
        adjustment = ThresholdAdjustment(
            low_delta=delta,
            medium_delta=delta,
            high_delta=delta,
            feedback_type=FeedbackType.FALSE_POSITIVE if delta >= 0 else FeedbackType.MISSED_THREAT,
            original_risk_score=50,
        )
        assert service._apply_adjustment(low, medium, high, adjustment) == expected
```

(Inside `class TestApplyAdjustment`. Row traces were hand-verified against the original: e.g. (95,100,100)+0 →
cascades medium=100, high=105 → overflow 5 → (min(90,95),95,100)=(90,95,100), finals no-ops.)

### Draft 3 — feedback counters accumulate (kills C10 = 2)

```python
    @pytest.mark.asyncio
    async def test_feedback_counts_accumulate(self) -> None:
        """Repeated feedback must increment counts, never pin them to 1."""
        service = CalibrationService()

        from backend.models.user_calibration import UserCalibration

        calibration = UserCalibration(
            id=1,
            user_id="test_user",
            low_threshold=30,
            medium_threshold=60,
            high_threshold=85,
            decay_factor=0.1,
            false_positive_count=5,
            missed_threat_count=4,
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = calibration
        mock_session.execute.return_value = mock_result

        from backend.models.event import Event
        from backend.models.event_feedback import EventFeedback

        mock_event = MagicMock(spec=Event)
        mock_event.id = 1
        mock_event.risk_score = 75

        mock_feedback = MagicMock(spec=EventFeedback)
        mock_feedback.feedback_type = FeedbackType.FALSE_POSITIVE
        result = await service.adjust_from_feedback(
            mock_session, mock_feedback, mock_event, "test_user"
        )
        assert result.false_positive_count == 6  # mutant `= 1` yields 1

        mock_feedback.feedback_type = FeedbackType.MISSED_THREAT
        result = await service.adjust_from_feedback(
            mock_session, mock_feedback, mock_event, "test_user"
        )
        assert result.missed_threat_count == 5  # mutant `= 1` yields 1
```

(Inside `class TestAdjustFromFeedback`.)

### Draft 4 — `is_calibrated` with a single feedback counter (kills C2 = 3)

```python
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("false_positive_count", "missed_threat_count"),
        [
            (1, 0),  # kills `and` mutant (False) and fp>1 mutant (False)
            (0, 1),  # kills `and` mutant (False) and mt>1 mutant (False)
        ],
    )
    async def test_is_calibrated_true_with_single_counter(
        self,
        false_positive_count: int,
        missed_threat_count: int,
    ) -> None:
        """Any feedback (exactly one on either counter) marks the user calibrated."""
        service = CalibrationService()

        from backend.models.user_calibration import UserCalibration

        calibration = UserCalibration(
            id=1,
            user_id="test_user",
            low_threshold=30,
            medium_threshold=60,
            high_threshold=85,
            decay_factor=0.1,
            false_positive_count=false_positive_count,
            missed_threat_count=missed_threat_count,
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = calibration
        mock_session.execute.return_value = mock_result

        thresholds = await service.get_thresholds(mock_session, "test_user")
        assert thresholds.is_calibrated is True
```

(Inside `class TestGetThresholds`, next to `test_get_thresholds_not_calibrated_when_no_feedback` at :217.)

## Kill arithmetic for WP4.4

| Draft     | Kills                                   |
| --------- | --------------------------------------- |
| 1         | C4 (17) + C5 for free (5)               |
| 2         | C7 (5)                                  |
| 3         | C10 (2)                                 |
| 4         | C2 (3)                                  |
| **Total** | **27/27 TEST-GAP (+5 LOW-VALUE bonus)** |

Remaining survivors (75 EQUIVALENT + 4 LOW-VALUE) are not test-killable / not worth killing: C1 crashes itself,
C3/C6 are provably input-indistinguishable (C6's absorption is also a code-simplification candidate — two
redundant clamp passes plus a dead underflow branch worth flagging to the module owner), C8/C9 are log-text,
C11/C12 are non-deterministic timestamp and single-user-only parameters.
