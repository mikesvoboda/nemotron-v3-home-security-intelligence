# WP4.4 Triage Dossier — backend/api/routes/prompt_management.py

**Wave**: read-only triage of SURVIVING mutants (no test execution, no repo writes). UNVERIFIED throughout.
**Meta census**: 79 keys, 51 killed, **28 survivors** (module kill rate 51/79 = 64.6%).
**Survivor concentration**: 26 of 28 in `_get_recommended_action` (lines 234-249), 2 in `_compute_config_diff` (lines 389-423). No survivors in any endpoint body.
**Diff source**: `uv run mutmut show <key>` succeeded for all 28 keys (rc=0 each).

## Covering tests (from mutmut-stats.json tests_by_mangled_function_name)

All in **`backend/tests/unit/api/routes/test_prompt_management.py`**:

| Function | Covering tests | What they actually assert |
|---|---|---|
| `x__get_recommended_action` (2 tests) | `TestCustomTestPromptEndpoint::test_test_prompt_returns_results` (:1583), `::test_test_prompt_risk_level_mapping` (:1681) | Only field **presence**: `assert "recommended_action" in data` (:1620). Never the value. Mapping test asserts `risk_level` only. |
| `x__compute_config_diff` (11 tests) | `TestComputeConfigDiff` (:1275-1343, 7 direct-call tests), `TestImportPreviewEndpoint` (:1070, 4 endpoint tests) | Direct tests exist for add/remove/change/list/version-ignoring, but NO list-vs-scalar mismatch case; new-config label checked only by substring `"New configuration" in ...` (:1151, :1283). |

No test file imports `_get_recommended_action` (:28 imports only `_compute_config_diff, router`). Repo-wide grep: the four action strings appear ONLY in prompt_management.py:244-249 — no frontend or other-backend consumer asserts them (frontend has zero references), so the string contract lives solely in this module and is unpinned by any test.

## Cluster table (counts sum to 28)

| # | Pattern (function / mutation kind) | Count | Example keys (≤3) | Classification | Why survivors slip through |
|---|---|---|---|---|---|
| C1 | `_get_recommended_action` (:244-247): dict **key** clobbered (`"low"`→`"XXlowXX"`) or case-flipped (`"LOW"`) → lookup miss returns generic default for that risk level | 8 | `..._x__get_recommended_action__mutmut_2`, `_mutmut_3`, `_mutmut_12` | TEST-GAP | Endpoint runs the lookup for every request (mapping test drives all 4 levels) but never asserts `recommended_action`'s value — only `"recommended_action" in data` (:1620) |
| C2 | `_get_recommended_action` (:244-247): dict **value** clobbered (`"XXMonitor - ...XX"`) or case-flipped (`"monitor - ..."`) → wrong recommendation text returned | 12 | `_mutmut_4`, `_mutmut_5`, `_mutmut_19` | TEST-GAP | Same absence: the response text is the entire product output of this helper; no test compares it. 8 case-only members are borderline-LOW-VALUE (prose case), but they die for free to the same exact-match assertion that kills the 4 copy-corruption members, so the cluster stays TEST-GAP |
| C3 | `_get_recommended_action` (:249): lookup key arg → `None` (`actions.get(None, "Review event details")`) → function ALWAYS returns the generic default regardless of level | 1 | `_mutmut_22` | TEST-GAP | Kills every per-level mapping; invisible because value is never asserted (same gap as C1/C2) |
| C4 | `_get_recommended_action` (:249): fallback **default arg** mutated — `None` (`_mutmut_23`), dropped (→None, `_mutmut_25`), clobbered (`"XXReview event detailsXX"`, `_mutmut_26`), case-flipped (`_mutmut_27`, `_mutmut_28`) | 5 | `_mutmut_23`, `_mutmut_25`, `_mutmut_26` | TEST-GAP | Unknown-level path is unreachable from the endpoint (callers always pass a canonical level), so no endpoint test can pin it; the helper's graceful-fallback is real intended behavior — `None` here would even break the required `recommended_action: str` field (schemas/prompt_management.py:819) with a 500 if any future caller passes a non-canonical level. Needs a direct helper unit test |
| C5 | `_compute_config_diff` (:397): new-config label `"New configuration (no existing version)"` XX-decorated | 1 | `..._x__compute_config_diff__mutmut_4` | TEST-GAP | Tests at :1151 and :1283 use substring `"New configuration" in ...` — the decoration keeps the substring, so the assertion passes on the mutant. Classic "test exists but asserts too weakly" |
| C6 | `_compute_config_diff` (:412): `isinstance(current[key], list) and isinstance(imported[key], list)` flipped to `or` → branch entered when only ONE side is a list → `set()` over a scalar raises **TypeError** (e.g. `set(5)` → 500 on `/import/preview`) or does char-set math over a string (`set("ab")` → bogus `Added ['a','b']` diff instead of `Changed: items`) | 1 | `..._x__compute_config_diff__mutmut_22` | TEST-GAP | `test_diff_list_changes` (:1323) uses list-vs-list only; `test_diff_changed_value` (:1313) uses scalar-vs-scalar. No list-vs-scalar mismatch test exists — the highest-severity survivor (crash-class) |

