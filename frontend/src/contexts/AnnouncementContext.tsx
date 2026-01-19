/* eslint-disable react-refresh/only-export-components */
/**
 * AnnouncementContext - Global ARIA live region announcements for React.
 *
 * Provides a context and hook for making screen reader announcements
 * of dynamic content changes. Uses a single global LiveRegion component
 * to avoid creating multiple live regions throughout the application.
 *
 * @example
 * // Wrap your app with the provider
 * <AnnouncementProvider>
 *   <App />
 * </AnnouncementProvider>
 *
 * @example
 * // Use the hook in components
 * const { announce } = useAnnounce();
 * announce('3 new items loaded', 'polite');
 * announce('Error: Connection lost', 'assertive');
 */
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react';

import { LiveRegion, type Politeness } from '../components/common/LiveRegion';

/**
 * Context value interface for announcement management.
 */
export interface AnnouncementContextType {
  /**
   * Announce a message to screen readers via the live region.
   *
   * @param message - The message to announce
   * @param politeness - The politeness level ('polite' | 'assertive')
   *                     Defaults to 'polite'
   */
  announce: (message: string, politeness?: Politeness) => void;
}

/**
 * Internal state for the announcement.
 */
interface AnnouncementState {
  /** The message to announce */
  message: string;
  /** The politeness level for the announcement */
  politeness: Politeness;
}

/**
 * Delay in milliseconds to clear message before setting new one.
 * This is necessary to ensure screen readers re-announce the same message.
 */
const CLEAR_DELAY_MS = 100;

/**
 * The Announcement context - null when accessed outside of provider.
 */
export const AnnouncementContext = createContext<AnnouncementContextType | null>(null);

/**
 * Props for the AnnouncementProvider component.
 */
export interface AnnouncementProviderProps {
  /** Child components that can access the announcement context */
  children: ReactNode;
}

/**
 * AnnouncementProvider component - wraps the application to provide
 * global screen reader announcement functionality.
 *
 * Manages the announcement state and provides the announce method.
 * Renders a single LiveRegion component that all announcements flow through.
 *
 * The provider clears the message briefly before setting a new one to ensure
 * screen readers will announce repeated messages.
 *
 * @example
 * <AnnouncementProvider>
 *   <App />
 * </AnnouncementProvider>
 */
export function AnnouncementProvider({ children }: AnnouncementProviderProps) {
  const [announcement, setAnnouncement] = useState<AnnouncementState>({
    message: '',
    politeness: 'polite',
  });

  // Use ref to track pending timeouts for cleanup
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  /**
   * Announce a message to screen readers.
   *
   * Clears the current message first, then sets the new message after a
   * brief delay. This ensures screen readers will re-announce even if
   * the same message is sent multiple times.
   */
  const announce = useCallback((message: string, politeness: Politeness = 'polite') => {
    // Clear any pending timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    // Clear the message first to trigger re-announcement
    setAnnouncement({ message: '', politeness });

    // Set the new message after a brief delay
    timeoutRef.current = setTimeout(() => {
      setAnnouncement({ message, politeness });
    }, CLEAR_DELAY_MS);
  }, []);

  /**
   * Memoized context value to prevent unnecessary re-renders.
   */
  const contextValue = useMemo<AnnouncementContextType>(
    () => ({
      announce,
    }),
    [announce]
  );

  return (
    <AnnouncementContext.Provider value={contextValue}>
      {children}
      <LiveRegion message={announcement.message} politeness={announcement.politeness} />
    </AnnouncementContext.Provider>
  );
}

/**
 * Hook to access the announcement context.
 *
 * Must be used within an AnnouncementProvider. Throws an error if used outside.
 *
 * @returns The announcement context with the announce method
 * @throws Error if used outside of AnnouncementProvider
 *
 * @example
 * function MyComponent() {
 *   const { announce } = useAnnounce();
 *
 *   const handleDataLoad = () => {
 *     const itemCount = 5;
 *     announce(`${itemCount} new items loaded`);
 *   };
 *
 *   return <button onClick={handleDataLoad}>Load Data</button>;
 * }
 */
export function useAnnounce(): AnnouncementContextType {
  const context = useContext(AnnouncementContext);
  if (!context) {
    throw new Error('useAnnounce must be used within an AnnouncementProvider');
  }
  return context;
}
