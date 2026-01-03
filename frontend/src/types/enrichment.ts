/**
 * Enrichment data types for AI-powered detection enrichment.
 *
 * These types represent the additional AI analysis data computed by the backend
 * enrichment pipeline, including vehicle classification, pet identification,
 * person attributes, license plates, weather conditions, and image quality.
 *
 * @see backend/services/enrichment_service.py
 */

/**
 * Vehicle enrichment data from AI classification.
 */
export interface VehicleEnrichment {
  /** Vehicle type classification */
  type: string; // sedan, SUV, pickup, van, truck
  /** Vehicle color */
  color: string;
  /** Detected damage types (if any) */
  damage?: string[]; // cracks, dents, glass_shatter, lamp_broken, scratches, tire_flat
  /** Whether the vehicle appears to be commercial */
  commercial?: boolean;
  /** Confidence score for the vehicle classification (0-1) */
  confidence: number;
}

/**
 * Pet enrichment data from AI identification.
 */
export interface PetEnrichment {
  /** Pet type */
  type: 'cat' | 'dog';
  /** Detected breed (if identifiable) */
  breed?: string;
  /** Confidence score for the pet identification (0-1) */
  confidence: number;
}

/**
 * Person enrichment data from AI analysis.
 */
export interface PersonEnrichment {
  /** Clothing description */
  clothing?: string;
  /** Detected action/pose */
  action?: string; // walking, standing, crouching
  /** Items being carried */
  carrying?: string; // backpack, package
  /** Whether attire appears suspicious (masks, hoods at night, etc.) */
  suspicious_attire?: boolean;
  /** Whether person appears to be wearing a service uniform */
  service_uniform?: boolean;
  /** Confidence score for the person analysis (0-1) */
  confidence: number;
}

/**
 * License plate enrichment data from OCR.
 */
export interface LicensePlateEnrichment {
  /** Detected license plate text */
  text: string;
  /** Confidence score for the OCR result (0-1) */
  confidence: number;
}

/**
 * Weather enrichment data from image analysis.
 */
export interface WeatherEnrichment {
  /** Detected weather condition (clear, rain, snow, fog, etc.) */
  condition: string;
  /** Confidence score for the weather detection (0-1) */
  confidence: number;
}

/**
 * Image quality enrichment data.
 */
export interface ImageQualityEnrichment {
  /** Quality score (0-1, where 1 is perfect quality) */
  score: number;
  /** List of detected quality issues */
  issues: string[]; // blur, low_light, overexposed, noise, etc.
}

/**
 * Complete enrichment data for a detection.
 * All fields are optional as each enrichment type is computed conditionally
 * based on what is detected in the image.
 */
export interface EnrichmentData {
  /** Vehicle classification and attributes */
  vehicle?: VehicleEnrichment;
  /** Pet identification */
  pet?: PetEnrichment;
  /** Person attributes and behavior */
  person?: PersonEnrichment;
  /** License plate OCR result */
  license_plate?: LicensePlateEnrichment;
  /** Weather condition detection */
  weather?: WeatherEnrichment;
  /** Image quality assessment */
  image_quality?: ImageQualityEnrichment;
}
