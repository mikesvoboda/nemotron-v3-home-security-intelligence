import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import RiskFlagsPanel from './RiskFlagsPanel';

import type { RiskFlag } from '../../types/risk-analysis';

describe('RiskFlagsPanel', () => {
  describe('rendering', () => {
    it('renders nothing when flags is null', () => {
      const { container } = render(<RiskFlagsPanel flags={null} />);
      expect(container.firstChild).toBeNull();
    });

    it('renders nothing when flags is undefined', () => {
      const { container } = render(<RiskFlagsPanel flags={undefined} />);
      expect(container.firstChild).toBeNull();
    });

    it('renders nothing when flags is empty array', () => {
      const { container } = render(<RiskFlagsPanel flags={[]} />);
      expect(container.firstChild).toBeNull();
    });

    it('renders the section header', () => {
      const flags: RiskFlag[] = [
        { type: 'loitering', description: 'Stationary for 5+ minutes', severity: 'warning' },
      ];
      render(<RiskFlagsPanel flags={flags} />);
      expect(screen.getByText('Risk Flags')).toBeInTheDocument();
    });

    it('displays flag count badge', () => {
      const flags: RiskFlag[] = [
        { type: 'loitering', description: 'Test', severity: 'warning' },
        { type: 'nighttime', description: 'Test', severity: 'alert' },
      ];
      render(<RiskFlagsPanel flags={flags} />);
      expect(screen.getByText('2')).toBeInTheDocument();
    });

    it('has correct test id', () => {
      const flags: RiskFlag[] = [
        { type: 'loitering', description: 'Test', severity: 'warning' },
      ];
      render(<RiskFlagsPanel flags={flags} />);
      expect(screen.getByTestId('risk-flags-panel')).toBeInTheDocument();
    });
  });

  describe('flag items', () => {
    it('renders one flag item', () => {
      const flags: RiskFlag[] = [
        { type: 'loitering', description: 'Stationary for 5+ minutes', severity: 'warning' },
      ];
      render(<RiskFlagsPanel flags={flags} />);
      expect(screen.getAllByTestId('risk-flag-item')).toHaveLength(1);
    });

    it('renders multiple flag items', () => {
      const flags: RiskFlag[] = [
        { type: 'loitering', description: 'Test 1', severity: 'warning' },
        { type: 'nighttime', description: 'Test 2', severity: 'alert' },
        { type: 'weapon_detected', description: 'Test 3', severity: 'critical' },
      ];
      render(<RiskFlagsPanel flags={flags} />);
      expect(screen.getAllByTestId('risk-flag-item')).toHaveLength(3);
    });

    it('displays flag type formatted', () => {
      const flags: RiskFlag[] = [
        { type: 'loitering', description: 'Test', severity: 'warning' },
      ];
      render(<RiskFlagsPanel flags={flags} />);
      expect(screen.getByText('Loitering')).toBeInTheDocument();
    });

    it('displays flag description', () => {
      const flags: RiskFlag[] = [
        { type: 'loitering', description: 'Person stationary near entrance', severity: 'warning' },
      ];
      render(<RiskFlagsPanel flags={flags} />);
      expect(screen.getByText('Person stationary near entrance')).toBeInTheDocument();
    });
  });

  describe('severity display', () => {
    it('displays warning severity badge', () => {
      const flags: RiskFlag[] = [
        { type: 'loitering', description: 'Test', severity: 'warning' },
      ];
      render(<RiskFlagsPanel flags={flags} />);
      expect(screen.getByText('Warning')).toBeInTheDocument();
    });

    it('displays alert severity badge', () => {
      const flags: RiskFlag[] = [
        { type: 'nighttime', description: 'Test', severity: 'alert' },
      ];
      render(<RiskFlagsPanel flags={flags} />);
      expect(screen.getByText('Alert')).toBeInTheDocument();
    });

    it('displays critical severity badge', () => {
      const flags: RiskFlag[] = [
        { type: 'weapon_detected', description: 'Test', severity: 'critical' },
      ];
      render(<RiskFlagsPanel flags={flags} />);
      expect(screen.getByText('Critical')).toBeInTheDocument();
    });
  });

  describe('flag type formatting', () => {
    it('formats underscore-separated types', () => {
      const flags: RiskFlag[] = [
        { type: 'weapon_detected', description: 'Test', severity: 'critical' },
      ];
      render(<RiskFlagsPanel flags={flags} />);
      expect(screen.getByText('Weapon Detected')).toBeInTheDocument();
    });

    it('formats hyphen-separated types', () => {
      const flags: RiskFlag[] = [
        { type: 'late-night-activity', description: 'Test', severity: 'alert' },
      ];
      render(<RiskFlagsPanel flags={flags} />);
      expect(screen.getByText('Late Night Activity')).toBeInTheDocument();
    });
  });

  describe('sorting', () => {
    it('sorts flags by severity (critical first)', () => {
      const flags: RiskFlag[] = [
        { type: 'loitering', description: 'Warning test', severity: 'warning' },
        { type: 'weapon_detected', description: 'Critical test', severity: 'critical' },
        { type: 'nighttime', description: 'Alert test', severity: 'alert' },
      ];
      render(<RiskFlagsPanel flags={flags} />);

      const items = screen.getAllByTestId('risk-flag-item');
      expect(items[0]).toHaveTextContent('Critical test');
      expect(items[1]).toHaveTextContent('Alert test');
      expect(items[2]).toHaveTextContent('Warning test');
    });
  });

  describe('critical flag highlighting', () => {
    it('uses red header when critical flag present', () => {
      const flags: RiskFlag[] = [
        { type: 'weapon_detected', description: 'Test', severity: 'critical' },
      ];
      render(<RiskFlagsPanel flags={flags} />);
      const header = screen.getByText('Risk Flags');
      expect(header).toHaveClass('text-red-400');
    });

    it('uses gray header when no critical flags', () => {
      const flags: RiskFlag[] = [
        { type: 'loitering', description: 'Test', severity: 'warning' },
      ];
      render(<RiskFlagsPanel flags={flags} />);
      const header = screen.getByText('Risk Flags');
      expect(header).toHaveClass('text-gray-400');
    });
  });

  describe('styling', () => {
    it('applies custom className', () => {
      const flags: RiskFlag[] = [
        { type: 'loitering', description: 'Test', severity: 'warning' },
      ];
      render(<RiskFlagsPanel flags={flags} className="custom-class" />);
      expect(screen.getByTestId('risk-flags-panel')).toHaveClass('custom-class');
    });
  });
});
