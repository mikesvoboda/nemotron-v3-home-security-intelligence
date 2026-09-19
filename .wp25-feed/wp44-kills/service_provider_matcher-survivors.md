# WP4.4 kill record — backend/services/service_provider_matcher.py

**Baseline:** 126 mutants, 87 killed by the pre-existing unit suite, 39 survivors.
**Batch:** `TestWp44MatcherRiskAndFields` (4 tests) + `TestWp44MatcherTieBreak` (1
test) appended to `backend/tests/unit/services/test_service_provider_matcher.py`
(import block extended with `ProviderEntry`).
**Strict census (drafted tests only, 39/39 keys, 0 no-verdicts): 26 killed / 39 probed.**
Module total after batch: **113/126 = 89.7% killed**.

## Killed (26 — exactly the dossier's TEST-GAP clusters 4, 6, 7, 8, 10)

| Dossier cluster | Keys | Killing test |
|---|---|---|
| 4 — exact path risk_modifier lookup degenerated (entry=None, .get(None), and False, wrong keys) | `match 8,9,11,13,17,18` | test_exact_match_emergency_has_authority_modifier (exact "Police" → EMERGENCY + risk_modifier "authority") |
| 6 — matched_alias identity/normalization unasserted | `match 25,30`, `__init__ 9,10` | test_exact_match_populates_normalized_matched_alias ("  fedex ground  " → matched_alias == "FEDEX GROUND") |
| 7 — scoring predicate: `>=`→`>` threshold (`14`), `>`→`>=` tiebreak (`15`), best_score=None (`16`) | `_fuzzy_match 14,15,16` | boundary: test_fuzzy_match_boundary_score_included ("Southern Californ" scores exactly 0.85 → SoCalGas/UTILITY); tie: test_fuzzy_match_first_alias_wins_on_tie (injected providers, Alpha Services first); 16 via full-field fuzzy assert |
| 8 — fuzzy risk_modifier lookup degenerated | `_fuzzy_match 24,25,26,27,29,31,33,34` | test_fuzzy_match_emergency_full_result_fields ("Police Departm" → Police/EMERGENCY/0.9032/"authority"/matched_alias=="Police Department") |
| 10 — ServiceMatch construction field loss (`category=None`, `risk_modifier=None`, `matched_alias=None`/dropped, `round(…,4)`→`round(…,5)`) | `_fuzzy_match 38,40,41,46,51` | same exact-fields assert (pins 0.9032 at 4dp, category, modifier, alias) |

## Remaining survivors (13 — all EQUIVALENT per dossier, census confirmed)

Clusters 1–3, 5, 9: `x_levenshtein_ratio__1` (one-empty guard lands on
fuzz.ratio=0.0 anyway), `__init__ 16` (debug log text), `match 1` (whitespace
guard → fuzzy matches nothing), `match 12,14,16,19,20` + `_fuzzy_match
28,30,32,35,36` (dead `.get` defaults / `or True` ternaries — the fallback value
is identical to the default on every reachable input). House precedent:
alert_service C2, audit_logger C5–C8. Zero drafted behavior tests touch them, as
predicted.

**Module closed: 113 killed + 13 classified = 126 = mutants_total.**
