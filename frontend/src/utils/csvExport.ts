/**
 * CSV Export utility functions for analytics data
 *
 * Provides functions to generate CSV content from analytics data and trigger
 * browser downloads. Supports proper escaping of special characters.
 *
 * @module utils/csvExport
 */

import type { CameraUptimeDataPoint } from '../services/api';
import type {
  DetectionTrendDataPoint,
  RiskHistoryDataPoint,
  ObjectDistributionDataPoint,
  RiskScoreDistributionBucket,
} from '../types/analytics';

// ============================================================================
// Types
// ============================================================================

/**
 * Data structure for analytics export.
 * Contains all the data sections that will be exported to CSV.
 */
export interface AnalyticsExportData {
  /** Date range for the analytics data */
  dateRange: {
    startDate: string;
    endDate: string;
  };
  /** Detection trends data */
  detectionTrends: {
    dataPoints: DetectionTrendDataPoint[];
    totalDetections: number;
  };
  /** Risk history data */
  riskHistory: {
    dataPoints: RiskHistoryDataPoint[];
  };
  /** Object distribution data */
  objectDistribution: {
    objectTypes: ObjectDistributionDataPoint[];
    totalDetections: number;
  };
  /** Camera uptime data */
  cameraUptime: {
    cameras: CameraUptimeDataPoint[];
  };
  /** Risk score distribution data */
  riskScoreDistribution: {
    buckets: RiskScoreDistributionBucket[];
    totalEvents: number;
  };
}

// ============================================================================
// CSV Utility Functions
// ============================================================================

/**
 * Escape a value for safe inclusion in CSV.
 *
 * Values containing commas, quotes, or newlines are wrapped in double quotes.
 * Double quotes within values are escaped by doubling them.
 *
 * @param value - The value to escape (string or number)
 * @returns Escaped string safe for CSV
 *
 * @example
 * escapeCSVValue('hello') // 'hello'
 * escapeCSVValue('hello, world') // '"hello, world"'
 * escapeCSVValue('say "hi"') // '"say ""hi"""'
 */
export function escapeCSVValue(value: string | number): string {
  const str = String(value);

  // Check if escaping is needed
  if (str.includes(',') || str.includes('"') || str.includes('\n') || str.includes('\r')) {
    // Escape double quotes by doubling them and wrap in quotes
    return `"${str.replace(/"/g, '""')}"`;
  }

  return str;
}

/**
 * Generate CSV content from headers and rows.
 *
 * Creates a properly formatted CSV string with escaped values.
 * Each row ends with a newline character.
 *
 * @param headers - Array of column header strings
 * @param rows - Array of row data (each row is an array of values)
 * @returns CSV content as a string
 *
 * @example
 * const csv = generateCSV(
 *   ['Name', 'Value'],
 *   [['Item A', 100], ['Item B', 200]]
 * );
 * // Returns: 'Name,Value\nItem A,100\nItem B,200\n'
 */
export function generateCSV(headers: string[], rows: (string | number)[][]): string {
  const lines: string[] = [];

  // Add header row
  lines.push(headers.map(escapeCSVValue).join(','));

  // Add data rows
  for (const row of rows) {
    lines.push(row.map(escapeCSVValue).join(','));
  }

  // Join with newlines and add trailing newline
  return lines.join('\n') + '\n';
}

/**
 * Trigger a browser download of CSV content.
 *
 * Creates a Blob from the CSV content, generates a temporary URL,
 * and triggers a download via a hidden anchor element.
 *
 * @param filename - The filename for the download (should end in .csv)
 * @param csvContent - The CSV content to download
 *
 * @example
 * downloadCSV('analytics-2026-01-26.csv', csvContent);
 */
export function downloadCSV(filename: string, csvContent: string): void {
  // Create blob with CSV content
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });

  // Create temporary URL for the blob
  const url = URL.createObjectURL(blob);

  // Create anchor element and trigger download
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();

  // Clean up the temporary URL
  URL.revokeObjectURL(url);
}

// ============================================================================
// Analytics Formatting
// ============================================================================

