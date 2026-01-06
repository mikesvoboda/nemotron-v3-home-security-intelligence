/**
 * Enrichment data types for AI-powered detection enrichment.
 *
 * These types represent the additional AI analysis data computed by the backend
 * enrichment pipeline, including vehicle classification, pet identification,
 * person attributes, license plates, weather conditions, and image quality.
 *
 * All types include:
 * - Strict literal types for known values where applicable
 * - Nullable/optional handling for conditional enrichments
 * - Type guards for runtime validation
 *
 * @see backend/services/enrichment_service.py
 */

// ============================================================================
// Vehicle Enrichment
// ============================================================================

/**
 * Known vehicle types from the classification model.
 */
export const VEHICLE_TYPES = ['sedan', 'SUV', 'pickup', 'van', 'truck', 'motorcycle', 'bus', 'other'] as const;

/**
 * Vehicle type literal union.
 */
export type VehicleType = (typeof VEHICLE_TYPES)[number];

/**
 * Known vehicle damage types.
 */
export const VEHICLE_DAMAGE_TYPES = ['cracks', 'dents', 'glass_shatter', 'lamp_broken', 'scratches', 'tire_flat'] as const;

/**
 * Vehicle damage type literal union.
 */
export type VehicleDamageType = (typeof VEHICLE_DAMAGE_TYPES)[number];

/**
 * Vehicle enrichment data from AI classification.
 */
export interface VehicleEnrichment {
  /**
   * Vehicle type classification.
   * Known types are defined in VEHICLE_TYPES constant.
   * String type allows for future model additions.
   */
  type: string;
  /** Vehicle color */
  color: string;
  /**
   * Detected damage types (if any).
   * Known types are defined in VEHICLE_DAMAGE_TYPES constant.
   */
  damage?: string[];
  /** Whether the vehicle appears to be commercial */
  commercial?: boolean;
  /** Confidence score for the vehicle classification (0-1) */
  confidence: number;
}

// ============================================================================
// Pet Enrichment
// ============================================================================

/**
 * Known pet types.
 */
export const PET_TYPES = ['cat', 'dog'] as const;

/**
 * Pet type literal union.
 */
export type PetType = (typeof PET_TYPES)[number];

/**
 * Pet enrichment data from AI identification.
 */
export interface PetEnrichment {
  /** Pet type */
  type: PetType;
  /** Detected breed (if identifiable) */
  breed?: string;
  /** Confidence score for the pet identification (0-1) */
  confidence: number;
}

// ============================================================================
// Person Enrichment
// ============================================================================

/**
 * Known person actions/poses.
 */
export const PERSON_ACTIONS = ['walking', 'standing', 'crouching', 'running', 'sitting', 'lying_down'] as const;

/**
 * Person action literal union.
 */
export type PersonAction = (typeof PERSON_ACTIONS)[number];

/**
 * Known items a person might be carrying.
 */
export const CARRYING_ITEMS = ['backpack', 'package', 'bag', 'briefcase', 'suitcase', 'none'] as const;

/**
 * Carrying item literal union.
 */
export type CarryingItem = (typeof CARRYING_ITEMS)[number];

/**
 * Person enrichment data from AI analysis.
 */
export interface PersonEnrichment {
  /** Clothing description */
  clothing?: string;
  /**
   * Detected action/pose.
   * Known actions are defined in PERSON_ACTIONS constant.
   */
  action?: string;
  /**
   * Items being carried.
   * Known items are defined in CARRYING_ITEMS constant.
   */
  carrying?: string;
  /** Whether attire appears suspicious (masks, hoods at night, etc.) */
  suspicious_attire?: boolean;
  /** Whether person appears to be wearing a service uniform */
  service_uniform?: boolean;
  /** Confidence score for the person analysis (0-1) */
  confidence: number;
}

// ============================================================================
// License Plate Enrichment
// ============================================================================

/**
 * License plate enrichment data from OCR.
 */
export interface LicensePlateEnrichment {
  /** Detected license plate text */
  text: string;
  /** Confidence score for the OCR result (0-1) */
  confidence: number;
}

// ============================================================================
// Weather Enrichment
// ============================================================================

/**
 * Known weather conditions.
 */
export const WEATHER_CONDITIONS = ['clear', 'cloudy', 'rain', 'snow', 'fog', 'haze', 'night', 'dusk', 'dawn'] as const;

/**
 * Weather condition literal union.
 */
export type WeatherCondition = (typeof WEATHER_CONDITIONS)[number];

/**
 * Weather enrichment data from image analysis.
 */
export interface WeatherEnrichment {
  /**
   * Detected weather condition.
   * Known conditions are defined in WEATHER_CONDITIONS constant.
   */
  condition: string;
  /** Confidence score for the weather detection (0-1) */
  confidence: number;
}

// ============================================================================
// Image Quality Enrichment
// ============================================================================

/**
 * Known image quality issues.
 */
export const IMAGE_QUALITY_ISSUES = ['blur', 'low_light', 'overexposed', 'underexposed', 'noise', 'motion_blur', 'compression_artifacts'] as const;

/**
 * Image quality issue literal union.
 */
export type ImageQualityIssue = (typeof IMAGE_QUALITY_ISSUES)[number];

