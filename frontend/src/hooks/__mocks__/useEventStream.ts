/**
 * Centralized mock for useEventStream hook.
 */

import { vi } from 'vitest';

import type { SecurityEvent, UseEventStreamReturn } from '../useEventStream';

let mockEvents: SecurityEvent[] = [];
let mockIsConnected: boolean = true;

export const mockClearEvents = vi.fn<() => void>(() => {
  mockEvents = [];
});

export function setMockEvents(events: SecurityEvent[]): void {
  mockEvents = [...events];
}

export function addMockEvent(event: SecurityEvent): void {
  mockEvents = [event, ...mockEvents];
}

export function setMockConnectionState(isConnected: boolean): void {
  mockIsConnected = isConnected;
}

export function getMockEvents(): SecurityEvent[] {
  return [...mockEvents];
}

export function resetMocks(): void {
  mockEvents = [];
  mockIsConnected = true;
  mockClearEvents.mockReset();
}

export function createMockSecurityEvent(overrides: Partial<SecurityEvent> = {}): SecurityEvent {
  return {
    id: `event-${Date.now()}`,
    event_id: Math.floor(Math.random() * 10000),
    camera_id: 'camera-1',
    camera_name: 'Front Door',
    risk_score: 50,
    risk_level: 'medium',
    summary: 'Motion detected',
    timestamp: new Date().toISOString(),
    started_at: new Date().toISOString(),
    ...overrides,
  };
}

export function createMockSecurityEvents(
  count: number,
  baseOverrides: Partial<SecurityEvent> = {}
): SecurityEvent[] {
  return Array.from({ length: count }, (_, index) =>
    createMockSecurityEvent({
      id: `event-${index + 1}`,
      event_id: index + 1,
      ...baseOverrides,
    })
  );
}

export const useEventStream = vi.fn((): UseEventStreamReturn => {
  return {
    events: mockEvents,
    isConnected: mockIsConnected,
    latestEvent: mockEvents.length > 0 ? mockEvents[0] : null,
    clearEvents: mockClearEvents,
  };
});

export type { SecurityEvent };
