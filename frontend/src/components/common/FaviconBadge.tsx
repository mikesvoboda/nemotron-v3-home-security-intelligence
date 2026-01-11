/**
 * FaviconBadge component
 *
 * Updates the browser favicon with an alert count badge and
 * modifies the document title to show the alert count.
 * Useful for indicating unread alerts when the tab is not in focus.
 */

import { useEffect, useRef, useCallback } from 'react';

export interface FaviconBadgeProps {
  /**
   * Number of active alerts to display
   */
  alertCount: number;
  /**
   * Base title for the document (without alert count)
   */
  baseTitle?: string;
  /**
   * Whether the badge feature is enabled
   * @default true
   */
  enabled?: boolean;
  /**
   * Path to the original favicon
   * @default '/favicon.svg'
   */
  faviconPath?: string;
  /**
   * Badge background color
   * @default '#ef4444' (red-500)
   */
  badgeColor?: string;
  /**
   * Badge text color
   * @default '#ffffff'
   */
  badgeTextColor?: string;
}

/**
 * Default base title for the application
 */
const DEFAULT_BASE_TITLE = 'Security Dashboard';

/**
 * FaviconBadge updates the browser favicon and title with alert count information.
 *
 * @example
 * ```tsx
 * // In your App.tsx
 * const { activeAlerts } = useAlerts();
 *
 * return (
 *   <>
 *     <FaviconBadge
 *       alertCount={activeAlerts.length}
 *       baseTitle="Security Dashboard"
 *     />
 *     <AppContent />
 *   </>
 * );
 * ```
 */
export default function FaviconBadge({
  alertCount,
  baseTitle = DEFAULT_BASE_TITLE,
  enabled = true,
  faviconPath = '/favicon.svg',
  badgeColor = '#ef4444',
  badgeTextColor = '#ffffff',
}: FaviconBadgeProps) {
  const originalFaviconRef = useRef<string | null>(null);
  const originalTitleRef = useRef<string | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  /**
   * Draw a badge on the favicon
   */
  const drawFaviconWithBadge = useCallback(
    (count: number): void => {
      if (typeof document === 'undefined') return;

      // Get or create canvas
      if (!canvasRef.current) {
        canvasRef.current = document.createElement('canvas');
        canvasRef.current.width = 32;
        canvasRef.current.height = 32;
      }

      const canvas = canvasRef.current;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      // Load the original favicon
      const img = new Image();
      img.crossOrigin = 'anonymous';

      img.onload = () => {
        // Clear canvas
        ctx.clearRect(0, 0, 32, 32);

        // Draw original favicon
        ctx.drawImage(img, 0, 0, 32, 32);

        if (count > 0) {
          // Draw badge background
          const badgeSize = count > 99 ? 18 : count > 9 ? 16 : 14;
          const badgeX = 32 - badgeSize;
          const badgeY = 0;

          ctx.beginPath();
          ctx.arc(badgeX + badgeSize / 2, badgeY + badgeSize / 2, badgeSize / 2, 0, 2 * Math.PI);
          ctx.fillStyle = badgeColor;
          ctx.fill();

          // Draw count text
          const displayCount = count > 99 ? '99+' : String(count);
          const fontSize = count > 99 ? 8 : count > 9 ? 10 : 12;

          ctx.fillStyle = badgeTextColor;
          ctx.font = `bold ${fontSize}px Arial, sans-serif`;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(displayCount, badgeX + badgeSize / 2, badgeY + badgeSize / 2 + 1);
        }

        // Update favicon
        const faviconUrl = canvas.toDataURL('image/png');
        updateFaviconElement(faviconUrl);
      };

      img.onerror = () => {
        // If SVG fails, try PNG fallback
        const fallbackImg = new Image();
        fallbackImg.crossOrigin = 'anonymous';
        fallbackImg.src = '/favicon.ico';
        fallbackImg.onload = () => {
          ctx.clearRect(0, 0, 32, 32);
          ctx.drawImage(fallbackImg, 0, 0, 32, 32);

          if (count > 0) {
            const badgeSize = count > 99 ? 18 : count > 9 ? 16 : 14;
            const badgeX = 32 - badgeSize;
            const badgeY = 0;

            ctx.beginPath();
            ctx.arc(badgeX + badgeSize / 2, badgeY + badgeSize / 2, badgeSize / 2, 0, 2 * Math.PI);
            ctx.fillStyle = badgeColor;
            ctx.fill();

            const displayCount = count > 99 ? '99+' : String(count);
            const fontSize = count > 99 ? 8 : count > 9 ? 10 : 12;

            ctx.fillStyle = badgeTextColor;
            ctx.font = `bold ${fontSize}px Arial, sans-serif`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(displayCount, badgeX + badgeSize / 2, badgeY + badgeSize / 2 + 1);
          }

          const faviconUrl = canvas.toDataURL('image/png');
          updateFaviconElement(faviconUrl);
        };
      };

      img.src = faviconPath;
    },
    [faviconPath, badgeColor, badgeTextColor]
  );

  /**
   * Update the favicon link element
   */
  const updateFaviconElement = (href: string): void => {
    if (typeof document === 'undefined') return;

    // Find existing favicon link or create new one
    let link = document.querySelector<HTMLLinkElement>('link[rel="icon"]');

    if (!link) {
      link = document.createElement('link');
      link.rel = 'icon';
      document.head.appendChild(link);
    }

    link.type = 'image/png';
    link.href = href;
  };

  /**
   * Restore original favicon
   */
  const restoreOriginalFavicon = useCallback((): void => {
    if (typeof document === 'undefined') return;

    if (originalFaviconRef.current) {
      updateFaviconElement(originalFaviconRef.current);
    } else {
      // Reset to default favicon path
      const link = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
      if (link) {
        link.href = faviconPath;
      }
    }
  }, [faviconPath]);

  /**
   * Update document title with alert count
   */
  const updateTitle = useCallback(
    (count: number): void => {
      if (typeof document === 'undefined') return;

      if (count > 0) {
        document.title = `(${count}) ${baseTitle}`;
      } else {
        document.title = baseTitle;
      }
    },
    [baseTitle]
  );

  /**
   * Restore original document title
   */
  const restoreOriginalTitle = useCallback((): void => {
    if (typeof document === 'undefined') return;

    if (originalTitleRef.current) {
      document.title = originalTitleRef.current;
    } else {
      document.title = baseTitle;
    }
  }, [baseTitle]);

  // Store original favicon and title on mount
  useEffect(() => {
    if (typeof document === 'undefined') return;

    // Store original favicon
    const existingFavicon = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
    if (existingFavicon) {
      originalFaviconRef.current = existingFavicon.href;
    }

    // Store original title
    originalTitleRef.current = document.title;

    return () => {
      // Restore originals on unmount
      restoreOriginalFavicon();
      restoreOriginalTitle();
    };
  }, [restoreOriginalFavicon, restoreOriginalTitle]);

  // Update favicon and title when alert count changes
  useEffect(() => {
    if (!enabled) {
      restoreOriginalFavicon();
      restoreOriginalTitle();
      return;
    }

    const count = Math.max(0, Math.floor(alertCount));

    // Update title
    updateTitle(count);

    // Update favicon
    drawFaviconWithBadge(count);
  }, [alertCount, enabled, drawFaviconWithBadge, updateTitle, restoreOriginalFavicon, restoreOriginalTitle]);

  // This component renders nothing visible
  return null;
}

export type { FaviconBadgeProps as FaviconBadgePropsType };
