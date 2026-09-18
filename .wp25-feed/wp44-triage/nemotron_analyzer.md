# WP4.4 Triage Dossier — backend/services/nemotron_analyzer.py

- **Survivors:** 125 of 3511 mutants (meta: `mutants/backend/services/nemotron_analyzer.py.meta`, exit_code 0)
- **Functions involved:** `_extract_json_objects` (43), `NemotronAnalyzer.warmup` (49), `NemotronAnalyzer._get_enrichment_result` (21), `NemotronAnalyzer.analyze_batch_streaming` (6), `NemotronAnalyzer.get_warmth_state` (5), `NemotronAnalyzer.record_rollout_feedback` (1)
- **Verdict split:** TEST-GAP 80 · EQUIVALENT 25 · LOW-VALUE 20
- Diff source: `uv run mutmut show <key>` for all 125 keys (re-collected after a `/tmp` collision with a sibling agent clobbered the first `all-diffs.txt`; verified zero foreign-module lines in the final capture, with `warmup__mutmut_9` fetched individually).

## Covering tests (from `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`)

| Function                  | Covering tests                                                                                                                                                                                                                                                                                                                                              |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `_extract_json_objects`   | `test_nemotron_analyzer.py:291 test_parse_llm_response_with_extra_text`, `:312 ..._no_json`, `:320 ..._invalid_json`, `:333 ..._missing_required_fields`, `:1625 ..._multiple_json_objects`, `:1757-1806` region (`test_call_llm_invalid_json_in_response`), `test_nemotron_guided_json.py::TestFallbackParsing::test_parse_llm_response_raises_on_no_json` |
| `warmup`                  | `test_nemotron_analyzer.py:3803 test_warmup_success`, `:3820 test_warmup_failure`, `:3833 test_warmup_disabled`; `test_model_warmup.py:141 test_warmup_on_startup_success`, `:154 ..._failure`                                                                                                                                                              |
| `get_warmth_state`        | `test_nemotron_analyzer.py:3724/:3731/:3740` (cold/warm/warming); `test_model_warmup.py:184/:193/:203`                                                                                                                                                                                                                                                      |
| `_get_enrichment_result`  | `test_nemotron_analyzer.py:2342 test_get_enrichment_result_returns_failed_tracking_on_failure`, `:2386 ..._none_when_disabled`                                                                                                                                                                                                                              |
| `analyze_batch_streaming` | `test_nemotron_analyzer.py:4397 test_analyze_batch_streaming_delegates_to_streaming_module`                                                                                                                                                                                                                                                                 |
| `record_rollout_feedback` | `test_nemotron_analyzer.py:4909 ..._no_rollout_manager`, `:4918 ..._control_group`                                                                                                                                                                                                                                                                          |

## Why the extractor survivors are the big fish

`_extract_json_objects` (backend/services/nemotron_analyzer.py:159-198) is only reached from `_parse_llm_response` (:4257-4346) **after** the fast-path `json.loads` fails, and its failure is masked by TWO further fallbacks: truncation recovery (:4321-4335) and the legacy `_JSON_PATTERN` regex (:4338-4344). Every surviving test either hits the fast path or gets rescued by the regex, so no test ever makes the balanced-brace scanner load-bearing. 37 of the 43 survivors are real scanner breakage; a single direct unit test of the helper kills them all.

## Cluster table (counts sum to 125)

