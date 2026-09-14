/**
 * Threat Detection Types for Weapon/Dangerous Object Detection
 *
 * This file contains types for two related but distinct threat systems:
 *
 * 1. ThreatDetection (NEM-5024) - Backend database model for storing threat records
 *    Uses: threat_type, severity, ThreatSummary
 *
 * 2. ThreatData (NEM-5025) - AI pipeline detection results for UI display
 *    Uses: class_name, is_high_priority, RecentThreat
 *
 * @see backend/models/enrichment.py ThreatDetection model
 * @see backend/services/threat_detection_loader.py ThreatDetection dataclass
 */

// ============================================================================
// NEM-5024: Threat Type Constants (Database Model)
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
// NEM-5025: Threat Detection Constants (AI Pipeline)
// ============================================================================

/**
 * High-priority threat classes that should trigger immediate alerts.
 * These correspond to firearms and bladed weapons.
 */
export const HIGH_PRIORITY_THREATS = new Set([
  'gun',
  'pistol',
  'rifle',
  'firearm',
  'handgun',
  'knife',
  'machete',
  'sword',
]);

/**
 * All known threat classes that the detection model may identify.
 */
export const THREAT_CLASSES = new Set([
  'knife',
  'gun',
  'pistol',
  'rifle',
  'bat',
  'baseball_bat',
  'crowbar',
  'machete',
  'sword',
  'hammer',
  'axe',
  'weapon',
  'firearm',
  'handgun',
]);

// ============================================================================
// NEM-5024: Threat Detection Data Structures (Database Model)
// ============================================================================

/**
 * A single threat detection result from the database.
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
// NEM-5025: Threat Data Structures (AI Pipeline / UI Components)
// ============================================================================

/**
 * Single threat detection from the AI pipeline.
 * Used by ThreatIndicator, ThreatBoundingBox components.
 *
 * Matches backend/services/threat_detection_loader.py::ThreatDetection
 */
export interface ThreatData {
  /** Detected threat class (e.g., "knife", "gun", "bat") */
  class_name: string;
  /** Detection confidence (0-1) */
  confidence: number;
  /** Whether this is a high-priority threat (firearms, bladed weapons) */
  is_high_priority: boolean;
  /** Optional bounding box as [x1, y1, x2, y2] */
  bbox?: [number, number, number, number];
}

/**
 * Complete result from threat/weapon detection.
 *
 * Matches backend/services/threat_detection_loader.py::ThreatDetectionResult
 */
export interface ThreatDetectionResult {
  /** List of detected threats */
  threats: ThreatData[];
  /** Whether any threats were detected */
  has_threats: boolean;
  /** Whether any high-priority threats were detected */
  has_high_priority: boolean;
  /** Highest confidence among detections */
  highest_confidence: number;
  /** Brief summary of detected threats (e.g., "1x gun, 2x knife") */
  threat_summary: string;
  /** Total number of threats detected */
  threat_count: number;
}

/**
 * Recent threat data for the RecentThreatsIndicator component.
 * Represents a simplified view of a threat event for display in the header widget.
 */
export interface RecentThreat {
  /** Unique identifier for this threat record */
  id: string;
  /** Associated event ID for navigation */
  eventId: string;
  /** Type of weapon/threat detected (e.g., "handgun", "rifle", "knife") */
  weaponType: string;
  /** Camera name where threat was detected */
  cameraName: string;
  /** ISO timestamp of when the threat was detected */
  timestamp: string;
  /** Detection confidence (0-1) */
  confidence: number;
  /** Optional thumbnail URL for the threat */
  thumbnailUrl?: string;
}

// ============================================================================
// NEM-5024: Severity Configuration
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
// NEM-5025: Priority Configuration (UI Components)
// ============================================================================

/**
 * Priority levels for threat display styling
 */
export type ThreatPriority = 'critical' | 'warning';

/**
 * Configuration for threat priority display
 */
