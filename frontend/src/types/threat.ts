/**
 * Threat Detection Types for Weapon/Dangerous Object Detection
 *
 * These types represent threat detection results from the AI pipeline's
 * threat detection model (Threat-Detection-YOLOv8n).
 *
 * NEM-5024: Phase 4 - Threat Detection Surfacing
 * @see backend/models/enrichment.py ThreatDetection model
 */

// ============================================================================
// Threat Type Constants
// ============================================================================

/**
 * Known threat types from the threat detection model.
 * Matches backend ThreatDetection model CHECK constraint.
 */
export const THREAT_TYPES = ['gun', 'knife', 'grenade', 'explosive', 'weapon', 'other'] as const;

/**
 * Threat type literal union.
 */
export type ThreatType = (typeof THREAT_TYPES)[number];

/**
 * Threat severity levels from the threat detection model.
 * Matches backend ThreatDetection model CHECK constraint.
 */
export const THREAT_SEVERITIES = ['critical', 'high', 'medium', 'low'] as const;

/**
 * Threat severity literal union.
 */
export type ThreatSeverity = (typeof THREAT_SEVERITIES)[number];

// ============================================================================
// Threat Detection Data Structures
// ============================================================================

/**
 * A single threat detection result.
 * Represents a detected weapon or dangerous object in an image.
 */
export interface ThreatDetection {
  /** Unique identifier for the threat detection record */
  id?: number;
  /** Type of threat detected (gun, knife, etc.) */
  threat_type: ThreatType;
  /** Detection confidence score (0-1) */
  confidence: number;
  /** Severity classification (critical, high, medium, low) */
  severity: ThreatSeverity;
  /** Bounding box coordinates [x1, y1, x2, y2] */
  bbox?: number[] | null;
  /** Camera ID where threat was detected */
  camera_id?: string;
  /** Event ID associated with this detection */
  event_id?: number;
  /** Detection ID from the AI pipeline */
  detection_id?: number;
  /** ISO timestamp when detected */
  created_at?: string;
}

/**
 * Aggregated threat summary for display.
 * Used by ThreatDetectionBanner to show consolidated threat information.
 */
export interface ThreatSummary {
  /** Whether any threats are currently active */
  hasActiveThreats: boolean;
  /** Total number of active threat detections */
  totalThreats: number;
  /** Highest severity level among all threats */
  maxSeverity: ThreatSeverity | null;
  /** List of individual threat detections */
  threats: ThreatDetection[];
  /** Count of critical severity threats */
  criticalCount: number;
  /** Count of high severity threats */
  highCount: number;
  /** Count of medium severity threats */
  mediumCount: number;
  /** Most recent threat detection */
  latestThreat?: ThreatDetection | null;
  /** List of unique threat types detected */
  threatTypes: string[];
  /** Camera IDs with active threats */
  affectedCameras: string[];
}

// ============================================================================
// Severity Configuration
// ============================================================================

/**
 * Visual configuration for threat severity levels.
 * Provides colors and labels for UI display.
 */
export interface ThreatSeverityConfig {
  /** Display label for the severity level */
  label: string;
  /** Icon to display */
  icon: 'AlertOctagon' | 'AlertTriangle' | 'AlertCircle' | 'Info';
  /** Background color class (Tailwind) */
  bgColor: string;
  /** Border color class (Tailwind) */
  borderColor: string;
  /** Text color class (Tailwind) */
  textColor: string;
  /** Animation class for emphasis */
  animationClass?: string;
}

/**
 * Configuration for each threat severity level.
 */
export const THREAT_SEVERITY_CONFIG: Record<ThreatSeverity, ThreatSeverityConfig> = {
  critical: {
    label: 'CRITICAL',
    icon: 'AlertOctagon',
    bgColor: 'bg-red-900/50',
    borderColor: 'border-red-500',
    textColor: 'text-red-400',
    animationClass: 'motion-safe:animate-pulse',
  },
  high: {
    label: 'HIGH',
    icon: 'AlertTriangle',
    bgColor: 'bg-orange-900/40',
    borderColor: 'border-orange-500',
    textColor: 'text-orange-400',
    animationClass: 'motion-safe:animate-pulse',
  },
  medium: {
    label: 'MEDIUM',
    icon: 'AlertCircle',
    bgColor: 'bg-yellow-900/30',
    borderColor: 'border-yellow-500',
    textColor: 'text-yellow-400',
    animationClass: undefined,
  },
  low: {
    label: 'LOW',
    icon: 'Info',
    bgColor: 'bg-gray-800/30',
    borderColor: 'border-gray-500',
    textColor: 'text-gray-400',
    animationClass: undefined,
  },
};

