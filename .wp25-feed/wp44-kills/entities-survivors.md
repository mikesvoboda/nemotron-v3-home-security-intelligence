# WP4.4 kill record — backend/api/routes/entities.py

**Baseline:** 130 mutants, 91 killed by the pre-existing unit suite, 39 survivors.
**Batch:** `TestWp44EntitySummaryGaps` (4 tests) appended to
`backend/tests/unit/api/routes/test_entities.py` (module-level import block extended
with `_entity_model_to_summary`, `_entity_to_trust_response`,
`_extract_cameras_seen_from_entity`).
**Strict census (drafted tests only, 39/39 keys, 0 no-verdicts): 29 killed / 39 probed.**
Module total after batch: **120/130 = 92.3% killed**.

## Killed (29 — the 28 dossier TEST-GAP keys + 1 incidental)

| Cluster | Keys | Killing test |
|---|---|---|
| C1+C4 trust-field loss | `_entity_model_to_summary 5,6,7,8,9,10,11,12,24,33` + `25` | test_summary_carries_trust_fields |
| C2 cameras_seen extraction | `_extract_cameras_seen_from_entity 1,2,3,4,5` | test_prefers_cameras_seen_list_and_ignores_non_list |
| C3 thumbnail suppression | `_entity_model_to_summary 13,14,16,23,32` | test_summary_thumbnail_url_and_id |
| C6 id=str(None) | `_entity_model_to_summary 35` | same |
| incidental | `_entity_model_to_summary 34` | same (thumbnail kwarg path) |
| C9 temporal fields | `_entity_to_trust_response 37,38,39,46,47,48` | test_entity_trust_response_carries_temporal_fields |

## Remaining survivors (10 — all classified unkillable-per-dossier)

C5 `trust_status` init `""`-vs-None (1, LOW-VALUE display-only), C7 XX-prefixed
ValueError message (1, EQUIVALENT — `match=` is a prefix search), C8
trust_status_str garbage funneling (7, EQUIVALENT — the
try/TrustStatus/except-UNCLASSIFIED guard makes every variant identical), C10
thumbnail init `""` on falsy detection id (1, LOW-VALUE).

**Module closed: 120 killed + 10 classified = 130 = mutants_total.**
Side observation carried: the `except ValueError, TypeError:` PEP-758 legacy syntax at
entities.py:286/553/806/1085 needs a separate cleanup ticket (3.13 would reject it).
