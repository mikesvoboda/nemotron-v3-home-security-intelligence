/**
 * ConfirmWithTextDialog - A confirmation dialog requiring typed confirmation
 *
 * Used for destructive operations like deleting data. The user must type
 * a specific confirmation string (e.g., "DELETE" or "RESET DATABASE") to
 * enable the confirm button.
 *
 * @example
 * ```tsx
 * <ConfirmWithTextDialog
 *   isOpen={showConfirm}
 *   title="Delete All Events"
 *   description="This will permanently delete all events. This action cannot be undone."
 *   confirmText="DELETE"
 *   onConfirm={handleDelete}
 *   onCancel={() => setShowConfirm(false)}
 *   isLoading={isDeleting}
 *   variant="danger"
 * />
 * ```
 */

import { Button, TextInput } from '@tremor/react';
import { clsx } from 'clsx';
import { AlertTriangle } from 'lucide-react';
import { useState, useEffect, useCallback } from 'react';

import ResponsiveModal from '../common/ResponsiveModal';

export type ConfirmDialogVariant = 'danger' | 'warning';

export interface ConfirmWithTextDialogProps {
  /** Whether the dialog is open */
  isOpen: boolean;
  /** Dialog title */
  title: string;
  /** Description of what will happen */
  description: string;
  /** Text the user must type to confirm (case-sensitive) */
  confirmText: string;
  /** Callback when confirmed */
  onConfirm: () => void;
  /** Callback when cancelled */
  onCancel: () => void;
  /** Whether the confirm action is loading */
  isLoading?: boolean;
  /** Visual variant for styling */
  variant?: ConfirmDialogVariant;
  /** Custom confirm button text (default: "Confirm") */
  confirmButtonText?: string;
  /** Custom loading button text (default based on variant) */
  loadingButtonText?: string;
}

/**
 * Get button styling based on variant
 */
function getButtonStyles(variant: ConfirmDialogVariant, isDisabled: boolean): string {
  const baseClasses = 'text-white transition-colors focus:ring-2 focus:ring-offset-2';

  if (variant === 'danger') {
    return clsx(
      baseClasses,
      'bg-red-600 hover:bg-red-700 focus:ring-red-500',
      isDisabled && 'opacity-50 cursor-not-allowed'
    );
  }

  // warning variant
  return clsx(
    baseClasses,
    'bg-amber-600 hover:bg-amber-700 focus:ring-amber-500',
    isDisabled && 'opacity-50 cursor-not-allowed'
  );
}

/**
 * ConfirmWithTextDialog component
 */
export default function ConfirmWithTextDialog({
  isOpen,
  title,
  description,
  confirmText,
  onConfirm,
  onCancel,
  isLoading = false,
  variant = 'danger',
  confirmButtonText = 'Confirm',
  loadingButtonText,
}: ConfirmWithTextDialogProps) {
  const [inputValue, setInputValue] = useState('');

  // Clear input when dialog closes
  useEffect(() => {
    if (!isOpen) {
      setInputValue('');
    }
  }, [isOpen]);

  const isMatch = inputValue === confirmText;
  const canConfirm = isMatch && !isLoading;

  const handleConfirm = useCallback(() => {
    if (canConfirm) {
      onConfirm();
    }
  }, [canConfirm, onConfirm]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && canConfirm) {
        handleConfirm();
      }
    },
    [canConfirm, handleConfirm]
  );

  // Default loading text based on variant
  const defaultLoadingText = variant === 'danger' ? 'Deleting...' : 'Processing...';
  const loadingText = loadingButtonText ?? defaultLoadingText;

  return (
    <ResponsiveModal
      isOpen={isOpen}
      onClose={onCancel}
      size="sm"
      variant="scale"
      mobileHeight="auto"
      title={title}
      closeOnBackdropClick={!isLoading}
      closeOnEscape={!isLoading}
      aria-labelledby="confirm-dialog-title"
      aria-describedby="confirm-dialog-description"
    >
      <div className="p-6">
        {/* Header with warning icon */}
        <div className="mb-4 flex items-start gap-3">
          <div
            className={clsx(
              'flex-shrink-0 rounded-full p-2',
              variant === 'danger' ? 'bg-red-500/20' : 'bg-amber-500/20'
            )}
          >
            <AlertTriangle
              className={clsx(
                'h-5 w-5',
                variant === 'danger' ? 'text-red-400' : 'text-amber-400'
              )}
            />
          </div>
          <div>
            <h2
              id="confirm-dialog-title"
              className="text-lg font-semibold text-white"
            >
              {title}
            </h2>
            <p
              id="confirm-dialog-description"
              className="mt-1 text-sm text-gray-400"
            >
              {description}
            </p>
          </div>
        </div>

        {/* Confirmation input */}
        <div className="mb-6">
          <label className="mb-2 block text-sm text-gray-300">
            Type &quot;{confirmText}&quot; to confirm
          </label>
          <TextInput
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={`Type "${confirmText}"`}
            disabled={isLoading}
            className="w-full"
            // eslint-disable-next-line jsx-a11y/no-autofocus
            autoFocus
          />
        </div>

        {/* Action buttons */}
        <div className="flex gap-3">
          <Button
            onClick={onCancel}
            disabled={isLoading}
            variant="secondary"
            className="flex-1"
          >
            Cancel
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={!canConfirm}
            className={clsx(
              'flex-1',
              getButtonStyles(variant, !canConfirm)
            )}
          >
            {isLoading ? loadingText : confirmButtonText}
          </Button>
        </div>
      </div>
    </ResponsiveModal>
  );
}
