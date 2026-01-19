/**
 * JobsEmptyState - Empty state display for the Jobs page
 *
 * Shown when there are no background jobs to display.
 * Features:
 * - Visual illustration with Briefcase icon in circle background
 * - Clear explanation of what creates jobs
 * - Examples of job-creating actions with icons
 */

import { Briefcase, Download, RefreshCw, Trash2 } from 'lucide-react';

export default function JobsEmptyState() {
  return (
    <div
      className="flex min-h-[400px] items-center justify-center rounded-lg border border-gray-800 bg-[#1F1F1F]"
      data-testid="jobs-empty-state"
    >
      <div className="flex flex-col items-center justify-center py-16">
        {/* Icon in circle background */}
        <div className="mb-6 flex h-32 w-32 items-center justify-center rounded-full bg-gray-800">
          <Briefcase className="h-16 w-16 text-gray-600" />
        </div>

        {/* Title */}
        <h2 className="mb-2 text-xl font-semibold text-white">No Background Jobs</h2>

        {/* Description */}
        <p className="mb-6 max-w-md text-center text-gray-400">
          Jobs appear here when you schedule exports, run bulk operations, or request AI
          re-evaluations of events.
        </p>

        {/* Example actions that create jobs */}
        <div className="grid grid-cols-1 gap-4 text-sm sm:grid-cols-3">
          <div className="flex flex-col items-center gap-2 rounded-lg border border-gray-700 bg-gray-800/50 px-4 py-3">
            <Download className="h-5 w-5 text-gray-500" />
            <span className="text-gray-400">Export Data</span>
          </div>
          <div className="flex flex-col items-center gap-2 rounded-lg border border-gray-700 bg-gray-800/50 px-4 py-3">
            <RefreshCw className="h-5 w-5 text-gray-500" />
            <span className="text-gray-400">Re-evaluate</span>
          </div>
          <div className="flex flex-col items-center gap-2 rounded-lg border border-gray-700 bg-gray-800/50 px-4 py-3">
            <Trash2 className="h-5 w-5 text-gray-500" />
            <span className="text-gray-400">Bulk Delete</span>
          </div>
        </div>
      </div>
    </div>
  );
}
