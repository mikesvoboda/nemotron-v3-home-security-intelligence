/**
 * DetectionQualityBadge - Color-coded confidence quality tier badge
 *
 * Displays a prominent badge indicating the detection confidence quality tier:
 * - EXCELLENT (>=0.9): Green badge
 * - GOOD (>=0.75): Blue badge
 * - MODERATE (>=0.5): Yellow badge
 * - MARGINAL (<0.5): Red badge
 *
 * Used inline per detection in the EventDetailModal to give quick visual
 * feedback on detection reliability.
 */

import { clsx } from 'clsx';
import { Shield, ShieldAlert, ShieldCheck, ShieldQuestion } from 'lucide-react';

// ============================================================================
// Types
// ============================================================================

export type QualityTier = 'EXCELLENT' | 'GOOD' | 'MODERATE' | 'MARGINAL';

export interface DetectionQualityBadgeProps {
  /** Detection confidence score (0-1) */
  confidence: number;
  /** Size variant */
  size?: 'sm' | 'md';
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Determine the quality tier from a confidence score.
 */
export function getQualityTier(confidence: number): QualityTier {
  if (confidence >= 0.9) return 'EXCELLENT';
  if (confidence >= 0.75) return 'GOOD';
  if (confidence >= 0.5) return 'MODERATE';
  return 'MARGINAL';
}

/**
 * Get style classes for a quality tier.
 */
function getTierStyles(tier: QualityTier): { bg: string; border: string; text: string } {
  switch (tier) {
    case 'EXCELLENT':
      return {
        bg: 'bg-green-500/15',
        border: 'border-green-500/40',
        text: 'text-green-400',
      };
    case 'GOOD':
      return {
        bg: 'bg-blue-500/15',
        border: 'border-blue-500/40',
        text: 'text-blue-400',
      };
    case 'MODERATE':
      return {
        bg: 'bg-yellow-500/15',
        border: 'border-yellow-500/40',
        text: 'text-yellow-400',
      };
    case 'MARGINAL':
      return {
        bg: 'bg-red-500/15',
        border: 'border-red-500/40',
        text: 'text-red-400',
      };
  }
}

/**
 * Get the icon for a quality tier.
 */
function getTierIcon(tier: QualityTier, sizeClass: string) {
  switch (tier) {
    case 'EXCELLENT':
      return <ShieldCheck className={sizeClass} />;
    case 'GOOD':
      return <Shield className={sizeClass} />;
    case 'MODERATE':
      return <ShieldAlert className={sizeClass} />;
    case 'MARGINAL':
      return <ShieldQuestion className={sizeClass} />;
  }
}

// ============================================================================
// Component
// ============================================================================

/**
 * DetectionQualityBadge - Displays a color-coded badge for detection confidence quality.
 */
export default function DetectionQualityBadge({
  confidence,
  size = 'sm',
  className,
}: DetectionQualityBadgeProps) {
  const tier = getQualityTier(confidence);
  const styles = getTierStyles(tier);
  const iconSize = size === 'sm' ? 'h-3 w-3' : 'h-3.5 w-3.5';
  const paddingClass = size === 'sm' ? 'px-1.5 py-0.5 text-xs gap-1' : 'px-2 py-0.5 text-xs gap-1.5';

  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-md border font-semibold',
        styles.bg,
        styles.border,
        styles.text,
        paddingClass,
        className
      )}
      title={`Quality: ${tier} (${Math.round(confidence * 100)}%)`}
      data-testid="detection-quality-badge"
      data-tier={tier}
    >
      {getTierIcon(tier, iconSize)}
      {tier}
    </span>
  );
}
