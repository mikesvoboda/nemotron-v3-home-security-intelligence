import { Dialog, Transition } from '@headlessui/react';
import { AlertCircle, Clock, Code2, Info, X, XCircle } from 'lucide-react';
import { Fragment, useEffect } from 'react';

export type LogLevel = 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';

export interface LogEntry {
  id: number;
  timestamp: string;
  level: LogLevel;
  component: string;
  message: string;
  camera_id?: string | null;
  event_id?: number | null;
  request_id?: string | null;
  detection_id?: number | null;
  duration_ms?: number | null;
  extra?: Record<string, unknown> | null;
  source: string;
  user_agent?: string | null;
}

export interface LogDetailModalProps {
  log: LogEntry | null;
  isOpen: boolean;
  onClose: () => void;
}

/**
 * LogDetailModal component displays full log entry details in a modal overlay
 */
export default function LogDetailModal({ log, isOpen, onClose }: LogDetailModalProps) {
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

  // Get log level styling
  const getLevelBadge = (level: LogLevel) => {
    const baseClasses = 'inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold';

    switch (level) {
      case 'DEBUG':
        return {
          className: `${baseClasses} bg-gray-800 text-gray-300`,
          icon: <Code2 className="h-3.5 w-3.5" />,
        };
      case 'INFO':
        return {
          className: `${baseClasses} bg-blue-900/30 text-blue-400`,
          icon: <Info className="h-3.5 w-3.5" />,
        };
      case 'WARNING':
        return {
          className: `${baseClasses} bg-yellow-900/30 text-yellow-400`,
          icon: <AlertCircle className="h-3.5 w-3.5" />,
        };
      case 'ERROR':
        return {
          className: `${baseClasses} bg-red-900/30 text-red-400`,
          icon: <XCircle className="h-3.5 w-3.5" />,
        };
      case 'CRITICAL':
        return {
          className: `${baseClasses} bg-red-600 text-white`,
          icon: <XCircle className="h-3.5 w-3.5" />,
        };
      default:
        return {
          className: `${baseClasses} bg-gray-800 text-gray-300`,
          icon: <Info className="h-3.5 w-3.5" />,
        };
    }
  };

  const levelBadge = getLevelBadge(log.level);

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
              <Dialog.Panel className="w-full max-w-4xl transform overflow-hidden rounded-xl border border-gray-800 bg-[#1A1A1A] shadow-2xl transition-all">
                {/* Header */}
                <div className="flex items-start justify-between border-b border-gray-800 p-6">
                  <div className="flex-1">
                    <Dialog.Title
                      as="h2"
                      className="text-2xl font-bold text-white"
                      id="log-detail-title"
                    >
                      {log.component}
                    </Dialog.Title>
                    <div className="mt-2 flex items-center gap-2 text-sm text-gray-400">
                      <Clock className="h-4 w-4" />
                      <span>{formatTimestamp(log.timestamp)}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={levelBadge.className}>
                      {levelBadge.icon}
                      {log.level}
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
                  {/* Log Message */}
                  <div className="mb-6">
                    <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-400">
                      Message
                    </h3>
                    <p className="text-base leading-relaxed text-gray-200">{log.message}</p>
                  </div>

                  {/* Log Metadata */}
                  <div className="mb-6 rounded-lg border border-gray-800 bg-black/20 p-4">
                    <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-400">
                      Log Details
                    </h3>
                    <dl className="grid gap-2 text-sm">
                      <div className="flex justify-between">
                        <dt className="text-gray-400">Log ID</dt>
                        <dd className="font-mono text-gray-300">{log.id}</dd>
                      </div>
                      <div className="flex justify-between">
                        <dt className="text-gray-400">Component</dt>
                        <dd className="text-gray-300">{log.component}</dd>
                      </div>
                      <div className="flex justify-between">
                        <dt className="text-gray-400">Source</dt>
                        <dd className="text-gray-300">{log.source}</dd>
                      </div>
                      {log.camera_id && (
                        <div className="flex justify-between">
                          <dt className="text-gray-400">Camera ID</dt>
                          <dd className="text-gray-300">{log.camera_id}</dd>
                        </div>
                      )}
                      {log.event_id && (
                        <div className="flex justify-between">
                          <dt className="text-gray-400">Event ID</dt>
                          <dd className="font-mono text-gray-300">{log.event_id}</dd>
                        </div>
                      )}
                      {log.detection_id && (
                        <div className="flex justify-between">
                          <dt className="text-gray-400">Detection ID</dt>
                          <dd className="font-mono text-gray-300">{log.detection_id}</dd>
                        </div>
                      )}
                      {log.request_id && (
                        <div className="flex justify-between">
                          <dt className="text-gray-400">Request ID</dt>
                          <dd className="font-mono text-gray-300">{log.request_id}</dd>
                        </div>
                      )}
                      {log.duration_ms !== null && log.duration_ms !== undefined && (
                        <div className="flex justify-between">
                          <dt className="text-gray-400">Duration</dt>
                          <dd className="text-gray-300">{log.duration_ms} ms</dd>
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
                        <p className="font-mono text-xs text-gray-300">{log.user_agent}</p>
                      </div>
                    </div>
                  )}

                  {/* Extra JSON Data */}
                  {log.extra && Object.keys(log.extra).length > 0 && (
                    <div className="mb-6">
                      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-400">
                        Additional Data
                      </h3>
                      <div className="rounded-lg bg-[#76B900]/10 p-4">
                        <pre className="overflow-x-auto font-mono text-xs leading-relaxed text-gray-300">
                          {formatJSON(log.extra)}
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
