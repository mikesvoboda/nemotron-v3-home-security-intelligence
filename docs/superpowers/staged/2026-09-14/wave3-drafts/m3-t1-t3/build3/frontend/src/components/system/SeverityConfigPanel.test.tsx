import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import SeverityConfigPanel from './SeverityConfigPanel';

import type { SeverityDefinitionResponse, SeverityMetadataResponse } from '../../types/generated';

// Mock data generators
function createMockSeverityDefinition(
  severity: 'low' | 'medium' | 'high' | 'critical',
  label: string,
  description: string,
  color: string,
  priority: number,
  minScore: number,
  maxScore: number
): SeverityDefinitionResponse {
  return {
    severity,
    label,
    description,
    color,
    priority,
    min_score: minScore,
    max_score: maxScore,
  };
}

function createMockSeverityMetadata(): SeverityMetadataResponse {
  return {
    definitions: [
      createMockSeverityDefinition(
        'low',
        'Low',
        'Routine activity, no concern',
        '#22c55e',
        3,
        0,
        29
      ),
      createMockSeverityDefinition(
        'medium',
        'Medium',
        'Notable activity, worth reviewing',
        '#eab308',
        2,
        30,
        59
      ),
      createMockSeverityDefinition(
        'high',
        'High',
        'Concerning activity, review soon',
        '#f97316',
        1,
        60,
        84
      ),
      createMockSeverityDefinition(
        'critical',
        'Critical',
        'Immediate attention required',
        '#ef4444',
        0,
        85,
        100
      ),
    ],
    thresholds: {
      low_max: 29,
      medium_max: 59,
      high_max: 84,
    },
  };
}

const mockSeverityMetadata = createMockSeverityMetadata();

