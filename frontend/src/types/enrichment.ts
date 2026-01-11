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
// Posture Enrichment (Legacy - simpler posture detection)
// ============================================================================

/**
 * Posture enrichment data from basic AI pose analysis.
 * Note: For detailed ViTPose analysis, see PoseEnrichment below.
 */
export interface PostureEnrichment {
  /** Detected posture classification */
  posture: string;
  /** Confidence score for the posture detection (0-1) */
  confidence: number;
}

/**
 * Check if a posture is considered high-risk for security purposes.
 * Works with both PostureEnrichment and PoseEnrichment postures.
 */
export function isHighRiskPosture(posture: string): boolean {
  const highRisk = ['crouching', 'lying_down', 'hands_raised', 'fighting_stance'];
  return highRisk.includes(posture);
}

/**
 * Get the risk level for a posture.
 * Returns 'alert' for high-security threats, 'warning' for concerning postures.
 */
export function getPostureRiskLevel(posture: string): 'alert' | 'warning' | 'normal' {
  if (posture === 'hands_raised' || posture === 'fighting_stance') {
    return 'alert';
  }
  if (posture === 'crouching' || posture === 'lying_down') {
    return 'warning';
  }
  return 'normal';
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
// Pose Enrichment (ViTPose)
// ============================================================================

/**
 * Known posture classifications from ViTPose.
 */
export const POSTURE_TYPES = ['standing', 'walking', 'running', 'sitting', 'crouching', 'lying_down', 'unknown'] as const;

/**
 * Posture type literal union.
 */
export type PostureType = (typeof POSTURE_TYPES)[number];

/**
 * Known pose security alerts that indicate potential threats.
 */
export const POSE_ALERTS = ['crouching', 'lying_down', 'hands_raised', 'fighting_stance'] as const;

/**
 * Pose alert type literal union.
 */
export type PoseAlert = (typeof POSE_ALERTS)[number];

/** Alias for backward compatibility */
export const SECURITY_ALERTS = POSE_ALERTS;
export type SecurityAlertType = PoseAlert;

/**
 * Keypoint data structure - each is [x, y, confidence].
 */
export type PoseKeypoint = [number, number, number];

/**
 * Pose enrichment data from ViTPose+ analysis.
 * Contains keypoints for skeleton overlay and security-relevant alerts.
 */
export interface PoseEnrichment {
  /**
   * Classified posture type.
   * Known types: standing, walking, running, sitting, crouching, lying_down, unknown.
   */
  posture: string;
  /**
   * Security-relevant pose alerts.
   * - crouching: Potential hiding/break-in attempt
   * - lying_down: Possible medical emergency
   * - hands_raised: Surrender/robbery situation
   * - fighting_stance: Aggressive posture
   */
  alerts: string[];
  /** Alias for alerts - for component compatibility */
  security_alerts?: string[];
  /**
   * Keypoints array in COCO 17 keypoint order.
   * Format: [[x, y, confidence], ...] where x and y are normalized (0-1).
   */
  keypoints: number[][];
  /** Number of detected keypoints */
  keypoint_count?: number;
  /** Overall confidence score for the pose detection (0-1) */
  confidence?: number;
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
  /** Posture/pose detection for security monitoring */
  posture?: PostureEnrichment | null;
  /** License plate OCR result */
  license_plate?: LicensePlateEnrichment | null;
  /** Weather condition detection */
  weather?: WeatherEnrichment | null;
  /** Image quality assessment */
  image_quality?: ImageQualityEnrichment | null;
  /** Pose analysis from ViTPose+ */
  pose?: PoseEnrichment | null;
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
 * Type guard for PostureEnrichment.
 */
export function isPostureEnrichment(value: unknown): value is PostureEnrichment {
  if (!hasValidConfidence(value)) return false;
  const obj = value as Record<string, unknown>;
  return typeof obj.posture === 'string';
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
 * Type guard for PoseEnrichment.
 */
export function isPoseEnrichment(value: unknown): value is PoseEnrichment {
  if (typeof value !== 'object' || value === null) return false;
  const obj = value as Record<string, unknown>;
  return (
    typeof obj.posture === 'string' &&
    Array.isArray(obj.alerts) &&
    Array.isArray(obj.keypoints)
  );
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
  if (obj.posture !== undefined && obj.posture !== null && !isPostureEnrichment(obj.posture)) return false;
  if (obj.license_plate !== undefined && obj.license_plate !== null && !isLicensePlateEnrichment(obj.license_plate)) return false;
  if (obj.weather !== undefined && obj.weather !== null && !isWeatherEnrichment(obj.weather)) return false;
  if (obj.image_quality !== undefined && obj.image_quality !== null && !isImageQualityEnrichment(obj.image_quality)) return false;
  if (obj.pose !== undefined && obj.pose !== null && !isPoseEnrichment(obj.pose)) return false;

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

// ============================================================================
// Enrichment Result Types with Strict Null Handling
// ============================================================================

/**
 * Result type for operations that may fail or return no data.
 * Provides a unified way to handle success, error, and empty states.
 */
export interface EnrichmentResult<T> {
  /** The data payload, null if error or not available */
  data: T | null;
  /** Error message if the operation failed, null otherwise */
  error: string | null;
  /** Whether the enrichment data is available */
  isAvailable: boolean;
}

/**
 * Type guard to check if an EnrichmentResult contains valid data.
 * Use this to narrow the type from EnrichmentResult<T> to { data: T }.
 *
 * @example
 * ```ts
 * const result: EnrichmentResult<VehicleEnrichment> = getVehicleEnrichment(data);
 * if (hasEnrichmentData(result)) {
 *   // result.data is now VehicleEnrichment, not VehicleEnrichment | null
 *   console.log(result.data.type);
 * }
 * ```
 */
export function hasEnrichmentData<T>(
  result: EnrichmentResult<T>
): result is EnrichmentResult<T> & { data: T; isAvailable: true; error: null } {
  return result.data !== null && result.isAvailable && result.error === null;
}

/**
 * Type guard to check if an EnrichmentResult contains an error.
 */
export function hasEnrichmentError<T>(
  result: EnrichmentResult<T>
): result is EnrichmentResult<T> & { data: null; error: string } {
  return result.error !== null;
}

/**
 * Create a successful EnrichmentResult with data.
 */
export function enrichmentSuccess<T>(data: T): EnrichmentResult<T> {
  return { data, error: null, isAvailable: true };
}

/**
 * Create a failed EnrichmentResult with an error message.
 */
export function enrichmentError<T>(error: string): EnrichmentResult<T> {
  return { data: null, error, isAvailable: false };
}

/**
 * Create an empty EnrichmentResult (no data, no error).
 */
export function enrichmentEmpty<T>(): EnrichmentResult<T> {
  return { data: null, error: null, isAvailable: false };
}

// ============================================================================
// Safe Accessor Functions with Default Values
// ============================================================================

/**
 * Safely get a string value from an enrichment field with a default.
 *
 * @param value - The value to extract, may be null/undefined
 * @param defaultValue - Default value if null/undefined (default: 'N/A')
 * @returns The string value or the default
 *
 * @example
 * ```ts
 * const description = getEnrichmentString(enrichment?.vehicle?.type, 'Unknown vehicle');
 * ```
 */
export function getEnrichmentString(
  value: string | null | undefined,
  defaultValue: string = 'N/A'
): string {
  return value ?? defaultValue;
}

/**
 * Safely get a number value from an enrichment field with a default.
 *
 * @param value - The value to extract, may be null/undefined
 * @param defaultValue - Default value if null/undefined (default: 0)
 * @returns The number value or the default
 *
 * @example
 * ```ts
 * const confidence = getEnrichmentNumber(enrichment?.vehicle?.confidence, 0);
 * ```
 */
export function getEnrichmentNumber(
  value: number | null | undefined,
  defaultValue: number = 0
): number {
  return value ?? defaultValue;
}

/**
 * Safely get an array value from an enrichment field with a default.
 *
 * @param value - The value to extract, may be null/undefined
 * @param defaultValue - Default value if null/undefined (default: [])
 * @returns The array value or the default
 *
 * @example
 * ```ts
 * const damageTypes = getEnrichmentArray(enrichment?.vehicle?.damage, []);
 * ```
 */
export function getEnrichmentArray<T>(
  value: T[] | null | undefined,
  defaultValue: T[] = []
): T[] {
  return value ?? defaultValue;
}

/**
 * Safely get a boolean value from an enrichment field with a default.
 *
 * @param value - The value to extract, may be null/undefined
 * @param defaultValue - Default value if null/undefined (default: false)
 * @returns The boolean value or the default
 *
 * @example
 * ```ts
 * const isCommercial = getEnrichmentBoolean(enrichment?.vehicle?.commercial, false);
 * ```
 */
export function getEnrichmentBoolean(
  value: boolean | null | undefined,
  defaultValue: boolean = false
): boolean {
  return value ?? defaultValue;
}

// ============================================================================
// Wrapped Enrichment Accessors
// ============================================================================

/**
 * Safely extract vehicle enrichment data from EnrichmentData.
 * Returns an EnrichmentResult with type guards for safe access.
 */
export function getVehicleEnrichmentResult(
  data: EnrichmentData | null | undefined
): EnrichmentResult<VehicleEnrichment> {
  if (!data) return enrichmentEmpty();
  const vehicle = data.vehicle;
  if (vehicle === null || vehicle === undefined) return enrichmentEmpty();
  if (!isVehicleEnrichment(vehicle)) {
    return enrichmentError('Invalid vehicle enrichment data');
  }
  return enrichmentSuccess(vehicle);
}

/**
 * Safely extract pet enrichment data from EnrichmentData.
 * Returns an EnrichmentResult with type guards for safe access.
 */
export function getPetEnrichmentResult(
  data: EnrichmentData | null | undefined
): EnrichmentResult<PetEnrichment> {
  if (!data) return enrichmentEmpty();
  const pet = data.pet;
  if (pet === null || pet === undefined) return enrichmentEmpty();
  if (!isPetEnrichment(pet)) {
    return enrichmentError('Invalid pet enrichment data');
  }
  return enrichmentSuccess(pet);
}

/**
 * Safely extract person enrichment data from EnrichmentData.
 * Returns an EnrichmentResult with type guards for safe access.
 */
export function getPersonEnrichmentResult(
  data: EnrichmentData | null | undefined
): EnrichmentResult<PersonEnrichment> {
  if (!data) return enrichmentEmpty();
  const person = data.person;
  if (person === null || person === undefined) return enrichmentEmpty();
  if (!isPersonEnrichment(person)) {
    return enrichmentError('Invalid person enrichment data');
  }
  return enrichmentSuccess(person);
}

/**
 * Safely extract posture enrichment data from EnrichmentData.
 * Returns an EnrichmentResult with type guards for safe access.
 */
export function getPostureEnrichmentResult(
  data: EnrichmentData | null | undefined
): EnrichmentResult<PostureEnrichment> {
  if (!data) return enrichmentEmpty();
  const posture = data.posture;
  if (posture === null || posture === undefined) return enrichmentEmpty();
  if (!isPostureEnrichment(posture)) {
    return enrichmentError('Invalid posture enrichment data');
  }
  return enrichmentSuccess(posture);
}

/**
 * Safely extract license plate enrichment data from EnrichmentData.
 * Returns an EnrichmentResult with type guards for safe access.
 */
export function getLicensePlateEnrichmentResult(
  data: EnrichmentData | null | undefined
): EnrichmentResult<LicensePlateEnrichment> {
  if (!data) return enrichmentEmpty();
  const plate = data.license_plate;
  if (plate === null || plate === undefined) return enrichmentEmpty();
  if (!isLicensePlateEnrichment(plate)) {
    return enrichmentError('Invalid license plate enrichment data');
  }
  return enrichmentSuccess(plate);
}

/**
 * Safely extract weather enrichment data from EnrichmentData.
 * Returns an EnrichmentResult with type guards for safe access.
 */
export function getWeatherEnrichmentResult(
  data: EnrichmentData | null | undefined
): EnrichmentResult<WeatherEnrichment> {
  if (!data) return enrichmentEmpty();
  const weather = data.weather;
  if (weather === null || weather === undefined) return enrichmentEmpty();
  if (!isWeatherEnrichment(weather)) {
    return enrichmentError('Invalid weather enrichment data');
  }
  return enrichmentSuccess(weather);
}

/**
 * Safely extract image quality enrichment data from EnrichmentData.
 * Returns an EnrichmentResult with type guards for safe access.
 */
export function getImageQualityEnrichmentResult(
  data: EnrichmentData | null | undefined
): EnrichmentResult<ImageQualityEnrichment> {
  if (!data) return enrichmentEmpty();
  const quality = data.image_quality;
  if (quality === null || quality === undefined) return enrichmentEmpty();
  if (!isImageQualityEnrichment(quality)) {
    return enrichmentError('Invalid image quality enrichment data');
  }
  return enrichmentSuccess(quality);
}

/**
 * Safely extract pose enrichment data from EnrichmentData.
 * Returns an EnrichmentResult with type guards for safe access.
 */
export function getPoseEnrichmentResult(
  data: EnrichmentData | null | undefined
): EnrichmentResult<PoseEnrichment> {
  if (!data) return enrichmentEmpty();
  const pose = data.pose;
  if (pose === null || pose === undefined) return enrichmentEmpty();
  if (!isPoseEnrichment(pose)) {
    return enrichmentError('Invalid pose enrichment data');
  }
  return enrichmentSuccess(pose);
}
