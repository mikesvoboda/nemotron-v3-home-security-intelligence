/**
 * Plate Read types for License Plate Recognition (LPR/ALPR) UI.
 *
 * These types match the backend Pydantic schemas in backend/api/schemas/plate_read.py.
 *
 * @see backend/api/schemas/plate_read.py - Backend schema definitions
 * @see backend/api/routes/plate_reads.py - API endpoints
 */

// ============================================================================
// Core Types
// ============================================================================

/**
 * Bounding box coordinates for plate detection.
 * Coordinates are in pixel space relative to the source image.
 */
export interface BoundingBox {
  /** Left edge X coordinate */
  x1: number;
  /** Top edge Y coordinate */
  y1: number;
  /** Right edge X coordinate */
  x2: number;
  /** Bottom edge Y coordinate */
  y2: number;
}

/**
 * A single plate read record from the ALPR system.
 * Represents a license plate detection with OCR results and quality metrics.
 */
export interface PlateRead {
  /** Database record ID */
  id: number;
  /** Camera ID where plate was detected */
  camera_id: string;
  /** Detection timestamp (ISO 8601 format) */
  timestamp: string;
  /** Recognized plate text (alphanumeric only) */
  plate_text: string;
  /** Raw OCR output before filtering */
  raw_text: string;
  /** Plate detection confidence (0-1) */
  detection_confidence: number;
  /** Text recognition confidence (0-1) */
  ocr_confidence: number;
  /** Bounding box [x1, y1, x2, y2] in pixel coordinates */
  bbox: [number, number, number, number];
  /** Image quality assessment score (0-1) */
  image_quality_score: number;
  /** Whether low-light enhancement was applied */
  is_enhanced: boolean;
  /** Whether motion blur was detected */
  is_blurry: boolean;
  /** Record creation timestamp (ISO 8601 format) */
  created_at: string;
}

// ============================================================================
// Response Types
// ============================================================================

/**
 * Paginated list of plate reads.
 * Standard pagination envelope for plate read list endpoints.
 */
export interface PlateReadListResponse {
  /** List of plate reads */
  plate_reads: PlateRead[];
  /** Total number of plate reads matching query */
  total: number;
  /** Current page number (1-indexed) */
  page: number;
  /** Number of items per page */
  page_size: number;
}

/**
 * Statistics for plate recognition performance and activity.
 * Aggregated metrics for monitoring ALPR system health and usage.
 */
export interface PlateStatisticsResponse {
  /** Total number of plate reads */
  total_reads: number;
  /** Count of unique plate texts */
  unique_plates: number;
  /** Average OCR confidence (0-1) */
  avg_ocr_confidence: number;
  /** Average image quality score (0-1) */
  avg_quality_score: number;
  /** Number of reads with low-light enhancement */
  enhanced_count: number;
  /** Number of reads with motion blur */
  blurry_count: number;
  /** Reads in the last hour */
  reads_last_hour: number;
  /** Reads in the last 24 hours */
  reads_last_24h: number;
}

// ============================================================================
// Request Parameter Types
// ============================================================================

/**
 * Search parameters for plate text search.
 * Used with the /plate-reads/search endpoint.
 */
export interface PlateSearchParams {
  /** Plate text to search for (partial match unless exact=true) */
  text: string;
  /** If true, match exact plate text only */
  exact?: boolean;
  /** Page number (1-indexed, default: 1) */
  page?: number;
  /** Number of items per page (default: 50, max: 1000) */
  page_size?: number;
}

/**
 * Filter parameters for plate read listing.
 * Used with the /plate-reads endpoint.
 */
export interface PlateReadFilters {
  /** Filter by camera ID */
  camera_id?: string;
  /** Filter by start time (ISO 8601 format) */
  start_time?: string;
  /** Filter by end time (ISO 8601 format) */
  end_time?: string;
  /** Minimum OCR confidence threshold (0-1) */
  min_confidence?: number;
  /** Page number (1-indexed, default: 1) */
  page?: number;
  /** Number of items per page (default: 50, max: 1000) */
  page_size?: number;
}

// ============================================================================
// Recognition Types (for manual recognition requests)
// ============================================================================

/**
 * Request payload for plate recognition from image data.
 * Used for the /recognize endpoint.
 */
