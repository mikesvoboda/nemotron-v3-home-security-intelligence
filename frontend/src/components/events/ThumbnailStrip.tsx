import { Clock } from 'lucide-react';

export interface DetectionThumbnail {
  id: number;
  detected_at: string;
  thumbnail_url: string;
  object_type?: string;
  confidence?: number;
}

export interface ThumbnailStripProps {
  detections: DetectionThumbnail[];
  selectedDetectionId?: number;
  onThumbnailClick?: (detectionId: number) => void;
  loading?: boolean;
}

/**
 * ThumbnailStrip component displays a horizontal scrollable strip of detection thumbnails
 * with timestamps. Allows clicking thumbnails to view specific detections.
 */
export default function ThumbnailStrip({
  detections,
  selectedDetectionId,
  onThumbnailClick,
  loading = false,
}: ThumbnailStripProps) {
  if (loading) {
    return (
      <div className="rounded-lg border border-gray-800 bg-black/20 p-4">
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-400">
          Detection Sequence
        </h3>
        <div className="flex gap-2 overflow-x-auto pb-2">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="flex flex-col items-center gap-1"
              style={{ minWidth: '120px' }}
            >
              <div className="h-20 w-full animate-pulse rounded-lg bg-gray-800" />
              <div className="h-4 w-16 animate-pulse rounded bg-gray-800" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!detections || detections.length === 0) {
    return null;
  }

  // Format timestamp to show relative time or HH:MM:SS
  const formatTimestamp = (isoString: string): string => {
    try {
      const date = new Date(isoString);
      return date.toLocaleString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
      });
    } catch {
      return '--:--:--';
    }
  };

  // Calculate time difference from first detection
  const getRelativeTime = (isoString: string): string => {
    try {
      const firstTime = new Date(detections[0].detected_at).getTime();
      const currentTime = new Date(isoString).getTime();
      const diffSeconds = Math.floor((currentTime - firstTime) / 1000);

      if (diffSeconds === 0) return '00:00';

      const minutes = Math.floor(diffSeconds / 60);
      const seconds = diffSeconds % 60;
      return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    } catch {
      return '00:00';
    }
  };

  return (
    <div className="rounded-lg border border-gray-800 bg-black/20 p-4">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-400">
        Detection Sequence ({detections.length})
      </h3>
      <div className="flex gap-3 overflow-x-auto pb-2" style={{ scrollbarWidth: 'thin' }}>
        {detections.map((detection, index) => {
          const isSelected = selectedDetectionId === detection.id;
          const relativeTime = getRelativeTime(detection.detected_at);
          const timestamp = formatTimestamp(detection.detected_at);

          return (
            <button
              key={detection.id}
              onClick={() => onThumbnailClick?.(detection.id)}
              className={`group relative flex flex-shrink-0 flex-col items-center gap-2 rounded-lg p-2 transition-all ${
                isSelected
                  ? 'bg-[#76B900]/20 ring-2 ring-[#76B900]'
                  : 'hover:bg-gray-800/50 focus:bg-gray-800/50'
              }`}
              style={{ minWidth: '120px' }}
              aria-label={`View detection ${index + 1} at ${timestamp}`}
              type="button"
            >
              {/* Thumbnail image */}
              <div
                className={`relative overflow-hidden rounded-md border ${
                  isSelected ? 'border-[#76B900]' : 'border-gray-700'
                } transition-all group-hover:border-[#76B900]/50`}
              >
                <img
                  src={detection.thumbnail_url}
                  alt={`Detection ${index + 1}: ${detection.object_type || 'object'}`}
                  className="h-20 w-full object-cover"
                  loading="lazy"
                />
                {/* Sequence number badge */}
                <div className="absolute right-1 top-1 rounded-full bg-black/75 px-2 py-0.5 text-xs font-semibold text-white">
                  #{index + 1}
                </div>
              </div>

              {/* Timestamp and relative time */}
              <div className="flex flex-col items-center gap-0.5 text-xs">
                <div className="flex items-center gap-1 text-gray-400">
                  <Clock className="h-3 w-3" />
                  <span className="font-mono">{relativeTime}</span>
                </div>
                <span className="font-mono text-gray-500">{timestamp}</span>
              </div>

              {/* Object type and confidence (if available) */}
              {detection.object_type && (
                <div className="text-xs text-gray-400">
                  {detection.object_type}
                  {detection.confidence !== undefined &&
                    ` (${Math.round(detection.confidence * 100)}%)`}
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
