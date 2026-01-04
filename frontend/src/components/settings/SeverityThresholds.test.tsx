import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import SeverityThresholds from './SeverityThresholds';
import * as api from '../../services/api';

// Mock the API module
vi.mock('../../services/api');

describe('SeverityThresholds', () => {
  const mockSeverityConfig: api.SeverityMetadataResponse = {
    definitions: [
      {
        severity: 'low',
        label: 'Low',
        description: 'Routine activity',
        color: '#22c55e',
        priority: 3,
        min_score: 0,
        max_score: 29,
      },
      {
        severity: 'medium',
        label: 'Medium',
        description: 'Elevated attention needed',
        color: '#eab308',
        priority: 2,
        min_score: 30,
        max_score: 59,
      },
      {
        severity: 'high',
        label: 'High',
        description: 'Significant concern',
        color: '#f97316',
        priority: 1,
        min_score: 60,
        max_score: 84,
      },
      {
        severity: 'critical',
        label: 'Critical',
        description: 'Immediate attention required',
        color: '#ef4444',
        priority: 0,
        min_score: 85,
        max_score: 100,
      },
    ],
    thresholds: {
      low_max: 29,
      medium_max: 59,
      high_max: 84,
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders component with title', async () => {
    vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);

    render(<SeverityThresholds />);

    await waitFor(() => {
      expect(screen.getByText('Risk Score Thresholds')).toBeInTheDocument();
    });
  });

  it('shows loading skeleton while fetching config', () => {
    vi.mocked(api.fetchSeverityConfig).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );

    render(<SeverityThresholds />);

    // Check for skeleton loading elements
    const skeletons = document.querySelectorAll('.skeleton');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('displays all severity levels after loading', async () => {
    vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);

    render(<SeverityThresholds />);

    await waitFor(() => {
      expect(screen.getByText('Low')).toBeInTheDocument();
    });

    expect(screen.getByText('Medium')).toBeInTheDocument();
    expect(screen.getByText('High')).toBeInTheDocument();
    expect(screen.getByText('Critical')).toBeInTheDocument();
  });

  it('displays correct score ranges for each severity level', async () => {
    vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);

    render(<SeverityThresholds />);

    await waitFor(() => {
      expect(screen.getByText('0-29')).toBeInTheDocument();
    });

    expect(screen.getByText('30-59')).toBeInTheDocument();
    expect(screen.getByText('60-84')).toBeInTheDocument();
    expect(screen.getByText('85-100')).toBeInTheDocument();
  });

  it('displays descriptions for each severity level', async () => {
    vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);

    render(<SeverityThresholds />);

    await waitFor(() => {
      expect(screen.getByText('Routine activity')).toBeInTheDocument();
    });

    expect(screen.getByText('Elevated attention needed')).toBeInTheDocument();
    expect(screen.getByText('Significant concern')).toBeInTheDocument();
    expect(screen.getByText('Immediate attention required')).toBeInTheDocument();
  });

  it('applies correct colors to severity indicators', async () => {
    vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);

    render(<SeverityThresholds />);

    await waitFor(() => {
      expect(screen.getByText('Low')).toBeInTheDocument();
    });

    // Find color indicators by data-testid
    const lowIndicator = screen.getByTestId('severity-indicator-low');
    const mediumIndicator = screen.getByTestId('severity-indicator-medium');
    const highIndicator = screen.getByTestId('severity-indicator-high');
    const criticalIndicator = screen.getByTestId('severity-indicator-critical');

    expect(lowIndicator).toHaveStyle({ backgroundColor: '#22c55e' });
    expect(mediumIndicator).toHaveStyle({ backgroundColor: '#eab308' });
    expect(highIndicator).toHaveStyle({ backgroundColor: '#f97316' });
    expect(criticalIndicator).toHaveStyle({ backgroundColor: '#ef4444' });
  });

  it('displays error message when fetch fails', async () => {
    vi.mocked(api.fetchSeverityConfig).mockRejectedValue(new Error('Network error'));

    render(<SeverityThresholds />);

    await waitFor(() => {
      expect(screen.getByText('Failed to load severity thresholds')).toBeInTheDocument();
    });
  });

  it('displays error message for non-Error objects', async () => {
    vi.mocked(api.fetchSeverityConfig).mockRejectedValue('Unknown error');

    render(<SeverityThresholds />);

    await waitFor(() => {
      expect(screen.getByText('Failed to load severity thresholds')).toBeInTheDocument();
    });
  });

  it('does not show severity data when error occurs', async () => {
    vi.mocked(api.fetchSeverityConfig).mockRejectedValue(new Error('Network error'));

    render(<SeverityThresholds />);

    await waitFor(() => {
      expect(screen.getByText('Failed to load severity thresholds')).toBeInTheDocument();
    });

    expect(screen.queryByText('Low')).not.toBeInTheDocument();
    expect(screen.queryByText('Medium')).not.toBeInTheDocument();
    expect(screen.queryByText('High')).not.toBeInTheDocument();
    expect(screen.queryByText('Critical')).not.toBeInTheDocument();
  });

  it('applies custom className', async () => {
    vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);

    render(<SeverityThresholds className="custom-test-class" />);

    await waitFor(() => {
      expect(screen.getByText('Risk Score Thresholds')).toBeInTheDocument();
    });

    // The Card component should have the custom class
    const card = screen.getByText('Risk Score Thresholds').closest('.custom-test-class');
    expect(card).toBeInTheDocument();
  });

  it('renders severity levels in order from low to critical', async () => {
    vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);

    render(<SeverityThresholds />);

    await waitFor(() => {
      expect(screen.getByText('Low')).toBeInTheDocument();
    });

    // Get all severity rows
    const rows = screen.getAllByRole('row');

    // First data row (after header) should be Low
    // The order should be Low -> Medium -> High -> Critical based on score
    const rowTexts = rows.map((row) => row.textContent);
    const lowIndex = rowTexts.findIndex((text) => text?.includes('Low'));
    const mediumIndex = rowTexts.findIndex((text) => text?.includes('Medium'));
    const highIndex = rowTexts.findIndex((text) => text?.includes('High'));
    const criticalIndex = rowTexts.findIndex((text) => text?.includes('Critical'));

    expect(lowIndex).toBeLessThan(mediumIndex);
    expect(mediumIndex).toBeLessThan(highIndex);
    expect(highIndex).toBeLessThan(criticalIndex);
  });

  describe('accessibility', () => {
    it('uses table for semantic structure', async () => {
      vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);

      render(<SeverityThresholds />);

      await waitFor(() => {
        expect(screen.getByRole('table')).toBeInTheDocument();
      });
    });

    it('includes proper table headers', async () => {
      vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);

      render(<SeverityThresholds />);

      await waitFor(() => {
        expect(screen.getByRole('columnheader', { name: /level/i })).toBeInTheDocument();
      });

      expect(screen.getByRole('columnheader', { name: /range/i })).toBeInTheDocument();
      expect(screen.getByRole('columnheader', { name: /description/i })).toBeInTheDocument();
    });
  });

  describe('edge cases', () => {
    it('handles empty definitions array', async () => {
      vi.mocked(api.fetchSeverityConfig).mockResolvedValue({
        definitions: [],
        thresholds: {
          low_max: 29,
          medium_max: 59,
          high_max: 84,
        },
      });

      render(<SeverityThresholds />);

      // Wait for loading to complete - table should render even with empty definitions
      await waitFor(() => {
        expect(screen.getByRole('table')).toBeInTheDocument();
      });

      // Verify the table is rendered with headers but no data rows
      expect(screen.getByRole('columnheader', { name: /level/i })).toBeInTheDocument();
    });

    it('handles custom threshold values', async () => {
      const customConfig: api.SeverityMetadataResponse = {
        definitions: [
          {
            severity: 'low',
            label: 'Low',
            description: 'Safe',
            color: '#22c55e',
            priority: 3,
            min_score: 0,
            max_score: 20,
          },
          {
            severity: 'medium',
            label: 'Medium',
            description: 'Warning',
            color: '#eab308',
            priority: 2,
            min_score: 21,
            max_score: 50,
          },
          {
            severity: 'high',
            label: 'High',
            description: 'Danger',
            color: '#f97316',
            priority: 1,
            min_score: 51,
            max_score: 80,
          },
          {
            severity: 'critical',
            label: 'Critical',
            description: 'Emergency',
            color: '#ef4444',
            priority: 0,
            min_score: 81,
            max_score: 100,
          },
        ],
        thresholds: {
          low_max: 20,
          medium_max: 50,
          high_max: 80,
        },
      };

      vi.mocked(api.fetchSeverityConfig).mockResolvedValue(customConfig);

      render(<SeverityThresholds />);

      await waitFor(() => {
        expect(screen.getByText('0-20')).toBeInTheDocument();
      });

      expect(screen.getByText('21-50')).toBeInTheDocument();
      expect(screen.getByText('51-80')).toBeInTheDocument();
      expect(screen.getByText('81-100')).toBeInTheDocument();
    });
  });

  describe('editing functionality', () => {
    it('shows Edit Thresholds button when loaded', async () => {
      vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);

      render(<SeverityThresholds />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /edit thresholds/i })).toBeInTheDocument();
      });
    });

    it('enters edit mode when Edit Thresholds is clicked', async () => {
      vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);
      const user = userEvent.setup();

      render(<SeverityThresholds />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /edit thresholds/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /edit thresholds/i }));

      // Should show input fields
      expect(screen.getByTestId('threshold-input-low')).toBeInTheDocument();
      expect(screen.getByTestId('threshold-input-medium')).toBeInTheDocument();
      expect(screen.getByTestId('threshold-input-high')).toBeInTheDocument();

      // Should show Save and Reset buttons
      expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /reset/i })).toBeInTheDocument();
    });

    it('shows correct initial values in edit inputs', async () => {
      vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);
      const user = userEvent.setup();

      render(<SeverityThresholds />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /edit thresholds/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /edit thresholds/i }));

      expect(screen.getByTestId('threshold-input-low')).toHaveValue(29);
      expect(screen.getByTestId('threshold-input-medium')).toHaveValue(59);
      expect(screen.getByTestId('threshold-input-high')).toHaveValue(84);
    });

    it('updates ranges dynamically when thresholds are changed', async () => {
      vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);

      render(<SeverityThresholds />);

      // Wait for data to load and table to render
      await waitFor(() => {
        expect(screen.getByRole('table')).toBeInTheDocument();
      });

      // Click the edit button
      fireEvent.click(screen.getByRole('button', { name: /edit thresholds/i }));

      // Wait for edit mode to be active
      await waitFor(() => {
        expect(screen.getByTestId('threshold-input-low')).toBeInTheDocument();
      });

      // Change the low threshold value
      const lowInput = screen.getByTestId('threshold-input-low');
      fireEvent.change(lowInput, { target: { value: '25' } });

      // Should show updated range text in table (0-25 for low)
      await waitFor(() => {
        expect(screen.getByText('0-25')).toBeInTheDocument();
      });
      // Should show updated range for medium (26-59)
      expect(screen.getByText('26-59')).toBeInTheDocument();
    });

    it('resets to original values when Reset is clicked', async () => {
      vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);
      const user = userEvent.setup();

      render(<SeverityThresholds />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /edit thresholds/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /edit thresholds/i }));

      const lowInput = screen.getByTestId('threshold-input-low');
      await user.clear(lowInput);
      await user.type(lowInput, '25');

      await user.click(screen.getByRole('button', { name: /reset/i }));

      // Should exit edit mode
      expect(screen.queryByTestId('threshold-input-low')).not.toBeInTheDocument();

      // Should show original values
      expect(screen.getByText('0-29')).toBeInTheDocument();
    });

    it('validates that low_max is less than medium_max', async () => {
      vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);
      const user = userEvent.setup();

      render(<SeverityThresholds />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /edit thresholds/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /edit thresholds/i }));

      // Set low_max higher than medium_max
      const lowInput = screen.getByTestId('threshold-input-low');
      await user.clear(lowInput);
      await user.type(lowInput, '65');

      await waitFor(() => {
        expect(screen.getByText(/Low max must be less than Medium max/i)).toBeInTheDocument();
      });

      // Save button should be disabled due to validation error
      expect(screen.getByRole('button', { name: /save/i })).toBeDisabled();
    });

    it('validates that medium_max is less than high_max', async () => {
      vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);
      const user = userEvent.setup();

      render(<SeverityThresholds />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /edit thresholds/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /edit thresholds/i }));

      // Set medium_max higher than high_max
      const mediumInput = screen.getByTestId('threshold-input-medium');
      await user.clear(mediumInput);
      await user.type(mediumInput, '90');

      await waitFor(() => {
        expect(screen.getByText(/Medium max must be less than High max/i)).toBeInTheDocument();
      });
    });

    it('validates boundary values', async () => {
      vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);
      const user = userEvent.setup();

      render(<SeverityThresholds />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /edit thresholds/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /edit thresholds/i }));

      // Set low_max to 0 (invalid - should be >= 1)
      const lowInput = screen.getByTestId('threshold-input-low');
      fireEvent.change(lowInput, { target: { value: '0' } });

      // Use getAllByText since error appears in both summary and inline
      await waitFor(() => {
        const errorMessages = screen.getAllByText(/Low max must be between 1 and 98/i);
        expect(errorMessages.length).toBeGreaterThan(0);
      });
    });

    it('saves thresholds successfully', async () => {
      const updatedConfig = {
        ...mockSeverityConfig,
        thresholds: {
          low_max: 25,
          medium_max: 59,
          high_max: 84,
        },
        definitions: mockSeverityConfig.definitions.map((d) => {
          if (d.severity === 'low') return { ...d, max_score: 25 };
          if (d.severity === 'medium') return { ...d, min_score: 26 };
          return d;
        }),
      };

      vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);
      vi.mocked(api.updateSeverityThresholds).mockResolvedValue(updatedConfig);

      render(<SeverityThresholds />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /edit thresholds/i })).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: /edit thresholds/i }));

      await waitFor(() => {
        expect(screen.getByTestId('threshold-input-low')).toBeInTheDocument();
      });

      const lowInput = screen.getByTestId('threshold-input-low');
      fireEvent.change(lowInput, { target: { value: '25' } });

      fireEvent.click(screen.getByRole('button', { name: /save/i }));

      await waitFor(() => {
        expect(api.updateSeverityThresholds).toHaveBeenCalledWith({
          low_max: 25,
          medium_max: 59,
          high_max: 84,
        });
      });

      // Should show success message
      await waitFor(() => {
        expect(screen.getByText(/saved successfully/i)).toBeInTheDocument();
      });

      // Should exit edit mode
      expect(screen.queryByTestId('threshold-input-low')).not.toBeInTheDocument();
    });

    it('displays error when save fails', async () => {
      vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);
      vi.mocked(api.updateSeverityThresholds).mockRejectedValue(new Error('Save failed'));

      render(<SeverityThresholds />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /edit thresholds/i })).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: /edit thresholds/i }));

      await waitFor(() => {
        expect(screen.getByTestId('threshold-input-low')).toBeInTheDocument();
      });

      const lowInput = screen.getByTestId('threshold-input-low');
      fireEvent.change(lowInput, { target: { value: '25' } });

      fireEvent.click(screen.getByRole('button', { name: /save/i }));

      await waitFor(() => {
        expect(screen.getByText(/Failed to save severity thresholds/i)).toBeInTheDocument();
      });
    });

    it('disables Save button when no changes made', async () => {
      vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);
      const user = userEvent.setup();

      render(<SeverityThresholds />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /edit thresholds/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /edit thresholds/i }));

      // Save button should be disabled since no changes were made
      expect(screen.getByRole('button', { name: /save/i })).toBeDisabled();
    });

    it('shows Saving... text while saving', async () => {
      vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);
      vi.mocked(api.updateSeverityThresholds).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(<SeverityThresholds />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /edit thresholds/i })).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: /edit thresholds/i }));

      await waitFor(() => {
        expect(screen.getByTestId('threshold-input-low')).toBeInTheDocument();
      });

      const lowInput = screen.getByTestId('threshold-input-low');
      fireEvent.change(lowInput, { target: { value: '25' } });

      fireEvent.click(screen.getByRole('button', { name: /save/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /saving/i })).toBeInTheDocument();
      });
    });

    it('does not show Edit button during loading', () => {
      vi.mocked(api.fetchSeverityConfig).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(<SeverityThresholds />);

      expect(screen.queryByRole('button', { name: /edit thresholds/i })).not.toBeInTheDocument();
    });

    it('does not show Edit button when error occurs', async () => {
      vi.mocked(api.fetchSeverityConfig).mockRejectedValue(new Error('Network error'));

      render(<SeverityThresholds />);

      await waitFor(() => {
        expect(screen.getByText(/Failed to load severity thresholds/i)).toBeInTheDocument();
      });

      expect(screen.queryByRole('button', { name: /edit thresholds/i })).not.toBeInTheDocument();
    });
  });
});
