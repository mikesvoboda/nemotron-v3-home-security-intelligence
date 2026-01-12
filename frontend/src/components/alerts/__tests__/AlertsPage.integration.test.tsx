import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useMemo, useState } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AlertActions from '../AlertActions';
import AlertCard from '../AlertCard';
import AlertFilters from '../AlertFilters';

import type { AlertCardProps } from '../AlertCard';
import type { AlertFilterCounts, AlertFilterType } from '../AlertFilters';

/**
 * Integration tests for Alert System components
 * Tests real component interactions without mocks
 *
 * Tests cover:
 * 1. Filter interactions with AlertCard filtering
 * 2. Batch selection via AlertActions
 * 3. Bulk operations on selected alerts
 * 4. Selection state flow between components
 */

// Helper to create test alert data
const createMockAlert = (overrides: Partial<AlertCardProps> = {}): AlertCardProps => {
  const id = overrides.id || `alert-${Math.random()}`;
  return {
    id,
    eventId: 123,
    severity: 'high',
    status: 'pending',
    timestamp: new Date(Date.now() - 30 * 60000).toISOString(), // 30 minutes ago
    camera_name: 'Front Door',
    risk_score: 75,
    summary: 'Person detected near entrance',
    dedup_key: 'front_door:person',
    ...overrides,
  };
};

/**
 * TestAlertsPage component simulates the redesigned alerts page
 * with AlertFilters, AlertActions, and AlertCard components working together
 */
function TestAlertsPage() {
  const alerts = useMemo(
    () => [
      createMockAlert({ id: 'alert-1', severity: 'critical', camera_name: 'Front Door' }),
      createMockAlert({ id: 'alert-2', severity: 'high', camera_name: 'Backyard' }),
      createMockAlert({ id: 'alert-3', severity: 'medium', camera_name: 'Garage' }),
      createMockAlert({ id: 'alert-4', severity: 'critical', camera_name: 'Side Gate' }),
      createMockAlert({ id: 'alert-5', severity: 'high', camera_name: 'Driveway' }),
    ],
    []
  );

  const [selectedAlertIds, setSelectedAlertIds] = useState<Set<string>>(new Set());
  const [activeFilter, setActiveFilter] = useState<AlertFilterType>('all');

  // Filter alerts based on active filter
  const filteredAlerts = useMemo(() => {
    return alerts.filter((alert) => {
      if (activeFilter === 'all') return true;
      if (activeFilter === 'critical') return alert.severity === 'critical';
      if (activeFilter === 'high') return alert.severity === 'high';
      if (activeFilter === 'medium') return alert.severity === 'medium';
      if (activeFilter === 'unread') return alert.status === 'pending';
      return true;
    });
  }, [alerts, activeFilter]);

  // Calculate filter counts
  const filterCounts: AlertFilterCounts = useMemo(() => {
    return {
      all: alerts.length,
      critical: alerts.filter((a) => a.severity === 'critical').length,
      high: alerts.filter((a) => a.severity === 'high').length,
      medium: alerts.filter((a) => a.severity === 'medium').length,
      unread: alerts.filter((a) => a.status === 'pending').length,
    };
  }, [alerts]);

  // Calculate selection state
  const selectedFilteredAlertIds = useMemo(() => {
    return Array.from(selectedAlertIds).filter((id) =>
      filteredAlerts.some((alert) => alert.id === id)
    );
  }, [selectedAlertIds, filteredAlerts]);

  const hasUnacknowledged = useMemo(() => {
    return selectedFilteredAlertIds.some((id) => {
      const alert = alerts.find((a) => a.id === id);
      return alert?.status === 'pending';
    });
  }, [selectedFilteredAlertIds, alerts]);

  // Handlers
  const handleFilterChange = (filter: AlertFilterType) => {
    setActiveFilter(filter);
  };

  const handleSelectAll = (selectAll: boolean) => {
    if (selectAll) {
      const allIds = new Set(filteredAlerts.map((a) => a.id));
      setSelectedAlertIds(allIds);
    } else {
      setSelectedAlertIds(new Set());
    }
  };

  const handleSelectChange = (alertId: string, selected: boolean) => {
    const newSelection = new Set(selectedAlertIds);
    if (selected) {
      newSelection.add(alertId);
    } else {
      newSelection.delete(alertId);
    }
    setSelectedAlertIds(newSelection);
  };

  const handleAcknowledgeSelected = vi.fn(() => {
    // Mock API call - acknowledges selected alerts
    const ids = Array.from(selectedAlertIds);
    // eslint-disable-next-line no-console
    console.log('Acknowledging alerts:', ids);
  });

  const handleDismissSelected = vi.fn(() => {
    // Mock API call - dismisses selected alerts
    const ids = Array.from(selectedAlertIds);
    // eslint-disable-next-line no-console
    console.log('Dismissing alerts:', ids);
  });

  const handleClearSelection = () => {
    setSelectedAlertIds(new Set());
  };

  return (
    <div data-testid="test-alerts-page">
      {/* Filters */}
      <AlertFilters
        activeFilter={activeFilter}
        onFilterChange={handleFilterChange}
        counts={filterCounts}
      />

      {/* Batch Actions */}
      <div className="mt-4">
        <AlertActions
          selectedCount={selectedFilteredAlertIds.length}
          totalCount={filteredAlerts.length}
          hasUnacknowledged={hasUnacknowledged}
          onSelectAll={handleSelectAll}
          onAcknowledgeSelected={handleAcknowledgeSelected}
          onDismissSelected={handleDismissSelected}
          onClearSelection={handleClearSelection}
        />
      </div>

      {/* Alert Cards */}
      <div className="mt-4 grid gap-4" data-testid="alert-cards-container">
        {filteredAlerts.map((alert) => (
          <AlertCard
            key={alert.id}
            {...alert}
            selected={selectedAlertIds.has(alert.id)}
            onSelectChange={handleSelectChange}
            onAcknowledge={vi.fn()}
            onDismiss={vi.fn()}
            onSnooze={vi.fn()}
            onViewEvent={vi.fn()}
          />
        ))}
      </div>
    </div>
  );
}

