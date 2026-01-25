/**
 * Tests for ZoneEditorSidebar component (NEM-3200)
 *
 * Tests the tabbed sidebar interface including:
 * - Tab navigation (Draw, Configure, Analytics)
 * - Zone selection
 * - Collapsed state
 * - Zone list operations
 * - Integration with intelligence components
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import ZoneEditorSidebar from './ZoneEditorSidebar';

import type { Zone } from '../../services/api';

// Mock child components to isolate sidebar testing
vi.mock('./ZoneStatusCard', () => ({
  default: ({ zoneId, zoneName }: { zoneId: string; zoneName: string }) => (
    <div data-testid="mock-zone-status-card">
      ZoneStatusCard: {zoneName} ({zoneId})
    </div>
  ),
}));

vi.mock('./ZoneActivityHeatmap', () => ({
  default: ({ zoneId, zoneName }: { zoneId: string; zoneName: string }) => (
    <div data-testid="mock-zone-activity-heatmap">
      ZoneActivityHeatmap: {zoneName} ({zoneId})
    </div>
  ),
}));

vi.mock('./ZoneOwnershipPanel', () => ({
  default: ({ zoneId, zoneName }: { zoneId: string; zoneName: string }) => (
    <div data-testid="mock-zone-ownership-panel">
      ZoneOwnershipPanel: {zoneName} ({zoneId})
    </div>
  ),
}));

describe('ZoneEditorSidebar', () => {
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
  ];

  const defaultProps = {
    cameraId: 'cam-1',
    zones: mockZones,
    selectedZoneId: null,
    onZoneSelect: vi.fn(),
    onZoneEdit: vi.fn(),
    onZoneDelete: vi.fn(),
    onZoneToggleEnabled: vi.fn(),
  };

  // Create a new QueryClient for each test
  let queryClient: QueryClient;

  const renderWithProvider = (ui: React.ReactElement) => {
    return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
  };

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
  });

  afterEach(() => {
    queryClient.clear();
    vi.restoreAllMocks();
  });

  describe('Rendering', () => {
    it('should render the sidebar', async () => {
      renderWithProvider(<ZoneEditorSidebar {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('zone-editor-sidebar')).toBeInTheDocument();
      });
    });

    it('should render sidebar header', async () => {
      renderWithProvider(<ZoneEditorSidebar {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Zone Editor')).toBeInTheDocument();
      });
    });

    it('should render all three tabs', async () => {
      renderWithProvider(<ZoneEditorSidebar {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('tab-draw')).toBeInTheDocument();
        expect(screen.getByTestId('tab-configure')).toBeInTheDocument();
        expect(screen.getByTestId('tab-analytics')).toBeInTheDocument();
      });
    });

    it('should display tab labels', async () => {
      renderWithProvider(<ZoneEditorSidebar {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Draw')).toBeInTheDocument();
        expect(screen.getByText('Configure')).toBeInTheDocument();
        expect(screen.getByText('Analytics')).toBeInTheDocument();
      });
    });
  });

  describe('Tab Navigation', () => {
    it('should default to Draw tab', async () => {
      renderWithProvider(<ZoneEditorSidebar {...defaultProps} />);

      await waitFor(() => {
        // Draw tab content should show zones list
        expect(screen.getByText('Zones (2)')).toBeInTheDocument();
      });
    });

    it('should switch to Configure tab on click', async () => {
      const user = userEvent.setup();
      renderWithProvider(<ZoneEditorSidebar {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('tab-configure')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('tab-configure'));

      await waitFor(() => {
        expect(screen.getByText('Select a zone to configure')).toBeInTheDocument();
      });
    });

    it('should switch to Analytics tab on click', async () => {
      const user = userEvent.setup();
      renderWithProvider(<ZoneEditorSidebar {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('tab-analytics')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('tab-analytics'));

      await waitFor(() => {
        expect(screen.getByText('Select a zone for analytics')).toBeInTheDocument();
      });
    });

    it('should call onTabChange callback when tab changes', async () => {
      const onTabChange = vi.fn();
      const user = userEvent.setup();

      renderWithProvider(<ZoneEditorSidebar {...defaultProps} onTabChange={onTabChange} />);

      await waitFor(() => {
        expect(screen.getByTestId('tab-configure')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('tab-configure'));

      expect(onTabChange).toHaveBeenCalledWith('configure');
    });

    it('should respect activeTab prop', async () => {
      renderWithProvider(<ZoneEditorSidebar {...defaultProps} activeTab="analytics" />);

      await waitFor(() => {
        expect(screen.getByText('Select a zone for analytics')).toBeInTheDocument();
      });
    });
  });

  describe('Draw Tab', () => {
    it('should display zone count', async () => {
      renderWithProvider(<ZoneEditorSidebar {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Zones (2)')).toBeInTheDocument();
      });
    });

    it('should display zone names', async () => {
      renderWithProvider(<ZoneEditorSidebar {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
        // 'Driveway' appears as both zone name and zone type badge
        expect(screen.getAllByText('Driveway').length).toBeGreaterThanOrEqual(1);
      });
    });
  });

  describe('Configure Tab', () => {
    it('should show empty state when no zone selected', async () => {
      const user = userEvent.setup();
      renderWithProvider(<ZoneEditorSidebar {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('tab-configure')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('tab-configure'));

      await waitFor(() => {
        expect(screen.getByText('Select a zone to configure')).toBeInTheDocument();
        expect(
          screen.getByText('Configure ownership, access control, and settings')
        ).toBeInTheDocument();
      });
    });

    it('should show zone intelligence when zone selected', async () => {
      const user = userEvent.setup();
      renderWithProvider(<ZoneEditorSidebar {...defaultProps} selectedZoneId="zone-1" />);

      await waitFor(() => {
        expect(screen.getByTestId('tab-configure')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('tab-configure'));

      await waitFor(() => {
        expect(screen.getByTestId('mock-zone-status-card')).toBeInTheDocument();
        expect(screen.getByTestId('mock-zone-ownership-panel')).toBeInTheDocument();
      });
    });

    it('should show zone selector dropdown', async () => {
      const user = userEvent.setup();
      renderWithProvider(<ZoneEditorSidebar {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('tab-configure')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('tab-configure'));

      await waitFor(() => {
        expect(screen.getByTestId('zone-selector')).toBeInTheDocument();
      });
    });
  });

  describe('Analytics Tab', () => {
    it('should show empty state when no zone selected', async () => {
      const user = userEvent.setup();
      renderWithProvider(<ZoneEditorSidebar {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('tab-analytics')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('tab-analytics'));

      await waitFor(() => {
        expect(screen.getByText('Select a zone for analytics')).toBeInTheDocument();
        expect(
          screen.getByText('View activity patterns, heatmaps, and trends')
        ).toBeInTheDocument();
      });
    });

    it('should show analytics when zone selected', async () => {
      const user = userEvent.setup();
      renderWithProvider(<ZoneEditorSidebar {...defaultProps} selectedZoneId="zone-1" />);

      await waitFor(() => {
        expect(screen.getByTestId('tab-analytics')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('tab-analytics'));

      await waitFor(() => {
        expect(screen.getByTestId('mock-zone-status-card')).toBeInTheDocument();
        expect(screen.getByTestId('mock-zone-activity-heatmap')).toBeInTheDocument();
      });
    });
  });

  describe('Collapsed State', () => {
    it('should render collapse button', async () => {
      renderWithProvider(<ZoneEditorSidebar {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('collapse-sidebar-btn')).toBeInTheDocument();
      });
    });

    it('should collapse sidebar when collapse button clicked', async () => {
      const user = userEvent.setup();
      const onCollapseChange = vi.fn();

      renderWithProvider(
        <ZoneEditorSidebar {...defaultProps} onCollapseChange={onCollapseChange} />
      );

      await waitFor(() => {
        expect(screen.getByTestId('collapse-sidebar-btn')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('collapse-sidebar-btn'));

      expect(onCollapseChange).toHaveBeenCalledWith(true);
    });

    it('should render collapsed view when collapsed prop is true', async () => {
      const onCollapseChange = vi.fn();

      renderWithProvider(
        <ZoneEditorSidebar {...defaultProps} collapsed={true} onCollapseChange={onCollapseChange} />
      );

      await waitFor(() => {
        expect(screen.getByTestId('expand-sidebar-btn')).toBeInTheDocument();
      });

      // Collapsed view should show only icons
      expect(screen.queryByText('Zone Editor')).not.toBeInTheDocument();
    });

    it('should show expand button in collapsed state', async () => {
      renderWithProvider(
        <ZoneEditorSidebar {...defaultProps} collapsed onCollapseChange={vi.fn()} />
      );

      await waitFor(() => {
        expect(screen.getByTestId('expand-sidebar-btn')).toBeInTheDocument();
      });
    });

    it('should expand sidebar when expand button clicked', async () => {
      const user = userEvent.setup();
      const onCollapseChange = vi.fn();

      renderWithProvider(
        <ZoneEditorSidebar {...defaultProps} collapsed onCollapseChange={onCollapseChange} />
      );

      await waitFor(() => {
        expect(screen.getByTestId('expand-sidebar-btn')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('expand-sidebar-btn'));

      expect(onCollapseChange).toHaveBeenCalledWith(false);
    });

    it('should show collapsed tab icons', async () => {
      renderWithProvider(
        <ZoneEditorSidebar {...defaultProps} collapsed onCollapseChange={vi.fn()} />
      );

      await waitFor(() => {
        expect(screen.getByTestId('collapsed-tab-draw')).toBeInTheDocument();
        expect(screen.getByTestId('collapsed-tab-configure')).toBeInTheDocument();
        expect(screen.getByTestId('collapsed-tab-analytics')).toBeInTheDocument();
      });
    });

    it('should switch tabs from collapsed state', async () => {
      const user = userEvent.setup();
      const onTabChange = vi.fn();

      renderWithProvider(
        <ZoneEditorSidebar
          {...defaultProps}
          collapsed
          onCollapseChange={vi.fn()}
          onTabChange={onTabChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('collapsed-tab-analytics')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('collapsed-tab-analytics'));

      expect(onTabChange).toHaveBeenCalledWith('analytics');
    });
  });

  describe('Zone Selection', () => {
    it('should call onZoneSelect when zone is selected', async () => {
      const onZoneSelect = vi.fn();
      const user = userEvent.setup();

      renderWithProvider(<ZoneEditorSidebar {...defaultProps} onZoneSelect={onZoneSelect} />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      // Click on the zone in the list
      await user.click(screen.getByText('Front Door'));

      expect(onZoneSelect).toHaveBeenCalled();
    });
  });

  describe('Zone Operations', () => {
    it('should call onZoneEdit when edit is triggered', async () => {
      const onZoneEdit = vi.fn();
      const user = userEvent.setup();

      renderWithProvider(<ZoneEditorSidebar {...defaultProps} onZoneEdit={onZoneEdit} />);

      await waitFor(() => {
        expect(screen.getAllByTitle('Edit zone').length).toBeGreaterThan(0);
      });

      await user.click(screen.getAllByTitle('Edit zone')[0]);

      expect(onZoneEdit).toHaveBeenCalledWith(mockZones[0]);
    });

    it('should call onZoneDelete when delete is triggered', async () => {
      const onZoneDelete = vi.fn();
      const user = userEvent.setup();

      renderWithProvider(<ZoneEditorSidebar {...defaultProps} onZoneDelete={onZoneDelete} />);

      await waitFor(() => {
        expect(screen.getAllByTitle('Delete zone').length).toBeGreaterThan(0);
      });

      await user.click(screen.getAllByTitle('Delete zone')[0]);

      expect(onZoneDelete).toHaveBeenCalledWith(mockZones[0]);
    });

    it('should call onZoneToggleEnabled when toggle is triggered', async () => {
      const onZoneToggleEnabled = vi.fn();
      const user = userEvent.setup();

      renderWithProvider(
        <ZoneEditorSidebar {...defaultProps} onZoneToggleEnabled={onZoneToggleEnabled} />
      );

      await waitFor(() => {
        expect(screen.getAllByTitle(/able zone/i).length).toBeGreaterThan(0);
      });

      await user.click(screen.getAllByTitle(/able zone/i)[0]);

      expect(onZoneToggleEnabled).toHaveBeenCalledWith(mockZones[0]);
    });
  });

  describe('Empty State', () => {
    it('should show empty state message when no zones', async () => {
      const user = userEvent.setup();
      renderWithProvider(<ZoneEditorSidebar {...defaultProps} zones={[]} />);

      await waitFor(() => {
        expect(screen.getByTestId('tab-configure')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('tab-configure'));

      await waitFor(() => {
        expect(screen.getByText('No zones defined')).toBeInTheDocument();
        expect(screen.getByText('Draw a zone to get started')).toBeInTheDocument();
      });
    });
  });

  describe('Custom Styling', () => {
    it('should apply custom className', async () => {
      renderWithProvider(<ZoneEditorSidebar {...defaultProps} className="custom-class" />);

      await waitFor(() => {
        expect(screen.getByTestId('zone-editor-sidebar')).toHaveClass('custom-class');
      });
    });
  });
});
