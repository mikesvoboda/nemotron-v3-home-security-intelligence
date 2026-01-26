/**
 * Scheduled Reports Types
 *
 * Types for scheduled report management feature.
 * These types mirror the backend schemas defined in
 * `backend/api/schemas/scheduled_report.py`.
 *
 * @see NEM-3667 - Scheduled Reports Frontend UI
 */

// ============================================================================
// Enums and Literal Types
// ============================================================================

/**
 * Frequency options for scheduled reports.
 */
export type ReportFrequency = 'daily' | 'weekly' | 'monthly';

/**
 * All possible report frequencies.
 */
export const REPORT_FREQUENCIES: readonly ReportFrequency[] = [
  'daily',
  'weekly',
  'monthly',
] as const;

/**
 * Output format options for scheduled reports.
 */
export type ReportFormat = 'pdf' | 'csv' | 'json';

/**
 * All possible report formats.
 */
export const REPORT_FORMATS: readonly ReportFormat[] = ['pdf', 'csv', 'json'] as const;

// ============================================================================
// Scheduled Report Types
// ============================================================================

/**
 * Schema for creating a new scheduled report.
 */
export interface ScheduledReportCreate {
  /** Name/title of the scheduled report */
  name: string;
  /** How often the report should run (daily, weekly, monthly) */
  frequency: ReportFrequency;
  /** Day of week (0=Monday, 6=Sunday) for weekly reports */
  day_of_week?: number | null;
  /** Day of month (1-31) for monthly reports */
  day_of_month?: number | null;
  /** Hour of day to run report (0-23, default 8) */
  hour?: number;
  /** Minute of hour to run report (0-59, default 0) */
  minute?: number;
  /** Timezone for schedule (e.g., 'America/New_York', 'UTC') */
  timezone?: string;
  /** Output format for the report (pdf, csv, json) */
  format?: ReportFormat;
  /** Whether the scheduled report is active */
  enabled?: boolean;
  /** Email addresses to send report to (max 10) */
  email_recipients?: string[] | null;
  /** Include visual charts in the report */
  include_charts?: boolean;
  /** Include detailed event breakdowns */
  include_event_details?: boolean;
}

/**
 * Schema for updating an existing scheduled report.
 * All fields are optional for partial updates.
 */
export interface ScheduledReportUpdate {
  /** Name/title of the scheduled report */
  name?: string;
  /** How often the report should run (daily, weekly, monthly) */
  frequency?: ReportFrequency;
  /** Day of week (0=Monday, 6=Sunday) for weekly reports */
  day_of_week?: number | null;
  /** Day of month (1-31) for monthly reports */
  day_of_month?: number | null;
  /** Hour of day to run report (0-23) */
  hour?: number;
  /** Minute of hour to run report (0-59) */
  minute?: number;
  /** Timezone for schedule (e.g., 'America/New_York', 'UTC') */
  timezone?: string;
  /** Output format for the report (pdf, csv, json) */
  format?: ReportFormat;
  /** Whether the scheduled report is active */
  enabled?: boolean;
  /** Email addresses to send report to (max 10) */
  email_recipients?: string[] | null;
  /** Include visual charts in the report */
  include_charts?: boolean;
  /** Include detailed event breakdowns */
  include_event_details?: boolean;
}

/**
 * Full scheduled report response from API.
 */
export interface ScheduledReport {
  /** Scheduled report ID */
  id: number;
  /** Name/title of the scheduled report */
  name: string;
  /** How often the report runs */
  frequency: ReportFrequency;
  /** Day of week (0=Monday, 6=Sunday) for weekly reports */
  day_of_week: number | null;
  /** Day of month (1-31) for monthly reports */
  day_of_month: number | null;
  /** Hour of day to run report (0-23) */
  hour: number;
  /** Minute of hour to run report (0-59) */
  minute: number;
  /** Timezone for schedule */
  timezone: string;
  /** Output format for the report */
  format: ReportFormat;
  /** Whether the scheduled report is active */
  enabled: boolean;
  /** Email addresses to send report to */
  email_recipients: string[] | null;
  /** Include visual charts in the report */
  include_charts: boolean;
  /** Include detailed event breakdowns */
  include_event_details: boolean;
  /** When the report last ran successfully (ISO 8601) */
  last_run_at: string | null;
  /** When the report is scheduled to run next (ISO 8601) */
  next_run_at: string | null;
  /** When the report was created (ISO 8601) */
  created_at: string;
  /** When the report was last updated (ISO 8601) */
  updated_at: string;
}

