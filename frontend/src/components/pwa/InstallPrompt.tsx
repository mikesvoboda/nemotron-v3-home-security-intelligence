/**
 * InstallPrompt - PWA install prompt banner component.
 *
 * Captures the beforeinstallprompt event and displays a custom install banner
 * after user engagement criteria are met (visits and/or time on site).
 *
 * Features:
 * - Captures and stores beforeinstallprompt event for later use
 * - Shows banner after configurable engagement thresholds
 * - Tracks visits and time on site in localStorage
 * - Dismissal persists with configurable cooldown period
 * - Tracks installation success
 * - WCAG 2.1 AA compliant
 *
 * @example
 * ```tsx
 * // Basic usage - shows after 2 visits and 30 seconds
 * <InstallPrompt />
 *
 * // Custom thresholds
 * <InstallPrompt minVisits={3} minTimeOnSite={60000} />
 *
 * // Immediate show (for testing)
 * <InstallPrompt minVisits={0} minTimeOnSite={0} />
 * ```
 */

import { clsx } from 'clsx';
import { Smartphone, X } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

import Button from '../common/Button';

// ============================================================================
// Types
// ============================================================================

/**
 * BeforeInstallPromptEvent type definition.
 * This event is not in the standard TypeScript DOM types.
 */
export interface BeforeInstallPromptEvent extends Event {
  /** Shows the native install prompt to the user */
  prompt(): Promise<void>;
  /** Promise that resolves when user makes a choice */
  userChoice: Promise<{
    outcome: 'accepted' | 'dismissed';
    platform: string;
  }>;
}

/**
 * Props for the InstallPrompt component
 */
export interface InstallPromptProps {
  /**
   * Minimum number of visits before showing the prompt.
   * @default 2
   */
  minVisits?: number;
  /**
   * Minimum time on site (in milliseconds) before showing the prompt.
   * @default 30000 (30 seconds)
   */
  minTimeOnSite?: number;
  /**
   * Number of days to wait after dismissal before showing again.
   * @default 7
   */
  dismissCooldownDays?: number;
  /**
   * Additional CSS classes to apply to the banner.
   */
  className?: string;
}

// ============================================================================
// Constants
// ============================================================================

/** localStorage key for visit count */
const VISIT_COUNT_KEY = 'pwa-visit-count';

/** localStorage key for dismissal timestamp */
const DISMISSED_KEY = 'pwa-install-dismissed';

/** localStorage key for installed state */
const INSTALLED_KEY = 'pwa-installed';

/** Default minimum visits before showing prompt */
const DEFAULT_MIN_VISITS = 2;

/** Default minimum time on site (30 seconds) */
const DEFAULT_MIN_TIME_ON_SITE = 30000;

/** Default dismissal cooldown (7 days) */
const DEFAULT_DISMISS_COOLDOWN_DAYS = 7;

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get the current visit count from localStorage
 */
function getVisitCount(): number {
  const stored = localStorage.getItem(VISIT_COUNT_KEY);
  return stored ? parseInt(stored, 10) : 0;
}

/**
 * Increment and store the visit count
 */
function incrementVisitCount(): number {
  const current = getVisitCount();
  const newCount = current + 1;
  localStorage.setItem(VISIT_COUNT_KEY, newCount.toString());
  return newCount;
}

/**
 * Check if the PWA is already installed
 */
function isAlreadyInstalled(): boolean {
  return localStorage.getItem(INSTALLED_KEY) === 'true';
}

/**
 * Check if the prompt was recently dismissed
 */
function isRecentlyDismissed(cooldownDays: number): boolean {
  const dismissedAt = localStorage.getItem(DISMISSED_KEY);
  if (!dismissedAt) return false;

  const dismissedTimestamp = parseInt(dismissedAt, 10);
  const cooldownMs = cooldownDays * 24 * 60 * 60 * 1000;
  return Date.now() - dismissedTimestamp < cooldownMs;
}

/**
 * Mark the prompt as dismissed
 */
function markDismissed(): void {
  localStorage.setItem(DISMISSED_KEY, Date.now().toString());
}

/**
 * Mark the app as installed
 */
function markInstalled(): void {
  localStorage.setItem(INSTALLED_KEY, 'true');
}

// ============================================================================
// Component
// ============================================================================

/**
 * PWA install prompt banner component.
 *
 * Displays a custom install banner when the beforeinstallprompt event fires
 * and engagement criteria are met.
 */
