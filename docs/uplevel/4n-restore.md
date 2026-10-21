# 4n — Restore from Backup Design

> Step 1 of the Restore feature package (`packages/backend.md`, "B4.\* Feature track"), copied
> from [`templates/feature-design.md`](templates/feature-design.md).

**Package:** `B4.6` (backend leads; a small frontend part in the same PR, UR-9) · **Inventory
row:** F-101 · **R2 ruling:** complete, priority 1 (R2a row 16) · **Designed:** 2026-10-21, with the
owner

## Where it starts

Facts read at `main` `c75111487`.

- **The chain:** `start_restore` (`backend/api/routes/backup.py:632`) records a restore job, and
  `run_restore_job` (`:263`) calls `RestoreService.restore_from_backup`
  (`backend/services/restore_service.py`) inside one transaction.
- **The two table lists have drifted.** Backup writes `activity_baselines` and `class_baselines`
  (`backend/services/backup_service.py:142-151`); restore's own list names `baselines`
  (`restore_service.py:48-57`) and skips any table not on it (`:203`). Both baseline tables are
  dropped from every restore while the job reports success.
- **Restore is not all-or-nothing for records.** A record that fails to insert is logged and
  skipped (`restore_service.py:419`), and a table with no model mapping is skipped (`:394`).
- **Restore wipes event history.** Each table is emptied with `DELETE` before refilling (`:399`),
  starting with `cameras`. Events, detections, plate reads, face events, tracks and heatmaps all
  reference cameras `ON DELETE CASCADE` (for example `backend/models/event.py:56`,
  `backend/models/detection.py:41`), and backups do not contain events, so a restore deletes the
  whole event history and nothing brings it back.
- **Backups hold alerts but not alert rules.** `alerts` rows point at events the backup lacks;
  `alert_rules`, which are configuration, are not backed up.

## What the user can do when this is done

The user opens Restore under Data and picks a backup. The system first saves a "before restore"
backup of the current state, then applies the chosen one, reporting each table it restored with
its row count and anything it kept that the backup did not contain, with a link to the safety
backup in case they want to undo. Their event history is untouched.

## Decisions

| question                             | decision                                                                                                                                                                                                                                                                                  | why                                                                                      |
| ------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| Is there a safety net?               | Restore takes an automatic backup first, named "before restore of <backup> at <time>". If that backup fails, the restore does not start.                                                                                                                                                  | A restore overwrites configuration; the user can undo it by restoring the safety backup. |
| How is a backup applied?             | Merge by id. Configuration rows (cameras, zones, prompts, household members, settings, alert rules) are upserted by primary key; rows not in the backup are kept and reported. The two baseline tables belong to the backup and are replaced. Nothing is deleted through a cascade.       | Wiping `cameras` cascades away every event.                                              |
| What if anything fails?              | All or nothing. An unrecognised table, a file the manifest lists but the archive lacks, or a rejected record rolls everything back, and the job names the table, the record and the error.                                                                                                | A restore that reports success while dropping data is worse than one that fails.         |
| How do the table lists stay aligned? | One shared list defines what backup writes and what restore reads, and a test asserts every backed-up table has a restore mapping.                                                                                                                                                        | Two lists drifted and lost both baseline tables.                                         |
| What does a backup contain?          | Configuration: cameras, zones, prompts, both baseline tables, household members, settings and alert rules; recipients and channels join when `4n-alerting.md` lands. `alerts` leave the backup. An older backup's `alerts` file is listed as skipped by design, not treated as a failure. | Alerts are event history whose events a backup does not hold.                            |

## Shape

- **The module behind the seam:** `RestoreService`, with the shared table list in one place both
  services import. Domain term, added to `docs/reference/glossary.md`: **safety backup**.
- **Its interface:** `restore_from_backup(path) -> RestoreResult` with, per table, rows upserted,
  rows replaced and rows kept; the safety backup's id; and, on failure, a `RestoreError` naming
  the table, the record index and the cause. Invariants: no row of `events` or any table that
  cascades from `cameras` changes; the transaction commits only if every table restores.
- **Its adapters:** the restore job (`run_restore_job`), which takes the safety backup through
  `BackupService` before calling it; the Restore modal.

## What changes

- **backend:** `restore_service.py` (shared list, upsert by id, replace for baselines, strict
  failure, the per-table result); `backup_service.py` (shared list; `alert_rules` in, `alerts`
  out); `run_restore_job` (safety backup first, its id in the job result); the restore job's
  result schema.
- **frontend:** `RestoreModal.tsx` shows the safety backup with a restore link, the per-table
  summary ("restored 4 cameras, kept 1 not in this backup") and the failure detail.

## Tests

- **Consolidation scope:** `restore_service.py`, `backup_service.py`, the backup and restore
  routes, and `RestoreModal` with their tests.
- **Tests through the interface:**
  - restoring into a database that holds events leaves every event and detection in place;
  - a camera in the backup overwrites the current one; a camera not in the backup is kept and
    reported; baselines are replaced;
  - a backup with an unknown table or a bad record changes nothing and fails with the detail;
  - the safety backup exists before any row changes, and its failure stops the restore;
  - every table the backup writes has a restore mapping;
  - an older backup containing `alerts` restores the rest and lists `alerts` as skipped.

## Golden path

- **Spec:** create a backup; rename a camera and change a baseline; restore; the name and the
  baseline come back, every event is still present, and a "before restore" backup is listed. A
  tampered backup fails and nothing changes. External-interface steps in
  `backend/tests/golden/external/`, extending `test_backup.py`; the modal step in Playwright.
- **Fake-stack scenario:** the seeded cameras, baselines and events.
- **Real-tier check:** the operator restores a backup on a test deployment and compares event
  counts before and after.

## Privacy and security

Backups already hold household members' names and settings; adding alert rules adds no personal
data. The safety backup is an ordinary backup, listed and deletable like the others. Under
`EXPOSE_LAN` the routes keep their existing authentication.

## Rollout and reversal

No schema change, and the backup format version stays `1.0`; older backups restore as described.
Code reversal is a revert. A restore itself is reversed by restoring its safety backup.

## Done when

The golden path is green on the fake stack, the real-tier check is posted, and F-101 reads
**works**.
