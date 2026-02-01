/**
 * RTSPPreviewPlayer Component (NEM-4762 Phase 4: Live Preview)
 *
 * Displays a live WebRTC video preview of an RTSP camera stream using go2rtc.
 * Features:
 * - WebRTC video playback
 * - Connection status display
 * - Session expiry countdown (5 minutes)
 * - Retry button on error
 * - Cleanup on unmount
 * - PTZ controls overlay (NEM-4885)
 */

import { clsx } from 'clsx';
import { AlertCircle, Loader2, Move, RefreshCw, Video, VideoOff, X } from 'lucide-react';
import React, { useCallback, useEffect, useRef, useState } from 'react';

import { useRtspPreview } from '../../hooks/useRtspPreview';
import { PTZControls } from '../ptz';

import type { PreviewConfig } from '../../types/preview';

export interface RTSPPreviewPlayerProps {
  /** Preview configuration with RTSP URL and optional credentials */
  config: PreviewConfig;
  /** Whether to auto-start the preview */
  autoStart?: boolean;
  /** Callback when preview starts successfully */
  onConnected?: () => void;
  /** Callback when preview encounters an error */
  onError?: (error: string) => void;
  /** Callback when preview stops */
  onStopped?: () => void;
  /** Additional CSS classes */
  className?: string;
  /** Session expiry time in seconds (default: 300) */
  expiresIn?: number;
  /** Whether camera supports PTZ control (NEM-4885) */
  hasPtz?: boolean;
  /** Camera ID for PTZ control (required if hasPtz is true) */
  cameraId?: string;
}

/** Default session expiry time (5 minutes) */
const DEFAULT_EXPIRY_SECONDS = 300;

/**
 * Format remaining time as MM:SS
 */
