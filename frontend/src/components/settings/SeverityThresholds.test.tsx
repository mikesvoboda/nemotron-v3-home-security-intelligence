import { render, screen, waitFor } from '@testing-library/react';
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

      await waitFor(() => {
        expect(screen.getByText('Risk Score Thresholds')).toBeInTheDocument();
      });

      // Should still render the table but with no data rows
      expect(screen.getByRole('table')).toBeInTheDocument();
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
});
