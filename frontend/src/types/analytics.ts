/**
 * Analytics types for the frontend.
 *
 * These types match the backend Pydantic schemas in backend/api/schemas/analytics.py.
 *
 * @see backend/api/schemas/analytics.py - Backend schema definitions
 * @see backend/api/routes/analytics.py - API endpoints
 */

// ============================================================================
// Detection Trends Types
// ============================================================================

/**
 * A single data point in the detection trend response.
 * Represents detection count for a specific date.
 */
export interface DetectionTrendDataPoint {
  /** Date in ISO format (YYYY-MM-DD) */
  date: string;
  /** Number of detections on this date */
  count: number;
}

/**
 * Response from GET /api/analytics/detection-trends endpoint.
 * Contains daily detection counts for a date range.
 */
export interface DetectionTrendsResponse {
  /** Detection counts aggregated by day */
  data_points: DetectionTrendDataPoint[];
  /** Total detections in the date range */
  total_detections: number;
  /** Start date of the range (ISO format) */
  start_date: string;
  /** End date of the range (ISO format) */
  end_date: string;
}

/**
 * Query parameters for the detection trends endpoint.
 */
export interface DetectionTrendsParams {
  /** Start date in ISO format (YYYY-MM-DD) */
  start_date: string;
  /** End date in ISO format (YYYY-MM-DD) */
  end_date: string;
}

// ============================================================================
// Risk History Types
// ============================================================================

/**
 * A single data point in the risk history response.
 * Represents event counts by risk level for a specific date.
 */
export interface RiskHistoryDataPoint {
  /** Date in ISO format (YYYY-MM-DD) */
  date: string;
  /** Count of low risk events */
  low: number;
  /** Count of medium risk events */
  medium: number;
  /** Count of high risk events */
  high: number;
  /** Count of critical risk events */
  critical: number;
}

/**
 * Response from GET /api/analytics/risk-history endpoint.
 */
export interface RiskHistoryResponse {
  /** Risk level counts aggregated by day */
  data_points: RiskHistoryDataPoint[];
  /** Start date of the range (ISO format) */
  start_date: string;
  /** End date of the range (ISO format) */
  end_date: string;
}

/**
 * Query parameters for the risk history endpoint.
 */
export interface RiskHistoryQueryParams {
  /** Start date in ISO format (YYYY-MM-DD) */
  start_date: string;
  /** End date in ISO format (YYYY-MM-DD) */
  end_date: string;
}

// ============================================================================
// Camera Uptime Types
// ============================================================================

/**
 * Uptime data for a single camera.
 */
export interface CameraUptimeDataPoint {
  /** Camera ID */
  camera_id: string;
  /** Camera name */
  camera_name: string;
  /** Uptime percentage (0-100) */
  uptime_percentage: number;
  /** Total detections in date range */
  detection_count: number;
}

/**
 * Response from GET /api/analytics/camera-uptime endpoint.
 */
export interface CameraUptimeResponse {
  /** Uptime data per camera */
  cameras: CameraUptimeDataPoint[];
  /** Start date of the range (ISO format) */
  start_date: string;
  /** End date of the range (ISO format) */
  end_date: string;
}

// ============================================================================
// Object Distribution Types
// ============================================================================

/**
 * Detection count for a single object type.
 */
export interface ObjectDistributionDataPoint {
  /** Object type (e.g., 'person', 'car') */
  object_type: string;
  /** Number of detections for this object type */
  count: number;
  /** Percentage of total detections (0-100) */
  percentage: number;
}

/**
 * Response from GET /api/analytics/object-distribution endpoint.
 */
export interface ObjectDistributionResponse {
  /** Detection counts by object type */
  object_types: ObjectDistributionDataPoint[];
  /** Total detections in date range */
  total_detections: number;
  /** Start date of the range (ISO format) */
  start_date: string;
  /** End date of the range (ISO format) */
  end_date: string;
}

// ============================================================================
// Risk Score Distribution Types (NEM-3602)
// ============================================================================

/**
 * A single bucket in the risk score distribution histogram.
 */
export interface RiskScoreDistributionBucket {
  /** Minimum score in this bucket (inclusive) */
  min_score: number;
  /** Maximum score in this bucket (exclusive, except last bucket includes 100) */
  max_score: number;
  /** Number of events in this bucket */
  count: number;
}

/**
 * Response from GET /api/analytics/risk-score-distribution endpoint.
 */
export interface RiskScoreDistributionResponse {
  /** Risk score distribution buckets */
  buckets: RiskScoreDistributionBucket[];
  /** Total events with risk scores in date range */
  total_events: number;
  /** Start date of the range (ISO format) */
  start_date: string;
  /** End date of the range (ISO format) */
  end_date: string;
  /** Size of each bucket */
  bucket_size: number;
}

/**
 * Query parameters for the risk score distribution endpoint.
 */
export interface RiskScoreDistributionParams {
  /** Start date in ISO format (YYYY-MM-DD) */
  start_date: string;
  /** End date in ISO format (YYYY-MM-DD) */
  end_date: string;
  /** Size of each bucket (default: 10) */
  bucket_size?: number;
}

// ============================================================================
// Risk Score Trends Types (NEM-3602)
// ============================================================================

/**
 * A single data point in the risk score trends response.
 * Represents average risk score for a specific date.
 */
export interface RiskScoreTrendDataPoint {
  /** Date in ISO format (YYYY-MM-DD) */
  date: string;
  /** Average risk score on this date */
  avg_score: number;
  /** Number of events on this date */
  count: number;
}

/**
 * Response from GET /api/analytics/risk-score-trends endpoint.
 */
export interface RiskScoreTrendsResponse {
  /** Average risk score aggregated by day */
  data_points: RiskScoreTrendDataPoint[];
  /** Start date of the range (ISO format) */
  start_date: string;
  /** End date of the range (ISO format) */
  end_date: string;
}

/**
 * Query parameters for the risk score trends endpoint.
 */
export interface RiskScoreTrendsParams {
  /** Start date in ISO format (YYYY-MM-DD) */
  start_date: string;
  /** End date in ISO format (YYYY-MM-DD) */
  end_date: string;
}
