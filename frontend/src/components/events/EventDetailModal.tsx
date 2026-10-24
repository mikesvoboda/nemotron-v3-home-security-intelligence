import { Dialog, Transition } from '@headlessui/react';
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Clock,
  Download,
  Eye,
  Film,
  Printer,
  RefreshCw,
  Save,
  Timer,
  TrendingUp,
  UserPlus,
  X,
} from 'lucide-react';
import { Fragment, useEffect, useMemo, useState } from 'react';

// R2a row 32 (F-068) retired
import ConfidenceIndicators from './ConfidenceIndicators';
import DetectionQualityBadge from './DetectionQualityBadge';
import EntityTrackingPanel from './EntityTrackingPanel';
import EventVerificationSection from './EventVerificationSection';
import EventVideoPlayer from './EventVideoPlayer';
import LLMReasoningExplorer from './LLMReasoningExplorer';
import MatchedEntitiesSection from './MatchedEntitiesSection';
import ReidMatchesPanel from './ReidMatchesPanel';
import RiskFactorsBreakdown from './RiskFactorsBreakdown';
import RiskFactorsList from './RiskFactorsList';
import ThumbnailStrip from './ThumbnailStrip';
import { useEventDetectionsQuery } from '../../hooks/useEventDetectionsQuery';
import {
  fetchEntity,
  getDetectionFullImageUrl,
  getDetectionImageUrl,
  getDetectionVideoThumbnailUrl,
  getDetectionVideoUrl,
} from '../../services/api';
import { triggerEvaluation, AuditApiError } from '../../services/auditApi';
import { THREAT_CLASSES } from '../../types/threat';
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
import AdvancedOnly from '../common/AdvancedOnly';
import IconButton from '../common/IconButton';
import Lightbox from '../common/Lightbox';
import NotifyBadge from '../common/NotifyBadge';
import RiskBadge from '../common/RiskBadge';
import SnoozeBadge from '../common/SnoozeBadge';
import SnoozeButton from '../common/SnoozeButton';
import VerdictBadge from '../common/VerdictBadge';
import DetectionImage from '../detection/DetectionImage';
import EntityDetailModal from '../entities/EntityDetailModal';
import EnrollFaceModal from '../face-recognition/EnrollFaceModal';
import FeedbackPanel from '../feedback/FeedbackPanel';
import VideoPlayer from '../video/VideoPlayer';

import type { DetectionThumbnail } from './ThumbnailStrip';
import type { EntityDetail } from '../../services/api';
import type { EventVerificationPayload } from '../../types/generated/websocket';
import type {
  RiskEntity,
  RiskFactor,
  RiskFlag,
  ConfidenceFactors,
} from '../../types/risk-analysis';
import type { LightboxImage } from '../common/Lightbox';
import type { BoundingBox } from '../detection/BoundingBoxOverlay';

/**
 * Weapon classes draw red in the overlay (F4.4): the colour the retired
 * threats-only box component used for high-priority threats, carried onto the
 * shared detection/BoundingBoxOverlay. Tailwind red-500.
 */
const WEAPON_BOX_COLOUR = '#ef4444';

/** Threat classes from the shared vocabulary - a weapon box is red. */

/**
 * A detection as the modal displays it: the label, its confidence, and the
 * bounding box in the original image's pixels. Filled from the modal's own
 * fetch of GET /api/events/{id}/detections (F4.4) - the event list payload
 * carries no detections, so the list and overlay read this, not the event.
 */
export interface Detection {
  label: string;
  confidence: number;
  bbox?: { x: number; y: number; width: number; height: number };
}

