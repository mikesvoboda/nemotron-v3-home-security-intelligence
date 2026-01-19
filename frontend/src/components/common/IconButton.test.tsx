import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { X, Settings, Save, Filter, ChevronLeft, ChevronRight } from 'lucide-react';
import { describe, it, expect, vi } from 'vitest';

import IconButton from './IconButton';

describe('IconButton', () => {
  describe('rendering', () => {
    it('renders with required aria-label', () => {
      render(<IconButton icon={<X />} aria-label="Close modal" />);
      const button = screen.getByRole('button', { name: /close modal/i });
      expect(button).toBeInTheDocument();
      expect(button).toHaveAttribute('aria-label', 'Close modal');
    });

    it('renders the icon', () => {
      render(<IconButton icon={<X data-testid="x-icon" />} aria-label="Close" />);
      expect(screen.getByTestId('x-icon')).toBeInTheDocument();
    });

    it('renders with default type="button"', () => {
      render(<IconButton icon={<X />} aria-label="Close" />);
      expect(screen.getByRole('button')).toHaveAttribute('type', 'button');
    });

    it('applies custom className', () => {
      render(<IconButton icon={<X />} aria-label="Close" className="custom-class" />);
      expect(screen.getByRole('button')).toHaveClass('custom-class');
    });

    it('passes additional HTML attributes', () => {
      render(<IconButton icon={<X />} aria-label="Close" data-testid="custom-button" />);
      expect(screen.getByTestId('custom-button')).toBeInTheDocument();
    });
  });

  describe('minimum touch target size (WCAG 2.5.5 AAA)', () => {
    it('has min-h-11 min-w-11 classes for sm size', () => {
      render(<IconButton icon={<X />} aria-label="Close" size="sm" />);
      const button = screen.getByRole('button');
      expect(button).toHaveClass('min-h-11');
      expect(button).toHaveClass('min-w-11');
      expect(button).toHaveClass('h-11');
      expect(button).toHaveClass('w-11');
    });

    it('has min-h-11 min-w-11 classes for md size (default)', () => {
      render(<IconButton icon={<X />} aria-label="Close" />);
      const button = screen.getByRole('button');
      expect(button).toHaveClass('min-h-11');
      expect(button).toHaveClass('min-w-11');
      expect(button).toHaveClass('h-11');
      expect(button).toHaveClass('w-11');
    });

    it('has min-h-12 min-w-12 classes for lg size', () => {
      render(<IconButton icon={<X />} aria-label="Close" size="lg" />);
      const button = screen.getByRole('button');
      expect(button).toHaveClass('min-h-12');
      expect(button).toHaveClass('min-w-12');
      expect(button).toHaveClass('h-12');
      expect(button).toHaveClass('w-12');
    });
  });

  describe('size variants', () => {
    it('applies sm size classes correctly', () => {
      render(<IconButton icon={<X />} aria-label="Close" size="sm" />);
      const button = screen.getByRole('button');
      expect(button).toHaveClass('h-11');
      expect(button).toHaveClass('w-11');
      expect(button).toHaveClass('[&>svg]:h-4');
      expect(button).toHaveClass('[&>svg]:w-4');
    });

    it('applies md size classes correctly (default)', () => {
      render(<IconButton icon={<X />} aria-label="Close" size="md" />);
      const button = screen.getByRole('button');
      expect(button).toHaveClass('h-11');
      expect(button).toHaveClass('w-11');
      expect(button).toHaveClass('[&>svg]:h-5');
      expect(button).toHaveClass('[&>svg]:w-5');
    });

    it('applies lg size classes correctly', () => {
      render(<IconButton icon={<X />} aria-label="Close" size="lg" />);
      const button = screen.getByRole('button');
      expect(button).toHaveClass('h-12');
      expect(button).toHaveClass('w-12');
      expect(button).toHaveClass('[&>svg]:h-6');
      expect(button).toHaveClass('[&>svg]:w-6');
    });
  });

  describe('variant styles', () => {
    it('applies ghost variant by default', () => {
      render(<IconButton icon={<X />} aria-label="Close" />);
      const button = screen.getByRole('button');
      expect(button).toHaveClass('bg-transparent');
      expect(button).toHaveClass('text-gray-400');
      expect(button).toHaveClass('hover:bg-gray-800');
      expect(button).toHaveClass('hover:text-white');
    });

    it('applies ghost variant classes', () => {
      render(<IconButton icon={<X />} aria-label="Close" variant="ghost" />);
      const button = screen.getByRole('button');
      expect(button).toHaveClass('bg-transparent');
      expect(button).toHaveClass('text-gray-400');
      expect(button).toHaveClass('hover:bg-gray-800');
    });

    it('applies outline variant classes', () => {
      render(<IconButton icon={<X />} aria-label="Close" variant="outline" />);
      const button = screen.getByRole('button');
      expect(button).toHaveClass('border');
      expect(button).toHaveClass('border-gray-700');
      expect(button).toHaveClass('bg-transparent');
    });

    it('applies solid variant classes', () => {
      render(<IconButton icon={<X />} aria-label="Close" variant="solid" />);
      const button = screen.getByRole('button');
      expect(button).toHaveClass('bg-gray-800');
      expect(button).toHaveClass('text-white');
      expect(button).toHaveClass('hover:bg-gray-700');
    });
  });

  describe('loading state', () => {
    it('shows loading spinner when isLoading is true', () => {
      render(<IconButton icon={<X data-testid="x-icon" />} aria-label="Close" isLoading />);
      const button = screen.getByRole('button');
      // Icon should be replaced by spinner
      expect(screen.queryByTestId('x-icon')).not.toBeInTheDocument();
      // Should have a spinning SVG
      const spinner = button.querySelector('svg.animate-spin');
      expect(spinner).toBeInTheDocument();
    });

    it('disables button when loading', () => {
      render(<IconButton icon={<X />} aria-label="Close" isLoading />);
      expect(screen.getByRole('button')).toBeDisabled();
    });

    it('sets aria-busy when loading', () => {
      render(<IconButton icon={<X />} aria-label="Close" isLoading />);
      expect(screen.getByRole('button')).toHaveAttribute('aria-busy', 'true');
    });

    it('applies cursor-wait class when loading', () => {
      render(<IconButton icon={<X />} aria-label="Close" isLoading />);
      expect(screen.getByRole('button')).toHaveClass('cursor-wait');
    });

    it('applies opacity-50 class when loading', () => {
      render(<IconButton icon={<X />} aria-label="Close" isLoading />);
      expect(screen.getByRole('button')).toHaveClass('opacity-50');
    });
  });

  describe('active state', () => {
    it('applies active styling when isActive is true (ghost variant)', () => {
      render(<IconButton icon={<Filter />} aria-label="Toggle filter" isActive />);
      const button = screen.getByRole('button');
      expect(button).toHaveClass('bg-gray-800');
      expect(button).toHaveClass('text-white');
    });

    it('applies active styling when isActive is true (outline variant)', () => {
      render(
        <IconButton icon={<Filter />} aria-label="Toggle filter" isActive variant="outline" />
      );
      const button = screen.getByRole('button');
      expect(button).toHaveClass('border-[#76B900]');
      expect(button).toHaveClass('bg-[#76B900]/10');
      expect(button).toHaveClass('text-[#76B900]');
    });

    it('applies active styling when isActive is true (solid variant)', () => {
      render(<IconButton icon={<Filter />} aria-label="Toggle filter" isActive variant="solid" />);
      const button = screen.getByRole('button');
      expect(button).toHaveClass('bg-[#76B900]');
      expect(button).toHaveClass('text-black');
    });

    it('sets aria-pressed when isActive is true', () => {
      render(<IconButton icon={<Filter />} aria-label="Toggle filter" isActive />);
      expect(screen.getByRole('button')).toHaveAttribute('aria-pressed', 'true');
    });

    it('sets aria-pressed to false when isActive is false', () => {
      render(<IconButton icon={<Filter />} aria-label="Toggle filter" isActive={false} />);
      expect(screen.getByRole('button')).toHaveAttribute('aria-pressed', 'false');
    });
  });

  describe('click handling', () => {
    it('triggers onClick handler when clicked', () => {
      const onClick = vi.fn();
      render(<IconButton icon={<X />} aria-label="Close" onClick={onClick} />);
      fireEvent.click(screen.getByRole('button'));
      expect(onClick).toHaveBeenCalledTimes(1);
    });

    it('does not trigger onClick when disabled', () => {
      const onClick = vi.fn();
      render(<IconButton icon={<X />} aria-label="Close" onClick={onClick} disabled />);
      fireEvent.click(screen.getByRole('button'));
      expect(onClick).not.toHaveBeenCalled();
    });

    it('does not trigger onClick when loading', () => {
      const onClick = vi.fn();
      render(<IconButton icon={<X />} aria-label="Close" onClick={onClick} isLoading />);
      fireEvent.click(screen.getByRole('button'));
      expect(onClick).not.toHaveBeenCalled();
    });
  });

  describe('disabled state', () => {
    it('disables button when disabled prop is true', () => {
      render(<IconButton icon={<X />} aria-label="Close" disabled />);
      expect(screen.getByRole('button')).toBeDisabled();
    });

    it('applies opacity-50 when disabled', () => {
      render(<IconButton icon={<X />} aria-label="Close" disabled />);
      expect(screen.getByRole('button')).toHaveClass('opacity-50');
    });

    it('applies cursor-not-allowed when disabled', () => {
      render(<IconButton icon={<X />} aria-label="Close" disabled />);
      expect(screen.getByRole('button')).toHaveClass('cursor-not-allowed');
    });
  });

  describe('focus styles', () => {
    it('has focus-visible ring classes', () => {
      render(<IconButton icon={<X />} aria-label="Close" />);
      const button = screen.getByRole('button');
      expect(button).toHaveClass('focus-visible:ring-2');
      expect(button).toHaveClass('focus-visible:ring-[#76B900]');
    });

    it('has focus-visible ring-offset classes', () => {
      render(<IconButton icon={<X />} aria-label="Close" />);
      const button = screen.getByRole('button');
      expect(button).toHaveClass('focus-visible:ring-offset-2');
      expect(button).toHaveClass('focus-visible:ring-offset-gray-900');
    });
  });

  describe('tooltip support', () => {
    it('renders without tooltip by default', () => {
      render(<IconButton icon={<Settings />} aria-label="Settings" />);
      expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
    });

    it('shows tooltip on hover when tooltip prop is provided', async () => {
      render(
        <IconButton icon={<Settings />} aria-label="Open settings" tooltip="Settings" />
      );

      const button = screen.getByRole('button');
      fireEvent.mouseEnter(button);

      await waitFor(() => {
        expect(screen.getByRole('tooltip')).toBeInTheDocument();
        expect(screen.getByText('Settings')).toBeInTheDocument();
      });
    });

    it('does not show tooltip when disabled', async () => {
      render(
        <IconButton icon={<Settings />} aria-label="Open settings" tooltip="Settings" disabled />
      );

      const button = screen.getByRole('button');
      fireEvent.mouseEnter(button);

      // Wait a bit and verify tooltip doesn't appear
      await waitFor(
        () => {
          expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
        },
        { timeout: 500 }
      );
    });

    it('does not show tooltip when loading', async () => {
      render(
        <IconButton icon={<Settings />} aria-label="Open settings" tooltip="Settings" isLoading />
      );

      const button = screen.getByRole('button');
      fireEvent.mouseEnter(button);

      // Wait a bit and verify tooltip doesn't appear
      await waitFor(
        () => {
          expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
        },
        { timeout: 500 }
      );
    });
  });

  describe('ref forwarding', () => {
    it('forwards ref to button element', () => {
      const ref = { current: null as HTMLButtonElement | null };
      render(<IconButton ref={ref} icon={<X />} aria-label="Close" />);
      expect(ref.current).toBeInstanceOf(HTMLButtonElement);
    });
  });

  describe('navigation button examples', () => {
    it('works as previous/next navigation buttons', () => {
      const onPrev = vi.fn();
      const onNext = vi.fn();

      render(
        <>
          <IconButton icon={<ChevronLeft />} aria-label="Previous" onClick={onPrev} />
          <IconButton icon={<ChevronRight />} aria-label="Next" onClick={onNext} />
        </>
      );

      fireEvent.click(screen.getByRole('button', { name: /previous/i }));
      expect(onPrev).toHaveBeenCalledTimes(1);

      fireEvent.click(screen.getByRole('button', { name: /next/i }));
      expect(onNext).toHaveBeenCalledTimes(1);
    });
  });

  describe('accessibility', () => {
    it('has correct role', () => {
      render(<IconButton icon={<X />} aria-label="Close" />);
      expect(screen.getByRole('button')).toBeInTheDocument();
    });

    it('aria-label is accessible to screen readers', () => {
      render(<IconButton icon={<X />} aria-label="Close modal dialog" />);
      expect(screen.getByRole('button', { name: /close modal dialog/i })).toBeInTheDocument();
    });

    it('announces loading state via aria-busy', () => {
      const { rerender } = render(<IconButton icon={<Save />} aria-label="Save" />);
      expect(screen.getByRole('button')).toHaveAttribute('aria-busy', 'false');

      rerender(<IconButton icon={<Save />} aria-label="Save" isLoading />);
      expect(screen.getByRole('button')).toHaveAttribute('aria-busy', 'true');
    });

    it('announces active state via aria-pressed', () => {
      const { rerender } = render(<IconButton icon={<Filter />} aria-label="Filter" />);
      expect(screen.getByRole('button')).toHaveAttribute('aria-pressed', 'false');

      rerender(<IconButton icon={<Filter />} aria-label="Filter" isActive />);
      expect(screen.getByRole('button')).toHaveAttribute('aria-pressed', 'true');
    });
  });
});
