# 4n — Debug Tools Design

> Step 1 of the debug tools packages (`packages/backend.md`, "B4.\* Feature track", and
> `packages/frontend.md`, "F4.\* Feature track, frontend parts"), copied from
> [`templates/feature-design.md`](templates/feature-design.md). Ruling 319 settled its decisions;
> this design makes them exact.

**Packages:** `B4.12`, `F4.10` · **Inventory rows:** F-133, F-145, F-151–F-159, F-195 (OD-36,
ruled keep, admin-only) · **R2 ruling:** F-151–F-153 and F-157 complete, priority 2, following
OD-36; ruling 319 settles OD-36 · **Designed:** 2026-10-22, with the owner

## Where it starts

Facts read at `main` `9481f00cc`.

- **The guard does nothing.** The 22 routes of `backend/api/routes/debug.py` (prefix `/api/debug`,
  `:46`) depend on `require_debug_mode` (`:57`), whose body is `pass` (`:71-72`). Its docstring
  (`:12-14`) and each route's "Debug mode disabled" 404 response (for example `:843`) describe a
  guard that never runs.
- **Ten of them change state:** `POST /log-level` (`:746`), `/profile/start` (`:839`),
  `/profile/stop` (`:881`), `/memory/gc` (`:1206`), `/memory/tracemalloc/start` (`:1257`),
  `/memory/tracemalloc/stop` (`:1299`), `/replay/{recording_id}` (`:1522`),
  `DELETE /recordings/{recording_id}` (`:1651`), `POST /batch/add-detection` (`:1728`) and
  `/batch/reset-metrics` (`:1850`). With LAN exposure on, any session reaches them, and so does any
  API key whose scope covers them (`backend/api/middleware/auth.py:15-21`).
- **The real admin check exists, and what it answers.** `get_current_admin_user`
  (`backend/api/routes/auth.py:485-504`) depends on `get_current_user`, which reads only the session
  cookie (`:419-439`). With LAN exposure off, the middleware passes every request
  (`backend/api/middleware/auth.py:661-663`), so the route answers: 401 with no session, an unknown
  session or an API key alone; 403 for a non-admin; 503 when Redis is down (`auth.py:442-447`). With
  LAN exposure on, a missing or bad credential is refused by the middleware with 401 (`:667-668`); a
  valid key alone passes it and gets 401 from the route. The first account is always an admin
  (`auth.py:216`), and with no account the app sends everyone to `/setup`
  (`frontend/src/components/auth/ProtectedRoute.tsx:79-81`).
- **The UI cannot tell an admin with LAN exposure off.** `AuthContext` loads `/api/auth/me` only
  when the backend requires auth (`frontend/src/contexts/AuthContext.tsx:149-160`), so that no
  login appears with `EXPOSE_LAN` unset (F1.3). `4n-status.md` gives Restart a sign-in prompt in
  `ServicesPanel` (`F4.8`) without naming how the UI learns who is admin.
- **Who calls the routes.**
  - **The Developer Tools** on `/operations` render with no condition
    (`frontend/src/components/system/SystemMonitoringPage.tsx:666`). The section also holds the
    Test Data panel (`:726-736`), whose rows OD-37 rules.
  - **Logging Settings** (F-195) on `/settings/admin` (`AdminSettings.tsx:756`) reads `/config` and
    reads and sets `/log-level`; it also edits log retention through `PATCH /api/system/config`
    (`LoggingSettings.tsx:172-180`).
  - **The Databases section's Redis INFO** (F-145) reads `/redis/info` while the page's
    `system-debug-mode` flag is on (`SystemMonitoringPage.tsx:85`, `:94-100`).
  - **No UI reaches** `DeveloperToolsPage`, which has no route and hosts the circuit-breaker and
    memory panels, nor the unused `usePipelineErrorsQuery` and `useWebSocketConnectionsQuery`.
  - **Scripts:** the golden harness seeds recordings and loads the pipeline through `/recordings`
    and `/pipeline-state` with no cookie (`scripts/feature_check.py:3142`, `:3262`), and a failure
    stops the run before any spec (`:4314-4315`);
    `backend/tests/unit/scripts/test_feature_check.py:6603-6664` pins those calls. The daily load
    test calls three debug routes with no cookie (`scripts/load_test.py:43-45`, `:70`;
    `.github/workflows/load-tests.yml:355`).
