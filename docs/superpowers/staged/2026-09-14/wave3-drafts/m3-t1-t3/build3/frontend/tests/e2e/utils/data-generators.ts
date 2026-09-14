/**
 * Test Data Generators for E2E Tests
 *
 * Provides factory functions for generating realistic test data with randomization
 * and customization support. Use these instead of hardcoded mock data for more
 * comprehensive test coverage.
 */

import type { Locator } from '@playwright/test';

/**
 * Camera test data interface
 */
export interface CameraData {
  id: string;
  name: string;
  folder_path: string;
  status: 'online' | 'offline';
  created_at: string;
  last_seen_at: string;
}

/**
 * Event test data interface
 */
export interface EventData {
  id: number;
  camera_id: string;
  camera_name: string;
  timestamp: string;
  started_at: string;
  ended_at: string;
  risk_score: number;
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  summary: string;
  reviewed: boolean;
  notes: string;
}

/**
 * Detection test data interface
 */
export interface DetectionData {
  id: number;
  event_id: number;
  camera_id: string;
  object_class: string;
  confidence: number;
  bbox: [number, number, number, number];
  image_path: string;
  timestamp: string;
}

/**
 * Alert test data interface
 */
export interface AlertData {
  id: number;
  rule_id: string;
  event_id: number;
  severity: 'low' | 'medium' | 'high' | 'critical';
  title: string;
  message: string;
  channels: string[];
  sent_at: string;
  acknowledged: boolean;
  acknowledged_at?: string;
}

/**
 * Generate camera test data
 *
 * Creates realistic camera data with optional overrides for specific test scenarios.
 *
 * @param overrides - Optional field overrides
 * @param seed - Optional seed for deterministic random data (default: random)
 * @returns Complete camera data object
 *
 * @example
 * ```typescript
 * test('displays camera status', async ({ page }) => {
 *   const camera = generateCamera({ status: 'offline' });
 *
 *   await mockApiResponse(page, '/api/cameras', { cameras: [camera] });
 *   await page.goto('/');
 *
 *   await expect(page.getByText(camera.name)).toBeVisible();
 *   await expect(page.getByText('Offline')).toBeVisible();
 * });
 * ```
 */
export function generateCamera(overrides: Partial<CameraData> = {}, seed?: number): CameraData {
  const rng = seed !== undefined ? seededRandom(seed) : Math.random;
  const id = overrides.id || `cam-${Math.floor(rng() * 1000)}`;
  const names = ['Front Door', 'Back Yard', 'Garage', 'Driveway', 'Side Gate', 'Patio', 'Entrance'];
  const name = overrides.name || names[Math.floor(rng() * names.length)];

  return {
    id,
    name,
    folder_path: `/export/foscam/${id}`,
    status: overrides.status || (rng() > 0.2 ? 'online' : 'offline'),
    created_at: overrides.created_at || new Date(Date.now() - rng() * 30 * 24 * 60 * 60 * 1000).toISOString(),
    last_seen_at: overrides.last_seen_at || new Date(Date.now() - rng() * 60 * 60 * 1000).toISOString(),
    ...overrides,
  };
}

/**
 * Generate multiple cameras
 *
 * @param count - Number of cameras to generate
 * @param seed - Optional seed for deterministic data
 * @returns Array of camera data
 *
 * @example
 * ```typescript
 * const cameras = generateCameras(5);
 * await mockApiResponse(page, '/api/cameras', { cameras });
 * ```
 */
export function generateCameras(count: number, seed?: number): CameraData[] {
  return Array.from({ length: count }, (_, i) => generateCamera({}, seed ? seed + i : undefined));
}

/**
 * Generate event test data
 *
 * Creates realistic security event data with randomized risk scores and summaries.
 *
 * @param overrides - Optional field overrides
 * @param seed - Optional seed for deterministic random data
 * @returns Complete event data object
 *
 * @example
 * ```typescript
 * test('displays high-risk events', async ({ page }) => {
 *   const highRiskEvent = generateEvent({ risk_level: 'high', risk_score: 85 });
 *
 *   await mockApiResponse(page, '/api/events', { events: [highRiskEvent] });
 *   await page.goto('/timeline');
 *
 *   await expect(page.getByText(highRiskEvent.summary)).toBeVisible();
 * });
 * ```
 */
