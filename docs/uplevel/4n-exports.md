# 4n — Exports Design

> Step 1 of the Exports feature packages (`packages/backend.md`, "B4.\* Feature track"), copied
> from [`templates/feature-design.md`](templates/feature-design.md).

**Packages:** `B4.10`, `F4.7` · **Inventory rows:** F-051, F-098, F-099 (and F-298's detections
export) · **R2 ruling:** complete, priority 2 ("serve the file; drop or implement the two types;
honour cancel", R2a row 13) · **Designed:** 2026-10-22, with the owner · **Builds on:**
[`4n-alerting.md`](4n-alerting.md) (the alert rows the Alerts type reads),
[`4n-trash.md`](4n-trash.md) and [`4n-restore.md`](4n-restore.md)

## Where it starts

Facts read at `main` `aec5580aa`.

- **Two job systems export events.** The timeline's Export button
  (`frontend/src/components/ExportButton.tsx`) calls `POST /api/events/export`
  (`backend/api/routes/jobs.py:751-808`), which starts an in-memory tracker job with no
  `export_jobs` row (`:779`), polled through `GET /api/jobs/{job_id}`. The export modal
  (`ExportModal.tsx`, `ExportProgress.tsx`) and Data › Export (`DataManagementPage.tsx`) use the
  database-backed jobs in `backend/api/routes/exports.py`: `POST /api/exports` (`:231`), list,
  status, `DELETE` (`:428`) and `GET /api/exports/{job_id}/download` (`:487`). Both run
  `ExportService.export_events_with_progress` (`backend/services/export_service.py:722`).
- **The button's download is a 404 (F-051).** It opens `/api/exports/<filename>`
  (`ExportButton.tsx:123`, `:163`), which `GET /api/exports/{job_id}` reads as a job id and refuses
  (`exports.py:107-114`); the tracker job has no row, so `/download` would refuse it too. Its
  Excel choice is a 422, because the tracker route accepts only csv, json and zip
  (`backend/api/schemas/jobs.py:249-254`).
- **Alerts and Full Backup export events (F-098).** Both pages offer the two types
  (`DataManagementPage.tsx:186-187`, `ExportModal.tsx:236-246`); the route stores the type
  (`exports.py:272`) and never passes it to the task (`:288-301`).
- **Cancel only relabels (F-099).** `cancel_export` sets the row to `FAILED` (`exports.py:453`); the
  worker never checks for cancellation (`backend/services/job_tracker.py:538`), so a finished job
  overwrites the row with `COMPLETED` (`exports.py:180-181`). The button's and the modal's Cancel
  clear local state only (`ExportButton.tsx:223`, `ExportModal.tsx:178`); `ExportStatus` has no
  cancelled value (`backend/models/export_job.py:51-57`).
- **Files live in RAM and never expire.** `EXPORT_DIR` is `/tmp/exports`
  (`export_service.py:54`), a tmpfs in production (`docker-compose.prod.yml:393-394`): a restart
  loses the files while their jobs read `COMPLETED`, and download then answers "not found on disk"
  (`exports.py:519-523`). `expires_at` defaults to seven days (`export_job.py:142-146`) and nothing
  reads it.
- **The ZIP holds only the JSON** (`export_service.py:856-864`).
- **An unused synchronous export leaks Trash.** `GET /api/events/export`
  (`backend/api/routes/events.py:1295`) has no caller in the app and no `deleted_at` filter
  (`:1386-1398`), so it exports trashed events; the job path filters them
  (`export_service.py:766`). F-298's `GET /api/detections/export` selects detections without
  checking their event (`backend/api/routes/detections.py:697`) and includes a `file_path` column.
- **Backups are configuration only.** F-100's backups hold configuration tables
  (`backend/services/backup_service.py:53-66`), and the restore design says a backup holds "Not
  events, alerts, known persons" and footage is never in an archive (`4n-restore.md:71`).
- **No golden path covers F-051, F-098 or F-099.** `frontend/tests/e2e/specs/event-export.spec.ts`
  mocks a route that does not exist (`:60`), and its cancel test asserts nothing (`:536`).

## What the user can do when this is done

From the timeline, the household exports the events it is looking at, with every filter it has
set, as CSV, JSON, Excel, or a ZIP with each event's picture, and downloads the file. From Data ›
Export it can also export its alert history. It can cancel an export in progress, and the job says
it was cancelled. An export stays downloadable for a day, across restarts, and then expires.

## Decisions

| question                          | decision                                                                                                                                                                                                                                                                   | why                                                                                                      |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Which export types survive?       | Events, and Alerts as alert history from the alert rows `B4.1` writes. "Full Backup" leaves the export menu, and a link to Data › Backups takes its place (owner, EX-1).                                                                                                   | Alert history has rows to export now; a full backup would duplicate F-100 or contradict `4n-restore.md`. |
| How many export paths?            | One: the database-backed job, `POST /api/exports` and its `/download`, for the button, the modal and Data › Export. `POST /api/events/export`, its tracker job and the unused `GET /api/events/export` retire; F-298 stays the integrator's synchronous API (owner, EX-2). | One history, one cancel, one download, and the Trash leak goes with the unused route.                    |
| Where do files live, how long?    | On the data volume. An hourly cleanup deletes each file 24 hours after it finishes and marks its job expired (owner, EX-3).                                                                                                                                                | Files survive restarts, and a purged event lingers in an export for at most a day.                       |
| What goes in an export?           | CSV, JSON and Excel carry text. ZIP carries the JSON and each event's thumbnail, named by event id, up to 1,000 events (owner, EX-4).                                                                                                                                      | A picture export for an insurer or the police, bounded in size; clips stay out.                          |
| What does cancel do?              | The worker checks between batches, stops and deletes its partial file; the job reads `cancelled`, and a finishing job cannot overwrite it.                                                                                                                                 | Cancel means stopped, wherever it is pressed.                                                            |
| Which filters apply?              | Every filter the timeline shows: camera, time, risk, verdict, object type, reviewed and search.                                                                                                                                                                            | An export should hold what the household is looking at.                                                  |
| Who can export, and is it logged? | A session or API key with `EXPOSE_LAN=true`, as today. Starting an export and each download are audited, and starting exports is rate-limited.                                                                                                                             | Exports carry the household's events and pictures.                                                       |

## Approaches weighed

| approach                                | for                                                    | against                                                                    |
| --------------------------------------- | ------------------------------------------------------ | -------------------------------------------------------------------------- |
| **A. One database-backed job** (chosen) | One history, cancel and download; progress by polling. | The button changes path and its tests follow.                              |
| B. Keep both jobs, add a file route     | The button barely changes.                             | Two job systems, two histories, two cancels.                               |
| C. A streaming GET for the button       | No job at all.                                         | No progress, no cancel, and a large export ties up a request.              |
| Full Backup as events plus footage      | One archive of everything.                             | Contradicts the settled restore design; gigabytes; a second backup system. |

## Shape

- **The module behind the seam:** `ExportService` (`backend/services/export_service.py`), split by
  type behind one entry. Domain terms, added to `docs/reference/glossary.md`: **export job**,
  **export type** (`events`, `alerts`), **expired export**.
- **Its interface:**
  - `run(job_id)` reads the job's type, format and filters, writes the file in batches, and
    checks for cancellation between batches. It returns the file's path, size and row count, or
    `Cancelled` (the partial file deleted), or raises `ExportTooLarge` for a ZIP over 1,000 events
    (the job fails with that message).
  - `events(filters)` and `alerts(filters)` yield rows in batches; `events` takes every timeline
    filter and excludes trashed events; `alerts` returns, per alert: created, rule, camera,
    severity, verdict and its source, match count, the people told and on which channels, and the
    state (`open`, `acknowledged`, `dismissed`).
  - `expire(now)` deletes files whose job finished over 24 hours ago and marks those jobs
    `expired`.
  - Invariants: a job ends in exactly one of `completed`, `failed`, `cancelled` or `expired`;
    every status write after `running` is conditional on the status it expects, so a late finish
    cannot overwrite a cancel; a file is served only from the path stored on its job.
  - Configuration: `EXPORT_DIR` on the data volume, `EXPORT_RETENTION_HOURS` (24) and
    `EXPORT_ZIP_MAX_EVENTS` (1,000).
- **Its adapters:**
  - **HTTP:** `POST /api/exports` (type, format, filters), list, status, `DELETE` (cancel), and
    `/download`, which answers 410 "expired, export again" for an expired job.
  - **The worker:** the background task that runs a job.
  - **The cleanup:** an hourly job calling `expire`.

## What changes

- **backend (`B4.10`):** `export_service.py` (types, batches, ZIP thumbnails, cancel, expiry);
  `exports.py` (filters, conditional writes, 410, audit, rate limit); `export_job.py` (statuses
  `cancelled` and `expired`, an additive recorded upgrade); the cleanup job; retire
  `POST /api/events/export` and its tracker job from `jobs.py`, and `GET /api/events/export` from
  `events.py`, through `scripts/retired_paths.txt`; `detections.py` (the Trash filter, no
  `file_path`); `EXPORT_DIR` in `config.py`, `.env.example` and the compose volume (UR-9).
- **frontend (`F4.7`):** `ExportButton.tsx` on `POST /api/exports` and `/download`, passing every
  timeline filter; `ExportModal.tsx` and `DataManagementPage.tsx` offer Events and Alerts and link
  to Backups; Cancel calls `DELETE` everywhere; the cancelled and expired states; the
  `exportEventsCSV` client and the tracker polling go.
- **docs:** the glossary terms; Trash's erasure text says a purged event can remain in an export for
  at most a day (`4n-trash.md` and its user doc; UR-81).

## Failure handling

- **A worker that dies mid-export** leaves the job `running`; at startup, jobs still `running` or
  `pending` are marked `failed` ("interrupted"), and their partial files deleted.
- **A cancel during the last batch** wins: the finishing write is conditional on `running`.
- **A missing thumbnail** is skipped and listed in the ZIP's JSON as absent.
- **A full disk** fails the job with the error, deletes the partial file, and leaves other jobs
  alone.

## Tests

- **Consolidation scope:** `export_service.py`, `exports.py`, `job_tracker.py`'s export path, the
  `jobs.py` and `events.py` export routes (whose tests retire with them), `detections.py`'s export,
  and `ExportButton`, `ExportModal`, `ExportProgress`, `useExportJobs`; the e2e spec that mocks a
  missing route is rewritten or retired.
- **Tests through the interface:** each type and format; every timeline filter reaches the query;
  trashed events never appear (events, ZIP, detections); cancel before start, mid-export and during
  the last batch; a late finish never overwrites `cancelled`; the ZIP limit; expiry deletes the file
  and answers 410; startup marks interrupted jobs; the retired routes answer 404.

## Golden path

- **Spec, backend** (`backend/tests/golden/external/test_export_job.py`, extended): start an events
  export and an alerts export, download each; cancel one mid-run and read `cancelled`; expire one
  with a fixed clock and read 410.
- **Spec, UI** (Playwright, `frontend/tests/golden/timeline/`): set a filter, export from the
  timeline button and download the file; cancel an export and see it cancelled; Data › Export lists
  the Alerts type and links to Backups.
- **Fake-stack scenario:** the seeded events and one alert from the fake pipeline.
- **Real-tier check:** the operator exports a ZIP from the test deployment on the GB300 and reads
  its thumbnails, then cancels a large export.

## Privacy and security

Exports carry event text, which can name people or plates, and in a ZIP their pictures. Files live
on the data volume for at most 24 hours, excluded from backups, and are served only from the path
stored on their job. With `EXPOSE_LAN=true` every route needs a session or API key; starting and
downloading are audited, and starting is rate-limited. Trashed events never appear in any export.

## Rollout and reversal

The schema change is additive. On upgrade, existing jobs keep their status, and files left in
`/tmp/exports` are gone with the tmpfs; their jobs are marked expired at startup. The retired
routes go through `scripts/retired_paths.txt`. Code reversal is a revert; the recorded upgrade
stays.

## Packages

| package | lane (proposed) | depends on                                                     | contents                                                                                                    | its own golden path   |
| ------- | --------------- | -------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- | --------------------- |
| `B4.10` | backend         | `B4.1` and `B4.2` merged (the alert rows and their deliveries) | One job path, the two types, ZIP thumbnails, files and expiry, cancel, filters, audit, the retired routes.  | Backend pytest above. |
| `F4.7`  | frontend        | `B4.10`                                                        | The button and modal on the one path, the Alerts type, the Backups link, cancel everywhere, the new states. | Playwright above.     |

Each runs the six steps as two PRs: a test-only consolidation PR, then the build.

## Done when

Each package: its golden path green on the fake stack and its real-tier check posted. F-051, F-098
and F-099 read **works** once both packages have merged and the real-tier check is posted.
