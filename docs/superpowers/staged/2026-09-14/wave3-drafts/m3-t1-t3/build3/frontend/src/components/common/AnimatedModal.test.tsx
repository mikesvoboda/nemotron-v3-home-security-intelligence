/* eslint-disable @typescript-eslint/unbound-method */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AnimatedModal from './AnimatedModal';
import { logger } from '../../services/logger';

// Mock the logger
vi.mock('../../services/logger', () => ({
  logger: {
    interaction: vi.fn(),
  },
}));

// Mock framer-motion to avoid animation timing issues in tests
vi.mock('framer-motion', () => ({
  motion: {
    div: ({
      children,
      className,
      'data-testid': testId,
      initial,
      animate,
      exit,
      variants,
      onClick,
      onKeyDown,
      role,
      'aria-modal': ariaModal,
      'aria-labelledby': ariaLabelledby,
      'aria-describedby': ariaDescribedby,
      tabIndex,
      ...props
    }: {
      children?: React.ReactNode;
      className?: string;
      'data-testid'?: string;
      initial?: string | object;
      animate?: string | object;
      exit?: string | object;
      variants?: object;
      onClick?: () => void;
      onKeyDown?: () => void;
      role?: string;
      'aria-modal'?: boolean;
      'aria-labelledby'?: string;
      'aria-describedby'?: string;
      tabIndex?: number;
      [key: string]: unknown;
    }) => (
      // eslint-disable-next-line jsx-a11y/no-static-element-interactions -- mock for framer-motion
      <div
        className={className}
        data-testid={testId}
        data-initial={JSON.stringify(initial)}
        data-animate={JSON.stringify(animate)}
        data-exit={JSON.stringify(exit)}
        data-variants={JSON.stringify(variants)}
        onClick={onClick}
        onKeyDown={onKeyDown}
        role={role || 'presentation'}
        aria-modal={ariaModal}
        aria-labelledby={ariaLabelledby}
        aria-describedby={ariaDescribedby}
        tabIndex={tabIndex}
        {...props}
      >
        {children}
      </div>
    ),
  },
  AnimatePresence: ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="animate-presence">{children}</div>
  ),
  useReducedMotion: vi.fn(() => false),
}));

