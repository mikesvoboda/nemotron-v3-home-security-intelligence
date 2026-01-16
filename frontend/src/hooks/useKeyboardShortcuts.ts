/**
 * useKeyboardShortcuts - Global keyboard navigation shortcuts
 *
 * Provides keyboard shortcuts for navigating the application:
 * - Single-key shortcuts: ? for help
 * - Chord shortcuts: g + d for dashboard, g + t for timeline, etc.
 * - Modifier shortcuts: Cmd/Ctrl + K for command palette
 *
 * Automatically ignores shortcuts when typing in input fields.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

/** Chord timeout in milliseconds */
const CHORD_TIMEOUT = 1000;

/** Map of chord second keys to routes */
const CHORD_ROUTES: Record<string, string> = {
  d: '/', // Dashboard
  t: '/timeline', // Timeline
  a: '/analytics', // Analytics
  l: '/alerts', // Alerts
  e: '/entities', // Entities
  o: '/logs', // Logs (o for lOgs since l is taken)
  s: '/system', // System monitoring
  ',': '/settings', // Settings (Vim-style)
};

/**
 * Options for the useKeyboardShortcuts hook
 */
export interface UseKeyboardShortcutsOptions {
  /** Callback when ? is pressed to open help modal */
  onOpenHelp?: () => void;
  /** Callback when Cmd/Ctrl + K is pressed to open command palette */
  onOpenCommandPalette?: () => void;
  /** Callback when Escape is pressed */
  onEscape?: () => void;
  /** Whether shortcuts are enabled (default: true) */
  enabled?: boolean;
}

/**
 * Return type for the useKeyboardShortcuts hook
 */
export interface UseKeyboardShortcutsReturn {
  /** Whether a chord is pending (g has been pressed) */
  isPendingChord: boolean;
}

/**
 * Check if the event target is an editable element
 */
function isEditableElement(target: EventTarget | null): boolean {
  if (!target || !(target instanceof HTMLElement)) {
    return false;
  }

  const tagName = target.tagName.toLowerCase();
  if (tagName === 'input' || tagName === 'textarea') {
    return true;
  }

  if (target.contentEditable === 'true') {
    return true;
  }

  return false;
}

/**
 * Hook providing global keyboard navigation shortcuts
 *
 * @param options - Configuration options
 * @returns Object containing pending chord state
 */
export function useKeyboardShortcuts(
  options: UseKeyboardShortcutsOptions = {}
): UseKeyboardShortcutsReturn {
  const { onOpenHelp, onOpenCommandPalette, onEscape, enabled = true } = options;
  const navigate = useNavigate();

  // Use both state (for re-renders) and ref (for stable handler access)
  const [isPendingChord, setIsPendingChord] = useState(false);
  const isPendingChordRef = useRef(false);
  const chordTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Keep refs in sync with state
  useEffect(() => {
    isPendingChordRef.current = isPendingChord;
  }, [isPendingChord]);

  const clearChordTimeout = useCallback(() => {
    if (chordTimeoutRef.current) {
      clearTimeout(chordTimeoutRef.current);
      chordTimeoutRef.current = null;
    }
  }, []);

  const resetChord = useCallback(() => {
    isPendingChordRef.current = false;
    setIsPendingChord(false);
    clearChordTimeout();
  }, [clearChordTimeout]);

  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (!enabled) {
        return;
      }

      // Ignore when typing in input fields
      if (isEditableElement(event.target)) {
        return;
      }

      const { key, metaKey, ctrlKey } = event;

      // Command palette: Cmd+K (Mac) or Ctrl+K (Windows/Linux)
      if (key === 'k' && (metaKey || ctrlKey)) {
        event.preventDefault();
        onOpenCommandPalette?.();
        return;
      }

      // Escape key
      if (key === 'Escape') {
        onEscape?.();
        resetChord();
        return;
      }

      // Help modal: ?
      if (key === '?') {
        event.preventDefault();
        onOpenHelp?.();
        return;
      }

      // Chord handling - use ref for consistent state access
      if (isPendingChordRef.current) {
        // Complete the chord
        const route = CHORD_ROUTES[key];
        if (route) {
          event.preventDefault();
          void navigate(route);
        }
        resetChord();
        return;
      }

      // Start a new chord with 'g'
      if (key === 'g') {
        isPendingChordRef.current = true;
        setIsPendingChord(true);
        clearChordTimeout();
        chordTimeoutRef.current = setTimeout(() => {
          isPendingChordRef.current = false;
          setIsPendingChord(false);
        }, CHORD_TIMEOUT);
        return;
      }
    },
    [enabled, navigate, onOpenCommandPalette, onEscape, onOpenHelp, resetChord, clearChordTimeout]
  );

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      clearChordTimeout();
    };
  }, [handleKeyDown, clearChordTimeout]);

  return {
    isPendingChord,
  };
}

export default useKeyboardShortcuts;
