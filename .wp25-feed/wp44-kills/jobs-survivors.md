# api/routes/jobs.py surviving-mutant record (STRICT census 2026-09-19, wave-67)

25 mutants; 0 killed pre-WP4.4 (score 0.0% — run_export_job had no direct
test coverage at all; every mutant survived because nothing called it).
Wave-67 batch (4 tests in TestRunExportJobTask in test_jobs.py):
**25 newly killed**. STRICT census: all 25 open keys re-probed with synced
tests, kill = rc in (1,3), -n 0, 0 no-verdicts.

Coverage map: run_export_job driven end-to-end against a REAL JobTracker
(hermetic — _schedule_persist early-returns with redis_client=None, _broadcast
no-ops with no callback; JobTracker.start/complete raise KeyError on unknown
ids, so mis-addressed job ids fail the test): filter pass-through to
get_filtered_detections (camera_id/since/until), job identity + COMPLETED
result, the RUNNING progress snapshot [(JobStatus.RUNNING, "Starting csv
export...")], and completion end-state (COMPLETED, error None, result dict,
started_at/completed_at set). The broad except in run_export_job swallows
errors into fail_job, so end-state assertions are the kill vectors.

Module total: (0+25)/25 = **25 = 100.0%** (was 0.0% pre-WP4.4).
0 survivors. The surviving-mutant record is the empty set.

Harness observation for WP4.4 queue: the fail_job call line itself generated
ZERO mutants (mutmut emitted none for that statement) — the J-cluster spread
is entirely inside the success path; noted for the next survivor sweep.