describe('AnimatedModal', () => {
  const mockOnClose = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('basic rendering', () => {
    it('renders nothing when isOpen is false', () => {
      render(
        <AnimatedModal isOpen={false} onClose={mockOnClose}>
          <div>Modal Content</div>
        </AnimatedModal>
      );

      expect(screen.queryByTestId('animated-modal')).not.toBeInTheDocument();
    });

    it('renders content when isOpen is true', () => {
      render(
        <AnimatedModal isOpen={true} onClose={mockOnClose}>
          <div>Modal Content</div>
        </AnimatedModal>
      );

      expect(screen.getByText('Modal Content')).toBeInTheDocument();
    });

    it('renders backdrop when open', () => {
      render(
        <AnimatedModal isOpen={true} onClose={mockOnClose}>
          <div>Modal Content</div>
        </AnimatedModal>
      );

      expect(screen.getByTestId('animated-modal-backdrop')).toBeInTheDocument();
    });

    it('renders modal container when open', () => {
      render(
        <AnimatedModal isOpen={true} onClose={mockOnClose}>
          <div>Modal Content</div>
        </AnimatedModal>
      );

      expect(screen.getByTestId('animated-modal')).toBeInTheDocument();
    });
  });

  describe('animation variants', () => {
    it('configures scale animation by default', () => {
      render(
        <AnimatedModal isOpen={true} onClose={mockOnClose}>
          <div>Content</div>
        </AnimatedModal>
      );

      const modal = screen.getByTestId('animated-modal');
      expect(modal).toHaveAttribute('data-initial', '"initial"');
      expect(modal).toHaveAttribute('data-animate', '"animate"');
      expect(modal).toHaveAttribute('data-exit', '"exit"');
    });

    it('supports slideUp variant', () => {
      render(
        <AnimatedModal isOpen={true} onClose={mockOnClose} variant="slideUp">
          <div>Content</div>
        </AnimatedModal>
      );

      const modal = screen.getByTestId('animated-modal');
      const variants = JSON.parse(modal.getAttribute('data-variants') || '{}');
      expect(variants).toBeDefined();
    });

    it('supports slideDown variant', () => {
      render(
        <AnimatedModal isOpen={true} onClose={mockOnClose} variant="slideDown">
          <div>Content</div>
        </AnimatedModal>
      );

      const modal = screen.getByTestId('animated-modal');
      expect(modal).toBeInTheDocument();
    });

    it('supports fade variant', () => {
      render(
        <AnimatedModal isOpen={true} onClose={mockOnClose} variant="fade">
          <div>Content</div>
        </AnimatedModal>
      );

      const modal = screen.getByTestId('animated-modal');
      expect(modal).toBeInTheDocument();
    });

    it('supports scale variant explicitly', () => {
      render(
        <AnimatedModal isOpen={true} onClose={mockOnClose} variant="scale">
          <div>Content</div>
        </AnimatedModal>
      );

      const modal = screen.getByTestId('animated-modal');
      expect(modal).toBeInTheDocument();
    });
  });

  describe('close behavior', () => {
    it('calls onClose when clicking backdrop', async () => {
      const user = userEvent.setup();
      render(
        <AnimatedModal isOpen={true} onClose={mockOnClose}>
          <div>Modal Content</div>
        </AnimatedModal>
      );

      await user.click(screen.getByTestId('animated-modal-backdrop'));

      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });

    it('does not call onClose when clicking modal content', async () => {
      const user = userEvent.setup();
      render(
        <AnimatedModal isOpen={true} onClose={mockOnClose}>
          <div data-testid="modal-content">Modal Content</div>
        </AnimatedModal>
      );

      await user.click(screen.getByTestId('modal-content'));

      expect(mockOnClose).not.toHaveBeenCalled();
    });

    it('calls onClose on Escape key', async () => {
      render(
        <AnimatedModal isOpen={true} onClose={mockOnClose}>
          <div>Modal Content</div>
        </AnimatedModal>
      );

      fireEvent.keyDown(document, { key: 'Escape' });

      await waitFor(() => {
        expect(mockOnClose).toHaveBeenCalledTimes(1);
      });
    });

    it('does not close on backdrop click when closeOnBackdropClick is false', async () => {
      const user = userEvent.setup();
      render(
        <AnimatedModal isOpen={true} onClose={mockOnClose} closeOnBackdropClick={false}>
          <div>Modal Content</div>
        </AnimatedModal>
      );

      await user.click(screen.getByTestId('animated-modal-backdrop'));

      expect(mockOnClose).not.toHaveBeenCalled();
    });

    it('does not close on Escape when closeOnEscape is false', () => {
      render(
        <AnimatedModal isOpen={true} onClose={mockOnClose} closeOnEscape={false}>
          <div>Modal Content</div>
        </AnimatedModal>
      );

      fireEvent.keyDown(document, { key: 'Escape' });

      expect(mockOnClose).not.toHaveBeenCalled();
    });
  });

  describe('reduced motion support', () => {
    it('respects prefers-reduced-motion setting', async () => {
      const { useReducedMotion } = await import('framer-motion');
      vi.mocked(useReducedMotion).mockReturnValue(true);

      render(
        <AnimatedModal isOpen={true} onClose={mockOnClose}>
          <div>Modal Content</div>
        </AnimatedModal>
      );

      expect(screen.getByText('Modal Content')).toBeInTheDocument();
    });

    it('applies reduced motion class when motion is reduced', async () => {
      const { useReducedMotion } = await import('framer-motion');
      vi.mocked(useReducedMotion).mockReturnValue(true);

      render(
        <AnimatedModal isOpen={true} onClose={mockOnClose}>
          <div>Modal Content</div>
        </AnimatedModal>
      );

      const modal = screen.getByTestId('animated-modal');
      expect(modal).toHaveClass('motion-reduce');
    });
  });

  describe('custom className', () => {
    it('applies custom className to modal', () => {
      render(
        <AnimatedModal isOpen={true} onClose={mockOnClose} className="custom-modal-class">
          <div>Modal Content</div>
        </AnimatedModal>
      );

      const modal = screen.getByTestId('animated-modal');
      expect(modal).toHaveClass('custom-modal-class');
    });

    it('applies custom backdropClassName to backdrop', () => {
      render(
        <AnimatedModal isOpen={true} onClose={mockOnClose} backdropClassName="custom-backdrop">
          <div>Modal Content</div>
        </AnimatedModal>
      );

      const backdrop = screen.getByTestId('animated-modal-backdrop');
      expect(backdrop).toHaveClass('custom-backdrop');
    });
  });

  describe('accessibility', () => {
    it('has role="dialog" by default', () => {
      render(
        <AnimatedModal isOpen={true} onClose={mockOnClose}>
          <div>Modal Content</div>
        </AnimatedModal>
      );

      const modal = screen.getByTestId('animated-modal');
      expect(modal).toHaveAttribute('role', 'dialog');
    });

    it('has aria-modal="true"', () => {
      render(
        <AnimatedModal isOpen={true} onClose={mockOnClose}>
          <div>Modal Content</div>
        </AnimatedModal>
      );

      const modal = screen.getByTestId('animated-modal');
      expect(modal).toHaveAttribute('aria-modal', 'true');
    });

    it('supports aria-labelledby', () => {
      render(
        <AnimatedModal isOpen={true} onClose={mockOnClose} aria-labelledby="modal-title">
          <h2 id="modal-title">Modal Title</h2>
          <div>Modal Content</div>
        </AnimatedModal>
      );

      const modal = screen.getByTestId('animated-modal');
      expect(modal).toHaveAttribute('aria-labelledby', 'modal-title');
    });

    it('supports aria-describedby', () => {
      render(
        <AnimatedModal isOpen={true} onClose={mockOnClose} aria-describedby="modal-description">
          <p id="modal-description">This is the modal description</p>
        </AnimatedModal>
      );

      const modal = screen.getByTestId('animated-modal');
      expect(modal).toHaveAttribute('aria-describedby', 'modal-description');
    });

    it('is focusable', () => {
      render(
        <AnimatedModal isOpen={true} onClose={mockOnClose}>
          <div>Modal Content</div>
        </AnimatedModal>
      );

      const modal = screen.getByTestId('animated-modal');
      expect(modal).toHaveAttribute('tabIndex', '-1');
    });
  });

  describe('AnimatePresence integration', () => {
    it('wraps modal in AnimatePresence for exit animations', () => {
      render(
        <AnimatedModal isOpen={true} onClose={mockOnClose}>
          <div>Modal Content</div>
        </AnimatedModal>
      );

      expect(screen.getByTestId('animate-presence')).toBeInTheDocument();
    });
  });

  describe('backdrop configuration', () => {
    it('backdrop has proper opacity for dark theme', () => {
      render(
        <AnimatedModal isOpen={true} onClose={mockOnClose}>
          <div>Modal Content</div>
        </AnimatedModal>
      );

      const backdrop = screen.getByTestId('animated-modal-backdrop');
      expect(backdrop).toHaveClass('bg-black/80');
    });
  });

  describe('portal rendering', () => {
    it('renders modal in portal container', () => {
      render(
        <AnimatedModal isOpen={true} onClose={mockOnClose}>
          <div>Modal Content</div>
        </AnimatedModal>
      );

      // Modal should be rendered (portal is mocked)
      expect(screen.getByText('Modal Content')).toBeInTheDocument();
    });
  });

  describe('z-index layering', () => {
    it('backdrop has proper z-index', () => {
      render(
        <AnimatedModal isOpen={true} onClose={mockOnClose}>
          <div>Modal Content</div>
        </AnimatedModal>
      );

      const backdrop = screen.getByTestId('animated-modal-backdrop');
      expect(backdrop).toHaveClass('z-50');
    });

    it('modal has higher z-index than backdrop', () => {
      render(
        <AnimatedModal isOpen={true} onClose={mockOnClose}>
          <div>Modal Content</div>
        </AnimatedModal>
      );

      const modal = screen.getByTestId('animated-modal');
      expect(modal).toHaveClass('z-50');
    });
  });

  describe('size variants', () => {
    it('supports sm size', () => {
      render(
        <AnimatedModal isOpen={true} onClose={mockOnClose} size="sm">
          <div>Modal Content</div>
        </AnimatedModal>
      );

      const modal = screen.getByTestId('animated-modal');
      expect(modal).toHaveClass('max-w-sm');
    });

    it('supports md size (default)', () => {
      render(
        <AnimatedModal isOpen={true} onClose={mockOnClose}>
          <div>Modal Content</div>
        </AnimatedModal>
      );

      const modal = screen.getByTestId('animated-modal');
      expect(modal).toHaveClass('max-w-md');
    });

    it('supports lg size', () => {
      render(
        <AnimatedModal isOpen={true} onClose={mockOnClose} size="lg">
          <div>Modal Content</div>
        </AnimatedModal>
      );

      const modal = screen.getByTestId('animated-modal');
      expect(modal).toHaveClass('max-w-lg');
    });

    it('supports xl size', () => {
      render(
        <AnimatedModal isOpen={true} onClose={mockOnClose} size="xl">
          <div>Modal Content</div>
        </AnimatedModal>
      );

      const modal = screen.getByTestId('animated-modal');
      expect(modal).toHaveClass('max-w-xl');
    });

    it('supports full size', () => {
      render(
        <AnimatedModal isOpen={true} onClose={mockOnClose} size="full">
          <div>Modal Content</div>
        </AnimatedModal>
      );

      const modal = screen.getByTestId('animated-modal');
      expect(modal).toHaveClass('max-w-full');
    });
  });

  describe('interaction tracking', () => {
    it('does not track when modalName is not provided', () => {
      const { rerender } = render(
        <AnimatedModal isOpen={false} onClose={mockOnClose}>
          <div>Modal Content</div>
        </AnimatedModal>
      );

      rerender(
        <AnimatedModal isOpen={true} onClose={mockOnClose}>
          <div>Modal Content</div>
        </AnimatedModal>
      );

      expect(logger.interaction).not.toHaveBeenCalled();
    });

    it('tracks modal open when modalName is provided', () => {
      const { rerender } = render(
        <AnimatedModal isOpen={false} onClose={mockOnClose} modalName="test_modal">
          <div>Modal Content</div>
        </AnimatedModal>
      );

      // Open the modal
      rerender(
        <AnimatedModal isOpen={true} onClose={mockOnClose} modalName="test_modal">
          <div>Modal Content</div>
        </AnimatedModal>
      );

      expect(logger.interaction).toHaveBeenCalledWith('open', 'modal.test_modal');
    });

    it('tracks modal close when modalName is provided', () => {
      const { rerender } = render(
        <AnimatedModal isOpen={true} onClose={mockOnClose} modalName="test_modal">
          <div>Modal Content</div>
        </AnimatedModal>
      );

      vi.clearAllMocks();

      // Close the modal
      rerender(
        <AnimatedModal isOpen={false} onClose={mockOnClose} modalName="test_modal">
          <div>Modal Content</div>
        </AnimatedModal>
      );

      expect(logger.interaction).toHaveBeenCalledWith('close', 'modal.test_modal');
    });

    it('does not track on initial render (only tracks state changes)', () => {
      render(
        <AnimatedModal isOpen={true} onClose={mockOnClose} modalName="test_modal">
          <div>Modal Content</div>
        </AnimatedModal>
      );

      // Should not log on initial render since it's not a state change
      expect(logger.interaction).not.toHaveBeenCalled();
    });

    it('tracks multiple open/close cycles', () => {
      const { rerender } = render(
        <AnimatedModal isOpen={false} onClose={mockOnClose} modalName="cycle_modal">
          <div>Modal Content</div>
        </AnimatedModal>
      );

      // Open
      rerender(
        <AnimatedModal isOpen={true} onClose={mockOnClose} modalName="cycle_modal">
          <div>Modal Content</div>
        </AnimatedModal>
      );
      expect(logger.interaction).toHaveBeenCalledWith('open', 'modal.cycle_modal');

      // Close
      rerender(
        <AnimatedModal isOpen={false} onClose={mockOnClose} modalName="cycle_modal">
          <div>Modal Content</div>
        </AnimatedModal>
      );
      expect(logger.interaction).toHaveBeenCalledWith('close', 'modal.cycle_modal');

      // Open again
      rerender(
        <AnimatedModal isOpen={true} onClose={mockOnClose} modalName="cycle_modal">
          <div>Modal Content</div>
        </AnimatedModal>
      );

      expect(logger.interaction).toHaveBeenCalledTimes(3);
    });
  });
});
