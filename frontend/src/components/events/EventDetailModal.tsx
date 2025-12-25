import { Dialog, Transition } from '@headlessui/react';
import { ArrowLeft, ArrowRight, CheckCircle2, Clock, Download, Flag, Save, Timer, X } from 'lucide-react';
import { Fragment, useEffect, useState } from 'react';

import ThumbnailStrip from './ThumbnailStrip';
import { fetchEventDetections, getDetectionImageUrl } from '../../services/api';
import { getRiskLevel } from '../../utils/risk';
import { formatDuration } from '../../utils/time';
import RiskBadge from '../common/RiskBadge';
import DetectionImage from '../detection/DetectionImage';

import type { DetectionThumbnail } from './ThumbnailStrip';
import type { BoundingBox } from '../detection/BoundingBoxOverlay';

export interface Detection {
  label: string;
  confidence: number;
  bbox?: { x: number; y: number; width: number; height: number };
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
  // State for notes editing
  const [notesText, setNotesText] = useState<string>('');
  const [isSavingNotes, setIsSavingNotes] = useState<boolean>(false);
  const [notesSaved, setNotesSaved] = useState<boolean>(false);

  // State for detection sequence thumbnails
  const [detectionSequence, setDetectionSequence] = useState<DetectionThumbnail[]>([]);
  const [loadingDetections, setLoadingDetections] = useState<boolean>(false);
  const [selectedDetectionId, setSelectedDetectionId] = useState<number | undefined>();

  // State for flag event
  const [isFlagging, setIsFlagging] = useState<boolean>(false);

  // State for download media
  const [isDownloading, setIsDownloading] = useState<boolean>(false);

  // Initialize notes text when event changes
  useEffect(() => {
    if (event) {
      setNotesText(event.notes || '');
      setNotesSaved(false);
    }
  }, [event]);

  // Fetch detection sequence when event changes
  useEffect(() => {
    if (!event || !event.id) {
      setDetectionSequence([]);
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

        // Transform API detections to thumbnail format
        const thumbnails: DetectionThumbnail[] = response.detections.map((detection) => ({
          id: detection.id,
          detected_at: detection.detected_at,
          thumbnail_url: getDetectionImageUrl(detection.id),
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
      } finally {
        setLoadingDetections(false);
      }
    };

    void loadDetections();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- selectedDetectionId intentionally excluded to avoid refetching
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

  // Handle thumbnail click to view specific detection
  const handleThumbnailClick = (detectionId: number) => {
    setSelectedDetectionId(detectionId);
    // TODO: Could add logic to update the main image view to show this specific detection
  };

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

  if (!event) {
    return null;
  }

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
              <Dialog.Panel className="w-full max-w-4xl transform overflow-hidden rounded-xl border border-gray-800 bg-[#1A1A1A] shadow-2xl transition-all">
                {/* Header */}
                <div className="flex items-start justify-between border-b border-gray-800 p-6">
                  <div className="flex-1">
                    <Dialog.Title
                      as="h2"
                      className="text-2xl font-bold text-white"
                      id="event-detail-title"
                    >
                      {event.camera_name}
                    </Dialog.Title>
                    <div className="mt-2 flex flex-col gap-1">
                      <div className="flex items-center gap-2 text-sm text-gray-400">
                        <Clock className="h-4 w-4" />
                        <span>{formatTimestamp(event.timestamp)}</span>
                      </div>
                      {(event.started_at || event.ended_at !== undefined) && (
                        <div className="flex items-center gap-2 text-sm text-gray-400">
                          <Timer className="h-4 w-4" />
                          <span>Duration: {formatDuration(event.started_at || event.timestamp, event.ended_at ?? null)}</span>
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <RiskBadge level={riskLevel} score={event.risk_score} showScore={true} size="lg" />
                    <button
                      onClick={onClose}
                      className="rounded-lg p-2 text-gray-400 transition-colors hover:bg-gray-800 hover:text-white"
                      aria-label="Close modal"
                    >
                      <X className="h-6 w-6" />
                    </button>
                  </div>
                </div>

                {/* Content */}
                <div className="max-h-[calc(100vh-200px)] overflow-y-auto p-6">
                  {/* Full-size image with bounding boxes */}
                  {imageUrl && (
                    <div className="mb-6 overflow-hidden rounded-lg bg-black">
                      {hasBoundingBoxes ? (
                        <DetectionImage
                          src={imageUrl}
                          alt={`${event.camera_name} detection at ${formatTimestamp(event.timestamp)}`}
                          boxes={convertToBoundingBoxes()}
                          showLabels={true}
                          showConfidence={true}
                          className="w-full"
                        />
                      ) : (
                        <img
                          src={imageUrl}
                          alt={`${event.camera_name} at ${formatTimestamp(event.timestamp)}`}
                          className="w-full object-contain"
                        />
                      )}
                    </div>
                  )}

                  {/* Detection Sequence Thumbnail Strip */}
                  <div className="mb-6">
                    <ThumbnailStrip
                      detections={detectionSequence}
                      selectedDetectionId={selectedDetectionId}
                      onThumbnailClick={handleThumbnailClick}
                      loading={loadingDetections}
                    />
                  </div>

                  {/* AI Summary */}
                  <div className="mb-6">
                    <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-400">
                      AI Summary
                    </h3>
                    <p className="text-base leading-relaxed text-gray-200">{event.summary}</p>
                  </div>

                  {/* AI Reasoning */}
                  {event.reasoning && (
                    <div className="mb-6">
                      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-400">
                        AI Reasoning
                      </h3>
                      <div className="rounded-lg bg-[#76B900]/10 p-4">
                        <p className="text-sm leading-relaxed text-gray-300">{event.reasoning}</p>
                      </div>
                    </div>
                  )}

                  {/* Detections */}
                  {event.detections.length > 0 && (
                    <div className="mb-6">
                      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-400">
                        Detected Objects ({event.detections.length})
                      </h3>
                      <div className="grid gap-2">
                        {event.detections.map((detection, index) => (
                          <div
                            key={`${detection.label}-${index}`}
                            className="flex items-center justify-between rounded-lg bg-black/30 px-4 py-3"
                          >
                            <span className="text-sm font-medium text-white">{detection.label}</span>
                            <span className="rounded-full bg-gray-800 px-3 py-1 text-xs font-semibold text-gray-300">
                              {formatConfidence(detection.confidence)}
                            </span>
                          </div>
                        ))}
                      </div>
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
                          <dd className="text-gray-300">{formatDuration(event.started_at || event.timestamp, event.ended_at ?? null)}</dd>
                        </div>
                      )}
                      <div className="flex justify-between">
                        <dt className="text-gray-400">Status</dt>
                        <dd className="text-gray-300">
                          {event.reviewed ? (
                            <span className="inline-flex items-center gap-1 text-green-500">
                              <CheckCircle2 className="h-4 w-4" />
                              Reviewed
                            </span>
                          ) : (
                            <span className="text-yellow-500">Pending Review</span>
                          )}
                        </dd>
                      </div>
                    </dl>
                  </div>
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
    </Transition>
  );
}
