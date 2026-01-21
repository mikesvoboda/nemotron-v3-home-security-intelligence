/**
 * Tests for useZonePresence hook
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, act } from '@testing-library/react';
import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useZonePresence } from './useZonePresence';

import type { HouseholdMember } from './useHouseholdApi';
import type { DetectionNewPayload, EventCreatedPayload } from '../types/websocket-events';

// ============================================================================
// Mocks
// ============================================================================

// Mock household members data
const mockHouseholdMembers: HouseholdMember[] = [
  {
    id: 1,
    name: 'John Doe',
    role: 'resident',
    trusted_level: 'full',
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  },
  {
    id: 2,
    name: 'Jane Smith',
    role: 'family',
    trusted_level: 'full',
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  },
  {
    id: 3,
    name: 'Bob Service',
    role: 'service_worker',
    trusted_level: 'partial',
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  },
];

// Mock the household API hook
const mockUseMembersQuery = vi.fn();
vi.mock('./useHouseholdApi', () => ({
  useMembersQuery: () => mockUseMembersQuery(),
}));

// Track WebSocket event handlers
type WebSocketEventHandlers = Record<string, ((payload: unknown) => void) | undefined>;
let capturedHandlers: WebSocketEventHandlers = {};
const mockUseWebSocketEvents = vi.fn();

vi.mock('./useWebSocketEvent', () => ({
  useWebSocketEvents: (handlers: WebSocketEventHandlers, options: { enabled?: boolean }) => {
    // Store handlers for testing
    capturedHandlers = handlers;
    return mockUseWebSocketEvents(handlers, options);
  },
}));

// ============================================================================
// Test Setup
// ============================================================================

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        staleTime: 0,
        gcTime: 0,
      },
    },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

describe('useZonePresence', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    capturedHandlers = {};

    // Default mock implementations
    mockUseMembersQuery.mockReturnValue({
      data: mockHouseholdMembers,
      isLoading: false,
      error: null,
    });

    mockUseWebSocketEvents.mockReturnValue({
      isConnected: true,
      reconnectCount: 0,
      hasExhaustedRetries: false,
      lastHeartbeat: null,
      reconnect: vi.fn(),
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Initial State', () => {
    it('should return empty members list initially', () => {
      const { result } = renderHook(() => useZonePresence('zone-1'), {
        wrapper: createWrapper(),
      });

      expect(result.current.members).toEqual([]);
      expect(result.current.presentCount).toBe(0);
      expect(result.current.activeCount).toBe(0);
    });

    it('should return loading state from household query', () => {
      mockUseMembersQuery.mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
      });

      const { result } = renderHook(() => useZonePresence('zone-1'), {
        wrapper: createWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('should return error state from household query', () => {
      const error = new Error('Failed to fetch members');
      mockUseMembersQuery.mockReturnValue({
        data: undefined,
        isLoading: false,
        error,
      });

      const { result } = renderHook(() => useZonePresence('zone-1'), {
        wrapper: createWrapper(),
      });

      expect(result.current.error).toBe(error);
    });

    it('should return WebSocket connection state', () => {
      mockUseWebSocketEvents.mockReturnValue({
        isConnected: true,
        reconnectCount: 0,
        hasExhaustedRetries: false,
        lastHeartbeat: null,
        reconnect: vi.fn(),
      });

      const { result } = renderHook(() => useZonePresence('zone-1'), {
        wrapper: createWrapper(),
      });

      expect(result.current.isConnected).toBe(true);
    });

    it('should return disconnected state when WebSocket is not connected', () => {
      mockUseWebSocketEvents.mockReturnValue({
        isConnected: false,
        reconnectCount: 2,
        hasExhaustedRetries: false,
        lastHeartbeat: null,
        reconnect: vi.fn(),
      });

      const { result } = renderHook(() => useZonePresence('zone-1'), {
        wrapper: createWrapper(),
      });

      expect(result.current.isConnected).toBe(false);
    });
  });

  describe('Detection Event Handling', () => {
    it('should add member presence on detection event', () => {
      const { result } = renderHook(() => useZonePresence('zone-1'), {
        wrapper: createWrapper(),
      });

      const detectionPayload: DetectionNewPayload = {
        detection_id: 'det-1',
        label: 'person',
        confidence: 0.95,
        camera_id: 'cam-1',
        timestamp: new Date().toISOString(),
      };

      act(() => {
        capturedHandlers['detection.new']?.(detectionPayload);
      });

      expect(result.current.members.length).toBe(1);
      expect(result.current.presentCount).toBe(1);
    });

    it('should mark member as active for recent detections', () => {
      const { result } = renderHook(
        () =>
          useZonePresence('zone-1', {
            activeThresholdMs: 30000,
          }),
        { wrapper: createWrapper() }
      );

      const detectionPayload: DetectionNewPayload = {
        detection_id: 'det-1',
        label: 'person',
        confidence: 0.95,
        camera_id: 'cam-1',
        timestamp: new Date().toISOString(),
      };

      act(() => {
        capturedHandlers['detection.new']?.(detectionPayload);
      });

      expect(result.current.members[0]?.isActive).toBe(true);
      expect(result.current.activeCount).toBe(1);
    });

    it('should mark member as stale after threshold', () => {
      const staleThresholdMs = 5 * 60 * 1000; // 5 minutes
      const { result } = renderHook(
        () =>
          useZonePresence('zone-1', {
            staleThresholdMs,
            activeThresholdMs: 30000,
          }),
        { wrapper: createWrapper() }
      );

      // Create timestamp 6 minutes ago
      const pastTimestamp = new Date(Date.now() - 6 * 60 * 1000).toISOString();

      const detectionPayload: DetectionNewPayload = {
        detection_id: 'det-1',
        label: 'person',
        confidence: 0.95,
        camera_id: 'cam-1',
        timestamp: pastTimestamp,
      };

      act(() => {
        capturedHandlers['detection.new']?.(detectionPayload);
      });

      expect(result.current.members[0]?.isStale).toBe(true);
      expect(result.current.members[0]?.isActive).toBe(false);
    });

    it('should not add presence for non-person detections', () => {
      const { result } = renderHook(() => useZonePresence('zone-1'), {
        wrapper: createWrapper(),
      });

      const detectionPayload: DetectionNewPayload = {
        detection_id: 'det-1',
        label: 'car',
        confidence: 0.95,
        camera_id: 'cam-1',
        timestamp: new Date().toISOString(),
      };

      act(() => {
        capturedHandlers['detection.new']?.(detectionPayload);
      });

      expect(result.current.members.length).toBe(0);
    });

    it('should ignore detections for other zones', () => {
      const { result } = renderHook(() => useZonePresence('zone-1'), {
        wrapper: createWrapper(),
      });

      const detectionPayload: DetectionNewPayload & { zone_id?: string } = {
        detection_id: 'det-1',
        label: 'person',
        confidence: 0.95,
        camera_id: 'cam-1',
        timestamp: new Date().toISOString(),
        zone_id: 'zone-2', // Different zone
      };

      act(() => {
        capturedHandlers['detection.new']?.(detectionPayload);
      });

      expect(result.current.members.length).toBe(0);
    });

    it('should update existing member presence on new detection', () => {
      const { result } = renderHook(() => useZonePresence('zone-1'), {
        wrapper: createWrapper(),
      });

      // First detection
      const firstTimestamp = new Date(Date.now() - 60000).toISOString();
      act(() => {
        capturedHandlers['detection.new']?.({
          detection_id: 'det-1',
          label: 'person',
          confidence: 0.95,
          camera_id: 'cam-1',
          timestamp: firstTimestamp,
        });
      });

      const firstLastSeen = result.current.members[0]?.lastSeen;

      // Second detection with newer timestamp
      const secondTimestamp = new Date().toISOString();
      act(() => {
        capturedHandlers['detection.new']?.({
          detection_id: 'det-2',
          label: 'person',
          confidence: 0.95,
          camera_id: 'cam-1',
          timestamp: secondTimestamp,
        });
      });

      // Should still be 1 member, but with updated timestamp
      expect(result.current.members.length).toBe(1);
      expect(result.current.members[0]?.lastSeen).not.toBe(firstLastSeen);
    });
  });

  describe('Event Created Handling', () => {
    it('should add member presence on event created', () => {
      const { result } = renderHook(() => useZonePresence('zone-1'), {
        wrapper: createWrapper(),
      });

      const eventPayload: EventCreatedPayload = {
        id: 1,
        event_id: 1,
        batch_id: 'batch-1',
        camera_id: 'cam-1',
        risk_score: 50,
        risk_level: 'medium',
        summary: 'Person detected',
        reasoning: 'Person detected in zone',
        started_at: new Date().toISOString(),
      };

      act(() => {
        capturedHandlers['event.created']?.(eventPayload);
      });

      expect(result.current.members.length).toBe(1);
    });

    it('should handle event without started_at timestamp', () => {
      const { result } = renderHook(() => useZonePresence('zone-1'), {
        wrapper: createWrapper(),
      });

      const eventPayload: EventCreatedPayload = {
        id: 1,
        event_id: 1,
        batch_id: 'batch-1',
        camera_id: 'cam-1',
        risk_score: 50,
        risk_level: 'medium',
        summary: 'Person detected',
        reasoning: 'Person detected in zone',
      };

      act(() => {
        capturedHandlers['event.created']?.(eventPayload);
      });

      expect(result.current.members.length).toBe(1);
      expect(result.current.members[0]?.lastSeen).toBeDefined();
    });
  });

  describe('Zone Change Handling', () => {
    it('should clear presence when zone changes', () => {
      const { result, rerender } = renderHook(
        ({ zoneId }: { zoneId: string }) => useZonePresence(zoneId),
        {
          wrapper: createWrapper(),
          initialProps: { zoneId: 'zone-1' },
        }
      );

      // Add a detection
      act(() => {
        capturedHandlers['detection.new']?.({
          detection_id: 'det-1',
          label: 'person',
          confidence: 0.95,
          camera_id: 'cam-1',
          timestamp: new Date().toISOString(),
        });
      });

      expect(result.current.members.length).toBe(1);

      // Change zone
      rerender({ zoneId: 'zone-2' });

      expect(result.current.members.length).toBe(0);
    });
  });

  describe('clearPresence', () => {
    it('should clear all presence records', () => {
      const { result } = renderHook(() => useZonePresence('zone-1'), {
        wrapper: createWrapper(),
      });

      // Add a detection
      act(() => {
        capturedHandlers['detection.new']?.({
          detection_id: 'det-1',
          label: 'person',
          confidence: 0.95,
          camera_id: 'cam-1',
          timestamp: new Date().toISOString(),
        });
      });

      expect(result.current.members.length).toBe(1);

      // Clear presence
      act(() => {
        result.current.clearPresence();
      });

      expect(result.current.members.length).toBe(0);
      expect(result.current.presentCount).toBe(0);
    });

    it('should be a stable function reference', () => {
      const { result, rerender } = renderHook(() => useZonePresence('zone-1'), {
        wrapper: createWrapper(),
      });

      const firstRef = result.current.clearPresence;
      rerender();
      const secondRef = result.current.clearPresence;

      expect(firstRef).toBe(secondRef);
    });
  });

  describe('Enabled Option', () => {
    it('should not subscribe to WebSocket when disabled', () => {
      renderHook(() => useZonePresence('zone-1', { enabled: false }), {
        wrapper: createWrapper(),
      });

      expect(mockUseWebSocketEvents).toHaveBeenCalledWith(
        expect.any(Object),
        expect.objectContaining({ enabled: false })
      );
    });

    it('should subscribe to WebSocket when enabled', () => {
      renderHook(() => useZonePresence('zone-1', { enabled: true }), {
        wrapper: createWrapper(),
      });

      expect(mockUseWebSocketEvents).toHaveBeenCalledWith(
        expect.any(Object),
        expect.objectContaining({ enabled: true })
      );
    });
  });

  describe('Empty Household Members', () => {
    it('should handle empty household members', () => {
      mockUseMembersQuery.mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      });

      const { result } = renderHook(() => useZonePresence('zone-1'), {
        wrapper: createWrapper(),
      });

      // Try to add a detection
      act(() => {
        capturedHandlers['detection.new']?.({
          detection_id: 'det-1',
          label: 'person',
          confidence: 0.95,
          camera_id: 'cam-1',
          timestamp: new Date().toISOString(),
        });
      });

      expect(result.current.members.length).toBe(0);
    });

    it('should handle undefined household members', () => {
      mockUseMembersQuery.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: null,
      });

      const { result } = renderHook(() => useZonePresence('zone-1'), {
        wrapper: createWrapper(),
      });

      expect(result.current.members).toEqual([]);
    });

    it('should not crash when event created with no members', () => {
      mockUseMembersQuery.mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      });

      const { result } = renderHook(() => useZonePresence('zone-1'), {
        wrapper: createWrapper(),
      });

      act(() => {
        capturedHandlers['event.created']?.({
          id: 1,
          event_id: 1,
          batch_id: 'batch-1',
          camera_id: 'cam-1',
          risk_score: 50,
          risk_level: 'medium',
          summary: 'Person detected',
          reasoning: 'Person detected in zone',
        });
      });

      expect(result.current.members.length).toBe(0);
    });
  });

  describe('Member Sorting', () => {
    it('should sort members by most recently seen', () => {
      mockUseMembersQuery.mockReturnValue({
        data: [
          { ...mockHouseholdMembers[0], id: 1 },
          { ...mockHouseholdMembers[1], id: 2 },
        ],
        isLoading: false,
        error: null,
      });

      const { result } = renderHook(() => useZonePresence('zone-1'), {
        wrapper: createWrapper(),
      });

      // Add detection
      act(() => {
        capturedHandlers['detection.new']?.({
          detection_id: 'det-1',
          label: 'person',
          confidence: 0.95,
          camera_id: 'cam-1',
          timestamp: new Date().toISOString(),
        });
      });

      expect(result.current.members.length).toBe(1);
      expect(result.current.members[0]).toBeDefined();
    });
  });

  describe('Options Validation', () => {
    it('should use default options when not provided', () => {
      const { result } = renderHook(() => useZonePresence('zone-1'), {
        wrapper: createWrapper(),
      });

      expect(result.current).toBeDefined();
      expect(result.current.members).toEqual([]);
    });

    it('should accept custom stale and active thresholds', () => {
      const customStaleMs = 10 * 60 * 1000; // 10 minutes
      const customActiveMs = 60 * 1000; // 1 minute

      const { result } = renderHook(
        () =>
          useZonePresence('zone-1', {
            staleThresholdMs: customStaleMs,
            activeThresholdMs: customActiveMs,
          }),
        { wrapper: createWrapper() }
      );

      // Add detection 2 minutes ago
      const timestamp = new Date(Date.now() - 2 * 60 * 1000).toISOString();

      act(() => {
        capturedHandlers['detection.new']?.({
          detection_id: 'det-1',
          label: 'person',
          confidence: 0.95,
          camera_id: 'cam-1',
          timestamp,
        });
      });

      expect(result.current.members.length).toBe(1);
      // 2 minutes > 1 minute active threshold
      expect(result.current.members[0]?.isActive).toBe(false);
      // 2 minutes < 10 minutes stale threshold
      expect(result.current.members[0]?.isStale).toBe(false);
    });
  });

  describe('WebSocket Handlers Registration', () => {
    it('should register detection.new handler', () => {
      renderHook(() => useZonePresence('zone-1'), {
        wrapper: createWrapper(),
      });

      expect(capturedHandlers['detection.new']).toBeDefined();
      expect(typeof capturedHandlers['detection.new']).toBe('function');
    });

    it('should register event.created handler', () => {
      renderHook(() => useZonePresence('zone-1'), {
        wrapper: createWrapper(),
      });

      expect(capturedHandlers['event.created']).toBeDefined();
      expect(typeof capturedHandlers['event.created']).toBe('function');
    });
  });

  describe('Detection without timestamp', () => {
    it('should use current time when detection has no timestamp', () => {
      const { result } = renderHook(() => useZonePresence('zone-1'), {
        wrapper: createWrapper(),
      });

      const detectionPayload: DetectionNewPayload = {
        detection_id: 'det-1',
        label: 'person',
        confidence: 0.95,
        camera_id: 'cam-1',
      };

      const beforeTime = Date.now();
      act(() => {
        capturedHandlers['detection.new']?.(detectionPayload);
      });
      const afterTime = Date.now();

      expect(result.current.members.length).toBe(1);
      const memberLastSeen = new Date(result.current.members[0]?.lastSeen ?? '').getTime();
      expect(memberLastSeen).toBeGreaterThanOrEqual(beforeTime);
      expect(memberLastSeen).toBeLessThanOrEqual(afterTime);
    });
  });
});
