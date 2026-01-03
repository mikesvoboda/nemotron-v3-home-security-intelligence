/**
 * Tests for ZoneList component
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import ZoneList from './ZoneList';

import type { Zone } from '../../types/generated';

describe('ZoneList', () => {
  const mockZones: Zone[] = [
    {
      id: 'zone-1',
      camera_id: 'cam-1',
      name: 'Front Door',
      zone_type: 'entry_point',
      coordinates: [
        [0.1, 0.1],
        [0.3, 0.1],
        [0.3, 0.3],
        [0.1, 0.3],
      ],
      shape: 'rectangle',
      color: '#3B82F6',
      enabled: true,
      priority: 10,
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    },
    {
      id: 'zone-2',
      camera_id: 'cam-1',
      name: 'Driveway',
      zone_type: 'driveway',
      coordinates: [
        [0.5, 0.5],
        [0.9, 0.5],
        [0.9, 0.9],
        [0.5, 0.9],
      ],
      shape: 'rectangle',
      color: '#10B981',
      enabled: false,
      priority: 5,
      created_at: '2025-01-02T00:00:00Z',
      updated_at: '2025-01-02T00:00:00Z',
    },
    {
      id: 'zone-3',
      camera_id: 'cam-1',
      name: 'Sidewalk Area',
      zone_type: 'sidewalk',
      coordinates: [
        [0.2, 0.6],
        [0.4, 0.6],
        [0.4, 0.8],
        [0.2, 0.8],
      ],
      shape: 'rectangle',
      color: '#F59E0B',
      enabled: true,
      priority: 3,
      created_at: '2025-01-03T00:00:00Z',
      updated_at: '2025-01-03T00:00:00Z',
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Display Zones', () => {
    it('should display all zones with their names', () => {
      render(<ZoneList zones={mockZones} />);

      expect(screen.getByText('Front Door')).toBeInTheDocument();
      // 'Driveway' appears twice - once as name, once as type badge
      expect(screen.getAllByText('Driveway')).toHaveLength(2);
      expect(screen.getByText('Sidewalk Area')).toBeInTheDocument();
    });

    it('should display zone type badges', () => {
      render(<ZoneList zones={mockZones} />);

      expect(screen.getByText('Entry Point')).toBeInTheDocument();
      // 'Driveway' appears as both zone name and type badge
      const drivewayTexts = screen.getAllByText('Driveway');
      expect(drivewayTexts.length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('Sidewalk')).toBeInTheDocument();
    });

    it('should display priority for each zone', () => {
      render(<ZoneList zones={mockZones} />);

      expect(screen.getByText('Priority: 10')).toBeInTheDocument();
      expect(screen.getByText('Priority: 5')).toBeInTheDocument();
      expect(screen.getByText('Priority: 3')).toBeInTheDocument();
    });

    it('should display color indicators for zones', () => {
      const { container } = render(<ZoneList zones={mockZones} />);

      // Check for color indicator divs
      const colorIndicators = container.querySelectorAll('.h-8.w-8.rounded');
      expect(colorIndicators).toHaveLength(3);
    });

    it('should show disabled badge for disabled zones', () => {
      render(<ZoneList zones={mockZones} />);

      // Only zone-2 (Driveway) is disabled
      expect(screen.getByText('Disabled')).toBeInTheDocument();
    });

    it('should apply reduced opacity to disabled zones', () => {
      const { container } = render(<ZoneList zones={mockZones} />);

      // The disabled zone container should have opacity-50 class
      const zoneItems = container.querySelectorAll('[role="button"]');
      const disabledZone = Array.from(zoneItems).find((item) =>
        item.classList.contains('opacity-50')
      );
      expect(disabledZone).toBeTruthy();
    });
  });

  describe('Zone Type Badges', () => {
    it('should display correct badge color for entry_point', () => {
      render(<ZoneList zones={[mockZones[0]]} />);

      const badge = screen.getByText('Entry Point');
      expect(badge).toHaveClass('bg-red-500/20', 'text-red-400');
    });

    it('should display correct badge color for driveway', () => {
      render(<ZoneList zones={[mockZones[1]]} />);

      // Note: 'Driveway' appears both as name and type label
      const badges = screen.getAllByText('Driveway');
      const typeBadge = badges.find((el) => el.classList.contains('rounded'));
      expect(typeBadge).toHaveClass('bg-amber-500/20', 'text-amber-400');
    });

    it('should display correct badge color for sidewalk', () => {
      render(<ZoneList zones={[mockZones[2]]} />);

      const badge = screen.getByText('Sidewalk');
      expect(badge).toHaveClass('bg-blue-500/20', 'text-blue-400');
    });

    it('should display other badge for unknown zone types', () => {
      const otherZone: Zone = {
        ...mockZones[0],
        id: 'zone-other',
        name: 'Other Zone',
        zone_type: 'other',
      };
      render(<ZoneList zones={[otherZone]} />);

      const badge = screen.getByText('Other');
      expect(badge).toHaveClass('bg-gray-500/20', 'text-gray-400');
    });
  });

  describe('Empty State', () => {
    it('should display empty state when no zones exist', () => {
      render(<ZoneList zones={[]} />);

      expect(screen.getByText('No zones defined')).toBeInTheDocument();
      expect(
        screen.getByText('Draw a zone on the camera view to get started')
      ).toBeInTheDocument();
    });

    it('should not display zone list when empty', () => {
      const { container } = render(<ZoneList zones={[]} />);

      const zoneItems = container.querySelectorAll('[role="button"]');
      expect(zoneItems).toHaveLength(0);
    });
  });

  describe('Zone Selection', () => {
    it('should call onSelect when zone is clicked', async () => {
      const onSelect = vi.fn();
      render(<ZoneList zones={mockZones} onSelect={onSelect} />);

      const frontDoorZone = screen.getByText('Front Door').closest('[role="button"]');
      if (frontDoorZone) {
        await userEvent.click(frontDoorZone);
      }

      expect(onSelect).toHaveBeenCalledWith('zone-1');
    });

    it('should highlight selected zone', () => {
      const { container } = render(
        <ZoneList zones={mockZones} selectedZoneId="zone-1" />
      );

      const zoneItems = container.querySelectorAll('[role="button"]');
      const selectedZone = Array.from(zoneItems).find((item) =>
        item.classList.contains('border-primary')
      );
      expect(selectedZone).toBeTruthy();
    });

    it('should set aria-pressed for selected zone', () => {
      render(<ZoneList zones={mockZones} selectedZoneId="zone-1" />);

      const selectedZone = screen.getByText('Front Door').closest('[role="button"]');
      expect(selectedZone).toHaveAttribute('aria-pressed', 'true');
    });

    it('should support keyboard selection with Enter', async () => {
      const onSelect = vi.fn();
      render(<ZoneList zones={mockZones} onSelect={onSelect} />);

      const frontDoorZone = screen.getByText('Front Door').closest('[role="button"]');
      if (frontDoorZone instanceof HTMLElement) {
        frontDoorZone.focus();
        await userEvent.keyboard('{Enter}');
      }

      expect(onSelect).toHaveBeenCalledWith('zone-1');
    });

    it('should support keyboard selection with Space', async () => {
      const onSelect = vi.fn();
      render(<ZoneList zones={mockZones} onSelect={onSelect} />);

      const frontDoorZone = screen.getByText('Front Door').closest('[role="button"]');
      if (frontDoorZone instanceof HTMLElement) {
        frontDoorZone.focus();
        await userEvent.keyboard(' ');
      }

      expect(onSelect).toHaveBeenCalledWith('zone-1');
    });
  });

  describe('Enable/Disable Toggle', () => {
    it('should render toggle button when onToggleEnabled is provided', () => {
      const onToggleEnabled = vi.fn();
      render(<ZoneList zones={mockZones} onToggleEnabled={onToggleEnabled} />);

      // Should have toggle buttons (eye icons)
      const enableButtons = screen.getAllByTitle(/able zone/i);
      expect(enableButtons.length).toBeGreaterThan(0);
    });

    it('should not render toggle button when onToggleEnabled is not provided', () => {
      render(<ZoneList zones={mockZones} />);

      const enableButtons = screen.queryAllByTitle(/able zone/i);
      expect(enableButtons).toHaveLength(0);
    });

    it('should call onToggleEnabled when toggle is clicked', async () => {
      const onToggleEnabled = vi.fn();
      render(<ZoneList zones={mockZones} onToggleEnabled={onToggleEnabled} />);

      const toggleButtons = screen.getAllByTitle(/able zone/i);
      await userEvent.click(toggleButtons[0]);

      expect(onToggleEnabled).toHaveBeenCalledWith(mockZones[0]);
    });

    it('should show "Disable zone" title for enabled zones', () => {
      const onToggleEnabled = vi.fn();
      render(<ZoneList zones={[mockZones[0]]} onToggleEnabled={onToggleEnabled} />);

      expect(screen.getByTitle('Disable zone')).toBeInTheDocument();
    });

    it('should show "Enable zone" title for disabled zones', () => {
      const onToggleEnabled = vi.fn();
      render(<ZoneList zones={[mockZones[1]]} onToggleEnabled={onToggleEnabled} />);

      expect(screen.getByTitle('Enable zone')).toBeInTheDocument();
    });

    it('should not propagate click to zone selection', async () => {
      const onSelect = vi.fn();
      const onToggleEnabled = vi.fn();
      render(
        <ZoneList zones={mockZones} onSelect={onSelect} onToggleEnabled={onToggleEnabled} />
      );

      const toggleButtons = screen.getAllByTitle(/able zone/i);
      await userEvent.click(toggleButtons[0]);

      expect(onToggleEnabled).toHaveBeenCalled();
      expect(onSelect).not.toHaveBeenCalled();
    });
  });

  describe('Edit Button', () => {
    it('should render edit button when onEdit is provided', () => {
      const onEdit = vi.fn();
      render(<ZoneList zones={mockZones} onEdit={onEdit} />);

      const editButtons = screen.getAllByTitle('Edit zone');
      expect(editButtons.length).toBeGreaterThan(0);
    });

    it('should not render edit button when onEdit is not provided', () => {
      render(<ZoneList zones={mockZones} />);

      const editButtons = screen.queryAllByTitle('Edit zone');
      expect(editButtons).toHaveLength(0);
    });

    it('should call onEdit when edit button is clicked', async () => {
      const onEdit = vi.fn();
      render(<ZoneList zones={mockZones} onEdit={onEdit} />);

      const editButtons = screen.getAllByTitle('Edit zone');
      await userEvent.click(editButtons[0]);

      expect(onEdit).toHaveBeenCalledWith(mockZones[0]);
    });

    it('should not propagate click to zone selection', async () => {
      const onSelect = vi.fn();
      const onEdit = vi.fn();
      render(<ZoneList zones={mockZones} onSelect={onSelect} onEdit={onEdit} />);

      const editButtons = screen.getAllByTitle('Edit zone');
      await userEvent.click(editButtons[0]);

      expect(onEdit).toHaveBeenCalled();
      expect(onSelect).not.toHaveBeenCalled();
    });
  });

  describe('Delete Button', () => {
    it('should render delete button when onDelete is provided', () => {
      const onDelete = vi.fn();
      render(<ZoneList zones={mockZones} onDelete={onDelete} />);

      const deleteButtons = screen.getAllByTitle('Delete zone');
      expect(deleteButtons.length).toBeGreaterThan(0);
    });

    it('should not render delete button when onDelete is not provided', () => {
      render(<ZoneList zones={mockZones} />);

      const deleteButtons = screen.queryAllByTitle('Delete zone');
      expect(deleteButtons).toHaveLength(0);
    });

    it('should call onDelete when delete button is clicked', async () => {
      const onDelete = vi.fn();
      render(<ZoneList zones={mockZones} onDelete={onDelete} />);

      const deleteButtons = screen.getAllByTitle('Delete zone');
      await userEvent.click(deleteButtons[0]);

      expect(onDelete).toHaveBeenCalledWith(mockZones[0]);
    });

    it('should not propagate click to zone selection', async () => {
      const onSelect = vi.fn();
      const onDelete = vi.fn();
      render(<ZoneList zones={mockZones} onSelect={onSelect} onDelete={onDelete} />);

      const deleteButtons = screen.getAllByTitle('Delete zone');
      await userEvent.click(deleteButtons[0]);

      expect(onDelete).toHaveBeenCalled();
      expect(onSelect).not.toHaveBeenCalled();
    });
  });

  describe('Disabled State', () => {
    it('should disable all interactions when disabled prop is true', async () => {
      const onSelect = vi.fn();
      const onEdit = vi.fn();
      const onDelete = vi.fn();
      const onToggleEnabled = vi.fn();

      render(
        <ZoneList
          zones={mockZones}
          disabled={true}
          onSelect={onSelect}
          onEdit={onEdit}
          onDelete={onDelete}
          onToggleEnabled={onToggleEnabled}
        />
      );

      // Try clicking the zone
      const zoneItem = screen.getByText('Front Door').closest('[role="button"]');
      if (zoneItem) {
        await userEvent.click(zoneItem);
      }
      expect(onSelect).not.toHaveBeenCalled();

      // Try clicking edit
      const editButtons = screen.getAllByTitle('Edit zone');
      await userEvent.click(editButtons[0]);
      expect(onEdit).not.toHaveBeenCalled();

      // Try clicking delete
      const deleteButtons = screen.getAllByTitle('Delete zone');
      await userEvent.click(deleteButtons[0]);
      expect(onDelete).not.toHaveBeenCalled();

      // Try clicking toggle
      const toggleButtons = screen.getAllByTitle(/able zone/i);
      await userEvent.click(toggleButtons[0]);
      expect(onToggleEnabled).not.toHaveBeenCalled();
    });

    it('should set aria-disabled when disabled', () => {
      render(<ZoneList zones={mockZones} disabled={true} />);

      const zoneItems = screen.getAllByRole('button');
      zoneItems.forEach((item) => {
        expect(item).toHaveAttribute('aria-disabled', 'true');
      });
    });

    it('should set tabIndex to -1 when disabled', () => {
      render(<ZoneList zones={mockZones} disabled={true} />);

      const zoneItems = screen.getAllByRole('button');
      zoneItems.forEach((item) => {
        expect(item).toHaveAttribute('tabindex', '-1');
      });
    });
  });

  describe('Accessibility', () => {
    it('should have proper role="button" on zone items', () => {
      render(<ZoneList zones={mockZones} />);

      const zoneItems = screen.getAllByRole('button');
      expect(zoneItems.length).toBeGreaterThanOrEqual(3); // At least the 3 zone items
    });

    it('should be focusable by default', () => {
      render(<ZoneList zones={mockZones} />);

      const zoneItem = screen.getByText('Front Door').closest('[role="button"]');
      expect(zoneItem).toHaveAttribute('tabindex', '0');
    });
  });
});
