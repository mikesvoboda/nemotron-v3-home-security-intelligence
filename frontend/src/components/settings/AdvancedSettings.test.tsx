import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AdvancedSettings from './AdvancedSettings';
import * as api from '../../services/api';

// Mock the API module
vi.mock('../../services/api');

describe('AdvancedSettings', () => {
  const mockSeverityData: api.SeverityMetadataResponse = {
    definitions: [
      {
        severity: 'low',
        label: 'Low',
        description: 'Routine activity, no concern',
        color: '#22c55e',
        priority: 3,
        min_score: 0,
        max_score: 29,
      },
      {
        severity: 'medium',
        label: 'Medium',
        description: 'Notable activity, worth reviewing',
        color: '#eab308',
        priority: 2,
        min_score: 30,
        max_score: 59,
      },
      {
        severity: 'high',
        label: 'High',
        description: 'Concerning activity, review soon',
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

  describe('Severity Thresholds Card', () => {
    it('renders severity thresholds section title', async () => {
      vi.mocked(api.fetchSeverityMetadata).mockResolvedValue(mockSeverityData);

      render(<AdvancedSettings />);

      await waitFor(() => {
        expect(screen.getByText('Severity Thresholds')).toBeInTheDocument();
      });
    });

    it('shows loading skeleton while fetching data', () => {
      vi.mocked(api.fetchSeverityMetadata).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(<AdvancedSettings />);

      // Check for skeleton loading elements
      const skeletons = document.querySelectorAll('.skeleton');
      expect(skeletons.length).toBeGreaterThan(0);
    });

    it('displays all severity level definitions after loading', async () => {
      vi.mocked(api.fetchSeverityMetadata).mockResolvedValue(mockSeverityData);

      render(<AdvancedSettings />);

      await waitFor(() => {
        // Use getAllByText since severity labels appear in both the bar and cards
        expect(screen.getAllByText('Low').length).toBeGreaterThanOrEqual(1);
      });

      // Each severity level appears multiple times (in bar and in definition cards)
      expect(screen.getAllByText('Medium').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('High').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('Critical').length).toBeGreaterThanOrEqual(1);
    });

    it('displays severity descriptions', async () => {
      vi.mocked(api.fetchSeverityMetadata).mockResolvedValue(mockSeverityData);

      render(<AdvancedSettings />);

      await waitFor(() => {
        expect(screen.getByText('Routine activity, no concern')).toBeInTheDocument();
      });

      expect(screen.getByText('Notable activity, worth reviewing')).toBeInTheDocument();
      expect(screen.getByText('Concerning activity, review soon')).toBeInTheDocument();
      expect(screen.getByText('Immediate attention required')).toBeInTheDocument();
    });

    it('displays severity score ranges', async () => {
      vi.mocked(api.fetchSeverityMetadata).mockResolvedValue(mockSeverityData);

      render(<AdvancedSettings />);

      await waitFor(() => {
        expect(screen.getByText('0 - 29')).toBeInTheDocument();
      });

      expect(screen.getByText('30 - 59')).toBeInTheDocument();
      expect(screen.getByText('60 - 84')).toBeInTheDocument();
      expect(screen.getByText('85 - 100')).toBeInTheDocument();
    });

    it('displays info banner about risk score classification', async () => {
      vi.mocked(api.fetchSeverityMetadata).mockResolvedValue(mockSeverityData);

      render(<AdvancedSettings />);

      await waitFor(() => {
        expect(screen.getByText('Risk Score Classification')).toBeInTheDocument();
      });

      expect(
        screen.getByText(/Events are classified by risk score \(0-100\) into severity levels/i)
      ).toBeInTheDocument();
    });

    it('displays configuration note about environment variables', async () => {
      vi.mocked(api.fetchSeverityMetadata).mockResolvedValue(mockSeverityData);

      render(<AdvancedSettings />);

      await waitFor(() => {
        expect(
          screen.getByText(/Severity thresholds are configured via environment variables/i)
        ).toBeInTheDocument();
      });
    });
  });

  describe('Fast Path Detection Card', () => {
    it('renders fast path detection section title', async () => {
      vi.mocked(api.fetchSeverityMetadata).mockResolvedValue(mockSeverityData);

      render(<AdvancedSettings />);

      await waitFor(() => {
        expect(screen.getByText('Fast Path Detection')).toBeInTheDocument();
      });
    });

    it('displays priority analysis mode info', async () => {
      vi.mocked(api.fetchSeverityMetadata).mockResolvedValue(mockSeverityData);

      render(<AdvancedSettings />);

      await waitFor(() => {
        expect(screen.getByText('Priority Analysis Mode')).toBeInTheDocument();
      });
    });

    it('displays confidence threshold value', async () => {
      vi.mocked(api.fetchSeverityMetadata).mockResolvedValue(mockSeverityData);

      render(<AdvancedSettings />);

      await waitFor(() => {
        expect(screen.getByText('Confidence Threshold')).toBeInTheDocument();
      });

      expect(screen.getByText('90%')).toBeInTheDocument();
    });

    it('displays fast path object types', async () => {
      vi.mocked(api.fetchSeverityMetadata).mockResolvedValue(mockSeverityData);

      render(<AdvancedSettings />);

      await waitFor(() => {
        expect(screen.getByText('Fast Path Object Types')).toBeInTheDocument();
      });

      expect(screen.getByText('person')).toBeInTheDocument();
    });
  });

  describe('Video Processing Card', () => {
    it('renders video processing section title', async () => {
      vi.mocked(api.fetchSeverityMetadata).mockResolvedValue(mockSeverityData);

      render(<AdvancedSettings />);

      await waitFor(() => {
        expect(screen.getByText('Video Processing')).toBeInTheDocument();
      });
    });

    it('displays frame extraction interval', async () => {
      vi.mocked(api.fetchSeverityMetadata).mockResolvedValue(mockSeverityData);

      render(<AdvancedSettings />);

      await waitFor(() => {
        expect(screen.getByText('Frame Extraction Interval')).toBeInTheDocument();
      });

      expect(screen.getByText('2.0s')).toBeInTheDocument();
    });

    it('displays pre-roll duration', async () => {
      vi.mocked(api.fetchSeverityMetadata).mockResolvedValue(mockSeverityData);

      render(<AdvancedSettings />);

      await waitFor(() => {
        expect(screen.getByText('Pre-Roll Duration')).toBeInTheDocument();
      });
    });

    it('displays post-roll duration', async () => {
      vi.mocked(api.fetchSeverityMetadata).mockResolvedValue(mockSeverityData);

      render(<AdvancedSettings />);

      await waitFor(() => {
        expect(screen.getByText('Post-Roll Duration')).toBeInTheDocument();
      });
    });
  });

  describe('GPU Monitoring Card', () => {
    it('renders GPU monitoring section title', async () => {
      vi.mocked(api.fetchSeverityMetadata).mockResolvedValue(mockSeverityData);

      render(<AdvancedSettings />);

      await waitFor(() => {
        expect(screen.getByText('GPU Monitoring')).toBeInTheDocument();
      });
    });

    it('displays stats polling interval', async () => {
      vi.mocked(api.fetchSeverityMetadata).mockResolvedValue(mockSeverityData);

      render(<AdvancedSettings />);

      await waitFor(() => {
        expect(screen.getByText('Stats Polling Interval')).toBeInTheDocument();
      });

      expect(screen.getByText('5.0s')).toBeInTheDocument();
    });

    it('displays stats history duration', async () => {
      vi.mocked(api.fetchSeverityMetadata).mockResolvedValue(mockSeverityData);

      render(<AdvancedSettings />);

      await waitFor(() => {
        expect(screen.getByText('Stats History Duration')).toBeInTheDocument();
      });

      expect(screen.getByText('60 min')).toBeInTheDocument();
    });
  });

  describe('Error Handling', () => {
    it('displays error message when fetch fails', async () => {
      vi.mocked(api.fetchSeverityMetadata).mockRejectedValue(new Error('Network error'));

      render(<AdvancedSettings />);

      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });
    });

    it('displays generic error for non-Error objects', async () => {
      vi.mocked(api.fetchSeverityMetadata).mockRejectedValue('Unknown error');

      render(<AdvancedSettings />);

      await waitFor(() => {
        expect(screen.getByText('Failed to load severity settings')).toBeInTheDocument();
      });
    });

    it('does not show severity definitions when error occurs', async () => {
      vi.mocked(api.fetchSeverityMetadata).mockRejectedValue(new Error('Network error'));

      render(<AdvancedSettings />);

      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });

      // Severity levels section header should not be visible
      expect(screen.queryByText('Severity Levels')).not.toBeInTheDocument();
    });
  });

  describe('Custom Thresholds', () => {
    it('displays custom threshold values', async () => {
      const customData: api.SeverityMetadataResponse = {
        definitions: [
          {
            severity: 'low',
            label: 'Low',
            description: 'Routine activity, no concern',
            color: '#22c55e',
            priority: 3,
            min_score: 0,
            max_score: 19,
          },
          {
            severity: 'medium',
            label: 'Medium',
            description: 'Notable activity, worth reviewing',
            color: '#eab308',
            priority: 2,
            min_score: 20,
            max_score: 49,
          },
          {
            severity: 'high',
            label: 'High',
            description: 'Concerning activity, review soon',
            color: '#f97316',
            priority: 1,
            min_score: 50,
            max_score: 79,
          },
          {
            severity: 'critical',
            label: 'Critical',
            description: 'Immediate attention required',
            color: '#ef4444',
            priority: 0,
            min_score: 80,
            max_score: 100,
          },
        ],
        thresholds: {
          low_max: 19,
          medium_max: 49,
          high_max: 79,
        },
      };

      vi.mocked(api.fetchSeverityMetadata).mockResolvedValue(customData);

      render(<AdvancedSettings />);

      await waitFor(() => {
        expect(screen.getByText('0 - 19')).toBeInTheDocument();
      });

      expect(screen.getByText('20 - 49')).toBeInTheDocument();
      expect(screen.getByText('50 - 79')).toBeInTheDocument();
      expect(screen.getByText('80 - 100')).toBeInTheDocument();
    });
  });

  describe('Props', () => {
    it('applies custom className', async () => {
      vi.mocked(api.fetchSeverityMetadata).mockResolvedValue(mockSeverityData);

      const { container } = render(<AdvancedSettings className="custom-test-class" />);

      await waitFor(() => {
        expect(screen.getByText('Severity Thresholds')).toBeInTheDocument();
      });

      // The wrapper div should have the custom class
      expect(container.firstChild).toHaveClass('custom-test-class');
    });
  });

  describe('Severity Bar Visualization', () => {
    it('renders visual severity bar', async () => {
      vi.mocked(api.fetchSeverityMetadata).mockResolvedValue(mockSeverityData);

      render(<AdvancedSettings />);

      await waitFor(() => {
        // Check that "Risk Score" label is rendered in the bar
        expect(screen.getByText('Risk Score')).toBeInTheDocument();
      });
    });

    it('displays threshold markers', async () => {
      vi.mocked(api.fetchSeverityMetadata).mockResolvedValue(mockSeverityData);

      render(<AdvancedSettings />);

      await waitFor(() => {
        // Threshold marker values should be displayed
        expect(screen.getByText('29')).toBeInTheDocument();
      });

      expect(screen.getByText('59')).toBeInTheDocument();
      expect(screen.getByText('84')).toBeInTheDocument();
    });
  });
});
