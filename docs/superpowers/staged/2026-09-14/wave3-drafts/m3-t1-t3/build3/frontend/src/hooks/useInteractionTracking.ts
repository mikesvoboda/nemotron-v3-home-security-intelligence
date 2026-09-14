/**
 * useInteractionTracking - React hook for tracking user interactions.
 *
 * Provides memoized callbacks for tracking clicks, changes, and form submissions
 * with consistent component naming and minimal overhead.
 *
 * @example
 * ```tsx
 * function MyComponent() {
 *   const { trackClick, trackChange, trackSubmit } = useInteractionTracking('MyComponent');
 *
 *   return (
 *     <button onClick={() => trackClick('save_button')}>
 *       Save
 *     </button>
 *   );
 * }
 * ```
 *
 * IMPORTANT: Never log sensitive data (passwords, personal info, tokens).
 * Only log structural interaction data for debugging and analytics.
 */
import { useCallback } from 'react';

import { logger } from '../services/logger';

/**
 * Hook return type for interaction tracking
 */
export interface InteractionTracking {
  /** Track click events on buttons, links, etc. */
  trackClick: (elementName: string, extra?: Record<string, unknown>) => void;
  /** Track change events on inputs, selects, etc. */
  trackChange: (fieldName: string, extra?: Record<string, unknown>) => void;
  /** Track form submission events */
  trackSubmit: (success: boolean, extra?: Record<string, unknown>) => void;
  /** Track modal/dialog open events */
  trackOpen: (modalName: string, extra?: Record<string, unknown>) => void;
  /** Track modal/dialog close events */
  trackClose: (modalName: string, extra?: Record<string, unknown>) => void;
  /** Track toggle events (switches, checkboxes) */
  trackToggle: (elementName: string, enabled: boolean, extra?: Record<string, unknown>) => void;
}

/**
 * React hook for tracking user interactions within a component.
 *
 * @param componentName - The name of the component for namespacing events
 * @returns Object with tracking methods
 */
export function useInteractionTracking(componentName: string): InteractionTracking {
  const trackClick = useCallback(
    (elementName: string, extra?: Record<string, unknown>) => {
      logger.interaction('click', `${componentName}.${elementName}`, extra);
    },
    [componentName]
  );

  const trackChange = useCallback(
    (fieldName: string, extra?: Record<string, unknown>) => {
      logger.interaction('change', `${componentName}.${fieldName}`, extra);
    },
    [componentName]
  );

  const trackSubmit = useCallback(
    (success: boolean, extra?: Record<string, unknown>) => {
      logger.formSubmit(componentName, success, extra);
    },
    [componentName]
  );

  const trackOpen = useCallback(
    (modalName: string, extra?: Record<string, unknown>) => {
      logger.interaction('open', `${componentName}.${modalName}`, extra);
    },
    [componentName]
  );

  const trackClose = useCallback(
    (modalName: string, extra?: Record<string, unknown>) => {
      logger.interaction('close', `${componentName}.${modalName}`, extra);
    },
    [componentName]
  );

  const trackToggle = useCallback(
    (elementName: string, enabled: boolean, extra?: Record<string, unknown>) => {
      logger.interaction('toggle', `${componentName}.${elementName}`, {
        enabled,
        ...extra,
      });
    },
    [componentName]
  );

  return {
    trackClick,
    trackChange,
    trackSubmit,
    trackOpen,
    trackClose,
    trackToggle,
  };
}
