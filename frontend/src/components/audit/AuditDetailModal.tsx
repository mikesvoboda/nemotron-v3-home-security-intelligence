import { Dialog, Transition } from '@headlessui/react';
import { CheckCircle, Clock, Globe, User, X, XCircle } from 'lucide-react';
import { Fragment, useEffect } from 'react';

import type { AuditEntry } from './AuditTable';

export interface AuditDetailModalProps {
  log: AuditEntry | null;
  isOpen: boolean;
  onClose: () => void;
}

/**
 * AuditDetailModal component displays full audit log entry details in a modal overlay
 */
export default function AuditDetailModal({ log, isOpen, onClose }: AuditDetailModalProps) {
  // Handle escape key to close modal
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);

  if (!log) {
    return null;
  }

  // Convert ISO timestamp to readable format
  const formatTimestamp = (isoString: string): string => {
    try {
      const date = new Date(isoString);
      return date.toLocaleString('en-US', {
        month: 'long',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        second: '2-digit',
        hour12: true,
      });
    } catch {
      return isoString;
    }
  };

  // Format action name for display
  const formatAction = (action: string): string => {
    return action
      .split('_')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(' ');
  };

  // Get status badge styling
  const getStatusBadge = (status: string) => {
    const baseClasses =
      'inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold';

    switch (status.toLowerCase()) {
      case 'success':
        return {
          className: `${baseClasses} bg-green-900/30 text-green-400`,
          icon: <CheckCircle className="h-3.5 w-3.5" />,
        };
      case 'failure':
      case 'failed':
      case 'error':
        return {
          className: `${baseClasses} bg-red-900/30 text-red-400`,
          icon: <XCircle className="h-3.5 w-3.5" />,
        };
      default:
        return {
          className: `${baseClasses} bg-gray-800 text-gray-300`,
          icon: null,
        };
    }
  };

  const statusBadge = getStatusBadge(log.status);

  // Pretty-print JSON data
  const formatJSON = (data: Record<string, unknown> | null | undefined): string => {
    if (!data) return 'null';
    try {
      return JSON.stringify(data, null, 2);
    } catch {
      return String(data);
    }
  };

  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={onClose}>
        {/* Dark backdrop */}
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

        {/* Modal content */}
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
              <Dialog.Panel className="w-full max-w-2xl transform overflow-hidden rounded-xl border border-gray-800 bg-[#1A1A1A] shadow-2xl transition-all">
                {/* Header */}
                <div className="flex items-start justify-between border-b border-gray-800 p-6">
                  <div className="flex-1">
                    <Dialog.Title
                      as="h2"
                      className="text-2xl font-bold text-white"
                      id="audit-detail-title"
                    >
                      {formatAction(log.action)}
                    </Dialog.Title>
                    <div className="mt-2 flex items-center gap-2 text-sm text-gray-400">
                      <Clock className="h-4 w-4" />
                      <span>{formatTimestamp(log.timestamp)}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={statusBadge.className}>
                      {statusBadge.icon}
                      {log.status}
                    </span>
                    <button
                      onClick={onClose}
                      className="rounded-lg p-2 text-gray-400 transition-colors hover:bg-gray-800 hover:text-white"
                      aria-label="Close modal"
                    >
                      <X className="h-6 w-6" />
                    </button>
                  </div>
                </div>

                {/* Content */}
                <div className="max-h-[calc(100vh-200px)] overflow-y-auto p-6">
                  {/* Actor and Resource Info */}
                  <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
                    {/* Actor Card */}
                    <div className="rounded-lg border border-gray-800 bg-black/20 p-4">
                      <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-gray-400">
                        <User className="h-4 w-4" />
                        Actor
                      </div>
                      <p className="text-lg font-medium text-[#76B900]">{log.actor}</p>
                    </div>

                    {/* Resource Card */}
                    <div className="rounded-lg border border-gray-800 bg-black/20 p-4">
                      <div className="mb-2 text-sm font-semibold text-gray-400">Resource</div>
                      <p className="font-mono text-sm text-gray-300">
                        {log.resource_type}
                        {log.resource_id && (
                          <span className="text-gray-500"> / {log.resource_id}</span>
                        )}
                      </p>
                    </div>
                  </div>

                  {/* Audit Log Metadata */}
                  <div className="mb-6 rounded-lg border border-gray-800 bg-black/20 p-4">
                    <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-400">
                      Entry Details
                    </h3>
                    <dl className="grid gap-2 text-sm">
                      <div className="flex justify-between">
                        <dt className="text-gray-400">Audit ID</dt>
                        <dd className="font-mono text-gray-300">{log.id}</dd>
                      </div>
                      <div className="flex justify-between">
                        <dt className="text-gray-400">Action</dt>
                        <dd className="text-gray-300">{log.action}</dd>
                      </div>
                      <div className="flex justify-between">
                        <dt className="text-gray-400">Status</dt>
                        <dd className="text-gray-300">{log.status}</dd>
                      </div>
                      {log.ip_address && (
                        <div className="flex justify-between">
                          <dt className="flex items-center gap-1.5 text-gray-400">
                            <Globe className="h-3.5 w-3.5" />
                            IP Address
                          </dt>
                          <dd className="font-mono text-gray-300">{log.ip_address}</dd>
                        </div>
                      )}
                    </dl>
                  </div>

                  {/* User Agent */}
                  {log.user_agent && (
                    <div className="mb-6">
                      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-400">
                        User Agent
                      </h3>
                      <div className="rounded-lg bg-black/30 p-4">
                        <p className="break-all font-mono text-xs text-gray-300">{log.user_agent}</p>
                      </div>
                    </div>
                  )}

                  {/* Details JSON Data */}
                  {log.details && Object.keys(log.details).length > 0 && (
                    <div className="mb-6">
                      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-400">
                        Additional Details
                      </h3>
                      <div className="rounded-lg bg-[#76B900]/10 p-4">
                        <pre className="overflow-x-auto font-mono text-xs leading-relaxed text-gray-300">
                          {formatJSON(log.details)}
                        </pre>
                      </div>
                    </div>
                  )}
                </div>

                {/* Footer */}
                <div className="flex items-center justify-end border-t border-gray-800 bg-black/20 p-6">
                  <button
                    onClick={onClose}
                    className="rounded-lg bg-gray-800 px-6 py-2 text-sm font-semibold text-white transition-colors hover:bg-gray-700"
                    aria-label="Close modal"
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
