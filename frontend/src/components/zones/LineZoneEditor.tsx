/**
 * LineZoneEditor - Tripwire/line zone drawing component
 *
 * Component for drawing and displaying line zones (tripwires) on camera feeds.
 * Line zones are used for entry detection triggers when entities cross a virtual line.
 *
 * Features:
 * - Two-point line drawing (start and end)
 * - Line preview while drawing
 * - Direction indicator arrow
 * - Minimum line length enforcement
 * - Display of existing line zones
 * - Selection and interaction with existing lines
 * - Keyboard navigation (Escape to cancel)
 *
 * @module components/zones/LineZoneEditor
 * @see NEM-3720 Create frontend zone editor components
 */

import { clsx } from 'clsx';
import { useCallback, useEffect, useRef, useState } from 'react';

import type { Point } from './ZoneCanvas';

// ============================================================================
// Types
// ============================================================================

/**
 * Props for the LineZoneEditor component.
 */
export interface LineZoneEditorProps {
  /** URL for the camera snapshot background image */
  snapshotUrl: string;
  /** Whether the component is in drawing mode */
  isDrawing?: boolean;
  /** Color for the line being drawn */
  lineColor?: string;
  /** Whether to show direction indicator arrow */
  showDirection?: boolean;
  /** Existing line zones to display as [start, end] point pairs */
  existingLines?: [Point, Point][];
  /** Currently selected line index */
  selectedLineIndex?: number;
  /** Callback when line drawing is complete */
  onLineComplete?: (points: [Point, Point]) => void;
  /** Callback when drawing is cancelled */
  onCancel?: () => void;
  /** Callback when an existing line is selected */
  onLineSelect?: (index: number) => void;
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Constants
// ============================================================================

/** Minimum line length as fraction of container size (0-1) */
const MIN_LINE_LENGTH = 0.05;

/** Default line color */
const DEFAULT_LINE_COLOR = '#EF4444';

// ============================================================================
// Component
// ============================================================================

/**
 * LineZoneEditor component for drawing tripwire/line zones.
 *
 * Line zones are simple two-point zones used for detecting when
 * entities cross a boundary. Common use cases include entry/exit detection
 * at doorways or property boundaries.
 *
 * @param props - Component props
 * @returns Rendered LineZoneEditor component
 */
export default function LineZoneEditor({
  snapshotUrl,
  isDrawing = false,
  lineColor = DEFAULT_LINE_COLOR,
  showDirection = false,
  existingLines = [],
  selectedLineIndex,
  onLineComplete,
  onCancel,
  onLineSelect,
  className,
}: LineZoneEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 });
  const [imageLoaded, setImageLoaded] = useState(false);
  const [imageError, setImageError] = useState(false);

  // Drawing state
  const [startPoint, setStartPoint] = useState<Point | null>(null);
  const [currentMousePos, setCurrentMousePos] = useState<Point | null>(null);

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

  // Handle keyboard events
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isDrawing) {
        setStartPoint(null);
        setCurrentMousePos(null);
        onCancel?.();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isDrawing, onCancel]);

  // Reset state when drawing mode changes
  useEffect(() => {
    if (!isDrawing) {
      setStartPoint(null);
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

  /**
   * Calculate the distance between two points.
   */
  const getDistance = (p1: Point, p2: Point): number => {
    const dx = p2[0] - p1[0];
    const dy = p2[1] - p1[1];
    return Math.sqrt(dx * dx + dy * dy);
  };

  // ============================================================================
  // Event Handlers
  // ============================================================================

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (!isDrawing) return;
      e.preventDefault();

      const pos = getMousePos(e);

      if (!startPoint) {
        // First click - set start point
        setStartPoint(pos);
      } else {
        // Second click - check minimum length and complete
        const distance = getDistance(startPoint, pos);
        if (distance >= MIN_LINE_LENGTH) {
          onLineComplete?.([startPoint, pos]);
          setStartPoint(null);
          setCurrentMousePos(null);
        }
        // If too short, do nothing (user needs to click farther away)
      }
    },
    [isDrawing, startPoint, getMousePos, onLineComplete]
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!isDrawing) return;
      const pos = getMousePos(e);
      setCurrentMousePos(pos);
    },
    [isDrawing, getMousePos]
  );

  // ============================================================================
  // Render Functions
  // ============================================================================

  /**
   * Render an existing line.
   */
  const renderLine = (line: [Point, Point], index: number) => {
    const [start, end] = line;
    const [x1, y1] = normalizedToPixel(start[0], start[1]);
    const [x2, y2] = normalizedToPixel(end[0], end[1]);
    const isSelected = index === selectedLineIndex;

    return (
      <g key={index}>
        <line
          x1={x1}
          y1={y1}
          x2={x2}
          y2={y2}
          stroke={lineColor}
          strokeWidth={isSelected ? 4 : 3}
          strokeLinecap="round"
          className="cursor-pointer transition-all duration-200"
          onClick={() => onLineSelect?.(index)}
        />
        {/* Start point marker */}
        <circle cx={x1} cy={y1} r={6} fill={lineColor} stroke="white" strokeWidth={2} />
        {/* End point marker */}
        <circle cx={x2} cy={y2} r={6} fill={lineColor} stroke="white" strokeWidth={2} />
      </g>
    );
  };

  /**
   * Render the line preview while drawing.
   */
  const renderDrawingPreview = () => {
    if (!startPoint) return null;

    const [x1, y1] = normalizedToPixel(startPoint[0], startPoint[1]);
    const endPoint = currentMousePos || startPoint;
    const [x2, y2] = normalizedToPixel(endPoint[0], endPoint[1]);

    return (
      <g>
        {/* Line preview */}
        <line
          x1={x1}
          y1={y1}
          x2={x2}
          y2={y2}
          stroke={lineColor}
          strokeWidth={3}
          strokeLinecap="round"
          strokeDasharray="8,4"
          markerEnd={showDirection ? 'url(#arrowhead)' : undefined}
        />
        {/* Start point */}
        <circle cx={x1} cy={y1} r={6} fill={lineColor} stroke="white" strokeWidth={2} />
        {/* Current/end point */}
        {currentMousePos && (
          <circle cx={x2} cy={y2} r={6} fill={lineColor} stroke="white" strokeWidth={2} />
        )}
      </g>
    );
  };

  /**
   * Get instruction text based on drawing state.
   */
  const getInstructions = (): string => {
    if (!isDrawing) return '';
    if (!startPoint) {
      return 'Click to set the start point of the tripwire line';
    }
    return 'Click to set the end point. Press ESC to cancel.';
  };

  // ============================================================================
  // Render
  // ============================================================================

  return (
    // eslint-disable-next-line jsx-a11y/no-static-element-interactions -- Keyboard events handled via window.addEventListener for drawing canvas
    <div
      ref={containerRef}
      role={isDrawing ? 'application' : 'img'}
      aria-label={isDrawing ? 'Tripwire line drawing canvas - click to draw' : 'Camera tripwire lines view'}
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

      {/* SVG overlay for lines */}
      {imageLoaded && (
        <svg
          className="absolute inset-0 h-full w-full"
          style={{ pointerEvents: isDrawing ? 'none' : 'auto' }}
          data-testid="line-editor-svg"
        >
          {/* Defs for arrow marker */}
          {showDirection && (
            <defs>
              <marker
                id="arrowhead"
                markerWidth="10"
                markerHeight="7"
                refX="9"
                refY="3.5"
                orient="auto"
              >
                <polygon points="0 0, 10 3.5, 0 7" fill={lineColor} />
              </marker>
            </defs>
          )}

          {/* Only render line content when container has size */}
          {containerSize.width > 0 && (
            <>
              {/* Existing lines */}
              {existingLines.map((line, index) => renderLine(line, index))}

              {/* Drawing preview */}
              {isDrawing && renderDrawingPreview()}
            </>
          )}
        </svg>
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
