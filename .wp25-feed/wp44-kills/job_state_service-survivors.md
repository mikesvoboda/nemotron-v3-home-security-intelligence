# WP4.4 kill record — backend/services/job_state_service.py

**Baseline:** 147 mutants, 105 killed by the pre-existing unit suite, 42 survivors.
**Batch:** `TestWp44JobStateGaps` (6 tests) appended to
`backend/tests/unit/services/test_job_state_service.py`.
**Strict census (drafted tests only, 42/42 keys, 0 no-verdicts): 16 killed / 42 probed.**
Module total after batch: **121/147 = 82.3% killed**.

## Killed (16 — exactly the dossier's TEST-GAP set)

| Cluster | Keys | Killing test |
|---|---|---|
| C5 to_dict key renames | `to_dict__17,18,19,20` | test_to_dict_full_serialization_contract |
| C6 to_dict timestamp guards | `to_dict__12,15` | same (started_at=None crash + completed_at present) |
| C7 naive timestamps | `create_job__15`, `transition__28` | test_created_and_transition_timestamps_are_utc_aware |
| C8 error-gate and→or | `transition__43` | test_error_message_recorded_only_for_failure_states |
| C9 aborted tuple clobber | `transition__47,48` | test_aborted_transition_records_error_message |
| C10 metadata "null" string | `_record_transition__13` | test_transition_without_metadata_records_null |
| C11/C12 module helpers unknown status | `get_valid_target_states__2,4`, `validate_transition__3,5` | test_module_level_helpers_unknown_status |

## Remaining survivors (26 — all deliberate non-gaps)

All 26 are the transition() logging clusters the dossier classified LOW-VALUE/EQUIVALENT:
C1 success `logger.info` extra-payload (10), C2 invalid-transition `logger.warning`
extra-payload (8), C3+C4 message-text variants (8). The census confirmed zero of the
drafted behavior tests touch them (expected, by design — house precedent: alert_service
C2, audit_logger C5-C8). The rejection signal itself is carried by
`InvalidStateTransition` and asserted in TestExceptionDetails; the success transition is
asserted by return value.

**Module closed: 121 killed + 26 classified = 147 = mutants_total.**