export default function InstallPrompt({
  minVisits = DEFAULT_MIN_VISITS,
  minTimeOnSite = DEFAULT_MIN_TIME_ON_SITE,
  dismissCooldownDays = DEFAULT_DISMISS_COOLDOWN_DAYS,
  className,
}: InstallPromptProps): React.ReactElement | null {
  // State
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [showBanner, setShowBanner] = useState(false);

  // Refs
  const visitCountRef = useRef(0);
  const startTimeRef = useRef(Date.now());
  const timeCheckIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  /**
   * Check if all engagement criteria are met
   */
  const checkEngagementCriteria = useCallback((): boolean => {
    // Check if already installed or recently dismissed
    if (isAlreadyInstalled() || isRecentlyDismissed(dismissCooldownDays)) {
      return false;
    }

    // Check visit count
    const visitsMet = visitCountRef.current >= minVisits;

    // Check time on site
    const timeOnSite = Date.now() - startTimeRef.current;
    const timeMet = timeOnSite >= minTimeOnSite;

    return visitsMet && timeMet;
  }, [minVisits, minTimeOnSite, dismissCooldownDays]);

  /**
   * Handle the beforeinstallprompt event
   */
  const handleBeforeInstallPrompt = useCallback(
    (e: Event): void => {
      // Prevent the default browser prompt
      e.preventDefault();

      // Store the event for later use
      setDeferredPrompt(e as BeforeInstallPromptEvent);

      // Check if we should show the banner immediately
      if (checkEngagementCriteria()) {
        setShowBanner(true);
      }
    },
    [checkEngagementCriteria]
  );

  /**
   * Handle install button click
   */
  const handleInstall = useCallback((): void => {
    if (!deferredPrompt) return;

    // Show the native install prompt and wait for user choice
    void (async () => {
      await deferredPrompt.prompt();

      // Wait for user choice
      const { outcome } = await deferredPrompt.userChoice;

      // Track installation
      if (outcome === 'accepted') {
        markInstalled();
      }

      // Clean up
      setDeferredPrompt(null);
      setShowBanner(false);
    })();
  }, [deferredPrompt]);

  /**
   * Handle dismiss button click
   */
  const handleDismiss = useCallback((): void => {
    markDismissed();
    setShowBanner(false);
  }, []);

  // Increment visit count on mount
  useEffect(() => {
    visitCountRef.current = incrementVisitCount();
  }, []);

  // Set up beforeinstallprompt event listener
  useEffect(() => {
    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);

    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    };
  }, [handleBeforeInstallPrompt]);

  // Set up time-based checking
  useEffect(() => {
    // Only set up timer if we have a deferred prompt and time threshold is non-zero
    if (!deferredPrompt || minTimeOnSite === 0) return;

    // Check periodically if time threshold is met
    timeCheckIntervalRef.current = setInterval(() => {
      if (checkEngagementCriteria() && !showBanner) {
        setShowBanner(true);
        // Clear interval once we show the banner
        if (timeCheckIntervalRef.current) {
          clearInterval(timeCheckIntervalRef.current);
        }
      }
    }, 1000);

    return () => {
      if (timeCheckIntervalRef.current) {
        clearInterval(timeCheckIntervalRef.current);
      }
    };
  }, [deferredPrompt, minTimeOnSite, checkEngagementCriteria, showBanner]);

  // Don't render if we shouldn't show the banner
  if (!showBanner || !deferredPrompt) {
    return null;
  }

  return (
    <div
      data-testid="install-prompt"
      role="dialog"
      aria-labelledby="install-prompt-title"
      aria-describedby="install-prompt-description"
      className={clsx(
        'fixed bottom-4 left-4 right-4 z-50',
        'md:left-auto md:right-4 md:w-96',
        'rounded-lg border border-gray-700 bg-gray-800 p-4 shadow-lg',
        className
      )}
    >
      <div className="flex gap-3">
        <div
          data-testid="install-prompt-icon"
          aria-hidden="true"
          className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-gray-700"
        >
          <Smartphone className="h-5 w-5 text-[#76B900]" />
        </div>
        <div className="flex-1">
          <h3 id="install-prompt-title" className="font-semibold text-white">
            Install Security Dashboard
          </h3>
          <p id="install-prompt-description" className="text-sm text-gray-400">
            Get quick access and offline viewing
          </p>
        </div>
        <button
          type="button"
          onClick={handleDismiss}
          className="flex-shrink-0 text-gray-500 transition-colors hover:text-gray-300"
          aria-label="Dismiss"
        >
          <X className="h-5 w-5" aria-hidden="true" />
        </button>
      </div>
      <div className="mt-4 flex gap-2">
        <Button variant="outline" size="sm" onClick={handleDismiss} className="flex-1">
          Not now
        </Button>
        <Button variant="primary" size="sm" onClick={handleInstall} className="flex-1">
          Install
        </Button>
      </div>
    </div>
  );
}
