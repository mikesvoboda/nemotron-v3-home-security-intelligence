import { ChevronDown, ChevronUp, Clock, Eye, Timer, TrendingUp } from 'lucide-react';
import { useState } from 'react';

import {
  calculateAverageConfidence,
  calculateMaxConfidence,
  formatConfidencePercent,
  getConfidenceBgColorClass,
  getConfidenceBorderColorClass,
  getConfidenceLabel,
  getConfidenceLevel,
  getConfidenceTextColorClass,
  sortDetectionsByConfidence,
} from '../../utils/confidence';
import { getRiskColor, getRiskLevel } from '../../utils/risk';
import { formatDuration } from '../../utils/time';
import ObjectTypeBadge from '../common/ObjectTypeBadge';
import RiskBadge from '../common/RiskBadge';
import DetectionImage from '../detection/DetectionImage';

import type { BoundingBox } from '../detection/BoundingBoxOverlay';

export interface Detection {
  label: string;
  confidence: number;
  bbox?: { x: number; y: number; width: number; height: number };
}

export interface EventCardProps {
  id: string;
  timestamp: string;
  camera_name: string;
  risk_score: number;
  risk_label: string;
  summary: string;
  reasoning?: string;
  thumbnail_url?: string;
  detections: Detection[];
  started_at?: string;
  ended_at?: string | null;
  onViewDetails?: (eventId: string) => void;
  onClick?: (eventId: string) => void;
  className?: string;
  /** When true, adds left margin to header to accommodate an overlaying checkbox */
  hasCheckboxOverlay?: boolean;
}

/**
 * EventCard component displays a single security event with thumbnail, detections, and AI analysis
 */
