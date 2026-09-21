# WP4.4 Triage Dossier — backend/services/prompt_auto_tuner.py

**Source:** `backend/services/prompt_auto_tuner.py` (206 lines)
**Mutants:** 117 total | killed 79 | **survived 38** | unchecked 0
**Covering test file (primary):** `backend/tests/unit/services/test_prompt_auto_tuner.py`
**Covering test file (secondary, executes via analyzer):** `backend/tests/unit/services/test_nemotron_analyzer.py` (test_analyze_batch_* — exercises `get_tuning_context` call shape but only via mocks)

All 38 diffs obtained read-only via `uv run mutmut show` (no failures, no cache contention). Only two functions produce survivors:
- `_filter_by_priority` — 10 survivors (keys 3,5,7,9,11,14,16,19,20,21)
- `get_tuning_context` — 28 survivors (keys 3,5,41,45,48,51,53,56,59,62,65,67,70,73,74,75,76,78,79,80,81,82,83,84,85,86,87,88)

## Per-cluster table

| # | Cluster (function : line) | Keys | Count | Class | Why it survives |
|---|---|---|---|---|---|
| C1 | `_filter_by_priority` :87 — `min_level` fallback default `2` → `None`/removed/`3` | fp:3, fp:5, fp:7 | 3 | **TEST-GAP** | Docstring says invalid `min_priority` "Default to medium". No test ever passes an unrecognized `min_priority`. Mutant 7 silently re-tiers unknown values to "high" filtering; 3/5 raise TypeError (`int >= None`), which inside `get_tuning_context` is swallowed by the broad except → empty context. |
| C2 | `_filter_by_priority` :91 — item-unknown-priority fallback `1` → `None`/removed/`2` | fp:9, fp:11, fp:21 | 3 | **TEST-GAP** | A recommendation with an unrecognized priority string (e.g. `"critical"`) is treated as level 1. No test fixture contains a non-{high,medium,low} priority. Mutant 21 re-tiers unknown priorities to medium (they leak past the medium filter); 9/11 TypeError. |
| C3 | `_filter_by_priority` :91 — item missing `"priority"` key default `"low"` → `None`/removed | fp:14, fp:16 | 2 | **TEST-GAP** | Original: dict without `priority` is treated as low (`.lower()` of `"low"`). Mutant: `r.get(...)` yields `None` → `None.lower()` AttributeError → whole `get_tuning_context` collapses to `""`. No test recommendation lacks the `priority` key. |
| C4 | `_filter_by_priority` :91 — default string `"low"` → `"XXlowXX"` / `"LOW"` | fp:19, fp:20 | 2 | **EQUIVALENT** | Both pass through `.lower()`: `"xxlowxx"` falls to the level-1 fallback (same result), `"LOW".lower()=="low"` hits the same dict entry. Semantically identical on every input. |
| C5 | `get_tuning_context` :126-129 — `session=session` kwarg → `None` / removed | gtc:3, gtc:5 | 2 | **TEST-GAP** | Existing `test_uses_default_days_and_min_priority` (test file :296-317) asserts `call_kwargs["days"]` but **never asserts `session` is forwarded**. In production a dropped/`None` session breaks or mis-scopes the audit query; invisible to the mock-based suite. |
| C6 | `get_tuning_context` :156/160/168 — section header strings wrapped in `XX…XX` | gtc:41, gtc:45, gtc:59 | 3 | **TEST-GAP (weak assertion)** | Tests assert `"## AUTO-TUNING (From Historical Analysis)" in context` etc. — the XX-wrapped mutant **contains** the original as a substring, so `in` passes. These headers are prompt text sent to the LLM; exact form is the contract. Needs exact/anchored assertion. |
| C7 | `get_tuning_context` :161/169 — top-N slices `[:3]→[:4]`, `[:2]→[:3]` | gtc:48, gtc:62 | 2 | **TEST-GAP** | The limit tests (`:224`, `:270`) use `sample_recommendations`, but the default `medium` priority filter removes the 4th missing_context item ("Add lighting conditions", low) and the 3rd format item ("Add confidence thresholds", low) **before** the slice — so the widened slice never renders an extra line. The slice boundary is unreachable with that fixture. Prompt-size cap (documented "top 3"/"top 2") unenforced. |
| C8 | `get_tuning_context` :162/170 — `r.get("suggestion", "")` default → `None`/removed/`"XXXX"` (both loops) | gtc:51, 53, 56, 65, 67, 70 | 6 | **EQUIVALENT** | Dead default: the `missing_context`/`format_suggestions` comprehensions at :141-150 already require `r.get("suggestion")` truthy, so the key is always present when these lines run. No input can observe the default. |
| C9 | `get_tuning_context` :174 — `"\n".join` → `"XX\nXX".join` | gtc:73 | 1 | **TEST-GAP** | All existing assertions are per-line `in context` checks — none observes line **joining**, so `XX` litter between lines passes every test. The rendered block is injected into the LLM prompt verbatim; killed by the same exact-output assertion as C6. |
| C10 | `get_tuning_context` :181 — `exc_info=True` → `None`/removed/`False` | gtc:76, 79, 88 | 3 | **LOW-VALUE** | Real loss of traceback on the failure-path warning, but observability detail no caller-visible behavior depends on; no caplog assertion in this module's suite and pinning `exc_info` is low ROI. |
| C11 | `get_tuning_context` :179 — warning message text → `None`/`XX…XX`/lowercase/UPPERCASE | gtc:74, 80, 81, 82 | 4 | **EQUIVALENT** | Pure human-facing log text; `logger.warning(None)` is legal. No behavioral change; message string is not an asserted contract. |
| C12 | `get_tuning_context` :180 — `extra={…}` kwarg → `None` / removed | gtc:75, 78 | 2 | **LOW-VALUE** | Structured-log diagnostic payload dropped; no consumer in the tested surface asserts it. |
| C13 | `get_tuning_context` :180 — keys/values inside `extra` dict (`camera_id`→`XXcamera_idXX`/`CAMERA_ID`, `error`→`XXerrorXX`/`ERROR`, `str(e)`→`str(None)`) | gtc:83, 84, 85, 86, 87 | 7 | **LOW-VALUE** | Same rationale as C12 — log-schema drift, only observable by a log aggregator outside the test scope. gtc:87 flattens the error detail to `"None"` (worst of the cluster) but still only observability. |

