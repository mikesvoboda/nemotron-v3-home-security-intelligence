/**
 * RecordingDetailModal - Display full details of a recorded API request
 *
 * Shows headers, request body, response body, and provides a "Copy as cURL" button.
 * Sensitive header values are automatically redacted.
 *
 * Implements NEM-2721: Request Recording and Replay panel
 */

import { clsx } from 'clsx';
import { X, Copy, Check, Loader2, AlertCircle } from 'lucide-react';
import { useState, useCallback, useMemo } from 'react';

import ResponsiveModal from '../common/ResponsiveModal';

import type { RecordingDetailResponse } from '../../services/api';

export interface RecordingDetailModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback when modal should close */
  onClose: () => void;
  /** Recording details to display */
  recording: RecordingDetailResponse | null;
  /** Whether recording is loading */
  isLoading: boolean;
  /** Error loading recording */
  error: Error | null;
}

// Headers that should have their values redacted
const SENSITIVE_HEADERS = new Set([
  'authorization',
  'x-api-key',
  'api-key',
  'cookie',
  'set-cookie',
  'x-auth-token',
  'x-access-token',
  'bearer',
  'password',
  'secret',
]);

/**
 * Check if a header name should have its value redacted
 */
function isSensitiveHeader(headerName: string): boolean {
  const lowerName = headerName.toLowerCase();
  return (
    SENSITIVE_HEADERS.has(lowerName) ||
    lowerName.includes('secret') ||
    lowerName.includes('password') ||
    lowerName.includes('token') ||
    lowerName.includes('auth')
  );
}

/**
 * Format JSON for display with syntax highlighting
 */
function formatJson(data: unknown): string {
  if (data === null || data === undefined) {
    return 'null';
  }
  try {
    return JSON.stringify(data, null, 2);
  } catch {
    // Fallback for non-serializable data
    if (typeof data === 'object') {
      return '[Object]';
    }
    // For primitives, use JSON.stringify to avoid base-to-string issues
    return JSON.stringify(data);
  }
}

/**
 * Get color classes for HTTP method badge
 */
function getMethodBadgeClasses(method: string): string {
  switch (method.toUpperCase()) {
    case 'GET':
      return 'bg-blue-500/10 text-blue-400 border-blue-500/20';
    case 'POST':
      return 'bg-green-500/10 text-green-400 border-green-500/20';
    case 'PUT':
    case 'PATCH':
      return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20';
    case 'DELETE':
      return 'bg-red-500/10 text-red-400 border-red-500/20';
    default:
      return 'bg-gray-500/10 text-gray-400 border-gray-500/20';
  }
}

/**
 * Get color classes for status code badge
 */
function getStatusCodeClasses(statusCode: number): string {
  if (statusCode >= 200 && statusCode < 300) {
    return 'bg-green-500/10 text-green-400 border-green-500/20';
  } else if (statusCode >= 400 && statusCode < 500) {
    return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20';
  } else if (statusCode >= 500) {
    return 'bg-red-500/10 text-red-400 border-red-500/20';
  }
  return 'bg-gray-500/10 text-gray-400 border-gray-500/20';
}

/**
 * Generate a cURL command from the recording
 */
function generateCurlCommand(recording: RecordingDetailResponse): string {
  const parts: string[] = ['curl'];

  // Add method (skip for GET)
  if (recording.method !== 'GET') {
    parts.push(`-X ${recording.method}`);
  }

  // Build URL with query params
  let url = recording.path;
  if (recording.query_params && Object.keys(recording.query_params).length > 0) {
    const params = new URLSearchParams(recording.query_params);
    url += `?${params.toString()}`;
  }

  // Add headers (skip sensitive ones)
  if (recording.headers) {
    for (const [key, value] of Object.entries(recording.headers)) {
      if (!isSensitiveHeader(key) && key.toLowerCase() !== 'host' && key.toLowerCase() !== 'content-length') {
        parts.push(`-H '${key}: ${value}'`);
      }
    }
  }

  // Add request body
  if (recording.body) {
    const bodyJson = JSON.stringify(recording.body);
    parts.push(`-d '${bodyJson}'`);
  }

  // Add URL (placeholder for base URL)
  parts.push(`'http://localhost:8000${url}'`);

  return parts.join(' \\\n  ');
}

/**
 * RecordingDetailModal displays the full details of a recorded API request.
 */
