import React, { useState } from 'react';

import BoundingBoxOverlay, { BoundingBox } from './BoundingBoxOverlay';
import PoseSkeletonOverlay, { Keypoint } from './PoseSkeletonOverlay';
import Lightbox from '../common/Lightbox';

export interface DetectionImageProps {
  src: string;
  alt: string;
  boxes: BoundingBox[];
  showLabels?: boolean;
  showConfidence?: boolean;
  minConfidence?: number;
  className?: string;
  /** Callback when a bounding box is clicked */
  onClick?: (box: BoundingBox) => void;
  /** Enable lightbox on image click (default: false) */
  enableLightbox?: boolean;
  /** Caption to show in the lightbox */
  lightboxCaption?: string;
  /** Pose keypoints for skeleton overlay [[x, y, conf], ...] */
  poseKeypoints?: Keypoint[] | null;
  /** Whether to show pose skeleton overlay (default: true when keypoints provided) */
  showPoseSkeleton?: boolean;
  /** Minimum confidence for pose keypoints (default: 0.3) */
  poseMinConfidence?: number;
}

const DetectionImage: React.FC<DetectionImageProps> = ({
  src,
  alt,
  boxes,
  showLabels = true,
  showConfidence = true,
  minConfidence = 0,
  className = '',
  onClick,
  enableLightbox = false,
  lightboxCaption,
  poseKeypoints,
  showPoseSkeleton = true,
  poseMinConfidence = 0.3,
}) => {
  const [imageDimensions, setImageDimensions] = useState<{
    width: number;
    height: number;
  } | null>(null);
  const [isLightboxOpen, setIsLightboxOpen] = useState(false);

  const handleImageLoad = (event: React.SyntheticEvent<HTMLImageElement>) => {
    const img = event.currentTarget;
    setImageDimensions({
      width: img.naturalWidth,
      height: img.naturalHeight,
    });
  };

  const handleImageClick = () => {
    if (enableLightbox) {
      setIsLightboxOpen(true);
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (enableLightbox && (event.key === 'Enter' || event.key === ' ')) {
      event.preventDefault();
      setIsLightboxOpen(true);
    }
  };

  return (
    <>
      <div
        className={`relative inline-block ${className} ${enableLightbox ? 'cursor-pointer' : ''}`}
        data-testid="detection-image-container"
        {...(enableLightbox && {
          onClick: handleImageClick,
          onKeyDown: handleKeyDown,
          role: 'button',
          tabIndex: 0,
          'aria-label': `View ${alt} in full size`,
        })}
      >
        <img
          src={src}
          alt={alt}
          onLoad={handleImageLoad}
          className="block h-full w-full object-contain"
          data-testid="detection-image"
        />
        {imageDimensions && (
          <>
            <BoundingBoxOverlay
              boxes={boxes}
              imageWidth={imageDimensions.width}
              imageHeight={imageDimensions.height}
              showLabels={showLabels}
              showConfidence={showConfidence}
              minConfidence={minConfidence}
              onClick={onClick}
            />
            {poseKeypoints && (
              <PoseSkeletonOverlay
                keypoints={poseKeypoints}
                imageWidth={imageDimensions.width}
                imageHeight={imageDimensions.height}
                visible={showPoseSkeleton}
                minConfidence={poseMinConfidence}
              />
            )}
          </>
        )}
        {enableLightbox && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/0 opacity-0 transition-opacity hover:bg-black/30 hover:opacity-100">
            <span className="rounded-lg bg-black/60 px-3 py-1.5 text-sm font-medium text-white">
              Click to enlarge
            </span>
          </div>
        )}
      </div>

      {enableLightbox && (
        <Lightbox
          images={{ src, alt, caption: lightboxCaption }}
          isOpen={isLightboxOpen}
          onClose={() => setIsLightboxOpen(false)}
        />
      )}
    </>
  );
};

export default DetectionImage;
