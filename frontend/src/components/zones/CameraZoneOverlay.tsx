/**
 * CameraZoneOverlay - SVG overlay for camera video feeds with zone visualization
 *
 * This component renders zone polygons on top of camera video feeds, providing
 * real-time zone intelligence visualization including:
 * - Zone boundary polygons with configurable colors
 * - Heatmap mode showing activity levels
 * - Presence indicators showing household members in zones
 * - Alert badges for active zone anomalies
 * - Interactive selection and hover effects
 *
 * Coordinates are normalized (0-1 range) and transformed to video dimensions.
 *
 * @module components/zones/CameraZoneOverlay
 * @see NEM-3202 Phase 5.3 - Camera View Zone Overlay
 *
 * @example
 * ```tsx
 * <div className="relative">
 *   <video src={cameraFeed} />
 *   <CameraZoneOverlay
 *     cameraId="cam-1"
 *     videoWidth={1920}
 *     videoHeight={1080}
 *     mode="heatmap"
 *     onZoneClick={(zoneId) => console.log('Selected:', zoneId)}
 *     showLabels
 *     showPresence
 *     showAlerts
 *   />
 * </div>
 * ```
 */

import { clsx } from 'clsx';
import { useCallback, useMemo, useState } from 'react';

import { useZoneAnomalies } from '../../hooks/useZoneAnomalies';
import { useZonePresence } from '../../hooks/useZonePresence';
import { useZonesQuery } from '../../hooks/useZones';

import type { Zone } from '../../types/generated';

// ============================================================================
// Types
// ============================================================================

/**
 * Display modes for the zone overlay.
 * - draw: Interactive mode for zone editing (no special visualization)
 * - heatmap: Color zones by activity level
 * - presence: Show presence indicators in zones
 * - alerts: Highlight zones with active alerts
 */
export type OverlayMode = 'draw' | 'heatmap' | 'presence' | 'alerts';

/**
 * Props for the CameraZoneOverlay component.
 */
