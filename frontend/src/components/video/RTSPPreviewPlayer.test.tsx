/**
 * RTSPPreviewPlayer Component Tests (NEM-4762 Phase 4: Live Preview)
 *
 * Tests the WebRTC-based RTSP preview player component including:
 * - State rendering (idle, connecting, connected, error)
 * - User interactions (start, stop, retry)
 * - Session expiry countdown
 * - Callback invocations
 */

import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import RTSPPreviewPlayer from './RTSPPreviewPlayer';
import { useRtspPreview } from '../../hooks/useRtspPreview';

import type { PreviewConfig } from '../../types/preview';

// Mock the useRtspPreview hook
const mockStartPreview = vi.fn();
const mockStopPreview = vi.fn();

vi.mock('../../hooks/useRtspPreview', () => ({
  useRtspPreview: vi.fn(() => ({
    state: 'idle',
    error: undefined,
    peerConnection: undefined,
    startPreview: mockStartPreview,
    stopPreview: mockStopPreview,
  })),
}));

const mockUseRtspPreview = vi.mocked(useRtspPreview);

// Mock RTCPeerConnection for jsdom environment
class MockRTCPeerConnection {
  localDescription: RTCSessionDescription | null = null;
  remoteDescription: RTCSessionDescription | null = null;
  connectionState: RTCPeerConnectionState = 'new';
  iceConnectionState: RTCIceConnectionState = 'new';
  signalingState: RTCSignalingState = 'stable';

  private listeners: Map<string, Set<EventListener>> = new Map();

  addEventListener(type: string, listener: EventListener): void {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, new Set());
    }
    this.listeners.get(type)!.add(listener);
  }

  removeEventListener(type: string, listener: EventListener): void {
    this.listeners.get(type)?.delete(listener);
  }

  close(): void {
    this.connectionState = 'closed';
  }

  createOffer(): Promise<RTCSessionDescriptionInit> {
    return Promise.resolve({ type: 'offer', sdp: 'mock-offer-sdp' });
  }

  createAnswer(): Promise<RTCSessionDescriptionInit> {
    return Promise.resolve({ type: 'answer', sdp: 'mock-answer-sdp' });
  }

  setLocalDescription(desc: RTCSessionDescriptionInit): Promise<void> {
    this.localDescription = desc as RTCSessionDescription;
    return Promise.resolve();
  }

  setRemoteDescription(desc: RTCSessionDescriptionInit): Promise<void> {
    this.remoteDescription = desc as RTCSessionDescription;
    return Promise.resolve();
  }

  addTransceiver(): RTCRtpTransceiver {
    return {} as RTCRtpTransceiver;
  }
}

// Set up global mock before tests run
global.RTCPeerConnection = MockRTCPeerConnection as unknown as typeof RTCPeerConnection;

const defaultConfig: PreviewConfig = {
  rtspUrl: 'rtsp://192.168.1.100:554/stream1',
  username: 'admin',
  password: 'password123', // pragma: allowlist secret
};

