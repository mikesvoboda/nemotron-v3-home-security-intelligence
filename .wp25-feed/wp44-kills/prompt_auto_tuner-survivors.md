# WP4.4 kill record — backend/services/prompt_auto_tuner.py

**Baseline:** 117 mutants, 79 killed by the pre-existing unit suite, 38 survivors.
**Batch:** `TestWp44PromptTunerGaps` (6 tests) appended to
`backend/tests/unit/services/test_prompt_auto_tuner.py` (module-level import of
`PromptAutoTuner` added).
**Strict census (drafted tests only, 38/38 keys, 0 no-verdicts): 16 killed / 38 probed.**
Module total after batch: **95/117 = 81.2% killed**.

## Killed (16 — exactly the dossier's TEST-GAP clusters C1,C2,C3,C5,C6,C7,C9)

| Dossier cluster | Keys | Killing test |
|---|---|---|
| C5 — `session=` kwarg → None / removed at the audit call | `get_tuning_context 3,5` | test_forwards_session_to_audit_service (`call_kwargs.get("session") is mock_db_session`) |
| C1 — `min_level` fallback `2` → None/removed/3 | `_filter_by_priority 3,5,7` | test_invalid_min_priority_defaults_to_medium (min_priority="urgent" → medium tier: ["H","M"]) |
| C2 — item-unknown-priority fallback `1` → None/removed/2 | `_filter_by_priority 9,11,21` | test_unknown_item_priority_treated_as_low (priority "urgent" kept at low, dropped at medium) |
| C3 — missing `priority` key default → None/removed | `_filter_by_priority 14,16` | test_missing_priority_key_treated_as_low |
| C6 — section-header strings XX-wrapped (substring `in` tolerates) | `get_tuning_context 41,45,59` | test_exact_rendered_block (`== "\n".join([...])`) |
| C9 — `"\n".join` → `"XX\nXX".join` | `get_tuning_context 73` | same exact-block assert |
| C7 — top-N slices `[:3]→[:4]`, `[:2]→[:3]` | `get_tuning_context 48,62` | test_slice_limits_with_eligible_items_only (4×high missing_context → "MC3" absent; 3×high format → "FS2" absent) |

## Remaining survivors (22 — all classified, census confirmed)

- C4 EQUIVALENT (2): `_filter_by_priority 19,20` — `"XXlowXX"`/`"LOW"` both land on
  the same `.lower()` lookup outcome as `"low"`.
- C8 EQUIVALENT (6): `get_tuning_context 51,53,56,65,67,70` — dead
  `r.get("suggestion", …)` defaults; the comprehension upstream already requires a
  truthy `suggestion`, so the default is unreachable.
- C11 EQUIVALENT (4): `get_tuning_context 74,80,81,82` — failure-path warning
  message text (`None`/XX/lower/upper); `logger.warning(None)` is legal.
- C10/C12/C13 LOW-VALUE (10): `get_tuning_context 75,76,78,79,83,84,85,86,87,88`
  — `exc_info` kwarg variants, `extra={…}` removal, and the extra-dict key/value
  casing (`camera_id`→`XXcamera_idXX`, `error`→`XXerrorXX`, `str(e)`→`str(None)`);
  structured-log drift with no asserting consumer (house precedent: job_state
  C1–C4 log clusters).

**Module closed: 95 killed + 22 classified = 117 = mutants_total.**
