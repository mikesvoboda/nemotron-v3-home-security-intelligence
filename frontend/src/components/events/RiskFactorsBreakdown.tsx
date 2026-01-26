/**
 * RiskFactorsBreakdown - Collapsible risk analysis breakdown component (NEM-3671)
 *
 * Displays a comprehensive breakdown of risk factors that contributed to the
 * risk score calculation. Shows entities, flags, confidence factors, and
 * recommended actions in a collapsible accordion view.
 */

import { clsx } from 'clsx';
import { ChevronDown, ChevronUp, Scale, TrendingUp } from 'lucide-react';
import { useState } from 'react';

import ConfidenceIndicators from './ConfidenceIndicators';
import EntityThreatCards from './EntityThreatCards';
import RecommendedActionCard from './RecommendedActionCard';
import RiskFlagsPanel from './RiskFlagsPanel';
import { getRiskLevel, getRiskTextClass, getRiskBgClass } from '../../utils/risk';

import type { RiskEntity, RiskFlag, ConfidenceFactors } from '../../types/risk-analysis';

/**
 * Contribution factor representing how much each category affects the risk score
 */
interface ContributionFactor {
  /** Category label */
  label: string;
  /** Weight/contribution percentage (0-100) */
  weight: number;
  /** Color class for the factor */
  colorClass: string;
  /** Background color class */
  bgColorClass: string;
}

export interface RiskFactorsBreakdownProps {
  /** Risk score (0-100) */
  riskScore: number;
  /** AI reasoning text */
  reasoning?: string | null;
  /** Entities identified in analysis */
  entities?: RiskEntity[] | null;
  /** Risk flags raised during analysis */
  flags?: RiskFlag[] | null;
  /** Recommended action from analysis */
  recommendedAction?: string | null;
  /** Confidence factors affecting analysis reliability */
  confidenceFactors?: ConfidenceFactors | null;
  /** Whether the event has been reviewed */
  isReviewed?: boolean;
  /** Additional CSS classes */
  className?: string;
  /** Default expanded state */
  defaultExpanded?: boolean;
}

/**
 * Calculate contribution weights based on available data
 */
function calculateContributions(
  entities: RiskEntity[] | null | undefined,
  flags: RiskFlag[] | null | undefined,
  confidenceFactors: ConfidenceFactors | null | undefined
): ContributionFactor[] {
  const contributions: ContributionFactor[] = [];

  // Entities contribution (based on count and threat levels)
  if (entities && entities.length > 0) {
    const hasHighThreat = entities.some((e) => e.threat_level === 'high');
    const hasMediumThreat = entities.some((e) => e.threat_level === 'medium');

    let entityWeight = 20 + entities.length * 5; // Base 20 + 5 per entity
    if (hasHighThreat) entityWeight += 15;
    if (hasMediumThreat) entityWeight += 10;
    entityWeight = Math.min(entityWeight, 40); // Cap at 40

    contributions.push({
      label: 'Entities',
      weight: entityWeight,
      colorClass: hasHighThreat ? 'text-red-400' : hasMediumThreat ? 'text-yellow-400' : 'text-green-400',
      bgColorClass: hasHighThreat ? 'bg-red-500' : hasMediumThreat ? 'bg-yellow-500' : 'bg-green-500',
    });
  }

  // Flags contribution (based on count and severities)
  if (flags && flags.length > 0) {
    const hasCritical = flags.some((f) => f.severity === 'critical');
    const hasAlert = flags.some((f) => f.severity === 'alert');

    let flagWeight = 15 + flags.length * 10; // Base 15 + 10 per flag
    if (hasCritical) flagWeight += 20;
    if (hasAlert) flagWeight += 10;
    flagWeight = Math.min(flagWeight, 50); // Cap at 50

    contributions.push({
      label: 'Risk Flags',
      weight: flagWeight,
      colorClass: hasCritical ? 'text-red-400' : hasAlert ? 'text-orange-400' : 'text-yellow-400',
      bgColorClass: hasCritical ? 'bg-red-500' : hasAlert ? 'bg-orange-500' : 'bg-yellow-500',
    });
  }

  // Confidence factors contribution (inverse - poor quality increases perceived risk)
  if (confidenceFactors) {
    let qualityWeight = 10; // Base contribution

    if (confidenceFactors.detection_quality === 'poor') qualityWeight += 10;
    else if (confidenceFactors.detection_quality === 'fair') qualityWeight += 5;

    if (confidenceFactors.weather_impact === 'significant') qualityWeight += 8;
    else if (confidenceFactors.weather_impact === 'minor') qualityWeight += 4;

    if (confidenceFactors.enrichment_coverage === 'minimal') qualityWeight += 7;
    else if (confidenceFactors.enrichment_coverage === 'partial') qualityWeight += 3;

    const isGood =
      confidenceFactors.detection_quality === 'good' &&
      confidenceFactors.weather_impact === 'none' &&
      confidenceFactors.enrichment_coverage === 'full';

    contributions.push({
      label: 'Analysis Quality',
      weight: qualityWeight,
      colorClass: isGood ? 'text-green-400' : 'text-yellow-400',
      bgColorClass: isGood ? 'bg-green-500' : 'bg-yellow-500',
    });
  }

  // Normalize weights to sum to 100
  const totalWeight = contributions.reduce((sum, c) => sum + c.weight, 0);
  if (totalWeight > 0) {
    contributions.forEach((c) => {
      c.weight = Math.round((c.weight / totalWeight) * 100);
    });
  }

  return contributions;
}