describe('SeverityConfigPanel', () => {
  describe('rendering', () => {
    it('renders the component with title', () => {
      render(<SeverityConfigPanel data={mockSeverityMetadata} loading={false} error={null} />);

      expect(screen.getByTestId('severity-config-panel')).toBeInTheDocument();
      expect(screen.getByText('Severity Configuration')).toBeInTheDocument();
    });

    it('renders all four severity levels', () => {
      render(<SeverityConfigPanel data={mockSeverityMetadata} loading={false} error={null} />);

      expect(screen.getByTestId('severity-level-low')).toBeInTheDocument();
      expect(screen.getByTestId('severity-level-medium')).toBeInTheDocument();
      expect(screen.getByTestId('severity-level-high')).toBeInTheDocument();
      expect(screen.getByTestId('severity-level-critical')).toBeInTheDocument();
    });
  });

  describe('severity labels', () => {
    it('displays severity labels', () => {
      render(<SeverityConfigPanel data={mockSeverityMetadata} loading={false} error={null} />);

      expect(screen.getByText('Low')).toBeInTheDocument();
      expect(screen.getByText('Medium')).toBeInTheDocument();
      expect(screen.getByText('High')).toBeInTheDocument();
      expect(screen.getByText('Critical')).toBeInTheDocument();
    });
  });

  describe('severity descriptions', () => {
    it('displays descriptions for each severity level', () => {
      render(<SeverityConfigPanel data={mockSeverityMetadata} loading={false} error={null} />);

      expect(screen.getByText('Routine activity, no concern')).toBeInTheDocument();
      expect(screen.getByText('Notable activity, worth reviewing')).toBeInTheDocument();
      expect(screen.getByText('Concerning activity, review soon')).toBeInTheDocument();
      expect(screen.getByText('Immediate attention required')).toBeInTheDocument();
    });
  });

  describe('risk score ranges', () => {
    it('displays risk score ranges for each severity level', () => {
      render(<SeverityConfigPanel data={mockSeverityMetadata} loading={false} error={null} />);

      expect(screen.getByTestId('score-range-low')).toHaveTextContent('0-29');
      expect(screen.getByTestId('score-range-medium')).toHaveTextContent('30-59');
      expect(screen.getByTestId('score-range-high')).toHaveTextContent('60-84');
      expect(screen.getByTestId('score-range-critical')).toHaveTextContent('85-100');
    });
  });

  describe('color display', () => {
    it('displays color indicators for each severity level', () => {
      render(<SeverityConfigPanel data={mockSeverityMetadata} loading={false} error={null} />);

      const lowColor = screen.getByTestId('color-indicator-low');
      const mediumColor = screen.getByTestId('color-indicator-medium');
      const highColor = screen.getByTestId('color-indicator-high');
      const criticalColor = screen.getByTestId('color-indicator-critical');

      // Check that color indicators exist
      expect(lowColor).toBeInTheDocument();
      expect(mediumColor).toBeInTheDocument();
      expect(highColor).toBeInTheDocument();
      expect(criticalColor).toBeInTheDocument();
    });
  });

  describe('thresholds display', () => {
    it('displays threshold values', () => {
      render(<SeverityConfigPanel data={mockSeverityMetadata} loading={false} error={null} />);

      expect(screen.getByTestId('thresholds-section')).toBeInTheDocument();
      expect(screen.getByTestId('threshold-low-max')).toHaveTextContent('29');
      expect(screen.getByTestId('threshold-medium-max')).toHaveTextContent('59');
      expect(screen.getByTestId('threshold-high-max')).toHaveTextContent('84');
    });
  });

  describe('loading state', () => {
    it('displays loading skeleton when loading is true', () => {
      render(<SeverityConfigPanel data={null} loading={true} error={null} />);

      expect(screen.getByTestId('severity-config-panel-loading')).toBeInTheDocument();
    });

    it('does not display severity levels when loading', () => {
      render(<SeverityConfigPanel data={null} loading={true} error={null} />);

      expect(screen.queryByTestId('severity-level-low')).not.toBeInTheDocument();
      expect(screen.queryByTestId('severity-level-critical')).not.toBeInTheDocument();
    });
  });

  describe('error state', () => {
    it('displays error message when error is present', () => {
      render(
        <SeverityConfigPanel
          data={null}
          loading={false}
          error="Failed to fetch severity metadata"
        />
      );

      expect(screen.getByTestId('severity-config-panel-error')).toBeInTheDocument();
      expect(screen.getByText(/Failed to fetch severity metadata/i)).toBeInTheDocument();
    });
  });

  describe('read-only indicator', () => {
    it('displays read-only indicator', () => {
      render(<SeverityConfigPanel data={mockSeverityMetadata} loading={false} error={null} />);

      // Should indicate that this is read-only configuration
      expect(screen.getByText(/Read-only/i)).toBeInTheDocument();
    });
  });

  describe('priority ordering', () => {
    it('displays severity levels in correct order (critical first)', () => {
      render(<SeverityConfigPanel data={mockSeverityMetadata} loading={false} error={null} />);

      // Get all severity level elements
      const severityLevels = screen.getAllByTestId(/severity-level-/);

      // Verify order: critical (priority 0) should be first
      expect(severityLevels[0]).toHaveAttribute('data-testid', 'severity-level-critical');
      expect(severityLevels[1]).toHaveAttribute('data-testid', 'severity-level-high');
      expect(severityLevels[2]).toHaveAttribute('data-testid', 'severity-level-medium');
      expect(severityLevels[3]).toHaveAttribute('data-testid', 'severity-level-low');
    });
  });

  describe('empty data handling', () => {
    it('handles empty definitions array gracefully', () => {
      const emptyData: SeverityMetadataResponse = {
        definitions: [],
        thresholds: {
          low_max: 29,
          medium_max: 59,
          high_max: 84,
        },
      };

      render(<SeverityConfigPanel data={emptyData} loading={false} error={null} />);

      expect(screen.getByTestId('severity-config-panel')).toBeInTheDocument();
      expect(screen.getByText(/No severity levels/i)).toBeInTheDocument();
    });
  });

  describe('visual consistency', () => {
    it('renders consistent card styling', () => {
      render(<SeverityConfigPanel data={mockSeverityMetadata} loading={false} error={null} />);

      const panel = screen.getByTestId('severity-config-panel');
      expect(panel).toBeInTheDocument();
    });
  });
});
