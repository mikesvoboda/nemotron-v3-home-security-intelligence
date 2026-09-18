# WP4.4 Triage Dossier — backend/services/prompt_service.py

- **Surviving mutants:** 142 (exit_code 0 in `mutants/backend/services/prompt_service.py.meta`)
- **Covering test files:**
  - `backend/tests/unit/services/test_prompt_ab_testing.py` (all PromptABTester / PromptShadowRunner / PromptRollbackChecker / PromptEvaluator functions; 1–5 tests per function)
  - `backend/tests/unit/services/test_prompt_service.py` (all PromptService functions; 1–4 tests per function)
- **Diff method:** manual variant-vs-`__mutmut_orig` diff from `mutants/backend/services/prompt_service.py` (trampoline layout, `xǁClassǁfunc__mutmut_N` defs). 142/142 extracted; mutmut show not needed.
- **Key structural weakness:** the A/B-testing tests mock at the wrong level — `create_evaluation_batch` mocks `session.execute` (so the SQL built is never examined), `compare_prompt_versions` mocks `evaluate_prompt_version` (so call args never checked), latency assertions are `>= 0` (so any latency formula survives), and `record_prompt_latency` is asserted `called_once()` without args.

## Cluster table (counts sum to 142)

| #   | Cluster                                                                                                                                                                                        | Count | Keys (≤3 examples)                                                                                            | Class      | Notes / covering test                                                                                                                                                                                         |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----- | ------------------------------------------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| C1  | `record_prompt_execution`: Prometheus label `f"v{version}"` / latency value replaced by `None`                                                                                                 | 2     | …record_prompt_execution\_\_mutmut_1, \_2                                                                     | TEST-GAP   | `test_prompt_ab_testing.py::TestPromptPerformanceMetrics::test_prompt_ab_tester_records_metrics` asserts only `mock_record.assert_called_once()` — never the label or value.                                  |
| C2  | `_calculate_correlation`: insufficient-sample guard `len(events) < 2` → `<= 2` / `< 3`                                                                                                         | 2     | …\_calculate_correlation\_\_mutmut_1, \_2                                                                     | TEST-GAP   | Only reached via `evaluate_prompt_version`; no direct test. 2-event batch silently returns None.                                                                                                              |
| C3  | `_calculate_correlation`: `getattr(e, "risk_score", 0)` missing-score default 0 → `1`/`None`/missing                                                                                           | 3     | …\_calculate_correlation\_\_mutmut_6, \_9, \_12                                                               | TEST-GAP   | Covering test's events are `MagicMock`s, which synthesize `risk_score`, so the default branch never executes meaningfully.                                                                                    |
| C4  | `_calculate_correlation`: NaN guard tautology — return `[0,1]`→`[1,1]` cell, `not isnan` → `… or True`                                                                                         | 2     | …\_calculate_correlation\_\_mutmut_19, \_22                                                                   | TEST-GAP   | NaN input and non-symmetric corrcoef matrices never fed in tests.                                                                                                                                             |
| C5  | `create_evaluation_batch`: cutoff computed as **future** timestamp — `- timedelta` → `+`, `datetime.now(None)` naive now                                                                       | 2     | …create_evaluation_batch\_\_mutmut_2, \_3                                                                     | TEST-GAP   | `test_create_evaluation_batch` mocks `session.execute` return; query WHERE clause never inspected (SQLite would still return rows for a future cutoff only if the filter is not evaluated against real data). |
| C6  | `create_evaluation_batch`: SQL shape — cutoff comparison `>=`→`>`, whole select-chainer → `None`, `.where(None)`, `.order_by(None)`, `.limit(None)`, `select(None)`                            | 6     | …create_evaluation_batch\_\_mutmut_6, \_7, \_8                                                                | TEST-GAP   | Same mock-session gap as C5: any argument swap passes because execute is faked. (m10 `select(None)` and m9 `.where(None)` also here.)                                                                         |
| C7  | `create_evaluation_batch`: `EvaluationBatch(created_at=…)` timestamp `UTC`→`None` (naive now)                                                                                                  | 1     | …create_evaluation_batch\_\_mutmut_18                                                                         | TEST-GAP   | Test asserts `batch.created_at is not None` only; naive vs aware never checked.                                                                                                                               |
| C8  | `evaluate_prompt_version`: `_run_prompt_for_event(prompt_version, event)` call args → `None`/dropped                                                                                           | 4     | …evaluate_prompt_version\_\_mutmut_6, \_7, \_8                                                                | TEST-GAP   | Covering test patches the method with AsyncMock but never asserts its call args — evaluator can query the wrong version/event.                                                                                |
| C9  | `evaluate_prompt_version`: missing-score defaults `result.get("risk_score", 0)` / `getattr(event, "risk_score", 0)` mutated (None, 1, key rename/drop)                                         | 10    | …evaluate_prompt_version\_\_mutmut_15, \_16, \_18 also \_19, \_20, \_21, \_23, \_25, \_28, \_31)              | TEST-GAP   | Mock results always contain `risk_score` and mock events always have it, so defaults never fire; key-text mutants would make every score silently 0-diff.                                                     |
| C10 | `evaluate_prompt_version`: latency math `* 1000` → `/ 1000`, `+ start_time`, `* 1001`; latencies accumulator → None                                                                            | 4     | …evaluate_prompt_version\_\_mutmut_3, \_11, \_12 (also \_13)                                                  | TEST-GAP   | `average_latency_ms` never asserted at all in `test_evaluate_prompt_version_against_batch`.                                                                                                                   |
| C11 | `evaluate_prompt_version`: results fields — `abs(new - orig)` → `abs(new + orig)`, `score_variance=None`/dropped, `average_latency_ms=None`/dropped, guard tautology `… if latencies else 0.0` | 8     | …evaluate_prompt_version\_\_mutmut_34, \_41, \_42 (also \_46, \_47, \_53; \_54, \_57 see classification note) | TEST-GAP   | Test asserts `average_score_diff is not None` — a tautological assertion; exact values never checked.                                                                                                         |
| C12 | `compare_prompt_versions`: `evaluate_prompt_version(session, version, batch)` call args → `None`/dropped                                                                                       | 12    | …compare_prompt_versions\_\_mutmut_2, \_3, \_4 (also \_5, \_6, \_7, \_9, \_10, \_11, \_12, \_13, \_14)        | TEST-GAP   | Covering test replaces `evaluate_prompt_version` with AsyncMock and never checks args — version_a/version_b swap invisible.                                                                                   |
| C13 | `compare_prompt_versions`: composite score `(avg_diff or 0) + (variance or 0)` operator/constant flips (`+`→`-`, `or`→`and`, `or 0`→`or 1`)                                                    | 8     | …compare_prompt_versions\_\_mutmut_16, \_17, \_18 (also \_19, \_20, \_23, \_24, \_26)                         | TEST-GAP   | Existing test's gap/variance values (2.5/10 vs 8/25) are too far apart — recommendation unchanged under every flip.                                                                                           |
| C14 | `compare_prompt_versions`: recommendation tie-break `score_a <= score_b` → `<` / `… or True`                                                                                                   | 2     | …compare_prompt_versions\_\_mutmut_29, \_30                                                                   | TEST-GAP   | No tie scenario; `or True` (always pick A) not exercised because B is always worse in tests.                                                                                                                  |
| C15 | `check_rollback_needed`: boundary comparisons `sample_count < min` → `<=`, `latency > max` → `>=`, `variance > max` → `>=`                                                                     | 3     | …check_rollback_needed\_\_mutmut_10, \_16, \_22                                                               | TEST-GAP   | Tests use metrics far from thresholds (150 vs 100, 75 vs 50) — boundary equality never probed.                                                                                                                |
| C16 | `check_rollback_needed`: "Rollback disabled" reason string → None/case/garble                                                                                                                  | 5     | …check_rollback_needed\_\_mutmut_3, \_5, \_7 also \_8, \_9)                                                   | TEST-GAP   | `test_rollback_disabled_no_action` asserts only `should_rollback is False`; never `result.reason` — API/UI surface for "why not rolled back" is untested.                                                     |
| C17 | `execute_rollback`: `_disable_ab_test` / `_log_rollback` args → `None`/dropped                                                                                                                 | 7     | …execute_rollback\_\_mutmut_1, \_2, \_3 (also \_4, \_5, \_6, \_7)                                             | TEST-GAP   | `test_execute_rollback` asserts `called_once()` on both, never with-args.                                                                                                                                     |
| C18 | `execute_rollback`: `record_prompt_rollback(model-if-hasattr, "performance")` — hasattr flips, model/type args → None, string-case/garble of `"nemotron"`/`"performance"`                      | 11    | …execute_rollback\_\_mutmut_8, \_9, \_12 (also \_13, \_14, \_18, \_19, \_20, \_21, \_22, \_23)                | TEST-GAP   | The metric call is not even patched/asserted in the existing test.                                                                                                                                            |
| C19 | `execute_rollback`: result `previous_version`/`new_version` → `None`/dropped                                                                                                                   | 4     | …execute_rollback\_\_mutmut_25, \_26, \_28 (also \_29)                                                        | TEST-GAP   | Test asserts `result.success is True` only; the version bookkeeping (audit trail of what was rolled back) unchecked.                                                                                          |
| C20 | `export_all_prompts`: `exported_at` timestamp `datetime.now(UTC)` → `datetime.now(None)` naive                                                                                                 | 1     | …export_all_prompts\_\_mutmut_8                                                                               | TEST-GAP   | Test checks key presence, never tz-awareness (breaks downstream ISO8601 parsers).                                                                                                                             |
| C21 | `get_all_prompts`: per-model config → `None` / `get_prompt_for_model(session, None)`                                                                                                           | 3     | …get_all_prompts\_\_mutmut_3, \_5, \_8                                                                        | TEST-GAP   | `test_get_all_prompts_returns_all_models` checks keys only — every value could be None and it passes.                                                                                                         |
| C22 | `get_version_history`: pagination — whole query chain → None, `.order_by(None)`, `.offset(None)`, `.limit(None)`                                                                               | 4     | …get_version_history\_\_mutmut_17, \_18, \_19 (also \_20)                                                     | TEST-GAP   | Mock session ignores the query entirely; ordering/pagination never verified.                                                                                                                                  |
| C23 | `get_version_history`: model filter `== model` → `!= model` / `where(None)` (both query and count query)                                                                                       | 5     | …get_version_history\_\_mutmut_7, \_8, \_9 (also \_10, \_11)                                                  | TEST-GAP   | Filtered result set never compared against unfiltered — flipped predicate returns the complement and nobody notices.                                                                                          |
| C24 | `get_version_history`: count plumbing — `select(None)`/`count(None)`/`execute(None)`/`scalar() or 1` fallback                                                                                  | 6     | …get_version_history\_\_mutmut_2, \_4, \_5 (also \_13, \_16, \_22)                                            | TEST-GAP   | Existing test's `total == 10` assertion kills _value_ changes, but arg-to-None mutants pass because `execute` is mocked.                                                                                      |
| C25 | `restore_version`: `PromptVersion.id == version_id` → `!=` / `where(None)` / `select(None)` / `execute(None)`                                                                                  | 4     | …restore_version\_\_mutmut_2, \_3, \_4 (also \_5)                                                             | TEST-GAP   | Not-found path is tested, but a flipped id predicate (restoring the _wrong_ version against a real DB) is not.                                                                                                |
| C26 | `restore_version`: forwarded `model=`/`config=` → `None`                                                                                                                                       | 2     | …restore_version\_\_mutmut_10, \_11                                                                           | TEST-GAP   | Test asserts new version number and description, not that model/config are the restored ones.                                                                                                                 |
| C27 | `PromptShadowRunner.__init__`: `get_logger(__name__)` → `get_logger(None)`                                                                                                                     | 1     | …PromptShadowRunnerǁ**init\_\_**mutmut_3                                                                      | LOW-VALUE  | Logger name changes; no test should assert it.                                                                                                                                                                |
| C28 | `run_shadow_comparison`: `control_latency_ms` / `shadow_latency_ms` math `* 1000` → `/ 1000`, `+ start`, `* 1001`                                                                              | 6     | …run_shadow_comparison\_\_mutmut_8, \_9, \_10 (also \_24, \_25, \_26)                                         | TEST-GAP   | Existing assertions are `assert result.control_latency_ms >= 0` — satisfied by any formula.                                                                                                                   |
| C29 | `run_shadow_comparison`: `_run_single_prompt(version, context)` call args → `None`/dropped                                                                                                     | 3     | …run_shadow_comparison\_\_mutmut_4, \_19, \_20                                                                | TEST-GAP   | Test asserts `call_count == 2` but never which version/context was passed — control/shadow swap undetected.                                                                                                   |
| C30 | `run_shadow_comparison`: missing-score defaults `control_result.get("risk_score", 0)` / `shadow_result…` mutated                                                                               | 6     | …run_shadow_comparison\_\_mutmut_31, \_33, \_36 (also \_39, \_41, \_44)                                       | TEST-GAP   | Mocked responses always carry `risk_score`; defaults never exercised — a missing key would crash on `None` subtraction (mutants \_31/\_39 actually flip risk_score_diff to exception path).                   |
| C31 | `run_shadow_comparison`: `ShadowComparisonResult(control_result=…, control_latency_ms=…)` kwarg dropped (silently defaults to 0.0/None) + `record_shadow_comparison(model)` → `None`           | 2     | …run_shadow_comparison\_\_mutmut_15, \_48                                                                     | TEST-GAP   | `control_latency_ms` silently 0; Prometheus metric loses its model label. Neither asserted.                                                                                                                   |
| C32 | `run_shadow_comparison`: log message argument → `None` (info + warning)                                                                                                                        | 2     | …run_shadow_comparison\_\_mutmut_49, \_52                                                                     | LOW-VALUE  | f-string→None inside `.info()/.warning()` — logging text only; warning still fires with the same control flow.                                                                                                |
| C33 | `check_rollback_needed`: `RollbackCheckResult(should_rollback=False, reason=None)` → `reason` kwarg dropped                                                                                    | 1     | …check_rollback_needed\_\_mutmut_30                                                                           | EQUIVALENT | `reason=None` is the dataclass default — byte-identical behavior.                                                                                                                                             |