export interface Event {
  id: string;
  timestamp: string;
  camera_id?: string;
  camera_name: string;
  /** Null = no verdict/level yet (1.6, D11) - the modal shows Unverified. */
  risk_score: number | null;
  /** Display label; optional. */
  risk_label?: string;
  /** VLM verdict from the event's verification row (1.6, spec §4). */
  verdict?: EventVerificationPayload['verdict'] | null;
  /**
   * Persisted notify decision (ISS-001). true/false is a decision on the
   * record (the badge renders it); undefined/null means NO DECISION and
   * renders nothing - absence is not False (the `verification` contract).
   */
  notify?: boolean | null;
  /**
   * The full verification row (1.6, spec §4 "Event detail"): scene
   * description, criteria checklist, reviewed frames. Undefined = no row
   * (legacy events) and the verification section renders nothing.
   */
  verification?: EventVerificationPayload | null;
  summary: string;
  reasoning?: string;
  image_url?: string;
  thumbnail_url?: string;
  started_at?: string;
  ended_at?: string | null;
  reviewed?: boolean;
  notes?: string | null;
  entity_id?: string | null;
  /** Florence-2 generated scene caption describing the overall scene */
  scene_caption?: string | null;
  /** ISO timestamp until which alerts for this event are snoozed (NEM-3640) */
  snooze_until?: string | null;
  /** Optimistic locking version (NEM-3625). Include in updates to prevent conflicts. */
  version?: number;
  /** Advanced risk analysis fields (NEM-3601) */
  entities?: RiskEntity[] | null;
  flags?: RiskFlag[] | null;
  recommended_action?: string | null;
  confidence_factors?: ConfidenceFactors | null;
  /** Individual factors contributing to risk score (NEM-3603) */
  risk_factors?: RiskFactor[] | null;
}

