/**
 * React hook for SSE-based streaming analysis (NEM-1665, NEM-2488).
 *
 * Provides a React-friendly interface for consuming Server-Sent Events
 * from the LLM analysis streaming endpoint.
 */

import { useState, useCallback, useRef, useEffect } from 'react';

import {
  createAnalysisStream,
  type AnalysisStreamParams,
  type AnalysisStreamEvent,
} from '../services/api';
import { logger } from '../services/logger';

/**
 * Connection state for the SSE stream.
 */
export type AnalysisStreamStatus = 'idle' | 'connecting' | 'connected' | 'complete' | 'error';

/**
 * Return type for useAnalysisStream hook.
 */
export interface UseAnalysisStreamReturn {
  /** Current connection status */
  status: AnalysisStreamStatus;
  /** Accumulated response text from progress events */
  accumulatedText: string;
  /** Final result from complete event */
  result: AnalysisStreamResult | null;
  /** Error information if status is 'error' */
  error: AnalysisStreamError | null;
  /** Start streaming analysis for a batch */
  startStream: (params: AnalysisStreamParams) => void;
  /** Stop the current stream */
  stopStream: () => void;
  /** Whether a stream is currently active */
  isStreaming: boolean;
}

/**
 * Result data from a completed analysis.
 */
export interface AnalysisStreamResult {
  /** Event ID created from analysis */
  eventId: number;
  /** Final risk score (0-100) */
  riskScore: number;
  /** Risk level derived from score */
  riskLevel: string;
  /** Summary text */
  summary: string;
}

/**
 * Error data from a failed analysis.
 */
export interface AnalysisStreamError {
  /** Error code from the backend */
  code: string;
  /** Human-readable error message */
  message: string;
  /** Whether the error is recoverable (can retry) */
  recoverable: boolean;
}

/**
 * React hook for consuming streaming LLM analysis via Server-Sent Events.
 *
 * Provides progressive updates during LLM inference, allowing the UI to
 * display partial results and typing indicators.
 *
 * @param options - Optional configuration
 * @param options.onProgress - Callback for progress events with accumulated text
 * @param options.onComplete - Callback when analysis completes successfully
 * @param options.onError - Callback when analysis fails
 *
 * @example
 * ```tsx
 * function AnalysisComponent({ batchId, cameraId }) {
 *   const {
 *     status,
 *     accumulatedText,
 *     result,
 *     error,
 *     startStream,
 *     stopStream,
 *     isStreaming,
 *   } = useAnalysisStream({
 *     onComplete: (result) => {
 *       console.log('Analysis complete:', result);
 *     },
 *   });
 *
 *   useEffect(() => {
 *     startStream({ batchId, cameraId });
 *     return () => stopStream();
 *   }, [batchId, cameraId, startStream, stopStream]);
 *
 *   if (isStreaming) {
 *     return <div>Analyzing... {accumulatedText}</div>;
 *   }
 *
 *   if (error) {
 *     return <div>Error: {error.message}</div>;
 *   }
 *
 *   if (result) {
 *     return <div>Risk: {result.riskLevel} ({result.riskScore})</div>;
 *   }
 *
 *   return null;
 * }
 * ```
 */