**Totals:** TEST-GAP 16 (C1 3, C2 3, C3 2, C5 2, C6 3, C7 2, C9 1) | EQUIVALENT 12 (C4 2, C8 6, C11 4) | LOW-VALUE 10 (C10 3, C12 2, C13 5) → **38 = survivors_total**

## Why the existing suite misses each TEST-GAP cluster

- **C1/C2/C3**: `TestPriorityFiltering::test_filter_by_priority_high_only` (:509) is the only filter-focused test and its fixture has only clean `high/medium/low` values with `priority` always present; `min_priority` is only ever `"high"` (a valid key, :526) or default `"medium"`. The fallback arguments at :87 and :91 are never fed a lookup miss.
- **C5**: call-shape is asserted for `days` only (test :313-316, :337-338). `session` never appears in any `call_args` assertion.
- **C6/C9**: every format assertion is `substring in context`; `in` cannot distinguish `XXHEADERXX` from `HEADER`, nor a mangled join separator.
- **C7**: `test_limits_missing_context_to_top_3` (:224) and `test_limits_format_suggestions_to_top_2` (:270) assert the right negatives, but their fixture's 4th/3rd items are `priority: low` — already filtered out by the medium default — so `[:4]`/`[:3]` render nothing extra. The boundary needs a fixture of ≥4 (resp. ≥3) **priority-eligible** items.

## Drafted tests (UNVERIFIED — not yet run red/green)