export interface EventDetailModalProps {
  event: Event | null;
  isOpen: boolean;
  onClose: () => void;
  onMarkReviewed?: (eventId: string) => void;
  onNavigate?: (direction: 'prev' | 'next') => void;
  onSaveNotes?: (eventId: string, notes: string) => Promise<void>;
  onDownloadMedia?: (eventId: string) => Promise<void>;
  /** Callback to snooze the event for a duration in seconds (NEM-3640) */
  onSnooze?: (eventId: string, seconds: number) => void;
  /** Callback to clear the snooze on the event (NEM-3640) */
  onUnsnooze?: (eventId: string) => void;
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
  onDownloadMedia,
  onSnooze,
  onUnsnooze,
}: EventDetailModalProps) {
  // State for active tab (Details vs AI Analysis vs AI Audit vs Video Clip)
  const [activeTab, setActiveTab] = useState<'details' | 'analysis' | 'audit' | 'clip'>('details');

  // State for notes editing
  const [notesText, setNotesText] = useState<string>('');
  const [isSavingNotes, setIsSavingNotes] = useState<boolean>(false);
  const [notesSaved, setNotesSaved] = useState<boolean>(false);

  // State for selected detection in thumbnail strip
  const [selectedDetectionId, setSelectedDetectionId] = useState<number | undefined>();

  // State for download media
  const [isDownloading, setIsDownloading] = useState<boolean>(false);

  // State for thumbnail lightbox
  const [thumbnailLightboxOpen, setThumbnailLightboxOpen] = useState<boolean>(false);
  const [thumbnailLightboxIndex, setThumbnailLightboxIndex] = useState<number>(0);

  // State for re-evaluate AI analysis
  const [isReEvaluating, setIsReEvaluating] = useState<boolean>(false);
  const [reEvaluateError, setReEvaluateError] = useState<string | null>(null);
  const [reEvaluateSuccess, setReEvaluateSuccess] = useState<boolean>(false);

  // State for entity detail modal
  const [entityDetailOpen, setEntityDetailOpen] = useState<boolean>(false);
  const [selectedEntity, setSelectedEntity] = useState<EntityDetail | null>(null);

  // State for face enrollment modal
  const [enrollFaceModalOpen, setEnrollFaceModalOpen] = useState<boolean>(false);

  // Parse event ID for API calls
  const eventIdNumber = event ? parseInt(event.id, 10) : NaN;

  // Query for event detections (uses React Query for caching and deduplication)
  const { detections: detectionsData, isLoading: loadingDetections } = useEventDetectionsQuery({
    eventId: eventIdNumber,
    limit: 100,
    enabled: !isNaN(eventIdNumber) && isOpen,
    staleTime: 30000, // 30 seconds
  });

  // Transform detections to thumbnail format (memoized for performance)
  const detectionSequence = useMemo((): DetectionThumbnail[] => {
    if (!detectionsData || detectionsData.length === 0) {
      return [];
    }
    return detectionsData.map((detection) => ({
      id: detection.id,
      detected_at: detection.detected_at,
      thumbnail_url:
        detection.media_type === 'video'
          ? getDetectionVideoThumbnailUrl(detection.id)
          : getDetectionImageUrl(detection.id),
      object_type: detection.object_type || undefined,
      confidence: detection.confidence || undefined,
    }));
  }, [detectionsData]);

  // Initialize notes text, reset re-evaluate state, and reset selection when event changes
  useEffect(() => {
    if (event) {
      setNotesText(event.notes || '');
      setNotesSaved(false);
      setReEvaluateError(null);
      setReEvaluateSuccess(false);
      // Reset selected detection when switching events
      setSelectedDetectionId(undefined);
    }
  }, [event]);

  // Auto-select first detection when detections load
  useEffect(() => {
    if (detectionSequence.length > 0 && selectedDetectionId === undefined) {
      setSelectedDetectionId(detectionSequence[0].id);
    }
  }, [detectionSequence, selectedDetectionId]);

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
  // Updates selectedDetectionId which triggers re-render of main display area
  // The main display uses selectedDetection to determine if showing video or image
  const handleThumbnailClick = (detectionId: number) => {
    setSelectedDetectionId(detectionId);
  };

  // Handle thumbnail double-click to open lightbox for full-size view
  const handleThumbnailLightbox = (detectionId: number) => {
    const index = detectionSequence.findIndex((d) => d.id === detectionId);
    if (index !== -1) {
      setThumbnailLightboxIndex(index);
      setThumbnailLightboxOpen(true);
    }
  };

  // Handle matched entity click to open EntityDetailModal
  const handleMatchedEntityClick = async (entityId: string) => {
    try {
      const entity = await fetchEntity(entityId);
      setSelectedEntity(entity);
      setEntityDetailOpen(true);
    } catch (error) {
      console.error('Failed to fetch entity details:', error);
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

  // Determine if selected detection has a person (for face enrollment)
  // A "person" detection can potentially have a face to enroll
  const hasPersonDetection = useMemo(() => {
    if (!selectedDetection) return false;
    const objectType = selectedDetection.object_type?.toLowerCase() ?? '';
    return objectType === 'person' || objectType.includes('person') || objectType === 'face';
  }, [selectedDetection]);

  // The detections the modal displays, from its own fetch (F4.4): the wire
  // event carries no detections, so the detected-objects list and the
  // overlay are driven by this, not by the event prop.
  const modalDetections = useMemo((): Detection[] => {
    return (detectionsData ?? []).map((d) => ({
      label: d.object_type || 'object',
      confidence: d.confidence ?? 0,
      bbox:
        d.bbox_x !== null &&
        d.bbox_x !== undefined &&
        d.bbox_y !== null &&
        d.bbox_y !== undefined &&
        d.bbox_width !== null &&
        d.bbox_width !== undefined &&
        d.bbox_height !== null &&
        d.bbox_height !== undefined
          ? { x: d.bbox_x, y: d.bbox_y, width: d.bbox_width, height: d.bbox_height }
          : undefined,
    }));
  }, [detectionsData]);

  // Boxes for the selected still image (F4.4): a box lives in the pixels of
  // the file it was drawn on, so the overlay shows every IMAGE detection from
  // the same file_path as the selected detection. A video detection keeps no
  // frame to draw on - it plays in the video player with no box.
  const boxesForSelectedImage = useMemo((): BoundingBox[] => {
    if (!selectedDetection || selectedDetection.media_type === 'video') return [];
    const filePath = selectedDetection.file_path;
    return detectionsData
      .filter(
        (d) =>
          d.file_path === filePath &&
          d.media_type !== 'video' &&
          d.bbox_x !== null &&
          d.bbox_x !== undefined &&
          d.bbox_y !== null &&
          d.bbox_y !== undefined &&
          d.bbox_width !== null &&
          d.bbox_width !== undefined &&
          d.bbox_height !== null &&
          d.bbox_height !== undefined
      )
      .map((d): BoundingBox => ({
        x: d.bbox_x as number,
        y: d.bbox_y as number,
        width: d.bbox_width as number,
        height: d.bbox_height as number,
        label: d.object_type || 'object',
        confidence: d.confidence ?? 0,
        // A weapon draws red regardless of the class palette (F4.4): the
        // threat colour the retired threats-only box component used, carried
        // onto the same-kind overlay.
        ...(THREAT_CLASSES.has((d.object_type || '').toLowerCase()) && {
          color: WEAPON_BOX_COLOUR,
        }),
      }));
  }, [selectedDetection, detectionsData]);

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

  // Risk level, or null when the event has none to show (1.6, D11). The
  // header then shows the verdict (or Unverified) instead of a RiskBadge,
  // and the score readout says "Not analyzed" instead of "0 / 100".
  const riskLevel = event.risk_score === null ? null : getRiskLevel(event.risk_score);
  // RiskBadge's score prop is `number | undefined` (omits it from the
  // aria-label when absent) - map the nullable event score once, here.
  const riskScoreForBadge = event.risk_score ?? undefined;

  // Format confidence as percentage
  const formatConfidence = (confidence: number): string => {
    return `${Math.round(confidence * 100)}%`;
  };

  // Use full-size image if available, otherwise fallback to thumbnail
  const imageUrl = event.image_url || event.thumbnail_url;

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
              <Dialog.Panel
                className="w-full max-w-lg transform overflow-hidden rounded-xl border border-gray-800 bg-[#1A1A1A] shadow-2xl transition-all sm:max-w-2xl lg:max-w-4xl"
                data-testid="event-detail-modal"
              >
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
                      <div
                        className="flex items-center gap-2 text-sm text-gray-400"
                        data-testid="detection-timestamp"
                      >
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
                    {/* Snooze Status Badge (NEM-3640) */}
                    <SnoozeBadge snoozeUntil={event.snooze_until} size="md" showEndTime={true} />
                    {/* ISS-001: the notify decision belongs to the detail
                        surface at md size. Renders NOTHING when no decision
                        exists (absence is not a decision not to page). */}
                    <NotifyBadge notify={event.notify} size="md" />
                    <div data-testid="risk-score">
                      {riskLevel !== null ? (
                        <RiskBadge
                          level={riskLevel}
                          score={riskScoreForBadge}
                          showScore={true}
                          size="lg"
                        />
                      ) : (
                        <VerdictBadge
                          verdict={event.verification?.verdict ?? event.verdict ?? 'none'}
                          size="md"
                        />
                      )}
                    </div>
                    {riskLevel !== null && (
                      <VerdictBadge
                        verdict={event.verification?.verdict ?? event.verdict ?? 'none'}
                        size="md"
                      />
                    )}
                    <IconButton
                      icon={<X />}
                      aria-label="Close modal"
                      onClick={onClose}
                      variant="ghost"
                      size="lg"
                      data-testid="close-modal-button"
                    />
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
                  <AdvancedOnly>
                    <button
                      onClick={() => setActiveTab('analysis')}
                      className={`px-4 py-3 text-sm font-medium transition-colors ${
                        activeTab === 'analysis'
                          ? 'border-b-2 border-[#76B900] text-[#76B900]'
                          : 'text-gray-400 hover:text-gray-200'
                      }`}
                      data-testid="ai-analysis-tab"
                    >
                      AI Analysis
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
                  </AdvancedOnly>
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
                  ) : activeTab === 'analysis' ? (
                    /* AI Analysis Tab - LLM Reasoning */
                    <div className="space-y-6" data-testid="ai-analysis-tab-content">
                      {/* LLM Reasoning Explorer - Shows <think> blocks, risk factors, enrichment sources */}
                      {!isNaN(eventIdNumber) && (
                        <LLMReasoningExplorer eventId={eventIdNumber} defaultExpanded={true} />
                      )}
                    </div>
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
                      ) : selectedDetectionId && selectedDetection ? (
                        // Show selected detection's image when a detection thumbnail is clicked
                        <div className="mb-6 overflow-hidden rounded-lg bg-black">
                          <DetectionImage
                            src={getDetectionFullImageUrl(selectedDetectionId)}
                            alt={`${selectedDetection.object_type || 'Detection'} at ${formatTimestamp(selectedDetection.detected_at)}`}
                            boxes={boxesForSelectedImage}
                            className="w-full"
                            enableLightbox={true}
                            lightboxCaption={`${event.camera_name} - ${selectedDetection.object_type || 'Detection'}${selectedDetection.confidence ? ` (${Math.round(selectedDetection.confidence * 100)}%)` : ''}`}
                          />
                        </div>
                      ) : imageUrl ? (
                        // Fallback to event's main image when no detection is selected.
                        // Never gets boxes (F4.4): the fallback thumbnail has no
                        // selected detection, so there is no file_path to match
                        // boxes against - only the selected-detection still does.
                        <div className="mb-6 overflow-hidden rounded-lg bg-black">
                          <DetectionImage
                            src={imageUrl}
                            alt={`${event.camera_name} at ${formatTimestamp(event.timestamp)}`}
                            boxes={[]}
                            className="w-full"
                            enableLightbox={true}
                            lightboxCaption={`${event.camera_name} - ${formatTimestamp(event.timestamp)}`}
                          />
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

                      {/* Add Face to Known Persons Button (NEM-4688 Phase 4) */}
                      {hasPersonDetection && selectedDetectionId && (
                        <div className="mb-6">
                          <button
                            onClick={() => setEnrollFaceModalOpen(true)}
                            className="flex items-center gap-2 rounded-lg border border-[#76B900]/40 bg-[#76B900]/10 px-4 py-2.5 text-sm font-medium text-[#76B900] transition-colors hover:bg-[#76B900]/20"
                            data-testid="enroll-face-button"
                          >
                            <UserPlus className="h-4 w-4" />
                            Add Face to Known Persons
                          </button>
                        </div>
                      )}

                      {/* AI Summary */}
                      <div className="mb-6" data-testid="ai-analysis-section">
                        <div className="mb-2 flex items-center justify-between">
                          <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-400">
                            AI Summary
                          </h3>
                          <AdvancedOnly>
                            <button
                              onClick={() => void handleReEvaluate()}
                              disabled={isReEvaluating}
                              className="flex items-center gap-1.5 rounded-md bg-gray-800 px-2.5 py-1 text-xs font-medium text-gray-300 transition-colors hover:bg-gray-700 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
                              aria-label="Re-evaluate AI analysis"
                              data-testid="re-evaluate-button"
                            >
                              <RefreshCw
                                className={`h-3.5 w-3.5 ${isReEvaluating ? 'animate-spin' : ''}`}
                              />
                              {isReEvaluating ? 'Re-evaluating...' : 'Re-evaluate'}
                            </button>
                          </AdvancedOnly>
                        </div>
                        {/* Re-evaluate feedback */}
                        <AdvancedOnly>
                          {reEvaluateError && (
                            <div
                              className="mb-2 rounded-md bg-red-900/20 px-3 py-2 text-xs text-red-400"
                              data-testid="re-evaluate-error"
                            >
                              {reEvaluateError}
                            </div>
                          )}
                          {reEvaluateSuccess && (
                            <div
                              className="mb-2 flex items-center gap-1.5 rounded-md bg-green-900/20 px-3 py-2 text-xs text-green-400"
                              data-testid="re-evaluate-success"
                            >
                              <CheckCircle2 className="h-3.5 w-3.5" />
                              Re-evaluation triggered successfully
                            </div>
                          )}
                        </AdvancedOnly>
                        <p className="text-base leading-relaxed text-gray-200">{event.summary}</p>
                      </div>

                      {/* AI Scene Description (Florence-2 Caption) - Advanced only (F4.9) */}
                      <AdvancedOnly>
                        {event.scene_caption && (
                          <div className="mb-6" data-testid="scene-caption-section">
                            <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-gray-400">
                              <Eye className="h-4 w-4" aria-hidden="true" />
                              AI Scene Description
                            </h3>
                            <div className="rounded-lg border border-gray-700 bg-black/20 p-4">
                              <p
                                className="text-sm italic leading-relaxed text-gray-300"
                                data-testid="scene-caption-text"
                              >
                                {event.scene_caption}
                              </p>
                            </div>
                          </div>
                        )}
                      </AdvancedOnly>

                      {/* Risk Factors Breakdown (NEM-3671) - Advanced only (F4.9) */}
                      <AdvancedOnly>
                        {event.risk_score !== null && (
                          <RiskFactorsBreakdown
                            riskScore={event.risk_score}
                            reasoning={event.reasoning}
                            entities={event.entities}
                            flags={event.flags}
                            recommendedAction={event.recommended_action}
                            confidenceFactors={event.confidence_factors}
                            isReviewed={event.reviewed}
                            className="mb-6"
                          />
                        )}
                      </AdvancedOnly>

                      {/* VLM verification (1.6, spec §4): scene, criteria, frames - Advanced only (F4.9 MO2) */}
                      <AdvancedOnly>
                        <EventVerificationSection
                          verification={event.verification}
                          className="mb-6"
                        />
                      </AdvancedOnly>

                      {/* Risk Factors List (NEM-3603) */}
                      {event.risk_factors && event.risk_factors.length > 0 && (
                        <div className="mb-6" data-testid="risk-factors-section">
                          <RiskFactorsList riskFactors={event.risk_factors} />
                        </div>
                      )}

                      {/* Risk Score Confidence Indicators (NEM-3606) - Advanced only (F4.9 MO1) */}
                      <AdvancedOnly>
                        {event.confidence_factors && (
                          <div className="mb-6" data-testid="confidence-indicators-section">
                            <ConfidenceIndicators
                              confidenceFactors={event.confidence_factors}
                              mode="detailed"
                            />
                          </div>
                        )}
                      </AdvancedOnly>

                      {/* Detections with Color-Coded Confidence - from the
                          modal's own fetch (F4.4), not the event prop (the
                          wire event carries none) */}
                      {modalDetections.length > 0 && (
                        <div className="mb-6" data-testid="detection-objects">
                          <div className="mb-3 flex items-center justify-between">
                            <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-400">
                              Detected Objects ({modalDetections.length})
                            </h3>
                            {/* Aggregate Confidence Display */}
                            {modalDetections.length > 0 && (
                              <div className="flex items-center gap-3 text-sm">
                                <TrendingUp className="h-4 w-4 text-gray-400" aria-hidden="true" />
                                {calculateAverageConfidence(modalDetections) !== null && (
                                  <div className="flex items-center gap-1">
                                    <span className="text-gray-400">Avg:</span>
                                    <span
                                      className={`font-semibold ${getConfidenceTextColorClass(
                                        getConfidenceLevel(
                                          calculateAverageConfidence(modalDetections) as number
                                        )
                                      )}`}
                                    >
                                      {formatConfidencePercent(
                                        calculateAverageConfidence(modalDetections) as number
                                      )}
                                    </span>
                                  </div>
                                )}
                                {calculateMaxConfidence(modalDetections) !== null && (
                                  <div className="flex items-center gap-1">
                                    <span className="text-gray-400">Max:</span>
                                    <span
                                      className={`font-semibold ${getConfidenceTextColorClass(
                                        getConfidenceLevel(
                                          calculateMaxConfidence(modalDetections) as number
                                        )
                                      )}`}
                                    >
                                      {formatConfidencePercent(
                                        calculateMaxConfidence(modalDetections) as number
                                      )}
                                    </span>
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                          <div className="grid gap-2">
                            {sortDetectionsByConfidence(modalDetections).map((detection, index) => {
                              const level = getConfidenceLevel(detection.confidence);
                              const confidenceLabel = getConfidenceLabel(level);
                              return (
                                <div
                                  key={`${detection.label}-${index}`}
                                  className={`flex items-center justify-between rounded-lg border px-4 py-3 ${getConfidenceBgColorClass(level)} ${getConfidenceBorderColorClass(level)}`}
                                  title={`${confidenceLabel}`}
                                >
                                  <div className="flex items-center gap-2">
                                    <span className="text-sm font-medium text-white">
                                      {detection.label}
                                    </span>
                                    <DetectionQualityBadge
                                      confidence={detection.confidence}
                                      size="sm"
                                    />
                                  </div>
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
                                        style={{
                                          width: `${Math.round(detection.confidence * 100)}%`,
                                        }}
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

                      {/* R2a row 32 (F-068) retired
                       *
                       *
                       *
                       *
                       *
                       *
                       *
                       *
                       *
                       */}

                      {/* Re-Identification Matches - Advanced only (F4.9) */}
                      <AdvancedOnly>
                        {selectedDetectionId && (
                          <div className="mb-6">
                            <ReidMatchesPanel
                              detectionId={selectedDetectionId}
                              entityType={
                                modalDetections.some(
                                  (d) =>
                                    d.label.toLowerCase().includes('vehicle') ||
                                    d.label.toLowerCase().includes('car') ||
                                    d.label.toLowerCase().includes('truck')
                                )
                                  ? 'vehicle'
                                  : 'person'
                              }
                            />
                          </div>
                        )}

                        {/* Cross-Camera Entity Tracking */}
                        {event.entity_id && (
                          <div className="mb-6">
                            <EntityTrackingPanel
                              entityId={event.entity_id}
                              currentCameraId={event.camera_id || event.camera_name}
                              currentTimestamp={event.timestamp}
                            />
                          </div>
                        )}

                        {/* Matched Entities (Re-ID Matches) */}
                        {!isNaN(eventIdNumber) && (
                          <MatchedEntitiesSection
                            eventId={eventIdNumber}
                            onEntityClick={(entityId) => void handleMatchedEntityClick(entityId)}
                          />
                        )}
                      </AdvancedOnly>

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

                      {/* Event Feedback - FeedbackPanel handles all feedback state internally (NEM-4928) */}
                      {!isNaN(eventIdNumber) && (
                        <FeedbackPanel
                          eventId={eventIdNumber}
                          currentRiskScore={riskScoreForBadge}
                          className="mb-6"
                        />
                      )}

                      {/* Event Metadata */}
                      <div className="rounded-lg border border-gray-800 bg-black/20 p-4">
                        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-400">
                          Event Details
                        </h3>
                        <dl className="grid gap-2 text-sm">
                          <AdvancedOnly>
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
                              <dd className="text-gray-300">
                                {event.risk_score === null
                                  ? 'Not analyzed'
                                  : `${event.risk_score} / 100`}
                              </dd>
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
                          </AdvancedOnly>
                          <div className="flex justify-between">
                            <dt className="text-gray-400">Status</dt>
                            <dd className="text-gray-300">
                              {event.reviewed ? (
                                <span
                                  className="inline-flex items-center gap-1 text-green-500"
                                  data-testid="status-reviewed"
                                >
                                  <CheckCircle2 className="h-4 w-4" />
                                  Reviewed
                                </span>
                              ) : (
                                <span className="text-yellow-500">Pending Review</span>
                              )}
                            </dd>
                          </div>
                          <AdvancedOnly>
                            {/* Version indicator for optimistic locking (NEM-3625) */}
                            {event.version !== undefined && (
                              <div className="flex justify-between" data-testid="event-version">
                                <dt className="text-gray-400">Revision</dt>
                                <dd className="font-mono text-gray-500">Rev. {event.version}</dd>
                              </div>
                            )}
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
                          </AdvancedOnly>
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
                    {/* Snooze Button (NEM-3640) */}
                    {onSnooze && onUnsnooze && (
                      <SnoozeButton
                        snoozeUntil={event.snooze_until}
                        onSnooze={(seconds) => onSnooze(event.id, seconds)}
                        onUnsnooze={() => onUnsnooze(event.id)}
                        size="md"
                        data-testid="snooze-button"
                      />
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

                    {/* Print Event Report button */}
                    <button
                      onClick={() => window.print()}
                      className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-semibold text-white transition-all hover:bg-gray-700 active:bg-gray-900"
                      aria-label="Print event report"
                      data-testid="print-event-button"
                    >
                      <Printer className="h-4 w-4" />
                      Print
                    </button>

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

      {/* Entity Detail Modal */}
      <EntityDetailModal
        entity={selectedEntity}
        isOpen={entityDetailOpen}
        onClose={() => {
          setEntityDetailOpen(false);
          setSelectedEntity(null);
        }}
      />

      {/* Face Enrollment Modal (NEM-4688 Phase 4) */}
      {selectedDetectionId && selectedDetection && (
        <EnrollFaceModal
          isOpen={enrollFaceModalOpen}
          onClose={() => setEnrollFaceModalOpen(false)}
          detectionId={String(selectedDetectionId)}
          facePreviewUrl={getDetectionFullImageUrl(selectedDetectionId)}
          qualityScore={selectedDetection.confidence ?? 0.85}
          cameraName={event?.camera_name ?? 'Unknown'}
          timestamp={selectedDetection.detected_at}
        />
      )}
    </Transition>
  );
}
