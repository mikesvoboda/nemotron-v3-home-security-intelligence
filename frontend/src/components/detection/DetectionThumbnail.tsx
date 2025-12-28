/**
 * DetectionThumbnail Component
 *
 * Displays a detection image with pre-rendered bounding box overlays from the backend.
 * The backend generates thumbnails with bounding boxes and confidence labels already drawn.
 *
 * Features:
 * - Fetches detection images from /api/detections/{id}/image
 * - Shows loading skeleton while image loads
 * - Handles error states with retry option
 * - Supports click handlers for interaction
 * - Responsive sizing with aspect ratio preservation
 */

import React, { useState, useCallback } from 'react';

import { getDetectionImageUrl } from '../../services/api';

export type DetectionThumbnailSize = 'sm' | 'md' | 'lg';

export interface DetectionThumbnailProps {
  /** Detection ID to fetch the image for */
  detectionId: number;
  /** Alt text for accessibility */
  alt: string;
  /** Size variant: sm (120x90), md (240x180), lg (320x240) */
  size?: DetectionThumbnailSize;
  /** Additional CSS classes */
  className?: string;
  /** Click handler */
  onClick?: () => void;
  /** Whether to show loading placeholder */
  showLoading?: boolean;
  /** Custom placeholder while loading */
  loadingPlaceholder?: React.ReactNode;
  /** Custom error component */
  errorComponent?: React.ReactNode;
}

// Size presets matching common thumbnail dimensions
const SIZE_CLASSES: Record<DetectionThumbnailSize, string> = {
  sm: 'w-[120px] h-[90px]',
  md: 'w-[240px] h-[180px]',
  lg: 'w-[320px] h-[240px]',
};

/**
 * Loading skeleton component displayed while the image loads.
 */
const LoadingSkeleton: React.FC<{ size: DetectionThumbnailSize }> = ({ size }) => (
  <div
    className={`${SIZE_CLASSES[size]} animate-pulse rounded-lg bg-gray-700`}
    data-testid="loading-skeleton"
  >
    <div className="flex h-full items-center justify-center">
      <svg
        className="h-8 w-8 text-gray-600"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
        />
      </svg>
    </div>
  </div>
);

/**
 * Error component displayed when image fails to load.
 */
const ErrorDisplay: React.FC<{
  size: DetectionThumbnailSize;
  onRetry?: () => void;
  errorMessage?: string;
}> = ({ size, onRetry, errorMessage }) => (
  <div
    className={`${SIZE_CLASSES[size]} flex flex-col items-center justify-center rounded-lg border border-red-800 bg-gray-800`}
    data-testid="error-display"
  >
    <svg
      className="mb-2 h-6 w-6 text-red-500"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
      />
    </svg>
    <span className="text-xs text-gray-400">{errorMessage || 'Failed to load'}</span>
    {onRetry && (
      <button
        onClick={onRetry}
        className="mt-2 rounded bg-gray-700 px-2 py-1 text-xs text-gray-300 transition-colors hover:bg-gray-600"
        type="button"
      >
        Retry
      </button>
    )}
  </div>
);

/**
 * DetectionThumbnail displays a detection image with server-rendered bounding boxes.
 *
 * The backend handles drawing bounding boxes and confidence labels on the image,
 * so this component simply loads and displays the pre-rendered image.
 *
 * @example
 * ```tsx
 * <DetectionThumbnail
 *   detectionId={123}
 *   alt="Person detected at front door"
 *   size="md"
 *   onClick={() => openDetailModal(123)}
 * />
 * ```
 */
const DetectionThumbnail: React.FC<DetectionThumbnailProps> = ({
  detectionId,
  alt,
  size = 'md',
  className = '',
  onClick,
  showLoading = true,
  loadingPlaceholder,
  errorComponent,
}) => {
  const [status, setStatus] = useState<'loading' | 'loaded' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState<string>();

  const imageUrl = getDetectionImageUrl(detectionId);

  const handleLoad = useCallback(() => {
    setStatus('loaded');
    setErrorMessage(undefined);
  }, []);

  const handleError = useCallback(() => {
    setStatus('error');
    setErrorMessage('Image not found');
  }, []);

  const handleRetry = useCallback(() => {
    setStatus('loading');
    setErrorMessage(undefined);
    // Force re-render by using a timestamp query param
    // This is handled by creating a new Image element below
  }, []);

  // Render loading placeholder
  if (status === 'loading' && showLoading) {
    return (
      <div className={`relative ${className}`}>
        {loadingPlaceholder || <LoadingSkeleton size={size} />}
        {/* Hidden image to trigger load */}
        <img
          src={imageUrl}
          alt=""
          onLoad={handleLoad}
          onError={handleError}
          className="absolute opacity-0"
          aria-hidden="true"
        />
      </div>
    );
  }

  // Render error state
  if (status === 'error') {
    return (
      <div className={className}>
        {errorComponent || (
          <ErrorDisplay size={size} onRetry={handleRetry} errorMessage={errorMessage} />
        )}
      </div>
    );
  }

  // Render loaded image
  return (
    <div
      className={`relative overflow-hidden rounded-lg ${className}`}
      onClick={onClick}
      onKeyDown={(e) => {
        if (onClick && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault();
          onClick();
        }
      }}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      <img
        src={imageUrl}
        alt={alt}
        className={`${SIZE_CLASSES[size]} rounded-lg object-cover`}
        onError={handleError}
      />
      {/* Hover overlay for clickable thumbnails */}
      {onClick && (
        <div className="absolute inset-0 rounded-lg bg-black/0 transition-colors hover:bg-black/20" />
      )}
    </div>
  );
};

export default DetectionThumbnail;
