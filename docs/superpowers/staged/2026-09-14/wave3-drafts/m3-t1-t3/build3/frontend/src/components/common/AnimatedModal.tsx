import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { useCallback, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';

import {
  backdropVariants,
  defaultTransition,
  modalTransitionVariants,
  reducedMotionTransition,
  type ModalTransitionVariant,
} from './animations';
import { logger } from '../../services/logger';

import type { ReactNode } from 'react';

export type ModalSize = 'sm' | 'md' | 'lg' | 'xl' | 'full';

export interface AnimatedModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback when modal should close */
  onClose: () => void;
  /** Modal content */
  children: ReactNode;
  /** Animation variant to use */
  variant?: ModalTransitionVariant;
  /** Modal size */
  size?: ModalSize;
  /** Close when clicking backdrop */
  closeOnBackdropClick?: boolean;
  /** Close when pressing Escape key */
  closeOnEscape?: boolean;
  /** Additional CSS classes for modal */
  className?: string;
  /** Additional CSS classes for backdrop */
  backdropClassName?: string;
  /** ARIA labelledby for accessibility */
  'aria-labelledby'?: string;
  /** ARIA describedby for accessibility */
  'aria-describedby'?: string;
  /** Modal name for interaction tracking (optional) */
  modalName?: string;
}

const sizeClasses: Record<ModalSize, string> = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-lg',
  xl: 'max-w-xl',
  full: 'max-w-full',
};

/**
 * AnimatedModal provides a modal dialog with smooth open/close animations.
 * Supports multiple animation variants and respects reduced motion preferences.
 *
 * @example
 * ```tsx
 * <AnimatedModal
 *   isOpen={isModalOpen}
 *   onClose={() => setIsModalOpen(false)}
 *   variant="scale"
 * >
 *   <h2>Modal Title</h2>
 *   <p>Modal content here</p>
 * </AnimatedModal>
 * ```
 */
export default function AnimatedModal({
  isOpen,
  onClose,
  children,
  variant = 'scale',
  size = 'md',
  closeOnBackdropClick = true,
  closeOnEscape = true,
  className = '',
  backdropClassName = '',
  'aria-labelledby': ariaLabelledby,
  'aria-describedby': ariaDescribedby,
  modalName,
}: AnimatedModalProps) {
  const prefersReducedMotion = useReducedMotion();
  const prevIsOpenRef = useRef(isOpen);

  // Track modal open/close events
  useEffect(() => {
    // Only track if modalName is provided
    if (!modalName) return;

    // Track state changes, not initial render
    if (prevIsOpenRef.current !== isOpen) {
      if (isOpen) {
        logger.interaction('open', `modal.${modalName}`);
      } else {
        logger.interaction('close', `modal.${modalName}`);
      }
      prevIsOpenRef.current = isOpen;
    }
  }, [isOpen, modalName]);

  const variants = modalTransitionVariants[variant];
  const transition = prefersReducedMotion ? reducedMotionTransition : defaultTransition;

  const handleBackdropClick = useCallback(() => {
    if (closeOnBackdropClick) {
      onClose();
    }
  }, [closeOnBackdropClick, onClose]);

  const handleModalClick = useCallback((e: React.MouseEvent) => {
    // Prevent click from propagating to backdrop
    e.stopPropagation();
  }, []);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape' && closeOnEscape) {
        onClose();
      }
    },
    [closeOnEscape, onClose]
  );

  // Handle Escape key
  useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
      // Prevent body scroll when modal is open
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [isOpen, handleKeyDown]);

  const modalClasses = [
    'z-50',
    'w-full',
    sizeClasses[size],
    'bg-gray-900',
    'rounded-lg',
    'shadow-xl',
    'relative',
    className,
    prefersReducedMotion ? 'motion-reduce' : '',
  ]
    .filter(Boolean)
    .join(' ');

  const backdropClasses = [
    'fixed',
    'inset-0',
    'z-50',
    'bg-black/80',
    'flex',
    'items-center',
    'justify-center',
    'p-4',
    backdropClassName,
  ]
    .filter(Boolean)
    .join(' ');

  const modalContent = (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          data-testid="animated-modal-backdrop"
          className={backdropClasses}
          variants={backdropVariants}
          initial="initial"
          animate="animate"
          exit="exit"
          transition={transition}
          onClick={handleBackdropClick}
        >
          <motion.div
            data-testid="animated-modal"
            className={modalClasses}
            variants={variants}
            initial="initial"
            animate="animate"
            exit="exit"
            transition={transition}
            onClick={handleModalClick}
            role="dialog"
            aria-modal={true}
            aria-labelledby={ariaLabelledby}
            aria-describedby={ariaDescribedby}
            tabIndex={-1}
          >
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );

  // Render in portal for proper z-index stacking
  if (typeof document !== 'undefined') {
    return createPortal(modalContent, document.body);
  }

  return modalContent;
}
