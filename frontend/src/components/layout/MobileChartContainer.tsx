/**
 * MobileChartContainer - Responsive chart wrapper for mobile devices
 *
 * Reduces chart height to 180px on mobile viewports.
 * Provides tap-to-expand functionality to view charts in fullscreen modal.
 */

import { Maximize2, X } from 'lucide-react';
import { ReactNode, useState, useEffect } from 'react';

import IconButton from '../common/IconButton';

export interface MobileChartContainerProps {
  /** Chart title displayed in header */
  title: string;
  /** Chart content to render */
  children: ReactNode;
  /** Whether to show the expand button (default: true) */
  showExpandButton?: boolean;
  /** Additional CSS classes for container */
  className?: string;
}

export default function MobileChartContainer({
  title,
  children,
  showExpandButton = true,
  className = '',
}: MobileChartContainerProps) {
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Handle escape key to close modal
  useEffect(() => {
    if (!isFullscreen) return;

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsFullscreen(false);
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isFullscreen]);

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (isFullscreen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isFullscreen]);

  return (
    <>
      <div className={className}>
        {/* Header with title and expand button */}
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-base font-semibold text-white">{title}</h3>
          {showExpandButton && (
            <IconButton
              icon={<Maximize2 />}
              aria-label={`Expand ${title} to fullscreen`}
              onClick={() => setIsFullscreen(true)}
              variant="ghost"
              size="md"
            />
          )}
        </div>

        {/* Chart container with mobile height constraint */}
        <div className="h-[180px] overflow-hidden rounded-lg bg-[#1A1A1A]">{children}</div>
      </div>

      {/* Fullscreen modal */}
      {isFullscreen && (
        <div className="fixed inset-0 z-[100] flex flex-col bg-[#0E0E0E]">
          {/* Backdrop */}
          <div
            className="absolute inset-0"
            onClick={() => setIsFullscreen(false)}
            data-testid="fullscreen-backdrop"
            aria-hidden="true"
          />

          {/* Modal content */}
          <div
            className="relative z-10 flex h-full flex-col"
            role="dialog"
            aria-modal="true"
            aria-labelledby="fullscreen-chart-title"
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-gray-800 bg-[#1A1A1A] px-4 py-3">
              <h2 id="fullscreen-chart-title" className="text-lg font-semibold text-white">
                {title}
              </h2>
              <IconButton
                icon={<X />}
                aria-label="Close fullscreen"
                onClick={() => setIsFullscreen(false)}
                variant="ghost"
                size="md"
              />
            </div>

            {/* Chart at full height */}
            <div className="h-full flex-1 overflow-auto p-4">{children}</div>
          </div>
        </div>
      )}
    </>
  );
}
