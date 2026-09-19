# WP4.4 kill record — backend/services/event_service.py

**Baseline:** 102 mutants, 60 killed by the pre-existing unit suite, 42 survivors.
**Batch:** `TestWp44EventServiceDeleteGaps` (8 tests) appended to
`backend/tests/unit/services/test_event_service.py` (own fixtures +
`_mock_event`/`_mock_result` helpers; `datetime UTC/timedelta` import).
**Strict census v1: 19/42. Residual audit found killable TEST-GAP keys the draft
missed (statement-blind execute on restore/hard paths; alerts.* projection);
added 3 tests + 2 asserts, green-proved, re-censused.**
**Strict census v2 (drafted tests only, 42/42 keys, 0 no-verdicts): 27 killed / 42 probed.**
Module total after batch: **87/102 = 85.3% killed**.

## Killed (27)

| Dossier cluster | Keys | Killing test |
|---|---|---|
| C1 soft fetch family (stmt/where/select/execute clobber, ==→!=) | `soft 2,3,5,7,9` | test_soft_delete_fetch_statement_targets_the_requested_event (literal_binds: `WHERE events.id = 123`, no `!=`, no `WHERE NULL`) |
| C1 restore fetch family | `restore 2,3,10,14,16` | test_restore_fetch_statement_targets_the_requested_event (same pin; _10 select(None) build-error re-killed) |
| C1 hard fetch family | `hard 1,2,4,6,8` | test_hard_delete_fetch_statement_eagerly_loads_and_filters (`_with_options==1` + FROM/WHERE pins) |
| C2 alert-count statement family | `soft 19,20,21,22,24` | test_soft_delete_alert_count_statement_filters_by_event_id (`WHERE alerts.event_id = 123`, `alerts.id` projection, no `NULL AS`) |
| C6+C7 restore loader options | `restore 7,8,9` | test_restore_event_fetch_eagerly_loads_detections_and_deferred_columns (`_with_options==3`, reasoning/llm_prompt in SELECT list) |
| C5 cascade keyword defaults | `soft 1`, `restore 1` | test_soft_delete_default_cascade_schedules_file_deletion / test_restore_default_cascade_cancels_pending_file_deletions |
| C8 `and`→`or` cascade flip | `restore 24` | test_restore_without_cascade_skips_file_deletion_cancel |
| C9 naive deleted_at | `soft 13` | test_soft_delete_stamps_utc_aware_deleted_at (`utcoffset() == timedelta(0)`) |

## Remaining survivors (15 — all classified, census confirmed)

- C3 EQUIVALENT (7): `soft 18,36,37`, `restore 34,35`, `hard 15,21` — logger
  message → None; `logger.info(None)` is legal, no behavior or return change.
- C4 LOW-VALUE (8): `soft 16,17,26,27`, `restore 27,28,32,33` — `> 0` boundary
  flips (`>= 0`, `> 1`) guarding exclusively log lines. House precedent:
  job_state C1–C4, alert_service C2.

**Module closed: 87 killed + 15 classified = 102 = mutants_total.**

**Census note:** v1 (19/42) archived at `/tmp/wp25/wp44-kills/pre-evs-fetch/`.
v1→v2 delta +8 = hard fetch family (5, no hard-path pin existed in v1) +
`restore 3,14` (where(None)/!= — survived v1's options-count test, which only
crashes on whole-stmt/option mutations) + `soft 21` (select(None) renders
`SELECT NULL AS anon_1` with the WHERE intact — dossier's "build error" call was
wrong; v1's startswith/WHERE asserts tolerated it, the alerts.* projection pin
kills it). All survivors were draft omissions, not unkillability.
