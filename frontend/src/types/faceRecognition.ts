/**
 * Face Recognition Type Definitions
 *
 * Types for face recognition API endpoints including known persons management,
 * face embeddings, face detection events, and person appearance tracking.
 *
 * @module types/faceRecognition
 * @see docs/plans/2025-01-31-face-recognition-ui-design.md
 */

// ============================================================================
// Face Quality Assessment Types (NEM-4953)
// ============================================================================

/**
 * Individual quality factor assessment.
 * Each factor is scored 0-1 where 1 is best quality.
 */
export interface QualityFactor {
  /** Score for this factor (0-1, higher is better) */
  score: number;
  /** Human-readable label for the factor */
  label: string;
  /** Status indicator based on score thresholds */
  status: 'good' | 'fair' | 'poor';
  /** Recommendation to improve this factor if not good */
  recommendation?: string;
}

/**
 * Quality factors breakdown for face enrollment.
 * Provides detailed assessment of face image quality.
 */
export interface QualityFactors {
  /** Sharpness/blur assessment - higher means sharper */
  blur: QualityFactor;
  /** Lighting/exposure assessment - higher means better lit */
  lighting: QualityFactor;
  /** Face angle/pose assessment - higher means more frontal */
  angle: QualityFactor;
  /** Face occlusion assessment - higher means less occluded */
  occlusion: QualityFactor;
}

/**
 * Complete face quality assessment response.
 * Includes overall score and factor breakdown.
 */
export interface FaceQualityAssessment {
  /** Overall quality score (0-1) */
  overall_score: number;
  /** Whether the face passes minimum quality threshold for enrollment */
  is_enrollable: boolean;
  /** Quality factors breakdown */
  factors: QualityFactors;
  /** Overall recommendation if quality is not optimal */
  recommendation?: string;
}

/**
 * Compute quality factors from an overall quality score.
 * Used when backend only provides overall score.
 *
 * @param overallScore - Overall quality score (0-1)
 * @returns Quality factors with estimated breakdown
 */
export function computeQualityFactorsFromScore(overallScore: number): QualityFactors {
  // Simulate factor breakdown based on overall score
  // In production, backend would provide actual factors
  const getStatus = (score: number): 'good' | 'fair' | 'poor' => {
    if (score >= 0.8) return 'good';
    if (score >= 0.6) return 'fair';
    return 'poor';
  };

  const getRecommendation = (
    factor: string,
    score: number
  ): string | undefined => {
    if (score >= 0.8) return undefined;
    const recommendations: Record<string, string> = {
      blur: 'Hold the camera steady or improve lighting for a sharper image',
      lighting: 'Face towards a light source or move to a better-lit area',
      angle: 'Look directly at the camera with face fully visible',
      occlusion:
        'Remove glasses, hats, or other items covering your face',
    };
    return recommendations[factor];
  };

  // Distribute overall score across factors with slight variation
  const variance = 0.1;
  const blurScore = Math.max(0, Math.min(1, overallScore + (Math.random() - 0.5) * variance));
  const lightingScore = Math.max(0, Math.min(1, overallScore + (Math.random() - 0.5) * variance));
  const angleScore = Math.max(0, Math.min(1, overallScore + (Math.random() - 0.5) * variance));
  const occlusionScore = Math.max(0, Math.min(1, overallScore + (Math.random() - 0.5) * variance));

  return {
    blur: {
      score: blurScore,
      label: 'Sharpness',
      status: getStatus(blurScore),
      recommendation: getRecommendation('blur', blurScore),
    },
    lighting: {
      score: lightingScore,
      label: 'Lighting',
      status: getStatus(lightingScore),
      recommendation: getRecommendation('lighting', lightingScore),
    },
    angle: {
      score: angleScore,
      label: 'Face Angle',
      status: getStatus(angleScore),
      recommendation: getRecommendation('angle', angleScore),
    },
    occlusion: {
      score: occlusionScore,
      label: 'Visibility',
      status: getStatus(occlusionScore),
      recommendation: getRecommendation('occlusion', occlusionScore),
    },
  };
}

/**
 * Get status from a quality score.
 */
export function getQualityStatus(score: number): 'good' | 'fair' | 'poor' {
  if (score >= 0.8) return 'good';
  if (score >= 0.7) return 'fair';
  return 'poor';
}

/**
 * Check if a quality score is enrollable (meets minimum threshold).
 */
export function isQualityEnrollable(score: number): boolean {
  return score >= 0.7;
}

/**
 * Get overall recommendation based on quality score and factors.
 */
