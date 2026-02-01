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