export default function EventCard({
  id,
  timestamp,
  camera_name,
  risk_score,
  summary,
  reasoning,
  thumbnail_url,
  detections,
  started_at,
  ended_at,
  onViewDetails,
  onClick,
  className = '',
  hasCheckboxOverlay = false,
}: EventCardProps) {
  const [showReasoning, setShowReasoning] = useState(false);

  // Convert ISO timestamp to readable format
  const formatTimestamp = (isoString: string): string => {
    try {
      const date = new Date(isoString);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMins / 60);
      const diffDays = Math.floor(diffHours / 24);

      // If within last hour, show "X minutes ago"
      if (diffMins < 60) {
        return diffMins <= 1 ? 'Just now' : `${diffMins} minutes ago`;
      }

      // If within last 24 hours, show "X hours ago"
      if (diffHours < 24) {
        return diffHours === 1 ? '1 hour ago' : `${diffHours} hours ago`;
      }

      // If within last week, show "X days ago"
      if (diffDays < 7) {
        return diffDays === 1 ? '1 day ago' : `${diffDays} days ago`;
      }

      // Otherwise show formatted date and time
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

  // Convert Detection to BoundingBox format for DetectionImage component
  const convertToBoundingBoxes = (): BoundingBox[] => {
    return detections
      .filter((d) => d.bbox)
      .map((d) => {
        const bbox = d.bbox as { x: number; y: number; width: number; height: number };
        return {
          x: bbox.x,
          y: bbox.y,
          width: bbox.width,
          height: bbox.height,
          label: d.label,
          confidence: d.confidence,
        };
      });
  };

  // Get risk level from score
  const riskLevel = getRiskLevel(risk_score);

  // Format confidence as percentage
  const formatConfidence = (confidence: number): string => {
    return `${Math.round(confidence * 100)}%`;
  };

  // Get unique object types from detections
  const uniqueObjectTypes = Array.from(new Set(detections.map((d) => d.label.toLowerCase())));

  // Calculate aggregate confidence metrics
  const avgConfidence = calculateAverageConfidence(detections);
  const maxConfidence = calculateMaxConfidence(detections);

  // Sort detections by confidence (highest first)
  const sortedDetections = sortDetectionsByConfidence(detections);

  // Get left border color class based on risk level
  const getBorderColorClass = (): string => {
    const borderColors: Record<string, string> = {
      low: 'border-l-risk-low',
      medium: 'border-l-risk-medium',
      high: 'border-l-risk-high',
      critical: 'border-l-red-500',
    };
    return borderColors[riskLevel];
  };

  // Handle card click - don't trigger if clicking on interactive elements
  const handleCardClick = (e: React.MouseEvent<HTMLDivElement>) => {
    // Check if the click target is an interactive element (button, etc.)
    const target = e.target as HTMLElement;
    const isInteractive = target.closest('button') || target.closest('a');

    if (onClick && !isInteractive) {
      onClick(id);
    }
  };

  // Determine if card should be clickable
  const isClickable = !!onClick;

  return (
    <div
      className={`rounded-lg border border-gray-800 ${getBorderColorClass()} border-l-4 bg-[#1F1F1F] p-4 shadow-lg transition-all hover:border-gray-700 ${isClickable ? 'cursor-pointer hover:bg-[#252525]' : ''} ${className}`}
      {...(isClickable && {
        onClick: handleCardClick,
        onKeyDown: (e: React.KeyboardEvent) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onClick?.(id);
          }
        },
        role: 'button',
        tabIndex: 0,
        'aria-label': `View details for event from ${camera_name}`,
      })}
    >
      {/* Header: Camera name, timestamp, risk badge */}
      <div className={`mb-3 flex items-start justify-between ${hasCheckboxOverlay ? 'ml-8' : ''}`}>
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-base font-semibold text-white" title={camera_name}>
            {camera_name}
          </h3>
          <div className="mt-1 flex flex-col gap-1">
            <div className="flex items-center gap-1.5 text-sm text-gray-400">
              <Clock className="h-3.5 w-3.5" />
              <span>{formatTimestamp(timestamp)}</span>
            </div>
            {(started_at || ended_at !== undefined) && (
              <div className="flex items-center gap-1.5 text-sm text-gray-400">
                <Timer className="h-3.5 w-3.5" />
                <span>Duration: {formatDuration(started_at || timestamp, ended_at ?? null)}</span>
              </div>
            )}
          </div>
        </div>
        <RiskBadge level={riskLevel} score={risk_score} showScore={true} size="md" />
      </div>

      {/* Object Type Badges */}
      {uniqueObjectTypes.length > 0 && (
        <div className="mb-3 flex flex-wrap gap-1.5">
          {uniqueObjectTypes.map((type) => (
            <ObjectTypeBadge key={type} type={type} size="sm" />
          ))}
        </div>
      )}

      {/* Risk Score Progress Bar */}
      <div className="mb-3">
        <div className="mb-1.5 flex items-center justify-between text-xs text-gray-400">
          <span className="font-medium">Risk Score</span>
          <span className="font-semibold">{risk_score}/100</span>
        </div>
        <div
          className="h-2 w-full overflow-hidden rounded-full bg-gray-800"
          role="progressbar"
          aria-valuenow={risk_score}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Risk score: ${risk_score} out of 100`}
        >
          <div
            className="h-full rounded-full transition-all duration-500 ease-out"
            style={{
              width: `${risk_score}%`,
              backgroundColor: getRiskColor(riskLevel),
            }}
          />
        </div>
      </div>

      {/* Thumbnail with bounding boxes (if available) */}
      {thumbnail_url && (
        <div className="mb-3 overflow-hidden rounded-md bg-black">
          {detections.some((d) => d.bbox) ? (
            <DetectionImage
              src={thumbnail_url}
              alt={`${camera_name} detection at ${formatTimestamp(timestamp)}`}
              boxes={convertToBoundingBoxes()}
              showLabels={true}
              showConfidence={true}
              className="w-full"
            />
          ) : (
            <img
              src={thumbnail_url}
              alt={`${camera_name} at ${formatTimestamp(timestamp)}`}
              className="h-48 w-full object-cover"
            />
          )}
        </div>
      )}

      {/* AI Summary */}
      <div className="mb-3">
        <p className="text-sm leading-relaxed text-gray-200">{summary}</p>
      </div>

      {/* Detection List with Color-Coded Confidence */}
      {detections.length > 0 && (
        <div className="mb-3 rounded-md bg-black/30 p-3">
          <div className="mb-2 flex items-center justify-between">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-400">
              Detections ({detections.length})
            </h4>
            {/* Aggregate Confidence Display */}
            {avgConfidence !== null && maxConfidence !== null && (
              <div
                className="flex items-center gap-2 text-xs"
                title={`Average: ${formatConfidencePercent(avgConfidence)} | Max: ${formatConfidencePercent(maxConfidence)}`}
              >
                <TrendingUp className="h-3 w-3 text-gray-400" aria-hidden="true" />
                <span className="text-gray-400">Avg:</span>
                <span
                  className={`font-semibold ${getConfidenceTextColorClass(getConfidenceLevel(avgConfidence))}`}
                >
                  {formatConfidencePercent(avgConfidence)}
                </span>
                <span className="text-gray-500">|</span>
                <span className="text-gray-400">Max:</span>
                <span
                  className={`font-semibold ${getConfidenceTextColorClass(getConfidenceLevel(maxConfidence))}`}
                >
                  {formatConfidencePercent(maxConfidence)}
                </span>
              </div>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            {sortedDetections.map((detection, index) => {
              const level = getConfidenceLevel(detection.confidence);
              const confidenceLabel = getConfidenceLabel(level);
              return (
                <div
                  key={`${detection.label}-${index}`}
                  className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs ${getConfidenceBgColorClass(level)} ${getConfidenceBorderColorClass(level)}`}
                  title={`${detection.label}: ${formatConfidence(detection.confidence)} - ${confidenceLabel}`}
                >
                  <span className="font-medium text-white">{detection.label}</span>
                  <span className={`font-semibold ${getConfidenceTextColorClass(level)}`}>
                    {formatConfidence(detection.confidence)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* AI Reasoning (expandable) */}
      {reasoning && (
        <div className="mb-3">
          <button
            onClick={() => setShowReasoning(!showReasoning)}
            className="flex w-full items-center justify-between rounded-md bg-[#76B900]/10 px-3 py-2 text-left text-sm font-medium text-[#76B900] transition-colors hover:bg-[#76B900]/20"
            aria-expanded={showReasoning}
            aria-controls={`reasoning-${id}`}
          >
            <span>AI Reasoning</span>
            {showReasoning ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </button>
          {showReasoning && (
            <div
              id={`reasoning-${id}`}
              className="mt-2 rounded-md bg-black/20 p-3 text-sm leading-relaxed text-gray-300"
            >
              {reasoning}
            </div>
          )}
        </div>
      )}

      {/* View Details Button */}
      {onViewDetails && (
        <button
          onClick={() => onViewDetails(id)}
          className="flex w-full items-center justify-center gap-2 rounded-md bg-[#76B900] px-4 py-2 text-sm font-semibold text-black transition-all hover:bg-[#88d200] active:bg-[#68a000]"
          aria-label={`View details for event ${id}`}
        >
          <Eye className="h-4 w-4" />
          View Details
        </button>
      )}
    </div>
  );
}
