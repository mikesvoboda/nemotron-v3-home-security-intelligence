# 4n — Trash Design

> Step 1 of the Trash feature packages (`packages/backend.md`, "B4.\* Feature track"), copied from
> [`templates/feature-design.md`](templates/feature-design.md).

**Packages:** `B4.4`, then `F4.3` · **Inventory rows:** F-087, F-088 · **R2 ruling:** complete,
priority 1 (R2a row 14; rulings 131, 135) · **Designed:** 2026-10-21, with the owner

## Where it starts

Facts read at `main` `bc89bf68a`.

- **Nothing in the UI moves an event to Trash.** The soft-delete routes exist,
  `delete_event` (`backend/api/routes/events.py:2687`, calling `soft_delete_event` at `:2710`) and
  `bulk_delete_events` (`:1842`), but no frontend surface calls them, so `/trash` fills only through
  direct API use.
- **Trash itself works.** `list_deleted_events` (`events.py:1508`) and `restore_event` (`:2744`)
  back `frontend/src/pages/TrashPage.tsx` through `frontend/src/hooks/useTrashQuery.ts`.
- **Single permanent delete does not.** The client sends `{ soft_delete: false }`
  (`frontend/src/services/api.ts:2517`), the route ignores it and soft-deletes again, and on a
  trashed event `soft_delete_event` raises "Event already deleted"
  (`backend/services/event_service.py:125`), returned as 409. Nothing is purged.
- **Bulk permanent delete removes files and the event, not its detections.** `bulk_delete_events`
  calls `hard_delete_event` (`events.py:1885`; `event_service.py:249`), which deletes the paths
  `_collect_file_paths` gathers (`event_service.py:65`: the clip, each detection's image and
  thumbnail), then the event row. `Event.detections` is view-only (`backend/models/event.py:174`);
  only the `event_detections` link rows cascade. The detection rows and their `enrichment_data`
  survive, and every detection from one image or video shares that file (`file_path`).
- **Orphaned detections come back.** At startup, `recover_orphaned_detections`
  (`backend/services/batch_aggregator.py:1504`, called from `backend/main.py:961`) re-batches
  detections that have no event link, so a hard-deleted event's detections return as a new event.
- **General retention ignores Trash.** The cleanup service deletes detections by `detected_at` and
  events by `started_at` (`backend/services/cleanup_service.py:283-296`) without reading
  `deleted_at`, removes neither clips nor original images, and cannot be turned off
  (`retention_days`, default 30, `gt=0`, `backend/core/config.py:757-760`).
- **Soft delete schedules its files for deletion.** It queues the event's files for deletion in
  300 s (`event_service.py:154-166`, `backend/services/file_service.py:25`) and restore cancels the
  job. No production code starts the worker that would run it.
- **What derived data exists, and how it links.** Every child table of `events` cascades (alerts,
  verifications, notify decisions, feedback, audit). Re-ID `entities` keep the detection that
  created them (`primary_detection_id`, no foreign key, `backend/models/entity.py:7-9`), and their
  Redis copies carry a detection id and expire within 48 h (`backend/services/reid_service.py:71`).
  Legacy `face_detection_events` hold a face vector with camera and time but no event or detection
  link (`backend/models/face_identity.py:210`). None of these stores has a live writer on `main`.
  Household reference embeddings lose only their source event (`backend/models/household.py:203`,
  `SET NULL`); a gallery face enrolled from a detection keeps its file path
  (`backend/api/routes/face_recognition.py:752`).

## What the user can do when this is done

The user opens an event and clicks Delete; a toast says "Moved to Trash · Undo". In Trash the
event shows how long ago it was deleted and when it will be purged. The user restores it, or
deletes it permanently after confirming, and it is gone with its footage, its detections and the
face and re-ID data that can be traced to it. Anything left in Trash is purged when its date comes.

## Decisions

