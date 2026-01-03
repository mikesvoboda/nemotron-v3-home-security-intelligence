import { clsx } from 'clsx';
import { useCallback, useEffect, useRef, useState } from 'react';

import type { Zone, ZoneShape } from '../../types/generated';

/** Coordinates as [x, y] normalized to 0-1 range */
export type Point = [number, number];

export interface ZoneCanvasProps {
  /** Camera snapshot URL for background */
  snapshotUrl: string;
  /** Existing zones to display */
  zones: Zone[];
  /** Currently selected zone ID */
  selectedZoneId?: string | null;
  /** Currently drawing new zone */
  isDrawing?: boolean;
  /** Shape to draw (rectangle or polygon) */
  drawShape?: ZoneShape;
  /** Color for new zone being drawn */
  drawColor?: string;
  /** Callback when a zone is clicked */
  onZoneClick?: (zoneId: string) => void;
  /** Callback when drawing is complete with normalized coordinates */
  onDrawComplete?: (coordinates: Point[]) => void;
  /** Callback when drawing is cancelled */
  onDrawCancel?: () => void;
}

/**
 * ZoneCanvas component for displaying and drawing zones on camera snapshots.
 *
 * Features:
 * - Displays camera snapshot as background
 * - Renders existing zones as SVG overlays
 * - Supports drawing rectangles by click-drag
 * - Supports drawing polygons by clicking points
 * - Normalizes coordinates to 0-1 range
 */
