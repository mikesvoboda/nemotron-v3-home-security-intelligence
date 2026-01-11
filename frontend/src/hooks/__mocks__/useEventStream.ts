/**
 * Mock for useEventStream hook.
 *
 * Provides configurable factory functions for testing components that depend
 * on the security event stream. Follows the same patterns as backend/tests/mock_utils.py.
 *
 * @example
 * ```typescript
 * import { vi } from 'vitest';
 * import { createMockEventStream, mockUseEventStream, createMockSecurityEvent } from '../__mocks__';
 *
 * vi.mock('../hooks/useEventStream', () => ({
 *   useEventStream: mockUseEventStream,
 * }));
 *
 * // In test
 * mockUseEventStream.mockReturnValue(
 *   createMockEventStream({
 *     events: [createMockSecurityEvent({ risk_level: 'high' })],
 *     isConnected: true,
 *   })
 * );
 * ```
 */

import { vi } from 'vitest';

import type { RiskLevel } from '../../types/websocket';
import type { SequenceStatistics } from '../sequenceValidator';
import type { UseEventStreamReturn, SecurityEvent } from '../useEventStream';

// =============================================================================
// Types
// =============================================================================

/**
 * Configuration options for creating a mock security event.
 * All properties are optional and will fall back to sensible defaults.
 */
export interface MockSecurityEventOptions {
  /** Event ID (string or number). Default: auto-generated */
  id?: string | number;
  /** Numeric event ID. Default: auto-generated */
  event_id?: number;
  /** Batch ID grouping related detections. Default: auto-generated */
  batch_id?: string;
  /** Camera that captured the event. Default: 'front_door' */
  camera_id?: string;
  /** Human-readable camera name. Default: 'Front Door' */
  camera_name?: string;
  /** AI-determined risk score (0-100). Default: 50 */
  risk_score?: number;
  /** Categorical risk level. Default: 'medium' */
  risk_level?: RiskLevel;
  /** AI-generated event summary. Default: 'Test security event' */
  summary?: string;
  /** Event timestamp. Default: current ISO timestamp */
  timestamp?: string;
  /** When the event started. Default: current ISO timestamp */
  started_at?: string;
}

/**
 * Configuration options for creating a mock event stream return value.
 * All properties are optional and will fall back to sensible defaults.
 */
export interface MockEventStreamOptions {
  /** Array of security events. Default: empty array */
  events?: SecurityEvent[];
  /** Whether the WebSocket is connected. Default: false */
  isConnected?: boolean;
  /** Sequence validation statistics. Default: empty stats */
  sequenceStats?: SequenceStatistics;
}

/**
 * Default empty sequence statistics for mocks.
 */
const DEFAULT_SEQUENCE_STATS: SequenceStatistics = {
  processedCount: 0,
  duplicateCount: 0,
  resyncCount: 0,
  outOfOrderCount: 0,
  currentBufferSize: 0,
};

/**
 * Mock return type for useEventStream hook.
 * Extends UseEventStreamReturn with vi.Mock type for clearEvents.
 */
export interface MockEventStreamReturn extends Omit<UseEventStreamReturn, 'clearEvents'> {
  /** Mock clearEvents function */
  clearEvents: ReturnType<typeof vi.fn>;
}

// =============================================================================
// Counter for unique IDs
// =============================================================================

let eventIdCounter = 1;

/**
 * Resets the event ID counter to 1.
 * Call this in beforeEach to ensure consistent IDs across tests.
 */
export function resetEventIdCounter(): void {
  eventIdCounter = 1;
}

// =============================================================================
// Security Event Factory
// =============================================================================

/**
 * Creates a mock security event with configurable properties.
 *
 * @param options - Configuration options for the mock event
 * @returns A mock SecurityEvent object
 *
 * @example
 * ```typescript
 * // Default event
 * const event = createMockSecurityEvent();
 *
 * // High risk event
 * const highRiskEvent = createMockSecurityEvent({
 *   risk_score: 85,
 *   risk_level: 'high',
 *   summary: 'Person detected at entry point',
 * });
 *
 * // Event from specific camera
 * const cameraEvent = createMockSecurityEvent({
 *   camera_id: 'backyard',
 *   camera_name: 'Backyard Camera',
 * });
 * ```
 */
