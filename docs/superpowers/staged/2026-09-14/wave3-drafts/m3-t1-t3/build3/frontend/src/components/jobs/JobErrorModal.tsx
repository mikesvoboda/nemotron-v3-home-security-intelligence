/**
 * JobErrorModal - Modal for displaying full error traceback
 *
 * Displays the complete error traceback for a failed job in a
 * scrollable, copy-friendly format.
 *
 * UI Design:
 * ┌─────────────────────────────────────────────────────────────────┐
 * │ Error Details                                          [X]     │
 * ├─────────────────────────────────────────────────────────────────┤
 * │ Job: Export #142                                               │
 * │ Failed at: Jan 15, 2024 10:32:00 AM                            │
 * ├─────────────────────────────────────────────────────────────────┤
 * │ ┌─────────────────────────────────────────────────────────────┐│
 * ││ Traceback (most recent call last):                          ││
 * ││   File "/app/services/export.py", line 142, in export_data  ││
 * ││     result = process_batch(batch)                           ││
 * ││   File "/app/services/export.py", line 89, in process_batch ││
 * ││     raise ExportError("Connection timeout")                 ││
 * ││ ExportError: Connection timeout                             ││
 * │└─────────────────────────────────────────────────────────────┘│
 * ├─────────────────────────────────────────────────────────────────┤
 * │                               [Copy to Clipboard] [Close]      │
 * └─────────────────────────────────────────────────────────────────┘
 *
 * @module components/jobs/JobErrorModal
 * @see NEM-3593
 */

import { Dialog, Transition } from '@headlessui/react';
import { AlertCircle, X, Copy, Check, Clock, Briefcase } from 'lucide-react';
import { Fragment, useState, useCallback } from 'react';

export interface JobErrorModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback to close the modal */
  onClose: () => void;
  /** Job ID for display */
  jobId: string;
  /** Job type for display */
  jobType: string;
  /** Error message (short description) */
  errorMessage: string;
  /** Full error traceback */
  errorTraceback?: string | null;
  /** When the error occurred (ISO timestamp) */
  failedAt?: string | null;
  /** Retry attempt number when error occurred */
  attemptNumber?: number;
}

/**
 * Format timestamp for display.
 */
function formatTimestamp(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  });
}

/**
 * Format job type for display.
 */
function formatJobType(jobType: string): string {
  return jobType.charAt(0).toUpperCase() + jobType.slice(1);
}

/**
 * Extract short ID from job_id (e.g., "export-142" -> "#142").
 */
function formatJobId(jobId: string): string {
  const match = jobId.match(/(\d+)$/);
  if (match) {
    return `#${match[1]}`;
  }
  // For UUIDs, show first 8 characters
  if (jobId.length > 20) {
    return jobId.substring(0, 8) + '...';
  }
  return jobId;
}

/**
 * JobErrorModal displays the full error details and traceback for a failed job.
 */
export default function JobErrorModal({
  isOpen,
  onClose,
  jobId,
  jobType,
  errorMessage,
  errorTraceback,
  failedAt,
  attemptNumber,
}: JobErrorModalProps) {
  const [copied, setCopied] = useState(false);

  // Full content to copy includes job info and error details
  const fullErrorContent = [
    `Job: ${formatJobType(jobType)} ${formatJobId(jobId)}`,
    failedAt ? `Failed at: ${formatTimestamp(failedAt)}` : null,
    attemptNumber ? `Attempt: ${attemptNumber}` : null,
    '',
    'Error Message:',
    errorMessage,
    '',
    errorTraceback ? 'Traceback:' : null,
    errorTraceback,
  ]
    .filter(Boolean)
    .join('\n');

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(fullErrorContent);
      setCopied(true);
      // Reset copied state after 2 seconds
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy to clipboard:', err);
    }
  }, [fullErrorContent]);

  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={onClose}>
        {/* Backdrop */}
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/75" aria-hidden="true" />
        </Transition.Child>

        {/* Modal */}
        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <Dialog.Panel
                data-testid="job-error-modal"
                className="w-full max-w-3xl transform overflow-hidden rounded-xl border border-gray-800 bg-[#1A1A1A] shadow-2xl transition-all"
              >
                {/* Header */}
                <div className="flex items-center justify-between border-b border-gray-800 px-6 py-4">
                  <div className="flex items-center gap-3">
                    <div className="rounded-full bg-red-500/10 p-2">
                      <AlertCircle className="h-5 w-5 text-red-400" />
                    </div>
                    <Dialog.Title as="h2" className="text-lg font-semibold text-white">
                      Error Details
                    </Dialog.Title>
                  </div>
                  <button
                    onClick={onClose}
                    className="rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-gray-800 hover:text-white"
                    aria-label="Close modal"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>

                {/* Job Info */}
                <div className="border-b border-gray-800 px-6 py-4">
                  <div className="flex flex-wrap items-center gap-4 text-sm">
                    <div className="flex items-center gap-2">
                      <Briefcase className="h-4 w-4 text-gray-500" />
                      <span className="text-gray-400">Job:</span>
                      <span className="font-medium text-white">
                        {formatJobType(jobType)} {formatJobId(jobId)}
                      </span>
                    </div>
                    {failedAt && (
                      <div className="flex items-center gap-2">
                        <Clock className="h-4 w-4 text-gray-500" />
                        <span className="text-gray-400">Failed at:</span>
                        <span className="text-gray-300">{formatTimestamp(failedAt)}</span>
                      </div>
                    )}
                    {attemptNumber && (
                      <div className="flex items-center gap-2">
                        <span className="text-gray-400">Attempt:</span>
                        <span className="rounded-full bg-red-500/10 px-2 py-0.5 text-xs font-medium text-red-400">
                          {attemptNumber}
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Error Content */}
                <div className="px-6 py-4">
                  {/* Error Message */}
                  <div className="mb-4">
                    <h3 className="mb-2 text-sm font-medium text-gray-400">Error Message</h3>
                    <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4">
                      <p className="text-sm text-red-300">{errorMessage}</p>
                    </div>
                  </div>

                  {/* Traceback */}
                  {errorTraceback && (
                    <div>
                      <h3 className="mb-2 text-sm font-medium text-gray-400">Traceback</h3>
                      <div className="max-h-80 overflow-auto rounded-lg bg-gray-900 p-4">
                        <pre
                          data-testid="error-traceback"
                          className="whitespace-pre-wrap font-mono text-xs text-gray-300"
                        >
                          {errorTraceback}
                        </pre>
                      </div>
                    </div>
                  )}
                </div>

                {/* Footer */}
                <div className="flex items-center justify-end gap-3 border-t border-gray-800 px-6 py-4">
                  <button
                    onClick={() => void handleCopy()}
                    data-testid="copy-button"
                    className="flex items-center gap-2 rounded-lg border border-gray-700 bg-gray-800 px-4 py-2 text-sm font-medium text-gray-300 transition-colors hover:bg-gray-700"
                  >
                    {copied ? (
                      <>
                        <Check className="h-4 w-4 text-green-400" />
                        <span className="text-green-400">Copied!</span>
                      </>
                    ) : (
                      <>
                        <Copy className="h-4 w-4" />
                        Copy to Clipboard
                      </>
                    )}
                  </button>
                  <button
                    onClick={onClose}
                    className="rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700"
                  >
                    Close
                  </button>
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
}
