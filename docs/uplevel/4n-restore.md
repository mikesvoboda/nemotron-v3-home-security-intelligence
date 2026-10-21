# 4n — Restore from Backup Design

> Step 1 of the Restore feature package (`packages/backend.md`, "B4.\* Feature track"), copied
> from [`templates/feature-design.md`](templates/feature-design.md).

**Package:** `B4.6` (backend leads; a small frontend part in the same PR, UR-9) · **Inventory
row:** F-101 · **R2 ruling:** complete, priority 1 (R2a row 16) · **Designed:** 2026-10-21, with the
owner

## Where it starts

Facts read at `main` `bc89bf68a`.

- **The chain is not one transaction.** `start_restore` (`backend/api/routes/backup.py:632`)
  records a restore job, and `run_restore_job` (`:263`) calls `RestoreService.restore_from_backup`
  (`backend/services/restore_service.py`). Its progress callback commits the same session the
  restore writes on (`backup.py:296-309`), and the service calls it before each table
  (`restore_service.py:216-218`). Every finished table is committed before the next starts, so the
  rollback on failure (`:235`) undoes only the table that failed.
- **The two table lists have drifted.** Backup writes `activity_baselines` and `class_baselines`
  (`backend/services/backup_service.py:142-151`); restore loops only over its own list
  (`restore_service.py:202-204`), which names `baselines` (`:48-57`). Both baseline tables are
  dropped from every restore while the job reports success.
- **Restore is not all-or-nothing for records.** A record the model rejects is logged and skipped
  (`restore_service.py:414-419`); a table whose model fails to import is skipped (`:393-395`).
  Records are rebuilt as `model_class(**data)` (`:410`), so a key the model lacks is a rejection,
  and the archive's version must match exactly (`:284-289`).
- **Restore rewinds event history.** Each table is emptied with `DELETE` before refilling (`:399`),
  starting with `cameras`. Events, detections, plate reads, face events, tracks and heatmaps all
  reference cameras `ON DELETE CASCADE` (for example `backend/models/event.py:56`,
  `backend/models/detection.py:41`). Every archive also holds `events`, added outside the list
  (`backup_service.py:163-175`), so a restore brings back the events of backup time without their
  detections and loses everything newer.
- **Backups do not survive a restart.** They are written to `/tmp/backups`
  (`backup_service.py:51`), a tmpfs in the production backend container
  (`docker-compose.prod.yml:393-394`). Restore takes only an uploaded file (`backup.py:632`), so
  the usual recovery is download, reinstall, upload: an archive from another installation is the
  normal case.
- **Ids are local to an installation.** `household_members.id` is a serial number
  (`backend/models/household.py:90`) that face embeddings, registered vehicles and zone settings
  reference; nothing advances a sequence after an insert with explicit ids, and the manifest names
  no installation (`backup_service.py:72-83`).
- **Backed-up rows point at parents that are not backed up.** `cameras.property_id` references
  `properties` (`backend/models/camera.py:118-120`), which references `households`
  (`backend/models/property.py:68`); household members reference `households` and
  `known_persons` (`household.py:91-115`). Areas are user configuration too.
- **The wrong prompt store is backed up.** The archive holds `prompt_configs`, which nothing but
  restore writes; the prompts the app uses are `prompt_versions`
  (`backend/services/prompt_service.py:759`).
- **Backups hold alerts but not alert rules.** `alerts` are event history; `alert_rules`, which are
  configuration, are left out.

## What the user can do when this is done

The user opens Restore under Data and picks a backup, from this installation or another. The system
first saves a "before restore" backup of the current state, then applies the chosen one, reporting
each table it restored with its row count, the rows it added and anything it kept that the backup
did not contain, with a link to the safety backup. Their event history is untouched.

## Decisions