All follow the file's existing style: `pytest.mark.asyncio`, `patch("backend.services.prompt_auto_tuner.get_audit_service", autospec=True)`, `MagicMock` service with `AsyncMock` return value, `mock_db_session` fixture. Target file: `backend/tests/unit/services/test_prompt_auto_tuner.py`.

### T1 — `test_forwards_session_to_audit_service` → kills C5 (gtc:3, gtc:5)

```python
    @pytest.mark.asyncio
    async def test_forwards_session_to_audit_service(self, mock_db_session):
        """Test the caller's db session is forwarded to get_recommendations."""
        from backend.services.prompt_auto_tuner import PromptAutoTuner

        with patch(
            "backend.services.prompt_auto_tuner.get_audit_service", autospec=True
        ) as mock_get_audit:
            mock_service = MagicMock()
            mock_service.get_recommendations = AsyncMock(return_value=[])
            mock_get_audit.return_value = mock_service

            tuner = PromptAutoTuner()
            await tuner.get_tuning_context(
                session=mock_db_session,
                camera_id="front_door",
            )

            call_kwargs = mock_service.get_recommendations.call_args.kwargs
            assert call_kwargs.get("session") is mock_db_session
```

TDD: on gtc:3 (`session=None`) the `is` assert fails; on gtc:5 (kwarg removed) `call_kwargs.get("session")` is `None` → fails; passes on original.

### T2 — `test_invalid_min_priority_defaults_to_medium` → kills C1 (fp:3, fp:5, fp:7)

```python
class TestPriorityFiltering:
    # ... existing test ...

    def test_invalid_min_priority_defaults_to_medium(self):
        """Test unrecognized min_priority falls back to medium filtering."""
        from backend.services.prompt_auto_tuner import PromptAutoTuner

        tuner = PromptAutoTuner()
        recs = [
            {"priority": "high", "category": "missing_context", "suggestion": "H"},
            {"priority": "medium", "category": "missing_context", "suggestion": "M"},
            {"priority": "low", "category": "missing_context", "suggestion": "L"},
        ]

        result = tuner._filter_by_priority(recs, "urgent")  # not in PRIORITY_LEVELS

        # Default-to-medium: high and medium kept, low dropped
        assert [r["suggestion"] for r in result] == ["H", "M"]
```

TDD: on fp:7 (default 3) only `["H"]` remains → fails; on fp:3/fp:5 (`None` default) `1 >= None` raises TypeError → fails; passes on original.

### T3 — `test_unknown_item_priority_treated_as_low` → kills C2 (fp:9, fp:11, fp:21)

```python
    def test_unknown_item_priority_treated_as_low(self):
        """Test a recommendation with an unrecognized priority string is level 1."""
        from backend.services.prompt_auto_tuner import PromptAutoTuner

        tuner = PromptAutoTuner()
        recs = [
            {"priority": "urgent", "category": "missing_context", "suggestion": "U"},
            {"priority": "low", "category": "missing_context", "suggestion": "L"},
        ]

        # Unknown "urgent" falls back to low (level 1): visible only at min_priority=low
        assert [r["suggestion"] for r in tuner._filter_by_priority(recs, "low")] == ["U", "L"]
        assert tuner._filter_by_priority(recs, "medium") == []
```

TDD: on fp:21 (`"urgent"` → level 2) it survives the medium filter → second assert fails; on fp:9/fp:11 the `>=` comparison with `None` raises → fails; passes on original.

### T4 — `test_missing_priority_key_treated_as_low` → kills C3 (fp:14, fp:16)

```python
    def test_missing_priority_key_treated_as_low(self):
        """Test a recommendation dict without a 'priority' key defaults to low."""
        from backend.services.prompt_auto_tuner import PromptAutoTuner

        tuner = PromptAutoTuner()
        recs = [{"category": "missing_context", "suggestion": "NOKEY"}]

        assert [r["suggestion"] for r in tuner._filter_by_priority(recs, "low")] == ["NOKEY"]
        assert tuner._filter_by_priority(recs, "medium") == []
```

TDD: on fp:14/fp:16 `r.get("priority", None)` returns `None` for the keyless dict → `None.lower()` AttributeError → fails; passes on original (`"low"` → level 1, kept only at min_priority=low).