describe('RTSPPreviewPlayer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseRtspPreview.mockReturnValue({
      state: 'idle',
      error: undefined,
      peerConnection: undefined,
      startPreview: mockStartPreview,
      stopPreview: mockStopPreview,
    });
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  describe('Idle State', () => {
    it('renders idle state with start button', () => {
      render(<RTSPPreviewPlayer config={defaultConfig} />);

      expect(screen.getByTestId('rtsp-preview-player')).toBeInTheDocument();
      expect(screen.getByTestId('idle-overlay')).toBeInTheDocument();
      expect(screen.getByTestId('start-preview-button')).toBeInTheDocument();
      expect(screen.getByText('Preview not started')).toBeInTheDocument();
    });

    it('calls startPreview when start button is clicked', () => {
      render(<RTSPPreviewPlayer config={defaultConfig} />);

      const startButton = screen.getByTestId('start-preview-button');
      fireEvent.click(startButton);

      expect(mockStartPreview).toHaveBeenCalledWith(defaultConfig);
    });

    it('auto-starts preview when autoStart prop is true', () => {
      render(<RTSPPreviewPlayer config={defaultConfig} autoStart />);

      expect(mockStartPreview).toHaveBeenCalledWith(defaultConfig);
    });
  });

  describe('Connecting State', () => {
    it('renders connecting state with loading spinner', () => {
      mockUseRtspPreview.mockReturnValue({
        state: 'connecting',
        error: undefined,
        peerConnection: undefined,
        startPreview: mockStartPreview,
        stopPreview: mockStopPreview,
      });

      render(<RTSPPreviewPlayer config={defaultConfig} />);

      expect(screen.getByTestId('connecting-overlay')).toBeInTheDocument();
      expect(screen.getByText('Connecting to camera...')).toBeInTheDocument();
    });
  });

  describe('Connected State', () => {
    it('renders connected state with video and status bar', () => {
      mockUseRtspPreview.mockReturnValue({
        state: 'connected',
        error: undefined,
        peerConnection: new RTCPeerConnection(),
        startPreview: mockStartPreview,
        stopPreview: mockStopPreview,
      });

      render(<RTSPPreviewPlayer config={defaultConfig} />);

      expect(screen.getByTestId('preview-video')).toBeInTheDocument();
      expect(screen.getByTestId('status-bar')).toBeInTheDocument();
      expect(screen.getByText('LIVE')).toBeInTheDocument();
      expect(screen.getByTestId('time-remaining')).toBeInTheDocument();
      expect(screen.getByTestId('stop-preview-button')).toBeInTheDocument();
    });

    it('displays session expiry countdown', () => {
      mockUseRtspPreview.mockReturnValue({
        state: 'connected',
        error: undefined,
        peerConnection: new RTCPeerConnection(),
        startPreview: mockStartPreview,
        stopPreview: mockStopPreview,
      });

      render(<RTSPPreviewPlayer config={defaultConfig} expiresIn={300} />);

      expect(screen.getByText('5:00 remaining')).toBeInTheDocument();
    });

    it('calls stopPreview when stop button is clicked', () => {
      mockUseRtspPreview.mockReturnValue({
        state: 'connected',
        error: undefined,
        peerConnection: new RTCPeerConnection(),
        startPreview: mockStartPreview,
        stopPreview: mockStopPreview,
      });

      render(<RTSPPreviewPlayer config={defaultConfig} />);

      const stopButton = screen.getByTestId('stop-preview-button');
      fireEvent.click(stopButton);

      expect(mockStopPreview).toHaveBeenCalled();
    });

    it('invokes onConnected callback when connected', () => {
      const onConnected = vi.fn();

      mockUseRtspPreview.mockReturnValue({
        state: 'connected',
        error: undefined,
        peerConnection: new RTCPeerConnection(),
        startPreview: mockStartPreview,
        stopPreview: mockStopPreview,
      });

      render(<RTSPPreviewPlayer config={defaultConfig} onConnected={onConnected} />);

      expect(onConnected).toHaveBeenCalled();
    });

    it('counts down session expiry time', () => {
      vi.useFakeTimers();

      mockUseRtspPreview.mockReturnValue({
        state: 'connected',
        error: undefined,
        peerConnection: new RTCPeerConnection(),
        startPreview: mockStartPreview,
        stopPreview: mockStopPreview,
      });

      render(<RTSPPreviewPlayer config={defaultConfig} expiresIn={5} />);

      expect(screen.getByText('0:05 remaining')).toBeInTheDocument();

      // Advance timers within act to trigger React state update
      act(() => {
        vi.advanceTimersByTime(1000);
      });

      // After advancing timers, the countdown should update
      expect(screen.getByText('0:04 remaining')).toBeInTheDocument();

      vi.useRealTimers();
    });

    it('stops preview when session expires', () => {
      vi.useFakeTimers();

      mockUseRtspPreview.mockReturnValue({
        state: 'connected',
        error: undefined,
        peerConnection: new RTCPeerConnection(),
        startPreview: mockStartPreview,
        stopPreview: mockStopPreview,
      });

      render(<RTSPPreviewPlayer config={defaultConfig} expiresIn={2} />);

      // Advance timers within act to trigger React state update and expiry logic
      act(() => {
        vi.advanceTimersByTime(2000);
      });

      // After session expires, stopPreview should be called
      expect(mockStopPreview).toHaveBeenCalled();

      vi.useRealTimers();
    });
  });

  describe('Error State', () => {
    it('renders error state with retry button', () => {
      const errorMessage = 'Connection failed';

      mockUseRtspPreview.mockReturnValue({
        state: 'error',
        error: errorMessage,
        peerConnection: undefined,
        startPreview: mockStartPreview,
        stopPreview: mockStopPreview,
      });

      render(<RTSPPreviewPlayer config={defaultConfig} />);

      expect(screen.getByTestId('error-overlay')).toBeInTheDocument();
      expect(screen.getByText('Connection Failed')).toBeInTheDocument();
      expect(screen.getByText(errorMessage)).toBeInTheDocument();
      expect(screen.getByTestId('retry-button')).toBeInTheDocument();
    });

    it('calls startPreview when retry button is clicked', () => {
      mockUseRtspPreview.mockReturnValue({
        state: 'error',
        error: 'Connection failed',
        peerConnection: undefined,
        startPreview: mockStartPreview,
        stopPreview: mockStopPreview,
      });

      render(<RTSPPreviewPlayer config={defaultConfig} />);

      const retryButton = screen.getByTestId('retry-button');
      fireEvent.click(retryButton);

      expect(mockStartPreview).toHaveBeenCalledWith(defaultConfig);
    });

    it('invokes onError callback when error occurs', () => {
      const onError = vi.fn();
      const errorMessage = 'Connection failed';

      mockUseRtspPreview.mockReturnValue({
        state: 'error',
        error: errorMessage,
        peerConnection: undefined,
        startPreview: mockStartPreview,
        stopPreview: mockStopPreview,
      });

      render(<RTSPPreviewPlayer config={defaultConfig} onError={onError} />);

      expect(onError).toHaveBeenCalledWith(errorMessage);
    });
  });

  describe('Stopped State', () => {
    it('renders stopped state after being stopped', async () => {
      // Start with connected state, then stop
      mockUseRtspPreview.mockReturnValue({
        state: 'connected',
        error: undefined,
        peerConnection: new RTCPeerConnection(),
        startPreview: mockStartPreview,
        stopPreview: mockStopPreview,
      });

      const { rerender } = render(<RTSPPreviewPlayer config={defaultConfig} autoStart />);

      // Now simulate the stopped state
      mockUseRtspPreview.mockReturnValue({
        state: 'idle',
        error: undefined,
        peerConnection: undefined,
        startPreview: mockStartPreview,
        stopPreview: mockStopPreview,
      });

      rerender(<RTSPPreviewPlayer config={defaultConfig} autoStart />);

      // After being stopped, it shows the stopped overlay (hasStarted is true)
      await waitFor(() => {
        expect(screen.getByTestId('stopped-overlay')).toBeInTheDocument();
      });

      expect(screen.getByText('Preview stopped')).toBeInTheDocument();
      expect(screen.getByTestId('restart-preview-button')).toBeInTheDocument();
    });

    it('invokes onStopped callback when preview stops', async () => {
      const onStopped = vi.fn();

      // Start with connected state
      mockUseRtspPreview.mockReturnValue({
        state: 'connected',
        error: undefined,
        peerConnection: new RTCPeerConnection(),
        startPreview: mockStartPreview,
        stopPreview: mockStopPreview,
      });

      const { rerender } = render(
        <RTSPPreviewPlayer config={defaultConfig} autoStart onStopped={onStopped} />
      );

      // Transition to idle state (stopped)
      mockUseRtspPreview.mockReturnValue({
        state: 'idle',
        error: undefined,
        peerConnection: undefined,
        startPreview: mockStartPreview,
        stopPreview: mockStopPreview,
      });

      rerender(
        <RTSPPreviewPlayer config={defaultConfig} autoStart onStopped={onStopped} />
      );

      await waitFor(() => {
        expect(onStopped).toHaveBeenCalled();
      });
    });
  });

  describe('CSS and Styling', () => {
    it('applies custom className', () => {
      render(<RTSPPreviewPlayer config={defaultConfig} className="custom-class" />);

      const player = screen.getByTestId('rtsp-preview-player');
      expect(player).toHaveClass('custom-class');
    });

    it('has aspect-video class for 16:9 ratio', () => {
      render(<RTSPPreviewPlayer config={defaultConfig} />);

      const player = screen.getByTestId('rtsp-preview-player');
      expect(player).toHaveClass('aspect-video');
    });
  });
});