| #   | Pattern                                                                                                                                                                                                                                                                                                                           | Fn                      | Count | Class        | Example keys                                       | Note                                                                                                                                                                                                                         |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- | ----- | ------------ | -------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| C1  | Brace-depth arithmetic/comparison flipped (`depth=0→1`, `+=1→-=1/+=2/=1`, `-=1→+=1/-=2/=1`, `depth==0→!=0/==1`)                                                                                                                                                                                                                   | extract_json_objects    | 9     | **TEST-GAP** | `x__extract_json_objects__mutmut_13`, `_38`, `_45` | Tests never observe the extracted candidate strings directly                                                                                                                                                                 |
| C2  | Char-comparison branch flips on quote/brace tests (`==`→`!=`, `==`→never-matching `"XX{XX"` literal)                                                                                                                                                                                                                              | extract_json_objects    | 8     | **TEST-GAP** | `_27`, `_31`, `_35`                                | String-literal/depth state machine corrupted; only observable at helper level                                                                                                                                                |
| C3  | `in_string` state assignments + escape-skip condition clobbered (init `False→True`, close→`True`, open→`None/False`, `c=="\\"`→`!=`/`or`/XX-const)                                                                                                                                                                                | extract_json_objects    | 7     | **TEST-GAP** | `_15`, `_22`, `_34`                                | Escaped-quote/brace-in-string inputs never supplied                                                                                                                                                                          |
| C4  | Outer scan / cursor advance broken (start `i=1`, `text[i]!="{ "` flips, `i+=2`, `continue→break`, `c=None`, `j+=2`)                                                                                                                                                                                                               | extract_json_objects    | 7     | **TEST-GAP** | `_3`, `_6`, `_58`                                  | Scanner misses or skips object starts                                                                                                                                                                                        |
| C5  | Emitted slice / resume point wrong (`text[i:j+1]→j-1/j+2`, resume `i=j+1→j-1/j+2`, `found_end=True→False/None`)                                                                                                                                                                                                                   | extract_json_objects    | 6     | **TEST-GAP** | `_48`, `_49`, `_51`                                | `_51`/`_50` return only the first object; `_53` (resume `j-1`) infinite-loops on standalone `{}` input — kill depends on the mutmut run timeout, note for WP4.4                                                              |
| C6  | Truthiness-preserving `False→None` inits and end-of-input guard tweaks (`j+1<n`→`j-1<n`/`j+2<n`/`j+1<=n`)                                                                                                                                                                                                                         | extract_json_objects    | 6     | EQUIVALENT   | `_14`, `_17`, `_24`                                | `None` falsy == `False` (14/17/29); guard only differs when backslash is the last char, where no object can close anyway (24/25/26)                                                                                          |
| C7  | warmup metrics call args not asserted: `set_model_warmth_state`/`observe_model_warmup_duration`/`record_model_cold_start` get wrong model label (`None`/`"NEMOTRON"`/`"XXnemotronXX"`) or wrong state (casing/None → gauge falls through to 0), `duration = monotic()-start → +start`, `was_cold=None` (skips cold-start counter) | warmup                  | 23    | **TEST-GAP** | `warmup__mutmut_7`, `_10`, `_42`                   | Existing tests only assert return value + `is_cold()`. Prometheus label/value IS a real contract (dashboards). Killable via patched-boundary call-args test (D2)                                                             |
| C8  | Pure log-message text mutations (`logger.debug/info/warning` message → None / XX-wrapped / lower / UPPER)                                                                                                                                                                                                                         | warmup                  | 13    | EQUIVALENT   | `_2`, `_19`, `_60`                                 | Per rubric: message text is not asserted behavior; `caplog` would kill them but shouldn't be required                                                                                                                        |
| C9  | Structured-log `extra=` payload of "warmup completed" mutated (dropped, `None`, key renames `duration→DURATION` etc.)                                                                                                                                                                                                             | warmup                  | 6     | LOW-VALUE    | `_44`, `_46`, `_47`                                | Real change, but log-field shape nobody asserts                                                                                                                                                                              |
| C10 | Failed-warmup branch `set_model_warmth_state("nemotron", "cold")` → `(…, None/"XXcoldXX"/"COLD")`                                                                                                                                                                                                                                 | warmup                  | 3     | EQUIVALENT   | `_53`, `_58`, `_59`                                | `{"cold":0,…}.get(state, 0)` → gauge 0 either way (call-args tests still kill these, but gauge semantics preserved)                                                                                                          |
| C11 | `_is_warming` lifecycle: `True→None/False` before probe (warmup no longer reports "warming") and finally `False→True` (stuck "warming" forever)                                                                                                                                                                                   | warmup                  | 3     | **TEST-GAP** | `_8`, `_9`, `_66`                                  | No test observes `get_warmth_state()` DURING warmup or asserts the post-warmup state string. Killed by D2                                                                                                                    |
| C12 | `_is_warming = False → None` in finally                                                                                                                                                                                                                                                                                           | warmup                  | 1     | EQUIVALENT   | `_65`                                              | Sole consumer is truthiness (`get_warmth_state` :1403); falsy→falsy                                                                                                                                                          |
| C13 | get_warmth_state time-based cold branch never exercised: `is_cold=None` (always "warm"), `>`→`>=` boundary, `and False`, `"cold"`→`"XXcoldXX"/"COLD"`                                                                                                                                                                             | get_warmth_state        | 5     | **TEST-GAP** | `_17`, `_20`, `_23`                                | `test_get_warmth_state_cold` hits the `_last_inference_time is None` early-return (:1409), never line 1416-1418; warm test asserts "warm" but threshold crossing / `"cold"`-on-line-1418 never asserted                      |
| C14 | `_run_enrichment_pipeline(detections, camera_id=camera_id)` forwarding mutated (detections→None, camera_id→None, either dropped)                                                                                                                                                                                                  | \_get_enrichment_result | 4     | **TEST-GAP** | `__mutmut_3`, `_4`, `_5`                           | `_5` raises TypeError caught by the broad `except Exception` at :2111 → returns FAILED result, which the only covering failure-path test asserts — survives by accident. Success path never stubs the pipeline. Killed by D4 |
| C15 | Failure-path logger call payload (message text, `extra`, `exc_info=True→False/None/dropped`, `str(e)→str(None)`)                                                                                                                                                                                                                  | \_get_enrichment_result | 14    | LOW-VALUE    | `_8`, `_13`, `_21`                                 | Diagnostics only                                                                                                                                                                                                             |
| C16 | FAILED fallback result `successful_models=[]→None`                                                                                                                                                                                                                                                                                | \_get_enrichment_result | 1     | **TEST-GAP** | `_23`                                              | Test asserts status/data/failed_models/errors but not successful_models; downstream `len(result.successful_models)` (success_rate) TypeErrors on consumer. Killed by D4b one-liner                                           |
| C17 | Fallback result construction drops args that equal dataclass defaults (`successful_models=[]` omitted, `data=None` omitted)                                                                                                                                                                                                       | \_get_enrichment_result | 2     | EQUIVALENT   | `_27`, `_30`                                       | `EnrichmentTrackingResult` (backend/services/enrichment_pipeline.py:472-476) has `default_factory=list` / `default=None` — identical object                                                                                  |
| C18 | `analyze_batch_streaming` delegates with kwargs zeroed/dropped (`analyzer=None`, `batch_id=None`, `camera_id=None/omitted`, `detection_ids=None/omitted`)                                                                                                                                                                         | analyze_batch_streaming | 6     | **TEST-GAP** | `__mutmut_1`, `_7`, `_8`                           | Existing test (:4397) does `assert_called_once()` — no arg assertion; autospec tolerates None kwargs. Killed by D5                                                                                                           |
| C19 | `record_rollout_feedback`: camera_id not forwarded to `get_group_for_camera` (`camera_id→None`)                                                                                                                                                                                                                                   | record_rollout_feedback | 1     | **TEST-GAP** | `__mutmut_3`                                       | Control-group test asserts feedback routing but never the lookup arg. Killed by D6                                                                                                                                           |

