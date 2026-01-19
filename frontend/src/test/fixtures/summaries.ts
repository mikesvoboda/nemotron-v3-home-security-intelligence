/**
 * Summary Test Fixtures
 *
 * Mock data helpers for testing summary components.
 * Provides factory functions and pre-configured fixtures for common test scenarios.
 *
 * @see NEM-2930 - Comprehensive Summary Card Test Suite
 */

import type { Summary, SummaryBulletPoint } from '@/types/summary';

/**
 * Options for creating a mock summary.
 */
interface CreateMockSummaryOptions {
  /** Summary ID (default: 1) */
  id?: number;
  /** LLM-generated content (default: basic summary text) */
  content?: string;
  /** Number of events analyzed (default: 0) */
  eventCount?: number;
  /** Window start timestamp (default: 1 hour ago) */
  windowStart?: string;
  /** Window end timestamp (default: now) */
  windowEnd?: string;
  /** Generated timestamp (default: now) */
  generatedAt?: string;
  /** Maximum risk score (0-100, optional) */
  maxRiskScore?: number;
  /** Structured bullet points (optional) */
  bulletPoints?: SummaryBulletPoint[];
  /** Focus areas (optional) */
  focusAreas?: string[];
  /** Dominant patterns (optional) */
  dominantPatterns?: string[];
  /** Human-readable time range (optional) */
  timeRangeFormatted?: string;
  /** Weather conditions (optional) */
  weatherConditions?: string;
}

/**
 * Factory function to create a mock Summary object.
 *
 * @param options - Override options for the summary
 * @returns A complete Summary object with defaults
 *
 * @example
 * ```ts
 * const summary = createMockSummary({
 *   eventCount: 3,
 *   maxRiskScore: 75,
 * });
 * ```
 */
export function createMockSummary(options: CreateMockSummaryOptions = {}): Summary {
  const now = new Date().toISOString();
  const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000).toISOString();

  return {
    id: options.id ?? 1,
    content: options.content ?? 'No significant events detected during this period.',
    eventCount: options.eventCount ?? 0,
    windowStart: options.windowStart ?? oneHourAgo,
    windowEnd: options.windowEnd ?? now,
    generatedAt: options.generatedAt ?? now,
    maxRiskScore: options.maxRiskScore,
    bulletPoints: options.bulletPoints,
    focusAreas: options.focusAreas,
    dominantPatterns: options.dominantPatterns,
    timeRangeFormatted: options.timeRangeFormatted,
    weatherConditions: options.weatherConditions,
  };
}

/**
 * Mock summary with high severity (critical event detected).
 * Includes multiple risk factors and detailed bullet points.
 */
export const mockSummaryHighSeverity: Summary = createMockSummary({
  id: 101,
  content:
    'CRITICAL: Person detected at front door at 2:45 PM. Activity occurred after hours with no expected visitors. Motion detected for 3 minutes. High confidence detection.',
  eventCount: 3,
  maxRiskScore: 92,
  bulletPoints: [
    {
      icon: 'alert',
      text: 'Person detected at front door at 2:45 PM',
      severity: 92,
    },
    {
      icon: 'time',
      text: 'Activity after hours (expected quiet time)',
      severity: 80,
    },
    {
      icon: 'location',
      text: 'Front Door - High security zone',
      severity: 75,
    },
  ],
  focusAreas: ['Front Door', 'Entrance'],
  dominantPatterns: ['person'],
  timeRangeFormatted: '2:45 PM - 2:48 PM',
  weatherConditions: 'Clear',
});

/**
 * Mock summary with all clear status (no events).
 * Represents a quiet period with no security concerns.
 */
export const mockSummaryAllClear: Summary = createMockSummary({
  id: 102,
  content: 'All clear. No high-priority events detected during this period. Property is quiet.',
  eventCount: 0,
  maxRiskScore: 0,
  focusAreas: [],
  dominantPatterns: [],
  weatherConditions: 'Partly Cloudy',
});

/**
 * Mock summary with empty content (edge case).
 * Tests handling of malformed or minimal summary data.
 */
