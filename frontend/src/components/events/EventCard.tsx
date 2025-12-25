import { ChevronDown, ChevronUp, Clock, Eye } from 'lucide-react';
import { useState } from 'react';

import { getRiskLevel } from '../../utils/risk';
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
  onViewDetails?: (eventId: string) => void;
  className?: string;
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
  onViewDetails,
  className = '',
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

  return (
    <div
      className={`rounded-lg border border-gray-800 bg-[#1F1F1F] p-4 shadow-lg transition-all hover:border-gray-700 ${className}`}
    >
      {/* Header: Camera name, timestamp, risk badge */}
      <div className="mb-3 flex items-start justify-between">
        <div className="flex-1">
          <h3 className="text-base font-semibold text-white">{camera_name}</h3>
          <div className="mt-1 flex items-center gap-1.5 text-sm text-gray-400">
            <Clock className="h-3.5 w-3.5" />
            <span>{formatTimestamp(timestamp)}</span>
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

      {/* Detection List */}
      {detections.length > 0 && (
        <div className="mb-3 rounded-md bg-black/30 p-3">
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-400">
            Detections ({detections.length})
          </h4>
          <div className="flex flex-wrap gap-2">
            {detections.map((detection, index) => (
              <div
                key={`${detection.label}-${index}`}
                className="flex items-center gap-1.5 rounded-full bg-gray-800/60 px-3 py-1 text-xs"
              >
                <span className="font-medium text-white">{detection.label}</span>
                <span className="text-gray-400">{formatConfidence(detection.confidence)}</span>
              </div>
            ))}
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
