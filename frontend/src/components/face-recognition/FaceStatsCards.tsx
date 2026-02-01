/**
 * FaceStatsCards - Display face detection statistics in a card grid
 *
 * Features:
 * - Displays today's face detection counts
 * - Shows known vs unknown breakdown
 * - Displays camera count from detections
 * - Loading skeleton state
 * - Responsive grid: 2x2 on mobile, 4x1 on desktop
 *
 * @module components/face-recognition/FaceStatsCards
 * @see NEM-4688 Phase 1 - Face Recognition UI
 * @see docs/plans/2025-01-31-face-recognition-ui-design.md
 */

import { Camera, Eye, HelpCircle, User, Users } from 'lucide-react';
import { memo } from 'react';

import type { FaceStats } from '../../types/faceRecognition';

// ============================================================================
// Types
// ============================================================================

/**
 * Props for FaceStatsCards component.
 */
export interface FaceStatsCardsProps {
  /** Face detection statistics */
  stats?: FaceStats;
  /** Whether data is loading */
  isLoading?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Props for PersonStatsCards component.
 */
export interface PersonStatsCardsProps {
  /** Total number of sightings */
  totalSightings?: number;
  /** Average sightings per day */
  avgPerDay?: number;
  /** Number of cameras where person was seen */
  cameraCount?: number;
  /** Whether data is loading */
  isLoading?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Props for individual stat card.
 */
interface StatCardProps {
  /** Card label text */
  label: string;
  /** Value to display */
  value: number | string;
  /** Icon component to display */
  icon: React.ReactNode;
  /** Whether loading state is active */
  loading?: boolean;
  /** Test ID for the card */
  testId: string;
}

// ============================================================================
// StatCard Component
// ============================================================================

/**
 * Individual stat card component.
 */
function StatCard({ label, value, icon, loading = false, testId }: StatCardProps) {
  return (
    <div
      data-testid={testId}
      className="rounded-lg border border-gray-700 bg-[#1A1A1A] p-4 text-center"
    >
      <div className="mb-2 flex justify-center">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gray-800">
          {icon}
        </div>
      </div>
      {loading ? (
        <div className="mx-auto mt-1 h-8 w-12 animate-pulse rounded bg-gray-700" />
      ) : (
        <div className="text-2xl font-bold text-white">{value}</div>
      )}
      <div className="mt-1 text-sm text-gray-400">{label}</div>
    </div>
  );
}

// ============================================================================
// FaceStatsCards Component
// ============================================================================

/**
 * FaceStatsCards displays face detection statistics in a responsive grid.
 *
 * Layout:
 * - Mobile: 2x2 grid
 * - Desktop: 4x1 row
 *
 * Cards:
 * 1. Total Faces - total detections today
 * 2. Known - recognized face count
 * 3. Unknown - unrecognized face count
 * 4. Cameras - number of cameras with detections
 */
const FaceStatsCards = memo(function FaceStatsCards({
  stats,
  isLoading = false,
  className = '',
}: FaceStatsCardsProps) {
  // Extract stats with defaults
  const totalToday = stats?.total_today ?? 0;
  const knownCount = stats?.known_count ?? 0;
  const unknownCount = stats?.unknown_count ?? 0;
  const cameraCount = stats?.by_camera ? Object.keys(stats.by_camera).length : 0;

  return (
    <div className={`grid grid-cols-2 gap-4 md:grid-cols-4 ${className}`}>
      <StatCard
        testId="face-stats-total"
        label="Total Faces"
        value={totalToday}
        icon={<Users className="h-5 w-5 text-[#76B900]" />}
        loading={isLoading}
      />
      <StatCard
        testId="face-stats-known"
        label="Known"
        value={knownCount}
        icon={<User className="h-5 w-5 text-green-400" />}
        loading={isLoading}
      />
      <StatCard
        testId="face-stats-unknown"
        label="Unknown"
        value={unknownCount}
        icon={<HelpCircle className="h-5 w-5 text-yellow-400" />}
        loading={isLoading}
      />
      <StatCard
        testId="face-stats-cameras"
        label="Cameras"
        value={cameraCount}
        icon={<Camera className="h-5 w-5 text-blue-400" />}
        loading={isLoading}
      />
    </div>
  );
});

// ============================================================================
// PersonStatsCards Component
// ============================================================================

/**
 * PersonStatsCards displays person tracking statistics for a specific individual.
 *
 * Layout:
 * - 3-column grid
 *
 * Cards:
 * 1. Sightings - total appearances
 * 2. Avg/Day - average daily sightings
 * 3. Cameras - number of unique cameras
 */
export const PersonStatsCards = memo(function PersonStatsCards({
  totalSightings = 0,
  avgPerDay = 0,
  cameraCount = 0,
  isLoading = false,
  className = '',
}: PersonStatsCardsProps) {
  // Format avgPerDay to one decimal place if it has decimals
  const formattedAvg = Number.isInteger(avgPerDay) ? avgPerDay.toString() : avgPerDay.toFixed(1);

  return (
    <div className={`grid grid-cols-3 gap-4 ${className}`}>
      <StatCard
        testId="person-stats-sightings"
        label="Sightings"
        value={totalSightings}
        icon={<Eye className="h-5 w-5 text-[#76B900]" />}
        loading={isLoading}
      />
      <StatCard
        testId="person-stats-avg"
        label="Avg/Day"
        value={formattedAvg}
        icon={<Users className="h-5 w-5 text-blue-400" />}
        loading={isLoading}
      />
      <StatCard
        testId="person-stats-cameras"
        label="Cameras"
        value={cameraCount}
        icon={<Camera className="h-5 w-5 text-purple-400" />}
        loading={isLoading}
      />
    </div>
  );
});

export default FaceStatsCards;