export function createMockSecurityEvent(options: MockSecurityEventOptions = {}): SecurityEvent {
  const id = eventIdCounter++;
  const now = new Date().toISOString();

  return {
    id: options.id ?? id,
    event_id: options.event_id ?? id,
    batch_id: options.batch_id ?? `batch-${id}`,
    camera_id: options.camera_id ?? 'front_door',
    camera_name: options.camera_name ?? 'Front Door',
    risk_score: options.risk_score ?? 50,
    risk_level: options.risk_level ?? 'medium',
    summary: options.summary ?? 'Test security event',
    timestamp: options.timestamp ?? now,
    started_at: options.started_at ?? now,
  };
}

/**
 * Creates a mock security event with low risk level.
 * Convenience function for testing low-risk scenarios.
 *
 * @param options - Additional options to override
 * @returns A mock SecurityEvent with low risk
 */
export function createLowRiskEvent(options: Partial<MockSecurityEventOptions> = {}): SecurityEvent {
  return createMockSecurityEvent({
    risk_score: 15,
    risk_level: 'low',
    summary: 'Normal activity detected',
    ...options,
  });
}

/**
 * Creates a mock security event with medium risk level.
 * Convenience function for testing medium-risk scenarios.
 *
 * @param options - Additional options to override
 * @returns A mock SecurityEvent with medium risk
 */
export function createMediumRiskEvent(options: Partial<MockSecurityEventOptions> = {}): SecurityEvent {
  return createMockSecurityEvent({
    risk_score: 50,
    risk_level: 'medium',
    summary: 'Unusual activity detected',
    ...options,
  });
}

/**
 * Creates a mock security event with high risk level.
 * Convenience function for testing high-risk scenarios.
 *
 * @param options - Additional options to override
 * @returns A mock SecurityEvent with high risk
 */
export function createHighRiskEvent(options: Partial<MockSecurityEventOptions> = {}): SecurityEvent {
  return createMockSecurityEvent({
    risk_score: 80,
    risk_level: 'high',
    summary: 'Suspicious activity detected',
    ...options,
  });
}

/**
 * Creates a mock security event with critical risk level.
 * Convenience function for testing critical alerts.
 *
 * @param options - Additional options to override
 * @returns A mock SecurityEvent with critical risk
 */
export function createCriticalRiskEvent(options: Partial<MockSecurityEventOptions> = {}): SecurityEvent {
  return createMockSecurityEvent({
    risk_score: 95,
    risk_level: 'critical',
    summary: 'Immediate attention required',
    ...options,
  });
}

/**
 * Creates an array of mock security events with varying risk levels.
 * Useful for testing event list components.
 *
 * @param count - Number of events to create. Default: 5
 * @returns Array of mock SecurityEvent objects
 *
 * @example
 * ```typescript
 * const events = createMockEventList(10);
 * // Returns 10 events with varying risk levels
 * ```
 */
export function createMockEventList(count: number = 5): SecurityEvent[] {
  const riskLevels: RiskLevel[] = ['low', 'medium', 'high', 'critical'];
  const riskScores = [20, 50, 75, 95];

  return Array.from({ length: count }, (_, index) => {
    const levelIndex = index % riskLevels.length;
    return createMockSecurityEvent({
      risk_level: riskLevels[levelIndex],
      risk_score: riskScores[levelIndex],
      summary: `Event ${index + 1}: ${riskLevels[levelIndex]} risk activity`,
    });
  });
}

// =============================================================================
// Event Stream Factory
// =============================================================================

/**
 * Creates a mock event stream return value with configurable properties.
 *
 * @param options - Configuration options for the mock
 * @returns A mock UseEventStreamReturn object
 *
 * @example
 * ```typescript
 * // Empty stream (default)
 * const stream = createMockEventStream();
 *
 * // Stream with events
 * const streamWithEvents = createMockEventStream({
 *   events: [createMockSecurityEvent(), createMockSecurityEvent()],
 *   isConnected: true,
 * });
 *
 * // Disconnected stream
 * const disconnected = createMockEventStream({ isConnected: false });
 * ```
 */
export function createMockEventStream(options: MockEventStreamOptions = {}): MockEventStreamReturn {
  const { events = [], isConnected = false, sequenceStats = DEFAULT_SEQUENCE_STATS } = options;

  return {
    events,
    isConnected,
    latestEvent: events.length > 0 ? events[0] : null,
    clearEvents: vi.fn(),
    sequenceStats,
  };
}

