/**
 * ToastProvider - Component for providing toast notification functionality
 *
 * Wraps the application with sonner's Toaster component, pre-configured
 * for the NVIDIA dark theme styling. This component should be placed
 * near the root of the application tree.
 *
 * @example
 * ```tsx
 * // In App.tsx
 * import { ToastProvider } from './components/common';
 *
 * function App() {
 *   return (
 *     <ToastProvider>
 *       <Router>
 *         <Layout>
 *           {children}
 *         </Layout>
 *       </Router>
 *     </ToastProvider>
 *   );
 * }
 * ```
 */

import { type ReactNode, type JSX } from 'react';
import { Toaster } from 'sonner';

// Import toast styles
import '../../styles/toast.css';

/**
 * Position options for the toast container
 */
export type ToastPosition =
  | 'top-left'
  | 'top-center'
  | 'top-right'
  | 'bottom-left'
  | 'bottom-center'
  | 'bottom-right';

/**
 * Theme options for toasts
 */
export type ToastTheme = 'light' | 'dark' | 'system';

/**
 * Props for the ToastProvider component
 */
export interface ToastProviderProps {
  /** Child components to wrap */
  children?: ReactNode;
  /** Position of the toast container (default: 'bottom-right') */
  position?: ToastPosition;
  /** Color theme (default: 'dark') */
  theme?: ToastTheme;
  /** Whether to use rich colors for different toast types (default: true) */
  richColors?: boolean;
  /** Whether to show a close button on toasts (default: true) */
  closeButton?: boolean;
  /** Additional CSS class name */
  className?: string;
  /** Offset from the edges of the viewport */
  offset?: string | number;
  /** Gap between toasts */
  gap?: number;
  /** Maximum number of toasts visible at once */
  visibleToasts?: number;
  /** Whether to expand toasts on hover */
  expand?: boolean;
  /** Duration in ms before toasts auto-dismiss (default: 4000) */
  duration?: number;
}

/**
 * ToastProvider component that sets up the toast notification system.
 *
 * This component renders sonner's Toaster with NVIDIA-themed defaults
 * and includes children passthrough for use as a wrapper component.
 *
 * Features:
 * - Pre-configured dark theme matching NVIDIA brand
 * - NVIDIA green (#76B900) accent colors
 * - Responsive positioning
 * - Accessible by default (uses ARIA live regions)
 * - Supports all toast variants (success, error, warning, info, loading)
 *
 * @param props - Component props
 * @returns ToastProvider component
 */
function ToastProvider({
  children,
  position = 'bottom-right',
  theme = 'dark',
  richColors = true,
  closeButton = true,
  className,
  offset,
  gap = 12,
  visibleToasts = 4,
  expand = true,
  duration = 4000,
}: ToastProviderProps): JSX.Element {
  // Combine default nvidia-toast class with any custom className
  const toasterClassName = className ? `nvidia-toast ${className}` : 'nvidia-toast';

  return (
    <>
      {children}
      <Toaster
        theme={theme}
        position={position}
        richColors={richColors}
        closeButton={closeButton}
        className={toasterClassName}
        offset={offset}
        gap={gap}
        visibleToasts={visibleToasts}
        expand={expand}
        duration={duration}
        toastOptions={{
          // Default options applied to all toasts
          classNames: {
            toast: 'nvidia-toast-item',
            title: 'nvidia-toast-title',
            description: 'nvidia-toast-description',
            actionButton: 'nvidia-toast-action',
            cancelButton: 'nvidia-toast-cancel',
            closeButton: 'nvidia-toast-close',
          },
        }}
      />
    </>
  );
}

ToastProvider.displayName = 'ToastProvider';

export { ToastProvider };
export default ToastProvider;
