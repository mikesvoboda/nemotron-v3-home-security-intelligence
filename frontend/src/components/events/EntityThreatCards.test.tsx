import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import EntityThreatCards from './EntityThreatCards';

import type { RiskEntity } from '../../types/risk-analysis';

describe('EntityThreatCards', () => {
  describe('rendering', () => {
    it('renders nothing when entities is null', () => {
      const { container } = render(<EntityThreatCards entities={null} />);
      expect(container.firstChild).toBeNull();
    });

    it('renders nothing when entities is undefined', () => {
      const { container } = render(<EntityThreatCards entities={undefined} />);
      expect(container.firstChild).toBeNull();
    });

    it('renders nothing when entities is empty array', () => {
      const { container } = render(<EntityThreatCards entities={[]} />);
      expect(container.firstChild).toBeNull();
    });

    it('renders the section header', () => {
      const entities: RiskEntity[] = [
        { type: 'person', description: 'Unknown individual', threat_level: 'medium' },
      ];
      render(<EntityThreatCards entities={entities} />);
      expect(screen.getByText('Identified Entities')).toBeInTheDocument();
    });

    it('has correct test id', () => {
      const entities: RiskEntity[] = [
        { type: 'person', description: 'Test', threat_level: 'low' },
      ];
      render(<EntityThreatCards entities={entities} />);
      expect(screen.getByTestId('entity-threat-cards')).toBeInTheDocument();
    });
  });

  describe('entity cards', () => {
    it('renders one entity card', () => {
      const entities: RiskEntity[] = [
        { type: 'person', description: 'Unknown individual', threat_level: 'medium' },
      ];
      render(<EntityThreatCards entities={entities} />);
      expect(screen.getAllByTestId('entity-card')).toHaveLength(1);
    });

    it('renders multiple entity cards', () => {
      const entities: RiskEntity[] = [
        { type: 'person', description: 'Unknown individual', threat_level: 'medium' },
        { type: 'vehicle', description: 'Unmarked van', threat_level: 'low' },
        { type: 'package', description: 'Suspicious package', threat_level: 'high' },
      ];
      render(<EntityThreatCards entities={entities} />);
      expect(screen.getAllByTestId('entity-card')).toHaveLength(3);
    });

    it('displays entity type', () => {
      const entities: RiskEntity[] = [
        { type: 'person', description: 'Unknown individual', threat_level: 'medium' },
      ];
      render(<EntityThreatCards entities={entities} />);
      expect(screen.getByText('Person')).toBeInTheDocument();
    });

    it('displays entity description', () => {
      const entities: RiskEntity[] = [
        { type: 'person', description: 'Unknown individual near entrance', threat_level: 'medium' },
      ];
      render(<EntityThreatCards entities={entities} />);
      expect(screen.getByText('Unknown individual near entrance')).toBeInTheDocument();
    });
  });

  describe('threat level display', () => {
    it('displays low threat level badge', () => {
      const entities: RiskEntity[] = [
        { type: 'person', description: 'Delivery person', threat_level: 'low' },
      ];
      render(<EntityThreatCards entities={entities} />);
      expect(screen.getByText('Low')).toBeInTheDocument();
    });

    it('displays medium threat level badge', () => {
      const entities: RiskEntity[] = [
        { type: 'person', description: 'Unknown individual', threat_level: 'medium' },
      ];
      render(<EntityThreatCards entities={entities} />);
      expect(screen.getByText('Medium')).toBeInTheDocument();
    });

    it('displays high threat level badge', () => {
      const entities: RiskEntity[] = [
        { type: 'person', description: 'Armed individual', threat_level: 'high' },
      ];
      render(<EntityThreatCards entities={entities} />);
      expect(screen.getByText('High')).toBeInTheDocument();
    });
  });

  describe('entity type formatting', () => {
    it('capitalizes entity type', () => {
      const entities: RiskEntity[] = [
        { type: 'vehicle', description: 'Test', threat_level: 'low' },
      ];
      render(<EntityThreatCards entities={entities} />);
      expect(screen.getByText('Vehicle')).toBeInTheDocument();
    });

    it('handles multi-word types', () => {
      const entities: RiskEntity[] = [
        { type: 'delivery_person', description: 'Test', threat_level: 'low' },
      ];
      render(<EntityThreatCards entities={entities} />);
      expect(screen.getByText('Delivery Person')).toBeInTheDocument();
    });
  });

  describe('styling', () => {
    it('applies custom className', () => {
      const entities: RiskEntity[] = [
        { type: 'person', description: 'Test', threat_level: 'low' },
      ];
      render(<EntityThreatCards entities={entities} className="custom-class" />);
      expect(screen.getByTestId('entity-threat-cards')).toHaveClass('custom-class');
    });
  });
});
