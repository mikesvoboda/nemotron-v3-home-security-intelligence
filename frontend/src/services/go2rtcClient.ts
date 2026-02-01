/**
 * go2rtc WebRTC Client (NEM-4760 Phase 4: Live Preview)
 *
 * Client for connecting to go2rtc server for WebRTC-based RTSP stream preview.
 * Handles WebRTC signaling (SDP offer/answer exchange) with go2rtc.
 */

import type { PreviewConfig } from '../types/preview';

/**
 * Response from preview start endpoint
 */
interface PreviewStartResponse {
  webrtc_url: string;
  stream_id: string;
  expires_in: number;
  sdp?: string;
}

// Track current stream ID for cleanup
let currentStreamId: string | null = null;

/**
 * go2rtc client for WebRTC preview functionality
 */
export const go2rtcClient = {
  /**
   * Create a preview stream and perform WebRTC signaling
   *
   * @param config Preview configuration with RTSP URL and optional credentials
   * @returns SDP answer from go2rtc for setting as remote description
   */
  createPreview: async (config: PreviewConfig): Promise<RTCSessionDescriptionInit> => {
    // Create a temporary peer connection to generate the offer
    const pc = new RTCPeerConnection();
    pc.addTransceiver('video', { direction: 'recvonly' });
    pc.addTransceiver('audio', { direction: 'recvonly' });

    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    pc.close();

    // Send offer to backend to start preview and get answer
    const response = await fetch('/api/cameras/preview/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        rtsp_url: config.rtspUrl,
        username: config.username,
        password: config.password,
        offer: offer.sdp,
      }),
    });

    if (!response.ok) {
      const errorData = (await response.json().catch(() => ({}))) as { detail?: string };
      const message = errorData.detail ?? `HTTP error ${response.status}`;
      throw new Error(message);
    }

    const data = (await response.json()) as PreviewStartResponse;
    currentStreamId = data.stream_id;

    // Return the SDP answer from go2rtc
    return {
      type: 'answer' as RTCSdpType,
      sdp: data.sdp,
    };
  },

  /**
   * Stop the current preview stream
   * This is a best-effort cleanup operation
   */
  stopPreview: (): void => {
    if (!currentStreamId) {
      return;
    }

    const streamId = currentStreamId;
    currentStreamId = null;

    // Fire and forget - we don't wait for the response
    void fetch(`/api/cameras/preview/${streamId}/stop`, {
      method: 'DELETE',
    }).catch(() => {
      // Silently ignore errors - this is best-effort cleanup
    });
  },
};
