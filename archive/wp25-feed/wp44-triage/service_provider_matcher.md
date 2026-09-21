# WP4.4 Triage Dossier — backend/services/service_provider_matcher.py

- **Survivors:** 39 of 126 keys (meta `mutants/backend/services/service_provider_matcher.py.meta`)
- **Diff source:** `uv run mutmut show <key>` for all 39 (no fallback needed)
- **Covering test file (primary):** `backend/tests/unit/services/test_service_provider_matcher.py`
- **Secondary executor (never asserts these fields):** `backend/tests/unit/services/test_scene_ocr_service.py` (imports only `ServiceMatch`), consumer context: `backend/services/scene_ocr_service.py`
- **Classification split:** TEST-GAP 26 / EQUIVALENT 13 / LOW-VALUE 0

## Why risk_modifier / category / confidence matter to production (kills LOW-VALUE drift)

`scene_ocr_service.py` serializes exactly `provider/category/confidence/risk_modifier` into the OCR
result dict (`DetectionOCRResult.to_dict` → `service_match.to_dict`, scene_ocr_service.py:145-146) and
feeds `service_match.category` into `record_scene_ocr_provider_match` (scene_ocr_service.py:470).
`matched_alias` is NOT serialized (ServiceMatch.to_dict, matcher.py:101-108) — it is the documented
debug field. So mutants of the first four fields are real production-behavior changes → TEST-GAP;
matched_alias-only mutants are flagged with that nuance but still killable via public API contract.

## Key DB facts verified live against the shipped module (no tests were run)

- `SERVICE_CATEGORIES`: **every** category has a `risk_modifier` key; the ONLY non-default modifier is
  `EMERGENCY → "authority"`. No provider references a missing category. ⇒ every
  `.get("risk_modifier", DEFAULT)` default and the ternary's `else` branch is **unreachable** with the
  shipped table — that is why the 13 "dead-default" mutants survive.
- EMERGENCY providers: Police, Fire Department, Ambulance, Sheriff (all exact-alias reachable).
- Cross-provider normalized alias collisions: **none** (189 keys in `_exact_lookup`).
- `rapidfuzz fuzz.ratio(x, "")` == 0.0 for any x ⇒ the levenshtein empty-guard flip is value-equivalent.
- Boundary input `"Southern Californ"` → exact score **0.85** (== DEFAULT_MATCH_THRESHOLD), SoCalGas/UTILITY,
  confidence 0.85, matched_alias `"Southern California Gas"`.
- Fuzzy multi-pass input `"Police Departm"` (not an exact alias): "Police Department" 0.9032 and
  "Police Dept" 0.88 both ≥ 0.85 ⇒ original returns Police/EMERGENCY/0.9032/authority/"Police Department".
- Tie input (custom providers): `"ABCDEFGHIJKLMNOPQRST"` vs `ABCDEFGHIJKLMNOPQRSZ` / `ZABCDEFGHIJKLMNOPQRS`
  → both 0.95; original first-wins → "Alpha Services".
- No cross-provider top-score ties exist at/above 0.85 among DB-alias truncations (53 same-provider alias
  ties do exist — they only shuffle matched_alias case).

## Cluster table (counts sum to 39)

