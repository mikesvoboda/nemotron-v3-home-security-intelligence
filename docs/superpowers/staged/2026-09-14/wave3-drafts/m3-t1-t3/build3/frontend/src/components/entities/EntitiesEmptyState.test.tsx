import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect } from 'vitest';

import EntitiesEmptyState from './EntitiesEmptyState';

// Helper to render with router
const renderWithRouter = (component: React.ReactElement) => {
  return render(<BrowserRouter>{component}</BrowserRouter>);
};

describe('EntitiesEmptyState', () => {
  describe('Rendering', () => {
    it('renders the empty state title', () => {
      renderWithRouter(<EntitiesEmptyState />);

      expect(screen.getByText('No Entities Tracked Yet')).toBeInTheDocument();
    });

    it('renders the description text', () => {
      renderWithRouter(<EntitiesEmptyState />);

      expect(
        screen.getByText(/Entities are automatically created when the AI identifies/i)
      ).toBeInTheDocument();
    });

    it('renders the "How it works" section', () => {
      renderWithRouter(<EntitiesEmptyState />);

      expect(screen.getByText('How it works')).toBeInTheDocument();
    });

    it('renders all four steps in "How it works"', () => {
      renderWithRouter(<EntitiesEmptyState />);

      expect(screen.getByText(/Camera detects a person or vehicle/i)).toBeInTheDocument();
      expect(screen.getByText(/AI extracts visual features/i)).toBeInTheDocument();
      expect(screen.getByText(/System matches across all camera feeds/i)).toBeInTheDocument();
      expect(screen.getByText(/Entity profile created with movement history/i)).toBeInTheDocument();
    });

    it('renders the CTA button', () => {
      renderWithRouter(<EntitiesEmptyState />);

      const ctaButton = screen.getByRole('link', { name: /View Detection Settings/i });
      expect(ctaButton).toBeInTheDocument();
    });

    it('CTA button links to settings page', () => {
      renderWithRouter(<EntitiesEmptyState />);

      const ctaButton = screen.getByRole('link', { name: /View Detection Settings/i });
      expect(ctaButton).toHaveAttribute('href', '/settings');
    });
  });

  describe('Illustration', () => {
    it('renders animated illustration icons', () => {
      const { container } = renderWithRouter(<EntitiesEmptyState />);

      // Check for animation classes
      const floatingElements = container.querySelectorAll('[class*="animate-float"]');
      expect(floatingElements.length).toBe(4); // Person, Car, MapPin, Clock

      const pulsingElements = container.querySelectorAll('[class*="animate-pulse"]');
      expect(pulsingElements.length).toBe(1); // Scan icon
    });

    it('has staggered animation delays on floating icons', () => {
      const { container } = renderWithRouter(<EntitiesEmptyState />);

      const floatingElements = container.querySelectorAll('[class*="animate-float"]');
      const delays = Array.from(floatingElements).map(
        (el) => (el as HTMLElement).style.animationDelay
      );

      // Check that delays are different
      expect(new Set(delays).size).toBe(4);
    });
  });

  describe('Accessibility', () => {
    it('has proper heading hierarchy', () => {
      renderWithRouter(<EntitiesEmptyState />);

      const mainHeading = screen.getByRole('heading', { level: 2 });
      expect(mainHeading).toHaveTextContent('No Entities Tracked Yet');

      const subHeading = screen.getByRole('heading', { level: 3 });
      expect(subHeading).toHaveTextContent('How it works');
    });

    it('CTA button is keyboard accessible', () => {
      renderWithRouter(<EntitiesEmptyState />);

      const ctaButton = screen.getByRole('link', { name: /View Detection Settings/i });
      expect(ctaButton).toBeInTheDocument();
      expect(ctaButton.tagName).toBe('A'); // Link elements are keyboard accessible
    });
  });

  describe('Styling', () => {
    it('applies NVIDIA green accent color', () => {
      const { container } = renderWithRouter(<EntitiesEmptyState />);

      // Check for the NVIDIA green color class
      const greenElements = container.querySelectorAll('[class*="[#76B900]"]');
      expect(greenElements.length).toBeGreaterThan(0);
    });

    it('has dark theme background', () => {
      const { container } = renderWithRouter(<EntitiesEmptyState />);

      // Check for the dark background class
      const darkBgElements = container.querySelectorAll('[class*="bg-[#1F1F1F]"]');
      expect(darkBgElements.length).toBeGreaterThan(0);
    });

    it('uses step number badges with NVIDIA green', () => {
      const { container } = renderWithRouter(<EntitiesEmptyState />);

      // Check for step numbers (1, 2, 3, 4)
      expect(screen.getByText('1')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText('4')).toBeInTheDocument();

      // Check that they have NVIDIA green styling
      const stepBadges = container.querySelectorAll('[class*="bg-[#76B900]/10"]');
      expect(stepBadges.length).toBeGreaterThan(4); // Step badges + other green elements
    });
  });

  describe('Responsive Design', () => {
    it('uses responsive grid for steps on small screens', () => {
      const { container } = renderWithRouter(<EntitiesEmptyState />);

      // Check for responsive grid classes
      const gridElements = container.querySelectorAll('[class*="sm:grid-cols-2"]');
      expect(gridElements.length).toBeGreaterThan(0);
    });
  });
});
