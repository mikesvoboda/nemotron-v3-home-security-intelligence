/**
 * useRtspPreview Hook Test Suite (NEM-4760 Phase 4: Live Preview)
 *
 * TDD Red Phase: Tests MUST FAIL until useRtspPreview hook is implemented
 *
 * Tests cover:
 * - Initial idle state
 * - Connection state transitions
 * - Successful WebRTC connection
 * - Error handling
 * - Stream cleanup on stop
 * - Cleanup on unmount
 * - Multiple consecutive preview requests
 */

import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useRtspPreview } from './useRtspPreview';

import type { PreviewConfig } from '../types/preview';

// Mock go2rtc client - must use inline object to avoid hoisting issues
vi.mock('../services/go2rtcClient', () => ({
  go2rtcClient: {
    createPreview: vi.fn(),
    stopPreview: vi.fn(),
  },
}));

// Get a reference to the mock for test assertions
const mockGo2rtcClient = vi.mocked(
  (await import('../services/go2rtcClient')).go2rtcClient
);

// Mock RTCPeerConnection
class MockRTCPeerConnection {
  localDescription: RTCSessionDescription | null = null;
  remoteDescription: RTCSessionDescription | null = null;
  connectionState: RTCPeerConnectionState = 'new';
  onicecandidate: ((event: RTCPeerConnectionIceEvent) => void) | null = null;
  ontrack: ((event: RTCTrackEvent) => void) | null = null;
  onconnectionstatechange: ((event: Event) => void) | null = null;

  createOffer(): Promise<RTCSessionDescriptionInit> {
    return Promise.resolve({
      type: 'offer' as RTCSdpType,
      sdp: 'mock-offer-sdp',
    });
  }

  setLocalDescription(description: RTCSessionDescriptionInit): Promise<void> {
    this.localDescription = description as RTCSessionDescription;
    return Promise.resolve();
  }

  setRemoteDescription(description: RTCSessionDescriptionInit): Promise<void> {
    this.remoteDescription = description as RTCSessionDescription;
    return Promise.resolve();
  }

  addTransceiver(_kind: string, _init?: RTCRtpTransceiverInit): RTCRtpTransceiver {
    return {} as RTCRtpTransceiver;
  }

  close(): void {
    this.connectionState = 'closed';
  }
}

// Setup WebRTC mocks
beforeEach(() => {
  // @ts-expect-error - Mock for testing
  global.RTCPeerConnection = MockRTCPeerConnection;
  vi.clearAllMocks();
});

afterEach(() => {
  vi.resetAllMocks();
});

