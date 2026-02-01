/**
 * PlateStatisticsCards - Display plate read statistics in a grid of cards
 *
 * Shows key metrics including total reads, unique plates, OCR confidence,
 * recent activity, and quality indicators (enhanced/blurry counts).
 */

import { Card, Text } from '@tremor/react';
import {
  AlertCircle,
  Car,
  Fingerprint,
  Gauge,
  Clock,
  Sun,
  Focus,
  Loader2,
} from 'lucide-react';

import { usePlateStatisticsQuery } from '../../hooks/usePlateStatisticsQuery';

// ============================================================================
// Types
// ============================================================================

/**
 * Badge component for showing comparison values
 */
interface ComparisonBadgeProps {
  /** Value to display */
  value: number;
  /** Label for the comparison */
  label: string;
}

/**
 * Single stat card props
 */
interface StatCardProps {
  /** Card title */
  title: string;
  /** Main value to display */
  value: string | number;
  /** Icon component to display */
  icon: React.ReactNode;
  /** Optional comparison badge */
  badge?: ComparisonBadgeProps;
  /** Test ID for the card */
  testId: string;
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Format a number with thousands separator.
 *
 * @param num - Number to format
 * @returns Formatted number string
 */
function formatNumber(num: number): string {
  return num.toLocaleString();
}

// ============================================================================
// Sub-Components
// ============================================================================

/**
 * Comparison badge showing recent activity
 */
function ComparisonBadge({ value, label }: ComparisonBadgeProps) {
  return (
    <span className="ml-2 rounded-full bg-[#76B900]/20 px-2 py-0.5 text-xs text-[#76B900]">
      {formatNumber(value)} {label}
    </span>
  );
}

/**
 * Single statistics card
 */
function StatCard({ title, value, icon, badge, testId }: StatCardProps) {
  return (
    <Card className="p-4" data-testid={testId}>
      <div className="flex items-center gap-2">
        <span className="text-[#76B900]">{icon}</span>
        <Text className="text-sm text-gray-400">{title}</Text>
      </div>
      <div className="mt-2 flex items-baseline">
        <p className="text-2xl font-bold text-white">{value}</p>
        {badge && <ComparisonBadge value={badge.value} label={badge.label} />}
      </div>
    </Card>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * PlateStatisticsCards displays plate read statistics in a grid layout.
 *
 * Fetches statistics using the usePlateStatisticsQuery hook and displays:
 * - Total plate reads (with 24h comparison)
 * - Unique plates count
 * - Average OCR confidence percentage
 * - Reads in the last hour
 * - Enhanced (low-light) read count
 * - Blurry read count
 *
 * @returns React element
 */
export function PlateStatisticsCards(): React.ReactElement {
  const {
    totalReads,
    uniquePlates,
    avgConfidencePercent,
    readsLastHour,
    readsLast24h,
    enhancedCount,
    blurryCount,
    isLoading,
    error,
  } = usePlateStatisticsQuery();

  // Loading state
  if (isLoading) {
    return (
      <div
        className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4"
        data-testid="plate-statistics-loading"
      >
        {Array.from({ length: 6 }, (_, i) => (
          <Card key={i} className="p-4">
            <div className="flex h-20 items-center justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
            </div>
          </Card>
        ))}
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div
        className="rounded-lg border border-red-500/20 bg-red-500/10 p-4"
        data-testid="plate-statistics-error"
      >
        <div className="flex items-center gap-2 text-red-400">
          <AlertCircle className="h-5 w-5" />
          <Text>Failed to load plate statistics</Text>
        </div>
      </div>
    );
  }

  return (
    <div
      className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3"
      data-testid="plate-statistics-cards"
    >
      <StatCard
        title="Total Plate Reads"
        value={formatNumber(totalReads)}
        icon={<Car className="h-5 w-5" />}
        badge={{ value: readsLast24h, label: 'last 24h' }}
        testId="stat-total-reads"
      />

      <StatCard
        title="Unique Plates"
        value={formatNumber(uniquePlates)}
        icon={<Fingerprint className="h-5 w-5" />}
        testId="stat-unique-plates"
      />

      <StatCard
        title="Avg OCR Confidence"
        value={`${avgConfidencePercent}%`}
        icon={<Gauge className="h-5 w-5" />}
        testId="stat-avg-confidence"
      />

      <StatCard
        title="Reads Last Hour"
        value={formatNumber(readsLastHour)}
        icon={<Clock className="h-5 w-5" />}
        testId="stat-reads-last-hour"
      />

      <StatCard
        title="Enhanced (Low-Light)"
        value={formatNumber(enhancedCount)}
        icon={<Sun className="h-5 w-5" />}
        testId="stat-enhanced-count"
      />

      <StatCard
        title="Blurry Reads"
        value={formatNumber(blurryCount)}
        icon={<Focus className="h-5 w-5" />}
        testId="stat-blurry-count"
      />
    </div>
  );
}

export default PlateStatisticsCards;
