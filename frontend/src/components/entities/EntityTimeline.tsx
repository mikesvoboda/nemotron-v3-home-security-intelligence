import { Camera, Car, Clock, User } from 'lucide-react';

export interface EntityAppearance {
  detection_id: string;
  camera_id: string;
  camera_name: string | null;
  timestamp: string;
  thumbnail_url: string | null;
  similarity_score: number | null;
  attributes: Record<string, unknown>;
}

export interface EntityTimelineProps {
  entity_id: string;
  entity_type: 'person' | 'vehicle';
  appearances: EntityAppearance[];
  className?: string;
}

/**
 * EntityTimeline displays a chronological timeline of entity appearances
 * across different cameras, showing thumbnails and similarity scores.
 */
export default function EntityTimeline({
  entity_type,
  appearances,
  className = '',
}: EntityTimelineProps) {
  // Format timestamp to relative time
  const formatTimestamp = (isoString: string): string => {
    try {
      const date = new Date(isoString);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMins / 60);
      const diffDays = Math.floor(diffHours / 24);

      if (diffMins < 1) return 'Just now';
      if (diffMins < 60) return `${diffMins} minutes ago`;
      if (diffHours < 24) return diffHours === 1 ? '1 hour ago' : `${diffHours} hours ago`;
      if (diffDays < 7) return diffDays === 1 ? '1 day ago' : `${diffDays} days ago`;

      return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
        hour: 'numeric',
        minute: '2-digit',
        hour12: true,
      });
    } catch {
      return isoString;
    }
  };

  // Format similarity score as percentage
  const formatSimilarity = (score: number): string => {
    return `${Math.round(score * 100)}%`;
  };

  // Get entity type label
  const entityTypeLabel = entity_type === 'person' ? 'person' : 'vehicle';

  // Sort appearances by timestamp (most recent first)
  const sortedAppearances = [...appearances].sort((a, b) => {
    return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
  });

  return (
    <div className={`rounded-lg border border-gray-800 bg-[#1F1F1F] p-4 ${className}`}>
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-lg font-semibold text-white">
          <Clock className="h-5 w-5 text-[#76B900]" />
          Appearance Timeline
        </h3>
        <span className="text-sm text-gray-400">
          {appearances.length} {entityTypeLabel} {appearances.length === 1 ? 'appearance' : 'appearances'}
        </span>
      </div>

      {/* Empty state */}
      {appearances.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-8 text-gray-500">
          {entity_type === 'person' ? (
            <User className="mb-2 h-12 w-12" />
          ) : (
            <Car className="mb-2 h-12 w-12" />
          )}
          <p>No appearances recorded</p>
        </div>
      ) : (
        /* Timeline */
        <ul className="space-y-0">
          {sortedAppearances.map((appearance, index) => (
            <li key={appearance.detection_id} className="relative">
              {/* Timeline connector line */}
              {index < sortedAppearances.length - 1 && (
                <div className="absolute left-6 top-12 h-full w-px border-l-2 border-gray-700" />
              )}

              <div className="flex gap-3 pb-4">
                {/* Thumbnail */}
                <div className="relative flex h-12 w-12 flex-shrink-0 items-center justify-center overflow-hidden rounded-full bg-gray-800">
                  {appearance.thumbnail_url ? (
                    <img
                      src={appearance.thumbnail_url}
                      alt={`${entity_type} at ${appearance.camera_name || appearance.camera_id}`}
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <div
                      data-testid="timeline-placeholder"
                      className="flex h-full w-full items-center justify-center text-gray-600"
                    >
                      {entity_type === 'person' ? (
                        <User className="h-6 w-6" />
                      ) : (
                        <Car className="h-6 w-6" />
                      )}
                    </div>
                  )}
                </div>

                {/* Content */}
                <div className="min-w-0 flex-1">
                  {/* Camera name */}
                  <div className="flex items-center gap-2">
                    <Camera className="h-4 w-4 text-gray-400" />
                    <span className="font-medium text-white">
                      {appearance.camera_name || appearance.camera_id}
                    </span>
                    {appearance.similarity_score !== null && (
                      <span className="rounded bg-[#76B900]/20 px-1.5 py-0.5 text-xs font-medium text-[#76B900]">
                        {formatSimilarity(appearance.similarity_score)}
                      </span>
                    )}
                  </div>

                  {/* Timestamp */}
                  <div className="mt-1 flex items-center gap-1 text-xs text-gray-400">
                    <Clock className="h-3 w-3" />
                    <span>{formatTimestamp(appearance.timestamp)}</span>
                  </div>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