| question                                   | decision                                                                                                                                                                                                                                                                                                                                                                                 | why                                                                                                      |
| ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Is there a safety net?                     | Restore takes an automatic backup first, named "before restore of <backup> at <time>", committed as its own job before any row changes. If it fails, the restore does not start. Restoring it reverts changed rows and the baselines; rows the restore added stay, and the restore result lists them by name.                                                                            | A restore overwrites configuration. Under merge, a full undo is not possible, so the doc promises less.  |
| Where do backups live?                     | Under `/app/data/backups`, on the data volume.                                                                                                                                                                                                                                                                                                                                           | A safety backup on a tmpfs is gone after a restart.                                                      |
| How is a backup applied?                   | Merge, each table by its own key (Shape). Rows not in the backup are kept and reported. Baselines are replaced for the cameras the archive contains. Nothing is deleted through a cascade.                                                                                                                                                                                               | Wiping `cameras` cascades away every event.                                                              |
| What if the archive is from elsewhere?     | The manifest carries an `installation_id`, kept in settings and never overwritten by a restore. From the same installation, rows merge by id. From another installation or an unmarked (older) archive, household members are inserted with new ids and never overwrite a local member; households, properties and areas are matched by name and remapped.                               | A member's id from another installation names a different person; overwriting it moves their embeddings. |
| What about a member's known person?        | Known persons and every embedding stay out of backups. A member's link is kept when the archive is from this installation and the person exists; otherwise it is cleared and reported.                                                                                                                                                                                                   | Face embeddings are biometric; re-enrolment rebuilds them.                                               |
| What if anything fails?                    | All or nothing: the restore runs in one transaction with one commit. An unrecognised table, a file the manifest lists but the archive lacks, or a rejected record rolls everything back, and the job names the table, the record and the error.                                                                                                                                          | A restore that reports success while dropping data is worse than one that fails.                         |
| How do the table lists stay aligned?       | One shared list defines what backup writes and what restore reads, and a test asserts every backed-up table has a restore mapping.                                                                                                                                                                                                                                                       | Two lists drifted and lost both baseline tables.                                                         |
| What does a backup contain?                | Configuration: households, properties, areas, cameras and their areas, zones, both baseline tables, household members, prompt versions, settings and alert rules. Recipients and channels join without their secrets, with whichever of `B4.2` and `B4.6` lands second; camera notification settings are covered once `B4.5` moves them into rules. Not events, alerts or known persons. | Events and alerts are history; their detections and footage are never in an archive.                     |
| What happens to an older archive's events? | Skipped by design. The format moves to `1.1`, with an adapter per older version; the `1.0` adapter lists `events` and `alerts` as skipped and restores the rest.                                                                                                                                                                                                                         | Restored events would come back without detections or footage, and their ids clash across installs.      |

## Shape

- **The module behind the seam:** `RestoreService`, with the shared table list in one place both
  services import. Domain terms, added to `docs/reference/glossary.md`: **safety backup**,
  **installation id**.
- **Its interface:** `restore_from_backup(path, db) -> RestoreResult` with, per table, rows
  updated, inserted, replaced and kept, the added rows by name, the cleared known-person links,
  and the safety backup's id; on failure, a `RestoreError` naming the table, the record index and
  the cause. `RestoreService` never commits.
- **Keys, in restore order:** households, properties and areas (by id from this installation, by
  name from another); cameras (by id, the folder name; a clash on the unique name or folder path is
  a named failure); camera areas; zones (UUID); baselines (by their unique slot, inserted without
  ids, `backend/models/baseline.py:71`, `:124`); household members (by id from this installation,
  inserted new from another); prompt versions (by model and version; the archive's active version
  becomes active); settings (by key); alert rules (UUID). After any insert with explicit ids the
  table's sequence is advanced with `setval`.
- **Versions:** each archive version has an import adapter. A key missing from a record keeps the
  local value on update and the default on insert; a key the model lacks is an error unless that
  version's adapter handles it. If this package lands before `B4.5`, `B4.5` ships the adapter for
  `alert_rules` records from before its contract.
