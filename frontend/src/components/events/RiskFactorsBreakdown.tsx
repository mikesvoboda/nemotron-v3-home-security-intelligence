/**
 * RiskFactorsBreakdown - Display risk score contribution factors (NEM-3603)
 *
 * Shows individual factors that contribute to the overall risk score.
 * Factors can have positive contributions (increase risk, shown in red/orange)
 * or negative contributions (decrease risk, shown in green).
 * Factors are sorted by contribution magnitude (largest impact first).
 */

import { clsx } from 'clsx';
import { TrendingDown, TrendingUp, Scale } from 'lucide-react';

import type { RiskFactor } from '../../types/risk-analysis';
import type { ReactNode } from 'react';

export interface RiskFactorsBreakdownProps {
  /** List of risk factors from analysis */
  riskFactors: RiskFactor[] | null | undefined;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Get icon for factor contribution type
 */
function getContributionIcon(contribution: number): ReactNode {
  const iconClass = 'h-4 w-4';

  if (contribution > 0) {
    return <TrendingUp className={iconClass} aria-hidden="true" />;
  } else if (contribution < 0) {
    return <TrendingDown className={iconClass} aria-hidden="true" />;
  }
  return <Scale className={iconClass} aria-hidden="true" />;
}

/**
 * Get color classes for factor contribution
 */
function getContributionColors(contribution: number): {
  text: string;
  bg: string;
  border: string;
} {
  if (contribution > 10) {
    // High positive (increases risk significantly)
    return {
      text: 'text-red-400',
      bg: 'bg-red-500/20',
      border: 'border-red-500/40',
    };
  } else if (contribution > 0) {
    // Low positive (increases risk slightly)
    return {
      text: 'text-orange-400',
      bg: 'bg-orange-500/20',
      border: 'border-orange-500/40',
    };
  } else if (contribution < -10) {
    // High negative (decreases risk significantly)
    return {
      text: 'text-green-400',
      bg: 'bg-green-500/20',
      border: 'border-green-500/40',
    };
  } else if (contribution < 0) {
    // Low negative (decreases risk slightly)
    return {
      text: 'text-emerald-400',
      bg: 'bg-emerald-500/20',
      border: 'border-emerald-500/40',
    };
  }
  // Neutral
  return {
    text: 'text-gray-400',
    bg: 'bg-gray-500/20',
    border: 'border-gray-500/40',
  };
}

/**
 * Format factor name for display
 * Converts snake_case to Title Case
 */
function formatFactorName(factorName: string): string {
  return factorName
    .replace(/_/g, ' ')
    .replace(/-/g, ' ')
    .split(' ')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

/**
 * Format contribution value for display
 */
function formatContribution(contribution: number): string {
  const sign = contribution > 0 ? '+' : '';
  return `${sign}${contribution.toFixed(1)}`;
}

/**
 * Sort factors by absolute contribution magnitude (largest impact first)
 */
function sortByMagnitude(factors: RiskFactor[]): RiskFactor[] {
  return [...factors].sort((a, b) => {
    return Math.abs(b.contribution) - Math.abs(a.contribution);
  });
}

/**
 * Single factor item component
 */
function FactorItem({ factor }: { factor: RiskFactor }) {
  const colors = getContributionColors(factor.contribution);

  return (
    <div
      data-testid="risk-factor-item"
      className={clsx(
        'flex items-start gap-3 rounded-lg border p-3',
        colors.bg,
        colors.border
      )}
    >
      <div className={clsx('flex-shrink-0 mt-0.5', colors.text)}>
        {getContributionIcon(factor.contribution)}
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2 mb-1">
          <h5 className={clsx('text-sm font-medium', colors.text)}>
            {formatFactorName(factor.factor_name)}
          </h5>
          <span
            className={clsx(
              'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-bold tabular-nums',
              colors.bg,
              colors.text
            )}
          >
            {formatContribution(factor.contribution)}
          </span>
        </div>
        {factor.description && (
          <p className="text-xs text-gray-300">{factor.description}</p>
        )}
      </div>
    </div>
  );
}

/**
 * RiskFactorsBreakdown component
 *
 * Renders a list of risk factors contributing to the overall score,
 * sorted by magnitude (largest impact first).
 * Returns null if no factors are provided.
 */
export default function RiskFactorsBreakdown({
  riskFactors,
  className,
}: RiskFactorsBreakdownProps) {
  // Don't render if no factors
  if (!riskFactors || riskFactors.length === 0) {
    return null;
  }

  const sortedFactors = sortByMagnitude(riskFactors);

  // Calculate totals for summary
  const positiveTotal = riskFactors
    .filter((f) => f.contribution > 0)
    .reduce((sum, f) => sum + f.contribution, 0);
  const negativeTotal = riskFactors
    .filter((f) => f.contribution < 0)
    .reduce((sum, f) => sum + f.contribution, 0);

  return (
    <div
      data-testid="risk-factors-breakdown"
      className={clsx('space-y-3', className)}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h4 className="text-sm font-semibold uppercase tracking-wide text-gray-400">
            Risk Factors
          </h4>
          <span className="inline-flex items-center justify-center rounded-full bg-gray-600 px-2 py-0.5 text-xs font-bold text-gray-200">
            {riskFactors.length}
          </span>
        </div>

        {/* Net contribution summary */}
        <div className="flex items-center gap-3 text-xs">
          {positiveTotal > 0 && (
            <span className="flex items-center gap-1 text-red-400">
              <TrendingUp className="h-3 w-3" aria-hidden="true" />
              +{positiveTotal.toFixed(1)}
            </span>
          )}
          {negativeTotal < 0 && (
            <span className="flex items-center gap-1 text-green-400">
              <TrendingDown className="h-3 w-3" aria-hidden="true" />
              {negativeTotal.toFixed(1)}
            </span>
          )}
        </div>
      </div>

      <div className="space-y-2">
        {sortedFactors.map((factor, index) => (
          <FactorItem key={`${factor.factor_name}-${index}`} factor={factor} />
        ))}
      </div>
    </div>
  );
}
