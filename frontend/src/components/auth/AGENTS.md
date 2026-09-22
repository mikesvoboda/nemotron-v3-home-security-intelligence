# Auth Components

## Purpose

First-time setup and route-protection UI for the single-user auth model. `SetupPage` is the registration screen shown until the first admin account exists; `ProtectedRoute` is the wrapper that gates the app shell.

## Key Files

| File                      | Purpose                                                             |
| ------------------------- | ------------------------------------------------------------------- |
| `index.ts`                | Barrel: exports `ProtectedRoute`, `SetupPage`                       |
| `SetupPage.tsx`           | First-admin registration form (name/email/password)                 |
| `ProtectedRoute.tsx`      | Auth gate: redirects to `/setup` or `/login`, else renders children |
| `SetupPage.test.tsx`      | Validation, redirect, accessibility                                 |
| `ProtectedRoute.test.tsx` | Redirect branches for setup/unauthenticated/authorized              |

## Related Files

| File                                    | Purpose                                                                |
| --------------------------------------- | ---------------------------------------------------------------------- |
| `frontend/src/contexts/AuthContext.tsx` | `useAuth()` — `setupRequired`, `isAuthenticated`, `login`, `register`  |
| `frontend/src/services/authApi.ts`      | `/api/auth/*` client                                                   |
| `frontend/src/App.tsx`                  | Wires `SetupPage` to `/setup` and wraps app routes in `ProtectedRoute` |

## Patterns

- **Setup gate:** `ProtectedRoute` sends the user to `/setup` when `setupRequired === true`, and also when the setup-status check errored (`setupRequired === null && error`) — the setup page handles that case gracefully rather than deadlocking.
- **No login screen here:** `/login` is not part of this directory; the normal post-registration flow is "API endpoints open" (see root `AGENTS.md` auth model).
- **Return path:** `ProtectedRoute` stashes the intended route in `location.state` so login can bounce back.