- **The profiling row is broken at the client and at the response.**
  - Status reads `/api/debug/profile`, which is not served; `/profile/stats` is (`:924`).
  - `/profile/stats` answers `is_profiling`, `stats_text`, `last_profile_path` and `timestamp`
    (`:830-836`), but the client reads `results` (`frontend/src/hooks/useProfileQuery.ts:129`), and
    the panel needs `results` for its function table and its Download button (F-151–F-153).
  - Download fetches `/profile/download`, which is not served (F-153).
  - Clear all sends `DELETE /recordings`, which answers 405; only one recording can be deleted at a
    time (`:1405`, `:1651`; F-157). The R2 sheet's fix is "delete per recording".
  - `frontend/src/__tests__/api-endpoint-contract-known-missing.json` records all three as known
    missing, and the contract test fails on an entry that has gone stale.
- **Specs.** The default test stack runs with `DEBUG=false` (`docker-compose.ci.yml:131`).
  - `operations/batch-statistics` and `operations/performance-alerts` use debug routes as supply
    or load; `shell/rate-limit` signs in only when the backend requires auth
    (`frontend/tests/golden/shell/rate-limit.spec.ts:276-285`), which CI never does, and its restore
    step expects 200 (`:626-643`).
  - The tools' own specs: `operations/config-inspector`, `operations/log-level`,
    `operations/recording-replay` and its seeded twin, `operations/databases` (F-145),
    `operations/debug-mode-toggle` and its seeded twin, `operations/test-data`,
    `gpu-storage-admin/admin-logging`, `gpu-storage-admin/admin-settings-page` (`:114`) and
    `gpu-storage-admin/developer-tools-seed-clear.seeded`. No profiling spec exists.
  - The harness signs in with `loginAsAdmin` (`frontend/tests/golden/harness.ts:640`) or
    `loginAsAdminShell` (`:663`).
  - Backend tests outside the router's own reach debug routes too:
    `backend/tests/unit/api/middleware/test_request_recorder.py:851-1024`,
    `backend/tests/unit/middleware/test_correlation_id.py:76` and
    `backend/tests/integration/test_admin_api.py:514`.

## What the user can do when this is done

An admin opens Operations in Advanced mode and uses the Developer Tools: profiling starts, stops,
shows its top functions and downloads the profile; recordings replay, delete one at a time or clear
all; the log level changes. Anyone else sees the admin sign-in prompt in their place, and the server
refuses the routes to them.

## Decisions