| # | Pattern | Count | Keys (≤3 examples) | Class | Kill / rationale |
|---|---------|-------|--------------------|-------|------------------|
| 1 | `levenshtein_ratio`: empty-guard `or`→`and` | 1 | `x_levenshtein_ratio__mutmut_1` | EQUIVALENT | Mutant defers one-empty calls to `fuzz.ratio`, which returns 0.0 for empty-vs-nonempty (verified). Identical output for every str input. |
| 2 | `__init__`: debug log message replaced by `None` | 1 | `…__init____mutmut_16` | EQUIVALENT | Pure log text; `logger.debug(None)` formats "None", no behavior. |
| 3 | `match()`: empty/whitespace guard `or`→`and` | 1 | `…match__mutmut_1` | EQUIVALENT | Whitespace-only input falls through to fuzzy, which matches nothing (`ratio("",alias)`=0.0) → None anyway. Only diff is off-contract `None` input (AttributeError vs None). |
| 4 | `match()` exact path: risk_modifier lookup degenerated to fallback (`entry=None`, `.get(None)`, `and False`, wrong keys `XXrisk_modifierXX`/`RISK_MODIFIER`) | 6 | `match__8, match__9, match__11` (+13,17,18) | TEST-GAP | Exact path runs in ~20 tests but every asserted provider (FedEx/UPS/USPS/Amazon/PG&E/AT&T) maps to "low_risk_service", so fallback==correct. Nothing asserts the only distinguishing modifier `authority` (EMERGENCY). Kill: `test_exact_match_emergency_has_authority_modifier`. |
| 5 | `match()` exact path: `.get("risk_modifier", DEFAULT)` default mutated / `or True` ternary | 5 | `match__12, match__14, match__16` (+19,20) | EQUIVALENT | Default and `else` branch fire only when the `risk_modifier` key / category entry is missing — unreachable with the shipped table (verified: all 15 entries have the key). Differs only on a self-inconsistent custom categories dict (crash vs fallback) — nobody should assert that. |
| 6 | `__init__` alias index + `match()` exact-path `matched_alias` identity unasserted | 4 | `__init__9 (normalized=None), __init__10 (.lower()), match__25 (matched_alias=None), match__30 (kwarg dropped)` | TEST-GAP | With `providers=None`-style clobber the exact O(1) index is destroyed, yet every existing assertion (provider/category/confidence) is reproduced verbatim by the fuzzy fallback (score 1.0 ⇒ confidence 1.0) — matched_alias is the only observable difference (exact path stores the normalized input "FEDEX GROUND"; fuzzy stores the DB alias "FedEx Ground"). Public dataclass field with documented meaning; note it is not serialized to Nemotron (debug-only). Kill: `test_exact_match_populates_normalized_matched_alias`. |
| 7 | `_fuzzy_match` scoring predicate: `>=`→`>` threshold, `>`→`>=` tiebreak, `best_score=None` | 3 | `_fuzzy_match__14, _fuzzy_match__15, _fuzzy_match__16` | TEST-GAP | `__14`: only exact-0.85 inputs affected ("Southern Californ" → mutant returns None). `__15`: tie order flipped (killable via injected providers; original first-wins is the determinism contract of the public `providers=` API). `__16`: any input where a 2nd alias clears the threshold raises `TypeError: '>' not supported between float and None` — "Police Departm" does exactly that. Existing suite never hits a 2-pass fuzzy input (checked all fuzzy tests). Kills: `test_fuzzy_match_boundary_score_included`, `test_fuzzy_match_first_alias_wins_on_tie`, `test_fuzzy_match_emergency_full_result_fields`. |
| 8 | `_fuzzy_match` risk_modifier lookup degenerated to fallback (`entry=None`, `.get(None)`, `risk_modifier=None`, `and False`, `.get("low_risk_service")` (always None), wrong keys) | 8 | `_fuzzy_match__24, _fuzzy_match__25, _fuzzy_match__26` (+27,29,31,33,34) | TEST-GAP | Mirror of #4 on the fuzzy path: no fuzzy-path test asserts risk_modifier at all (fuzzy tests assert only provider/confidence — test file :298-365). Kill: `test_fuzzy_match_emergency_full_result_fields`. |
| 9 | `_fuzzy_match`: `.get("risk_modifier", DEFAULT)` default mutated / `or True` ternary | 5 | `_fuzzy_match__28, _fuzzy_match__30, _fuzzy_match__32` (+35,36) | EQUIVALENT | Same dead-default argument as #5 for the fuzzy path. |
| 10 | `_fuzzy_match` ServiceMatch return construction: `category=None`, `risk_modifier=None`, `matched_alias=None`/dropped, `round(...,4)`→`round(...,5)` | 5 | `_fuzzy_match__38, _fuzzy_match__40, _fuzzy_match__41` (+46,51) | TEST-GAP | No fuzzy test asserts category (→ serialized into OCR result + metrics, production-impacting) or pins the 4-decimal confidence contract (`0.9032` vs `0.90323` flows to the Nemotron prompt). matched_alias nils (__41/__46) are the debug field — kept in this cluster since the same kill test covers them. Kill: `test_fuzzy_match_emergency_full_result_fields`. |