function formatTimeRemaining(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

/**
 * RTSPPreviewPlayer displays a live WebRTC video stream from an RTSP camera.
 *
 * Uses the useRtspPreview hook to manage the WebRTC connection lifecycle
 * and displays appropriate status for idle, connecting, connected, and error states.
 */
const RTSPPreviewPlayer: React.FC<RTSPPreviewPlayerProps> = ({
  config,
  autoStart = false,
  onConnected,
  onError,
  onStopped,
  className,
  expiresIn = DEFAULT_EXPIRY_SECONDS,
  hasPtz = false,
  cameraId,
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const { state, error, peerConnection, startPreview, stopPreview } = useRtspPreview();
  const [timeRemaining, setTimeRemaining] = useState(expiresIn);
  const [hasStarted, setHasStarted] = useState(false);
  const [showPtzControls, setShowPtzControls] = useState(false);

  // Start preview on mount if autoStart is enabled
  useEffect(() => {
    if (autoStart && !hasStarted) {
      startPreview(config);
      setHasStarted(true);
    }
  }, [autoStart, config, hasStarted, startPreview]);

  // Handle state changes
  useEffect(() => {
    if (state === 'connected') {
      onConnected?.();
      setTimeRemaining(expiresIn);
    } else if (state === 'error' && error) {
      onError?.(error);
    } else if (state === 'idle' && hasStarted) {
      onStopped?.();
    }
  }, [state, error, hasStarted, expiresIn, onConnected, onError, onStopped]);

  // Connect video element to peer connection stream
  useEffect(() => {
    if (!videoRef.current || !peerConnection) return;

    const handleTrack = (event: RTCTrackEvent) => {
      if (videoRef.current && event.streams[0]) {
        videoRef.current.srcObject = event.streams[0];
      }
    };

    peerConnection.addEventListener('track', handleTrack);

    return () => {
      peerConnection.removeEventListener('track', handleTrack);
    };
  }, [peerConnection]);

  // Session expiry countdown
  useEffect(() => {
    if (state !== 'connected') return;

    const interval = setInterval(() => {
      setTimeRemaining((prev) => {
        if (prev <= 1) {
          // Session expired - stop preview
          stopPreview();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [state, stopPreview]);

  // Handle manual start
  const handleStart = useCallback(() => {
    startPreview(config);
    setHasStarted(true);
  }, [config, startPreview]);

  // Handle retry after error
  const handleRetry = useCallback(() => {
    startPreview(config);
  }, [config, startPreview]);

  // Handle stop
  const handleStop = useCallback(() => {
    stopPreview();
    setHasStarted(false);
  }, [stopPreview]);

  // Toggle PTZ controls overlay
  const togglePtzControls = useCallback(() => {
    setShowPtzControls((prev) => !prev);
  }, []);

  // Hide PTZ controls when video stops
  useEffect(() => {
    if (state !== 'connected') {
      setShowPtzControls(false);
    }
  }, [state]);

  // Render based on state
  return (
    <div
      className={clsx(
        'relative overflow-hidden rounded-lg bg-black',
        'aspect-video',
        className
      )}
      data-testid="rtsp-preview-player"
    >
      {/* Video Element */}
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className={clsx(
          'h-full w-full object-contain',
          state === 'connected' ? 'opacity-100' : 'opacity-0'
        )}
        data-testid="preview-video"
      />

      {/* Idle State - Not started */}
      {state === 'idle' && !hasStarted && (
        <div
          className="absolute inset-0 flex flex-col items-center justify-center bg-gray-900"
          data-testid="idle-overlay"
        >
          <VideoOff className="h-12 w-12 text-gray-500 mb-4" />
          <p className="text-text-secondary mb-4">Preview not started</p>
          <button
            onClick={handleStart}
            className={clsx(
              'inline-flex items-center gap-2 rounded-lg px-4 py-2',
              'bg-primary text-gray-900 font-medium',
              'transition-all hover:bg-primary-400',
              'focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-gray-900'
            )}
            data-testid="start-preview-button"
          >
            <Video className="h-4 w-4" />
            Start Preview
          </button>
        </div>
      )}

      {/* Connecting State */}
      {state === 'connecting' && (
        <div
          className="absolute inset-0 flex flex-col items-center justify-center bg-gray-900"
          data-testid="connecting-overlay"
        >
          <Loader2 className="h-12 w-12 text-primary animate-spin mb-4" />
          <p className="text-text-secondary">Connecting to camera...</p>
        </div>
      )}

      {/* Error State */}
      {state === 'error' && (
        <div
          className="absolute inset-0 flex flex-col items-center justify-center bg-gray-900"
          data-testid="error-overlay"
        >
          <AlertCircle className="h-12 w-12 text-red-500 mb-4" />
          <p className="text-red-500 font-medium mb-2">Connection Failed</p>
          <p className="text-red-400 text-sm mb-4 max-w-[80%] text-center">{error}</p>
          <button
            onClick={handleRetry}
            className={clsx(
              'inline-flex items-center gap-2 rounded-lg px-4 py-2',
              'bg-red-700 text-white font-medium',
              'transition-all hover:bg-red-600',
              'focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 focus:ring-offset-gray-900'
            )}
            data-testid="retry-button"
          >
            <RefreshCw className="h-4 w-4" />
            Retry
          </button>
        </div>
      )}

      {/* Connected State - Status Bar */}
      {state === 'connected' && (
        <div
          className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/80 to-transparent px-4 py-3"
          data-testid="status-bar"
        >
          <div className="flex items-center justify-between">
            {/* Live indicator */}
            <div className="flex items-center gap-2">
              <span className="relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500" />
              </span>
              <span className="text-sm font-medium text-white">LIVE</span>
            </div>

            {/* Session expiry countdown and controls */}
            <div className="flex items-center gap-4">
              <span
                className={clsx(
                  'text-sm',
                  timeRemaining <= 60 ? 'text-yellow-400' : 'text-text-secondary'
                )}
                data-testid="time-remaining"
              >
                {formatTimeRemaining(timeRemaining)} remaining
              </span>

              {/* PTZ toggle button */}
              {hasPtz && cameraId && (
                <button
                  onClick={togglePtzControls}
                  className={clsx(
                    'flex items-center gap-1.5 rounded-md px-2 py-1',
                    'text-sm font-medium transition-colors',
                    'focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-1 focus:ring-offset-black',
                    showPtzControls
                      ? 'bg-primary text-gray-900'
                      : 'bg-gray-800/80 text-gray-200 hover:bg-gray-700'
                  )}
                  aria-label={showPtzControls ? 'Hide PTZ controls' : 'Show PTZ controls'}
                  aria-pressed={showPtzControls}
                  data-testid="ptz-toggle-button"
                >
                  <Move className="h-4 w-4" />
                  PTZ
                </button>
              )}

              {/* Stop button */}
              <button
                onClick={handleStop}
                className={clsx(
                  'text-sm text-red-400 hover:text-red-300',
                  'focus:outline-none focus:underline'
                )}
                data-testid="stop-preview-button"
              >
                Stop Preview
              </button>
            </div>
          </div>
        </div>
      )}

      {/* PTZ Controls Overlay (NEM-4885) */}
      {state === 'connected' && hasPtz && cameraId && showPtzControls && (
        <div
          className={clsx(
            'absolute right-3 bottom-16',
            'transition-all duration-200 ease-in-out',
            'animate-in fade-in slide-in-from-right-2'
          )}
          data-testid="ptz-overlay"
        >
          <div className="relative">
            {/* Close button */}
            <button
              onClick={togglePtzControls}
              className={clsx(
                'absolute -top-2 -right-2 z-10',
                'flex items-center justify-center',
                'h-6 w-6 rounded-full',
                'bg-gray-700 text-gray-300 hover:bg-gray-600 hover:text-white',
                'transition-colors',
                'focus:outline-none focus:ring-2 focus:ring-primary'
              )}
              aria-label="Close PTZ controls"
              data-testid="ptz-close-button"
            >
              <X className="h-3.5 w-3.5" />
            </button>

            {/* PTZ Controls */}
            <PTZControls
              cameraId={cameraId}
              compact
              ptzSupported
              className="shadow-lg"
            />
          </div>
        </div>
      )}

      {/* Idle State - After being stopped */}
      {state === 'idle' && hasStarted && (
        <div
          className="absolute inset-0 flex flex-col items-center justify-center bg-gray-900"
          data-testid="stopped-overlay"
        >
          <VideoOff className="h-12 w-12 text-gray-500 mb-4" />
          <p className="text-text-secondary mb-4">Preview stopped</p>
          <button
            onClick={handleStart}
            className={clsx(
              'inline-flex items-center gap-2 rounded-lg px-4 py-2',
              'bg-primary text-gray-900 font-medium',
              'transition-all hover:bg-primary-400',
              'focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-gray-900'
            )}
            data-testid="restart-preview-button"
          >
            <RefreshCw className="h-4 w-4" />
            Restart Preview
          </button>
        </div>
      )}
    </div>
  );
};

export default RTSPPreviewPlayer;
