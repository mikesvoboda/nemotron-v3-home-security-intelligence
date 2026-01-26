import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import RiskFactorsBreakdown from './RiskFactorsBreakdown';

import type { RiskEntity, RiskFlag, ConfidenceFactors } from '../../types/risk-analysis';

describe('RiskFactorsBreakdown', () => {
  // Sample test data
  const mockEntities: RiskEntity[] = [
    { type: 'person', description: 'Unknown individual near entrance', threat_level: 'medium' },
    { type: 'vehicle', description: 'Unrecognized sedan', threat_level: 'low' },
  ];

  const mockFlags: RiskFlag[] = [
    { type: 'loitering', description: 'Stationary for 5+ minutes', severity: 'warning' },
    { type: 'nighttime_activity', description: 'Activity after hours', severity: 'alert' },
  ];

  const mockConfidenceFactors: ConfidenceFactors = {
    detection_quality: 'good',
    weather_impact: 'none',
    enrichment_coverage: 'full',
  };

  const mockReasoning = 'Person detected near front entrance during evening hours with unidentified vehicle.';
  const mockRecommendedAction = 'Review camera footage and verify identity';

  describe('rendering', () => {
    it('renders nothing when no data is provided', () => {
      const { container } = render(<RiskFactorsBreakdown riskScore={50} />);
      expect(container.firstChild).toBeNull();
    });

    it('renders when only reasoning is provided', () => {
      render(<RiskFactorsBreakdown riskScore={50} reasoning={mockReasoning} />);
      expect(screen.getByTestId('risk-factors-breakdown')).toBeInTheDocument();
    });

    it('renders when only entities are provided', () => {
      render(<RiskFactorsBreakdown riskScore={50} entities={mockEntities} />);
      expect(screen.getByTestId('risk-factors-breakdown')).toBeInTheDocument();
    });

    it('renders when only flags are provided', () => {
      render(<RiskFactorsBreakdown riskScore={50} flags={mockFlags} />);
      expect(screen.getByTestId('risk-factors-breakdown')).toBeInTheDocument();
    });

    it('renders when only confidence factors are provided', () => {
      render(<RiskFactorsBreakdown riskScore={50} confidenceFactors={mockConfidenceFactors} />);
      expect(screen.getByTestId('risk-factors-breakdown')).toBeInTheDocument();
    });

    it('renders when only recommended action is provided', () => {
      render(<RiskFactorsBreakdown riskScore={50} recommendedAction={mockRecommendedAction} />);
      expect(screen.getByTestId('risk-factors-breakdown')).toBeInTheDocument();
    });

    it('renders nothing when reasoning is empty string', () => {
      const { container } = render(<RiskFactorsBreakdown riskScore={50} reasoning="" />);
      expect(container.firstChild).toBeNull();
    });

    it('renders nothing when reasoning is whitespace only', () => {
      const { container } = render(<RiskFactorsBreakdown riskScore={50} reasoning="   " />);
      expect(container.firstChild).toBeNull();
    });
  });

  describe('header display', () => {
    it('displays the section title', () => {
      render(<RiskFactorsBreakdown riskScore={50} entities={mockEntities} />);
      expect(screen.getByText('Risk Factors Breakdown')).toBeInTheDocument();
    });

    it('shows factor count in subtitle', () => {
      render(<RiskFactorsBreakdown riskScore={50} entities={mockEntities} flags={mockFlags} />);
      expect(screen.getByText('4 factors contributing to risk score')).toBeInTheDocument();
    });

    it('shows singular factor when only one', () => {
      const singleEntity: RiskEntity[] = [
        { type: 'person', description: 'Test', threat_level: 'low' },
      ];
      render(<RiskFactorsBreakdown riskScore={50} entities={singleEntity} />);
      expect(screen.getByText('1 factor contributing to risk score')).toBeInTheDocument();
    });

    it('shows generic message when only confidence factors present', () => {
      render(<RiskFactorsBreakdown riskScore={50} confidenceFactors={mockConfidenceFactors} />);
      expect(screen.getByText('Analysis details and confidence factors')).toBeInTheDocument();
    });
  });

  describe('collapsible behavior', () => {
    it('starts collapsed by default', () => {
      render(<RiskFactorsBreakdown riskScore={50} entities={mockEntities} />);
      expect(screen.queryByTestId('risk-factors-content')).not.toBeInTheDocument();
    });

    it('starts expanded when defaultExpanded is true', () => {
      render(
        <RiskFactorsBreakdown riskScore={50} entities={mockEntities} defaultExpanded={true} />
      );
      expect(screen.getByTestId('risk-factors-content')).toBeInTheDocument();
    });

    it('expands when toggle is clicked', async () => {
      const user = userEvent.setup();
      render(<RiskFactorsBreakdown riskScore={50} entities={mockEntities} />);

      await user.click(screen.getByTestId('risk-factors-toggle'));
      expect(screen.getByTestId('risk-factors-content')).toBeInTheDocument();
    });

    it('collapses when toggle is clicked again', async () => {
      const user = userEvent.setup();
      render(
        <RiskFactorsBreakdown riskScore={50} entities={mockEntities} defaultExpanded={true} />
      );

      await user.click(screen.getByTestId('risk-factors-toggle'));
      expect(screen.queryByTestId('risk-factors-content')).not.toBeInTheDocument();
    });

    it('has correct aria-expanded attribute', async () => {
      const user = userEvent.setup();
      render(<RiskFactorsBreakdown riskScore={50} entities={mockEntities} />);

      const toggle = screen.getByTestId('risk-factors-toggle');
      expect(toggle).toHaveAttribute('aria-expanded', 'false');

      await user.click(toggle);
      expect(toggle).toHaveAttribute('aria-expanded', 'true');
    });
  });

  describe('contribution pills when collapsed', () => {
    it('shows contribution pills when collapsed', () => {
      render(
        <RiskFactorsBreakdown
          riskScore={50}
          entities={mockEntities}
          flags={mockFlags}
          confidenceFactors={mockConfidenceFactors}
        />
      );
      expect(screen.getByTestId('contribution-pills')).toBeInTheDocument();
    });

    it('hides contribution pills when expanded', async () => {
      const user = userEvent.setup();
      render(
        <RiskFactorsBreakdown
          riskScore={50}
          entities={mockEntities}
          flags={mockFlags}
          confidenceFactors={mockConfidenceFactors}
        />
      );

      await user.click(screen.getByTestId('risk-factors-toggle'));
      expect(screen.queryByTestId('contribution-pills')).not.toBeInTheDocument();
    });
  });

  describe('expanded content', () => {
    it('renders contribution bars when expanded', async () => {
      const user = userEvent.setup();
      render(
        <RiskFactorsBreakdown
          riskScore={50}
          entities={mockEntities}
          flags={mockFlags}
          confidenceFactors={mockConfidenceFactors}
        />
      );

      await user.click(screen.getByTestId('risk-factors-toggle'));
      expect(screen.getByTestId('contribution-bars')).toBeInTheDocument();
    });

    it('renders reasoning section when expanded', async () => {
      const user = userEvent.setup();
      render(<RiskFactorsBreakdown riskScore={50} reasoning={mockReasoning} />);

      await user.click(screen.getByTestId('risk-factors-toggle'));
      expect(screen.getByTestId('reasoning-section')).toBeInTheDocument();
      expect(screen.getByText(mockReasoning)).toBeInTheDocument();
    });

    it('renders recommended action card when expanded', async () => {
      const user = userEvent.setup();
      render(
        <RiskFactorsBreakdown riskScore={50} recommendedAction={mockRecommendedAction} />
      );

      await user.click(screen.getByTestId('risk-factors-toggle'));
      expect(screen.getByTestId('recommended-action-card')).toBeInTheDocument();
    });

    it('renders risk flags panel when expanded', async () => {
      const user = userEvent.setup();
      render(<RiskFactorsBreakdown riskScore={50} flags={mockFlags} />);

      await user.click(screen.getByTestId('risk-factors-toggle'));
      expect(screen.getByTestId('risk-flags-panel')).toBeInTheDocument();
    });

    it('renders entity threat cards when expanded', async () => {
      const user = userEvent.setup();
      render(<RiskFactorsBreakdown riskScore={50} entities={mockEntities} />);

      await user.click(screen.getByTestId('risk-factors-toggle'));
      expect(screen.getByTestId('entity-threat-cards')).toBeInTheDocument();
    });

    it('renders confidence indicators when expanded', async () => {
      const user = userEvent.setup();
      render(<RiskFactorsBreakdown riskScore={50} confidenceFactors={mockConfidenceFactors} />);

      await user.click(screen.getByTestId('risk-factors-toggle'));
      expect(screen.getByTestId('confidence-indicators')).toBeInTheDocument();
    });
  });

  describe('contribution calculation', () => {
    it('shows contribution percentages that sum to 100', async () => {
      const user = userEvent.setup();
      render(
        <RiskFactorsBreakdown
          riskScore={50}
          entities={mockEntities}
          flags={mockFlags}
          confidenceFactors={mockConfidenceFactors}
        />
      );

      await user.click(screen.getByTestId('risk-factors-toggle'));

      // Check that all contribution bars exist
      expect(screen.getByTestId('contribution-bar-entities')).toBeInTheDocument();
      expect(screen.getByTestId('contribution-bar-risk-flags')).toBeInTheDocument();
      expect(screen.getByTestId('contribution-bar-analysis-quality')).toBeInTheDocument();
    });

    it('adjusts entity contribution based on threat levels', async () => {
      const user = userEvent.setup();
      const highThreatEntities: RiskEntity[] = [
        { type: 'weapon', description: 'Detected weapon', threat_level: 'high' },
      ];

      render(
        <RiskFactorsBreakdown
          riskScore={75}
          entities={highThreatEntities}
          confidenceFactors={mockConfidenceFactors}
        />
      );

      await user.click(screen.getByTestId('risk-factors-toggle'));
      expect(screen.getByTestId('contribution-bar-entities')).toBeInTheDocument();
    });

    it('adjusts flag contribution based on severity', async () => {
      const user = userEvent.setup();
      const criticalFlags: RiskFlag[] = [
        { type: 'weapon_detected', description: 'Weapon visible', severity: 'critical' },
      ];

      render(
        <RiskFactorsBreakdown
          riskScore={85}
          flags={criticalFlags}
          confidenceFactors={mockConfidenceFactors}
        />
      );

      await user.click(screen.getByTestId('risk-factors-toggle'));
      expect(screen.getByTestId('contribution-bar-risk-flags')).toBeInTheDocument();
    });
  });

  describe('risk level styling', () => {
    it('uses appropriate styling for low risk', () => {
      render(<RiskFactorsBreakdown riskScore={20} entities={mockEntities} />);
      expect(screen.getByTestId('risk-factors-breakdown')).toBeInTheDocument();
    });

    it('uses appropriate styling for medium risk', () => {
      render(<RiskFactorsBreakdown riskScore={45} entities={mockEntities} />);
      expect(screen.getByTestId('risk-factors-breakdown')).toBeInTheDocument();
    });

    it('uses appropriate styling for high risk', () => {
      render(<RiskFactorsBreakdown riskScore={75} entities={mockEntities} />);
      expect(screen.getByTestId('risk-factors-breakdown')).toBeInTheDocument();
    });

    it('uses appropriate styling for critical risk', () => {
      render(<RiskFactorsBreakdown riskScore={90} entities={mockEntities} />);
      expect(screen.getByTestId('risk-factors-breakdown')).toBeInTheDocument();
    });
  });

  describe('reviewed state', () => {
    it('passes isReviewed to RecommendedActionCard', async () => {
      const user = userEvent.setup();
      render(
        <RiskFactorsBreakdown
          riskScore={50}
          recommendedAction={mockRecommendedAction}
          isReviewed={true}
        />
      );

      await user.click(screen.getByTestId('risk-factors-toggle'));
      const actionCard = screen.getByTestId('recommended-action-card');
      // When reviewed, the card should have gray styling instead of amber
      expect(actionCard).toHaveClass('border-gray-600');
    });
  });

  describe('custom className', () => {
    it('applies custom className', () => {
      render(
        <RiskFactorsBreakdown
          riskScore={50}
          entities={mockEntities}
          className="custom-class"
        />
      );
      expect(screen.getByTestId('risk-factors-breakdown')).toHaveClass('custom-class');
    });
  });

  describe('all data combined', () => {
    it('renders all sections in correct order when expanded', () => {
      render(
        <RiskFactorsBreakdown
          riskScore={65}
          reasoning={mockReasoning}
          entities={mockEntities}
          flags={mockFlags}
          recommendedAction={mockRecommendedAction}
          confidenceFactors={mockConfidenceFactors}
          defaultExpanded={true}
        />
      );

      // Verify all sections are present
      expect(screen.getByTestId('contribution-bars')).toBeInTheDocument();
      expect(screen.getByTestId('recommended-action-card')).toBeInTheDocument();
      expect(screen.getByTestId('reasoning-section')).toBeInTheDocument();
      expect(screen.getByTestId('risk-flags-panel')).toBeInTheDocument();
      expect(screen.getByTestId('entity-threat-cards')).toBeInTheDocument();
      expect(screen.getByTestId('confidence-indicators')).toBeInTheDocument();
    });
  });
});