Sum: 1+1+1+6+5+4+3+8+5+5 = **39** ✓ (TEST-GAP 26, EQUIVALENT 13, LOW-VALUE 0)

## Why existing tests miss these (file:line anchors)

`backend/tests/unit/services/test_service_provider_matcher.py`
- `TestLevenshteinRatio` :33-55 — exercises the guard only with `("",""), ("FedEx",""), ("","FedEx")`; mutant #1 returns the same 0.0.
- `TestServiceProviderMatcherExactMatch` :166-225 — asserts provider/category/confidence, never matched_alias or risk_modifier.
- `TestServiceProviderMatcherFuzzyMatch` :289-365 — asserts provider/confidence only; two tests are conditional (`if result is not None`), which can never fail on a mutant that returns None.
- `TestServiceProviderMatcherEdgeCases.test_match_returns_correct_risk_modifier` :632-639 — the only risk_modifier-through-match test; uses FedEx/UPS/Amazon/PG&E/AT&T, i.e. only providers whose correct answer **equals the fallback default** → kills nothing.
- `TestServiceProviderMatcherConfidenceScores` :647-677 — never pins an exact rounded value (`0.9032`).
- `TestServiceProviderMatcherCustomThreshold` :759-780 — both tests assert *no match*, so the `>=` boundary is never approached from the match side.
- `TestServiceProviderMatcherCategoryInfo` :723-751 — asserts `authority` only via `get_category_info`, never through `match()`.

## Drafted tests (UNVERIFIED — not yet run red/green)

Append to `backend/tests/unit/services/test_service_provider_matcher.py`.
Add `ProviderEntry` to the existing import block (lines 19-26) for the tie test.
TDD procedure: each test fails on the cluster's mutant diff (named value mismatch / TypeError / None-return) and passes on the original — confirm red under `mutmut run` re-check of the listed keys, green on unmutated source.

