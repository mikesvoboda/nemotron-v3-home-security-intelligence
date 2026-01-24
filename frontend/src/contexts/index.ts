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

// System data context for shared polling
export {
  SystemDataContext,
  SystemDataProvider,
  useSystemData,
  useSystemDataOptional,
  DEFAULT_HEALTH,
  DEFAULT_GPU_STATS,
} from './SystemDataContext';

export type { SystemData, SystemDataProviderProps } from './SystemDataContext';

// Announcement context for screen reader announcements
export { AnnouncementContext, AnnouncementProvider, useAnnounce } from './AnnouncementContext';

export type { AnnouncementContextType, AnnouncementProviderProps } from './AnnouncementContext';