export function useAnalysisStream(
  options: {
    onProgress?: (text: string) => void;
    onComplete?: (result: AnalysisStreamResult) => void;
    onError?: (error: AnalysisStreamError) => void;
  } = {}
): UseAnalysisStreamReturn {
  const [status, setStatus] = useState<AnalysisStreamStatus>('idle');
  const [accumulatedText, setAccumulatedText] = useState<string>('');
  const [result, setResult] = useState<AnalysisStreamResult | null>(null);
  const [error, setError] = useState<AnalysisStreamError | null>(null);

  // Refs for callbacks to avoid stale closures
  const onProgressRef = useRef(options.onProgress);
  const onCompleteRef = useRef(options.onComplete);
  const onErrorRef = useRef(options.onError);

  // Update refs when callbacks change
  useEffect(() => {
    onProgressRef.current = options.onProgress;
    onCompleteRef.current = options.onComplete;
    onErrorRef.current = options.onError;
  }, [options.onProgress, options.onComplete, options.onError]);

  // Ref to hold the EventSource instance
  const eventSourceRef = useRef<EventSource | null>(null);

  // Track mounted state to prevent state updates after unmount
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;

    return () => {
      isMountedRef.current = false;
      // Close any open connection on unmount
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, []);

  const stopStream = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
      logger.debug('Analysis stream closed', { component: 'useAnalysisStream' });
    }

    if (isMountedRef.current && status !== 'complete' && status !== 'error') {
      setStatus('idle');
    }
  }, [status]);

  const startStream = useCallback(
    (params: AnalysisStreamParams) => {
      // Close any existing connection
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }

      // Reset state
      if (isMountedRef.current) {
        setStatus('connecting');
        setAccumulatedText('');
        setResult(null);
        setError(null);
      }

      logger.debug('Starting analysis stream', {
        component: 'useAnalysisStream',
        batchId: params.batchId,
        cameraId: params.cameraId,
      });

      const eventSource = createAnalysisStream(params);
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
        if (isMountedRef.current) {
          setStatus('connected');
          logger.debug('Analysis stream connected', { component: 'useAnalysisStream' });
        }
      };

      eventSource.onmessage = (event: MessageEvent) => {
        if (!isMountedRef.current) {
          return;
        }

        try {
          const data = JSON.parse(event.data as string) as AnalysisStreamEvent;

          switch (data.event_type) {
            case 'progress':
              if (data.accumulated_text !== undefined) {
                setAccumulatedText(data.accumulated_text);
                onProgressRef.current?.(data.accumulated_text);
              }
              break;

            case 'complete':
              if (
                data.event_id !== undefined &&
                data.risk_score !== undefined &&
                data.risk_level !== undefined &&
                data.summary !== undefined
              ) {
                const completedResult: AnalysisStreamResult = {
                  eventId: data.event_id,
                  riskScore: data.risk_score,
                  riskLevel: data.risk_level,
                  summary: data.summary,
                };
                setResult(completedResult);
                setStatus('complete');
                onCompleteRef.current?.(completedResult);
                logger.info('Analysis stream completed', {
                  component: 'useAnalysisStream',
                  eventId: data.event_id,
                  riskScore: data.risk_score,
                });
              }
              // Close connection after complete
              eventSource.close();
              eventSourceRef.current = null;
              break;

            case 'error': {
              const streamError: AnalysisStreamError = {
                code: data.error_code ?? 'UNKNOWN_ERROR',
                message: data.error_message ?? 'An unknown error occurred',
                recoverable: data.recoverable ?? false,
              };
              setError(streamError);
              setStatus('error');
              onErrorRef.current?.(streamError);
              logger.error('Analysis stream error', {
                component: 'useAnalysisStream',
                errorCode: streamError.code,
                errorMessage: streamError.message,
                recoverable: streamError.recoverable,
              });
              // Close connection after error
              eventSource.close();
              eventSourceRef.current = null;
              break;
            }

            default:
              // Ignore unknown event types
              logger.warn('Unknown analysis stream event type', {
                component: 'useAnalysisStream',
                eventType: (data as { event_type: string }).event_type,
              });
          }
        } catch (parseError) {
          logger.error('Failed to parse analysis stream event', {
            component: 'useAnalysisStream',
            error: parseError instanceof Error ? parseError.message : 'Unknown parse error',
            rawData: event.data,
          });
        }
      };

      eventSource.onerror = () => {
        if (!isMountedRef.current) {
          return;
        }

        // Only set error state if we're not already complete
        if (status !== 'complete') {
          const connectionError: AnalysisStreamError = {
            code: 'CONNECTION_ERROR',
            message: 'Lost connection to analysis stream',
            recoverable: true,
          };
          setError(connectionError);
          setStatus('error');
          onErrorRef.current?.(connectionError);
          logger.error('Analysis stream connection error', {
            component: 'useAnalysisStream',
          });
        }

        // Close on error
        eventSource.close();
        eventSourceRef.current = null;
      };
    },
    [status]
  );

  const isStreaming = status === 'connecting' || status === 'connected';

  return {
    status,
    accumulatedText,
    result,
    error,
    startStream,
    stopStream,
    isStreaming,
  };
}

export default useAnalysisStream;