/**
 * Format analytics data into a comprehensive CSV string.
 *
 * Creates a multi-section CSV with all analytics data including:
 * - Detection Trends
 * - Risk History
 * - Object Distribution
 * - Camera Uptime
 * - Risk Score Distribution
 *
 * Each section is separated by a blank line for readability.
 *
 * @param data - The analytics data to format
 * @returns Formatted CSV content string
 *
 * @example
 * const csvContent = formatAnalyticsForCSV({
 *   dateRange: { startDate: '2026-01-19', endDate: '2026-01-26' },
 *   detectionTrends: { dataPoints: [...], totalDetections: 250 },
 *   // ... other sections
 * });
 */
export function formatAnalyticsForCSV(data: AnalyticsExportData): string {
  const sections: string[] = [];

  // Header section
  sections.push(
    generateCSV(
      ['Analytics Export'],
      [
        ['Generated', new Date().toISOString()],
        ['Date Range', `${data.dateRange.startDate} to ${data.dateRange.endDate}`],
      ]
    )
  );

  // Detection Trends section
  sections.push(formatDetectionTrendsSection(data.detectionTrends));

  // Risk History section
  sections.push(formatRiskHistorySection(data.riskHistory));

  // Object Distribution section
  sections.push(formatObjectDistributionSection(data.objectDistribution));

  // Camera Uptime section
  sections.push(formatCameraUptimeSection(data.cameraUptime));

  // Risk Score Distribution section
  sections.push(formatRiskScoreDistributionSection(data.riskScoreDistribution));

  return sections.join('\n');
}

/**
 * Format Detection Trends data for CSV.
 */
function formatDetectionTrendsSection(trends: AnalyticsExportData['detectionTrends']): string {
  const rows: (string | number)[][] = trends.dataPoints.map((point) => [point.date, point.count]);

  // Add total row
  rows.push(['Total', trends.totalDetections]);

  return generateCSV(['Detection Trends'], []) + generateCSV(['Date', 'Detections'], rows);
}

/**
 * Format Risk History data for CSV.
 */
function formatRiskHistorySection(history: AnalyticsExportData['riskHistory']): string {
  const rows: (string | number)[][] = history.dataPoints.map((point) => [
    point.date,
    point.low,
    point.medium,
    point.high,
    point.critical,
  ]);

  return generateCSV(['Risk History'], []) + generateCSV(['Date', 'Low', 'Medium', 'High', 'Critical'], rows);
}

/**
 * Format Object Distribution data for CSV.
 */
function formatObjectDistributionSection(distribution: AnalyticsExportData['objectDistribution']): string {
  const rows: (string | number)[][] = distribution.objectTypes.map((obj) => [
    obj.object_type,
    obj.count,
    `${obj.percentage}%`,
  ]);

  // Add total row
  rows.push(['Total', distribution.totalDetections, '100%']);

  return generateCSV(['Object Distribution'], []) + generateCSV(['Object Type', 'Count', 'Percentage'], rows);
}

/**
 * Format Camera Uptime data for CSV.
 */
function formatCameraUptimeSection(uptime: AnalyticsExportData['cameraUptime']): string {
  const rows: (string | number)[][] = uptime.cameras.map((cam) => [
    cam.camera_name,
    `${cam.uptime_percentage}%`,
    cam.detection_count,
  ]);

  return generateCSV(['Camera Uptime'], []) + generateCSV(['Camera Name', 'Uptime %', 'Detection Count'], rows);
}

/**
 * Format Risk Score Distribution data for CSV.
 */
function formatRiskScoreDistributionSection(
  distribution: AnalyticsExportData['riskScoreDistribution']
): string {
  const rows: (string | number)[][] = distribution.buckets.map((bucket) => [
    `${bucket.min_score}-${bucket.max_score}`,
    bucket.count,
  ]);

  // Add total row
  rows.push(['Total Events', distribution.totalEvents]);

  return generateCSV(['Risk Score Distribution'], []) + generateCSV(['Score Range', 'Count'], rows);
}