/**
 * Response for listing scheduled reports.
 */
export interface ScheduledReportListResponse {
  /** List of scheduled reports */
  items: ScheduledReport[];
  /** Total count */
  total: number;
}

/**
 * Response from manually triggering a report.
 */
export interface ScheduledReportRunResponse {
  /** ID of the report being run */
  report_id: number;
  /** Status of the run (running, queued, failed) */
  status: string;
  /** Status message */
  message: string;
  /** When the run was initiated (ISO 8601) */
  started_at: string;
}

// ============================================================================
// UI Helper Constants
// ============================================================================

/**
 * Human-readable labels for report frequencies.
 */
export const FREQUENCY_LABELS: Record<ReportFrequency, string> = {
  daily: 'Daily',
  weekly: 'Weekly',
  monthly: 'Monthly',
};

/**
 * Human-readable labels for report formats.
 */
export const FORMAT_LABELS: Record<ReportFormat, string> = {
  pdf: 'PDF',
  csv: 'CSV',
  json: 'JSON',
};

/**
 * Day of week labels (0=Monday, 6=Sunday).
 */
export const DAY_OF_WEEK_LABELS: Record<number, string> = {
  0: 'Monday',
  1: 'Tuesday',
  2: 'Wednesday',
  3: 'Thursday',
  4: 'Friday',
  5: 'Saturday',
  6: 'Sunday',
};

/**
 * Common timezone options.
 */
export const COMMON_TIMEZONES: readonly string[] = [
  'UTC',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'Europe/London',
  'Europe/Paris',
  'Europe/Berlin',
  'Asia/Tokyo',
  'Asia/Shanghai',
  'Asia/Singapore',
  'Australia/Sydney',
] as const;

// ============================================================================
// Type Guards
// ============================================================================

/**
 * Type guard to check if a string is a valid report frequency.
 */
export function isReportFrequency(value: unknown): value is ReportFrequency {
  return (
    typeof value === 'string' && REPORT_FREQUENCIES.includes(value as ReportFrequency)
  );
}

/**
 * Type guard to check if a string is a valid report format.
 */
export function isReportFormat(value: unknown): value is ReportFormat {
  return typeof value === 'string' && REPORT_FORMATS.includes(value as ReportFormat);
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Format a time (hour and minute) for display.
 */
export function formatTime(hour: number, minute: number): string {
  const h = hour % 12 || 12;
  const m = minute.toString().padStart(2, '0');
  const ampm = hour < 12 ? 'AM' : 'PM';
  return `${h}:${m} ${ampm}`;
}

/**
 * Get a human-readable schedule description.
 */
export function getScheduleDescription(report: ScheduledReport): string {
  const time = formatTime(report.hour, report.minute);

  switch (report.frequency) {
    case 'daily':
      return `Daily at ${time}`;
    case 'weekly':
      if (report.day_of_week !== null) {
        return `${DAY_OF_WEEK_LABELS[report.day_of_week]}s at ${time}`;
      }
      return `Weekly at ${time}`;
    case 'monthly':
      if (report.day_of_month !== null) {
        const suffix = getOrdinalSuffix(report.day_of_month);
        return `${report.day_of_month}${suffix} of each month at ${time}`;
      }
      return `Monthly at ${time}`;
    default:
      return `At ${time}`;
  }
}

/**
 * Get ordinal suffix for a number (1st, 2nd, 3rd, etc.).
 */
function getOrdinalSuffix(n: number): string {
  const s = ['th', 'st', 'nd', 'rd'];
  const v = n % 100;
  return s[(v - 20) % 10] || s[v] || s[0];
}
