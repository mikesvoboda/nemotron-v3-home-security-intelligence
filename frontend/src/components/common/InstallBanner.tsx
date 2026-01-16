/**
 * InstallBanner component
 *
 * Displays a banner prompting users to install the PWA.
 * Respects user dismissal with configurable timeout.
 */

import { Download, X } from 'lucide-react';
import React, { useState, useCallback, useMemo } from 'react';

const STORAGE_KEY = 'pwa-install-dismissed';
const DEFAULT_DISMISSAL_TIMEOUT_DAYS = 7;

// BeforeInstallPromptEvent is not in lib.dom.d.ts
interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

export interface InstallBannerProps {
  /** The deferred install prompt event (null if not available) */
  deferredPrompt: BeforeInstallPromptEvent | null;
  /** Called when the banner is dismissed (either by user or after install) */
  onDismiss: () => void;
  /** Number of days to wait before showing the banner again after dismissal */
  dismissalTimeoutDays?: number;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Check if the banner should be shown based on previous dismissal
 */
function shouldShowBanner(dismissalTimeoutDays: number): boolean {
  const dismissedAt = localStorage.getItem(STORAGE_KEY);

  if (!dismissedAt) {
    return true;
  }

  const dismissedTimestamp = parseInt(dismissedAt, 10);
  const timeoutMs = dismissalTimeoutDays * 24 * 60 * 60 * 1000;
  const now = Date.now();

  return now - dismissedTimestamp > timeoutMs;
}

/**
 * PWA install banner component.
 *
 * @example
 * ```tsx
 * function App() {
 *   const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
 *
 *   useEffect(() => {
 *     const handler = (e: Event) => {
 *       e.preventDefault();
 *       setDeferredPrompt(e as BeforeInstallPromptEvent);
 *     };
 *
 *     window.addEventListener('beforeinstallprompt', handler);
 *     return () => window.removeEventListener('beforeinstallprompt', handler);
 *   }, []);
 *
 *   return (
 *     <>
 *       <InstallBanner
 *         deferredPrompt={deferredPrompt}
 *         onDismiss={() => setDeferredPrompt(null)}
 *       />
 *       <MainContent />
 *     </>
 *   );
 * }
 * ```
 */
export default function InstallBanner({
  deferredPrompt,
  onDismiss,
  dismissalTimeoutDays = DEFAULT_DISMISSAL_TIMEOUT_DAYS,
  className = '',
}: InstallBannerProps): React.ReactElement | null {
  const [isInstalling, setIsInstalling] = useState(false);

  // Check if we should show based on previous dismissal
  const canShow = useMemo(() => shouldShowBanner(dismissalTimeoutDays), [dismissalTimeoutDays]);

  // Handle install button click
  const handleInstall = useCallback(async () => {
    if (!deferredPrompt) return;

    setIsInstalling(true);

    try {
      await deferredPrompt.prompt();
      const { outcome } = await deferredPrompt.userChoice;

      if (outcome === 'accepted') {
        // User accepted - dismiss banner
        onDismiss();
      }
    } catch {
      // Prompt failed - silently ignore
    } finally {
      setIsInstalling(false);
    }
  }, [deferredPrompt, onDismiss]);

  // Handle dismiss button click
  const handleDismiss = useCallback(() => {
    // Save dismissal timestamp
    localStorage.setItem(STORAGE_KEY, String(Date.now()));
    onDismiss();
  }, [onDismiss]);

  // Don't render if no prompt or recently dismissed
  if (!deferredPrompt || !canShow) {
    return null;
  }

  return (
    <div
      data-testid="install-banner"
      role="banner"
      className={`fixed bottom-0 left-0 right-0 z-50 border-t border-gray-700 bg-gray-900 px-4 py-3 sm:px-6 ${className} `}
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
        {/* Icon and message */}
        <div className="flex items-center gap-3">
          <div className="flex-shrink-0 rounded-lg bg-[#76B900]/10 p-2">
            <Download className="h-5 w-5 text-[#76B900]" aria-hidden="true" />
          </div>
          <div className="flex flex-col sm:flex-row sm:items-center sm:gap-2">
            <p className="text-sm font-medium text-white">Install Nemotron Security</p>
            <p className="text-xs text-gray-400 sm:text-sm">
              Get instant alerts and offline access
            </p>
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void handleInstall()}
            disabled={isInstalling}
            className="inline-flex items-center gap-1.5 rounded-md bg-[#76B900] px-3 py-1.5 text-sm font-medium text-black transition-colors hover:bg-[#8BC34A] focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-gray-900 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Download className="h-4 w-4" aria-hidden="true" />
            {isInstalling ? 'Installing...' : 'Install'}
          </button>

          <button
            type="button"
            onClick={handleDismiss}
            className="rounded-md p-1.5 text-gray-400 transition-colors hover:bg-gray-800 hover:text-white focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 focus:ring-offset-gray-900"
            aria-label="Dismiss install banner"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
      </div>
    </div>
  );
}
