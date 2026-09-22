# Component Library Docs

Documentation for the React component library, mirrored from `frontend/src/components/`.

## Purpose

This tree documents what the components actually accept: prop tables, defaults, and usage.
It is reference material for anyone writing or changing frontend components.

## Contents

| Area                                    | What lives here                                                      |
| --------------------------------------- | -------------------------------------------------------------------- |
| `common/`                               | UI primitives (buttons, modals, loading, status, errors)             |
| `feature-specific/`                     | Dashboard, event, and settings component docs                        |
| `layout/`                               | App shell: Layout, Header, Sidebar, mobile nav                       |
| `patterns/`                             | Cross-cutting form, data-display, error-handling guides              |
| `README.md`                             | Index of every page in this tree                                     |
| `common/buttons.md`                     | Button, IconButton                                                   |
| `common/modals.md`                      | AnimatedModal, ResponsiveModal, BottomSheet                          |
| `common/loading-states.md`              | LoadingSpinner, RouteLoadingFallback, Skeleton, InfiniteScrollStatus |
| `common/notifications.md`               | ConnectionStatusBanner (toast system: `ToastProvider` / `useToast`)  |
| `common/status-indicators.md`           | ServiceStatusIndicator, WebSocketStatus, OfflineIndicator, badges    |
| `common/error-boundaries.md`            | The five error boundaries                                            |
| `feature-specific/dashboard-widgets.md` | DashboardPage and its widgets                                        |
| `feature-specific/event-components.md`  | Event browsing, detail, enrichment, feedback components              |
| `feature-specific/settings-panels.md`   | Settings page panels (cameras, GPU, storage, prompts)                |
| `layout/layout.md`                      | Shell components and responsive behavior                             |
| `patterns/form-patterns.md`             | react-hook-form + zod forms, FormField, SubmitButton                 |
| `patterns/data-display-patterns.md`     | Cards, tables, lists, charts, empty/loading states                   |
| `patterns/error-handling.md`            | Error hierarchy, API error handling, recovery                        |

## Rules for writing here

- Ground-truth source is `frontend/src/components/`. Every prop name, type, and default in a table must exist in the component's `Props` interface at the time of writing.
- Keep tables in sync when a component's props change — update the doc page in the same PR.
- One section (`##`) per component, with a `**Location:**` line pointing at the `.tsx` file.

## Related

- [README.md](./README.md) — index
- `frontend/AGENTS.md` — frontend architecture and navigation
