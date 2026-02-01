/**
 * Face Recognition Components
 *
 * This module exports components for the face recognition UI including:
 * - Known persons management (cards, modals, tabs)
 * - Face detection events display
 * - Person tracking and journey visualization
 * - Unknown stranger detection panels
 *
 * @module components/face-recognition
 * @see NEM-4688 - Face Recognition & Person Re-ID UI
 * @see docs/plans/2025-01-31-face-recognition-ui-design.md
 */

// ============================================================================
// Card Components
// ============================================================================

export { default as KnownPersonCard } from './KnownPersonCard';
export { default as FaceEventCard } from './FaceEventCard';

// ============================================================================
// Type Exports
// ============================================================================

// Component-specific types
export type { KnownPerson, KnownPersonCardProps } from './KnownPersonCard';
export type { FaceEventCardProps } from './FaceEventCard';

// Re-export domain types from central type definitions
export type {
  // Known Person types
  KnownPersonCreate,
  KnownPersonUpdate,
  // Face Embedding types
  FaceEmbedding,
  EnrollFaceRequest,
  EnrollFaceResponse,
  // Face Event types
  BoundingBox,
  FaceDetectionEvent,
  FaceEventsFilter,
  FaceEventsResponse,
  IdentifyFaceRequest,
  IdentifyFaceResponse,
  // Statistics types
  CameraFaceStats,
  FaceStats,
  // Person Appearance types
  PersonAppearance,
  DateRange,
  AppearancesFilter,
  PersonAppearancesResponse,
  // Unknown Stranger types
  UnknownStrangerSummary,
} from '../../types/faceRecognition';

// ============================================================================
// Planned Components (NEM-4688)
// ============================================================================

// Tab Components (Phase 2+)
// export { default as KnownPersonsTab } from './KnownPersonsTab';
// export { default as FaceEventsTab } from './FaceEventsTab';
// export { default as PersonTrackingTab } from './PersonTrackingTab';

// Card Components (Phase 2+)
// FaceEventCard now exported above

// Modal Components (Phase 2+)
// export { default as KnownPersonDetailModal } from './KnownPersonDetailModal';
// export { default as AddPersonModal } from './AddPersonModal';
export { default as EnrollFaceModal } from './EnrollFaceModal';
export type { EnrollFaceModalProps } from './EnrollFaceModal';
export { default as IdentifyPersonModal } from './IdentifyPersonModal';
export type { IdentifyPersonModalProps } from './IdentifyPersonModal';

// Panel Components (Phase 3+)
// export { default as UnknownStrangersPanel } from './UnknownStrangersPanel';
// export { default as FaceStatsCards } from './FaceStatsCards';

// Timeline Components (Phase 3+)
// export { default as PersonJourneyTimeline } from './PersonJourneyTimeline';
