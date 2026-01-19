import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import PlaceholderThumbnail from './PlaceholderThumbnail';

describe('PlaceholderThumbnail', () => {
  describe('entity type icons', () => {
    it('renders person silhouette (User icon) for person entities', () => {
      const { container } = render(<PlaceholderThumbnail entityType="person" />);
      const userIcon = container.querySelector('svg.lucide-user');
      expect(userIcon).toBeInTheDocument();
    });

    it('renders vehicle silhouette (Car icon) for vehicle entities', () => {
      const { container } = render(<PlaceholderThumbnail entityType="vehicle" />);
      const carIcon = container.querySelector('svg.lucide-car');
      expect(carIcon).toBeInTheDocument();
    });

    it('renders generic silhouette (HelpCircle icon) for unknown entities', () => {
      const { container } = render(<PlaceholderThumbnail entityType="unknown" />);
      const helpIcon = container.querySelector('svg.lucide-help-circle');
      expect(helpIcon).toBeInTheDocument();
    });

    it('renders generic silhouette for any unrecognized entity type', () => {
      const { container } = render(
        <PlaceholderThumbnail entityType="something_else" />
      );
      const helpIcon = container.querySelector('svg.lucide-help-circle');
      expect(helpIcon).toBeInTheDocument();
    });
  });

  describe('aspect ratio and styling', () => {
    it('maintains aspect ratio with proper container classes', () => {
      const { container } = render(<PlaceholderThumbnail entityType="person" />);
      const wrapper = container.firstChild as HTMLElement;
      // Should have flex centering classes for proper aspect ratio maintenance
      expect(wrapper).toHaveClass('flex');
      expect(wrapper).toHaveClass('items-center');
      expect(wrapper).toHaveClass('justify-center');
    });

    it('fills parent container with full width and height', () => {
      const { container } = render(<PlaceholderThumbnail entityType="vehicle" />);
      const wrapper = container.firstChild as HTMLElement;
      expect(wrapper).toHaveClass('w-full');
      expect(wrapper).toHaveClass('h-full');
    });

    it('applies muted color styling for silhouette', () => {
      const { container } = render(<PlaceholderThumbnail entityType="person" />);
      const wrapper = container.firstChild as HTMLElement;
      expect(wrapper).toHaveClass('text-gray-600');
    });

    it('renders icon with appropriate size', () => {
      const { container } = render(<PlaceholderThumbnail entityType="person" />);
      const icon = container.querySelector('svg');
      expect(icon).toHaveClass('h-16');
      expect(icon).toHaveClass('w-16');
    });
  });

  describe('accessibility', () => {
    it('has data-testid for testing', () => {
      render(<PlaceholderThumbnail entityType="person" />);
      expect(screen.getByTestId('placeholder-thumbnail')).toBeInTheDocument();
    });

    it('does not display text like "undefined" or "thumbnail"', () => {
      render(<PlaceholderThumbnail entityType="person" />);
      expect(screen.queryByText(/undefined/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/thumbnail/i)).not.toBeInTheDocument();
    });

    it('does not display any visible text for person type', () => {
      render(<PlaceholderThumbnail entityType="person" />);
      const placeholder = screen.getByTestId('placeholder-thumbnail');
      // Should only contain the icon, no text content
      expect(placeholder.textContent).toBe('');
    });

    it('does not display any visible text for vehicle type', () => {
      render(<PlaceholderThumbnail entityType="vehicle" />);
      const placeholder = screen.getByTestId('placeholder-thumbnail');
      expect(placeholder.textContent).toBe('');
    });
  });

  describe('custom className', () => {
    it('accepts and applies custom className', () => {
      const { container } = render(
        <PlaceholderThumbnail entityType="person" className="custom-class" />
      );
      const wrapper = container.firstChild as HTMLElement;
      expect(wrapper).toHaveClass('custom-class');
    });

    it('merges custom className with default classes', () => {
      const { container } = render(
        <PlaceholderThumbnail entityType="person" className="my-extra-class" />
      );
      const wrapper = container.firstChild as HTMLElement;
      expect(wrapper).toHaveClass('flex');
      expect(wrapper).toHaveClass('my-extra-class');
    });
  });
});
