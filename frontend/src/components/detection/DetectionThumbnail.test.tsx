import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import DetectionThumbnail from './DetectionThumbnail';

// Mock the api module
vi.mock('../../services/api', () => ({
  getDetectionImageUrl: (id: number) => `/api/detections/${id}/image`,
}));

describe('DetectionThumbnail', () => {
  const defaultProps = {
    detectionId: 123,
    alt: 'Person detected at front door',
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('rendering', () => {
    it('renders without crashing', () => {
      const { container } = render(<DetectionThumbnail {...defaultProps} />);
      expect(container).toBeInTheDocument();
    });

    it('shows loading skeleton by default', () => {
      render(<DetectionThumbnail {...defaultProps} />);
      expect(screen.getByTestId('loading-skeleton')).toBeInTheDocument();
    });

    it('renders hidden image during loading state', () => {
      const { container } = render(<DetectionThumbnail {...defaultProps} />);
      const hiddenImg = container.querySelector('img[aria-hidden="true"]');
      expect(hiddenImg).toBeInTheDocument();
      expect(hiddenImg).toHaveClass('opacity-0');
    });

    it('uses correct image URL from getDetectionImageUrl', () => {
      const { container } = render(<DetectionThumbnail {...defaultProps} />);
      const img = container.querySelector('img');
      expect(img).toHaveAttribute('src', '/api/detections/123/image');
    });

    it('does not show loading skeleton when showLoading is false', () => {
      render(<DetectionThumbnail {...defaultProps} showLoading={false} />);
      expect(screen.queryByTestId('loading-skeleton')).not.toBeInTheDocument();
    });

    it('renders custom loading placeholder when provided', () => {
      render(
        <DetectionThumbnail
          {...defaultProps}
          loadingPlaceholder={<div data-testid="custom-loading">Custom Loading</div>}
        />
      );
      expect(screen.getByTestId('custom-loading')).toBeInTheDocument();
      expect(screen.queryByTestId('loading-skeleton')).not.toBeInTheDocument();
    });
  });

  describe('size variants', () => {
    it('applies medium size classes by default', () => {
      render(<DetectionThumbnail {...defaultProps} />);
      const skeleton = screen.getByTestId('loading-skeleton');
      expect(skeleton).toHaveClass('w-[240px]', 'h-[180px]');
    });

    it('applies small size classes when size="sm"', () => {
      render(<DetectionThumbnail {...defaultProps} size="sm" />);
      const skeleton = screen.getByTestId('loading-skeleton');
      expect(skeleton).toHaveClass('w-[120px]', 'h-[90px]');
    });

    it('applies large size classes when size="lg"', () => {
      render(<DetectionThumbnail {...defaultProps} size="lg" />);
      const skeleton = screen.getByTestId('loading-skeleton');
      expect(skeleton).toHaveClass('w-[320px]', 'h-[240px]');
    });
  });

  describe('loading state', () => {
    it('transitions to loaded state on image load', async () => {
      const { container } = render(<DetectionThumbnail {...defaultProps} />);

      // Initially shows loading skeleton
      expect(screen.getByTestId('loading-skeleton')).toBeInTheDocument();

      // Simulate image load
      const hiddenImg = container.querySelector('img[aria-hidden="true"]') as HTMLImageElement;
      fireEvent.load(hiddenImg);

      await waitFor(() => {
        expect(screen.queryByTestId('loading-skeleton')).not.toBeInTheDocument();
      });
    });

    it('shows image with correct alt text after loading', async () => {
      const { container } = render(<DetectionThumbnail {...defaultProps} />);

      const hiddenImg = container.querySelector('img[aria-hidden="true"]') as HTMLImageElement;
      fireEvent.load(hiddenImg);

      await waitFor(() => {
        const visibleImg = container.querySelector('img:not([aria-hidden])');
        expect(visibleImg).toHaveAttribute('alt', 'Person detected at front door');
      });
    });
  });

  describe('error state', () => {
    it('shows error display on image load failure', async () => {
      const { container } = render(<DetectionThumbnail {...defaultProps} />);

      const hiddenImg = container.querySelector('img[aria-hidden="true"]') as HTMLImageElement;
      fireEvent.error(hiddenImg);

      await waitFor(() => {
        expect(screen.getByTestId('error-display')).toBeInTheDocument();
      });
    });

    it('shows error message in error display', async () => {
      const { container } = render(<DetectionThumbnail {...defaultProps} />);

      const hiddenImg = container.querySelector('img[aria-hidden="true"]') as HTMLImageElement;
      fireEvent.error(hiddenImg);

      await waitFor(() => {
        expect(screen.getByText(/Failed to load|Image not found/)).toBeInTheDocument();
      });
    });

    it('shows retry button in error state', async () => {
      const { container } = render(<DetectionThumbnail {...defaultProps} />);

      const hiddenImg = container.querySelector('img[aria-hidden="true"]') as HTMLImageElement;
      fireEvent.error(hiddenImg);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
      });
    });

    it('resets to loading state when retry is clicked', async () => {
      const { container } = render(<DetectionThumbnail {...defaultProps} />);

      // Trigger error state
      const hiddenImg = container.querySelector('img[aria-hidden="true"]') as HTMLImageElement;
      fireEvent.error(hiddenImg);

      await waitFor(() => {
        expect(screen.getByTestId('error-display')).toBeInTheDocument();
      });

      // Click retry
      fireEvent.click(screen.getByRole('button', { name: /retry/i }));

      // Should show loading again
      await waitFor(() => {
        expect(screen.getByTestId('loading-skeleton')).toBeInTheDocument();
        expect(screen.queryByTestId('error-display')).not.toBeInTheDocument();
      });
    });

    it('renders custom error component when provided', async () => {
      const { container } = render(
        <DetectionThumbnail
          {...defaultProps}
          errorComponent={<div data-testid="custom-error">Custom Error</div>}
        />
      );

      const hiddenImg = container.querySelector('img[aria-hidden="true"]') as HTMLImageElement;
      fireEvent.error(hiddenImg);

      await waitFor(() => {
        expect(screen.getByTestId('custom-error')).toBeInTheDocument();
        expect(screen.queryByTestId('error-display')).not.toBeInTheDocument();
      });
    });
  });

  describe('click handling', () => {
    it('calls onClick when clicked', async () => {
      const handleClick = vi.fn();
      const { container } = render(<DetectionThumbnail {...defaultProps} onClick={handleClick} />);

      // Load the image first
      const hiddenImg = container.querySelector('img[aria-hidden="true"]') as HTMLImageElement;
      fireEvent.load(hiddenImg);

      await waitFor(() => {
        const wrapper = container.querySelector('div[role="button"]');
        expect(wrapper).toBeInTheDocument();
      });

      // Click the wrapper
      const wrapper = container.querySelector('div[role="button"]');
      fireEvent.click(wrapper!);

      expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it('adds button role when onClick is provided', async () => {
      const { container } = render(<DetectionThumbnail {...defaultProps} onClick={() => {}} />);

      const hiddenImg = container.querySelector('img[aria-hidden="true"]') as HTMLImageElement;
      fireEvent.load(hiddenImg);

      await waitFor(() => {
        const wrapper = container.querySelector('div[role="button"]');
        expect(wrapper).toBeInTheDocument();
        expect(wrapper).toHaveAttribute('tabindex', '0');
      });
    });

    it('does not add button role when onClick is not provided', async () => {
      const { container } = render(<DetectionThumbnail {...defaultProps} />);

      const hiddenImg = container.querySelector('img[aria-hidden="true"]') as HTMLImageElement;
      fireEvent.load(hiddenImg);

      await waitFor(() => {
        const wrapper = container.querySelector('div[role="button"]');
        expect(wrapper).not.toBeInTheDocument();
      });
    });

    it('handles keyboard activation with Enter key', async () => {
      const handleClick = vi.fn();
      const { container } = render(<DetectionThumbnail {...defaultProps} onClick={handleClick} />);

      const hiddenImg = container.querySelector('img[aria-hidden="true"]') as HTMLImageElement;
      fireEvent.load(hiddenImg);

      await waitFor(() => {
        const wrapper = container.querySelector('div[role="button"]');
        expect(wrapper).toBeInTheDocument();
      });

      const wrapper = container.querySelector('div[role="button"]');
      fireEvent.keyDown(wrapper!, { key: 'Enter' });

      expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it('handles keyboard activation with Space key', async () => {
      const handleClick = vi.fn();
      const { container } = render(<DetectionThumbnail {...defaultProps} onClick={handleClick} />);

      const hiddenImg = container.querySelector('img[aria-hidden="true"]') as HTMLImageElement;
      fireEvent.load(hiddenImg);

      await waitFor(() => {
        const wrapper = container.querySelector('div[role="button"]');
        expect(wrapper).toBeInTheDocument();
      });

      const wrapper = container.querySelector('div[role="button"]');
      fireEvent.keyDown(wrapper!, { key: ' ' });

      expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it('does not trigger onClick on other key presses', async () => {
      const handleClick = vi.fn();
      const { container } = render(<DetectionThumbnail {...defaultProps} onClick={handleClick} />);

      const hiddenImg = container.querySelector('img[aria-hidden="true"]') as HTMLImageElement;
      fireEvent.load(hiddenImg);

      await waitFor(() => {
        const wrapper = container.querySelector('div[role="button"]');
        expect(wrapper).toBeInTheDocument();
      });

      const wrapper = container.querySelector('div[role="button"]');
      fireEvent.keyDown(wrapper!, { key: 'Tab' });

      expect(handleClick).not.toHaveBeenCalled();
    });
  });

  describe('className prop', () => {
    it('applies custom className to wrapper', () => {
      const { container } = render(
        <DetectionThumbnail {...defaultProps} className="custom-class border-2" />
      );

      const wrapper = container.firstChild;
      expect(wrapper).toHaveClass('custom-class', 'border-2');
    });
  });

  describe('hover overlay', () => {
    it('renders hover overlay when onClick is provided', async () => {
      const { container } = render(<DetectionThumbnail {...defaultProps} onClick={() => {}} />);

      const hiddenImg = container.querySelector('img[aria-hidden="true"]') as HTMLImageElement;
      fireEvent.load(hiddenImg);

      await waitFor(() => {
        const overlay = container.querySelector('.hover\\:bg-black\\/20');
        expect(overlay).toBeInTheDocument();
      });
    });

    it('does not render hover overlay when onClick is not provided', async () => {
      const { container } = render(<DetectionThumbnail {...defaultProps} />);

      const hiddenImg = container.querySelector('img[aria-hidden="true"]') as HTMLImageElement;
      fireEvent.load(hiddenImg);

      await waitFor(() => {
        const overlay = container.querySelector('.hover\\:bg-black\\/20');
        expect(overlay).not.toBeInTheDocument();
      });
    });
  });

  describe('error recovery', () => {
    it('can recover from error state after retry succeeds', async () => {
      const { container } = render(<DetectionThumbnail {...defaultProps} />);

      // First, trigger error
      const hiddenImg = container.querySelector('img[aria-hidden="true"]') as HTMLImageElement;
      fireEvent.error(hiddenImg);

      await waitFor(() => {
        expect(screen.getByTestId('error-display')).toBeInTheDocument();
      });

      // Click retry
      fireEvent.click(screen.getByRole('button', { name: /retry/i }));

      // Now in loading state again
      await waitFor(() => {
        expect(screen.getByTestId('loading-skeleton')).toBeInTheDocument();
      });

      // Simulate successful load
      const newHiddenImg = container.querySelector('img[aria-hidden="true"]') as HTMLImageElement;
      fireEvent.load(newHiddenImg);

      // Should now show the image
      await waitFor(() => {
        expect(screen.queryByTestId('loading-skeleton')).not.toBeInTheDocument();
        expect(screen.queryByTestId('error-display')).not.toBeInTheDocument();
        const visibleImg = container.querySelector('img:not([aria-hidden])');
        expect(visibleImg).toBeInTheDocument();
      });
    });
  });

  describe('different detection IDs', () => {
    it('generates correct URL for different detection IDs', () => {
      const { container, rerender } = render(
        <DetectionThumbnail detectionId={1} alt="Detection 1" />
      );
      let img = container.querySelector('img');
      expect(img).toHaveAttribute('src', '/api/detections/1/image');

      rerender(<DetectionThumbnail detectionId={999} alt="Detection 999" />);
      img = container.querySelector('img');
      expect(img).toHaveAttribute('src', '/api/detections/999/image');
    });
  });

  describe('snapshots', () => {
    it('renders loading skeleton state', () => {
      const { container } = render(<DetectionThumbnail {...defaultProps} />);
      expect(container.firstChild).toMatchSnapshot();
    });

    it.each(['sm', 'md', 'lg'] as const)('renders %s size loading skeleton', (size) => {
      const { container } = render(<DetectionThumbnail {...defaultProps} size={size} />);
      expect(container.firstChild).toMatchSnapshot();
    });

    it('renders error state', async () => {
      const { container } = render(<DetectionThumbnail {...defaultProps} />);
      const hiddenImg = container.querySelector('img[aria-hidden="true"]') as HTMLImageElement;
      fireEvent.error(hiddenImg);

      await waitFor(() => {
        expect(screen.getByTestId('error-display')).toBeInTheDocument();
      });

      expect(container.firstChild).toMatchSnapshot();
    });

    it('renders loaded state with image', async () => {
      const { container } = render(<DetectionThumbnail {...defaultProps} />);
      const hiddenImg = container.querySelector('img[aria-hidden="true"]') as HTMLImageElement;
      fireEvent.load(hiddenImg);

      await waitFor(() => {
        expect(screen.queryByTestId('loading-skeleton')).not.toBeInTheDocument();
      });

      expect(container.firstChild).toMatchSnapshot();
    });

    it('renders with onClick handler (clickable state)', async () => {
      const { container } = render(
        <DetectionThumbnail {...defaultProps} onClick={() => {}} />
      );
      const hiddenImg = container.querySelector('img[aria-hidden="true"]') as HTMLImageElement;
      fireEvent.load(hiddenImg);

      await waitFor(() => {
        expect(screen.queryByTestId('loading-skeleton')).not.toBeInTheDocument();
      });

      expect(container.firstChild).toMatchSnapshot();
    });

    it('renders with custom className', () => {
      const { container } = render(
        <DetectionThumbnail {...defaultProps} className="custom-border border-4" />
      );
      expect(container.firstChild).toMatchSnapshot();
    });

    it('renders with showLoading disabled', () => {
      const { container } = render(<DetectionThumbnail {...defaultProps} showLoading={false} />);
      expect(container.firstChild).toMatchSnapshot();
    });
  });
});
