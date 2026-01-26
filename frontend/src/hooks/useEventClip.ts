import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import {
  fetchEventClipInfo,
  generateEventClip,
  getEventClipUrl,
  type ClipGenerateRequest,
  type ClipInfoResponse,
} from '../services/api';

export interface UseEventClipOptions {
  /** Whether to automatically fetch clip info on mount. Defaults to true. */
  autoFetch?: boolean;
}

export interface UseEventClipResult {
  /** Whether clip info is being fetched */
  isLoading: boolean;
  /** Current clip info from the server */
  clipInfo: ClipInfoResponse | null;
  /** Whether a clip is currently being generated */
  isGenerating: boolean;
  /** Error message if any operation failed */
  error: string | null;
  /** Full URL to the clip video (null if not available) */
  clipUrl: string | null;
  /** Whether a clip is available for this event */
  isClipAvailable: boolean;
  /** Whether clip generation can be initiated (not currently generating) */
  canGenerateClip: boolean;
  /** Function to generate/regenerate the clip */
  generateClip: (request?: ClipGenerateRequest) => Promise<void>;
  /** Function to refetch clip info */
  refetch: () => Promise<void>;
}

/**
 * Hook for managing event clip state including fetching info and generating clips.
 *
 * @param eventId - The event ID to manage clips for (undefined to disable)
 * @param options - Hook options
 * @returns Clip state and actions
 *
 * @example
 * ```tsx
 * const { isClipAvailable, clipUrl, isGenerating, generateClip } = useEventClip(eventId);
 *
 * return (
 *   <button onClick={() => generateClip()} disabled={isGenerating}>
 *     {isGenerating ? 'Generating...' : isClipAvailable ? 'Regenerate' : 'Generate Clip'}
 *   </button>
 * );
 * ```
 */
export function useEventClip(
  eventId: number | undefined,
  options: UseEventClipOptions = {}
): UseEventClipResult {
  const { autoFetch = true } = options;

  // State
  const [clipInfo, setClipInfo] = useState<ClipInfoResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(eventId !== undefined && autoFetch);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Track if component is mounted to prevent state updates after unmount
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // Fetch clip info
  const fetchClipInfo = useCallback(async () => {
    if (eventId === undefined) return;
    if (!isMountedRef.current) return;

    setIsLoading(true);
    setError(null);

    try {
      const info = await fetchEventClipInfo(eventId);
      if (isMountedRef.current) {
        setClipInfo(info);
      }
    } catch (err) {
      if (isMountedRef.current) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to load clip info';
        setError(errorMessage);
        console.error('Failed to fetch clip info:', err);
      }
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [eventId]);

  // Auto-fetch on mount when autoFetch is true
  useEffect(() => {
    if (autoFetch && eventId !== undefined) {
      void fetchClipInfo();
    }
  }, [autoFetch, eventId, fetchClipInfo]);

  // Generate clip
  const handleGenerateClip = useCallback(
    async (request?: ClipGenerateRequest) => {
      if (eventId === undefined) return;
      if (!isMountedRef.current) return;

      setIsGenerating(true);
      setError(null);

      try {
        const response = await generateEventClip(eventId, request);

        if (!isMountedRef.current) return;

        if (response.status === 'completed' && response.clip_url) {
          // Update clip info with generated clip
          setClipInfo({
            event_id: eventId,
            clip_available: true,
            clip_url: response.clip_url,
            duration_seconds: null,
            generated_at: response.generated_at,
            file_size_bytes: null,
          });
        } else if (response.status === 'failed') {
          setError(response.message || 'Failed to generate clip');
          // Update clip info to reflect unavailable state
          setClipInfo((prev) => prev ? { ...prev, clip_available: false } : {
            event_id: eventId,
            clip_available: false,
            clip_url: null,
            duration_seconds: null,
            generated_at: null,
            file_size_bytes: null,
          });
        }
      } catch (err) {
        if (isMountedRef.current) {
          const errorMessage = err instanceof Error ? err.message : 'Failed to generate clip';
          setError(errorMessage);
          console.error('Failed to generate clip:', err);
        }
      } finally {
        if (isMountedRef.current) {
          setIsGenerating(false);
        }
      }
    },
    [eventId]
  );

  // Computed values
  const clipUrl = useMemo(() => {
    if (clipInfo?.clip_available && clipInfo.clip_url) {
      return getEventClipUrl(clipInfo.clip_url);
    }
    return null;
  }, [clipInfo]);

  const isClipAvailable = clipInfo?.clip_available ?? false;
  const canGenerateClip = !isGenerating && !isLoading;

  return {
    isLoading,
    clipInfo,
    isGenerating,
    error,
    clipUrl,
    isClipAvailable,
    canGenerateClip,
    generateClip: handleGenerateClip,
    refetch: fetchClipInfo,
  };
}
