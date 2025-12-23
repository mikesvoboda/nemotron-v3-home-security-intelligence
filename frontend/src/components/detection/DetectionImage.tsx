import React, { useState } from 'react';

import BoundingBoxOverlay, { BoundingBox } from './BoundingBoxOverlay';

export interface DetectionImageProps {
  src: string;
  alt: string;
  boxes: BoundingBox[];
  showLabels?: boolean;
  showConfidence?: boolean;
  minConfidence?: number;
  className?: string;
  onClick?: (box: BoundingBox) => void;
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
}) => {
  const [imageDimensions, setImageDimensions] = useState<{
    width: number;
    height: number;
  } | null>(null);

  const handleImageLoad = (event: React.SyntheticEvent<HTMLImageElement>) => {
    const img = event.currentTarget;
    setImageDimensions({
      width: img.naturalWidth,
      height: img.naturalHeight,
    });
  };

  return (
    <div className={`relative inline-block ${className}`}>
      <img
        src={src}
        alt={alt}
        onLoad={handleImageLoad}
        className="block h-full w-full object-contain"
      />
      {imageDimensions && (
        <BoundingBoxOverlay
          boxes={boxes}
          imageWidth={imageDimensions.width}
          imageHeight={imageDimensions.height}
          showLabels={showLabels}
          showConfidence={showConfidence}
          minConfidence={minConfidence}
          onClick={onClick}
        />
      )}
    </div>
  );
};

export default DetectionImage;
