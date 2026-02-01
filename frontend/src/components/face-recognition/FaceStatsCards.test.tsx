/**
 * Tests for FaceStatsCards and PersonStatsCards components (NEM-4688 Phase 1)
 *
 * Tests cover:
 * - Rendering stats cards with all values
 * - Loading skeleton states
 * - Error handling
 * - Responsive grid layout
 * - Null/undefined stats handling
 * - Icon display
 * - Accessibility
 *
 * @see docs/plans/2025-01-31-face-recognition-ui-design.md
 */

import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import FaceStatsCards, { PersonStatsCards } from './FaceStatsCards';

import type { FaceStats } from '../../types/faceRecognition';

// ============================================================================
// Mock Data
// ============================================================================

const mockFaceStats: FaceStats = {
  total_today: 47,
  known_count: 38,
  unknown_count: 9,
  by_camera: {
    '1': { total: 20, known: 15, unknown: 5 },
    '2': { total: 27, known: 23, unknown: 4 },
  },
  unique_known_persons: 12,
  unique_unknown_faces: 6,
};

const mockPersonStats = {
  totalSightings: 23,
  avgPerDay: 3.3,
  cameraCount: 4,
};

// ============================================================================
// FaceStatsCards Tests
// ============================================================================

describe('FaceStatsCards', () => {
  describe('Rendering', () => {
    it('renders all four main stats cards', () => {
      render(<FaceStatsCards stats={mockFaceStats} />);

      expect(screen.getByText('Total Faces')).toBeInTheDocument();
      expect(screen.getByText('Known')).toBeInTheDocument();
      expect(screen.getByText('Unknown')).toBeInTheDocument();
      expect(screen.getByText('Cameras')).toBeInTheDocument();
    });

    it('displays stats values correctly', () => {
      render(<FaceStatsCards stats={mockFaceStats} />);

      expect(screen.getByText('47')).toBeInTheDocument(); // total_today
      expect(screen.getByText('38')).toBeInTheDocument(); // known_count
      expect(screen.getByText('9')).toBeInTheDocument(); // unknown_count
      expect(screen.getByText('2')).toBeInTheDocument(); // camera count from by_camera keys
    });

    it('applies custom className', () => {
      const { container } = render(
        <FaceStatsCards stats={mockFaceStats} className="custom-class" />
      );

      const wrapper = container.querySelector('.custom-class');
      expect(wrapper).toBeInTheDocument();
    });

    it('renders with data-testid for each card', () => {
      render(<FaceStatsCards stats={mockFaceStats} />);

      expect(screen.getByTestId('face-stats-total')).toBeInTheDocument();
      expect(screen.getByTestId('face-stats-known')).toBeInTheDocument();
      expect(screen.getByTestId('face-stats-unknown')).toBeInTheDocument();
      expect(screen.getByTestId('face-stats-cameras')).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    it('displays loading skeleton when isLoading is true', () => {
      const { container } = render(<FaceStatsCards isLoading={true} />);

      // Look for animate-pulse class that indicates loading skeleton
      const loadingSkeletons = container.querySelectorAll('.animate-pulse');
      expect(loadingSkeletons.length).toBeGreaterThan(0);
    });

    it('shows card structure during loading', () => {
      render(<FaceStatsCards isLoading={true} />);

      // Labels should still be visible during loading
      expect(screen.getByText('Total Faces')).toBeInTheDocument();
      expect(screen.getByText('Known')).toBeInTheDocument();
      expect(screen.getByText('Unknown')).toBeInTheDocument();
      expect(screen.getByText('Cameras')).toBeInTheDocument();
    });

    it('hides values during loading', () => {
      render(<FaceStatsCards isLoading={true} stats={mockFaceStats} />);

      // Values should not be visible during loading (skeleton shown instead)
      expect(screen.queryByText('47')).not.toBeInTheDocument();
    });
  });

  describe('Null Stats', () => {
    it('displays zeros when stats is undefined', () => {
      render(<FaceStatsCards />);

      const zeros = screen.getAllByText('0');
      expect(zeros.length).toBe(4); // All four cards should show 0
    });

    it('displays zeros when stats is null', () => {
      render(<FaceStatsCards stats={null as unknown as FaceStats} />);

      const zeros = screen.getAllByText('0');
      expect(zeros.length).toBe(4);
    });
  });

  describe('Partial Stats', () => {
    it('handles stats with empty by_camera', () => {
      const partialStats: FaceStats = {
        total_today: 10,
        known_count: 7,
        unknown_count: 3,
        by_camera: {},
      };

      render(<FaceStatsCards stats={partialStats} />);

      expect(screen.getByText('10')).toBeInTheDocument();
      expect(screen.getByText('7')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument();
      // Camera count should be 0 for empty by_camera
      const zeros = screen.getAllByText('0');
      expect(zeros.length).toBe(1); // Only camera count is 0
    });

    it('handles stats with zero values', () => {
      const zeroStats: FaceStats = {
        total_today: 0,
        known_count: 0,
        unknown_count: 0,
        by_camera: {},
      };

      render(<FaceStatsCards stats={zeroStats} />);

      const zeros = screen.getAllByText('0');
      expect(zeros.length).toBe(4);
    });
  });

  describe('Grid Layout', () => {
    it('renders cards in a grid layout', () => {
      const { container } = render(<FaceStatsCards stats={mockFaceStats} />);

      const grid = container.querySelector('.grid');
      expect(grid).toBeInTheDocument();
    });

    it('uses responsive grid classes', () => {
      const { container } = render(<FaceStatsCards stats={mockFaceStats} />);

      const grid = container.querySelector('.grid');
      expect(grid).toHaveClass('grid-cols-2');
      expect(grid).toHaveClass('md:grid-cols-4');
    });
  });

  describe('Styling', () => {
    it('uses dark theme background colors', () => {
      const { container } = render(<FaceStatsCards stats={mockFaceStats} />);

      // Check for the card background color
      const cards = container.querySelectorAll('[data-testid^="face-stats-"]');
      expect(cards.length).toBe(4);
      cards.forEach((card) => {
        expect(card).toHaveClass('bg-[#1A1A1A]');
      });
    });

    it('uses border styling for cards', () => {
      const { container } = render(<FaceStatsCards stats={mockFaceStats} />);

      const cards = container.querySelectorAll('[data-testid^="face-stats-"]');
      cards.forEach((card) => {
        expect(card).toHaveClass('border');
        expect(card).toHaveClass('border-gray-700');
      });
    });

    it('applies rounded corners to cards', () => {
      const { container } = render(<FaceStatsCards stats={mockFaceStats} />);

      const cards = container.querySelectorAll('[data-testid^="face-stats-"]');
      cards.forEach((card) => {
        expect(card).toHaveClass('rounded-lg');
      });
    });
  });

  describe('Text Styling', () => {
    it('uses large font for values', () => {
      const { container } = render(<FaceStatsCards stats={mockFaceStats} />);

      // Find value elements with text-2xl
      const valueElements = container.querySelectorAll('.text-2xl');
      expect(valueElements.length).toBe(4);
    });

    it('uses smaller font for labels', () => {
      const { container } = render(<FaceStatsCards stats={mockFaceStats} />);

      // Find label elements with text-sm
      const labelElements = container.querySelectorAll('.text-sm');
      expect(labelElements.length).toBeGreaterThanOrEqual(4);
    });

    it('uses gray color for labels', () => {
      const { container } = render(<FaceStatsCards stats={mockFaceStats} />);

      const labelElements = container.querySelectorAll('.text-gray-400');
      expect(labelElements.length).toBeGreaterThanOrEqual(4);
    });

    it('uses white color for values', () => {
      const { container } = render(<FaceStatsCards stats={mockFaceStats} />);

      const valueElements = container.querySelectorAll('.text-white');
      expect(valueElements.length).toBeGreaterThanOrEqual(4);
    });
  });

  describe('Accessibility', () => {
    it('renders with semantic structure', () => {
      render(<FaceStatsCards stats={mockFaceStats} />);

      // Cards should be accessible
      const cards = screen.getAllByTestId(/^face-stats-/);
      expect(cards.length).toBe(4);
    });
  });

  describe('Icons', () => {
    it('renders icon elements in each card', () => {
      const { container } = render(<FaceStatsCards stats={mockFaceStats} />);

      // Check for lucide icon classes
      const icons = container.querySelectorAll('svg');
      expect(icons.length).toBeGreaterThanOrEqual(4);
    });
  });
});

// ============================================================================
// PersonStatsCards Tests
// ============================================================================

describe('PersonStatsCards', () => {
  describe('Rendering', () => {
    it('renders all three stats cards', () => {
      render(<PersonStatsCards {...mockPersonStats} />);

      expect(screen.getByText('Sightings')).toBeInTheDocument();
      expect(screen.getByText('Avg/Day')).toBeInTheDocument();
      expect(screen.getByText('Cameras')).toBeInTheDocument();
    });

    it('displays stats values correctly', () => {
      render(<PersonStatsCards {...mockPersonStats} />);

      expect(screen.getByText('23')).toBeInTheDocument(); // totalSightings
      expect(screen.getByText('3.3')).toBeInTheDocument(); // avgPerDay
      expect(screen.getByText('4')).toBeInTheDocument(); // cameraCount
    });

    it('applies custom className', () => {
      const { container } = render(
        <PersonStatsCards {...mockPersonStats} className="custom-person-class" />
      );

      const wrapper = container.querySelector('.custom-person-class');
      expect(wrapper).toBeInTheDocument();
    });

    it('renders with data-testid for each card', () => {
      render(<PersonStatsCards {...mockPersonStats} />);

      expect(screen.getByTestId('person-stats-sightings')).toBeInTheDocument();
      expect(screen.getByTestId('person-stats-avg')).toBeInTheDocument();
      expect(screen.getByTestId('person-stats-cameras')).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    it('displays loading skeleton when isLoading is true', () => {
      const { container } = render(<PersonStatsCards {...mockPersonStats} isLoading={true} />);

      const loadingSkeletons = container.querySelectorAll('.animate-pulse');
      expect(loadingSkeletons.length).toBeGreaterThan(0);
    });

    it('shows labels during loading', () => {
      render(<PersonStatsCards {...mockPersonStats} isLoading={true} />);

      expect(screen.getByText('Sightings')).toBeInTheDocument();
      expect(screen.getByText('Avg/Day')).toBeInTheDocument();
      expect(screen.getByText('Cameras')).toBeInTheDocument();
    });
  });

  describe('Default Values', () => {
    it('displays zeros when values are undefined', () => {
      render(<PersonStatsCards />);

      const zeros = screen.getAllByText('0');
      expect(zeros.length).toBe(3);
    });

    it('handles zero values correctly', () => {
      render(<PersonStatsCards totalSightings={0} avgPerDay={0} cameraCount={0} />);

      const zeros = screen.getAllByText('0');
      expect(zeros.length).toBe(3);
    });
  });

  describe('Decimal Formatting', () => {
    it('displays avgPerDay with one decimal place', () => {
      render(<PersonStatsCards totalSightings={10} avgPerDay={3.333} cameraCount={2} />);

      // Should be formatted to 3.3
      expect(screen.getByText('3.3')).toBeInTheDocument();
    });

    it('handles integer avgPerDay values', () => {
      render(<PersonStatsCards totalSightings={10} avgPerDay={3} cameraCount={2} />);

      expect(screen.getByText('3')).toBeInTheDocument();
    });
  });

  describe('Grid Layout', () => {
    it('renders cards in a grid layout', () => {
      const { container } = render(<PersonStatsCards {...mockPersonStats} />);

      const grid = container.querySelector('.grid');
      expect(grid).toBeInTheDocument();
    });

    it('uses 3-column grid', () => {
      const { container } = render(<PersonStatsCards {...mockPersonStats} />);

      const grid = container.querySelector('.grid');
      // PersonStatsCards uses grid-cols-3 for 3 cards
      expect(grid).toHaveClass('grid-cols-3');
    });
  });

  describe('Styling', () => {
    it('uses dark theme background colors', () => {
      const { container } = render(<PersonStatsCards {...mockPersonStats} />);

      const cards = container.querySelectorAll('[data-testid^="person-stats-"]');
      expect(cards.length).toBe(3);
      cards.forEach((card) => {
        expect(card).toHaveClass('bg-[#1A1A1A]');
      });
    });

    it('uses consistent border styling', () => {
      const { container } = render(<PersonStatsCards {...mockPersonStats} />);

      const cards = container.querySelectorAll('[data-testid^="person-stats-"]');
      cards.forEach((card) => {
        expect(card).toHaveClass('border');
        expect(card).toHaveClass('border-gray-700');
      });
    });
  });

  describe('Icons', () => {
    it('renders icon elements in each card', () => {
      const { container } = render(<PersonStatsCards {...mockPersonStats} />);

      const icons = container.querySelectorAll('svg');
      expect(icons.length).toBeGreaterThanOrEqual(3);
    });
  });
});
