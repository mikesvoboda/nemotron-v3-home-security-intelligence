import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import BottomSheet from './BottomSheet';

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
      onDragEnd: _onDragEnd,
      role,
      'aria-modal': ariaModal,
      'aria-labelledby': ariaLabelledby,
      'aria-describedby': ariaDescribedby,
      'aria-hidden': ariaHidden,
      tabIndex,
      drag,
      dragConstraints,
      dragElastic,
      ...props
    }: {
      children?: React.ReactNode;
      className?: string;
      'data-testid'?: string;
      initial?: string | object;
      animate?: string | object;
      exit?: string | object;
      variants?: object;
      onClick?: (e: React.MouseEvent) => void;
      onKeyDown?: () => void;
      onDragEnd?: (event: unknown, info: unknown) => void;
      role?: string;
      'aria-modal'?: boolean;
      'aria-labelledby'?: string;
      'aria-describedby'?: string;
      'aria-hidden'?: boolean;
      tabIndex?: number;
      drag?: string;
      dragConstraints?: object;
      dragElastic?: object;
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
        data-drag={drag}
        data-drag-constraints={JSON.stringify(dragConstraints)}
        data-drag-elastic={JSON.stringify(dragElastic)}
        onClick={onClick}
        onKeyDown={onKeyDown}
        role={role || 'presentation'}
        aria-modal={ariaModal}
        aria-labelledby={ariaLabelledby}
        aria-describedby={ariaDescribedby}
        aria-hidden={ariaHidden}
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

describe('BottomSheet', () => {
  const mockOnClose = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    // Reset body overflow
    document.body.style.overflow = '';
  });

  describe('basic rendering', () => {
    it('renders nothing when isOpen is false', () => {
      render(
        <BottomSheet isOpen={false} onClose={mockOnClose}>
          <div>Sheet Content</div>
        </BottomSheet>
      );

      expect(screen.queryByTestId('bottom-sheet')).not.toBeInTheDocument();
    });

    it('renders content when isOpen is true', () => {
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose}>
          <div>Sheet Content</div>
        </BottomSheet>
      );

      expect(screen.getByText('Sheet Content')).toBeInTheDocument();
    });

    it('renders backdrop when open', () => {
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose}>
          <div>Sheet Content</div>
        </BottomSheet>
      );

      expect(screen.getByTestId('bottom-sheet-backdrop')).toBeInTheDocument();
    });

    it('renders bottom sheet container when open', () => {
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose}>
          <div>Sheet Content</div>
        </BottomSheet>
      );

      expect(screen.getByTestId('bottom-sheet')).toBeInTheDocument();
    });
  });

  describe('title rendering', () => {
    it('renders title when provided', () => {
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose} title="Test Title">
          <div>Sheet Content</div>
        </BottomSheet>
      );

      expect(screen.getByTestId('bottom-sheet-title')).toBeInTheDocument();
      expect(screen.getByText('Test Title')).toBeInTheDocument();
    });

    it('does not render title element when not provided', () => {
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose}>
          <div>Sheet Content</div>
        </BottomSheet>
      );

      expect(screen.queryByTestId('bottom-sheet-title')).not.toBeInTheDocument();
    });
  });

  describe('drag handle visibility', () => {
    it('shows drag handle by default', () => {
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose}>
          <div>Sheet Content</div>
        </BottomSheet>
      );

      expect(screen.getByTestId('bottom-sheet-drag-handle')).toBeInTheDocument();
    });

    it('hides drag handle when showDragHandle is false', () => {
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose} showDragHandle={false}>
          <div>Sheet Content</div>
        </BottomSheet>
      );

      expect(screen.queryByTestId('bottom-sheet-drag-handle')).not.toBeInTheDocument();
    });
  });

  describe('close button', () => {
    it('shows close button by default', () => {
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose}>
          <div>Sheet Content</div>
        </BottomSheet>
      );

      expect(screen.getByTestId('bottom-sheet-close-button')).toBeInTheDocument();
    });

    it('hides close button when showCloseButton is false', () => {
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose} showCloseButton={false}>
          <div>Sheet Content</div>
        </BottomSheet>
      );

      expect(screen.queryByTestId('bottom-sheet-close-button')).not.toBeInTheDocument();
    });

    it('has 44x44px minimum touch target for accessibility', () => {
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose}>
          <div>Sheet Content</div>
        </BottomSheet>
      );

      const closeButton = screen.getByTestId('bottom-sheet-close-button');
      expect(closeButton).toHaveClass('min-h-[44px]');
      expect(closeButton).toHaveClass('min-w-[44px]');
    });

    it('calls onClose when close button is clicked', async () => {
      const user = userEvent.setup();
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose}>
          <div>Sheet Content</div>
        </BottomSheet>
      );

      await user.click(screen.getByTestId('bottom-sheet-close-button'));

      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });
  });

  describe('backdrop click closes', () => {
    it('calls onClose when clicking backdrop', async () => {
      const user = userEvent.setup();
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose}>
          <div>Sheet Content</div>
        </BottomSheet>
      );

      await user.click(screen.getByTestId('bottom-sheet-backdrop'));

      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });

    it('does not close on backdrop click when closeOnBackdropClick is false', async () => {
      const user = userEvent.setup();
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose} closeOnBackdropClick={false}>
          <div>Sheet Content</div>
        </BottomSheet>
      );

      await user.click(screen.getByTestId('bottom-sheet-backdrop'));

      expect(mockOnClose).not.toHaveBeenCalled();
    });

    it('does not call onClose when clicking sheet content', async () => {
      const user = userEvent.setup();
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose}>
          <div data-testid="sheet-content">Sheet Content</div>
        </BottomSheet>
      );

      await user.click(screen.getByTestId('sheet-content'));

      expect(mockOnClose).not.toHaveBeenCalled();
    });
  });

  describe('escape key closes', () => {
    it('calls onClose on Escape key', async () => {
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose}>
          <div>Sheet Content</div>
        </BottomSheet>
      );

      fireEvent.keyDown(document, { key: 'Escape' });

      await waitFor(() => {
        expect(mockOnClose).toHaveBeenCalledTimes(1);
      });
    });

    it('does not close on Escape when closeOnEscape is false', () => {
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose} closeOnEscape={false}>
          <div>Sheet Content</div>
        </BottomSheet>
      );

      fireEvent.keyDown(document, { key: 'Escape' });

      expect(mockOnClose).not.toHaveBeenCalled();
    });
  });

  describe('body scroll prevention', () => {
    it('prevents body scroll when open', () => {
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose}>
          <div>Sheet Content</div>
        </BottomSheet>
      );

      expect(document.body.style.overflow).toBe('hidden');
    });

    it('restores body scroll when closed', () => {
      const { rerender } = render(
        <BottomSheet isOpen={true} onClose={mockOnClose}>
          <div>Sheet Content</div>
        </BottomSheet>
      );

      expect(document.body.style.overflow).toBe('hidden');

      rerender(
        <BottomSheet isOpen={false} onClose={mockOnClose}>
          <div>Sheet Content</div>
        </BottomSheet>
      );

      expect(document.body.style.overflow).toBe('');
    });

    it('restores original body overflow on unmount', () => {
      document.body.style.overflow = 'scroll';

      const { unmount } = render(
        <BottomSheet isOpen={true} onClose={mockOnClose}>
          <div>Sheet Content</div>
        </BottomSheet>
      );

      expect(document.body.style.overflow).toBe('hidden');

      unmount();

      expect(document.body.style.overflow).toBe('scroll');
    });
  });

  describe('ARIA attributes', () => {
    it('has role="dialog"', () => {
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose}>
          <div>Sheet Content</div>
        </BottomSheet>
      );

      const sheet = screen.getByTestId('bottom-sheet');
      expect(sheet).toHaveAttribute('role', 'dialog');
    });

    it('has aria-modal="true"', () => {
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose}>
          <div>Sheet Content</div>
        </BottomSheet>
      );

      const sheet = screen.getByTestId('bottom-sheet');
      expect(sheet).toHaveAttribute('aria-modal', 'true');
    });

    it('sets aria-labelledby to title id when title is provided', () => {
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose} title="My Title">
          <div>Sheet Content</div>
        </BottomSheet>
      );

      const sheet = screen.getByTestId('bottom-sheet');
      expect(sheet).toHaveAttribute('aria-labelledby', 'bottom-sheet-title');
    });

    it('supports custom aria-labelledby', () => {
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose} aria-labelledby="custom-label">
          <h2 id="custom-label">Custom Title</h2>
          <div>Sheet Content</div>
        </BottomSheet>
      );

      const sheet = screen.getByTestId('bottom-sheet');
      expect(sheet).toHaveAttribute('aria-labelledby', 'custom-label');
    });

    it('supports aria-describedby', () => {
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose} aria-describedby="sheet-description">
          <p id="sheet-description">This is the sheet description</p>
        </BottomSheet>
      );

      const sheet = screen.getByTestId('bottom-sheet');
      expect(sheet).toHaveAttribute('aria-describedby', 'sheet-description');
    });

    it('is focusable', () => {
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose}>
          <div>Sheet Content</div>
        </BottomSheet>
      );

      const sheet = screen.getByTestId('bottom-sheet');
      expect(sheet).toHaveAttribute('tabIndex', '-1');
    });

    it('backdrop has aria-hidden', () => {
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose}>
          <div>Sheet Content</div>
        </BottomSheet>
      );

      const backdrop = screen.getByTestId('bottom-sheet-backdrop');
      expect(backdrop).toHaveAttribute('aria-hidden', 'true');
    });
  });

  describe('height variants', () => {
    it('applies auto height class by default', () => {
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose}>
          <div>Sheet Content</div>
        </BottomSheet>
      );

      const sheet = screen.getByTestId('bottom-sheet');
      expect(sheet).toHaveClass('max-h-[85vh]');
    });

    it('applies half height class', () => {
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose} height="half">
          <div>Sheet Content</div>
        </BottomSheet>
      );

      const sheet = screen.getByTestId('bottom-sheet');
      expect(sheet).toHaveClass('max-h-[50vh]');
    });

    it('applies full height class', () => {
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose} height="full">
          <div>Sheet Content</div>
        </BottomSheet>
      );

      const sheet = screen.getByTestId('bottom-sheet');
      expect(sheet).toHaveClass('max-h-[calc(100vh-2rem)]');
    });
  });

  describe('drag functionality', () => {
    it('has drag="y" attribute for vertical dragging', () => {
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose}>
          <div>Sheet Content</div>
        </BottomSheet>
      );

      const sheet = screen.getByTestId('bottom-sheet');
      expect(sheet).toHaveAttribute('data-drag', 'y');
    });

    it('has drag constraints configured', () => {
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose}>
          <div>Sheet Content</div>
        </BottomSheet>
      );

      const sheet = screen.getByTestId('bottom-sheet');
      const constraints = JSON.parse(sheet.getAttribute('data-drag-constraints') || '{}');
      expect(constraints.top).toBe(0);
    });
  });

  describe('custom className', () => {
    it('applies custom className to sheet', () => {
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose} className="custom-sheet-class">
          <div>Sheet Content</div>
        </BottomSheet>
      );

      const sheet = screen.getByTestId('bottom-sheet');
      expect(sheet).toHaveClass('custom-sheet-class');
    });
  });

  describe('AnimatePresence integration', () => {
    it('wraps sheet in AnimatePresence for exit animations', () => {
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose}>
          <div>Sheet Content</div>
        </BottomSheet>
      );

      expect(screen.getByTestId('animate-presence')).toBeInTheDocument();
    });
  });

  describe('reduced motion support', () => {
    it('respects prefers-reduced-motion setting', async () => {
      const { useReducedMotion } = await import('framer-motion');
      vi.mocked(useReducedMotion).mockReturnValue(true);

      render(
        <BottomSheet isOpen={true} onClose={mockOnClose}>
          <div>Sheet Content</div>
        </BottomSheet>
      );

      expect(screen.getByText('Sheet Content')).toBeInTheDocument();
    });

    it('applies reduced motion class when motion is reduced', async () => {
      const { useReducedMotion } = await import('framer-motion');
      vi.mocked(useReducedMotion).mockReturnValue(true);

      render(
        <BottomSheet isOpen={true} onClose={mockOnClose}>
          <div>Sheet Content</div>
        </BottomSheet>
      );

      const sheet = screen.getByTestId('bottom-sheet');
      expect(sheet).toHaveClass('motion-reduce');
    });
  });

  describe('z-index layering', () => {
    it('backdrop has z-50', () => {
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose}>
          <div>Sheet Content</div>
        </BottomSheet>
      );

      const backdrop = screen.getByTestId('bottom-sheet-backdrop');
      expect(backdrop).toHaveClass('z-50');
    });

    it('sheet has z-50', () => {
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose}>
          <div>Sheet Content</div>
        </BottomSheet>
      );

      const sheet = screen.getByTestId('bottom-sheet');
      expect(sheet).toHaveClass('z-50');
    });
  });

  describe('styling', () => {
    it('has rounded top corners', () => {
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose}>
          <div>Sheet Content</div>
        </BottomSheet>
      );

      const sheet = screen.getByTestId('bottom-sheet');
      expect(sheet).toHaveClass('rounded-t-2xl');
    });

    it('positions at bottom of screen', () => {
      render(
        <BottomSheet isOpen={true} onClose={mockOnClose}>
          <div>Sheet Content</div>
        </BottomSheet>
      );

      const sheet = screen.getByTestId('bottom-sheet');
      expect(sheet).toHaveClass('bottom-0');
      expect(sheet).toHaveClass('left-0');
      expect(sheet).toHaveClass('right-0');
    });
  });
});
