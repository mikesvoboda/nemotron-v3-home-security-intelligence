import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import Lightbox from './Lightbox';

describe('Lightbox', () => {
  const mockOnClose = vi.fn();
  const mockOnIndexChange = vi.fn();

  const singleImage = {
    src: '/test-image.jpg',
    alt: 'Test image',
  };

  const multipleImages = [
    { src: '/image-1.jpg', alt: 'Image 1', caption: 'First image caption' },
    { src: '/image-2.jpg', alt: 'Image 2', caption: 'Second image caption' },
    { src: '/image-3.jpg', alt: 'Image 3' },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('basic rendering', () => {
    it('renders nothing when isOpen is false', () => {
      render(<Lightbox images={singleImage} isOpen={false} onClose={mockOnClose} />);
      expect(screen.queryByTestId('lightbox-image')).not.toBeInTheDocument();
    });

    it('renders image when isOpen is true', async () => {
      render(<Lightbox images={singleImage} isOpen={true} onClose={mockOnClose} />);
      await waitFor(() => {
        const image = screen.getByTestId('lightbox-image');
        expect(image).toBeInTheDocument();
        expect(image).toHaveAttribute('src', '/test-image.jpg');
        expect(image).toHaveAttribute('alt', 'Test image');
      });
    });

    it('renders backdrop when open', async () => {
      render(<Lightbox images={singleImage} isOpen={true} onClose={mockOnClose} />);
      await waitFor(() => {
        expect(screen.getByTestId('lightbox-backdrop')).toBeInTheDocument();
      });
    });

    it('renders close button when open', async () => {
      render(<Lightbox images={singleImage} isOpen={true} onClose={mockOnClose} />);
      await waitFor(() => {
        expect(screen.getByTestId('lightbox-close-button')).toBeInTheDocument();
      });
    });

    it('does not render navigation for single image', async () => {
      render(<Lightbox images={singleImage} isOpen={true} onClose={mockOnClose} />);
      await waitFor(() => {
        expect(screen.getByTestId('lightbox-image')).toBeInTheDocument();
      });
      expect(screen.queryByTestId('lightbox-prev-button')).not.toBeInTheDocument();
      expect(screen.queryByTestId('lightbox-next-button')).not.toBeInTheDocument();
    });

    it('does not render counter for single image', async () => {
      render(<Lightbox images={singleImage} isOpen={true} onClose={mockOnClose} />);
      await waitFor(() => {
        expect(screen.getByTestId('lightbox-image')).toBeInTheDocument();
      });
      expect(screen.queryByTestId('lightbox-counter')).not.toBeInTheDocument();
    });

    it('renders nothing when images array is empty', () => {
      render(<Lightbox images={[]} isOpen={true} onClose={mockOnClose} />);
      expect(screen.queryByTestId('lightbox-image')).not.toBeInTheDocument();
    });
  });

  describe('multi-image gallery', () => {
    it('renders navigation buttons for multiple images', async () => {
      render(<Lightbox images={multipleImages} isOpen={true} onClose={mockOnClose} />);
      await waitFor(() => {
        expect(screen.getByTestId('lightbox-prev-button')).toBeInTheDocument();
        expect(screen.getByTestId('lightbox-next-button')).toBeInTheDocument();
      });
    });

    it('renders image counter for multiple images', async () => {
      render(<Lightbox images={multipleImages} isOpen={true} onClose={mockOnClose} />);
      await waitFor(() => {
        const counter = screen.getByTestId('lightbox-counter');
        expect(counter).toBeInTheDocument();
        expect(counter).toHaveTextContent('1 / 3');
      });
    });

    it('displays correct image based on initialIndex', async () => {
      render(
        <Lightbox images={multipleImages} initialIndex={1} isOpen={true} onClose={mockOnClose} />
      );
      await waitFor(() => {
        expect(screen.getByTestId('lightbox-image')).toHaveAttribute('src', '/image-2.jpg');
        expect(screen.getByTestId('lightbox-counter')).toHaveTextContent('2 / 3');
      });
    });

    it('hides navigation when showNavigation is false', async () => {
      render(
        <Lightbox
          images={multipleImages}
          isOpen={true}
          onClose={mockOnClose}
          showNavigation={false}
        />
      );
      await waitFor(() => {
        expect(screen.getByTestId('lightbox-image')).toBeInTheDocument();
      });
      expect(screen.queryByTestId('lightbox-prev-button')).not.toBeInTheDocument();
      expect(screen.queryByTestId('lightbox-next-button')).not.toBeInTheDocument();
    });

    it('hides counter when showCounter is false', async () => {
      render(
        <Lightbox images={multipleImages} isOpen={true} onClose={mockOnClose} showCounter={false} />
      );
      await waitFor(() => {
        expect(screen.getByTestId('lightbox-image')).toBeInTheDocument();
      });
      expect(screen.queryByTestId('lightbox-counter')).not.toBeInTheDocument();
    });
  });

  describe('navigation behavior', () => {
    it('navigates to next image when clicking next button', async () => {
      const user = userEvent.setup();
      render(
        <Lightbox
          images={multipleImages}
          isOpen={true}
          onClose={mockOnClose}
          onIndexChange={mockOnIndexChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('lightbox-next-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('lightbox-next-button'));

      await waitFor(() => {
        expect(screen.getByTestId('lightbox-image')).toHaveAttribute('src', '/image-2.jpg');
        expect(screen.getByTestId('lightbox-counter')).toHaveTextContent('2 / 3');
        expect(mockOnIndexChange).toHaveBeenCalledWith(1);
      });
    });

    it('navigates to previous image when clicking prev button', async () => {
      const user = userEvent.setup();
      render(
        <Lightbox
          images={multipleImages}
          initialIndex={2}
          isOpen={true}
          onClose={mockOnClose}
          onIndexChange={mockOnIndexChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('lightbox-prev-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('lightbox-prev-button'));

      await waitFor(() => {
        expect(screen.getByTestId('lightbox-image')).toHaveAttribute('src', '/image-2.jpg');
        expect(screen.getByTestId('lightbox-counter')).toHaveTextContent('2 / 3');
        expect(mockOnIndexChange).toHaveBeenCalledWith(1);
      });
    });

    it('wraps around to last image when going previous from first', async () => {
      const user = userEvent.setup();
      render(
        <Lightbox
          images={multipleImages}
          initialIndex={0}
          isOpen={true}
          onClose={mockOnClose}
          onIndexChange={mockOnIndexChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('lightbox-prev-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('lightbox-prev-button'));

      await waitFor(() => {
        expect(screen.getByTestId('lightbox-image')).toHaveAttribute('src', '/image-3.jpg');
        expect(mockOnIndexChange).toHaveBeenCalledWith(2);
      });
    });

    it('wraps around to first image when going next from last', async () => {
      const user = userEvent.setup();
      render(
        <Lightbox
          images={multipleImages}
          initialIndex={2}
          isOpen={true}
          onClose={mockOnClose}
          onIndexChange={mockOnIndexChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('lightbox-next-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('lightbox-next-button'));

      await waitFor(() => {
        expect(screen.getByTestId('lightbox-image')).toHaveAttribute('src', '/image-1.jpg');
        expect(mockOnIndexChange).toHaveBeenCalledWith(0);
      });
    });
  });

  describe('keyboard navigation', () => {
    it('closes on Escape key', async () => {
      render(<Lightbox images={singleImage} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByTestId('lightbox-image')).toBeInTheDocument();
      });

      fireEvent.keyDown(document, { key: 'Escape' });

      await waitFor(() => {
        expect(mockOnClose).toHaveBeenCalledTimes(1);
      });
    });

    it('navigates to next image on ArrowRight', async () => {
      render(
        <Lightbox
          images={multipleImages}
          isOpen={true}
          onClose={mockOnClose}
          onIndexChange={mockOnIndexChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('lightbox-image')).toBeInTheDocument();
      });

      fireEvent.keyDown(document, { key: 'ArrowRight' });

      await waitFor(() => {
        expect(screen.getByTestId('lightbox-image')).toHaveAttribute('src', '/image-2.jpg');
        expect(mockOnIndexChange).toHaveBeenCalledWith(1);
      });
    });

    it('navigates to previous image on ArrowLeft', async () => {
      render(
        <Lightbox
          images={multipleImages}
          initialIndex={2}
          isOpen={true}
          onClose={mockOnClose}
          onIndexChange={mockOnIndexChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('lightbox-image')).toBeInTheDocument();
      });

      fireEvent.keyDown(document, { key: 'ArrowLeft' });

      await waitFor(() => {
        expect(screen.getByTestId('lightbox-image')).toHaveAttribute('src', '/image-2.jpg');
        expect(mockOnIndexChange).toHaveBeenCalledWith(1);
      });
    });

    it('does not navigate on arrow keys for single image', async () => {
      render(
        <Lightbox
          images={singleImage}
          isOpen={true}
          onClose={mockOnClose}
          onIndexChange={mockOnIndexChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('lightbox-image')).toBeInTheDocument();
      });

      fireEvent.keyDown(document, { key: 'ArrowRight' });
      fireEvent.keyDown(document, { key: 'ArrowLeft' });

      expect(mockOnIndexChange).not.toHaveBeenCalled();
    });
  });

  describe('close behavior', () => {
    it('calls onClose when clicking close button', async () => {
      const user = userEvent.setup();
      render(<Lightbox images={singleImage} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByTestId('lightbox-close-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('lightbox-close-button'));

      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });

    it('has proper aria-label on close button', async () => {
      render(<Lightbox images={singleImage} isOpen={true} onClose={mockOnClose} />);
      await waitFor(() => {
        expect(screen.getByTestId('lightbox-close-button')).toHaveAttribute(
          'aria-label',
          'Close lightbox'
        );
      });
    });
  });

  describe('caption display', () => {
    it('renders caption when provided', async () => {
      render(
        <Lightbox images={multipleImages} initialIndex={0} isOpen={true} onClose={mockOnClose} />
      );
      await waitFor(() => {
        expect(screen.getByTestId('lightbox-caption')).toHaveTextContent('First image caption');
      });
    });

    it('does not render caption when not provided', async () => {
      render(
        <Lightbox images={multipleImages} initialIndex={2} isOpen={true} onClose={mockOnClose} />
      );
      await waitFor(() => {
        expect(screen.getByTestId('lightbox-image')).toBeInTheDocument();
      });
      expect(screen.queryByTestId('lightbox-caption')).not.toBeInTheDocument();
    });

    it('updates caption when navigating', async () => {
      const user = userEvent.setup();
      render(<Lightbox images={multipleImages} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByTestId('lightbox-caption')).toHaveTextContent('First image caption');
      });

      await user.click(screen.getByTestId('lightbox-next-button'));

      await waitFor(() => {
        expect(screen.getByTestId('lightbox-caption')).toHaveTextContent('Second image caption');
      });
    });
  });

  describe('accessibility', () => {
    it('has accessible navigation buttons with aria-labels', async () => {
      render(<Lightbox images={multipleImages} isOpen={true} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByTestId('lightbox-prev-button')).toHaveAttribute(
          'aria-label',
          'Previous image'
        );
        expect(screen.getByTestId('lightbox-next-button')).toHaveAttribute(
          'aria-label',
          'Next image'
        );
      });
    });

    it('has aria-live region for counter', async () => {
      render(<Lightbox images={multipleImages} isOpen={true} onClose={mockOnClose} />);
      await waitFor(() => {
        expect(screen.getByTestId('lightbox-counter')).toHaveAttribute('aria-live', 'polite');
      });
    });

    it('has sr-only title for screen readers', async () => {
      render(<Lightbox images={singleImage} isOpen={true} onClose={mockOnClose} />);
      await waitFor(() => {
        expect(screen.getByText('Test image')).toHaveClass('sr-only');
      });
    });
  });

  describe('styling', () => {
    it('applies custom className', async () => {
      const { baseElement } = render(
        <Lightbox
          images={singleImage}
          isOpen={true}
          onClose={mockOnClose}
          className="custom-class"
        />
      );
      await waitFor(() => {
        // The className is applied to the Dialog element (portal renders in body)
        expect(baseElement.querySelector('.custom-class')).toBeInTheDocument();
      });
    });

    it('has dark backdrop with proper opacity', async () => {
      render(<Lightbox images={singleImage} isOpen={true} onClose={mockOnClose} />);
      await waitFor(() => {
        expect(screen.getByTestId('lightbox-backdrop')).toHaveClass('bg-black/90');
      });
    });

    it('image has proper styling classes', async () => {
      render(<Lightbox images={singleImage} isOpen={true} onClose={mockOnClose} />);
      await waitFor(() => {
        const image = screen.getByTestId('lightbox-image');
        expect(image).toHaveClass('max-h-[85vh]', 'max-w-full', 'object-contain', 'rounded-lg');
      });
    });
  });

  describe('state reset', () => {
    it('resets to initialIndex when modal reopens', async () => {
      const { rerender } = render(
        <Lightbox images={multipleImages} initialIndex={0} isOpen={true} onClose={mockOnClose} />
      );

      await waitFor(() => {
        expect(screen.getByTestId('lightbox-image')).toBeInTheDocument();
      });

      // Navigate to second image
      fireEvent.keyDown(document, { key: 'ArrowRight' });
      await waitFor(() => {
        expect(screen.getByTestId('lightbox-counter')).toHaveTextContent('2 / 3');
      });

      // Close and reopen
      rerender(
        <Lightbox images={multipleImages} initialIndex={0} isOpen={false} onClose={mockOnClose} />
      );
      rerender(
        <Lightbox images={multipleImages} initialIndex={0} isOpen={true} onClose={mockOnClose} />
      );

      // Should be back to first image
      await waitFor(() => {
        expect(screen.getByTestId('lightbox-counter')).toHaveTextContent('1 / 3');
      });
    });
  });
});
