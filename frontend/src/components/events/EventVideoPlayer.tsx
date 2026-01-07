import { AlertCircle, Download, Loader2, RefreshCw } from 'lucide-react';
import { useEffect, useState } from 'react';

import {
  fetchEventClipInfo,
  generateEventClip,
  getEventClipUrl,
  type ClipInfoResponse,
  type ClipGenerateResponse,
} from '../../services/api';

export interface EventVideoPlayerProps {
  /** The event ID to display video clip for */
  eventId: number;
  /** Optional CSS classes */
  className?: string;
}

/**
 * EventVideoPlayer component displays and manages video clips for events.
 *
 * Features:
 * - Automatic clip availability check on mount
 * - Generate clip button if no clip exists
 * - Loading states during generation
 * - HTML5 video player with controls
 * - Download button for clips
 * - Error handling for generation failures
 *
 * @example
 * <EventVideoPlayer eventId={123} />
 */
export default function EventVideoPlayer({ eventId, className = '' }: EventVideoPlayerProps) {
  // Clip info state
  const [clipInfo, setClipInfo] = useState<ClipInfoResponse | null>(null);
  const [isLoadingInfo, setIsLoadingInfo] = useState<boolean>(true);
  const [loadInfoError, setLoadInfoError] = useState<string | null>(null);

  // Generation state
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [generateError, setGenerateError] = useState<string | null>(null);

  // Fetch clip info on mount
  useEffect(() => {
    const loadClipInfo = async () => {
      setIsLoadingInfo(true);
      setLoadInfoError(null);

      try {
        const info = await fetchEventClipInfo(eventId);
        setClipInfo(info);
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Failed to load clip info';
        setLoadInfoError(errorMessage);
        console.error('Failed to fetch clip info:', error);
      } finally {
        setIsLoadingInfo(false);
      }
    };

    void loadClipInfo();
  }, [eventId]);

  // Handle generate clip button
  const handleGenerateClip = async () => {
    setIsGenerating(true);
    setGenerateError(null);

    try {
      const response: ClipGenerateResponse = await generateEventClip(eventId);

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
        setGenerateError(response.message || 'Failed to generate clip');
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to generate clip';
      setGenerateError(errorMessage);
      console.error('Failed to generate clip:', error);
    } finally {
      setIsGenerating(false);
    }
  };

  // Handle download clip
  const handleDownloadClip = () => {
    if (!clipInfo?.clip_url) return;

    const link = document.createElement('a');
    link.href = getEventClipUrl(clipInfo.clip_url);
    link.download = `event_${eventId}_clip.mp4`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Loading state
  if (isLoadingInfo) {
    return (
      <div
        className={`flex items-center justify-center rounded-lg bg-black/30 p-8 ${className}`}
        data-testid="clip-loading"
      >
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-sm text-gray-400">Loading clip info...</p>
        </div>
      </div>
    );
  }

  // Error loading clip info
  if (loadInfoError) {
    return (
      <div
        className={`flex items-center justify-center rounded-lg border border-red-800 bg-red-900/20 p-8 ${className}`}
        data-testid="clip-error"
      >
        <div className="flex flex-col items-center gap-3 text-center">
          <AlertCircle className="h-8 w-8 text-red-500" />
          <div>
            <p className="font-medium text-red-400">Failed to load clip info</p>
            <p className="mt-1 text-sm text-red-300">{loadInfoError}</p>
          </div>
        </div>
      </div>
    );
  }

  // No clip available - show generate button
  if (!clipInfo?.clip_available) {
    return (
      <div
        className={`flex flex-col items-center justify-center gap-4 rounded-lg border border-gray-800 bg-black/30 p-8 ${className}`}
        data-testid="clip-unavailable"
      >
        <div className="text-center">
          <p className="text-sm font-medium text-gray-300">No video clip available</p>
          <p className="mt-1 text-xs text-gray-400">
            Generate a clip from detection images for this event
          </p>
        </div>

        {generateError && (
          <div className="w-full rounded-md border border-red-800 bg-red-900/20 px-3 py-2 text-center">
            <p className="text-xs text-red-400">{generateError}</p>
          </div>
        )}

        <button
          onClick={() => void handleGenerateClip()}
          disabled={isGenerating}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-black transition-all hover:bg-[#88d200] active:bg-[#68a000] disabled:cursor-not-allowed disabled:opacity-50"
          aria-label="Generate video clip"
          data-testid="generate-clip-button"
        >
          {isGenerating ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Generating...
            </>
          ) : (
            <>
              <RefreshCw className="h-4 w-4" />
              Generate Clip
            </>
          )}
        </button>
      </div>
    );
  }

  // Clip available - show video player
  // clip_url is guaranteed to be non-null when clip_available is true
  // eslint-disable-next-line @typescript-eslint/no-non-null-assertion -- clip_url is guaranteed by API when clip_available is true
  const clipUrl = getEventClipUrl(clipInfo.clip_url!);

  return (
    <div className={`space-y-3 ${className}`} data-testid="clip-available">
      {/* Video player */}
      <div className="overflow-hidden rounded-lg bg-black">
{/* eslint-disable-next-line jsx-a11y/media-has-caption -- Security camera clips don't have captions */}
        <video
          src={clipUrl}
          controls
          className="w-full"
          preload="metadata"
          data-testid="video-player"
        >
          Your browser does not support the video tag.
        </video>
      </div>

      {/* Clip metadata and actions */}
      <div className="flex items-center justify-between rounded-lg border border-gray-800 bg-black/20 px-4 py-3">
        <div className="flex items-center gap-4 text-xs text-gray-400">
          {clipInfo.duration_seconds && (
            <span>
              Duration: <span className="font-medium text-gray-300">{clipInfo.duration_seconds}s</span>
            </span>
          )}
          {clipInfo.file_size_bytes && (
            <span>
              Size:{' '}
              <span className="font-medium text-gray-300">
                {(clipInfo.file_size_bytes / (1024 * 1024)).toFixed(1)} MB
              </span>
            </span>
          )}
          {clipInfo.generated_at && (
            <span>
              Generated:{' '}
              <span className="font-medium text-gray-300">
                {new Date(clipInfo.generated_at).toLocaleString()}
              </span>
            </span>
          )}
        </div>

        {/* Download button */}
        <button
          onClick={handleDownloadClip}
          className="flex items-center gap-1.5 rounded-md bg-gray-800 px-3 py-1.5 text-xs font-medium text-gray-300 transition-colors hover:bg-gray-700 hover:text-white"
          aria-label="Download clip"
          data-testid="download-clip-button"
        >
          <Download className="h-3.5 w-3.5" />
          Download
        </button>
      </div>
    </div>
  );
}
