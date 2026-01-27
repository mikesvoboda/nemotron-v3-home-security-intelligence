/**
 * PolygonZoneEditor - Polygon zone drawing component for restricted areas
 *
 * Component for drawing and displaying polygon zones (restricted areas) on camera feeds.
 * Polygon zones define specific regions with multiple vertices for area-based detection.
 *
 * Features:
 * - Multi-point polygon drawing
 * - Polygon preview while drawing
 * - Vertex markers with drag support
 * - Minimum 3 points requirement
 * - Undo last point (Ctrl+Z)
 * - Zone type styling and indicators
 * - Display of existing polygon zones
 * - Selection and interaction with existing zones
 * - Keyboard navigation (Escape to cancel, Enter to complete)
 *
 * @module components/zones/PolygonZoneEditor
 * @see NEM-3720 Create frontend zone editor components
 */

import { clsx } from 'clsx';
import { Undo2 } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

import type { Point } from './ZoneCanvas';
import type { ZoneType } from '../../types/generated';

// ============================================================================
// Types
// ============================================================================

/**
 * Existing zone data for display.
 */
export interface ExistingZone {
  /** Unique zone identifier */
  id: string;
  /** Zone coordinates as normalized points */
  coordinates: Point[];
  /** Zone display color */
  color: string;
  /** Zone name */
  name: string;
}

/**
 * Props for the PolygonZoneEditor component.
 */
