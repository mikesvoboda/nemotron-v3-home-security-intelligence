import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import ExportPanel from './ExportPanel';
import * as api from '../../services/api';

import type { Camera, EventStatsResponse } from '../../services/api';

// Mock API module with explicit function mocks
vi.mock('../../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/api')>();
  return {
    ...actual,
    fetchCameras: vi.fn(),
    fetchEventStats: vi.fn(),
    exportEventsCSV: vi.fn(),
    exportEventsJSON: vi.fn(),
  };
});

describe('ExportPanel', () => {
  const mockCameras: Camera[] = [
    {
      id: 'camera-1',
      name: 'Front Door',
      folder_path: '/path/to/front',
      status: 'online',
      created_at: '2024-01-01T00:00:00Z',
      last_seen_at: '2024-01-01T12:00:00Z',
    },
    {
      id: 'camera-2',
      name: 'Back Yard',
      folder_path: '/path/to/back',
      status: 'online',
      created_at: '2024-01-01T00:00:00Z',
      last_seen_at: '2024-01-01T12:00:00Z',
    },
  ];

  const mockStats: EventStatsResponse = {
    total_events: 150,
    events_by_risk_level: {
      critical: 10,
      high: 30,
      medium: 60,
      low: 50,
    },
    events_by_camera: [
      { camera_id: 'camera-1', camera_name: 'Front Door', event_count: 80 },
      { camera_id: 'camera-2', camera_name: 'Back Yard', event_count: 70 },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
    vi.mocked(api.fetchEventStats).mockResolvedValue(mockStats);
    vi.mocked(api.exportEventsCSV).mockResolvedValue(undefined);
    // Mock exportEventsJSON if it exists (added in NEM-3611)
    if (api.exportEventsJSON) {
      vi.mocked(api.exportEventsJSON).mockResolvedValue(undefined);
    }
  });

  describe('Rendering', () => {
    it('renders the export panel title', async () => {
      render(<ExportPanel />);

      expect(screen.getByText('Data Export')).toBeInTheDocument();

      // Wait for async state updates to complete
      await waitFor(() => {
        expect(api.fetchCameras).toHaveBeenCalled();
      });
    });

    it('renders format selection with CSV selected by default', async () => {
      render(<ExportPanel />);

      expect(screen.getByText('Export Format')).toBeInTheDocument();

      const csvButton = screen.getByRole('button', { name: /CSV/i });
      expect(csvButton).toHaveAttribute('aria-pressed', 'true');

      await waitFor(() => {
        expect(api.fetchCameras).toHaveBeenCalled();
      });
    });

    it('renders filter options section', async () => {
      render(<ExportPanel />);

      expect(screen.getByText('Filter Options')).toBeInTheDocument();
      expect(screen.getByLabelText('Camera')).toBeInTheDocument();
      expect(screen.getByLabelText('Risk Level')).toBeInTheDocument();
      expect(screen.getByLabelText('Start Date')).toBeInTheDocument();
      expect(screen.getByLabelText('End Date')).toBeInTheDocument();
      expect(screen.getByLabelText('Review Status')).toBeInTheDocument();

      await waitFor(() => {
        expect(api.fetchCameras).toHaveBeenCalled();
      });
    });

    it('renders export preview section', async () => {
      render(<ExportPanel />);

      expect(screen.getByText('Export Preview')).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.getByText(/~150 events/)).toBeInTheDocument();
      });
    });

    it('renders export button', async () => {
      render(<ExportPanel />);

      expect(screen.getByRole('button', { name: /Export Events/i })).toBeInTheDocument();

      await waitFor(() => {
        expect(api.fetchCameras).toHaveBeenCalled();
      });
    });
  });

  describe('Filter Options', () => {
    it('loads cameras into camera dropdown', async () => {
      render(<ExportPanel />);

      const cameraSelect = screen.getByLabelText('Camera');

      // Wait for camera options to actually render (not just API call)
      await waitFor(() => {
        const options = within(cameraSelect).getAllByRole('option');
        expect(options.length).toBeGreaterThan(1); // More than just "All Cameras"
      });

      const options = within(cameraSelect).getAllByRole('option');
      expect(options).toHaveLength(3); // All Cameras + 2 cameras
      expect(options[0]).toHaveTextContent('All Cameras');
      expect(options[1]).toHaveTextContent('Front Door');
      expect(options[2]).toHaveTextContent('Back Yard');
    });

    it('allows selecting a camera filter', async () => {
      const user = userEvent.setup();
      render(<ExportPanel />);

      // Wait for camera options to actually render (not just API call)
      const cameraSelect = screen.getByLabelText('Camera');
      await waitFor(() => {
        const options = within(cameraSelect).getAllByRole('option');
        expect(options.length).toBeGreaterThan(1); // More than just "All Cameras"
      });

      await user.selectOptions(cameraSelect, 'camera-1');

      expect(cameraSelect).toHaveValue('camera-1');
    });

    it('allows selecting a risk level filter', async () => {
      const user = userEvent.setup();
      render(<ExportPanel />);

      const riskSelect = screen.getByLabelText('Risk Level');
      await user.selectOptions(riskSelect, 'high');

      expect(riskSelect).toHaveValue('high');
    });

    it('allows selecting date filters', async () => {
      const user = userEvent.setup();
      render(<ExportPanel />);

      const startDateInput = screen.getByLabelText('Start Date');
      const endDateInput = screen.getByLabelText('End Date');

      await user.type(startDateInput, '2024-01-01');
      await user.type(endDateInput, '2024-01-31');

      expect(startDateInput).toHaveValue('2024-01-01');
      expect(endDateInput).toHaveValue('2024-01-31');
    });

    it('allows selecting review status filter', async () => {
      const user = userEvent.setup();
      render(<ExportPanel />);

      const statusSelect = screen.getByLabelText('Review Status');
      await user.selectOptions(statusSelect, 'false');

      expect(statusSelect).toHaveValue('false');
    });

    it('shows clear all filters link when filters are active', async () => {
      const user = userEvent.setup();
      render(<ExportPanel />);

      // Initially no clear link
      expect(screen.queryByText('Clear all filters')).not.toBeInTheDocument();

      // Apply a filter
      const riskSelect = screen.getByLabelText('Risk Level');
      await user.selectOptions(riskSelect, 'high');

      // Clear link should appear
      expect(screen.getByText('Clear all filters')).toBeInTheDocument();
    });

    it('clears all filters when clicking clear all filters', async () => {
      const user = userEvent.setup();
      render(<ExportPanel />);

      // Apply filters
      const riskSelect = screen.getByLabelText('Risk Level');
      await user.selectOptions(riskSelect, 'high');

      const cameraSelect = screen.getByLabelText('Camera');
      await waitFor(() => {
        expect(api.fetchCameras).toHaveBeenCalled();
      });
      await user.selectOptions(cameraSelect, 'camera-1');

      // Click clear all
      await user.click(screen.getByText('Clear all filters'));

      // Filters should be reset
      expect(riskSelect).toHaveValue('');
      expect(cameraSelect).toHaveValue('');
    });
  });

  describe('Initial Filters', () => {
    it('accepts initial filters from props', async () => {
      render(
        <ExportPanel
          initialFilters={{
            camera_id: 'camera-1',
            risk_level: 'high',
            start_date: '2024-01-01',
          }}
        />
      );

      await waitFor(() => {
        expect(api.fetchCameras).toHaveBeenCalled();
      });

      const cameraSelect = screen.getByLabelText('Camera');
      const riskSelect = screen.getByLabelText('Risk Level');
      const startDateInput = screen.getByLabelText('Start Date');

      expect(cameraSelect).toHaveValue('camera-1');
      expect(riskSelect).toHaveValue('high');
      expect(startDateInput).toHaveValue('2024-01-01');
    });
  });

  describe('Export Preview', () => {
    it('shows event count from stats', async () => {
      render(<ExportPanel />);

      await waitFor(() => {
        expect(screen.getByText(/~150 events/)).toBeInTheDocument();
      });
    });

    it('shows calculating while loading stats', () => {
      vi.mocked(api.fetchEventStats).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(<ExportPanel />);

      expect(screen.getByText('Calculating...')).toBeInTheDocument();
    });

    it('updates estimate when filters change', async () => {
      const user = userEvent.setup();
      render(<ExportPanel />);

      await waitFor(() => {
        expect(screen.getByText(/~150 events/)).toBeInTheDocument();
      });

      // Apply risk filter
      const riskSelect = screen.getByLabelText('Risk Level');
      await user.selectOptions(riskSelect, 'high');

      // Estimate should update to show filtered count
      await waitFor(() => {
        expect(screen.getByText(/~30 events \(filtered\)/)).toBeInTheDocument();
      });
    });

    it('shows format in preview', async () => {
      render(<ExportPanel />);

      expect(screen.getByText('Format')).toBeInTheDocument();
      // There are multiple CSV texts - one in the format selector and one in the preview
      // Just check that at least one exists
      expect(screen.getAllByText('CSV').length).toBeGreaterThan(0);

      await waitFor(() => {
        expect(api.fetchCameras).toHaveBeenCalled();
      });
    });
  });

  describe('Export Action', () => {
    it('calls exportEventsCSV with current filters', async () => {
      const user = userEvent.setup();
      render(<ExportPanel />);

      // Wait for camera options to actually render (not just API call)
      const cameraSelect = screen.getByLabelText('Camera');
      await waitFor(() => {
        const options = within(cameraSelect).getAllByRole('option');
        expect(options.length).toBeGreaterThan(1); // More than just "All Cameras"
      });

      // Apply some filters
      await user.selectOptions(cameraSelect, 'camera-1');

      const riskSelect = screen.getByLabelText('Risk Level');
      await user.selectOptions(riskSelect, 'high');

      // Click export
      const exportButton = screen.getByRole('button', { name: /Export Events/i });
      await user.click(exportButton);

      await waitFor(() => {
        expect(api.exportEventsCSV).toHaveBeenCalledWith({
          camera_id: 'camera-1',
          risk_level: 'high',
          start_date: undefined,
          end_date: undefined,
          reviewed: undefined,
        });
      });
    });

    it('shows loading state during export', async () => {
      const user = userEvent.setup();

      // Make export slow
      vi.mocked(api.exportEventsCSV).mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 100))
      );

      render(<ExportPanel />);

      await waitFor(() => {
        expect(api.fetchCameras).toHaveBeenCalled();
      });

      const exportButton = screen.getByRole('button', { name: /Export Events/i });
      await user.click(exportButton);

      // Should show loading state
      expect(screen.getByText('Exporting...')).toBeInTheDocument();
      expect(exportButton).toBeDisabled();
    });

    it('shows success message after CSV export', async () => {
      const user = userEvent.setup();
      render(<ExportPanel />);

      await waitFor(() => {
        expect(api.fetchCameras).toHaveBeenCalled();
      });

      const exportButton = screen.getByRole('button', { name: /Export Events/i });
      await user.click(exportButton);

      await waitFor(() => {
        expect(
          screen.getByText('Export completed successfully! Check your downloads folder.')
        ).toBeInTheDocument();
      });
      expect(api.exportEventsCSV).toHaveBeenCalled();
    });

    it('exports events as JSON when JSON format is selected', async () => {
      const user = userEvent.setup();
      render(<ExportPanel />);

      await waitFor(() => {
        expect(api.fetchCameras).toHaveBeenCalled();
      });

      // Find and click JSON format button
      const jsonButton = screen.getByRole('button', { name: /JSON/i });
      expect(jsonButton).toHaveAttribute('aria-pressed', 'false');
      await user.click(jsonButton);

      // Verify JSON is now selected
      await waitFor(() => {
        expect(jsonButton).toHaveAttribute('aria-pressed', 'true');
      });

      // Click export
      const exportButton = screen.getByRole('button', { name: /Export Events/i });
      await user.click(exportButton);

      await waitFor(() => {
        // Should call exportEventsJSON, not exportEventsCSV
        expect(api.exportEventsJSON).toHaveBeenCalled();
        expect(
          screen.getByText('Export completed successfully! Check your downloads folder.')
        ).toBeInTheDocument();
      });
    });

    it('shows error message on export failure', async () => {
      const user = userEvent.setup();
      vi.mocked(api.exportEventsCSV).mockRejectedValue(new Error('Network error'));

      render(<ExportPanel />);

      await waitFor(() => {
        expect(api.fetchCameras).toHaveBeenCalled();
      });

      const exportButton = screen.getByRole('button', { name: /Export Events/i });
      await user.click(exportButton);

      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });
    });

    it('calls onExportStart callback', async () => {
      const user = userEvent.setup();
      const handleExportStart = vi.fn();

      render(<ExportPanel onExportStart={handleExportStart} />);

      await waitFor(() => {
        expect(api.fetchCameras).toHaveBeenCalled();
      });

      const exportButton = screen.getByRole('button', { name: /Export Events/i });
      await user.click(exportButton);

      expect(handleExportStart).toHaveBeenCalled();
    });

    it('calls onExportComplete callback on success', async () => {
      const user = userEvent.setup();
      const handleExportComplete = vi.fn();

      render(<ExportPanel onExportComplete={handleExportComplete} />);

      await waitFor(() => {
        expect(api.fetchCameras).toHaveBeenCalled();
      });

      const exportButton = screen.getByRole('button', { name: /Export Events/i });
      await user.click(exportButton);

      await waitFor(() => {
        expect(handleExportComplete).toHaveBeenCalledWith(true, 'Export completed successfully');
      });
    });

    it('calls onExportComplete callback on failure', async () => {
      const user = userEvent.setup();
      const handleExportComplete = vi.fn();
      vi.mocked(api.exportEventsCSV).mockRejectedValue(new Error('Export failed'));

      render(<ExportPanel onExportComplete={handleExportComplete} />);

      await waitFor(() => {
        expect(api.fetchCameras).toHaveBeenCalled();
      });

      const exportButton = screen.getByRole('button', { name: /Export Events/i });
      await user.click(exportButton);

      await waitFor(() => {
        expect(handleExportComplete).toHaveBeenCalledWith(false, 'Export failed');
      });
    });

    it('disables export button when no events', async () => {
      vi.mocked(api.fetchEventStats).mockResolvedValue({
        total_events: 0,
        events_by_risk_level: { critical: 0, high: 0, medium: 0, low: 0 },
        events_by_camera: [],
      });

      render(<ExportPanel />);

      // Wait for stats to load AND for React to re-render with the disabled state
      await waitFor(() => {
        expect(api.fetchEventStats).toHaveBeenCalled();
        const exportButton = screen.getByRole('button', { name: /Export Events/i });
        expect(exportButton).toBeDisabled();
      });
    });
  });

  describe('Format Selection', () => {
    it('CSV format is selected by default', async () => {
      render(<ExportPanel />);

      const csvButton = screen.getByRole('button', { name: /CSV/i });
      expect(csvButton).toHaveAttribute('aria-pressed', 'true');

      await waitFor(() => {
        expect(api.fetchCameras).toHaveBeenCalled();
      });
    });

    it('JSON format button is enabled and selectable', async () => {
      const user = userEvent.setup();
      render(<ExportPanel />);

      const jsonButton = screen.getByRole('button', { name: /JSON/i });
      expect(jsonButton).not.toBeDisabled();

      // Click JSON button to select it
      await user.click(jsonButton);
      expect(jsonButton).toHaveAttribute('aria-pressed', 'true');

      await waitFor(() => {
        expect(api.fetchCameras).toHaveBeenCalled();
      });
    });
  });

  describe('Collapsible Mode', () => {
    it('renders as collapsible when prop is set', async () => {
      render(<ExportPanel collapsible />);

      // Should have a toggle button
      const toggleButton = screen.getByRole('button', { name: /Data Export/i });
      expect(toggleButton).toHaveAttribute('aria-expanded', 'true');

      await waitFor(() => {
        expect(api.fetchCameras).toHaveBeenCalled();
      });
    });

    it('starts collapsed when defaultCollapsed is true', async () => {
      render(<ExportPanel collapsible defaultCollapsed />);

      const toggleButton = screen.getByRole('button', { name: /Data Export/i });
      expect(toggleButton).toHaveAttribute('aria-expanded', 'false');

      // Content should not be visible
      expect(screen.queryByText('Export Format')).not.toBeInTheDocument();

      await waitFor(() => {
        expect(api.fetchCameras).toHaveBeenCalled();
      });
    });

    it('toggles content when clicking header in collapsible mode', async () => {
      const user = userEvent.setup();
      render(<ExportPanel collapsible defaultCollapsed />);

      // Initially collapsed
      expect(screen.queryByText('Export Format')).not.toBeInTheDocument();

      // Click to expand
      const toggleButton = screen.getByRole('button', { name: /Data Export/i });
      await user.click(toggleButton);

      // Content should now be visible
      expect(screen.getByText('Export Format')).toBeInTheDocument();

      // Click to collapse again
      await user.click(toggleButton);

      // Content should be hidden again
      expect(screen.queryByText('Export Format')).not.toBeInTheDocument();
    });

    it('is not collapsible by default', async () => {
      render(<ExportPanel />);

      // Should not have toggle functionality - title is just text, not a button
      const title = screen.getByText('Data Export');
      expect(title.tagName).not.toBe('BUTTON');

      // Content should be visible
      expect(screen.getByText('Export Format')).toBeInTheDocument();

      await waitFor(() => {
        expect(api.fetchCameras).toHaveBeenCalled();
      });
    });
  });

  describe('Error Handling', () => {
    it('handles camera fetch error gracefully', async () => {
      vi.mocked(api.fetchCameras).mockRejectedValue(new Error('Camera fetch failed'));

      render(<ExportPanel />);

      await waitFor(() => {
        expect(api.fetchCameras).toHaveBeenCalled();
      });

      // Panel should still render
      expect(screen.getByText('Data Export')).toBeInTheDocument();

      // Camera dropdown should only have "All Cameras" option
      const cameraSelect = screen.getByLabelText('Camera');
      const options = within(cameraSelect).getAllByRole('option');
      expect(options).toHaveLength(1);
      expect(options[0]).toHaveTextContent('All Cameras');
    });

    it('handles stats fetch error gracefully', async () => {
      vi.mocked(api.fetchEventStats).mockRejectedValue(new Error('Stats fetch failed'));

      render(<ExportPanel />);

      // Wait for stats fetch to complete and show "Unknown" (not "Calculating...")
      await waitFor(() => {
        expect(screen.getByText('Unknown')).toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    it('has proper labels for all form inputs', async () => {
      render(<ExportPanel />);

      expect(screen.getByLabelText('Camera')).toBeInTheDocument();
      expect(screen.getByLabelText('Risk Level')).toBeInTheDocument();
      expect(screen.getByLabelText('Start Date')).toBeInTheDocument();
      expect(screen.getByLabelText('End Date')).toBeInTheDocument();
      expect(screen.getByLabelText('Review Status')).toBeInTheDocument();

      await waitFor(() => {
        expect(api.fetchCameras).toHaveBeenCalled();
      });
    });

    it('has aria-pressed on format buttons', async () => {
      render(<ExportPanel />);

      const csvButton = screen.getByRole('button', { name: /CSV/i });
      expect(csvButton).toHaveAttribute('aria-pressed');

      await waitFor(() => {
        expect(api.fetchCameras).toHaveBeenCalled();
      });
    });
  });
});
