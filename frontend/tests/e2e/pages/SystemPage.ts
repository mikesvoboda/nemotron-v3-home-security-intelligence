/**
 * SystemPage - Page Object for the System Monitoring page
 *
 * Provides selectors and interactions for:
 * - System overview (uptime, cameras, events, detections)
 * - Service health status
 * - Pipeline queues
 * - GPU stats
 * - Latency stats
 * - AI models panel
 * - Databases panel
 * - Host system panel
 * - Containers panel
 * - Time range selector
 * - Performance alerts
 */

import type { Page, Locator } from '@playwright/test';
import { expect } from '@playwright/test';
import { BasePage } from './BasePage';

export class SystemPage extends BasePage {
  // Page heading
  readonly pageTitle: Locator;
  readonly pageSubtitle: Locator;
  readonly serverIcon: Locator;

  // Time Range Selector
  readonly timeRangeSelector: Locator;
  readonly timeRange1h: Locator;
  readonly timeRange6h: Locator;
  readonly timeRange24h: Locator;
  readonly timeRange7d: Locator;

  // Performance Alerts
  readonly performanceAlerts: Locator;
  readonly alertItems: Locator;

  // System Overview Card
  readonly systemOverviewCard: Locator;
  readonly uptime: Locator;
  readonly totalCameras: Locator;
  readonly totalEvents: Locator;
  readonly totalDetections: Locator;

  // Service Health Card
  readonly serviceHealthCard: Locator;
  readonly overallHealthBadge: Locator;
  readonly serviceRows: Locator;
  readonly postgresqlService: Locator;
  readonly redisService: Locator;
  readonly rtdetrService: Locator;
  readonly nemotronService: Locator;

  // Worker Status Panel
  readonly workerStatusPanel: Locator;
  readonly workerItems: Locator;

  // Pipeline Metrics Panel (combined Queues + Latency + Throughput)
  readonly pipelineMetricsPanel: Locator;
  readonly pipelineQueuesCard: Locator; // Alias for backwards compatibility
  readonly detectionQueue: Locator;
  readonly analysisQueue: Locator;

  // GPU Stats Card
  readonly gpuStatsCard: Locator;
  readonly gpuName: Locator;
  readonly gpuUtilization: Locator;
  readonly gpuMemory: Locator;
  readonly gpuTemperature: Locator;
  readonly gpuPower: Locator;

  // Latency Stats Card
  readonly latencyStatsCard: Locator;
  readonly detectLatency: Locator;
  readonly analyzeLatency: Locator;

  // AI Models Panel
  readonly aiModelsPanel: Locator;
  readonly rtdetrPanel: Locator;
  readonly nemotronPanel: Locator;

  // Databases Panel
  readonly databasesPanel: Locator;
  readonly postgresqlPanel: Locator;
  readonly redisPanel: Locator;

  // Host System Panel
  readonly hostSystemPanel: Locator;
  readonly cpuUsage: Locator;
  readonly ramUsage: Locator;
  readonly diskUsage: Locator;

  // Containers Panel
  readonly containersPanel: Locator;
  readonly containerItems: Locator;

  // Loading/Error States
  readonly loadingSkeleton: Locator;
  readonly errorMessage: Locator;
  readonly reloadButton: Locator;

