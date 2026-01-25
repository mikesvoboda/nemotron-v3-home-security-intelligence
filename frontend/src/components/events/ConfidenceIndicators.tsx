/**
 * ConfidenceIndicators - Display confidence factors from risk analysis (NEM-3601)
 *
 * Shows indicators for factors affecting the confidence of the risk analysis:
 * - Detection quality (good/fair/poor)
 * - Weather impact (none/minor/significant)
 * - Enrichment coverage (full/partial/minimal)
 */

import { clsx } from 'clsx';
import { CheckCircle, AlertCircle, XCircle, Camera, Cloud, Database } from 'lucide-react';

import { CONFIDENCE_FACTOR_CONFIG } from '../../types/risk-analysis';

import type { ConfidenceFactors } from '../../types/risk-analysis';
import type { ReactNode } from 'react';

export interface ConfidenceIndicatorsProps {
  /** Confidence factors from risk analysis */
  confidenceFactors: ConfidenceFactors | null | undefined;
  /** Additional CSS classes */
  className?: string;
  /** Display mode: 'inline' for compact or 'detailed' for full */
  mode?: 'inline' | 'detailed';
}

type IndicatorValue = 'good' | 'none' | 'full' | 'fair' | 'minor' | 'partial' | 'poor' | 'significant' | 'minimal';

/**
 * Get icon for indicator value
 */
function getIndicatorIcon(value: IndicatorValue): ReactNode {
  const iconClass = 'h-3.5 w-3.5';

  switch (value) {
    case 'good':
    case 'none':
    case 'full':
      return <CheckCircle className={iconClass} />;
    case 'fair':
    case 'minor':
    case 'partial':
      return <AlertCircle className={iconClass} />;
    case 'poor':
    case 'significant':
    case 'minimal':
      return <XCircle className={iconClass} />;
    default:
      return <AlertCircle className={iconClass} />;
  }
}

/**
 * Get category icon
 */
function getCategoryIcon(category: string): ReactNode {
  const iconClass = 'h-4 w-4';

  switch (category) {
    case 'detection_quality':
      return <Camera className={iconClass} />;
    case 'weather_impact':
      return <Cloud className={iconClass} />;
    case 'enrichment_coverage':
      return <Database className={iconClass} />;
    default:
      return <Database className={iconClass} />;
  }
}

/**
 * Get display config for a value
 */
function getValueConfig(
  category: keyof typeof CONFIDENCE_FACTOR_CONFIG,
  value: string
): { label: string; color: string } | null {
  const categoryConfig = CONFIDENCE_FACTOR_CONFIG[category];
  if (!categoryConfig) return null;

  const values = categoryConfig.values as Record<string, { label: string; color: string }>;
  return values[value] || null;
}

/**
 * Single indicator component
 */
function Indicator({
  category,
  value,
  mode,
}: {
  category: keyof typeof CONFIDENCE_FACTOR_CONFIG;
  value: IndicatorValue;
  mode: 'inline' | 'detailed';
}) {
  const categoryConfig = CONFIDENCE_FACTOR_CONFIG[category];
  const valueConfig = getValueConfig(category, value);

  if (!valueConfig) {
    return null;
  }

  if (mode === 'inline') {
    return (
      <div
        data-testid="confidence-indicator"
        className={clsx(
          'flex items-center gap-1 rounded-md border border-gray-700 bg-gray-800/50 px-2 py-1',
          valueConfig.color
        )}
        title={`${categoryConfig.label}: ${valueConfig.label}`}
      >
        {getCategoryIcon(category)}
        <span className="text-xs">{valueConfig.label}</span>
      </div>
    );
  }

  return (
    <div
      data-testid="confidence-indicator"
      className="flex items-center justify-between py-1.5"
    >
      <div className="flex items-center gap-2 text-gray-400">
        {getCategoryIcon(category)}
        <span className="text-xs">{categoryConfig.label}</span>
      </div>
      <div className={clsx('flex items-center gap-1', valueConfig.color)}>
        {getIndicatorIcon(value)}
        <span className="text-xs font-medium">{valueConfig.label}</span>
      </div>
    </div>
  );
}

/**
 * ConfidenceIndicators component
 *
 * Renders indicators showing the reliability of the risk analysis.
 * Returns null if no confidence factors are provided.
 */
export default function ConfidenceIndicators({
  confidenceFactors,
  className,
  mode = 'detailed',
}: ConfidenceIndicatorsProps) {
  // Don't render if no factors
  if (!confidenceFactors) {
    return null;
  }

  if (mode === 'inline') {
    return (
      <div
        data-testid="confidence-indicators"
        className={clsx('flex flex-wrap items-center gap-2', className)}
      >
        <Indicator
          category="detection_quality"
          value={confidenceFactors.detection_quality}
          mode={mode}
        />
        <Indicator
          category="weather_impact"
          value={confidenceFactors.weather_impact}
          mode={mode}
        />
        <Indicator
          category="enrichment_coverage"
          value={confidenceFactors.enrichment_coverage}
          mode={mode}
        />
      </div>
    );
  }

  return (
    <div
      data-testid="confidence-indicators"
      className={clsx('rounded-lg border border-gray-800 bg-black/20 p-3', className)}
    >
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
        Analysis Confidence
      </h4>

      <div className="divide-y divide-gray-800">
        <Indicator
          category="detection_quality"
          value={confidenceFactors.detection_quality}
          mode={mode}
        />
        <Indicator
          category="weather_impact"
          value={confidenceFactors.weather_impact}
          mode={mode}
        />
        <Indicator
          category="enrichment_coverage"
          value={confidenceFactors.enrichment_coverage}
          mode={mode}
        />
      </div>
    </div>
  );
}
