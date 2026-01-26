/**
 * Scheduled Reports API Client
 *
 * Provides typed fetch wrappers for scheduled report management REST endpoints.
 *
 * Endpoints:
 *   GET    /api/scheduled-reports           - List all scheduled reports
 *   POST   /api/scheduled-reports           - Create a new scheduled report
 *   GET    /api/scheduled-reports/:id       - Get scheduled report details
 *   PUT    /api/scheduled-reports/:id       - Update a scheduled report
 *   DELETE /api/scheduled-reports/:id       - Delete a scheduled report
 *   POST   /api/scheduled-reports/:id/trigger - Manually trigger a report
 *
 * @see NEM-3667 - Scheduled Reports Frontend UI
 * @see backend/api/routes/scheduled_reports.py - Backend implementation
 */

import type {
  ScheduledReport,
  ScheduledReportCreate,
  ScheduledReportUpdate,
  ScheduledReportListResponse,
  ScheduledReportRunResponse,
} from '../types/scheduledReport';

// ============================================================================
// Configuration
// ============================================================================

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '';
const API_KEY = import.meta.env.VITE_API_KEY as string | undefined;
const API_BASE = '/api/scheduled-reports';

// ============================================================================
// Error Handling
// ============================================================================

/**
 * Custom error class for Scheduled Reports API failures.
 * Includes HTTP status code and parsed error data.
 */
export class ScheduledReportsApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public data?: unknown
  ) {
    super(message);
    this.name = 'ScheduledReportsApiError';
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

    throw new ScheduledReportsApiError(response.status, errorMessage, errorData);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  try {
    return (await response.json()) as T;
  } catch (error) {
    throw new ScheduledReportsApiError(response.status, 'Failed to parse response JSON', error);
  }
}

/**
 * Perform a fetch request to the Scheduled Reports API with error handling.
 *
 * @param endpoint - API endpoint path (relative to /api/scheduled-reports)
 * @param options - Optional fetch options
 * @returns Parsed JSON response
 */
async function fetchScheduledReportsApi<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const url = `${BASE_URL}${API_BASE}${endpoint}`;

  const fetchOptions: RequestInit = {
    ...options,
    headers: buildHeaders(),
  };

  try {
    const response = await fetch(url, fetchOptions);
    return handleResponse<T>(response);
  } catch (error) {
    if (error instanceof ScheduledReportsApiError) {
      throw error;
    }
    throw new ScheduledReportsApiError(
      0,
      error instanceof Error ? error.message : 'Network request failed'
    );
  }
}

// ============================================================================
// API Functions - CRUD Operations
// ============================================================================

/**
 * List all scheduled reports.
 *
 * @returns List of scheduled reports with total count
 * @throws ScheduledReportsApiError on server errors
 *
 * @example
 * ```typescript
 * const { items, total } = await listScheduledReports();
 * console.log(`Found ${total} scheduled reports`);
 * ```
 */
export async function listScheduledReports(): Promise<ScheduledReportListResponse> {
  return fetchScheduledReportsApi<ScheduledReportListResponse>('');
}

/**
 * Get a scheduled report by ID.
 *
 * @param id - Scheduled report ID
 * @returns Scheduled report details
 * @throws ScheduledReportsApiError if not found or on server errors
 *
 * @example
 * ```typescript
 * const report = await getScheduledReport(1);
 * console.log(`Report: ${report.name}`);
 * ```
 */
export async function getScheduledReport(id: number): Promise<ScheduledReport> {
  return fetchScheduledReportsApi<ScheduledReport>(`/${id}`);
}

/**
 * Create a new scheduled report.
 *
 * @param data - Scheduled report creation data
 * @returns Created scheduled report
 * @throws ScheduledReportsApiError on validation or server errors
 *
 * @example
 * ```typescript
 * const report = await createScheduledReport({
 *   name: 'Weekly Security Summary',
 *   frequency: 'weekly',
 *   day_of_week: 1,
 *   hour: 8,
 *   minute: 0,
 *   format: 'pdf',
 *   email_recipients: ['admin@example.com'],
 * });
 * ```
 */
export async function createScheduledReport(
  data: ScheduledReportCreate
): Promise<ScheduledReport> {
  return fetchScheduledReportsApi<ScheduledReport>('', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * Update a scheduled report.
 *
 * @param id - Scheduled report ID
 * @param data - Fields to update
 * @returns Updated scheduled report
 * @throws ScheduledReportsApiError if not found or on validation/server errors
 *
 * @example
 * ```typescript
 * const updated = await updateScheduledReport(1, {
 *   name: 'Updated Report Name',
 *   enabled: false,
 * });
 * ```
 */
export async function updateScheduledReport(
  id: number,
  data: ScheduledReportUpdate
): Promise<ScheduledReport> {
  return fetchScheduledReportsApi<ScheduledReport>(`/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

/**
 * Delete a scheduled report.
 *
 * @param id - Scheduled report ID
 * @throws ScheduledReportsApiError if not found or on server errors
 *
 * @example
 * ```typescript
 * await deleteScheduledReport(1);
 * ```
 */
export async function deleteScheduledReport(id: number): Promise<void> {
  return fetchScheduledReportsApi<void>(`/${id}`, {
    method: 'DELETE',
  });
}

// ============================================================================
// API Functions - Trigger Operations
// ============================================================================

/**
 * Manually trigger a scheduled report to run immediately.
 *
 * @param id - Scheduled report ID
 * @returns Run response with status
 * @throws ScheduledReportsApiError if not found or on server errors
 *
 * @example
 * ```typescript
 * const result = await triggerScheduledReport(1);
 * console.log(`Report triggered: ${result.message}`);
 * ```
 */
export async function triggerScheduledReport(
  id: number
): Promise<ScheduledReportRunResponse> {
  return fetchScheduledReportsApi<ScheduledReportRunResponse>(`/${id}/trigger`, {
    method: 'POST',
  });
}
