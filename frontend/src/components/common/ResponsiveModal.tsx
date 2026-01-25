/**
 * ResponsiveModal - Wrapper that auto-switches between modal types based on viewport
 *
 * Renders a BottomSheet on mobile viewports and AnimatedModal on desktop.
 * Provides a unified API for modals that work well across all device sizes.
 */

import AnimatedModal from './AnimatedModal';
import BottomSheet from './BottomSheet';
import { useIsMobile } from '../../hooks/useMediaQuery';

import type { ModalSize } from './AnimatedModal';
import type { BottomSheetHeight, ModalTransitionVariant } from './animations';
import type { ReactNode } from 'react';

export interface ResponsiveModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback when modal should close */
  onClose: () => void;
  /** Modal content */
  children: ReactNode;
  /** Title for the modal (shown in header on mobile) */
  title?: string;
  /** Animation variant for desktop modal */
  variant?: ModalTransitionVariant;
  /** Size for desktop modal */
  size?: ModalSize;
  /** Height variant for mobile bottom sheet */
  mobileHeight?: BottomSheetHeight;
  /** Show drag handle on mobile (default: true) */
  showDragHandle?: boolean;
  /** Show close button (default: true) */
  showCloseButton?: boolean;
  /** Close when clicking backdrop (default: true) */
  closeOnBackdropClick?: boolean;
  /** Close when pressing Escape key (default: true) */
  closeOnEscape?: boolean;
  /** Additional CSS classes for the modal container */
  className?: string;
  /** Additional CSS classes for the backdrop */
  backdropClassName?: string;
  /** Mobile breakpoint in pixels (default: 768) */
  mobileBreakpoint?: number;
  /** ARIA labelledby for accessibility */
  'aria-labelledby'?: string;
  /** ARIA describedby for accessibility */
  'aria-describedby'?: string;
}

/**
 * ResponsiveModal automatically switches between a bottom sheet on mobile
 * and a centered modal on desktop for optimal user experience.
 *
 * @example
 * ```tsx
 * <ResponsiveModal
 *   isOpen={isOpen}
 *   onClose={() => setIsOpen(false)}
 *   title="Details"
 *   size="lg"
 *   mobileHeight="full"
 * >
 *   <div>Modal content that adapts to screen size</div>
 * </ResponsiveModal>
 * ```
 */
export default function ResponsiveModal({
  isOpen,
  onClose,
  children,
  title,
  variant = 'scale',
  size = 'md',
  mobileHeight = 'auto',
  showDragHandle = true,
  showCloseButton = true,
  closeOnBackdropClick = true,
  closeOnEscape = true,
  className,
  backdropClassName,
  mobileBreakpoint = 768,
  'aria-labelledby': ariaLabelledby,
  'aria-describedby': ariaDescribedby,
}: ResponsiveModalProps) {
  const isMobile = useIsMobile(mobileBreakpoint);

  if (isMobile) {
    return (
      <BottomSheet
        isOpen={isOpen}
        onClose={onClose}
        title={title}
        height={mobileHeight}
        showDragHandle={showDragHandle}
        showCloseButton={showCloseButton}
        closeOnBackdropClick={closeOnBackdropClick}
        closeOnEscape={closeOnEscape}
        className={className}
        aria-labelledby={ariaLabelledby}
        aria-describedby={ariaDescribedby}
      >
        {children}
      </BottomSheet>
    );
  }

  return (
    <AnimatedModal
      isOpen={isOpen}
      onClose={onClose}
      variant={variant}
      size={size}
      closeOnBackdropClick={closeOnBackdropClick}
      closeOnEscape={closeOnEscape}
      className={className}
      backdropClassName={backdropClassName}
      aria-labelledby={ariaLabelledby}
      aria-describedby={ariaDescribedby}
    >
      {children}
    </AnimatedModal>
  );
}

export type { ModalSize, BottomSheetHeight, ModalTransitionVariant };
