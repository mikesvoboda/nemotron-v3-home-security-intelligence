/**
 * CleanupRow - A row component for cleanup/delete operations
 *
 * Displays a warning/danger button that opens a confirmation dialog
 * before performing the cleanup operation. Used in the TestDataPanel
 * for destructive operations like deleting events or resetting the database.
 *
 * @example
 * ```tsx
 * <CleanupRow
 *   label="Delete All Events"
 *   description="Permanently deletes all events from the database."
 *   confirmText="DELETE"
 *   onCleanup={() => cleanupEvents()}
 *   isLoading={isDeleting}
 *   variant="warning"
 * />
 * ```
 */

import { Button, Text } from '@tremor/react';
import { clsx } from 'clsx';
import { AlertTriangle, Trash2 } from 'lucide-react';
import { useState, useCallback } from 'react';

import ConfirmWithTextDialog, { type ConfirmDialogVariant } from './ConfirmWithTextDialog';

export interface CleanupRowProps {
  /** Label for the row */
  label: string;
  /** Description of what the cleanup does */
  description: string;
  /** Text the user must type to confirm (case-sensitive) */
  confirmText: string;
  /** Callback when cleanup is confirmed */
  onCleanup: () => Promise<void>;
  /** Whether the cleanup operation is loading */
  isLoading?: boolean;
  /** Visual variant for styling */
  variant?: ConfirmDialogVariant;
  /** Custom button text (default: label) */
  buttonText?: string;
  /** Custom loading text (default: "Deleting...") */
  loadingText?: string;
  /** Dialog title (default: "Confirm {label}") */
  dialogTitle?: string;
}

/**
 * Get button styling based on variant
 */
function getButtonStyles(variant: ConfirmDialogVariant): string {
  const baseClasses = 'text-white transition-colors';

  if (variant === 'danger') {
    return clsx(baseClasses, 'border-red-600 bg-red-600 hover:bg-red-700');
  }

  // warning variant
  return clsx(baseClasses, 'border-amber-600 bg-amber-600 hover:bg-amber-700');
}

/**
 * CleanupRow component
 */
export default function CleanupRow({
  label,
  description,
  confirmText,
  onCleanup,
  isLoading = false,
  variant = 'warning',
  buttonText,
  loadingText = 'Deleting...',
  dialogTitle,
}: CleanupRowProps) {
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);

  const handleOpenDialog = useCallback(() => {
    if (!isLoading) {
      setShowConfirmDialog(true);
    }
  }, [isLoading]);

  const handleCloseDialog = useCallback(() => {
    setShowConfirmDialog(false);
  }, []);

  const handleConfirm = useCallback(async () => {
    await onCleanup();
    setShowConfirmDialog(false);
  }, [onCleanup]);

  const displayButtonText = isLoading ? loadingText : (buttonText ?? label);
  const displayDialogTitle = dialogTitle ?? `Confirm ${label}`;

  return (
    <>
      <div
        className={clsx(
          'flex items-center justify-between gap-4 rounded-lg p-4',
          variant === 'danger'
            ? 'border border-red-500/30 bg-red-500/10'
            : 'border border-amber-500/30 bg-amber-500/10'
        )}
      >
        <div className="flex-1">
          <div className="flex items-center gap-2">
            {variant === 'danger' ? (
              <Trash2 className="h-4 w-4 text-red-400" />
            ) : (
              <AlertTriangle className="h-4 w-4 text-amber-400" />
            )}
            <Text
              className={clsx(
                'font-medium',
                variant === 'danger' ? 'text-red-300' : 'text-amber-300'
              )}
            >
              {label}
            </Text>
          </div>
          <Text className="mt-1 text-xs text-gray-400">{description}</Text>
        </div>

        <Button
          onClick={handleOpenDialog}
          disabled={isLoading}
          className={clsx(
            getButtonStyles(variant),
            'disabled:cursor-not-allowed disabled:opacity-50'
          )}
        >
          {displayButtonText}
        </Button>
      </div>

      <ConfirmWithTextDialog
        isOpen={showConfirmDialog}
        title={displayDialogTitle}
        description={description}
        confirmText={confirmText}
        onConfirm={() => void handleConfirm()}
        onCancel={handleCloseDialog}
        isLoading={isLoading}
        variant={variant}
      />
    </>
  );
}