| question                          | decision                                                                                                                                                                                                                                                                                | why                                                                                                                                |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| Keep or retire?                   | Keep (owner, ruling 319).                                                                                                                                                                                                                                                               | Most of the tools' golden paths are green; profiling's fixes are small.                                                            |
| Who may call the routes?          | An admin session, through `get_current_admin_user`, in every setup (owner, ruling 319). The refusals are pinned: 401 with no session, an unknown one or an API key alone; 403 for a non-admin; 503 when Redis is down; and with LAN exposure on, the middleware's 401 (review DT6).     | The check the owner chose for Restart; `settings.debug` no longer decides.                                                         |
| How does the UI know an admin?    | `F4.8` builds a shared `useIsAdmin`, which loads `/api/auth/me` whether or not the backend requires auth and reads 401 as "not signed in" without redirecting, and a shared `AdminSignInPrompt`; Restart and these tools both use them (owner; review DT5).                             | With LAN exposure off the UI never loads the user today, and no login may appear unasked (F1.3).                                   |
| What sits behind the gate?        | The whole Developer Tools section (profiling, recordings, configuration inspector, log level, and the Test Data panel, whose keep or retire stays OD-37's), Logging Settings with its retention fields, and the Redis INFO block (review DT10).                                         | Each calls a debug route or sits in the gated section; one rule for the section is easier to keep.                                 |
| Where do the tools sit?           | Operations and Admin, in Advanced's Operations & Monitoring hub (`4n-modes.md`).                                                                                                                                                                                                        | Ruling 319 left placement to the modes design.                                                                                     |
| How are the profiling rows fixed? | `/profile/stats` adds `results`, the top functions of the last stopped profile (name, calls, own time, cumulative time), beside its fields; `GET /profile/download` serves that profile; the client reads `/profile/stats`; Clear all deletes each recording in turn (review DT2, DT3). | What the panel already renders, from the profile the backend already keeps; the sheet's per-recording fix.                         |
| How do the specs run?             | Every spec that opens a gated surface or calls a debug route signs in as admin; `shell/rate-limit` always does. None moves to a `DEBUG=true` run (owner, ruling 319).                                                                                                                   | They stay on the default stack.                                                                                                    |
| In which order?                   | `B4.12` (backend) first adds the profiling results and the download route, guarding nothing yet. `F4.10` (frontend) then gates the UI, fixes the client and the specs, and closes the 22 routes behind the admin check as its cross-lane part (owner; review DT1).                      | Each lands green alone: the UI has its routes before it needs them, and the routes close in the PR that moves every caller (UR-9). |

## Shape

- **The module behind the seam:** the existing debug router. Its dependency becomes
  `get_current_admin_user` in place of `require_debug_mode`, which goes. No new domain term.
- **Its interface:**
  - Every `/api/debug/*` route refuses as the Decisions table pins.
  - `GET /api/debug/profile/stats` adds `results: list[{function, calls, own_seconds,
cumulative_seconds}] | null`, the top functions of the last stopped profile.
  - `GET /api/debug/profile/download` returns the last stopped profile as a `.prof` file, and 404
    when none exists.
- **Its adapters:** the Developer Tools panels, Logging Settings and the Databases section, through
  the existing hooks and `F4.8`'s `useIsAdmin`; the golden harness and the load test, with an admin
  cookie.

## What changes

- **`B4.12` (backend, expand):** `/profile/stats`' `results`, `/profile/download`, and their tests;
  `docs/openapi.json` and the generated types regenerated (UR-83); the `/api/debug/profile/download`
  entry leaves the contract's known-missing list. Nothing is guarded yet.
- **`F4.10` (frontend, contract):**
  - The gated surfaces render for an admin and show `AdminSignInPrompt` otherwise.
  - The profiling client reads `/profile/stats` and its `results`, Start and Stop follow it, and
    Download calls `B4.12`'s route; Clear all deletes each recording. The `/api/debug/profile` and
    `DELETE /api/debug/recordings` entries leave the known-missing list.
  - A new `operations/profiling.spec.ts`; every spec in "Where it starts" signs in as admin.
  - **Its cross-lane part (UR-9):** `require_debug_mode` goes and the 22 routes take the admin
    check; `scripts/feature_check.py` sends the harness admin's cookie (the admin it registers at
    `:3093`) with `test_feature_check.py`; `scripts/load_test.py` signs in or drops its debug calls;
    the backend tests above sign in; `docs/openapi.json` and the types are regenerated (UR-83); the
    stale docstring, the 404 responses and `backend/api/routes/AGENTS.md` (`:679`, `:691`, `:738`)
    are corrected (UR-81).
- **Docs:** F-145, F-151–F-159 and F-195 re-cite; F-133 is unchanged (it follows `DEBUG`).
  `packages/backend.md:320` stops calling OD-36 open, in the plan PR;
  `docs/vss-integration/17-action-plan.md:613` gains a pointer to ruling 319 in docs' next register
  PR (ruling 321).

## Failure handling

- **No admin session:** the sign-in prompt, never a redirect. With no account at all, the app is
  already on `/setup`.
- **Redis down:** the routes answer 503 and the panels say the backend cannot check who is signed
  in.
- **Download with no stopped profile:** 404, and the panel says no profile has been recorded.

## Tests

- **Consolidation scope:** the debug router's backend tests, the three backend tests above, the
  harness's debug calls in `test_feature_check.py`, and the Developer Tools, Logging Settings and
  Databases panel tests.
- **Tests through the interface:** each refusal and the admin pass on one read route and one
  state-changing route, with LAN exposure off and on; `results` and the download after a profile
  stops; Clear all deleting every recording; each gated surface's admin and non-admin rendering.

## Golden path

- **Spec, backend** (`backend/tests/golden/external/test_debug_access.py`, `F4.10`): with
  `DEBUG=false`, a debug route answers 401 without a session and 403 for a non-admin, and works for
  an admin. `B4.12`'s own golden path is the same file's profiling leg: start, stop, `results`,
  download.
