import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import ThreatDetectionBanner from './ThreatDetectionBanner';

import type { ThreatDetection, ThreatSummary } from '../../types/threat';

// Helper to create a mock threat detection
function createThreatDetection(
  overrides: Partial<ThreatDetection> = {}
): ThreatDetection {
  return {
    id: 1,
    threat_type: 'gun',
    confidence: 0.95,
    severity: 'critical',
    camera_id: 'front_door',
    event_id: 123,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

// Helper to create a mock threat summary
function createThreatSummary(
  threats: ThreatDetection[] = [],
  overrides: Partial<ThreatSummary> = {}
): ThreatSummary {
  const severities = threats.map((t) => t.severity);
  const maxSeverity = severities.length > 0
    ? severities.reduce((max, current) => {
        const order = { critical: 0, high: 1, medium: 2, low: 3 };
        return order[current] < order[max] ? current : max;
      })
    : null;

  return {
    hasActiveThreats: threats.length > 0,
    totalThreats: threats.length,
    maxSeverity,
    threats,
    criticalCount: threats.filter((t) => t.severity === 'critical').length,
    highCount: threats.filter((t) => t.severity === 'high').length,
    mediumCount: threats.filter((t) => t.severity === 'medium').length,
    latestThreat: threats[0] ?? null,
    threatTypes: [...new Set(threats.map((t) => t.threat_type))],
    affectedCameras: [...new Set(threats.filter((t) => t.camera_id).map((t) => t.camera_id!))],
    ...overrides,
  };
}

describe('ThreatDetectionBanner', () => {
  describe('rendering when no threats', () => {
    it('renders nothing when threatSummary is null', () => {
      const { container } = render(<ThreatDetectionBanner threatSummary={null} />);
      expect(container.firstChild).toBeNull();
    });

    it('renders nothing when threatSummary is undefined', () => {
      const { container } = render(<ThreatDetectionBanner threatSummary={undefined} />);
      expect(container.firstChild).toBeNull();
    });

    it('renders nothing when hasActiveThreats is false', () => {
      const summary = createThreatSummary([]);
      const { container } = render(<ThreatDetectionBanner threatSummary={summary} />);
      expect(container.firstChild).toBeNull();
    });
  });

  describe('rendering with critical threats', () => {
    it('renders critical severity banner for gun detection', () => {
      const threat = createThreatDetection({ threat_type: 'gun', severity: 'critical' });
      const summary = createThreatSummary([threat]);

      render(<ThreatDetectionBanner threatSummary={summary} />);

      expect(screen.getByTestId('threat-detection-banner')).toBeInTheDocument();
      expect(screen.getByText(/THREAT DETECTED/i)).toBeInTheDocument();
      expect(screen.getByText(/Firearm/i)).toBeInTheDocument();
    });

    it('shows critical styling for critical severity', () => {
      const threat = createThreatDetection({ severity: 'critical' });
      const summary = createThreatSummary([threat]);

      render(<ThreatDetectionBanner threatSummary={summary} />);

      const banner = screen.getByTestId('threat-detection-banner');
      expect(banner).toHaveClass('border-red-500');
    });

    it('applies animation class for critical severity', () => {
      const threat = createThreatDetection({ severity: 'critical' });
      const summary = createThreatSummary([threat]);

      render(<ThreatDetectionBanner threatSummary={summary} />);

      const banner = screen.getByTestId('threat-detection-banner');
      expect(banner).toHaveClass('motion-safe:animate-pulse');
    });
  });

  describe('rendering with high severity threats', () => {
    it('renders high severity banner for knife detection', () => {
      const threat = createThreatDetection({ threat_type: 'knife', severity: 'high' });
      const summary = createThreatSummary([threat]);

      render(<ThreatDetectionBanner threatSummary={summary} />);

      expect(screen.getByTestId('threat-detection-banner')).toBeInTheDocument();
      expect(screen.getByText(/Knife/i)).toBeInTheDocument();
    });

    it('shows high severity styling', () => {
      const threat = createThreatDetection({ severity: 'high' });
      const summary = createThreatSummary([threat]);

      render(<ThreatDetectionBanner threatSummary={summary} />);

      const banner = screen.getByTestId('threat-detection-banner');
      expect(banner).toHaveClass('border-orange-500');
    });
  });

  describe('rendering with multiple threats', () => {
    it('shows count of multiple threats', () => {
      const threats = [
        createThreatDetection({ id: 1, threat_type: 'gun' }),
        createThreatDetection({ id: 2, threat_type: 'knife', severity: 'high' }),
      ];
      const summary = createThreatSummary(threats);

      render(<ThreatDetectionBanner threatSummary={summary} />);

      expect(screen.getByText(/2 threats/i)).toBeInTheDocument();
    });

    it('shows most severe styling when mixed severities', () => {
      const threats = [
        createThreatDetection({ id: 1, severity: 'high' }),
        createThreatDetection({ id: 2, severity: 'critical' }),
        createThreatDetection({ id: 3, severity: 'medium' }),
      ];
      const summary = createThreatSummary(threats);

      render(<ThreatDetectionBanner threatSummary={summary} />);

      const banner = screen.getByTestId('threat-detection-banner');
      // Should use critical styling since it's the most severe
      expect(banner).toHaveClass('border-red-500');
    });

    it('lists all unique threat types', () => {
      const threats = [
        createThreatDetection({ id: 1, threat_type: 'gun' }),
        createThreatDetection({ id: 2, threat_type: 'knife', severity: 'high' }),
        createThreatDetection({ id: 3, threat_type: 'gun' }), // duplicate
      ];
      const summary = createThreatSummary(threats);

      render(<ThreatDetectionBanner threatSummary={summary} />);

      expect(screen.getByText(/Firearm/i)).toBeInTheDocument();
      expect(screen.getByText(/Knife/i)).toBeInTheDocument();
    });
  });

  describe('camera information', () => {
    it('shows camera name when single camera affected', () => {
      const threat = createThreatDetection({ camera_id: 'front_door' });
      const summary = createThreatSummary([threat]);

      render(<ThreatDetectionBanner threatSummary={summary} />);

      expect(screen.getByText(/front_door/i)).toBeInTheDocument();
    });

    it('shows count when multiple cameras affected', () => {
      const threats = [
        createThreatDetection({ id: 1, camera_id: 'front_door' }),
        createThreatDetection({ id: 2, camera_id: 'back_yard', severity: 'high' }),
      ];
      const summary = createThreatSummary(threats);

      render(<ThreatDetectionBanner threatSummary={summary} />);

      expect(screen.getByText(/2 cameras/i)).toBeInTheDocument();
    });
  });

  describe('click interactions', () => {
    it('calls onClick when banner is clicked', async () => {
      const user = userEvent.setup();
      const onClick = vi.fn();
      const threat = createThreatDetection();
      const summary = createThreatSummary([threat]);

      render(<ThreatDetectionBanner threatSummary={summary} onClick={onClick} />);

      await user.click(screen.getByTestId('threat-detection-banner'));
      expect(onClick).toHaveBeenCalledTimes(1);
    });

    it('calls onViewEvent with latest event ID when view button clicked', async () => {
      const user = userEvent.setup();
      const onViewEvent = vi.fn();
      const threat = createThreatDetection({ event_id: 456 });
      const summary = createThreatSummary([threat]);

      render(<ThreatDetectionBanner threatSummary={summary} onViewEvent={onViewEvent} />);

      const viewButton = screen.getByRole('button', { name: /view/i });
      await user.click(viewButton);
      expect(onViewEvent).toHaveBeenCalledWith(456);
    });

    it('does not propagate click event to parent when view button clicked', async () => {
      const user = userEvent.setup();
      const onClick = vi.fn();
      const onViewEvent = vi.fn();
      const threat = createThreatDetection({ event_id: 789 });
      const summary = createThreatSummary([threat]);

      render(
        <ThreatDetectionBanner
          threatSummary={summary}
          onClick={onClick}
          onViewEvent={onViewEvent}
        />
      );

      const viewButton = screen.getByRole('button', { name: /view/i });
      await user.click(viewButton);
      expect(onViewEvent).toHaveBeenCalled();
      expect(onClick).not.toHaveBeenCalled();
    });
  });

  describe('dismissible behavior', () => {
    it('shows dismiss button when onDismiss is provided', () => {
      const onDismiss = vi.fn();
      const threat = createThreatDetection();
      const summary = createThreatSummary([threat]);

      render(<ThreatDetectionBanner threatSummary={summary} onDismiss={onDismiss} />);

      expect(screen.getByRole('button', { name: /dismiss/i })).toBeInTheDocument();
    });

    it('hides dismiss button when onDismiss is not provided', () => {
      const threat = createThreatDetection();
      const summary = createThreatSummary([threat]);

      render(<ThreatDetectionBanner threatSummary={summary} />);

      expect(screen.queryByRole('button', { name: /dismiss/i })).not.toBeInTheDocument();
    });

    it('calls onDismiss when dismiss button is clicked', async () => {
      const user = userEvent.setup();
      const onDismiss = vi.fn();
      const threat = createThreatDetection();
      const summary = createThreatSummary([threat]);

      render(<ThreatDetectionBanner threatSummary={summary} onDismiss={onDismiss} />);

      await user.click(screen.getByRole('button', { name: /dismiss/i }));
      expect(onDismiss).toHaveBeenCalledTimes(1);
    });
  });

  describe('compact mode', () => {
    it('renders compact version when compact prop is true', () => {
      const threat = createThreatDetection();
      const summary = createThreatSummary([threat]);

      render(<ThreatDetectionBanner threatSummary={summary} compact />);

      const banner = screen.getByTestId('threat-detection-banner');
      expect(banner).toHaveClass('py-2'); // Compact has smaller padding
    });

    it('renders full version by default', () => {
      const threat = createThreatDetection();
      const summary = createThreatSummary([threat]);

      render(<ThreatDetectionBanner threatSummary={summary} />);

      const banner = screen.getByTestId('threat-detection-banner');
      expect(banner).toHaveClass('py-3'); // Full has larger padding
    });
  });

  describe('accessibility', () => {
    it('has role="alert" for screen readers', () => {
      const threat = createThreatDetection();
      const summary = createThreatSummary([threat]);

      render(<ThreatDetectionBanner threatSummary={summary} />);

      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('has aria-live="assertive" for critical threats', () => {
      const threat = createThreatDetection({ severity: 'critical' });
      const summary = createThreatSummary([threat]);

      render(<ThreatDetectionBanner threatSummary={summary} />);

      expect(screen.getByRole('alert')).toHaveAttribute('aria-live', 'assertive');
    });

    it('has aria-live="polite" for non-critical threats', () => {
      const threat = createThreatDetection({ severity: 'medium' });
      const summary = createThreatSummary([threat]);

      render(<ThreatDetectionBanner threatSummary={summary} />);

      expect(screen.getByRole('alert')).toHaveAttribute('aria-live', 'polite');
    });

    it('clickable banner has proper keyboard navigation', async () => {
      const user = userEvent.setup();
      const onClick = vi.fn();
      const threat = createThreatDetection();
      const summary = createThreatSummary([threat]);

      render(<ThreatDetectionBanner threatSummary={summary} onClick={onClick} />);

      const banner = screen.getByTestId('threat-detection-banner');
      banner.focus();
      await user.keyboard('{Enter}');
      expect(onClick).toHaveBeenCalledTimes(1);
    });
  });

  describe('className prop', () => {
    it('applies additional className', () => {
      const threat = createThreatDetection();
      const summary = createThreatSummary([threat]);

      render(<ThreatDetectionBanner threatSummary={summary} className="custom-class" />);

      const banner = screen.getByTestId('threat-detection-banner');
      expect(banner).toHaveClass('custom-class');
    });

    it('merges with default classes', () => {
      const threat = createThreatDetection();
      const summary = createThreatSummary([threat]);

      render(<ThreatDetectionBanner threatSummary={summary} className="mt-4" />);

      const banner = screen.getByTestId('threat-detection-banner');
      expect(banner).toHaveClass('mt-4', 'rounded-lg', 'border-2');
    });
  });

  describe('confidence display', () => {
    it('shows confidence percentage for single threat', () => {
      const threat = createThreatDetection({ confidence: 0.92 });
      const summary = createThreatSummary([threat]);

      render(<ThreatDetectionBanner threatSummary={summary} showConfidence />);

      expect(screen.getByText(/92%/)).toBeInTheDocument();
    });

    it('hides confidence when showConfidence is false', () => {
      const threat = createThreatDetection({ confidence: 0.92 });
      const summary = createThreatSummary([threat]);

      render(<ThreatDetectionBanner threatSummary={summary} showConfidence={false} />);

      expect(screen.queryByText(/92%/)).not.toBeInTheDocument();
    });
  });
});
