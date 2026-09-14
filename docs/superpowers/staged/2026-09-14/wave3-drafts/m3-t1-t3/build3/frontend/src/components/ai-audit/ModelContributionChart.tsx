/**
 * ModelContributionChart Component
 *
 * Displays a horizontal bar chart showing the contribution rate of each AI model
 * to the overall event analysis. Shows:
 * - Model name with icon
 * - Contribution rate as percentage (0-100%)
 * - Number of events the model contributed to
 * - Visual bar representing the percentage
 *
 * Models are sorted by contribution rate in descending order.
 */

import { Eye, Scan, Image, Shirt } from 'lucide-react';

// ============================================================================
// Types
// ============================================================================

export interface ModelContribution {
  /** Name of the AI model */
  modelName: string;
  /** Contribution rate (0-1) */
  rate: number;
  /** Number of events this model contributed to */
  eventCount: number;
}

export interface ModelContributionChartProps {
  /** Array of model contribution data */
  contributions: ModelContribution[];
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get icon component for known models
 */
function getModelIcon(modelName: string) {
  const name = modelName.toLowerCase();
  if (name.includes('rtdetr') || name.includes('yolo')) return Scan;
  if (name.includes('florence')) return Eye;
  if (name.includes('clip') && name.includes('fashion')) return Shirt;
  if (name.includes('clip')) return Image;
  return Scan; // Default icon
}

/**
 * Format number with commas (e.g., 1000 -> 1,000)
 */
function formatNumber(num: number): string {
  return num.toLocaleString();
}

// ============================================================================
// Component
// ============================================================================

/**
 * ModelContributionChart - Visual breakdown of AI model contributions
 */
export default function ModelContributionChart({ contributions }: ModelContributionChartProps) {
  // Empty state
  if (contributions.length === 0) {
    return (
      <div
        className="rounded-lg border border-gray-800 bg-[#1F1F1F] p-12 text-center"
        data-testid="model-contribution-chart"
      >
        <p className="text-gray-400">No contribution data available yet.</p>
        <p className="mt-2 text-sm text-gray-500">
          Run batch audits to see model contribution rates.
        </p>
      </div>
    );
  }

  // Sort contributions by rate descending
  const sortedContributions = [...contributions].sort((a, b) => b.rate - a.rate);

  return (
    <div
      className="rounded-lg border border-gray-800 bg-[#1F1F1F] p-6"
      data-testid="model-contribution-chart"
    >
      {/* Header */}
      <div className="mb-6">
        <h3 className="text-lg font-semibold text-white">Model Contribution Breakdown</h3>
        <p className="mt-1 text-sm text-gray-400">
          Percentage of events each AI model contributed to
        </p>
      </div>

      {/* Chart */}
      <div className="space-y-4">
        {sortedContributions.map((contribution) => {
          const Icon = getModelIcon(contribution.modelName);
          const percentage = Math.round(contribution.rate * 100);

          return (
            <div key={contribution.modelName} className="space-y-2">
              {/* Model name and stats */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Icon className="h-4 w-4 text-gray-400" />
                  <span className="font-medium text-white">{contribution.modelName}</span>
                </div>
                <div className="flex items-center gap-4 text-sm">
                  <span className="text-gray-400">
                    {formatNumber(contribution.eventCount)} events
                  </span>
                  <span className="font-semibold text-[#76B900]">{percentage}%</span>
                </div>
              </div>

              {/* Progress bar */}
              <div className="h-2 w-full overflow-hidden rounded-full bg-gray-800">
                <div
                  role="progressbar"
                  aria-label={`${contribution.modelName} contribution: ${percentage}%`}
                  aria-valuenow={percentage}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  title={`${percentage}% contribution rate`}
                  className="h-full bg-gradient-to-r from-[#76B900] to-[#8ACE00] transition-all duration-300"
                  style={{ width: `${percentage}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
