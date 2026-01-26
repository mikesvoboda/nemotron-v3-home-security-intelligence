/**
 * RiskFactorsList - Display risk score contribution factors (NEM-3603)
 *
 * Shows individual factors that contribute to the overall risk score.
 * Factors can have positive contributions (increase risk, shown in red/orange)
 * or negative contributions (decrease risk, shown in green).
 * Factors are sorted by contribution magnitude (largest impact first).
 */

import { clsx } from 'clsx';
import { TrendingDown, TrendingUp, Scale } from 'lucide-react';

import type { RiskFactor } from '../../types/risk-analysis';
import type { ReactElement, ReactNode } from 'react';

export interface RiskFactorsListProps {
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
      text: 'text-emerald-400',
      bg: 'bg-emerald-500/20',
      border: 'border-emerald-500/40',
    };
  } else if (contribution < 0) {
    // Low negative (decreases risk slightly)
    return {
      text: 'text-green-400',
      bg: 'bg-green-500/20',
      border: 'border-green-500/40',
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
 * Format contribution value for display
 */
function formatContribution(contribution: number): string {
  const sign = contribution > 0 ? '+' : '';
  return `${sign}${contribution.toFixed(1)}`;
}

/**
 * RiskFactorsList component
 */
export default function RiskFactorsList({
  riskFactors,
  className,
}: RiskFactorsListProps): ReactElement | null {
  // Don't render if no factors
  if (!riskFactors || riskFactors.length === 0) {
    return null;
  }

  // Sort factors by contribution magnitude (largest impact first)
  const sortedFactors = [...riskFactors].sort(
    (a, b) => Math.abs(b.contribution) - Math.abs(a.contribution)
  );

  // Calculate totals
  const positiveTotal = riskFactors
    .filter((f) => f.contribution > 0)
    .reduce((sum, f) => sum + f.contribution, 0);
  const negativeTotal = riskFactors
    .filter((f) => f.contribution < 0)
    .reduce((sum, f) => sum + f.contribution, 0);

  return (
    <div
      className={clsx('rounded-lg border border-gray-700 bg-gray-800/50 p-4', className)}
      data-testid="risk-factors-list"
    >
      <h4 className="mb-3 flex items-center gap-2 text-sm font-medium text-gray-200">
        <Scale className="h-4 w-4" aria-hidden="true" />
        Risk Factor Contributions
      </h4>

      {/* Factors list */}
      <div className="space-y-2">
        {sortedFactors.map((factor, index) => {
          const colors = getContributionColors(factor.contribution);
          return (
            <div
              key={`${factor.factor_name}-${index}`}
              className={clsx(
                'flex items-center justify-between rounded-md border p-2',
                colors.bg,
                colors.border
              )}
              data-testid={`risk-factor-${index}`}
            >
              <div className="flex items-center gap-2">
                <span className={colors.text}>{getContributionIcon(factor.contribution)}</span>
                <span className="text-sm text-gray-200">{factor.factor_name}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className={clsx('text-sm font-medium', colors.text)}>
                  {formatContribution(factor.contribution)}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Summary totals */}
      <div className="mt-3 flex justify-between border-t border-gray-700 pt-3 text-xs">
        <div className="flex items-center gap-1">
          <TrendingUp className="h-3 w-3 text-red-400" aria-hidden="true" />
          <span className="text-gray-400">Increasing:</span>
          <span className="font-medium text-red-400">+{positiveTotal.toFixed(1)}</span>
        </div>
        <div className="flex items-center gap-1">
          <TrendingDown className="h-3 w-3 text-emerald-400" aria-hidden="true" />
          <span className="text-gray-400">Decreasing:</span>
          <span className="font-medium text-emerald-400">{negativeTotal.toFixed(1)}</span>
        </div>
      </div>

      {/* Factor descriptions (if any) */}
      {sortedFactors.some((f) => f.description) && (
        <div className="mt-3 space-y-1 border-t border-gray-700 pt-3">
          {sortedFactors
            .filter((f) => f.description)
            .map((factor, index) => (
              <p key={`desc-${index}`} className="text-xs text-gray-400">
                <span className="font-medium text-gray-300">{factor.factor_name}:</span>{' '}
                {factor.description}
              </p>
            ))}
        </div>
      )}
    </div>
  );
}
