/**
 * Zone Analytics types for the enhanced ZonesPage.
 *
 * These types support the Zone Analytics Dashboard tabs with crossing
 * trends, line zone statistics, and comparison features.
 *
 * @module types/zoneAnalytics
 * @see NEM-4714 - Zone Analytics Dashboard Phase 1B
 */

// ============================================================================
// Tab Types
// ============================================================================

/**
 * Tab options for ZonesPage.
 * - overview: Zone grid, trust matrix, anomaly feed
 * - analytics: Crossing trends, line zone statistics
 * - comparison: Multi-zone comparison charts
 */
export type ZoneAnalyticsTab = 'overview' | 'analytics' | 'comparison';

/**
 * Tab configuration for rendering in the UI.
 */
export interface ZoneTabConfig {
  /** Unique tab identifier */
  id: ZoneAnalyticsTab;
  /** Display label for the tab */
  label: string;
  /** lucide-react icon name */
  icon: string;
}

// ============================================================================
// Line Zone Types
// ============================================================================

/**
 * Line zone with crossing counts.
 * Represents a line-type zone with aggregated in/out crossing statistics.
 */
export interface LineZoneWithCounts {
  /** Zone ID */
  id: number;
  /** Zone name */
  name: string;
  /** Camera ID the zone belongs to */
  camera_id: string;
  /** Total entries (crossings from outside to inside) */
  in_count: number;
  /** Total exits (crossings from inside to outside) */
  out_count: number;
  /** Whether the zone is enabled */
  enabled: boolean;
}

// ============================================================================
// Crossing Trends Types
// ============================================================================

/**
 * A single data point in the crossing trends response.
 * Represents crossing counts for a specific time interval.
 */
export interface CrossingTrendDataPoint {
  /** Timestamp in ISO format */
  timestamp: string;
  /** Number of entries during this interval */
  in_count: number;
  /** Number of exits during this interval */
  out_count: number;
  /** Net flow (in_count - out_count) */
  net_flow: number;
}

/**
 * Response from crossing trends endpoint.
 * Contains time-series data for line zone crossings.
 */
export interface CrossingTrendsResponse {
  /** Zone ID */
  zone_id: number;
  /** Zone name */
  zone_name: string;
  /** Trend data points */
  trends: CrossingTrendDataPoint[];
  /** Total entries in the time range */
  total_in: number;
  /** Total exits in the time range */
  total_out: number;
  /** Start of the time range (ISO format) */
  start_time: string;
  /** End of the time range (ISO format) */
  end_time: string;
  /** Aggregation interval */
  interval: 'hour' | 'day';
}

// ============================================================================
// Constants
// ============================================================================

/**
 * Tab definitions for the ZonesPage.
 * Order determines display order in the tab list.
 */
export const ZONE_TABS: ZoneTabConfig[] = [
  { id: 'overview', label: 'Overview', icon: 'LayoutGrid' },
  { id: 'analytics', label: 'Analytics', icon: 'BarChart3' },
  { id: 'comparison', label: 'Comparison', icon: 'GitCompare' },
];
