# Frontend Contexts Directory

## Purpose

React Context providers for global state management across the application. Currently contains toast notification context for centralized user feedback.

## Directory Contents

```
frontend/src/contexts/
├── AGENTS.md                     # This documentation file
├── index.ts                      # Central export point
├── AnnouncementContext.tsx       # Live region announcements provider
├── AnnouncementContext.test.tsx  # Tests for announcement context
├── AuthContext.tsx               # Authentication state
├── AuthContext.test.tsx          # Tests for auth context
├── DebugModeContext.tsx          # Debug mode state provider
├── DebugModeContext.test.tsx     # Tests for debug mode context
├── ThemeContext.tsx              # Light/dark mode
└── ThemeContext.test.tsx         # Tests for theme context
```

## Key Files

| File                           | Purpose                                          |
| ------------------------------ | ------------------------------------------------ |
| `index.ts`                     | Re-exports all contexts for clean imports        |
| `AnnouncementContext.tsx`      | ARIA live region announcements for accessibility |
| `AnnouncementContext.test.tsx` | Tests for announcement context                   |
| `DebugModeContext.tsx`         | Debug mode state provider with localStorage      |
| `DebugModeContext.test.tsx`    | Tests for debug mode context                     |

## What lives here

The contexts the app actually mounts: `AnnouncementContext`, `AuthContext`,
`DebugModeContext` and `ThemeContext`, re-exported by `index.ts`. `App.tsx`
mounts `ThemeProvider`, `AnnouncementProvider` and `AuthProvider` from that
barrel.

Two families were removed by F3.2 (2026-10-18) because nothing mounted them:
`ToastContext` (the live pair today is `hooks/useToast.ts`, sonner-backed, and
`components/common/ToastProvider.tsx`) and the `SystemDataContext` family
(`SystemDataContext`, `CameraContext`, `HealthContext`, `MetricsContext`),
whose only importer was `index.ts` itself. Before adding a context back, grep
for a production consumer of its hook — a barrel export is not a consumer, and
that is what let these four survive reachability checks.

## Related Files

- `../App.tsx` - Provider setup
- `../hooks/useToast.ts` and `../components/common/ToastProvider.tsx` - the live toast pair

## Notes for AI Agents

- A provider is only live if something mounts it; check `App.tsx` and the
  route tree, not the barrel.
- `useToast()` (from `hooks/useToast.ts`) is the toast API.
