import React from 'react';

export interface BoundingBox {
  x: number; // top-left x (pixels or percentage)
  y: number; // top-left y
  width: number; // box width
  height: number; // box height
  label: string; // e.g., "person", "car"
  confidence: number; // 0-1
  color?: string; // optional custom color
}

export interface BoundingBoxOverlayProps {
  boxes: BoundingBox[];
  imageWidth: number;
  imageHeight: number;
  showLabels?: boolean;
  showConfidence?: boolean;
  minConfidence?: number; // filter boxes below threshold
  onClick?: (box: BoundingBox) => void;
}

// Default color scheme for common object types
const DEFAULT_COLORS: Record<string, string> = {
  person: '#ef4444', // red
  car: '#3b82f6', // blue
  dog: '#f59e0b', // amber
  cat: '#8b5cf6', // purple
  package: '#10b981', // green
  default: '#6b7280', // gray
};

const BoundingBoxOverlay: React.FC<BoundingBoxOverlayProps> = ({
  boxes,
  imageWidth,
  imageHeight,
  showLabels = true,
  showConfidence = true,
  minConfidence = 0,
  onClick,
}) => {
  // Filter boxes by minimum confidence threshold
  const filteredBoxes = boxes.filter((box) => box.confidence >= minConfidence);

  // Get color for a box based on label or custom color
  const getBoxColor = (box: BoundingBox): string => {
    if (box.color) {
      return box.color;
    }
    return DEFAULT_COLORS[box.label.toLowerCase()] || DEFAULT_COLORS.default;
  };

  // Format confidence as percentage
  const formatConfidence = (confidence: number): string => {
    return `${Math.round(confidence * 100)}%`;
  };

  // Handle edge cases
  if (imageWidth <= 0 || imageHeight <= 0) {
    return null;
  }

  if (filteredBoxes.length === 0) {
    return null;
  }

  return (
    <svg
      className="pointer-events-none absolute inset-0 h-full w-full"
      viewBox={`0 0 ${imageWidth} ${imageHeight}`}
      preserveAspectRatio="none"
      style={{ zIndex: 10 }}
    >
      {filteredBoxes.map((box, index) => {
        const color = getBoxColor(box);
        const boxKey = `box-${index}-${box.label}-${box.x}-${box.y}`;

        return (
          <g key={boxKey}>
            {/* Bounding box rectangle */}
            <rect
              x={box.x}
              y={box.y}
              width={box.width}
              height={box.height}
              fill="none"
              stroke={color}
              strokeWidth="3"
              className={onClick ? 'pointer-events-auto cursor-pointer' : ''}
              onClick={() => onClick?.(box)}
              style={{
                transition: 'stroke-width 0.2s ease',
              }}
              onMouseEnter={(e) => {
                if (onClick) {
                  (e.target as SVGRectElement).setAttribute('stroke-width', '5');
                }
              }}
              onMouseLeave={(e) => {
                if (onClick) {
                  (e.target as SVGRectElement).setAttribute('stroke-width', '3');
                }
              }}
            />

            {/* Label background and text */}
            {showLabels && (
              <g>
                {/* Label background */}
                <rect
                  x={box.x}
                  y={box.y - 28}
                  width={showConfidence ? box.label.length * 8 + 40 : box.label.length * 8 + 16}
                  height="24"
                  fill={color}
                  opacity="0.9"
                  rx="4"
                />

                {/* Label text */}
                <text
                  x={box.x + 8}
                  y={box.y - 10}
                  fill="white"
                  fontSize="14"
                  fontWeight="600"
                  fontFamily="Inter, system-ui, sans-serif"
                  className="pointer-events-none select-none"
                >
                  {box.label}
                  {showConfidence && (
                    <tspan fill="white" opacity="0.9" fontWeight="500">
                      {' '}
                      {formatConfidence(box.confidence)}
                    </tspan>
                  )}
                </text>
              </g>
            )}
          </g>
        );
      })}
    </svg>
  );
};

export default BoundingBoxOverlay;