export function generateEvent(overrides: Partial<EventData> = {}, seed?: number): EventData {
  const rng = seed !== undefined ? seededRandom(seed) : Math.random;

  // Generate risk level and corresponding score
  let riskLevel: EventData['risk_level'];
  let riskScore: number;

  if (overrides.risk_level) {
    riskLevel = overrides.risk_level;
    riskScore =
      overrides.risk_score ||
      {
        low: Math.floor(rng() * 30),
        medium: Math.floor(rng() * 30) + 30,
        high: Math.floor(rng() * 20) + 60,
        critical: Math.floor(rng() * 20) + 80,
      }[riskLevel];
  } else if (overrides.risk_score !== undefined) {
    riskScore = overrides.risk_score;
    riskLevel =
      riskScore < 30 ? 'low' : riskScore < 60 ? 'medium' : riskScore < 80 ? 'high' : 'critical';
  } else {
    const rand = rng();
    if (rand < 0.5) {
      riskLevel = 'low';
      riskScore = Math.floor(rng() * 30);
    } else if (rand < 0.8) {
      riskLevel = 'medium';
      riskScore = Math.floor(rng() * 30) + 30;
    } else if (rand < 0.95) {
      riskLevel = 'high';
      riskScore = Math.floor(rng() * 20) + 60;
    } else {
      riskLevel = 'critical';
      riskScore = Math.floor(rng() * 20) + 80;
    }
  }

  // Generate realistic summaries based on risk level
  const summaries = {
    low: [
      'Person detected at front door - appears to be delivery',
      'Animal detected in yard - likely neighborhood cat',
      'Vehicle passing by on street',
      'Person walking dog on sidewalk',
    ],
    medium: [
      'Unknown person detected near fence',
      'Prolonged activity detected in driveway',
      'Multiple people detected in restricted area',
      'Unusual movement pattern detected',
    ],
    high: [
      'Suspicious vehicle parked with occupants inside',
      'Unknown person attempting to open gate',
      'Prolonged loitering detected near entry point',
      'Multiple unknown individuals in secured area',
    ],
    critical: [
      'Multiple unknown individuals attempting door entry',
      'Forced entry attempt detected',
      'Aggressive behavior detected',
      'Security breach in progress',
    ],
  };

  const summaryOptions = summaries[riskLevel];
  const summary = overrides.summary || summaryOptions[Math.floor(rng() * summaryOptions.length)];

  const startTime = new Date(Date.now() - rng() * 24 * 60 * 60 * 1000);
  const endTime = new Date(startTime.getTime() + rng() * 5 * 60 * 1000);

  return {
    id: overrides.id || Math.floor(rng() * 10000),
    camera_id: overrides.camera_id || 'cam-1',
    camera_name: overrides.camera_name || 'Front Door',
    timestamp: overrides.timestamp || startTime.toISOString(),
    started_at: overrides.started_at || startTime.toISOString(),
    ended_at: overrides.ended_at || endTime.toISOString(),
    risk_score: riskScore,
    risk_level: riskLevel,
    summary,
    reviewed: overrides.reviewed ?? rng() > 0.7,
    notes: overrides.notes || '',
    ...overrides,
  };
}

/**
 * Generate multiple events
 *
 * @param count - Number of events to generate
 * @param seed - Optional seed for deterministic data
 * @returns Array of event data
 *
 * @example
 * ```typescript
 * const events = generateEvents(10, { minRiskScore: 70 });
 * await mockApiResponse(page, '/api/events', { events });
 * ```
 */
export function generateEvents(
  count: number,
  options: { seed?: number; minRiskScore?: number; maxRiskScore?: number } = {}
): EventData[] {
  const { seed, minRiskScore, maxRiskScore } = options;

  return Array.from({ length: count }, (_, i) => {
    let riskScore: number | undefined;

    if (minRiskScore !== undefined || maxRiskScore !== undefined) {
      const min = minRiskScore || 0;
      const max = maxRiskScore || 100;
      const rng = seed !== undefined ? seededRandom(seed + i) : Math.random;
      riskScore = Math.floor(rng() * (max - min) + min);
    }

    return generateEvent({ id: i + 1, risk_score: riskScore }, seed ? seed + i : undefined);
  });
}

