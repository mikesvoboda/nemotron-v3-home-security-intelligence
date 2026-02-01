/**
 * Plate Reads API Client for License Plate Recognition endpoints.
 *
 * Provides typed fetch wrappers for plate read REST endpoints including
 * listing, searching, statistics, and individual plate read retrieval.
 *
 * @see backend/api/routes/plate_reads.py - Backend implementation
 * @see backend/api/schemas/plate_read.py - Backend Pydantic schemas
 */

import type {
  PlateRead,
  PlateReadFilters,
  PlateReadListResponse,
  PlateSearchParams,
  PlateStatisticsResponse,
} from '../types/plateRead';

// ============================================================================
// Configuration
// ============================================================================

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '';
const API_KEY = import.meta.env.VITE_API_KEY as string | undefined;

// ============================================================================
// Error Handling
// ============================================================================

/**
 * Custom error class for Plate Reads API failures.
 * Includes HTTP status code and parsed error data.
 */
export class PlateReadsApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public data?: unknown
  ) {
    super(message);
    this.name = 'PlateReadsApiError';
  }
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Build headers with optional API key authentication.
 */
function buildHeaders(): HeadersInit {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (API_KEY) {
    headers['X-API-Key'] = API_KEY;
  }
  return headers;
}

/**
 * Handle API response with proper error handling.
 * Parses error details from FastAPI response format.
 */
async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
    let errorData: unknown = undefined;

    try {
      const errorBody: unknown = await response.json();
      if (typeof errorBody === 'object' && errorBody !== null && 'detail' in errorBody) {
        errorMessage = String((errorBody as { detail: unknown }).detail);
        errorData = errorBody;
      } else if (typeof errorBody === 'string') {
        errorMessage = errorBody;
      } else {
        errorData = errorBody;
      }
    } catch {
      // If response body is not JSON, use status text
    }

    throw new PlateReadsApiError(response.status, errorMessage, errorData);
  }

  try {
    return (await response.json()) as T;
  } catch (error) {
    throw new PlateReadsApiError(response.status, 'Failed to parse response JSON', error);
  }
}

/**
 * Perform a fetch request to the plate reads API with error handling.
 */
async function fetchPlateReadsApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}/api/plate-reads${endpoint}`;

  const fetchOptions: RequestInit = {
    ...options,
    headers: buildHeaders(),
  };

  try {
    const response = await fetch(url, fetchOptions);
    return handleResponse<T>(response);
  } catch (error) {
    if (error instanceof PlateReadsApiError) {
      throw error;
    }
    throw new PlateReadsApiError(
      0,
      error instanceof Error ? error.message : 'Network request failed'
    );
  }
}

/**
 * Build URL query string from filter parameters.
 * Omits undefined values.
 */
function buildQueryString(params: Record<string, string | number | boolean | undefined>): string {
  const searchParams = new URLSearchParams();

  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) {
      searchParams.append(key, String(value));
    }
  }

  const queryString = searchParams.toString();
  return queryString ? `?${queryString}` : '';
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Fetch plate read statistics.
 *
 * Returns aggregated statistics for the ALPR system including total reads,
 * unique plates, average confidence scores, and recent activity.
 *
 * @returns PlateStatisticsResponse with aggregate statistics
 * @throws PlateReadsApiError on network or API errors
 */
export async function fetchPlateStatistics(): Promise<PlateStatisticsResponse> {
  return fetchPlateReadsApi<PlateStatisticsResponse>('/stats');
}

/**
 * Fetch a paginated list of plate reads.
 *
 * Supports filtering by camera, time range, and minimum confidence.
 *
 * @param params - Filter and pagination parameters
 * @returns PlateReadListResponse with paginated plate reads
 * @throws PlateReadsApiError on network or API errors
 */
export async function fetchPlateReads(
  params?: PlateReadFilters
): Promise<PlateReadListResponse> {
  const queryString = params
    ? buildQueryString({
        camera_id: params.camera_id,
        start_time: params.start_time,
        end_time: params.end_time,
        min_confidence: params.min_confidence,
        page: params.page,
        page_size: params.page_size,
      })
    : '';

  return fetchPlateReadsApi<PlateReadListResponse>(queryString);
}

/**
 * Search plate reads by plate text.
 *
 * Performs partial or exact matching on plate text.
 *
 * @param params - Search parameters including text and pagination
 * @returns PlateReadListResponse with matching plate reads
 * @throws PlateReadsApiError on network or API errors
 */
export async function searchPlateReads(
  params: PlateSearchParams
): Promise<PlateReadListResponse> {
  const queryString = buildQueryString({
    text: params.text,
    exact: params.exact,
    page: params.page,
    page_size: params.page_size,
  });

  return fetchPlateReadsApi<PlateReadListResponse>(`/search${queryString}`);
}

/**
 * Fetch a single plate read by ID.
 *
 * Retrieves the full plate read record including all detection details.
 *
 * @param id - The plate read ID
 * @returns PlateRead with full details
 * @throws PlateReadsApiError if not found (404) or other errors
 */
export async function fetchPlateReadById(id: number): Promise<PlateRead> {
  return fetchPlateReadsApi<PlateRead>(`/${id}`);
}

/**
 * Fetch plate reads for a specific camera.
 *
 * Convenience function for filtering by a single camera.
 *
 * @param cameraId - The camera ID to filter by
 * @param params - Optional additional filter and pagination parameters
 * @returns PlateReadListResponse with paginated plate reads
 * @throws PlateReadsApiError on network or API errors
 */
export async function fetchPlateReadsByCamera(
  cameraId: string,
  params?: Omit<PlateReadFilters, 'camera_id'>
): Promise<PlateReadListResponse> {
  return fetchPlateReads({
    ...params,
    camera_id: cameraId,
  });
}

/**
 * Fetch plate reads for a specific date range.
 *
 * Convenience function for time-based filtering.
 *
 * @param startTime - Start time in ISO 8601 format
 * @param endTime - End time in ISO 8601 format
 * @param params - Optional additional filter and pagination parameters
 * @returns PlateReadListResponse with paginated plate reads
 * @throws PlateReadsApiError on network or API errors
 */
export async function fetchPlateReadsByDateRange(
  startTime: string,
  endTime: string,
  params?: Omit<PlateReadFilters, 'start_time' | 'end_time'>
): Promise<PlateReadListResponse> {
  return fetchPlateReads({
    ...params,
    start_time: startTime,
    end_time: endTime,
  });
}

/**
 * Fetch high-confidence plate reads.
 *
 * Convenience function for filtering by minimum confidence threshold.
 *
 * @param minConfidence - Minimum OCR confidence (0-1), defaults to 0.9
 * @param params - Optional additional filter and pagination parameters
 * @returns PlateReadListResponse with paginated plate reads
 * @throws PlateReadsApiError on network or API errors
 */
export async function fetchHighConfidencePlateReads(
  minConfidence: number = 0.9,
  params?: Omit<PlateReadFilters, 'min_confidence'>
): Promise<PlateReadListResponse> {
  return fetchPlateReads({
    ...params,
    min_confidence: minConfidence,
  });
}
