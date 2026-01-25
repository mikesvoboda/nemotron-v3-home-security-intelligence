/**
 * RecommendedActionCard - Display recommended action from risk analysis (NEM-3601)
 *
 * Shows the LLM-suggested action to take based on the risk analysis.
 * Displayed prominently when present to guide security response.
 */

import { clsx } from 'clsx';
import { AlertCircle, ArrowRight, CheckCircle } from 'lucide-react';

export interface RecommendedActionCardProps {
  /** Recommended action text from LLM analysis */
  recommendedAction: string | null | undefined;
  /** Additional CSS classes */
  className?: string;
  /** Whether the event has been reviewed (affects styling) */
  isReviewed?: boolean;
}

/**
 * RecommendedActionCard component
 *
 * Renders a card displaying the recommended action from risk analysis.
 * Returns null if no recommended action is provided.
 */
export default function RecommendedActionCard({
  recommendedAction,
  className,
  isReviewed = false,
}: RecommendedActionCardProps) {
  // Don't render if no action
  if (!recommendedAction) {
    return null;
  }

  return (
    <div
      data-testid="recommended-action-card"
      className={clsx(
        'rounded-lg border p-4',
        isReviewed
          ? 'border-gray-600 bg-gray-800/50'
          : 'border-amber-500/40 bg-amber-500/10',
        className
      )}
    >
      <div className="flex items-start gap-3">
        <div
          className={clsx(
            'flex-shrink-0 rounded-full p-1.5',
            isReviewed ? 'bg-gray-700 text-gray-400' : 'bg-amber-500/20 text-amber-400'
          )}
        >
          {isReviewed ? (
            <CheckCircle className="h-5 w-5" />
          ) : (
            <AlertCircle className="h-5 w-5" />
          )}
        </div>

        <div className="flex-1 min-w-0">
          <h4
            className={clsx(
              'text-sm font-semibold uppercase tracking-wide mb-1',
              isReviewed ? 'text-gray-400' : 'text-amber-400'
            )}
          >
            Recommended Action
          </h4>
          <p
            className={clsx(
              'text-sm',
              isReviewed ? 'text-gray-300' : 'text-white'
            )}
          >
            {recommendedAction}
          </p>
        </div>

        {!isReviewed && (
          <ArrowRight className="h-5 w-5 flex-shrink-0 text-amber-400" />
        )}
      </div>
    </div>
  );
}
