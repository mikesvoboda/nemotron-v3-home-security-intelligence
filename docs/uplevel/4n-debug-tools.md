# 4n — Debug Tools Design

> Step 1 of the debug tools packages (`packages/backend.md`, "B4.\* Feature track"), copied from
> [`templates/feature-design.md`](templates/feature-design.md). Ruling 319 settled its decisions;
> this design makes them exact.

**Packages:** `F4.10`, `B4.12` · **Inventory rows:** F-133, F-145, F-151–F-159, F-195 (OD-36,
ruled keep, admin-only) · **R2 ruling:** F-151–F-153 and F-157 complete, priority 2, following
OD-36; ruling 319 settles OD-36 · **Designed:** 2026-10-22, with the owner

## Where it starts

Facts read at `main` `9481f00cc`.

- **The guard does nothing.** The 22 routes of `backend/api/routes/debug.py` (prefix `/api/debug`,
  `:46`) depend on `require_debug_mode` (`:57`), whose body is `pass` (`:71-72`).
- **Ten of them change state:** `POST /log-level` (`:746`), `/profile/start` (`:839`),
  `/profile/stop` (`:881`), `/memory/gc` (`:1206`), `/memory/tracemalloc/start` (`:1257`),
  `/memory/tracemalloc/stop` (`:1299`), `/replay/{recording_id}` (`:1522`),
  `DELETE /recordings/{recording_id}` (`:1651`), `POST /batch/add-detection` (`:1728`) and
  `/batch/reset-metrics` (`:1850`). With LAN exposure on, any session or API key reaches them.
- **The real admin check exists.** `get_current_admin_user` (`backend/api/routes/auth.py:485`)
  takes a session and refuses a non-admin with 403. `4n-status.md` puts Restart behind it, with a
  sign-in prompt in the UI (`F4.8`).
- **Who calls the routes.**
  - **The Developer Tools** on `/operations` render with no condition
    (`frontend/src/components/system/SystemMonitoringPage.tsx:666`).
  - **Logging Settings** (F-195) on `/settings/admin` (`AdminSettings.tsx:756`) reads `/config`
    and reads and sets `/log-level`.
  - **The Databases section's Redis INFO** (F-145) reads `/redis/info`, and loads only while the
    page's debug toggle is on (`SystemMonitoringPage.tsx:94-100`).
- **The profiling row is broken at the client.**
  - Status reads `/api/debug/profile`, which is not served; only `/profile/stats` is (`:924`).
  - Start and Stop follow that 404ing status, so the button never turns to Stop (F-152).
  - Download fetches `/profile/download`, which is not served (F-153).
  - Clear all sends `DELETE /recordings`, which answers 405, since only a single recording can be
    deleted (`:1405`, `:1651`; F-157).
- **The default test stack runs with `DEBUG=false`** (`docker-compose.ci.yml:131`). Four golden
  specs use debug routes there as supply or load: `operations/batch-statistics`,
  `operations/performance-alerts`, `operations/databases` and `shell/rate-limit`. The tools' own
  specs are `operations/config-inspector`, `operations/log-level`, `operations/recording-replay`
  (and its seeded twin) and `gpu-storage-admin/admin-logging`. The harness has `loginAsAdmin`
  (`frontend/tests/golden/harness.ts:640`).

## What the user can do when this is done

An admin opens Operations in Advanced mode and uses the Developer Tools: profiling starts, stops,
shows its top functions and downloads; recordings replay, delete one at a time or clear all; the
log level changes. Anyone else sees the admin sign-in prompt in their place, and the server refuses
the routes to them.

## Decisions

| question                          | decision                                                                                                                                          | why                                                                                                |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Keep or retire?                   | Keep (owner, ruling 319).                                                                                                                         | The tools are useful, and their golden paths are already green.                                    |
| Who may call the routes?          | An admin session, through `get_current_admin_user`, in every setup; no session, a non-admin and an API key are refused (owner, ruling 319).       | The check the owner chose for Restart; `settings.debug` no longer decides.                         |
| What does a non-admin see?        | `F4.8`'s admin sign-in prompt in place of the Developer Tools, Logging Settings and the Redis INFO block.                                         | One prompt for every admin action.                                                                 |
| Where do the tools sit?           | Operations, in Advanced's Operations & Monitoring hub (`4n-modes.md`).                                                                            | Ruling 319 left placement to the modes design.                                                     |
| How are the profiling rows fixed? | Status reads `/profile/stats`; Start and Stop follow it; Download gets a served route; Clear all deletes each recording.                          | The sheet's S fixes (OD-36's "To complete").                                                       |
| How do the specs run?             | The supply specs and the tools' specs sign in with `loginAsAdmin`; none moves to a `DEBUG=true` run (owner, ruling 319).                          | They stay on the default stack.                                                                    |
| In which order?                   | `F4.10` first: the UI renders the tools for an admin session only, and the specs sign in as admin. `B4.12` then puts the routes behind the check. | Each stays green alone; guarding the routes first would break the UI until the frontend caught up. |

