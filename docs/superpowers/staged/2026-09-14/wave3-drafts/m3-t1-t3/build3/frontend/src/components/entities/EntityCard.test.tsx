import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import EntityCard, {
  type EntityCardProps,
  getActivityTier,
  tierStyles,
  type ActivityTier,
} from './EntityCard';

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
      const placeholder = screen.getByTestId('placeholder-thumbnail');
      expect(placeholder).toBeInTheDocument();
    });

    it('renders correct alt text for thumbnail', () => {
      render(<EntityCard {...mockPersonProps} />);
      const img = screen.getByRole('img');
      expect(img).toHaveAttribute('alt', expect.stringContaining('Person'));
    });

    it('renders person placeholder for person entities without thumbnail', () => {
      const personNoThumbnail = { ...mockPersonProps, thumbnail_url: null };
      const { container } = render(<EntityCard {...personNoThumbnail} />);
      // Should show User icon for person type
      const userIcon = container.querySelector(
        '[data-testid="placeholder-thumbnail"] svg.lucide-user'
      );
      expect(userIcon).toBeInTheDocument();
    });

    it('renders vehicle placeholder for vehicle entities without thumbnail', () => {
      const { container } = render(<EntityCard {...mockVehicleProps} />);
      // Should show Car icon for vehicle type
      const carIcon = container.querySelector(
        '[data-testid="placeholder-thumbnail"] svg.lucide-car'
      );
      expect(carIcon).toBeInTheDocument();
    });

    it('maintains aspect ratio in thumbnail container', () => {
      render(<EntityCard {...mockVehicleProps} />);
      const thumbnailContainer = screen.getByTestId('thumbnail-container');
      expect(thumbnailContainer).toHaveClass('h-32');
      expect(thumbnailContainer).toHaveClass('overflow-hidden');
    });
  });

  describe('image error fallback', () => {
    it('falls back to placeholder when image fails to load', () => {
      render(<EntityCard {...mockPersonProps} />);

      // Initially shows the image
      const img = screen.getByRole('img');
      expect(img).toBeInTheDocument();

      // Trigger image error
      fireEvent.error(img);

      // Should now show placeholder instead
      const placeholder = screen.getByTestId('placeholder-thumbnail');
      expect(placeholder).toBeInTheDocument();
      expect(screen.queryByRole('img')).not.toBeInTheDocument();
    });

    it('shows person placeholder on image error for person entity', () => {
      const { container } = render(<EntityCard {...mockPersonProps} />);

      // Trigger image error
      const img = screen.getByRole('img');
      fireEvent.error(img);

      // Should show User icon
      const userIcon = container.querySelector(
        '[data-testid="placeholder-thumbnail"] svg.lucide-user'
      );
      expect(userIcon).toBeInTheDocument();
    });

    it('shows vehicle placeholder on image error for vehicle entity', () => {
      const vehicleWithThumbnail = {
        ...mockVehicleProps,
        thumbnail_url: 'https://example.com/vehicle.jpg',
      };
      const { container } = render(<EntityCard {...vehicleWithThumbnail} />);

      // Trigger image error
      const img = screen.getByRole('img');
      fireEvent.error(img);

      // Should show Car icon
      const carIcon = container.querySelector(
        '[data-testid="placeholder-thumbnail"] svg.lucide-car'
      );
      expect(carIcon).toBeInTheDocument();
    });

    it('does not display text like "undefined" or "thumbnail" on error', () => {
      render(<EntityCard {...mockPersonProps} />);

      // Trigger image error
      const img = screen.getByRole('img');
      fireEvent.error(img);

      // Should not display problematic text
      expect(screen.queryByText(/undefined/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/^thumbnail$/i)).not.toBeInTheDocument();
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

  describe('activity tier calculation (getActivityTier)', () => {
    // Use a fixed timestamp for testing
    const NOW = new Date('2024-01-15T12:00:00Z').getTime();

    describe('hot tier', () => {
      it('returns hot when 20+ sightings AND seen within 24 hours', () => {
        const lastSeen = new Date(NOW - 12 * 60 * 60 * 1000).toISOString(); // 12 hours ago
        expect(getActivityTier(20, lastSeen, NOW)).toBe('hot');
        expect(getActivityTier(25, lastSeen, NOW)).toBe('hot');
        expect(getActivityTier(100, lastSeen, NOW)).toBe('hot');
      });

      it('returns hot when exactly at 24 hour boundary', () => {
        const lastSeen = new Date(NOW - 24 * 60 * 60 * 1000).toISOString(); // exactly 24 hours ago
        expect(getActivityTier(20, lastSeen, NOW)).toBe('hot');
      });

      it('does not return hot if less than 20 sightings even if recent', () => {
        const lastSeen = new Date(NOW - 1 * 60 * 60 * 1000).toISOString(); // 1 hour ago
        expect(getActivityTier(19, lastSeen, NOW)).not.toBe('hot');
      });

      it('does not return hot if more than 24 hours old even with many sightings', () => {
        const lastSeen = new Date(NOW - 25 * 60 * 60 * 1000).toISOString(); // 25 hours ago
        expect(getActivityTier(20, lastSeen, NOW)).not.toBe('hot');
      });
    });

    describe('active tier', () => {
      it('returns active when 10+ sightings regardless of time', () => {
        const lastSeen = new Date(NOW - 72 * 60 * 60 * 1000).toISOString(); // 72 hours ago
        expect(getActivityTier(10, lastSeen, NOW)).toBe('active');
        expect(getActivityTier(15, lastSeen, NOW)).toBe('active');
      });

      it('returns active when seen within 48 hours regardless of count', () => {
        const lastSeen = new Date(NOW - 24 * 60 * 60 * 1000).toISOString(); // 24 hours ago
        expect(getActivityTier(5, lastSeen, NOW)).toBe('active');
        expect(getActivityTier(9, lastSeen, NOW)).toBe('active');
      });

      it('returns active when exactly at 48 hour boundary', () => {
        const lastSeen = new Date(NOW - 48 * 60 * 60 * 1000).toISOString(); // exactly 48 hours ago
        expect(getActivityTier(3, lastSeen, NOW)).toBe('active');
      });
    });

    describe('normal tier', () => {
      it('returns normal when 3+ sightings but older than 48 hours', () => {
        const lastSeen = new Date(NOW - 72 * 60 * 60 * 1000).toISOString(); // 72 hours ago
        expect(getActivityTier(3, lastSeen, NOW)).toBe('normal');
        expect(getActivityTier(5, lastSeen, NOW)).toBe('normal');
        expect(getActivityTier(9, lastSeen, NOW)).toBe('normal');
      });
    });

    describe('cold tier', () => {
      it('returns cold when less than 3 sightings and older than 48 hours', () => {
        const lastSeen = new Date(NOW - 72 * 60 * 60 * 1000).toISOString(); // 72 hours ago
        expect(getActivityTier(0, lastSeen, NOW)).toBe('cold');
        expect(getActivityTier(1, lastSeen, NOW)).toBe('cold');
        expect(getActivityTier(2, lastSeen, NOW)).toBe('cold');
      });
    });

    describe('tier priority', () => {
      it('hot takes priority over active when both conditions met', () => {
        const lastSeen = new Date(NOW - 1 * 60 * 60 * 1000).toISOString(); // 1 hour ago
        // 20 sightings within 24 hours qualifies for both hot (20+ && <24h) and active (10+)
        expect(getActivityTier(20, lastSeen, NOW)).toBe('hot');
      });
    });
  });

  describe('activity tier styling', () => {
    it('applies scale-105 class to hot tier entities', () => {
      const { container } = render(<EntityCard {...mockPersonProps} activity_tier="hot" />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('scale-105');
    });

    it('applies ring-2 and ring-red-500 classes to hot tier entities', () => {
      const { container } = render(<EntityCard {...mockPersonProps} activity_tier="hot" />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('ring-2');
      expect(card).toHaveClass('ring-red-500');
    });

    it('applies z-10 class to hot tier entities', () => {
      const { container } = render(<EntityCard {...mockPersonProps} activity_tier="hot" />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('z-10');
    });

    it('applies ring-1 and ring-[#76B900] classes to active tier entities', () => {
      const { container } = render(<EntityCard {...mockPersonProps} activity_tier="active" />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('ring-1');
      expect(card).toHaveClass('ring-[#76B900]');
    });

    it('does not apply extra styling to normal tier entities', () => {
      const { container } = render(<EntityCard {...mockPersonProps} activity_tier="normal" />);
      const card = container.firstChild as HTMLElement;
      expect(card).not.toHaveClass('ring-1');
      expect(card).not.toHaveClass('ring-2');
      expect(card).not.toHaveClass('scale-105');
      expect(card).not.toHaveClass('opacity-70');
    });

    it('applies opacity-70 class to cold tier entities', () => {
      const { container } = render(<EntityCard {...mockPersonProps} activity_tier="cold" />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('opacity-70');
    });

    it('sets data-activity-tier attribute on card', () => {
      const { container } = render(<EntityCard {...mockPersonProps} activity_tier="hot" />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveAttribute('data-activity-tier', 'hot');
    });
  });

  describe('activity tier badges', () => {
    it('displays HOT badge for hot tier entities', () => {
      render(<EntityCard {...mockPersonProps} activity_tier="hot" />);
      const hotBadge = screen.getByTestId('activity-badge-hot');
      expect(hotBadge).toBeInTheDocument();
      expect(hotBadge).toHaveTextContent('HOT');
    });

    it('HOT badge has animate-pulse class for animation', () => {
      render(<EntityCard {...mockPersonProps} activity_tier="hot" />);
      const hotBadge = screen.getByTestId('activity-badge-hot');
      expect(hotBadge).toHaveClass('animate-pulse');
    });

    it('displays Active badge for active tier entities', () => {
      render(<EntityCard {...mockPersonProps} activity_tier="active" />);
      const activeBadge = screen.getByTestId('activity-badge-active');
      expect(activeBadge).toBeInTheDocument();
      expect(activeBadge).toHaveTextContent('Active');
    });

    it('does not display activity badge for normal tier entities', () => {
      render(<EntityCard {...mockPersonProps} activity_tier="normal" />);
      expect(screen.queryByTestId('activity-badge-hot')).not.toBeInTheDocument();
      expect(screen.queryByTestId('activity-badge-active')).not.toBeInTheDocument();
    });

    it('does not display activity badge for cold tier entities', () => {
      render(<EntityCard {...mockPersonProps} activity_tier="cold" />);
      expect(screen.queryByTestId('activity-badge-hot')).not.toBeInTheDocument();
      expect(screen.queryByTestId('activity-badge-active')).not.toBeInTheDocument();
    });

    it('does not display activity badge when activity_tier is undefined', () => {
      render(<EntityCard {...mockPersonProps} />);
      expect(screen.queryByTestId('activity-badge-hot')).not.toBeInTheDocument();
      expect(screen.queryByTestId('activity-badge-active')).not.toBeInTheDocument();
    });
  });

  describe('tierStyles constant', () => {
    it('contains all activity tier keys', () => {
      const tiers: ActivityTier[] = ['hot', 'active', 'normal', 'cold'];
      tiers.forEach((tier) => {
        expect(tierStyles).toHaveProperty(tier);
      });
    });

    it('hot tier includes scale-105 and ring-2 ring-red-500', () => {
      expect(tierStyles.hot).toContain('scale-105');
      expect(tierStyles.hot).toContain('ring-2');
      expect(tierStyles.hot).toContain('ring-red-500');
    });

    it('active tier includes ring-1 and ring-[#76B900]', () => {
      expect(tierStyles.active).toContain('ring-1');
      expect(tierStyles.active).toContain('ring-[#76B900]');
    });

    it('normal tier has empty styling', () => {
      expect(tierStyles.normal).toBe('');
    });

    it('cold tier includes opacity-70', () => {
      expect(tierStyles.cold).toContain('opacity-70');
    });
  });
});