describe('useRtspPreview', () => {
  describe('Initial State', () => {
    it('should initialize with idle state', () => {
      const { result } = renderHook(() => useRtspPreview());

      expect(result.current.state).toBe('idle');
      expect(result.current.error).toBeUndefined();
      expect(result.current.peerConnection).toBeUndefined();
    });
  });

  describe('Connection Lifecycle', () => {
    it('should transition to connecting when startPreview is called', async () => {
      mockGo2rtcClient.createPreview.mockResolvedValue({
        type: 'answer' as RTCSdpType,
        sdp: 'mock-answer-sdp',
      });

      const { result } = renderHook(() => useRtspPreview());

      const config: PreviewConfig = {
        rtspUrl: 'rtsp://192.168.1.100:554/stream1',
        username: 'admin',
        password: 'password123', // pragma: allowlist secret
      };

      act(() => {
        result.current.startPreview(config);
      });

      // Should immediately transition to connecting state
      await waitFor(() => {
        expect(result.current.state).toBe('connecting');
      });
    });

    it('should handle successful WebRTC connection', async () => {
      const mockAnswer = {
        type: 'answer' as RTCSdpType,
        sdp: 'mock-answer-sdp',
      };

      mockGo2rtcClient.createPreview.mockResolvedValue(mockAnswer);

      const { result } = renderHook(() => useRtspPreview());

      const config: PreviewConfig = {
        rtspUrl: 'rtsp://192.168.1.100:554/stream1',
      };

      act(() => {
        result.current.startPreview(config);
      });

      await waitFor(() => {
        expect(result.current.state).toBe('connecting');
      });

      // Simulate successful connection
      await waitFor(
        () => {
          expect(result.current.state).toBe('connected');
        },
        { timeout: 3000 }
      );

      expect(result.current.peerConnection).toBeDefined();
      expect(result.current.error).toBeUndefined();
      expect(mockGo2rtcClient.createPreview).toHaveBeenCalledWith(
        expect.objectContaining({
          rtspUrl: config.rtspUrl,
        })
      );
    });

    it('should handle connection with credentials', async () => {
      const mockAnswer = {
        type: 'answer' as RTCSdpType,
        sdp: 'mock-answer-sdp',
      };

      mockGo2rtcClient.createPreview.mockResolvedValue(mockAnswer);

      const { result } = renderHook(() => useRtspPreview());

      const config: PreviewConfig = {
        rtspUrl: 'rtsp://192.168.1.100:554/stream1',
        username: 'admin',
        password: 'secret123', // pragma: allowlist secret
      };

      act(() => {
        result.current.startPreview(config);
      });

      await waitFor(() => {
        expect(result.current.state).toBe('connecting');
      });

      await waitFor(
        () => {
          expect(result.current.state).toBe('connected');
        },
        { timeout: 3000 }
      );

      expect(mockGo2rtcClient.createPreview).toHaveBeenCalledWith(
        expect.objectContaining({
          rtspUrl: config.rtspUrl,
          username: config.username,
          password: config.password,
        })
      );
    });
  });

  describe('Error Handling', () => {
    it('should handle connection errors', async () => {
      const errorMessage = 'Failed to connect to stream';
      mockGo2rtcClient.createPreview.mockRejectedValue(new Error(errorMessage));

      const { result } = renderHook(() => useRtspPreview());

      const config: PreviewConfig = {
        rtspUrl: 'rtsp://192.168.1.100:554/stream1',
      };

      act(() => {
        result.current.startPreview(config);
      });

      await waitFor(() => {
        expect(result.current.state).toBe('connecting');
      });

      await waitFor(
        () => {
          expect(result.current.state).toBe('error');
        },
        { timeout: 3000 }
      );

      expect(result.current.error).toBe(errorMessage);
      expect(result.current.peerConnection).toBeUndefined();
    });

    it('should handle authentication errors', async () => {
      mockGo2rtcClient.createPreview.mockRejectedValue(new Error('Authentication failed'));

      const { result } = renderHook(() => useRtspPreview());

      const config: PreviewConfig = {
        rtspUrl: 'rtsp://192.168.1.100:554/stream1',
        username: 'wrong',
        password: 'credentials', // pragma: allowlist secret
      };

      act(() => {
        result.current.startPreview(config);
      });

      await waitFor(() => {
        expect(result.current.state).toBe('error');
      });

      expect(result.current.error).toContain('Authentication');
    });

    it('should handle network timeout errors', async () => {
      mockGo2rtcClient.createPreview.mockRejectedValue(new Error('Connection timeout'));

      const { result } = renderHook(() => useRtspPreview());

      const config: PreviewConfig = {
        rtspUrl: 'rtsp://192.168.1.100:554/stream1',
      };

      act(() => {
        result.current.startPreview(config);
      });

      await waitFor(() => {
        expect(result.current.state).toBe('error');
      });

      expect(result.current.error).toContain('timeout');
    });

    it('should handle invalid stream format errors', async () => {
      mockGo2rtcClient.createPreview.mockRejectedValue(new Error('Invalid stream format'));

      const { result } = renderHook(() => useRtspPreview());

      const config: PreviewConfig = {
        rtspUrl: 'rtsp://192.168.1.100:554/invalid',
      };

      act(() => {
        result.current.startPreview(config);
      });

      await waitFor(() => {
        expect(result.current.state).toBe('error');
      });

      expect(result.current.error).toContain('Invalid stream format');
    });
  });

  describe('Stream Cleanup', () => {
    it('should clean up stream when stopPreview is called', async () => {
      const mockAnswer = {
        type: 'answer' as RTCSdpType,
        sdp: 'mock-answer-sdp',
      };

      mockGo2rtcClient.createPreview.mockResolvedValue(mockAnswer);

      const { result } = renderHook(() => useRtspPreview());

      const config: PreviewConfig = {
        rtspUrl: 'rtsp://192.168.1.100:554/stream1',
      };

      act(() => {
        result.current.startPreview(config);
      });

      await waitFor(() => {
        expect(result.current.state).toBe('connected');
      });

      const connectionBeforeStop = result.current.peerConnection;
      expect(connectionBeforeStop).toBeDefined();

      act(() => {
        result.current.stopPreview();
      });

      await waitFor(() => {
        expect(result.current.state).toBe('idle');
      });

      expect(result.current.peerConnection).toBeUndefined();
      expect(result.current.error).toBeUndefined();
      expect(mockGo2rtcClient.stopPreview).toHaveBeenCalled();
    });

    it('should handle stopPreview when not connected', () => {
      const { result } = renderHook(() => useRtspPreview());

      act(() => {
        result.current.stopPreview();
      });

      expect(result.current.state).toBe('idle');
      expect(mockGo2rtcClient.stopPreview).not.toHaveBeenCalled();
    });

    it('should cleanup on unmount', async () => {
      const mockAnswer = {
        type: 'answer' as RTCSdpType,
        sdp: 'mock-answer-sdp',
      };

      mockGo2rtcClient.createPreview.mockResolvedValue(mockAnswer);

      const { result, unmount } = renderHook(() => useRtspPreview());

      const config: PreviewConfig = {
        rtspUrl: 'rtsp://192.168.1.100:554/stream1',
      };

      act(() => {
        result.current.startPreview(config);
      });

      await waitFor(() => {
        expect(result.current.state).toBe('connected');
      });

      unmount();

      // Cleanup should be called
      expect(mockGo2rtcClient.stopPreview).toHaveBeenCalled();
    });
  });

  describe('Multiple Preview Requests', () => {
    it('should stop previous preview before starting new one', async () => {
      const mockAnswer = {
        type: 'answer' as RTCSdpType,
        sdp: 'mock-answer-sdp',
      };

      mockGo2rtcClient.createPreview.mockResolvedValue(mockAnswer);

      const { result } = renderHook(() => useRtspPreview());

      const config1: PreviewConfig = {
        rtspUrl: 'rtsp://192.168.1.100:554/stream1',
      };

      const config2: PreviewConfig = {
        rtspUrl: 'rtsp://192.168.1.101:554/stream2',
      };

      // Start first preview
      act(() => {
        result.current.startPreview(config1);
      });

      await waitFor(() => {
        expect(result.current.state).toBe('connected');
      });

      expect(mockGo2rtcClient.createPreview).toHaveBeenCalledTimes(1);

      // Start second preview (should stop first one)
      act(() => {
        result.current.startPreview(config2);
      });

      await waitFor(() => {
        expect(result.current.state).toBe('connecting');
      });

      expect(mockGo2rtcClient.stopPreview).toHaveBeenCalled();

      await waitFor(() => {
        expect(result.current.state).toBe('connected');
      });

      expect(mockGo2rtcClient.createPreview).toHaveBeenCalledTimes(2);
    });

    it('should not allow simultaneous preview requests', async () => {
      const mockAnswer = {
        type: 'answer' as RTCSdpType,
        sdp: 'mock-answer-sdp',
      };

      mockGo2rtcClient.createPreview.mockImplementation(
        () =>
          new Promise((resolve) => {
            setTimeout(() => resolve(mockAnswer), 100);
          })
      );

      const { result } = renderHook(() => useRtspPreview());

      const config: PreviewConfig = {
        rtspUrl: 'rtsp://192.168.1.100:554/stream1',
      };

      // Start first preview
      act(() => {
        result.current.startPreview(config);
      });

      await waitFor(() => {
        expect(result.current.state).toBe('connecting');
      });

      // Attempt second preview while first is connecting
      act(() => {
        result.current.startPreview(config);
      });

      // Should still only be one createPreview call initially
      await waitFor(() => {
        expect(result.current.state).toBe('connected');
      });

      // Second call should have cancelled (peerConnection closed) and restarted
      // Note: stopPreview is only called when there's an active stream to stop,
      // which isn't the case when still in 'connecting' state before signaling completes
      expect(mockGo2rtcClient.createPreview).toHaveBeenCalledTimes(2);
    });
  });

  describe('State Transitions', () => {
    it('should clear error when starting new preview', async () => {
      mockGo2rtcClient.createPreview.mockRejectedValueOnce(new Error('Connection failed'));

      const { result } = renderHook(() => useRtspPreview());

      const config: PreviewConfig = {
        rtspUrl: 'rtsp://192.168.1.100:554/stream1',
      };

      // First attempt fails
      act(() => {
        result.current.startPreview(config);
      });

      await waitFor(() => {
        expect(result.current.state).toBe('error');
      });

      expect(result.current.error).toBeDefined();

      // Second attempt should clear error
      const mockAnswer = {
        type: 'answer' as RTCSdpType,
        sdp: 'mock-answer-sdp',
      };
      mockGo2rtcClient.createPreview.mockResolvedValueOnce(mockAnswer);

      act(() => {
        result.current.startPreview(config);
      });

      await waitFor(() => {
        expect(result.current.state).toBe('connecting');
      });

      expect(result.current.error).toBeUndefined();

      await waitFor(() => {
        expect(result.current.state).toBe('connected');
      });
    });

    it('should transition idle -> connecting -> connected', async () => {
      const mockAnswer = {
        type: 'answer' as RTCSdpType,
        sdp: 'mock-answer-sdp',
      };

      // Add a small delay to ensure we can capture the 'connecting' state
      mockGo2rtcClient.createPreview.mockImplementation(
        () =>
          new Promise((resolve) => {
            setTimeout(() => resolve(mockAnswer), 50);
          })
      );

      const { result } = renderHook(() => useRtspPreview());

      const states: string[] = [];

      const config: PreviewConfig = {
        rtspUrl: 'rtsp://192.168.1.100:554/stream1',
      };

      // Track state changes
      expect(result.current.state).toBe('idle');
      states.push(result.current.state);

      act(() => {
        result.current.startPreview(config);
      });

      await waitFor(() => {
        expect(result.current.state).toBe('connecting');
      });
      states.push(result.current.state);

      await waitFor(() => {
        expect(result.current.state).toBe('connected');
      });
      states.push(result.current.state);

      expect(states).toEqual(['idle', 'connecting', 'connected']);
    });

    it('should transition idle -> connecting -> error on failure', async () => {
      // Add a small delay to ensure we can capture the 'connecting' state
      mockGo2rtcClient.createPreview.mockImplementation(
        () =>
          new Promise((_, reject) => {
            setTimeout(() => reject(new Error('Connection failed')), 50);
          })
      );

      const { result } = renderHook(() => useRtspPreview());

      const states: string[] = [];

      const config: PreviewConfig = {
        rtspUrl: 'rtsp://192.168.1.100:554/stream1',
      };

      expect(result.current.state).toBe('idle');
      states.push(result.current.state);

      act(() => {
        result.current.startPreview(config);
      });

      await waitFor(() => {
        expect(result.current.state).toBe('connecting');
      });
      states.push(result.current.state);

      await waitFor(() => {
        expect(result.current.state).toBe('error');
      });
      states.push(result.current.state);

      expect(states).toEqual(['idle', 'connecting', 'error']);
    });

    it('should transition connected -> idle when stopped', async () => {
      const mockAnswer = {
        type: 'answer' as RTCSdpType,
        sdp: 'mock-answer-sdp',
      };

      mockGo2rtcClient.createPreview.mockResolvedValue(mockAnswer);

      const { result } = renderHook(() => useRtspPreview());

      const config: PreviewConfig = {
        rtspUrl: 'rtsp://192.168.1.100:554/stream1',
      };

      act(() => {
        result.current.startPreview(config);
      });

      await waitFor(() => {
        expect(result.current.state).toBe('connected');
      });

      act(() => {
        result.current.stopPreview();
      });

      await waitFor(() => {
        expect(result.current.state).toBe('idle');
      });
    });
  });
});