export function getOverallRecommendation(
  score: number,
  factors?: QualityFactors
): string | undefined {
  if (score >= 0.8) return undefined;

  if (score < 0.7) {
    return 'Image quality is too low for enrollment. Please try again with better lighting and a clearer view of your face.';
  }

  // Score is 0.7-0.8 (fair)
  if (factors) {
    // Find the worst factor
    const factorEntries = Object.entries(factors) as [keyof QualityFactors, QualityFactor][];
    const worstFactor = factorEntries.reduce((worst, [, factor]) =>
      factor.score < worst.score ? factor : worst
    , factorEntries[0][1]);

    if (worstFactor.recommendation) {
      return worstFactor.recommendation;
    }
  }

  return 'Recognition accuracy may be reduced. Consider capturing a clearer image.';
}

// ============================================================================
// Known Person Types
// ============================================================================

/**
 * A known person in the face recognition database.
 * Can optionally be linked to a household member.
 */
export interface KnownPerson {
  /** Unique identifier */
  id: number;
  /** Display name of the person */
  name: string;
  /** Whether this person is a household member */
  is_household_member: boolean;
  /** Optional notes about the person */
  notes?: string | null;
  /** When the person was created */
  created_at: string;
  /** When the person was last updated */
  updated_at: string;
  /** Number of face embeddings enrolled for this person */
  embedding_count: number;
  /** Optional linked household member ID */
  household_member_id?: number | null;
}

/**
 * Request payload for creating a known person.
 */
export interface KnownPersonCreate {
  /** Display name of the person */
  name: string;
  /** Whether this person is a household member */
  is_household_member?: boolean;
  /** Optional notes about the person */
  notes?: string | null;
  /** Optional linked household member ID */
  household_member_id?: number | null;
}

/**
 * Request payload for updating a known person.
 */
export interface KnownPersonUpdate {
  /** Display name of the person */
  name?: string | null;
  /** Whether this person is a household member */
  is_household_member?: boolean | null;
  /** Optional notes about the person */
  notes?: string | null;
  /** Optional linked household member ID */
  household_member_id?: number | null;
}

// ============================================================================
// Face Embedding Types
// ============================================================================

/**
 * A face embedding stored for a known person.
 * Multiple embeddings per person improves recognition accuracy.
 */
export interface FaceEmbedding {
  /** Unique identifier */
  id: number;
  /** ID of the associated known person */
  person_id: number;
  /** Quality score of the face image (0-1) */
  quality_score: number;
  /** Path to the source image used for this embedding */
  source_image_path?: string | null;
  /** When the embedding was created */
  created_at: string;
}

/**
 * Request payload for enrolling a face from an existing detection.
 */
export interface EnrollFaceRequest {
  /** ID of the detection to extract face from */
  detection_id: string;
}

/**
 * Response from face enrollment.
 */
export interface EnrollFaceResponse {
  /** Whether enrollment was successful */
  success: boolean;
  /** ID of the created embedding */
  embedding_id: number;
  /** Quality score of the enrolled face */
  quality_score: number;
  /** Optional message (e.g., quality warning) */
  message?: string;
}

// ============================================================================
// Face Detection Event Types
// ============================================================================

/**
 * Bounding box coordinates as [x, y, width, height].
 */
export type BoundingBox = [number, number, number, number];

/**
 * A face detection event from the video analytics pipeline.
 */
export interface FaceDetectionEvent {
  /** Unique identifier */
  id: number;
  /** ID of the camera that captured the face */
  camera_id: number;
  /** Display name of the camera */
  camera_name: string;
  /** When the face was detected */
  timestamp: string;
  /** Bounding box of the face in the frame [x, y, width, height] */
  bbox: BoundingBox;
  /** ID of matched known person, if any */
  matched_person_id?: number | null;
  /** Name of matched known person, if any */
  matched_person_name?: string | null;
  /** Match confidence score (0-1) */
  match_confidence?: number | null;
  /** Whether this face is from an unknown person */
  is_unknown: boolean;
  /** Quality score of the detected face (0-1) */
  quality_score: number;
  /** URL to the face thumbnail image */
  thumbnail_url?: string | null;
  /** ID of the associated detection record */
  detection_id?: string | null;
  /** ID of the associated event */
  event_id?: number | null;
}

/**
 * Filter options for querying face events.
 */
export interface FaceEventsFilter {
  /** Filter by camera ID */
  camera_id?: number;
  /** Filter by known person ID */
  person_id?: number;
  /** Filter unknown faces only */
  unknown_only?: boolean;
  /** Start date (ISO format) */
  start_date?: string;
  /** End date (ISO format) */
  end_date?: string;
  /** Minimum quality score */
  min_quality?: number;
  /** Cursor for pagination */
  cursor?: string;
  /** Number of items per page */
  limit?: number;
}

