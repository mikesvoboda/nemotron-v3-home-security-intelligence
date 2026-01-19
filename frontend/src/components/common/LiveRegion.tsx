/**
 * LiveRegion - ARIA live region component for screen reader announcements.
 *
 * This component provides a visually hidden live region that announces
 * dynamic content changes to screen reader users. It supports both
 * "polite" (waits for idle) and "assertive" (interrupts immediately)
 * politeness levels.
 *
 * The component is visually hidden using the sr-only utility class
 * but remains accessible to assistive technologies.
 *
 * @example
 * // Basic usage with polite announcement
 * <LiveRegion message="3 new items loaded" />
 *
 * @example
 * // Assertive announcement for urgent messages
 * <LiveRegion message="Error: Connection lost" politeness="assertive" />
 */

/**
 * Politeness level for ARIA live regions.
 * - "polite": Waits for idle before announcing (default, non-intrusive)
 * - "assertive": Interrupts current speech immediately (urgent messages)
 */
export type Politeness = 'polite' | 'assertive';

/**
 * Props for the LiveRegion component.
 */
export interface LiveRegionProps {
  /**
   * The message to announce to screen readers.
   * Empty string will render an empty region.
   */
  message: string;

  /**
   * The politeness level for the announcement.
   * - "polite" (default): Waits for idle before announcing
   * - "assertive": Interrupts current speech immediately
   */
  politeness?: Politeness;
}

/**
 * A visually hidden ARIA live region for screen reader announcements.
 *
 * This component renders a div with appropriate ARIA attributes
 * that screen readers will announce when the content changes.
 * The region is visually hidden but remains accessible.
 */
export function LiveRegion({ message, politeness = 'polite' }: LiveRegionProps) {
  return (
    <div role="status" aria-live={politeness} aria-atomic="true" className="sr-only">
      {message}
    </div>
  );
}