## Drafted tests (highest-value TEST-GAP clusters)

TDD procedure (same for all six): add test against current source → run → **green**; apply the cluster's mutant diff → run → **assert fails (red)**; revert → green. All are **UNVERIFIED — not yet run red/green** (test execution forbidden during the live mutation run).

### D1 — kills C1–C5 (37 mutants) · `backend/tests/unit/services/test_nemotron_analyzer.py` (module-level, matches style at :291)

```python
def test_extract_json_objects_balanced_scanner_contract():
    """_extract_json_objects is the only parser for LLM text that defeats the
    fast-path and the _JSON_PATTERN regex — pin its contract directly.

    UNVERIFIED - not yet run red/green.
    """
    from backend.services.nemotron_analyzer import _extract_json_objects

    # flat object at position 0 (kills i=1 start, != flips, c=None, j+=2)
    assert _extract_json_objects('{"a": 1}') == ['{"a": 1}']
    # leading text at odd offset (kills i+=2 skip, continue->break)
    assert _extract_json_objects('X{"a": 1}') == ['{"a": 1}']
    # arbitrary nesting (kills depth arithmetic / depth==0 flips)
    nested = '{"a": {"b": {"c": 1}}}'
    assert _extract_json_objects(nested) == [nested]
    # escaped quote + brace inside string (kills escape/state-machine mutants)
    esc = '{"s": "a\\"b {x} c"}'
    assert _extract_json_objects(esc) == [esc]
    # two adjacent objects (kills slice/reume off-by-one + found_end falsy)
    assert _extract_json_objects('{"a": 1}{"b": 2}') == ['{"a": 1}', '{"b": 2}']
    # empty standalone object (kills mutmut_53 resume->j-1 via its rescan loop;
    # NOTE: that mutant loops forever here, kill relies on the mutmut timeout)
    assert _extract_json_objects('{}') == ['{}']
    # no object closes => nothing extracted
    assert _extract_json_objects('{"a": 1') == []
    assert _extract_json_objects('plain text') == []
```

