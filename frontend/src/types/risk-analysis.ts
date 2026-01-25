/**
 * Advanced Risk Analysis Types (NEM-3601)
 *
 * Types for capturing rich structured data from Nemotron LLM analysis.
 * These types match the backend schemas defined in backend/api/schemas/llm_response.py
 */

// ============================================================================
// Literal Types
// ============================================================================

/**
 * Threat level for entities identified in analysis
 */
export type ThreatLevel = 'low' | 'medium' | 'high';

/**
 * Severity level for risk flags
 */
export type FlagSeverity = 'warning' | 'alert' | 'critical';

/**
 * Detection quality assessment
 */
export type DetectionQuality = 'good' | 'fair' | 'poor';

/**
 * Weather impact on detection accuracy
 */
export type WeatherImpact = 'none' | 'minor' | 'significant';

/**
 * Completeness of enrichment data
 */
export type EnrichmentCoverage = 'full' | 'partial' | 'minimal';

// ============================================================================
// Interfaces
// ============================================================================

/**
 * Entity identified during risk analysis
 *
 * Entities represent objects of interest detected in the scene that
 * contribute to the overall risk assessment (e.g., people, vehicles, packages).
 */
export interface RiskEntity {
  /** Category of entity (e.g., "person", "vehicle", "package") */
  type: string;
  /** Detailed description of the entity */
  description: string;
  /** Risk level attributed to this entity */
  threat_level: ThreatLevel;
}

/**
 * Risk flag indicating a specific concern or anomaly
 *
 * Flags represent specific behaviors, patterns, or conditions that
 * warrant attention (e.g., loitering, nighttime activity, weapon detected).
 */
export interface RiskFlag {
  /** Category of flag (e.g., "loitering", "weapon_detected") */
  type: string;
  /** Explanation of the flag */
  description: string;
  /** Severity level of this flag */
  severity: FlagSeverity;
}

/**
 * Factors affecting confidence in the risk analysis
 *
 * These factors help explain the reliability of the risk assessment
 * and can be used to understand when additional review may be needed.
 */
export interface ConfidenceFactors {
  /** Quality of the detection data */
  detection_quality: DetectionQuality;
  /** Impact of weather conditions on detection accuracy */
  weather_impact: WeatherImpact;
  /** Completeness of enrichment data available */
  enrichment_coverage: EnrichmentCoverage;
}

/**
 * Advanced risk analysis data from event response
 *
 * These fields are optional and may be null for older events
 * created before NEM-3601 was implemented.
 */
export interface AdvancedRiskAnalysis {
  /** Entities identified in the analysis (people, vehicles, objects) */
  entities: RiskEntity[];
  /** Risk flags raised during analysis */
  flags: RiskFlag[];
  /** Suggested action based on the analysis */
  recommended_action: string | null;
  /** Factors affecting confidence in the analysis */
  confidence_factors: ConfidenceFactors | null;
}

// ============================================================================
// Type Guards
// ============================================================================

/**
 * Check if value is a valid ThreatLevel
 */
export function isThreatLevel(value: unknown): value is ThreatLevel {
  return value === 'low' || value === 'medium' || value === 'high';
}

/**
 * Check if value is a valid FlagSeverity
 */
export function isFlagSeverity(value: unknown): value is FlagSeverity {
  return value === 'warning' || value === 'alert' || value === 'critical';
}

/**
 * Check if value is a valid RiskEntity
 */
export function isRiskEntity(value: unknown): value is RiskEntity {
  if (typeof value !== 'object' || value === null) return false;
  const obj = value as Record<string, unknown>;
  return (
    typeof obj.type === 'string' &&
    typeof obj.description === 'string' &&
    isThreatLevel(obj.threat_level)
  );
}

/**
 * Check if value is a valid RiskFlag
 */
export function isRiskFlag(value: unknown): value is RiskFlag {
  if (typeof value !== 'object' || value === null) return false;
  const obj = value as Record<string, unknown>;
  return (
    typeof obj.type === 'string' &&
    typeof obj.description === 'string' &&
    isFlagSeverity(obj.severity)
  );
}

/**
 * Check if value is a valid ConfidenceFactors
 */
export function isConfidenceFactors(value: unknown): value is ConfidenceFactors {
  if (typeof value !== 'object' || value === null) return false;
  const obj = value as Record<string, unknown>;
  return (
    (obj.detection_quality === 'good' ||
      obj.detection_quality === 'fair' ||
      obj.detection_quality === 'poor') &&
    (obj.weather_impact === 'none' ||
      obj.weather_impact === 'minor' ||
      obj.weather_impact === 'significant') &&
    (obj.enrichment_coverage === 'full' ||
      obj.enrichment_coverage === 'partial' ||
      obj.enrichment_coverage === 'minimal')
  );
}

// ============================================================================
// Configuration
// ============================================================================

/**
 * Configuration for threat level display
 */
export const THREAT_LEVEL_CONFIG: Record<
  ThreatLevel,
  { label: string; color: string; bgColor: string; borderColor: string }
> = {
  low: {
    label: 'Low',
    color: 'text-green-400',
    bgColor: 'bg-green-500/20',
    borderColor: 'border-green-500/40',
  },
  medium: {
    label: 'Medium',
    color: 'text-yellow-400',
    bgColor: 'bg-yellow-500/20',
    borderColor: 'border-yellow-500/40',
  },
  high: {
    label: 'High',
    color: 'text-red-400',
    bgColor: 'bg-red-500/20',
    borderColor: 'border-red-500/40',
  },
};

/**
 * Configuration for flag severity display
 */
export const FLAG_SEVERITY_CONFIG: Record<
  FlagSeverity,
  { label: string; color: string; bgColor: string; borderColor: string; icon: string }
> = {
  warning: {
    label: 'Warning',
    color: 'text-yellow-400',
    bgColor: 'bg-yellow-500/20',
    borderColor: 'border-yellow-500/40',
    icon: 'AlertTriangle',
  },
  alert: {
    label: 'Alert',
    color: 'text-orange-400',
    bgColor: 'bg-orange-500/20',
    borderColor: 'border-orange-500/40',
    icon: 'AlertCircle',
  },
  critical: {
    label: 'Critical',
    color: 'text-red-400',
    bgColor: 'bg-red-500/20',
    borderColor: 'border-red-500/40',
    icon: 'XCircle',
  },
};

/**
 * Configuration for confidence factor display
 */
export const CONFIDENCE_FACTOR_CONFIG = {
  detection_quality: {
    label: 'Detection Quality',
    values: {
      good: { label: 'Good', color: 'text-green-400' },
      fair: { label: 'Fair', color: 'text-yellow-400' },
      poor: { label: 'Poor', color: 'text-red-400' },
    },
  },
  weather_impact: {
    label: 'Weather Impact',
    values: {
      none: { label: 'None', color: 'text-green-400' },
      minor: { label: 'Minor', color: 'text-yellow-400' },
      significant: { label: 'Significant', color: 'text-red-400' },
    },
  },
  enrichment_coverage: {
    label: 'Enrichment Coverage',
    values: {
      full: { label: 'Full', color: 'text-green-400' },
      partial: { label: 'Partial', color: 'text-yellow-400' },
      minimal: { label: 'Minimal', color: 'text-red-400' },
    },
  },
} as const;