| question                                                           | decision                                                                                                                                                                                                                                                                                                                                                                                     | why                                                                                                                          |
| ------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| How does an event reach Trash?                                     | Delete in the event detail modal and a bulk Delete on the timeline, both on the existing soft-delete routes. No confirmation; an Undo toast instead. Soft delete no longer schedules its files for deletion.                                                                                                                                                                                 | Ruling 131; a soft delete is reversible, so a dialog only adds friction, and Trash must keep the footage it promises.        |
| What does a permanent delete remove?                               | The event's detections with their enrichment; the files no surviving detection uses; `entities` whose `primary_detection_id` is purged; legacy face rows on the event's camera within its start and end time; and the event row with everything that cascades from it. Enrolled references stay; their links to the event and its files are cleared. Redis re-ID copies expire on their own. | A stranger's biometric trace should go with the footage; enrolled household references must not silently weaken recognition. |
| Can an event be deleted permanently without passing through Trash? | No. A permanent delete of an event not in Trash returns 409; a bulk permanent delete purges the trashed events and reports the others as refused.                                                                                                                                                                                                                                            | One path, so every permanent delete is a deliberate second step.                                                             |
| When does Trash empty itself?                                      | The daily job purges each trashed event at the earlier of `deleted_at + trash_retention_days` (default 30) and `started_at + retention_days`, before general retention runs. Trash shows that date. `trash_retention_days = 0` turns off only the Trash clock.                                                                                                                               | Deleting an event should never extend its life, and general retention must not skip the purge's erasure.                     |
| What happens to an alert whose events are trashed?                 | An alert covers every event folded into it (`alert_events`, added by `B4.1`). It is dismissed with the reason "events moved to Trash" only when all its events are in Trash; restoring does not reopen it. A purge removes its link rows and repoints it to its earliest surviving event; the alert and its deliveries go only when no event is left.                                        | Keeps the Alerts page (`4n-alerting.md`) from pointing at deleted events, without losing alerts for live activity.           |
| How is the work packaged?                                          | `B4.4` (backend) lands first with an HTTP golden path; `F4.3` (frontend) depends on it and carries the Playwright path.                                                                                                                                                                                                                                                                      | Neither half can pass a shared end-to-end path alone.                                                                        |

## Shape

- **The module behind the seam:** `EventPurger` in `backend/services/event_purger.py`. Domain term,
  added to `docs/reference/glossary.md`: **purge** (a permanent delete, including detections and
  derived data).
- **Its interface:** `purge(event_ids, *, reason: "user" | "trash_retention") -> PurgeReport` with,
  per event, purged or refused (not in Trash) or kept (a file failed), the files deleted and
  failed, and the rows removed by kind.
- **Its order:**
  1. refuse any event not in Trash;
  2. collect the detections linked to the purged events and to no surviving event;
  3. collect the files: each event's clip, those detections' thumbnails, and their `file_path`s
     that no surviving detection references;
  4. delete the files, counting a missing file as deleted; if any deletion fails, leave that event
     in Trash, report it, and let the daily job retry;
  5. in one transaction: delete the derived rows, clear enrolled references' links, remove the
     event from its alerts' `alert_events` (once `B4.1` has landed), delete the detections and
     the events, and write the audit entry.
- **Invariants:** an enrolled reference embedding is never deleted, only unlinked. Any new writer
  of a vector derived from a detection stores the detection's id, through a recorded SQL upgrade
  (`backend/migrations/registry.py`); the face-events package (F-276) adds
  `face_detection_events.detection_id` with its writer.
- **Its adapters:** the single permanent delete route, the bulk delete route, Empty Trash, and the
  daily cleanup job. All four call `purge`; `hard_delete_event`'s file deletion moves inside it.

## What changes

- **backend (`B4.4`):**
  - `event_purger.py` (new); `delete_event` honours `?permanent=true` and calls the purger;
    `bulk_delete_events` and Empty Trash call it too;
  - `soft_delete_event` stops scheduling file deletion, and the delayed-deletion path is removed;
  - the cleanup service runs the trash purge first, at the earlier deadline; `trash_retention_days`
    joins `backend/core/config.py`, `.env.example` and the compose `environment:` block (UR-9),
    read so that 0 stays 0 (not `value or default`);
  - alerts: soft delete dismisses an alert whose events are all in Trash, and purge maintains
    `alert_events`; whichever of `B4.1` and `B4.4` lands second carries this, and whichever of
    `B4.2` and `B4.4` lands second carries the deliveries' removal;
  - the general audit log records each purge without content: the event id, the time, the reason.
