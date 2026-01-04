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
      // There are multiple "Low" texts (visual bar and table), so check for multiple
      expect(screen.getAllByText('Low').length).toBeGreaterThanOrEqual(1);
    });

    expect(screen.getAllByText('Medium').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('High').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Critical').length).toBeGreaterThanOrEqual(1);
  });

  it('displays correct score ranges in the table', async () => {
    vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);

    render(<SeverityThresholds />);

    await waitFor(() => {
      // Score ranges appear in the table
      expect(screen.getAllByText('0-29').length).toBeGreaterThanOrEqual(1);
    });

    expect(screen.getAllByText('30-59').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('60-84').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('85-100').length).toBeGreaterThanOrEqual(1);
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

  it('applies custom className', async () => {
    vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);

    render(<SeverityThresholds className="custom-test-class" />);

    await waitFor(() => {
      expect(screen.getByText('Risk Score Thresholds')).toBeInTheDocument();
    });

    // The Card component should have the custom class
    const card = screen.getByTestId('severity-thresholds-card');
    expect(card).toHaveClass('custom-test-class');
  });

  describe('editable thresholds', () => {
    it('renders threshold sliders', async () => {
      vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);

      render(<SeverityThresholds />);

      await waitFor(() => {
        expect(screen.getByTestId('low-max-slider')).toBeInTheDocument();
      });

      expect(screen.getByTestId('medium-max-slider')).toBeInTheDocument();
      expect(screen.getByTestId('high-max-slider')).toBeInTheDocument();
    });

    it('displays current threshold values', async () => {
      vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);

      render(<SeverityThresholds />);

      await waitFor(() => {
        expect(screen.getByText('29')).toBeInTheDocument();
      });

      expect(screen.getByText('59')).toBeInTheDocument();
      expect(screen.getByText('84')).toBeInTheDocument();
    });

    it('enables save button when thresholds are modified', async () => {
      vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);

      render(<SeverityThresholds />);

      await waitFor(() => {
        expect(screen.getByTestId('low-max-slider')).toBeInTheDocument();
      });

      // Save button should be disabled initially
      const saveButton = screen.getByTestId('save-thresholds-button');
      expect(saveButton).toBeDisabled();

      // Change threshold value
      const lowMaxSlider = screen.getByTestId('low-max-slider');
      fireEvent.change(lowMaxSlider, { target: { value: '25' } });

      // Save button should now be enabled
      expect(saveButton).not.toBeDisabled();
    });

    it('calls updateSeverityThresholds on save', async () => {
      vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);
      vi.mocked(api.updateSeverityThresholds).mockResolvedValue({
        ...mockSeverityConfig,
        thresholds: { low_max: 25, medium_max: 59, high_max: 84 },
      });

      const user = userEvent.setup();
      render(<SeverityThresholds />);

      await waitFor(() => {
        expect(screen.getByTestId('low-max-slider')).toBeInTheDocument();
      });

      // Change threshold value
      const lowMaxSlider = screen.getByTestId('low-max-slider');
      fireEvent.change(lowMaxSlider, { target: { value: '25' } });

      // Click save
      const saveButton = screen.getByTestId('save-thresholds-button');
      await user.click(saveButton);

      await waitFor(() => {
        expect(api.updateSeverityThresholds).toHaveBeenCalledWith({
          low_max: 25,
          medium_max: 59,
          high_max: 84,
        });
      });
    });

    it('shows success message after save', async () => {
      vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);
      vi.mocked(api.updateSeverityThresholds).mockResolvedValue({
        ...mockSeverityConfig,
        thresholds: { low_max: 25, medium_max: 59, high_max: 84 },
      });

      const user = userEvent.setup();
      render(<SeverityThresholds />);

      await waitFor(() => {
        expect(screen.getByTestId('low-max-slider')).toBeInTheDocument();
      });

      // Change and save
      const lowMaxSlider = screen.getByTestId('low-max-slider');
      fireEvent.change(lowMaxSlider, { target: { value: '25' } });

      const saveButton = screen.getByTestId('save-thresholds-button');
      await user.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText('Thresholds saved successfully!')).toBeInTheDocument();
      });
    });

    it('shows error message on save failure', async () => {
      vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);
      vi.mocked(api.updateSeverityThresholds).mockRejectedValue(new Error('Save failed'));

      const user = userEvent.setup();
      render(<SeverityThresholds />);

      await waitFor(() => {
        expect(screen.getByTestId('low-max-slider')).toBeInTheDocument();
      });

      // Change and save
      const lowMaxSlider = screen.getByTestId('low-max-slider');
      fireEvent.change(lowMaxSlider, { target: { value: '25' } });

      const saveButton = screen.getByTestId('save-thresholds-button');
      await user.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText('Save failed')).toBeInTheDocument();
      });
    });

    it('resets changes when reset button is clicked', async () => {
      vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);

      const user = userEvent.setup();
      render(<SeverityThresholds />);

      await waitFor(() => {
        expect(screen.getByTestId('low-max-slider')).toBeInTheDocument();
      });

      // Change threshold value
      const lowMaxSlider = screen.getByTestId('low-max-slider');
      fireEvent.change(lowMaxSlider, { target: { value: '25' } });

      // Verify change
      expect((lowMaxSlider as HTMLInputElement).value).toBe('25');

      // Click reset
      const resetButton = screen.getByTestId('reset-thresholds-button');
      await user.click(resetButton);

      // Value should be reset to original
      expect((lowMaxSlider as HTMLInputElement).value).toBe('29');
    });
  });

  describe('validation', () => {
    it('shows validation error when low_max >= medium_max', async () => {
      vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);

      render(<SeverityThresholds />);

      await waitFor(() => {
        expect(screen.getByTestId('low-max-slider')).toBeInTheDocument();
      });

      // Set low_max higher than medium_max
      const lowMaxSlider = screen.getByTestId('low-max-slider');
      fireEvent.change(lowMaxSlider, { target: { value: '60' } });

      await waitFor(() => {
        expect(screen.getByText('Low max must be less than Medium max')).toBeInTheDocument();
      });

      // Save button should be disabled
      const saveButton = screen.getByTestId('save-thresholds-button');
      expect(saveButton).toBeDisabled();
    });

    it('shows validation error when medium_max >= high_max', async () => {
      vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);

      render(<SeverityThresholds />);

      await waitFor(() => {
        expect(screen.getByTestId('medium-max-slider')).toBeInTheDocument();
      });

      // Set medium_max higher than high_max
      const mediumMaxSlider = screen.getByTestId('medium-max-slider');
      fireEvent.change(mediumMaxSlider, { target: { value: '90' } });

      await waitFor(() => {
        expect(screen.getByText('Medium max must be less than High max')).toBeInTheDocument();
      });
    });
  });

  describe('visual range bar', () => {
    it('renders score distribution bar', async () => {
      vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);

      render(<SeverityThresholds />);

      await waitFor(() => {
        expect(screen.getByText('Score Distribution')).toBeInTheDocument();
      });
    });
  });

  describe('critical range display', () => {
    it('displays calculated critical range', async () => {
      vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);

      render(<SeverityThresholds />);

      await waitFor(() => {
        expect(screen.getByText('Critical Range')).toBeInTheDocument();
      });

      // With default high_max of 84, critical range should be 85-100
      // Appears in multiple places (display box and table)
      expect(screen.getAllByText('85-100').length).toBeGreaterThanOrEqual(1);
    });

    it('shows critical range updates when high_max changes', async () => {
      vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);

      render(<SeverityThresholds />);

      await waitFor(() => {
        expect(screen.getByTestId('high-max-slider')).toBeInTheDocument();
      });

      // Change high_max
      const highMaxSlider = screen.getByTestId('high-max-slider');
      fireEvent.change(highMaxSlider, { target: { value: '90' } });

      // Critical range should update to 91-100
      await waitFor(() => {
        expect(screen.getAllByText('91-100').length).toBeGreaterThanOrEqual(1);
      });
    });
  });

  describe('accessibility', () => {
    it('has proper aria-labels on sliders', async () => {
      vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);

      render(<SeverityThresholds />);

      await waitFor(() => {
        expect(screen.getByLabelText('Low severity maximum score')).toBeInTheDocument();
      });

      expect(screen.getByLabelText('Medium severity maximum score')).toBeInTheDocument();
      expect(screen.getByLabelText('High severity maximum score')).toBeInTheDocument();
    });

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
        expect(screen.getAllByText('0-20').length).toBeGreaterThanOrEqual(1);
      });

      expect(screen.getAllByText('21-50').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('51-80').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('81-100').length).toBeGreaterThanOrEqual(1);
    });
  });
});