Assertions compare the **raw extracted strings**, so slice mutants (48/49) that merely make `json.loads` fail in the caller are still caught — the caller-level tests could never see them.

### D2 — kills C7 + C11 (26 mutants) · `backend/tests/unit/services/test_model_warmup.py` (into `TestNemotronAnalyzerWarmup`, style matches :141)

```python
@pytest.mark.asyncio
async def test_warmup_emits_nemotron_labeled_metrics_and_warming_lifecycle(self, analyzer):
    """Warmup must label every metric 'nemotron', record the cold start,
    report 'warming' while in flight and leave the flag cleared after.

    UNVERIFIED - not yet run red/green.
    """
    from unittest.mock import call

    with (
        patch.object(analyzer, "model_readiness_probe", new_callable=AsyncMock) as mock_probe,
        patch("backend.core.metrics.set_model_warmth_state") as mock_state,
        patch("backend.core.metrics.observe_model_warmup_duration") as mock_observe,
        patch("backend.core.metrics.record_model_cold_start") as mock_cold,
    ):
        def probe_checks_warming():
            # during warmup the analyzer must report 'warming'
            assert analyzer.get_warmth_state()["state"] == "warming"
            return True

        mock_probe.side_effect = probe_checks_warming
        result = await analyzer.warmup()

    assert result is True
    mock_state.assert_has_calls([call("nemotron", "warming"), call("nemotron", "warm")])
    mock_cold.assert_called_once_with("nemotron")          # kills was_cold=None + counter label mutants
    (model, duration), _ = mock_observe.call_args
    assert model == "nemotron"
    assert 0.0 <= duration < 60.0                          # kills duration = monotonic() + start_time
    assert analyzer.get_warmth_state()["state"] == "warm"  # kills _is_warming stuck-True in finally
```

Fresh analyzer is cold (`_last_inference_time None`), so the cold-start counter must fire. `patch("backend.core.metrics.*")` works because `warmup()` imports the helpers from the module at call time (:1479-1483).

### D3 — kills C13 (5 mutants) · `test_model_warmup.py` (`TestNemotronAnalyzerWarmup`; threshold = 300 s from its fixture :54)

```python
def test_get_warmth_state_cold_after_threshold(self, analyzer):
    """The time-based cold branch (nemotron_analyzer.py:1416-1418) is never
    exercised today: the existing 'cold' test takes the None early-return.

    UNVERIFIED - not yet run red/green.
    """
    analyzer._last_inference_time = time.monotonic() - 600.0  # threshold is 300s

    state = analyzer.get_warmth_state()

    assert state["state"] == "cold"
    assert state["last_inference_seconds_ago"] > 300.0


def test_get_warmth_state_exactly_at_threshold_is_warm(self, analyzer):
    """Boundary: cold requires seconds_ago > threshold (strict >).

    UNVERIFIED - not yet run red/green.
    """
    import backend.services.nemotron_analyzer as na

    analyzer._cold_start_threshold = 100.0
    analyzer._last_inference_time = 1000.0
    with patch.object(na.time, "monotonic", return_value=1100.0):  # exactly 100s ago
        state = analyzer.get_warmth_state()

    assert state["state"] == "warm"  # >= mutant reports 'cold' here
    assert state["last_inference_seconds_ago"] == 100.0
```

