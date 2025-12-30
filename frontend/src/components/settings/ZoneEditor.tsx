import { clsx } from 'clsx';
import { Move, Plus, RotateCcw } from 'lucide-react';
import React, { useCallback, useEffect, useRef, useState } from 'react';

import type { Zone, ZoneShape, ZoneType } from '../../services/api';

/**
 * Point coordinates in normalized 0-1 range
 */
export interface Point {
  x: number;
  y: number;
}

export interface ZoneEditorProps {
  /** Camera image URL for background */
  imageUrl?: string;
  /** Existing zones to display */
  zones: Zone[];
  /** Currently selected zone ID */
  selectedZoneId?: string;
  /** Called when a zone is selected */
  onZoneSelect?: (zoneId: string | null) => void;
  /** Called when zone coordinates are updated */
  onZoneUpdate?: (zoneId: string, coordinates: number[][]) => void | Promise<void>;
  /** Called when a new zone is created */
  onZoneCreate?: (coordinates: number[][], shape: ZoneShape) => void;
  /** Current drawing mode */
  mode?: 'view' | 'draw' | 'edit';
  /** Shape to draw when in draw mode */
  drawShape?: ZoneShape;
  /** Image dimensions for proper scaling */
  imageDimensions?: { width: number; height: number };
  /** Additional CSS classes */
  className?: string;
}

// Zone type color mapping
const ZONE_TYPE_COLORS: Record<ZoneType, string> = {
  entry_point: '#ef4444', // red
  driveway: '#3b82f6', // blue
  sidewalk: '#f59e0b', // amber
  yard: '#10b981', // green
  other: '#6b7280', // gray
};

/**
 * ZoneEditor - Interactive visual component for drawing and editing zones on camera images
 *
 * Features:
 * - Draw rectangle or polygon zones on camera preview
 * - Edit existing zone coordinates by dragging points
 * - Visual feedback for zone types with different colors
 * - Support for normalized coordinates (0-1 range)
 */