/**
 * RiskFactorsBreakdown component
 *
 * Renders a collapsible breakdown of all risk factors contributing to the
 * event's risk score. Includes entities, flags, confidence indicators,
 * and recommended actions.
 */
export default function RiskFactorsBreakdown({
  riskScore,
  reasoning,
  entities,
  flags,
  recommendedAction,
  confidenceFactors,
  isReviewed = false,
  className,
  defaultExpanded = false,
}: RiskFactorsBreakdownProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  // Check if there's any data to display
  const hasEntities = entities && entities.length > 0;
  const hasFlags = flags && flags.length > 0;
  const hasConfidenceFactors = confidenceFactors !== null && confidenceFactors !== undefined;
  const hasRecommendedAction = recommendedAction !== null && recommendedAction !== undefined;
  const hasReasoning = reasoning !== null && reasoning !== undefined && reasoning.trim() !== '';

  // If no data to display, render nothing
  if (!hasEntities && !hasFlags && !hasConfidenceFactors && !hasRecommendedAction && !hasReasoning) {
    return null;
  }

  const riskLevel = getRiskLevel(riskScore);
  const contributions = calculateContributions(entities, flags, confidenceFactors);

  // Count total contributing factors
  const totalFactors = (hasEntities ? (entities?.length ?? 0) : 0) + (hasFlags ? (flags?.length ?? 0) : 0);

  return (
    <div
      data-testid="risk-factors-breakdown"
      className={clsx('rounded-lg border border-gray-800 bg-black/30', className)}
    >
      {/* Collapsible Header */}
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex w-full items-center justify-between p-4 text-left transition-colors hover:bg-white/5"
        aria-expanded={isExpanded}
        aria-controls="risk-factors-content"
        data-testid="risk-factors-toggle"
      >
        <div className="flex items-center gap-3">
          <div
            className={clsx(
              'flex h-8 w-8 items-center justify-center rounded-lg',
              getRiskBgClass(riskLevel) + '/20'
            )}
          >
            <Scale className={clsx('h-4 w-4', getRiskTextClass(riskLevel))} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">
              Risk Factors Breakdown
            </h3>
            <p className="text-xs text-gray-400">
              {totalFactors > 0
                ? `${totalFactors} factor${totalFactors !== 1 ? 's' : ''} contributing to risk score`
                : 'Analysis details and confidence factors'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Quick contribution summary when collapsed */}
          {!isExpanded && contributions.length > 0 && (
            <div className="hidden items-center gap-1 sm:flex" data-testid="contribution-pills">
              {contributions.slice(0, 3).map((c) => (
                <span
                  key={c.label}
                  className={clsx(
                    'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
                    c.bgColorClass + '/20',
                    c.colorClass
                  )}
                >
                  {c.label}: {c.weight}%
                </span>
              ))}
            </div>
          )}

          {isExpanded ? (
            <ChevronUp className="h-5 w-5 text-gray-400" />
          ) : (
            <ChevronDown className="h-5 w-5 text-gray-400" />
          )}
        </div>
      </button>

      {/* Expandable Content */}
      {isExpanded && (
        <div
          id="risk-factors-content"
          className="border-t border-gray-800 p-4"
          data-testid="risk-factors-content"
        >
          {/* Contribution Bars */}
          {contributions.length > 0 && (
            <div className="mb-6">
              <div className="mb-2 flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-gray-400" />
                <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                  Risk Contribution
                </h4>
              </div>

              <div className="space-y-2" data-testid="contribution-bars">
                {contributions.map((contribution) => (
                  <div key={contribution.label} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-gray-300">{contribution.label}</span>
                      <span className={contribution.colorClass}>{contribution.weight}%</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-gray-800">
                      <div
                        className={clsx('h-full rounded-full transition-all duration-300', contribution.bgColorClass)}
                        style={{ width: `${contribution.weight}%` }}
                        data-testid={`contribution-bar-${contribution.label.toLowerCase().replace(/\s/g, '-')}`}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Recommended Action (most prominent) */}
          {hasRecommendedAction && (
            <div className="mb-4">
              <RecommendedActionCard
                recommendedAction={recommendedAction}
                isReviewed={isReviewed}
              />
            </div>
          )}

          {/* AI Reasoning */}
          {hasReasoning && (
            <div className="mb-4" data-testid="reasoning-section">
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-400">
                AI Reasoning
              </h4>
              <div className="rounded-lg bg-[#76B900]/10 p-3">
                <p className="text-sm leading-relaxed text-gray-300">{reasoning}</p>
              </div>
            </div>
          )}

          {/* Risk Flags */}
          {hasFlags && (
            <div className="mb-4">
              <RiskFlagsPanel flags={flags} />
            </div>
          )}

          {/* Identified Entities */}
          {hasEntities && (
            <div className="mb-4">
              <EntityThreatCards entities={entities} />
            </div>
          )}

          {/* Confidence Indicators */}
          {hasConfidenceFactors && (
            <div>
              <ConfidenceIndicators confidenceFactors={confidenceFactors} mode="detailed" />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