### D4 / D4b — kill C14 + C16 (5 mutants) · `backend/tests/unit/services/test_nemotron_analyzer.py` (next to :2342; fixture at :104)

```python
@pytest.mark.asyncio
async def test_get_enrichment_result_forwards_detections_and_camera_id(analyzer):
    """_get_enrichment_result must forward the real detections and camera_id
    to the pipeline (camera_id drives scene-change/re-id).

    UNVERIFIED - not yet run red/green.
    """
    from datetime import UTC

    from backend.models.detection import Detection
    from backend.services.enrichment_pipeline import (
        EnrichmentResult,
        EnrichmentStatus,
        EnrichmentTrackingResult,
    )

    detections = [
        Detection(
            id=4101,
            camera_id="test",
            file_path="/export/foscam/test/img1.jpg",
            detected_at=datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC),
            object_type="person",
            confidence=0.95,
        ),
    ]
    sentinel = EnrichmentTrackingResult(
        status=EnrichmentStatus.FULL,
        successful_models=["face"],
        data=EnrichmentResult(),
    )
    analyzer._run_enrichment_pipeline = AsyncMock(return_value=sentinel)

    result = await analyzer._get_enrichment_result(
        batch_id="b1", detections=detections, camera_id="cam9",
    )

    call = analyzer._run_enrichment_pipeline.await_args
    assert call.args[0] is detections                      # kills detections->None / dropped
    assert call.kwargs["camera_id"] == "cam9"              # kills camera_id->None / dropped
    assert result is sentinel                              # kills TypeError-swallow variant (mutmut_5)
```

D4b — one line appended to the existing `test_get_enrichment_result_returns_failed_tracking_on_failure` (:2342): `assert result.successful_models == []` (kills `_23`: None ≠ []; `_27` stays green — dataclass default is `[]`).

### D5 — kills C18 (6 mutants) · `test_nemotron_analyzer.py` (replace/augments :4397)

```python
@pytest.mark.asyncio
async def test_analyze_batch_streaming_forwards_all_kwargs(analyzer, mock_redis_client):
    """The streaming delegation must pass every identity kwarg, not None-filled.

    UNVERIFIED - not yet run red/green.
    """

    async def gen():
        yield {"type": "progress", "data": {"status": "analyzing"}}

    with patch(
        "backend.services.nemotron_streaming.analyze_batch_streaming",
        return_value=gen(),
        autospec=True,
    ) as mock_streaming:
        updates = []
        async for update in analyzer.analyze_batch_streaming(
            batch_id="b7", camera_id="front_door", detection_ids=[9, 8],
        ):
            updates.append(update)

    assert len(updates) == 1
    mock_streaming.assert_called_once_with(
        analyzer=analyzer,
        batch_id="b7",
        camera_id="front_door",
        detection_ids=[9, 8],
    )
```

### D6 — kills C19 (1 mutant) · `test_nemotron_analyzer.py` (treatment-routing sibling of :4918)

```python
@pytest.mark.asyncio
async def test_record_rollout_feedback_routes_by_camera_id(analyzer):
    """Feedback routing must look up the group for the ACTUAL camera_id.

    UNVERIFIED - not yet run red/green.
    """
    from backend.config.prompt_ab_rollout import ExperimentGroup

    mock_rollout = MagicMock(spec=ABRolloutManager)
    mock_rollout.get_group_for_camera.return_value = ExperimentGroup.TREATMENT
    analyzer._rollout_manager = mock_rollout

    analyzer.record_rollout_feedback("cam-42", is_false_positive=False)

    mock_rollout.get_group_for_camera.assert_called_once_with("cam-42")  # kills camera_id->None
    mock_rollout.record_treatment_feedback.assert_called_once_with(False)
```

## Notes for WP4.4

- C8/C15 (log text + payload) and C6/C10/C12/C17 (true equivalences): recommend suppress/mark rather than test.
- `_extract_json_objects` C5's `mutmut_53` is a latent infinite-loop bug on standalone `{}` input; the drafted assert exposes it only via mutmut timeout — consider `pytest-timeout` or replacing the resume with `i = j + 1` guarded to always advance.
- Coverage after D1–D6: 80/80 TEST-GAP survivors killed by 6 tests (7 if D4b counted separately).