- **Invariants:** no row of `events`, or of any table that references events or detections,
  changes. Of the tables that reference cameras, only `camera_areas` and `camera_zones`
  (upserted) and the two baseline tables (replaced for the archive's cameras) change. The
  transaction commits only if every table restores.
- **Its adapters:** the restore job (`run_restore_job`), which opens its own sessions: session A
  takes the safety backup through `BackupService` and commits its job; session B runs the restore
  in one transaction with one commit; session C writes progress. The Restore modal.

## What changes

- **backend:** `restore_service.py` (shared list, per-table keys, adapters, remapping, `setval`,
  strict failure, no commits, the per-table result); `backup_service.py` (shared list; the new
  tables in, `events`, `alerts` and `prompt_configs` out; `installation_id` and version `1.1` in
  the manifest; the directory under `/app/data`); `run_restore_job` (three sessions, safety backup
  first, its id in the job result); the restore job's result schema, its new fields kept in the
  job's existing JSON columns.
- **frontend:** `RestoreModal.tsx` shows the safety backup with a restore link, the per-table
  summary ("restored 4 cameras, added 1, kept 1 not in this backup"), the added rows and cleared
  links by name, and the failure detail.

## Tests

- **Consolidation scope:** `restore_service.py`, `backup_service.py`, the backup and restore
  routes, and `RestoreModal` with their tests.
- **Tests through the interface:**
  - restoring into a database that holds events leaves every event and detection in place;
  - restoring into an empty database succeeds, parents first;
  - a camera in the backup overwrites the current one; a camera not in the backup is kept and
    reported; baselines are replaced for the archive's cameras only;
  - a failure in the last table changes nothing, run through the real restore job;
  - a backup with an unknown table or a bad record changes nothing and fails with the detail;
  - the safety backup exists before any row changes, survives a restart, and its failure stops
    the restore;
  - an archive from another installation inserts its members with new ids and never overwrites a
    local one; a member's known-person link from it is cleared and reported;
  - after a restore, inserting a new member or baseline does not fail on a duplicate key;
  - every table the backup writes has a restore mapping;
  - a `1.0` archive from `origin/main`, with `events` and `alerts`, restores the rest and lists
    both as skipped.

## Golden path

- **Spec:** create a backup; rename a camera and change a baseline; restore; the name and the
  baseline come back, every event is still present, and a "before restore" backup is listed. A
  tampered backup fails and nothing changes. External-interface steps in
  `backend/tests/golden/external/`, extending `test_backup.py`; the modal step in Playwright.
- **Fake-stack scenario:** the seeded cameras, baselines, members and events.
- **Real-tier check:** the operator restores a backup on a test deployment and compares event
  counts before and after.

## Privacy and security

Backups already hold household members' names and settings, and camera RTSP passwords in plain text
(`camera.py:130`); this design adds no personal data and keeps known persons and every embedding
out. Recipient channels arrive without their secrets, with whichever of `B4.2` and `B4.6` lands
second. The safety backup is an ordinary
backup, listed and deletable like the others. Under `EXPOSE_LAN` the routes keep their existing
authentication.

## Rollout and reversal

No schema change: the installation id is a setting and the job's new fields live in its existing
JSON columns. The backup format moves to `1.1`; `1.0` archives restore through their adapter.
Code reversal is a revert. A restore itself is reversed, as far as merge allows, by restoring its
safety backup.

## Review

An adversarial review (2026-10-21) and a fresh-context check of it found five issues and corrected
six claims in "Where it starts". The owner ruled on four:

| #   | finding                                                           | amendment                                                                                                    |
| --- | ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| R4  | Progress commits defeat the all-or-nothing transaction            | Three sessions: safety backup, one-commit restore, progress                                                  |
| R5  | Merging by id can overwrite another installation's rows           | Per-table keys; `installation_id`; foreign members inserted new (owner); `setval`                            |
| R6  | Backed-up rows point at parents that are not backed up            | Households, properties and areas backed up and restored first; known persons left out, links cleared (owner) |
| R7  | Every archive holds events; strict rebuild breaks on old archives | Events skipped by design (owner); format `1.1` with adapters; `B4.5` ships the `alert_rules` adapter         |
| R10 | Restoring the safety backup cannot undo a merge                   | The promise narrowed; added rows listed by name (owner); backups moved to the data volume                    |

## Done when

The golden path is green on the fake stack, the real-tier check is posted, and F-101 reads
**works**.