- **frontend (`F4.3`):** Delete in `EventDetailModal`, bulk Delete on the timeline, the Undo
  toast; `permanentlyDeleteEvent` (`frontend/src/services/api.ts:2514`) sends
  `?permanent=true`; `TrashPage` shows the deleted and purge dates; the setting appears under
  Settings › Data.

## Tests

- **Consolidation scope:** `backend/api/routes/events.py` (the delete, bulk delete, list deleted
  and restore routes), `backend/services/event_service.py`, the cleanup service; frontend
  `TrashPage`, `useTrashQuery`, `EventDetailModal` and the timeline's selection bar.
- **Tests through the interface:**
  - `purge` removes the event, its detections, its files, the entity created from a purged
    detection and a legacy face row in the event's window; it keeps an enrolled reference
    embedding with its links cleared;
  - a file another surviving detection uses is kept; a failed file deletion leaves the event in
    Trash and reported;
  - after a purge and a restart, orphan recovery finds nothing;
  - a permanent delete of an event not in Trash returns 409; a bulk permanent delete of trashed
    and live events purges the first and refuses the second;
  - on a fixed clock the trash purge keeps an event trashed 29 days ago, purges one trashed 30
    days ago, and purges at `started_at + retention_days` when that is earlier; 0 disables only
    the Trash clock;
  - an alert covering two events stays open when one is trashed, is repointed when its first is
    purged, and is removed with its deliveries when both are.

## Golden path

- **`B4.4` (pytest, `backend/tests/golden/external/test_trash_purge.py`):** a permanent delete of a
  live event answers 409; trash it, delete it permanently, and it answers 404 with its files and
  detections gone; Empty Trash purges the rest.
- **`F4.3` (Playwright):** open an event, Delete, Undo, Delete again; find it in Trash; Restore it;
  Delete again; Delete permanently and confirm. The event then answers 404 and its files are gone.
  It replaces the current spec's API-side seeding (ruling 135).
- **Fake-stack scenario:** any seeded event with a detection image and a thumbnail.
- **Real-tier check:** the operator purges one event on a test deployment and lists its media
  directory before and after.

## Privacy and security

- **Erasure:** a permanent delete removes the footage, the detections and the biometric data that
  can be traced to the event (OD-18, OD-19); the trash purge does the same when its date comes.
  Redis re-ID copies are not chased; they expire within 48 h.
- **What stays:** a content-free audit entry, and enrolled reference embeddings, which are the
  household's own records.
- **Access:** under `EXPOSE_LAN` the routes keep their existing authentication.

## Rollout and reversal

No migration in `B4.4`: `events.deleted_at` exists, `alert_events` arrives with `B4.1`'s upgrade,
and the provenance column arrives with its writer. The trash purge starts with the default of 30
days; setting `trash_retention_days` to 0 stops its clock. Code reversal is a revert.

## Review

An adversarial review (2026-10-21) and a fresh-context check of it found six issues; every cite
held at `origin/main` `bc89bf68a`, and one claim (detections cascade) was wrong. The owner ruled on
four:

| #   | finding                                               | amendment                                                                                                  |
| --- | ----------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| T1  | Not every derived vector links to its event           | Erasure narrowed to what links; legacy face rows by time window (owner); a provenance rule for new writers |
| T2  | Deleting an event leaves its detections, which return | The purge deletes detections; shared files kept; failed files keep the event in Trash                      |
| T3  | General retention erases Trash early and incompletely | The earlier deadline, purged first through the purger (owner)                                              |
| T11 | Neither package can pass the shared golden path alone | `B4.4` with a pytest path, `F4.3` after it (owner)                                                         |
| N1  | Soft delete schedules its files for deletion          | Soft delete stops scheduling; the delayed-deletion path goes                                               |
| N2  | Purging an alert's first event deletes a folded alert | `alert_events` in `B4.1`; dismiss when all events are trashed; repoint on purge (owner)                    |

## Done when

`B4.4`: its pytest golden path is green on the fake stack and the real-tier check is posted.
`F4.3`: its Playwright golden path is green on the fake stack, and F-087 and F-088 read **works**.
