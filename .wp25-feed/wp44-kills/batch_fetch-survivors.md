# services/batch_fetch.py surviving-mutant record (STRICT census 2026-09-19, wave-66)

101 mutants; 44 killed pre-WP4.4 (score 64.4%). Wave-66 batch (6 tests in
`TestWp44BatchFetchStatementContracts`, test_batch_fetch.py): **19 newly killed**.
STRICT census: all 36 open keys re-probed with synced tests, kill = rc in (1,3),
-n 0, 0 no-verdicts.

Coverage map: single-query SQL contract (no-NULL columns, `detections.id IN (...)`
ids, ORDER BY ASC — C4/C5), batch-loop partition coverage via _IN_CLAUSE union
(C7), file-path loop equivalents (C8), file-path statement contracts (C10),
by_ids batch_size forwarding (C13, byids_8), projection `SELECT detections.file_path FROM detections`.

Module total: (65+19)/101 = **84 = 83.2%** (was 64.4% pre-WP4.4 — arbiter caught
= 44 run6-kills + 21 run6 timeouts; the 21 timeouts never re-enter the survivor set).
17 survivors remain (13 det_*, paths_27, byids_5/9/10) — ALL log/debug-text (C1, 8, EQUIVALENT), batch_count
bookkeeping that feeds only the debug f-string (C2, 4, EQUIVALENT), dedup-log
guard flip (C3, LOW-VALUE), `<=`→`<` fast-path boundary (C11, LOW-VALUE: batch
of exactly batch_size takes the loop path, results identical), order_by_time
delegate kwargs unobservable through the dict-return (C12, 3, EQUIVALENT).
Every TEST-GAP key died. Survivors ARE the record.

```
backend.services.batch_fetch.x_batch_fetch_detections__mutmut_12
backend.services.batch_fetch.x_batch_fetch_detections__mutmut_13
backend.services.batch_fetch.x_batch_fetch_detections__mutmut_14
backend.services.batch_fetch.x_batch_fetch_detections__mutmut_27
backend.services.batch_fetch.x_batch_fetch_detections__mutmut_3
backend.services.batch_fetch.x_batch_fetch_detections__mutmut_30
backend.services.batch_fetch.x_batch_fetch_detections__mutmut_4
backend.services.batch_fetch.x_batch_fetch_detections__mutmut_40
backend.services.batch_fetch.x_batch_fetch_detections__mutmut_41
backend.services.batch_fetch.x_batch_fetch_detections__mutmut_42
backend.services.batch_fetch.x_batch_fetch_detections__mutmut_5
backend.services.batch_fetch.x_batch_fetch_detections__mutmut_54
backend.services.batch_fetch.x_batch_fetch_detections__mutmut_6
backend.services.batch_fetch.x_batch_fetch_detections_by_ids__mutmut_10
backend.services.batch_fetch.x_batch_fetch_detections_by_ids__mutmut_5
backend.services.batch_fetch.x_batch_fetch_detections_by_ids__mutmut_9
backend.services.batch_fetch.x_batch_fetch_file_paths__mutmut_27
```
