/**
 * RawSettingsPanel - Admin interface for raw system settings (NEM-4951).
 *
 * Provides a table view of all system settings with the ability to:
 * - View settings as key-value pairs
 * - Edit setting values via a modal
 * - Delete settings with confirmation
 * - Refresh the settings list
 *
 * @see NEM-4951 - Raw Settings Key-Value Admin Interface
 */
import { Dialog, Transition } from '@headlessui/react';
import { Card, Text, Button, Badge } from '@tremor/react';
import { clsx } from 'clsx';
import { formatDistanceToNow } from 'date-fns';
import {
  AlertTriangle,
  Database,
  Edit2,
  Loader2,
  RefreshCw,
  Save,
  Trash2,
  X,
} from 'lucide-react';
import { Fragment, useCallback, useState } from 'react';

import { useSystemSettings, useSystemSetting } from '../../hooks/useSystemSetting';
import { useToast } from '../../hooks/useToast';

export interface RawSettingsPanelProps {
  /** Optional className for styling */
  className?: string;
}

/**
 * Truncate and format JSON value for table display.
 */
function formatValueForDisplay(value: Record<string, unknown>): string {
  const json = JSON.stringify(value);
  if (json.length > 60) {
    return json.substring(0, 57) + '...';
  }
  return json;
}

/**
 * Format a timestamp as relative time (e.g., "2 hours ago").
 */
function formatTimestamp(timestamp: string): string {
  try {
    return formatDistanceToNow(new Date(timestamp), { addSuffix: true });
  } catch {
    return timestamp;
  }
}

/**
 * RawSettingsPanel component
 *
 * Displays all system settings in a table with edit and delete capabilities.
 */