// ============================================================================
// Threat Type Configuration
// ============================================================================

/**
 * Human-readable labels for threat types.
 */
export const THREAT_TYPE_LABELS: Record<string, string> = {
  gun: 'Firearm',
  knife: 'Knife/Blade',
  grenade: 'Grenade',
  explosive: 'Explosive Device',
  weapon: 'Weapon',
  other: 'Unknown Threat',
};

/**
 * Get human-readable label for a threat type.
 */
export function getThreatTypeLabel(threatType: string): string {
  return THREAT_TYPE_LABELS[threatType] ?? threatType.charAt(0).toUpperCase() + threatType.slice(1);
}

// ============================================================================
// Type Guards
// ============================================================================

/**
 * Type guard to check if a value is a valid ThreatType.
 */
export function isThreatType(value: unknown): value is ThreatType {
  return typeof value === 'string' && THREAT_TYPES.includes(value as ThreatType);
}

/**
 * Type guard to check if a value is a valid ThreatSeverity.
 */
export function isThreatSeverity(value: unknown): value is ThreatSeverity {
  return typeof value === 'string' && THREAT_SEVERITIES.includes(value as ThreatSeverity);
}

/**
 * Type guard to check if a value is a valid ThreatDetection.
 */
export function isThreatDetection(value: unknown): value is ThreatDetection {
  if (typeof value !== 'object' || value === null) return false;
  const obj = value as Record<string, unknown>;
  return (
    typeof obj.threat_type === 'string' &&
    typeof obj.confidence === 'number' &&
    obj.confidence >= 0 &&
    obj.confidence <= 1 &&
    typeof obj.severity === 'string' &&
    THREAT_SEVERITIES.includes(obj.severity as ThreatSeverity)
  );
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Severity ordering for comparison (lower index = higher severity).
 */
export const SEVERITY_ORDER: Record<ThreatSeverity, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

/**
 * Compare two severity levels.
 * Returns negative if a is more severe, positive if b is more severe.
 */
export function compareSeverity(a: ThreatSeverity, b: ThreatSeverity): number {
  return SEVERITY_ORDER[a] - SEVERITY_ORDER[b];
}

/**
 * Get the maximum (most severe) severity from a list.
 */
export function getMaxSeverity(severities: ThreatSeverity[]): ThreatSeverity | null {
  if (severities.length === 0) return null;
  return severities.reduce((max, current) =>
    compareSeverity(current, max) < 0 ? current : max
  );
}

/**
 * Create an empty threat summary.
 */
export function createEmptyThreatSummary(): ThreatSummary {
  return {
    hasActiveThreats: false,
    totalThreats: 0,
    maxSeverity: null,
    threats: [],
    criticalCount: 0,
    highCount: 0,
    mediumCount: 0,
    latestThreat: null,
    threatTypes: [],
    affectedCameras: [],
  };
}

/**
 * Create a threat summary from a list of threat detections.
 */
export function createThreatSummary(threats: ThreatDetection[]): ThreatSummary {
  if (threats.length === 0) {
    return createEmptyThreatSummary();
  }

  const severities = threats.map((t) => t.severity);
  const uniqueThreatTypes = [...new Set(threats.map((t) => t.threat_type))];
  const affectedCameras = [...new Set(threats.map((t) => t.camera_id).filter((id): id is string => Boolean(id)))];

  // Sort threats by created_at (newest first) to find latest
  const sortedThreats = [...threats].sort((a, b) => {
    if (!a.created_at && !b.created_at) return 0;
    if (!a.created_at) return 1;
    if (!b.created_at) return -1;
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });

  return {
    hasActiveThreats: true,
    totalThreats: threats.length,
    maxSeverity: getMaxSeverity(severities),
    threats,
    criticalCount: threats.filter((t) => t.severity === 'critical').length,
    highCount: threats.filter((t) => t.severity === 'high').length,
    mediumCount: threats.filter((t) => t.severity === 'medium').length,
    latestThreat: sortedThreats[0] ?? null,
    threatTypes: uniqueThreatTypes,
    affectedCameras,
  };
}
