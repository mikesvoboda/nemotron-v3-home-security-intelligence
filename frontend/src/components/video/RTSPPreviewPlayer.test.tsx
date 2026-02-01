/**
 * RTSPPreviewPlayer Component Tests (NEM-4762 Phase 4: Live Preview)
 *
 * Tests the WebRTC-based RTSP preview player component including:
 * - State rendering (idle, connecting, connected, error)
 * - User interactions (start, stop, retry)
 * - Session expiry countdown
 * - Callback invocations
 * - PTZ controls overlay (NEM-4885)
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

// Mock PTZControls component
vi.mock('../ptz', () => ({
  PTZControls: ({ cameraId, compact }: { cameraId: string; compact: boolean }) => (
    <div data-testid="ptz-controls-mock" data-camera-id={cameraId} data-compact={compact}>
      PTZ Controls Mock
    </div>
  ),
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

  describe('PTZ Controls Overlay (NEM-4885)', () => {
    beforeEach(() => {
      mockUseRtspPreview.mockReturnValue({
        state: 'connected',
        error: undefined,
        peerConnection: new RTCPeerConnection(),
        startPreview: mockStartPreview,
        stopPreview: mockStopPreview,
      });
    });

    it('does not show PTZ toggle button when hasPtz is false', () => {
      render(<RTSPPreviewPlayer config={defaultConfig} />);

      expect(screen.queryByTestId('ptz-toggle-button')).not.toBeInTheDocument();
    });

    it('does not show PTZ toggle button when cameraId is missing', () => {
      render(<RTSPPreviewPlayer config={defaultConfig} hasPtz />);

      expect(screen.queryByTestId('ptz-toggle-button')).not.toBeInTheDocument();
    });

    it('shows PTZ toggle button when hasPtz and cameraId are provided', () => {
      render(<RTSPPreviewPlayer config={defaultConfig} hasPtz cameraId="camera-1" />);

      expect(screen.getByTestId('ptz-toggle-button')).toBeInTheDocument();
      expect(screen.getByText('PTZ')).toBeInTheDocument();
    });

    it('does not show PTZ overlay initially', () => {
      render(<RTSPPreviewPlayer config={defaultConfig} hasPtz cameraId="camera-1" />);

      expect(screen.queryByTestId('ptz-overlay')).not.toBeInTheDocument();
    });

    it('shows PTZ overlay when toggle button is clicked', () => {
      render(<RTSPPreviewPlayer config={defaultConfig} hasPtz cameraId="camera-1" />);

      const toggleButton = screen.getByTestId('ptz-toggle-button');
      fireEvent.click(toggleButton);

      expect(screen.getByTestId('ptz-overlay')).toBeInTheDocument();
      expect(screen.getByTestId('ptz-controls-mock')).toBeInTheDocument();
    });

    it('hides PTZ overlay when toggle button is clicked again', () => {
      render(<RTSPPreviewPlayer config={defaultConfig} hasPtz cameraId="camera-1" />);

      const toggleButton = screen.getByTestId('ptz-toggle-button');

      // Open
      fireEvent.click(toggleButton);
      expect(screen.getByTestId('ptz-overlay')).toBeInTheDocument();

      // Close
      fireEvent.click(toggleButton);
      expect(screen.queryByTestId('ptz-overlay')).not.toBeInTheDocument();
    });

    it('hides PTZ overlay when close button is clicked', () => {
      render(<RTSPPreviewPlayer config={defaultConfig} hasPtz cameraId="camera-1" />);

      // Open PTZ overlay
      fireEvent.click(screen.getByTestId('ptz-toggle-button'));
      expect(screen.getByTestId('ptz-overlay')).toBeInTheDocument();

      // Click close button
      fireEvent.click(screen.getByTestId('ptz-close-button'));
      expect(screen.queryByTestId('ptz-overlay')).not.toBeInTheDocument();
    });

    it('passes correct props to PTZControls component', () => {
      render(<RTSPPreviewPlayer config={defaultConfig} hasPtz cameraId="camera-1" />);

      fireEvent.click(screen.getByTestId('ptz-toggle-button'));

      const ptzControls = screen.getByTestId('ptz-controls-mock');
      expect(ptzControls).toHaveAttribute('data-camera-id', 'camera-1');
      expect(ptzControls).toHaveAttribute('data-compact', 'true');
    });

    it('toggle button has correct aria attributes', () => {
      render(<RTSPPreviewPlayer config={defaultConfig} hasPtz cameraId="camera-1" />);

      const toggleButton = screen.getByTestId('ptz-toggle-button');

      // Initially not pressed
      expect(toggleButton).toHaveAttribute('aria-pressed', 'false');
      expect(toggleButton).toHaveAttribute('aria-label', 'Show PTZ controls');

      // After click
      fireEvent.click(toggleButton);
      expect(toggleButton).toHaveAttribute('aria-pressed', 'true');
      expect(toggleButton).toHaveAttribute('aria-label', 'Hide PTZ controls');
    });

    it('hides PTZ controls when video stops', async () => {
      const { rerender } = render(
        <RTSPPreviewPlayer config={defaultConfig} hasPtz cameraId="camera-1" />
      );

      // Open PTZ controls
      fireEvent.click(screen.getByTestId('ptz-toggle-button'));
      expect(screen.getByTestId('ptz-overlay')).toBeInTheDocument();

      // Simulate video stopping
      mockUseRtspPreview.mockReturnValue({
        state: 'idle',
        error: undefined,
        peerConnection: undefined,
        startPreview: mockStartPreview,
        stopPreview: mockStopPreview,
      });

      rerender(<RTSPPreviewPlayer config={defaultConfig} hasPtz cameraId="camera-1" autoStart />);

      await waitFor(() => {
        expect(screen.queryByTestId('ptz-overlay')).not.toBeInTheDocument();
      });
    });

    it('does not show PTZ controls in non-connected states', () => {
      // Test idle state
      mockUseRtspPreview.mockReturnValue({
        state: 'idle',
        error: undefined,
        peerConnection: undefined,
        startPreview: mockStartPreview,
        stopPreview: mockStopPreview,
      });

      const { rerender } = render(
        <RTSPPreviewPlayer config={defaultConfig} hasPtz cameraId="camera-1" />
      );
      expect(screen.queryByTestId('ptz-toggle-button')).not.toBeInTheDocument();

      // Test connecting state
      mockUseRtspPreview.mockReturnValue({
        state: 'connecting',
        error: undefined,
        peerConnection: undefined,
        startPreview: mockStartPreview,
        stopPreview: mockStopPreview,
      });

      rerender(<RTSPPreviewPlayer config={defaultConfig} hasPtz cameraId="camera-1" />);
      expect(screen.queryByTestId('ptz-toggle-button')).not.toBeInTheDocument();

      // Test error state
      mockUseRtspPreview.mockReturnValue({
        state: 'error',
        error: 'Connection failed',
        peerConnection: undefined,
        startPreview: mockStartPreview,
        stopPreview: mockStopPreview,
      });

      rerender(<RTSPPreviewPlayer config={defaultConfig} hasPtz cameraId="camera-1" />);
      expect(screen.queryByTestId('ptz-toggle-button')).not.toBeInTheDocument();
    });
  });
});
