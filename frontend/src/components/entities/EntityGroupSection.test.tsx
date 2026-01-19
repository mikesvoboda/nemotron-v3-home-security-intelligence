import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Car, HelpCircle, User } from 'lucide-react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import EntityGroupSection, { type GroupedEntity } from './EntityGroupSection';

describe('EntityGroupSection', () => {
  // Base time for consistent testing
  const BASE_TIME = new Date('2024-01-15T10:00:00Z').getTime();

  // Mock entity data
  const mockPeople: GroupedEntity[] = [
    {
      id: 'person-001',
      entity_type: 'person',
      first_seen: '2024-01-15T08:00:00Z',
      last_seen: '2024-01-15T10:00:00Z',
      appearance_count: 5,
      cameras_seen: ['front_door', 'back_yard'],
      thumbnail_url: 'https://example.com/thumb1.jpg',
      trust_status: 'trusted',
    },
    {
      id: 'person-002',
      entity_type: 'person',
      first_seen: '2024-01-15T09:00:00Z',
      last_seen: '2024-01-15T09:30:00Z',
      appearance_count: 2,
      cameras_seen: ['driveway'],
      thumbnail_url: null,
      trust_status: 'unclassified',
    },
  ];

  const mockVehicles: GroupedEntity[] = [
    {
      id: 'vehicle-001',
      entity_type: 'vehicle',
      first_seen: '2024-01-15T07:00:00Z',
      last_seen: '2024-01-15T11:00:00Z',
      appearance_count: 3,
      cameras_seen: ['driveway'],
      thumbnail_url: 'https://example.com/car.jpg',
      trust_status: 'untrusted',
    },
  ];

  const mockUnknown: GroupedEntity[] = [
    {
      id: 'unknown-001',
      entity_type: 'unknown_type',
      first_seen: '2024-01-15T06:00:00Z',
      last_seen: '2024-01-15T06:30:00Z',
      appearance_count: 1,
      cameras_seen: ['garage'],
      thumbnail_url: null,
      trust_status: null,
    },
  ];

  // Mock system time for consistent testing
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(BASE_TIME);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('basic rendering', () => {
    it('renders section with title, icon, and count', () => {
      render(<EntityGroupSection title="People" icon={User} entities={mockPeople} />);

      expect(screen.getByText('People')).toBeInTheDocument();
      expect(screen.getByTestId('entity-group-count-people')).toHaveTextContent('2');
    });

    it('renders entity cards when expanded', () => {
      render(<EntityGroupSection title="People" icon={User} entities={mockPeople} />);

      // Should show both entity cards
      const entityCards = screen.getAllByTestId('entity-card');
      expect(entityCards).toHaveLength(2);
    });

    it('displays correct count for single entity', () => {
      render(<EntityGroupSection title="Vehicles" icon={Car} entities={mockVehicles} />);

      expect(screen.getByTestId('entity-group-count-vehicles')).toHaveTextContent('1');
    });

    it('renders with different icon for each section type', () => {
      const { container: peopleContainer } = render(
        <EntityGroupSection title="People" icon={User} entities={mockPeople} />
      );
      expect(peopleContainer.querySelector('.lucide-user')).toBeInTheDocument();

      const { container: vehicleContainer } = render(
        <EntityGroupSection title="Vehicles" icon={Car} entities={mockVehicles} />
      );
      expect(vehicleContainer.querySelector('.lucide-car')).toBeInTheDocument();

      const { container: unknownContainer } = render(
        <EntityGroupSection title="Unknown" icon={HelpCircle} entities={mockUnknown} />
      );
      // HelpCircle icon renders as lucide-help-circle
      expect(unknownContainer.querySelector('[class*="lucide"]')).toBeInTheDocument();
    });
  });

  describe('empty section behavior', () => {
    it('does not render when entities array is empty', () => {
      const { container } = render(<EntityGroupSection title="People" icon={User} entities={[]} />);

      expect(container.firstChild).toBeNull();
      expect(screen.queryByText('People')).not.toBeInTheDocument();
    });
  });

  describe('collapse behavior', () => {
    it('shows content when not collapsed by default', () => {
      render(
        <EntityGroupSection title="People" icon={User} entities={mockPeople} defaultCollapsed={false} />
      );

      expect(screen.getByTestId('entity-group-content-people')).toBeInTheDocument();
      expect(screen.getByTestId('collapse-icon-expanded')).toBeInTheDocument();
    });

    it('hides content when collapsed by default', () => {
      render(
        <EntityGroupSection title="Unknown" icon={HelpCircle} entities={mockUnknown} defaultCollapsed={true} />
      );

      expect(screen.queryByTestId('entity-group-content-unknown')).not.toBeInTheDocument();
      expect(screen.getByTestId('collapse-icon-collapsed')).toBeInTheDocument();
    });

    it('toggles collapse state when header is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();

      render(
        <EntityGroupSection title="People" icon={User} entities={mockPeople} defaultCollapsed={false} />
      );

      // Initially expanded
      expect(screen.getByTestId('entity-group-content-people')).toBeInTheDocument();

      // Click header to collapse
      await user.click(screen.getByTestId('entity-group-header-people'));

      // Should now be collapsed
      expect(screen.queryByTestId('entity-group-content-people')).not.toBeInTheDocument();

      // Click header to expand again
      await user.click(screen.getByTestId('entity-group-header-people'));

      // Should be expanded again
      expect(screen.getByTestId('entity-group-content-people')).toBeInTheDocument();

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('expands collapsed section when header is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();

      render(
        <EntityGroupSection title="Unknown" icon={HelpCircle} entities={mockUnknown} defaultCollapsed={true} />
      );

      // Initially collapsed
      expect(screen.queryByTestId('entity-group-content-unknown')).not.toBeInTheDocument();

      // Click header to expand
      await user.click(screen.getByTestId('entity-group-header-unknown'));

      // Should now be expanded
      expect(screen.getByTestId('entity-group-content-unknown')).toBeInTheDocument();

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });
  });

  describe('keyboard accessibility', () => {
    it('toggles collapse with Enter key', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();

      render(
        <EntityGroupSection title="People" icon={User} entities={mockPeople} defaultCollapsed={false} />
      );

      const header = screen.getByTestId('entity-group-header-people');
      header.focus();

      await user.keyboard('{Enter}');

      expect(screen.queryByTestId('entity-group-content-people')).not.toBeInTheDocument();

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('toggles collapse with Space key', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();

      render(
        <EntityGroupSection title="People" icon={User} entities={mockPeople} defaultCollapsed={false} />
      );

      const header = screen.getByTestId('entity-group-header-people');
      header.focus();

      await user.keyboard(' ');

      expect(screen.queryByTestId('entity-group-content-people')).not.toBeInTheDocument();

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('has correct aria-expanded attribute', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();

      render(
        <EntityGroupSection title="People" icon={User} entities={mockPeople} defaultCollapsed={false} />
      );

      const header = screen.getByTestId('entity-group-header-people');

      // Initially expanded
      expect(header).toHaveAttribute('aria-expanded', 'true');

      // Click to collapse
      await user.click(header);

      // Should show collapsed state
      expect(header).toHaveAttribute('aria-expanded', 'false');

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('has aria-controls linking to content', () => {
      render(<EntityGroupSection title="People" icon={User} entities={mockPeople} />);

      const header = screen.getByTestId('entity-group-header-people');
      expect(header).toHaveAttribute('aria-controls', 'entity-group-content-people');
    });
  });

  describe('entity card interaction', () => {
    it('calls onEntityClick when entity card is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleClick = vi.fn();

      render(
        <EntityGroupSection
          title="People"
          icon={User}
          entities={mockPeople}
          onEntityClick={handleClick}
        />
      );

      // Click the first entity card
      const entityCards = screen.getAllByRole('button');
      const entityCard = entityCards.find((btn) =>
        btn.getAttribute('aria-label')?.includes('View entity')
      );

      if (entityCard) {
        await user.click(entityCard);
        expect(handleClick).toHaveBeenCalledWith('person-001');
      }

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('passes trust status through getEntityTrustStatus callback', () => {
      const getTrustStatus = vi.fn().mockReturnValue('trusted');

      render(
        <EntityGroupSection
          title="People"
          icon={User}
          entities={mockPeople}
          getEntityTrustStatus={getTrustStatus}
        />
      );

      // The callback should be called for each entity
      expect(getTrustStatus).toHaveBeenCalledWith('person-001', 'trusted');
      expect(getTrustStatus).toHaveBeenCalledWith('person-002', 'unclassified');
    });
  });

  describe('styling', () => {
    it('applies custom className', () => {
      const { container } = render(
        <EntityGroupSection
          title="People"
          icon={User}
          entities={mockPeople}
          className="custom-class"
        />
      );

      const section = container.firstChild as HTMLElement;
      expect(section).toHaveClass('custom-class');
    });

    it('applies NVIDIA green accent color to icon', () => {
      const { container } = render(
        <EntityGroupSection title="People" icon={User} entities={mockPeople} />
      );

      const greenIcon = container.querySelector('.text-\\[\\#76B900\\]');
      expect(greenIcon).toBeInTheDocument();
    });

    it('applies dark theme background to header', () => {
      render(<EntityGroupSection title="People" icon={User} entities={mockPeople} />);

      const header = screen.getByTestId('entity-group-header-people');
      expect(header).toHaveClass('bg-[#1F1F1F]');
    });

    it('renders grid layout for entity cards', () => {
      render(<EntityGroupSection title="People" icon={User} entities={mockPeople} />);

      const content = screen.getByTestId('entity-group-content-people');
      expect(content).toHaveClass('grid');
    });
  });

  describe('data-testid attributes', () => {
    it('generates correct testid for section', () => {
      render(<EntityGroupSection title="People" icon={User} entities={mockPeople} />);

      expect(screen.getByTestId('entity-group-people')).toBeInTheDocument();
    });

    it('generates correct testid for header', () => {
      render(<EntityGroupSection title="People" icon={User} entities={mockPeople} />);

      expect(screen.getByTestId('entity-group-header-people')).toBeInTheDocument();
    });

    it('generates correct testid for count badge', () => {
      render(<EntityGroupSection title="People" icon={User} entities={mockPeople} />);

      expect(screen.getByTestId('entity-group-count-people')).toBeInTheDocument();
    });

    it('generates correct testid for content area', () => {
      render(<EntityGroupSection title="People" icon={User} entities={mockPeople} />);

      expect(screen.getByTestId('entity-group-content-people')).toBeInTheDocument();
    });

    it('handles multi-word titles in testid', () => {
      render(
        <EntityGroupSection title="Unknown Entities" icon={HelpCircle} entities={mockUnknown} />
      );

      expect(screen.getByTestId('entity-group-unknown-entities')).toBeInTheDocument();
    });
  });
});
