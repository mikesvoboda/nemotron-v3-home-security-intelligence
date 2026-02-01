/**
 * WorkerActionConfirmDialog component for confirming worker actions (NEM-4831).
 *
 * A confirmation dialog specifically for worker control actions (stop, restart).
 * Uses warning variant for stop actions and default for restart.
 *
 * @example
 * ```tsx
 * <WorkerActionConfirmDialog
 *   isOpen={showDialog}
 *   workerName="file_watcher"
 *   action="stop"
 *   onConfirm={() => stopWorker('file_watcher')}
 *   onCancel={() => setShowDialog(false)}
 *   isLoading={isStopLoading}
 * />
 * ```
 */

import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { AlertTriangle, Info, Loader2 } from 'lucide-react';
import { memo, useCallback, useEffect, useId, useRef } from 'react';
import { createPortal } from 'react-dom';

export type WorkerAction = 'stop' | 'restart';

export interface WorkerActionConfirmDialogProps {
  /** Whether the dialog is open */
  isOpen: boolean;
  /** Name of the worker being acted upon */
  workerName: string;
  /** The action to confirm */
  action: WorkerAction;
  /** Callback when confirm button is clicked */
  onConfirm: () => void;
  /** Callback when cancel button is clicked or dialog should close */
  onCancel: () => void;
  /** Whether an async action is in progress */
  isLoading?: boolean;
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
 * Get action-specific configuration
 */
function getActionConfig(action: WorkerAction) {
  if (action === 'stop') {
    return {
      variant: 'warning' as const,
      title: (name: string) => `Stop Worker "${name}"`,
      description: (name: string) =>
        `Are you sure you want to stop worker "${name}"? This will interrupt any ongoing work.`,
      confirmLabel: 'Stop',
      loadingLabel: 'Stopping...',
      buttonClass: 'bg-amber-600 hover:bg-amber-700 focus:ring-amber-500/50',
    };
  }
  return {
    variant: 'default' as const,
    title: (name: string) => `Restart Worker "${name}"`,
    description: (name: string) =>
      `Are you sure you want to restart worker "${name}"? This will temporarily interrupt any ongoing work.`,
    confirmLabel: 'Restart',
    loadingLabel: 'Restarting...',
    buttonClass: 'bg-[#76B900] hover:bg-[#6aa800] focus:ring-[#76B900]/50',
  };
}

/**
 * WorkerActionConfirmDialog - Confirmation dialog for worker actions
 */
const WorkerActionConfirmDialog = memo(function WorkerActionConfirmDialog({
  isOpen,
  workerName,
  action,
  onConfirm,
  onCancel,
  isLoading = false,
}: WorkerActionConfirmDialogProps) {
  const prefersReducedMotion = useReducedMotion();
  const titleId = useId();
  const descriptionId = useId();
  const cancelButtonRef = useRef<HTMLButtonElement>(null);
  const confirmButtonRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  const config = getActionConfig(action);

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
    if (!isLoading) {
      onCancel();
    }
  }, [isLoading, onCancel]);

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
            data-testid="worker-action-confirm-dialog"
            data-variant={config.variant}
            className="w-full max-w-md rounded-lg bg-gray-900 p-6 shadow-xl"
            variants={variants}
            initial="initial"
            animate="animate"
            exit="exit"
            transition={transition}
            onClick={handleDialogClick}
          >
            {/* Icon and Title */}
            <div className="flex items-start gap-3">
              {action === 'stop' ? (
                <AlertTriangle
                  className="h-6 w-6 flex-shrink-0 text-amber-500"
                  data-testid="warning-icon"
                />
              ) : (
                <Info
                  className="h-6 w-6 flex-shrink-0 text-[#76B900]"
                  data-testid="info-icon"
                />
              )}
              <div>
                <h2 id={titleId} className="text-lg font-semibold text-white">
                  {config.title(workerName)}
                </h2>

                {/* Description */}
                <p id={descriptionId} className="mt-2 text-sm text-gray-400">
                  {config.description(workerName)}
                </p>
              </div>
            </div>

            {/* Actions */}
            <div className="mt-6 flex justify-end gap-3">
              {/* Cancel Button */}
              <button
                ref={cancelButtonRef}
                type="button"
                disabled={isLoading}
                onClick={handleCancel}
                data-testid="worker-action-cancel-button"
                className="rounded-md bg-gray-700 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-gray-500/50 focus:ring-offset-2 focus:ring-offset-gray-900 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Cancel
              </button>

              {/* Confirm Button */}
              <button
                ref={confirmButtonRef}
                type="button"
                disabled={isLoading}
                onClick={handleConfirm}
                data-testid="worker-action-confirm-button"
                className={`flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium text-white transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-900 disabled:cursor-not-allowed disabled:opacity-50 ${config.buttonClass}`}
              >
                {isLoading && (
                  <Loader2 data-testid="loading-spinner" className="h-4 w-4 animate-spin" />
                )}
                {isLoading ? config.loadingLabel : config.confirmLabel}
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

export default WorkerActionConfirmDialog;
