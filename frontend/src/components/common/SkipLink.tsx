/**
 * Skip to Content Link Component
 *
 * Provides a keyboard-accessible link that allows users to bypass
 * navigation and jump directly to the main content area.
 *
 * - Visually hidden by default using sr-only
 * - Becomes visible when focused for keyboard users
 * - High contrast styling for visibility when focused
 *
 * @example
 * ```tsx
 * // In Layout component - must be first focusable element
 * <SkipLink />
 * <Header />
 * <main id="main-content" tabIndex={-1}>
 *   {children}
 * </main>
 * ```
 */

export interface SkipLinkProps {
  /** Target element ID (default: "main-content") */
  targetId?: string;
  /** Link text (default: "Skip to main content") */
  children?: string;
}

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

export default SkipLink;
