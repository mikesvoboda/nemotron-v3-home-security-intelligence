# 4n — Easy and Advanced Modes Design

> Step 1 of the Easy and Advanced modes package (`packages/frontend.md`, "F4.\* Feature track,
> frontend parts"), copied from [`templates/feature-design.md`](templates/feature-design.md).

**Package:** `F4.9` · **Inventory rows:** F-299 (new: Header › Easy/Advanced mode switch); F-017,
F-019 (the navigation it reshapes); F-006, F-007, F-061, F-062, F-063 (surfaces it shows only in
Advanced) · **R2 ruling:** none of its own; ruling 182 (UR-182) rules the switch and each mode's
scope, and F-063 (complete, P2) waits on this design (ruling 317) · **Designed:** 2026-10-22, with
the owner

## Where it starts

Facts read at `main` `9481f00cc`.

- **No mode exists.** A case-insensitive search for easy, beginner, expert, simple mode, advanced
  mode and similar finds nothing in `frontend/src` or `backend/`. "Advanced" appears only as the
  advanced-filter panels (`frontend/src/components/search/SearchBar.tsx:88`).
- **Navigation is three hand-kept lists.**
  - **The sidebar.** `navGroups` (`frontend/src/components/layout/sidebarNav.ts:58-147`) holds four
    groups (Monitoring, Analytics, Operations, Admin) and 33 items. `NavItem` has no visibility
    field (`:39-47`), and `Sidebar` renders every group (`Sidebar.tsx:338-347`).
  - **The phone bar.** Dashboard, Timeline and Alerts (`MobileBottomNav.tsx:32-36`), plus a More
    sheet listing every other item (`:146-199`).
  - **The command palette.** Ten entries
    (`frontend/src/components/common/CommandPalette.tsx:48-119`). Its chords live in
    `frontend/src/hooks/useKeyboardShortcuts.ts:19-29`, and the help modal keeps a third copy
    (`ShortcutsHelpModal.tsx:45-57`). `g y` opens `/system`, which has no route;
    `F4.8` points it at `/operations` (`4n-status.md`).
- **Settings has its own tab bar.** `settingsTabsConfig.ts:38-109` lists ten tabs, Prompts
  (`:81-87`) and AI Models (`:95-101`) among them; `/settings/gpu` has no tab
  (`SettingsPage.tsx:174`).
- **The header has no mode control.** It renders the theme toggle
  (`frontend/src/components/layout/Header.tsx:318-320`), the WebSocket status (F-007, `:387-394`),
  the REST Fallback pill (`:397-401`) and the GPU pill (F-006, `:418-421`), among others.
- **The theme is the pattern to follow.** `ThemeContext` persists `theme-mode` through
  `useLocalStorage` (`frontend/src/contexts/ThemeContext.tsx:64`, `:122`), and its toggle sits in
  the header. `useLocalStorage` catches storage errors (`frontend/src/hooks/useLocalStorage.ts:92`,
  `:159`).
- **The server keeps no per-user preference.** The `users` table has no preference column
  (`backend/models/user.py:39-62`), and with `EXPOSE_LAN` off, the default
  (`backend/core/config.py:435-436`), the frontend never loads a user
  (`frontend/src/contexts/AuthContext.tsx:153-163`). The household-wide `system_settings` store
  exists (`backend/api/routes/system_settings.py:31`).
- **The event modal has four tabs** (`frontend/src/components/events/EventDetailModal.tsx:635-679`):
  Details, AI Analysis (`LLMReasoningExplorer`, `:685-692`), AI Audit (`:1183-1185`) and Video
  Clip. Details carries the AI summary with Re-evaluate (`:792-830`), the risk breakdown
  (`:850-864`), the VLM verification (`:866-874`), confidence (`:882-989`), the re-ID and entity
  panels (`:1003-1039`), feedback (`:1074-1081`) and the metadata (`:1083`).
- **Easy pages link to Advanced pages in three places.** The dashboard's System card opens
  `/operations` (`frontend/src/components/dashboard/StatsRow.tsx:271-279`); the palette lists
  Entities, Logs, System and AI Performance; Settings shows Prompts and AI Models. The event modal
  shows re-ID content inline and links nowhere Advanced.
- **Tests pin today's navigation.** Golden: `shell/nav.spec.ts` (the Analytics group, `:203-210`;
  Entities on a phone, `:277-283`), `shell/palette.spec.ts` (the ordered ten, `:155-166`),
  `shell/header.spec.ts` (F-006, `:124-180`), `settings-cameras/settings-shell.spec.ts` (the tabs,
  `:39-50`), `timeline/event-reevaluate.spec.ts` (`:279-334`) and
  `timeline/event-detail-modal.spec.ts` (`:1800`). Unit: `Sidebar.test.tsx` (33 links, `:186-191`;
  the groups, `:499-515`), `MobileBottomNav.test.tsx:208` and `CommandPalette.test.tsx:53-180`.