export interface PolygonZoneEditorProps {
  /** URL for the camera snapshot background image */
  snapshotUrl: string;
  /** Whether the component is in drawing mode */
  isDrawing?: boolean;
  /** Type of zone being created (for styling) */
  zoneType?: ZoneType;
  /** Color for the zone being drawn */
  zoneColor?: string;
  /** Existing zones to display */
  existingZones?: ExistingZone[];
  /** Currently selected zone ID */
  selectedZoneId?: string;
  /** Callback when polygon drawing is complete */
  onPolygonComplete?: (points: Point[]) => void;
  /** Callback when drawing is cancelled */
  onCancel?: () => void;
  /** Callback when an existing zone is selected */
  onZoneSelect?: (zoneId: string) => void;
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Constants
// ============================================================================

/** Minimum number of points for a valid polygon */
const MIN_POINTS = 3;

/** Zone type configuration for styling */
const ZONE_TYPE_CONFIG: Record<
  ZoneType,
  { label: string; bgColor: string; textColor: string }
> = {
  entry_point: {
    label: 'Entry Point',
    bgColor: 'bg-red-500',
    textColor: 'text-red-400',
  },
  driveway: {
    label: 'Driveway',
    bgColor: 'bg-amber-500',
    textColor: 'text-amber-400',
  },
  sidewalk: {
    label: 'Sidewalk',
    bgColor: 'bg-blue-500',
    textColor: 'text-blue-400',
  },
  yard: {
    label: 'Yard',
    bgColor: 'bg-green-500',
    textColor: 'text-green-400',
  },
  other: {
    label: 'Other',
    bgColor: 'bg-gray-500',
    textColor: 'text-gray-400',
  },
};

// ============================================================================
// Component
// ============================================================================

/**
 * PolygonZoneEditor component for drawing polygon zones.
 *
 * Polygon zones define specific areas on camera feeds for area-based
 * detection. Common use cases include restricted areas, entry zones,
 * driveways, and other regions of interest.
 *
 * @param props - Component props
 * @returns Rendered PolygonZoneEditor component
 */
export default function PolygonZoneEditor({
  snapshotUrl,
  isDrawing = false,
  zoneType = 'other',
  zoneColor = '#3B82F6',
  existingZones = [],
  selectedZoneId,
  onPolygonComplete,
  onCancel,
  onZoneSelect,
  className,
}: PolygonZoneEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 });
  const [imageLoaded, setImageLoaded] = useState(false);
  const [imageError, setImageError] = useState(false);

  // Drawing state
  const [points, setPoints] = useState<Point[]>([]);
  const [currentMousePos, setCurrentMousePos] = useState<Point | null>(null);

  // Get zone type config
  const typeConfig = ZONE_TYPE_CONFIG[zoneType] || ZONE_TYPE_CONFIG.other;

  // ============================================================================
  // Effects
  // ============================================================================

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

  // Undo the last point
  const handleUndo = useCallback(() => {
    setPoints((prev) => prev.slice(0, -1));
  }, []);

  // Handle keyboard events
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isDrawing) return;

      if (e.key === 'Escape') {
        setPoints([]);
        setCurrentMousePos(null);
        onCancel?.();
      } else if (e.key === 'Enter' && points.length >= MIN_POINTS) {
        onPolygonComplete?.(points);
        setPoints([]);
        setCurrentMousePos(null);
      } else if (e.key === 'z' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        handleUndo();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isDrawing, points, onCancel, onPolygonComplete, handleUndo]);

  // Reset state when drawing mode changes
  useEffect(() => {
    if (!isDrawing) {
      setPoints([]);
      setCurrentMousePos(null);
    }
  }, [isDrawing]);

  // ============================================================================
  // Helper Functions
  // ============================================================================

  /**
   * Convert pixel coordinates to normalized 0-1 coordinates.
   */
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

  /**
   * Convert normalized coordinates to pixel coordinates.
   */
  const normalizedToPixel = useCallback(
    (normalizedX: number, normalizedY: number): [number, number] => {
      return [normalizedX * containerSize.width, normalizedY * containerSize.height];
    },
    [containerSize]
  );

  /**
   * Get mouse position relative to container.
   */
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

  // ============================================================================
  // Event Handlers
  // ============================================================================

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (!isDrawing) return;
      e.preventDefault();

      const pos = getMousePos(e);
      setPoints((prev) => [...prev, pos]);
    },
    [isDrawing, getMousePos]
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!isDrawing) return;
      const pos = getMousePos(e);
      setCurrentMousePos(pos);
    },
    [isDrawing, getMousePos]
  );

  const handleDoubleClick = useCallback(
    (e: React.MouseEvent) => {
      if (!isDrawing || points.length < MIN_POINTS) return;
      e.preventDefault();

      onPolygonComplete?.(points);
      setPoints([]);
      setCurrentMousePos(null);
    },
    [isDrawing, points, onPolygonComplete]
  );

  // ============================================================================
  // Render Functions
  // ============================================================================

  /**
   * Render an existing zone.
   */
  const renderZone = (zone: ExistingZone) => {
    const isSelected = zone.id === selectedZoneId;
    const pointsStr = zone.coordinates
      .map((coord) => {
        const [px, py] = normalizedToPixel(coord[0], coord[1]);
        return `${px},${py}`;
      })
      .join(' ');

    return (
      <g key={zone.id}>
        <polygon
          points={pointsStr}
          fill={zone.color}
          fillOpacity={isSelected ? 0.4 : 0.25}
          stroke={zone.color}
          strokeWidth={isSelected ? 3 : 2}
          className="cursor-pointer transition-all duration-200"
          onClick={() => onZoneSelect?.(zone.id)}
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

  /**
   * Render the polygon preview while drawing.
   */
  const renderDrawingPreview = () => {
    if (points.length === 0) return null;

    // Build points string including current mouse position
    const allPoints = [...points];
    if (currentMousePos) {
      allPoints.push(currentMousePos);
    }

    const pointsStr = allPoints
      .map((coord) => {
        const [px, py] = normalizedToPixel(coord[0], coord[1]);
        return `${px},${py}`;
      })
      .join(' ');

    return (
      <g>
        {/* Polygon preview */}
        <polygon
          points={pointsStr}
          fill={zoneColor}
          fillOpacity={0.3}
          stroke={zoneColor}
          strokeWidth={2}
          strokeDasharray="8,4"
        />

        {/* Vertex markers */}
        {points.map((point, index) => {
          const [px, py] = normalizedToPixel(point[0], point[1]);
          return (
            <circle
              key={index}
              cx={px}
              cy={py}
              r={5}
              fill={zoneColor}
              stroke="white"
              strokeWidth={2}
            />
          );
        })}
      </g>
    );
  };

  /**
   * Get instruction text based on drawing state.
   */
  const getInstructions = (): string => {
    if (!isDrawing) return '';
    if (points.length === 0) {
      return 'Click to add points. Double-click or press Enter to complete (min 3 points).';
    }
    if (points.length < MIN_POINTS) {
      return `${points.length} point${points.length > 1 ? 's' : ''} - Add ${MIN_POINTS - points.length} more. Press ESC to cancel.`;
    }
    return `${points.length} points - Double-click or press Enter to complete. Press ESC to cancel.`;
  };

  // ============================================================================
  // Render
  // ============================================================================

  return (
    // eslint-disable-next-line jsx-a11y/no-static-element-interactions -- Keyboard events handled via window.addEventListener for drawing canvas
    <div
      ref={containerRef}
      role={isDrawing ? 'application' : 'img'}
      aria-label={
        isDrawing
          ? 'Polygon zone drawing canvas - click to add points'
          : 'Camera polygon zones view'
      }
      tabIndex={0}
      className={clsx(
        'relative overflow-hidden rounded-lg border border-gray-700 bg-gray-900',
        'focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-gray-900',
        isDrawing && 'cursor-crosshair',
        className
      )}
      style={{ aspectRatio: '16/9' }}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
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
      {imageLoaded && (
        <svg
          className="absolute inset-0 h-full w-full"
          style={{ pointerEvents: isDrawing ? 'none' : 'auto' }}
          data-testid="zone-editor-svg"
        >
          {/* Only render zone content when container has size */}
          {containerSize.width > 0 && (
            <>
              {/* Existing zones */}
              {existingZones.map(renderZone)}

              {/* Drawing preview */}
              {isDrawing && renderDrawingPreview()}
            </>
          )}
        </svg>
      )}

      {/* Zone type indicator */}
      {isDrawing && (
        <div className="absolute left-2 top-2 flex items-center gap-2 rounded bg-black/70 px-2 py-1">
          <div
            data-testid="zone-type-indicator"
            className={clsx('h-3 w-3 rounded-full', typeConfig.bgColor)}
          />
          <span className={clsx('text-xs font-medium', typeConfig.textColor)}>
            {typeConfig.label}
          </span>
        </div>
      )}

      {/* Drawing controls */}
      {isDrawing && points.length > 0 && (
        <div className="absolute right-2 top-2 flex items-center gap-2">
          <button
            type="button"
            onClick={handleUndo}
            className="flex items-center gap-1 rounded bg-black/70 px-2 py-1 text-xs text-white hover:bg-black/80"
            aria-label="Undo last point"
          >
            <Undo2 className="h-3 w-3" />
            Undo
          </button>
        </div>
      )}

      {/* Drawing instructions */}
      {isDrawing && (
        <div className="pointer-events-none absolute bottom-2 left-2 rounded bg-black/70 px-2 py-1 text-xs text-white">
          {getInstructions()}
        </div>
      )}
    </div>
  );
}