/**
 * Creates a connected event stream with a specified number of events.
 * Convenience function for common test scenario.
 *
 * @param eventCount - Number of events to include. Default: 5
 * @returns A mock UseEventStreamReturn object with events
 *
 * @example
 * ```typescript
 * const stream = createConnectedEventStream(10);
 * expect(stream.isConnected).toBe(true);
 * expect(stream.events).toHaveLength(10);
 * ```
 */
export function createConnectedEventStream(eventCount: number = 5): MockEventStreamReturn {
  return createMockEventStream({
    events: createMockEventList(eventCount),
    isConnected: true,
  });
}

/**
 * Creates a disconnected event stream.
 * Convenience function for testing disconnection states.
 *
 * @returns A mock UseEventStreamReturn object in disconnected state
 */
export function createDisconnectedEventStream(): MockEventStreamReturn {
  return createMockEventStream({
    events: [],
    isConnected: false,
  });
}

// =============================================================================
// Mock Hook Implementation
// =============================================================================

/**
 * Mock implementation of useEventStream hook.
 * Use with vi.mock() to replace the actual hook in tests.
 *
 * @example
 * ```typescript
 * import { vi } from 'vitest';
 * import { mockUseEventStream, createMockEventStream } from '../__mocks__';
 *
 * vi.mock('../hooks/useEventStream', () => ({
 *   useEventStream: mockUseEventStream,
 * }));
 *
 * beforeEach(() => {
 *   mockUseEventStream.mockClear();
 *   mockUseEventStream.mockReturnValue(createMockEventStream());
 * });
 *
 * it('shows events list when connected', () => {
 *   mockUseEventStream.mockReturnValue(createConnectedEventStream(5));
 *   // ... test component
 * });
 * ```
 */
export const mockUseEventStream = vi.fn((): MockEventStreamReturn => createMockEventStream());

// =============================================================================
// Test Utilities
// =============================================================================

/**
 * Adds an event to a mock event stream.
 * Returns a new mock with the event added to the front.
 *
 * @param mockReturn - The current mock event stream
 * @param event - The event to add
 * @returns A new MockEventStreamReturn with the event added
 *
 * @example
 * ```typescript
 * let stream = createMockEventStream({ isConnected: true });
 * stream = addEventToStream(stream, createHighRiskEvent());
 * expect(stream.events).toHaveLength(1);
 * expect(stream.latestEvent?.risk_level).toBe('high');
 * ```
 */
export function addEventToStream(
  mockReturn: MockEventStreamReturn,
  event: SecurityEvent
): MockEventStreamReturn {
  const newEvents = [event, ...mockReturn.events];
  return {
    ...mockReturn,
    events: newEvents,
    latestEvent: event,
    sequenceStats: mockReturn.sequenceStats,
  };
}

/**
 * Resets the mock event stream to initial state.
 * Call this in beforeEach to ensure clean state between tests.
 *
 * @param mockReturn - The mock event stream to reset
 *
 * @example
 * ```typescript
 * const stream = createMockEventStream();
 *
 * beforeEach(() => {
 *   resetEventStreamMock(stream);
 * });
 * ```
 */
export function resetEventStreamMock(mockReturn: MockEventStreamReturn): void {
  mockReturn.clearEvents.mockClear();
}

// =============================================================================
// Parameterized Test Helpers
// =============================================================================

/**
 * Test cases for risk levels.
 * Use with describe.each() for parameterized tests.
 *
 * @example
 * ```typescript
 * describe.each(RISK_LEVEL_TEST_CASES)(
 *   'Risk level $level',
 *   ({ score, level }) => {
 *     it(`displays correct styling for ${level}`, () => {
 *       const event = createMockSecurityEvent({ risk_score: score, risk_level: level });
 *       // ... test implementation
 *     });
 *   }
 * );
 * ```
 */
export const RISK_LEVEL_TEST_CASES: Array<{ score: number; level: RiskLevel }> = [
  { score: 0, level: 'low' },
  { score: 10, level: 'low' },
  { score: 30, level: 'low' },
  { score: 40, level: 'medium' },
  { score: 50, level: 'medium' },
  { score: 60, level: 'medium' },
  { score: 70, level: 'high' },
  { score: 80, level: 'high' },
  { score: 90, level: 'high' },
  { score: 95, level: 'critical' },
  { score: 100, level: 'critical' },
];

// =============================================================================
// Re-exports for convenience
// =============================================================================

export type { UseEventStreamReturn, SecurityEvent, RiskLevel };
