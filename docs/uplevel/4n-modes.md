# 4n — Easy and Advanced Modes Design

> Step 1 of the Easy and Advanced modes package (`packages/frontend.md`, "F4.\* Feature track,
> frontend parts"), copied from [`templates/feature-design.md`](templates/feature-design.md).

**Package:** `F4.9` · **Inventory rows:** F-299 (new: Header › Easy/Advanced view mode); F-017,
F-018, F-019, F-021, F-198 (the navigation, palette, tour and settings shell it reshapes); F-006,
F-007, F-061, F-062, F-063, F-187 (surfaces it shows only in Advanced); F-054, F-056 (event-modal
rows whose specs move) · **R2 ruling:** none of its
own; ruling 182 (UR-182) rules the switch and each mode's scope, and F-063 (complete, P2) waits on
this design (ruling 317), so it takes priority 2 · **Designed:** 2026-10-22, with the owner

## Where it starts

Facts read at `main` `9481f00cc`.

- **No view mode exists.** Nothing in `frontend/src` or `backend/` switches what the app shows by
  audience. "Advanced" names only filter panels (`frontend/src/components/search/SearchBar.tsx:88`,
  `frontend/src/components/plate-reads/PlateSearchBar.tsx:117`) and the event's "advanced risk
  analysis" fields (`EventDetailModal.tsx:140`).
- **A debug mode does exist, and is a different thing.** `DebugModeContext` stores
  `system-debug-mode` through `useLocalStorage`
  (`frontend/src/contexts/DebugModeContext.tsx:61-70`); its toggle sits on `/operations` and shows
  only when the backend runs with `DEBUG=true` (`SystemMonitoringPage.tsx:408`,
  `DebugModeToggle.tsx:51`). It gates Raw Settings and the seed/clear tools on `/settings/admin`
  (`AdminSettings.tsx:158`, `:760`, `:778`). This design leaves it alone; ruling 319 and
  `4n-debug-tools.md` govern who may use the debug routes.
- **Navigation is six hand-kept lists.**
  - **The sidebar.** `navGroups` (`frontend/src/components/layout/sidebarNav.ts:58-147`) holds four
    groups (Monitoring, Analytics, Operations, Admin) and 33 items. `NavItem` has no visibility
    field (`:39-47`); two items carry the tour's targets (`:70`, `:143`). `Sidebar` renders every
    group (`Sidebar.tsx:338-347`).
  - **The phone bar.** `primaryNavItems` holds Dashboard, Timeline and Alerts
    (`MobileBottomNav.tsx:32-36`); its More sheet derives from `navGroups` (`:146-199`) and matches
    a path by segment (`:72`).
  - **The command palette.** `NAVIGATION_ITEMS` holds ten entries with keywords and shortcuts
    (`frontend/src/components/common/CommandPalette.tsx:41-42`, `:48-119`). The chords are
    `CHORD_ROUTES` (`frontend/src/hooks/useKeyboardShortcuts.ts:19-29`) and the help modal keeps
    `SHORTCUT_GROUPS` (`ShortcutsHelpModal.tsx:45-57`). `g y` opens `/system`, which has no route;
    `F4.8` points it at `/operations` (`4n-status.md`).
  - **Settings' tab bar.** `settingsTabsConfig.ts:38-109` lists ten tabs, Prompts (`:81-87`) and AI
    Models (`:95-101`) among them. `/settings/gpu` is routed (`App.tsx:317`) but has no tab.
    `SettingsPage` wraps every `/settings/*` page in its title, `DebugModeProvider` and
    `SecureContextWarning` (`SettingsPage.tsx:177-189`), and labels its panel by the tab
    (`:224`).
- **The header has no view control.** Among its items: the theme toggle
  (`frontend/src/components/layout/Header.tsx:318-320`), the scene-change badge (F-008, `:323-329`),
  the infrastructure-alert badge (F-009, `:332-338`), recent threats (F-010, `:341-343`), the AI
  status badge (F-011, `:345-350`), the health indicator (F-005, `:353-384`), the WebSocket status
  (F-007, `:387-394`), the REST Fallback pill (`:397-401`), the disk warning (F-012, `:404-415`) and
  the GPU pill (F-006, `:418-421`). `Layout` shows a connection banner when the sockets drop
  (`Layout.tsx:143-151`).
- **The theme is the pattern to follow, with two differences.** `ThemeContext` persists
  `theme-mode` through `useLocalStorage` (`frontend/src/contexts/ThemeContext.tsx:64`, `:122`), and
  its toggle sits in the header; but `useTheme` throws outside its provider (`:214`).
  `useLocalStorage` stores JSON (`frontend/src/hooks/useLocalStorage.ts:91`, `:153`) and catches
  storage errors (`:92`, `:159`).
- **The server keeps no per-user preference.** The `users` table has no preference column
  (`backend/models/user.py:39-62`), and with `EXPOSE_LAN` off, the default
  (`backend/core/config.py:435-436`), the frontend never loads a user
  (`frontend/src/contexts/AuthContext.tsx:153-163`). The household-wide `system_settings` store
  exists (`backend/api/routes/system_settings.py:31`).
- **The event modal has four tabs** (`frontend/src/components/events/EventDetailModal.tsx:635-679`):
  Details, AI Analysis (`:647-656`, `LLMReasoningExplorer` at `:685-692`), AI Audit (`:1183-1185`)
  and Video Clip. The header shows the risk badge, and the verdict badge only when no risk level
  exists (`:612-621`). Details holds, in order:
  - the AI summary with Re-evaluate (`:792-830`);
  - a scene caption block, the Florence-2 leftover (`:832-848`);
  - the risk breakdown (`:850-864`) and the VLM verification (`:866-874`);
  - the risk factors list (`:875-880`);
  - the confidence summary (`:882-890`) and the detected-objects list with confidence bars
    (`:892-989`);
  - the re-ID and entity panels (`:1003-1039`), notes, feedback (`:1074-1081`);
  - the metadata block (`:1083-1181`), whose Status row shows Reviewed or Pending Review
    (`:1122`, `:1128`).
- **Trends is a Grafana page by default.** `/analytics` opens on its Grafana view
  (`frontend/src/components/analytics/AnalyticsPage.tsx:43`); its native view (F-071) is the other.
- **Easy pages link to Advanced pages in three places.** The dashboard's System card opens
  `/operations` (`frontend/src/components/dashboard/StatsRow.tsx:271-279`); the palette lists
  Entities, Logs, System and AI Performance; Settings shows Prompts, AI Models and Admin. The event
  modal shows re-ID content inline and links nowhere Advanced.
- **Rulings it must fit.**
  - Ruling 182 sets the two modes and their scope.
  - Ruling 128 gives Grafana one Monitoring entry: the Monitoring package replaces eight wrapper
    pages, Logs among them (`packages/frontend.md`, "Monitoring").
  - Ruling 183 keeps the scene-change vertical.
  - Ruling 319 makes the Developer Tools admin-only and leaves their placement to this design.
  - The settled designs place an arming chip in the header on every page and a Settings › Arming
    tab (`4n-arming.md`), the Alerts screens in Easy with verdict badges on their rows
    (`4n-alerting.md`), a Verification filter and the detection list with confidence bars on the
    timeline (`4n-timeline.md`), the scene-change badge and page for the household
    (`4n-scene-changes.md`), and an admin-only Restart on Operations (`4n-status.md`).
  - The owner's spec is input, not plan text: PR #7130 at `1ea280866`,
    `docs/superpowers/2026-10-14-rtx-vss-blueprint/owner-spec.md` §2.

## What the user can do when this is done

A household member opens the app and sees five things: Dashboard, Timeline & Search, Alerts &
Rules, Household and Settings, with no GPU numbers and no AI internals. An event shows what
happened, its risk and verdict, the boxed detections and whether it was reviewed. The person who
runs the GPU flips the header switch to Advanced on their own computer, and gets the AI Workbench,
GPU & Models, Entities & Re-ID, and Operations & Monitoring, the GPU pill, and the AI Analysis and
AI Audit tabs on each event. Each browser remembers its own mode, and a link to an Advanced page
still opens in Easy, with a banner offering to switch.

## Decisions

| question                                | decision                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | why                                                                                                                                          |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------- |
| Where is the mode kept?                 | Per browser, in `localStorage` (`ui-mode`, stored as JSON like every `useLocalStorage` key). A browser with no value, or an unknown one, shows Easy (owner).                                                                                                                                                                                                                                                                                                                                                                                     | The owner's desktop stays Advanced while the household's phones stay Easy; no sign-in exists by default.                                     |
| How is Easy's sidebar shaped?           | Ruling 182's five items, each a hub whose tab bar holds today's pages at today's URLs; Advanced shows those five, a divider labelled "AI Blueprint", then its four hubs (owner). The page map is below.                                                                                                                                                                                                                                                                                                                                          | Five items, as ruled, with no page rebuilt and no link broken.                                                                               |
| What does an Advanced URL do in Easy?   | The page opens with its hub's tab bar, under a banner: "This is an Advanced page", Switch to Advanced and Back to Home. No sidebar item is highlighted (owner).                                                                                                                                                                                                                                                                                                                                                                                  | Bookmarks and links never break; the mode is a view, not a lock.                                                                             |
| What does the header show?              | Both modes: search, the docs link, the theme toggle, the scene-change badge (F-008), the infrastructure-alert badge (F-009), recent threats (F-010), the AI status badge (F-011), the health indicator (F-005), the disk warning (F-012), the arming chip (`F4.5`) and the switch. Advanced adds the GPU pill (F-006), the WebSocket status (F-007) and REST Fallback (owner). `Layout`'s connection banner shows in both.                                                                                                                       | The health indicator and the banner already say a connection is lost in plain words; the placed badges are the household's (`4n-status.md`). |
| Where do scene changes live?            | Easy: a tab of Alerts & Rules (owner).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | A blocked or moved camera is a security event; its alert and badge are the household's.                                                      |
| What does the event modal show in Easy? | The Details and Video Clip tabs. Details shows the summary, the risk factors list, the detected-objects list with its confidence bars, notes, feedback, the household actions, and the Status row; the header shows the risk badge and, always, the verdict badge. Advanced adds the AI Analysis and AI Audit tabs, and in Details Re-evaluate, the scene caption, the risk breakdown, the verification's scene, criteria and frames, the confidence summary, the re-ID and entity panels and the rest of the metadata (owner; review MO1, MO2). | Plain for the household, with every result its own actions and filters rely on; the depth one switch away.                                   |
| What does F4.9 do to F-063?             | Hides the existing AI Analysis tab in Easy and nothing more. F-063's own design session renames it "AI X-Ray" and rebuilds its content on the live VLM columns, as its own package (review MO3).                                                                                                                                                                                                                                                                                                                                                 | One design per feature (UR-79); F-063 waits on this one (ruling 317).                                                                        |
| Is the mode access control?             | No. Every page stays reachable by URL in either mode, and the server's checks are unchanged: the login with `EXPOSE_LAN=true`, and the admin session for Restart and the debug routes (ruling 319).                                                                                                                                                                                                                                                                                                                                              | A view preference that pretended to protect would mislead.                                                                                   |
| Who may switch?                         | Anyone at that browser; no sign-in.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | It changes only what that browser shows.                                                                                                     |
| Where do the admin tools sit?           | The Admin settings tab (`/settings/admin`: logging, flush queues, feature toggles, raw settings, seed and clear) and the Developer Tools on Operations both sit in Operations & Monitoring, in Advanced (owner; review MO5). Who may use them is ruling 319's.                                                                                                                                                                                                                                                                                   | They are the install's machinery, not the household's settings.                                                                              |
| What does Trends open on?               | In Easy, its native view; the Grafana view shows only in Advanced (review MO6).                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | Grafana is Monitoring's (ruling 128), and sits behind its own login with LAN exposure on (UR-33).                                            |
| What stays the same in both modes?      | The dashboard (its AI row is placed for the household, `4n-status.md`; widgets are each user's choice), the first-visit tour (its steps point at the Timeline & Search and Settings hubs, both Easy), and the `g` shortcuts, which open their page in either mode.                                                                                                                                                                                                                                                                               | Nothing the household relies on moves.                                                                                                       |
| Who builds it?                          | heavy-a, which has been free since `B4.7` merged (owner).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | Frontend has eight packages queued.                                                                                                          |

### The page map

Each sidebar item is a hub; its tabs are today's pages, at today's URLs (owner).

| mode     | hub                         | tabs                                                                                                                                                                                                                                                                                                                             |
| -------- | --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Easy     | **Dashboard**               | Overview `/` · Trends `/analytics`                                                                                                                                                                                                                                                                                               |
| Easy     | **Timeline & Search**       | Timeline `/timeline` · Trash `/trash`                                                                                                                                                                                                                                                                                            |
| Easy     | **Alerts & Rules**          | Alerts `/alerts` · Scene changes `/scene-changes` · Rules `/settings/rules`                                                                                                                                                                                                                                                      |
| Easy     | **Household**               | Members `/household` · People & faces `/face-recognition` · Vehicles & plates `/plate-reads` · Zones `/zones`                                                                                                                                                                                                                    |
| Easy     | **Settings**                | Cameras · Processing · Notifications · Ambient · Access · Storage · Arming (`F4.5`), all `/settings/<tab>`, and Data `/data` · Webhooks `/webhooks` · Audit log `/audit`; `/notifications` until `F4.2` redirects it; `/settings` itself belongs here                                                                            |
| Advanced | **AI Workbench**            | AI Audit `/ai-audit` · Prompts `/settings/prompts`                                                                                                                                                                                                                                                                               |
| Advanced | **GPU & Models**            | AI Performance `/ai` · AI Models `/settings/ai-models` · GPU `/settings/gpu`                                                                                                                                                                                                                                                     |
| Advanced | **Entities & Re-ID**        | Entities `/entities` · Re-ID `/reid` · Heatmaps `/heatmaps` · Object tracks `/tracks`                                                                                                                                                                                                                                            |
| Advanced | **Operations & Monitoring** | Operations `/operations` · Admin `/settings/admin` · Jobs `/jobs` · Performance `/performance`, and the eight pages the Monitoring package folds into one Monitoring tab (ruling 128): Logs `/logs`, `/ai-services`, `/video-analytics`, `/pyroscope`, `/operations-dashboard`, `/gpu-metrics`, `/request-profiling`, `/tracing` |

Rules, Prompts, AI Models and Admin leave Settings' tab bar but keep their URLs. Every routed page
belongs to exactly one hub, so the sidebar always knows which item to highlight. `/login`, `/setup`,
the `/events/:eventId` redirect and the not-found page belong to none. Until `F4.2` lands, the
Settings hub's two notification pages read "Notifications" (`/settings/notifications`) and
"Notification history" (`/notifications`).

## Approaches weighed

| approach                                       | for                                                                                      | against                                                               |
| ---------------------------------------------- | ---------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| **A. One registry of hubs and modes** (chosen) | Sidebar, phone bar, palette, chords, help modal, tab bar, tour and banner read one list. | The six existing lists and their tests change in one package.         |
| B. Separate Easy and Advanced layouts          | Each mode's shell is simple to read.                                                     | Two shells to keep in step; a shared link lands in the wrong one.     |
| C. Mode checks in each component               | Smallest first change.                                                                   | The lists drift, as the palette, sidebar and help modal already have. |
| Storage: per signed-in user                    | Follows a person across devices.                                                         | No user exists with LAN exposure off, the default.                    |
| Storage: household-wide (`system_settings`)    | One place to set it.                                                                     | Flipping the desktop to Advanced flips every phone.                   |

## Shape

- **The module behind the seam:** `frontend/src/config/surfaces.ts`, the registry, and
  `frontend/src/contexts/ViewModeContext.tsx`. Domain terms, added to `docs/reference/glossary.md`:
  **view mode** (Easy or Advanced: what one browser shows; distinct from the arming mode, the debug
  mode and the degradation mode) and **hub** (a sidebar entry and the tab bar over the pages it
  holds).
- **Its interface:**
  - `type ViewMode = 'easy' | 'advanced'`.
  - `interface Hub { id; label; icon; mode: ViewMode; tabs: HubTab[]; dataTour?; badge? }`, where
    `badge` names the count a hub item shows (Alerts & Rules carries `F4.1`'s open count).
  - `interface HubTab { path; label; testId; keywords?; shortcut?; exact? }`: `keywords` feed the
    palette's search, `shortcut` the `g` chord, and `exact` marks a path that matches only itself.
  - `HUBS: readonly Hub[]`, Easy's five first, in the page map's order.
  - `hubForPath(pathname): Hub | undefined`. `/` and `/settings` match only themselves; any other
    tab path matches itself and the paths below it by segment (`startsWith(path + '/')`), and the
    longest match wins, so `/settings/rules` is Alerts & Rules while `/settings/cameras` is
    Settings. An unrouted path still renders not-found and highlights nothing.
  - `modeOfPath(pathname): ViewMode | undefined`.
  - `useViewMode(): { mode: ViewMode; setMode(mode: ViewMode): void }`, persisted as `ui-mode`.
    Outside its provider it returns Easy and a no-op setter, so components render in tests without
    a provider.
- **Its invariants:** every routed page maps to exactly one hub; a hub's tabs share its mode; Easy
  has five hubs and Advanced four; a missing or unknown stored value reads as Easy.
- **Its adapters:**
  - The sidebar, the phone bar's More sheet, the command palette, `CHORD_ROUTES`, the help
    modal's navigation group, `HubTabBar` and `AdvancedBanner` read the registry. The sidebar
    renders `dataTour` on the Timeline & Search and Settings items (`timeline-link`,
    `settings-link`).
  - The header, the event modal and the Trends page read the mode through `<AdvancedOnly>`.
  - `ModeSwitch` sets it from the header (desktop and tablet), the sidebar drawer and the More sheet
    (phones).

## What changes

Frontend only: no backend change, no API change, no contract.

- **New:** `config/surfaces.ts`, `contexts/ViewModeContext.tsx`, and the components `ModeSwitch`,
  `AdvancedOnly`, `HubTabBar` and `AdvancedBanner`.
- **Edited:**
  - `App.tsx` mounts `ViewModeProvider` beside `ThemeProvider`.
  - `Layout.tsx` renders `HubTabBar`, and `AdvancedBanner` on an Advanced page in Easy.
  - `Sidebar.tsx` lists the current mode's hubs flat. `sidebarNav.ts` and its expansion key go; the
    collapsed state stays.
  - `MobileBottomNav.tsx` keeps Dashboard, Timeline, Alerts and More; More lists the remaining hubs
    under the switch.
  - `CommandPalette.tsx` lists the current mode's hubs and tabs, with their keywords, and adds
    "Switch to Advanced" or "Switch to Easy". `useKeyboardShortcuts.ts` and
    `ShortcutsHelpModal.tsx` derive the chords from the registry; the help modal marks the ones that
    open Advanced pages.
  - `Header.tsx` adds the switch and wraps F-006, F-007 and REST Fallback in `<AdvancedOnly>`.
  - `SettingsPage.tsx` keeps its outlet and providers; its heading comes from `hubForPath`, its tab
    bar gives way to `HubTabBar`, and its panel is labelled by `HubTabBar`'s tab.
    `settingsTabsConfig.ts` goes.
  - `EventDetailModal.tsx` wraps the AI Analysis and AI Audit tabs and the Advanced parts of
    Details in `<AdvancedOnly>`, and shows the verdict badge in the header in both modes.
  - `AnalyticsPage.tsx` opens on its native view in Easy and offers the Grafana view only in
    Advanced.
  - `test-utils/renderWithProviders.tsx` (`:188`) takes a `mode` option.
- **Docs (UR-81):** `docs/reference/glossary.md` (view mode, hub);
  `docs/reference/feature-inventory.md` (F-299, and the re-cites under "Done when");
  `frontend/src/components/settings/AGENTS.md`, `docs/components/layout/layout.md`,
  `docs/ui/settings.md`, `docs/ui/keyboard-shortcuts.md` and `docs/getting-started/tour.md`, each
  where it names the old groups, tabs or targets.
- **Beside other packages.** Whichever of each pair merges second carries the change:
  - `F4.1` puts the open count on the Alerts nav item and rewrites the modal's snooze and its spec
    (`4n-alerting.md`): the count becomes the Alerts & Rules hub's `badge`, and the snooze stays an
    Easy action.
  - `F4.2` removes `/notifications` and its nav item: its registry row goes.
  - `F4.3` adds Delete to the modal (`4n-trash.md`): an Easy action.
  - `F4.5` adds the arming chip (both modes) and the Settings › Arming tab: a registry row in the
    Settings hub instead of a `settingsTabsConfig.ts` entry.
  - `F4.6` keeps the scene-change badge (both modes) and the page (Alerts & Rules).
  - `F4.8` points the palette's System entry and `g y` at `/operations`: a registry row and
    shortcut; its `palette.spec.ts` edit sets the mode it asserts.
  - `F4.10` changes the Developer Tools, Logging Settings and their specs (`4n-debug-tools.md`):
    Admin and Operations are Advanced tabs.
  - The Monitoring package (P3) replaces the eight folded tabs with one Monitoring tab and moves
    `/ai`'s dashboard half into it (ruling 128).
  - After `F4.9`, a new page or palette entry is a registry row.

## Failure handling

- **Storage unavailable** (a private window, blocked storage): `useLocalStorage` catches the error,
  so the browser shows Easy and a switch lasts until reload.
- **A page left out of the registry:** the invariant test fails in CI before it ships.
- **An Advanced page opened in Easy:** it works, under the banner; no sidebar item is highlighted.

## Tests

- **Consolidation scope.** The test-only PR consolidates, around one navigation fixture and one
  event-modal fixture, the tests of every file the build edits: `Sidebar`, `MobileBottomNav`,
  `CommandPalette`, `ShortcutsHelpModal`, `Header`, `Layout`, `SettingsPage`, `EventDetailModal`,
  `AnalyticsPage` and `ProductTour`, and the golden specs listed below.
- **Tests through the interface:**
  - The registry: each routed page in `App.tsx` maps to exactly one hub; a hub's tabs share its
    mode; Easy has five hubs and Advanced four; `hubForPath` matches `/` and `/settings` exactly,
    otherwise the longest tab path by segment.
  - `ViewModeContext`: Easy by default, persisted across a remount, an unknown stored value read as
    Easy, Easy outside a provider.
  - `<AdvancedOnly>`: renders its children only in Advanced.
- **Specs and tests that move (UR-9).** Each Advanced assertion first sets Advanced through a
  harness helper, `setMode(page, mode)`. It writes `ui-mode` as JSON (`"advanced"`), through an init
  script that writes only when the key is absent, so a reload or an in-test switch keeps the
  browser's choice. Specs that open an Advanced page by URL need no helper; the banner is not in
  their way. Easy assertions stay, beside them.
  - **Golden, navigation:** `shell/nav.spec.ts:184-247`, `:277-283`;
    `shell/palette.spec.ts:155-166`, `:182-201`, `:226-231`; `shell/tour.spec.ts:45`, `:323-375`;
    `shell/disk-warning.seeded.spec.ts:127`; `timeline/export-modal.spec.ts:1045-1050`;
    `settings-cameras/settings-shell.spec.ts:39-50`, `:72-119`; `shell/ambient.spec.ts:138`.
  - **Golden, header:** `shell/header.spec.ts:124-180` (F-006); `shell/ws-status.spec.ts:245`,
    `:259-327` (F-007 and REST Fallback).
  - **Golden, event modal:** `timeline/event-reevaluate.spec.ts:174-355`;
    `timeline/event-detail-modal.spec.ts:501-537`, `:1035-1060`, `:1118-1176`, `:1231`,
    `:1450-1644`, `:1794-1832`; `timeline/event-detail.spec.ts:196-240` (the Status row stays
    Easy).
  - **Unit:** `Sidebar.test.tsx:186-191`, `:499-515`; `MobileBottomNav.test.tsx:180-245`;
    `CommandPalette.test.tsx:53-185`; `Header.test.tsx:291-450`, `:1061-1102`, `:1311-1370`;
    `EventDetailModal.test.tsx:372-422`, `:525-706`, `:893-945`, `:2072-2312`, `:2505-2623`;
    `SettingsPage.test.tsx:16`, `:139-224`; `ProductTour.test.tsx:498-504`; `Layout.test.tsx`;
    `src/__tests__/feature-inventory.test.ts:226-229` (rows that name `sidebarNav.ts` or
    `settingsTabsConfig.ts`).
  - **E2E (CI skips them; they still move):** `tests/e2e/pages/BasePage.ts:67-73`,
    `pages/SettingsPage.ts:70-93`; `specs/responsive.spec.ts:190-197`,
    `ai-performance.spec.ts:125-133`, `ai-audit.spec.ts:179-187`, `websocket.spec.ts:87-121`,
    `event-detail.spec.ts:403-408`, `model-zoo.spec.ts:338-660`;
    `user-journeys/detection-workflow.spec.ts:58`, `investigation-workflow.spec.ts:69`, `:350`,
    `settings-navigation.spec.ts:50-54`. The nightly visual baselines
    (`visual/components.visual.spec.ts:23-30`, `settings.visual.spec.ts:92`) are re-shot.

## Golden path

- **Spec:** `frontend/tests/golden/shell/modes.spec.ts`.
  1. A fresh browser shows the five Easy items and no GPU pill.
  2. An event's modal shows Details and Video Clip, the verdict badge and the detected objects, and
     no AI Analysis tab.
  3. `/operations` opens with the Advanced banner and the Operations & Monitoring tab bar.
  4. Switching to Advanced shows nine items, the GPU pill and the AI Analysis tab.
  5. A reload keeps Advanced.
  6. Switching back returns the five items.
- **Fake-stack scenario:** the standard fake stack with one seeded event; no verdict matters.
- **Real-tier check:** the same spec under `scripts/feature-check.sh --real`; nothing in it touches
  a model.

## Privacy and security

No personal data: the browser stores only `easy` or `advanced`. The mode is not access control, and
the design says so in its decisions: every page stays reachable by URL, and the server's checks are
unchanged. The Developer Tools stay admin-only (ruling 319); Restart stays admin-only
(`4n-status.md`).

## Rollout and reversal

One build PR switches it on; every browser starts in Easy. A revert backs it out, leaving an unread
`ui-mode` key behind.

## Packages

| package | lane                     | depends on | contents                                                                                                                                                                                                | its own golden path |
| ------- | ------------------------ | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------- |
| `F4.9`  | heavy-a (owner's choice) | none       | The registry, the view mode, the switch, the hubs and tab bars, the banner, the header, event-modal and Trends gating, the phone bar, palette, chords and help modal, and every spec and doc they move. | Playwright above.   |

It runs the six steps as two PRs: a test-only consolidation PR, then the build. It is lane tier.
heavy-a follows `packages/frontend.md`'s block for it (UR-59). F-063's AI X-Ray is its own design
session and package after it.

## Review

An adversarial review (2026-10-22) and two fresh-context checks of the code and of the settled
designs found these; every cite in "Where it starts" held, and the owner ruled two (MO5, and the
debug order in `4n-debug-tools.md`):

| #    | finding                                                                                             | amendment                                                                                                                                     |
| ---- | --------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| MO1  | "Confidence" swallowed F-055's detected-objects list, which the timeline design shows the household | Only the confidence summary is Advanced; the detection list and its bars stay in Easy                                                         |
| MO2  | Easy hid the verdict (Alerts rows and the Verification filter show it) and the Reviewed status      | The header's verdict badge shows in both modes; the Status row stays in Easy; only the verification's scene, criteria and frames are Advanced |
| MO3  | The golden path asserted an "AI X-Ray" tab nothing builds                                           | F4.9 hides the existing AI Analysis tab; F-063's own design renames and rebuilds it; the spec asserts tabs that exist                         |
| MO4  | The registry lacked the tour's targets, the palette's keywords, the shortcuts and a badge           | `Hub` and `HubTab` carry them; the chords and the help modal derive from the registry                                                         |
| MO5  | `/settings/admin` holds logging, flush queues, toggles and seed tools, not household settings       | Admin moves to Operations & Monitoring (owner)                                                                                                |
| MO6  | Trends opened on a Grafana iframe                                                                   | In Easy it opens on its native view; the Grafana view is Advanced                                                                             |
| MO7  | `/settings` and Settings › Arming had no hub; "below" was not by segment                            | Settings claims `/settings` exactly; Arming is a Settings tab; tab paths match by segment                                                     |
| MO8  | The Monitoring package folds eight pages, Logs among them                                           | Logs stays a tab until the Monitoring package folds all eight                                                                                 |
| MO9  | Pages under other hubs kept SettingsPage's "Settings" heading and dangling tab labels               | The heading comes from the hub; the panel is labelled by `HubTabBar`'s tab                                                                    |
| MO10 | The helper wrote raw text, re-wrote on reload, and `useTheme`'s pattern throws outside a provider   | `setMode` writes JSON only when absent; `useViewMode` is Easy outside a provider; `renderWithProviders` takes a mode                          |
| MO11 | About 30 specs and unit ranges were missing, and the consolidation scope named only the nav tests   | The full list above; the test-only PR consolidates every edited file's tests                                                                  |
| MO12 | Overlaps with `F4.1`, `F4.2`, `F4.3`, `F4.5`, `F4.8` and `F4.10` were unstated                      | One "whichever merges second carries" line each                                                                                               |
| MO13 | A debug mode already exists, and "mode" also names the arming and degradation modes                 | "Where it starts" names it; the glossary term is **view mode**                                                                                |
| MO14 | The inventory and doc re-cites were incomplete                                                      | F-006, F-007, F-017, F-018, F-019, F-021, F-054, F-056, F-061–F-063, F-187 and F-198 re-cite; the UR-81 docs are listed                       |

## Done when

The golden path is green on the fake stack and its real-tier check is posted; F-299 reads **works**;
F-006, F-007, F-017, F-018, F-019, F-021, F-054, F-056, F-061, F-062, F-063, F-187 and F-198 cite
the registry or the moved specs, and `feature-inventory.test.ts` passes. (#7130 closes as consumed
when the plan PR carrying this design merges, ruling 321.)
