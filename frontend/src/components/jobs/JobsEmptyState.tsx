/**
 * JobsEmptyState - Empty state display for the Jobs page
 *
 * Shown when there are no background jobs to display.
 */

import { Briefcase } from 'lucide-react';

export interface JobsEmptyStateProps {
  /** Optional custom message to display */
  message?: string;
  /** Optional custom description */
  description?: string;
}

export default function JobsEmptyState({
  message = 'No Jobs Found',
  description = 'No background jobs have been created yet. Jobs will appear here when you export data or run other background tasks.',
}: JobsEmptyStateProps) {
  return (
    <div
      className="flex min-h-[400px] items-center justify-center rounded-lg border border-gray-800 bg-[#1F1F1F]"
      data-testid="jobs-empty-state"
    >
      <div className="text-center">
        <Briefcase className="mx-auto mb-4 h-16 w-16 text-gray-600" />
        <p className="mb-2 text-lg font-semibold text-gray-300">{message}</p>
        <p className="max-w-md text-sm text-gray-500">{description}</p>
      </div>
    </div>
  );
}
