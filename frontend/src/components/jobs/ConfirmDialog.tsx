/**
 * ConfirmDialog component for job action confirmations (NEM-2712).
 *
 * A reusable confirmation dialog for destructive or important actions.
 * Supports different variants for visual styling based on action severity:
 * - default: Primary/green confirm button
 * - warning: Amber/yellow confirm button
 * - danger: Red confirm button
 *
 * @example
 * ```tsx
 * <ConfirmDialog
 *   isOpen={showDialog}
 *   title="Delete Job"
 *   description="This action cannot be undone. The job record will be permanently deleted."
 *   confirmLabel="Delete"
 *   variant="danger"
 *   onConfirm={() => deleteJob(jobId)}
 *   onCancel={() => setShowDialog(false)}
 * />
 * ```
 */
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { Loader2 } from 'lucide-react';
import { memo, useCallback, useEffect, useId, useRef } from 'react';
import { createPortal } from 'react-dom';

export type ConfirmDialogVariant = 'default' | 'warning' | 'danger';

export interface ConfirmDialogProps {
  /** Whether the dialog is open */
  isOpen: boolean;
  /** Dialog title */
  title: string;
  /** Dialog description/message */
  description: string;
  /** Text for the confirm button */
  confirmLabel: string;
  /** Text for the cancel button (default: "Cancel") */
  cancelLabel?: string;
  /** Variant for styling the confirm button */
  variant?: ConfirmDialogVariant;
  /** Whether an async action is in progress */
  isLoading?: boolean;
  /** Text to show while loading (replaces confirm button text) */
  loadingText?: string;
  /** Whether clicking backdrop should close the dialog (default: true) */
  closeOnBackdrop?: boolean;
  /** Callback when confirm button is clicked */
  onConfirm: () => void;
  /** Callback when cancel button is clicked or dialog should close */
  onCancel: () => void;
}

/**
 * Animation variants for the dialog
 */
const backdropVariants = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  exit: { opacity: 0 },
};

const dialogVariants = {
  initial: { opacity: 0, scale: 0.95, y: 10 },
  animate: { opacity: 1, scale: 1, y: 0 },
  exit: { opacity: 0, scale: 0.95, y: 10 },
};

const reducedMotionVariants = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  exit: { opacity: 0 },
};

/**
 * Confirm button styling based on variant
 */
const confirmButtonStyles: Record<ConfirmDialogVariant, string> = {
  default: 'bg-[#76B900] hover:bg-[#6aa800] text-white focus:ring-[#76B900]/50',
  warning: 'bg-amber-600 hover:bg-amber-700 text-white focus:ring-amber-500/50',
  danger: 'bg-red-600 hover:bg-red-700 text-white focus:ring-red-500/50',
};

/**
 * ConfirmDialog - A modal dialog for confirming actions
 */
const ConfirmDialog = memo(function ConfirmDialog({
  isOpen,
  title,
  description,
  confirmLabel,
  cancelLabel = 'Cancel',
  variant = 'default',
  isLoading = false,
  loadingText,
  closeOnBackdrop = true,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const prefersReducedMotion = useReducedMotion();
  const titleId = useId();
  const descriptionId = useId();
  const cancelButtonRef = useRef<HTMLButtonElement>(null);
  const confirmButtonRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  // Focus management - focus cancel button when dialog opens
  useEffect(() => {
    if (isOpen && cancelButtonRef.current) {
      cancelButtonRef.current.focus();
    }
  }, [isOpen]);

  // Handle Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen && !isLoading) {
        onCancel();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
      // Prevent body scroll
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [isOpen, isLoading, onCancel]);

  // Focus trap - keep focus within dialog
  useEffect(() => {
    if (!isOpen || !dialogRef.current) return;

    const handleFocusTrap = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return;

      const focusableElements = dialogRef.current?.querySelectorAll<HTMLElement>(
        'button:not([disabled]), [tabindex]:not([tabindex="-1"])'
      );

      if (!focusableElements || focusableElements.length === 0) return;

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];

      if (e.shiftKey && document.activeElement === firstElement) {
        e.preventDefault();
        lastElement.focus();
      } else if (!e.shiftKey && document.activeElement === lastElement) {
        e.preventDefault();
        firstElement.focus();
      }
    };

    document.addEventListener('keydown', handleFocusTrap);
    return () => document.removeEventListener('keydown', handleFocusTrap);
  }, [isOpen]);

  const handleBackdropClick = useCallback(() => {
    if (closeOnBackdrop && !isLoading) {
      onCancel();
    }
  }, [closeOnBackdrop, isLoading, onCancel]);

  const handleDialogClick = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
  }, []);

  const handleConfirm = useCallback(() => {
    if (!isLoading) {
      onConfirm();
    }
  }, [isLoading, onConfirm]);

  const handleCancel = useCallback(() => {
    if (!isLoading) {
      onCancel();
    }
  }, [isLoading, onCancel]);

  const transition = prefersReducedMotion
    ? { duration: 0.1 }
    : { duration: 0.2, ease: 'easeOut' as const };

  const variants = prefersReducedMotion ? reducedMotionVariants : dialogVariants;

  const dialogContent = (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          data-testid="dialog-backdrop"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
          variants={backdropVariants}
          initial="initial"
          animate="animate"
          exit="exit"
          transition={transition}
          onClick={handleBackdropClick}
        >
          <motion.div
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            aria-describedby={descriptionId}
            data-testid="confirm-dialog"
            className="w-full max-w-md rounded-lg bg-gray-900 p-6 shadow-xl"
            variants={variants}
            initial="initial"
            animate="animate"
            exit="exit"
            transition={transition}
            onClick={handleDialogClick}
          >
            {/* Title */}
            <h2 id={titleId} className="text-lg font-semibold text-white">
              {title}
            </h2>

            {/* Description */}
            <p id={descriptionId} className="mt-2 text-sm text-gray-400">
              {description}
            </p>

            {/* Actions */}
            <div className="mt-6 flex justify-end gap-3">
              {/* Cancel Button */}
              <button
                ref={cancelButtonRef}
                type="button"
                disabled={isLoading}
                onClick={handleCancel}
                className="rounded-md bg-gray-700 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-gray-500/50 focus:ring-offset-2 focus:ring-offset-gray-900 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {cancelLabel}
              </button>

              {/* Confirm Button */}
              <button
                ref={confirmButtonRef}
                type="button"
                disabled={isLoading}
                onClick={handleConfirm}
                className={`flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-900 disabled:cursor-not-allowed disabled:opacity-50 ${confirmButtonStyles[variant]}`}
              >
                {isLoading && (
                  <Loader2 data-testid="loading-spinner" className="h-4 w-4 animate-spin" />
                )}
                {isLoading && loadingText ? loadingText : confirmLabel}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );

  // Render in portal for proper z-index stacking
  if (typeof document !== 'undefined') {
    return createPortal(dialogContent, document.body);
  }

  return dialogContent;
});

export default ConfirmDialog;