export interface PlateRecognizeRequest {
  /** Camera ID for the source image */
  camera_id: string;
  /** Base64-encoded image data (JPEG or PNG) */
  image_base64: string;
  /** Optional bounding box for plate region [x1, y1, x2, y2] */
  detection_bbox?: [number, number, number, number] | null;
  /** Detection confidence from upstream detector (default: 1.0) */
  detection_confidence?: number;
}

/**
 * Response from plate recognition request.
 * Returns recognized plate text and confidence metrics.
 */
export interface PlateRecognizeResponse {
  /** Recognized plate text (alphanumeric only) */
  plate_text: string;
  /** Raw OCR output before filtering */
  raw_text: string;
  /** OCR confidence (0-1) */
  ocr_confidence: number;
  /** Image quality score (0-1) */
  image_quality_score: number;
  /** Whether low-light enhancement was applied */
  is_enhanced: boolean;
  /** Whether motion blur was detected */
  is_blurry: boolean;
  /** Whether the read was stored in database */
  stored: boolean;
  /** Database ID if stored (null if not stored) */
  plate_read_id: number | null;
}

// ============================================================================
// Utility Types
// ============================================================================

/**
 * Sort options for plate reads listing.
 */
export type PlateReadSortField =
  | 'timestamp'
  | 'plate_text'
  | 'ocr_confidence'
  | 'detection_confidence'
  | 'image_quality_score';

/**
 * Sort direction for plate reads listing.
 */
export type SortDirection = 'asc' | 'desc';

/**
 * Extended filter parameters including sorting.
 */
export interface PlateReadQueryParams extends PlateReadFilters {
  /** Field to sort by */
  sort_by?: PlateReadSortField;
  /** Sort direction */
  sort_direction?: SortDirection;
}

// ============================================================================
// Type Guards
// ============================================================================

/**
 * Type guard to check if a value is a valid PlateRead object.
 */
export function isPlateRead(value: unknown): value is PlateRead {
  if (typeof value !== 'object' || value === null) {
    return false;
  }
  const obj = value as Record<string, unknown>;
  return (
    typeof obj.id === 'number' &&
    typeof obj.camera_id === 'string' &&
    typeof obj.timestamp === 'string' &&
    typeof obj.plate_text === 'string' &&
    typeof obj.raw_text === 'string' &&
    typeof obj.detection_confidence === 'number' &&
    typeof obj.ocr_confidence === 'number' &&
    Array.isArray(obj.bbox) &&
    obj.bbox.length === 4 &&
    typeof obj.image_quality_score === 'number' &&
    typeof obj.is_enhanced === 'boolean' &&
    typeof obj.is_blurry === 'boolean' &&
    typeof obj.created_at === 'string'
  );
}

/**
 * Type guard to check if a value is a valid PlateStatisticsResponse.
 */
export function isPlateStatisticsResponse(value: unknown): value is PlateStatisticsResponse {
  if (typeof value !== 'object' || value === null) {
    return false;
  }
  const obj = value as Record<string, unknown>;
  return (
    typeof obj.total_reads === 'number' &&
    typeof obj.unique_plates === 'number' &&
    typeof obj.avg_ocr_confidence === 'number' &&
    typeof obj.avg_quality_score === 'number' &&
    typeof obj.enhanced_count === 'number' &&
    typeof obj.blurry_count === 'number' &&
    typeof obj.reads_last_hour === 'number' &&
    typeof obj.reads_last_24h === 'number'
  );
}

// ============================================================================
// Formatting Utilities
// ============================================================================

/**
 * Format a confidence value as a percentage string.
 * @param confidence - Confidence value (0-1)
 * @returns Formatted percentage string (e.g., "95.2%")
 */
export function formatConfidence(confidence: number): string {
  return `${(confidence * 100).toFixed(1)}%`;
}

/**
 * Get a human-readable quality label based on the quality score.
 * @param score - Quality score (0-1)
 * @returns Quality label
 */
export function getQualityLabel(score: number): 'Excellent' | 'Good' | 'Fair' | 'Poor' {
  if (score >= 0.9) return 'Excellent';
  if (score >= 0.7) return 'Good';
  if (score >= 0.5) return 'Fair';
  return 'Poor';
}

/**
 * Get confidence level category.
 * @param confidence - Confidence value (0-1)
 * @returns Confidence level category
 */
export function getConfidenceLevel(confidence: number): 'high' | 'medium' | 'low' {
  if (confidence >= 0.85) return 'high';
  if (confidence >= 0.65) return 'medium';
  return 'low';
}
