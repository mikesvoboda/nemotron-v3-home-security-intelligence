/**
 * Barrel export for React contexts.
 *
 * This module exports all context providers and hooks used throughout
 * the application for centralized state management.
 */

// Toast notifications live in `hooks/useToast.ts` (the live hook, sonner-backed)
// and `components/common/ToastProvider.tsx` (the mounted provider). The
// `contexts/ToastContext.tsx` re-implementation was dead and F3.2 removed it.

// The `SystemDataContext` family — `SystemDataContext`, `CameraContext`,
// `HealthContext` and `MetricsContext`, with the providers and hooks that
// compose them — had no production consumer at `2fb1c95d8`: `App.tsx` mounts
// only `ThemeProvider`, `ToastProvider`, `AnnouncementProvider` and
// `AuthProvider` from this barrel, nothing else imports any of the four, and
// every hook they export is knip-unused. F3.2 removed them under the package's
// "dead contexts and stores" clause.

// Announcement context for screen reader announcements
export { AnnouncementContext, AnnouncementProvider, useAnnounce } from './AnnouncementContext';

export type { AnnouncementContextType, AnnouncementProviderProps } from './AnnouncementContext';

// Theme context for light/dark mode (NEM-3609)
export {
  ThemeContext,
  ThemeProvider,
  useTheme,
  useThemeOptional,
  THEME_STORAGE_KEY,
} from './ThemeContext';

export type {
  ThemeContextValue,
  ThemeMode,
  ResolvedTheme,
  ThemeProviderProps,
} from './ThemeContext';

// Auth context for authentication state (NEM-5322)
export { AuthProvider, useAuth } from './AuthContext';

export type {
  AuthContextType,
  AuthProviderProps,
  User,
  LoginRequest,
  RegisterRequest,
} from './AuthContext';