- **Spec, UI** (`F4.10`): the tools' specs signed in as admin, plus `operations/profiling.spec.ts`
  (start, stop, the function table, download) and Clear all in
  `operations/recording-replay.seeded.spec.ts`. Signed out, `/operations` shows the sign-in prompt
  where the tools were.
- **Fake-stack scenario:** the seeded fake tier with `REQUEST_RECORDING_ENABLED=true`, as today.
- **Real-tier check:** the same specs under `scripts/feature-check.sh --real`.

## Privacy and security

Recordings may hold request bodies; only an admin session can now list, replay, delete or clear
them, and replaying a request against the live app is an admin's act. No API key reaches any debug
route.

## Rollout and reversal

`B4.12` adds a field and a route and closes nothing. `F4.10` changes who sees the tools and closes
the routes in one PR, so reverting it reopens them and restores the old UI together.

## Packages

| package | lane     | depends on      | contents                                                                                                                                   | its own golden path                      |
| ------- | -------- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------- |
| `B4.12` | backend  | none            | Expand: profiling `results`, the download route, the regenerated contract.                                                                 | The backend golden file's profiling leg. |
| `F4.10` | frontend | `B4.12`, `F4.8` | Contract: the gated UI with `F4.8`'s prompt, the profiling client, Clear all, specs as admin; closes the 22 routes and moves every caller. | The specs above.                         |

Both are owner-flagged (ruling 89) and run the six steps as two PRs each. `B4.12` goes on
backend's queue after `B4.10`; `F4.10` goes on frontend's after `F4.7`.

## Review

An adversarial review (2026-10-22) and a fresh-context check of the code found these; the owner
ruled the order (DT1) and the shared admin check (DT5):

| #    | finding                                                                                                       | amendment                                                                                                          |
| ---- | ------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| DT1  | `F4.10`'s golden path needed routes `B4.12` added only after it                                               | `B4.12` expands first; `F4.10` closes the routes as its cross-lane part (owner)                                    |
| DT2  | `/profile/stats` lacks the `results` the panel reads, so the URL fix alone leaves the table and Download dead | `/profile/stats` adds `results`; Download serves the last stopped profile                                          |
| DT3  | A bulk delete route contradicted the sheet's per-recording fix                                                | No bulk route; Clear all deletes each recording                                                                    |
| DT4  | Closing the routes breaks the golden harness and the load test, which call them with no cookie                | The closing PR sends the harness admin's cookie, updates their tests, and fixes the load test                      |
| DT5  | With LAN exposure off the UI never loads `/me`, so it cannot tell an admin                                    | `F4.8` builds the shared `useIsAdmin` and `AdminSignInPrompt` (owner); `4n-status.md` says so                      |
| DT6  | An API key alone gets 401, not 403; `4n-status.md` said 403                                                   | The codes are pinned here; `4n-status.md` is corrected                                                             |
| DT7  | `shell/rate-limit` signs in only when auth is required                                                        | It always signs in as admin                                                                                        |
| DT8  | The contract's known-missing entries would go stale                                                           | Each leaves in the PR that serves or stops calling it                                                              |
| DT9  | Callers, specs and backend tests were missing, and no profiling spec exists                                   | All listed; `F4.10` adds `operations/profiling.spec.ts`                                                            |
| DT10 | The gate also hides the Test Data panel and log retention                                                     | Stated; both admin-only; Test Data stays OD-37's                                                                   |
| DT11 | "No admin exists" cannot happen; Redis down was unhandled                                                     | No admin session shows the prompt; Redis down answers 503 and the panels say so                                    |
| DT12 | The backend proof was a unit test                                                                             | `backend/tests/golden/external/test_debug_access.py` (UR-127)                                                      |
| DT13 | Stale docs describe the old guard and an open OD-36                                                           | The docstring, the 404 responses, `AGENTS.md`, `17-action-plan.md:613` and `packages/backend.md:320` are corrected |

## Done when

Both packages' golden paths are green on the fake stack and their real-tier checks are posted;
F-151–F-153 and F-157 read **works**; the known-missing list holds no debug entry; and a golden test
pins a debug route refused to a non-admin session with `DEBUG=false`.