**Totals:** TEST-GAP 138 (C1–C26, C28–C31) + LOW-VALUE 3 (C27, C32) + EQUIVALENT 1 (C33) = 142 + boundary-cluster note: C11 includes `_54` (`or True` guard) and `_57` (`else 1.0`) — the `latencies == [] with score_diffs != []` state is unreachable (`score_diffs` and `latencies` append in the same try block and `abs()` raises before either append on bad data), so those two are practically-equivalent but are kept in TEST-GAP C11 because the drafted test's exact-value asserts cover the whole field anyway.

## Drafted tests (UNVERIFIED — not yet run red/green)

TDD procedure for each: run the new test against the mutant source (or apply the cluster's one-line flip manually) → assertion must FAIL (RED); run against original `backend/services/prompt_service.py` → must PASS (GREEN).

### D1 — comparison scoring, tie-break and call plumbing (kills C12 + C13 + C14, 22 mutants)

Target file: `backend/tests/unit/services/test_prompt_ab_testing.py` (class `TestAutomatedEvaluation`)

```python
# UNVERIFIED - not yet run red/green
    @pytest.mark.asyncio
    async def test_compare_prompt_versions_scores_tie_break_and_plumbing(
        self, mock_session, sample_historical_events
    ):
        """Score = avg_diff + variance per version; tie keeps A; each version called with own args."""
        from backend.services.prompt_service import (
            EvaluationBatch,
            EvaluationResults,
            PromptEvaluator,
        )

        evaluator = PromptEvaluator()
        batch = EvaluationBatch(events=sample_historical_events, created_at=datetime.now(UTC))

        async def run_case(diff_a, var_a, diff_b, var_b):
            mock_eval = AsyncMock(
                side_effect=[
                    EvaluationResults(
                        total_events=3, average_score_diff=diff_a, score_variance=var_a
                    ),
                    EvaluationResults(
                        total_events=3, average_score_diff=diff_b, score_variance=var_b
                    ),
                ]
            )
            with patch.object(evaluator, "evaluate_prompt_version", mock_eval):
                comparison = await evaluator.compare_prompt_versions(
                    mock_session, 1, 2, batch
                )
            return comparison, mock_eval

        # Plumbing: version A then version B, with the caller's own session and batch
        _cmp, mock_eval = await run_case(2.5, 10.0, 8.0, 25.0)
        assert mock_eval.await_args_list == [
            call(mock_session, 1, batch),
            call(mock_session, 2, batch),
        ]

        # Tie (score_a == score_b == 12.5): original keeps version A (<=), '<' mutant picks B
        cmp_tie, _ = await run_case(2.5, 10.0, 7.5, 5.0)
        assert cmp_tie.recommended_version == 1

        # B genuinely better (12.5 vs 11): any score inflation/deflation of A flips this
        cmp_b, _ = await run_case(2.5, 10.0, 6.0, 5.0)
        assert cmp_b.recommended_version == 2

        # A better despite B's large avg_diff: 'and 0' mutant zeroes B's diff and flips to B
        cmp_a, _ = await run_case(1.0, 1.0, 8.0, 1.0)
        assert cmp_a.recommended_version == 1

        # falsy-field scenario: score_b = 0 + 0, score_a = 0.8 -> B; 'or 1' mutants -> A
        cmp_zero, _ = await run_case(0.8, 0.0, 0.0, 0.0)
        assert cmp_zero.recommended_version == 2
```

Also add to the imports at the top of `test_prompt_ab_testing.py`: `from unittest.mock import AsyncMock, MagicMock, call, patch` (add `call`).

Kill mapping: scenarios call 1→2→T→B→A→Z; plumbing list kills C12's twelve `_2/_3/_4/_5/_6/_7/_9/_10/_11/_12/_13/_14`; the T/B/A/Z recommendation asserts jointly kill every C13 flip (verified arithmetic per mutant: 16→B, 17→B, 18→B, 19→B, 20→B, 23→A-scenario, 24→Z, 26→Z) and C14's `_29` (B-scenario) and `_30` (T-scenario).

### D2 — correlation math, guards, defaults (kills C2 + C3 + C4, 7 mutants)

Target file: `backend/tests/unit/services/test_prompt_ab_testing.py` (class `TestAutomatedEvaluation`)

```python
# UNVERIFIED - not yet run red/green
    def test_calculate_correlation_values_and_guards(self):
        """Direct tests of _calculate_correlation: value, 2-event floor, missing-score default, NaN guard."""
        import math

        from backend.services.prompt_service import PromptEvaluator

        class Ev:
            def __init__(self, risk_score=None, has_score=True):
                if has_score:
                    self.risk_score = risk_score

        evaluator = PromptEvaluator()

        # Perfect linear relation -> +1.0
        events = [Ev(10), Ev(20), Ev(30)]
        assert evaluator._calculate_correlation(events, [5.0, 10.0, 15.0]) == pytest.approx(1.0)

        # Exactly 2 events must still produce a value ('< 3' / '<= 2' mutants return None)
        assert evaluator._calculate_correlation([Ev(10), Ev(20)], [5.0, 10.0]) is not None

        # Missing risk_score defaults to 0 -> corr([10,30,0],[5,35,90]) = -0.4809 (not 1.0 [1,1]-cell,
        # not -0.4584 default-1, not None/exception from default-None or 2-arg getattr)
        ev_no_score = [Ev(10), Ev(30), Ev(has_score=False)]
        value = evaluator._calculate_correlation(ev_no_score, [5.0, 35.0, 90.0])
        assert value is not None
        assert value == pytest.approx(-0.48089709037492606, abs=1e-6)

        # Constant score diffs -> corrcoef NaN -> guard must return None ('or True' mutant returns NaN)
        nan_result = evaluator._calculate_correlation([Ev(10), Ev(20)], [7.0, 7.0])
        assert nan_result is None  # original: NaN -> None; m22 'or True' -> float(NaN) fails this
```

### D3 — evaluation math: scores, latencies, output fields, call args (kills C8 + C9 + C10 + C11, 26 mutants — incl. the 2 practically-equivalent \_54/\_57)

Target file: `backend/tests/unit/services/test_prompt_ab_testing.py` (class `TestAutomatedEvaluation`)

```python
# UNVERIFIED - not yet run red/green
    @pytest.mark.asyncio
    async def test_evaluate_prompt_version_exact_metrics(self, mock_session):
        """Exact score-diff/variance/latency values, and prompt run receives (version, event)."""
        from backend.services.prompt_service import EvaluationBatch, PromptEvaluator

        class Ev:
            def __init__(self, id_, risk_score=None, has_score=True):
                self.id = id_
                if has_score:
                    self.risk_score = risk_score

        events = [Ev(1, 50), Ev(2, 75)]
        batch = EvaluationBatch(events=events, created_at=datetime.now(UTC))

        evaluator = PromptEvaluator()
        mock_run = AsyncMock(side_effect=[{"risk_score": 60}, {"risk_score": 90}])

        # time.monotonic(): start1=100.0 end1=100.25 start2=200.0 end2=200.5 -> latencies 250/500 ms
        with (
            patch.object(evaluator, "_run_prompt_for_event", mock_run),
            patch(
                "backend.services.prompt_service.time.monotonic",
                side_effect=[100.0, 100.25, 200.0, 200.5],
            ),
        ):
            results = await evaluator.evaluate_prompt_version(
                session=mock_session, prompt_version=2, batch=batch
            )

        # Each prompt run receives the requested version and the actual event
        assert mock_run.await_args_list == [call(2, events[0]), call(2, events[1])]

        # diffs = [|60-50|, |90-75|] = [10, 15]
        assert results.total_events == 2
        assert results.average_score_diff == pytest.approx(12.5)  # kills +-flip, key renames, defaults
        assert results.score_variance == pytest.approx(6.25)  # kills score_variance None/dropped
        assert results.average_latency_ms == pytest.approx(375.0, abs=0.1)  # kills /1000, +start, *1001

        # Missing risk_score in a prompt result -> defaults to 0, event still counted
        evaluator2 = PromptEvaluator()
        mock_run2 = AsyncMock(side_effect=[{"risk_score": 60}, {}])
        with (
            patch.object(evaluator2, "_run_prompt_for_event", mock_run2),
            patch(
                "backend.services.prompt_service.time.monotonic",
                side_effect=[0.0, 0.01, 0.0, 0.02],
            ),
        ):
            results2 = await evaluator2.evaluate_prompt_version(
                session=mock_session, prompt_version=2, batch=batch
            )
        assert results2.total_events == 2  # default-None/getattr-None mutants skip the event
        assert results2.average_score_diff == pytest.approx(42.5)  # [10, 75]; default-1 mutant gives 42.0

        # Event missing risk_score -> event-side default 0: diffs [10, 70] -> mean 40
        events3 = [Ev(1, 50), Ev(2, has_score=False)]
        batch3 = EvaluationBatch(events=events3, created_at=datetime.now(UTC))
        evaluator3 = PromptEvaluator()
        mock_run3 = AsyncMock(side_effect=[{"risk_score": 60}, {"risk_score": 70}])
        with (
            patch.object(evaluator3, "_run_prompt_for_event", mock_run3),
            patch(
                "backend.services.prompt_service.time.monotonic",
                side_effect=[0.0, 0.01, 0.0, 0.01],
            ),
        ):
            results3 = await evaluator3.evaluate_prompt_version(
                session=mock_session, prompt_version=2, batch=batch3
            )
        # getattr default-1 mutant -> [10, 69] mean 39.5; default-None -> event skipped, total 1
        assert results3.total_events == 2
        assert results3.average_score_diff == pytest.approx(40.0)
```

Requires adding `call` to the mock imports (same edit as D1).

### D4 — rollback thresholds at the boundary + reason strings (kills C15 + C16, 7 mutants)

Target file: `backend/tests/unit/services/test_prompt_ab_testing.py` (class `TestRollbackTrigger`)

```python
# UNVERIFIED - not yet run red/green
    @pytest.mark.asyncio
    async def test_check_rollback_exact_threshold_boundaries(self, rollback_config):
        """Metrics exactly AT the thresholds must NOT roll back; disabled path names the reason."""
        from backend.services.prompt_service import PromptRollbackChecker

        checker = PromptRollbackChecker(rollback_config)

        # sample_count == min_samples (100): proceeds, clean metrics -> reason None ('<=' mutant: 'Insufficient')
        result = await checker.check_rollback_needed(
            MagicMock(latency_increase_pct=10.0, score_variance=10.0, sample_count=100)
        )
        assert result.should_rollback is False
        assert result.reason is None

        # latency exactly at max (50.0): no rollback ('>=' mutant rolls back)
        result = await checker.check_rollback_needed(
            MagicMock(latency_increase_pct=50.0, score_variance=10.0, sample_count=150)
        )
        assert result.should_rollback is False

        # variance exactly at max (15.0): no rollback ('>=' mutant rolls back)
        result = await checker.check_rollback_needed(
            MagicMock(latency_increase_pct=10.0, score_variance=15.0, sample_count=150)
        )
        assert result.should_rollback is False

    @pytest.mark.asyncio
    async def test_check_rollback_disabled_reports_reason_text(self, rollback_config):
        """Disabled rollback must explain itself with the exact reason string."""
        from backend.services.prompt_service import PromptRollbackChecker

        rollback_config.enabled = False
        checker = PromptRollbackChecker(rollback_config)

        result = await checker.check_rollback_needed(
            MagicMock(latency_increase_pct=100.0, score_variance=50.0, sample_count=1000)
        )
        assert result.should_rollback is False
        assert result.reason == "Rollback disabled"
```

### D5 — rollback execution plumbing + version bookkeeping (kills C17 + C18 + C19, 22 mutants)

Target file: `backend/tests/unit/services/test_prompt_ab_testing.py` (class `TestRollbackTrigger`)

```python
# UNVERIFIED - not yet run red/green
    @pytest.mark.asyncio
    async def test_execute_rollback_full_plumbing(self, rollback_config):
        """Disable/log/metric calls carry the right args and result records both versions."""
        from backend.services.prompt_service import PromptRollbackChecker

        from types import SimpleNamespace

        checker = PromptRollbackChecker(rollback_config)
        mock_session = AsyncMock()
        # NOTE: a REAL object (not MagicMock — mock auto-creates any attribute, which would
        # let renamed-hasattr mutants m18/m19 survive) whose model is deliberately
        # NON-default ("test-model") so every hasattr/arg mutant that forces the
        # "nemotron" fallback is caught by the metric assert.
        mock_ab_config = SimpleNamespace(
            control_version=1, treatment_version=2, enabled=True, model="test-model"
        )

        with (
            patch.object(checker, "_disable_ab_test", AsyncMock()) as mock_disable,
            patch.object(checker, "_log_rollback", MagicMock()) as mock_log,
            patch("backend.core.metrics.record_prompt_rollback", autospec=True) as mock_metric,
        ):
            result = await checker.execute_rollback(
                session=mock_session,
                ab_config=mock_ab_config,
                reason="High latency detected",
            )

        assert result.success is True
        mock_disable.assert_called_once_with(mock_ab_config)  # kills None/dropped config
        mock_log.assert_called_once_with(1, 2, "High latency detected")  # kills arg mutants
        mock_metric.assert_called_once_with("test-model", "performance")  # kills hasattr/arg mutants
        assert result.previous_version == 2  # rolled back FROM treatment
        assert result.new_version == 1  # now active is control

    @pytest.mark.asyncio
    async def test_execute_rollback_without_model_attr_defaults_nemotron(self, rollback_config):
        """A config lacking .model must fall back to the exact string 'nemotron'."""
        from types import SimpleNamespace

        from backend.services.prompt_service import PromptRollbackChecker

        checker = PromptRollbackChecker(rollback_config)
        bare_config = SimpleNamespace(control_version=4, treatment_version=9)

        with (
            patch.object(checker, "_disable_ab_test", AsyncMock()),
            patch.object(checker, "_log_rollback", MagicMock()),
            patch("backend.core.metrics.record_prompt_rollback", autospec=True) as mock_metric,
        ):
            result = await checker.execute_rollback(
                session=AsyncMock(), ab_config=bare_config, reason="manual"
            )

        assert result.success is True
        mock_metric.assert_called_once_with("nemotron", "performance")
        assert (result.previous_version, result.new_version) == (9, 4)
```

Note: the first test's `SimpleNamespace` has a real `model` attr, so `hasattr(ab_config, "model")` is True and `hasattr → None/"XXmodelXX"/"MODEL"` mutants all flip to the `"nemotron"` fallback — caught by asserting `("test-model", "performance")`. The second test (bare SimpleNamespace without `model`) covers the opposite branch, killing the `"XXnemotronXX"`/`"NEMOTRON"` fallback-string mutants. Together they kill all 11 C18 mutants.

### D6 — evaluation-batch query shape (kills C5 + C6 + C7, 10 mutants)

Target file: `backend/tests/unit/services/test_prompt_ab_testing.py` (class `TestAutomatedEvaluation`)

```python
# UNVERIFIED - not yet run red/green
    @pytest.mark.asyncio
    async def test_create_evaluation_batch_query_shape(self, mock_session, sample_historical_events):
        """The SQL actually built: inclusive recent-window filter, newest-first, bounded sample,
        tz-aware batch timestamp."""
        from backend.models.event import Event
        from backend.services.prompt_service import PromptEvaluator

        mock_result = MagicMock()
        mock_result.scalars = MagicMock(
            return_value=MagicMock(all=MagicMock(return_value=sample_historical_events))
        )
        mock_session.execute.return_value = mock_result

        evaluator = PromptEvaluator()
        batch = await evaluator.create_evaluation_batch(
            session=mock_session, hours_back=24, sample_size=10
        )

        # Inspect the SELECT the service actually compiled against the events table
        (statement,) = mock_session.execute.await_args.args
        compiled = statement.compile(compile_kwargs={"literal_binds": True})
        sql = str(compiled)
        cutoff = list(compiled.params.values())[0] if compiled.params else None
        if cutoff is None:  # literal_binds inlined the bound value instead
            import re

            m = re.search(r"started_at >= ([\d\- :.]+)", sql)
            cutoff = datetime.fromisoformat(m.group(1).strip())

        assert "events" in sql
        assert "started_at >=" in sql  # inclusive window: kills '>' flip and where(None)
        assert "ORDER BY" in sql and "DESC" in sql  # kills order_by(None)
        assert "LIMIT" in sql  # kills limit(None)
        assert cutoff is not None and cutoff < datetime.now(UTC)  # kills '- timedelta' -> '+'
        assert cutoff.tzinfo is not None  # kills datetime.now(None) at the cutoff

        # Batch timestamp must be tz-aware (datetime.now(None) mutant produces naive datetime)
        assert batch.created_at is not None and batch.created_at.tzinfo is not None
```

Notes: `compiled.params` may be empty when `literal_binds=True` inlines the value (the regex fallback handles that); whichever path fires, the cutoff direction + inclusivity + tz-awareness asserts are the load-bearing ones. The `select(None)`/chain-to-`None` mutants (m6, m10) make `str(statement.compile(...))` or the `.args` destructure itself fail, so they are killed by the same test. If SQLAlchemy emits `events_1` aliasing, the `"events" in sql` substring still matches.

## Kill-coverage summary

| Drafted test               | Clusters killed  | Mutants                                                                |
| -------------------------- | ---------------- | ---------------------------------------------------------------------- |
| D1                         | C12, C13, C14    | 22                                                                     |
| D2                         | C2, C3, C4       | 7                                                                      |
| D3                         | C8, C9, C10, C11 | 26 (incl. 2 practically-equivalent, \_54/\_57, that fall out for free) |
| D4                         | C15, C16         | 8                                                                      |
| D5                         | C17, C18, C19    | 22                                                                     |
| D6                         | C5, C6, C7       | 9                                                                      |
| **total drafted coverage** |                  | **94 / 142**                                                           |

Remaining TEST-GAP mutants with no drafted test yet: C1 (record label, 2 — trivial `assert_called_once_with(f"v{version}", latency_seconds)` extension), C20 (export tz-awareness, 1 — assert `datetime.fromisoformat(export["exported_at"]).tzinfo is not None`), C21 (get_all_prompts values, 3 — extend `test_get_all_prompts_returns_all_models` to assert `prompts["nemotron"]["system_prompt"]`), C22–C26 (get_version_history/restore_version SQL shape + forwarding, 21 — need compiled-SQL asserts mirroring D6, or a real-DB integration test; the mocked-session unit style cannot see these), C28–C31 (shadow runner plumbing, 17 — mirror D3's monotonic-patch + `await_args_list` asserts against `_run_single_prompt`, and assert `result.control_latency_ms == pytest.approx(expected)`). LOW-VALUE (3) and EQUIVALENT (1) are intentionally not killed.