export interface CameraZoneOverlayProps {
  /** Camera ID to fetch zones for */
  cameraId: string;
  /** Video/container width in pixels */
  videoWidth: number;
  /** Video/container height in pixels */
  videoHeight: number;
  /** Display mode for the overlay */
  mode?: OverlayMode;
  /** Currently selected zone ID */
  selectedZoneId?: string;
  /** Callback when a zone is clicked */
  onZoneClick?: (zoneId: string) => void;
  /** Callback when a zone is hovered (null on mouse leave) */
  onZoneHover?: (zoneId: string | null) => void;
  /** Whether to show zone name labels */
  showLabels?: boolean;
  /** Whether to show presence indicators */
  showPresence?: boolean;
  /** Whether to show alert badges */
  showAlerts?: boolean;
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Transform normalized coordinates (0-1) to pixel coordinates.
 */
function normalizedToPixel(
  coord: [number, number],
  width: number,
  height: number
): [number, number] {
  return [coord[0] * width, coord[1] * height];
}

/**
 * Calculate the centroid of a polygon for label/badge positioning.
 */
function calculateCentroid(
  coordinates: Array<[number, number]>,
  width: number,
  height: number
): [number, number] {
  if (coordinates.length === 0) {
    return [0, 0];
  }

  const sum = coordinates.reduce(
    (acc, coord) => {
      const [x, y] = normalizedToPixel(coord, width, height);
      return [acc[0] + x, acc[1] + y] as [number, number];
    },
    [0, 0] as [number, number]
  );

  return [sum[0] / coordinates.length, sum[1] / coordinates.length];
}

/**
 * Convert coordinates array to SVG polygon points string.
 */
function coordinatesToPoints(
  coordinates: Array<[number, number]>,
  width: number,
  height: number
): string {
  return coordinates
    .map((coord) => {
      const [x, y] = normalizedToPixel(coord, width, height);
      return `${x},${y}`;
    })
    .join(' ');
}

/**
 * Get fill opacity based on activity level (priority as a proxy for activity).
 */
function getActivityOpacity(priority: number, mode: OverlayMode): number {
  if (mode !== 'heatmap') {
    return 0.25;
  }
  // Priority ranges from 0-100, map to 0.2-0.6 opacity
  const normalizedPriority = Math.min(100, Math.max(0, priority));
  return 0.2 + (normalizedPriority / 100) * 0.4;
}

/**
 * Get heatmap color based on activity level.
 */
function getHeatmapColor(priority: number): string {
  // Low activity: green, medium: yellow, high: red
  if (priority < 33) {
    return '#22C55E'; // green
  } else if (priority < 66) {
    return '#EAB308'; // yellow
  }
  return '#EF4444'; // red
}

// ============================================================================
// Subcomponents
// ============================================================================

/**
 * Zone polygon with interactive features.
 */
interface ZonePolygonProps {
  zone: Zone;
  width: number;
  height: number;
  mode: OverlayMode;
  isSelected: boolean;
  isHovered: boolean;
  onClick?: () => void;
  onMouseEnter?: () => void;
  onMouseLeave?: () => void;
  onKeyDown?: (e: React.KeyboardEvent) => void;
}

function ZonePolygon({
  zone,
  width,
  height,
  mode,
  isSelected,
  isHovered,
  onClick,
  onMouseEnter,
  onMouseLeave,
  onKeyDown,
}: ZonePolygonProps) {
  // Skip rendering if no coordinates
  if (!zone.coordinates || zone.coordinates.length === 0) {
    return null;
  }

  const points = coordinatesToPoints(
    zone.coordinates as Array<[number, number]>,
    width,
    height
  );

  const fillColor = mode === 'heatmap' ? getHeatmapColor(zone.priority) : zone.color;
  const fillOpacity = getActivityOpacity(zone.priority, mode);
  const strokeWidth = isSelected ? 3 : isHovered ? 2.5 : 2;

  return (
    <polygon
      data-testid={`zone-polygon-${zone.id}`}
      points={points}
      fill={fillColor}
      fillOpacity={isSelected ? fillOpacity + 0.15 : fillOpacity}
      stroke={zone.color}
      strokeWidth={strokeWidth}
      strokeDasharray={zone.enabled ? undefined : '8,4'}
      className={clsx(
        'cursor-pointer transition-all duration-200',
        isSelected && 'selected',
        isHovered && 'hovered'
      )}
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      onKeyDown={onKeyDown}
    />
  );
}

/**
 * Zone label text element.
 */
interface ZoneLabelProps {
  zone: Zone;
  width: number;
  height: number;
}

function ZoneLabel({ zone, width, height }: ZoneLabelProps) {
  if (!zone.coordinates || zone.coordinates.length === 0) {
    return null;
  }

  const [cx, cy] = calculateCentroid(
    zone.coordinates as Array<[number, number]>,
    width,
    height
  );

  return (
    <text
      x={cx}
      y={cy}
      fill="white"
      fontSize="14"
      fontWeight="600"
      textAnchor="middle"
      dominantBaseline="middle"
      className="pointer-events-none select-none"
      style={{
        textShadow: '0 1px 2px rgba(0,0,0,0.8), 0 0 4px rgba(0,0,0,0.5)',
      }}
    >
      {zone.name}
    </text>
  );
}

/**
 * Presence indicator badge showing number of people in zone.
 */
interface PresenceBadgeProps {
  zoneId: string;
  width: number;
  height: number;
  coordinates: Array<[number, number]>;
}

function PresenceBadge({ zoneId, width, height, coordinates }: PresenceBadgeProps) {
  const { presentCount, isActive } = useZonePresenceForBadge(zoneId);

  if (presentCount === 0) {
    return null;
  }

  const [cx, cy] = calculateCentroid(coordinates, width, height);
  const badgeRadius = 14;
  const badgeX = cx + 20;
  const badgeY = cy - 20;

  return (
    <g data-testid={`zone-presence-${zoneId}`}>
      {/* Background circle */}
      <circle
        cx={badgeX}
        cy={badgeY}
        r={badgeRadius}
        fill="#3B82F6"
        className={clsx(isActive && 'animate-pulse')}
      />
      {/* Icon placeholder (using text for now) */}
      <text
        x={badgeX}
        y={badgeY}
        fill="white"
        fontSize="12"
        fontWeight="bold"
        textAnchor="middle"
        dominantBaseline="middle"
        className="pointer-events-none select-none"
      >
        {presentCount}
      </text>
    </g>
  );
}

/**
 * Custom hook for presence badge to avoid hook rules violation.
 */
function useZonePresenceForBadge(zoneId: string) {
  const { presentCount, activeCount } = useZonePresence(zoneId);
  return { presentCount, isActive: activeCount > 0 };
}

/**
 * Alert badge showing number of active anomalies in zone.
 */
interface AlertBadgeProps {
  zoneId: string;
  width: number;
  height: number;
  coordinates: Array<[number, number]>;
  anomalyCount: number;
}

function AlertBadge({
  zoneId,
  width,
  height,
  coordinates,
  anomalyCount,
}: AlertBadgeProps) {
  if (anomalyCount === 0) {
    return null;
  }

  const [cx, cy] = calculateCentroid(coordinates, width, height);
  const badgeRadius = 14;
  const badgeX = cx - 20;
  const badgeY = cy - 20;

  return (
    <g data-testid={`zone-alert-${zoneId}`} className="animate-pulse">
      {/* Background circle with warning color */}
      <circle cx={badgeX} cy={badgeY} r={badgeRadius} fill="#EF4444" />
      {/* Count text */}
      <text
        x={badgeX}
        y={badgeY}
        fill="white"
        fontSize="12"
        fontWeight="bold"
        textAnchor="middle"
        dominantBaseline="middle"
        className="pointer-events-none select-none"
      >
        {anomalyCount}
      </text>
    </g>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * CameraZoneOverlay component.
 *
 * Renders an SVG overlay on top of camera video feeds showing zone boundaries
 * with real-time intelligence visualization.
 *
 * @param props - Component props
 * @returns Rendered SVG overlay
 */
export default function CameraZoneOverlay({
  cameraId,
  videoWidth,
  videoHeight,
  mode = 'draw',
  selectedZoneId,
  onZoneClick,
  onZoneHover,
  showLabels = true,
  showPresence = false,
  showAlerts = false,
  className,
}: CameraZoneOverlayProps) {
  // State for hover tracking
  const [hoveredZoneId, setHoveredZoneId] = useState<string | null>(null);

  // Fetch zones for this camera
  const { zones } = useZonesQuery(cameraId, {
    enabledFilter: undefined, // Get all zones including disabled
  });

  // Fetch anomalies for alert badges
  const { anomalies } = useZoneAnomalies({
    enabled: showAlerts,
    unacknowledgedOnly: true,
  });

  // Group anomalies by zone ID for quick lookup
  const anomaliesByZone = useMemo(() => {
    const map = new Map<string, number>();
    anomalies.forEach((anomaly) => {
      const count = map.get(anomaly.zone_id) ?? 0;
      map.set(anomaly.zone_id, count + 1);
    });
    return map;
  }, [anomalies]);

  // Event handlers
  const handleZoneClick = useCallback(
    (zoneId: string) => {
      onZoneClick?.(zoneId);
    },
    [onZoneClick]
  );

  const handleZoneMouseEnter = useCallback(
    (zoneId: string) => {
      setHoveredZoneId(zoneId);
      onZoneHover?.(zoneId);
    },
    [onZoneHover]
  );

  const handleZoneMouseLeave = useCallback(() => {
    setHoveredZoneId(null);
    onZoneHover?.(null);
  }, [onZoneHover]);

  const handleZoneKeyDown = useCallback(
    (zoneId: string, e: React.KeyboardEvent) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        onZoneClick?.(zoneId);
      }
    },
    [onZoneClick]
  );

  // Filter out zones with no coordinates
  const validZones = useMemo(
    () => zones.filter((zone) => zone.coordinates && zone.coordinates.length > 0),
    [zones]
  );

  return (
    <svg
      data-testid="camera-zone-overlay"
      viewBox={`0 0 ${videoWidth} ${videoHeight}`}
      width="100%"
      height="100%"
      className={clsx(
        'absolute inset-0 pointer-events-auto',
        mode === 'draw' && 'mode-draw cursor-crosshair',
        mode === 'heatmap' && 'mode-heatmap',
        mode === 'presence' && 'mode-presence',
        mode === 'alerts' && 'mode-alerts',
        className
      )}
      aria-label="Camera zone overlay"
      role="img"
      style={{ overflow: 'visible' }}
    >
      {/* Defs for filters and gradients */}
      <defs>
        <filter id="zone-glow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="2" result="coloredBlur" />
          <feMerge>
            <feMergeNode in="coloredBlur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Zone groups */}
      {validZones.map((zone) => {
        const isSelected = zone.id === selectedZoneId;
        const isHovered = zone.id === hoveredZoneId;
        const anomalyCount = anomaliesByZone.get(zone.id) ?? 0;

        return (
          <g
            key={zone.id}
            data-testid={`zone-group-${zone.id}`}
            aria-label={`Zone: ${zone.name}`}
            aria-disabled={!zone.enabled}
            tabIndex={0}
            role="button"
            onFocus={() => handleZoneMouseEnter(zone.id)}
            onBlur={handleZoneMouseLeave}
            onKeyDown={(e) => handleZoneKeyDown(zone.id, e)}
            filter={isSelected || isHovered ? 'url(#zone-glow)' : undefined}
          >
            {/* Zone polygon */}
            <ZonePolygon
              zone={zone}
              width={videoWidth}
              height={videoHeight}
              mode={mode}
              isSelected={isSelected}
              isHovered={isHovered}
              onClick={() => handleZoneClick(zone.id)}
              onMouseEnter={() => handleZoneMouseEnter(zone.id)}
              onMouseLeave={handleZoneMouseLeave}
            />

            {/* Zone label */}
            {showLabels && (
              <ZoneLabel zone={zone} width={videoWidth} height={videoHeight} />
            )}

            {/* Presence badge */}
            {showPresence && mode === 'presence' && (
              <PresenceBadge
                zoneId={zone.id}
                width={videoWidth}
                height={videoHeight}
                coordinates={zone.coordinates as Array<[number, number]>}
              />
            )}

            {/* Alert badge */}
            {showAlerts && anomalyCount > 0 && (
              <AlertBadge
                zoneId={zone.id}
                width={videoWidth}
                height={videoHeight}
                coordinates={zone.coordinates as Array<[number, number]>}
                anomalyCount={anomalyCount}
              />
            )}
          </g>
        );
      })}
    </svg>
  );
}
