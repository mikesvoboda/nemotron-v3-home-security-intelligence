/**
 * KnownPersonsTab - Grid view of known persons with stats and unknown strangers panel.
 *
 * Displays:
 * - Header with count and "Add Person" button
 * - Responsive grid of known person cards
 * - Recent unknown faces section (limited to 3)
 * - Today's face detection statistics
 *
 * @module components/face-recognition/KnownPersonsTab
 * @see NEM-4688 Phase 1 - Known Persons Management
 */

import { AlertTriangle, Camera, Loader2, Plus, User, UserCheck, Users } from 'lucide-react';
import { useCallback } from 'react';

import type { KnownPerson } from '@/types/faceRecognition';

import {
  useKnownPersonsQuery,
  useUnknownStrangersQuery,
  useFaceStatsQuery,
} from '@/hooks/useFaceRecognitionApi';

// ============================================================================
// Types
// ============================================================================

export interface KnownPersonsTabProps {
  /** Callback when a person card is clicked */
  onPersonClick: (person: KnownPerson) => void;
  /** Callback when the Add Person button is clicked */
  onAddPerson: () => void;
}

// ============================================================================
// Sub-Components
// ============================================================================

/**
 * Individual known person card with avatar, name, and embedding count.
 */
interface KnownPersonCardProps {
  person: KnownPerson;
  onClick: () => void;
}

function KnownPersonCard({ person, onClick }: KnownPersonCardProps) {
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        onClick();
      }
    },
    [onClick]
  );

  return (
    <div
      data-testid="known-person-card"
      className="flex flex-col items-center rounded-lg border border-gray-700 bg-[#1A1A1A] p-4 transition-colors hover:border-gray-600 hover:bg-[#252525] cursor-pointer"
      onClick={onClick}
      onKeyDown={handleKeyDown}
      tabIndex={0}
      role="button"
      aria-label={`View details for ${person.name}`}
    >
      {/* Avatar */}
      <div className="mb-3 flex h-16 w-16 items-center justify-center rounded-full bg-[#76B900]/10">
        <User className="h-8 w-8 text-[#76B900]" aria-hidden="true" />
      </div>

      {/* Name */}
      <span className="mb-1 text-center text-sm font-medium text-white truncate w-full">
        {person.name}
      </span>

      {/* Embedding count badge */}
      <div className="flex items-center gap-1 text-xs text-gray-400">
        <UserCheck className="h-3 w-3" aria-hidden="true" />
        <span>{person.embedding_count}</span>
      </div>

      {/* Household member indicator */}
      {person.is_household_member && (
        <span className="mt-2 rounded-full bg-blue-500/20 px-2 py-0.5 text-xs text-blue-400">
          Household
        </span>
      )}
    </div>
  );
}

/**
 * Statistics card component for displaying a single stat.
 */
interface StatCardProps {
  label: string;
  value: number;
  icon: React.ElementType;
  testId: string;
}

function StatCard({ label, value, icon: Icon, testId }: StatCardProps) {
  return (
    <div
      data-testid={testId}
      className="flex flex-col items-center rounded-lg border border-gray-700 bg-[#1A1A1A] p-4"
    >
      <Icon className="mb-2 h-5 w-5 text-gray-400" aria-hidden="true" />
      <span className="text-2xl font-bold text-white">{value}</span>
      <span className="text-xs text-gray-400">{label}</span>
    </div>
  );
}

/**
 * Unknown stranger card showing basic info.
 */
interface UnknownStrangerCardProps {
  cameraName: string;
  timestamp: string;
}