  constructor(page: Page) {
    super(page);

    // Page heading
    this.pageTitle = page.getByRole('heading', { name: /System Monitoring/i });
    this.pageSubtitle = page.getByText(/Real-time system metrics/i);
    this.serverIcon = page.locator('svg.lucide-server').first();

    // Time Range Selector - actual values are 5m, 15m, 60m per TimeRangeSelector component
    this.timeRangeSelector = page.locator('[data-testid="time-range-selector"]');
    this.timeRange1h = page.locator('[data-testid="time-range-selector"] button').filter({ hasText: '5m' });
    this.timeRange6h = page.locator('[data-testid="time-range-selector"] button').filter({ hasText: '15m' });
    this.timeRange24h = page.locator('[data-testid="time-range-selector"] button').filter({ hasText: '60m' });
    this.timeRange7d = page.locator('[data-testid="time-range-selector"] button').filter({ hasText: '60m' });

    // Performance Alerts
    this.performanceAlerts = page.locator('[data-testid="system-performance-alerts"]');
    this.alertItems = page.locator('[data-testid="system-performance-alerts"] [class*="alert"]');

    // System Overview Card
    this.systemOverviewCard = page.locator('[data-testid="system-overview-card"]');
    this.uptime = page.getByText(/Uptime/i).locator('..').locator('[class*="Metric"]');
    this.totalCameras = page.getByText(/Total Cameras/i).locator('..').locator('[class*="Metric"]');
    this.totalEvents = page.getByText(/Total Events/i).locator('..').locator('[class*="Metric"]');
    this.totalDetections = page.getByText(/Total Detections/i).locator('..').locator('[class*="Metric"]');

    // Service Health Card
    this.serviceHealthCard = page.locator('[data-testid="service-health-card"]');
    this.overallHealthBadge = page.locator('[data-testid="overall-health-badge"]');
    this.serviceRows = page.locator('[data-testid^="service-row-"]');
    this.postgresqlService = page.locator('[data-testid="service-row-postgresql"]');
    this.redisService = page.locator('[data-testid="service-row-redis"]');
    this.rtdetrService = page.locator('[data-testid="service-row-rtdetr_server"]');
    this.nemotronService = page.locator('[data-testid="service-row-nemotron"]');

    // Worker Status Panel
    this.workerStatusPanel = page.locator('[class*="WorkerStatusPanel"]');
    this.workerItems = page.locator('[class*="WorkerStatusPanel"] [class*="worker"]');

    // Pipeline Metrics Panel (combined Queues + Latency + Throughput)
    this.pipelineMetricsPanel = page.locator('[data-testid="pipeline-metrics-panel"]');
    this.pipelineQueuesCard = this.pipelineMetricsPanel; // Alias for backwards compatibility
    this.detectionQueue = page.locator('[data-testid="detection-queue-row"]');
    this.analysisQueue = page.locator('[data-testid="analysis-queue-row"]');

    // GPU Stats Card - look for the section with GPU heading
    this.gpuStatsCard = page.locator('div').filter({ has: page.getByText(/GPU Status|GPU Metrics/i) }).first();
    this.gpuName = page.getByText(/NVIDIA|RTX|GPU/i).first();
    this.gpuUtilization = page.getByText(/Utilization/i).first();
    this.gpuMemory = page.getByText(/Memory/i).first();
    this.gpuTemperature = page.getByText(/Temperature/i).first();
    this.gpuPower = page.getByText(/Power/i).first();

    // Latency Stats Card
    this.latencyStatsCard = page.locator('[data-testid="latency-stats-card"]');
    this.detectLatency = page.getByText(/Detection \(RT-DETR/i).locator('..');
    this.analyzeLatency = page.getByText(/Analysis \(Nemotron/i).locator('..');

    // AI Models Panel
    this.aiModelsPanel = page.locator('[data-testid="ai-models-panel-section"]');
    this.rtdetrPanel = page.getByText(/RT-DETR/i).first().locator('..');
    this.nemotronPanel = page.getByText(/Nemotron/i).first().locator('..');

    // Databases Panel
    this.databasesPanel = page.locator('[data-testid="databases-panel-section"]');
    this.postgresqlPanel = page.getByText(/PostgreSQL/i).locator('..');
    this.redisPanel = page.getByText(/Redis/i).locator('..');

    // Host System Panel
    this.hostSystemPanel = page.locator('[data-testid="host-system-panel-section"]');
    this.cpuUsage = page.getByText(/CPU/i).first();
    this.ramUsage = page.getByText(/RAM/i).first();
    this.diskUsage = page.getByText(/Disk/i).first();

    // Containers Panel
    this.containersPanel = page.locator('[data-testid="containers-panel-section"]');
    this.containerItems = page.locator('[data-testid="containers-panel-section"] [class*="container"]');

    // Loading/Error States
    this.loadingSkeleton = page.locator('[data-testid="system-monitoring-loading"]');
    this.errorMessage = page.locator('[data-testid="system-monitoring-error"]');
    this.reloadButton = page.getByRole('button', { name: /Reload Page/i });
  }

  /**
   * Navigate to the System page
   */
  async goto(): Promise<void> {
    await this.page.goto('/system');
  }

  /**
   * Wait for the system page to fully load
   */
  async waitForSystemLoad(): Promise<void> {
    await expect(this.pageTitle).toBeVisible({ timeout: this.pageLoadTimeout });
  }

  /**
   * Select time range
   */
  async selectTimeRange(range: '1h' | '6h' | '24h' | '7d'): Promise<void> {
    const buttons: Record<string, Locator> = {
      '1h': this.timeRange1h,
      '6h': this.timeRange6h,
      '24h': this.timeRange24h,
      '7d': this.timeRange7d,
    };
    await buttons[range].click();
  }

  /**
   * Check if system is in loading state
   */
  async isLoading(): Promise<boolean> {
    return this.loadingSkeleton.isVisible().catch(() => false);
  }

  /**
   * Check if system is in error state
   */
  async hasError(): Promise<boolean> {
    return this.errorMessage.isVisible().catch(() => false);
  }

  /**
   * Click reload button in error state
   */
  async clickReload(): Promise<void> {
    await this.reloadButton.click();
  }

  /**
   * Check if performance alerts are shown
   */
  async hasPerformanceAlerts(): Promise<boolean> {
    return this.performanceAlerts.isVisible().catch(() => false);
  }

  /**
   * Get count of performance alerts
   */
  async getAlertCount(): Promise<number> {
    return this.alertItems.count();
  }

  /**
   * Get uptime text
   */
  async getUptimeText(): Promise<string | null> {
    return this.uptime.textContent();
  }

  /**
   * Get overall health status
   */
  async getOverallHealthStatus(): Promise<string | null> {
    return this.overallHealthBadge.textContent();
  }

  /**
   * Get count of service rows
   */
  async getServiceCount(): Promise<number> {
    return this.serviceRows.count();
  }

  /**
   * Check if GPU stats are displayed
   */
  async hasGpuStats(): Promise<boolean> {
    return this.gpuStatsCard.isVisible().catch(() => false);
  }

  /**
   * Check if latency stats are displayed (now part of pipeline metrics panel)
   */
  async hasLatencyStats(): Promise<boolean> {
    // Latency is now combined into the pipeline metrics panel
    return this.pipelineMetricsPanel.isVisible().catch(() => false);
  }

  /**
   * Check if a specific service is healthy
   */
  async isServiceHealthy(service: 'postgresql' | 'redis' | 'rtdetr' | 'nemotron'): Promise<boolean> {
    const serviceLocators: Record<string, Locator> = {
      postgresql: this.postgresqlService,
      redis: this.redisService,
      rtdetr: this.rtdetrService,
      nemotron: this.nemotronService,
    };
    const row = serviceLocators[service];
    const badge = row.locator('[class*="Badge"]');
    const text = await badge.textContent();
    return text?.toLowerCase() === 'healthy';
  }
}
