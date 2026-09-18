# WP4.4 Triage Dossier — backend/api/routes/logs.py

- **Meta:** `mutants/backend/api/routes/logs.py.meta` — 116 mutants, 54 killed, **62 survived**, 0 unchecked.
- **All 62 survivors are in `_log_frontend_entry`** (backend/api/routes/logs.py:118-207). Every other function in the module is fully killed.
- **Covering tests:** `backend/tests/unit/api/routes/test_logs.py` — class `TestLogFrontendEntryHelper` (lines 54-167; 6 tests, per `mutmut-stats.json` `tests_by_mangled_function_name`). The endpoint classes `TestIngestFrontendLog*` patch out `_log_frontend_entry` and cover none of these mutants.
- Diffs captured read-only via `uv run mutmut show <key>` (all 62 succeeded); raw dump: `/tmp/wp25/wp44-triage/logs_diffs_raw.txt`. Key list: `/tmp/wp25/wp44-triage/logs_surv_keys.txt`.

## Why the existing tests miss everything

`TestLogFrontendEntryHelper` asserts only: return True/False, `log.assert_called_once()`, the positional level int and message substring (`call_args[0][0]`, `call_args[0][1]`), `extra` key **presence** (`"ctx_action" in extra` — never values), `extra["frontend_user_agent"]` values in two tests (the only value-level extra assertions in the file), and `logger.warning.assert_called_once()` on the exception path — never the warning text.

Unexecuted-as-asserted, therefore: the entire `extra` Loki-label contract (key names + values for `source`/`frontend_component`/`frontend_url`/`frontend_timestamp`), all `max_length=` sanitization caps, the message/component truncation behavior, and the context item/size budget loops (logs.py:155-184).

## Cluster table (verified signature fold; counts sum to 62)

| id | pattern (mutation kind @ function/concern) | n | class | example keys (`x__log_frontend_entry__mutmut_N`) |
|---|---|---|---|---|
| C1 | `extra` dict key `XXclobberXX` renames (source/frontend_component/frontend_url/frontend_timestamp×2) | 5 | TEST-GAP | 2, 6, 18 |
| C2 | `extra` dict key CASE renames (`"SOURCE"`, `"FRONTEND_COMPONENT"`, …) | 5 | TEST-GAP | 3, 7, 19 |
| C3 | `extra` field-value damage: `"XXfrontendXX"`/`"FRONTEND"` source value (4,5), `"None"`-producing sanitize-input swaps (10,20,78), drop-value-to-`None` (17,45,77), `"unknown"` fallback clobbers (15,16), `datetime.now(None)` naive-local timestamp (51), missing-fallback (48) | 12 | TEST-GAP | 10, 51, 77 |
| C5 | `[component]` message-label fallback `or "frontend"` string clobber in log text | 2 | TEST-GAP | 105, 106 |
| C6 | sanitize `max_length=` tweaks: dropped-to-default-10000 or ±1 on 8 call sites (component 13/14, url 23/24, entry-UA 31/32, header-UA 43/44, ctx-key 75/76, ctx-value 81/82, message 97/98, label 103/107) | 17 | TEST-GAP | 24, 82, 97 |
| C7 | context 20-item-cap bypass (`max_context_items` 21 = 57; `>=`→`>` = 64; counter `-=` = 86; `+= 2` = 87) | 4 | TEST-GAP | 57, 64, 87 |
| C8 | ctx key length-50 boundary (`<=`→`<` drops 50-char key = 62; `<= 51` admits 51-char key = 63) | 2 | TEST-GAP | 62, 63 |
| C9 | context 10KB cumulative-budget arithmetic (seed 1 = 53; max 10001 = 55; `item_size` minus = 68; `size - item >` = 69; `>=` = 70; `size = item` reset = 83; `size -= item` = 84) | 7 | TEST-GAP | 53, 69, 83 |
| C10 | `item_count` seeded 1 (59) / assignment-1 instead of `+=` (85) — cap never reached, 21st item admitted | 2 | TEST-GAP | 59, 85 |
| C11 | `value_str = str(None)` — feeds size math only; stored value unaffected | 1 | LOW-VALUE | 66 |
| C12 | `value is not None or len(key) <= 50` — admits None values only when a >50-char key is present, which the item filter already excludes in production (schema caps keep keys short in practice) | 1 | LOW-VALUE | 60 |
| C13 | exception handler `logger.warning(None)` — diagnostic text lost; test asserts the call, not the message | 1 | LOW-VALUE | 115 |
| C14 | `_LOG_LEVEL_MAP.get(..., INFO)` default tweaks (`None` = 90, dropped = 92) — default unreachable: `FrontendLogLevel` enum values all exist in the map (completeness already asserted by `test_log_level_map_has_all_levels`) | 2 | EQUIVALENT | 90, 92 |
| C15 | `entry.component` guard boolean forced (`and False` = 8 → always "unknown"; `or True` = 9 → sanitize(None) → "None") | 2 | TEST-GAP | 8, 9 |