const ZoneEditor: React.FC<ZoneEditorProps> = ({
  imageUrl,
  zones,
  selectedZoneId,
  onZoneSelect,
  onZoneUpdate,
  onZoneCreate,
  mode = 'view',
  drawShape = 'rectangle',
  imageDimensions: _imageDimensions,
  className,
}) => {
  // Note: _imageDimensions is reserved for future use when implementing
  // pixel-based coordinate normalization from known image dimensions
  void _imageDimensions;
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 });
  const [drawingPoints, setDrawingPoints] = useState<Point[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [dragPointIndex, setDragPointIndex] = useState<number | null>(null);
  const [hoveredZoneId, setHoveredZoneId] = useState<string | null>(null);

  // Observe container size changes
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        setContainerSize({ width, height });
      }
    });

    resizeObserver.observe(container);
    return () => resizeObserver.disconnect();
  }, []);

  // Convert normalized coordinates to pixel coordinates
  const toPixel = useCallback(
    (point: Point): Point => ({
      x: point.x * containerSize.width,
      y: point.y * containerSize.height,
    }),
    [containerSize]
  );

  // Convert pixel coordinates to normalized coordinates
  const toNormalized = useCallback(
    (point: Point): Point => ({
      x: Math.max(0, Math.min(1, point.x / containerSize.width)),
      y: Math.max(0, Math.min(1, point.y / containerSize.height)),
    }),
    [containerSize]
  );

  // Get mouse position relative to container
  const getMousePosition = useCallback(
    (e: React.MouseEvent): Point => {
      const container = containerRef.current;
      if (!container) return { x: 0, y: 0 };

      const rect = container.getBoundingClientRect();
      return {
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      };
    },
    []
  );

  // Handle click for zone selection or drawing
  const handleClick = useCallback(
    (e: React.MouseEvent) => {
      if (mode === 'view') return;

      const mousePos = getMousePosition(e);
      const normalizedPos = toNormalized(mousePos);

      if (mode === 'draw') {
        if (drawShape === 'rectangle') {
          // For rectangle, two clicks define opposite corners
          if (drawingPoints.length === 0) {
            setDrawingPoints([normalizedPos]);
          } else if (drawingPoints.length === 1) {
            // Create rectangle from two corners
            const p1 = drawingPoints[0];
            const p2 = normalizedPos;
            const rectCoords = [
              [Math.min(p1.x, p2.x), Math.min(p1.y, p2.y)],
              [Math.max(p1.x, p2.x), Math.min(p1.y, p2.y)],
              [Math.max(p1.x, p2.x), Math.max(p1.y, p2.y)],
              [Math.min(p1.x, p2.x), Math.max(p1.y, p2.y)],
            ];
            onZoneCreate?.(rectCoords, 'rectangle');
            setDrawingPoints([]);
          }
        } else {
          // For polygon, accumulate points
          setDrawingPoints([...drawingPoints, normalizedPos]);
        }
      }
    },
    [mode, drawShape, drawingPoints, getMousePosition, toNormalized, onZoneCreate]
  );

  // Handle double-click to finish polygon
  const handleDoubleClick = useCallback(() => {
    if (mode === 'draw' && drawShape === 'polygon' && drawingPoints.length >= 3) {
      const coords = drawingPoints.map((p) => [p.x, p.y]);
      onZoneCreate?.(coords, 'polygon');
      setDrawingPoints([]);
    }
  }, [mode, drawShape, drawingPoints, onZoneCreate]);

  // Handle mouse down for dragging zone points
  const handlePointMouseDown = useCallback(
    (e: React.MouseEvent, zoneId: string, pointIndex: number) => {
      e.stopPropagation();
      if (mode === 'edit' && selectedZoneId === zoneId) {
        setIsDragging(true);
        setDragPointIndex(pointIndex);
      }
    },
    [mode, selectedZoneId]
  );

  // Handle mouse move for dragging
  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!isDragging || dragPointIndex === null || !selectedZoneId) return;

      const mousePos = getMousePosition(e);
      const normalizedPos = toNormalized(mousePos);

      const zone = zones.find((z) => z.id === selectedZoneId);
      if (!zone) return;

      const newCoords = zone.coordinates.map((coord, i) =>
        i === dragPointIndex ? [normalizedPos.x, normalizedPos.y] : coord
      );

      void onZoneUpdate?.(selectedZoneId, newCoords);
    },
    [
      isDragging,
      dragPointIndex,
      selectedZoneId,
      zones,
      getMousePosition,
      toNormalized,
      onZoneUpdate,
    ]
  );

  // Handle mouse up to stop dragging
  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
    setDragPointIndex(null);
  }, []);

  // Handle zone click for selection
  const handleZoneClick = useCallback(
    (e: React.MouseEvent, zoneId: string) => {
      e.stopPropagation();
      if (mode !== 'draw') {
        onZoneSelect?.(selectedZoneId === zoneId ? null : zoneId);
      }
    },
    [mode, selectedZoneId, onZoneSelect]
  );

  // Clear drawing points
  const handleClearDrawing = useCallback(() => {
    setDrawingPoints([]);
  }, []);

  // Cancel drawing mode when Escape is pressed
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setDrawingPoints([]);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Convert zone coordinates to SVG polygon points
  const getPolygonPoints = useCallback(
    (coordinates: number[][]): string => {
      return coordinates
        .map((coord) => {
          const pixel = toPixel({ x: coord[0], y: coord[1] });
          return `${pixel.x},${pixel.y}`;
        })
        .join(' ');
    },
    [toPixel]
  );

  // Get zone color
  const getZoneColor = (zone: Zone): string => {
    return zone.color || ZONE_TYPE_COLORS[zone.zone_type] || ZONE_TYPE_COLORS.other;
  };

  return (
    // eslint-disable-next-line jsx-a11y/no-static-element-interactions, jsx-a11y/click-events-have-key-events
    <div
      ref={containerRef}
      className={clsx(
        'relative overflow-hidden rounded-lg border border-gray-700 bg-gray-900',
        mode === 'draw' && 'cursor-crosshair',
        mode === 'edit' && 'cursor-move',
        className
      )}
      onClick={handleClick}
      onDoubleClick={handleDoubleClick}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      {/* Background image */}
      {imageUrl ? (
        <img
          src={imageUrl}
          alt="Camera preview"
          className="h-full w-full object-contain"
          draggable={false}
        />
      ) : (
        <div className="flex h-64 w-full items-center justify-center bg-gray-800 text-text-secondary">
          No camera preview available
        </div>
      )}

      {/* SVG overlay for zones */}
      {containerSize.width > 0 && containerSize.height > 0 && (
        <svg
          className="pointer-events-none absolute inset-0 h-full w-full"
          viewBox={`0 0 ${containerSize.width} ${containerSize.height}`}
          style={{ zIndex: 10 }}
        >
          {/* Existing zones */}
          {zones.map((zone) => {
            const color = getZoneColor(zone);
            const isSelected = selectedZoneId === zone.id;
            const isHovered = hoveredZoneId === zone.id;
            const opacity = zone.enabled ? (isSelected || isHovered ? 0.5 : 0.3) : 0.15;

            return (
              <g key={zone.id}>
                {/* Zone polygon */}
                <polygon
                  points={getPolygonPoints(zone.coordinates)}
                  fill={color}
                  fillOpacity={opacity}
                  stroke={color}
                  strokeWidth={isSelected ? 3 : 2}
                  strokeDasharray={zone.enabled ? 'none' : '5,5'}
                  className="pointer-events-auto cursor-pointer"
                  onClick={(e) => handleZoneClick(e, zone.id)}
                  onMouseEnter={() => setHoveredZoneId(zone.id)}
                  onMouseLeave={() => setHoveredZoneId(null)}
                />

                {/* Edit handles for selected zone */}
                {isSelected &&
                  mode === 'edit' &&
                  zone.coordinates.map((coord, i) => {
                    const pixel = toPixel({ x: coord[0], y: coord[1] });
                    return (
                      <circle
                        key={`handle-${i}`}
                        cx={pixel.x}
                        cy={pixel.y}
                        r={8}
                        fill="white"
                        stroke={color}
                        strokeWidth={2}
                        className="pointer-events-auto cursor-move"
                        onMouseDown={(e) =>
                          handlePointMouseDown(e as unknown as React.MouseEvent, zone.id, i)
                        }
                      />
                    );
                  })}

                {/* Zone label */}
                {(isSelected || isHovered) && zone.coordinates.length > 0 && (
                  <g>
                    <rect
                      x={toPixel({ x: zone.coordinates[0][0], y: zone.coordinates[0][1] }).x}
                      y={toPixel({ x: zone.coordinates[0][0], y: zone.coordinates[0][1] }).y - 28}
                      width={zone.name.length * 8 + 16}
                      height={24}
                      fill={color}
                      opacity={0.9}
                      rx={4}
                    />
                    <text
                      x={toPixel({ x: zone.coordinates[0][0], y: zone.coordinates[0][1] }).x + 8}
                      y={toPixel({ x: zone.coordinates[0][0], y: zone.coordinates[0][1] }).y - 10}
                      fill="white"
                      fontSize="14"
                      fontWeight="600"
                      fontFamily="Inter, system-ui, sans-serif"
                      className="pointer-events-none select-none"
                    >
                      {zone.name}
                    </text>
                  </g>
                )}
              </g>
            );
          })}

          {/* Drawing preview */}
          {mode === 'draw' && drawingPoints.length > 0 && (
            <g>
              {/* Preview polygon */}
              <polygon
                points={drawingPoints.map((p) => `${toPixel(p).x},${toPixel(p).y}`).join(' ')}
                fill="#76B900"
                fillOpacity={0.3}
                stroke="#76B900"
                strokeWidth={2}
                strokeDasharray="5,5"
              />

              {/* Drawing points */}
              {drawingPoints.map((point, i) => {
                const pixel = toPixel(point);
                return (
                  <circle
                    key={`draw-point-${i}`}
                    cx={pixel.x}
                    cy={pixel.y}
                    r={6}
                    fill="#76B900"
                    stroke="white"
                    strokeWidth={2}
                  />
                );
              })}
            </g>
          )}
        </svg>
      )}

      {/* Drawing instructions overlay */}
      {mode === 'draw' && (
        <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between rounded bg-black/70 px-3 py-2 text-sm text-white">
          <span>
            {drawShape === 'rectangle'
              ? drawingPoints.length === 0
                ? 'Click to set first corner'
                : 'Click to set opposite corner'
              : drawingPoints.length < 3
                ? `Click to add points (${drawingPoints.length}/3 minimum)`
                : 'Double-click to finish polygon, or click to add more points'}
          </span>
          {drawingPoints.length > 0 && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleClearDrawing();
              }}
              className="flex items-center gap-1 rounded bg-gray-700 px-2 py-1 text-xs hover:bg-gray-600"
            >
              <RotateCcw className="h-3 w-3" />
              Reset
            </button>
          )}
        </div>
      )}

      {/* Mode indicator */}
      <div className="absolute right-2 top-2 flex items-center gap-2">
        {mode === 'draw' && (
          <div className="flex items-center gap-1 rounded bg-primary/90 px-2 py-1 text-xs font-medium text-gray-900">
            <Plus className="h-3 w-3" />
            Draw {drawShape}
          </div>
        )}
        {mode === 'edit' && selectedZoneId && (
          <div className="flex items-center gap-1 rounded bg-blue-500/90 px-2 py-1 text-xs font-medium text-white">
            <Move className="h-3 w-3" />
            Edit Zone
          </div>
        )}
      </div>
    </div>
  );
};

export default ZoneEditor;