**Totals: 8+12+1+5+1+1 = 28 = survivors_total.** No EQUIVALENT (every survivor changes observable output for some input) and no cluster fully LOW-VALUE (C2's case-only half noted above is pinned by the same drafted assertion).

## Drafted tests — UNVERIFIED - not yet run red/green

All target `backend/tests/unit/api/routes/test_prompt_management.py`. Style matches the file: direct-helper class like `TestComputeConfigDiff`, for-loop table like `test_test_prompt_risk_level_mapping` (:1681), `-> None` hints, no `parametrize` (file uses zero parametrize).
Import edit required: line 28 → `from backend.api.routes.prompt_management import _compute_config_diff, _get_recommended_action, router`

### T1 — pin per-level recommendation text (kills C1 + C2 + C3 = 21 mutants)

```python
class TestGetRecommendedAction:
    """Tests for _get_recommended_action helper function."""

    def test_recommended_action_exact_for_each_known_level(self) -> None:
        """Each canonical risk level maps to its exact documented action."""
        expected_actions = {
            "low": "Monitor - No immediate action required",
            "medium": "Review - Check event details when convenient",
            "high": "Investigate - Review event details promptly",
            "critical": "Alert - Immediate attention required",
        }

        for level, expected_action in expected_actions.items():
            assert _get_recommended_action(level) == expected_action

    def test_recommended_action_levels_are_distinct(self) -> None:
        """Sanity: no two levels collapse onto the same action (kills key-clobbers that alias to default)."""
        actions = {_get_recommended_action(level) for level in ("low", "medium", "high", "critical")}
        assert len(actions) == 4
```
TDD: exact-match fails on every C1 mutant (lookup miss returns the default string), every C2 mutant (case/decoration differs), and C3 (always-default); passes on original.

### T2 — pin the unknown-level fallback (kills C4 = 5 mutants)

```python
    def test_recommended_action_unknown_level_falls_back(self) -> None:
        """Non-canonical risk level returns the generic review action, never None."""
        assert _get_recommended_action("unknown") == "Review event details"
        assert _get_recommended_action("") == "Review event details"
```
TDD: fails on `_mutmut_23`/`_mutmut_25` (returns None) and `_mutmut_26`/`_27`/`_28` (text differs); passes on original. Direct-call only — the fallback is unreachable through the endpoint, hence the helper-level test (same pattern as `TestComputeConfigDiff`).

### T3 — list-vs-scalar mismatch (kills C6 = 1 mutant, crash-class)

```python
    def test_diff_list_vs_scalar_is_reported_as_changed(self) -> None:
        """List value replaced by scalar is 'Changed', not set-diffed character-wise."""
        current = {"items": ["a", "b"], "version": 1}
        imported = {"items": "a"}

        has_changes, changes = _compute_config_diff(current, imported)

        assert has_changes is True
        assert changes == ["Changed: items"]

    def test_diff_scalar_vs_list_does_not_raise(self) -> None:
        """Scalar value replaced by list is 'Changed' — set() must not be applied to the scalar (TypeError guard)."""
        current = {"items": 5, "version": 1}
        imported = {"items": [1, 2]}

        has_changes, changes = _compute_config_diff(current, imported)

        assert has_changes is True
        assert changes == ["Changed: items"]
```
TDD: on the `or` mutant the first test produces `items: Removed [...]` char-set noise (assert fails) and the second raises `TypeError: 'int' object is not iterable` (test errors); both pass on original. Add inside existing `TestComputeConfigDiff` (:1275).

### T4 — exact new-config label (kills C5 = 1 mutant)

```python
    def test_diff_new_config_label_exact(self) -> None:
        """New-configuration entry carries the exact contract label (substring match would let decorations pass)."""
        has_changes, changes = _compute_config_diff(None, {"key": "value"})

        assert has_changes is True
        assert changes == ["New configuration (no existing version)"]
```
TDD: exact equality fails on the XX-decorated label; passes on original. (Prefer adding alongside `test_diff_new_config` :1278; the endpoint twin at `test_import_preview_new_configuration` :1130 could likewise be tightened from `"New configuration" in ...` to equality on `data["diffs"][0]["changes"][0]`.)

## Kill-set reconciliation

| Draft | Kills | Running total |
|---|---|---|
| T1 | C1(8) + C2(12) + C3(1) = 21 | 21 |
| T2 | C4 (5) | 26 |
| T3 | C6 (1) | 27 |
| T4 | C5 (1) | **28 / 28** |

If all four pass green on original, module kill rate moves 51/79 → 79/79 (100%).

## Verification protocol (for the serial pytest lane, not this triage)

1. Sync the edited test file into `mutants/` before any kill-probe (stale-mutants-tree protocol — see memory `mutants-tree-test-sync-trap`).
2. Red on mutant copies for each example key per cluster (at minimum: `_get_recommended_action__mutmut_2`, `_mutmut_5`, `_mutmut_22`, `_mutmut_23`, `_compute_config_diff__mutmut_4`, `_compute_config_diff__mutmut_22`).
3. Green on the pristine tree, then full module run.
