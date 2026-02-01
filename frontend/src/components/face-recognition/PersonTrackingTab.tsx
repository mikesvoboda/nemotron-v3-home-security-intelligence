/**
 * PersonTrackingTab - Display person appearance timeline and journey visualization
 *
 * Shows a vertical timeline of a selected person's appearances across cameras,
 * with statistics cards showing sightings count, average per day, and cameras seen.
 *
 * Features:
 * - Searchable person selector dropdown
 * - Date range selection (Today, Yesterday, Last 7 days, Custom)
 * - Vertical journey timeline with appearance details
 * - Statistics cards for tracking metrics
 * - Loading and error states
 *
 * @module components/face-recognition/PersonTrackingTab
 * @see NEM-4688 Phase 3 - Person Tracking
 */

import { Combobox, Transition } from '@headlessui/react';
import { clsx } from 'clsx';
import {
  AlertTriangle,
  Calendar,
  Camera,
  Check,
  ChevronDown,
  Clock,
  Home,
  Loader2,
  MapPin,
  RefreshCw,
  Search,
  User,
} from 'lucide-react';
import { Fragment, useCallback, useMemo, useState } from 'react';

import {
  useKnownPersonsQuery,
  usePersonAppearancesQuery,
} from '../../hooks/useFaceRecognitionApi';

import type { KnownPerson, PersonAppearance, AppearancesFilter } from '../../types/faceRecognition';

// ============================================================================
// Types
// ============================================================================

export interface PersonTrackingTabProps {
  /** Initial person ID to display (optional) */
  initialPersonId?: number;
  /** Additional CSS classes */
  className?: string;
}

type DateRangePreset = 'today' | 'yesterday' | '7d' | 'custom';

interface DateRangeOption {
  value: DateRangePreset;
  label: string;
}

// ============================================================================
// Constants
// ============================================================================

const DATE_RANGE_OPTIONS: DateRangeOption[] = [
  { value: 'today', label: 'Today' },
  { value: 'yesterday', label: 'Yesterday' },
  { value: '7d', label: 'Last 7 days' },
  { value: 'custom', label: 'Custom' },
];

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get date range from preset selection.
 */
function getDateRangeFromPreset(preset: DateRangePreset): { start_date: string; end_date: string } {
  const today = new Date();
  const endDate = today.toISOString().split('T')[0];

  switch (preset) {
    case 'today':
      return { start_date: endDate, end_date: endDate };
    case 'yesterday': {
      const yesterday = new Date(today);
      yesterday.setDate(yesterday.getDate() - 1);
      const yesterdayStr = yesterday.toISOString().split('T')[0];
      return { start_date: yesterdayStr, end_date: yesterdayStr };
    }
    case '7d': {
      const weekAgo = new Date(today);
      weekAgo.setDate(weekAgo.getDate() - 6);
      return { start_date: weekAgo.toISOString().split('T')[0], end_date: endDate };
    }
    case 'custom':
    default:
      return { start_date: endDate, end_date: endDate };
  }
}

/**
 * Format timestamp for display in timeline (e.g., "8:15 AM").
 */
