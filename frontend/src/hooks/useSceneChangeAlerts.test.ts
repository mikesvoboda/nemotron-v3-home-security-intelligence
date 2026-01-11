import { renderHook, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import {
  useSceneChangeAlerts,
  formatChangeType,
  getChangeSeverity,
} from './useSceneChangeAlerts';
import * as useWebSocketModule from './useWebSocket';

import type { UseWebSocketReturn } from './useWebSocket';

// Mock useWebSocket hook
vi.mock('./useWebSocket', () => ({
  useWebSocket: vi.fn(),
}));

// Mock buildWebSocketOptions
vi.mock('../services/api', () => ({
  buildWebSocketOptions: vi.fn(() => ({
    url: 'ws://localhost:8000/ws/events',
    protocols: [],
  })),
}));

describe('useSceneChangeAlerts', () => {
  let onMessageCallback: ((data: unknown) => void) | null = null;

  beforeEach(() => {
    onMessageCallback = null;

    vi.spyOn(useWebSocketModule, 'useWebSocket').mockImplementation((options) => {
      // Capture the onMessage callback
      onMessageCallback = options.onMessage ?? null;
      return {
        isConnected: true,
        lastMessage: null,
        send: vi.fn(),
        connect: vi.fn(),
        disconnect: vi.fn(),
        connectionState: 'connected',
        reconnectAttempts: 0,
        hasExhaustedRetries: false,
      } as unknown as UseWebSocketReturn;
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('returns initial state with empty alerts', () => {
    const { result } = renderHook(() => useSceneChangeAlerts());

    expect(result.current.alerts).toEqual([]);
    expect(result.current.unacknowledgedCount).toBe(0);
    expect(result.current.hasAlerts).toBe(false);
    expect(result.current.isConnected).toBe(true);
  });

  it('adds new scene change alerts from WebSocket messages', () => {
    const { result } = renderHook(() => useSceneChangeAlerts());

    expect(onMessageCallback).not.toBeNull();

    // Simulate receiving a scene change message
    act(() => {
      onMessageCallback!({
        type: 'scene_change',
        data: {
          id: 1,
          camera_id: 'front_door',
          detected_at: '2026-01-10T10:00:00Z',
          change_type: 'view_blocked',
          similarity_score: 0.25,
        },
      });
    });

    expect(result.current.alerts).toHaveLength(1);
    expect(result.current.alerts[0].id).toBe(1);
    expect(result.current.alerts[0].cameraId).toBe('front_door');
    expect(result.current.alerts[0].changeType).toBe('view_blocked');
    expect(result.current.alerts[0].similarityScore).toBe(0.25);
    expect(result.current.alerts[0].dismissed).toBe(false);
    expect(result.current.unacknowledgedCount).toBe(1);
    expect(result.current.hasAlerts).toBe(true);
  });

  it('prevents duplicate alerts by ID', () => {
    const { result } = renderHook(() => useSceneChangeAlerts());

    act(() => {
      onMessageCallback!({
        type: 'scene_change',
        data: {
          id: 1,
          camera_id: 'front_door',
          detected_at: '2026-01-10T10:00:00Z',
          change_type: 'view_blocked',
          similarity_score: 0.25,
        },
      });
    });

    act(() => {
      // Try to add the same alert again
      onMessageCallback!({
        type: 'scene_change',
        data: {
          id: 1,
          camera_id: 'front_door',
          detected_at: '2026-01-10T10:00:00Z',
          change_type: 'view_blocked',
          similarity_score: 0.25,
        },
      });
    });

    expect(result.current.alerts).toHaveLength(1);
  });

  it('dismisses a specific alert', () => {
    const { result } = renderHook(() => useSceneChangeAlerts());

    act(() => {
      onMessageCallback!({
        type: 'scene_change',
        data: {
          id: 1,
          camera_id: 'front_door',
          detected_at: '2026-01-10T10:00:00Z',
          change_type: 'view_blocked',
          similarity_score: 0.25,
        },
      });
    });

    act(() => {
      onMessageCallback!({
        type: 'scene_change',
        data: {
          id: 2,
          camera_id: 'back_yard',
          detected_at: '2026-01-10T10:01:00Z',
          change_type: 'angle_changed',
          similarity_score: 0.45,
        },
      });
    });

    expect(result.current.unacknowledgedCount).toBe(2);

    act(() => {
      result.current.dismissAlert(1);
    });

    expect(result.current.alerts).toHaveLength(2);
    expect(result.current.alerts.find((a) => a.id === 1)?.dismissed).toBe(true);
    expect(result.current.alerts.find((a) => a.id === 2)?.dismissed).toBe(false);
    expect(result.current.unacknowledgedCount).toBe(1);
    expect(result.current.hasAlerts).toBe(true);
  });

  it('dismisses all alerts', () => {
    const { result } = renderHook(() => useSceneChangeAlerts());

    act(() => {
      onMessageCallback!({
        type: 'scene_change',
        data: {
          id: 1,
          camera_id: 'front_door',
          detected_at: '2026-01-10T10:00:00Z',
          change_type: 'view_blocked',
          similarity_score: 0.25,
        },
      });
    });

    act(() => {
      onMessageCallback!({
        type: 'scene_change',
        data: {
          id: 2,
          camera_id: 'back_yard',
          detected_at: '2026-01-10T10:01:00Z',
          change_type: 'angle_changed',
          similarity_score: 0.45,
        },
      });
    });

    act(() => {
      result.current.dismissAll();
    });

    expect(result.current.alerts).toHaveLength(2);
    expect(result.current.alerts.every((a) => a.dismissed)).toBe(true);
    expect(result.current.unacknowledgedCount).toBe(0);
    expect(result.current.hasAlerts).toBe(false);
  });

  it('clears all alerts', () => {
    const { result } = renderHook(() => useSceneChangeAlerts());

    act(() => {
      onMessageCallback!({
        type: 'scene_change',
        data: {
          id: 1,
          camera_id: 'front_door',
          detected_at: '2026-01-10T10:00:00Z',
          change_type: 'view_blocked',
          similarity_score: 0.25,
        },
      });
    });

    act(() => {
      result.current.clearAlerts();
    });

    expect(result.current.alerts).toEqual([]);
    expect(result.current.unacknowledgedCount).toBe(0);
  });

  it('respects maxAlerts option', () => {
    const { result } = renderHook(() => useSceneChangeAlerts({ maxAlerts: 2 }));

    // Add 3 alerts
    act(() => {
      for (let i = 1; i <= 3; i++) {
        onMessageCallback!({
          type: 'scene_change',
          data: {
            id: i,
            camera_id: `camera_${i}`,
            detected_at: `2026-01-10T10:0${i}:00Z`,
            change_type: 'view_blocked',
            similarity_score: 0.25,
          },
        });
      }
    });

    // Should only keep the 2 most recent alerts
    expect(result.current.alerts).toHaveLength(2);
    // Most recent alert (id: 3) should be first
    expect(result.current.alerts[0].id).toBe(3);
    expect(result.current.alerts[1].id).toBe(2);
  });

  it('ignores non-scene-change messages', () => {
    const { result } = renderHook(() => useSceneChangeAlerts());

    act(() => {
      // Event message
      onMessageCallback!({
        type: 'event',
        data: {
          id: 1,
          camera_id: 'front_door',
          risk_score: 50,
          risk_level: 'medium',
          summary: 'Person detected',
        },
      });
    });

    act(() => {
      // System status message
      onMessageCallback!({
        type: 'system_status',
        data: {
          gpu: { utilization: 50 },
          health: 'healthy',
        },
        timestamp: '2026-01-10T10:00:00Z',
      });
    });

    expect(result.current.alerts).toEqual([]);
  });
});

describe('formatChangeType', () => {
  it('formats view_blocked', () => {
    expect(formatChangeType('view_blocked')).toBe('View Blocked');
  });

  it('formats angle_changed', () => {
    expect(formatChangeType('angle_changed')).toBe('Angle Changed');
  });

  it('formats view_tampered', () => {
    expect(formatChangeType('view_tampered')).toBe('View Tampered');
  });

  it('returns Unknown for unknown types', () => {
    expect(formatChangeType('something_else')).toBe('Unknown');
  });
});

describe('getChangeSeverity', () => {
  it('returns high for view_blocked', () => {
    expect(getChangeSeverity('view_blocked')).toBe('high');
  });

  it('returns high for view_tampered', () => {
    expect(getChangeSeverity('view_tampered')).toBe('high');
  });

  it('returns medium for angle_changed', () => {
    expect(getChangeSeverity('angle_changed')).toBe('medium');
  });

  it('returns low for unknown types', () => {
    expect(getChangeSeverity('unknown')).toBe('low');
  });
});