export const THREAT_PRIORITY_CONFIG: Record<
  ThreatPriority,
  {
    label: string;
    bgColor: string;
    borderColor: string;
    textColor: string;
    iconTestId: string;
  }
> = {
  critical: {
    label: 'Critical',
    bgColor: 'bg-red-600',
    borderColor: 'border-red-800',
    textColor: 'text-white',
    iconTestId: 'critical-icon',
  },
  warning: {
    label: 'Warning',
    bgColor: 'bg-orange-500',
    borderColor: 'border-orange-700',
    textColor: 'text-white',
    iconTestId: 'warning-icon',
  },
};

// ============================================================================
// NEM-5024: Threat Type Configuration
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
 * Type guard to check if a value is a valid ThreatDetection (database model).
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

/**
 * Check if value is a valid ThreatData (AI pipeline)
 */
export function isThreatData(value: unknown): value is ThreatData {
  if (typeof value !== 'object' || value === null) return false;
  const obj = value as Record<string, unknown>;
  return (
    typeof obj.class_name === 'string' &&
    typeof obj.confidence === 'number' &&
    typeof obj.is_high_priority === 'boolean'
  );
}

/**
 * Check if value is a valid ThreatDetectionResult
 */
export function isThreatDetectionResult(value: unknown): value is ThreatDetectionResult {
  if (typeof value !== 'object' || value === null) return false;
  const obj = value as Record<string, unknown>;
  return (
    Array.isArray(obj.threats) &&
    typeof obj.has_threats === 'boolean' &&
    typeof obj.has_high_priority === 'boolean' &&
    typeof obj.highest_confidence === 'number' &&
    typeof obj.threat_summary === 'string' &&
    typeof obj.threat_count === 'number'
  );
}

// ============================================================================
// NEM-5024: Utility Functions
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
  return severities.reduce((max, current) => (compareSeverity(current, max) < 0 ? current : max));
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
  const affectedCameras = [
    ...new Set(threats.map((t) => t.camera_id).filter((id): id is string => Boolean(id))),
  ];

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

// ============================================================================
// NEM-5025: Utility Functions (UI Components)
// ============================================================================

/**
 * Get the priority configuration for a threat based on is_high_priority flag
 */
export function getThreatPriorityConfig(isHighPriority: boolean) {
  return isHighPriority ? THREAT_PRIORITY_CONFIG.critical : THREAT_PRIORITY_CONFIG.warning;
}

/**
 * Format a threat class name for display (uppercase, underscores to spaces)
 */
export function formatThreatClassName(className: string): string {
  return className.replace(/_/g, ' ').toUpperCase();
}

/**
 * Format confidence as a percentage string
 */
export function formatConfidencePercent(confidence: number): string {
  return `${Math.round(confidence * 100)}%`;
}

// ============================================================================
// NEM-5025: Recent Threats Hook Types
// ============================================================================

/**
 * Props for the RecentThreatsIndicator component
 */
export interface RecentThreatsIndicatorProps {
  /** Callback when a threat item is clicked, receives the event ID */
  onThreatClick?: (eventId: string) => void;
  /** Maximum number of threats to show in dropdown. Default: 5 */
  maxVisible?: number;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Return type for the useRecentThreats hook
 */
export interface UseRecentThreatsReturn {
  /** List of recent threats (filtered to last 24 hours) */
  threats: RecentThreat[];
  /** Total count of threats */
  count: number;
  /** Whether WebSocket is connected */
  isConnected: boolean;
  /** Flag indicating a new threat just arrived (for animation) */
  hasNewThreat: boolean;
  /** Clear the new threat flag */
  clearNewThreatFlag: () => void;
}

/**
 * Options for the useRecentThreats hook
 */
export interface UseRecentThreatsOptions {
  /** Callback when a new threat is received via WebSocket */
  onNewThreat?: (threat: RecentThreat) => void;
  /** Maximum age in hours for threats to include. Default: 24 */
  maxAgeHours?: number;
}
