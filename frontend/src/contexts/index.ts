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
