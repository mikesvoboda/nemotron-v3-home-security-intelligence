# WP4.4 Triage Dossier — backend/services/token_counter.py

- **Module:** `backend/services/token_counter.py`
- **Mutants:** 223 total, 145 killed, **78 survived** (0 unchecked) — 35% mutation score
- **Verdict source:** `mutants/backend/services/token_counter.py.meta` (`exit_code_by_key == 0`)
- **Diffs:** all 78 obtained via `uv run mutmut show <key>` (no failures; no manual-diff fallback needed)
- **Key files:**
  - Source: `backend/services/token_counter.py` (line refs below)
  - Covering test file (primary): `backend/tests/unit/services/test_token_counter.py`
  - Secondary executors (real code never runs — they mock `get_token_counter`): `backend/tests/unit/services/test_nemotron_analyzer.py` (MagicMock at :3655, :4050, :4088, :4143), `test_nemotron_guided_json.py`, `test_correlation_propagation.py`, `test_ai_inference_semaphore.py`
- **Classification totals: TEST-GAP 33 / EQUIVALENT 45 / LOW-VALUE 0 (sum 78)**

## Facts established (drive the classifications; verified without running the suite)

1. `count_tokens(None)` does **not** crash — `if not text: return 0` (`token_counter.py:186-187`), `None` is falsy. So `count_tokens(None)` mutants return `0`, not TypeErrors. This reclassified several "crash-survivor" guesses (see C7 ted_38/ted_47).
2. `tiktoken.get_encoding(None)` raises `ValueError: Expected a string in get_encoding, got <class 'NoneType'>` (probed via `uv run python`, hermetic).
3. `Settings` has **no `nemotron_model_name` field** (grep of `backend/` finds it only in token_counter's own docstring/getattr) → `getattr(settings, "nemotron_model_name", None)` is always `None`, so the *third* chain term in `__init__:149-151` is live and the `getattr`-source mutants are inert.
4. `sanitize_metric_label(None)` returns `"unknown"` (`backend/core/sanitization.py:359`) → `model=None` gauge label does not crash; it silently retitles the Prometheus series.
5. `TokenCounter.model_name`'s only production consumer is the gauge call at `validate_prompt:218`; the analyzer never passes or reads it (`nemotron_analyzer.py:4419-4469`).
6. The analyzer consumes only `is_valid / prompt_tokens / available_tokens / was_truncated / sections_removed / truncated_prompt` — never `warning`, `original_tokens`, or `final_tokens`.
7. `TokenCounter.__init__` rejects `max_output_tokens >= context_window` (line 155) → `available_tokens = context_window − output` is always ≥ 1 → the `available_tokens > 0` utilization guard (`validate_prompt:207`) is dead code.
8. **No test anywhere asserts token_counter log-record `extra` payloads or messages** (`caplog` unused in `test_token_counter.py`; repo-wide `extra`-asserting tests live in unrelated modules).

## Cluster table (18 clusters, counts sum to 78; membership listed at bottom)

| # | Pattern | n | Examples | Class | Ruling |
|---|---|--:|---|---|---|
| C1 | log **message f-string → `None`** in `__init__`/`validate_prompt`/`truncate_enrichment_data` | 6 | init_27, init_35, vp_25 | EQUIVALENT | Message-text only; no caplog/record assertions exist for these records. |
| C2 | `logger.warning(..., extra={...})`: **extras dict dropped (`extra=None`), key clobbered (`XXkXX`/`UPPER`), or whole dict deleted** in `validate_prompt` + `truncate_enrichment_data` | 27 | vp_29, vp_43, ted_30 | EQUIVALENT | Pure log-record metadata; nothing in production or tests reads it. Note: the dict embeds `self.count_tokens(truncated_prompt)` (vp_26/28/40/42, ted_27/29/32/34) — but with fact 1 it cannot crash and its value feeds only the record. |
| C3 | **`<=` → `<` off-by-one on exact-fit token gates**: `is_valid` (vp_20), `truncate_to_fit` fits-check (ttf_4), `truncate_enrichment_data` early return (ted_3), loop break (ted_18) | 4 | vp_20, ttf_4, ted_18 | TEST-GAP | Real behavior at equality: exact-fit prompt reported invalid; exact-fit text unnecessarily truncated; exact-fit prompt force-truncated; loop removes one section too many at exact mid-loop fit. Tests sit far from boundaries (`test_token_counter.py:177` uses strict `<`, :287 uses `<= 50` after slack removal). |
| C4 | **`target_tokens <= 0` → `<= 1`** (`truncate_to_fit:294`): budget==1 case | 1 | ttf_10 | TEST-GAP | Original keeps 1 content token + suffix; mutant returns bare suffix. Never exercised. |
| C5 | **`target_tokens <= 0` → `< 0`** (same line, budget==0 case) | 1 | ttf_9 | EQUIVALENT | Provably identical: at target==0 mutant does `tokens[:0]` → `decode([])==""` → `""+suffix == suffix` = original's early-return value. |
| C6 | **`final_tokens > max_tokens` → `>=`** (hard-truncation trigger, `truncate_enrichment_data:355`) | 1 | ted_39 | EQUIVALENT | Provably identical: at `final==max`, `truncate_to_fit(text, max)` re-encodes, `len(tokens) <= max` → returns text unchanged; recount identical. Extra call is a no-op. |
| C7 | **hard-truncation branch arg/result plumbing** (`lines 355-361`): `count_tokens(None)`, `truncate_to_fit` arg nulling/deletion, `final_tokens=None`/0 | 8 | ted_38, ted_41, ted_43 | TEST-GAP | Real diffs: ted_38/ted_47 report `final_tokens=0` (and ted_38 skips hard truncation entirely, leaving an over-limit prompt); ted_41/ted_42 put `None` into `truncated_prompt`; ted_43/44/45 raise TypeError; ted_46 `None`. Survive because **no test reaches the branch** — `test_truncate_enrichment_removes_sections` (:266) fits after removal; analyzer tests mock the counter. Note ted_38's silent wrongness: 0 <= 50 satisfies the existing assertion (:287). |
| C8 | **`TruncationResult` fields → `None`** on both return paths (`original_tokens`/`final_tokens`/`truncated_prompt`) | 4 | ted_5, ted_6, ted_48 | TEST-GAP | `test_truncate_enrichment_no_truncation_needed` (:257) asserts `was_truncated`/`truncated_prompt`/`sections_removed` only — never the token-count fields; hard-return path unexecuted (C7). Killed by D1a+D1b. |
| C9 | `TruncationResult(sections_removed=[])` / `was_truncated=False` kwarg **removed** (defaults take over) on early return | 2 | ted_12, ted_13 | EQUIVALENT | Dataclass defaults are exactly `[]` / `False` (`token_counter.py:105-106`). |
| C10 | utilization guard **dead-code mutations** (`or True`, `>0`→`>=0`/`>1`, else `1.0`→`2.0`) at `validate_prompt:207` | 4 | vp_9, vp_13 | EQUIVALENT | Guard unreachable given fact 7; `>1` only diverges at `available_tokens==1` — also unreachable (min available is 1... wait: constructor allows `max_output = context-1` → available==1 possible in production, but no reachable test config hits it and the mutated comparisons are *true* at available==1, identical to original). |
| C11 | warning threshold **`>=` → `>`** (`validate_prompt:239`) | 1 | vp_37 | TEST-GAP | At utilization exactly at threshold the mutant silently drops the warning. `test_validate_prompt_high_utilization_warning` (:194) uses ~2500/3072 (never equality). |
| C12 | `warning = None` → `""` initialization | 1 | vp_21 | EQUIVALENT | Every warning-taking path reassigns a truthy f-string; non-warning paths leave falsy either way. |
| C13 | **model_name fallback chain / gauge label**: `_model_name=None`, `or`→`and`, default-constant clobbers, `self.model_name=None`, gauge `model=None` | 7 | init_10, init_22, vp_15 | TEST-GAP | Live chain (fact 3): init_10/11/22 → `model_name=None` → gauge series retitled `"nemotron-mini"`→`"unknown"` (fact 4 — no crash, silent cardinality relabel on Grafana dashboards, NEM-3288); init_20/21 change the reachable default constant; init_12 breaks explicit `model_name=` (chain `and` kills the left operand since the settings attr is always None). No test asserts `.model_name` or the gauge label (`TestMetricsIntegration` :473 patches only `observe_context_utilization` with a loose 0..2 float bound). |
| C14 | encoding selection broken: `self.encoding_name=None`, `or`→`and`, `get_encoding(None)` in `__init__` | 3 | init_2, init_26 | TEST-GAP | Under the repo's config (default encoding IS `cl100k_base`, `config.py:1225`) final state coincidentally matches → survives `test_init_with_custom_values`/`test_init_with_invalid_encoding_fallback`. But a caller passing e.g. `encoding_name="o200k_base"` gets silently downgraded to `cl100k_base` (token counts wrong for that model) — line executed, contract never asserted. Killable hermetically by mocking `tiktoken.get_encoding` (D6a). |
| C15 | fallback-branch `self._encoding = None` (line 169, reached by `test_init_with_invalid_encoding_fallback` :103) | 1 | init_28 | TEST-GAP | The test asserts only `encoding_name == "cl100k_base"`, then abandons the counter — it never counts a token, so the poisoned `_encoding` goes unnoticed. Killed by D6b. |
| C16 | wrapper arg swap/deletion: `validate_prompt(max_output_tokens)` / `validate_prompt(None, max_output_tokens)` | 2 | x_vpt_1, x_vpt_3 | TEST-GAP | Real change: with a non-None override the wrapper crashes (`encode(int)` → TypeError) or validates the wrong value. The sole test (`:397`) passes `max_output=None`, where `count_tokens(None)→0` (fact 1) → `is_valid=True` masks it. |
| C17 | wrapper drops the `max_output_tokens` override (→ `None`) | 2 | x_vpt_2, x_vpt_4 | TEST-GAP | Caller's override silently ignored (instance default used). Wrapper's one test passes `None`, so the default path is identical; forwarding is the wrapper's whole contract and is unasserted. |
| C18 | `getattr`-source mutants with no live effect: `getattr(None, …)`, `"XXnemotron_model_nameXX"`, `"NEMOTRON_MODEL_NAME"` | 3 | init_13, init_18, init_19 | EQUIVALENT | Attribute never exists on `Settings` (fact 3) → all variants evaluate to `None` exactly like the original. |

**Sum check:** 6+27+4+1+1+1+8+4+2+4+1+1+7+3+1+2+2+3 = **78** (TEST-GAP 33 = C3+C4+C7+C8+C11+C13+C14+C15+C16+C17; EQUIVALENT 45 = C1+C2+C5+C6+C9+C10+C12+C18).

## Drafted kill-tests (target file `backend/tests/unit/services/test_token_counter.py`)

**// UNVERIFIED - not yet run red/green.** TDD procedure: add the test → run against the mutant source (expect FAIL on the mutant diff) → run against original (expect PASS) → commit test before any source change. Style follows the existing file (fixtures `token_counter` / `small_context_counter`, class grouping, `unittest.mock.patch`).

### D1 → C7 (8) + C8 (4) = 12 mutants

```python
class TestHardTruncationPath:
    """Cover the last-resort hard-truncation branch (no removable sections)."""

    def test_hard_truncation_result_integrity(self, token_counter):
        """Prompt with no ## sections must be hard-truncated with a valid result."""
        # No headers/braces → _remove_section never matches → loop cannot reach the
        # limit → hard truncation branch (token_counter.py:355-361) executes.
        prompt = "word " * 200
        n = token_counter.count_tokens(prompt)
        result = token_counter.truncate_enrichment_data(prompt, max_tokens=50)

        assert result.was_truncated is True
        assert result.sections_removed == []
        assert result.original_tokens == n                    # kills ted_5/ted_49 (None)
        assert isinstance(result.truncated_prompt, str)       # kills ted_41/ted_42/ted_48
        assert result.final_tokens == token_counter.count_tokens(result.truncated_prompt)
        #                       ^ kills ted_38/ted_46/ted_47 (0 or None)
        assert result.final_tokens <= 50                      # also fails for 0-final: see below
        # (final==0 fails the equality assert above; the <=50 line documents intent)

    def test_no_truncation_result_fields(self, token_counter):
        """Early-return path must carry real counts in both token fields."""
        prompt = "Short prompt with minimal content"
        n = token_counter.count_tokens(prompt)
        result = token_counter.truncate_enrichment_data(prompt, max_tokens=5000)

        assert result.was_truncated is False
        assert result.original_tokens == n                    # kills early-return None fields
        assert result.final_tokens == n                       # kills ted_6
```

Note: ted_43/ted_44/ted_45 are killed by D1a crashing (TypeError at `token_counter.py:360`); ted_38 specifically leaves an over-limit prompt with `final_tokens=0` — the equality assert catches it.

### D2 → C3 (4)

```python
class TestExactFitBoundaries:
    """Exact-equality boundaries on the token gates."""

    def test_prompt_exactly_at_available_is_valid(self, small_context_counter):
        """prompt_tokens == available_tokens must be valid (kills vp_20)."""
        k = 1
        while small_context_counter.count_tokens("word " * k) < 400:  # 500 - 100
            k += 1
        prompt = "word " * k
        assert small_context_counter.count_tokens(prompt) == 400  # calibration guard
        result = small_context_counter.validate_prompt(prompt)
        assert result.is_valid is True
        assert result.error is None

    def test_text_exactly_at_max_is_unchanged(self, token_counter):
        """len(tokens) == max_tokens returns text untouched (kills ttf_4)."""
        text = "word " * 20
        n = token_counter.count_tokens(text)
        assert token_counter.truncate_to_fit(text, max_tokens=n) == text

    def test_prompt_exactly_at_max_skips_truncation(self, token_counter):
        """original_tokens == max_tokens must early-return untouched (kills ted_3)."""
        prompt = "word " * 20
        n = token_counter.count_tokens(prompt)
        result = token_counter.truncate_enrichment_data(prompt, max_tokens=n)
        assert result.was_truncated is False
        assert result.final_tokens == n

    def test_loop_breaks_when_sections_reach_exact_fit(self, small_context_counter):
        """After a removal lands exactly on max_tokens no more sections are removed (kills ted_18)."""
        prompt = (
            "## Depth Context\nLess important depth data.\n\n"
            "## Weather Context\nSunny, clear skies.\n"
        )
        after_depth, removed = small_context_counter._remove_section(prompt, "depth_context")
        assert removed is True
        max_tokens = small_context_counter.count_tokens(after_depth)  # exact fit target
        result = small_context_counter.truncate_enrichment_data(prompt, max_tokens=max_tokens)
        assert result.was_truncated is True
        assert result.sections_removed == ["depth_context"]
        # mutant (loop uses <) does not break on the exact fit and removes weather too
        assert "Weather Context" in result.truncated_prompt
```

### D3 → C4 (1)

```python
class TestSuffixBudgetBoundary:
    """truncate_to_fit token-budget arithmetic at one-token precision."""

    def test_one_content_token_survives_when_budget_is_one(self, token_counter):
        """max_tokens == suffix_tokens + 1 must keep exactly one content token (kills ttf_10)."""
        suffix = " END"
        suffix_tokens = token_counter.count_tokens(suffix)
        text = "word " * 200
        out = token_counter.truncate_to_fit(text, max_tokens=suffix_tokens + 1, suffix=suffix)
        assert out.endswith(suffix)
        assert out != suffix                       # mutant returns the bare suffix
        assert token_counter.count_tokens(out) == suffix_tokens + 1
```

### D4 → C13 (7)

```python
class TestModelNameResolution:
    """model_name resolution and the NEM-3288 gauge label."""

    def test_model_name_defaults_and_explicit(self):
        counter = TokenCounter()
        assert counter.model_name == "nemotron-mini"   # kills init_10/11/20/21/22
        explicit = TokenCounter(model_name="probe-model")
        assert explicit.model_name == "probe-model"    # kills init_12 (chain `and`)

    @patch("backend.core.metrics.set_llm_context_utilization_ratio", autospec=True)
    def test_gauge_is_labelled_with_model_name(self, mock_gauge):
        """The utilization gauge must carry counter.model_name, never None/'unknown'."""
        counter = TokenCounter(model_name="probe-model")
        counter.validate_prompt("hello")
        mock_gauge.assert_called_once_with(
            model="probe-model", utilization=mock.ANY  # add: from unittest.mock import ANY as mock_ANY
        )
        # kills vp_15 (model=None), init_10/11/22 (None → "unknown" after sanitization)
```

Import adjustment for the existing header: `from unittest.mock import ANY, patch` and use `model="probe-model", utilization=ANY`.

### D5 → C11 (1)

```python
class TestWarningThresholdBoundary:
    """The >= comparison that decides whether a warning is emitted."""

    def test_utilization_exactly_at_threshold_warns(self):
        """utilization == warning_threshold must produce a warning (kills vp_37)."""
        # available = 3024 - 1024 = 2000; threshold 0.8 → boundary at exactly 1600 tokens
        counter = TokenCounter(
            encoding_name="cl100k_base",
            context_window=3024,
            max_output_tokens=1024,
            warning_threshold=0.8,
        )
        k = 1
        while counter.count_tokens("word " * k) < 1600:
            k += 1
        prompt = "word " * k
        assert counter.count_tokens(prompt) == 1600  # calibration guard (red-proves here)
        result = counter.validate_prompt(prompt)
        assert result.is_valid is True               # 1600 < 2000
        assert result.warning is not None            # mutant (>) yields None
```

### D6 → C14 (3) + C15 (1) + C16 (2) + C17 (2) = 8

```python
class TestEncodingSelectionAndWrappers:
    """Encoding is honored (not silently replaced) and wrappers forward args."""

    @patch("backend.services.token_counter.tiktoken.get_encoding", autospec=True)
    def test_init_requests_configured_encoding(self, mock_get_encoding):
        """get_encoding must be asked for the configured name, not None (kills init_2/3/26)."""
        mock_get_encoding.return_value.encode.return_value = [1]
        counter = TokenCounter(
            encoding_name="o200k_base", context_window=4096, max_output_tokens=1024
        )
        mock_get_encoding.assert_called_once_with("o200k_base")
        assert counter.encoding_name == "o200k_base"

    def test_invalid_encoding_fallback_still_counts(self):
        """The cl100k_base fallback must produce a working encoder (kills init_28)."""
        counter = TokenCounter(encoding_name="invalid_encoding_xyz")
        assert counter.count_tokens("hello world") > 0

    def test_validate_prompt_tokens_forwards_all_arguments(self):
        """The wrapper must forward prompt AND the output-token override (kills x_vpt_1..4)."""
        result = validate_prompt_tokens("Test prompt", max_output_tokens=1536)
        assert result.max_output_tokens == 1536      # kills x_vpt_2/x_vpt_4 (override→None)
        assert result.available_tokens == result.context_window - 1536
        # x_vpt_1/x_vpt_3 crash: prompt arg replaced by an int → encode(int) → TypeError
```

## Draft → cluster kill map

| Draft | Clusters | Mutants |
|---|---|--:|
| D1 | C7, C8 | 12 |
| D2 | C3 | 4 |
| D3 | C4 | 1 |
| D4 | C13 | 7 |
| D5 | C11 | 1 |
| D6 | C14, C15, C16, C17 | 8 |
| | **TEST-GAP killed (all 33)** | **33** |

Residual after drafts: 45 EQUIVALENT survivors (C1/C2 logging payload mutations 33; provable no-ops C5/C6/C9/C12 5; dead-code/guard/source mutants C10/C18 7). Suggested follow-up if a "kill-equivalents" pass is wanted: a `caplog` + record-field convention, or mark C1/C2 keys as intentionally-equivalent in the baseline notes.

## Covering-test weak-assertion sites (`file:line`)

- `backend/tests/unit/services/test_token_counter.py`
  - :177 `assert result.prompt_tokens < result.available_tokens` — strict `<`, never equality (C3/vp_20)
  - :194 warning test sits at ~81% utilization, never at threshold (C11)
  - :238/:251 truncate_to_fit tests never hit `target_tokens <= 0` / `== 1` (C4; C5/C6 are no-ops)
  - :266 `assert result.final_tokens <= 50` — slack fit; `original_tokens`/re-count never checked; hard-truncation branch never entered (C7/C8)
  - :289 priority test wraps its only assertion in `if result.was_truncated and ...` (soft)
  - :74 default-init test never asserts `model_name` (C13)
  - :103 fallback test never exercises the returned encoder (C15)
  - :473-483 metrics test patches only `observe_context_utilization`, loose float bound; never patches `set_llm_context_utilization_ratio` (C13/vp_15)
  - No `caplog` anywhere in the file (C1/C2)
- `backend/tests/unit/services/test_nemotron_analyzer.py` :3655, :4050, :4088, :4143 — spec'd `MagicMock` counter means real `validate_prompt`/`truncate_*`/`__init__` lines never execute under these 21+ "covering" tests; this is why crash-capable survivors (C7) persist despite huge `tests_by_mangled_function_name` lists.
- `backend/services/nemotron_analyzer.py` :4419-4469 — consumer contract: `is_valid`, `available_tokens`, `was_truncated`, `sections_removed`, `truncated_prompt` are load-bearing; `warning`/`original_tokens`/`final_tokens` are not read.

## Survivor → cluster membership (complete partition)

- C1 (6): init_27, init_35, vp_25, vp_39, ted_26, ted_40
- C2 (27): vp_26, vp_28, vp_29, vp_30, vp_31, vp_32, vp_33, vp_34, vp_35, vp_36, vp_40, vp_42, vp_43, vp_44, vp_45, vp_46, vp_47, vp_48, ted_27, ted_29, ted_30, ted_31, ted_32, ted_33, ted_34, ted_35, ted_36
- C3 (4): vp_20, ttf_4, ted_3, ted_18
- C4 (1): ttf_10
- C5 (1): ttf_9
- C6 (1): ted_39
- C7 (8): ted_38, ted_41, ted_42, ted_43, ted_44, ted_45, ted_46, ted_47
- C8 (4): ted_5, ted_6, ted_48, ted_49
- C9 (2): ted_12, ted_13
- C10 (4): vp_9, vp_11, vp_12, vp_13
- C11 (1): vp_37
- C12 (1): vp_21
- C13 (7): init_10, init_11, init_12, init_20, init_21, init_22, vp_15
- C14 (3): init_2, init_3, init_26
- C15 (1): init_28
- C16 (2): x_vpt_1, x_vpt_3
- C17 (2): x_vpt_2, x_vpt_4
- C18 (3): init_13, init_18, init_19

(`init_` = `xǁTokenCounterǁ__init____mutmut_N`, `vp_` = `validate_prompt`, `ttf_` = `truncate_to_fit`, `ted_` = `truncate_enrichment_data`, `x_vpt_` = module-level `x_validate_prompt_tokens`.)
