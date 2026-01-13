import { clsx } from 'clsx';
import { Camera } from 'lucide-react';
import { useState } from 'react';

// ============================================================================
// Types
// ============================================================================

export interface ThumbnailImageProps {
  /** The source URL of the thumbnail image */
  src?: string;
  /** Alt text for the image */
  alt: string;
  /** Optional className for the container */
  className?: string;
  /** Optional className for the image */
  imageClassName?: string;
  /** Size of the thumbnail (width and height) */
  size?: 'sm' | 'md' | 'lg';
  /** Test ID for the component */
  testId?: string;
}

// ============================================================================
// Constants
// ============================================================================

const sizeClasses: Record<string, { container: string; icon: string }> = {
  sm: { container: 'h-12 w-12', icon: 'h-5 w-5' },
  md: { container: 'h-20 w-20', icon: 'h-8 w-8' },
  lg: { container: 'h-32 w-32', icon: 'h-12 w-12' },
};

// ============================================================================
// Component
// ============================================================================

/**
 * ThumbnailImage displays an image with graceful fallback handling.
 * When the image fails to load (invalid URL, network error, etc.),
 * it displays a placeholder icon instead.
 */
export default function ThumbnailImage({
  src,
  alt,
  className,
  imageClassName,
  size = 'md',
  testId = 'thumbnail-image',
}: ThumbnailImageProps) {
  const [hasError, setHasError] = useState(false);

  const sizeConfig = sizeClasses[size];

  // Handle image load error
  const handleError = () => {
    setHasError(true);
  };

  // Show placeholder when no src provided or when image fails to load
  const showPlaceholder = !src || hasError;

  return (
    <div
      className={clsx('flex-shrink-0', className)}
      data-testid={testId}
    >
      {showPlaceholder ? (
        <div
          className={clsx(
            'flex items-center justify-center rounded-md bg-gray-900',
            sizeConfig.container
          )}
          data-testid={`${testId}-placeholder`}
          aria-label={`Placeholder for ${alt}`}
        >
          <Camera className={clsx('text-gray-700', sizeConfig.icon)} />
        </div>
      ) : (
        <img
          src={src}
          alt={alt}
          className={clsx(
            'rounded-md bg-gray-900 object-cover',
            sizeConfig.container,
            imageClassName
          )}
          onError={handleError}
          data-testid={`${testId}-img`}
        />
      )}
    </div>
  );
}