- **Rulings it must fit.**
  - Ruling 182 sets the two modes and their scope.
  - Ruling 128 gives Grafana one Monitoring entry.
  - Ruling 183 keeps the scene-change vertical.
  - Ruling 319 makes the Developer Tools admin-only and leaves their placement to this design.
  - The settled designs place an arming chip in the header on every page (`4n-arming.md`), the
    Alerts screens in Easy (`4n-alerting.md`), the scene-change badge and page for the household
    (`4n-scene-changes.md`), and an admin-only Restart on Operations (`4n-status.md`).
  - The owner's spec is input, not plan text: PR #7130 at `1ea280866`,
    `docs/superpowers/2026-10-14-rtx-vss-blueprint/owner-spec.md` §2.

## What the user can do when this is done

A household member opens the app and sees five things: Dashboard, Timeline & Search, Alerts &
Rules, Household and Settings, with no GPU numbers and no AI internals. The person who runs the GPU
flips the header switch to Advanced on their own computer, and gets the AI Workbench, GPU & Models,
Entities & Re-ID, and Operations & Monitoring, the GPU pill, and the AI X-Ray tab on each event.
Each browser remembers its own mode, and a link to an Advanced page still opens in Easy, with a
banner offering to switch.

## Decisions

| question                                | decision                                                                                                                                                                                                                                                                                          | why                                                                                                                   |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Where is the mode kept?                 | Per browser, in `localStorage` (`ui-mode`), like the theme. A browser with no value starts in Easy (owner).                                                                                                                                                                                       | The owner's desktop stays Advanced while the household's phones stay Easy; no sign-in exists by default.              |
| How is Easy's sidebar shaped?           | Ruling 182's five items, each a hub whose tab bar holds today's pages at today's URLs; Advanced adds four hubs the same way (owner). The page map is below.                                                                                                                                       | Five items, as ruled, with no page rebuilt and no link broken.                                                        |
| What does an Advanced URL do in Easy?   | The page opens, with a banner: "This is an Advanced page", Switch to Advanced and Back to Home (owner).                                                                                                                                                                                           | Bookmarks and links never break; the mode is a view, not a lock.                                                      |
| Which header items are Advanced?        | The GPU pill (F-006), the WebSocket status (F-007) and REST Fallback. Both modes keep the badges, the health indicator, the disk warning, the arming chip and the switch (owner).                                                                                                                 | The health indicator already says "Degraded" or "Offline" in plain words.                                             |
| Where do scene changes live?            | Easy: a tab of Alerts & Rules (owner).                                                                                                                                                                                                                                                            | A blocked or moved camera is a security event; its alert and badge are the household's.                               |
| What does the event modal show in Easy? | Details and Video Clip: the summary, risk level, who, where and when, the boxed detections, the household actions, notes and feedback. Advanced adds the AI X-Ray and AI Audit tabs, and in Details the verification, confidence, risk breakdown, re-ID panels, metadata and Re-evaluate (owner). | Plain for the household; the depth one switch away. Re-evaluate re-runs the pipeline rather than acting on the event. |
| Is the mode access control?             | No. Every page stays reachable by URL in either mode, and the server's checks are unchanged: the login with `EXPOSE_LAN=true`, and the admin session for Restart and the debug routes (ruling 319).                                                                                               | A view preference that pretended to protect would mislead.                                                            |
| Who may switch?                         | Anyone at that browser; no sign-in.                                                                                                                                                                                                                                                               | It changes only what that browser shows.                                                                              |
| Where do the Developer Tools sit?       | On Operations, in the Operations & Monitoring hub (Advanced), admin-only per ruling 319.                                                                                                                                                                                                          | Ruling 319 left their placement here; they are AI-blueprint depth.                                                    |
| What stays the same in both modes?      | The dashboard (its AI row is placed for the household, `4n-status.md`; widgets are each user's choice), the first-visit tour (its steps point at Timeline and Settings, both Easy), and the `g` shortcuts, which open their page in either mode.                                                  | Nothing the household relies on moves.                                                                                |
| Who builds it?                          | heavy-a, after `B4.7` merges (owner).                                                                                                                                                                                                                                                             | heavy-a's queue is empty then; frontend has seven packages queued.                                                    |

### The page map

Each sidebar item is a hub; its tabs are today's pages, at today's URLs (owner).

| mode     | hub                         | tabs                                                                                                                                                                                                                                                                                                                   |
| -------- | --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Easy     | **Dashboard**               | Overview `/` · Trends `/analytics`                                                                                                                                                                                                                                                                                     |
| Easy     | **Timeline & Search**       | Timeline `/timeline` · Trash `/trash`                                                                                                                                                                                                                                                                                  |
| Easy     | **Alerts & Rules**          | Alerts `/alerts` · Scene changes `/scene-changes` · Rules `/settings/rules`                                                                                                                                                                                                                                            |
| Easy     | **Household**               | Members `/household` · People & faces `/face-recognition` · Vehicles & plates `/plate-reads` · Zones `/zones`                                                                                                                                                                                                          |
| Easy     | **Settings**                | Cameras · Processing · Notifications · Ambient · Access · Storage · Admin (`/settings/*`), and Data `/data` · Webhooks `/webhooks` · Audit log `/audit`; `/notifications` until `F4.2` redirects it                                                                                                                    |
| Advanced | **AI Workbench**            | AI Audit `/ai-audit` · Prompts `/settings/prompts`                                                                                                                                                                                                                                                                     |
| Advanced | **GPU & Models**            | AI Performance `/ai` · AI Models `/settings/ai-models` · GPU `/settings/gpu`                                                                                                                                                                                                                                           |
| Advanced | **Entities & Re-ID**        | Entities `/entities` · Re-ID `/reid` · Heatmaps `/heatmaps` · Object tracks `/tracks`                                                                                                                                                                                                                                  |
| Advanced | **Operations & Monitoring** | Operations `/operations` · Jobs `/jobs` · Performance `/performance` · Logs `/logs`, and the seven Grafana pages (`/ai-services`, `/video-analytics`, `/pyroscope`, `/operations-dashboard`, `/gpu-metrics`, `/request-profiling`, `/tracing`) until the Monitoring package makes them one Monitoring tab (ruling 128) |

Rules, Prompts and AI Models leave Settings' tab bar but keep their URLs. Every routed page belongs
to exactly one hub, so the sidebar always knows which item to highlight. `/login`, `/setup`, the
`/events/:eventId` redirect and the not-found page belong to none.

## Approaches weighed

| approach                                       | for                                                            | against                                                               |
| ---------------------------------------------- | -------------------------------------------------------------- | --------------------------------------------------------------------- |
| **A. One registry of hubs and modes** (chosen) | Sidebar, phone bar, palette, tab bar and banner read one list. | The three existing nav lists and their tests change in one package.   |
| B. Separate Easy and Advanced layouts          | Each mode's shell is simple to read.                           | Two shells to keep in step; a shared link lands in the wrong one.     |
| C. Mode checks in each component               | Smallest first change.                                         | The lists drift, as the palette, sidebar and help modal already have. |
| Storage: per signed-in user                    | Follows a person across devices.                               | No user exists with LAN exposure off, the default.                    |
| Storage: household-wide (`system_settings`)    | One place to set it.                                           | Flipping the desktop to Advanced flips every phone.                   |

## Shape

- **The module behind the seam:** `frontend/src/config/surfaces.ts`, the registry, and
  `frontend/src/contexts/ModeContext.tsx`. Domain terms, added to `docs/reference/glossary.md`:
  **mode** (Easy or Advanced: what one browser shows) and **hub** (a sidebar entry and the tab bar
  over the pages it holds).
- **Its interface:**
  - `type Mode = 'easy' | 'advanced'`.
  - `interface Hub { id; label; icon; mode: Mode; tabs: HubTab[] }` and
    `interface HubTab { path; label; testId }`.
  - `HUBS: readonly Hub[]`, Easy's five first, in the page map's order.
  - `hubForPath(pathname): Hub | undefined`. `/` matches only itself; any other tab path matches
    itself and the paths below it, and the longest match wins, so `/settings/rules` is Alerts &
    Rules while `/settings/cameras` is Settings.
  - `modeOfPath(pathname): Mode | undefined`.
  - `useMode(): { mode: Mode; setMode(mode: Mode): void }`, persisted as `ui-mode`.
- **Its invariants:** every routed page maps to exactly one hub; a hub's tabs share its mode; Easy
  has five hubs and Advanced four; a missing or unknown stored value reads as Easy.
- **Its adapters:** the sidebar, the phone bar's More sheet, the command palette, `HubTabBar` and
  `AdvancedBanner` read the registry; the header and the event modal read the mode through
  `<AdvancedOnly>`; `ModeSwitch` sets it from the header (desktop and tablet), the sidebar drawer
  and the More sheet (phones).

## What changes

Frontend only: no backend change, no API change, no contract.

- **New:** `config/surfaces.ts`, `contexts/ModeContext.tsx`, and the components `ModeSwitch`,
  `AdvancedOnly`, `HubTabBar` and `AdvancedBanner`.
- **Edited:**
  - `App.tsx` mounts `ModeProvider` beside `ThemeProvider`.
  - `Layout.tsx` renders `HubTabBar`, and `AdvancedBanner` on an Advanced page in Easy.
  - `Sidebar.tsx` lists the current mode's hubs flat; in Advanced a divider labelled "AI Blueprint"
    precedes the four. `sidebarNav.ts` and its expansion key go; the collapsed state stays.
  - `MobileBottomNav.tsx` keeps Dashboard, Timeline, Alerts and More; More lists the remaining
    hubs under the switch.
  - `CommandPalette.tsx` lists the current mode's hubs and tabs and adds "Switch to Advanced" or
    "Switch to Easy". `ShortcutsHelpModal.tsx` marks the chords that open Advanced pages.
  - `Header.tsx` adds the switch and wraps F-006, F-007 and REST Fallback in `<AdvancedOnly>`.
  - `SettingsPage.tsx` keeps its outlet; its tab bar gives way to `HubTabBar`, and
    `settingsTabsConfig.ts` goes.
  - `EventDetailModal.tsx` wraps the AI Analysis and AI Audit tabs and the Advanced parts of
    Details in `<AdvancedOnly>`.
- **Docs:** `docs/reference/glossary.md` (mode, hub); `docs/reference/feature-inventory.md` gains
  F-299 and re-cites F-017 and F-019 to the registry.
- **Beside other packages:**
  - `F4.1` puts the open count on the Alerts nav item (`4n-alerting.md`); the Alerts & Rules hub
    item carries it.
  - `F4.5` adds the arming chip and `F4.6` the scene-change badge; both stay in both modes.
  - `F4.8` points the palette's System entry and `g y` at `/operations`.
  - Whichever of these merges second adapts to the other. After `F4.9`, a new page or palette
    entry is a registry row.
  - The Monitoring package (P3) replaces the seven Grafana tabs with one Monitoring tab (ruling
    128).

## Failure handling

- **Storage unavailable** (a private window, blocked storage): `useLocalStorage` catches the error,
  so the browser shows Easy and a switch lasts until reload.
- **A page left out of the registry:** the invariant test fails in CI before it ships.
- **An Advanced page opened in Easy:** it works, under the banner; no sidebar item is highlighted.

## Tests

- **Consolidation scope:** the shell's navigation tests, unit (`Sidebar`, `MobileBottomNav`,
  `CommandPalette`) and golden (`shell/nav`, `shell/palette`, `shell/header`), consolidate around
  one navigation fixture before the build.
