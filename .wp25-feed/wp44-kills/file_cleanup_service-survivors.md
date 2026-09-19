# services/file_cleanup_service.py surviving-mutant record (STRICT census 2026-09-19, wave-66 v2)

125 mutants; 92 killed pre-WP4.4 (score 73.6%). Wave-66 batch (6 tests in
`TestWp44FileCleanupGaps`, test_file_cleanup_service.py): **24 newly killed**
(v1 census), residual audit found `delete_files_batch__mutmut_16`
(`total_failed += -> =`) still alive: the drafted batch test gave event1
failed=0 / event2 failed=1, and last-wins `=` takes event2's value — the
nonzero contributor WAS the last event. v2 fix: event1 (3 files) owns ALL
nonzero counts (deleted+missing+failed), event2 contributes only a second
deleted; a first-event nonzero breaks every `=` mutant. v2 re-census (9
survivor keys re-probed, synced test, 0 no-verdicts): **25/33 total killed**.

Coverage map: path-string CONTENTS of result.deleted/missing (C3, 8), exact
byte sums (C4, 3), batch aggregates across two nonzero-bearing events (C5, 6,
incl. the flipped-16 fix), get_event_files statement contract — SELECT events.
columns, no NULL, `events.id = 123`, `!=`-free, one eager-load option (C6, 5),
event_id identity + `or 0` fallback (C2), empty-path skip with real path AFTER
empties (C8).

Module total: (92+25)/125 = **117 = 93.6%** (was 73.6% pre-WP4.4).
8 survivors remain — dossier-predicted exactly: C1 log message/format-arg
clobbers to `None` (7, EQUIVALENT: logger args only, result objects unchanged)
+ C7 summary-log `or`->`and` (1, LOW-VALUE: log presence only).
Every TEST-GAP key is dead. They ARE the surviving-mutant record.

```
backend.services.file_cleanup_service.xǁFileCleanupServiceǁ_delete_single_file__mutmut_5
backend.services.file_cleanup_service.xǁFileCleanupServiceǁ_delete_single_file__mutmut_8
backend.services.file_cleanup_service.xǁFileCleanupServiceǁdelete_event_files__mutmut_18
backend.services.file_cleanup_service.xǁFileCleanupServiceǁdelete_event_files__mutmut_19
backend.services.file_cleanup_service.xǁFileCleanupServiceǁdelete_event_files__mutmut_9
backend.services.file_cleanup_service.xǁFileCleanupServiceǁdelete_files_batch__mutmut_20
backend.services.file_cleanup_service.xǁFileCleanupServiceǁdelete_files_batch__mutmut_5
backend.services.file_cleanup_service.xǁFileCleanupServiceǁget_event_files__mutmut_12
```