/**
 * Generate detection test data
 *
 * Creates realistic object detection data with bounding boxes and confidence scores.
 *
 * @param overrides - Optional field overrides
 * @param seed - Optional seed for deterministic random data
 * @returns Complete detection data object
 *
 * @example
 * ```typescript
 * test('displays detection details', async ({ page }) => {
 *   const detection = generateDetection({ object_class: 'person', confidence: 0.95 });
 *
 *   await mockApiResponse(page, `/api/events/1/detections`, { detections: [detection] });
 *   await page.goto('/events/1');
 *
 *   await expect(page.getByText('Person (95%)')).toBeVisible();
 * });
 * ```
 */
export function generateDetection(overrides: Partial<DetectionData> = {}, seed?: number): DetectionData {
  const rng = seed !== undefined ? seededRandom(seed) : Math.random;

  const objectClasses = ['person', 'vehicle', 'animal', 'bicycle', 'package'];
  const objectClass = overrides.object_class || objectClasses[Math.floor(rng() * objectClasses.length)];

  // Generate realistic bounding box [x, y, width, height]
  const x = Math.floor(rng() * 800);
  const y = Math.floor(rng() * 600);
  const width = Math.floor(rng() * 200) + 100;
  const height = Math.floor(rng() * 300) + 150;

  return {
    id: overrides.id || Math.floor(rng() * 10000),
    event_id: overrides.event_id || 1,
    camera_id: overrides.camera_id || 'cam-1',
    object_class: objectClass,
    confidence: overrides.confidence ?? rng() * 0.3 + 0.7, // 0.7 - 1.0
    bbox: overrides.bbox || [x, y, width, height],
    image_path: overrides.image_path || `/export/foscam/cam-1/snapshot_${Date.now()}.jpg`,
    timestamp: overrides.timestamp || new Date().toISOString(),
    ...overrides,
  };
}

/**
 * Generate multiple detections
 *
 * @param count - Number of detections to generate
 * @param seed - Optional seed for deterministic data
 * @returns Array of detection data
 */
export function generateDetections(count: number, seed?: number): DetectionData[] {
  return Array.from({ length: count }, (_, i) => generateDetection({}, seed ? seed + i : undefined));
}

/**
 * Generate alert test data
 *
 * Creates realistic alert data for testing notification and alerting systems.
 *
 * @param overrides - Optional field overrides
 * @param seed - Optional seed for deterministic random data
 * @returns Complete alert data object
 *
 * @example
 * ```typescript
 * test('displays critical alerts', async ({ page }) => {
 *   const alert = generateAlert({ severity: 'critical', acknowledged: false });
 *
 *   await mockApiResponse(page, '/api/alerts', { alerts: [alert] });
 *   await page.goto('/alerts');
 *
 *   await expect(page.getByRole('button', { name: 'Acknowledge' })).toBeVisible();
 * });
 * ```
 */
export function generateAlert(overrides: Partial<AlertData> = {}, seed?: number): AlertData {
  const rng = seed !== undefined ? seededRandom(seed) : Math.random;

  const severity = overrides.severity || (['low', 'medium', 'high', 'critical'][
    Math.floor(rng() * 4)
  ] as AlertData['severity']);

  const titles = {
    low: ['Low Activity Alert', 'Minor Detection', 'Routine Event'],
    medium: ['Moderate Activity Alert', 'Attention Required', 'Unusual Activity'],
    high: ['High-Risk Event Detected', 'Security Alert', 'Immediate Attention Required'],
    critical: ['CRITICAL: Security Breach', 'URGENT: Multiple Intruders', 'CRITICAL: Forced Entry'],
  };

  const messages = {
    low: ['Low-risk activity detected. Review when convenient.'],
    medium: ['Unusual activity detected. Please review footage.'],
    high: ['High-risk event detected. Immediate review recommended.'],
    critical: ['Critical security event detected. Immediate action required.'],
  };

  const title = overrides.title || titles[severity][Math.floor(rng() * titles[severity].length)];
  const message = overrides.message || messages[severity][Math.floor(rng() * messages[severity].length)];

  const sentTime = new Date(Date.now() - rng() * 60 * 60 * 1000);
  const acknowledged = overrides.acknowledged ?? rng() > 0.6;

  return {
    id: overrides.id || Math.floor(rng() * 10000),
    rule_id: overrides.rule_id || `rule-${Math.floor(rng() * 100)}`,
    event_id: overrides.event_id || Math.floor(rng() * 1000),
    severity,
    title,
    message,
    channels: overrides.channels || ['email', 'pushover'],
    sent_at: overrides.sent_at || sentTime.toISOString(),
    acknowledged,
    acknowledged_at: acknowledged ? new Date(sentTime.getTime() + rng() * 30 * 60 * 1000).toISOString() : undefined,
    ...overrides,
  };
}

