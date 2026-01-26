/**
 * Tests for BatchSettingsTooltips component
 *
 * @see NEM-3873 - Batch Config Validation
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import BatchSettingsTooltips, {
  BatchSettingsValidationDisplay,
  BatchSettingsLatencyPreview,
} from './BatchSettingsTooltips';

describe('BatchSettingsTooltips', () => {
  describe('BatchSettingsValidationDisplay', () => {
    it('renders nothing when no warnings or errors', () => {
      const { container } = render(
        <BatchSettingsValidationDisplay windowSeconds={90} idleTimeoutSeconds={30} />
      );

      expect(container.querySelector('[data-testid="batch-validation-warnings"]')).toBeNull();
      expect(container.querySelector('[data-testid="batch-validation-errors"]')).toBeNull();
    });

    it('displays warning when idle_timeout >= window', () => {
      render(
        <BatchSettingsValidationDisplay windowSeconds={60} idleTimeoutSeconds={90} />
      );

      expect(screen.getByText(/Idle timeout should be less than batch window/i)).toBeInTheDocument();
    });

    it('displays warning when window < 30s', () => {
      render(
        <BatchSettingsValidationDisplay windowSeconds={20} idleTimeoutSeconds={10} />
      );

      expect(screen.getByText(/under 30 seconds/i)).toBeInTheDocument();
    });

    it('displays warning when window > 180s', () => {
      render(
        <BatchSettingsValidationDisplay windowSeconds={200} idleTimeoutSeconds={60} />
      );

      expect(screen.getByText(/over 180 seconds/i)).toBeInTheDocument();
    });

    it('displays error when window is 0', () => {
      render(
        <BatchSettingsValidationDisplay windowSeconds={0} idleTimeoutSeconds={30} />
      );

      expect(screen.getByTestId('batch-validation-errors')).toBeInTheDocument();
    });

    it('displays multiple warnings', () => {
      render(
        <BatchSettingsValidationDisplay windowSeconds={20} idleTimeoutSeconds={25} />
      );

      // Both window < 30 and idle >= window warnings
      const warnings = screen.getByTestId('batch-validation-warnings');
      expect(warnings).toBeInTheDocument();
    });
  });

  describe('BatchSettingsLatencyPreview', () => {
    it('displays latency range for real-time preset', () => {
      render(<BatchSettingsLatencyPreview windowSeconds={30} idleTimeoutSeconds={10} />);

      // Should show 10-30s range
      expect(screen.getByText(/10.*30/)).toBeInTheDocument();
    });

    it('displays latency range for balanced preset', () => {
      render(<BatchSettingsLatencyPreview windowSeconds={90} idleTimeoutSeconds={30} />);

      // Should show 30-90s range
      expect(screen.getByText(/30.*90/)).toBeInTheDocument();
    });

    it('displays latency range for efficient preset', () => {
      render(<BatchSettingsLatencyPreview windowSeconds={180} idleTimeoutSeconds={60} />);

      // Should show 60-180s range
      expect(screen.getByText(/60.*180/)).toBeInTheDocument();
    });

    it('displays preset type description', () => {
      render(<BatchSettingsLatencyPreview windowSeconds={30} idleTimeoutSeconds={10} />);

      expect(screen.getByText(/Real-time/)).toBeInTheDocument();
    });

    it('displays Custom for non-preset values', () => {
      render(<BatchSettingsLatencyPreview windowSeconds={120} idleTimeoutSeconds={45} />);

      expect(screen.getByText(/Custom/)).toBeInTheDocument();
    });
  });

  describe('BatchSettingsTooltips (wrapper)', () => {
    it('renders all subcomponents', () => {
      render(<BatchSettingsTooltips windowSeconds={90} idleTimeoutSeconds={30} />);

      // Should have latency preview
      expect(screen.getByTestId('batch-latency-preview')).toBeInTheDocument();
    });

    it('shows warnings when present', () => {
      render(<BatchSettingsTooltips windowSeconds={20} idleTimeoutSeconds={10} />);

      expect(screen.getByTestId('batch-validation-warnings')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      render(
        <BatchSettingsTooltips
          windowSeconds={90}
          idleTimeoutSeconds={30}
          className="custom-class"
        />
      );

      const container = screen.getByTestId('batch-settings-tooltips');
      expect(container).toHaveClass('custom-class');
    });
  });
});
