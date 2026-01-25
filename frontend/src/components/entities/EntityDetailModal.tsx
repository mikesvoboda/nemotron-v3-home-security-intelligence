import { Dialog, Transition } from '@headlessui/react';
import {
  Calendar,
  Camera,
  Car,
  ChevronLeft,
  ChevronRight,
  Clock,
  Eye,
  ExternalLink,
  Image,
  Loader2,
  User,
  X,
} from 'lucide-react';
import { Fragment, useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import EntityTimeline from './EntityTimeline';
import TrustClassificationControls from './TrustClassificationControls';
import { useEntityHistory } from '../../hooks/useEntityHistory';
import { getDetectionImageUrl, getDetectionFullImageUrl } from '../../services/api';
import IconButton from '../common/IconButton';
import Lightbox from '../common/Lightbox';
import DetectionImage from '../detection/DetectionImage';

import type { EntityDetail, TrustStatus as ApiTrustStatus } from '../../services/api';
import type { LightboxImage } from '../common/Lightbox';

/**
 * Trust status for an entity, indicating whether they are known/trusted
 * Maps to API TrustStatus: 'trusted' | 'untrusted' | 'unclassified'
 * Legacy values 'unknown' and 'flagged' are mapped for backward compatibility
 */
export type TrustStatus = ApiTrustStatus | 'unknown' | 'flagged';

/**
 * Normalize trust status from various sources to the canonical API values.
 * Handles legacy values like 'unknown' -> 'unclassified', 'flagged' -> 'untrusted', 'suspicious' -> 'untrusted'
 */
function normalizeTrustStatus(status: TrustStatus | null | undefined): ApiTrustStatus {
  if (!status) return 'unclassified';
  switch (status) {
    case 'trusted':
      return 'trusted';
    case 'untrusted':
    case 'flagged':
      return 'untrusted';
    case 'unknown':
    case 'unclassified':
    default:
      return 'unclassified';
  }
}

export interface EntityDetailModalProps {
  entity: EntityDetail | null;
  isOpen: boolean;
  onClose: () => void;
  /** Optional: Trust status for the entity (default: 'unclassified') */
  trustStatus?: TrustStatus | null;
  /** Optional: Callback when trust status is changed - uses API TrustStatus type */
  onTrustStatusChange?: (entityId: string, status: ApiTrustStatus) => void;
  /** Optional: Whether a trust update is currently in progress */
  isTrustUpdating?: boolean;
}

/**
 * EntityDetailModal displays full entity details in a modal overlay,
 * including the appearance timeline across cameras and detection visualization
 * with bounding box overlays.
 */
export default function EntityDetailModal({
  entity,
  isOpen,
  onClose,
  trustStatus = 'unclassified',
  onTrustStatusChange,
  isTrustUpdating = false,
}: EntityDetailModalProps) {
  const navigate = useNavigate();

  // State for selected detection visualization
  const [selectedDetectionIndex, setSelectedDetectionIndex] = useState<number>(0);
  const [lightboxOpen, setLightboxOpen] = useState(false);

  // Normalize the trust status to API-compatible value
  const normalizedTrustStatus = normalizeTrustStatus(trustStatus);

  // Fetch entity detections with pagination
  const {
    detections: detectionsResponse,
    isLoadingDetections,
    fetchMoreDetections,
    hasMoreDetections,
    isFetchingMoreDetections,
  } = useEntityHistory(entity?.id, { enabled: isOpen && !!entity });

  // Get the list of detections
  const detections = useMemo(
    () => detectionsResponse?.detections ?? [],
    [detectionsResponse?.detections]
  );

  // Reset selection when entity changes
  useEffect(() => {
    setSelectedDetectionIndex(0);
  }, [entity?.id]);

  // Currently selected detection
  const selectedDetection = useMemo(
    () => (detections.length > 0 ? detections[selectedDetectionIndex] : null),
    [detections, selectedDetectionIndex]
  );

  // Build lightbox images from detections
  const lightboxImages = useMemo((): LightboxImage[] => {
    return detections.map((detection) => ({
      src: getDetectionFullImageUrl(detection.detection_id),
      alt: `${detection.object_type || 'Detection'} at ${detection.camera_name || detection.camera_id}`,
      caption: detection.object_type
        ? `${detection.object_type} - ${detection.camera_name || detection.camera_id}`
        : undefined,
    }));
  }, [detections]);

  // Handle detection navigation
  const handlePrevDetection = useCallback(() => {
    setSelectedDetectionIndex((prev) => Math.max(0, prev - 1));
  }, []);

  const handleNextDetection = useCallback(() => {
    setSelectedDetectionIndex((prev) => {
      const nextIndex = prev + 1;
      // Load more if approaching the end
      if (nextIndex >= detections.length - 2 && hasMoreDetections && !isFetchingMoreDetections) {
        fetchMoreDetections();
      }
      return Math.min(detections.length - 1, nextIndex);
    });
  }, [detections.length, hasMoreDetections, isFetchingMoreDetections, fetchMoreDetections]);

  // Open lightbox at current selection
  const handleOpenLightbox = useCallback(() => {
    setLightboxOpen(true);
  }, []);

  // Handle trust status change - Promise-returning wrapper for TrustClassificationControls
  const handleTrustStatusChange = useCallback(
    async (entityId: string, newStatus: ApiTrustStatus): Promise<void> => {
      if (onTrustStatusChange) {
        await Promise.resolve(onTrustStatusChange(entityId, newStatus));
      }
    },
    [onTrustStatusChange]
  );

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

  // Format confidence as percentage
  const formatConfidence = (confidence: number | null | undefined): string => {
    if (confidence === null || confidence === undefined) return 'N/A';
    return `${Math.round(confidence * 100)}%`;
  };

  // Handle "View Events" navigation - opens timeline filtered by entity's cameras and time range
  const handleViewEvents = useCallback(() => {
    if (!entity) return;

    // Build URL parameters for the timeline
    const params = new URLSearchParams();

    // Set date range based on entity's first_seen and last_seen
    // Add a small buffer to ensure events are captured
    if (entity.first_seen) {
      const startDate = new Date(entity.first_seen);
      startDate.setHours(0, 0, 0, 0); // Start of the day
      params.set('start_date', startDate.toISOString().split('T')[0]);
    }

    if (entity.last_seen) {
      const endDate = new Date(entity.last_seen);
      endDate.setHours(23, 59, 59, 999); // End of the day
      params.set('end_date', endDate.toISOString().split('T')[0]);
    }

    // Filter by object type based on entity type
    if (entity.entity_type === 'person') {
      params.set('object_type', 'person');
    } else if (entity.entity_type === 'vehicle') {
      params.set('object_type', 'vehicle');
    }

    // If entity was only seen on one camera, filter by that camera
    if (entity.cameras_seen && entity.cameras_seen.length === 1) {
      params.set('camera_id', entity.cameras_seen[0]);
    }

    // Close modal and navigate to timeline
    onClose();
    void navigate(`/timeline?${params.toString()}`);
  }, [entity, onClose, navigate]);

  if (!entity) {
    return null;
  }

  // Get entity type display label
  const entityTypeLabel = entity.entity_type === 'person' ? 'Person' : 'Vehicle';

  return (
    <>
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
                  className="w-full max-w-3xl transform overflow-hidden rounded-xl border border-gray-800 bg-[#1A1A1A] shadow-2xl transition-all"
                  data-testid="entity-detail-modal"
                >
                  {/* Header */}
                  <div className="flex items-start justify-between border-b border-gray-800 p-6">
                    <div className="flex items-center gap-4">
                      {/* Entity thumbnail or icon */}
                      <div className="flex h-16 w-16 items-center justify-center overflow-hidden rounded-full bg-gray-800">
                        {entity.thumbnail_url ? (
                          <img
                            src={entity.thumbnail_url}
                            alt={`${entityTypeLabel} entity thumbnail`}
                            className="h-full w-full object-cover"
                            data-testid="entity-thumbnail"
                          />
                        ) : (
                          <div
                            className="flex h-full w-full items-center justify-center text-gray-500"
                            data-testid="entity-placeholder"
                          >
                            {entity.entity_type === 'person' ? (
                              <User className="h-8 w-8" />
                            ) : (
                              <Car className="h-8 w-8" />
                            )}
                          </div>
                        )}
                      </div>

                      <div>
                        <Dialog.Title
                          as="h2"
                          className="flex items-center gap-2 text-xl font-bold text-white"
                          data-testid="entity-type-title"
                        >
                          {entity.entity_type === 'person' ? (
                            <User className="h-5 w-5 text-[#76B900]" />
                          ) : (
                            <Car className="h-5 w-5 text-[#76B900]" />
                          )}
                          {entityTypeLabel}
                        </Dialog.Title>
                        <p className="mt-1 font-mono text-sm text-gray-400" data-testid="entity-id">
                          {entity.id}
                        </p>
                        {/* Trust Classification Controls */}
                        <TrustClassificationControls
                          currentStatus={normalizedTrustStatus}
                          entityId={entity.id}
                          onStatusChange={handleTrustStatusChange}
                          isLoading={isTrustUpdating}
                          readOnly={!onTrustStatusChange}
                          size="sm"
                          className="mt-3"
                        />
                      </div>
                    </div>

                    <IconButton
                      icon={<X />}
                      aria-label="Close modal"
                      onClick={onClose}
                      variant="ghost"
                      size="lg"
                      data-testid="close-modal-button"
                    />
                  </div>

                  {/* Content */}
                  <div className="max-h-[calc(100vh-200px)] overflow-y-auto p-6">
                    {/* Stats row */}
                    <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
                      {/* Appearances */}
                      <div
                        className="rounded-lg border border-gray-800 bg-black/30 p-3"
                        data-testid="appearance-count-card"
                      >
                        <div className="flex items-center gap-2 text-xl font-bold text-white">
                          <Eye className="h-5 w-5 text-gray-400" />
                          <span>{entity.appearance_count}</span>
                        </div>
                        <p className="mt-1 text-xs text-gray-400">
                          {entity.appearance_count === 1 ? 'appearance' : 'appearances'}
                        </p>
                      </div>

                      {/* Cameras */}
                      <div
                        className="rounded-lg border border-gray-800 bg-black/30 p-3"
                        data-testid="cameras-count-card"
                      >
                        <div className="flex items-center gap-2 text-xl font-bold text-white">
                          <Camera className="h-5 w-5 text-gray-400" />
                          <span>{(entity.cameras_seen ?? []).length}</span>
                        </div>
                        <p className="mt-1 text-xs text-gray-400">
                          {(entity.cameras_seen ?? []).length === 1 ? 'camera' : 'cameras'}
                        </p>
                      </div>

                      {/* First seen */}
                      <div
                        className="rounded-lg border border-gray-800 bg-black/30 p-3"
                        data-testid="first-seen-card"
                      >
                        <div className="flex items-center gap-2 text-sm font-medium text-white">
                          <Clock className="h-4 w-4 text-gray-400" />
                          <span>First seen</span>
                        </div>
                        <p className="mt-1 text-xs text-gray-300">
                          {formatTimestamp(entity.first_seen)}
                        </p>
                      </div>

                      {/* Last seen */}
                      <div
                        className="rounded-lg border border-gray-800 bg-black/30 p-3"
                        data-testid="last-seen-card"
                      >
                        <div className="flex items-center gap-2 text-sm font-medium text-white">
                          <Clock className="h-4 w-4 text-gray-400" />
                          <span>Last seen</span>
                        </div>
                        <p className="mt-1 text-xs text-gray-300">
                          {formatTimestamp(entity.last_seen)}
                        </p>
                      </div>
                    </div>

                    {/* Cameras list */}
                    {(entity.cameras_seen ?? []).length > 0 && (
                      <div className="mb-6">
                        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-400">
                          Cameras
                        </h3>
                        <div className="flex flex-wrap gap-2" data-testid="cameras-list">
                          {(entity.cameras_seen ?? []).map((camera) => (
                            <span
                              key={camera}
                              className="flex items-center gap-1 rounded-full bg-gray-800 px-3 py-1 text-sm text-gray-300"
                            >
                              <Camera className="h-3.5 w-3.5" />
                              {camera}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Detection Visualization Section */}
                    <div className="mb-6" data-testid="detection-visualization-section">
                      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-gray-400">
                        <Image className="h-4 w-4" />
                        Detection History
                        {detections.length > 0 && (
                          <span className="ml-auto text-xs font-normal normal-case text-gray-500">
                            {selectedDetectionIndex + 1} of {detections.length}
                            {hasMoreDetections && '+'}
                          </span>
                        )}
                      </h3>

                      {/* Loading state */}
                      {isLoadingDetections && detections.length === 0 && (
                        <div
                          className="flex flex-col items-center justify-center rounded-lg border border-gray-800 bg-black/30 py-12"
                          data-testid="detection-loading"
                        >
                          <Loader2 className="h-8 w-8 animate-spin text-[#76B900]" />
                          <p className="mt-2 text-sm text-gray-400">Loading detections...</p>
                        </div>
                      )}

                      {/* Empty state */}
                      {!isLoadingDetections && detections.length === 0 && (
                        <div
                          className="flex flex-col items-center justify-center rounded-lg border border-gray-800 bg-black/30 py-12"
                          data-testid="detection-empty"
                        >
                          <Image className="h-12 w-12 text-gray-600" />
                          <p className="mt-2 text-sm text-gray-400">
                            No detection images available
                          </p>
                        </div>
                      )}

                      {/* Detection viewer */}
                      {detections.length > 0 && selectedDetection && (
                        <div className="space-y-3">
                          {/* Main detection image with bounding box */}
                          <div
                            className="relative overflow-hidden rounded-lg border border-gray-800 bg-black"
                            data-testid="detection-image-container"
                          >
                            <DetectionImage
                              src={getDetectionImageUrl(selectedDetection.detection_id)}
                              alt={`${selectedDetection.object_type || 'Detection'} at ${selectedDetection.camera_name || selectedDetection.camera_id}`}
                              boxes={[]}
                              className="w-full"
                              enableLightbox={false}
                            />

                            {/* Navigation arrows */}
                            {detections.length > 1 && (
                              <>
                                <IconButton
                                  icon={<ChevronLeft />}
                                  aria-label="Previous detection"
                                  onClick={handlePrevDetection}
                                  disabled={selectedDetectionIndex === 0}
                                  variant="solid"
                                  size="lg"
                                  className="absolute left-2 top-1/2 -translate-y-1/2 !rounded-full !bg-black/60 hover:!bg-black/80"
                                  data-testid="prev-detection-button"
                                />
                                <IconButton
                                  icon={
                                    isFetchingMoreDetections &&
                                    selectedDetectionIndex >= detections.length - 1 ? (
                                      <Loader2 className="animate-spin" />
                                    ) : (
                                      <ChevronRight />
                                    )
                                  }
                                  aria-label="Next detection"
                                  onClick={handleNextDetection}
                                  disabled={
                                    selectedDetectionIndex >= detections.length - 1 &&
                                    !hasMoreDetections
                                  }
                                  variant="solid"
                                  size="lg"
                                  className="absolute right-2 top-1/2 -translate-y-1/2 !rounded-full !bg-black/60 hover:!bg-black/80"
                                  data-testid="next-detection-button"
                                />
                              </>
                            )}

                            {/* Expand button */}
                            <button
                              onClick={handleOpenLightbox}
                              className="absolute bottom-2 right-2 rounded-lg bg-black/60 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-black/80"
                              data-testid="expand-detection-button"
                            >
                              View Full Size
                            </button>
                          </div>

                          {/* Detection metadata */}
                          <div
                            className="flex flex-wrap items-center gap-3 rounded-lg border border-gray-800 bg-black/20 px-4 py-2"
                            data-testid="detection-metadata"
                          >
                            <span className="flex items-center gap-1.5 text-sm text-gray-300">
                              <Camera className="h-4 w-4 text-gray-400" />
                              {selectedDetection.camera_name || selectedDetection.camera_id}
                            </span>
                            <span className="flex items-center gap-1.5 text-sm text-gray-300">
                              <Clock className="h-4 w-4 text-gray-400" />
                              {formatTimestamp(selectedDetection.timestamp)}
                            </span>
                            {selectedDetection.object_type && (
                              <span className="rounded bg-[#76B900]/20 px-2 py-0.5 text-xs font-medium text-[#76B900]">
                                {selectedDetection.object_type}
                              </span>
                            )}
                            {selectedDetection.confidence !== null &&
                              selectedDetection.confidence !== undefined && (
                                <span className="text-xs text-gray-400">
                                  Confidence: {formatConfidence(selectedDetection.confidence)}
                                </span>
                              )}
                          </div>

                          {/* Thumbnail strip */}
                          {detections.length > 1 && (
                            <div
                              className="flex gap-2 overflow-x-auto pb-2"
                              data-testid="detection-thumbnail-strip"
                            >
                              {detections.map((detection, index) => (
                                <button
                                  key={detection.detection_id}
                                  onClick={() => setSelectedDetectionIndex(index)}
                                  className={`relative flex-shrink-0 overflow-hidden rounded-lg border-2 transition-all ${
                                    index === selectedDetectionIndex
                                      ? 'border-[#76B900] ring-2 ring-[#76B900]/30'
                                      : 'border-gray-700 hover:border-gray-600'
                                  }`}
                                  data-testid={`detection-thumbnail-${detection.detection_id}`}
                                >
                                  <img
                                    src={getDetectionImageUrl(detection.detection_id)}
                                    alt={`Detection ${index + 1}`}
                                    className="h-16 w-16 object-cover"
                                    loading="lazy"
                                  />
                                  {detection.confidence !== null &&
                                    detection.confidence !== undefined && (
                                      <span className="absolute bottom-0 right-0 rounded-tl bg-black/70 px-1 text-[10px] text-white">
                                        {formatConfidence(detection.confidence)}
                                      </span>
                                    )}
                                </button>
                              ))}
                              {hasMoreDetections && (
                                <button
                                  onClick={fetchMoreDetections}
                                  disabled={isFetchingMoreDetections}
                                  className="flex h-16 w-16 flex-shrink-0 items-center justify-center rounded-lg border-2 border-dashed border-gray-700 text-gray-500 transition-colors hover:border-gray-600 hover:text-gray-400"
                                  data-testid="load-more-detections"
                                >
                                  {isFetchingMoreDetections ? (
                                    <Loader2 className="h-5 w-5 animate-spin" />
                                  ) : (
                                    <span className="text-xs">Load more</span>
                                  )}
                                </button>
                              )}
                            </div>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Appearance Timeline */}
                    <EntityTimeline
                      entity_id={entity.id}
                      entity_type={entity.entity_type as 'person' | 'vehicle'}
                      appearances={entity.appearances ?? []}
                    />
                  </div>

                  {/* Footer */}
                  <div className="flex items-center justify-between border-t border-gray-800 bg-black/20 p-4">
                    <button
                      onClick={handleViewEvents}
                      className="flex items-center gap-2 rounded-lg bg-[#76B900]/20 px-4 py-2 text-sm font-semibold text-[#76B900] transition-colors hover:bg-[#76B900]/30"
                      data-testid="view-events-button"
                    >
                      <Calendar className="h-4 w-4" />
                      View Events
                      <ExternalLink className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={onClose}
                      className="rounded-lg bg-gray-800 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-gray-700"
                    >
                      Close
                    </button>
                  </div>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition>

      {/* Lightbox for full-size detection images */}
      {lightboxImages.length > 0 && (
        <Lightbox
          images={lightboxImages}
          initialIndex={selectedDetectionIndex}
          isOpen={lightboxOpen}
          onClose={() => setLightboxOpen(false)}
          onIndexChange={setSelectedDetectionIndex}
        />
      )}
    </>
  );
}