```python
# =============================================================================
# ServiceProviderMatcher Risk-Modifier & Result-Field Coverage (WP4.4 mutants)
# =============================================================================


class TestServiceProviderMatcherRiskAndFields:
    """Pin the observable fields the current suite never asserts.

    Every category except EMERGENCY maps to "low_risk_service", so all existing
    risk_modifier coverage passes even when the lookup degenerates to its
    fallback. These tests use the only non-default modifier ("authority") and
    assert the full ServiceMatch field set on both the exact and fuzzy paths.
    """

    @pytest.fixture
    def matcher(self) -> ServiceProviderMatcher:
        """Create a ServiceProviderMatcher instance."""
        reset_service_provider_matcher()
        return get_service_provider_matcher()

    def test_exact_match_emergency_has_authority_modifier(
        self, matcher: ServiceProviderMatcher
    ) -> None:
        """Exact EMERGENCY match must resolve risk_modifier 'authority'.

        Kills cluster 4 (match__8/9/11/13/17/18): each degenerated lookup yields
        "low_risk_service" here instead of "authority".
        """
        result = matcher.match("Police")  # exact alias "POLICE"

        assert result is not None
        assert result.provider == "Police"
        assert result.category == "EMERGENCY"
        assert result.confidence == 1.0
        assert result.risk_modifier == "authority"

    def test_exact_match_populates_normalized_matched_alias(
        self, matcher: ServiceProviderMatcher
    ) -> None:
        """Exact path stores the normalized input as matched_alias.

        Kills cluster 6 (__init__9/10, match__25/30): with the alias index
        clobbered the call falls through to the fuzzy path, which yields
        matched_alias "FedEx Ground" (the DB alias string) instead of the
        normalized "FEDEX GROUND"; the None/"" variants fail the same assert.
        """
        result = matcher.match("  fedex ground  ")

        assert result is not None
        assert result.provider == "FedEx"
        assert result.confidence == 1.0
        assert result.matched_alias == "FEDEX GROUND"

    def test_fuzzy_match_emergency_full_result_fields(
        self, matcher: ServiceProviderMatcher
    ) -> None:
        """Fuzzy EMERGENCY match returns the complete, rounded result.

        "Police Departm" is not an exact alias; it scores 0.9032 against
        "Police Department" and 0.88 against "Police Dept" — two aliases above
        threshold, so the best-score bookkeeping line executes a second time.
        Kills cluster 8 (all 8 lookup-degeneration mutants: authority expected),
        cluster 10 (__38 category, __40 risk_modifier, __41/__46 matched_alias,
        __51 pins the 4-decimal rounding: mutant yields 0.90323), and
        cluster 7's __16 (best_score=None raises TypeError on the 2nd pass).
        """
        result = matcher.match("Police Departm")

        assert result is not None
        assert result.provider == "Police"
        assert result.category == "EMERGENCY"
        assert result.confidence == 0.9032
        assert result.risk_modifier == "authority"
        assert result.matched_alias == "Police Department"

    def test_fuzzy_match_boundary_score_included(
        self, matcher: ServiceProviderMatcher
    ) -> None:
        """Similarity exactly at the threshold must match (>=, not >).

        "Southern Californ" scores exactly 0.85 vs alias
        "Southern California Gas". Kills cluster 7's __14 (mutant returns None).
        """
        result = matcher.match("Southern Californ")

        assert result is not None
        assert result.provider == "SoCalGas"
        assert result.category == "UTILITY"
        assert result.confidence == 0.85


class TestServiceProviderMatcherTieBreak:
    """Determinism contract of the public providers= injection API."""

    def test_fuzzy_match_first_alias_wins_on_tie(self) -> None:
        """Equal best scores keep the first-encountered alias (strict >).

        Kills cluster 7's __15 (`>` → `>=`): the mutant's second tied alias
        (0.95 >= 0.95) replaces the first and the provider becomes
        "Zeta Services".
        """
        providers: list[ProviderEntry] = [
            {
                "name": "Alpha Services",
                "aliases": ["ABCDEFGHIJKLMNOPQRSZ"],
                "category": "DELIVERY",
            },
            {
                "name": "Zeta Services",
                "aliases": ["ZABCDEFGHIJKLMNOPQRS"],
                "category": "UTILITY",
            },
        ]
        matcher = ServiceProviderMatcher(providers=providers)

        result = matcher.match("ABCDEFGHIJKLMNOPQRST")  # 0.95 vs both aliases

        assert result is not None
        assert result.provider == "Alpha Services"
        assert result.category == "DELIVERY"
        assert result.confidence == 0.95
```

### Kill map for drafted tests

| Draft test | Kills clusters | Mutant keys |
|------------|----------------|-------------|
| `test_exact_match_emergency_has_authority_modifier` | 4 | match__8,9,11,13,17,18 |
| `test_exact_match_populates_normalized_matched_alias` | 6 | __init__9, __init__10, match__25, match__30 |
| `test_fuzzy_match_emergency_full_result_fields` | 8, 10, part of 7 | _fuzzy_match__24,25,26,27,29,31,33,34,38,40,41,46,51,16 |
| `test_fuzzy_match_boundary_score_included` | 7 | _fuzzy_match__14 |
| `test_fuzzy_match_first_alias_wins_on_tie` | 7 | _fuzzy_match__15 |

Projected: 26/39 survivors killed; remaining 13 are the EQUIVALENT clusters (1,2,3,5,9) — no
assertion exists that separates them without asserting off-contract internals (crash-vs-fallback on a
self-inconsistent custom categories dict) — leave as permanent survivors or trawl with a future
`providers=`/`categories=` inconsistency test if the team ever wants those branches pinned.
