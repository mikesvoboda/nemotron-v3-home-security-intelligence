/**
 * BottomSheet - Mobile-optimized modal that slides up from the bottom
 *
 * Features:
 * - Spring animation on open/close
 * - Drag-to-dismiss with threshold
 * - Escape key closes sheet
 * - Backdrop click closes (configurable)
 * - Prevents body scroll when open
 * - Safe area padding for notched devices
 * - Height variants: 'auto', 'half', 'full'
 * - Accessible with proper ARIA attributes
 */

import { clsx } from 'clsx';
import { AnimatePresence, motion, useReducedMotion, type PanInfo } from 'framer-motion';
import { X } from 'lucide-react';
import { useCallback, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';

import {
  backdropVariants,
  bottomSheetSpringTransition,
  bottomSheetVariants,
  getBottomSheetHeightClass,
  reducedMotionTransition,
} from './animations';

import type { BottomSheetHeight } from './animations';
import type { ReactNode } from 'react';

/** Drag threshold in pixels - sheet closes if dragged beyond this */
const DRAG_CLOSE_THRESHOLD = 100;

export interface BottomSheetProps {
  /** Whether the bottom sheet is open */
  isOpen: boolean;
  /** Callback when bottom sheet should close */
  onClose: () => void;
  /** Bottom sheet content */
  children: ReactNode;
  /** Title displayed in the header */
  title?: string;
  /** Height variant for the bottom sheet */
  height?: BottomSheetHeight;
  /** Whether to show the drag handle indicator */
  showDragHandle?: boolean;
  /** Whether to show the close button */
  showCloseButton?: boolean;
  /** Close when clicking backdrop */
  closeOnBackdropClick?: boolean;
  /** Close when pressing Escape key */
  closeOnEscape?: boolean;
  /** Additional CSS classes for the bottom sheet container */
  className?: string;
  /** ARIA labelledby for accessibility */
  'aria-labelledby'?: string;
  /** ARIA describedby for accessibility */
  'aria-describedby'?: string;
}

/**
 * BottomSheet provides a mobile-optimized modal that slides up from the bottom.
 * Features drag-to-dismiss functionality and spring animations.
 *
 * @example
 * ```tsx
 * <BottomSheet
 *   isOpen={isOpen}
 *   onClose={() => setIsOpen(false)}
 *   title="Options"
 *   height="auto"
 * >
 *   <div>Bottom sheet content here</div>
 * </BottomSheet>
 * ```
 */
export default function BottomSheet({
  isOpen,
  onClose,
  children,
  title,
  height = 'auto',
  showDragHandle = true,
  showCloseButton = true,
  closeOnBackdropClick = true,
  closeOnEscape = true,
  className,
  'aria-labelledby': ariaLabelledby,
  'aria-describedby': ariaDescribedby,
}: BottomSheetProps) {
  const prefersReducedMotion = useReducedMotion();
  const sheetRef = useRef<HTMLDivElement>(null);

  const transition = prefersReducedMotion ? reducedMotionTransition : bottomSheetSpringTransition;

  // Handle backdrop click
  const handleBackdropClick = useCallback(() => {
    if (closeOnBackdropClick) {
      onClose();
    }
  }, [closeOnBackdropClick, onClose]);

  // Prevent click propagation from sheet content
  const handleSheetClick = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
  }, []);

  // Handle escape key
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape' && closeOnEscape) {
        onClose();
      }
    },
    [closeOnEscape, onClose]
  );

  // Handle drag end - close if dragged beyond threshold
  const handleDragEnd = useCallback(
    (_event: MouseEvent | TouchEvent | PointerEvent, info: PanInfo) => {
      // Close if dragged down beyond threshold
      if (info.offset.y > DRAG_CLOSE_THRESHOLD) {
        onClose();
      }
    },
    [onClose]
  );

  // Setup keyboard listener and body scroll lock
  useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
      // Prevent body scroll when sheet is open
      const originalOverflow = document.body.style.overflow;
      document.body.style.overflow = 'hidden';

      return () => {
        document.removeEventListener('keydown', handleKeyDown);
        document.body.style.overflow = originalOverflow;
      };
    }
  }, [isOpen, handleKeyDown]);

  // Focus management - focus sheet when opened
  useEffect(() => {
    if (isOpen && sheetRef.current) {
      sheetRef.current.focus();
    }
  }, [isOpen]);

  const heightClass = getBottomSheetHeightClass(height);

  const sheetClasses = clsx(
    // Base styles
    'fixed',
    'bottom-0',
    'left-0',
    'right-0',
    'z-50',
    'bg-gray-900',
    'rounded-t-2xl',
    'shadow-2xl',
    'overflow-hidden',
    'flex',
    'flex-col',
    // Safe area padding for notched devices
    'pb-safe',
    // Height
    heightClass,
    // Reduced motion
    prefersReducedMotion && 'motion-reduce',
    // Custom classes
    className
  );

  const backdropClasses = clsx(
    'fixed',
    'inset-0',
    'z-50',
    'bg-black/75',
    prefersReducedMotion && 'motion-reduce'
  );

  const sheetContent = (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            data-testid="bottom-sheet-backdrop"
            className={backdropClasses}
            variants={backdropVariants}
            initial="initial"
            animate="animate"
            exit="exit"
            transition={transition}
            onClick={handleBackdropClick}
            aria-hidden="true"
          />

          {/* Bottom Sheet */}
          <motion.div
            ref={sheetRef}
            data-testid="bottom-sheet"
            className={sheetClasses}
            variants={bottomSheetVariants}
            initial="initial"
            animate="animate"
            exit="exit"
            transition={transition}
            onClick={handleSheetClick}
            drag="y"
            dragConstraints={{ top: 0 }}
            dragElastic={{ top: 0, bottom: 0.5 }}
            onDragEnd={handleDragEnd}
            role="dialog"
            aria-modal={true}
            aria-labelledby={ariaLabelledby || (title ? 'bottom-sheet-title' : undefined)}
            aria-describedby={ariaDescribedby}
            tabIndex={-1}
          >
            {/* Drag Handle */}
            {showDragHandle && (
              <div className="flex justify-center pb-2 pt-3" data-testid="bottom-sheet-drag-handle">
                <div className="h-1.5 w-12 rounded-full bg-gray-600" />
              </div>
            )}

            {/* Header with title and close button */}
            {(title || showCloseButton) && (
              <div className="flex items-center justify-between border-b border-gray-800 px-4 py-2">
                {title ? (
                  <h2
                    id="bottom-sheet-title"
                    className="text-lg font-semibold text-white"
                    data-testid="bottom-sheet-title"
                  >
                    {title}
                  </h2>
                ) : (
                  <div />
                )}
                {showCloseButton && (
                  <button
                    onClick={onClose}
                    className={clsx(
                      'flex items-center justify-center',
                      // 44x44px touch target for accessibility
                      'min-h-[44px] min-w-[44px]',
                      'rounded-lg',
                      'text-gray-400',
                      'transition-colors',
                      'hover:bg-gray-800 hover:text-white',
                      'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-gray-900'
                    )}
                    aria-label="Close bottom sheet"
                    data-testid="bottom-sheet-close-button"
                  >
                    <X className="h-6 w-6" />
                  </button>
                )}
              </div>
            )}

            {/* Content */}
            <div
              className="flex-1 overflow-y-auto overscroll-contain px-4 py-4"
              data-testid="bottom-sheet-content"
            >
              {children}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );

  // Render in portal for proper z-index stacking
  if (typeof document !== 'undefined') {
    return createPortal(sheetContent, document.body);
  }

  return sheetContent;
}

export type { BottomSheetHeight };
