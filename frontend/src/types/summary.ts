/**
 * Summary Types
 *
 * Types for event summary feature.
 *
 * Summaries are LLM-generated narrative descriptions of high/critical
 * security events, generated every 5 minutes by a background job.
 *
 * @see backend/api/schemas/summary.py - Backend Pydantic schemas
 * @see NEM-2894, NEM-2923
 */

// ============================================================================
// Enums
// ============================================================================

/**
 * Type of summary (matches backend SummaryType enum).
 */
export type SummaryType = 'hourly' | 'daily';

/**
 * Icon types for summary bullet points.
 */
export type BulletPointIcon = 'alert' | 'location' | 'pattern' | 'time' | 'weather';

// ============================================================================
// Response Types
// ============================================================================

/**
 * A bullet point in a summary with icon and optional severity.
 */
export interface SummaryBulletPoint {
  /** Icon type for the bullet point */
  icon: BulletPointIcon;

  /** Text content of the bullet point */
  text: string;

  /** Optional severity level for coloring (0-100) */
  severity?: number;
}

/**
 * A single summary response from the API.
 */
export interface Summary {
  /** Unique identifier */
  id: number;

  /** LLM-generated narrative content */
  content: string;

  /** Number of high/critical events included in this summary */
  eventCount: number;

  /** Start of the time window (ISO 8601 string) */
  windowStart: string;

  /** End of the time window (ISO 8601 string) */
  windowEnd: string;

  /** When this summary was generated (ISO 8601 string) */
  generatedAt: string;

  /** Maximum risk score among events in this summary (0-100, optional) */
  maxRiskScore?: number;

  /** Structured bullet points for display (optional, may not be provided by backend) */
  bulletPoints?: SummaryBulletPoint[];

  /** Focus areas identified in this summary (e.g., camera names) */
  focusAreas?: string[];

  /** Dominant patterns detected (e.g., "person", "vehicle") */
  dominantPatterns?: string[];

  /** Human-readable formatted time range (e.g., "2:00 PM - 3:00 PM") */
  timeRangeFormatted?: string;

  /** Weather conditions during the summary period (optional) */
  weatherConditions?: string;
}

/**
 * Response from GET /api/summaries/latest.
 */
export interface SummariesLatestResponse {
  /** Latest hourly summary (past 60 minutes), null if none exists */
  hourly: Summary | null;

  /** Latest daily summary (since midnight), null if none exists */
  daily: Summary | null;
}

// ============================================================================
// WebSocket Types
// ============================================================================

/**
 * WebSocket message for summary updates.
 */
export interface SummaryUpdateMessage {
  type: 'summary_update';
  data: SummariesLatestResponse;
}

// ============================================================================
// Component Props Types
// ============================================================================

/**
 * Props for the SummaryCard component.
 */
export interface SummaryCardProps {
  /** Type of summary to display */
  type: SummaryType;

  /** The summary data, or null if loading/unavailable */
  summary: Summary | null;

  /** Whether the summary is currently loading */
  isLoading?: boolean;

  /** Error message if fetch failed */
  error?: string | null;
}

// ============================================================================
// Hook Types
// ============================================================================

/**
 * Return type for useSummaries hook.
 */
export interface UseSummariesResult {
  /** Latest hourly summary */
  hourly: Summary | null;

  /** Latest daily summary */
  daily: Summary | null;

  /** Whether data is being fetched */
  isLoading: boolean;

  /** Error if fetch failed */
  error: Error | null;

  /** Manually trigger a refetch */
  refetch: () => Promise<void>;
}

// ============================================================================
// Type Guards
// ============================================================================

/**
 * Type guard for Summary objects.
 *
 * @example
 * ```ts
 * if (isSummary(data)) {
 *   // data is Summary
 *   console.log(data.content);
 * }
 * ```
 */
export function isSummary(obj: unknown): obj is Summary {
  return (
    typeof obj === 'object' &&
    obj !== null &&
    'id' in obj &&
    'content' in obj &&
    'eventCount' in obj &&
    'windowStart' in obj &&
    'windowEnd' in obj &&
    'generatedAt' in obj
  );
}

/**
 * Type guard for SummaryUpdateMessage WebSocket messages.
 *
 * @example
 * ```ts
 * if (isSummaryUpdateMessage(msg)) {
 *   // msg is SummaryUpdateMessage
 *   console.log(msg.data.hourly);
 * }
 * ```
 */
export function isSummaryUpdateMessage(msg: unknown): msg is SummaryUpdateMessage {
  return (
    typeof msg === 'object' &&
    msg !== null &&
    'type' in msg &&
    (msg as { type: string }).type === 'summary_update' &&
    'data' in msg
  );
}