**Classification totals: TEST-GAP 57, LOW-VALUE 3, EQUIVALENT 2. Sum = 62 ✔** (fold verified programmatically: exact partition of the survivor list, each key's diff text matches its cluster signature).

Notes on judgment calls:
- **51 is TEST-GAP, not EQUIVALENT**: `datetime.now(None)` is naive **local** time. This sandbox runs EDT (UTC-4), so the ISO string differs in wall-clock value *and* offset suffix; on UTC CI it still loses `+00:00`. Downstream structured-logging consumers parsing `frontend_timestamp` get wrong/ambiguous times either way.
- **115 kept LOW-VALUE** (diagnostic text), but a one-line assertion is drafted since it's free.
- **C6's 17 keys split by reachability**: 9 are killable with schema-legal inputs (23, 24 url; 43, 44 header-UA; 81, 82 ctx-value; 97, 98 message; +103 no — see residuals), 8 are schema-shielded (component cap 13/14: `FrontendLogEntry.component` has `max_length=100` in backend/api/schemas/logs.py:83, so caps 100/101/10000 are indistinguishable; entry-UA 31/32: schema `max_length=500` (line 90); ctx-key 75/76: keys >50 are already excluded by the loop filter (logs.py:166), so caps never bite; label 103: component ≤100 → default 10000 vs 100 never differs). These are equivalent-in-practice and documented as acceptable residuals — do not write contorted mock-schema tests for them.

## Drafted tests

All in `backend/tests/unit/api/routes/test_logs.py`, class `TestLogFrontendEntryHelper`, existing style (patch `backend.api.routes.logs.frontend_logger` `autospec=True`, inspect `mock_logger.log.call_args`). **All UNVERIFIED — not yet run red/green.**

TDD procedure: with each drafted assertion, run the test against each mutant copy region → assertion fails (red) on the mutant diff, passes (green) on original `backend/api/routes/logs.py`.

### T1 — `test_log_entry_extra_matches_frontend_contract` (kills C1 4, C2 5, C3: 4,5,10,17,20,45, C15 2; keys 2-10,17-20,45-47,50 = 17)

```python
def test_log_entry_extra_matches_frontend_contract(self):
    """extra must carry the exact Loki label keys/values documented in the module docstring."""
    ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
    entry = FrontendLogEntry(
        level=FrontendLogLevel.INFO,
        message="Contract",
        component="Dashboard",
        url="https://example.com/dash",
        user_agent="TestBrowser/1.0",
        timestamp=ts,
    )

    with patch("backend.api.routes.logs.frontend_logger", autospec=True) as mock_logger:
        assert _log_frontend_entry(entry) is True

    extra = mock_logger.log.call_args[1]["extra"]
    assert extra["source"] == "frontend"
    assert extra["frontend_component"] == "Dashboard"
    assert extra["frontend_url"] == "https://example.com/dash"
    assert extra["frontend_user_agent"] == "TestBrowser/1.0"
    assert extra["frontend_timestamp"] == ts.isoformat()
    assert set(extra.keys()) == {
        "source",
        "frontend_component",
        "frontend_url",
        "frontend_user_agent",
        "frontend_timestamp",
    }
```

Kill note: the key-set assert kills every C1/C2 rename reachable on the timestamp-provided path (renamed key lands outside the set and the expected key raises KeyError); value asserts kill 4,5 (source value), 8,9 (guard forced → `"unknown"`/`"None"` != `"Dashboard"`), 10,20 (sanitize(None) → `"None"`), 17,45 (value `None`), 46,47,50 (timestamp-key rename/case on the provided-timestamp branch). 49 renames the key only on the no-timestamp branch and is killed by T2's key-set assert instead.

### T2 — `test_log_entry_minimal_extra_falls_back_to_unknown_and_utc` (kills C3: 15,16,48,51 + timestamp-key rename 49; keys 15,16,48,49,51 = 5)

```python
def test_log_entry_minimal_extra_falls_back_to_unknown_and_utc(self):
    """No component/url/UA/timestamp: fallbacks are 'unknown' and a UTC-aware now-ISO."""
    entry = FrontendLogEntry(level=FrontendLogLevel.INFO, message="Minimal")

    with patch("backend.api.routes.logs.frontend_logger", autospec=True) as mock_logger:
        assert _log_frontend_entry(entry) is True

    extra = mock_logger.log.call_args[1]["extra"]
    assert extra["frontend_component"] == "unknown"  # kills 15, 16
    assert set(extra.keys()) == {"source", "frontend_component", "frontend_timestamp"}
    stamp = datetime.fromisoformat(extra["frontend_timestamp"])  # 48 (None) raises TypeError
    assert stamp.tzinfo is not None  # kills 51: datetime.now(None) is naive local
    assert abs((datetime.now(UTC) - stamp).total_seconds()) < 5
```

### T3 — `test_log_entry_sanitize_caps_and_label` (kills C3: 77,78; C5 2; C6: 23,24,43,44,81,82,97,98; keys 23,24,43,44,77,78,81,82,97,98,105,106)

```python
def test_log_entry_sanitize_caps_and_label(self):
    """Sanitization caps: message@5000, url@500, header UA@500, ctx value@1000; label 'frontend'."""
    entry = FrontendLogEntry(
        level=FrontendLogLevel.INFO,
        message="A" * 6000,  # schema allows up to 10000
        component=None,
        url="https://" + "u" * 600,
        context={"k": "B" * 1500},
    )
    mock_request = MagicMock(spec=Request)
    mock_request.headers.get.return_value = "H" * 600

    with patch("backend.api.routes.logs.frontend_logger", autospec=True) as mock_logger:
        assert _log_frontend_entry(entry, mock_request) is True

    log_text = mock_logger.log.call_args[0][1]
    assert log_text.startswith("[frontend] ")  # kills 105, 106
    assert log_text == "[frontend] " + "A" * 5000 + "...[truncated]"  # kills 97, 98

    extra = mock_logger.log.call_args[1]["extra"]
    assert extra["frontend_url"] == ("https://" + "u" * 600)[:500] + "...[truncated]"  # kills 23, 24
    assert extra["frontend_user_agent"] == "H" * 500 + "...[truncated]"  # kills 43, 44
    assert extra["ctx_k"] == "B" * 1000 + "...[truncated]"  # kills 77, 78, 81, 82
```

### T4 — `test_log_entry_context_item_and_key_limits` (kills C7 4, C8 2, C10 2; keys 57,59,62,63,64,85,86,87)

```python
def test_log_entry_context_item_and_key_limits(self):
    """Keep exactly 20 items; keys of length 50 admitted, 51 excluded; 21st item dropped."""
    key50, key51 = "a" * 50, "a" * 51
    ctx = {key50: "ok", key51: "nope", **{f"k{i}": "v" for i in range(21)}}
    entry = FrontendLogEntry(level=FrontendLogLevel.INFO, message="Ctx", context=ctx)

    with patch("backend.api.routes.logs.frontend_logger", autospec=True) as mock_logger:
        assert _log_frontend_entry(entry) is True

    ctx_keys = {k for k in mock_logger.log.call_args[1]["extra"] if k.startswith("ctx_")}
    assert "ctx_" + key50 in ctx_keys  # kills 62 (len(key) < 50 drops it)
    assert "ctx_" + key51 not in ctx_keys  # kills 63 (<= 51 admits it)
    assert "ctx_k19" in ctx_keys  # 20th admitted item; kills 59, 85, 87 (counter drift drops it)
    assert "ctx_k20" not in ctx_keys  # kills 57, 64, 86 (cap-off-by-one admits the 21st)
```

Ordering note: key50/key51 go first so the length-boundary asserts are independent of the 20-item cap (key51 is filtered without incrementing `item_count`; key50 counts as item 1, k0..k19 as items 2..20, k20 trips the `item_count >= 20` guard).

### T5 — `test_log_entry_context_cumulative_size_budget` (kills C9 7; keys 53,55,68,69,70,83,84)

```python
def test_log_entry_context_cumulative_size_budget(self):
    """10KB cumulative guard: strict > break from a zero base, true accumulation."""
    witnesses = [
        # (context, must-admit, must-drop) — sizes = len(key)+len(str(value))
        ({"ab": "x" * 9998, "cd": "y"}, {"ab"}, {"cd"}),  # 0+10000 ok, 10003>10000 break.
        # 70 (>=): breaks AT 10000 -> ab absent; 53 (seed 1): 1+10000>10000 -> ab absent;
        # 68 (item_size=key-value=-9996) & 69 (size-item): cd admitted.
        ({"ab": "x" * 9998, "c": ""}, {"ab"}, {"c"}),  # exact-10001: orig breaks;
        # 55 (max 10001) admits c; 84 (size -= item) makes size negative -> admits c.
        ({"aaaa": "x" * 5996, "bbb": "y" * 97, "cccc": "z" * 5996}, {"aaaa", "bbb"}, {"cccc"}),
        # sizes 6000,100,6000: orig 6100 then 12100 break;
        # 83 (size = item, reset): 100+6000 ok -> admits cccc.
    ]
    with patch("backend.api.routes.logs.frontend_logger", autospec=True) as mock_logger:
        for ctx, must, must_drop in witnesses:
            assert _log_frontend_entry(
                FrontendLogEntry(level=FrontendLogLevel.INFO, message="W", context=ctx)
            ) is True
            extra = mock_logger.log.call_args[1]["extra"]
            assert all(f"ctx_{k}" in extra for k in must), ctx
            assert all(f"ctx_{k}" not in extra for k in must_drop), ctx
```

### T6 — one-line addition to existing `test_log_entry_returns_false_on_exception` (kills C13: 115)

In `backend/tests/unit/api/routes/test_logs.py` after line 167 (`mock_route_logger.warning.assert_called_once()`):

```python
            assert (
                "Failed to process frontend log entry" in mock_route_logger.warning.call_args[0][0]
            )
```

## Kill ledger (62 = 50 drafted kills + 8 schema-shielded + 2 LOW-VALUE kept open + 2 EQUIVALENT)

| Drafted test | Kills (mutant N) | n |
|---|---|---|
| T1 contract | 2,3,4,5,6,7,8,9,10,17,18,19,20,45,46,47,50 | 17 |
| T2 minimal fallback/UTC | 15,16,48,49,51 (49: key-set assert on the no-timestamp branch) | 5 |
| T3 caps + label | 23,24,43,44,77,78,81,82,97,98,105,106 | 12 |
| T4 item/key limits | 57,59,62,63,64,85,86,87 | 8 |
| T5 size budget | 53,55,68,69,70,83,84 | 7 |
| T6 warning text | 115 | 1 |
| **drafted total** | | **50** |
| Schema-shielded residuals (equivalent-in-practice; NOT drafted — see C6 note) | 13,14,31,32,75,76,103,107 | 8 |
| LOW-VALUE kept open | 60 (C12), 66 (C11) | 2 |
| EQUIVALENT | 90,92 (C14) | 2 |

50 + 8 + 2 + 2 = **62** ✔

## Covering test file references

- `backend/tests/unit/api/routes/test_logs.py:54-167` — `TestLogFrontendEntryHelper`, covering class for all 62
- `backend/tests/unit/api/routes/test_logs.py:151-167` — exception test to extend (T6)
- `backend/api/schemas/logs.py:78-90` — schema caps (`component` ≤100, `message` ≤10000, `url` ≤2000, `user_agent` ≤500) that shield the 8 residual mutants
- `backend/core/logging.py:1041-1104` — `sanitize_log_value` (truncation marker `"...[truncated]"` used verbatim in T3/T5 asserts)

## Verification-lane caveats

- Red/green NOT run here (harness constraint). T4/T5 boundary arithmetic was derived by hand from the loop semantics (logs.py:164-184) — re-check `ctx_` key counts against the exact insertion order before trusting green.
- T1's exact-key-set assert assumes no `ctx_*` keys with a context-free entry — correct for both original and all survivors in scope.
- `sanitize_log_value(value, max_length=...)` on a `dict`-typed ctx value stringifies before truncating; T3's `"B"*1500` is a str, so no stringification surprise.