export default function ZoneCanvas({
  snapshotUrl,
  zones,
  selectedZoneId,
  isDrawing = false,
  drawShape = 'rectangle',
  drawColor = '#3B82F6',
  onZoneClick,
  onDrawComplete,
  onDrawCancel,
}: ZoneCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 });
  const [imageLoaded, setImageLoaded] = useState(false);
  const [imageError, setImageError] = useState(false);

  // Drawing state
  const [drawingPoints, setDrawingPoints] = useState<Point[]>([]);
  const [isMouseDown, setIsMouseDown] = useState(false);
  const [currentMousePos, setCurrentMousePos] = useState<Point | null>(null);

  // Update container size on resize
  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        setContainerSize({ width: rect.width, height: rect.height });
      }
    };

    updateSize();
    window.addEventListener('resize', updateSize);
    return () => window.removeEventListener('resize', updateSize);
  }, [imageLoaded]);

  // Handle escape key to cancel drawing
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isDrawing) {
        setDrawingPoints([]);
        setIsMouseDown(false);
        setCurrentMousePos(null);
        onDrawCancel?.();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isDrawing, onDrawCancel]);

  // Reset drawing state when isDrawing changes
  useEffect(() => {
    if (!isDrawing) {
      setDrawingPoints([]);
      setIsMouseDown(false);
      setCurrentMousePos(null);
    }
  }, [isDrawing]);

  // Convert pixel coordinates to normalized 0-1 coordinates
  const pixelToNormalized = useCallback(
    (pixelX: number, pixelY: number): Point => {
      if (containerSize.width === 0 || containerSize.height === 0) {
        return [0, 0];
      }
      return [
        Math.max(0, Math.min(1, pixelX / containerSize.width)),
        Math.max(0, Math.min(1, pixelY / containerSize.height)),
      ];
    },
    [containerSize]
  );

  // Convert normalized coordinates to pixel coordinates
  const normalizedToPixel = useCallback(
    (normalizedX: number, normalizedY: number): [number, number] => {
      return [normalizedX * containerSize.width, normalizedY * containerSize.height];
    },
    [containerSize]
  );

  // Get mouse position relative to container
  const getMousePos = useCallback(
    (e: React.MouseEvent): Point => {
      if (!containerRef.current) return [0, 0];
      const rect = containerRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      return pixelToNormalized(x, y);
    },
    [pixelToNormalized]
  );

  // Handle mouse down for drawing
  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (!isDrawing) return;
      e.preventDefault();

      const pos = getMousePos(e);

      if (drawShape === 'rectangle') {
        setDrawingPoints([pos]);
        setIsMouseDown(true);
      } else {
        // Polygon: add point on click
        setDrawingPoints((prev) => [...prev, pos]);
      }
    },
    [isDrawing, drawShape, getMousePos]
  );

  // Handle mouse move for drawing
  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!isDrawing) return;

      const pos = getMousePos(e);
      setCurrentMousePos(pos);

      if (drawShape === 'rectangle' && isMouseDown && drawingPoints.length === 1) {
        // Update second point while dragging
        setDrawingPoints([drawingPoints[0], pos]);
      }
    },
    [isDrawing, drawShape, isMouseDown, drawingPoints, getMousePos]
  );

  // Handle mouse up for drawing
  const handleMouseUp = useCallback(
    (e: React.MouseEvent) => {
      if (!isDrawing || !isMouseDown) return;
      e.preventDefault();

      setIsMouseDown(false);

      if (drawShape === 'rectangle' && drawingPoints.length >= 1) {
        const pos = getMousePos(e);
        const startPoint = drawingPoints[0];

        // Create rectangle coordinates (4 corners)
        const minX = Math.min(startPoint[0], pos[0]);
        const maxX = Math.max(startPoint[0], pos[0]);
        const minY = Math.min(startPoint[1], pos[1]);
        const maxY = Math.max(startPoint[1], pos[1]);

        // Ensure minimum size
        if (maxX - minX > 0.02 && maxY - minY > 0.02) {
          const rectCoords: Point[] = [
            [minX, minY],
            [maxX, minY],
            [maxX, maxY],
            [minX, maxY],
          ];
          onDrawComplete?.(rectCoords);
        }
        setDrawingPoints([]);
      }
    },
    [isDrawing, isMouseDown, drawShape, drawingPoints, getMousePos, onDrawComplete]
  );

  // Handle double click to complete polygon
  const handleDoubleClick = useCallback(
    (e: React.MouseEvent) => {
      if (!isDrawing || drawShape !== 'polygon') return;
      e.preventDefault();

      if (drawingPoints.length >= 3) {
        onDrawComplete?.(drawingPoints);
      }
      setDrawingPoints([]);
    },
    [isDrawing, drawShape, drawingPoints, onDrawComplete]
  );

  // Render a zone as SVG polygon
  const renderZone = (zone: Zone) => {
    const isSelected = zone.id === selectedZoneId;
    const points = zone.coordinates
      .map((coord) => {
        const [px, py] = normalizedToPixel(coord[0], coord[1]);
        return `${px},${py}`;
      })
      .join(' ');

    return (
      <g key={zone.id} className="cursor-pointer" onClick={() => onZoneClick?.(zone.id)}>
        <polygon
          points={points}
          fill={zone.color}
          fillOpacity={isSelected ? 0.4 : 0.25}
          stroke={zone.color}
          strokeWidth={isSelected ? 3 : 2}
          strokeDasharray={zone.enabled ? undefined : '5,5'}
          className="transition-all duration-200"
        />
        {/* Zone label */}
        {zone.coordinates.length > 0 && (
          <text
            x={normalizedToPixel(zone.coordinates[0][0], zone.coordinates[0][1])[0] + 5}
            y={normalizedToPixel(zone.coordinates[0][0], zone.coordinates[0][1])[1] + 20}
            fill="white"
            fontSize="12"
            fontWeight="bold"
            className="pointer-events-none select-none drop-shadow-md"
          >
            {zone.name}
          </text>
        )}
      </g>
    );
  };

  // Render drawing preview
  const renderDrawingPreview = () => {
    if (!isDrawing || drawingPoints.length === 0) return null;

    if (drawShape === 'rectangle' && drawingPoints.length >= 1) {
      const endPoint = currentMousePos || drawingPoints[1] || drawingPoints[0];
      const startPoint = drawingPoints[0];

      const minX = Math.min(startPoint[0], endPoint[0]);
      const maxX = Math.max(startPoint[0], endPoint[0]);
      const minY = Math.min(startPoint[1], endPoint[1]);
      const maxY = Math.max(startPoint[1], endPoint[1]);

      const [x, y] = normalizedToPixel(minX, minY);
      const [x2, y2] = normalizedToPixel(maxX, maxY);

      return (
        <rect
          x={x}
          y={y}
          width={x2 - x}
          height={y2 - y}
          fill={drawColor}
          fillOpacity={0.3}
          stroke={drawColor}
          strokeWidth={2}
          strokeDasharray="5,5"
        />
      );
    }

    if (drawShape === 'polygon' && drawingPoints.length >= 1) {
      const points = drawingPoints.map((coord) => {
        const [px, py] = normalizedToPixel(coord[0], coord[1]);
        return `${px},${py}`;
      });

      // Add current mouse position if available
      if (currentMousePos) {
        const [px, py] = normalizedToPixel(currentMousePos[0], currentMousePos[1]);
        points.push(`${px},${py}`);
      }

      return (
        <>
          <polygon
            points={points.join(' ')}
            fill={drawColor}
            fillOpacity={0.3}
            stroke={drawColor}
            strokeWidth={2}
            strokeDasharray="5,5"
          />
          {/* Draw vertices */}
          {drawingPoints.map((point, i) => {
            const [px, py] = normalizedToPixel(point[0], point[1]);
            return (
              <circle
                key={i}
                cx={px}
                cy={py}
                r={5}
                fill={drawColor}
                stroke="white"
                strokeWidth={2}
              />
            );
          })}
        </>
      );
    }

    return null;
  };

  return (
    // eslint-disable-next-line jsx-a11y/no-static-element-interactions
    <div
      ref={containerRef}
      aria-label={isDrawing ? 'Zone drawing canvas - click and drag to draw' : 'Camera zones view'}
      className={clsx(
        'relative overflow-hidden rounded-lg border border-gray-700 bg-gray-900',
        isDrawing && 'cursor-crosshair'
      )}
      style={{ aspectRatio: '16/9' }}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onDoubleClick={handleDoubleClick}
    >
      {/* Camera snapshot background */}
      {imageError ? (
        <div className="flex h-full items-center justify-center bg-gray-800">
          <span className="text-gray-400">Failed to load camera snapshot</span>
        </div>
      ) : (
        <img
          src={snapshotUrl}
          alt="Camera snapshot"
          className="h-full w-full object-cover"
          onLoad={() => setImageLoaded(true)}
          onError={() => setImageError(true)}
          draggable={false}
        />
      )}

      {/* SVG overlay for zones */}
      {imageLoaded && containerSize.width > 0 && (
        <svg
          className="absolute inset-0 h-full w-full"
          style={{ pointerEvents: isDrawing ? 'none' : 'auto' }}
        >
          {/* Existing zones */}
          {zones.map(renderZone)}

          {/* Drawing preview */}
          {renderDrawingPreview()}
        </svg>
      )}

      {/* Drawing instructions */}
      {isDrawing && (
        <div className="pointer-events-none absolute bottom-2 left-2 rounded bg-black/70 px-2 py-1 text-xs text-white">
          {drawShape === 'rectangle'
            ? 'Click and drag to draw a rectangle. Press ESC to cancel.'
            : 'Click to add points. Double-click to complete. Press ESC to cancel.'}
        </div>
      )}
    </div>
  );
}
