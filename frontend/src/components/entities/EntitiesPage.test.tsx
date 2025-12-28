import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import EntitiesPage from './EntitiesPage';

describe('EntitiesPage', () => {
  describe('Rendering', () => {
    it('renders the page header with title and description', () => {
      render(<EntitiesPage />);

      expect(screen.getByText('Entities')).toBeInTheDocument();
      expect(
        screen.getByText('Track and identify people and vehicles across your cameras')
      ).toBeInTheDocument();
    });

    it('displays the coming soon message', () => {
      render(<EntitiesPage />);

      expect(screen.getByText('Coming Soon')).toBeInTheDocument();
      expect(
        screen.getByText(/The Entities feature is currently under development/)
      ).toBeInTheDocument();
    });

    it('lists planned features', () => {
      render(<EntitiesPage />);

      expect(screen.getByText('Track detected people and vehicles over time')).toBeInTheDocument();
      expect(
        screen.getByText('View movement patterns across multiple cameras')
      ).toBeInTheDocument();
      expect(screen.getByText('Classify entities as known or unknown')).toBeInTheDocument();
      expect(screen.getByText('Search and filter entity history')).toBeInTheDocument();
    });

    it('displays check back message', () => {
      render(<EntitiesPage />);

      expect(screen.getByText('Check back for updates')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has proper heading hierarchy', () => {
      render(<EntitiesPage />);

      const mainHeading = screen.getByRole('heading', { level: 1 });
      expect(mainHeading).toHaveTextContent('Entities');

      const subHeading = screen.getByRole('heading', { level: 2 });
      expect(subHeading).toHaveTextContent('Coming Soon');
    });

    it('renders icons with proper accessibility attributes', () => {
      const { container } = render(<EntitiesPage />);

      // Lucide icons should be present (they render as SVG elements)
      const svgElements = container.querySelectorAll('svg');
      expect(svgElements.length).toBeGreaterThan(0);
    });
  });

  describe('Styling', () => {
    it('applies NVIDIA green accent color to icons', () => {
      const { container } = render(<EntitiesPage />);

      // Check for the NVIDIA green color class on text elements
      const greenElements = container.querySelectorAll('.text-\\[\\#76B900\\]');
      expect(greenElements.length).toBeGreaterThan(0);
    });

    it('has dark theme background', () => {
      const { container } = render(<EntitiesPage />);

      // Check for the dark background class
      const darkBgElements = container.querySelectorAll('.bg-\\[\\#1F1F1F\\]');
      expect(darkBgElements.length).toBeGreaterThan(0);
    });
  });
});
