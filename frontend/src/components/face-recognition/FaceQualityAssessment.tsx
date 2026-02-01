/**
 * FaceQualityAssessment - Quality visualization during face enrollment
 *
 * Displays detailed face quality assessment including:
 * - Overall quality score with visual progress bar
 * - Quality factors breakdown (blur, lighting, angle, occlusion)
 * - Color-coded indicators (green/yellow/red)
 * - Recommendations for better enrollment
 * - Minimum quality threshold enforcement
 *
 * @module components/face-recognition/FaceQualityAssessment
 * @see NEM-4953 - Face Quality Assessment Visualization During Enrollment
 */

import { AlertCircle, AlertTriangle, CheckCircle2, Info } from 'lucide-react';
import { useMemo } from 'react';

import {
  computeQualityFactorsFromScore,
  getOverallRecommendation,
  getQualityStatus,
  isQualityEnrollable,
} from '../../types/faceRecognition';

import type { QualityFactor, QualityFactors } from '../../types/faceRecognition';

// ============================================================================
// Types
// ============================================================================

export interface FaceQualityAssessmentProps {
  /** Overall quality score (0-1) */
  qualityScore: number;
  /** Optional pre-computed quality factors (if not provided, will be computed from score) */
  qualityFactors?: QualityFactors;
  /** Whether to show the detailed factors breakdown */
  showFactors?: boolean;
  /** Whether to show recommendations */
  showRecommendations?: boolean;
  /** Compact mode for smaller displays */
  compact?: boolean;
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Constants
// ============================================================================

/** Quality threshold for blocking enrollment */
const QUALITY_BLOCK_THRESHOLD = 0.7;

/** Quality threshold for warning */
const QUALITY_WARN_THRESHOLD = 0.8;

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get color class for quality status.
 */
function getStatusColorClass(status: 'good' | 'fair' | 'poor'): string {
  switch (status) {
    case 'good':
      return 'bg-green-500';
    case 'fair':
      return 'bg-yellow-500';
    case 'poor':
      return 'bg-red-500';
  }
}

/**
 * Get text color class for quality status.
 */
function getStatusTextColorClass(status: 'good' | 'fair' | 'poor'): string {
  switch (status) {
    case 'good':
      return 'text-green-400';
    case 'fair':
      return 'text-yellow-400';
    case 'poor':
      return 'text-red-400';
  }
}

/**
 * Get label for quality status.
 */
function getStatusLabel(status: 'good' | 'fair' | 'poor'): string {
  switch (status) {
    case 'good':
      return 'Good';
    case 'fair':
      return 'Fair';
    case 'poor':
      return 'Poor';
  }
}

// ============================================================================
// Sub-Components
// ============================================================================

interface OverallScoreProps {
  score: number;
  status: 'good' | 'fair' | 'poor';
  compact?: boolean;
}

/**
 * Overall quality score display with progress bar.
 */
function OverallScore({ score, status, compact }: OverallScoreProps) {
  const progressWidth = Math.min(100, Math.max(0, score * 100));
  const colorClass = getStatusColorClass(status);
  const textColorClass = getStatusTextColorClass(status);

  return (
    <div data-testid="quality-overall-score">
      <div className="flex items-center justify-between text-sm mb-1">
        <span className="text-gray-400">Quality Score</span>
        <div className="flex items-center gap-2">
          <span className="text-white font-medium">{(score * 100).toFixed(0)}%</span>
          <span className={`${textColorClass} text-xs font-medium`}>
            {getStatusLabel(status)}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <div className={`flex-1 ${compact ? 'h-1.5' : 'h-2'} bg-gray-700 rounded-full overflow-hidden`}>
          <div
            data-testid="quality-progress-bar"
            className={`h-full transition-all duration-300 ${colorClass}`}
            style={{ width: `${progressWidth}%` }}
          />
        </div>
        <div
          data-testid="quality-indicator"
          className={`${compact ? 'w-2 h-2' : 'w-3 h-3'} rounded-full ${colorClass}`}
          aria-label={`Quality: ${getStatusLabel(status)}`}
        />
      </div>
    </div>
  );
}

interface FactorRowProps {
  factor: QualityFactor;
  compact?: boolean;
}

/**
 * Individual quality factor row with label, score bar, and status.
 */
function FactorRow({ factor, compact }: FactorRowProps) {
  const progressWidth = Math.min(100, Math.max(0, factor.score * 100));
  const colorClass = getStatusColorClass(factor.status);

  return (
    <div className="flex items-center gap-3" data-testid={`quality-factor-${factor.label.toLowerCase().replace(' ', '-')}`}>
      <span className={`${compact ? 'w-16' : 'w-20'} text-xs text-gray-400 truncate`}>
        {factor.label}
      </span>
      <div className={`flex-1 ${compact ? 'h-1' : 'h-1.5'} bg-gray-700 rounded-full overflow-hidden`}>
        <div
          className={`h-full transition-all duration-300 ${colorClass}`}
          style={{ width: `${progressWidth}%` }}
        />
      </div>
      <span className={`w-8 text-xs text-right ${getStatusTextColorClass(factor.status)}`}>
        {(factor.score * 100).toFixed(0)}%
      </span>
    </div>
  );
}

interface QualityWarningProps {
  score: number;
  recommendation?: string;
}

/**
 * Quality warning/error message with icon.
 */
function QualityWarning({ score, recommendation }: QualityWarningProps) {
  const isBlocked = score < QUALITY_BLOCK_THRESHOLD;
  const isFair = score >= QUALITY_BLOCK_THRESHOLD && score < QUALITY_WARN_THRESHOLD;

  if (!isBlocked && !isFair) {
    return null;
  }

  if (isBlocked) {
    return (
      <div
        className="p-3 rounded-lg bg-red-500/10 border border-red-500/30"
        data-testid="quality-blocked-warning"
      >
        <div className="flex items-start gap-2">
          <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm text-red-400 font-medium">Quality Too Low</p>
            <p className="text-xs text-red-400/80 mt-1">
              {recommendation ||
                'Image quality is below the minimum threshold (70%) required for enrollment. Please try again with better lighting and a clearer view of your face.'}
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className="p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/30"
      data-testid="quality-fair-warning"
    >
      <div className="flex items-start gap-2">
        <AlertTriangle className="w-4 h-4 text-yellow-400 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm text-yellow-400 font-medium">Moderate Quality</p>
          <p className="text-xs text-yellow-400/80 mt-1">
            {recommendation ||
              'Face recognition may be less accurate. Consider capturing a clearer image for better results.'}
          </p>
        </div>
      </div>
    </div>
  );
}

interface RecommendationsListProps {
  factors: QualityFactors;
}

/**
 * List of specific recommendations based on quality factors.
 */
function RecommendationsList({ factors }: RecommendationsListProps) {
  const recommendations = useMemo(() => {
    const recs: { factor: string; recommendation: string }[] = [];

    // Iterate over known factor keys to ensure type safety
    const factorKeys: (keyof QualityFactors)[] = ['blur', 'lighting', 'angle', 'occlusion'];
    factorKeys.forEach((key) => {
      const factor = factors[key];
      if (factor.recommendation && factor.status !== 'good') {
        recs.push({
          factor: factor.label,
          recommendation: factor.recommendation,
        });
      }
    });

    // Sort by score (worst first)
    return recs.sort((a, b) => {
      // Find the factor by label - use a safer approach
      const findScore = (label: string): number => {
        for (const key of factorKeys) {
          if (factors[key].label === label) {
            return factors[key].score;
          }
        }
        return 1;
      };
      return findScore(a.factor) - findScore(b.factor);
    });
  }, [factors]);

  if (recommendations.length === 0) {
    return null;
  }

  return (
    <div
      className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/30"
      data-testid="quality-recommendations"
    >
      <div className="flex items-start gap-2">
        <Info className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
        <div className="flex-1">
          <p className="text-sm text-blue-400 font-medium mb-2">Tips for Better Quality</p>
          <ul className="space-y-1">
            {recommendations.map(({ factor, recommendation }) => (
              <li key={factor} className="text-xs text-blue-400/80 flex items-start gap-2">
                <span className="text-blue-400/60">-</span>
                <span>
                  <strong className="text-blue-400">{factor}:</strong> {recommendation}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

interface GoodQualityMessageProps {
  score: number;
}

/**
 * Success message when quality is good.
 */
function GoodQualityMessage({ score }: GoodQualityMessageProps) {
  if (score < QUALITY_WARN_THRESHOLD) {
    return null;
  }

  return (
    <div
      className="p-3 rounded-lg bg-green-500/10 border border-green-500/30"
      data-testid="quality-good-message"
    >
      <div className="flex items-center gap-2">
        <CheckCircle2 className="w-4 h-4 text-green-400 flex-shrink-0" />
        <p className="text-sm text-green-400">
          Excellent quality! This face is suitable for enrollment.
        </p>
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * FaceQualityAssessment - Comprehensive quality visualization for face enrollment.
 *
 * Displays overall score, factor breakdown, and actionable recommendations
 * to help users capture high-quality face images for enrollment.
 */
export default function FaceQualityAssessment({
  qualityScore,
  qualityFactors,
  showFactors = true,
  showRecommendations = true,
  compact = false,
  className = '',
}: FaceQualityAssessmentProps) {
  // Compute factors if not provided
  const factors = useMemo(
    () => qualityFactors ?? computeQualityFactorsFromScore(qualityScore),
    [qualityScore, qualityFactors]
  );

  const status = getQualityStatus(qualityScore);
  const enrollable = isQualityEnrollable(qualityScore);
  const recommendation = getOverallRecommendation(qualityScore, factors);

  return (
    <div
      className={`space-y-3 ${className}`}
      data-testid="face-quality-assessment"
      data-enrollable={enrollable}
    >
      {/* Overall Score */}
      <OverallScore score={qualityScore} status={status} compact={compact} />

      {/* Quality Factors Breakdown */}
      {showFactors && (
        <div className={`space-y-2 ${compact ? 'pt-1' : 'pt-2'}`} data-testid="quality-factors">
          <p className="text-xs text-gray-500 uppercase tracking-wider">Quality Factors</p>
          <div className={`space-y-${compact ? '1' : '2'}`}>
            <FactorRow factor={factors.blur} compact={compact} />
            <FactorRow factor={factors.lighting} compact={compact} />
            <FactorRow factor={factors.angle} compact={compact} />
            <FactorRow factor={factors.occlusion} compact={compact} />
          </div>
        </div>
      )}

      {/* Warnings and Recommendations */}
      {showRecommendations && (
        <div className="space-y-2 pt-1">
          {/* Show success message for good quality */}
          <GoodQualityMessage score={qualityScore} />

          {/* Show warning for fair/poor quality */}
          <QualityWarning score={qualityScore} recommendation={recommendation} />

          {/* Show specific recommendations for non-good factors */}
          {status !== 'good' && <RecommendationsList factors={factors} />}
        </div>
      )}
    </div>
  );
}
