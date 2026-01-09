import { Dialog, Transition } from '@headlessui/react';
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Clock,
  Download,
  Film,
  Flag,
  RefreshCw,
  Save,
  Timer,
  TrendingUp,
  X,
} from 'lucide-react';
import { Fragment, useEffect, useMemo, useState } from 'react';

import EnrichmentPanel from './EnrichmentPanel';
import EventVideoPlayer from './EventVideoPlayer';
import ThumbnailStrip from './ThumbnailStrip';
import {
  fetchEventDetections,
  getDetectionFullImageUrl,
  getDetectionImageUrl,
  getDetectionVideoThumbnailUrl,
  getDetectionVideoUrl,
} from '../../services/api';
import { triggerEvaluation, AuditApiError } from '../../services/auditApi';
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
import { getRiskLevel } from '../../utils/risk';
import { formatDuration } from '../../utils/time';
import { EventAuditDetail } from '../audit';
import Lightbox from '../common/Lightbox';
import RiskBadge from '../common/RiskBadge';
import DetectionImage from '../detection/DetectionImage';
import VideoPlayer from '../video/VideoPlayer';

import type { DetectionThumbnail } from './ThumbnailStrip';
import type { EnrichmentData } from '../../types/enrichment';
import type { Detection as ApiDetection } from '../../types/generated';
import type { LightboxImage } from '../common/Lightbox';
import type { BoundingBox } from '../detection/BoundingBoxOverlay';

export interface Detection {
  label: string;
  confidence: number;
  bbox?: { x: number; y: number; width: number; height: number };
  enrichment_data?: EnrichmentData;
}

export interface Event {
  id: string;
  timestamp: string;
  camera_name: string;
  risk_score: number;
  risk_label: string;
  summary: string;
  reasoning?: string;
  image_url?: string;
  thumbnail_url?: string;
  detections: Detection[];
  started_at?: string;
  ended_at?: string | null;
  reviewed?: boolean;
  notes?: string | null;
  flagged?: boolean;
}

export interface EventDetailModalProps {
  event: Event | null;
  isOpen: boolean;
  onClose: () => void;
  onMarkReviewed?: (eventId: string) => void;
  onNavigate?: (direction: 'prev' | 'next') => void;
  onSaveNotes?: (eventId: string, notes: string) => Promise<void>;
  onFlagEvent?: (eventId: string, flagged: boolean) => Promise<void>;
  onDownloadMedia?: (eventId: string) => Promise<void>;
}

/**
 * EventDetailModal component displays full event details in a modal overlay
 */