- **Tests through the interface:**
  - The registry: each routed page in `App.tsx` maps to exactly one hub; a hub's tabs share its
    mode; Easy has five hubs and Advanced four; `hubForPath` matches `/` exactly and otherwise the
    longest tab path.
  - `ModeContext`: Easy by default, persisted across a remount, an unknown stored value read as
    Easy.
  - `<AdvancedOnly>`: renders its children only in Advanced.
  - The edited specs listed in "Where it starts" move with the change (UR-9). Specs that open an
    Advanced surface first set Advanced through a harness helper, `setMode(page, mode)`, which
    writes `ui-mode` before the page loads.

## Golden path

- **Spec:** `frontend/tests/golden/shell/modes.spec.ts`.
  1. A fresh browser shows the five Easy items and no GPU pill.
  2. An event's modal shows Details and Video Clip, and no AI X-Ray tab.
  3. `/operations` opens with the Advanced banner.
  4. Switching to Advanced shows nine items, the GPU pill and the AI X-Ray tab.
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

| package | lane            | depends on | contents                                                                                                                                                       | its own golden path |
| ------- | --------------- | ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------- |
| `F4.9`  | heavy-a (owner) | none       | The registry, the mode, the switch, the hubs and tab bars, the banner, the header and event-modal gating, the phone bar and palette, and every spec they move. | Playwright above.   |

It runs the six steps as two PRs: a test-only consolidation PR, then the build. It is lane tier.
heavy-a starts once `B4.7` (#7361) merges.

## Done when

The golden path is green on the fake stack and its real-tier check is posted; F-299 reads
**works**; F-017 and F-019 cite the registry; and #7130 is closed as consumed, pointing here.