export const mockSummaryEmpty: Summary = createMockSummary({
  id: 103,
  content: '',
  eventCount: 0,
  bulletPoints: [],
});

/**
 * Mock summary with medium severity (routine activity).
 * Represents normal activity that doesn't require immediate attention.
 */
export const mockSummaryMediumSeverity: Summary = createMockSummary({
  id: 104,
  content: 'Delivery person detected at front door at 10:30 AM. Package delivery completed.',
  eventCount: 1,
  maxRiskScore: 45,
  bulletPoints: [
    {
      icon: 'location',
      text: 'Front door activity detected',
      severity: 45,
    },
    {
      icon: 'time',
      text: 'During normal business hours',
      severity: 20,
    },
  ],
  focusAreas: ['Front Door'],
  dominantPatterns: ['person'],
  timeRangeFormatted: '10:30 AM',
  weatherConditions: 'Sunny',
});

/**
 * Mock summary with bullet points provided by backend.
 * Tests the happy path where backend provides structured data.
 */
export const mockSummaryWithBackendBullets: Summary = createMockSummary({
  id: 105,
  content:
    'Vehicle detected in driveway at 3:15 PM. Garage door opened at 3:16 PM. Person exited vehicle.',
  eventCount: 2,
  maxRiskScore: 55,
  bulletPoints: [
    {
      icon: 'pattern',
      text: 'Vehicle detected in driveway',
      severity: 50,
    },
    {
      icon: 'alert',
      text: 'Garage door opened',
      severity: 60,
    },
    {
      icon: 'location',
      text: 'Person exited vehicle and entered home',
      severity: 45,
    },
  ],
  focusAreas: ['Driveway', 'Garage'],
  dominantPatterns: ['vehicle', 'person'],
  timeRangeFormatted: '3:15 PM - 3:17 PM',
  weatherConditions: 'Overcast',
});

/**
 * Mock summary with long content (stress test).
 * Tests line clamping and overflow handling.
 */
export const mockSummaryLongContent: Summary = createMockSummary({
  id: 106,
  content:
    'Multiple events detected throughout the hour. Person activity at front door at 2:15 PM with extended duration. Vehicle detected in driveway at 2:22 PM. Additional person detected at side gate at 2:35 PM. Motion sensors triggered in backyard at 2:48 PM. Multiple cameras recorded activity simultaneously suggesting coordinated movement.',
  eventCount: 5,
  maxRiskScore: 78,
  bulletPoints: [
    {
      icon: 'alert',
      text: 'Person activity at front door (2:15 PM)',
      severity: 75,
    },
    {
      icon: 'pattern',
      text: 'Vehicle detected in driveway (2:22 PM)',
      severity: 60,
    },
    {
      icon: 'location',
      text: 'Person at side gate (2:35 PM)',
      severity: 80,
    },
    {
      icon: 'alert',
      text: 'Backyard motion sensors triggered (2:48 PM)',
      severity: 70,
    },
    {
      icon: 'time',
      text: 'Coordinated movement across multiple zones',
      severity: 85,
    },
  ],
  focusAreas: ['Front Door', 'Driveway', 'Side Gate', 'Backyard'],
  dominantPatterns: ['person', 'vehicle'],
  timeRangeFormatted: '2:15 PM - 2:50 PM',
  weatherConditions: 'Rain',
});

/**
 * Mock summary with weather context.
 * Tests integration of environmental context data.
 */
export const mockSummaryWithWeather: Summary = createMockSummary({
  id: 107,
  content: 'Animal detected in backyard during storm. Likely wildlife seeking shelter.',
  eventCount: 1,
  maxRiskScore: 25,
  bulletPoints: [
    {
      icon: 'location',
      text: 'Backyard activity detected',
      severity: 30,
    },
    {
      icon: 'weather',
      text: 'Heavy rain and wind conditions',
      severity: 20,
    },
  ],
  focusAreas: ['Backyard'],
  dominantPatterns: ['animal'],
  timeRangeFormatted: '4:30 PM',
  weatherConditions: 'Heavy Rain, Wind',
});