export default function EventDetailModal({
  event,
  isOpen,
  onClose,
  onMarkReviewed,
  onNavigate,
  onSaveNotes,
  onFlagEvent,
  onDownloadMedia,
}: EventDetailModalProps) {
  // State for active tab (Details vs AI Audit vs Video Clip)
  const [activeTab, setActiveTab] = useState<'details' | 'audit' | 'clip'>('details');

  // State for notes editing
  const [notesText, setNotesText] = useState<string>('');
  const [isSavingNotes, setIsSavingNotes] = useState<boolean>(false);
  const [notesSaved, setNotesSaved] = useState<boolean>(false);

  // State for detection sequence thumbnails
  const [detectionSequence, setDetectionSequence] = useState<DetectionThumbnail[]>([]);
  const [loadingDetections, setLoadingDetections] = useState<boolean>(false);
  const [selectedDetectionId, setSelectedDetectionId] = useState<number | undefined>();

  // State for full detection data (including video metadata)
  const [detectionsData, setDetectionsData] = useState<ApiDetection[]>([]);

  // State for flag event
  const [isFlagging, setIsFlagging] = useState<boolean>(false);

  // State for download media
  const [isDownloading, setIsDownloading] = useState<boolean>(false);

  // State for thumbnail lightbox
  const [thumbnailLightboxOpen, setThumbnailLightboxOpen] = useState<boolean>(false);
  const [thumbnailLightboxIndex, setThumbnailLightboxIndex] = useState<number>(0);

  // State for re-evaluate AI analysis
  const [isReEvaluating, setIsReEvaluating] = useState<boolean>(false);
  const [reEvaluateError, setReEvaluateError] = useState<string | null>(null);
  const [reEvaluateSuccess, setReEvaluateSuccess] = useState<boolean>(false);

  // Initialize notes text and reset re-evaluate state when event changes
  useEffect(() => {
    if (event) {
      setNotesText(event.notes || '');
      setNotesSaved(false);
      setReEvaluateError(null);
      setReEvaluateSuccess(false);
    }
  }, [event]);

  // Fetch detection sequence when event changes
  useEffect(() => {
    if (!event || !event.id) {
      setDetectionSequence([]);
      setDetectionsData([]);
      setSelectedDetectionId(undefined);
      return;
    }

    const loadDetections = async () => {
      setLoadingDetections(true);
      try {
        // Parse event ID as number (API expects number)
        const eventId = parseInt(event.id, 10);
        if (isNaN(eventId)) {
          console.error('Invalid event ID:', event.id);
          return;
        }

        const response = await fetchEventDetections(eventId, { limit: 100 });

        // Store full detection data for video metadata access
        setDetectionsData(response.detections);

        // Transform API detections to thumbnail format
        // For videos, use the video thumbnail endpoint; for images, use the image endpoint
        const thumbnails: DetectionThumbnail[] = response.detections.map((detection) => ({
          id: detection.id,
          detected_at: detection.detected_at,
          thumbnail_url:
            detection.media_type === 'video'
              ? getDetectionVideoThumbnailUrl(detection.id)
              : getDetectionImageUrl(detection.id),
          object_type: detection.object_type || undefined,
          confidence: detection.confidence || undefined,
        }));

        setDetectionSequence(thumbnails);

        // Auto-select first detection if none selected
        if (thumbnails.length > 0 && !selectedDetectionId) {
          setSelectedDetectionId(thumbnails[0].id);
        }
      } catch (error) {
        console.error('Failed to fetch detections:', error);
        setDetectionSequence([]);
        setDetectionsData([]);
      } finally {
        setLoadingDetections(false);
      }
    };

    void loadDetections();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- selectedDetectionId excluded: changing selection should not refetch detections
  }, [event]);

  // Handle notes save
  const handleSaveNotes = async () => {
    if (!event || !onSaveNotes) return;

    setIsSavingNotes(true);
    setNotesSaved(false);

    try {
      await onSaveNotes(event.id, notesText);
      setNotesSaved(true);
      // Clear saved indicator after 3 seconds
      setTimeout(() => setNotesSaved(false), 3000);
    } catch (error) {
      console.error('Failed to save notes:', error);
    } finally {
      setIsSavingNotes(false);
    }
  };

  // Handle flag event toggle
  const handleFlagEvent = async () => {
    if (!event || !onFlagEvent) return;

    setIsFlagging(true);

    try {
      const newFlaggedState = !event.flagged;
      await onFlagEvent(event.id, newFlaggedState);
    } catch (error) {
      console.error('Failed to flag event:', error);
    } finally {
      setIsFlagging(false);
    }
  };

  // Handle download media
  const handleDownloadMedia = async () => {
    if (!event || !onDownloadMedia) return;

    setIsDownloading(true);

    try {
      await onDownloadMedia(event.id);
    } catch (error) {
      console.error('Failed to download media:', error);
    } finally {
      setIsDownloading(false);
    }
  };

  // Handle re-evaluate AI analysis
  const handleReEvaluate = async () => {
    if (!event) return;

    const eventId = parseInt(event.id, 10);
    if (isNaN(eventId)) {
      console.error('Invalid event ID for re-evaluation:', event.id);
      return;
    }

    setIsReEvaluating(true);
    setReEvaluateError(null);
    setReEvaluateSuccess(false);

    try {
      await triggerEvaluation(eventId, false);
      setReEvaluateSuccess(true);
      // Auto-dismiss success indicator after 3 seconds
      setTimeout(() => setReEvaluateSuccess(false), 3000);
    } catch (error) {
      if (error instanceof AuditApiError) {
        setReEvaluateError(error.message);
      } else {
        setReEvaluateError('Failed to re-evaluate event');
      }
      console.error('Failed to re-evaluate event:', error);
    } finally {
      setIsReEvaluating(false);
    }
  };

  // Handle thumbnail click to view specific detection
  const handleThumbnailClick = (detectionId: number) => {
    setSelectedDetectionId(detectionId);
    // TODO: Could add logic to update the main image view to show this specific detection
  };

  // Handle thumbnail double-click to open lightbox for full-size view
  const handleThumbnailLightbox = (detectionId: number) => {
    const index = detectionSequence.findIndex((d) => d.id === detectionId);
    if (index !== -1) {
      setThumbnailLightboxIndex(index);
      setThumbnailLightboxOpen(true);
    }
  };

  // Build lightbox images array from detection sequence (images only, not videos)
  const thumbnailLightboxImages = useMemo((): LightboxImage[] => {
    // Helper to format timestamp for lightbox
    const formatDetectionTimestamp = (isoString: string): string => {
      try {
        const date = new Date(isoString);
        return date.toLocaleString('en-US', {
          month: 'short',
          day: 'numeric',
          hour: 'numeric',
          minute: '2-digit',
          hour12: true,
        });
      } catch {
        return isoString;
      }
    };

    return detectionSequence
      .filter((d) => {
        // Exclude videos from lightbox (they use video player instead)
        const detection = detectionsData.find((det) => det.id === d.id);
        return detection?.media_type !== 'video';
      })
      .map((detection) => ({
        // Use full-size original image for lightbox (without bounding box overlay)
        src: getDetectionFullImageUrl(detection.id),
        alt: `Detection ${detection.object_type || 'object'} at ${formatDetectionTimestamp(detection.detected_at)}`,
        caption: detection.object_type
          ? `${detection.object_type}${detection.confidence !== undefined ? ` (${Math.round(detection.confidence * 100)}%)` : ''}`
          : undefined,
      }));
  }, [detectionSequence, detectionsData]);

  // Handle escape key to close modal
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);

  // Handle keyboard navigation (arrow keys)
  useEffect(() => {
    const handleKeyboard = (e: KeyboardEvent) => {
      if (!isOpen || !onNavigate) return;

      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        onNavigate('prev');
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        onNavigate('next');
      }
    };

    document.addEventListener('keydown', handleKeyboard);
    return () => document.removeEventListener('keydown', handleKeyboard);
  }, [isOpen, onNavigate]);

  // Get the currently selected detection's full data (including video metadata)
  const selectedDetection = useMemo(() => {
    if (!selectedDetectionId || detectionsData.length === 0) return null;
    return detectionsData.find((d) => d.id === selectedDetectionId) || null;
  }, [selectedDetectionId, detectionsData]);

  // Determine if selected detection is a video
  const isVideoDetection = selectedDetection?.media_type === 'video';

  if (!event) {
    return null;
  }

  // Format video duration (e.g., "2m 30s" or "45s")
  const formatVideoDuration = (seconds: number): string => {
    if (!seconds || !isFinite(seconds)) return 'Unknown';
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    if (mins > 0) {
      return `${mins}m ${secs}s`;
    }
    return `${secs}s`;
  };

  // Format video resolution (e.g., "1920x1080")
  const formatVideoResolution = (width?: number | null, height?: number | null): string | null => {
    if (!width || !height) return null;
    return `${width}x${height}`;
  };

  // Convert ISO timestamp to readable format
  const formatTimestamp = (isoString: string): string => {
    try {
      const date = new Date(isoString);
      return date.toLocaleString('en-US', {
        month: 'long',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        second: '2-digit',
        hour12: true,
      });
    } catch {
      return isoString;
    }
  };

  // Convert Detection to BoundingBox format for DetectionImage component
  const convertToBoundingBoxes = (): BoundingBox[] => {
    return event.detections
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
  const riskLevel = getRiskLevel(event.risk_score);

  // Format confidence as percentage
  const formatConfidence = (confidence: number): string => {
    return `${Math.round(confidence * 100)}%`;
  };

  // Use full-size image if available, otherwise fallback to thumbnail
  const imageUrl = event.image_url || event.thumbnail_url;
  const hasBoundingBoxes = event.detections.some((d) => d.bbox);

  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={onClose}>
        {/* Dark backdrop */}
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/75" aria-hidden="true" />
        </Transition.Child>

        {/* Modal content */}
        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <Dialog.Panel className="w-full max-w-4xl transform overflow-hidden rounded-xl border border-gray-800 bg-[#1A1A1A] shadow-2xl transition-all" data-testid="event-detail-modal">
                {/* Header */}
                <div className="flex items-start justify-between border-b border-gray-800 p-6">
                  <div className="flex-1">
                    <Dialog.Title
                      as="h2"
                      className="text-2xl font-bold text-white"
                      id="event-detail-title"
                      data-testid="detection-camera"
                    >
                      {event.camera_name}
                    </Dialog.Title>
                    <div className="mt-2 flex flex-col gap-1">
                      <div className="flex items-center gap-2 text-sm text-gray-400" data-testid="detection-timestamp">
                        <Clock className="h-4 w-4" />
                        <span>{formatTimestamp(event.timestamp)}</span>
                      </div>
                      {(event.started_at || event.ended_at !== undefined) && (
                        <div className="flex items-center gap-2 text-sm text-gray-400">
                          <Timer className="h-4 w-4" />
                          <span>
                            Duration:{' '}
                            {formatDuration(
                              event.started_at || event.timestamp,
                              event.ended_at ?? null
                            )}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div data-testid="risk-score">
                      <RiskBadge
                        level={riskLevel}
                        score={event.risk_score}
                        showScore={true}
                        size="lg"
                      />
                    </div>
                    <button
                      onClick={onClose}
                      className="rounded-lg p-2 text-gray-400 transition-colors hover:bg-gray-800 hover:text-white"
                      aria-label="Close modal"
                      data-testid="close-modal-button"
                    >
                      <X className="h-6 w-6" />
                    </button>
                  </div>
                </div>

                {/* Tab Navigation */}
                <div className="flex border-b border-gray-800 px-6">
                  <button
                    onClick={() => setActiveTab('details')}
                    className={`px-4 py-3 text-sm font-medium transition-colors ${
                      activeTab === 'details'
                        ? 'border-b-2 border-[#76B900] text-[#76B900]'
                        : 'text-gray-400 hover:text-gray-200'
                    }`}
                  >
                    Details
                  </button>
                  <button
                    onClick={() => setActiveTab('audit')}
                    className={`px-4 py-3 text-sm font-medium transition-colors ${
                      activeTab === 'audit'
                        ? 'border-b-2 border-[#76B900] text-[#76B900]'
                        : 'text-gray-400 hover:text-gray-200'
                    }`}
                  >
                    AI Audit
                  </button>
                  <button
                    onClick={() => setActiveTab('clip')}
                    className={`px-4 py-3 text-sm font-medium transition-colors ${
                      activeTab === 'clip'
                        ? 'border-b-2 border-[#76B900] text-[#76B900]'
                        : 'text-gray-400 hover:text-gray-200'
                    }`}
                    data-testid="video-clip-tab"
                  >
                    Video Clip
                  </button>
                </div>

                {/* Content */}
                <div className="max-h-[calc(100vh-200px)] overflow-y-auto p-6">
                  {activeTab === 'clip' ? (
                    <EventVideoPlayer eventId={parseInt(event.id, 10)} />
                  ) : activeTab === 'details' ? (
                    <>
                      {/* Media display: Video or Image based on selected detection */}
                  {isVideoDetection && selectedDetectionId ? (
                    <div className="mb-6 overflow-hidden rounded-lg bg-black">
                      <VideoPlayer
                        src={getDetectionVideoUrl(selectedDetectionId)}
                        poster={getDetectionVideoThumbnailUrl(selectedDetectionId)}
                        className="w-full"
                      />
                      {/* Video metadata badge */}
                      <div className="flex items-center gap-3 border-t border-gray-800 bg-black/50 px-4 py-2">
                        <div className="flex items-center gap-1.5 text-xs text-gray-400">
                          <Film className="h-3.5 w-3.5" />
                          <span>Video</span>
                        </div>
                        {selectedDetection?.duration && (
                          <div className="text-xs text-gray-400">
                            <span className="font-medium text-gray-300">
                              {formatVideoDuration(selectedDetection.duration)}
                            </span>
                          </div>
                        )}
                        {formatVideoResolution(
                          selectedDetection?.video_width,
                          selectedDetection?.video_height
                        ) && (
                          <div className="text-xs text-gray-400">
                            <span className="font-medium text-gray-300">
                              {formatVideoResolution(
                                selectedDetection?.video_width,
                                selectedDetection?.video_height
                              )}
                            </span>
                          </div>
                        )}
                        {selectedDetection?.video_codec && (
                          <div className="text-xs text-gray-400">
                            <span className="font-medium text-gray-300">
                              {selectedDetection.video_codec.toUpperCase()}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  ) : imageUrl ? (
                    <div className="mb-6 overflow-hidden rounded-lg bg-black">
                      {hasBoundingBoxes ? (
                        <DetectionImage
                          src={imageUrl}
                          alt={`${event.camera_name} detection at ${formatTimestamp(event.timestamp)}`}
                          boxes={convertToBoundingBoxes()}
                          showLabels={true}
                          showConfidence={true}
                          className="w-full"
                          enableLightbox={true}
                          lightboxCaption={`${event.camera_name} - ${formatTimestamp(event.timestamp)}`}
                        />
                      ) : (
                        <DetectionImage
                          src={imageUrl}
                          alt={`${event.camera_name} at ${formatTimestamp(event.timestamp)}`}
                          boxes={[]}
                          className="w-full"
                          enableLightbox={true}
                          lightboxCaption={`${event.camera_name} - ${formatTimestamp(event.timestamp)}`}
                        />
                      )}
                    </div>
                  ) : null}

                  {/* Detection Sequence Thumbnail Strip */}
                  <div className="mb-6">
                    <ThumbnailStrip
                      detections={detectionSequence}
                      selectedDetectionId={selectedDetectionId}
                      onThumbnailClick={handleThumbnailClick}
                      onThumbnailDoubleClick={handleThumbnailLightbox}
                      loading={loadingDetections}
                    />
                  </div>

                  {/* AI Summary */}
                  <div className="mb-6" data-testid="ai-analysis-section">
                    <div className="mb-2 flex items-center justify-between">
                      <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-400">
                        AI Summary
                      </h3>
                      <button
                        onClick={() => void handleReEvaluate()}
                        disabled={isReEvaluating}
                        className="flex items-center gap-1.5 rounded-md bg-gray-800 px-2.5 py-1 text-xs font-medium text-gray-300 transition-colors hover:bg-gray-700 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
                        aria-label="Re-evaluate AI analysis"
                        data-testid="re-evaluate-button"
                      >
                        <RefreshCw className={`h-3.5 w-3.5 ${isReEvaluating ? 'animate-spin' : ''}`} />
                        {isReEvaluating ? 'Re-evaluating...' : 'Re-evaluate'}
                      </button>
                    </div>
                    {/* Re-evaluate feedback */}
                    {reEvaluateError && (
                      <div className="mb-2 rounded-md bg-red-900/20 px-3 py-2 text-xs text-red-400" data-testid="re-evaluate-error">
                        {reEvaluateError}
                      </div>
                    )}
                    {reEvaluateSuccess && (
                      <div className="mb-2 flex items-center gap-1.5 rounded-md bg-green-900/20 px-3 py-2 text-xs text-green-400" data-testid="re-evaluate-success">
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        Re-evaluation triggered successfully
                      </div>
                    )}
                    <p className="text-base leading-relaxed text-gray-200">{event.summary}</p>
                  </div>

                  {/* AI Reasoning */}
                  {event.reasoning && (
                    <div className="mb-6" data-testid="ai-reasoning">
                      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-400">
                        AI Reasoning
                      </h3>
                      <div className="rounded-lg bg-[#76B900]/10 p-4">
                        <p className="text-sm leading-relaxed text-gray-300">{event.reasoning}</p>
                      </div>
                    </div>
                  )}

                  {/* Detections with Color-Coded Confidence */}
                  {event.detections.length > 0 && (
                    <div className="mb-6" data-testid="detection-objects">
                      <div className="mb-3 flex items-center justify-between">
                        <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-400">
                          Detected Objects ({event.detections.length})
                        </h3>
                        {/* Aggregate Confidence Display */}
                        {event.detections.length > 0 && (
                          <div className="flex items-center gap-3 text-sm">
                            <TrendingUp className="h-4 w-4 text-gray-400" aria-hidden="true" />
                            {calculateAverageConfidence(event.detections) !== null && (
                              <div className="flex items-center gap-1">
                                <span className="text-gray-400">Avg:</span>
                                <span
                                  className={`font-semibold ${getConfidenceTextColorClass(
                                    getConfidenceLevel(
                                      calculateAverageConfidence(event.detections) as number
                                    )
                                  )}`}
                                >
                                  {formatConfidencePercent(
                                    calculateAverageConfidence(event.detections) as number
                                  )}
                                </span>
                              </div>
                            )}
                            {calculateMaxConfidence(event.detections) !== null && (
                              <div className="flex items-center gap-1">
                                <span className="text-gray-400">Max:</span>
                                <span
                                  className={`font-semibold ${getConfidenceTextColorClass(
                                    getConfidenceLevel(
                                      calculateMaxConfidence(event.detections) as number
                                    )
                                  )}`}
                                >
                                  {formatConfidencePercent(
                                    calculateMaxConfidence(event.detections) as number
                                  )}
                                </span>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                      <div className="grid gap-2">
                        {sortDetectionsByConfidence(event.detections).map((detection, index) => {
                          const level = getConfidenceLevel(detection.confidence);
                          const confidenceLabel = getConfidenceLabel(level);
                          return (
                            <div
                              key={`${detection.label}-${index}`}
                              className={`flex items-center justify-between rounded-lg border px-4 py-3 ${getConfidenceBgColorClass(level)} ${getConfidenceBorderColorClass(level)}`}
                              title={`${confidenceLabel}`}
                            >
                              <span className="text-sm font-medium text-white">
                                {detection.label}
                              </span>
                              <div className="flex items-center gap-2">
                                {/* Confidence bar */}
                                <div
                                  className="h-2 w-16 overflow-hidden rounded-full bg-gray-700"
                                  aria-hidden="true"
                                >
                                  <div
                                    className={`h-full rounded-full transition-all duration-300 ${
                                      level === 'low'
                                        ? 'bg-red-500'
                                        : level === 'medium'
                                          ? 'bg-yellow-500'
                                          : 'bg-green-500'
                                    }`}
                                    style={{ width: `${Math.round(detection.confidence * 100)}%` }}
                                  />
                                </div>
                                <span
                                  className={`min-w-[3rem] text-right text-xs font-semibold ${getConfidenceTextColorClass(level)}`}
                                >
                                  {formatConfidence(detection.confidence)}
                                </span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* AI Enrichment Analysis */}
                  {event.detections.some((d) => d.enrichment_data) && (
                    <div className="mb-6">
                      {event.detections
                        .filter((d) => d.enrichment_data)
                        .map((detection, index) => (
                          <EnrichmentPanel
                            key={`enrichment-${index}`}
                            enrichment_data={detection.enrichment_data}
                            className="mb-3"
                          />
                        ))}
                    </div>
                  )}

                  {/* User Notes */}
                  <div className="mb-6">
                    <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-400">
                      Notes
                    </h3>
                    <div className="space-y-3">
                      <textarea
                        value={notesText}
                        onChange={(e) => setNotesText(e.target.value)}
                        placeholder="Add notes about this event..."
                        rows={4}
                        className="w-full rounded-lg border border-gray-700 bg-black/30 px-4 py-3 text-sm text-gray-200 placeholder-gray-500 transition-colors focus:border-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]/20"
                      />
                      <div className="flex items-center justify-between">
                        <button
                          onClick={() => void handleSaveNotes()}
                          disabled={isSavingNotes || !onSaveNotes}
                          className="flex items-center gap-2 rounded-lg bg-[#76B900] px-4 py-2 text-sm font-semibold text-black transition-all hover:bg-[#88d200] active:bg-[#68a000] disabled:cursor-not-allowed disabled:opacity-50"
                          aria-label="Save notes"
                        >
                          <Save className="h-4 w-4" />
                          {isSavingNotes ? 'Saving...' : 'Save Notes'}
                        </button>
                        {notesSaved && (
                          <span className="flex items-center gap-1 text-sm text-green-500">
                            <CheckCircle2 className="h-4 w-4" />
                            Saved
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Event Metadata */}
                  <div className="rounded-lg border border-gray-800 bg-black/20 p-4">
                    <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-400">
                      Event Details
                    </h3>
                    <dl className="grid gap-2 text-sm">
                      <div className="flex justify-between">
                        <dt className="text-gray-400">Event ID</dt>
                        <dd className="font-mono text-gray-300">{event.id}</dd>
                      </div>
                      <div className="flex justify-between">
                        <dt className="text-gray-400">Camera</dt>
                        <dd className="text-gray-300">{event.camera_name}</dd>
                      </div>
                      <div className="flex justify-between">
                        <dt className="text-gray-400">Risk Score</dt>
                        <dd className="text-gray-300">{event.risk_score} / 100</dd>
                      </div>
                      {(event.started_at || event.ended_at !== undefined) && (
                        <div className="flex justify-between">
                          <dt className="text-gray-400">Duration</dt>
                          <dd className="text-gray-300">
                            {formatDuration(
                              event.started_at || event.timestamp,
                              event.ended_at ?? null
                            )}
                          </dd>
                        </div>
                      )}
                      <div className="flex justify-between">
                        <dt className="text-gray-400">Status</dt>
                        <dd className="text-gray-300">
                          {event.reviewed ? (
                            <span className="inline-flex items-center gap-1 text-green-500" data-testid="status-reviewed">
                              <CheckCircle2 className="h-4 w-4" />
                              Reviewed
                            </span>
                          ) : (
                            <span className="text-yellow-500">Pending Review</span>
                          )}
                        </dd>
                      </div>
                      {/* Video metadata in event details */}
                      {isVideoDetection && selectedDetection && (
                        <>
                          <div className="mt-2 border-t border-gray-700 pt-2">
                            <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-primary">
                              <Film className="h-3.5 w-3.5" />
                              <span>Video Details</span>
                            </div>
                          </div>
                          {selectedDetection.duration && (
                            <div className="flex justify-between">
                              <dt className="text-gray-400">Video Duration</dt>
                              <dd className="text-gray-300">
                                {formatVideoDuration(selectedDetection.duration)}
                              </dd>
                            </div>
                          )}
                          {formatVideoResolution(
                            selectedDetection.video_width,
                            selectedDetection.video_height
                          ) && (
                            <div className="flex justify-between">
                              <dt className="text-gray-400">Resolution</dt>
                              <dd className="text-gray-300">
                                {formatVideoResolution(
                                  selectedDetection.video_width,
                                  selectedDetection.video_height
                                )}
                              </dd>
                            </div>
                          )}
                          {selectedDetection.video_codec && (
                            <div className="flex justify-between">
                              <dt className="text-gray-400">Codec</dt>
                              <dd className="text-gray-300">
                                {selectedDetection.video_codec.toUpperCase()}
                              </dd>
                            </div>
                          )}
                        </>
                      )}
                    </dl>
                  </div>
                    </>
                  ) : (
                    <EventAuditDetail eventId={parseInt(event.id, 10)} />
                  )}
                </div>

                {/* Footer actions */}
                <div className="flex items-center justify-between border-t border-gray-800 bg-black/20 p-6">
                  {/* Navigation buttons */}
                  <div className="flex gap-2">
                    {onNavigate && (
                      <>
                        <button
                          onClick={() => onNavigate('prev')}
                          className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-gray-700"
                          aria-label="Previous event"
                        >
                          <ArrowLeft className="h-4 w-4" />
                          Previous
                        </button>
                        <button
                          onClick={() => onNavigate('next')}
                          className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-gray-700"
                          aria-label="Next event"
                        >
                          Next
                          <ArrowRight className="h-4 w-4" />
                        </button>
                      </>
                    )}
                  </div>

                  {/* Action buttons */}
                  <div className="flex items-center gap-2">
                    {/* Flag Event button */}
                    {onFlagEvent && (
                      <button
                        onClick={() => void handleFlagEvent()}
                        disabled={isFlagging}
                        className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition-all disabled:cursor-not-allowed disabled:opacity-50 ${
                          event.flagged
                            ? 'bg-yellow-600 text-white hover:bg-yellow-700 active:bg-yellow-800'
                            : 'bg-gray-800 text-white hover:bg-gray-700 active:bg-gray-900'
                        }`}
                        aria-label={event.flagged ? 'Unflag event' : 'Flag event'}
                      >
                        <Flag className="h-4 w-4" />
                        {isFlagging ? 'Flagging...' : event.flagged ? 'Unflag Event' : 'Flag Event'}
                      </button>
                    )}

                    {/* Download Media button */}
                    {onDownloadMedia && (
                      <button
                        onClick={() => void handleDownloadMedia()}
                        disabled={isDownloading}
                        className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-semibold text-white transition-all hover:bg-gray-700 active:bg-gray-900 disabled:cursor-not-allowed disabled:opacity-50"
                        aria-label="Download media"
                      >
                        <Download className="h-4 w-4" />
                        {isDownloading ? 'Downloading...' : 'Download Media'}
                      </button>
                    )}

                    {/* Mark as reviewed button */}
                    {onMarkReviewed && !event.reviewed && (
                      <button
                        onClick={() => onMarkReviewed(event.id)}
                        className="flex items-center gap-2 rounded-lg bg-[#76B900] px-6 py-2 text-sm font-semibold text-black transition-all hover:bg-[#88d200] active:bg-[#68a000]"
                        aria-label="Mark event as reviewed"
                        data-testid="mark-reviewed"
                      >
                        <CheckCircle2 className="h-4 w-4" />
                        Mark as Reviewed
                      </button>
                    )}
                  </div>
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>

      {/* Lightbox for thumbnail images */}
      {thumbnailLightboxImages.length > 0 && (
        <Lightbox
          images={thumbnailLightboxImages}
          initialIndex={thumbnailLightboxIndex}
          isOpen={thumbnailLightboxOpen}
          onClose={() => setThumbnailLightboxOpen(false)}
          onIndexChange={setThumbnailLightboxIndex}
        />
      )}
    </Transition>
  );
}