export default function RecordingDetailModal({
  isOpen,
  onClose,
  recording,
  isLoading,
  error,
}: RecordingDetailModalProps) {
  const [copied, setCopied] = useState(false);

  // Generate cURL command
  const curlCommand = useMemo(() => {
    if (!recording) return '';
    return generateCurlCommand(recording);
  }, [recording]);

  // Handle copy to clipboard
  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(curlCommand).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }).catch((err) => {
      console.error('Failed to copy to clipboard:', err);
    });
  }, [curlCommand]);

  return (
    <ResponsiveModal
      isOpen={isOpen}
      onClose={onClose}
      size="xl"
      variant="slideUp"
      mobileHeight="full"
      title="Recording Details"
      aria-labelledby="recording-detail-title"
    >
      <div className="max-h-[80vh] overflow-y-auto p-6">
        {/* Header */}
        <div className="mb-6 flex items-start justify-between">
          <div>
            <h2 id="recording-detail-title" className="text-lg font-semibold text-white">
              Recording Details
            </h2>
            {recording && (
              <p className="mt-1 text-sm text-gray-400">
                ID: <span className="font-mono">{recording.recording_id}</span>
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded p-1 text-gray-400 hover:bg-gray-800 hover:text-white"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Loading state */}
        {isLoading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-[#76B900]" />
            <span className="ml-3 text-gray-400">Loading recording details...</span>
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="rounded-lg border border-red-900/50 bg-red-950/20 p-4">
            <div className="flex items-center gap-3">
              <AlertCircle className="h-5 w-5 text-red-400" />
              <p className="text-red-400">{error.message}</p>
            </div>
          </div>
        )}

        {/* Content */}
        {recording && !isLoading && !error && (
          <div className="space-y-6">
            {/* Request overview */}
            <div className="flex flex-wrap items-center gap-4">
              <span
                className={clsx(
                  'inline-flex items-center rounded-full border px-3 py-1 text-sm font-semibold',
                  getMethodBadgeClasses(recording.method)
                )}
              >
                {recording.method}
              </span>
              <span className="font-mono text-white">{recording.path}</span>
              <span
                className={clsx(
                  'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold',
                  getStatusCodeClasses(recording.status_code)
                )}
              >
                {recording.status_code}
              </span>
              <span className="text-sm text-gray-400">{recording.duration_ms.toFixed(2)} ms</span>
            </div>

            {/* Copy as cURL button */}
            <div>
              <button
                onClick={handleCopy}
                className="flex items-center gap-2 rounded-md border border-gray-700 bg-gray-800 px-4 py-2 text-sm text-white transition-colors hover:border-[#76B900] hover:bg-gray-700"
                aria-label="Copy as cURL"
              >
                {copied ? (
                  <>
                    <Check className="h-4 w-4 text-green-400" />
                    Copied!
                  </>
                ) : (
                  <>
                    <Copy className="h-4 w-4" />
                    Copy as cURL
                  </>
                )}
              </button>
            </div>

            {/* Query parameters */}
            {recording.query_params && Object.keys(recording.query_params).length > 0 && (
              <div>
                <h3 className="mb-2 text-sm font-medium uppercase tracking-wider text-gray-400">
                  Query Parameters
                </h3>
                <div className="overflow-x-auto rounded-lg border border-gray-800 bg-[#1A1A1A]">
                  <table className="w-full">
                    <tbody>
                      {Object.entries(recording.query_params).map(([key, value]) => (
                        <tr key={key} className="border-b border-gray-800 last:border-0">
                          <td className="px-4 py-2 font-mono text-sm text-[#76B900]">{key}</td>
                          <td className="px-4 py-2 font-mono text-sm text-gray-300">{value}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Request headers */}
            {recording.headers && Object.keys(recording.headers).length > 0 && (
              <div>
                <h3 className="mb-2 text-sm font-medium uppercase tracking-wider text-gray-400">
                  Request Headers
                </h3>
                <div className="overflow-x-auto rounded-lg border border-gray-800 bg-[#1A1A1A]">
                  <table className="w-full">
                    <tbody>
                      {Object.entries(recording.headers).map(([key, value]) => (
                        <tr key={key} className="border-b border-gray-800 last:border-0">
                          <td className="px-4 py-2 font-mono text-sm text-[#76B900]">{key}</td>
                          <td className="px-4 py-2 font-mono text-sm text-gray-300">
                            {isSensitiveHeader(key) ? (
                              <span className="text-yellow-500">[REDACTED]</span>
                            ) : (
                              value
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Request body */}
            <div>
              <h3 className="mb-2 text-sm font-medium uppercase tracking-wider text-gray-400">
                Request Body
              </h3>
              <div className="overflow-x-auto rounded-lg border border-gray-800 bg-[#1A1A1A] p-4">
                <pre className="font-mono text-sm text-gray-300">
                  {recording.body ? formatJson(recording.body) : '(no body)'}
                </pre>
              </div>
            </div>

            {/* Response body */}
            <div>
              <h3 className="mb-2 text-sm font-medium uppercase tracking-wider text-gray-400">
                Response Body
              </h3>
              <div className="overflow-x-auto rounded-lg border border-gray-800 bg-[#1A1A1A] p-4">
                <pre className="font-mono text-sm text-gray-300">
                  {recording.response_body ? formatJson(recording.response_body) : '(no body)'}
                </pre>
              </div>
            </div>

            {/* Timestamp */}
            <div className="border-t border-gray-800 pt-4">
              <p className="text-xs text-gray-500">
                Recorded at: {new Date(recording.timestamp).toLocaleString()}
                {recording.retrieved_at && (
                  <> | Retrieved at: {new Date(recording.retrieved_at).toLocaleString()}</>
                )}
              </p>
            </div>
          </div>
        )}
      </div>
    </ResponsiveModal>
  );
}