/**
 * Image quality enrichment data.
 */
export interface ImageQualityEnrichment {
  /** Quality score (0-1, where 1 is perfect quality) */
  score: number;
  /**
   * List of detected quality issues.
   * Known issues are defined in IMAGE_QUALITY_ISSUES constant.
   */
  issues: string[];
}

// ============================================================================
// Complete Enrichment Data
// ============================================================================

/**
 * Complete enrichment data for a detection.
 * All fields are optional as each enrichment type is computed conditionally
 * based on what is detected in the image.
 */
export interface EnrichmentData {
  /** Vehicle classification and attributes */
  vehicle?: VehicleEnrichment | null;
  /** Pet identification */
  pet?: PetEnrichment | null;
  /** Person attributes and behavior */
  person?: PersonEnrichment | null;
  /** License plate OCR result */
  license_plate?: LicensePlateEnrichment | null;
  /** Weather condition detection */
  weather?: WeatherEnrichment | null;
  /** Image quality assessment */
  image_quality?: ImageQualityEnrichment | null;
}

// ============================================================================
// Type Guards
// ============================================================================

/**
 * Type guard to check if a value has a valid confidence score (0-1).
 */
function hasValidConfidence(value: unknown): value is { confidence: number } {
  if (typeof value !== 'object' || value === null) return false;
  const obj = value as Record<string, unknown>;
  return typeof obj.confidence === 'number' && obj.confidence >= 0 && obj.confidence <= 1;
}

/**
 * Type guard for VehicleEnrichment.
 */
export function isVehicleEnrichment(value: unknown): value is VehicleEnrichment {
  if (!hasValidConfidence(value)) return false;
  const obj = value as Record<string, unknown>;
  return typeof obj.type === 'string' && typeof obj.color === 'string';
}

/**
 * Type guard for PetEnrichment.
 */
export function isPetEnrichment(value: unknown): value is PetEnrichment {
  if (!hasValidConfidence(value)) return false;
  const obj = value as Record<string, unknown>;
  return typeof obj.type === 'string' && (obj.type === 'cat' || obj.type === 'dog');
}

/**
 * Type guard for PersonEnrichment.
 */
export function isPersonEnrichment(value: unknown): value is PersonEnrichment {
  if (!hasValidConfidence(value)) return false;
  // PersonEnrichment has no required fields beyond confidence
  return true;
}

/**
 * Type guard for LicensePlateEnrichment.
 */
export function isLicensePlateEnrichment(value: unknown): value is LicensePlateEnrichment {
  if (!hasValidConfidence(value)) return false;
  const obj = value as Record<string, unknown>;
  return typeof obj.text === 'string';
}

/**
 * Type guard for WeatherEnrichment.
 */
export function isWeatherEnrichment(value: unknown): value is WeatherEnrichment {
  if (!hasValidConfidence(value)) return false;
  const obj = value as Record<string, unknown>;
  return typeof obj.condition === 'string';
}

/**
 * Type guard for ImageQualityEnrichment.
 */
export function isImageQualityEnrichment(value: unknown): value is ImageQualityEnrichment {
  if (typeof value !== 'object' || value === null) return false;
  const obj = value as Record<string, unknown>;
  return typeof obj.score === 'number' && Array.isArray(obj.issues);
}

/**
 * Type guard for EnrichmentData.
 */
export function isEnrichmentData(value: unknown): value is EnrichmentData {
  if (typeof value !== 'object' || value === null) return false;
  const obj = value as Record<string, unknown>;

  // All fields are optional, so we just check that present fields are valid
  if (obj.vehicle !== undefined && obj.vehicle !== null && !isVehicleEnrichment(obj.vehicle)) return false;
  if (obj.pet !== undefined && obj.pet !== null && !isPetEnrichment(obj.pet)) return false;
  if (obj.person !== undefined && obj.person !== null && !isPersonEnrichment(obj.person)) return false;
  if (obj.license_plate !== undefined && obj.license_plate !== null && !isLicensePlateEnrichment(obj.license_plate)) return false;
  if (obj.weather !== undefined && obj.weather !== null && !isWeatherEnrichment(obj.weather)) return false;
  if (obj.image_quality !== undefined && obj.image_quality !== null && !isImageQualityEnrichment(obj.image_quality)) return false;

  return true;
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Safely get a value from nullable/optional enrichment field.
 * Returns the value if present and valid, undefined otherwise.
 */
export function getEnrichmentValue<K extends keyof EnrichmentData>(
  data: EnrichmentData | null | undefined,
  key: K
): NonNullable<EnrichmentData[K]> | undefined {
  if (!data) return undefined;
  const value = data[key];
  if (value === null || value === undefined) return undefined;
  return value as NonNullable<EnrichmentData[K]>;
}

/**
 * Check if enrichment data has any non-null enrichments.
 */
export function hasAnyEnrichment(data: EnrichmentData | null | undefined): boolean {
  if (!data) return false;
  return Object.values(data).some((v) => v !== null && v !== undefined);
}

/**
 * Count the number of non-null enrichments in the data.
 */
export function countEnrichments(data: EnrichmentData | null | undefined): number {
  if (!data) return 0;
  return Object.values(data).filter((v) => v !== null && v !== undefined).length;
}
