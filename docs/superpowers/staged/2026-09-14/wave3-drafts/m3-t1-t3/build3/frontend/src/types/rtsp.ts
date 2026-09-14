/**
 * RTSP Connection Testing Types (NEM-4748 Phase 2)
 *
 * These types match the backend RTSPTestService structures in:
 * backend/services/rtsp_test_service.py
 */

/**
 * Detected capabilities of an RTSP stream
 */
export interface RTSPCapabilities {
  video: boolean;
  audio: boolean;
  ptz: boolean;
  resolution: string | null;
  codec: string;
  fps: number | null;
}

/**
 * Result of an RTSP connection test
 */
export interface RTSPTestResult {
  success: boolean;
  latency_ms: number | null;
  capabilities: RTSPCapabilities | null;
  error_message: string | null;
}

/**
 * Request payload for testing an RTSP connection
 */
export interface RTSPTestRequest {
  rtsp_url: string;
  username?: string;
  password?: string;
}
