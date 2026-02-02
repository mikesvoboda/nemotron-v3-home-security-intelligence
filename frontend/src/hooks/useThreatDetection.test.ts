import { renderHook, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { useThreatDetection } from './useThreatDetection';

import type { ThreatDetection } from '../types/threat';

// Mock WebSocket events
const mockUseEventStream = vi.fn();
vi.mock('./useEventStream', () => ({
  useEventStream: () => mockUseEventStream(),
}));

// Helper to create mock threat data
function createMockThreat(overrides: Partial<ThreatDetection> = {}): ThreatDetection {
  return {
    id: 1,
    threat_type: 'gun',
    confidence: 0.95,
    severity: 'critical',
    camera_id: 'front_door',
    event_id: 123,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

describe('useThreatDetection', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockUseEventStream.mockReturnValue({
      events: [],
      isConnected: true,
      latestEvent: null,
      clearEvents: vi.fn(),
      sequenceStats: {
        processedCount: 0,
        duplicateCount: 0,
        resyncCount: 0,
        outOfOrderCount: 0,
        currentBufferSize: 0,
      },
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  describe('initial state', () => {
    it('returns empty threat summary when no threats', () => {
      const { result } = renderHook(() => useThreatDetection());

      expect(result.current.threatSummary.hasActiveThreats).toBe(false);
      expect(result.current.threatSummary.totalThreats).toBe(0);
      expect(result.current.threatSummary.threats).toHaveLength(0);
    });

    it('returns isLoading false by default', () => {
      const { result } = renderHook(() => useThreatDetection());

      expect(result.current.isLoading).toBe(false);
    });
  });

  describe('adding threats manually', () => {
    it('updates threat summary when threat is added', () => {
      const { result } = renderHook(() => useThreatDetection());

      act(() => {
        result.current.addThreat(createMockThreat());
      });

      expect(result.current.threatSummary.hasActiveThreats).toBe(true);
      expect(result.current.threatSummary.totalThreats).toBe(1);
    });

    it('calculates correct max severity', () => {
      const { result } = renderHook(() => useThreatDetection());

      act(() => {
        result.current.addThreat(createMockThreat({ id: 1, severity: 'medium' }));
        result.current.addThreat(createMockThreat({ id: 2, severity: 'critical' }));
        result.current.addThreat(createMockThreat({ id: 3, severity: 'high' }));
      });

      expect(result.current.threatSummary.maxSeverity).toBe('critical');
    });

    it('counts threats by severity correctly', () => {
      const { result } = renderHook(() => useThreatDetection());

      act(() => {
        result.current.addThreat(createMockThreat({ id: 1, severity: 'critical' }));
        result.current.addThreat(createMockThreat({ id: 2, severity: 'critical' }));
        result.current.addThreat(createMockThreat({ id: 3, severity: 'high' }));
        result.current.addThreat(createMockThreat({ id: 4, severity: 'medium' }));
      });

      expect(result.current.threatSummary.criticalCount).toBe(2);
      expect(result.current.threatSummary.highCount).toBe(1);
      expect(result.current.threatSummary.mediumCount).toBe(1);
    });

    it('tracks unique threat types', () => {
      const { result } = renderHook(() => useThreatDetection());

      act(() => {
        result.current.addThreat(createMockThreat({ id: 1, threat_type: 'gun' }));
        result.current.addThreat(createMockThreat({ id: 2, threat_type: 'knife', severity: 'high' }));
        result.current.addThreat(createMockThreat({ id: 3, threat_type: 'gun' }));
      });

      expect(result.current.threatSummary.threatTypes).toEqual(['gun', 'knife']);
    });

    it('tracks affected cameras', () => {
      const { result } = renderHook(() => useThreatDetection());

      act(() => {
        result.current.addThreat(createMockThreat({ id: 1, camera_id: 'front_door' }));
        result.current.addThreat(createMockThreat({ id: 2, camera_id: 'back_yard', severity: 'high' }));
        result.current.addThreat(createMockThreat({ id: 3, camera_id: 'front_door' }));
      });

      expect(result.current.threatSummary.affectedCameras).toEqual(['front_door', 'back_yard']);
    });
  });

  describe('removing threats', () => {
    it('removes specific threat by id', () => {
      const { result } = renderHook(() => useThreatDetection());

      act(() => {
        result.current.addThreat(createMockThreat({ id: 1 }));
        result.current.addThreat(createMockThreat({ id: 2, severity: 'high' }));
      });

      expect(result.current.threatSummary.totalThreats).toBe(2);

      act(() => {
        result.current.removeThreat(1);
      });

      expect(result.current.threatSummary.totalThreats).toBe(1);
      expect(result.current.threatSummary.threats[0].id).toBe(2);
    });

    it('clears all threats', () => {
      const { result } = renderHook(() => useThreatDetection());

      act(() => {
        result.current.addThreat(createMockThreat({ id: 1 }));
        result.current.addThreat(createMockThreat({ id: 2, severity: 'high' }));
        result.current.addThreat(createMockThreat({ id: 3, severity: 'medium' }));
      });

      expect(result.current.threatSummary.totalThreats).toBe(3);

      act(() => {
        result.current.clearThreats();
      });

      expect(result.current.threatSummary.hasActiveThreats).toBe(false);
      expect(result.current.threatSummary.totalThreats).toBe(0);
    });
  });

  describe('threat expiration', () => {
    it('expires threats after default timeout', () => {
      const { result } = renderHook(() => useThreatDetection());

      act(() => {
        result.current.addThreat(createMockThreat({ id: 1 }));
      });

      expect(result.current.threatSummary.totalThreats).toBe(1);

      // Advance time past default expiration (5 minutes)
      act(() => {
        vi.advanceTimersByTime(5 * 60 * 1000 + 1000);
      });

      expect(result.current.threatSummary.totalThreats).toBe(0);
    });

    it('respects custom expiration timeout', () => {
      const { result } = renderHook(() =>
        useThreatDetection({ expirationMs: 10000 }) // 10 seconds
      );

      act(() => {
        result.current.addThreat(createMockThreat({ id: 1 }));
      });

      // Before expiration
      act(() => {
        vi.advanceTimersByTime(5000);
      });
      expect(result.current.threatSummary.totalThreats).toBe(1);

      // After expiration
      act(() => {
        vi.advanceTimersByTime(6000);
      });
      expect(result.current.threatSummary.totalThreats).toBe(0);
    });

    it('does not expire threats when expirationMs is 0', () => {
      const { result } = renderHook(() =>
        useThreatDetection({ expirationMs: 0 })
      );

      act(() => {
        result.current.addThreat(createMockThreat({ id: 1 }));
      });

      // Advance time significantly
      act(() => {
        vi.advanceTimersByTime(10 * 60 * 1000);
      });

      expect(result.current.threatSummary.totalThreats).toBe(1);
    });
  });

  describe('dismissing threats', () => {
    it('dismisses threat by id', () => {
      const { result } = renderHook(() => useThreatDetection());

      act(() => {
        result.current.addThreat(createMockThreat({ id: 1 }));
        result.current.addThreat(createMockThreat({ id: 2, severity: 'high' }));
      });

      act(() => {
        result.current.dismissThreat(1);
      });

      expect(result.current.dismissedIds).toContain(1);
      expect(result.current.threatSummary.totalThreats).toBe(1);
    });

    it('dismissed threats are not re-added', () => {
      const { result } = renderHook(() => useThreatDetection());

      act(() => {
        result.current.addThreat(createMockThreat({ id: 1 }));
        result.current.dismissThreat(1);
      });

      expect(result.current.threatSummary.totalThreats).toBe(0);

      // Try to add the same threat again
      act(() => {
        result.current.addThreat(createMockThreat({ id: 1 }));
      });

      // Should still be dismissed
      expect(result.current.threatSummary.totalThreats).toBe(0);
    });

    it('resets dismissed ids when clearDismissed is called', () => {
      const { result } = renderHook(() => useThreatDetection());

      act(() => {
        result.current.addThreat(createMockThreat({ id: 1 }));
        result.current.dismissThreat(1);
      });

      expect(result.current.dismissedIds).toContain(1);

      // Clear dismissed IDs first
      act(() => {
        result.current.clearDismissed();
      });

      expect(result.current.dismissedIds).not.toContain(1);

      // Now add the threat in a separate act to ensure state has updated
      act(() => {
        result.current.addThreat(createMockThreat({ id: 1 }));
      });

      expect(result.current.threatSummary.totalThreats).toBe(1);
    });
  });

  describe('latest threat tracking', () => {
    it('tracks the most recent threat', () => {
      const { result } = renderHook(() => useThreatDetection());

      const oldDate = new Date('2024-01-01T10:00:00Z').toISOString();
      const newDate = new Date('2024-01-01T11:00:00Z').toISOString();

      act(() => {
        result.current.addThreat(createMockThreat({ id: 1, created_at: oldDate }));
        result.current.addThreat(createMockThreat({ id: 2, created_at: newDate, severity: 'high' }));
      });

      expect(result.current.threatSummary.latestThreat?.id).toBe(2);
    });
  });
});
