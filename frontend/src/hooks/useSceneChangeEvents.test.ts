import { renderHook, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import * as useCamerasQueryModule from './useCamerasQuery';
import { useSceneChangeEvents } from './useSceneChangeEvents';
import * as useToastModule from './useToast';
import * as useWebSocketModule from './useWebSocket';

import type { UseCamerasQueryReturn } from './useCamerasQuery';
import type { UseToastReturn } from './useToast';
import type { UseWebSocketReturn } from './useWebSocket';

// Mock dependencies
vi.mock('./useWebSocket', () => ({
  useWebSocket: vi.fn(),
}));

vi.mock('./useCamerasQuery', () => ({
  useCamerasQuery: vi.fn(),
}));

vi.mock('./useToast', () => ({
  useToast: vi.fn(),
}));

vi.mock('../services/api', () => ({
  buildWebSocketOptions: vi.fn(() => ({
    url: 'ws://localhost:8000/ws/events',
    protocols: [],
  })),
}));

describe('useSceneChangeEvents', () => {
  let onMessageCallback: ((data: unknown) => void) | null = null;
  let mockToast: UseToastReturn;

  beforeEach(() => {
    vi.useFakeTimers();
    onMessageCallback = null;

    // Mock useWebSocket
    vi.spyOn(useWebSocketModule, 'useWebSocket').mockImplementation((options) => {
      onMessageCallback = options.onMessage ?? null;
      return {
        isConnected: true,
        lastMessage: null,
        send: vi.fn(),
        connect: vi.fn(),
        disconnect: vi.fn(),
        hasExhaustedRetries: false,
        reconnectCount: 0,
        lastHeartbeat: null,
        connectionId: 'test-connection-id',
      } as UseWebSocketReturn;
    });

    // Mock useCamerasQuery with some test cameras
    vi.spyOn(useCamerasQueryModule, 'useCamerasQuery').mockReturnValue({
      cameras: [
        {
          id: 'front_door',
          name: 'Front Door Camera',
          folder_path: '/cameras/front',
          status: 'online',
          last_seen_at: null,
          created_at: '2026-01-01T00:00:00Z',
        },
        {
          id: 'back_yard',
          name: 'Back Yard Camera',
          folder_path: '/cameras/back',
          status: 'online',
          last_seen_at: null,
          created_at: '2026-01-01T00:00:00Z',
        },
        {
          id: 'garage',
          name: 'Garage Camera',
          folder_path: '/cameras/garage',
          status: 'online',
          last_seen_at: null,
          created_at: '2026-01-01T00:00:00Z',
        },
      ],
      isLoading: false,
      isRefetching: false,
      error: null,
      refetch: vi.fn(),
      isPlaceholderData: false,
    } as UseCamerasQueryReturn);

    // Mock useToast
    mockToast = {
      success: vi.fn().mockReturnValue('toast-id'),
      error: vi.fn().mockReturnValue('toast-id'),
      warning: vi.fn().mockReturnValue('toast-id'),
      info: vi.fn().mockReturnValue('toast-id'),
      loading: vi.fn().mockReturnValue('toast-id'),
      dismiss: vi.fn(),
      promise: vi.fn(),
    };
    vi.spyOn(useToastModule, 'useToast').mockReturnValue(mockToast);
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  it('returns initial state with empty activity', () => {
    const { result } = renderHook(() => useSceneChangeEvents());

    expect(result.current.cameraActivity).toEqual({});
    expect(result.current.activeCameraIds).toEqual([]);
    expect(result.current.recentEvents).toEqual([]);
    expect(result.current.isConnected).toBe(true);
    expect(result.current.totalEventCount).toBe(0);
  });

  it('processes legacy scene_change messages', () => {
    const { result } = renderHook(() => useSceneChangeEvents());

    expect(onMessageCallback).not.toBeNull();

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

    expect(result.current.recentEvents).toHaveLength(1);
    expect(result.current.recentEvents[0].id).toBe(1);
    expect(result.current.recentEvents[0].cameraId).toBe('front_door');
    expect(result.current.recentEvents[0].cameraName).toBe('Front Door Camera');
    expect(result.current.recentEvents[0].changeType).toBe('view_blocked');
    expect(result.current.totalEventCount).toBe(1);
    expect(result.current.activeCameraIds).toContain('front_door');
  });

  it('processes hierarchical scene_change.detected messages', () => {
    const { result } = renderHook(() => useSceneChangeEvents());

    act(() => {
      onMessageCallback!({
        type: 'scene_change.detected',
        payload: {
          id: 2,
          camera_id: 'back_yard',
          detected_at: '2026-01-10T10:05:00Z',
          change_type: 'angle_changed',
          similarity_score: 0.45,
        },
      });
    });

    expect(result.current.recentEvents).toHaveLength(1);
    expect(result.current.recentEvents[0].id).toBe(2);
    expect(result.current.recentEvents[0].cameraId).toBe('back_yard');
    expect(result.current.recentEvents[0].cameraName).toBe('Back Yard Camera');
    expect(result.current.recentEvents[0].changeType).toBe('angle_changed');
    expect(result.current.totalEventCount).toBe(1);
    expect(result.current.activeCameraIds).toContain('back_yard');
  });

  it('shows warning toast for high severity scene changes (view_blocked)', () => {
    renderHook(() => useSceneChangeEvents({ showToasts: true }));

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

    expect(mockToast.warning).toHaveBeenCalledWith(
      'Scene change detected on Front Door Camera',
      expect.objectContaining({
        description: 'View Blocked (similarity: 25%)',
        duration: 8000,
      })
    );
  });

  it('shows warning toast for high severity scene changes (view_tampered)', () => {
    renderHook(() => useSceneChangeEvents({ showToasts: true }));

    act(() => {
      onMessageCallback!({
        type: 'scene_change',
        data: {
          id: 1,
          camera_id: 'front_door',
          detected_at: '2026-01-10T10:00:00Z',
          change_type: 'view_tampered',
          similarity_score: 0.15,
        },
      });
    });

    expect(mockToast.warning).toHaveBeenCalledWith(
      'Scene change detected on Front Door Camera',
      expect.objectContaining({
        description: 'View Tampered (similarity: 15%)',
        duration: 8000,
      })
    );
  });

  it('shows info toast for medium severity scene changes (angle_changed)', () => {
    renderHook(() => useSceneChangeEvents({ showToasts: true }));

    act(() => {
      onMessageCallback!({
        type: 'scene_change',
        data: {
          id: 1,
          camera_id: 'front_door',
          detected_at: '2026-01-10T10:00:00Z',
          change_type: 'angle_changed',
          similarity_score: 0.45,
        },
      });
    });

    expect(mockToast.info).toHaveBeenCalledWith(
      'Scene change detected on Front Door Camera',
      expect.objectContaining({
        description: 'Angle Changed (similarity: 45%)',
        duration: 5000,
      })
    );
  });

  it('does not show toast when showToasts is false', () => {
    renderHook(() => useSceneChangeEvents({ showToasts: false }));

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

    expect(mockToast.warning).not.toHaveBeenCalled();
    expect(mockToast.info).not.toHaveBeenCalled();
  });

  it('falls back to camera ID when camera name is not found', () => {
    renderHook(() => useSceneChangeEvents({ showToasts: true }));

    act(() => {
      onMessageCallback!({
        type: 'scene_change',
        data: {
          id: 1,
          camera_id: 'unknown_camera',
          detected_at: '2026-01-10T10:00:00Z',
          change_type: 'view_blocked',
          similarity_score: 0.25,
        },
      });
    });

    expect(mockToast.warning).toHaveBeenCalledWith(
      'Scene change detected on unknown_camera',
      expect.anything()
    );
  });

  it('tracks camera activity state', () => {
    const { result } = renderHook(() => useSceneChangeEvents());

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

    expect(result.current.cameraActivity['front_door']).toBeDefined();
    expect(result.current.cameraActivity['front_door'].isActive).toBe(true);
    expect(result.current.cameraActivity['front_door'].cameraName).toBe('Front Door Camera');
    expect(result.current.cameraActivity['front_door'].lastChangeType).toBe('view_blocked');
    expect(result.current.hasRecentActivity('front_door')).toBe(true);
    expect(result.current.hasRecentActivity('back_yard')).toBe(false);
  });

  it('clears activity after timeout', () => {
    const { result } = renderHook(() => useSceneChangeEvents({ activityTimeoutMs: 5000 }));

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

    expect(result.current.hasRecentActivity('front_door')).toBe(true);

    // Fast-forward timer
    act(() => {
      vi.advanceTimersByTime(5000);
    });

    expect(result.current.hasRecentActivity('front_door')).toBe(false);
    expect(result.current.cameraActivity['front_door'].isActive).toBe(false);
  });

  it('clears activity manually for a specific camera', () => {
    const { result } = renderHook(() => useSceneChangeEvents());

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

    expect(result.current.activeCameraIds).toHaveLength(2);

    act(() => {
      result.current.clearActivity('front_door');
    });

    expect(result.current.hasRecentActivity('front_door')).toBe(false);
    expect(result.current.hasRecentActivity('back_yard')).toBe(true);
    expect(result.current.activeCameraIds).toEqual(['back_yard']);
  });

  it('clears all activity manually', () => {
    const { result } = renderHook(() => useSceneChangeEvents());

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

    expect(result.current.activeCameraIds).toHaveLength(2);

    act(() => {
      result.current.clearAllActivity();
    });

    expect(result.current.activeCameraIds).toEqual([]);
    expect(result.current.hasRecentActivity('front_door')).toBe(false);
    expect(result.current.hasRecentActivity('back_yard')).toBe(false);
  });

  it('calls onSceneChange callback', () => {
    const onSceneChange = vi.fn();
    renderHook(() => useSceneChangeEvents({ onSceneChange }));

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

    expect(onSceneChange).toHaveBeenCalledWith(
      expect.objectContaining({
        id: 1,
        cameraId: 'front_door',
        cameraName: 'Front Door Camera',
        changeType: 'view_blocked',
      })
    );
  });

  it('prevents duplicate events by ID', () => {
    const { result } = renderHook(() => useSceneChangeEvents());

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
      // Same event ID
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

    expect(result.current.recentEvents).toHaveLength(1);
    // But totalEventCount is still incremented
    expect(result.current.totalEventCount).toBe(2);
  });

  it('respects maxRecentEvents option', () => {
    const { result } = renderHook(() => useSceneChangeEvents({ maxRecentEvents: 2 }));

    // Add 3 events
    for (let i = 1; i <= 3; i++) {
      act(() => {
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
      });
    }

    expect(result.current.recentEvents).toHaveLength(2);
    // Most recent should be first
    expect(result.current.recentEvents[0].id).toBe(3);
    expect(result.current.recentEvents[1].id).toBe(2);
  });

  it('ignores non-scene-change messages', () => {
    const { result } = renderHook(() => useSceneChangeEvents());

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

    expect(result.current.recentEvents).toEqual([]);
    expect(result.current.totalEventCount).toBe(0);
  });

  it('returns activity state via getActivityState', () => {
    const { result } = renderHook(() => useSceneChangeEvents());

    expect(result.current.getActivityState('front_door')).toBeUndefined();

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

    const state = result.current.getActivityState('front_door');
    expect(state).toBeDefined();
    expect(state?.cameraId).toBe('front_door');
    expect(state?.cameraName).toBe('Front Door Camera');
    expect(state?.isActive).toBe(true);
    expect(state?.lastChangeType).toBe('view_blocked');
  });
});