## Shape

- **The module behind the seam:** the existing debug router. Its dependency becomes the admin check
  in place of `require_debug_mode`, which goes. No new domain term.
- **Its interface:**
  - Every `/api/debug/*` route answers 401 with no session and 403 for a non-admin session, and
    refuses an API key.
  - A new `GET /api/debug/profile/download` returns the last stopped profile as a `.prof` file,
    and 404 when none exists.
  - A new `DELETE /api/debug/recordings` clears every recording, and answers with the count.
- **Its adapters:** the Developer Tools panels, Logging Settings and the Databases section, through
  the existing hooks.

## What changes

- **`F4.10` (frontend):**
  - The Developer Tools section, Logging Settings and the Redis INFO block render for an admin
    session, and show `F4.8`'s sign-in prompt otherwise.
  - The profiling client reads `/profile/stats`, Start and Stop follow it, and Download and Clear
    all call the routes `B4.12` serves.
  - The four supply specs and the tools' specs sign in with `loginAsAdmin`.
- **`B4.12` (backend):**
  - `require_debug_mode` goes, and the 22 routes take the admin check.
  - It adds the download and clear-all routes, and regenerates the contract and types (UR-83).
  - Pytest proves the three refusals on one read route and one state-changing route, and that an
    admin passes.
- **Docs:** F-151–F-159, F-195 and F-145 re-cite their evidence; F-133 is unchanged (it follows
  `DEBUG`).

## Failure handling

- **No admin exists** (LAN exposure off, a fresh install): `F4.8`'s prompt offers to create the
  first admin.
- **Download with no stopped profile:** 404, and the panel says no profile has been recorded.

## Tests

- **Consolidation scope:** the debug router's backend tests and the Developer Tools panel tests.
- **Tests through the interface:** the refusals and the admin pass on two routes; download and
  clear-all on a seeded recorder; the panels' admin and non-admin rendering.

## Golden path

- **Spec:** the existing tools' specs, now signed in as admin, plus Download and Clear all in
  `operations/recording-replay.seeded.spec.ts` and the profiling panel. Signed out, `/operations`
  shows the sign-in prompt where the tools were.
- **Fake-stack scenario:** the seeded fake tier with `REQUEST_RECORDING_ENABLED=true`, as today.
- **Real-tier check:** the same specs under `scripts/feature-check.sh --real`.

## Privacy and security

Recordings may hold request bodies; only an admin session can now list, replay, delete or clear
them, and replaying a request against the live app is an admin's act. API keys reach none of it.

## Rollout and reversal

`F4.10` lands first and changes only who sees the tools; `B4.12` then closes the routes. Each
reverts alone: reverting `B4.12` reopens the routes, reverting `F4.10` alone is safe only before
`B4.12` merges.

## Packages

| package | lane     | depends on | contents                                                                                  | its own golden path       |
| ------- | -------- | ---------- | ----------------------------------------------------------------------------------------- | ------------------------- |
| `F4.10` | frontend | `F4.8`     | Admin-only rendering with the sign-in prompt, the profiling client fixes, specs as admin. | The tools' specs, above.  |
| `B4.12` | backend  | `F4.10`    | The admin check on all 22 routes, download and clear-all, the regenerated contract.       | Backend pytest of routes. |

Both are owner-flagged (ruling 89) and run the six steps as two PRs each. `F4.10` goes after
`F4.7` on frontend's queue; `B4.12` goes on backend's queue once `F4.10` merges.

## Done when

Both packages' golden paths are green on the fake stack and their real-tier checks are posted;
F-151–F-153 and F-157 read **works**; and a test pins a debug route refused to a non-admin session
with `DEBUG=false`.
