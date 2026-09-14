/**
 * Tests for useAIServiceStatus hook.
 */
import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useAIServiceStatus, type AIServiceStatusMessage } from './useAIServiceStatus';

// Mock the useWebSocket hook
const mockUseWebSocket = vi.fn();

vi.mock('./useWebSocket', () => ({
  useWebSocket: (options: { onMessage?: (data: unknown) => void }) => {
    mockUseWebSocket(options);
    return {
      isConnected: true,
      lastMessage: null,
      send: vi.fn(),
      connect: vi.fn(),
      disconnect: vi.fn(),
      hasExhaustedRetries: false,
      reconnectCount: 0,
      lastHeartbeat: null,
    };
  },
}));

// Mock the API service
vi.mock('../services/api', () => ({
  buildWebSocketOptions: (path: string) => ({
    url: `ws://localhost:8000${path}`,
    protocols: [],
  }),
}));

describe('useAIServiceStatus', () => {
  let capturedOnMessage: ((data: unknown) => void) | undefined;

  beforeEach(() => {
    vi.clearAllMocks();
    mockUseWebSocket.mockImplementation((options: { onMessage?: (data: unknown) => void }) => {
      capturedOnMessage = options.onMessage;
    });
  });

  afterEach(() => {
    capturedOnMessage = undefined;
  });

  it('returns initial state with normal degradation mode', () => {
    const { result } = renderHook(() => useAIServiceStatus());

    expect(result.current.degradationMode).toBe('normal');
    expect(result.current.availableFeatures).toEqual([]);
    expect(result.current.hasUnavailableService).toBe(false);
    expect(result.current.isOffline).toBe(false);
    expect(result.current.isDegraded).toBe(false);
    expect(result.current.lastUpdate).toBeNull();
  });

  it('returns null for all services initially', () => {
    const { result } = renderHook(() => useAIServiceStatus());

    expect(result.current.services.rtdetr).toBeNull();
    expect(result.current.services.nemotron).toBeNull();
    expect(result.current.services.florence).toBeNull();
    expect(result.current.services.clip).toBeNull();
  });

  it('updates state when receiving ai_service_status message', async () => {
    const { result } = renderHook(() => useAIServiceStatus());

    const message: AIServiceStatusMessage = {
      type: 'ai_service_status',
      timestamp: '2024-01-15T12:00:00Z',
      degradation_mode: 'degraded',
      services: {
        rtdetr: {
          service: 'rtdetr',
          status: 'healthy',
          circuit_state: 'closed',
          last_success: '2024-01-15T11:59:00Z',
          failure_count: 0,
          error_message: null,
          last_check: '2024-01-15T12:00:00Z',
        },
        nemotron: {
          service: 'nemotron',
          status: 'healthy',
          circuit_state: 'closed',
          last_success: '2024-01-15T11:59:00Z',
          failure_count: 0,
          error_message: null,
          last_check: '2024-01-15T12:00:00Z',
        },
        florence: {
          service: 'florence',
          status: 'unavailable',
          circuit_state: 'open',
          last_success: null,
          failure_count: 5,
          error_message: 'Connection refused',
          last_check: '2024-01-15T12:00:00Z',
        },
        clip: {
          service: 'clip',
          status: 'healthy',
          circuit_state: 'closed',
          last_success: '2024-01-15T11:59:00Z',
          failure_count: 0,
          error_message: null,
          last_check: '2024-01-15T12:00:00Z',
        },
      },
      available_features: ['object_detection', 'risk_analysis', 'entity_tracking'],
    };

    act(() => {
      capturedOnMessage?.(message);
    });

    await waitFor(() => {
      expect(result.current.degradationMode).toBe('degraded');
      expect(result.current.lastUpdate).toBe('2024-01-15T12:00:00Z');
      expect(result.current.availableFeatures).toContain('object_detection');
      expect(result.current.services.florence?.status).toBe('unavailable');
    });
  });

  it('calculates hasUnavailableService correctly', async () => {
    const { result } = renderHook(() => useAIServiceStatus());

    const message: AIServiceStatusMessage = {
      type: 'ai_service_status',
      timestamp: '2024-01-15T12:00:00Z',
      degradation_mode: 'minimal',
      services: {
        rtdetr: {
          service: 'rtdetr',
          status: 'unavailable',
          circuit_state: 'open',
          last_success: null,
          failure_count: 3,
          error_message: 'Timeout',
          last_check: '2024-01-15T12:00:00Z',
        },
        nemotron: {
          service: 'nemotron',
          status: 'healthy',
          circuit_state: 'closed',
          last_success: '2024-01-15T11:59:00Z',
          failure_count: 0,
          error_message: null,
          last_check: '2024-01-15T12:00:00Z',
        },
        florence: {
          service: 'florence',
          status: 'healthy',
          circuit_state: 'closed',
          last_success: '2024-01-15T11:59:00Z',
          failure_count: 0,
          error_message: null,
          last_check: '2024-01-15T12:00:00Z',
        },
        clip: {
          service: 'clip',
          status: 'healthy',
          circuit_state: 'closed',
          last_success: '2024-01-15T11:59:00Z',
          failure_count: 0,
          error_message: null,
          last_check: '2024-01-15T12:00:00Z',
        },
      },
      available_features: ['risk_analysis'],
    };

    act(() => {
      capturedOnMessage?.(message);
    });

    await waitFor(() => {
      expect(result.current.hasUnavailableService).toBe(true);
    });
  });

  it('calculates isOffline correctly', async () => {
    const { result } = renderHook(() => useAIServiceStatus());

    const message: AIServiceStatusMessage = {
      type: 'ai_service_status',
      timestamp: '2024-01-15T12:00:00Z',
      degradation_mode: 'offline',
      services: {
        rtdetr: {
          service: 'rtdetr',
          status: 'unavailable',
          circuit_state: 'open',
          last_success: null,
          failure_count: 5,
          error_message: 'Service down',
          last_check: '2024-01-15T12:00:00Z',
        },
        nemotron: {
          service: 'nemotron',
          status: 'unavailable',
          circuit_state: 'open',
          last_success: null,
          failure_count: 5,
          error_message: 'Service down',
          last_check: '2024-01-15T12:00:00Z',
        },
        florence: {
          service: 'florence',
          status: 'unavailable',
          circuit_state: 'open',
          last_success: null,
          failure_count: 5,
          error_message: 'Service down',
          last_check: '2024-01-15T12:00:00Z',
        },
        clip: {
          service: 'clip',
          status: 'unavailable',
          circuit_state: 'open',
          last_success: null,
          failure_count: 5,
          error_message: 'Service down',
          last_check: '2024-01-15T12:00:00Z',
        },
      },
      available_features: ['event_history', 'camera_feeds'],
    };

    act(() => {
      capturedOnMessage?.(message);
    });

    await waitFor(() => {
      expect(result.current.isOffline).toBe(true);
      expect(result.current.isDegraded).toBe(true);
    });
  });

  it('getServiceState returns correct service state', async () => {
    const { result } = renderHook(() => useAIServiceStatus());

    const message: AIServiceStatusMessage = {
      type: 'ai_service_status',
      timestamp: '2024-01-15T12:00:00Z',
      degradation_mode: 'normal',
      services: {
        rtdetr: {
          service: 'rtdetr',
          status: 'healthy',
          circuit_state: 'closed',
          last_success: '2024-01-15T11:59:00Z',
          failure_count: 0,
          error_message: null,
          last_check: '2024-01-15T12:00:00Z',
        },
        nemotron: {
          service: 'nemotron',
          status: 'healthy',
          circuit_state: 'closed',
          last_success: '2024-01-15T11:59:00Z',
          failure_count: 0,
          error_message: null,
          last_check: '2024-01-15T12:00:00Z',
        },
        florence: {
          service: 'florence',
          status: 'healthy',
          circuit_state: 'closed',
          last_success: '2024-01-15T11:59:00Z',
          failure_count: 0,
          error_message: null,
          last_check: '2024-01-15T12:00:00Z',
        },
        clip: {
          service: 'clip',
          status: 'healthy',
          circuit_state: 'closed',
          last_success: '2024-01-15T11:59:00Z',
          failure_count: 0,
          error_message: null,
          last_check: '2024-01-15T12:00:00Z',
        },
      },
      available_features: ['object_detection', 'risk_analysis'],
    };

    act(() => {
      capturedOnMessage?.(message);
    });

    await waitFor(() => {
      const rtdetrState = result.current.getServiceState('rtdetr');
      expect(rtdetrState?.status).toBe('healthy');
      expect(rtdetrState?.circuit_state).toBe('closed');
    });
  });

  it('isFeatureAvailable returns correct value', async () => {
    const { result } = renderHook(() => useAIServiceStatus());

    const message: AIServiceStatusMessage = {
      type: 'ai_service_status',
      timestamp: '2024-01-15T12:00:00Z',
      degradation_mode: 'degraded',
      services: {
        rtdetr: {
          service: 'rtdetr',
          status: 'healthy',
          circuit_state: 'closed',
          last_success: '2024-01-15T11:59:00Z',
          failure_count: 0,
          error_message: null,
          last_check: '2024-01-15T12:00:00Z',
        },
        nemotron: {
          service: 'nemotron',
          status: 'healthy',
          circuit_state: 'closed',
          last_success: '2024-01-15T11:59:00Z',
          failure_count: 0,
          error_message: null,
          last_check: '2024-01-15T12:00:00Z',
        },
        florence: {
          service: 'florence',
          status: 'unavailable',
          circuit_state: 'open',
          last_success: null,
          failure_count: 5,
          error_message: 'Down',
          last_check: '2024-01-15T12:00:00Z',
        },
        clip: {
          service: 'clip',
          status: 'healthy',
          circuit_state: 'closed',
          last_success: '2024-01-15T11:59:00Z',
          failure_count: 0,
          error_message: null,
          last_check: '2024-01-15T12:00:00Z',
        },
      },
      available_features: ['object_detection', 'risk_analysis', 'entity_tracking'],
    };

    act(() => {
      capturedOnMessage?.(message);
    });

    await waitFor(() => {
      expect(result.current.isFeatureAvailable('object_detection')).toBe(true);
      expect(result.current.isFeatureAvailable('image_captioning')).toBe(false);
    });
  });

  it('ignores non-ai_service_status messages', () => {
    const { result } = renderHook(() => useAIServiceStatus());

    act(() => {
      capturedOnMessage?.({
        type: 'service_status',
        data: { service: 'redis', status: 'healthy' },
        timestamp: '2024-01-15T12:00:00Z',
      });
    });

    // State should remain unchanged
    expect(result.current.degradationMode).toBe('normal');
    expect(result.current.services.rtdetr).toBeNull();
  });

  it('ignores malformed messages', () => {
    const { result } = renderHook(() => useAIServiceStatus());

    act(() => {
      capturedOnMessage?.({
        type: 'ai_service_status',
        // Missing required fields
      });
    });

    // State should remain unchanged
    expect(result.current.degradationMode).toBe('normal');
  });
});
