# 4n — Trash Design

> Step 1 of the Trash feature packages (`packages/backend.md`, "B4.\* Feature track"), copied from
> [`templates/feature-design.md`](templates/feature-design.md).

**Packages:** `B4.4`, `F4.3` · **Inventory rows:** F-087, F-088 · **R2 ruling:** complete,
priority 1 (R2a row 14; rulings 131, 135) · **Designed:** 2026-10-21, with the owner

## Where it starts

Facts read at `main` `c75111487`.

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
- **Bulk permanent delete does work**, files included: `bulk_delete_events` calls
  `hard_delete_event` (`events.py:1885`; `event_service.py:249`), which deletes the paths
  `_collect_file_paths` gathers (`event_service.py:65`: the clip, each detection's image and
  thumbnail).
- **What survives a permanent delete today.** Every child table of `events` cascades (alerts,
  detections, verifications, notify decisions, feedback, audit). Derived data does not: re-ID
  entities keep a detection id with no foreign key (`backend/models/entity.py:7-9`), and household
  reference embeddings only lose their source link (`backend/models/household.py:203`,
  `SET NULL`).

## What the user can do when this is done

The user opens an event and clicks Delete; a toast says "Moved to Trash · Undo". In Trash the
event shows how long ago it was deleted and when it will be purged. The user restores it, or
deletes it permanently after confirming, and it is gone with its footage and the face and re-ID
data computed from it. Anything left in Trash is purged after 30 days.

## Decisions

| question                                                           | decision                                                                                                                                                                                                                                               | why                                                                                                                          |
| ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------- |
| How does an event reach Trash?                                     | Delete in the event detail modal and a bulk Delete on the timeline, both on the existing soft-delete routes. No confirmation; an Undo toast instead.                                                                                                   | Ruling 131; a soft delete is reversible, so a dialog only adds friction.                                                     |
| What does a permanent delete remove?                               | The event's files, the face embeddings and re-ID appearances computed from its detections, and the event row with everything that cascades from it. References a person deliberately enrolled stay; only their link to the event is cleared, as today. | A stranger's biometric trace should go with the footage; enrolled household references must not silently weaken recognition. |
| Can an event be deleted permanently without passing through Trash? | No. A permanent delete of an event not in Trash returns 409.                                                                                                                                                                                           | One path, so every permanent delete is a deliberate second step.                                                             |
| Does Trash empty itself?                                           | Yes: events trashed more than `trash_retention_days` ago (default 30, 0 turns it off) are purged by a daily job.                                                                                                                                       | What people expect of a trash can; deleted footage should not linger.                                                        |
| What happens to an alert whose event is trashed?                   | Its open alerts are dismissed with the reason "event moved to Trash". Restoring the event does not reopen them. A permanent delete removes the alerts and their deliveries with the event.                                                             | Keeps the Alerts page (`4n-alerting.md`) from pointing at events the user deleted.                                           |

## Shape

- **The module behind the seam:** `EventPurger` in `backend/services/event_purger.py`. Domain term,
  added to `docs/reference/glossary.md`: **purge** (a permanent delete, including derived data).
- **Its interface:** `purge(event_ids, *, reason: "user" | "trash_retention") -> PurgeReport` with
  the files deleted and failed, the derived rows removed, and the events removed. It refuses an
  event not in Trash. It keeps the invariant that an enrolled reference embedding is never
  deleted, only unlinked.
- **Its adapters:** the single permanent delete route, the bulk delete route, Empty Trash, and the
  daily cleanup job. All four call `purge`; `hard_delete_event`'s file deletion moves inside it.

## What changes

- **backend (`B4.4`):**
  - `event_purger.py` (new); `delete_event` honours `?permanent=true` and calls the purger;
    `bulk_delete_events` and Empty Trash call it too;
  - the cleanup service runs the trash-retention purge daily; `trash_retention_days` joins
    `backend/core/config.py`, `.env.example` and the compose `environment:` block (UR-9);
  - soft delete dismisses the event's open alerts once `B4.1` has landed (whichever of `B4.1` and
    `B4.4` lands second carries that step);
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
  - `purge` removes the files, a stranger's face embedding, the re-ID appearance, and the alert
    with its deliveries; it keeps an enrolled reference embedding with its source link cleared;
  - a permanent delete of an event not in Trash returns 409;
  - the retention purge on a fixed clock keeps an event trashed 29 days ago and purges one
    trashed 30 days ago; 0 disables it.

## Golden path

- **Spec (Playwright):** open an event, Delete, Undo, Delete again; find it in Trash; Restore it;
  Delete again; Delete permanently and confirm. The event then answers 404 and its files are
  gone. It replaces the current spec's API-side seeding (ruling 135).
- **Fake-stack scenario:** any seeded event with a detection image and a thumbnail.
- **Real-tier check:** the operator purges one event on a test deployment and lists its media
  directory before and after.

## Privacy and security

- **Erasure:** a permanent delete removes the footage and the biometric data computed from it
  (OD-18, OD-19); the retention purge does the same after 30 days.
- **What stays:** a content-free audit entry, and enrolled reference embeddings, which are the
  household's own records.
- **Access:** under `EXPOSE_LAN` the routes keep their existing authentication.

## Rollout and reversal

No migration: `events.deleted_at` exists. The retention purge starts with the default of 30 days;
setting `trash_retention_days` to 0 stops it. Code reversal is a revert.

## Done when

`B4.4` and `F4.3`: the golden path is green on the fake stack, the real-tier check is posted, and
F-087 and F-088 read **works**.
