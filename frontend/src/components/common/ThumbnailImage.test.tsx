import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import ThumbnailImage from './ThumbnailImage';

describe('ThumbnailImage', () => {
  const defaultProps = {
    src: 'https://example.com/image.jpg',
    alt: 'Test thumbnail',
  };

  describe('rendering', () => {
    it('renders image when src is provided', () => {
      render(<ThumbnailImage {...defaultProps} />);
      const img = screen.getByTestId('thumbnail-image-img');
      expect(img).toBeInTheDocument();
      expect(img).toHaveAttribute('src', defaultProps.src);
    });

    it('renders with correct alt text', () => {
      render(<ThumbnailImage {...defaultProps} />);
      const img = screen.getByAltText('Test thumbnail');
      expect(img).toBeInTheDocument();
    });

    it('renders placeholder when no src provided', () => {
      render(<ThumbnailImage alt="No image" />);
      const placeholder = screen.getByTestId('thumbnail-image-placeholder');
      expect(placeholder).toBeInTheDocument();
      expect(screen.queryByRole('img')).not.toBeInTheDocument();
    });

    it('renders placeholder when src is empty string', () => {
      render(<ThumbnailImage src="" alt="Empty src" />);
      const placeholder = screen.getByTestId('thumbnail-image-placeholder');
      expect(placeholder).toBeInTheDocument();
    });

    it('renders with custom testId', () => {
      render(<ThumbnailImage {...defaultProps} testId="custom-thumbnail" />);
      expect(screen.getByTestId('custom-thumbnail')).toBeInTheDocument();
      expect(screen.getByTestId('custom-thumbnail-img')).toBeInTheDocument();
    });
  });

  describe('error handling', () => {
    it('shows placeholder when image fails to load', () => {
      render(<ThumbnailImage {...defaultProps} />);

      const img = screen.getByTestId('thumbnail-image-img');
      expect(img).toBeInTheDocument();

      // Simulate image load error
      fireEvent.error(img);

      // Should now show placeholder instead of image
      expect(screen.queryByTestId('thumbnail-image-img')).not.toBeInTheDocument();
      expect(screen.getByTestId('thumbnail-image-placeholder')).toBeInTheDocument();
    });

    it('shows placeholder with aria-label when image fails to load', () => {
      render(<ThumbnailImage {...defaultProps} />);

      const img = screen.getByTestId('thumbnail-image-img');
      fireEvent.error(img);

      const placeholder = screen.getByTestId('thumbnail-image-placeholder');
      expect(placeholder).toHaveAttribute('aria-label', 'Placeholder for Test thumbnail');
    });

    it('handles multiple error events gracefully', () => {
      render(<ThumbnailImage {...defaultProps} />);

      const img = screen.getByTestId('thumbnail-image-img');

      // Multiple error events should not cause issues
      fireEvent.error(img);

      const placeholder = screen.getByTestId('thumbnail-image-placeholder');
      expect(placeholder).toBeInTheDocument();
    });
  });

  describe('sizing', () => {
    it('applies small size classes', () => {
      render(<ThumbnailImage {...defaultProps} size="sm" />);
      const img = screen.getByTestId('thumbnail-image-img');
      expect(img).toHaveClass('h-12', 'w-12');
    });

    it('applies medium size classes (default)', () => {
      render(<ThumbnailImage {...defaultProps} />);
      const img = screen.getByTestId('thumbnail-image-img');
      expect(img).toHaveClass('h-20', 'w-20');
    });

    it('applies large size classes', () => {
      render(<ThumbnailImage {...defaultProps} size="lg" />);
      const img = screen.getByTestId('thumbnail-image-img');
      expect(img).toHaveClass('h-32', 'w-32');
    });

    it('applies size classes to placeholder', () => {
      render(<ThumbnailImage alt="No image" size="lg" />);
      const placeholder = screen.getByTestId('thumbnail-image-placeholder');
      expect(placeholder).toHaveClass('h-32', 'w-32');
    });
  });

  describe('styling', () => {
    it('applies custom className to container', () => {
      const { container } = render(
        <ThumbnailImage {...defaultProps} className="custom-container" />
      );
      const wrapper = container.firstChild;
      expect(wrapper).toHaveClass('custom-container');
    });

    it('applies custom imageClassName to image', () => {
      render(<ThumbnailImage {...defaultProps} imageClassName="custom-image" />);
      const img = screen.getByTestId('thumbnail-image-img');
      expect(img).toHaveClass('custom-image');
    });

    it('applies default styling to image', () => {
      render(<ThumbnailImage {...defaultProps} />);
      const img = screen.getByTestId('thumbnail-image-img');
      expect(img).toHaveClass('rounded-md', 'bg-gray-900', 'object-cover');
    });

    it('applies default styling to placeholder', () => {
      render(<ThumbnailImage alt="No image" />);
      const placeholder = screen.getByTestId('thumbnail-image-placeholder');
      expect(placeholder).toHaveClass('rounded-md', 'bg-gray-900');
    });

    it('includes camera icon in placeholder', () => {
      const { container } = render(<ThumbnailImage alt="No image" />);
      const cameraIcon = container.querySelector('svg.lucide-camera');
      expect(cameraIcon).toBeInTheDocument();
    });
  });

  describe('layout preservation', () => {
    it('maintains flex-shrink-0 on container', () => {
      const { container } = render(<ThumbnailImage {...defaultProps} />);
      const wrapper = container.firstChild;
      expect(wrapper).toHaveClass('flex-shrink-0');
    });

    it('maintains same dimensions when switching from image to placeholder', () => {
      render(<ThumbnailImage {...defaultProps} size="md" />);

      const img = screen.getByTestId('thumbnail-image-img');
      expect(img).toHaveClass('h-20', 'w-20');

      fireEvent.error(img);

      const placeholder = screen.getByTestId('thumbnail-image-placeholder');
      expect(placeholder).toHaveClass('h-20', 'w-20');
    });
  });
});