/**
 * Generate multiple alerts
 *
 * @param count - Number of alerts to generate
 * @param seed - Optional seed for deterministic data
 * @returns Array of alert data
 */
export function generateAlerts(count: number, seed?: number): AlertData[] {
  return Array.from({ length: count }, (_, i) => generateAlert({}, seed ? seed + i : undefined));
}

/**
 * Generate GPU stats test data
 *
 * @param overrides - Optional field overrides
 * @returns GPU stats object
 *
 * @example
 * ```typescript
 * const gpuStats = generateGpuStats({ utilization: 95, temperature: 85 });
 * await mockApiResponse(page, '/api/system/gpu', gpuStats);
 * ```
 */
export function generateGpuStats(
  overrides: Partial<{
    gpu_name: string;
    utilization: number;
    memory_used: number;
    memory_total: number;
    temperature: number;
    power_usage: number;
    inference_fps: number;
  }> = {}
): Record<string, unknown> {
  const rng = Math.random;

  return {
    gpu_name: overrides.gpu_name || 'NVIDIA RTX A5500',
    utilization: overrides.utilization ?? Math.floor(rng() * 100),
    memory_used: overrides.memory_used ?? Math.floor(rng() * 20000) + 2000,
    memory_total: overrides.memory_total || 24576,
    temperature: overrides.temperature ?? Math.floor(rng() * 50) + 30,
    power_usage: overrides.power_usage ?? Math.floor(rng() * 200) + 50,
    inference_fps: overrides.inference_fps ?? rng() * 20 + 5,
  };
}

/**
 * Generate realistic email address
 *
 * @param seed - Optional seed for deterministic data
 * @returns Email address string
 */
export function generateEmail(seed?: number): string {
  const rng = seed !== undefined ? seededRandom(seed) : Math.random;
  const names = ['john', 'jane', 'bob', 'alice', 'charlie', 'diana'];
  const domains = ['example.com', 'test.com', 'demo.org'];

  const name = names[Math.floor(rng() * names.length)];
  const domain = domains[Math.floor(rng() * domains.length)];
  const random = Math.floor(rng() * 1000);

  return `${name}${random}@${domain}`;
}

/**
 * Generate realistic timestamp within a range
 *
 * @param options - Configuration options
 * @returns ISO timestamp string
 */
export function generateTimestamp(
  options: {
    minAgeMs?: number;
    maxAgeMs?: number;
    seed?: number;
  } = {}
): string {
  const { minAgeMs = 0, maxAgeMs = 24 * 60 * 60 * 1000, seed } = options;
  const rng = seed !== undefined ? seededRandom(seed) : Math.random;

  const ageMs = minAgeMs + rng() * (maxAgeMs - minAgeMs);
  return new Date(Date.now() - ageMs).toISOString();
}

/**
 * Seeded random number generator for deterministic tests
 *
 * Uses a simple Linear Congruential Generator (LCG) algorithm.
 *
 * @param seed - Numeric seed
 * @returns Random number generator function (returns 0-1)
 */
function seededRandom(seed: number): () => number {
  let state = seed;
  return function () {
    state = (state * 1664525 + 1013904223) % 4294967296;
    return state / 4294967296;
  };
}
