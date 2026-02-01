/**
 * ConnectionStatusCard Component (NEM-4748 Phase 2: Connection Testing)
 *
 * Displays RTSP connection test results including:
 * - Success/error state with latency
 * - Capabilities (video, audio, PTZ)
 * - Stream details (resolution, codec, FPS)
 * - Loading spinner for pending tests
 */

import { AlertCircle, Check, Loader2, X } from 'lucide-react';

import type { RTSPTestResult } from '../../types/rtsp';

interface ConnectionStatusCardProps {
  result: RTSPTestResult | null;
}

export default function ConnectionStatusCard({ result }: ConnectionStatusCardProps) {
  if (result === null) {
    return (
      <div className="rounded-lg border border-gray-800 bg-card p-4">
        <div className="flex items-center gap-3">
          <Loader2
            data-testid="loading-spinner"
            className="h-5 w-5 animate-spin text-primary"
          />
          <span className="text-text-secondary">Testing connection...</span>
        </div>
      </div>
    );
  }

  if (!result.success) {
    return (
      <div
        data-testid="error-container"
        className="rounded-lg border border-red-500/20 bg-red-500/10 p-4"
        role="alert"
      >
        <div className="flex items-start gap-3">
          <AlertCircle
            data-testid="error-icon"
            className="h-5 w-5 flex-shrink-0 text-red-500"
          />
          <div>
            <p className="font-medium text-red-500">Connection Failed</p>
            {result.error_message && (
              <p className="mt-1 text-sm text-red-400">{result.error_message}</p>
            )}
          </div>
        </div>
      </div>
    );
  }

  const { capabilities, latency_ms } = result;

  return (
    <div className="rounded-lg border border-gray-800 bg-card p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Check
            data-testid="success-indicator"
            className="h-5 w-5 text-green-500"
          />
          <span className="font-medium text-green-500">Connection Successful</span>
        </div>
        {latency_ms !== null && (
          <span className="text-sm text-text-secondary">{latency_ms} ms</span>
        )}
      </div>

      {capabilities && (
        <div className="space-y-3">
          <div className="flex items-center gap-4">
            <CapabilityIndicator
              name="Video"
              supported={capabilities.video}
              testId="capability-video"
            />
            <CapabilityIndicator
              name="Audio"
              supported={capabilities.audio}
              testId="capability-audio"
            />
            <CapabilityIndicator
              name="PTZ"
              supported={capabilities.ptz}
              testId="capability-ptz"
            />
          </div>

          <div className="flex flex-wrap items-center gap-3 text-sm text-text-secondary">
            {capabilities.resolution && (
              <span className="rounded bg-gray-800 px-2 py-1">
                {capabilities.resolution}
              </span>
            )}
            {capabilities.codec && (
              <span className="rounded bg-gray-800 px-2 py-1">
                {capabilities.codec}
              </span>
            )}
            {capabilities.fps !== null && (
              <span className="rounded bg-gray-800 px-2 py-1">
                {capabilities.fps} fps
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

interface CapabilityIndicatorProps {
  name: string;
  supported: boolean;
  testId: string;
}

function CapabilityIndicator({ name, supported, testId }: CapabilityIndicatorProps) {
  return (
    <div
      className="flex items-center gap-1.5"
      aria-label={`${name} ${supported ? 'supported' : 'not supported'}`}
    >
      <span
        data-testid={testId}
        className={supported ? 'text-green-500' : 'text-gray-500'}
      >
        {supported ? <Check className="h-4 w-4" /> : <X className="h-4 w-4" />}
      </span>
      <span className={supported ? 'text-text-primary' : 'text-text-secondary'}>
        {name}
      </span>
    </div>
  );
}
