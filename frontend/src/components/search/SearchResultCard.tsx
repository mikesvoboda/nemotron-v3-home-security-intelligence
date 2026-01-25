import { Camera, Clock, Eye, Star, Tag } from 'lucide-react';

import RiskBadge from '../common/RiskBadge';

import type { SearchResult } from '../../services/api';
import type { RiskLevel } from '../../utils/risk';

export interface SearchResultCardProps {
  /** Search result data */
  result: SearchResult;
  /** Called when the card is clicked */
  onClick?: (eventId: number) => void;
  /** Highlighted search terms (for future highlighting support) */
  highlightTerms?: string[];
  /** Whether the card is currently selected */
  isSelected?: boolean;
  /** Optional class name */
  className?: string;
}

/**
 * Format a relevance score for display
 * Higher scores indicate better matches
 */
function formatRelevanceScore(score: number): string {
  // Score is typically between 0 and ~1 for ts_rank
  // Display as a percentage-like value
  const percentage = Math.min(100, Math.round(score * 100));
  return `${percentage}%`;
}

/**
 * Get color class based on relevance score
 */
function getRelevanceColor(score: number): string {
  if (score >= 0.8) return 'text-green-400';
  if (score >= 0.5) return 'text-[#76B900]';
  if (score >= 0.3) return 'text-yellow-400';
  return 'text-gray-400';
}

/**
 * Format date for display
 */
function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

/**
 * Format time for display
 */
function formatTime(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * SearchResultCard displays a single search result with relevance scoring.
 *
 * Features:
 * - Prominent relevance score display
 * - Thumbnail image preview (NEM-3614)
 * - Risk level badge
 * - Camera and timestamp info
 * - Object types display
 * - Click to view details
 */
export default function SearchResultCard({
  result,
  onClick,
  isSelected = false,
  className = '',
}: SearchResultCardProps) {
  const handleClick = () => {
    if (onClick) {
      onClick(result.id);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleClick();
    }
  };

  // Parse object types
  const objectTypes =
    result.object_types
      ?.split(',')
      .map((t) => t.trim())
      .filter(Boolean) || [];

  // Get thumbnail URL with type safety (NEM-3614)
  const thumbnailUrl = (result as unknown as { thumbnail_url?: string }).thumbnail_url;

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      className={`group cursor-pointer rounded-lg border bg-[#1F1F1F] transition-all hover:border-[#76B900]/50 hover:shadow-lg ${
        isSelected ? 'border-[#76B900] ring-1 ring-[#76B900]' : 'border-gray-800'
      } ${className}`}
      aria-pressed={isSelected}
    >
      {/* Thumbnail Image (NEM-3614) */}
      {thumbnailUrl && (
        <div className="relative h-40 w-full overflow-hidden rounded-t-lg bg-gray-900">
          <img
            src={thumbnailUrl}
            alt={`Thumbnail for event ${result.id}`}
            className="h-full w-full object-cover transition-transform group-hover:scale-105"
            loading="lazy"
            onError={(e) => {
              // Hide image on error
              (e.target as HTMLImageElement).style.display = 'none';
            }}
          />
          {/* Risk badge overlay on thumbnail */}
          <div className="absolute right-2 top-2">
            <RiskBadge level={(result.risk_level as RiskLevel) || 'low'} size="sm" animated={false} />
          </div>
        </div>
      )}

      <div className="p-4">
        {/* Header Row: Relevance Score + Risk Badge (shown when no thumbnail) */}
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Star className={`h-4 w-4 ${getRelevanceColor(result.relevance_score)}`} />
            <span className={`text-sm font-semibold ${getRelevanceColor(result.relevance_score)}`}>
              {formatRelevanceScore(result.relevance_score)} match
            </span>
          </div>
          {!thumbnailUrl && (
            <RiskBadge level={(result.risk_level as RiskLevel) || 'low'} size="sm" animated={false} />
          )}
        </div>

      {/* Summary */}
      <h3 className="mb-2 line-clamp-2 text-base font-medium text-white">
        {result.summary || 'No summary available'}
      </h3>

      {/* Reasoning (if available) */}
      {result.reasoning && (
        <p className="mb-3 line-clamp-2 text-sm text-gray-400">{result.reasoning}</p>
      )}

      {/* Meta Information */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-gray-400">
        {/* Camera */}
        <div className="flex items-center gap-1.5">
          <Camera className="h-3.5 w-3.5" />
          <span>{result.camera_name || result.camera_id}</span>
        </div>

        {/* Date and Time */}
        <div className="flex items-center gap-1.5">
          <Clock className="h-3.5 w-3.5" />
          <span>
            {formatDate(result.started_at)} at {formatTime(result.started_at)}
          </span>
        </div>

        {/* Detection Count */}
        <div className="flex items-center gap-1.5">
          <Eye className="h-3.5 w-3.5" />
          <span>
            {result.detection_count} detection{result.detection_count !== 1 ? 's' : ''}
          </span>
        </div>
      </div>

      {/* Object Types */}
      {objectTypes.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Tag className="h-3.5 w-3.5 text-gray-500" />
          {objectTypes.map((type, index) => (
            <span
              key={index}
              className="rounded-full bg-gray-800 px-2 py-0.5 text-xs font-medium text-gray-300"
            >
              {type}
            </span>
          ))}
        </div>
      )}

      {/* Reviewed Status */}
      {result.reviewed && (
        <div className="mt-3 flex items-center gap-1.5 text-xs text-[#76B900]">
          <div className="h-2 w-2 rounded-full bg-[#76B900]" />
          <span>Reviewed</span>
        </div>
      )}
      </div>
    </div>
  );
}