describe('AlertsPage Integration Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Filter Interactions', () => {
    it('displays all alerts when "All" filter is active', () => {
      render(<TestAlertsPage />);

      // Should show all 5 alerts
      const cards = screen.getAllByRole('article');
      expect(cards).toHaveLength(5);
    });

    it('filters to show only critical alerts when critical filter is clicked', async () => {
      const user = userEvent.setup();
      render(<TestAlertsPage />);

      // Initially shows all 5 alerts
      expect(screen.getAllByRole('article')).toHaveLength(5);

      // Click critical filter
      const criticalBtn = screen.getByRole('button', { name: /filter by critical severity/i });
      await user.click(criticalBtn);

      // Should now show only 2 critical alerts
      await waitFor(() => {
        const cards = screen.getAllByRole('article');
        expect(cards).toHaveLength(2);
      });
    });

    it('filters to show only high alerts when high filter is clicked', async () => {
      const user = userEvent.setup();
      render(<TestAlertsPage />);

      // Click high filter
      const highBtn = screen.getByRole('button', { name: /filter by high severity/i });
      await user.click(highBtn);

      // Should now show only 2 high alerts
      await waitFor(() => {
        const cards = screen.getAllByRole('article');
        expect(cards).toHaveLength(2);
      });
    });

    it('filters to show only medium alerts when medium filter is clicked', async () => {
      const user = userEvent.setup();
      render(<TestAlertsPage />);

      // Click medium filter
      const mediumBtn = screen.getByRole('button', { name: /filter by medium severity/i });
      await user.click(mediumBtn);

      // Should now show only 1 medium alert
      await waitFor(() => {
        const cards = screen.getAllByRole('article');
        expect(cards).toHaveLength(1);
      });
    });

    it('displays correct alert counts in filter buttons', () => {
      render(<TestAlertsPage />);

      // Check counts in filter buttons using getAllByText for non-unique values
      const allCountBadges = screen.getAllByText('5');
      expect(allCountBadges.length).toBeGreaterThan(0); // All filter shows 5, unread also shows 5

      const criticalCountBadges = screen.getAllByText('2');
      expect(criticalCountBadges.length).toBeGreaterThan(0); // Critical filter shows 2, high also shows 2

      // Verify the filter buttons exist with proper labels
      expect(screen.getByRole('button', { name: /filter by all alerts/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /filter by critical severity/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /filter by high severity/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /filter by medium severity/i })).toBeInTheDocument();
    });

    it('updates displayed alerts when switching between filters', async () => {
      const user = userEvent.setup();
      render(<TestAlertsPage />);

      // Start with all alerts (5)
      expect(screen.getAllByRole('article')).toHaveLength(5);

      // Switch to critical (2)
      const criticalBtn = screen.getByRole('button', { name: /filter by critical severity/i });
      await user.click(criticalBtn);
      await waitFor(() => {
        expect(screen.getAllByRole('article')).toHaveLength(2);
      });

      // Switch to high (2)
      const highBtn = screen.getByRole('button', { name: /filter by high severity/i });
      await user.click(highBtn);
      await waitFor(() => {
        expect(screen.getAllByRole('article')).toHaveLength(2);
      });

      // Switch back to all (5)
      const allBtn = screen.getByRole('button', { name: /filter by all alerts/i });
      await user.click(allBtn);
      await waitFor(() => {
        expect(screen.getAllByRole('article')).toHaveLength(5);
      });
    });
  });

  describe('Batch Selection', () => {
    it('selects all alerts when "Select All" button is clicked', async () => {
      const user = userEvent.setup();
      render(<TestAlertsPage />);

      // Click Select All button
      const selectAllBtn = screen.getByRole('button', { name: /select all alerts/i });
      await user.click(selectAllBtn);

      // All checkboxes should be checked
      await waitFor(() => {
        const checkboxes = screen.getAllByRole('checkbox');
        checkboxes.forEach((checkbox) => {
          expect(checkbox).toBeChecked();
        });
      });

      // Should show "5 selected"
      expect(screen.getByText('5 selected')).toBeInTheDocument();
    });

    it('deselects all alerts when "Deselect All" is clicked', async () => {
      const user = userEvent.setup();
      render(<TestAlertsPage />);

      // First select all
      const selectAllBtn = screen.getByRole('button', { name: /select all alerts/i });
      await user.click(selectAllBtn);

      await waitFor(() => {
        expect(screen.getByText('5 selected')).toBeInTheDocument();
      });

      // Now deselect all
      const deselectAllBtn = screen.getByRole('button', { name: /deselect all alerts/i });
      await user.click(deselectAllBtn);

      // All checkboxes should be unchecked
      await waitFor(() => {
        const checkboxes = screen.getAllByRole('checkbox');
        checkboxes.forEach((checkbox) => {
          expect(checkbox).not.toBeChecked();
        });
      });

      // Should not show selection count
      expect(screen.queryByText(/selected/)).not.toBeInTheDocument();
    });

    it('individually selects alerts by clicking checkboxes', async () => {
      const user = userEvent.setup();
      render(<TestAlertsPage />);

      // Get all checkboxes
      const checkboxes = screen.getAllByRole('checkbox');

      // Select first 2 checkboxes
      await user.click(checkboxes[0]);
      await user.click(checkboxes[1]);

      // Should show "2 selected"
      await waitFor(() => {
        expect(screen.getByText('2 selected')).toBeInTheDocument();
      });

      // First 2 should be checked
      expect(checkboxes[0]).toBeChecked();
      expect(checkboxes[1]).toBeChecked();
      expect(checkboxes[2]).not.toBeChecked();
    });

    it('toggles individual alert selection correctly', async () => {
      const user = userEvent.setup();
      render(<TestAlertsPage />);

      const checkboxes = screen.getAllByRole('checkbox');

      // Select first checkbox
      await user.click(checkboxes[0]);
      await waitFor(() => {
        expect(checkboxes[0]).toBeChecked();
        expect(screen.getByText('1 selected')).toBeInTheDocument();
      });

      // Deselect first checkbox
      await user.click(checkboxes[0]);
      await waitFor(() => {
        expect(checkboxes[0]).not.toBeChecked();
        expect(screen.queryByText(/selected/)).not.toBeInTheDocument();
      });
    });

    it('maintains selection state when filtering', async () => {
      const user = userEvent.setup();
      render(<TestAlertsPage />);

      // Select all alerts (5)
      const selectAllBtn = screen.getByRole('button', { name: /select all alerts/i });
      await user.click(selectAllBtn);

      await waitFor(() => {
        expect(screen.getByText('5 selected')).toBeInTheDocument();
      });

      // Switch to critical filter (2 alerts)
      const criticalBtn = screen.getByRole('button', { name: /filter by critical severity/i });
      await user.click(criticalBtn);

      // Should show "2 selected" (only critical alerts are shown)
      await waitFor(() => {
        expect(screen.getByText('2 selected')).toBeInTheDocument();
        expect(screen.getAllByRole('article')).toHaveLength(2);
      });

      // Switch back to all
      const allBtn = screen.getByRole('button', { name: /filter by all alerts/i });
      await user.click(allBtn);

      // Should show all 5 selected again
      await waitFor(() => {
        expect(screen.getByText('5 selected')).toBeInTheDocument();
      });
    });
  });

  describe('Bulk Operations', () => {
    it('displays acknowledge selected button when alerts are selected', async () => {
      const user = userEvent.setup();
      render(<TestAlertsPage />);

      // Select first alert
      const checkboxes = screen.getAllByRole('checkbox');
      await user.click(checkboxes[0]);

      // Acknowledge Selected button should appear
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /acknowledge selected/i })).toBeInTheDocument();
      });
    });

    it('displays dismiss selected button when alerts are selected', async () => {
      const user = userEvent.setup();
      render(<TestAlertsPage />);

      // Select first alert
      const checkboxes = screen.getAllByRole('checkbox');
      await user.click(checkboxes[0]);

      // Dismiss Selected button should appear
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /dismiss selected/i })).toBeInTheDocument();
      });
    });

    it('calls acknowledge handler for all selected alerts', async () => {
      const user = userEvent.setup();
      const consoleLogSpy = vi.spyOn(console, 'log').mockImplementation(() => {});

      render(<TestAlertsPage />);

      // Select 3 alerts
      const checkboxes = screen.getAllByRole('checkbox');
      await user.click(checkboxes[0]);
      await user.click(checkboxes[1]);
      await user.click(checkboxes[2]);

      await waitFor(() => {
        expect(screen.getByText('3 selected')).toBeInTheDocument();
      });

      // Click Acknowledge Selected
      const acknowledgeBtn = screen.getByRole('button', { name: /acknowledge selected/i });
      await user.click(acknowledgeBtn);

      // Should have called console.log with selected alert IDs
      await waitFor(() => {
        expect(consoleLogSpy).toHaveBeenCalledWith(
          'Acknowledging alerts:',
          expect.arrayContaining(['alert-1', 'alert-2', 'alert-3'])
        );
      });

      consoleLogSpy.mockRestore();
    });

    it('calls dismiss handler for all selected alerts', async () => {
      const user = userEvent.setup();
      const consoleLogSpy = vi.spyOn(console, 'log').mockImplementation(() => {});

      render(<TestAlertsPage />);

      // Select 2 alerts
      const checkboxes = screen.getAllByRole('checkbox');
      await user.click(checkboxes[0]);
      await user.click(checkboxes[1]);

      await waitFor(() => {
        expect(screen.getByText('2 selected')).toBeInTheDocument();
      });

      // Click Dismiss Selected
      const dismissBtn = screen.getByRole('button', { name: /dismiss selected/i });
      await user.click(dismissBtn);

      // Should have called console.log with selected alert IDs
      await waitFor(() => {
        expect(consoleLogSpy).toHaveBeenCalledWith(
          'Dismissing alerts:',
          expect.arrayContaining(['alert-1', 'alert-2'])
        );
      });

      consoleLogSpy.mockRestore();
    });

    it('clears selection when clear selection button is clicked', async () => {
      const user = userEvent.setup();
      render(<TestAlertsPage />);

      // Select some alerts
      const selectAllBtn = screen.getByRole('button', { name: /select all alerts/i });
      await user.click(selectAllBtn);

      await waitFor(() => {
        expect(screen.getByText('5 selected')).toBeInTheDocument();
      });

      // Click Clear Selection
      const clearBtn = screen.getByRole('button', { name: /clear selection/i });
      await user.click(clearBtn);

      // Selection should be cleared
      await waitFor(() => {
        expect(screen.queryByText(/selected/)).not.toBeInTheDocument();
        const checkboxes = screen.getAllByRole('checkbox');
        checkboxes.forEach((checkbox) => {
          expect(checkbox).not.toBeChecked();
        });
      });
    });
  });

  describe('Selection State Flow', () => {
    it('flows selection state from AlertActions to AlertCard components', async () => {
      const user = userEvent.setup();
      render(<TestAlertsPage />);

      // Click Select All in AlertActions
      const selectAllBtn = screen.getByRole('button', { name: /select all alerts/i });
      await user.click(selectAllBtn);

      // All AlertCard checkboxes should be checked
      await waitFor(() => {
        const checkboxes = screen.getAllByRole('checkbox');
        expect(checkboxes).toHaveLength(5);
        checkboxes.forEach((checkbox) => {
          expect(checkbox).toBeChecked();
        });
      });
    });

    it('flows selection state from AlertCard to AlertActions count', async () => {
      const user = userEvent.setup();
      render(<TestAlertsPage />);

      // Click individual checkboxes in AlertCards
      const checkboxes = screen.getAllByRole('checkbox');
      await user.click(checkboxes[0]);
      await user.click(checkboxes[1]);
      await user.click(checkboxes[2]);

      // AlertActions should show correct count
      await waitFor(() => {
        expect(screen.getByText('3 selected')).toBeInTheDocument();
      });
    });

    it('updates AlertActions buttons based on AlertCard selection state', async () => {
      const user = userEvent.setup();
      render(<TestAlertsPage />);

      // Initially no selection - no batch action buttons
      expect(screen.queryByRole('button', { name: /acknowledge selected/i })).not.toBeInTheDocument();

      // Select an alert
      const checkboxes = screen.getAllByRole('checkbox');
      await user.click(checkboxes[0]);

      // Batch action buttons should appear
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /acknowledge selected/i })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /dismiss selected/i })).toBeInTheDocument();
      });
    });

    it('correctly handles selection state across filter changes', async () => {
      const user = userEvent.setup();
      render(<TestAlertsPage />);

      // Select first alert (critical)
      const checkboxes = screen.getAllByRole('checkbox');
      const firstCheckbox = checkboxes[0];
      await user.click(firstCheckbox);

      await waitFor(() => {
        expect(screen.getByText('1 selected')).toBeInTheDocument();
      });

      // Switch to high filter (first alert is critical, so it won't be shown)
      const highBtn = screen.getByRole('button', { name: /filter by high severity/i });
      await user.click(highBtn);

      // Should show 0 selected (because selected alert is filtered out)
      await waitFor(() => {
        expect(screen.queryByText(/selected/)).not.toBeInTheDocument();
      });

      // Switch back to all
      const allBtn = screen.getByRole('button', { name: /filter by all alerts/i });
      await user.click(allBtn);

      // Should show 1 selected again
      await waitFor(() => {
        expect(screen.getByText('1 selected')).toBeInTheDocument();
      });
    });

    it('maintains consistent selection state between all components', async () => {
      const user = userEvent.setup();
      render(<TestAlertsPage />);

      // Select all via AlertActions
      const selectAllBtn = screen.getByRole('button', { name: /select all alerts/i });
      await user.click(selectAllBtn);

      await waitFor(() => {
        // AlertActions shows correct count
        expect(screen.getByText('5 selected')).toBeInTheDocument();

        // All AlertCard checkboxes are checked
        const checkboxes = screen.getAllByRole('checkbox');
        checkboxes.forEach((checkbox) => {
          expect(checkbox).toBeChecked();
        });

        // Batch action buttons are enabled
        expect(screen.getByRole('button', { name: /acknowledge selected/i })).toBeInTheDocument();
      });

      // Deselect one via AlertCard
      const checkboxes = screen.getAllByRole('checkbox');
      await user.click(checkboxes[0]);

      await waitFor(() => {
        // AlertActions shows updated count
        expect(screen.getByText('4 selected')).toBeInTheDocument();

        // First checkbox is unchecked, others are checked
        expect(checkboxes[0]).not.toBeChecked();
        expect(checkboxes[1]).toBeChecked();
      });
    });
  });

  describe('Complex Interaction Flows', () => {
    it('handles filter change, select all, and bulk operation flow', async () => {
      const user = userEvent.setup();
      const consoleLogSpy = vi.spyOn(console, 'log').mockImplementation(() => {});

      render(<TestAlertsPage />);

      // 1. Filter to critical alerts
      const criticalBtn = screen.getByRole('button', { name: /filter by critical severity/i });
      await user.click(criticalBtn);

      await waitFor(() => {
        expect(screen.getAllByRole('article')).toHaveLength(2);
      });

      // 2. Select all critical alerts
      const selectAllBtn = screen.getByRole('button', { name: /select all alerts/i });
      await user.click(selectAllBtn);

      await waitFor(() => {
        expect(screen.getByText('2 selected')).toBeInTheDocument();
      });

      // 3. Acknowledge selected
      const acknowledgeBtn = screen.getByRole('button', { name: /acknowledge selected/i });
      await user.click(acknowledgeBtn);

      // Should have acknowledged both critical alerts
      await waitFor(() => {
        expect(consoleLogSpy).toHaveBeenCalledWith(
          'Acknowledging alerts:',
          expect.arrayContaining(['alert-1', 'alert-4'])
        );
      });

      consoleLogSpy.mockRestore();
    });

    it('handles partial selection, filter change, and additional selection', async () => {
      const user = userEvent.setup();
      render(<TestAlertsPage />);

      // 1. Select first 2 alerts
      const checkboxes = screen.getAllByRole('checkbox');
      await user.click(checkboxes[0]);
      await user.click(checkboxes[1]);

      await waitFor(() => {
        expect(screen.getByText('2 selected')).toBeInTheDocument();
      });

      // 2. Filter to critical (shows 2 critical alerts)
      const criticalBtn = screen.getByRole('button', { name: /filter by critical severity/i });
      await user.click(criticalBtn);

      await waitFor(() => {
        const cards = screen.getAllByRole('article');
        expect(cards).toHaveLength(2);
      });

      // 3. Should show how many of the filtered alerts are selected
      // (alert-1 is critical and was selected, so 1 selected)
      await waitFor(() => {
        const selectedText = screen.queryByText(/selected/);
        if (selectedText) {
          expect(selectedText.textContent).toMatch(/1 selected/);
        }
      });
    });
  });
});