function formatTime(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

/**
 * Infer action type based on camera name and position in sequence.
 */
function inferActionType(
  appearance: PersonAppearance,
  index: number,
  appearances: PersonAppearance[]
): string {
  const cameraName = appearance.camera_name.toLowerCase();
  const isFirst = index === 0;
  const isLast = index === appearances.length - 1;

  // Simple heuristics based on camera name
  if (cameraName.includes('driveway') || cameraName.includes('street')) {
    return isFirst ? 'arrived' : isLast ? 'departed' : 'passed';
  }
  if (cameraName.includes('door')) {
    // Check if previous appearance was outside
    if (index > 0) {
      const prevCamera = appearances[index - 1].camera_name.toLowerCase();
      if (prevCamera.includes('driveway') || prevCamera.includes('street')) {
        return 'entered';
      }
    }
    // Check if next appearance is outside
    if (index < appearances.length - 1) {
      const nextCamera = appearances[index + 1].camera_name.toLowerCase();
      if (nextCamera.includes('driveway') || nextCamera.includes('street')) {
        return 'exited';
      }
    }
    return 'detected';
  }
  return 'detected';
}

/**
 * Calculate statistics from appearances.
 */
function calculateStats(
  appearances: PersonAppearance[],
  dateRangePreset: DateRangePreset
): { sightings: number; avgPerDay: number; uniqueCameras: number } {
  const sightings = appearances.length;
  const uniqueCameras = new Set(appearances.map((a) => a.camera_id)).size;

  // Calculate number of days in range
  let daysInRange = 1;
  if (dateRangePreset === '7d') {
    daysInRange = 7;
  } else if (dateRangePreset === 'custom') {
    // For custom, estimate from actual appearance dates
    if (appearances.length > 0) {
      const dates = new Set(
        appearances.map((a) => new Date(a.timestamp).toISOString().split('T')[0])
      );
      daysInRange = Math.max(dates.size, 1);
    }
  }

  const avgPerDay = daysInRange > 0 ? sightings / daysInRange : 0;

  return { sightings, avgPerDay, uniqueCameras };
}

// ============================================================================
// Sub-components
// ============================================================================

/**
 * Person selector dropdown with search functionality.
 */
function PersonSelector({
  persons,
  selectedPerson,
  onSelect,
  isLoading,
}: {
  persons: KnownPerson[];
  selectedPerson: KnownPerson | null;
  onSelect: (person: KnownPerson | null) => void;
  isLoading: boolean;
}) {
  const [query, setQuery] = useState('');

  const filteredPersons = useMemo(() => {
    if (query === '') {
      return persons;
    }
    return persons.filter((person) =>
      person.name.toLowerCase().includes(query.toLowerCase())
    );
  }, [persons, query]);

  if (isLoading) {
    return (
      <div
        data-testid="persons-loading"
        className="flex items-center gap-2 px-4 py-2 bg-[#1A1A1A] border border-gray-700 rounded-lg"
      >
        <Loader2 className="h-5 w-5 animate-spin text-[#76B900]" data-testid="loading-spinner" />
        <span className="text-gray-400">Loading persons...</span>
      </div>
    );
  }

  return (
    <Combobox value={selectedPerson} onChange={onSelect}>
      <div className="relative">
        <div
          data-testid="person-selector"
          aria-label="Select a person"
          className="relative w-full cursor-default overflow-hidden rounded-lg bg-[#1A1A1A] border border-gray-700 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-[#76B900]"
        >
          <Combobox.Input
            className="w-full border-none py-2 pl-10 pr-10 text-sm text-white bg-transparent focus:ring-0"
            displayValue={(person: KnownPerson | null) => person?.name ?? ''}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search and select a person..."
          />
          <div className="absolute inset-y-0 left-0 flex items-center pl-3">
            <Search className="h-4 w-4 text-gray-400" aria-hidden="true" />
          </div>
          <Combobox.Button className="absolute inset-y-0 right-0 flex items-center pr-3">
            <ChevronDown className="h-5 w-5 text-gray-400" aria-hidden="true" />
          </Combobox.Button>
        </div>
        <Transition
          as={Fragment}
          leave="transition ease-in duration-100"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
          afterLeave={() => setQuery('')}
        >
          <Combobox.Options
            data-testid="person-dropdown"
            className="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-lg bg-[#1A1A1A] border border-gray-700 py-1 text-sm shadow-lg focus:outline-none"
          >
            {filteredPersons.length === 0 && query !== '' ? (
              <div className="relative cursor-default select-none py-2 px-4 text-gray-400">
                No persons found matching &ldquo;{query}&rdquo;
              </div>
            ) : filteredPersons.length === 0 ? (
              <div className="relative cursor-default select-none py-2 px-4 text-gray-400">
                No known persons available
              </div>
            ) : (
              filteredPersons.map((person) => (
                <Combobox.Option
                  key={person.id}
                  className={({ active }) =>
                    clsx(
                      'relative cursor-pointer select-none py-2 pl-10 pr-4 truncate',
                      active ? 'bg-[#76B900]/10 text-white' : 'text-gray-300'
                    )
                  }
                  value={person}
                >
                  {({ selected, active }) => (
                    <>
                      <span
                        className={clsx(
                          'block truncate',
                          selected ? 'font-semibold' : 'font-normal'
                        )}
                      >
                        {person.name}
                      </span>
                      {person.is_household_member && (
                        <span className="ml-2 inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs bg-blue-500/20 text-blue-400">
                          <Home className="h-3 w-3" />
                          Household
                        </span>
                      )}
                      {selected && (
                        <span
                          className={clsx(
                            'absolute inset-y-0 left-0 flex items-center pl-3',
                            active ? 'text-[#76B900]' : 'text-[#76B900]'
                          )}
                        >
                          <Check className="h-5 w-5" aria-hidden="true" />
                        </span>
                      )}
                    </>
                  )}
                </Combobox.Option>
              ))
            )}
          </Combobox.Options>
        </Transition>
      </div>
    </Combobox>
  );
}

/**
 * Date range selector with preset buttons.
 */
function DateRangeSelector({
  selectedPreset,
  onPresetSelect,
  customStartDate,
  customEndDate,
  onCustomStartChange,
  onCustomEndChange,
}: {
  selectedPreset: DateRangePreset;
  onPresetSelect: (preset: DateRangePreset) => void;
  customStartDate: string;
  customEndDate: string;
  onCustomStartChange: (date: string) => void;
  onCustomEndChange: (date: string) => void;
}) {
  return (
    <div data-testid="date-range-selector" className="space-y-3">
      {/* Preset buttons */}
      <div className="flex flex-wrap gap-2" role="group" aria-label="Date range presets">
        {DATE_RANGE_OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => onPresetSelect(option.value)}
            aria-pressed={selectedPreset === option.value}
            className={clsx(
              'px-3 py-1.5 text-sm font-medium rounded-lg transition-colors',
              selectedPreset === option.value
                ? 'bg-[#76B900] text-white'
                : 'bg-[#1A1A1A] border border-gray-700 text-gray-300 hover:border-[#76B900] hover:text-[#76B900]'
            )}
          >
            {option.label}
          </button>
        ))}
      </div>

      {/* Custom date inputs */}
      {selectedPreset === 'custom' && (
        <div className="flex flex-wrap gap-4">
          <div className="flex-1 min-w-[140px]">
            <label
              htmlFor="custom-start-date"
              className="block text-xs font-medium text-gray-400 mb-1"
            >
              Start Date
            </label>
            <div className="relative">
              <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
              <input
                id="custom-start-date"
                type="date"
                value={customStartDate}
                onChange={(e) => onCustomStartChange(e.target.value)}
                max={customEndDate || undefined}
                className="w-full pl-10 pr-3 py-2 bg-[#1A1A1A] border border-gray-700 rounded-lg text-sm text-white focus:border-[#76B900] focus:ring-1 focus:ring-[#76B900] focus:outline-none"
              />
            </div>
          </div>
          <div className="flex-1 min-w-[140px]">
            <label
              htmlFor="custom-end-date"
              className="block text-xs font-medium text-gray-400 mb-1"
            >
              End Date
            </label>
            <div className="relative">
              <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
              <input
                id="custom-end-date"
                type="date"
                value={customEndDate}
                onChange={(e) => onCustomEndChange(e.target.value)}
                min={customStartDate || undefined}
                className="w-full pl-10 pr-3 py-2 bg-[#1A1A1A] border border-gray-700 rounded-lg text-sm text-white focus:border-[#76B900] focus:ring-1 focus:ring-[#76B900] focus:outline-none"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Single timeline item showing an appearance.
 */
function TimelineItem({
  appearance,
  actionType,
  isLast,
}: {
  appearance: PersonAppearance;
  actionType: string;
  isLast: boolean;
}) {
  const confidence = Math.round(appearance.confidence * 100);

  return (
    <li data-testid="timeline-item" className="relative flex gap-4">
      {/* Timeline dot and connector */}
      <div className="flex flex-col items-center">
        <div
          data-testid="timeline-dot"
          className="w-3 h-3 rounded-full bg-[#76B900] flex-shrink-0 mt-1.5"
        />
        {!isLast && (
          <div data-testid="timeline-connector" className="w-0.5 flex-1 bg-gray-600 my-1" />
        )}
      </div>

      {/* Content */}
      <div className="flex-1 pb-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            {/* Time */}
            <div className="flex items-center gap-2">
              <span data-testid="appearance-time" className="text-sm font-medium text-white">
                {formatTime(appearance.timestamp)}
              </span>
              <span
                data-testid="action-type"
                className="text-xs px-2 py-0.5 rounded bg-gray-700 text-gray-300"
              >
                {actionType}
              </span>
            </div>

            {/* Camera and location */}
            <div className="flex items-center gap-2 mt-1">
              <MapPin className="h-4 w-4 text-gray-400" />
              <span className="text-sm text-gray-300">{appearance.camera_name}</span>
            </div>
          </div>

          {/* Thumbnail or icon */}
          <div className="flex-shrink-0">
            {appearance.thumbnail_url ? (
              <img
                src={appearance.thumbnail_url}
                alt={`Detection at ${appearance.camera_name}`}
                className="w-12 h-12 rounded-lg object-cover border border-gray-700"
              />
            ) : (
              <div
                data-testid="appearance-icon"
                className="w-12 h-12 rounded-lg bg-gray-700 flex items-center justify-center"
              >
                <User className="h-6 w-6 text-gray-400" />
              </div>
            )}
          </div>
        </div>

        {/* Confidence badge */}
        <div className="mt-2">
          <span className="text-xs text-gray-400">
            Confidence: <span className="text-[#76B900]">{confidence}%</span>
          </span>
        </div>
      </div>
    </li>
  );
}

/**
 * Journey timeline showing all appearances.
 */
function PersonJourneyTimeline({
  appearances,
  personName,
}: {
  appearances: PersonAppearance[];
  personName: string;
}) {
  if (appearances.length === 0) {
    return (
      <div className="text-center py-12">
        <div data-testid="empty-state-icon" className="mx-auto mb-4">
          <Camera className="h-12 w-12 text-gray-600 mx-auto" />
        </div>
        <p className="text-gray-400 mb-2">No appearances found</p>
        <p className="text-sm text-gray-500">
          {personName} has not been detected in the selected time period.
        </p>
      </div>
    );
  }

  // Sort appearances by timestamp (chronological order)
  const sortedAppearances = [...appearances].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  );

  return (
    <ul
      aria-label="Journey timeline"
      className="space-y-0"
    >
      {sortedAppearances.map((appearance, index) => (
        <TimelineItem
          key={appearance.detection_id}
          appearance={appearance}
          actionType={inferActionType(appearance, index, sortedAppearances)}
          isLast={index === sortedAppearances.length - 1}
        />
      ))}
    </ul>
  );
}

/**
 * Statistics cards showing tracking metrics.
 */
function PersonStatsCards({
  stats,
}: {
  stats: { sightings: number; avgPerDay: number; uniqueCameras: number };
}) {
  return (
    <div data-testid="stats-cards" className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      {/* Sightings */}
      <article
        data-testid="stat-sightings"
        className="bg-[#1A1A1A] rounded-lg border border-gray-700 p-4"
      >
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-[#76B900]/10">
            <User className="h-5 w-5 text-[#76B900]" />
          </div>
          <div>
            <p className="text-2xl font-bold text-white">{stats.sightings}</p>
            <p className="text-xs text-gray-400">Sightings</p>
          </div>
        </div>
      </article>

      {/* Average per day */}
      <article
        data-testid="stat-avg-day"
        className="bg-[#1A1A1A] rounded-lg border border-gray-700 p-4"
      >
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-blue-500/10">
            <Clock className="h-5 w-5 text-blue-400" />
          </div>
          <div>
            <p className="text-2xl font-bold text-white">{stats.avgPerDay.toFixed(1)}</p>
            <p className="text-xs text-gray-400">Avg/Day</p>
          </div>
        </div>
      </article>

      {/* Cameras */}
      <article
        data-testid="stat-cameras"
        className="bg-[#1A1A1A] rounded-lg border border-gray-700 p-4"
      >
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-purple-500/10">
            <Camera className="h-5 w-5 text-purple-400" />
          </div>
          <div>
            <p className="text-2xl font-bold text-white">{stats.uniqueCameras}</p>
            <p className="text-xs text-gray-400">Cameras</p>
          </div>
        </div>
      </article>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * PersonTrackingTab - Main component for person tracking visualization.
 *
 * Displays a searchable person selector, date range filter, journey timeline,
 * and statistics cards for the selected person's appearances.
 */
export default function PersonTrackingTab({
  initialPersonId,
  className,
}: PersonTrackingTabProps) {
  // State
  const [selectedPerson, setSelectedPerson] = useState<KnownPerson | null>(null);
  const [dateRangePreset, setDateRangePreset] = useState<DateRangePreset>('today');
  const [customStartDate, setCustomStartDate] = useState('');
  const [customEndDate, setCustomEndDate] = useState('');

  // Data fetching
  const personsQuery = useKnownPersonsQuery();
  const persons = useMemo(() => personsQuery.data ?? [], [personsQuery.data]);

  // Initialize selected person from prop (use useEffect for side effects)
  useMemo(() => {
    if (initialPersonId && !selectedPerson && persons.length > 0) {
      const person = persons.find((p) => p.id === initialPersonId);
      if (person) {
        setSelectedPerson(person);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialPersonId, persons.length]);

  // Build appearances filter
  const appearancesFilter: AppearancesFilter = useMemo(() => {
    if (dateRangePreset === 'custom' && customStartDate && customEndDate) {
      return {
        start_date: customStartDate,
        end_date: customEndDate,
      };
    }
    return getDateRangeFromPreset(dateRangePreset);
  }, [dateRangePreset, customStartDate, customEndDate]);

  const appearancesQuery = usePersonAppearancesQuery(
    selectedPerson?.id ?? null,
    appearancesFilter
  );

  const appearances = useMemo(
    () => appearancesQuery.data?.appearances ?? [],
    [appearancesQuery.data?.appearances]
  );
  const stats = useMemo(
    () => calculateStats(appearances, dateRangePreset),
    [appearances, dateRangePreset]
  );

  // Handlers
  const handlePersonSelect = useCallback((person: KnownPerson | null) => {
    setSelectedPerson(person);
  }, []);

  const handlePresetSelect = useCallback((preset: DateRangePreset) => {
    setDateRangePreset(preset);
    // Reset custom dates when switching to preset
    if (preset !== 'custom') {
      setCustomStartDate('');
      setCustomEndDate('');
    } else {
      // Initialize custom dates with today
      const today = new Date().toISOString().split('T')[0];
      setCustomStartDate(today);
      setCustomEndDate(today);
    }
  }, []);

  const handleRetry = useCallback(() => {
    void appearancesQuery.refetch();
  }, [appearancesQuery]);

  // Get title based on date range
  const getJourneyTitle = useCallback(() => {
    switch (dateRangePreset) {
      case 'today':
        return "Today's Journey";
      case 'yesterday':
        return "Yesterday's Journey";
      case '7d':
        return 'Last 7 Days Journey';
      case 'custom':
        return 'Journey';
      default:
        return 'Journey';
    }
  }, [dateRangePreset]);

  // Error state for persons
  if (personsQuery.isError) {
    const errorMessage =
      (personsQuery.error as Error | undefined)?.message ?? 'An error occurred';
    return (
      <div
        data-testid="person-tracking-tab"
        className={clsx('bg-[#121212] rounded-lg p-6', className)}
      >
        <h2 className="text-xl font-semibold text-white mb-4">Person Tracking</h2>
        <div role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 p-6 text-center">
          <AlertTriangle className="h-8 w-8 text-red-400 mx-auto mb-3" />
          <p className="text-red-400">{errorMessage}</p>
        </div>
      </div>
    );
  }

  // Empty state for no known persons
  if (!personsQuery.isLoading && persons.length === 0) {
    return (
      <div
        data-testid="person-tracking-tab"
        className={clsx('bg-[#121212] rounded-lg p-6', className)}
      >
        <h2 className="text-xl font-semibold text-white mb-4">Person Tracking</h2>
        <div className="rounded-lg border border-gray-700 bg-[#1A1A1A] p-8 text-center">
          <User className="h-12 w-12 text-gray-600 mx-auto mb-4" />
          <p className="text-gray-400 mb-2">No known persons</p>
          <p className="text-sm text-gray-500">
            Add known persons to track their appearances across cameras.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      data-testid="person-tracking-tab"
      className={clsx('bg-[#121212] rounded-lg p-6', className)}
    >
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <h2 className="text-xl font-semibold text-white">Person Tracking</h2>
        <div className="w-full sm:w-72">
          <PersonSelector
            persons={persons}
            selectedPerson={selectedPerson}
            onSelect={handlePersonSelect}
            isLoading={personsQuery.isLoading}
          />
        </div>
      </div>

      {/* No person selected state */}
      {!selectedPerson && !personsQuery.isLoading && (
        <div className="rounded-lg border border-gray-700 bg-[#1A1A1A] p-8 text-center">
          <Search className="h-12 w-12 text-gray-600 mx-auto mb-4" />
          <p className="text-gray-400 mb-2">Select a person to view their tracking data</p>
          <p className="text-sm text-gray-500">
            Use the dropdown above to search and select a person.
          </p>
        </div>
      )}

      {/* Main content when person is selected */}
      {selectedPerson && (
        <div className="space-y-6">
          {/* Date range selector */}
          <DateRangeSelector
            selectedPreset={dateRangePreset}
            onPresetSelect={handlePresetSelect}
            customStartDate={customStartDate}
            customEndDate={customEndDate}
            onCustomStartChange={setCustomStartDate}
            onCustomEndChange={setCustomEndDate}
          />

          {/* Loading state */}
          {appearancesQuery.isLoading && (
            <div
              data-testid="appearances-loading"
              role="status"
              className="flex items-center justify-center py-12"
            >
              <Loader2 className="h-8 w-8 animate-spin text-[#76B900]" data-testid="loading-spinner" />
              <span className="ml-3 text-gray-400">Loading appearances...</span>
            </div>
          )}

          {/* Error state */}
          {appearancesQuery.isError && (
            <div role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 p-6 text-center">
              <AlertTriangle className="h-8 w-8 text-red-400 mx-auto mb-3" />
              <p className="text-red-400 mb-4">
                {(appearancesQuery.error as Error | undefined)?.message ?? 'An error occurred'}
              </p>
              <button
                type="button"
                onClick={handleRetry}
                className="inline-flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors"
              >
                <RefreshCw className="h-4 w-4" />
                Retry
              </button>
            </div>
          )}

          {/* Journey timeline and stats */}
          {!appearancesQuery.isLoading && !appearancesQuery.isError && (
            <>
              {/* Statistics Cards */}
              <div>
                <h3 className="text-sm font-medium text-gray-400 mb-3">
                  Statistics ({dateRangePreset === '7d' ? 'Last 7 Days' : dateRangePreset === 'today' ? 'Today' : dateRangePreset === 'yesterday' ? 'Yesterday' : 'Custom Range'})
                </h3>
                <PersonStatsCards stats={stats} />
              </div>

              {/* Journey Timeline */}
              <div>
                <h3 className="text-lg font-semibold text-white mb-4">{getJourneyTitle()}</h3>
                <div className="bg-[#1A1A1A] rounded-lg border border-gray-700 p-4">
                  <PersonJourneyTimeline
                    appearances={appearances}
                    personName={selectedPerson.name}
                  />
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
