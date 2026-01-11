import { Dialog, Transition } from '@headlessui/react';
import { Camera, Car, Clock, Eye, User, X } from 'lucide-react';
import { Fragment } from 'react';

import EntityTimeline from './EntityTimeline';

import type { EntityDetail } from '../../services/api';

export interface EntityDetailModalProps {
  entity: EntityDetail | null;
  isOpen: boolean;
  onClose: () => void;
}

/**
 * EntityDetailModal displays full entity details in a modal overlay,
 * including the appearance timeline across cameras.
 */
export default function EntityDetailModal({
  entity,
  isOpen,
  onClose,
}: EntityDetailModalProps) {
  if (!entity) {
    return null;
  }

  // Format timestamp to relative time
  const formatTimestamp = (isoString: string): string => {
    try {
      const date = new Date(isoString);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMins / 60);
      const diffDays = Math.floor(diffHours / 24);

      if (diffMins < 1) return 'Just now';
      if (diffMins < 60) return `${diffMins} minutes ago`;
      if (diffHours < 24) return diffHours === 1 ? '1 hour ago' : `${diffHours} hours ago`;
      if (diffDays < 7) return diffDays === 1 ? '1 day ago' : `${diffDays} days ago`;

      return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
        hour: 'numeric',
        minute: '2-digit',
        hour12: true,
      });
    } catch {
      return isoString;
    }
  };

  // Get entity type display label
  const entityTypeLabel = entity.entity_type === 'person' ? 'Person' : 'Vehicle';

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
                  <div className="flex items-center gap-4">
                    {/* Entity thumbnail or icon */}
                    <div className="flex h-16 w-16 items-center justify-center overflow-hidden rounded-full bg-gray-800">
                      {entity.thumbnail_url ? (
                        <img
                          src={entity.thumbnail_url}
                          alt={`${entityTypeLabel} entity thumbnail`}
                          className="h-full w-full object-cover"
                        />
                      ) : (
                        <div className="flex h-full w-full items-center justify-center text-gray-500">
                          {entity.entity_type === 'person' ? (
                            <User className="h-8 w-8" />
                          ) : (
                            <Car className="h-8 w-8" />
                          )}
                        </div>
                      )}
                    </div>

                    <div>
                      <Dialog.Title
                        as="h2"
                        className="flex items-center gap-2 text-xl font-bold text-white"
                      >
                        {entity.entity_type === 'person' ? (
                          <User className="h-5 w-5 text-[#76B900]" />
                        ) : (
                          <Car className="h-5 w-5 text-[#76B900]" />
                        )}
                        {entityTypeLabel}
                      </Dialog.Title>
                      <p className="mt-1 font-mono text-sm text-gray-400">{entity.id}</p>
                    </div>
                  </div>

                  <button
                    onClick={onClose}
                    className="rounded-lg p-2 text-gray-400 transition-colors hover:bg-gray-800 hover:text-white"
                    aria-label="Close modal"
                  >
                    <X className="h-6 w-6" />
                  </button>
                </div>

                {/* Content */}
                <div className="max-h-[calc(100vh-200px)] overflow-y-auto p-6">
                  {/* Stats row */}
                  <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
                    {/* Appearances */}
                    <div className="rounded-lg border border-gray-800 bg-black/30 p-3">
                      <div className="flex items-center gap-2 text-xl font-bold text-white">
                        <Eye className="h-5 w-5 text-gray-400" />
                        <span>{entity.appearance_count}</span>
                      </div>
                      <p className="mt-1 text-xs text-gray-400">
                        {entity.appearance_count === 1 ? 'appearance' : 'appearances'}
                      </p>
                    </div>

                    {/* Cameras */}
                    <div className="rounded-lg border border-gray-800 bg-black/30 p-3">
                      <div className="flex items-center gap-2 text-xl font-bold text-white">
                        <Camera className="h-5 w-5 text-gray-400" />
                        <span>{(entity.cameras_seen ?? []).length}</span>
                      </div>
                      <p className="mt-1 text-xs text-gray-400">
                        {(entity.cameras_seen ?? []).length === 1 ? 'camera' : 'cameras'}
                      </p>
                    </div>

                    {/* First seen */}
                    <div className="rounded-lg border border-gray-800 bg-black/30 p-3">
                      <div className="flex items-center gap-2 text-sm font-medium text-white">
                        <Clock className="h-4 w-4 text-gray-400" />
                        <span>First seen</span>
                      </div>
                      <p className="mt-1 text-xs text-gray-300">
                        {formatTimestamp(entity.first_seen)}
                      </p>
                    </div>

                    {/* Last seen */}
                    <div className="rounded-lg border border-gray-800 bg-black/30 p-3">
                      <div className="flex items-center gap-2 text-sm font-medium text-white">
                        <Clock className="h-4 w-4 text-gray-400" />
                        <span>Last seen</span>
                      </div>
                      <p className="mt-1 text-xs text-gray-300">
                        {formatTimestamp(entity.last_seen)}
                      </p>
                    </div>
                  </div>

                  {/* Cameras list */}
                  {(entity.cameras_seen ?? []).length > 0 && (
                    <div className="mb-6">
                      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-400">
                        Cameras
                      </h3>
                      <div className="flex flex-wrap gap-2">
                        {(entity.cameras_seen ?? []).map((camera) => (
                          <span
                            key={camera}
                            className="flex items-center gap-1 rounded-full bg-gray-800 px-3 py-1 text-sm text-gray-300"
                          >
                            <Camera className="h-3.5 w-3.5" />
                            {camera}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Appearance Timeline */}
                  <EntityTimeline
                    entity_id={entity.id}
                    entity_type={entity.entity_type as 'person' | 'vehicle'}
                    appearances={entity.appearances ?? []}
                  />
                </div>

                {/* Footer */}
                <div className="flex items-center justify-end border-t border-gray-800 bg-black/20 p-4">
                  <button
                    onClick={onClose}
                    className="rounded-lg bg-gray-800 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-gray-700"
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
