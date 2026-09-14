/**
 * Skip to Content Link Components
 *
 * Provides keyboard-accessible links that allow users to bypass
 * navigation and jump directly to specific content areas.
 *
 * Two components are available:
 * - SkipLink: Single skip link (backward compatible)
 * - SkipLinkGroup: Multiple skip links for different targets
 *
 * @example
 * ```tsx
 * // Single skip link (original usage)
 * <SkipLink />
 *
 * // Multiple skip links
 * <SkipLinkGroup
 *   targets={[
 *     { id: 'main-navigation', label: 'Skip to navigation' },
 *     { id: 'sidebar-filters', label: 'Skip to filters' },
 *     { id: 'main-content', label: 'Skip to main content' },
 *   ]}
 * />
 * ```
 */

/**
 * Target configuration for skip links
 */
export interface SkipTarget {
  /** Target element ID (without #) */
  id: string;
  /** Label text for the skip link */
  label: string;
}

/**
 * Props for single SkipLink component
 */
export interface SkipLinkProps {
  /** Target element ID (default: "main-content") */
  targetId?: string;
  /** Link text (default: "Skip to main content") */
  children?: string;
}

/**
 * Props for SkipLinkGroup component
 */
export interface SkipLinkGroupProps {
  /** Array of skip targets */
  targets: SkipTarget[];
}

/**
 * Common styling for skip links
 */
const skipLinkBaseClass =
  'rounded-lg bg-[#76B900] px-4 py-2 font-medium text-black outline-none ring-2 ring-[#76B900] ring-offset-2 ring-offset-[#0E0E0E] focus:bg-[#76B900] focus:text-black';

/**
 * Single skip link component - visually hidden by default,
 * becomes visible when focused for keyboard users.
 */
export function SkipLink({
  targetId = 'main-content',
  children = 'Skip to main content',
}: SkipLinkProps) {
  return (
    <a
      href={`#${targetId}`}
      className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-[#76B900] focus:px-4 focus:py-2 focus:font-medium focus:text-black focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#0E0E0E]"
      data-testid="skip-link"
    >
      {children}
    </a>
  );
}

/**
 * Multiple skip links group component - visually hidden by default,
 * becomes visible when any link is focused. Allows keyboard users
 * to jump to different sections of the page.
 */
export function SkipLinkGroup({ targets }: SkipLinkGroupProps) {
  if (targets.length === 0) {
    return null;
  }

  return (
    <div
      className="sr-only focus-within:not-sr-only focus-within:fixed focus-within:left-4 focus-within:top-4 focus-within:z-50 focus-within:flex focus-within:flex-col focus-within:gap-2"
      data-testid="skip-link-group"
    >
      {targets.map((target) => (
        <a
          key={target.id}
          href={`#${target.id}`}
          className={skipLinkBaseClass}
          data-testid={`skip-link-${target.id}`}
        >
          {target.label}
        </a>
      ))}
    </div>
  );
}

export default SkipLink;
