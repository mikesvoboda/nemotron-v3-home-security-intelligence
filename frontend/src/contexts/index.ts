/**
 * Barrel export for React contexts.
 *
 * This module exports all context providers and hooks used throughout
 * the application for centralized state management.
 */

// Toast notifications context
export {
  ToastContext,
  ToastProvider,
  useToast,
  DEFAULT_TOAST_DURATION,
  MAX_TOASTS,
} from './ToastContext';

export type {
  Toast,
  ToastType,
  ToastContextType,
  ToastProviderContextType,
  ToastProviderProps,
} from './ToastContext';

// System data context for shared polling (composed from specialized contexts)
export {
  SystemDataContext,
  SystemDataProvider,
  useSystemData,
  useSystemDataOptional,
  DEFAULT_HEALTH,
  DEFAULT_GPU_STATS,
} from './SystemDataContext';

export type { SystemData, SystemDataProviderProps } from './SystemDataContext';

// Camera context for camera state
export {
  CameraContext,
  CameraProvider,
  useCameraContext,
  useCameraContextOptional,
} from './CameraContext';

export type { CameraContextData, CameraProviderProps } from './CameraContext';

// Health context for system health
export {
  HealthContext,
  HealthProvider,
  useHealthContext,
  useHealthContextOptional,
  DEFAULT_HEALTH as HEALTH_DEFAULT,
} from './HealthContext';

export type { HealthContextData, HealthProviderProps } from './HealthContext';

// Metrics context for GPU and performance metrics
export {
  MetricsContext,
  MetricsProvider,
  useMetricsContext,
  useMetricsContextOptional,
  DEFAULT_GPU_STATS as METRICS_DEFAULT_GPU_STATS,
} from './MetricsContext';

export type { MetricsContextData, MetricsProviderProps } from './MetricsContext';

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
