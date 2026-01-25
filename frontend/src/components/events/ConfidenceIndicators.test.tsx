import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import ConfidenceIndicators from './ConfidenceIndicators';

import type { ConfidenceFactors } from '../../types/risk-analysis';

describe('ConfidenceIndicators', () => {
  describe('rendering', () => {
    it('renders nothing when confidenceFactors is null', () => {
      const { container } = render(<ConfidenceIndicators confidenceFactors={null} />);
      expect(container.firstChild).toBeNull();
    });

    it('renders nothing when confidenceFactors is undefined', () => {
      const { container } = render(<ConfidenceIndicators confidenceFactors={undefined} />);
      expect(container.firstChild).toBeNull();
    });

    it('has correct test id', () => {
      const factors: ConfidenceFactors = {
        detection_quality: 'good',
        weather_impact: 'none',
        enrichment_coverage: 'full',
      };
      render(<ConfidenceIndicators confidenceFactors={factors} />);
      expect(screen.getByTestId('confidence-indicators')).toBeInTheDocument();
    });
  });

  describe('detailed mode (default)', () => {
    it('renders section header', () => {
      const factors: ConfidenceFactors = {
        detection_quality: 'good',
        weather_impact: 'none',
        enrichment_coverage: 'full',
      };
      render(<ConfidenceIndicators confidenceFactors={factors} />);
      expect(screen.getByText('Analysis Confidence')).toBeInTheDocument();
    });

    it('renders all three indicators', () => {
      const factors: ConfidenceFactors = {
        detection_quality: 'good',
        weather_impact: 'none',
        enrichment_coverage: 'full',
      };
      render(<ConfidenceIndicators confidenceFactors={factors} />);
      expect(screen.getAllByTestId('confidence-indicator')).toHaveLength(3);
    });

    it('displays detection quality label', () => {
      const factors: ConfidenceFactors = {
        detection_quality: 'good',
        weather_impact: 'none',
        enrichment_coverage: 'full',
      };
      render(<ConfidenceIndicators confidenceFactors={factors} />);
      expect(screen.getByText('Detection Quality')).toBeInTheDocument();
    });

    it('displays weather impact label', () => {
      const factors: ConfidenceFactors = {
        detection_quality: 'good',
        weather_impact: 'none',
        enrichment_coverage: 'full',
      };
      render(<ConfidenceIndicators confidenceFactors={factors} />);
      expect(screen.getByText('Weather Impact')).toBeInTheDocument();
    });

    it('displays enrichment coverage label', () => {
      const factors: ConfidenceFactors = {
        detection_quality: 'good',
        weather_impact: 'none',
        enrichment_coverage: 'full',
      };
      render(<ConfidenceIndicators confidenceFactors={factors} />);
      expect(screen.getByText('Enrichment Coverage')).toBeInTheDocument();
    });
  });

  describe('inline mode', () => {
    it('renders indicators in inline mode', () => {
      const factors: ConfidenceFactors = {
        detection_quality: 'good',
        weather_impact: 'none',
        enrichment_coverage: 'full',
      };
      render(<ConfidenceIndicators confidenceFactors={factors} mode="inline" />);
      expect(screen.getAllByTestId('confidence-indicator')).toHaveLength(3);
    });

    it('does not render section header in inline mode', () => {
      const factors: ConfidenceFactors = {
        detection_quality: 'good',
        weather_impact: 'none',
        enrichment_coverage: 'full',
      };
      render(<ConfidenceIndicators confidenceFactors={factors} mode="inline" />);
      expect(screen.queryByText('Analysis Confidence')).not.toBeInTheDocument();
    });
  });

  describe('detection quality values', () => {
    it('displays good detection quality', () => {
      const factors: ConfidenceFactors = {
        detection_quality: 'good',
        weather_impact: 'none',
        enrichment_coverage: 'full',
      };
      render(<ConfidenceIndicators confidenceFactors={factors} />);
      expect(screen.getByText('Good')).toBeInTheDocument();
    });

    it('displays fair detection quality', () => {
      const factors: ConfidenceFactors = {
        detection_quality: 'fair',
        weather_impact: 'none',
        enrichment_coverage: 'full',
      };
      render(<ConfidenceIndicators confidenceFactors={factors} />);
      expect(screen.getByText('Fair')).toBeInTheDocument();
    });

    it('displays poor detection quality', () => {
      const factors: ConfidenceFactors = {
        detection_quality: 'poor',
        weather_impact: 'none',
        enrichment_coverage: 'full',
      };
      render(<ConfidenceIndicators confidenceFactors={factors} />);
      expect(screen.getByText('Poor')).toBeInTheDocument();
    });
  });

  describe('weather impact values', () => {
    it('displays none weather impact', () => {
      const factors: ConfidenceFactors = {
        detection_quality: 'good',
        weather_impact: 'none',
        enrichment_coverage: 'full',
      };
      render(<ConfidenceIndicators confidenceFactors={factors} />);
      expect(screen.getByText('None')).toBeInTheDocument();
    });

    it('displays minor weather impact', () => {
      const factors: ConfidenceFactors = {
        detection_quality: 'good',
        weather_impact: 'minor',
        enrichment_coverage: 'full',
      };
      render(<ConfidenceIndicators confidenceFactors={factors} />);
      expect(screen.getByText('Minor')).toBeInTheDocument();
    });

    it('displays significant weather impact', () => {
      const factors: ConfidenceFactors = {
        detection_quality: 'good',
        weather_impact: 'significant',
        enrichment_coverage: 'full',
      };
      render(<ConfidenceIndicators confidenceFactors={factors} />);
      expect(screen.getByText('Significant')).toBeInTheDocument();
    });
  });

  describe('enrichment coverage values', () => {
    it('displays full enrichment coverage', () => {
      const factors: ConfidenceFactors = {
        detection_quality: 'good',
        weather_impact: 'none',
        enrichment_coverage: 'full',
      };
      render(<ConfidenceIndicators confidenceFactors={factors} />);
      expect(screen.getByText('Full')).toBeInTheDocument();
    });

    it('displays partial enrichment coverage', () => {
      const factors: ConfidenceFactors = {
        detection_quality: 'good',
        weather_impact: 'none',
        enrichment_coverage: 'partial',
      };
      render(<ConfidenceIndicators confidenceFactors={factors} />);
      expect(screen.getByText('Partial')).toBeInTheDocument();
    });

    it('displays minimal enrichment coverage', () => {
      const factors: ConfidenceFactors = {
        detection_quality: 'good',
        weather_impact: 'none',
        enrichment_coverage: 'minimal',
      };
      render(<ConfidenceIndicators confidenceFactors={factors} />);
      expect(screen.getByText('Minimal')).toBeInTheDocument();
    });
  });

  describe('mixed values', () => {
    it('displays mixed confidence factors', () => {
      const factors: ConfidenceFactors = {
        detection_quality: 'fair',
        weather_impact: 'minor',
        enrichment_coverage: 'partial',
      };
      render(<ConfidenceIndicators confidenceFactors={factors} />);
      expect(screen.getByText('Fair')).toBeInTheDocument();
      expect(screen.getByText('Minor')).toBeInTheDocument();
      expect(screen.getByText('Partial')).toBeInTheDocument();
    });

    it('displays worst-case confidence factors', () => {
      const factors: ConfidenceFactors = {
        detection_quality: 'poor',
        weather_impact: 'significant',
        enrichment_coverage: 'minimal',
      };
      render(<ConfidenceIndicators confidenceFactors={factors} />);
      expect(screen.getByText('Poor')).toBeInTheDocument();
      expect(screen.getByText('Significant')).toBeInTheDocument();
      expect(screen.getByText('Minimal')).toBeInTheDocument();
    });
  });

  describe('styling', () => {
    it('applies custom className', () => {
      const factors: ConfidenceFactors = {
        detection_quality: 'good',
        weather_impact: 'none',
        enrichment_coverage: 'full',
      };
      render(<ConfidenceIndicators confidenceFactors={factors} className="custom-class" />);
      expect(screen.getByTestId('confidence-indicators')).toHaveClass('custom-class');
    });
  });
});
