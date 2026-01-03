import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import SeverityConfigPanel from './SeverityConfigPanel';
import * as api from '../../services/api';

// Mock the API module
vi.mock('../../services/api', () => ({
  fetchSeverityMetadata: vi.fn(),
}));

const mockSeverityMetadataResponse = {
  definitions: [
    {
      severity: 'low' as const,
      label: 'Low',
      description: 'Routine activity, no concern',
      color: '#22c55e',
      priority: 3,
      min_score: 0,
      max_score: 29,
    },
    {
      severity: 'medium' as const,
      label: 'Medium',
      description: 'Notable activity, worth reviewing',
      color: '#eab308',
      priority: 2,
      min_score: 30,
      max_score: 59,
    },
    {
      severity: 'high' as const,
      label: 'High',
      description: 'Concerning activity, review soon',
      color: '#f97316',
      priority: 1,
      min_score: 60,
      max_score: 84,
    },
    {
      severity: 'critical' as const,
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

describe('SeverityConfigPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows loading state initially', () => {
    vi.mocked(api.fetchSeverityMetadata).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );

    render(<SeverityConfigPanel />);

    expect(screen.getByTestId('severity-config-panel-loading')).toBeInTheDocument();
  });

  it('displays severity definitions after loading', async () => {
    vi.mocked(api.fetchSeverityMetadata).mockResolvedValue(mockSeverityMetadataResponse);

    render(<SeverityConfigPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('severity-config-panel')).toBeInTheDocument();
    });

    // Check all severity levels are displayed
    expect(screen.getByTestId('severity-row-low')).toBeInTheDocument();
    expect(screen.getByTestId('severity-row-medium')).toBeInTheDocument();
    expect(screen.getByTestId('severity-row-high')).toBeInTheDocument();
    expect(screen.getByTestId('severity-row-critical')).toBeInTheDocument();
  });

  it('displays correct labels for each severity level', async () => {
    vi.mocked(api.fetchSeverityMetadata).mockResolvedValue(mockSeverityMetadataResponse);

    render(<SeverityConfigPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('severity-config-panel')).toBeInTheDocument();
    });

    // Check labels
    expect(screen.getByTestId('severity-label-low')).toHaveTextContent('Low');
    expect(screen.getByTestId('severity-label-medium')).toHaveTextContent('Medium');
    expect(screen.getByTestId('severity-label-high')).toHaveTextContent('High');
    expect(screen.getByTestId('severity-label-critical')).toHaveTextContent('Critical');
  });

  it('displays descriptions for each severity level', async () => {
    vi.mocked(api.fetchSeverityMetadata).mockResolvedValue(mockSeverityMetadataResponse);

    render(<SeverityConfigPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('severity-config-panel')).toBeInTheDocument();
    });

    // Check descriptions
    expect(screen.getByTestId('severity-description-low')).toHaveTextContent(
      'Routine activity, no concern'
    );
    expect(screen.getByTestId('severity-description-critical')).toHaveTextContent(
      'Immediate attention required'
    );
  });

  it('displays score ranges for each severity level', async () => {
    vi.mocked(api.fetchSeverityMetadata).mockResolvedValue(mockSeverityMetadataResponse);

    render(<SeverityConfigPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('severity-config-panel')).toBeInTheDocument();
    });

    // Check score ranges
    expect(screen.getByTestId('severity-range-low')).toHaveTextContent('0 - 29');
    expect(screen.getByTestId('severity-range-medium')).toHaveTextContent('30 - 59');
    expect(screen.getByTestId('severity-range-high')).toHaveTextContent('60 - 84');
    expect(screen.getByTestId('severity-range-critical')).toHaveTextContent('85 - 100');
  });

  it('displays color indicators for each severity level', async () => {
    vi.mocked(api.fetchSeverityMetadata).mockResolvedValue(mockSeverityMetadataResponse);

    render(<SeverityConfigPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('severity-config-panel')).toBeInTheDocument();
    });

    // Check color indicators exist
    expect(screen.getByTestId('severity-color-low')).toBeInTheDocument();
    expect(screen.getByTestId('severity-color-medium')).toBeInTheDocument();
    expect(screen.getByTestId('severity-color-high')).toBeInTheDocument();
    expect(screen.getByTestId('severity-color-critical')).toBeInTheDocument();
  });

  it('displays error state when API call fails', async () => {
    vi.mocked(api.fetchSeverityMetadata).mockRejectedValue(new Error('Network error'));

    render(<SeverityConfigPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('severity-config-panel-error')).toBeInTheDocument();
    });

    expect(screen.getByText(/Failed to load severity configuration/i)).toBeInTheDocument();
  });

  it('displays threshold configuration section', async () => {
    vi.mocked(api.fetchSeverityMetadata).mockResolvedValue(mockSeverityMetadataResponse);

    render(<SeverityConfigPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('severity-config-panel')).toBeInTheDocument();
    });

    // Check threshold values are displayed
    expect(screen.getByTestId('threshold-low-max')).toHaveTextContent('29');
    expect(screen.getByTestId('threshold-medium-max')).toHaveTextContent('59');
    expect(screen.getByTestId('threshold-high-max')).toHaveTextContent('84');
  });

  it('shows panel title correctly', async () => {
    vi.mocked(api.fetchSeverityMetadata).mockResolvedValue(mockSeverityMetadataResponse);

    render(<SeverityConfigPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('severity-config-panel')).toBeInTheDocument();
    });

    expect(screen.getByText('Severity Levels')).toBeInTheDocument();
  });

  it('handles empty definitions gracefully', async () => {
    vi.mocked(api.fetchSeverityMetadata).mockResolvedValue({
      definitions: [],
      thresholds: {
        low_max: 29,
        medium_max: 59,
        high_max: 84,
      },
    });

    render(<SeverityConfigPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('severity-config-panel')).toBeInTheDocument();
    });

    expect(screen.getByText(/No severity definitions configured/i)).toBeInTheDocument();
  });

  it('displays severity levels sorted by priority', async () => {
    vi.mocked(api.fetchSeverityMetadata).mockResolvedValue(mockSeverityMetadataResponse);

    render(<SeverityConfigPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('severity-config-panel')).toBeInTheDocument();
    });

    const severityRows = screen.getAllByTestId(/^severity-row-/);
    expect(severityRows).toHaveLength(4);

    // Critical (priority 0) should come first
    expect(severityRows[0]).toHaveAttribute('data-testid', 'severity-row-critical');
    expect(severityRows[1]).toHaveAttribute('data-testid', 'severity-row-high');
    expect(severityRows[2]).toHaveAttribute('data-testid', 'severity-row-medium');
    expect(severityRows[3]).toHaveAttribute('data-testid', 'severity-row-low');
  });

  it('applies correct color styling to severity badges', async () => {
    vi.mocked(api.fetchSeverityMetadata).mockResolvedValue(mockSeverityMetadataResponse);

    render(<SeverityConfigPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('severity-config-panel')).toBeInTheDocument();
    });

    // Color indicators should have inline style with background color (browser converts hex to rgb)
    const lowColor = screen.getByTestId('severity-color-low');
    expect(lowColor).toHaveAttribute('style', expect.stringContaining('rgb(34, 197, 94)'));

    const criticalColor = screen.getByTestId('severity-color-critical');
    expect(criticalColor).toHaveAttribute('style', expect.stringContaining('rgb(239, 68, 68)'));
  });

  it('shows visual risk score scale', async () => {
    vi.mocked(api.fetchSeverityMetadata).mockResolvedValue(mockSeverityMetadataResponse);

    render(<SeverityConfigPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('severity-config-panel')).toBeInTheDocument();
    });

    // Should show a visual scale at the bottom
    expect(screen.getByTestId('severity-scale')).toBeInTheDocument();
  });
});
