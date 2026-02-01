/**
 * Monitoring API client functions for Prometheus monitoring panel
 */

export interface TargetSummary {
  job: string;
  total: number;
  up: number;
  down: number;
  unknown: number;
}

export interface ExporterStatus {
  name: string;
  status: 'up' | 'down' | 'unknown';
  endpoint: string;
  last_scrape: string | null;
  error: string | null;
}

export interface MetricsCollection {
  collecting: boolean;
  last_successful_scrape: string | null;
  scrape_interval_seconds: number;
  total_series: number;
}

export interface MonitoringHealthResponse {
  healthy: boolean;
  prometheus_reachable: boolean;
  prometheus_url: string;
  targets_summary: TargetSummary[];
  exporters: ExporterStatus[];
  metrics_collection: MetricsCollection;
  issues: string[];
  timestamp: string;
}

export interface TargetDetail {
  job: string;
  instance: string;
  health: 'up' | 'down' | 'unknown';
  labels: Record<string, string>;
  last_scrape: string | null;
  last_error: string | null;
  scrape_duration_seconds: number;
}

export interface MonitoringTargetsResponse {
  targets: TargetDetail[];
  total: number;
  up: number;
  down: number;
  jobs: string[];
  timestamp: string;
}

/**
 * Fetch monitoring health status from Prometheus
 */
export async function fetchMonitoringHealth(): Promise<MonitoringHealthResponse> {
  const response = await fetch('/api/system/monitoring/health');
  if (!response.ok) {
    throw new Error(`Failed to fetch monitoring health: ${response.status} ${response.statusText}`);
  }
  return (await response.json()) as MonitoringHealthResponse;
}

/**
 * Fetch monitoring targets from Prometheus
 */
export async function fetchMonitoringTargets(): Promise<MonitoringTargetsResponse> {
  const response = await fetch('/api/system/monitoring/targets');
  if (!response.ok) {
    throw new Error(`Failed to fetch monitoring targets: ${response.status} ${response.statusText}`);
  }
  return (await response.json()) as MonitoringTargetsResponse;
}
