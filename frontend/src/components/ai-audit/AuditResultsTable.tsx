/**
 * AuditResultsTable Component
 *
 * Displays a table of recent batch audit results showing:
 * - Event ID (clickable link to event detail)
 * - Original risk score
 * - Re-evaluated risk score
 * - Delta (difference between scores)
 * - Quality score (1-5)
 * - Status badge (improved/unchanged/degraded)
 *
 * The table shows the last 10 audit results by default.
 */

import { CheckCircle, AlertCircle, MinusCircle } from 'lucide-react';
import { Link } from 'react-router-dom';

// ============================================================================
// Types
// ============================================================================

export interface AuditResult {
  /** Event ID */
  eventId: number;
  /** Original risk score from initial analysis */
  originalScore: number;
  /** Re-evaluated risk score from batch audit */
  reevaluatedScore: number;
  /** Difference between scores (negative = improvement) */
  delta: number;
  /** Quality score from self-evaluation (1-5) */
  qualityScore: number;
  /** Evaluation status */
  status: 'improved' | 'unchanged' | 'degraded';
}

export interface AuditResultsTableProps {
  /** Array of audit results to display */
  results: AuditResult[];
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get status badge styling and icon based on evaluation status
 */
function getStatusBadge(status: AuditResult['status']) {
  switch (status) {
    case 'improved':
      return {
        icon: CheckCircle,
        className: 'bg-green-900/30 text-green-400',
        label: 'Improved',
      };
    case 'degraded':
      return {
        icon: AlertCircle,
        className: 'bg-red-900/30 text-red-400',
        label: 'Degraded',
      };
    case 'unchanged':
      return {
        icon: MinusCircle,
        className: 'bg-gray-800 text-gray-400',
        label: 'Unchanged',
      };
  }
}

/**
 * Get delta styling based on value (negative = improvement = green)
 */
function getDeltaClassName(delta: number): string {
  if (delta < 0) return 'text-green-400'; // Improvement (lower risk)
  if (delta > 0) return 'text-red-400'; // Degradation (higher risk)
  return 'text-gray-400'; // Unchanged
}

// ============================================================================
// Component
// ============================================================================

/**
 * AuditResultsTable - Display recent batch audit results in tabular format
 */
export default function AuditResultsTable({ results }: AuditResultsTableProps) {
  // Empty state
  if (results.length === 0) {
    return (
      <div
        className="rounded-lg border border-gray-800 bg-[#1F1F1F] p-12 text-center"
        data-testid="audit-results-table"
      >
        <p className="text-gray-400">No audit results available yet.</p>
        <p className="mt-2 text-sm text-gray-500">Trigger a batch audit to see results here.</p>
      </div>
    );
  }

  return (
    <div
      className="rounded-lg border border-gray-800 bg-[#1F1F1F] p-6"
      data-testid="audit-results-table"
    >
      {/* Header */}
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-white">Recent Audit Results</h3>
        <p className="mt-1 text-sm text-gray-400">
          Showing {results.length} most recent {results.length === 1 ? 'result' : 'results'}
        </p>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-800 text-left text-sm font-medium text-gray-400">
              <th className="pb-3 pr-4">Event ID</th>
              <th className="pb-3 pr-4">Original Score</th>
              <th className="pb-3 pr-4">Re-evaluated</th>
              <th className="pb-3 pr-4">Delta</th>
              <th className="pb-3 pr-4">Quality</th>
              <th className="pb-3">Status</th>
            </tr>
          </thead>
          <tbody>
            {results.map((result) => {
              const statusBadge = getStatusBadge(result.status);
              const StatusIcon = statusBadge.icon;

              return (
                <tr
                  key={result.eventId}
                  className="border-b border-gray-800/50 transition-colors hover:bg-gray-800/30"
                >
                  {/* Event ID (clickable) */}
                  <td className="py-3 pr-4">
                    <Link
                      to={`/events/${result.eventId}`}
                      className="font-medium text-[#76B900] hover:text-[#8ACE00] hover:underline"
                    >
                      #{result.eventId}
                    </Link>
                  </td>

                  {/* Original Score */}
                  <td className="py-3 pr-4 text-gray-300">{result.originalScore}</td>

                  {/* Re-evaluated Score */}
                  <td className="py-3 pr-4 text-gray-300">{result.reevaluatedScore}</td>

                  {/* Delta */}
                  <td className={`py-3 pr-4 font-medium ${getDeltaClassName(result.delta)}`}>
                    {result.delta > 0 ? '+' : ''}
                    {result.delta}
                  </td>

                  {/* Quality Score */}
                  <td className="py-3 pr-4 text-gray-300">{result.qualityScore.toFixed(1)} / 5</td>

                  {/* Status Badge */}
                  <td className="py-3">
                    <span
                      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${statusBadge.className}`}
                    >
                      <StatusIcon className="h-3.5 w-3.5" />
                      {statusBadge.label}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