### T5 — `test_exact_rendered_block` → kills C6 (gtc:41, 45, 59) + C9 (gtc:73)

```python
    @pytest.mark.asyncio
    async def test_exact_rendered_block(self, mock_db_session):
        """Test the rendered context matches the documented format exactly."""
        from backend.services.prompt_auto_tuner import PromptAutoTuner

        recommendations = [
            {"category": "missing_context", "suggestion": "MC1", "frequency": 9, "priority": "high"},
            {"category": "missing_context", "suggestion": "MC2", "frequency": 8, "priority": "medium"},
            {"category": "format_suggestions", "suggestion": "FS1", "frequency": 7, "priority": "high"},
            {"category": "format_suggestions", "suggestion": "FS2", "frequency": 6, "priority": "medium"},
        ]

        with patch(
            "backend.services.prompt_auto_tuner.get_audit_service", autospec=True
        ) as mock_get_audit:
            mock_service = MagicMock()
            mock_service.get_recommendations = AsyncMock(return_value=recommendations)
            mock_get_audit.return_value = mock_service

            tuner = PromptAutoTuner()
            context = await tuner.get_tuning_context(
                session=mock_db_session,
                camera_id="front_door",
            )

            assert context == "\n".join(
                [
                    "## AUTO-TUNING (From Historical Analysis)",
                    "Previously helpful context that was missing:",
                    "  - MC1",
                    "  - MC2",
                    "Known prompt clarity issues:",
                    "  - FS1",
                    "  - FS2",
                ]
            )
```

TDD: on gtc:41/45/59 the mutated header carries `XX` padding → equality fails; on gtc:73 lines join with `XX\nXX` → equality fails; passes on original.

### T6 — `test_slice_limits_with_eligible_items_only` → kills C7 (gtc:48, gtc:62)

```python
    @pytest.mark.asyncio
    async def test_slice_limits_with_eligible_items_only(self, mock_db_session):
        """Test top-3/top-2 caps with all-priority-eligible items (limit tests' fixture
        lets the medium filter hide the boundary item before the slice runs)."""
        from backend.services.prompt_auto_tuner import PromptAutoTuner

        recommendations = [
            *[
                {"category": "missing_context", "suggestion": f"MC{i}", "frequency": 20 - i, "priority": "high"}
                for i in range(4)
            ],
            *[
                {"category": "format_suggestions", "suggestion": f"FS{i}", "frequency": 10 - i, "priority": "high"}
                for i in range(3)
            ],
        ]

        with patch(
            "backend.services.prompt_auto_tuner.get_audit_service", autospec=True
        ) as mock_get_audit:
            mock_service = MagicMock()
            mock_service.get_recommendations = AsyncMock(return_value=recommendations)
            mock_get_audit.return_value = mock_service

            tuner = PromptAutoTuner()
            context = await tuner.get_tuning_context(
                session=mock_db_session,
                camera_id="front_door",
            )

            assert "MC0" in context
            assert "MC2" in context
            assert "MC3" not in context  # 4th missing_context must be cut by [:3]
            assert "FS0" in context
            assert "FS1" in context
            assert "FS2" not in context  # 3rd format_suggestion must be cut by [:2]
```

TDD: on gtc:48 (`[:4]`) `"MC3"` renders → fails; on gtc:62 (`[:3]`) `"FS2"` renders → fails; passes on original.

## Coverage arithmetic

| Class | Clusters | Mutants |
|---|---|---|
| TEST-GAP | C1, C2, C3, C5, C6, C7, C9 | 16 |
| EQUIVALENT | C4, C8, C11 | 12 |
| LOW-VALUE | C10, C12, C13 | 10 |
| **Total** | 13 | **38** |

Drafted tests T1-T6 cover all 16 TEST-GAP mutants (T5 covers C6+C9; T2/T3/T4 are direct private-method calls — consistent with the file already poking `tuner._audit_service` at :148).
