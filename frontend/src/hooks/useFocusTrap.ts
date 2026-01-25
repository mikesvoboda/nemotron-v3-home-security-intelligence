/**
 * useFocusTrap - Reusable focus trap hook for modals and dialogs
 *
 * Traps focus within a container element, cycling through focusable elements
 * with Tab and Shift+Tab. Optionally returns focus to the trigger element
 * when deactivated.
 *
 * @example
 * ```tsx
 * function Modal({ isOpen, onClose }: ModalProps) {
 *   const { containerRef } = useFocusTrap({
 *     isActive: isOpen,
 *     onEscape: onClose,
 *     returnFocusOnDeactivate: true,
 *   });
 *
 *   return (
 *     <div ref={containerRef} role="dialog" aria-modal="true">
 *       <button>First</button>
 *       <button onClick={onClose}>Close</button>
 *     </div>
 *   );
 * }
 * ```
 */

import { useCallback, useEffect, useRef, RefObject } from 'react';

/**
 * Selector for focusable elements within the trap
 */
const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

/**
 * Options for the useFocusTrap hook
 */
export interface UseFocusTrapOptions {
  /** Whether the focus trap is currently active */
  isActive: boolean;
  /** Optional ref to the element that should receive initial focus */
  initialFocusRef?: RefObject<HTMLElement | null>;
  /** Whether to return focus to the previously focused element when deactivated (default: true) */
  returnFocusOnDeactivate?: boolean;
  /** Callback when Escape key is pressed */
  onEscape?: () => void;
}

/**
 * Return type for the useFocusTrap hook
 */
export interface UseFocusTrapReturn<T extends HTMLElement = HTMLElement> {
  /** Ref to attach to the container element that should trap focus */
  containerRef: RefObject<T | null>;
}

/**
 * Check if an element is visible (not hidden via CSS)
 * This works in both browser and jsdom environments
 */
function isElementVisible(el: HTMLElement): boolean {
  // Check for display:none or visibility:hidden via computed style
  // In jsdom, getComputedStyle returns default values, so this is more reliable
  if (el.hidden) return false;

  // Check offsetParent (null for display:none, but also null in jsdom)
  // Only rely on this in browser environments
  if (typeof window !== 'undefined' && el.offsetParent === null) {
    // In jsdom, offsetParent is always null, so we need a fallback
    // Check if we're in jsdom by looking at offsetWidth/offsetHeight
    // which are 0 in jsdom but also 0 for hidden elements
    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden') {
      return false;
    }
    // If offsetParent is null but display is not none, we might be in jsdom
    // or the element could be in a fixed/absolute container - consider it visible
  }

  return true;
}

/**
 * Get all focusable elements within a container
 */
function getFocusableElements(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
    isElementVisible
  );
}

/**
 * Hook for trapping focus within a container element
 *
 * @param options - Configuration options
 * @returns Object containing the container ref
 */
export function useFocusTrap<T extends HTMLElement = HTMLElement>(
  options: UseFocusTrapOptions
): UseFocusTrapReturn<T> {
  const { isActive, initialFocusRef, returnFocusOnDeactivate = true, onEscape } = options;

  const containerRef = useRef<T | null>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);

  // Store onEscape in a ref to avoid stale closures
  const onEscapeRef = useRef(onEscape);
  useEffect(() => {
    onEscapeRef.current = onEscape;
  }, [onEscape]);

  // Handle focus when activating
  useEffect(() => {
    if (!isActive) {
      return;
    }

    // Store the currently focused element before trapping focus
    previouslyFocusedRef.current = document.activeElement as HTMLElement;

    // Use requestAnimationFrame to ensure the DOM is fully rendered
    // This is necessary because the ref might not be attached yet when isActive becomes true
    const rafId = requestAnimationFrame(() => {
      const container = containerRef.current;
      if (!container) {
        return;
      }

      // Focus the initial element or the first focusable element
      const focusTarget = initialFocusRef?.current;
      if (focusTarget && container.contains(focusTarget)) {
        focusTarget.focus();
      } else {
        const focusableElements = getFocusableElements(container);
        if (focusableElements.length > 0) {
          focusableElements[0].focus();
        }
      }
    });

    return () => {
      cancelAnimationFrame(rafId);
    };
  }, [isActive, initialFocusRef]);

  // Handle returning focus when deactivating
  useEffect(() => {
    if (isActive) {
      return;
    }

    // Return focus to previously focused element
    if (returnFocusOnDeactivate && previouslyFocusedRef.current) {
      previouslyFocusedRef.current.focus();
      previouslyFocusedRef.current = null;
    }
  }, [isActive, returnFocusOnDeactivate]);

  // Keyboard event handler for Tab trapping and Escape
  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (!isActive) {
        return;
      }

      const container = containerRef.current;
      if (!container) {
        return;
      }

      // Handle Escape key
      if (event.key === 'Escape') {
        onEscapeRef.current?.();
        return;
      }

      // Handle Tab key
      if (event.key !== 'Tab') {
        return;
      }

      const focusableElements = getFocusableElements(container);
      if (focusableElements.length === 0) {
        event.preventDefault();
        return;
      }

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];

      // Shift+Tab from first element -> wrap to last
      if (event.shiftKey && document.activeElement === firstElement) {
        event.preventDefault();
        lastElement.focus();
        return;
      }

      // Tab from last element -> wrap to first
      if (!event.shiftKey && document.activeElement === lastElement) {
        event.preventDefault();
        firstElement.focus();
        return;
      }

      // If focus is outside the container, bring it back
      if (!container.contains(document.activeElement)) {
        event.preventDefault();
        if (event.shiftKey) {
          lastElement.focus();
        } else {
          firstElement.focus();
        }
      }
    },
    [isActive]
  );

  // Add/remove keyboard event listener
  useEffect(() => {
    if (!isActive) {
      return;
    }

    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isActive, handleKeyDown]);

  return {
    containerRef,
  };
}

export default useFocusTrap;
