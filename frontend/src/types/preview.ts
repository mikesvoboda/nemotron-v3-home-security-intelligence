/**
 * RTSP Live Preview Types (NEM-4760 Phase 4: Live Preview)
 *
 * Types for WebRTC-based RTSP stream preview functionality
 * using go2rtc for protocol conversion.
 */

/**
 * Preview connection state
 */
export type PreviewState = 'idle' | 'connecting' | 'connected' | 'error';

/**
 * Configuration for starting a preview stream
 */
export interface PreviewConfig {
  rtspUrl: string;
  username?: string;
  password?: string;
}

/**
 * Result of a preview connection attempt
 */
export interface PreviewResult {
  state: PreviewState;
  error?: string;
  peerConnection?: RTCPeerConnection;
}