/**
 * Paginated response for face events.
 */
export interface FaceEventsResponse {
  /** List of face events */
  items: FaceDetectionEvent[];
  /** Cursor for next page, null if no more pages */
  next_cursor: string | null;
  /** Total count of matching events */
  total: number;
}

/**
 * Request payload for manually identifying a face event as a known person.
 */
export interface IdentifyFaceRequest {
  /** ID of the known person to associate */
  known_person_id: number;
  /** Whether to also create an embedding from this face */
  create_embedding?: boolean;
}

/**
 * Response from face identification.
 */
export interface IdentifyFaceResponse {
  /** Whether identification was successful */
  success: boolean;
  /** Whether a new embedding was created */
  created_embedding: boolean;
  /** Optional message */
  message?: string;
}

// ============================================================================
// Face Statistics Types
// ============================================================================

/**
 * Camera-specific face detection statistics.
 */
export interface CameraFaceStats {
  /** Total face detections for this camera */
  total: number;
  /** Number of known person detections */
  known: number;
  /** Number of unknown person detections */
  unknown: number;
}

/**
 * Aggregated face detection statistics.
 */
export interface FaceStats {
  /** Total face detections today */
  total_today: number;
  /** Number of known person detections today */
  known_count: number;
  /** Number of unknown person detections today */
  unknown_count: number;
  /** Statistics broken down by camera */
  by_camera: Record<string, CameraFaceStats>;
  /** Number of unique known persons detected today */
  unique_known_persons?: number;
  /** Number of unique unknown faces today */
  unique_unknown_faces?: number;
}

// ============================================================================
// Person Appearance Types
// ============================================================================

/**
 * A single appearance of a known person at a camera.
 */
export interface PersonAppearance {
  /** When the person was detected */
  timestamp: string;
  /** ID of the camera */
  camera_id: number;
  /** Display name of the camera */
  camera_name: string;
  /** ID of the detection record */
  detection_id: string;
  /** Match confidence score (0-1) */
  confidence: number;
  /** URL to the thumbnail image */
  thumbnail_url?: string | null;
  /** ID of the associated event */
  event_id?: number | null;
}

/**
 * Date range filter for appearances.
 */
export interface DateRange {
  /** Start date (ISO format) */
  start_date: string;
  /** End date (ISO format) */
  end_date: string;
}

/**
 * Filter options for querying person appearances.
 */
export interface AppearancesFilter {
  /** Start date (ISO format) */
  start_date?: string;
  /** End date (ISO format) */
  end_date?: string;
  /** Filter by camera ID */
  camera_id?: number;
  /** Number of items per page */
  limit?: number;
  /** Offset for pagination */
  offset?: number;
}

/**
 * Response for person appearances query.
 */
export interface PersonAppearancesResponse {
  /** List of appearances */
  appearances: PersonAppearance[];
  /** Total count of appearances in the date range */
  total: number;
}

// ============================================================================
// Unknown Stranger Types
// ============================================================================

/**
 * Summary of unknown stranger detections.
 */
export interface UnknownStrangerSummary {
  /** List of recent unknown face events */
  items: FaceDetectionEvent[];
  /** Total count of unknown faces in the query period */
  total: number;
  /** Whether there are more items */
  has_more: boolean;
}

// ============================================================================
// Bulk Enrollment Types (NEM-4954)
// ============================================================================

/**
 * Result for a single image in bulk enrollment.
 */
export interface BulkEnrollmentImageResult {
  /** Original filename of the uploaded image */
  filename: string;
  /** Whether enrollment succeeded for this image */
  success: boolean;
  /** ID of created embedding if successful */
  embedding_id: number | null;
  /** Quality score of detected face */
  quality_score: number | null;
  /** Error message if enrollment failed */
  error: string | null;
}

/**
 * Request payload for bulk face enrollment.
 */
export interface BulkEnrollmentRequest {
  /** Files to upload */
  images: File[];
  /** ID of existing person to enroll to (optional) */
  person_id?: number;
  /** Name for new person if creating (optional) */
  new_person_name?: string;
  /** Whether new person is a household member */
  is_household_member?: boolean;
}

/**
 * Response from bulk enrollment.
 */
export interface BulkEnrollmentResponse {
  /** Total number of images submitted */
  total_images: number;
  /** Number of successful enrollments */
  successful: number;
  /** Number of failed enrollments */
  failed: number;
  /** Per-image enrollment results */
  results: BulkEnrollmentImageResult[];
  /** ID of the person images were enrolled to */
  person_id: number;
  /** Name of the person */
  person_name: string;
  /** Whether a new person was created */
  created_new_person: boolean;
}