export default function RawSettingsPanel({ className }: RawSettingsPanelProps) {
  const toast = useToast();
  const { settings, isLoading, isFetching, error, refetch } = useSystemSettings();

  // Edit modal state
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState<string>('');
  const [editError, setEditError] = useState<string | null>(null);

  // Delete dialog state
  const [deletingKey, setDeletingKey] = useState<string | null>(null);

  // Get the setting hook for the currently editing key
  const {
    updateSetting,
    deleteSetting,
  } = useSystemSetting({
    key: editingKey || deletingKey || '',
    enabled: Boolean(editingKey || deletingKey),
  });

  // Open edit modal for a setting
  const handleEdit = useCallback((key: string, value: Record<string, unknown>) => {
    setEditingKey(key);
    setEditValue(JSON.stringify(value, null, 2));
    setEditError(null);
  }, []);

  // Close edit modal
  const handleCancelEdit = useCallback(() => {
    setEditingKey(null);
    setEditValue('');
    setEditError(null);
  }, []);

  // Save edited value
  const handleSave = useCallback(async () => {
    if (!editingKey) return;

    // Validate JSON
    let parsedValue: Record<string, unknown>;
    try {
      parsedValue = JSON.parse(editValue) as Record<string, unknown>;
    } catch {
      setEditError('Invalid JSON: Please enter valid JSON syntax');
      return;
    }

    try {
      await updateSetting.mutateAsync(parsedValue);
      toast.success(`Setting "${editingKey}" updated`, {
        description: 'The setting value has been saved',
      });
      handleCancelEdit();
      void refetch();
    } catch (err) {
      toast.error('Failed to update setting', {
        description: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  }, [editingKey, editValue, updateSetting, toast, handleCancelEdit, refetch]);

  // Open delete confirmation
  const handleDeleteClick = useCallback((key: string) => {
    setDeletingKey(key);
  }, []);

  // Cancel delete
  const handleCancelDelete = useCallback(() => {
    setDeletingKey(null);
  }, []);

  // Confirm delete
  const handleConfirmDelete = useCallback(async () => {
    if (!deletingKey) return;

    try {
      await deleteSetting.mutateAsync();
      toast.success(`Setting "${deletingKey}" deleted`, {
        description: 'The setting has been removed',
      });
      setDeletingKey(null);
      void refetch();
    } catch (err) {
      toast.error('Failed to delete setting', {
        description: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  }, [deletingKey, deleteSetting, toast, refetch]);

  // Handle refresh
  const handleRefresh = useCallback(() => {
    void refetch();
  }, [refetch]);

  return (
    <div
      className={clsx('space-y-4', className)}
      data-testid="raw-settings-panel"
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Database className="h-5 w-5 text-indigo-400" />
          <div>
            <Text className="font-semibold text-white">Raw Settings</Text>
            <Text className="text-xs text-gray-500">
              View and edit raw system configuration key-value pairs
            </Text>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge size="sm" color="gray">
            {settings.length} settings
          </Badge>
          <Button
            size="xs"
            variant="secondary"
            onClick={handleRefresh}
            disabled={isFetching}
            data-testid="raw-settings-refresh"
            aria-label="Refresh settings"
          >
            <RefreshCw
              className={clsx('h-4 w-4', isFetching && 'animate-spin')}
            />
          </Button>
        </div>
      </div>

      {/* Loading state */}
      {isLoading && (
        <Card
          className="border-gray-800 bg-[#1A1A1A]"
          data-testid="raw-settings-loading"
        >
          <div className="flex items-center justify-center gap-2 py-8">
            <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
            <Text className="text-gray-400">Loading settings...</Text>
          </div>
        </Card>
      )}

      {/* Error state */}
      {error && !isLoading && (
        <Card
          className="border-red-500/30 bg-red-500/5"
          data-testid="raw-settings-error"
        >
          <div className="flex items-center gap-3 py-4">
            <AlertTriangle className="h-5 w-5 text-red-400" />
            <Text className="text-red-400">
              {error.message || 'Failed to fetch settings'}
            </Text>
            <Button
              size="xs"
              variant="secondary"
              onClick={handleRefresh}
              className="ml-auto"
            >
              Retry
            </Button>
          </div>
        </Card>
      )}

      {/* Empty state */}
      {!isLoading && !error && settings.length === 0 && (
        <Card
          className="border-gray-800 bg-[#1A1A1A]"
          data-testid="raw-settings-empty"
        >
          <div className="flex flex-col items-center justify-center gap-2 py-8">
            <Database className="h-8 w-8 text-gray-600" />
            <Text className="text-gray-400">No settings found</Text>
            <Text className="text-xs text-gray-600">
              System settings will appear here when created
            </Text>
          </div>
        </Card>
      )}

      {/* Settings table */}
      {!isLoading && !error && settings.length > 0 && (
        <Card className="overflow-hidden border-gray-800 bg-[#1A1A1A] p-0">
          <div className="overflow-x-auto">
            <table className="w-full" role="table">
              <thead>
                <tr className="border-b border-gray-800 bg-[#121212]">
                  <th
                    scope="col"
                    className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-400"
                  >
                    Key
                  </th>
                  <th
                    scope="col"
                    className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-400"
                  >
                    Value
                  </th>
                  <th
                    scope="col"
                    className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-400"
                  >
                    Last Updated
                  </th>
                  <th
                    scope="col"
                    className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-400"
                  >
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {settings.map((setting) => (
                  <tr
                    key={setting.key}
                    className="hover:bg-[#1F1F1F]"
                  >
                    <td className="whitespace-nowrap px-4 py-3">
                      <Text className="font-mono text-sm text-white">
                        {setting.key}
                      </Text>
                    </td>
                    <td className="px-4 py-3">
                      <Text className="font-mono text-xs text-gray-400">
                        {formatValueForDisplay(setting.value)}
                      </Text>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3">
                      <Text className="text-xs text-gray-500">
                        {formatTimestamp(setting.updated_at)}
                      </Text>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => handleEdit(setting.key, setting.value)}
                          className="rounded p-1.5 text-gray-400 transition-colors hover:bg-gray-700 hover:text-white"
                          data-testid={`raw-setting-edit-${setting.key}`}
                          aria-label={`Edit ${setting.key}`}
                        >
                          <Edit2 className="h-4 w-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDeleteClick(setting.key)}
                          className="rounded p-1.5 text-gray-400 transition-colors hover:bg-red-500/20 hover:text-red-400"
                          data-testid={`raw-setting-delete-${setting.key}`}
                          aria-label={`Delete ${setting.key}`}
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Edit Modal */}
      <Transition appear show={editingKey !== null} as={Fragment}>
        <Dialog
          as="div"
          className="relative z-50"
          onClose={handleCancelEdit}
        >
          <Transition.Child
            as={Fragment}
            enter="ease-out duration-300"
            enterFrom="opacity-0"
            enterTo="opacity-100"
            leave="ease-in duration-200"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-black/50" />
          </Transition.Child>

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
                  className="w-full max-w-lg transform rounded-lg border border-gray-700 bg-[#1A1A1A] p-6 shadow-xl transition-all"
                  data-testid="edit-setting-modal"
                >
                  <div className="flex items-center justify-between mb-4">
                    <Dialog.Title className="text-lg font-semibold text-white">
                      Edit Setting
                    </Dialog.Title>
                    <button
                      type="button"
                      onClick={handleCancelEdit}
                      className="rounded p-1 text-gray-400 hover:bg-gray-700 hover:text-white"
                    >
                      <X className="h-5 w-5" />
                    </button>
                  </div>

                  <div className="space-y-4">
                    {/* Key display (read-only, so using span instead of label) */}
                    <div>
                      <span className="block text-xs font-medium uppercase text-gray-400 mb-1">
                        Key
                      </span>
                      <Text className="font-mono text-sm text-white">
                        {editingKey}
                      </Text>
                    </div>

                    {/* Value editor */}
                    <div>
                      <label
                        htmlFor="edit-setting-value-input"
                        className="block text-xs font-medium uppercase text-gray-400 mb-1"
                      >
                        Value (JSON)
                      </label>
                      <textarea
                        id="edit-setting-value-input"
                        value={editValue}
                        onChange={(e) => {
                          setEditValue(e.target.value);
                          setEditError(null);
                        }}
                        rows={10}
                        className={clsx(
                          'w-full rounded-lg border bg-[#121212] p-3 font-mono text-sm text-white',
                          'focus:outline-none focus:ring-2 focus:ring-[#76B900]',
                          editError ? 'border-red-500' : 'border-gray-700'
                        )}
                        data-testid="edit-setting-value"
                      />
                      {editError && (
                        <div
                          className="mt-2 flex items-center gap-2 text-red-400"
                          data-testid="edit-setting-error"
                        >
                          <AlertTriangle className="h-4 w-4" />
                          <Text className="text-sm text-red-400">{editError}</Text>
                        </div>
                      )}
                    </div>

                    {/* Actions */}
                    <div className="flex justify-end gap-3 pt-4 border-t border-gray-700">
                      <Button
                        variant="secondary"
                        onClick={handleCancelEdit}
                        data-testid="edit-setting-cancel"
                      >
                        Cancel
                      </Button>
                      <Button
                        onClick={() => void handleSave()}
                        disabled={updateSetting.isPending}
                        className="bg-[#76B900] text-gray-950 hover:bg-[#5c8f00]"
                        data-testid="edit-setting-save"
                      >
                        {updateSetting.isPending ? (
                          <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Saving...
                          </>
                        ) : (
                          <>
                            <Save className="mr-2 h-4 w-4" />
                            Save
                          </>
                        )}
                      </Button>
                    </div>
                  </div>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition>

      {/* Delete Confirmation Dialog */}
      <Transition appear show={deletingKey !== null} as={Fragment}>
        <Dialog
          as="div"
          className="relative z-50"
          onClose={handleCancelDelete}
        >
          <Transition.Child
            as={Fragment}
            enter="ease-out duration-300"
            enterFrom="opacity-0"
            enterTo="opacity-100"
            leave="ease-in duration-200"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-black/50" />
          </Transition.Child>

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
                  className="w-full max-w-md transform rounded-lg border border-gray-700 bg-[#1A1A1A] p-6 shadow-xl transition-all"
                  data-testid="delete-setting-dialog"
                >
                  <div className="flex items-center gap-3 mb-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-red-500/20">
                      <Trash2 className="h-5 w-5 text-red-400" />
                    </div>
                    <Dialog.Title className="text-lg font-semibold text-white">
                      Delete Setting
                    </Dialog.Title>
                  </div>

                  <Text className="text-gray-400 mb-4">
                    Are you sure you want to delete the setting{' '}
                    <span className="font-mono text-white">{deletingKey}</span>?
                    This action cannot be undone.
                  </Text>

                  <div className="flex justify-end gap-3">
                    <Button
                      variant="secondary"
                      onClick={handleCancelDelete}
                      data-testid="delete-setting-cancel"
                    >
                      Cancel
                    </Button>
                    <Button
                      onClick={() => void handleConfirmDelete()}
                      disabled={deleteSetting.isPending}
                      className="bg-red-600 text-white hover:bg-red-700"
                      data-testid="delete-setting-confirm"
                    >
                      {deleteSetting.isPending ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Deleting...
                        </>
                      ) : (
                        <>
                          <Trash2 className="mr-2 h-4 w-4" />
                          Delete
                        </>
                      )}
                    </Button>
                  </div>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition>
    </div>
  );
}