function UnknownStrangerCard({ cameraName, timestamp }: UnknownStrangerCardProps) {
  const formattedTime = new Date(timestamp).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  });

  return (
    <div className="flex items-center gap-3 rounded-lg border border-gray-700 bg-[#1A1A1A] p-3">
      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-yellow-500/10">
        <AlertTriangle className="h-5 w-5 text-yellow-500" aria-hidden="true" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-white truncate">{cameraName}</p>
        <p className="text-xs text-gray-400">{formattedTime}</p>
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * KnownPersonsTab displays a grid of known persons with management controls.
 *
 * Features:
 * - Responsive grid layout (2-4 columns based on screen size)
 * - Add Person button in header
 * - Recent unknown faces panel (limited to 3)
 * - Today's face detection statistics
 * - Loading, error, and empty states
 */
export default function KnownPersonsTab({ onPersonClick, onAddPerson }: KnownPersonsTabProps) {
  // Fetch data using TanStack Query hooks
  const {
    data: knownPersons,
    isLoading: isLoadingPersons,
    error: personsError,
  } = useKnownPersonsQuery();

  const {
    data: unknownStrangers,
    isLoading: isLoadingStrangers,
    error: strangersError,
  } = useUnknownStrangersQuery(); // We'll take only 3 items in the UI

  const {
    data: faceStats,
    isLoading: isLoadingStats,
    error: statsError,
  } = useFaceStatsQuery();

  // Derived values
  const personCount = knownPersons?.length ?? 0;
  const cameraCount = faceStats ? Object.keys(faceStats.by_camera).length : 0;

  // Loading state for known persons section
  if (isLoadingPersons) {
    return (
      <div data-testid="known-persons-tab" className="space-y-6">
        <div data-testid="known-persons-loading" className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-[#76B900]" />
          <span className="ml-2 text-gray-400">Loading known persons...</span>
        </div>
      </div>
    );
  }

  // Error state for known persons
  if (personsError) {
    return (
      <div data-testid="known-persons-tab" className="space-y-6">
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-6 text-center">
          <AlertTriangle className="mx-auto mb-2 h-8 w-8 text-red-400" />
          <p className="text-red-400">
            {personsError instanceof Error ? personsError.message : 'Failed to load known persons'}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div data-testid="known-persons-tab" className="space-y-6">
      {/* Header Section */}
      <div
        data-testid="known-persons-header"
        className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between"
      >
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold text-white">Known Persons</h2>
          <span className="rounded-full bg-gray-700 px-2 py-0.5 text-xs font-medium text-gray-300">
            ({personCount})
          </span>
        </div>
        <button
          onClick={onAddPerson}
          className="inline-flex items-center gap-2 rounded-lg bg-[#76B900] px-4 py-2 text-sm font-medium text-black transition-colors hover:bg-[#88d200]"
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
          Add Person
        </button>
      </div>

      {/* Known Persons Grid or Empty State */}
      {personCount === 0 ? (
        <div className="rounded-lg border border-gray-700 bg-[#1A1A1A] p-8 text-center">
          <Users className="mx-auto mb-4 h-12 w-12 text-gray-600" />
          <p className="mb-2 text-gray-400">No known persons</p>
          <p className="text-sm text-gray-500">Add your first person to start tracking faces</p>
        </div>
      ) : (
        <div
          data-testid="known-persons-grid"
          className="grid gap-4 grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6"
        >
          {knownPersons?.map((person) => (
            <KnownPersonCard
              key={person.id}
              person={person}
              onClick={() => onPersonClick(person)}
            />
          ))}
        </div>
      )}

      {/* Recent Unknown Faces Section */}
      <div data-testid="unknown-strangers-section" className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-medium text-white">Recent Unknown Faces</h3>
          <button
            className="text-sm text-blue-400 transition-colors hover:text-blue-300"
            aria-label="View all unknown faces"
          >
            View All
          </button>
        </div>

        {isLoadingStrangers ? (
          <div className="flex items-center justify-center py-4">
            <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
          </div>
        ) : strangersError ? (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4">
            <p className="text-sm text-red-400">
              {strangersError instanceof Error
                ? strangersError.message
                : 'Failed to load unknown faces'}
            </p>
          </div>
        ) : unknownStrangers?.items.length === 0 ? (
          <div className="rounded-lg border border-gray-700 bg-[#1A1A1A] p-4 text-center">
            <p className="text-sm text-gray-400">No unknown faces detected today</p>
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-3">
            {unknownStrangers?.items.slice(0, 3).map((stranger) => (
              <UnknownStrangerCard
                key={stranger.id}
                cameraName={stranger.camera_name}
                timestamp={stranger.timestamp}
              />
            ))}
          </div>
        )}
      </div>

      {/* Today's Stats Section */}
      <div data-testid="stats-section" className="space-y-4">
        <h3 className="text-base font-medium text-white">Today&apos;s Stats</h3>

        {isLoadingStats ? (
          <div data-testid="stats-loading" className="flex items-center justify-center py-4">
            <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
          </div>
        ) : statsError ? (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4">
            <p className="text-sm text-red-400">
              {statsError instanceof Error ? statsError.message : 'Failed to load stats'}
            </p>
          </div>
        ) : (
          <div className="grid gap-4 grid-cols-2 sm:grid-cols-4">
            <StatCard
              testId="stat-card-total"
              label="Total"
              value={faceStats?.total_today ?? 0}
              icon={Users}
            />
            <StatCard
              testId="stat-card-known"
              label="Known"
              value={faceStats?.known_count ?? 0}
              icon={UserCheck}
            />
            <StatCard
              testId="stat-card-unknown"
              label="Unknown"
              value={faceStats?.unknown_count ?? 0}
              icon={AlertTriangle}
            />
            <StatCard
              testId="stat-card-cameras"
              label="Cameras"
              value={cameraCount}
              icon={Camera}
            />
          </div>
        )}
      </div>
    </div>
  );
}
