import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import EntityCard, { type EntityCardProps } from './EntityCard';

describe('EntityCard', () => {
  // Base time for consistent testing
  const BASE_TIME = new Date('2024-01-15T10:00:00Z').getTime();

  // Mock base props for a person entity
  const mockPersonProps: EntityCardProps = {
    id: 'entity-abc123',
    entity_type: 'person',
    first_seen: new Date(BASE_TIME - 3 * 60 * 60 * 1000).toISOString(), // 3 hours ago
    last_seen: new Date(BASE_TIME - 5 * 60 * 1000).toISOString(), // 5 mins ago
    appearance_count: 7,
    cameras_seen: ['front_door', 'back_yard', 'garage'],
    thumbnail_url: 'https://example.com/thumbnail.jpg',
  };

  // Mock base props for a vehicle entity
  const mockVehicleProps: EntityCardProps = {
    id: 'entity-xyz789',
    entity_type: 'vehicle',
    first_seen: new Date(BASE_TIME - 24 * 60 * 60 * 1000).toISOString(), // 1 day ago
    last_seen: new Date(BASE_TIME - 2 * 60 * 60 * 1000).toISOString(), // 2 hours ago
    appearance_count: 3,
    cameras_seen: ['driveway'],
    thumbnail_url: null,
  };

  // Mock system time for consistent testing
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(BASE_TIME);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('basic rendering', () => {
    it('renders component with required props', () => {
      render(<EntityCard {...mockPersonProps} />);
      expect(screen.getByText('Person')).toBeInTheDocument();
    });

    it('renders entity type for person', () => {
      render(<EntityCard {...mockPersonProps} />);
      expect(screen.getByText('Person')).toBeInTheDocument();
    });

    it('renders entity type for vehicle', () => {
      render(<EntityCard {...mockVehicleProps} />);
      expect(screen.getByText('Vehicle')).toBeInTheDocument();
    });

    it('renders entity ID in truncated form', () => {
      render(<EntityCard {...mockPersonProps} />);
      // Should show first 8 chars of ID
      expect(screen.getByText(/entity-a/)).toBeInTheDocument();
    });

    it('applies custom className', () => {
      const { container } = render(<EntityCard {...mockPersonProps} className="custom-class" />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('custom-class');
    });
  });

  describe('appearance count', () => {
    it('displays appearance count', () => {
      render(<EntityCard {...mockPersonProps} />);
      expect(screen.getByText('7')).toBeInTheDocument();
      expect(screen.getByText(/appearances/i)).toBeInTheDocument();
    });

    it('displays singular "appearance" for count of 1', () => {
      const singleAppearance = { ...mockPersonProps, appearance_count: 1 };
      render(<EntityCard {...singleAppearance} />);
      expect(screen.getByText('1')).toBeInTheDocument();
      expect(screen.getByText(/appearance$/i)).toBeInTheDocument();
    });
  });

  describe('cameras seen', () => {
    it('displays cameras seen count', () => {
      render(<EntityCard {...mockPersonProps} />);
      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText(/cameras/i)).toBeInTheDocument();
    });

    it('displays singular "camera" for single camera', () => {
      render(<EntityCard {...mockVehicleProps} />);
      expect(screen.getByText('1')).toBeInTheDocument();
      expect(screen.getByText(/camera$/i)).toBeInTheDocument();
    });

    it('shows camera names on hover via title attribute', () => {
      render(<EntityCard {...mockPersonProps} />);
      const cameraElement = screen.getByText(/cameras/i).closest('div');
      expect(cameraElement).toHaveAttribute('title', 'front_door, back_yard, garage');
    });
  });

  describe('timestamp formatting', () => {
    it('displays last seen timestamp', () => {
      render(<EntityCard {...mockPersonProps} />);
      expect(screen.getByText('Last seen:')).toBeInTheDocument();
      expect(screen.getByText(/5 minutes ago/)).toBeInTheDocument();
    });

    it('displays first seen timestamp', () => {
      render(<EntityCard {...mockPersonProps} />);
      expect(screen.getByText('First seen:')).toBeInTheDocument();
      expect(screen.getByText(/3 hours ago/)).toBeInTheDocument();
    });

    it('formats "just now" for recent timestamps', () => {
      const justNow = {
        ...mockPersonProps,
        last_seen: new Date(BASE_TIME - 30 * 1000).toISOString(),
      };
      render(<EntityCard {...justNow} />);
      expect(screen.getByText('Just now')).toBeInTheDocument();
    });

    it('formats days ago for older timestamps', () => {
      render(<EntityCard {...mockVehicleProps} />);
      expect(screen.getByText(/1 day ago/)).toBeInTheDocument();
    });
  });

  describe('thumbnail rendering', () => {
    it('renders thumbnail when thumbnail_url is provided', () => {
      render(<EntityCard {...mockPersonProps} />);
      const img = screen.getByRole('img');
      expect(img).toHaveAttribute('src', 'https://example.com/thumbnail.jpg');
    });

    it('renders placeholder when thumbnail_url is null', () => {
      render(<EntityCard {...mockVehicleProps} />);
      const images = screen.queryAllByRole('img');
      expect(images.length).toBe(0);
      // Should show placeholder icon
      const placeholder = screen.getByTestId('entity-placeholder');
      expect(placeholder).toBeInTheDocument();
    });

    it('renders correct alt text for thumbnail', () => {
      render(<EntityCard {...mockPersonProps} />);
      const img = screen.getByRole('img');
      expect(img).toHaveAttribute('alt', expect.stringContaining('Person'));
    });
  });

  describe('entity type icon', () => {
    it('shows person icon for person entities', () => {
      const { container } = render(<EntityCard {...mockPersonProps} />);
      const personIcon = container.querySelector('svg.lucide-user');
      expect(personIcon).toBeInTheDocument();
    });

    it('shows car icon for vehicle entities', () => {
      const { container } = render(<EntityCard {...mockVehicleProps} />);
      const carIcon = container.querySelector('svg.lucide-car');
      expect(carIcon).toBeInTheDocument();
    });
  });

  describe('click behavior', () => {
    it('calls onClick when card is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleClick = vi.fn();
      render(<EntityCard {...mockPersonProps} onClick={handleClick} />);

      const card = screen.getByRole('button');
      await user.click(card);

      expect(handleClick).toHaveBeenCalledWith('entity-abc123');
      expect(handleClick).toHaveBeenCalledTimes(1);

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('applies cursor-pointer when onClick is provided', () => {
      const handleClick = vi.fn();
      const { container } = render(<EntityCard {...mockPersonProps} onClick={handleClick} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('cursor-pointer');
    });

    it('does not apply cursor-pointer when onClick is not provided', () => {
      const { container } = render(<EntityCard {...mockPersonProps} />);
      const card = container.firstChild as HTMLElement;
      expect(card).not.toHaveClass('cursor-pointer');
    });

    it('has role="button" when onClick is provided', () => {
      const handleClick = vi.fn();
      render(<EntityCard {...mockPersonProps} onClick={handleClick} />);
      expect(screen.getByRole('button')).toBeInTheDocument();
    });

    it('supports keyboard navigation with Enter', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleClick = vi.fn();
      render(<EntityCard {...mockPersonProps} onClick={handleClick} />);

      const card = screen.getByRole('button');
      card.focus();
      await user.keyboard('{Enter}');

      expect(handleClick).toHaveBeenCalledWith('entity-abc123');

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('supports keyboard navigation with Space', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleClick = vi.fn();
      render(<EntityCard {...mockPersonProps} onClick={handleClick} />);

      const card = screen.getByRole('button');
      card.focus();
      await user.keyboard(' ');

      expect(handleClick).toHaveBeenCalledWith('entity-abc123');

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });
  });

  describe('styling', () => {
    it('applies NVIDIA dark theme background', () => {
      const { container } = render(<EntityCard {...mockPersonProps} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('bg-[#1F1F1F]');
    });

    it('applies rounded corners', () => {
      const { container } = render(<EntityCard {...mockPersonProps} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('rounded-lg');
    });

    it('applies border styling', () => {
      const { container } = render(<EntityCard {...mockPersonProps} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('border', 'border-gray-800');
    });

    it('applies hover effect', () => {
      const { container } = render(<EntityCard {...mockPersonProps} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('transition-all', 'hover:border-gray-700');
    });

    it('applies NVIDIA green accent for person type badge', () => {
      const { container } = render(<EntityCard {...mockPersonProps} />);
      const badge = container.querySelector('.bg-\\[\\#76B900\\]\\/20');
      expect(badge).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has appropriate aria-label when clickable', () => {
      const handleClick = vi.fn();
      render(<EntityCard {...mockPersonProps} onClick={handleClick} />);
      const card = screen.getByRole('button');
      expect(card).toHaveAttribute('aria-label', expect.stringContaining('View entity'));
    });

    it('thumbnail has alt text', () => {
      render(<EntityCard {...mockPersonProps} />);
      const img = screen.getByRole('img');
      expect(img).toHaveAttribute('alt');
    });

    it('has tabIndex=0 when clickable', () => {
      const handleClick = vi.fn();
      render(<EntityCard {...mockPersonProps} onClick={handleClick} />);
      const card = screen.getByRole('button');
      expect(card).toHaveAttribute('tabIndex', '0');
    });
  });

  describe('edge cases', () => {
    it('handles empty cameras_seen array', () => {
      const noCameras = { ...mockPersonProps, cameras_seen: [] };
      render(<EntityCard {...noCameras} />);
      expect(screen.getByText('0')).toBeInTheDocument();
      expect(screen.getByText(/cameras/i)).toBeInTheDocument();
    });

    it('handles zero appearance count', () => {
      const noAppearances = { ...mockPersonProps, appearance_count: 0 };
      render(<EntityCard {...noAppearances} />);
      expect(screen.getByText('0')).toBeInTheDocument();
    });

    it('handles very long entity ID', () => {
      const longId = {
        ...mockPersonProps,
        id: 'entity-very-long-identifier-that-should-be-truncated-for-display',
      };
      render(<EntityCard {...longId} />);
      // Should truncate to first 12 chars or similar
      expect(screen.getByText(/entity-very-/)).toBeInTheDocument();
    });

    it('handles many cameras', () => {
      const manyCameras = {
        ...mockPersonProps,
        cameras_seen: ['cam1', 'cam2', 'cam3', 'cam4', 'cam5', 'cam6', 'cam7', 'cam8'],
      };
      render(<EntityCard {...manyCameras} />);
      expect(screen.getByText('8')).toBeInTheDocument();
    });
  });
});
